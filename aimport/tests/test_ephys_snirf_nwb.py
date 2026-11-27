"""Phase 3 Task 10: SNIRF and NWB written from scratch (never copied), and the Task 9 review carries
(per-empty-room daysback, no silent skip, shared session files once, split empty-room FIF)."""
from __future__ import annotations

import json
import shutil
import tracemalloc
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pytest

mne = pytest.importorskip("mne")
pytest.importorskip("mne_bids")
h5py = pytest.importorskip("h5py")
pynwb = pytest.importorskip("pynwb")

from aimport import modality  # noqa: E402
from aimport.ephys import events, gate, headers, nwb, snirf  # noqa: E402
from aimport.ephys import write as ephys_write  # noqa: E402
from aimport.ezbids_runner import CoreResult  # noqa: E402
from aimport.pseudonyms import PseudonymKey  # noqa: E402
from aimport.writer import write_bids  # noqa: E402
from conftest import EPHYS_PLANTED, ephys_tokens  # noqa: E402
from fixtures import ephys_fixtures as fx  # noqa: E402
from test_ephys_write import (  # noqa: E402
    TERMS,
    _assert_clean,
    _one,
    _plan,
    ephys,
    meg_fif,
    plan_and_write,
    read_tsv,
)

CODE = events.CODE_PREFIX


@pytest.fixture
def key(tmp_path):
    k = PseudonymKey.load(tmp_path / "keys", "proj")
    yield k
    k.close()


def _h5_strings(path: Path) -> list[str]:
    """Every string in an HDF5 file: object names, attributes and string datasets."""
    out: list[str] = []

    def strings(value) -> list[str]:
        arr = np.asarray(value)
        if arr.dtype.kind not in "SUO":
            return []
        return [v.decode("utf-8", "replace") if isinstance(v, bytes) else str(v) for v in arr.reshape(-1).tolist()
                if isinstance(v, (bytes, str))]

    def visit(name, obj) -> None:
        out.append(name)
        for k, v in obj.attrs.items():
            out.append(k)
            if not isinstance(v, h5py.Reference):
                out.extend(strings(v))
        if isinstance(obj, h5py.Dataset) and obj.dtype.kind in "SUO" and h5py.check_ref_dtype(obj.dtype) is None:
            out.extend(strings(obj[()]))

    with h5py.File(path, "r") as f:
        for k, v in f.attrs.items():
            out += [k, *strings(v)]
        f.visititems(visit)
    return out


def _write_all(inp: Path, tmp_path: Path, key, schema, edit=None):
    """plan_and_write, also returning every file the writer reports."""
    plan, m, work = _plan(inp, tmp_path, key, schema, edit)
    staged = tmp_path / "staged"
    staged.mkdir(exist_ok=True)
    out = tmp_path / "out"
    manifest: dict = {}
    written = write_bids(plan, CoreResult(), inp, m.terms(work / "ephys"), key, schema, out, staged_dir=staged,
                         exclude=m.claim(inp, []).roots, manifest=manifest, modules=modality.modules(),
                         work_dir=work)
    return plan, out, manifest, written


# --- SNIRF -----------------------------------------------------------------------------------------------


def test_snirf_planted_cleared(tmp_path, key, schema):
    src = fx.planted_snirf(tmp_path / "in")
    plan, out, manifest = plan_and_write(tmp_path / "in", tmp_path, key, schema)
    e, rel = _one(manifest, plan, "_nirs.snirf")
    assert e.datatype == "nirs" and e.ephys_format == "SNIRF" and manifest[e.id][0] == rel
    with h5py.File(out / rel, "r") as f:
        tags = f["nirs/metaDataTags"]
        assert sorted(tags) == sorted(headers.SNIRF_TAGS) and "Operator" not in tags
        assert tags["SubjectID"][()].decode() == e.subject
        assert tags["MeasurementDate"][()].decode() == "unknown" == tags["MeasurementTime"][()].decode()
        assert tags["LengthUnit"][()].decode() == "mm"  # from the source
        name = f["nirs/stim1/name"][()].decode()
    assert name.startswith(CODE) and name in plan.event_names
    assert not ephys_tokens(" ".join(_h5_strings(out / rel)))
    events_rel = rel.replace("_nirs.snirf", "_events.tsv")
    assert {r["trial_type"] for r in read_tsv(out / events_rel)} == {name}
    assert (out / rel).read_bytes() != src.read_bytes()
    _assert_clean(out, [src])


