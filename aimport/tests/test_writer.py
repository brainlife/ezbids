import copy
import gzip
import json
import shutil
import sys
from datetime import datetime, timedelta
from pathlib import Path

import nibabel as nib
import numpy as np
import pydicom
import pytest
from pydicom.dataset import FileDataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, generate_uid

from aimport.ezbids_runner import CoreObject, CoreResult, CoreSeries, CoreSubject, parse_core, run_ezbids, stage_input
from aimport.plan import Plan, PlanEntry
from aimport.planner import build_plan, run_terms
from aimport.pseudonyms import PseudonymKey
from aimport.writer import _parse_age, write_bids
from conftest import NATIVE, PLANTED, tokens

FIXTURES = Path(__file__).parent / "fixtures"
sys.path.insert(0, str(FIXTURES))
from fetch_dcm_qa import fetch_dcm_qa  # noqa: E402

CACHE = Path("/tmp/aimport-dcm-qa-cache")
TERMS = {"Smith^John", "Smith", "John", "MRN0042", "19700101", "1970-01-01", "Hospital X"}
DIRTY = {"PatientName": "Smith^John", "PatientID": "MRN0042", "PatientSex": "M", "InstitutionName": "Hospital X",
         "SeriesDescription": "T1 Smith", "RepetitionTime": 2.0, "IntendedFor": ["x"], "B0FieldSource": None}


def write_dicom(path: Path, **fields) -> None:
    meta = FileMetaDataset()
    meta.MediaStorageSOPClassUID = "1.2.840.10008.5.1.4.1.1.4"
    meta.MediaStorageSOPInstanceUID = generate_uid()
    meta.TransferSyntaxUID = ExplicitVRLittleEndian
    ds = FileDataset(str(path), {}, file_meta=meta, preamble=b"\0" * 128)
    ds.SOPClassUID, ds.SOPInstanceUID = meta.MediaStorageSOPClassUID, meta.MediaStorageSOPInstanceUID
    for k, v in fields.items():
        setattr(ds, k, v)
    path.parent.mkdir(parents=True, exist_ok=True)
    ds.save_as(str(path), enforce_file_format=True)


def write_nifti(path: Path, value=1.0, descrip="Smith^John MRN0042") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    img = nib.Nifti1Image(np.full((3, 4, 5), value, dtype=np.float32), np.diag([2.0, 2.0, 2.0, 1.0]))
    img.header["descrip"] = descrip.encode()
    img.header["aux_file"] = b"smith.aux"
    img.header["intent_name"] = b"john"
    img.header["db_name"] = b"hospital x"
    nib.save(img, str(path))


def entry(series_idx, datatype, suffix, entities=None, subject_idx=0, session_idx=0, subject="01", session="1", **kw):
    base = dict(id=f"s{series_idx}-sub{subject_idx}-ses{session_idx}", series_idx=series_idx, subject_idx=subject_idx,
                session_idx=session_idx, subject=subject, session=session, datatype=datatype, suffix=suffix,
                entities=entities or {}, brainlife_datatype=None, brainlife_tags=[], source="heuristic",
                confidence=0.9, reason="", deface=datatype == "anat", exclude=False, status="ok", description="")
    base.update(kw)
    return PlanEntry(**base)


