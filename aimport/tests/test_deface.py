import shutil
import subprocess
import sys
import time
from pathlib import Path

import nibabel as nib
import numpy as np
import pytest

from aimport.deface import DefaceError, deface
from aimport.ezbids_runner import parse_core, run_ezbids, stage_input
from aimport.plan import Plan
from aimport.planner import build_plan, run_terms
from aimport.pseudonyms import PseudonymKey
from aimport.writer import write_bids
from test_writer import CACHE, Fake, entry

sys.path.insert(0, str(Path(__file__).parent / "fixtures"))
from fetch_dcm_qa import fetch_dcm_qa  # noqa: E402

AFFINE = np.diag([2.0, 2.0, 2.0, 1.0])
T1 = "sub-01/ses-1/anat/sub-01_ses-1_T1w.nii.gz"
T2 = "sub-01/ses-1/anat/sub-01_ses-1_T2w.nii.gz"
BOLD = "sub-01/ses-1/func/sub-01_ses-1_task-x_bold.nii.gz"


def save(path: Path, value=5.0):
    path.parent.mkdir(parents=True, exist_ok=True)
    data = np.full((6, 6, 6), value, dtype=np.float32)
    img = nib.Nifti1Image(data, AFFINE)
    img.header["descrip"] = b"clean"
    nib.save(img, str(path))


def make(tmp_path, deface_ids=("a", "b")):
    bids = tmp_path / "work" / "bids"
    for rel in (T1, T2, BOLD):
        save(bids / rel)
    plan = Plan(target="bids", entries=[
        entry(1, "anat", "T1w", deface=True), entry(2, "anat", "T2w", deface=True),
        entry(3, "func", "bold", entities={"task": "x"})])
    for e, i in zip(plan.entries, ("a", "b", "c")):
        e.id = i
        e.deface = i in deface_ids
    manifest = {"a": [T1], "b": [T2], "c": [BOLD]}
    return bids, plan, manifest, tmp_path / "work" / "pre-deface"


def fake_run(calls, fail_on=None, descrip=b"Smith^John"):
    """A pydeface stand-in: writes a copy of the input with the first slice zeroed."""
    def run(argv, **kw):
        calls.append((argv, kw))
        assert isinstance(argv, list) and not kw.get("shell")
        assert kw.get("timeout") == 600
        src, out = Path(argv[argv.index("--force") + 1]), Path(argv[argv.index("--outfile") + 1])
        if fail_on and fail_on in src.parts + (src.name,):
            return subprocess.CompletedProcess(argv, 1, "", "boom: bad things\n")
        img = nib.load(str(src))
        data = np.asarray(img.dataobj).copy()
        data[:, :, 0] = 0
        new = nib.Nifti1Image(data, img.affine)
        new.header["descrip"] = descrip
        nib.save(new, str(out))
        return subprocess.CompletedProcess(argv, 0, "", "")
    return run


@pytest.fixture
def calls(monkeypatch):
    c = []
    monkeypatch.setattr("aimport.deface.subprocess.run", fake_run(c))
    return c


def test_manifest_driven_selection(tmp_path, calls):
    bids, plan, manifest, pre = make(tmp_path, deface_ids=("a",))
    result = deface(bids, plan, "pydeface", pre, manifest)
    assert result == {"a": [pre / T1]}
    assert len(calls) == 1
    assert nib.load(str(pre / T1)).get_fdata()[:, :, 0].min() == 5.0  # the original
    out = nib.load(str(bids / T1))
    assert out.get_fdata()[:, :, 0].max() == 0 and out.shape == (6, 6, 6)
    assert nib.load(str(bids / T2)).get_fdata().min() == 5.0  # not selected
    assert not (pre / T2).exists() and not (pre / BOLD).exists()


def test_multiple_files_per_entry(tmp_path, calls):
    bids, plan, manifest, pre = make(tmp_path, deface_ids=("a",))
    manifest["a"].append(T2)
    assert deface(bids, plan, "pydeface", pre, manifest) == {"a": [pre / T1, pre / T2]}


def test_excluded_entry_not_defaced(tmp_path, calls):
    bids, plan, manifest, pre = make(tmp_path, deface_ids=("a",))
    del manifest["a"]  # excluded entries are never written
    assert deface(bids, plan, "pydeface", pre, manifest) == {}
    assert not calls


def test_pre_deface_dir_inside_bids_rejected(tmp_path, calls):
    bids, plan, manifest, _pre = make(tmp_path)
    for bad in (bids / "pre", bids, bids / "a" / ".." / "pre"):
        with pytest.raises(ValueError):
            deface(bids, plan, "pydeface", bad, manifest)
    assert not calls


