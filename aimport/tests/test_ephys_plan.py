"""Task 6: electrophysiology scan records and plan entries (ephys/module.py), the planner hook, mapping rows."""
from __future__ import annotations

import copy
import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pytest

from aimport import modality
from aimport.brainlife_map import draft_for, load_rows, to_brainlife
from aimport.ephys import module as ephys_module
from aimport.ephys.module import EPHYS_INDEX_BASE, HEADSHAPE_WARNING, PROGRESS, EphysModule
from aimport.ezbids_runner import CoreResult, parse_core
from aimport.planner import EPHYS_DATATYPE_REASON, MRI_EPHYS_REASON, TASK_REASON, apply_plan_edits, build_plan
from aimport.plan import Plan
from aimport.pseudonyms import PseudonymKey
from conftest import ephys_tokens
from fixtures.ephys_fixtures import (MEAS_DATE, SFREQ, planted_brainvision, planted_edf, planted_fif,
                                     planted_snirf)

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def key(tmp_path):
    k = PseudonymKey.load(tmp_path / "keys", "proj")
    yield k
    k.close()


def scan(inp: Path, work: Path, progress=None) -> tuple[EphysModule, modality.Claim]:
    m = EphysModule()
    claim = m.claim(inp, [])
    m.scan(inp, claim, work / "ephys", progress or (lambda msg: None))
    return m, claim


def make_plan(inp, work, key, schema, core=None, target="bids") -> Plan:
    m, claim = scan(inp, work)
    return build_plan(core or CoreResult(), inp, key, set(), None, schema, target, exclude=claim.roots,
                      extra_terms=frozenset(m.terms(work / "ephys")),
                      planners=[lambda subjects: m.plan(work / "ephys", key, set(), None, schema, target,
                                                        subjects=subjects)])


def ephys(plan: Plan):
    return [e for e in plan.entries if e.modality == "ephys"]


def edf(path: Path, labels, his_id="P1234567", when=MEAS_DATE, n=256):
    """A small EDF+ with the given signal labels, patient code and start time."""
    import edfio

    path.parent.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(0)
    signals = [edfio.EdfSignal(rng.standard_normal(n) * 20, sampling_frequency=SFREQ, label=lab,
                               physical_dimension="uV", physical_range=(-500.0, 500.0)) for lab in labels]
    edfio.Edf(signals, patient=edfio.Patient(code=his_id),
              recording=edfio.Recording(startdate=when.date()), starttime=when.time().replace(tzinfo=None)
              ).write(path)
    return path


def meg_fif(path: Path, when: datetime | None, his_id: str | None = "M7654321"):
    import mne

    path.parent.mkdir(parents=True, exist_ok=True)
    info = mne.create_info([f"MEG {i:03d}" for i in range(1, 5)], SFREQ, "mag")
    raw = mne.io.RawArray(np.zeros((4, 256)), info, verbose=False)
    if his_id:
        with raw.info._unlock():
            raw.info["subject_info"] = {"his_id": his_id}
    raw.set_meas_date(when)
    raw.save(path, overwrite=True, verbose=False)
    return path


# --- datatypes ---------------------------------------------------------------------------------


def test_datatypes(tmp_path, key, schema):
    inp = tmp_path / "in"
    edf(inp / "a" / "grid_rest.edf", ["SEEG LA1", "SEEG LA2", "ECOG G1", "EEG Fp1"], his_id="P1")
    edf(inp / "b" / "arm_rest.edf", ["EMG L1", "EMG L2", "EMG L3", "EEG Cz"], his_id="P2")
    planted_fif(inp / "c")
    planted_snirf(inp / "d")
    planted_brainvision(inp / "e")
    plan = make_plan(inp, tmp_path / "work", key, schema)
    datatypes = sorted(e.datatype for e in ephys(plan))
    assert datatypes == ["eeg", "emg", "ieeg", "meg", "nirs"]
    seeg = next(e for e in ephys(plan) if e.datatype == "ieeg")
    assert "seeg 2" in seeg.description and seeg.ephys_format == "BrainVision"
    assert next(e for e in ephys(plan) if e.datatype == "emg").ephys_format == "EDF"
    assert next(e for e in ephys(plan) if e.datatype == "meg").ephys_format == "FIF"
    assert next(e for e in ephys(plan) if e.datatype == "nirs").ephys_format == "SNIRF"
    for e in ephys(plan):
        assert e.status == "ok" and not e.exclude and e.deface is False, (e.datatype, e.reason)
        assert e.series_idx >= EPHYS_INDEX_BASE and e.subject_idx >= EPHYS_INDEX_BASE
        assert e.entities["task"] == "rest"