def test_snirf_roundtrip(tmp_path, key, schema):
    src = fx.planted_snirf(tmp_path / "in")
    plan, out, manifest = plan_and_write(tmp_path / "in", tmp_path, key, schema)
    _, rel = _one(manifest, plan, "_nirs.snirf")
    a = mne.io.read_raw_snirf(src, preload=False, verbose="error")
    b = mne.io.read_raw_snirf(out / rel, preload=False, verbose="error")
    assert b.ch_names == a.ch_names and b.info["sfreq"] == a.info["sfreq"]
    waves = [sorted({float(ch["loc"][9]) for ch in r.info["chs"]}) for r in (a, b)]
    assert waves[0] == waves[1] == [760.0, 850.0]
    np.testing.assert_allclose(b.get_data(), a.get_data(), rtol=1e-6)
    for ca, cb in zip(a.info["chs"], b.info["chs"]):
        np.testing.assert_allclose(cb["loc"][3:9], ca["loc"][3:9], rtol=1e-9)
    assert list(b.annotations.onset) == list(a.annotations.onset)
    optodes = next(out.rglob("*_optodes.tsv"))
    assert {r["name"] for r in read_tsv(optodes)} == {"S1", "S2", "D1", "D2"}


def test_snirf_rewrite_drops_unknown(tmp_path):
    """rewrite reads through MNE and writes anew: custom tags, unknown groups and stim text never survive."""
    src = fx.planted_snirf(tmp_path / "in")
    with h5py.File(src, "a") as f:
        f["nirs/metaDataTags"].create_dataset("lastName", data=np.array([b"Smith"]))
        f["nirs"].create_group("aux1").create_dataset("name", data=np.bytes_("Hospital X pulse"))
        f.create_dataset("notes", data=np.bytes_("Dr Jane Doe"))
    before = src.read_bytes()
    labels, _ = events.code([["Jane Doe tapping"]], TERMS)
    dest = tmp_path / "out.snirf"
    snirf.rewrite(src, dest, "01", labels)
    assert src.read_bytes() == before
    with h5py.File(dest, "r") as f:
        assert set(f) == {"formatVersion", "nirs"}
        assert set(f["nirs"]) == {"metaDataTags", "data1", "probe", "stim1"}
        assert f["formatVersion"][()].decode() == "1.1"
    assert not ephys_tokens(" ".join(_h5_strings(dest)))
    headers.check_snirf(dest, "01", {"E001"})
    with pytest.raises(headers.HeaderError, match="stim name"):
        headers.check_snirf(dest, "01", set())
    with pytest.raises(headers.HeaderError, match="SNIRF root"):
        headers.check_snirf(src, "01", {"E001"})
    with pytest.raises(headers.HeaderError, match="metaDataTags"):
        headers.check_snirf(fx.planted_snirf(tmp_path / "plain"), "01", {"E001"})


def test_snirf_written_in_chunks(tmp_path, monkeypatch):
    src = fx.planted_snirf(tmp_path / "in")
    raw = mne.io.read_raw_snirf(src, preload=False, verbose="error")
    spans: list[int] = []
    real = raw.get_data

    def spy(*a, start=0, stop=None, **kw):
        spans.append((stop if stop is not None else raw.n_times) - start)
        return real(*a, start=start, stop=stop, **kw)

    monkeypatch.setattr(raw, "get_data", spy)
    monkeypatch.setattr(snirf, "CHUNK_BYTES", 8 * len(raw.ch_names) * 100)
    snirf.write(raw, tmp_path / "out.snirf", "01", {"Jane Doe tapping": "E001"})
    assert len(spans) == -(-raw.n_times // 100) and max(spans) <= 100
    back = mne.io.read_raw_snirf(tmp_path / "out.snirf", preload=False, verbose="error")
    np.testing.assert_allclose(back.get_data(), real(), rtol=1e-12)


def _copy_tree(got: dict, inp: Path) -> None:
    for name, path in got.items():
        target = inp / name.rstrip("/")
        if path.is_dir():
            shutil.copytree(path, target)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)