class World:
    """A staged dir with one subject, two sessions (T1w twice in session 1, fmap + bold in 1, T1w in 2)."""

    def __init__(self, base: Path):
        self.staged, self.inp, self.out = base / "staged", base / "in", base / "out"
        objs, self.series_dirs = [], {}
        specs = [  # series_idx, session_idx, dir, date, time, extra files
            (0, 0, "t1a", "2023-01-10", "09:00:01.25", []),
            (0, 0, "t1b", "2023-01-10", "09:30:00", []),
            (1, 0, "fm", "2023-01-10", "09:40:00", []),
            (2, 0, "bold", "2023-01-10", "09:50:00", []),
            (3, 0, "dwi", "2023-01-10", "10:00:00", [".bval", ".bvec"]),
            (0, 1, "t1c", "2023-02-14", "08:00:00", []),
        ]
        for series_idx, ses, d, date, time, extra in specs:
            stem = f"{d}/img"
            write_nifti(self.staged / f"{stem}.nii.gz", value=float(len(objs) + 1))
            (self.staged / f"{stem}.json").write_text("{}")
            paths = [Path(f"./{stem}.json"), Path(f"./{stem}.nii.gz")]
            for e in extra:
                (self.staged / f"{stem}{e}").write_text("0 1 2\n")
                paths.append(Path(f"./{stem}{e}"))
            write_dicom(self.inp / d / "1.dcm", PatientID="MRN0042", PatientName="Smith^John", PatientAge="045Y",
                        PatientSex="F")
            objs.append(CoreObject(series_idx, 0, ses, date, time, {}, paths, dict(DIRTY)))
        series = [CoreSeries(i, "x", {}, "", "d", {}, Path("x")) for i in range(4)]
        subjects = [CoreSubject(0, "x", [{"PatientID": "MRN0042"}], [{}, {}])]
        self.core = CoreResult(series, objs, subjects)
        self.plan = Plan(target="bids", entries=[
            entry(0, "anat", "T1w"), entry(1, "fmap", "phasediff"), entry(2, "func", "bold", {"task": "rest"}),
            entry(3, "dwi", "dwi"), entry(0, "anat", "T1w", session_idx=1, session="2"),
        ], approved=True, dataset_name="Study", readme="Hello Smith")

    def write(self, key, schema, **kw):
        kw.setdefault("out_dir", self.out)
        return write_bids(kw.pop("plan", self.plan), self.core, self.inp, TERMS, key, schema, kw.pop("out_dir"),
                          staged_dir=self.staged, **kw)


@pytest.fixture
def world(tmp_path):
    return World(tmp_path)


@pytest.fixture
def key(tmp_path):
    k = PseudonymKey.load(tmp_path / "keys", "proj")
    yield k
    k.close()


def read_tsv(path: Path):
    lines = path.read_text().splitlines()
    head = lines[0].split("\t")
    return [dict(zip(head, ln.split("\t"))) for ln in lines[1:]]


def test_refuses_unapproved(world, key, schema):
    world.plan.approved = False
    with pytest.raises(PermissionError):
        world.write(key, schema)
    assert not world.out.exists()


def test_layout(world, key, schema):
    written = world.write(key, schema)
    out = world.out
    for rel in ["sub-01/ses-1/anat/sub-01_ses-1_run-1_T1w.nii.gz", "sub-01/ses-1/anat/sub-01_ses-1_run-2_T1w.json",
                "sub-01/ses-2/anat/sub-01_ses-2_T1w.nii.gz", "sub-01/ses-1/func/sub-01_ses-1_task-rest_bold.nii.gz",
                "sub-01/ses-1/dwi/sub-01_ses-1_dwi.bval", "sub-01/ses-1/dwi/sub-01_ses-1_dwi.bvec",
                "sub-01/ses-1/fmap/sub-01_ses-1_phasediff.json", "dataset_description.json", "README.md",
                "participants.tsv", "sub-01/ses-1/sub-01_ses-1_scans.tsv", "sub-01/ses-2/sub-01_ses-2_scans.tsv"]:
        assert (out / rel).is_file(), rel
    assert not (out / "sub-01/ses-1/anat/sub-01_ses-1_T1w.nii.gz").exists()  # collision: both got run-
    assert all(p.is_file() and out.resolve() in p.resolve().parents for p in written)
    assert {p.resolve() for p in written} == {p.resolve() for p in out.rglob("*") if p.is_file()}
    dd = json.loads((out / "dataset_description.json").read_text())
    assert dd == {"Name": "Study", "BIDSVersion": "1.11.2", "DatasetType": "raw", "GeneratedBy": [{"Name": "brainlife.io/aimport"}]}
    assert (out / "README.md").read_text() == "Hello [x]"


def test_manifest_maps_entries_to_written_niftis(world, key, schema):
    manifest = {}
    world.write(key, schema, manifest=manifest)
    assert manifest["s0-sub0-ses0"] == ["sub-01/ses-1/anat/sub-01_ses-1_run-1_T1w.nii.gz",
                                        "sub-01/ses-1/anat/sub-01_ses-1_run-2_T1w.nii.gz"]
    assert manifest["s2-sub0-ses0"] == ["sub-01/ses-1/func/sub-01_ses-1_task-rest_bold.nii.gz"]
    assert all((world.out / r).is_file() for rels in manifest.values() for r in rels)


