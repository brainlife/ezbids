"""Phase 3 Task 9: in-memory de-identification and the MNE-BIDS writer (eeg, ieeg, emg, meg)."""
from __future__ import annotations

import csv
import hashlib
import json
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pytest

mne = pytest.importorskip("mne")
pytest.importorskip("mne_bids")

from aimport import modality, server  # noqa: E402
from aimport.ephys import gate, headers  # noqa: E402
from aimport.ephys import write as ephys_write  # noqa: E402
from aimport.ephys.module import EphysModule  # noqa: E402
from aimport.ezbids_runner import CoreResult  # noqa: E402
from aimport.planner import apply_plan_edits, build_plan  # noqa: E402
from aimport.plan import Plan  # noqa: E402
from aimport.pseudonyms import PseudonymKey  # noqa: E402
from aimport.writer import write_bids  # noqa: E402
from conftest import EPHYS_PLANTED, ephys_tokens  # noqa: E402
from fixtures import ephys_fixtures as fx  # noqa: E402

TEXT = (".json", ".tsv", ".vhdr", ".vmrk", ".pos", ".md", ".txt")
TERMS = set(EPHYS_PLANTED)
FORBIDDEN = gate.forbidden_date_forms([fx.MEAS_DATE, date(1970, 1, 1)])


@pytest.fixture
def key(tmp_path):
    k = PseudonymKey.load(tmp_path / "keys", "proj")
    yield k
    k.close()


def _plan(inp: Path, tmp_path: Path, key, schema, edit=None) -> tuple[Plan, EphysModule, Path]:
    work = tmp_path / "work"
    m = EphysModule()
    claim = m.claim(inp, [])
    m.scan(inp, claim, work / "ephys", lambda msg: None)
    plan = build_plan(CoreResult(), inp, key, set(), None, schema, "bids", exclude=claim.roots,
                      extra_terms=frozenset(m.terms(work / "ephys")),
                      planners=[lambda subjects: m.plan(work / "ephys", key, set(), None, schema, "bids",
                                                        subjects=subjects)])
    edits = [{"id": e.id, "entities": {**e.entities, "task": "rest"}} for e in plan.entries
             if e.modality == "ephys" and e.datatype and e.entities.get("task") == "unknown"]
    if edits:
        apply_plan_edits(plan, edits, schema)
    if edit is not None:
        edit(plan)
    plan.approved = True
    return plan, m, work


def plan_and_write(inp: Path, tmp_path: Path, key, schema, edit=None, **kw):
    plan, m, work = _plan(inp, tmp_path, key, schema, edit)
    staged = tmp_path / "staged"
    staged.mkdir(exist_ok=True)
    out = tmp_path / "out"
    manifest: dict = {}
    write_bids(plan, CoreResult(), inp, m.terms(work / "ephys"), key, schema, out, staged_dir=staged,
               exclude=m.claim(inp, []).roots, manifest=manifest, modules=modality.modules(), work_dir=work, **kw)
    return plan, out, manifest


def ephys(plan: Plan):
    return [e for e in plan.entries if e.modality == "ephys" and not e.exclude]


