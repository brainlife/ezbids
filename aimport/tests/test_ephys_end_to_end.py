"""Phase 3 end to end: electrophysiology and optical recordings beside the planted MRI DICOMs.

Drives the real app through its API (TestClient, token, Host header) with the real ezBIDS, writers, defacer and
BIDS validator, and a recording LLM client, as ``test_end_to_end.py`` does. Docker only: the tools are in the image.

- The mixed import (module fixture ``mixed``): every planted builder of ``fixtures/ephys_fixtures.py``, an
  empty-room FIF, an Artinis ``.oxy4`` stub and the planted dcm_qa_xa30 DICOMs, in one subject folder.
- ``test_mne_testing_e2e``: one import per pinned mne-testing-data family (``ephys_data``).
- ``test_bids_examples_ephys``: the layout of one run of each bids-examples set, rebuilt from a synthetic recording.
"""
from __future__ import annotations

import csv
import gzip
import hashlib
import json
import re
import shutil
import sys
from datetime import date, datetime
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

mne = pytest.importorskip("mne")
pytest.importorskip("mne_bids")

from aimport import server  # noqa: E402
from aimport.ephys import gate  # noqa: E402
from aimport.server import create_app  # noqa: E402
from conftest import EPHYS_PLANTED, NATIVE, PLANTED, ephys_tokens, tokens  # noqa: E402

sys.path.insert(0, str(Path(__file__).parent / "fixtures"))
from fetch_dcm_qa import fetch_dcm_qa  # noqa: E402
from fixtures import ephys_fixtures as fx  # noqa: E402
from test_end_to_end import CACHE as DCM_QA_CACHE  # noqa: E402
from test_end_to_end import HOST, TOKEN, Api, Recorder, file_text  # noqa: E402
from test_ephys_write import edf, meg_fif  # noqa: E402

pytestmark = pytest.mark.docker

TERMS = set(EPHYS_PLANTED)  # lowercase already
# the original dates (meas_date, birthday) in every form the gate knows
FORBIDDEN = gate.forbidden_date_forms([fx.MEAS_DATE, date(1970, 1, 1)])
DATA_EXTS = (".nii.gz", ".nii", ".edf", ".bdf", ".eeg", ".fif", ".snirf", ".nwb")
QA_KINDS = ("traces", "psd", "channels")
OXY4 = "Smith_John_rest.oxy4"
MIB = 2**20


def found(text: str) -> set[str]:
    """Every planted ephys term, and the MRI planted and native terms, in text."""
    return ephys_tokens(text) | ((PLANTED | NATIVE) & tokens(text))


def sha_tree(root: Path) -> dict[str, str]:
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*")) if p.is_file()}


def tree_bytes(root: Path, skip: tuple[str, ...] = ()) -> int:
    total = 0
    for p in root.rglob("*"):
        rel = p.relative_to(root).as_posix()
        if p.is_file() and not any(rel == s or rel.startswith(s + "/") for s in skip):
            total += p.stat().st_size
    return total


