import hashlib
import json
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

from aimport import ezbids_runner  # noqa: E402
from aimport.ezbids_runner import EzbidsError, ezbids_command, parse_core, run_ezbids, stage_input  # noqa: E402


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


def _fake_handler(tmp_path: Path, script: str, monkeypatch) -> Path:
    """A handler folder whose preprocess is a shell script, run through AIMPORT_EZBIDS_ARGV (the command
    override the desktop app uses) so the runner's tail, timeout and kill paths are tested without node."""
    handler = tmp_path / "handler"
    handler.mkdir()
    (handler / "fake-preprocess.sh").write_text(script)
    monkeypatch.setenv("AIMPORT_EZBIDS_ARGV", json.dumps(["bash", str(handler / "fake-preprocess.sh")]))
    return handler


def test_run_failure_carries_tail(tmp_path, monkeypatch):
    handler = _fake_handler(tmp_path, "echo one\necho boom >&2\nexit 3\n", monkeypatch)
    with pytest.raises(EzbidsError) as e:
        run_ezbids(tmp_path, handler_dir=handler, log=lambda line: None)
    assert "one" in str(e.value) and "boom" in str(e.value)


def test_run_gets_staged_and_handler_dirs_in_handler_cwd(tmp_path, monkeypatch):
    handler = _fake_handler(tmp_path, 'echo "$1|$2|$PWD"\necho "{}" > "$1/ezBIDS_core.json"\n', monkeypatch)
    staged = tmp_path / "staged"
    staged.mkdir()
    lines = []
    assert run_ezbids(staged, handler_dir=handler, log=lines.append) == staged.resolve() / "ezBIDS_core.json"
    assert lines == [f"{staged.resolve()}|{handler}|{handler.resolve()}"]


def test_run_without_core_json_fails(tmp_path, monkeypatch):
    handler = _fake_handler(tmp_path, "echo done\n", monkeypatch)
    with pytest.raises(EzbidsError, match="without ezBIDS_core.json"):
        run_ezbids(tmp_path, handler_dir=handler, log=lambda line: None)


def test_command_is_the_handlers_preprocess_ts(tmp_path, monkeypatch):
    """The image runs the web handler's own preprocess.ts, as docker-compose runs the handler: node with
    ../node_modules/ts-node-dev, --transpile-only, the handler's tsconfig.json."""
    monkeypatch.delenv("AIMPORT_EZBIDS_ARGV", raising=False)
    monkeypatch.delenv("EZBIDS_PREPROCESS_PATH", raising=False)
    monkeypatch.setattr(ezbids_runner.shutil, "which", lambda name: "/usr/bin/node" if name == "node" else None)
    handler = tmp_path / "app" / "handler"
    handler.mkdir(parents=True)
    with pytest.raises(EzbidsError, match="preprocess not found"):
        ezbids_command(handler)  # no fallback: never an older preprocess.sh
    (handler / "preprocess.sh").write_text("exit 0\n")
    with pytest.raises(EzbidsError, match="preprocess not found"):
        ezbids_command(handler)
    (handler / "preprocess.ts").write_text("")
    with pytest.raises(EzbidsError, match="ts-node-dev not found"):
        ezbids_command(handler)
    bin_js = tmp_path / "app" / "node_modules" / "ts-node-dev" / "lib" / "bin.js"
    bin_js.parent.mkdir(parents=True)
    bin_js.write_text("")
    assert ezbids_command(handler) == ["/usr/bin/node", str(bin_js), "--transpile-only", "-P",
                                       str(handler / "tsconfig.json"), str(handler / "preprocess.ts")]
    (handler / "preprocess.js").write_text("")  # built, as handler/utils.ts resolveHandlerScript prefers
    assert ezbids_command(handler) == ["/usr/bin/node", str(handler / "preprocess.js")]
    monkeypatch.setattr(ezbids_runner.shutil, "which", lambda name: None)
    with pytest.raises(EzbidsError, match="node not found"):
        ezbids_command(handler)


def test_command_override_and_handler_dir_from_env(tmp_path, monkeypatch):
    """The desktop app: AIMPORT_EZBIDS_ARGV (Electron as node on preprocess.cjs) and AIMPORT_EZBIDS_HANDLER_DIR."""
    monkeypatch.setenv("AIMPORT_EZBIDS_ARGV", json.dumps(["/app/ezbids", "/h/preprocess.cjs"]))
    assert ezbids_command(tmp_path) == ["/app/ezbids", "/h/preprocess.cjs"]
    monkeypatch.setenv("AIMPORT_EZBIDS_ARGV", json.dumps("not a list"))
    with pytest.raises(EzbidsError, match="JSON list"):
        ezbids_command(tmp_path)
    monkeypatch.setenv("AIMPORT_EZBIDS_HANDLER_DIR", str(tmp_path))
    assert ezbids_runner.handler_dir_default() == tmp_path
    monkeypatch.delenv("AIMPORT_EZBIDS_HANDLER_DIR")
    assert ezbids_runner.handler_dir_default() == Path("/app/handler")


def test_run_timeout_kills_process_group(tmp_path, monkeypatch):
    marker = tmp_path / "child.pid"
    handler = _fake_handler(tmp_path, f"echo started\nsleep 30 &\necho $! > {marker}\nwait\n", monkeypatch)
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
