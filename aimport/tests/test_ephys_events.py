"""Phase 3 Task 5: coded event labels (``ephys/events.py``), channel renames (``ephys/channels.py``) and
``Plan.event_names`` (``PATCH /plan``)."""
from __future__ import annotations

import json
import random
import string

import pytest

from aimport.ephys import channels, events
from aimport.plan import Plan
from conftest import ephys_tokens
from fixtures import ephys_fixtures as fx
from test_server import SCAN, apps, client, hooks, make_client, planned, wait_stage  # noqa: F401 (fixtures)

TERMS = {"Smith", "John", "MRN0042", "Jane Doe"}


# --- events ---

def test_safe_labels_kept():
    safe = ["Stimulus/S  1", "BAD_ACQ_SKIP", "eyes closed", "Sleep stage N2", "12"]
    mapping, codes = events.code([safe], TERMS)
    assert codes == {}
    assert [mapping[events.normalise(s)] for s in safe] == safe  # written exactly as given
    assert events.label("Stimulus/S  1", mapping) == "Stimulus/S  1"
    assert all(events.is_safe(s) for s in safe)


def test_free_text_coded():
    mapping, codes = events.code(
        [["Smith John said hello", "1", "MRN0042 start"], ["eyes closed", "smith  john said HELLO", "rest Smith"]],
        TERMS,
    )
    assert mapping[events.normalise("Smith John said hello")] == "E001"
    assert events.label("smith  john said HELLO", mapping) == "E001"  # the second recording: same code
    assert mapping[events.normalise("MRN0042 start")] == "E002"
    assert mapping[events.normalise("rest Smith")] == "E003"
    assert mapping["1"] == "1" and mapping["eyes closed"] == "eyes closed"
    assert codes == {"E001": "E001", "E002": "E002", "E003": "E003"}
    assert not ephys_tokens(json.dumps(codes))
    # a free-text label not in safe words is coded even without run terms
    assert events.code([["patient moved head"]], set())[1] == {"E001": "E001"}


def test_safe_word_with_term_coded():
    mapping, codes = events.code([["rest", "eyes open"]], {"rest"})
    assert mapping["rest"] == "E001" and codes == {"E001": "E001"}
    assert mapping["eyes open"] == "eyes open"


def test_separator_variants_of_terms_coded():
    terms = {"Jane Doe"}
    mapping, codes = events.code([["BAD_JANE_DOE", "Jane_Doe", "jane.doe", "JaneDoe", "BAD_ACQ"]], terms)
    assert [mapping[k] for k in ("bad_jane_doe", "jane_doe", "jane.doe", "janedoe")] == ["E001", "E002", "E003",
                                                                                        "E004"]
    assert mapping["bad_acq"] == "BAD_ACQ"
    renamed = channels.rename(["Jane-Doe-Fp1", "Jane_Doe", "Fp2"], ["eeg", "eeg", "eeg"], terms)
    assert renamed == {"Jane-Doe-Fp1": "eeg_001", "Jane_Doe": "eeg_002"}


def test_ascii_only_safe_patterns():
    for text in ("\uff11\uff12", "\u0661\u0662", "ſtart", "marKer".replace("K", "\u212a"), "Stimulus/S \uff11"):
        assert not events.is_safe(text)
        assert events.code([[text]], set())[0][events.normalise(text)] == "E001"
    assert events.is_safe("12") and events.is_safe("START")


def test_safe_label_independent_of_order():
    a, _ = events.code([["Rest"], ["rest"]], set())
    b, _ = events.code([["rest"], ["Rest"]], set())
    assert a == b == {"rest": "Rest"}  # least by (casefold, text): "Rest" < "rest"
    c, _ = events.code([["Stimulus/S  1"], ["stimulus/s  1", "Stimulus/S 1"]], set())
    d, _ = events.code([["Stimulus/S 1", "stimulus/s  1"], ["Stimulus/S  1"]], set())
    assert c == d
    # a key is kept only when every variant is safe: "eyes  closed" (two spaces) is not, in either order
    e, ecodes = events.code([["eyes closed"], ["eyes  closed"]], set())
    f, _ = events.code([["eyes  closed"], ["eyes closed"]], set())
    assert e == f == {"eyes closed": "E001"} and ecodes == {"E001": "E001"}