def test_bids_folder_wins_and_emg_from_bdf_keeps_bdf():
    assert ephys_module.datatype_of({"rel": "sub-01/ieeg/sub-01_task-x_ieeg.edf", "family": "edf",
                                     "info": {"ch_types": {"eeg": 10}}})[0] == "ieeg"
    assert ephys_module.datatype_of({"rel": "x.ds", "family": "ctf", "info": None})[0] == "meg"
    assert ephys_module.datatype_of({"rel": "x.nwb", "family": "nwb", "info": None})[0] == "ieeg"
    assert ephys_module._default_format("emg", "bdf") == "BDF"
    assert ephys_module._default_format("emg", "edf") == "EDF"
    assert ephys_module._default_format("ieeg", "nwb") == "BrainVision"


# --- scan records ------------------------------------------------------------------------------


def test_records_local_with_progress(tmp_path):
    inp = tmp_path / "in"
    planted_edf(inp)
    planted_brainvision(inp)
    seen: list[str] = []
    scan(inp, tmp_path / "work", seen.append)
    work = tmp_path / "work" / "ephys"
    records = json.loads((work / "records.json").read_text())
    assert seen == [PROGRESS.format(k=k, n=2) for k in (1, 2)]
    for msg in seen:
        assert not ephys_tokens(msg)
    assert all(set(r) >= {"rel", "family", "companions", "headshape", "info", "terms", "event_labels"}
               for r in records)
    rec = next(r for r in records if r["family"] == "edf")
    assert rec["info"]["meas_date"].startswith("2025-02-15")  # local records only
    assert rec["info"]["his_id"] == "MRN0042"
    assert set(rec["event_labels"]) == {"E001", "1", "eyes closed"}
    assert all(a[2] in rec["event_labels"] for a in rec["info"]["annotations"])
    terms = set(json.loads((work / "terms.json").read_text()))
    assert "MRN0042" in terms and terms == EphysModule().terms(work)
    ev = json.loads((work / "events.json").read_text())
    assert ev["codes"]["E001"] == "smith john said hello" and ev["labels"]["eyes closed"] == "eyes closed"
    chans = json.loads((work / "channels.json").read_text())
    assert chans[rec["rel"]] == {"eeg_002": "Smith-Fp1"}  # new -> old


def test_unreadable_recording_is_unsupported_with_generic_reason(tmp_path, key, schema):
    inp = tmp_path / "in"
    (inp / "Smith_John_meg" / "Smith_rest.ds").mkdir(parents=True)  # a CTF folder with no header
    (inp / "Smith_John_meg" / "Smith_rest.ds" / "Smith_rest.res4").write_bytes(b"\0" * 64)
    plan = make_plan(inp, tmp_path / "work", key, schema)
    (e,) = ephys(plan)
    assert e.status == "unsupported" and e.exclude and e.ephys_format == ""
    assert e.datatype == "meg"
    assert e.reason == ephys_module.UNREADABLE_REASON
    assert "smith" not in json.dumps(asdict(plan)).lower()


def test_meta_redacted():
    meta = {"task": "Smith", "acq": "hd", "EEGReference": "Smith ref", "PowerLineFrequency": 60}
    out = ephys_module._clean_meta(meta, {"Smith"})
    assert out == {"acq": "hd", "EEGReference": "[x] ref", "PowerLineFrequency": 60}


def test_remote_ignored(tmp_path):
    planted_edf(tmp_path)
    claim = EphysModule().claim(tmp_path, ["https://example.org/x.edf"])
    assert claim.remote == [] and claim.roots


# --- subjects, sessions, tasks, runs -----------------------------------------------------------


def test_subject_pseudonymised(tmp_path, key, schema):
    inp = tmp_path / "in"
    planted_edf(inp)
    plan = make_plan(inp, tmp_path / "work", key, schema)
    (e,) = ephys(plan)
    assert key.subjects["ephys:id=MRN0042"] == e.subject
    again = make_plan(inp, tmp_path / "work2", key, schema)
    assert ephys(again)[0].subject == e.subject
    text = json.dumps(asdict(plan))
    assert not ephys_tokens(text)
    assert plan.event_names == {"E001": "E001"}
    assert e.event_counts == {"E001": 1, "1": 1, "eyes closed": 1}
    assert e.description == "EDF → BrainVision, 3 ch (eeg 3), 256 Hz, 10 s, 3 event codes"