@pytest.mark.ephys_data
def test_nirx_hitachi_to_snirf(tmp_path, key, schema):
    """NIRx (NIRScout folder) and a NIRSport2 SNIRF become new SNIRF files with optodes. Hitachi: no test
    file exists at the pinned mne-testing-data commit (DATASETS.md); it takes the same path (read_raw_hitachi)."""
    inp = tmp_path / "in"
    _copy_tree(fx.fetch_mne_testing(fx.MNE_TESTING_FAMILIES["nirx"] + fx.MNE_TESTING_FAMILIES["snirf"]), inp)
    plan, out, manifest = plan_and_write(inp, tmp_path, key, schema)
    nirs = [e for e in ephys(plan) if e.datatype == "nirs"]
    assert len(nirs) == 2 and all(e.ephys_format == "SNIRF" and manifest[e.id] for e in nirs)
    sources = [p for p in inp.rglob("*") if p.is_file()]
    for e in nirs:
        data = out / manifest[e.id][0]
        assert data.name.endswith("_nirs.snirf")
        headers.check_snirf(data, e.subject, set(plan.event_names.values()) | set(_labels(tmp_path)))
        raw = mne.io.read_raw_snirf(data, preload=False, verbose="error")
        assert raw.n_times > 0 and len(raw.ch_names) > 0
    assert list(out.rglob("*_optodes.tsv")) and list(out.rglob("*_coordsystem.json"))
    files = [p for p in out.rglob("*") if p.is_file() and not p.name.endswith("_scans.tsv")]
    assert gate.check(files, out, set(), set(), sources) == []


def _labels(tmp_path: Path) -> set[str]:
    ev = json.loads((tmp_path / "work" / "ephys" / "events.json").read_text())
    return set(ev["labels"].values())


# --- NWB -------------------------------------------------------------------------------------------------


def test_nwb_planted_cleared(tmp_path, key, schema):
    src = fx.planted_nwb(tmp_path / "in")
    plan, out, manifest = plan_and_write(tmp_path / "in", tmp_path, key, schema)
    e, rel = _one(manifest, plan, "_ieeg.nwb")
    assert e.datatype == "ieeg" and e.ephys_format == "NWB" and manifest[e.id][0] == rel
    assert e.description.startswith("NWB → NWB")
    strings = " ".join(_h5_strings(out / rel)).lower()
    assert not {t for t in EPHYS_PLANTED if t in strings}
    with pynwb.NWBHDF5IO(str(out / rel), "r") as io:
        got = io.read()
        assert got.session_start_time.year == 1900 and got.session_description == "n/a"
        assert got.subject.subject_id == e.subject and got.subject.sex == "M"
        assert got.subject.date_of_birth is None and not got.experimenter and not got.institution
        labels = list(got.trials["label"][:])
        assert labels and all(lab.startswith(CODE) for lab in labels)
        assert set(got.trials.colnames) == {"start_time", "stop_time", "label"}
        with h5py.File(src, "r") as f:
            np.testing.assert_array_equal(got.acquisition["ElectricalSeries"].data[:], f["acquisition/ieeg/data"][()])
    with h5py.File(out / rel, "r") as f:
        for g in ("processing", "analysis", "stimulus/presentation", "stimulus/templates"):
            assert len(f[g]) == 0, g
        assert set(f.get("specifications", {})) <= {"core", "hdmf-common"}
        assert f["identifier"][()] != b"aimport-planted-nwb"
    stem = rel[: -len("_ieeg.nwb")]
    for suffix in ("_ieeg.json", "_channels.tsv", "_events.tsv"):
        assert (out / (stem + suffix)).is_file(), suffix
    car = json.loads((out / (stem + "_ieeg.json")).read_text())
    assert car["TaskName"] == "rest" and car["ECOGChannelCount"] == 8 and car["SamplingFrequency"] == fx.SFREQ
    assert {r["trial_type"] for r in read_tsv(out / (stem + "_events.tsv"))} == set(labels)
    assert {r["type"] for r in read_tsv(out / (stem + "_channels.tsv"))} == {"ECOG"}
    electrodes = next(out.rglob("*_electrodes.tsv"))
    assert [r["x"] for r in read_tsv(electrodes)][:2] == ["0", "0.001"]
    assert json.loads(next(out.rglob("*_coordsystem.json")).read_text())["iEEGCoordinateUnits"] == "mm"
    _assert_clean(out, [src])