def test_manifest_cleared_when_write_fails(world, key, schema, monkeypatch):
    manifest = {}
    monkeypatch.setattr("aimport.writer._Writer.write_participants", lambda self, items: 1 / 0)
    with pytest.raises(ZeroDivisionError):
        world.write(key, schema, manifest=manifest)
    assert manifest == {}


def test_no_readme_when_empty(world, key, schema):
    world.plan.readme = ""
    world.write(key, schema)
    assert not (world.out / "README.md").exists()


def test_excluded_and_not_ok_never_written(world, key, schema):
    world.plan.entries[2].exclude = True
    world.plan.entries[3].status = "unknown"
    world.write(key, schema)
    assert not list(world.out.rglob("*bold*")) and not list(world.out.rglob("*dwi*"))


def test_sidecars_scrubbed(world, key, schema):
    world.write(key, schema)
    sc = json.loads((world.out / "sub-01/ses-1/func/sub-01_ses-1_task-rest_bold.json").read_text())
    assert sc == {"SeriesDescription": "T1 [x]", "RepetitionTime": 2.0, "TaskName": "rest"}


def test_no_identifiers_in_output(world, key, schema):
    world.write(key, schema)
    for f in world.out.rglob("*"):
        if f.suffix in {".json", ".tsv", ".md"}:
            assert not PLANTED & tokens(f.read_text()), f
            assert "smith" not in f.read_text().lower()
        if f.name.endswith(".nii.gz"):
            h = nib.load(str(f)).header
            text = " ".join(bytes(h[k]).decode(errors="replace") for k in ("descrip", "aux_file", "intent_name", "db_name"))
            assert not (PLANTED | NATIVE) & tokens(text) and text.strip("\0 ") == ""
            assert not (PLANTED | NATIVE) & tokens(gzip.open(f).read(348 + 64).decode(errors="replace"))


def test_nifti_data_and_affine_kept(world, key, schema):
    world.write(key, schema)
    new = nib.load(str(world.out / "sub-01/ses-2/anat/sub-01_ses-2_T1w.nii.gz"))
    old = nib.load(str(world.staged / "t1c/img.nii.gz"))
    assert np.array_equal(new.get_fdata(), old.get_fdata()) and np.array_equal(new.affine, old.affine)
    assert new.get_data_dtype() == old.get_data_dtype() and new.shape == old.shape


def test_dates_shifted_intervals_kept(world, key, schema):
    world.write(key, schema)
    off = key.date_offset_days("01")
    s1 = read_tsv(world.out / "sub-01/ses-1/sub-01_ses-1_scans.tsv")
    s2 = read_tsv(world.out / "sub-01/ses-2/sub-01_ses-2_scans.tsv")
    assert s1[0]["filename"] == "anat/sub-01_ses-1_run-1_T1w.nii.gz"
    t1 = datetime.fromisoformat(s1[0]["acq_time"])
    t2 = datetime.fromisoformat(s2[0]["acq_time"])
    assert s1[0]["acq_time"] == (datetime(2023, 1, 10, 9, 0, 1) + timedelta(days=off)).isoformat()
    assert t2 - t1 == datetime(2023, 2, 14, 8) - datetime(2023, 1, 10, 9, 0, 1)
    assert "2023-01-10" not in (world.out / "sub-01/ses-1/sub-01_ses-1_scans.tsv").read_text()


def test_placeholder_date_is_na(world, key, schema):
    for o in world.core.objects:
        o.acquisition_date = "0000-00-00"
    world.write(key, schema)
    assert {r["acq_time"] for r in read_tsv(world.out / "sub-01/ses-1/sub-01_ses-1_scans.tsv")} == {"n/a"}


@pytest.mark.parametrize("raw,expected", [("045Y", "45"), ("018M", "1.5"), ("006W", "0.1"), ("100D", "0.3"),
                                          ("090Y", "89"), ("089Y", "89"), ("999Y", "89"), ("", "n/a"), ("abc", "n/a"), (None, "n/a")])