def test_task_unknown_needs_review(tmp_path, key, schema):
    inp = tmp_path / "in"
    edf(inp / "data" / "recording1.edf", ["EEG Fp1", "EEG Fp2"])
    plan = make_plan(inp, tmp_path / "work", key, schema)
    (e,) = ephys(plan)
    assert e.entities["task"] == "unknown" and e.status == "unknown" and e.exclude
    assert e.reason == TASK_REASON
    apply_plan_edits(plan, [{"id": e.id, "entities": {"task": "rest"}}], schema)
    assert e.status == "ok" and not e.exclude
    assert e.brainlife_datatype == "neuro/eeg/brainvision" and e.brainlife_tags == ["rest"]


def test_emptyroom_paired_and_no_date_session(tmp_path, key, schema):
    inp = tmp_path / "in"
    day = MEAS_DATE
    meg_fif(inp / "meg" / "subj_rest_raw.fif", day.replace(hour=10))
    meg_fif(inp / "meg" / "subj_rest2_raw.fif", day.replace(hour=15))
    meg_fif(inp / "meg" / "emptyroom_am_raw.fif", day.replace(hour=9), his_id=None)
    meg_fif(inp / "meg" / "emptyroom_pm_raw.fif", day.replace(hour=16), his_id=None)
    meg_fif(inp / "other" / "emptyroom_raw.fif", datetime(2025, 3, 1, 10, tzinfo=timezone.utc), his_id=None)
    plan = make_plan(inp, tmp_path / "work", key, schema)
    rooms = [e for e in ephys(plan) if e.subject == "emptyroom"]
    meg = [e for e in ephys(plan) if e.subject != "emptyroom"]
    assert len(rooms) == 3 and len(meg) == 2
    for e in rooms:
        assert e.entities["task"] == "noise" and e.session is None and e.datatype == "meg"
        assert e.status == "ok"
    assert len({e.subject_idx for e in rooms}) == 1
    by_id = {e.id: e for e in rooms}
    # the 10:00 run pairs with the 09:00 empty room, the 15:00 run with the 16:00 one
    am, pm = sorted(meg, key=lambda e: e.entities.get("run", ""))
    assert am.empty_room in by_id and pm.empty_room in by_id and am.empty_room != pm.empty_room
    assert "ses-2025" not in json.dumps(asdict(plan)) and "20250" not in json.dumps(asdict(plan))
    for e in meg:
        assert e.session is None  # one recording day


def test_sessions_by_day(tmp_path, key, schema):
    inp = tmp_path / "in"
    edf(inp / "x" / "a_rest.edf", ["EEG Fp1"], when=datetime(2025, 2, 16, 9, tzinfo=timezone.utc))
    edf(inp / "x" / "b_rest.edf", ["EEG Fp1"], when=datetime(2025, 2, 15, 9, tzinfo=timezone.utc))
    plan = make_plan(inp, tmp_path / "work", key, schema)
    assert sorted(e.session for e in ephys(plan)) == ["01", "02"]
    first = next(e for e in ephys(plan) if e.series_idx == EPHYS_INDEX_BASE + 1)  # b_rest: the earlier day
    assert first.session == "01" and "run" not in first.entities


def test_runs_by_date(tmp_path, key, schema):
    inp = tmp_path / "in"
    # alphabetical order is the reverse of the recording order
    edf(inp / "x" / "a_rest.edf", ["EEG Fp1"], when=MEAS_DATE.replace(hour=14))
    edf(inp / "x" / "b_rest.edf", ["EEG Fp1"], when=MEAS_DATE.replace(hour=9))
    edf(inp / "x" / "c_oddball.edf", ["EEG Fp1"], when=MEAS_DATE.replace(hour=11))
    plan = make_plan(inp, tmp_path / "work", key, schema)
    a, b, c = sorted(ephys(plan), key=lambda e: e.series_idx)
    assert (a.entities["run"], b.entities["run"]) == ("2", "1")
    assert c.entities == {"task": "oddball"}
    assert a.session is None and len({a.subject, b.subject, c.subject}) == 1


# --- edits -------------------------------------------------------------------------------------


