import json

import pytest

from aimport.agent import (
    AutobidsifyClient,
    ClaudeClient,
    DatasetDraft,
    classify,
    client_from_env,
    draft_metadata,
)
from aimport.scrub import ScrubbedSeries

ENV_KEYS = ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "OLLAMA_BASE_URL", "DASHSCOPE_API_KEY", "AIMPORT_MODEL")


class Recorder:
    name = "recorder"

    def __init__(self, reply):
        self.reply, self.calls, self.users, self.systems, self.steps = reply, [], [], [], []

    def complete(self, system, user, step):
        self.calls.append(system + user)
        self.users.append(user)
        self.systems.append(system)
        self.steps.append(step)
        return self.reply


def ss(i, desc="[x] series", fields=None):
    return ScrubbedSeries(i, desc, "", "", fields or {})


def answer(idx=0, datatype="anat", suffix="T1w", entities=None, confidence=0.9, reason="r"):
    return {"series_idx": idx, "datatype": datatype, "suffix": suffix,
            "entities": entities or {}, "confidence": confidence, "reason": reason}


def test_payload_contains_only_scrubbed(schema):
    rec = Recorder('[{"series_idx":0,"datatype":"anat","suffix":"T1w","entities":{},"confidence":0.9,"reason":"MPRAGE"}]')
    classify([ScrubbedSeries(0, "[x] T1 MPRAGE", "", "", {"EchoTime": 0.003})], {}, rec, schema)
    assert "smith" not in rec.calls[0].lower()
    assert rec.steps == ["classify"]
    assert set(json.loads(rec.users[0])) == {"series"}
    assert "T1 MPRAGE" not in rec.systems[0] and "0.003" not in rec.systems[0]


def test_every_series_sent_with_heuristic(schema):
    rec = Recorder("[]")
    classify([ss(0), ss(1)], {0: ("anat", "T1w", {})}, rec, schema)
    sent = json.loads(rec.users[0])["series"]
    assert {s["series_idx"] for s in sent} == {0, 1}
    assert sent[0]["ezbids_guess"]["suffix"] == "T1w"


def test_invalid_answer_dropped(schema):
    rec = Recorder('[{"series_idx":0,"datatype":"anat","suffix":"bold","entities":{},"confidence":0.9,"reason":""}]')
    g = classify([ss(0)], {}, rec, schema)[0]
    assert g.datatype is None and g.reason == "agent answer not valid BIDS"


def test_missing_required_entity_rejected(schema):
    rec = Recorder(json.dumps([answer(0, "func", "bold", {})]))
    g = classify([ss(0)], {}, rec, schema)[0]
    assert g.datatype is None and g.reason == "agent answer not valid BIDS"


def test_required_entity_present_accepted(schema):
    rec = Recorder(json.dumps([answer(0, "func", "bold", {"task": "rest", "run": "1"}, 0.8, "rest fMRI")]))
    g = classify([ss(0)], {}, rec, schema)[0]
    assert (g.datatype, g.suffix, g.entities, g.confidence, g.reason) == (
        "func", "bold", {"task": "rest", "run": "1"}, 0.8, "rest fMRI")


def test_disallowed_entity_rejected(schema):
    rec = Recorder(json.dumps([answer(0, "anat", "T1w", {"direction": "AP"})]))
    assert classify([ss(0)], {}, rec, schema)[0].datatype is None


def test_abbreviated_entity_names_accepted(schema):
    rec = Recorder(json.dumps([answer(0, "anat", "T1w", {"acq": "mprage"})]))
    assert classify([ss(0)], {}, rec, schema)[0].entities == {"acquisition": "mprage"}


def test_bad_entity_value_rejected(schema):
    rec = Recorder(json.dumps([answer(0, "func", "bold", {"task": "re st/../x"})]))
    assert classify([ss(0)], {}, rec, schema)[0].datatype is None


def test_datatype_outside_phase1_rejected(schema):
    rec = Recorder(json.dumps([answer(0, "eeg", "eeg")]))
    assert classify([ss(0)], {}, rec, schema)[0].datatype is None


def test_confidence_clamped(schema):
    rec = Recorder(json.dumps([answer(0, confidence=7), answer(1, confidence=-2)]))
    g = classify([ss(0), ss(1)], {}, rec, schema)
    assert g[0].confidence == 1.0 and g[1].confidence == 0.0


def test_prose_and_fence_around_json(schema):
    body = json.dumps([answer(0)])
    for reply in (f"Here you go:\n```json\n{body}\n```\nDone.", f"Sure. {body} Hope it helps."):
        assert classify([ss(0)], {}, Recorder(reply), schema)[0].datatype == "anat"