def test_parse_age(raw, expected):
    assert _parse_age(raw) == expected


def test_participants_age_sex(world, key, schema):
    world.write(key, schema)
    assert read_tsv(world.out / "participants.tsv") == [{"participant_id": "sub-01", "age": "45", "sex": "F"}]


def test_participants_run_local_identity_uses_used_files(world, key, schema):
    world.core.subjects[0].patient_info = [{"PatientID": "anon"}]
    world.write(key, schema)
    assert read_tsv(world.out / "participants.tsv")[0]["age"] == "45"


def test_participants_na_without_dicoms(world, key, schema):
    shutil.rmtree(world.inp)
    world.inp.mkdir()
    world.write(key, schema)
    assert read_tsv(world.out / "participants.tsv") == [{"participant_id": "sub-01", "age": "n/a", "sex": "n/a"}]


def test_participants_sex_other_and_odd_values(world, key, schema):
    for d in world.inp.rglob("*.dcm"):
        write_dicom(d, PatientID="MRN0042", PatientAge="002W", PatientSex="X")
    world.write(key, schema)
    assert read_tsv(world.out / "participants.tsv")[0]["sex"] == "n/a"


def test_intended_for(world, key, schema):
    world.write(key, schema)
    fm = json.loads((world.out / "sub-01/ses-1/fmap/sub-01_ses-1_phasediff.json").read_text())
    assert fm["IntendedFor"] == ["bids::sub-01/ses-1/dwi/sub-01_ses-1_dwi.nii.gz",
                                 "bids::sub-01/ses-1/func/sub-01_ses-1_task-rest_bold.nii.gz"]
    t1 = json.loads((world.out / "sub-01/ses-2/anat/sub-01_ses-2_T1w.json").read_text())
    assert "IntendedFor" not in t1


def test_no_intended_for_without_targets(world, key, schema):
    world.plan.entries[2].exclude = world.plan.entries[3].exclude = True
    world.write(key, schema)
    assert "IntendedFor" not in json.loads((world.out / "sub-01/ses-1/fmap/sub-01_ses-1_phasediff.json").read_text())


def test_key_never_in_output(world, key, schema):
    world.write(key, schema)
    assert not list(world.out.rglob("*aimport-key*"))
    assert world.out.resolve() not in key.path.resolve().parents


def test_out_dir_must_be_empty(world, key, schema):
    world.out.mkdir()
    (world.out / "old.txt").write_text("x")
    with pytest.raises(FileExistsError):
        world.write(key, schema)
    assert (world.out / "old.txt").read_text() == "x"


def test_empty_existing_out_dir_ok(world, key, schema):
    world.out.mkdir()
    world.write(key, schema)
    assert (world.out / "dataset_description.json").exists()


def test_never_writes_outside_out_dir(world, key, schema, monkeypatch):
    monkeypatch.setattr(type(schema), "filename", lambda self, *a, **k: "../escape/sub-01_T1w.nii.gz")
    with pytest.raises(ValueError, match="outside"):
        world.write(key, schema)
    assert not (world.out.parent / "escape").exists()


@pytest.mark.parametrize("bad", ["../../../x.nii.gz", "/etc/x.nii.gz"])
def test_never_reads_outside_staged_dir(world, key, schema, bad):
    world.core.objects[0].paths[1] = Path(bad)
    with pytest.raises(ValueError, match="outside"):
        world.write(key, schema)


def test_symlink_into_input_is_read(world, key, schema, tmp_path):
    src = world.inp / "real.nii.gz"
    write_nifti(src, 7.0)
    link = world.staged / "t1c/img.nii.gz"
    link.unlink()
    link.symlink_to(src)
    world.write(key, schema)
    got = nib.load(str(world.out / "sub-01/ses-2/anat/sub-01_ses-2_T1w.nii.gz"))
    assert float(got.get_fdata().flat[0]) == 7.0
    assert nib.load(str(src)).header["descrip"].tobytes().startswith(b"Smith")  # input untouched