def read_tsv(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def _texts(out: Path):
    for p in sorted(out.rglob("*")):
        if p.is_file() and p.suffix.lower() in TEXT:
            yield p, p.read_text(encoding="utf-8", errors="replace")


def _assert_clean(out: Path, sources: list[Path] = ()) -> None:
    for p, text in _texts(out):
        assert not ephys_tokens(text), (p.relative_to(out), ephys_tokens(text))
    files = [p for p in out.rglob("*") if p.is_file()]
    v = gate.check(files, out, TERMS, FORBIDDEN, list(sources), allowed_dates=[])
    # scans.tsv acq_time holds the shifted date (allowed only there)
    assert v == [], v


def _one(manifest: dict, plan: Plan, suffix: str) -> tuple:
    for e in ephys(plan):
        for rel in manifest.get(e.id, []):
            if rel.endswith(suffix):
                return e, rel
    raise AssertionError(f"no {suffix} written: {manifest}")


def _edit_format(fmt: str):
    def edit(plan: Plan) -> None:
        for e in plan.entries:
            if e.modality == "ephys" and e.datatype == "eeg":
                e.ephys_format = fmt
    return edit


def edf(path: Path, labels, his_id="P1234567", when=fx.MEAS_DATE, n=2560, annotations=()):
    import edfio

    path.parent.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(0)
    signals = [edfio.EdfSignal(rng.standard_normal(n) * 20, sampling_frequency=fx.SFREQ, label=lab,
                               physical_dimension="uV", physical_range=(-500.0, 500.0)) for lab in labels]
    edfio.Edf(signals, patient=edfio.Patient(code=his_id, sex="F", birthdate=date(1980, 6, 30)),
              recording=edfio.Recording(startdate=when.date()), starttime=when.time().replace(tzinfo=None),
              annotations=[edfio.EdfAnnotation(onset=float(i + 1), duration=None, text=t)
                           for i, t in enumerate(annotations)]).write(path)
    return path


def meg_fif(path: Path, when: datetime | None, his_id: str | None = "M7654321", extra: int = 0):
    from mne._fiff._digitization import _make_dig_points

    path.parent.mkdir(parents=True, exist_ok=True)
    info = mne.create_info([f"MEG {i:03d}" for i in range(1, 5)], fx.SFREQ, "mag")
    rng = np.random.default_rng(0)
    raw = mne.io.RawArray(rng.standard_normal((4, 512)) * 1e-13, info, verbose=False)
    with raw.info._unlock():
        if his_id:
            raw.info["subject_info"] = {"his_id": his_id, "sex": 2, "birthday": date(1980, 6, 30)}
        raw.info["experimenter"] = "Jane Doe"
        raw.info["line_freq"] = 50.0
        raw.info["dig"] = _make_dig_points(
            nasion=[0.0, 0.1, 0.0], lpa=[-0.08, 0.0, 0.0], rpa=[0.08, 0.0, 0.0],
            hpi=[[0.0, 0.09, 0.02], [-0.07, 0.0, 0.02], [0.07, 0.0, 0.02]],
            extra_points=rng.standard_normal((extra, 3)) * 0.02 if extra else None, coord_frame="head")
    raw.set_meas_date(when)
    raw.save(path, overwrite=True, verbose=False)
    return path


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# --- units ---------------------------------------------------------------------------------------


def test_daysback():
    d = ephys_write.daysback([datetime(2025, 2, 15, 10, tzinfo=timezone.utc),
                              datetime(2024, 1, 1, tzinfo=timezone.utc)], -400)
    latest = datetime(2025, 2, 15, 10, tzinfo=timezone.utc)
    assert latest - timedelta(days=d - 400) < datetime(1925, 1, 1, tzinfo=timezone.utc)
    assert latest - timedelta(days=d - 401) >= datetime(1925, 1, 1, tzinfo=timezone.utc)
    assert ephys_write.daysback([], 30) == 30


def test_h5_strings_variable_length(tmp_path):
    """MATLAB v7.3 EEGLAB: a variable-length string dataset (which compares equal to h5py.ref_dtype) is
    read as text, not walked as references."""
    import h5py

    from aimport.ephys.discover import Recording

    path = tmp_path / "rest.set"
    with h5py.File(path, "w", userblock_size=512) as f:
        eeg = f.create_group("EEG")
        ds = eeg.create_dataset("comments", data=np.array(["Hospital X", "Dr Jane Doe"], dtype=object),
                                dtype=h5py.string_dtype())
        ds.attrs["MATLAB_class"] = np.bytes_("cell")
        data = eeg.create_dataset("data", data=np.zeros((3, 10), dtype=np.float32))
        data.attrs["MATLAB_class"] = np.bytes_("single")
    terms = headers.harvest(Recording(path.name, "eeglab"), tmp_path)
    assert {"Hospital X", "Dr Jane Doe"} <= terms


def test_gate_allowed_dates_and_vhdr_layout(tmp_path):
    out = tmp_path / "out"
    side = out / "sub-01" / "eeg" / "sub-01_task-rest_eeg.json"
    side.parent.mkdir(parents=True)
    side.write_text(json.dumps({"Note": "2019-03-04"}))
    assert gate.check([side], out, set(), set(), []) == ["sub-01/eeg/sub-01_task-rest_eeg.json: sidecar value"]
    assert gate.check([side], out, set(), set(), [], allowed_dates=[date(2019, 3, 4)]) == []
    vhdr = side.with_name("sub-01_task-rest_eeg.vhdr")
    vhdr.write_text("Brain Vision Data Exchange Header File Version 1.0\n[Common Infos]\nDataFile=x.eeg\n"
                    "MarkerFile=sub-01_task-rest_eeg.vmrk\n[Comment]\n")
    assert gate.check([vhdr], out, set(), set(), []) == [
        "sub-01/eeg/sub-01_task-rest_eeg.vhdr: data file name", "sub-01/eeg/sub-01_task-rest_eeg.vhdr: header section"]


def test_rewrite_edf_only_inside_root(tmp_path):
    src = fx.planted_edf(tmp_path / "in")
    before = src.read_bytes()
    with pytest.raises(headers.HeaderError):
        headers.rewrite_edf(src, root=tmp_path / "out")
    assert src.read_bytes() == before
    copy = tmp_path / "out" / "a.edf"
    copy.parent.mkdir()
    copy.write_bytes(before)
    with pytest.raises(headers.HeaderError, match="annotation"):
        headers.rewrite_edf(copy, root=tmp_path / "out", labels={"1"})
    h = headers.read_edf_header(copy)
    assert (h.patient, h.recording, h.startdate, h.starttime) == ("X X X X", "Startdate X X X X", "01.01.85",
                                                                  "00.00.00")
    assert len(copy.read_bytes()) == len(before)


# --- EEG -------------------------------------------------------------------------------------------


def test_edf_header_cleared(tmp_path, key, schema):
    fx.planted_edf(tmp_path / "in")
    plan, out, manifest = plan_and_write(tmp_path / "in", tmp_path, key, schema, edit=_edit_format("EDF"))
    e, rel = _one(manifest, plan, "_eeg.edf")
    assert e.ephys_format == "EDF"
    h = headers.read_edf_header(out / rel)
    assert (h.patient, h.recording, h.startdate, h.starttime) == ("X X X X", "Startdate X X X X", "01.01.85",
                                                                  "00.00.00")
    texts = headers.edf_annotation_texts(out / rel)
    assert texts and not ephys_tokens(" ".join(texts))
    assert set(texts) <= set(plan.event_names.values()) | {"1", "eyes closed"}
    _assert_clean(out, [tmp_path / "in" / fx.SUBJECT_DIR / "Smith_John_rest.edf"])


def test_brainvision_rebuilt(tmp_path, key, schema):
    fx.planted_brainvision(tmp_path / "in")
    plan, out, manifest = plan_and_write(tmp_path / "in", tmp_path, key, schema)
    e, rel = _one(manifest, plan, "_eeg.vhdr")
    stem = Path(rel).name[: -len(".vhdr")]
    vhdr = (out / rel).read_text()
    assert f"DataFile={stem}.eeg" in vhdr and f"MarkerFile={stem}.vmrk" in vhdr
    assert "[Comment]" not in vhdr and "Patient" not in vhdr
    sections = [line for line in vhdr.splitlines() if line.startswith("[")]
    assert set(sections) <= {"[Common Infos]", "[Binary Infos]", "[Channel Infos]", "[Coordinates]"}
    vmrk = (out / rel).with_suffix(".vmrk").read_text()
    labels = set(plan.event_names.values()) | {"Stimulus/S  1"}
    for line in vmrk.splitlines():
        if line.startswith("Mk"):
            mtype, desc = line.split("=", 1)[1].split(",")[:2]
            assert desc in labels or headers.is_safe(f"{mtype}/{desc}"), line
    _assert_clean(out, list((tmp_path / "in" / fx.SUBJECT_DIR).iterdir()))


def test_events_tsv_coded(tmp_path, key, schema):
    fx.planted_edf(tmp_path / "in")

    def rename(plan: Plan) -> None:
        plan.set_event_names({"E001": "greeting"})

    plan, out, manifest = plan_and_write(tmp_path / "in", tmp_path, key, schema, edit=rename)
    assert plan.event_names == {"E001": "greeting"}
    e, rel = _one(manifest, plan, "_events.tsv")
    rows = read_tsv(out / rel)
    kinds = {r["trial_type"] for r in rows}
    assert kinds == {"greeting", "1", "eyes closed"}  # "Smith John said hello" is E001, renamed
    assert not ephys_tokens((out / rel).read_text())


def test_channels_renamed_everywhere(tmp_path, key, schema):
    fx.planted_brainvision(tmp_path / "in")
    plan, out, manifest = plan_and_write(tmp_path / "in", tmp_path, key, schema)
    e, rel = _one(manifest, plan, "_eeg.vhdr")
    names = [r["name"] for r in read_tsv(out / rel.replace("_eeg.vhdr", "_channels.tsv"))]
    assert "Smith-Fp1" not in names and "eeg_002" in names and "Fp1" in names
    for p, text in _texts(out):
        assert "smith-fp1" not in text.lower(), p


def test_sidecar_allowlist(tmp_path, key, schema):
    fx.planted_brainvision(tmp_path / "in")
    plan, out, manifest = plan_and_write(tmp_path / "in", tmp_path, key, schema)
    e, rel = _one(manifest, plan, "_eeg.json")
    car = json.loads((out / rel).read_text())
    assert set(car) <= set(schema.sidecar_fields("eeg", "eeg"))
    assert "InstitutionName" not in car and "DeviceSerialNumber" not in car
    assert car["TaskName"] == "rest"


def test_scans_shifted_and_no_original_date(tmp_path, key, schema):
    fx.planted_edf(tmp_path / "in")
    plan, out, manifest = plan_and_write(tmp_path / "in", tmp_path, key, schema)
    e, rel = _one(manifest, plan, "_eeg.vhdr")
    offset = key.date_offset_days(e.subject)
    rows = read_tsv(out / f"sub-{e.subject}" / f"sub-{e.subject}_scans.tsv")
    want = (datetime(2025, 2, 15, 10, 0, 0) + timedelta(days=offset)).strftime("%Y-%m-%dT%H:%M:%S")
    assert rows == [{"filename": rel.split("/", 1)[1], "acq_time": want}]
    assert not (out / f"sub-{e.subject}" / f"sub-{e.subject}_scans.json").exists()  # time recorded
    shifted = (fx.MEAS_DATE + timedelta(days=offset)).date()
    files = [p for p in out.rglob("*") if p.is_file()]
    assert gate.check(files, out, TERMS, FORBIDDEN, [], allowed_dates=[shifted]) == []
    for p in files:
        assert b"2025" not in p.read_bytes() or p.suffix == ".eeg", p
    participants = read_tsv(out / "participants.tsv")
    assert participants == [{"participant_id": f"sub-{e.subject}", "age": "55", "sex": "M"}]


def test_source_unchanged(tmp_path, key, schema):
    fx.planted_edf(tmp_path / "in")
    fx.planted_brainvision(tmp_path / "in2")
    for d in ("in2",):
        for p in (tmp_path / d).rglob("*"):
            target = tmp_path / "in" / "bv" / p.relative_to(tmp_path / d)
            if p.is_file():
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(p.read_bytes())
    srcs = sorted(p for p in (tmp_path / "in").rglob("*") if p.is_file())
    before = {p: (p.stat().st_mtime_ns, _sha(p)) for p in srcs}
    plan, out, manifest = plan_and_write(tmp_path / "in", tmp_path, key, schema, edit=_edit_format("EDF"))
    assert {p: (p.stat().st_mtime_ns, _sha(p)) for p in srcs} == before
    assert len(ephys(plan)) == 2 and all(manifest[e.id] for e in ephys(plan))
    assert not (tmp_path / "work" / "ephys" / "scratch").exists()


# --- EMG -------------------------------------------------------------------------------------------


def test_emg_edf(tmp_path, key, schema):
    edf(tmp_path / "in" / "arm_rest.edf", ["EMG L1", "EMG L2", "EMG R1"], annotations=("start",))
    plan, out, manifest = plan_and_write(tmp_path / "in", tmp_path, key, schema)
    e, rel = _one(manifest, plan, "_emg.edf")
    assert e.datatype == "emg" and e.ephys_format == "EDF"
    car = json.loads((out / rel.replace("_emg.edf", "_emg.json")).read_text())
    assert car["EMGPlacementScheme"] == "Other" and "TODO" not in json.dumps(car)
    types = {r["type"] for r in read_tsv(out / rel.replace("_emg.edf", "_channels.tsv"))}
    assert types == {"EMG"}
    with pytest.raises(ValueError):
        apply_plan_edits(plan, [{"id": e.id, "ephys_format": "BrainVision"}], schema)
    e.ephys_format = "BrainVision"
    with pytest.raises(ValueError, match="cannot be written"):
        ephys_write.write_recording(e, {}, None, tmp_path / "s", lambda r: tmp_path / r, schema, set(),
                                    days_back=0, labels=set())


# --- MEG -------------------------------------------------------------------------------------------


def test_emptyroom_written_and_referenced(tmp_path, key, schema):
    day = fx.MEAS_DATE
    meg_fif(tmp_path / "in" / "meg" / "subj_rest_raw.fif", day.replace(hour=10))
    meg_fif(tmp_path / "in" / "meg" / "emptyroom_raw.fif", day.replace(hour=9), his_id=None)
    plan, out, manifest = plan_and_write(tmp_path / "in", tmp_path, key, schema)
    room = next(e for e in ephys(plan) if e.subject == "emptyroom")
    meg = next(e for e in ephys(plan) if e.subject != "emptyroom")
    assert meg.empty_room == room.id
    room_rel = manifest[room.id][0]
    assert room_rel == "sub-emptyroom/meg/sub-emptyroom_task-noise_meg.fif" and (out / room_rel).is_file()
    car = json.loads((out / manifest[meg.id][0].replace("_meg.fif", "_meg.json")).read_text())
    assert car["AssociatedEmptyRoom"] == room_rel
    assert not list(out.rglob("ses-*"))
    rows = {r["participant_id"]: r for r in read_tsv(out / "participants.tsv")}
    assert rows["sub-emptyroom"] == {"participant_id": "sub-emptyroom", "age": "n/a", "sex": "n/a"}
    assert rows[f"sub-{meg.subject}"]["sex"] == "F" and rows[f"sub-{meg.subject}"]["age"] == "44"
    er_scans = read_tsv(out / "sub-emptyroom" / "sub-emptyroom_scans.tsv")
    assert er_scans == [{"filename": "meg/sub-emptyroom_task-noise_meg.fif", "acq_time": "n/a"}]
    assert "emptyroom" not in key.offsets
    info = mne.io.read_info(out / room_rel, verbose=False)
    assert info["meas_date"].year < 1925
    _assert_clean(out, list((tmp_path / "in").rglob("*.fif")))


def test_meg_headshape_dropped_and_kept(tmp_path, key, schema):
    from mne._fiff.constants import FIFF

    meg_fif(tmp_path / "in" / "meg" / "subj_rest_raw.fif", fx.MEAS_DATE, extra=200)

    def counts(path: Path) -> dict:
        info = mne.io.read_info(path, verbose=False)
        kinds = [d["kind"] for d in info["dig"]]
        return {"extra": kinds.count(FIFF.FIFFV_POINT_EXTRA), "cardinal": kinds.count(FIFF.FIFFV_POINT_CARDINAL),
                "hpi": kinds.count(FIFF.FIFFV_POINT_HPI)}

    plan, out, manifest = plan_and_write(tmp_path / "in", tmp_path, key, schema)
    e, rel = _one(manifest, plan, "_meg.fif")
    assert counts(out / rel) == {"extra": 0, "cardinal": 3, "hpi": 3}
    assert json.loads((out / rel.replace("_meg.fif", "_meg.json")).read_text())["DigitizedHeadPoints"] is False
    assert not list(out.rglob("*_headshape*"))

    keep = tmp_path / "keep"
    plan, out, manifest = plan_and_write(tmp_path / "in", keep, key, schema, edit=lambda p: [
        setattr(x, "keep_headshape", True) for x in p.entries if x.modality == "ephys"])
    e, rel = _one(manifest, plan, "_meg.fif")
    assert counts(out / rel) == {"extra": 200, "cardinal": 3, "hpi": 3}
    assert json.loads((out / rel.replace("_meg.fif", "_meg.json")).read_text())["DigitizedHeadPoints"] is True


def test_headshape_points_without_keep_fail_the_gate(tmp_path, key, schema, monkeypatch):
    from aimport.ephys import deid

    meg_fif(tmp_path / "in" / "meg" / "subj_rest_raw.fif", fx.MEAS_DATE, extra=20)
    real = deid.clean
    monkeypatch.setattr(deid, "clean", lambda raw, **kw: real(raw, **{**kw, "keep_headshape": True}))
    with pytest.raises(gate.GateError, match="head-shape points"):
        plan_and_write(tmp_path / "in", tmp_path, key, schema)
    assert not (tmp_path / "work" / "ephys" / "scratch").exists()


@pytest.mark.ephys_data
def test_fif_subject_info_minimal(tmp_path, key, schema):
    from mne._fiff.constants import FIFF

    fx.planted_fif(tmp_path / "in")
    plan, out, manifest = plan_and_write(tmp_path / "in", tmp_path, key, schema)
    e, rel = _one(manifest, plan, "_meg.fif")
    info = mne.io.read_info(out / rel, verbose=False)
    assert set(info["subject_info"] or {}) <= {"sex", "hand"}
    for k in ("experimenter", "description", "proj_name"):
        assert not ephys_tokens(str(info[k] or "")), k
    kinds = [d["kind"] for d in info["dig"]]
    assert kinds.count(FIFF.FIFFV_POINT_EXTRA) == 0
    assert kinds.count(FIFF.FIFFV_POINT_CARDINAL) == 3 and kinds.count(FIFF.FIFFV_POINT_HPI) == 4
    _assert_clean(out, [tmp_path / "in" / fx.SUBJECT_DIR / "Smith_John_rest_raw.fif"])


@pytest.mark.ephys_data
def test_meg_headshape_dropped(tmp_path, key, schema):
    """The planted FIF: no EXTRA points by default, all 200 with keep_headshape; fiducials and HPI in both."""
    from mne._fiff.constants import FIFF

    fx.planted_fif(tmp_path / "in")
    for keep in (False, True):
        root = tmp_path / str(keep)
        plan, out, manifest = plan_and_write(tmp_path / "in", root, key, schema, edit=lambda p, keep=keep: [
            setattr(x, "keep_headshape", keep) for x in p.entries if x.modality == "ephys"])
        e, rel = _one(manifest, plan, "_meg.fif")
        kinds = [d["kind"] for d in mne.io.read_info(out / rel, verbose=False)["dig"]]
        assert kinds.count(FIFF.FIFFV_POINT_EXTRA) == (fx.FIF_DIG_COUNTS["extra"] if keep else 0)
        assert kinds.count(FIFF.FIFFV_POINT_CARDINAL) == 3 and kinds.count(FIFF.FIFFV_POINT_HPI) == 4
        assert json.loads((out / rel.replace("_meg.fif", "_meg.json")).read_text())["DigitizedHeadPoints"] is keep


@pytest.mark.ephys_data
@pytest.mark.parametrize("family", ["ctf", "kit", "bti"])
def test_ctf_kit_bti_to_fif(tmp_path, key, schema, family):
    import shutil

    got = fx.fetch_mne_testing(fx.MNE_TESTING_FAMILIES[family])
    inp = tmp_path / "in"
    for name, path in got.items():
        target = inp / name.rstrip("/")
        if path.is_dir():
            shutil.copytree(path, target)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
    plan, out, manifest = plan_and_write(inp, tmp_path, key, schema)
    written = [e for e in ephys(plan) if e.datatype == "meg"]
    assert written and all(e.ephys_format == "FIF" for e in written)
    for e in written:
        assert manifest[e.id][0].endswith("_meg.fif")
    files = [p for p in out.rglob("*") if p.is_file()]
    sources = [p for p in inp.rglob("*") if p.is_file()]
    v = gate.check([p for p in files if not p.name.endswith("_scans.tsv")], out, set(), set(), sources)
    assert v == [], v


# --- server --------------------------------------------------------------------------------------


def _wait(c, stages, timeout=120):
    end = time.time() + timeout
    while (s := c.get("/status").json())["stage"] not in stages and time.time() < end:
        time.sleep(0.05)
    return s


def test_gate_failure_sets_aside(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from aimport.server import create_app
    from aimport.validate import ValidationResult

    fx.planted_brainvision(tmp_path / "in")
    monkeypatch.setattr(headers, "rebuild_vhdr", lambda path, stem: None)
    monkeypatch.setattr(server, "client_from_env", lambda: None)
    monkeypatch.setattr(server, "run_ezbids", lambda *a, **k: pytest.fail("nothing is left for ezBIDS"))
    monkeypatch.setattr(server, "validate_bids", lambda bids: ValidationResult(
        ok=True, validator_version="2.4.1", bids_version="1.11.2"))
    app = create_app(tmp_path / "in", tmp_path / "work", tmp_path / "keys", "t" * 32, ["https://brainlife.io"],
                     ["testserver"])
    try:
        c = TestClient(app)
        c.headers["Authorization"] = "Bearer " + "t" * 32
        assert c.post("/scan", json={"project_id": "proj"}).status_code == 202
        assert _wait(c, ("planned", "failed"))["stage"] == "planned"
        edits = [{"id": e["id"], "entities": {**e["entities"], "task": "rest"}} for e in c.get("/plan").json()["entries"]
                 if e.get("modality") == "ephys" and e["entities"].get("task") == "unknown"]
        if edits:
            assert c.patch("/plan", json={"edits": edits}).status_code == 200
        assert c.post("/approve", json={}).status_code == 200
        assert c.post("/execute").status_code == 202
        s = _wait(c, ("validated", "invalid", "failed"))
    finally:
        app.state.server.close()
    assert s["stage"] == "failed", s
    assert s["message"].startswith("GateError: the output failed the final check")
    assert ".vhdr: header section" in s["message"]
    assert not ephys_tokens(json.dumps(s))
    # nothing uploadable is left: write_bids removes what it created before the server's set-aside runs
    assert not (tmp_path / "work" / "output" / "bids").exists()
    failed = tmp_path / "work" / "output" / "bids.failed"
    assert not failed.exists() or not [p for p in failed.rglob("*") if p.is_file()]
    assert not (tmp_path / "work" / "ephys" / "scratch").exists()


# --- docker: the validator accepts the output -------------------------------------------------------


@pytest.mark.docker
def test_ephys_output_validates(tmp_path, key, schema):
    from aimport.validate import validate_bids

    inp = tmp_path / "in"
    fx.planted_brainvision(inp / "a")
    edf(inp / "b" / "grid_rest.edf", ["SEEG LA1", "SEEG LA2", "SEEG LA3"], his_id="P2222222", annotations=("start",))
    edf(inp / "c" / "arm_rest.edf", ["EMG L1", "EMG L2"], his_id="P3333333")
    meg_fif(inp / "d" / "meg" / "subj_rest_raw.fif", fx.MEAS_DATE.replace(hour=10))
    meg_fif(inp / "d" / "meg" / "emptyroom_raw.fif", fx.MEAS_DATE.replace(hour=9), his_id=None)
    plan, out, manifest = plan_and_write(inp, tmp_path, key, schema)
    assert {e.datatype for e in ephys(plan)} == {"eeg", "ieeg", "emg", "meg"}
    result = validate_bids(out)
    assert result.ok, json.dumps(result.errors, indent=1)[:4000]