def test_malformed_json_is_model_error(schema):
    g = classify([ss(0), ss(1)], {}, Recorder("not json at all"), schema)
    assert [x.reason for x in g] == ["model error: JSONDecodeError"] * 2
    assert all(x.datatype is None and x.confidence == 0 for x in g)


def test_unknown_idx_ignored_and_omitted_gets_no_answer(schema):
    rec = Recorder(json.dumps([answer(99), answer(0)]))
    g = classify([ss(0), ss(1)], {}, rec, schema)
    assert [x.series_idx for x in g] == [0, 1]
    assert g[0].datatype == "anat"
    assert g[1].datatype is None and g[1].confidence == 0 and g[1].reason == "no answer"


def test_no_client_is_not_an_error(schema):
    g = classify([ss(0)], {}, None, schema)
    assert g[0].datatype is None and g[0].reason == "no model configured"
    assert draft_metadata([ss(0)], None, set()) is None


def test_client_exception_is_not_an_error(schema):
    class Boom:
        name = "boom"

        def complete(self, s, u, step):
            raise TimeoutError()

    assert classify([ss(0)], {}, Boom(), schema)[0].reason == "model error: TimeoutError"
    assert draft_metadata([ss(0)], Boom(), set()) is None


def test_draft_metadata_redacts_reply():
    rec = Recorder('Some text {"name": "Smith lab dataset", "readme": "Scanned at Hospital X: 1 T1w."}')
    d = draft_metadata([ss(0)], rec, {"smith", "hospital x"})
    assert isinstance(d, DatasetDraft)
    assert "smith" not in (d.name + d.readme).lower() and "hospital x" not in d.readme.lower()
    assert rec.steps == ["metadata"]
    assert set(json.loads(rec.users[0])) == {"series"}


def test_draft_metadata_bad_reply_is_none():
    assert draft_metadata([ss(0)], Recorder("nope"), set()) is None
    assert draft_metadata([ss(0)], Recorder('{"name": 3}'), set()) is None


@pytest.fixture
def clean_env(monkeypatch):
    for k in ENV_KEYS:
        monkeypatch.delenv(k, raising=False)
    return monkeypatch


@pytest.mark.parametrize("model,cls", [("claude-opus-5-5", ClaudeClient), ("gpt-4o", AutobidsifyClient),
                                       ("o3-mini", AutobidsifyClient),
                                       ("qwen3-coder-next:latest", AutobidsifyClient)])
def test_backend_routing(monkeypatch, model, cls):
    for k in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "OLLAMA_BASE_URL"):
        monkeypatch.setenv(k, "x")
    monkeypatch.setenv("AIMPORT_MODEL", model)
    assert isinstance(client_from_env(), cls)


def test_default_model_is_claude(clean_env):
    clean_env.setenv("ANTHROPIC_API_KEY", "x")
    c = client_from_env()
    assert isinstance(c, ClaudeClient) and c.model == "claude-opus-5-5"


def test_dashscope_satisfies_qwen(clean_env):
    clean_env.setenv("AIMPORT_MODEL", "qwen-plus")
    clean_env.setenv("DASHSCOPE_API_KEY", "x")
    assert isinstance(client_from_env(), AutobidsifyClient)


@pytest.mark.parametrize("model", ["claude-opus-5-5", "gpt-4o", "o1-mini", "qwen-plus", "unknown-model"])
def test_no_key_means_none(clean_env, model):
    clean_env.setenv("AIMPORT_MODEL", model)
    assert client_from_env() is None


def test_autobidsify_client_calls_through(monkeypatch):
    seen = {}

    def fake(model, system, user, step, temperature=None):
        seen.update(model=model, system=system, user=user, step=step)
        return "ok"

    monkeypatch.setattr("autobidsify.llm._call_llm", fake)
    assert AutobidsifyClient("gpt-4o").complete("s", "u", "classify") == "ok"
    assert seen == {"model": "gpt-4o", "system": "s", "user": "u", "step": "classify"}


def test_claude_client_uses_messages_api():
    class Block:
        def __init__(self, type, text=""):
            self.type, self.text = type, text

    class Messages:
        def create(self, **kw):
            self.kw = kw
            return type("R", (), {"content": [Block("thinking"), Block("text", "hi")]})()

    msgs = Messages()
    client = ClaudeClient()
    client._client = type("C", (), {"messages": msgs})()
    assert client.complete("sys", "usr", "classify") == "hi"
    assert msgs.kw["model"] == "claude-opus-5-5" and msgs.kw["system"] == "sys"
    assert msgs.kw["messages"] == [{"role": "user", "content": "usr"}]
    assert msgs.kw["max_tokens"] >= 1024