def test_symlink_elsewhere_refused(world, key, schema, tmp_path):
    other = tmp_path / "elsewhere.nii.gz"
    write_nifti(other)
    link = world.staged / "t1c/img.nii.gz"
    link.unlink()
    link.symlink_to(other)
    with pytest.raises(ValueError, match="outside"):
        world.write(key, schema)
    assert not world.out.exists() or not any(world.out.iterdir())


def test_failure_leaves_no_partial_output(world, key, schema):
    (world.staged / "t1c/img.nii.gz").unlink()
    with pytest.raises(FileNotFoundError):
        world.write(key, schema)
    assert not world.out.exists()


def test_identifying_label_refused(world, key, schema):
    world.plan.entries[2].entities = {"task": "smith"}
    with pytest.raises(ValueError, match="identifying"):
        world.write(key, schema)


# --- docker: the whole pipeline on planted DICOMs ---------------------------

class Fake:
    name = "fake"

    def __init__(self, idx):
        self.idx = idx

    def complete(self, system, user, step):
        if step == "classify":
            return json.dumps([{"series_idx": self.idx, "datatype": "func", "suffix": "bold", "entities": {"task": "fa"},
                                "confidence": 0.9, "reason": "bold"}])
        return "nope"


@pytest.fixture(scope="module")
def planted_out(tmp_path_factory, schema):
    base = tmp_path_factory.mktemp("writer")
    src = fetch_dcm_qa(base / "in", cache=CACHE)
    staged = stage_input(src, base / "work")
    core = parse_core(run_ezbids(staged, log=lambda line: None))
    bold = next(s.series_idx for s in core.series if "func-bold" in s.series_description)
    with PseudonymKey.load(base / "keys", "proj") as key:
        plan = build_plan(core, src, key, set(), Fake(bold), schema, "bids", staged_dir=staged)
        plan.approved = True
        terms = run_terms(core, src)
        out = base / "out"
        written = write_bids(plan, core, src, terms, key, schema, out, staged_dir=staged)
    return out, written, plan


@pytest.mark.docker
def test_planted_layout_and_no_leaks(planted_out):
    out, written, plan = planted_out
    names = {p.relative_to(out).as_posix() for p in written}
    print("\n" + "\n".join(sorted(names)))
    assert any(n.endswith("_T1w.nii.gz") for n in names)
    assert any("/fmap/" in n and n.endswith("_phasediff.json") for n in names)
    assert any("/dwi/" in n and n.endswith(".bval") for n in names)
    assert any("/func/" in n and n.endswith("_bold.nii.gz") for n in names)
    mags = {Path(n).name.split("_magnitude")[0] for n in names if "_magnitude" in n and n.endswith(".json")}
    suffixes = {Path(n).name.split("_")[-1] for n in names if "/fmap/" in n and n.endswith(".json")}
    assert suffixes == {"magnitude1.json", "magnitude2.json", "phasediff.json"} and len(mags) == 1
    assert mags == {Path(n).name.rsplit("_phasediff", 1)[0] for n in names if n.endswith("_phasediff.json")}
    for row in (out / "participants.tsv").read_text().splitlines()[1:]:
        _pid, age, sex = row.split("\t")
        assert age == "n/a" or float(age) <= 89
        assert sex in {"M", "F", "O", "n/a"}
    assert (out / "participants.json").is_file()
    assert not list(out.rglob("*aimport-key*"))
    for f in out.rglob("*"):
        if f.is_file() and f.suffix in {".json", ".tsv", ".md"}:
            text = f.read_text()
            assert not PLANTED & tokens(text) and not NATIVE & tokens(text), f
        if f.name.endswith(".nii.gz"):
            h = nib.load(str(f)).header
            text = " ".join(bytes(h[k]).decode(errors="replace") for k in ("descrip", "aux_file", "intent_name", "db_name"))
            assert not (PLANTED | NATIVE) & tokens(text), f
    fm = next(out.rglob("*phasediff.json"))
    assert json.loads(fm.read_text())["IntendedFor"]


# --- review fixes ---------------------------------------------------------------