def test_nwb_harvest_and_meta(tmp_path):
    src = fx.planted_nwb(tmp_path / "in")
    terms = nwb.harvest(src)
    assert {"Smith John grid", "Jane Doe", "Hospital X", "MRN0042", "seizure Dr Jane", "1970-01-01",
            "2025-02-15"} <= terms
    info = nwb.read_meta(src)
    assert (info.n_channels, info.n_times, info.sfreq, info.sex) == (8, fx.N_SAMPLES, fx.SFREQ, 1)
    assert info.ch_types == {"ecog": 8} and info.annotations == [(2.0, 1.0, "seizure Dr Jane")]
    assert "annotations" not in info.view() and "meas_date" not in info.view()


def test_nwb_as_brainvision(tmp_path, key, schema):
    """NWB input edited to BrainVision goes through MNE-BIDS (nwb.to_raw, deid.clean)."""
    src = fx.planted_nwb(tmp_path / "in")

    def edit(plan) -> None:
        for e in plan.entries:
            if e.modality == "ephys" and e.datatype == "ieeg":
                e.ephys_format = "BrainVision"

    plan, out, manifest = plan_and_write(tmp_path / "in", tmp_path, key, schema, edit=edit)
    e, rel = _one(manifest, plan, "_ieeg.vhdr")
    raw = mne.io.read_raw_brainvision(out / rel, preload=False, verbose="error")
    with h5py.File(src, "r") as f:
        np.testing.assert_allclose(raw.get_data(), f["acquisition/ieeg/data"][()].T, rtol=1e-3, atol=1e-7)
    rows = read_tsv(out / rel.replace("_ieeg.vhdr", "_events.tsv"))
    assert {r["trial_type"] for r in rows} == set(plan.event_names.values()) == {"E001"}
    assert [r["name"] for r in read_tsv(out / rel.replace("_ieeg.vhdr", "_channels.tsv"))][:2] == ["ch001", "ch002"]
    _assert_clean(out, [src])


def _big_nwb(path: Path, n_ch: int, n_times: int) -> None:
    """An NWB file with an n_times x n_ch float32 ElectricalSeries, filled chunk by chunk with h5py."""
    from hdmf.backends.hdf5.h5_utils import H5DataIO
    from pynwb import NWBHDF5IO, NWBFile
    from pynwb.ecephys import ElectricalSeries

    f = NWBFile(session_description="big", identifier="big", session_start_time=fx.MEAS_DATE)
    dev = f.create_device(name="amp")
    group = f.create_electrode_group(name="shaft", description="depth", location="hippocampus", device=dev)
    for _ in range(n_ch):
        f.add_electrode(group=group, location="hippocampus")
    f.add_acquisition(ElectricalSeries(
        name="ieeg", data=H5DataIO(np.zeros((1, n_ch), dtype="float32"), maxshape=(None, n_ch),
                                   chunks=(4096, n_ch)),
        electrodes=f.create_electrode_table_region(list(range(n_ch)), "all"), rate=1000.0))
    with NWBHDF5IO(str(path), "w") as io:
        io.write(f)
    with h5py.File(path, "a") as h:
        ds = h["acquisition/ieeg/data"]
        ds.resize((n_times, n_ch))
        step = 2**18
        for start in range(0, n_times, step):
            stop = min(n_times, start + step)
            ds[start:stop] = np.arange(start, stop, dtype="float32")[:, None] + np.arange(n_ch, dtype="float32")