def test_restore_on_failure(tmp_path, monkeypatch):
    bids, plan, manifest, pre = make(tmp_path)
    before = {r: (bids / r).read_bytes() for r in (T1, T2, BOLD)}
    monkeypatch.setattr("aimport.deface.subprocess.run", fake_run([], fail_on="sub-01_ses-1_T2w.nii.gz"))
    with pytest.raises(DefaceError) as ei:
        deface(bids, plan, "pydeface", pre, manifest)
    assert ei.value.entry_id == "b" and "boom" in str(ei.value)
    assert {r: (bids / r).read_bytes() for r in before} == before
    assert not (pre / T1).exists()
    assert not [p for p in tmp_path.rglob("*") if "deface-tmp" in p.name]


def test_restore_when_swap_fails(tmp_path, calls, monkeypatch):
    import aimport.deface as d
    bids, plan, manifest, pre = make(tmp_path)
    before = {r: (bids / r).read_bytes() for r in (T1, T2)}
    real, n = d.shutil.move, []

    def flaky(src, dst):
        n.append(1)
        if len(n) == 4:  # second original placed, then the second new image fails
            raise OSError("disk full")
        return real(src, dst)

    monkeypatch.setattr(d.shutil, "move", flaky)
    with pytest.raises(OSError):
        deface(bids, plan, "pydeface", pre, manifest)
    monkeypatch.setattr(d.shutil, "move", real)
    assert {r: (bids / r).read_bytes() for r in before} == before


def test_timeout_raises_deface_error(tmp_path, monkeypatch):
    bids, plan, manifest, pre = make(tmp_path)

    def run(argv, **kw):
        raise subprocess.TimeoutExpired(argv, 600)

    monkeypatch.setattr("aimport.deface.subprocess.run", run)
    with pytest.raises(DefaceError) as ei:
        deface(bids, plan, "pydeface", pre, manifest)
    assert ei.value.entry_id == "a" and "600" in str(ei.value)
    assert nib.load(str(bids / T1)).get_fdata().min() == 5.0


def test_header_text_cleared_data_unchanged(tmp_path, calls):
    bids, plan, manifest, pre = make(tmp_path, deface_ids=("a",))
    deface(bids, plan, "pydeface", pre, manifest)
    h = nib.load(str(bids / T1)).header
    for f in ("descrip", "aux_file", "intent_name", "db_name"):
        assert bytes(h[f]).strip(b"\0") == b""
    expected = np.full((6, 6, 6), 5.0, dtype=np.float32)
    expected[:, :, 0] = 0
    assert np.array_equal(np.asarray(nib.load(str(bids / T1)).dataobj), expected)


def test_changed_shape_refused_and_restored(tmp_path, monkeypatch):
    bids, plan, manifest, pre = make(tmp_path, deface_ids=("a",))
    before = (bids / T1).read_bytes()

    def run(argv, **kw):
        nib.save(nib.Nifti1Image(np.zeros((5, 5, 5), np.float32), AFFINE), argv[argv.index("--outfile") + 1])
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr("aimport.deface.subprocess.run", run)
    with pytest.raises(DefaceError):
        deface(bids, plan, "pydeface", pre, manifest)
    assert (bids / T1).read_bytes() == before


def test_quickshear_argv(tmp_path, monkeypatch):
    bids, plan, manifest, pre = make(tmp_path, deface_ids=("a",))
    seen = []

    def run(argv, **kw):
        seen.append(argv)
        assert kw.get("timeout") == 600 and not kw.get("shell")
        if argv[0].endswith("runROBEX.sh"):
            Path(argv[2]).write_bytes(b"mask")
        else:
            assert argv[0] == "quickshear"
            data = np.full((6, 6, 6), 5.0, np.float32)
            data[:, :, 0] = 0  # a plausible face-only output
            nib.save(nib.Nifti1Image(data, AFFINE), argv[3])
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr("aimport.deface.subprocess.run", run)
    deface(bids, plan, "quickshear", pre, manifest)
    assert [a[0].rsplit("/", 1)[-1] for a in seen] == ["runROBEX.sh", "quickshear"]
    assert "fslreorient2std" not in " ".join(" ".join(a) for a in seen)