def test_format_edit(tmp_path, key, schema):
    inp = tmp_path / "in"
    planted_brainvision(inp)
    edf(inp / "ieeg" / "grid_rest.edf", ["SEEG LA1", "SEEG LA2"], his_id="P9")
    plan = make_plan(inp, tmp_path / "work", key, schema)
    eeg = next(e for e in ephys(plan) if e.datatype == "eeg")
    ieeg = next(e for e in ephys(plan) if e.datatype == "ieeg")
    apply_plan_edits(plan, [{"id": eeg.id, "ephys_format": "EDF"}], schema)
    assert eeg.ephys_format == "EDF" and eeg.status == "ok"
    assert eeg.brainlife_datatype == "neuro/eeg/edf"
    with pytest.raises(ValueError):
        apply_plan_edits(plan, [{"id": eeg.id, "ephys_format": "FIF"}], schema)
    with pytest.raises(ValueError):
        apply_plan_edits(plan, [{"id": ieeg.id, "ephys_format": "NWB"}], schema)
    with pytest.raises(ValueError):
        apply_plan_edits(plan, [{"id": eeg.id, "ephys_format": None}], schema)
    with pytest.raises(ValueError):
        apply_plan_edits(plan, [{"id": eeg.id, "deface": True}], schema)
    assert eeg.ephys_format == "EDF"
    # a datatype edit keeps the format when the new datatype allows it, else takes its default
    apply_plan_edits(plan, [{"id": eeg.id, "datatype": "ieeg", "suffix": "ieeg"}], schema)
    assert eeg.ephys_format == "EDF" and eeg.status == "ok" and eeg.brainlife_datatype is None
    apply_plan_edits(plan, [{"id": eeg.id, "datatype": "meg", "suffix": "meg"}], schema)
    assert eeg.ephys_format == "FIF"
    # an ephys entry cannot become MRI
    apply_plan_edits(plan, [{"id": ieeg.id, "datatype": "anat", "suffix": "T1w"}], schema)
    assert ieeg.status == "unknown" and ieeg.exclude and ieeg.reason == EPHYS_DATATYPE_REASON
    apply_plan_edits(plan, [{"id": eeg.id, "keep_headshape": True}], schema)
    assert eeg.keep_headshape is True


def test_plan_round_trips(tmp_path, key, schema):
    inp = tmp_path / "in"
    planted_edf(inp)
    plan = make_plan(inp, tmp_path / "work", key, schema)
    plan.save(tmp_path / "plan.json")
    loaded = Plan.load(tmp_path / "plan.json")
    assert loaded.entries[0].modality == "ephys" and loaded.entries[0].event_counts == ephys(plan)[0].event_counts
    old = json.loads((tmp_path / "plan.json").read_text())
    for e in old["entries"]:  # a plan written before phase 3
        for k in ("modality", "ephys_format", "keep_headshape", "event_counts", "empty_room"):
            e.pop(k)
    (tmp_path / "old.json").write_text(json.dumps(old))
    e = Plan.load(tmp_path / "old.json").entries[0]
    assert e.modality == "mri" and e.ephys_format == "" and e.event_counts == {} and e.empty_room is None


# --- mapping -----------------------------------------------------------------------------------


def test_brainlife_ext_mapping():
    assert to_brainlife("eeg", "eeg", {"task": "rest"}, {}, ".eeg") == ("neuro/eeg/brainvision", ["rest"])
    assert to_brainlife("eeg", "eeg", {"task": "Rest"}, {}, ".edf") == ("neuro/eeg/edf", ["rest"])
    assert to_brainlife("eeg", "eeg", {"task": "rest"}, {}, ".bdf") == ("neuro/eeg/bdf", ["rest"])
    assert to_brainlife("meg", "meg", {"task": "rest"}, {}, ".fif") == ("neuro/meg/fif", ["rest"])
    assert to_brainlife("ieeg", "ieeg", {"task": "rest"}, {}, ".eeg") == (None, [])
    assert draft_for("ieeg", "ieeg") == "neuro/ieeg/ieeg"
    assert to_brainlife("anat", "T1w", {}, {}, ".nii.gz") == ("neuro/anat/t1w", [])  # falls back to the pair
    rows = {(r["bids"]["datatype"], r["bids"].get("extension")): r for r in load_rows()}
    for k in (("eeg", ".bdf"), ("eeg", ".edf"), ("eeg", ".eeg"), ("eeg", ".set"), ("meg", ".ds"), ("meg", ".fif")):
        assert rows[k]["status"] == "active" and "aimport writes" in rows[k]["note"]
    for r in load_rows():
        if r["bids"]["datatype"] in ("ieeg", "nirs", "emg"):
            assert r["status"] == "draft"