def read_tsv(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def ephys_entries(plan: dict) -> list[dict]:
    return [e for e in plan["entries"] if e.get("modality") == "ephys"]


def name_tasks(api: Api) -> None:
    """Give every writable ephys entry whose task is unknown the task ``rest`` (a reviewer edit)."""
    plan = api.call("GET", "/plan").json()
    edits = [{"id": e["id"], "entities": {**e["entities"], "task": "rest"}} for e in ephys_entries(plan)
             if e["ephys_format"] and e["entities"].get("task") == "unknown"]
    if edits:
        assert api.call("PATCH", "/plan", json={"edits": edits}).status_code == 200


def browser(api: Api) -> Api:
    """A browser-like Api for the viewer: no token, only the session cookie from the code exchange."""
    code = api.call("POST", "/viewer/session").json()["code"]
    b = Api.__new__(Api)
    b.client = TestClient(api.client.app, base_url=f"http://{HOST}")
    b.bodies = api.bodies  # one list: every body the run returned
    r = b.call("GET", f"/viewer/open?code={code}", follow_redirects=False)
    assert r.status_code == 303, r.text
    return b


def scan(api: Api, target: str = "bids") -> dict:
    assert api.call("POST", "/scan", json={"project_id": "proj", "target": target}).status_code == 202
    status = api.wait()
    assert status["stage"] == "planned", status
    return api.call("GET", "/plan").json()


def execute(api: Api, **approve) -> dict:
    r = api.call("POST", "/approve", json=approve)
    assert r.status_code == 200 and r.json()["approved"] is True, r.text
    assert api.call("POST", "/execute").status_code == 202
    return api.wait()


def ephys_input(inp: Path) -> None:
    """Every planted builder in the planted subject folder, an empty room an hour before the planted FIF on the same
    day, and an Artinis .oxy4 stub."""
    for build in (fx.planted_edf, fx.planted_bdf, fx.planted_brainvision, fx.planted_eeglab, fx.planted_fif,
                  fx.planted_snirf, fx.planted_ctf_pos, fx.planted_kit_hsp, fx.planted_nwb):
        build(inp)
    meg_fif(inp / fx.SUBJECT_DIR / "emptyroom_raw.fif", fx.MEAS_DATE.replace(hour=9), his_id=None)
    (inp / fx.SUBJECT_DIR / OXY4).write_bytes(b"OXY4" + bytes(60))


class Run:
    """What one import left: the API bodies, the LLM requests, the work folder and the input's hashes."""

    def __init__(self, inp: Path, work: Path, keys: Path):
        self.inp, self.work, self.keys = inp, work, keys
        self.rec = Recorder()
        self.app = create_app(inp, work, keys, TOKEN, [], [HOST])
        self.api = Api(self.app)
        self.before = sha_tree(inp)
        self.plan: dict = {}
        self.status: dict = {}
        self.png: list[bytes] = []

    @property
    def out(self) -> Path:
        return self.work / "output" / "bids"

    def close(self) -> None:
        self.app.state.server.close()

    def manifest_ephys(self) -> dict[str, list[str]]:
        ids = {e["id"] for e in ephys_entries(self.plan)}
        return {k: v for k, v in (self.status.get("manifest") or {}).items() if k in ids}

    def look(self) -> None:
        """Every route that shows recordings: the plan, status, events, viewer pages, trace windows, snapshots."""
        self.plan = self.api.call("GET", "/plan").json()
        self.api.call("GET", "/status")
        self.api.events()
        b = browser(self.api)
        assert b.call("GET", "/viewer/").status_code == 200
        for eid in self.manifest_ephys():
            assert b.call("GET", f"/viewer/traces/{eid}").status_code == 200, eid
            r = b.call("GET", f"/qa/traces/{eid}")
            assert r.status_code == 200, (eid, r.text)
            for kind in QA_KINDS:
                r = b.call("GET", f"/qa/png/{eid}/{kind}.png")
                assert r.status_code == 200, (eid, kind)
                self.png.append(r.content)


def _start(tmp: Path, make_input, monkeypatch) -> Run:
    inp = tmp / "in"
    make_input(inp)
    run = Run(inp, tmp / "work", tmp / "keys")
    monkeypatch.setattr(server, "client_from_env", lambda: run.rec)
    return run


@pytest.fixture(scope="module")
def mixed(tmp_path_factory):
    """The mixed import: planted DICOMs and every planted recording; E001 named ``greeting``; quickshear."""
    tmp = tmp_path_factory.mktemp("mixed")

    def make_input(inp: Path) -> None:
        fetch_dcm_qa(inp, plant=True, cache=DCM_QA_CACHE)
        ephys_input(inp)

    with pytest.MonkeyPatch.context() as mp:
        run = _start(tmp, make_input, mp)
        try:
            run.scanned = scan(run.api)
            name_tasks(run.api)
            r = run.api.call("PATCH", "/plan", json={"event_names": {"E001": "greeting"}})
            assert r.status_code == 200, r.text
            run.status = execute(run.api, deface_method="quickshear")
            run.look()
        finally:
            run.close()
    yield run


@pytest.fixture(scope="module")
def headshape_kept(tmp_path_factory):
    """An ephys-only import of the planted FIF (200 head-shape points in its dig), with ``keep_headshape``.

    The planted ``.pos``/``.hsp`` are not here: they are claimed only beside a CTF or KIT recording, so alone with a
    FIF they would be left for ezBIDS, which fails a scan that holds no imaging files."""
    tmp = tmp_path_factory.mktemp("headshape")

    def make_input(inp: Path) -> None:
        fx.planted_fif(inp)

    with pytest.MonkeyPatch.context() as mp:
        run = _start(tmp, make_input, mp)
        try:
            plan = scan(run.api)
            name_tasks(run.api)
            edits = [{"id": e["id"], "keep_headshape": True} for e in ephys_entries(plan) if e["datatype"] == "meg"]
            assert edits and run.api.call("PATCH", "/plan", json={"edits": edits}).status_code == 200
            run.status = execute(run.api)
            run.look()
        finally:
            run.close()
    yield run


def _meg_fif(run: Run) -> Path:
    for files in run.manifest_ephys().values():
        for rel in files:
            if rel.endswith("_meg.fif") and "emptyroom" not in rel:
                return run.out / rel
    raise AssertionError(run.manifest_ephys())


def _extra_points(path: Path) -> int:
    info = mne.io.read_info(path, verbose=False)
    return sum(1 for d in info["dig"] or [] if d["kind"] == mne.io.constants.FIFF.FIFFV_POINT_EXTRA)


def _dig_kinds(path: Path) -> set[int]:
    return {int(d["kind"]) for d in mne.io.read_info(path, verbose=False)["dig"] or []}


# --- the mixed import -----------------------------------------------------------------------------------------


def test_ephys_e2e_validated(mixed):
    s = mixed.status
    assert s["stage"] == "validated", s
    assert s["validation"]["ok"] is True, s["validation"]["errors"][:5]
    # MRI is not regressed by the recordings beside it: anat and func are still planned and written
    entries = mixed.plan["entries"]
    assert any(e["datatype"] == "anat" and not e["exclude"] for e in entries if e.get("modality", "mri") == "mri")
    assert any(e["datatype"] == "func" and not e["exclude"] for e in entries if e.get("modality", "mri") == "mri")
    assert list(mixed.out.rglob("*_T1w.nii.gz")) and list(mixed.out.rglob("*_bold.nii.gz"))
    # every writable recording was written, the empty room too; NIRS as SNIRF, the NWB as NWB
    written = [rel for files in mixed.manifest_ephys().values() for rel in files]
    for suffix in ("_eeg.vhdr", "_meg.fif", "_nirs.snirf", "_ieeg.nwb"):
        assert any(rel.endswith(suffix) for rel in written), (suffix, written)
    assert any(rel.startswith("sub-emptyroom/") for rel in written)
    meg = next(e for e in ephys_entries(mixed.plan) if e["datatype"] == "meg" and e["subject"] != "emptyroom")
    assert meg["empty_room"] and meg["empty_room"] in mixed.manifest_ephys()


def test_ephys_e2e_no_leak(mixed):
    # positive controls: the planted values are really in the input
    sub = mixed.inp / fx.SUBJECT_DIR
    assert {"mrn0042", "eegtech_jane"} <= ephys_tokens((sub / "Smith_John_rest.edf").read_bytes().decode("latin-1"))
    assert "dr jane" in ephys_tokens((sub / "Smith_John_rest.vmrk").read_text())

    # (a) every LLM request (the classifications and the metadata draft), and plan/scan/status.json
    assert mixed.rec.requests and "classify" in mixed.rec.steps
    assert any('"FormatFamily"' in r for r in mixed.rec.requests), "the recordings were sent to the agent"
    for i, request in enumerate(mixed.rec.requests):
        assert not found(request), (i, found(request))
    for name in ("plan.json", "scan.json", "status.json"):
        text = (mixed.work / name).read_text()
        assert not found(text), (name, found(text))

    # (b) every body the API returned: /plan, /status, /events, /viewer/*, /qa/traces/* and /qa/png/*
    assert len(mixed.api.bodies) > 10 and len(mixed.png) == 3 * len(mixed.manifest_ephys())
    for body in mixed.api.bodies:
        assert not found(body), found(body)
    for png in mixed.png:
        assert png.startswith(b"\x89PNG") and not found(png.decode("latin-1")), found(png.decode("latin-1"))

    # (c) every byte under output/bids: the gate over every file (headers, sidecars, copies of a source) ...
    out = mixed.out
    files = [p for p in out.rglob("*") if p.is_file()]
    assert not found("\n".join(str(p.relative_to(out)) for p in files))
    sources = [p for p in mixed.inp.rglob("*") if p.is_file() and fx.SUBJECT_DIR in p.parts
               and p.suffix.lower() not in ("", ".dcm")]
    shifted = {datetime.fromisoformat(row["acq_time"]).date() for p in out.rglob("*_scans.tsv")
               for row in read_tsv(p) if row.get("acq_time", "n/a") != "n/a"}
    assert shifted and fx.MEAS_DATE.date() not in shifted
    # NIfTI images are the MRI path's, checked below as phase 1 checks them (header text fields): the ephys gate's
    # byte scan of unknown binary files reads their gzip stream as text and can match by chance
    checked = [p for p in files if not p.name.endswith((".nii", ".nii.gz"))]
    violations = gate.check(checked, out, TERMS, FORBIDDEN, sources, allowed_dates=shifted)
    assert violations == [], violations
    # ... and a raw byte search of every non-data file (gunzipped), plus the NIfTI header text fields
    for p in files:
        name = p.name.lower()
        if name.endswith((".nii", ".nii.gz")):
            text = file_text(p)
        elif name.endswith(DATA_EXTS):
            continue
        else:
            raw = p.read_bytes()
            if name.endswith(".gz"):
                raw = gzip.decompress(raw)
            text = raw.decode("latin-1")
        assert not found(text), (p.relative_to(out), found(text))
    # the identifying lists stay local, under work/ephys
    assert (mixed.work / "ephys" / "events.json").is_file() and not list(out.rglob("events.json"))


def test_ephys_e2e_events_named(mixed):
    assert mixed.plan["event_names"]["E001"] == "greeting"
    events = [p for files in mixed.manifest_ephys().values() for p in files if p.endswith("_events.tsv")]
    named = [rel for rel in events if any(r["trial_type"] == "greeting" for r in read_tsv(mixed.out / rel))]
    assert named, events
    for rel in events:
        for row in read_tsv(mixed.out / rel):
            label = row["trial_type"]
            assert label == "greeting" or re.fullmatch(r"E\d{3}", label) or not found(label), (rel, label)
            assert label != "E001", (rel, "a named code is written by its name")


def test_ephys_e2e_headshape_opt_in(mixed, headshape_kept):
    # the default: no head-shape points, no headshape file, DigitizedHeadPoints false; fiducials and HPI kept
    default = _meg_fif(mixed)
    assert _extra_points(default) == 0
    kinds = _dig_kinds(default)
    assert {mne.io.constants.FIFF.FIFFV_POINT_CARDINAL, mne.io.constants.FIFF.FIFFV_POINT_HPI} <= kinds
    assert not list(mixed.out.rglob("*_headshape.*"))
    sidecar = json.loads(default.with_name(default.name.replace("_meg.fif", "_meg.json")).read_text())
    assert sidecar.get("DigitizedHeadPoints") is False
    # opted in: all 200 are kept, with the fiducials and HPI
    assert headshape_kept.status["stage"] == "validated", headshape_kept.status
    kept = _meg_fif(headshape_kept)
    assert _extra_points(kept) == fx.FIF_DIG_COUNTS["extra"]
    assert {mne.io.constants.FIFF.FIFFV_POINT_CARDINAL, mne.io.constants.FIFF.FIFFV_POINT_HPI} <= _dig_kinds(kept)
    for body in headshape_kept.api.bodies:
        assert not found(body), found(body)


def test_ephys_e2e_unsupported_reported(mixed):
    stub = [e for e in ephys_entries(mixed.plan) if e["status"] == "unsupported"]
    assert len(stub) == 1, stub
    e = stub[0]
    assert e["exclude"] is True and e["reason"] == "export to SNIRF first" and not e["ephys_format"]
    assert e["id"] not in (mixed.status.get("manifest") or {})
    assert not list(mixed.out.rglob("*.oxy*"))
    # the scan's own summary names the problem too, without the file's name
    assert not found(json.dumps(e))


def test_ephys_e2e_no_source_copy(mixed, headshape_kept):
    for run in (mixed, headshape_kept):
        assert sha_tree(run.inp) == run.before, "the input is unchanged"
        assert not (run.work / "ephys" / "scratch").exists(), "scratch is deleted after each write"
    # the ephys-only import: the work folder minus the output and the QA snapshots holds no recording
    assert tree_bytes(headshape_kept.work, ("output/bids", "ephys/qa")) < 2 * MIB
    # the mixed import: the same, besides the MRI path's own folders (ezBIDS's staging, the pre-deface originals)
    assert tree_bytes(mixed.work, ("output/bids", "ephys/qa", "ezbids", "pre-deface")) < 2 * MIB


def test_ephys_e2e_datatypes_target(tmp_path, monkeypatch):
    def make_input(inp: Path) -> None:
        fx.planted_brainvision(inp)
        fx.planted_fif(inp)
        fx.planted_snirf(inp)
        fx.planted_nwb(inp)
        edf(inp / "arm" / "arm_rest.edf", ["EMG L1", "EMG L2"], his_id="P3333333")

    run = _start(tmp_path, make_input, monkeypatch)
    try:
        plan = scan(run.api, target="datatypes")
    finally:
        run.close()
    by_dt = {}
    for e in ephys_entries(plan):
        by_dt.setdefault(e["datatype"], []).append(e)
    assert set(by_dt) == {"eeg", "meg", "ieeg", "nirs", "emg"}, by_dt.keys()
    assert [(e["brainlife_datatype"], e["brainlife_tags"], e["exclude"]) for e in by_dt["eeg"]] == \
        [("neuro/eeg/brainvision", ["rest"], False)]
    assert [(e["brainlife_datatype"], e["brainlife_tags"], e["exclude"]) for e in by_dt["meg"]] == \
        [("neuro/meg/fif", ["rest"], False)]
    for dt in ("ieeg", "nirs", "emg"):
        for e in by_dt[dt]:
            assert e["exclude"] is True and e["brainlife_datatype"] is None, e
            assert f"(draft neuro/{dt}/{dt}, not registered yet)" in e["reason"], e["reason"]
    for body in run.api.bodies:
        assert not found(body), found(body)


# --- mne-testing-data: one import per family ----------------------------------------------------------------------

UNSUPPORTED_FAMILIES = {"egi": "EGI .mff needs the mffpy package"}


@pytest.mark.ephys_data
@pytest.mark.parametrize("family", sorted(fx.MNE_TESTING_FAMILIES))
def test_mne_testing_e2e(tmp_path, monkeypatch, family):
    def make_input(inp: Path) -> None:
        for name, path in fx.fetch_mne_testing(fx.MNE_TESTING_FAMILIES[family]).items():
            target = inp / family / name.rstrip("/")
            target.parent.mkdir(parents=True, exist_ok=True)
            if path.is_dir():
                shutil.copytree(path, target)
            else:
                shutil.copyfile(path, target)

    run = _start(tmp_path, make_input, monkeypatch)
    monkeypatch.setattr(server, "client_from_env", lambda: None)  # heuristics only
    try:
        plan = scan(run.api)
        entries = ephys_entries(plan)
        assert entries, plan["entries"]
        if family in UNSUPPORTED_FAMILIES:
            assert all(e["status"] == "unsupported" and e["reason"] == UNSUPPORTED_FAMILIES[family]
                       for e in entries), entries
            return
        name_tasks(run.api)
        entries = ephys_entries(run.api.call("GET", "/plan").json())
        assert any(e["status"] == "ok" and not e["exclude"] for e in entries), entries
        run.status = execute(run.api)
    finally:
        run.close()
    assert run.status["stage"] == "validated", run.status
    assert run.status["validation"]["ok"] is True
    assert sha_tree(run.inp) == run.before


@pytest.mark.ephys_data
def test_openneuro_fnirs_e2e(tmp_path, monkeypatch):
    """The one OpenNeuro run (CC0, ds005929 1.0.1, a Homer3 SNIRF with aux and stim groups) imports and validates;
    its measurement date is not in the output."""
    def make_input(inp: Path) -> None:
        dest = inp / fx.OPENNEURO_FNIRS["path"]
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(fx.fetch_openneuro_fnirs(), dest)

    run = _start(tmp_path, make_input, monkeypatch)
    monkeypatch.setattr(server, "client_from_env", lambda: None)
    try:
        plan = scan(run.api)
        (e,) = ephys_entries(plan)
        assert (e["datatype"], e["ephys_format"]) == ("nirs", "SNIRF"), e
        name_tasks(run.api)
        run.status = execute(run.api)
    finally:
        run.close()
    assert run.status["stage"] == "validated", run.status
    files = [p for p in run.out.rglob("*") if p.is_file()]
    assert any(p.name.endswith("_nirs.snirf") for p in files)
    assert gate.check(files, run.out, set(), gate.forbidden_date_forms([date(2024, 11, 14)]), [],
                      allowed_dates=[]) == []
    assert sha_tree(run.inp) == run.before


# --- bids-examples: the layout of one run per example -----------------------------------------------------------

RECORDING_EXTS = (".edf", ".bdf", ".vhdr", ".set", ".snirf", ".ds", ".fif", ".nwb")
FORMAT_OF = {".edf": "EDF", ".bdf": "BDF", ".vhdr": "BrainVision", ".snirf": "SNIRF", ".ds": "FIF", ".fif": "FIF"}
RUN_ENTITIES = ("sub", "ses", "task", "acq", "run")
EPHYS_DATATYPES = ("eeg", "meg", "ieeg", "nirs", "emg")
MNE_TYPES = {"EEG": "eeg", "EOG": "eog", "HEOG": "eog", "VEOG": "eog", "ECG": "ecg", "EMG": "emg", "SEEG": "seeg",
             "ECOG": "ecog", "DBS": "dbs", "MISC": "misc", "TRIG": "stim", "NIRSCWAMPLITUDE": "fnirs_cw_amplitude"}
MAX_CHANNELS = 64
ENTITY_KEYS = {"task": "task", "acq": "acquisition", "run": "run"}
# runs that need an entity aimport does not plan (recording-): no run of the example qualifies
NO_RUN = {"emg_ConcurrentIndependentUnits": "every recording carries the recording- entity"}


def _entities(name: str) -> tuple[dict[str, str], str, str]:
    """(entities, suffix, extension) of a BIDS file name."""
    stem, dot, ext = name.partition(".")
    *pairs, suffix = stem.split("_")
    return dict(p.split("-", 1) for p in pairs), suffix, dot + ext


def _example_run(root: Path) -> Path | None:
    """The first raw recording (sorted) of a datatype aimport writes whose entities are all run entities."""
    for p in sorted(root.glob("sub-*/**/*")):
        if p.parent.name not in EPHYS_DATATYPES or not p.name.endswith(RECORDING_EXTS):
            continue
        ents, suffix, _ = _entities(p.name)
        if suffix == p.parent.name and set(ents) <= set(RUN_ENTITIES):
            return p
    return None


def _channels(example_rec: Path) -> tuple[list[str], list[str]]:
    ents, suffix, ext = _entities(example_rec.name)
    tsv = example_rec.with_name(example_rec.name[: -len(ext)].rsplit("_", 1)[0] + "_channels.tsv")
    names, types = [], []
    for row in read_tsv(tsv) if tsv.is_file() else []:
        row = {k.lstrip("﻿"): v for k, v in row.items()}
        t = MNE_TYPES.get(row["type"].upper())
        if t is None or row["name"] in names:
            continue
        names.append(row["name"])
        types.append(t)
    return names[:MAX_CHANNELS], types[:MAX_CHANNELS]


def _clean_snirf(path: Path, n_pairs: int) -> None:
    """A CW SNIRF with neutral metadata: n_pairs source-detector pairs at 760/850 nm."""
    import h5py

    path.parent.mkdir(parents=True, exist_ok=True)
    n_t = fx.N_SAMPLES
    rng = np.random.default_rng(0)
    pairs = [(1 + i // 2, 1 + i % 2) for i in range(max(1, n_pairs))]
    with h5py.File(path, "w") as f:
        f.create_dataset("formatVersion", data=np.bytes_("1.0"))
        nirs = f.create_group("nirs")
        tags = nirs.create_group("metaDataTags")
        for k, v in {"SubjectID": "x", "MeasurementDate": "unknown", "MeasurementTime": "unknown",
                     "LengthUnit": "mm", "TimeUnit": "s", "FrequencyUnit": "Hz"}.items():
            tags.create_dataset(k, data=np.bytes_(v))
        data = nirs.create_group("data1")
        data.create_dataset("dataTimeSeries", data=1.0 + 0.01 * rng.standard_normal((n_t, 2 * len(pairs))))
        data.create_dataset("time", data=np.arange(n_t) / fx.SFREQ)
        k = 1
        for wl in (1, 2):
            for s, d in pairs:
                ml = data.create_group(f"measurementList{k}")
                for key, value in (("sourceIndex", s), ("detectorIndex", d), ("wavelengthIndex", wl),
                                   ("dataType", 1), ("dataTypeIndex", 1)):
                    ml.create_dataset(key, data=np.int32(value))
                k += 1
        n_src = max(s for s, _ in pairs)
        probe = nirs.create_group("probe")
        probe.create_dataset("wavelengths", data=np.array([760.0, 850.0]))
        probe.create_dataset("sourcePos3D", data=np.array([[30.0 * i, 0.0, 80.0] for i in range(n_src)]))
        probe.create_dataset("detectorPos3D", data=np.array([[0.0, 30.0, 80.0], [30.0, 30.0, 80.0]]))
        probe.create_dataset("sourceLabels", data=np.array([f"S{i + 1}".encode() for i in range(n_src)]))
        probe.create_dataset("detectorLabels", data=np.array([b"D1", b"D2"]))
        stim = nirs.create_group("stim1")
        stim.create_dataset("name", data=np.bytes_("1"))
        stim.create_dataset("data", data=np.array([[2.0, 5.0, 1.0]]))


def _synthetic(example_rec: Path, inp: Path) -> bool:
    """Write a recording with the example's channel types under a neutral name (the example's labels would be
    identifying path words); returns whether events are expected."""
    ents, datatype, ext = _entities(example_rec.name)
    stem = example_rec.name[: -len(ext)]
    events = example_rec.with_name(stem.rsplit("_", 1)[0] + "_events.tsv").is_file()
    folder = inp / "synthetic"
    folder.mkdir(parents=True, exist_ok=True)
    if datatype == "nirs":
        names, _ = _channels(example_rec)
        _clean_snirf(folder / "recording.snirf", min(4, max(1, len(names) // 2)))
        return True
    if datatype == "meg":  # CTF axial gradiometers have no RawArray form: four magnetometers with dig points
        meg_fif(folder / "recording_raw.fif", fx.MEAS_DATE, his_id=None)
        return False
    names, types = _channels(example_rec)
    if not names:
        names, types = [f"{datatype.upper()}{i}" for i in range(1, 5)], [datatype if datatype != "ieeg" else "seeg"] * 4
    info = mne.create_info(names, fx.SFREQ, types)
    raw = mne.io.RawArray(np.random.default_rng(0).standard_normal((len(names), fx.N_SAMPLES)) * 1e-5, info,
                          verbose=False)
    raw.set_meas_date(fx.MEAS_DATE)
    with raw.info._unlock():
        raw.info["line_freq"] = 50.0
    if events:
        raw.set_annotations(mne.Annotations([1.0, 3.0], [0.0, 0.0], ["stimulus", "response"]))
    raw.save(folder / "recording_raw.fif", overwrite=True, verbose=False)
    return events


def _no_space(name: str) -> str:
    return re.sub(r"_space-[A-Za-z0-9]+", "", name)


def _applies(name: str, run_ents: dict[str, str]) -> bool:
    """Whether an example file in the run's folder belongs to the run (its entities are the run's, or a subset
    of them by inheritance; ``space-`` is ignored)."""
    ents, _, _ = _entities(name)
    ents.pop("space", None)
    return all(run_ents.get(k) == v for k, v in ents.items())


@pytest.mark.parametrize("example", fx.BIDS_EXAMPLES_SETS)
def test_bids_examples_ephys(tmp_path, schema, example):
    from aimport.pseudonyms import PseudonymKey
    from aimport.validate import validate_bids
    from test_ephys_write import plan_and_write

    root = fx.fetch_bids_examples([example])[example]
    rec = _example_run(root)
    if example in NO_RUN:
        assert rec is None, rec
        pytest.skip(NO_RUN[example])
    assert rec is not None
    run_ents, datatype, ext = _entities(rec.name)
    inp = tmp_path / "in"
    events = _synthetic(rec, inp)
    fmt = FORMAT_OF.get(ext, "BrainVision")

    def edit(plan):
        """The reviewer gives the recording the example's subject, session and entities: input labels that are
        not generic words are identifying terms by design, so the plan leaves them out."""
        from aimport.planner import apply_plan_edits

        (e,) = [e for e in plan.entries if e.modality == "ephys" and not e.exclude]
        entities = {ENTITY_KEYS[k]: v for k, v in run_ents.items() if k in ENTITY_KEYS}
        apply_plan_edits(plan, [{"id": e.id, "subject": run_ents["sub"], "session": run_ents.get("ses"),
                                 "datatype": datatype, "suffix": datatype, "entities": entities}], schema)
        apply_plan_edits(plan, [{"id": e.id, "ephys_format": fmt}], schema)
        assert e.status == "ok" and not e.exclude, e.reason

    key = PseudonymKey.load(tmp_path / "keys", "proj")
    try:
        plan, out, manifest = plan_and_write(inp, tmp_path, key, schema, edit=edit)
    finally:
        key.close()
    (entry,) = [e for e in plan.entries if e.modality == "ephys" and not e.exclude]
    assert entry.datatype == datatype
    written = manifest[entry.id]
    rel_dir = rec.parent.relative_to(root).as_posix()

    # the recording: the example's name (a .ds or .set example is written as FIF or BrainVision)
    ours_rec = [r for r in written if _entities(r.rsplit("/", 1)[-1])[1] == datatype
                and r.endswith(tuple(FORMAT_OF) + (".nwb",))]
    assert len(ours_rec) == 1, written
    want = rec.name[: -len(ext)] + (ext if ext in FORMAT_OF and FORMAT_OF[ext] == fmt and ext != ".ds" else
                                    {"BrainVision": ".vhdr", "FIF": ".fif"}[fmt])
    assert ours_rec[0] == f"{rel_dir}/{want}", (ours_rec, rel_dir, want)

    # every sidecar the example has for this run is written under the same name; ours are all in its folder
    example_names = {p.name for p in rec.parent.iterdir() if _applies(p.name, run_ents)}
    ours = {r.rsplit("/", 1)[-1]: r for r in written}
    assert all(r.startswith(rel_dir + "/") for r in written if "_scans.tsv" not in r), written
    for name in sorted(example_names):
        _, suffix, sext = _entities(name)
        if suffix == datatype and sext != ".json":
            continue  # the recording (and its BrainVision companions), checked above
        if suffix in ("electrodes", "photo", "physio", "headshape") or (suffix == "coordsystem" and datatype != "meg"
                                                                         and datatype != "nirs"):
            continue  # positions, photos and physio come from files the synthetic recording does not have
        if suffix == "events" and not events:
            continue
        assert name in ours, (name, sorted(ours))
    for name in ours:
        _, suffix, sext = _entities(name)
        if suffix in ("scans",) or (suffix == datatype and sext != ".json"):
            continue
        # positions name their space (space-<label>); the synthetic recording has none, so space is not compared
        same_kind = {_no_space(n) for n in example_names if _entities(n)[1:] == (suffix, sext)}
        if same_kind:
            assert _no_space(name) in same_kind, (name, same_kind)

    # the output validates as it is: no ignores (the example's own config ignores EMPTY_FILE; ours has data)
    result = validate_bids(out)
    assert result.ok, json.dumps(result.errors, indent=1)[:3000]
