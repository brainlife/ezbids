import hashlib
import os
import shutil
import sys
import time
from pathlib import Path

import pydicom
import pytest

FIXTURES = Path(__file__).parent / "fixtures"
sys.path.insert(0, str(FIXTURES))
from fetch_dcm_qa import (  # noqa: E402
    NATIVE_IDENTIFIERS,
    NON_DICOM_SUFFIXES,
    PLANTED,
    SUBJECT_DIR,
    _read_dicom,
    fetch_dcm_qa,
)

from aimport.ezbids_runner import EzbidsError, parse_core, run_ezbids, stage_input  # noqa: E402


def first_dicom(src: Path) -> Path:
    """First file under src that pydicom can read, skipping known non-DICOM files."""
    for path in sorted(src.rglob("*")):
        if not path.is_file() or path.suffix.lower() in NON_DICOM_SUFFIXES:
            continue
        try:
            if _read_dicom(path) is not None:
                return path
        except pydicom.errors.InvalidDicomError:  # junk such as .DS_Store
            continue
    raise AssertionError(f"no DICOM under {src}")


def test_parse_core_series_and_objects():
    r = parse_core(FIXTURES / "ezbids_core_siemens.json")
    assert r.series and r.objects and r.subjects
    assert all(o.series_idx in {s.series_idx for s in r.series} for o in r.objects)
    assert any(s.type == "anat/T1w" for s in r.series)


def snapshot(root: Path) -> dict:
    """relative path -> (kind, size, mtime_ns, sha256) for every entry under root."""
    snap = {}
    for p in sorted(root.rglob("*")):
        st = p.lstat()
        digest = hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() and not p.is_symlink() else ""
        snap[p.relative_to(root).as_posix()] = (p.is_dir(), st.st_size, st.st_mtime_ns, digest)
    return snap


def set_read_only(root: Path, read_only: bool) -> None:
    for p in [root, *root.rglob("*")]:
        if p.is_symlink():
            continue
        mode = p.stat().st_mode
        p.chmod(mode & ~0o222 if read_only else mode | 0o200)


def test_fixture_has_no_identifiers():
    text = (FIXTURES / "ezbids_core_siemens.json").read_text().lower()
    terms = set(NATIVE_IDENTIFIERS) | set(PLANTED.values()) | {SUBJECT_DIR, "smith", "mrn"}
    assert [t for t in terms if t.lower() in text] == []


def _fake_handler(tmp_path: Path, script: str) -> Path:
    handler = tmp_path / "handler"
    handler.mkdir()
    (handler / "preprocess.sh").write_text(script)
    return handler


def test_run_failure_carries_tail(tmp_path):
    handler = _fake_handler(tmp_path, "echo one\necho boom >&2\nexit 3\n")
    with pytest.raises(EzbidsError) as e:
        run_ezbids(tmp_path, handler_dir=handler, log=lambda line: None)
    assert "one" in str(e.value) and "boom" in str(e.value)


def test_run_timeout_kills_process_group(tmp_path):
    marker = tmp_path / "child.pid"
    handler = _fake_handler(tmp_path, f"echo started\nsleep 30 &\necho $! > {marker}\nwait\n")
    t0 = time.time()
    with pytest.raises(EzbidsError, match="timed out after"):
        run_ezbids(tmp_path, handler_dir=handler, log=lambda line: None, timeout_s=1)
    assert time.time() - t0 < 10
    pid = int(marker.read_text())
    time.sleep(0.2)
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)  # the sleep child died with its group


def test_stage_input_error_is_ezbids_error(tmp_path):
    with pytest.raises(EzbidsError, match="could not stage"):
        stage_input(tmp_path / "missing", tmp_path / "work")


@pytest.mark.docker
def test_run_on_planted_dicoms_with_junk(tmp_path):
    src = fetch_dcm_qa(tmp_path / "in")
    (src / "notes.pdf").write_bytes(b"%PDF-1.4")
    (src / ".DS_Store").write_bytes(b"\0")
    shutil.make_archive(str(src / "extra"), "zip", first_dicom(src).parent)
    before = snapshot(src)
    set_read_only(src, True)  # a write into the input fails (not for root, so the snapshot below also checks)
    try:
        core = run_ezbids(stage_input(src, tmp_path / "work"))
        after = snapshot(src)
    finally:
        set_read_only(src, False)
    assert parse_core(core).series
    assert after == before  # input untouched: same files, sizes, mtimes and hashes


@pytest.mark.docker_offline
def test_run_offline(tmp_path):
    core = run_ezbids(stage_input(fetch_dcm_qa(tmp_path / "in"), tmp_path / "work"))
    assert core.exists()
    assert parse_core(core).series