def test_nwb_bounded(tmp_path):
    n_ch, n_times = 64, 2**20  # 256 MiB of float32
    src = tmp_path / "big.nwb"
    _big_nwb(src, n_ch, n_times)
    dest = tmp_path / "out.nwb"
    tracemalloc.start()
    try:
        nwb.write(src, dest, "01", {}, {})
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert peak < 96 * 2**20, peak / 2**20
    with h5py.File(src, "r") as a, h5py.File(dest, "r") as b:
        x, y = a["acquisition/ieeg/data"], b["acquisition/ElectricalSeries/data"]
        assert x.shape == y.shape == (n_times, n_ch)
        for start in range(0, n_times, 2**18):
            np.testing.assert_array_equal(x[start:start + 2**18], y[start:start + 2**18])


# --- Task 9 review carries ---------------------------------------------------------------------------------


def test_each_emptyroom_has_its_own_daysback(tmp_path, key, schema):
    """m1: two empty rooms 100 days apart both land on 1924-12-31: no real gap survives between them."""
    day1 = fx.MEAS_DATE.replace(hour=9)
    day2 = day1 + timedelta(days=100)
    meg_fif(tmp_path / "in" / "a" / "meg" / "subj_rest_raw.fif", day1.replace(hour=10), his_id="M1111111")
    meg_fif(tmp_path / "in" / "a" / "meg" / "emptyroom_raw.fif", day1, his_id=None)
    meg_fif(tmp_path / "in" / "b" / "meg" / "subj_rest_raw.fif", day2.replace(hour=10), his_id="M2222222")
    meg_fif(tmp_path / "in" / "b" / "meg" / "emptyroom_raw.fif", day2.replace(hour=8), his_id=None)
    plan, out, manifest = plan_and_write(tmp_path / "in", tmp_path, key, schema)
    rooms = [e for e in ephys(plan) if e.subject == "emptyroom"]
    assert len(rooms) == 2
    when = sorted(mne.io.read_info(out / manifest[e.id][0], verbose=False)["meas_date"] for e in rooms)
    assert [w.date() for w in when] == [datetime(1924, 12, 31).date()] * 2
    assert {(w.hour, w.minute) for w in when} == {(8, 0), (9, 0)}  # time of day only
    for e in ephys(plan):
        if e.subject != "emptyroom":
            car = json.loads((out / manifest[e.id][0].replace("_meg.fif", "_meg.json")).read_text())
            room = next(r for r in rooms if r.id == e.empty_room)
            assert car["AssociatedEmptyRoom"] == manifest[room.id][0]
    _assert_clean(out, list((tmp_path / "in").rglob("*.fif")))


def test_included_entry_without_format_raises(tmp_path, key, schema):
    """m3: an included ephys entry with no output format is an error, never a silent skip."""
    fx.planted_brainvision(tmp_path / "in")

    def edit(plan) -> None:
        for e in plan.entries:
            if e.modality == "ephys":
                e.ephys_format = ""

    with pytest.raises(ValueError, match="no output format"):
        plan_and_write(tmp_path / "in", tmp_path, key, schema, edit=edit)
    assert not (tmp_path / "work" / "ephys" / "scratch").exists()


def test_session_files_listed_once(tmp_path, key, schema):
    """m4: two NIRS runs of one session share optodes.tsv and coordsystem.json: each is in the manifest once
    and in the writer's list of written files once."""
    src = fx.planted_snirf(tmp_path / "in")
    shutil.copyfile(src, src.with_name("Smith_John_rest2.snirf"))
    plan, out, manifest, written = _write_all(tmp_path / "in", tmp_path, key, schema)
    nirs = [e for e in ephys(plan) if e.datatype == "nirs"]
    assert len(nirs) == 2 and len({e.subject for e in nirs}) == 1
    listed = [r for e in nirs for r in manifest[e.id]]
    assert len(listed) == len(set(listed))
    shared = [r for r in listed if r.endswith(("_optodes.tsv", "_coordsystem.json"))]
    assert len(shared) == 2
    rels = [p.relative_to(out).as_posix() for p in written]
    assert len(rels) == len(set(rels))
    for r in shared:
        assert rels.count(r) == 1