def test_scaled_int16_voxels_byte_identical(world, key, schema):
    src = world.staged / "t1c/img.nii.gz"
    raw = (np.arange(60, dtype=np.int16).reshape(3, 4, 5) * 7 - 100)
    img = nib.Nifti1Image(raw, np.diag([1.5, 2.0, 2.5, 1.0]))
    img.header.set_slope_inter(0.5, 3)
    img.header["descrip"] = b"Smith^John"
    nib.save(img, str(src))
    world.write(key, schema)
    dest = world.out / "sub-01/ses-2/anat/sub-01_ses-2_T1w.nii.gz"
    assert dest.read_bytes()[:2] == b"\x1f\x8b"
    old, new = nib.load(str(src)), nib.load(str(dest))
    assert np.array_equal(np.asanyarray(new.dataobj.get_unscaled()), np.asanyarray(old.dataobj.get_unscaled()))
    assert np.asanyarray(new.dataobj.get_unscaled()).tobytes() == raw.tobytes()
    assert np.array_equal(new.get_fdata(), old.get_fdata())
    assert np.array_equal(new.affine, old.affine)
    assert new.get_data_dtype() == old.get_data_dtype()
    assert (new.dataobj.slope, new.dataobj.inter) == (0.5, 3)
    assert new.header["descrip"].tobytes().strip(b"\0") == b""


def test_nifti2_rejected_clearly(world, key, schema):
    nib.save(nib.Nifti2Image(np.zeros((2, 2, 2), np.int16), np.eye(4)), str(world.staged / "t1c/img.nii.gz"))
    with pytest.raises(ValueError, match="NIfTI-1"):
        world.write(key, schema)
    assert not world.out.exists()


def test_participants_json(world, key, schema):
    world.write(key, schema)
    pj = json.loads((world.out / "participants.json").read_text())
    assert pj["age"]["Units"] == "year" and pj["age"]["Description"] == "age at first scan of this import"
    assert set(pj["sex"]["Levels"]) == {"M", "F", "O"}


def two_echo_world(world, echoes):
    world.plan.entries[1].suffix = "magnitude1"
    first = world.core.objects[2]
    first.sidecar = {**first.sidecar, **echoes[0]}
    second = copy.copy(first)
    second.sidecar = {**first.sidecar, **echoes[1]}
    world.core.objects.insert(3, second)


@pytest.mark.parametrize("echoes", [
    [{"EchoNumber": 1, "EchoTime": 0.01}, {"EchoNumber": 2, "EchoTime": 0.01246}],
    [{"EchoNumber": 2, "EchoTime": 0.01246}, {"EchoNumber": 1, "EchoTime": 0.01}],
    [{"EchoNumber": None, "EchoTime": 0.01}, {"EchoNumber": None, "EchoTime": 0.01246}],
])
def test_two_echoes_become_magnitude1_and_2(world, key, schema, echoes):
    for e in echoes:
        if e["EchoNumber"] is None:
            e.pop("EchoNumber")
    two_echo_world(world, echoes)
    world.core.objects[2].sidecar.pop("EchoNumber", None)
    world.write(key, schema)
    fm = sorted(p.name for p in (world.out / "sub-01/ses-1/fmap").glob("*.json"))
    assert fm == ["sub-01_ses-1_magnitude1.json", "sub-01_ses-1_magnitude2.json"]
    m1 = json.loads((world.out / "sub-01/ses-1/fmap/sub-01_ses-1_magnitude1.json").read_text())
    assert m1["EchoTime"] == 0.01


def test_same_echo_repeated_uses_run(world, key, schema):
    two_echo_world(world, [{"EchoNumber": 1}, {"EchoNumber": 1}])
    world.write(key, schema)
    fm = sorted(p.name for p in (world.out / "sub-01/ses-1/fmap").glob("*.json"))
    assert fm == ["sub-01_ses-1_run-1_magnitude1.json", "sub-01_ses-1_run-2_magnitude1.json"]


def test_short_numeric_term_does_not_block_paths(world, key, schema):
    world.terms = TERMS | {"01", "1"}
    write_bids(world.plan, world.core, world.inp, world.terms, key, schema, world.out, staged_dir=world.staged)
    assert (world.out / "sub-01/ses-1/anat/sub-01_ses-1_run-1_T1w.nii.gz").exists()