def test_lossless_outside_face_despite_requantising_tool(tmp_path, monkeypatch):
    bids, plan, manifest, pre = make(tmp_path, deface_ids=("a",))
    rng = np.random.default_rng(0)
    raw = rng.integers(0, 1000, (6, 6, 6)).astype(np.int16)
    raw[3, 3, 3] = 0  # a zero in the original is not "face"
    img = nib.Nifti1Image(raw, AFFINE)
    img.header.set_slope_inter(0.5, 10.0)
    nib.save(img, str(bids / T1))
    original = (bids / T1).read_bytes()
    orig_raw = np.asanyarray(nib.load(str(bids / T1)).dataobj.get_unscaled()).copy()

    def run(argv, **kw):  # re-quantises everything (noise), zeroes the first slice
        src, out = Path(argv[argv.index("--force") + 1]), Path(argv[argv.index("--outfile") + 1])
        data = np.asarray(nib.load(str(src)).dataobj) + 0.123
        data[:, :, 0] = 0
        nib.save(nib.Nifti1Image(data.astype(np.float32), AFFINE), str(out))
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr("aimport.deface.subprocess.run", run)
    deface(bids, plan, "pydeface", pre, manifest)
    new = nib.load(str(bids / T1))
    new_raw = np.asanyarray(new.dataobj.get_unscaled())
    assert new_raw.dtype == orig_raw.dtype and (new.dataobj.slope, new.dataobj.inter) == (0.5, 10.0)
    face = np.zeros(raw.shape, bool)
    face[:, :, 0] = True
    assert np.array_equal(new_raw[~face], orig_raw[~face])  # byte-identical outside the face
    assert new_raw[3, 3, 3] == 0
    assert np.allclose(np.asarray(new.dataobj)[face], 0)  # reads back as zero, with the intercept
    assert (pre / T1).read_bytes() == original


def tool_writing(data_fn):
    def run(argv, **kw):
        src, out = Path(argv[argv.index("--force") + 1]), Path(argv[argv.index("--outfile") + 1])
        nib.save(nib.Nifti1Image(data_fn(np.asarray(nib.load(str(src)).dataobj)).astype(np.float32), AFFINE), str(out))
        return subprocess.CompletedProcess(argv, 0, "", "")
    return run


def zero_front(fraction):
    def fn(data):
        data = data.copy()
        data[: int(round(6 * fraction))] = 0
        return data
    return fn


@pytest.mark.parametrize("name,fn,message", [
    ("all-zero", lambda d: np.zeros_like(d), "more than 60%"),
    ("unchanged", lambda d: d, "removed no voxels"),
    ("too much", zero_front(4 / 6), "more than 60%"),
])
def test_implausible_mask_refused_and_restored(tmp_path, monkeypatch, name, fn, message):
    bids, plan, manifest, pre = make(tmp_path, deface_ids=("a",))
    before = (bids / T1).read_bytes()
    monkeypatch.setattr("aimport.deface.subprocess.run", tool_writing(fn))
    with pytest.raises(DefaceError, match=message) as ei:
        deface(bids, plan, "pydeface", pre, manifest)
    assert ei.value.entry_id == "a"
    assert (bids / T1).read_bytes() == before and not pre.exists()


def test_mask_at_limit_accepted(tmp_path, monkeypatch):
    bids, plan, manifest, pre = make(tmp_path, deface_ids=("a",))
    monkeypatch.setattr("aimport.deface.subprocess.run", tool_writing(zero_front(3 / 6)))  # 50%
    deface(bids, plan, "pydeface", pre, manifest)


def test_restore_failure_is_reported_and_others_restored(tmp_path, calls, monkeypatch):
    import aimport.deface as d
    bids, plan, manifest, pre = make(tmp_path)
    t1 = (bids / T1).read_bytes()
    real, n = d.shutil.move, []

    def flaky(src, dst):
        n.append(1)
        if len(n) == 4 or (len(n) > 4 and "T2w" in str(dst)):
            raise OSError("disk full")
        return real(src, dst)

    monkeypatch.setattr(d.shutil, "move", flaky)
    with pytest.raises(RuntimeError, match="T2w") as ei:
        deface(bids, plan, "pydeface", pre, manifest)
    assert isinstance(ei.value.__cause__, OSError)
    assert (bids / T1).read_bytes() == t1
    assert (pre / T2).is_file()  # the original that could not be restored is still there


def test_interrupt_between_move_and_record_loses_nothing(tmp_path, calls, monkeypatch):
    import aimport.deface as d
    bids, plan, manifest, pre = make(tmp_path, deface_ids=("a",))
    before = (bids / T1).read_bytes()
    real = d.shutil.move

    def interrupted(src, dst):
        real(src, dst)  # the original is moved, then the interrupt arrives
        raise KeyboardInterrupt

    monkeypatch.setattr(d.shutil, "move", interrupted)
    with pytest.raises(KeyboardInterrupt):
        deface(bids, plan, "pydeface", pre, manifest)
    monkeypatch.setattr(d.shutil, "move", real)
    assert (bids / T1).read_bytes() == before