def test_split_emptyroom_readable(tmp_path, key, schema, monkeypatch):
    """m2: an empty room split by MNE (small split_size here) is saved again under the output names, so the
    first part finds the next ones."""
    import mne_bids.write as mbw

    monkeypatch.setattr(mbw, "_FIFF_SPLIT_SIZE", "3MB")
    day = fx.MEAS_DATE
    meg_fif(tmp_path / "in" / "meg" / "subj_rest_raw.fif", day.replace(hour=10))
    room = tmp_path / "in" / "meg" / "emptyroom_raw.fif"
    info = mne.create_info([f"MEG {i:03d}" for i in range(1, 21)], 1000.0, "mag")
    raw = mne.io.RawArray(np.random.default_rng(0).standard_normal((20, 60000)) * 1e-13, info, verbose=False)
    raw.set_meas_date(day.replace(hour=9))
    raw.save(room, verbose=False)
    plan, out, manifest = plan_and_write(tmp_path / "in", tmp_path, key, schema)
    er = next(e for e in ephys(plan) if e.subject == "emptyroom")
    parts = [r for r in manifest[er.id] if r.endswith("_meg.fif")]
    assert len(parts) > 1 and parts[0] == "sub-emptyroom/meg/sub-emptyroom_task-noise_split-01_meg.fif"
    assert all("ses-" not in r for r in manifest[er.id])
    back = mne.io.read_raw_fif(out / parts[0], preload=False, verbose="error")
    assert back.n_times == 60000 and back.info["meas_date"].year < 1925
    np.testing.assert_allclose(back.get_data(), raw.get_data(), rtol=1e-5)
    meg = next(e for e in ephys(plan) if e.subject != "emptyroom")
    car = json.loads((out / manifest[meg.id][0].replace("_meg.fif", "_meg.json")).read_text())
    assert car["AssociatedEmptyRoom"] == parts[0]
    assert not list(out.rglob("ses-*"))
    _assert_clean(out, list((tmp_path / "in").rglob("*.fif")))


# --- docker: the validator accepts NIRS and NWB output ------------------------------------------------------


@pytest.mark.docker
def test_nirs_and_nwb_validate(tmp_path, key, schema):
    from aimport.validate import validate_bids

    inp = tmp_path / "in"
    fx.planted_snirf(inp / "a")
    fx.planted_nwb(inp / "b")
    _copy_tree(fx.fetch_mne_testing(fx.MNE_TESTING_FAMILIES["nirx"] + fx.MNE_TESTING_FAMILIES["snirf"]), inp / "c")
    plan, out, manifest = plan_and_write(inp, tmp_path, key, schema)
    assert {e.datatype for e in ephys(plan)} == {"nirs", "ieeg"}
    assert any(e.ephys_format == "NWB" for e in ephys(plan))
    result = validate_bids(out)
    assert result.ok, json.dumps(result.errors, indent=1)[:4000]


# --- fix round 1 ------------------------------------------------------------------------------------------


def test_acq_entity_planned_and_written(tmp_path, key, schema):
    """The acq entity is stored under the schema's name (acquisition), so an acq-hd input is nameable and written."""
    from test_ephys_write import edf

    edf(tmp_path / "in" / "sub-01" / "eeg" / "sub-01_task-rest_acq-hd_eeg.edf", ["EEG Fp1", "EEG Cz"], his_id="P5555555")
    plan, out, manifest = plan_and_write(tmp_path / "in", tmp_path, key, schema)
    e, rel = _one(manifest, plan, "_eeg.vhdr")
    assert e.status == "ok" and not e.exclude and e.entities == {"task": "rest", "acquisition": "hd"}
    assert rel.endswith("_task-rest_acq-hd_eeg.vhdr")