def test_mri_entry_cannot_become_ephys(tmp_path, key, schema):
    core = parse_core(FIXTURES / "ezbids_core_siemens.json")
    plan = build_plan(core, tmp_path, key, set(), None, schema, "bids")
    e = plan.entries[0]
    apply_plan_edits(plan, [{"id": e.id, "datatype": "eeg", "suffix": "eeg", "entities": {"task": "rest"}}], schema)
    assert e.status == "unknown" and e.reason == MRI_EPHYS_REASON
    with pytest.raises(ValueError):
        apply_plan_edits(plan, [{"id": e.id, "ephys_format": "EDF"}], schema)


# --- ancillary ---------------------------------------------------------------------------------


def test_inherited_ephys_sidecar_dropped(tmp_path, key, schema):
    inp = tmp_path / "in"
    eeg_dir = inp / "sub-01" / "eeg"
    edf(eeg_dir / "sub-01_task-rest_eeg.edf", ["EEG Fp1", "EEG Fp2"])
    (inp / "dataset_description.json").write_text(json.dumps({"Name": "x", "BIDSVersion": "1.11.2"}))
    (inp / "task-rest_eeg.json").write_text(json.dumps({"PowerLineFrequency": 50}))
    (inp / "task-rest_coordsystem.json").write_text(json.dumps({"EEGCoordinateSystem": "CapTrak"}))
    (inp / "task-rest_events.json").write_text(json.dumps({"trial_type": {"Description": "x"}}))
    (inp / "sub-01" / "sub-01_task-rest_eeg.json").write_text(json.dumps({"PowerLineFrequency": 50}))
    plan = make_plan(inp, tmp_path / "work", key, schema)
    (e,) = ephys(plan)
    assert e.datatype == "eeg" and e.entities == {"task": "rest"} and e.status == "ok"
    by_path = {a.path: a for a in plan.ancillary}
    sub = f"sub-{e.subject}"
    for path in ("task-rest_eeg.json", "task-rest_coordsystem.json", f"{sub}/{sub}_task-rest_eeg.json"):
        a = by_path[path]
        assert a.action == "drop" and a.locked and a.reason == "electrophysiology sidecars are generated by aimport"
    assert by_path["task-rest_events.json"].action == "keep" and not by_path["task-rest_events.json"].locked
    assert not any("/eeg/" in a.path for a in plan.ancillary)  # the claimed datatype folder


# --- MRI and ephys together --------------------------------------------------------------------


def test_indices_do_not_collide(tmp_path, key, schema):
    from aimport.ephys.module import EPHYS_INDEX_BASE as base

    inp = tmp_path / "in"
    planted_edf(inp / "eeg")
    planted_fif(inp / "meg")
    core = parse_core(FIXTURES / "ezbids_core_siemens.json")
    plan = make_plan(inp, tmp_path / "work", key, schema, core=copy.deepcopy(core))
    mri = [e for e in plan.entries if e.modality == "mri"]
    eph = ephys(plan)
    assert mri and eph
    assert not {e.subject_idx for e in mri} & {e.subject_idx for e in eph}
    assert not {e.series_idx for e in mri} & {e.series_idx for e in eph}
    assert len({e.id for e in plan.entries}) == len(plan.entries)
    # microscopy (phase 2) numbers from 1_000_000: the ranges stay apart
    assert base >= 2_000_000 and max(e.series_idx for e in mri) < 1_000_000
    # MRI subject IDs and sessions are those of an MRI-only plan (ephys is planned after them)
    with PseudonymKey.load(tmp_path / "keys-mri-only", "proj") as other:
        mri_only = build_plan(copy.deepcopy(core), tmp_path / "empty", other, set(), None, schema, "bids")
    assert [(e.id, e.subject, e.session) for e in mri] == [(e.id, e.subject, e.session) for e in mri_only.entries]
    assert not {e.subject for e in mri} & {e.subject for e in eph}


