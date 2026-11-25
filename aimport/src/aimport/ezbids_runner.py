"""Run ezBIDS's preprocessing pipeline as a subprocess and parse its first guess."""
from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Sequence

from .modality import ClaimedPaths

DEFAULT_HANDLER_DIR = Path("/app/handler")
# ts-node-dev, as the web handler runs it (docker-compose: node ../node_modules/ts-node-dev/lib/bin.js), relative to
# the handler folder
TS_NODE_DEV = Path("..") / "node_modules" / "ts-node-dev" / "lib" / "bin.js"


class EzbidsError(RuntimeError):
    """ezBIDS preprocess failed; the message is the tail of its output."""


def handler_dir_default() -> Path:
    """The ezBIDS handler folder: $AIMPORT_EZBIDS_HANDLER_DIR (the desktop app), else /app/handler (the image)."""
    return Path(os.environ.get("AIMPORT_EZBIDS_HANDLER_DIR") or DEFAULT_HANDLER_DIR)


def ezbids_command(handler_dir: Path) -> list[str]:
    """The command that runs ezBIDS's preprocess, the one the web handler and the desktop app run
    (handler/preprocess.ts; the staged folder and the handler folder are appended by run_ezbids).

    $AIMPORT_EZBIDS_ARGV (a JSON list; the desktop app: Electron as node on its bundled preprocess.cjs) wins.
    Otherwise as handler/utils.ts resolveHandlerScript and nodeArgsForScript do: $EZBIDS_PREPROCESS_PATH, else
    <handler>/preprocess.js when built, else <handler>/preprocess.ts through ts-node-dev (--transpile-only, the
    handler's tsconfig.json), with node. There is no other fallback: a missing script, node or ts-node-dev is an
    EzbidsError saying which.
    """
    argv = os.environ.get("AIMPORT_EZBIDS_ARGV")
    if argv:
        cmd = json.loads(argv)
        if not (isinstance(cmd, list) and cmd and all(isinstance(a, str) for a in cmd)):
            raise EzbidsError("AIMPORT_EZBIDS_ARGV must be a JSON list of strings")
        return cmd
    handler = Path(handler_dir)
    js = handler / "preprocess.js"
    script = Path(os.environ.get("EZBIDS_PREPROCESS_PATH") or (js if js.exists() else handler / "preprocess.ts"))
    if not script.is_file():
        raise EzbidsError(f"ezBIDS preprocess not found: {script} (the ezBIDS handler's preprocess.ts)")
    node = shutil.which("node")
    if node is None:
        raise EzbidsError("node not found on PATH: it runs ezBIDS preprocess")
    if script.suffix != ".ts":
        return [node, str(script)]
    ts_node_dev = (handler / TS_NODE_DEV).resolve()
    if not ts_node_dev.is_file():
        raise EzbidsError(f"ts-node-dev not found: {ts_node_dev} (install the ezBIDS root node_modules)")
    return [node, str(ts_node_dev), "--transpile-only", "-P", str(handler / "tsconfig.json"), str(script)]


def stage_input(input_dir: Path, work_dir: Path, exclude: Sequence[str] = ()) -> Path:
    """Symlink-tree input_dir into work_dir/ezbids so dcm2niix never writes to the input.

    Like ``cp -rs``: folders are created, every other entry (files and symlinks, a symlinked folder
    included) becomes an absolute symlink to its input path. The walk never follows links and never
    descends into a claimed root (``exclude``: input-relative POSIX paths); nothing under a claimed
    root, and no link that resolves into one, is staged.
    """
    src = Path(input_dir).resolve()
    if not src.is_dir():
        raise EzbidsError(f"could not stage {input_dir}: not a folder")
    staged = Path(work_dir) / "ezbids"
    staged.mkdir(parents=True, exist_ok=True)
    claimed = ClaimedPaths(src, exclude)
    try:
        for dirpath, dirs, files in os.walk(src, followlinks=False, onerror=_raise):
            here = Path(dirpath)
            out = staged / here.relative_to(src)
            out.mkdir(exist_ok=True)
            links = [d for d in dirs if (here / d).is_symlink()]
            dirs[:] = sorted(d for d in dirs if d not in links and not claimed.covers(here / d))
            for name in sorted(files + links):
                path = here / name
                if claimed.reaches(path) if name in links else claimed.covers(path):
                    continue
                target = out / name
                if target.is_symlink() or target.exists():
                    target.unlink()
                os.symlink(path, target)
    except OSError as e:
        raise EzbidsError(f"could not stage {input_dir}: {e}") from None
    return staged


def _raise(e: OSError) -> None:
    raise e


def has_files(staged: Path) -> bool:
    """True when the staged tree holds anything but folders (what ezBIDS could read)."""
    for _dirpath, dirs, files in os.walk(staged, followlinks=False):
        if files or any((Path(_dirpath) / d).is_symlink() for d in dirs):
            return True
    return False