def test_long_identifying_term_still_blocks_paths(world, key, schema):
    world.plan.entries[2].entities = {"task": "mrn0042"}
    with pytest.raises(ValueError, match="identifying"):
        world.write(key, schema)


def test_refuses_anat_without_deface_unless_opted_out(world, key, schema, tmp_path):
    world.plan.entries[0].deface = False
    with pytest.raises(ValueError, match="without defacing"):
        world.write(key, schema)
    assert not world.out.exists()
    world.plan.entries[0].deface_opt_out = True
    world.write(key, schema)
    assert (world.out / "sub-01/ses-1/anat/sub-01_ses-1_run-1_T1w.nii.gz").is_file()


def test_placeholder_patient_id_not_used_to_find_demographics(world, key, schema):
    for d in world.inp.rglob("*.dcm"):
        d.unlink()
    write_dicom(world.inp / "someone_else" / "1.dcm", PatientID="ANONYMOUS", PatientAge="070Y", PatientSex="M")
    world.core.subjects[0].patient_info = [{"PatientID": "ANONYMOUS"}]
    world.write(key, schema)
    assert read_tsv(world.out / "participants.tsv")[0]["age"] == "n/a"


# --- BIDS-like identifiers in the headers (dcm_qa_xa30: PatientName XAtest_sub-July11) ----------------

def _identity_world(world, **fields):
    """The world's DICOMs and ezBIDS patient info rewritten with these identity fields."""
    for dcm in world.inp.rglob("1.dcm"):
        write_dicom(dcm, PatientAge="045Y", PatientSex="F", **fields)
    world.core.subjects[0].patient_info = [dict(fields)]
    for o in world.core.objects:
        o.sidecar = {**{k: v for k, v in o.sidecar.items() if k not in ("PatientName", "PatientID")}, **fields}
    return run_terms(world.core, world.inp)


def _all_output_text(out: Path) -> str:
    parts = [str(p.relative_to(out)) for p in out.rglob("*")]
    for p in out.rglob("*"):
        if p.is_file() and not p.name.endswith(".nii.gz"):
            parts.append(p.read_text(errors="replace"))
        elif p.is_file():
            parts.append(bytes(nib.load(str(p)).header["descrip"]).decode(errors="replace"))
    return "\n".join(parts)


def test_bids_key_in_patient_name_is_not_a_term(world, key, schema):
    """The exact dcm_qa_xa30 case: execute writes sub-01..., the values around `sub` never leave."""
    terms = _identity_world(world, PatientName="XAtest_sub-July11", PatientID="12343@hucheng")
    assert {"XAtest", "July11"} <= terms and "sub" not in {t.lower() for t in terms}
    write_bids(world.plan, world.core, world.inp, terms, key, schema, world.out, staged_dir=world.staged)
    assert (world.out / "sub-01/ses-1/anat/sub-01_ses-1_run-1_T1w.nii.gz").exists()
    text = _all_output_text(world.out).lower()
    assert not [t for t in ("xatest", "july11", "hucheng") if t in text]


@pytest.mark.parametrize("pid", ["sub-01", "sub-07"])
def test_bids_like_patient_id_does_not_block_or_name_the_output(world, key, schema, pid):
    """A PatientID written as a BIDS label: the output is written, under a generated label (01, the first
    free one), never the source's when no sub- folder carried it (sub-07 is not reused)."""
    terms = _identity_world(world, PatientName="Doe^Jane", PatientID=pid)
    write_bids(world.plan, world.core, world.inp, terms, key, schema, world.out, staged_dir=world.staged)
    assert sorted(p.name for p in world.out.glob("sub-*")) == ["sub-01"]
    assert "sub-07" not in _all_output_text(world.out)


def test_destination_check_never_refuses_a_bare_bids_word(world, key, schema):
    terms = TERMS | {"sub", "ses", "anat", "T1w", "run", "task", "bold", "dwi", "fmap", "Sub"}
    write_bids(world.plan, world.core, world.inp, terms, key, schema, world.out, staged_dir=world.staged)
    assert (world.out / "sub-01/ses-1/func/sub-01_ses-1_task-rest_bold.nii.gz").exists()