def test_other_filesystem_rejected(tmp_path, calls, monkeypatch):
    import aimport.deface as d
    bids, plan, manifest, pre = make(tmp_path)
    monkeypatch.setattr(d, "_device", lambda p: 1 if Path(p) == bids.resolve() else 2)
    with pytest.raises(ValueError, match="same filesystem"):
        deface(bids, plan, "pydeface", pre, manifest)
    assert not calls


def test_intercept_not_representable_is_clear_error(tmp_path, monkeypatch):
    bids, plan, manifest, pre = make(tmp_path, deface_ids=("a",))
    img = nib.Nifti1Image(np.full((6, 6, 6), 5, np.int16), AFFINE)
    img.header.set_slope_inter(1.0, 100000.0)
    nib.save(img, str(bids / T1))
    before = (bids / T1).read_bytes()
    monkeypatch.setattr("aimport.deface.subprocess.run", tool_writing(zero_front(2 / 6)))
    with pytest.raises(DefaceError, match="reads back as zero"):
        deface(bids, plan, "pydeface", pre, manifest)
    assert (bids / T1).read_bytes() == before


def test_unknown_method_rejected(tmp_path):
    bids, plan, manifest, pre = make(tmp_path)
    with pytest.raises(ValueError):
        deface(bids, plan, "bogus", pre, manifest)


# --- docker: the real tools on the real T1w ------------------------------------

def deface_t1w(tmp_path, schema, method):
    src = fetch_dcm_qa(tmp_path / "in", cache=CACHE)
    staged = stage_input(src, tmp_path / "work")
    core = parse_core(run_ezbids(staged, log=lambda line: None))
    bold = next(s.series_idx for s in core.series if "func-bold" in s.series_description)
    with PseudonymKey.load(tmp_path / "keys", "proj") as key:
        plan = build_plan(core, src, key, set(), Fake(bold), schema, "bids", staged_dir=staged)
        plan.approved = True
        for e in plan.entries:
            e.deface = e.suffix == "T1w"
        bids, manifest = tmp_path / "bids", {}
        write_bids(plan, core, src, run_terms(core, src), key, schema, bids, staged_dir=staged, manifest=manifest)
    ids = [e.id for e in plan.entries if e.deface and not e.exclude and e.id in manifest]
    assert ids
    pre = tmp_path / "pre-deface"
    start = time.monotonic()
    originals = deface(bids, plan, method, pre, manifest)
    seconds = time.monotonic() - start
    assert set(originals) == set(ids)
    for eid in ids:
        for rel, orig in zip(manifest[eid], originals[eid]):
            assert pre not in bids.parents and bids not in orig.parents
            assert orig == pre / rel
            a, b = nib.load(str(orig)), nib.load(str(bids / rel))
            assert a.shape == b.shape and np.array_equal(a.affine, b.affine)
            x, y = np.asarray(a.dataobj, dtype=float), np.asarray(b.dataobj, dtype=float)
            changed = x != y
            ra = np.asanyarray(a.dataobj.get_unscaled())
            rb = np.asanyarray(b.dataobj.get_unscaled())
            assert a.get_data_dtype() == b.get_data_dtype()
            assert np.array_equal(ra[~changed], rb[~changed])  # raw values outside the face are exact
            assert np.allclose(y[changed], 0)  # inside the face: zero
            fraction = changed.mean()
            print(f"\nDEFACE {method}: {seconds:.1f} s, {fraction:.3%} of voxels changed")
            assert changed.any()
            assert fraction < 0.5  # the face only, a minority of voxels
            c = tuple(s // 2 for s in x.shape)
            sl = tuple(slice(i - 5, i + 5) for i in c)
            assert np.array_equal(x[sl], y[sl])  # brain centre untouched
            h = b.header
            for f in ("descrip", "aux_file", "intent_name", "db_name"):
                assert bytes(h[f]).strip(b"\0") == b""


@pytest.mark.docker
def test_quickshear_on_dcm_qa_t1w(tmp_path, schema):
    deface_t1w(tmp_path, schema, "quickshear")


@pytest.mark.docker_slow
@pytest.mark.skipif(not shutil.which("pydeface"), reason="pydeface is only in the engine image")
def test_pydeface_on_dcm_qa_t1w(tmp_path, schema):
    deface_t1w(tmp_path, schema, "pydeface")