def test_file_words_only_in_paths():
    """File-name words and extensions are skipped in paths only: in a header field they stay terms."""
    t = headers._Terms()
    t.name("Dat")
    t.text("Mat")
    t.paths(["nirx_15_3_recording/Khan_config.txt", "nirx_15_3_recording/Khan.dat"])
    got = t.result()
    assert {"Dat", "Mat", "Khan"} <= got
    assert not {"recording", "config", "txt", "dat"} & {g.lower() for g in got if g not in ("Dat",)}


def _khan_nwb(path: Path) -> Path:
    """An NWB file whose location, group, series and interval-table names carry a name."""
    from pynwb import NWBHDF5IO, NWBFile
    from pynwb.ecephys import ElectricalSeries
    from pynwb.epoch import TimeIntervals

    f = NWBFile(session_description="x", identifier="x", session_start_time=fx.MEAS_DATE)
    dev = f.create_device(name="amp")
    depth = f.create_electrode_group(name="DrKhan_shaft", description="depth", location="placed by DrKhan",
                                     device=dev)
    grid = f.create_electrode_group(name="grid", description="grid", location="left temporal", device=dev)
    for i in range(4):
        f.add_electrode(group=depth if i < 2 else grid, location="placed by DrKhan" if i < 2 else "left temporal")
    f.add_acquisition(ElectricalSeries(name="Khan_ieeg", data=np.zeros((512, 4), dtype="float32"),
                                       electrodes=f.create_electrode_table_region(list(range(4)), "all"),
                                       rate=256.0))
    notes = TimeIntervals(name="Khan_notes", description="x")
    notes.add_interval(start_time=1.0, stop_time=2.0)
    f.add_time_intervals(notes)
    path.parent.mkdir(parents=True, exist_ok=True)
    with NWBHDF5IO(str(path), "w") as io:
        io.write(f)
    return path


def test_nwb_names_and_locations_never_written(tmp_path, key, schema):
    src = _khan_nwb(tmp_path / "in" / fx.SUBJECT_DIR / "grid_rest.nwb")
    terms = nwb.harvest(src)
    assert {"placed by DrKhan", "DrKhan_shaft", "Khan_ieeg", "Khan_notes"} <= terms
    assert "left temporal" not in terms and nwb.safe_location("left temporal") == "left temporal"
    plan, out, manifest = plan_and_write(tmp_path / "in", tmp_path, key, schema)
    e, rel = _one(manifest, plan, "_ieeg.nwb")
    assert "khan" not in " ".join(_h5_strings(out / rel)).lower()
    for p in out.rglob("*"):
        if p.is_file():
            assert b"khan" not in p.read_bytes().lower(), p
    with pynwb.NWBHDF5IO(str(out / rel), "r") as io:
        got = io.read()
        assert list(got.electrodes["location"][:]) == ["n/a", "n/a", "left temporal", "left temporal"]
        assert sorted(got.electrode_groups) == ["group_001", "group_002"]
        assert list(got.acquisition) == ["ElectricalSeries"]
        assert "intervals_001" in got.intervals