def _kill_group(proc: subprocess.Popen) -> None:
    if os.name == "nt":
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True)
        return
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def run_ezbids(
    staged: Path,
    handler_dir: Path | None = None,
    log: Callable[[str], None] = print,
    timeout_s: float = 3600,
) -> Path:
    """Run ezBIDS's preprocess (``ezbids_command``) on staged and return the path of ezBIDS_core.json.

    handler_dir: default ``handler_dir_default()``. The whole process group (Windows: process tree) is
    killed on timeout or on any exception.
    """
    staged = Path(staged).resolve()
    handler = Path(handler_dir) if handler_dir is not None else handler_dir_default()
    argv = [*ezbids_command(handler), str(staged), str(handler)]
    try:
        proc = subprocess.Popen(
            argv,
            cwd=str(handler),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            errors="replace",
            start_new_session=os.name != "nt",
            creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
        )
    except OSError as e:
        raise EzbidsError(f"could not start ezBIDS preprocess: {e}") from None
    if proc.stdout is None:
        _kill_group(proc)
        raise EzbidsError("could not capture ezBIDS preprocess output")
    tail: list[str] = []
    timed_out = threading.Event()

    def on_timeout() -> None:
        timed_out.set()
        _kill_group(proc)

    timer = threading.Timer(timeout_s, on_timeout)
    timer.start()
    try:
        for line in proc.stdout:
            line = line.rstrip("\n")
            log(line)
            tail.append(line)
            del tail[:-40]
        returncode = proc.wait()
    finally:
        timer.cancel()
        _kill_group(proc)  # also reaps stragglers left by a failed or interrupted run
        proc.stdout.close()
    if timed_out.is_set():
        raise EzbidsError(f"timed out after {timeout_s}s\n" + "\n".join(tail))
    if returncode != 0:
        raise EzbidsError("\n".join(tail))
    core = staged / "ezBIDS_core.json"
    if not core.exists():
        raise EzbidsError("preprocess finished without ezBIDS_core.json\n" + "\n".join(tail))
    return core


@dataclass
class CoreSeries:
    series_idx: int
    type: str
    entities: dict[str, str]
    message: str
    series_description: str
    sidecar: dict
    nifti_path: Path


@dataclass
class CoreObject:
    series_idx: int
    subject_idx: int
    session_idx: int
    acquisition_date: str
    acquisition_time: str
    entities: dict
    paths: list[Path]
    sidecar: dict


@dataclass
class CoreSubject:
    subject_idx: int
    label: str
    patient_info: list[dict]
    sessions: list[dict]


@dataclass
class CoreResult:
    series: list[CoreSeries] = field(default_factory=list)
    objects: list[CoreObject] = field(default_factory=list)
    subjects: list[CoreSubject] = field(default_factory=list)


def _object_sidecar(items: list[dict]) -> dict:
    merged: dict = {}
    for item in items:
        if isinstance(item.get("sidecar"), dict):
            merged.update(item["sidecar"])
    return merged


def parse_core(path: Path) -> CoreResult:
    """Parse ezBIDS_core.json into dataclasses. Paths stay as written (relative to the staged root)."""
    raw = json.loads(Path(path).read_text())
    objects = [
        CoreObject(
            series_idx=o["series_idx"],
            subject_idx=o["subject_idx"],
            session_idx=o["session_idx"],
            acquisition_date=o.get("AcquisitionDate", ""),
            acquisition_time=o.get("AcquisitionTime", ""),
            entities={k: v for k, v in (o.get("entities") or {}).items() if v},
            paths=[Path(i["path"]) for i in o.get("items", []) if "path" in i],
            sidecar=_object_sidecar(o.get("items", [])),
        )
        for o in raw.get("objects", [])
    ]
    sidecar_by_series: dict[int, dict] = {}
    for o in objects:
        if o.sidecar:
            sidecar_by_series.setdefault(o.series_idx, o.sidecar)
    series = [
        CoreSeries(
            series_idx=s["series_idx"],
            type=s.get("type", ""),
            entities={k: v for k, v in (s.get("entities") or {}).items() if v},
            message=s.get("message", ""),
            series_description=s.get("SeriesDescription", ""),
            sidecar=sidecar_by_series.get(s["series_idx"], {}),
            nifti_path=Path(s["nifti_path"]),
        )
        for s in raw.get("series", [])
    ]
    subjects = [
        CoreSubject(
            subject_idx=i,
            label=s.get("subject", ""),
            patient_info=s.get("PatientInfo", []),
            sessions=s.get("sessions", []),
        )
        for i, s in enumerate(raw.get("subjects", []))
    ]
    return CoreResult(series=series, objects=objects, subjects=subjects)