def test_term_variants_and_dates_coded():
    from datetime import date

    from aimport.ephys import headers

    assert events.code([["REST", "rest 2"]], {"rest"})[1] == {"E001": "E001", "E002": "E002"}
    date_terms = headers._all_forms(date(2025, 2, 15))  # includes 15.02.25 and 250215
    mapping, codes = events.code([["150225", "250215", "42"]], date_terms)
    assert mapping["150225"] == "E001" and mapping["250215"] == "E002" and mapping["42"] == "42"


def test_counts():
    mapping, _ = events.code([["Smith said hi", "1", "1"]], TERMS)
    assert events.counts(["Smith said hi", "1", " 1 "], mapping) == {"E001": 1, "1": 2}
    with pytest.raises(ValueError) as e:
        events.counts(["Never seen Smith"], mapping)
    assert "Smith" not in str(e.value)


def test_planted_edf_annotations_coded(tmp_path):
    mne = pytest.importorskip("mne")
    raw = mne.io.read_raw_edf(fx.planted_edf(tmp_path), preload=False, verbose="error")
    mapping, codes = events.code([list(raw.annotations.description)], TERMS)
    assert codes == {"E001": "E001"}
    assert events.counts(raw.annotations, mapping) == {"E001": 1, "1": 1, "eyes closed": 1}
    renames = channels.rename(raw.ch_names, raw.get_channel_types(), TERMS)
    assert renames == {"Smith-Fp1": "eeg_002"}


# --- Plan.event_names ---

def _plan(event_names):
    return Plan(target="bids", entries=[], event_names=dict(event_names))


def test_set_event_names():
    p = _plan({"E001": "E001", "E002": "E002"})
    p.approved = True
    p.set_event_names({"E001": "eyes closed 2", "E002": "go/no-go+1"})
    assert p.event_names == {"E001": "eyes closed 2", "E002": "go/no-go+1"} and p.approved is False
    for bad in ({"E003": "x"}, {"E001": ""}, {"E001": " lead"}, {"E001": "x" * 41}, {"E001": "a;b"}, {"E001": 3}):
        with pytest.raises(ValueError):
            p.set_event_names(bad)
    with pytest.raises(ValueError, match="unknown event code"):
        p.set_event_names({"E001": "fine", "E009": "fine"})
    with pytest.raises(ValueError, match="two event codes would share one name"):
        p.set_event_names({"E002": "Eyes Closed 2"})  # E001 already has that name (case-insensitively)
    with pytest.raises(ValueError, match="two event codes would share one name"):
        p.set_event_names({"E001": "go", "E002": "go"})
    assert p.event_names == {"E001": "eyes closed 2", "E002": "go/no-go+1"}  # a bad edit changes nothing
    p.set_event_names({"E001": "a", "E002": "eyes closed 2"})  # a swap in one edit is fine
    assert p.event_names == {"E001": "a", "E002": "eyes closed 2"}


def test_plan_event_names_roundtrip(tmp_path):
    p = _plan({"E001": "go"})
    p.save(tmp_path / "plan.json")
    assert Plan.load(tmp_path / "plan.json").event_names == {"E001": "go"}
    data = json.loads((tmp_path / "plan.json").read_text())
    del data["event_names"]  # a plan written before Task 5
    (tmp_path / "plan.json").write_text(json.dumps(data))
    assert Plan.load(tmp_path / "plan.json").event_names == {}


def _seed(c, names):
    srv = c.app.state.server
    with srv.plan_lock:
        plan = srv.load_plan()
        plan.event_names = dict(names)
        srv.save_plan(plan)