def test_indices_do_not_collide_mri_micr_ephys(tmp_path, key, schema):
    """MRI < 1_000_000 <= microscopy < 2_000_000 <= ephys, all three in one plan; MRI as in an MRI-only plan."""
    from aimport.micr.module import MICR_INDEX_BASE, MicrModule
    from fixtures.micr_fixtures import planted_ome_tiff

    inp, work = tmp_path / "in", tmp_path / "work"
    planted_edf(inp / "eeg")
    planted_fif(inp / "meg")
    planted_ome_tiff(inp / "micr" / "stack.ome.tif")
    mm = MicrModule()
    mclaim = mm.claim(inp, [])
    mm.scan(inp, mclaim, work / "micr", lambda msg: None)
    em, eclaim = scan(inp, work)
    core = parse_core(FIXTURES / "ezbids_core_siemens.json")
    plan = build_plan(copy.deepcopy(core), inp, key, set(), None, schema, "bids",
                      exclude=list(mclaim.roots) + list(eclaim.roots),
                      extra_terms=frozenset(mm.terms(work / "micr") | em.terms(work / "ephys")),
                      planners=[lambda: mm.plan(work / "micr", key, set(), None, schema, "bids"),
                                lambda subjects: em.plan(work / "ephys", key, set(), None, schema, "bids",
                                                         subjects=subjects)])
    mri = [e for e in plan.entries if e.modality == "mri"]
    mic = [e for e in plan.entries if e.modality == "micr"]
    eph = ephys(plan)
    assert mri and mic and eph
    assert MICR_INDEX_BASE == 1_000_000 and EPHYS_INDEX_BASE == 2_000_000
    assert all(e.series_idx < MICR_INDEX_BASE and e.subject_idx < MICR_INDEX_BASE for e in mri)
    assert all(MICR_INDEX_BASE <= e.series_idx < EPHYS_INDEX_BASE for e in mic)
    assert all(MICR_INDEX_BASE <= e.subject_idx < EPHYS_INDEX_BASE for e in mic)
    assert all(e.series_idx >= EPHYS_INDEX_BASE and e.subject_idx >= EPHYS_INDEX_BASE for e in eph)
    assert len({e.id for e in plan.entries}) == len(plan.entries)
    with PseudonymKey.load(tmp_path / "keys-mri-only", "proj") as other:
        mri_only = build_plan(copy.deepcopy(core), tmp_path / "empty", other, set(), None, schema, "bids")
    assert [(e.id, e.subject, e.session) for e in mri] == [(e.id, e.subject, e.session) for e in mri_only.entries]
    assert not {e.subject for e in mri} & ({e.subject for e in mic} | {e.subject for e in eph})


def test_headshape_warning(tmp_path, key, schema):
    inp = tmp_path / "in"
    planted_fif(inp)
    plan = make_plan(inp, tmp_path / "work", key, schema)
    assert HEADSHAPE_WARNING in plan.warnings
    inp2 = tmp_path / "in2"
    planted_edf(inp2)
    assert HEADSHAPE_WARNING not in make_plan(inp2, tmp_path / "work2", key, schema).warnings


def test_load_size(tmp_path, key, schema, monkeypatch):
    inp = tmp_path / "in"
    planted_edf(inp)
    monkeypatch.setattr(ephys_module.readers, "WARN_LOAD_BYTES", 1000)
    plan = make_plan(inp, tmp_path / "work", key, schema)
    (e,) = ephys(plan)
    assert e.status == "ok"
    assert any(w.startswith(f"converting sub-{e.subject}_task-rest_eeg.vhdr loads about") for w in plan.warnings)
    monkeypatch.setenv("AIMPORT_EPHYS_MAX_LOAD_BYTES", "2000")
    plan = make_plan(inp, tmp_path / "work3", key, schema)
    (e,) = ephys(plan)
    assert e.status == "unsupported" and e.exclude and e.reason.startswith("converting sub-")


# --- fix round 1 -------------------------------------------------------------------------------


def edf_record(rel: str, when: str, his_id: str | None = "P1", run: str | None = None) -> dict:
    """A records.json record as the scan writes it (header facts only)."""
    info = {"ch_types": {"eeg": 2}, "n_channels": 2, "n_times": 10, "sfreq": 256.0, "duration_s": 1.0,
            "meas_date": when}
    if his_id:
        info["his_id"] = his_id
    return {"rel": rel, "family": "edf", "companions": [], "headshape": [], "empty_room": False,
            "meta": {"run": run} if run else {}, "info": info, "error": None, "terms": [], "event_labels": []}


def test_unusable_session_label_counts_as_none(key, schema):
    # MNE-BIDS's date-labelled session beside session-less recordings on two other days
    recs = [edf_record("sub-01/ses-20250301/eeg/sub-01_ses-20250301_task-rest_eeg.edf", "2025-03-01T09:00:00+00:00"),
            edf_record("sub-01/eeg/a_rest.edf", "2025-02-15T09:00:00+00:00"),
            edf_record("sub-01/eeg/b_rest.edf", "2025-02-16T09:00:00+00:00")]
    mp = ephys_module.plan_entries(recs, key, set(), schema, "bids")
    assert [e.session for e in mp.entries] == ["03", "01", "02"]
    assert all(e.status == "ok" for e in mp.entries)
    assert "20250301" not in json.dumps([asdict(e) for e in mp.entries])
    # a single day besides: no sessions at all
    mp = ephys_module.plan_entries(recs[:2] + [edf_record("sub-01/eeg/b_rest.edf", "2025-03-01T15:00:00+00:00")],
                                   key, set(), schema, "bids")
    assert {e.session for e in mp.entries} == {"01", "02"}


