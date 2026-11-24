"""Task 7: the agent sees allowlisted recording facts and coded event counts only; only ephys answers are kept."""
from __future__ import annotations

import hashlib
import json
import re

import pytest

from aimport.agent import CLASSIFY_SYSTEM, EPHYS_CLASSIFY_SYSTEM, MICR_CLASSIFY_SYSTEM
from aimport.ephys.module import EphysModule, ephys_view
from aimport.ezbids_runner import CoreResult
from aimport.planner import build_plan
from aimport.pseudonyms import PseudonymKey
from conftest import ephys_tokens
from fixtures.ephys_fixtures import planted_brainvision, planted_edf

MRI_PROMPT_SHA256 = "5fb7c028deadc1dfd608819d55c048c0ee0ed8b6d247cabffacf19d0d6c55a2f"
MICR_PROMPT_SHA256 = "35ef933ccb337bbd331b59d95fd1ff130704394bc61ca4b2b4cb468b30711e2c"
FIELDS = {"FormatFamily", "SystemFamily", "SamplingFrequency", "ChannelCount", "ChannelTypes", "DurationSeconds",
          "EventCounts", "LineFrequency", "HasDigitization", "Wavelengths", "Hints"}


class Recorder:
    name = "recorder"

    def __init__(self, reply):
        self.reply, self.users, self.systems = reply, [], []

    def complete(self, system, user, step):
        self.users.append(user)
        self.systems.append(system)
        return self.reply(user) if callable(self.reply) else self.reply


@pytest.fixture
def key(tmp_path):
    k = PseudonymKey.load(tmp_path / "keys", "proj")
    yield k
    k.close()


def reply_for(datatype, task=None, confidence=0.9):
    def reply(user):
        series = json.loads(user)["series"]
        return json.dumps([{"series_idx": s["series_idx"], "datatype": datatype, "suffix": datatype,
                            "entities": {"task": task} if task else {}, "confidence": confidence, "reason": "r"}
                           for s in series])
    return reply


def plan_with(root, tmp_path, key, schema, client):
    work = tmp_path / "work"
    m = EphysModule()
    claim = m.claim(root, [])
    m.scan(root, claim, work / "ephys", lambda msg: None)
    return build_plan(CoreResult(), root, key, set(), client, schema, "bids", exclude=claim.roots,
                      extra_terms=frozenset(m.terms(work / "ephys")),
                      planners=[lambda subjects: m.plan(work / "ephys", key, set(), client, schema, "bids",
                                                        subjects=subjects)])


def entries(plan):
    return [e for e in plan.entries if e.modality == "ephys"]


def strings(value):
    """Every key and string value of a JSON value."""
    if isinstance(value, dict):
        for k, v in value.items():
            yield str(k)
            yield from strings(v)
    elif isinstance(value, list):
        for v in value:
            yield from strings(v)
    elif isinstance(value, str):
        yield value


def test_ephys_payload_allowlisted(tmp_path, key, schema):
    root = tmp_path / "in"
    planted_edf(root)
    planted_brainvision(root)
    rec = Recorder(reply_for("eeg", "rest"))
    plan_with(root, tmp_path, key, schema, rec)
    assert EPHYS_CLASSIFY_SYSTEM in rec.systems
    seen = 0
    for user in rec.users:  # the classify and the metadata calls
        series = json.loads(user)["series"]
        series = [s for s in series if s["ezbids_type"] in ("eeg/eeg", "ieeg/ieeg")]
        seen += len(series)
        for s in series:
            assert set(s["fields"]) == FIELDS
            assert s["description"] == "" and s["protocol"] == ""
        assert not ephys_tokens(user) and "fp1" not in user.lower()
        for s in series:
            leaves = " ".join(strings(s["fields"]))
            assert "/" not in leaves and ":" not in leaves
            assert not re.search(r"\d{6}", leaves)
    assert seen >= 2


def test_event_counts_coded_only(tmp_path):
    from aimport.ephys import module as m

    root = tmp_path / "in"
    planted_edf(root)
    mod = EphysModule()
    claim = mod.claim(root, [])
    mod.scan(root, claim, tmp_path / "w", lambda msg: None)
    records = m.load_records(tmp_path / "w")
    (v,) = ephys_view(records)
    counts = v.fields["EventCounts"]
    assert counts and all(re.fullmatch(r"E\d{3}", k) or m.events.is_safe(k) for k in counts)
    assert v.ezbids_type == "eeg/eeg" and v.fields["Hints"] == ["rest"]
    records[0]["event_labels"].append("Smith John said hello")
    assert "Smith John said hello" not in ephys_view(records)[0].fields["EventCounts"]


def test_agent_fills_ambiguous_datatype(tmp_path, key, schema):
    root = tmp_path / "in"
    planted_edf(root)
    (e,) = entries(plan_with(root, tmp_path, key, schema, Recorder(reply_for("ieeg", "rest"))))
    assert e.datatype == "eeg" and e.agent_note and e.confidence < 0.8


def test_agent_agreement_fills_unknown_task_from_hints_only(tmp_path, key, schema):
    root = tmp_path / "in"
    planted_edf(root)
    (e,) = entries(plan_with(root, tmp_path / "a", key, schema, Recorder(reply_for("eeg", "rest", 0.95))))
    assert e.entities["task"] == "rest" and not e.agent_note and e.confidence >= 0.95
    (e,) = entries(plan_with(root, tmp_path / "b", key, schema, Recorder(reply_for("eeg", "gambling"))))
    assert e.entities["task"] == "rest"  # the heuristic's own word stands; an invented one is not taken


def test_agent_non_ephys_answer_rejected(tmp_path, key, schema):
    root = tmp_path / "in"
    planted_edf(root)
    (e,) = entries(plan_with(root, tmp_path, key, schema, Recorder(reply_for("anat", None))))
    assert e.datatype == "eeg" and not e.agent_note and e.confidence == 0.8


def test_mri_and_micr_prompts_unchanged():
    assert hashlib.sha256(CLASSIFY_SYSTEM.encode()).hexdigest() == MRI_PROMPT_SHA256
    assert hashlib.sha256(MICR_CLASSIFY_SYSTEM.encode()).hexdigest() == MICR_PROMPT_SHA256