def test_patch_event_names(planned, hooks):
    _seed(planned, {"E001": "E001", "E002": "E002"})
    r = planned.patch("/plan", json={"event_names": {"E001": "eyes closed"}})
    assert r.status_code == 200, r.text
    assert r.json()["event_names"] == {"E001": "eyes closed", "E002": "E002"}
    assert planned.get("/plan").json()["event_names"]["E001"] == "eyes closed"

    r = planned.patch("/plan", json={"event_names": {"E077": "go"}})
    assert r.status_code == 400 and r.json()["detail"] == "unknown event code"
    r = planned.patch("/plan", json={"event_names": {"E002": "Smith"}})
    assert r.status_code == 400 and r.json()["detail"] == "event name contains an identifying term"
    assert "smith" not in r.text.lower()
    assert planned.patch("/plan", json={"event_names": {"E002": "a;b"}}).status_code == 400
    r = planned.patch("/plan", json={"event_names": {"E002": "Eyes Closed"}})
    assert r.status_code == 400 and r.json()["detail"] == "two event codes would share one name"
    assert "eyes" not in r.text.lower()
    assert planned.patch("/plan", json={"event_names": ["E002"]}).status_code == 422
    assert planned.get("/plan").json()["event_names"] == {"E001": "eyes closed", "E002": "E002"}

    # approved: an edit unapproves (as every plan edit); once execution has started it is 409
    assert planned.post("/approve", json={}).status_code == 200
    r = planned.patch("/plan", json={"event_names": {"E002": "go"}})
    assert r.status_code == 200 and r.json()["approved"] is False
    assert planned.post("/approve", json={}).status_code == 200
    hooks.gate.clear()
    assert planned.post("/execute").status_code == 202
    assert planned.patch("/plan", json={"event_names": {"E002": "stop"}}).status_code == 409
    hooks.gate.set()
    wait_stage(planned, ["validated", "invalid", "failed"])

    text = planned.get("/plan").text
    assert not ephys_tokens(text) and "said hello" not in text.lower()


# --- channels ---

def test_channel_rename():
    names = ["Fp1", "Smith-Fp1", "EMG1", "S1_D1 760", "x" * 33, "MEG 0113", "STI 014", "Cz'", "A1+A2"]
    types = ["eeg", "eeg", "emg", "fnirs_cw_amplitude", "eeg", "grad", "stim", "eeg", "eeg"]
    out = channels.rename(names, types, TERMS)
    assert out == {"Smith-Fp1": "eeg_002", "x" * 33: "eeg_003"}
    assert channels.rename(names, types, TERMS) == out  # deterministic
    # the position is taken: the next free number
    assert channels.rename(["eeg_002", "Smith-Fp1"], ["eeg", "eeg"], TERMS) == {"Smith-Fp1": "eeg_003"}
    assert channels.rename(["EEG_001", "JDOE"], ["eeg", "stim"], {"JDOE"}) == {"JDOE": "stim_001"}
    assert channels.rename(["JDOE", "STIM_001"], ["stim", "stim"], {"JDOE"}) == {"JDOE": "stim_002"}
    assert channels.rename(["Fp1\n"], ["eeg"], set()) == {"Fp1\n": "eeg_001"}
    with pytest.raises(ValueError):
        channels.rename(["Fp1"], [], set())


def test_channel_rename_never_collides():
    rnd = random.Random(0)
    types = ["eeg", "eeg", "eeg", "stim", "misc"]
    alphabet = string.ascii_letters + string.digits + "_- "
    for _ in range(1000):
        n = rnd.randint(1, 30)
        names: list[str] = []
        while len(names) < n:
            kind = rnd.random()
            if kind < 0.3:
                cand = f"{rnd.choice(['eeg', 'EEG', 'stim', 'misc'])}_{rnd.randint(1, 12):03d}"
            elif kind < 0.5:
                cand = "Smith" + str(rnd.randint(0, 9))
            elif kind < 0.6:
                cand = "y" * rnd.randint(30, 40)
            else:
                cand = "".join(rnd.choice(alphabet) for _ in range(rnd.randint(1, 8)))
            if cand.casefold() not in {x.casefold() for x in names}:
                names.append(cand)
        ch_types = [rnd.choice(types) for _ in names]
        out = channels.rename(names, ch_types, TERMS)
        final = [out.get(x, x) for x in names]
        assert len({f.casefold() for f in final}) == len(final)
        for old, new in out.items():
            assert channels.is_kept(new, TERMS) and not channels.is_kept(old, TERMS)
        assert all(channels.is_kept(x, TERMS) for x in names if x not in out)