def test_numbered_sessions_skip_input_labels(key, schema):
    recs = [edf_record("sub-01/ses-01/eeg/sub-01_ses-01_task-rest_eeg.edf", "2025-03-01T09:00:00+00:00"),
            edf_record("sub-01/eeg/a_rest.edf", "2025-02-15T09:00:00+00:00"),
            edf_record("sub-01/eeg/b_rest.edf", "2025-02-16T09:00:00+00:00")]
    mp = ephys_module.plan_entries(recs, key, set(), schema, "bids")
    assert [e.session for e in mp.entries] == ["01", "02", "03"]
    assert len({e.session_idx for e in mp.entries}) == 3


def test_one_sub_folder_is_one_subject(key, schema):
    recs = [edf_record("sub-07/eeg/a_rest.edf", "2025-02-15T09:00:00+00:00", his_id=None),
            edf_record("sub-07/eeg/b_rest.edf", "2025-02-15T10:00:00+00:00", his_id="P42"),
            edf_record("sub-08/eeg/c_rest.edf", "2025-02-15T11:00:00+00:00", his_id=None)]
    mp = ephys_module.plan_entries(recs, key, set(), schema, "bids")
    a, b, c = mp.entries
    assert a.subject == b.subject and a.subject_idx == b.subject_idx and c.subject != a.subject
    assert key.subjects["ephys:id=P42"] == a.subject
    assert sum("run:" in o for o in key.subjects) == 1  # sub-08 only
    assert any(w.startswith("electrophysiology: subject identity could not be established for 1 ")
               for w in mp.warnings)


def test_run_local_warning_counts_every_run_local_subject(key, schema):
    recs = [edf_record("sub-07/eeg/a_rest.edf", "2025-02-15T09:00:00+00:00", his_id=None),
            edf_record("rest.edf", "2025-02-15T10:00:00+00:00", his_id=None)]
    mp = ephys_module.plan_entries(recs, key, set(), schema, "bids")
    assert ephys_module.NO_IDENTITY.format(n=2) in mp.warnings


def test_input_runs_kept_when_consistent(key, schema):
    recs = [edf_record("x/sub-01_task-rest_run-05_eeg.edf", "2025-02-15T14:00:00+00:00"),
            edf_record("x/sub-01_task-rest_run-03_eeg.edf", "2025-02-15T09:00:00+00:00"),
            edf_record("y/sub-01_task-oddball_run-02_eeg.edf", "2025-02-15T09:00:00+00:00")]
    mp = ephys_module.plan_entries(recs, key, set(), schema, "bids")
    assert [e.entities.get("run") for e in mp.entries] == ["05", "03", "02"]
    # two recordings claiming the same run: numbered by date instead
    recs[1] = edf_record("z/sub-01_task-rest_run-05_eeg.edf", "2025-02-15T09:00:00+00:00")
    mp = ephys_module.plan_entries(recs, key, set(), schema, "bids")
    assert [e.entities.get("run") for e in mp.entries][:2] == ["2", "1"]


def test_headshape_warning_only_for_written_entries(tmp_path, key, schema):
    inp = tmp_path / "in"
    path = planted_fif(inp)
    path.rename(path.with_name("Smith_John_recording_raw.fif"))  # no task word: needs review, not written
    plan = make_plan(inp, tmp_path / "work", key, schema)
    (e,) = ephys(plan)
    assert e.status == "unknown" and HEADSHAPE_WARNING not in plan.warnings


def mri_core(tmp_path: Path) -> CoreResult:
    """One MRI subject from a sub-01/anat folder, one session."""
    from aimport.ezbids_runner import CoreObject, CoreSeries, CoreSubject

    nii = tmp_path / "in" / "sub-01" / "anat" / "sub-01_T1w.nii.gz"
    return CoreResult(
        series=[CoreSeries(0, "anat/T1w", {}, "", "T1", {}, nii)],
        objects=[CoreObject(0, 0, 0, "2025-02-15", "09:00:00", {}, [nii], {})],
        subjects=[CoreSubject(0, "01", [{"PatientID": "MRN0042", "file_directory": "sub-01/anat"}],
                              [{"session": "", "AcquisitionDate": "2025-02-15"}])])