def test_nwb_channel_types_in_plan_and_editable(tmp_path, key, schema):
    from aimport.planner import apply_plan_edits

    _khan_nwb(tmp_path / "in" / fx.SUBJECT_DIR / "grid_rest.nwb")
    fx.planted_brainvision(tmp_path / "in" / "bv")
    seen = {}

    def edit(plan) -> None:
        e = next(x for x in ephys(plan) if x.ephys_format == "NWB")
        seen["guess"] = dict(e.channel_types)
        bv = next(x for x in ephys(plan) if x.ephys_format == "BrainVision")
        assert bv.channel_types == {}
        with pytest.raises(ValueError, match="channel_types"):
            apply_plan_edits(plan, [{"id": e.id, "channel_types": {"group_001": "eeg", "group_002": "ecog"}}], schema)
        with pytest.raises(ValueError, match="channel_types"):
            apply_plan_edits(plan, [{"id": e.id, "channel_types": {"group_009": "seeg"}}], schema)
        with pytest.raises(ValueError, match="channel_types"):
            apply_plan_edits(plan, [{"id": bv.id, "channel_types": {"group_001": "seeg"}}], schema)
        apply_plan_edits(plan, [{"id": e.id, "channel_types": {"group_001": "dbs", "group_002": "ecog"}}], schema)

    plan, out, manifest = plan_and_write(tmp_path / "in", tmp_path, key, schema, edit=edit)
    assert seen["guess"] == {"group_001": "seeg", "group_002": "ecog"}
    e, rel = _one(manifest, plan, "_ieeg.nwb")
    types = [r["type"] for r in read_tsv(out / rel.replace("_ieeg.nwb", "_channels.tsv"))]
    assert types == ["DBS", "DBS", "ECOG", "ECOG"]
    car = json.loads((out / rel.replace("_ieeg.nwb", "_ieeg.json")).read_text())
    assert (car["ECOGChannelCount"], car["SEEGChannelCount"]) == (2, 0)


def test_resave_split_without_private_split_size(tmp_path, monkeypatch):
    """_resave_split falls back to MNE's 2GB default when MNE-BIDS drops its private split size."""
    import mne_bids.write as mbw

    scratch = tmp_path / "scratch"
    scratch.mkdir()
    info = mne.create_info([f"MEG {i:03d}" for i in range(1, 21)], 1000.0, "mag")
    raw = mne.io.RawArray(np.random.default_rng(0).standard_normal((20, 60000)) * 1e-13, info, verbose=False)
    raw.save(scratch / "sub-emptyroom_ses-19241231_task-noise_meg.fif", split_size="3MB", split_naming="bids",
             verbose=False)
    parts = sorted(scratch.glob("*_split-*_meg.fif"))
    assert len(parts) > 1
    monkeypatch.delattr(mbw, "_FIFF_SPLIT_SIZE")
    new = ephys_write._resave_split(parts, "sub-emptyroom_task-noise_split-01_meg.fif", scratch)
    assert [p.name for p in new] == ["sub-emptyroom_task-noise_meg.fif"]  # one part at 2GB
    assert mne.io.read_raw_fif(new[0], preload=False, verbose="error").n_times == 60000


def test_nwb_channel_conversion_applied_before_offset(tmp_path):
    """Per NWB ElectricalSeries spec, data in Volts is data * conversion * channel_conversion + offset."""
    from pynwb import NWBHDF5IO, NWBFile
    from pynwb.ecephys import ElectricalSeries

    path = tmp_path / "scaled.nwb"
    f = NWBFile(session_description="x", identifier="x", session_start_time=fx.MEAS_DATE)
    dev = f.create_device(name="amp")
    grp = f.create_electrode_group(name="grid", description="grid", location="cortex", device=dev)
    for _ in range(3):
        f.add_electrode(group=grp, location="cortex")
    raw_samples = np.array([[100.0, 200.0, 300.0], [400.0, 500.0, 600.0]], dtype=np.float64)
    es = ElectricalSeries(
        name="ieeg",
        data=raw_samples,
        electrodes=f.create_electrode_table_region([0, 1, 2], "all"),
        rate=256.0,
        conversion=2.0,
        channel_conversion=np.array([1e-6, 5e-6, 1e-5], dtype=np.float64),
        offset=0.5,
    )
    f.add_acquisition(es)
    with NWBHDF5IO(str(path), "w") as io:
        io.write(f)

    with NWBHDF5IO(str(path), "r") as io:
        expected = io.read().acquisition["ieeg"].get_data_in_units().T

    np.testing.assert_allclose(nwb.to_raw(path).get_data(), expected)
    series = nwb.open_series(path)
    try:
        np.testing.assert_allclose(series.read([2, 0, 1], 0, 2), expected[[2, 0, 1]])
    finally:
        series.close()