def test_sub_folder_shared_with_mri(tmp_path, key, schema):
    inp = tmp_path / "in"
    edf(inp / "sub-01" / "eeg" / "sub-01_task-rest_eeg.edf", ["EEG Fp1"], his_id="P5555555")
    edf(inp / "sub-02" / "eeg" / "sub-02_task-rest_eeg.edf", ["EEG Fp1"], his_id="P6666666")
    plan = make_plan(inp, tmp_path / "work", key, schema, core=mri_core(tmp_path))
    mri = [e for e in plan.entries if e.modality == "mri"]
    (m,) = mri
    one, two = sorted(ephys(plan), key=lambda e: e.series_idx)
    assert one.subject == m.subject and one.subject_idx == m.subject_idx
    assert one.session == m.session and one.session_idx == m.session_idx  # the MRI subject's lone session
    assert two.subject != m.subject and two.subject_idx >= EPHYS_INDEX_BASE
    assert "ephys:id=P5555555" not in key.subjects  # the MRI subject's original stands for both
    assert len({e.subject for e in plan.entries}) == 2
    # a subject edit renames the MRI and ephys entries together
    apply_plan_edits(plan, [{"id": m.id, "subject": "zz9"}], schema)
    assert one.subject == "zz9"


def test_emptyroom_subject_not_renamed(tmp_path, key, schema):
    inp = tmp_path / "in"
    meg_fif(inp / "meg" / "subj_rest_raw.fif", MEAS_DATE)
    meg_fif(inp / "meg" / "emptyroom_raw.fif", MEAS_DATE, his_id=None)
    plan = make_plan(inp, tmp_path / "work", key, schema)
    room = next(e for e in ephys(plan) if e.subject == "emptyroom")
    other = next(e for e in ephys(plan) if e.subject != "emptyroom")
    assert "emptyroom" not in key.subjects.values()
    with pytest.raises(ValueError):
        apply_plan_edits(plan, [{"id": room.id, "subject": "noise1"}], schema)
    with pytest.raises(ValueError):
        apply_plan_edits(plan, [{"id": other.id, "subject": "emptyroom"}], schema)


def test_server_never_records_emptyroom(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from aimport import server
    from aimport.server import create_app

    inp = tmp_path / "in"
    meg_fif(inp / "meg" / "subj_rest_raw.fif", MEAS_DATE)
    meg_fif(inp / "meg" / "emptyroom_raw.fif", MEAS_DATE, his_id=None)
    monkeypatch.setattr(server, "client_from_env", lambda: None)
    monkeypatch.setattr(server, "run_ezbids", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no ezBIDS")))
    token = "t" * 32
    app = create_app(inp, tmp_path / "work", tmp_path / "keys", token, ["https://brainlife.io"], ["testserver"])
    try:
        c = TestClient(app)
        c.headers["Authorization"] = f"Bearer {token}"
        assert c.post("/scan", json={"project_id": "proj", "existing_subjects": []}).status_code == 202
        end = __import__("time").time() + 30
        while c.get("/status").json()["stage"] not in ("planned", "failed"):
            assert __import__("time").time() < end
            __import__("time").sleep(0.05)
        assert c.get("/status").json()["stage"] == "planned"
        ids = json.loads((tmp_path / "work" / "subject-ids.json").read_text())
        assert "emptyroom" not in ids.values() and len(ids) == 1
        keyfile = json.loads((tmp_path / "keys" / "proj.aimport-key.json").read_text())
        assert "emptyroom" not in keyfile["subjects"].values() and "emptyroom" not in keyfile["offsets"]
        entries = c.get("/plan").json()["entries"]
        room = next(e for e in entries if e["subject"] == "emptyroom")
        other = next(e for e in entries if e["subject"] != "emptyroom")
        # an edit is not refused because the empty-room subject is not among the recorded IDs
        assert c.patch("/plan", json={"edits": [{"id": room["id"], "keep_headshape": True}]}).status_code == 200
        assert c.patch("/plan", json={"edits": [{"id": other["id"], "subject": "zz1"}]}).status_code == 200
        assert c.patch("/plan", json={"edits": [{"id": room["id"], "subject": "zz2"}]}).status_code == 422
    finally:
        app.state.server.close()


def test_planners_with_and_without_the_mri_subjects():
    from aimport.planner import _call_planner

    assert _call_planner(lambda: "plain", {"01": {}}) == "plain"  # phase 2 planners take no argument
    assert _call_planner(lambda subjects: sorted(subjects), {"01": {}}) == ["01"]
