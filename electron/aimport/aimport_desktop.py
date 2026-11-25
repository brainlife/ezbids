"""aimport inside ezBIDS desktop: the engine from aimport/ (unchanged, same tree as the web) with the desktop's tools.

    python aimport_desktop.py serve --input ... --work ... --keys ... --port ...   (same as `python -m aimport serve`)

The Docker image gives the engine /app/handler (ezBIDS preprocess.ts, run with ts-node-dev), GNU `cp -rs`, a `bids-validator-2` wrapper on PATH,
/opt/bids-schema/schema.json, FSL (pydeface) and ROBEX (quickshear). The desktop app has none of these, so this
shim points the engine at what the app bundles instead. Each hook replaces a module attribute that must exist
(a renamed one fails at start, not mid-run). To upstream: turn these into env settings in aimport itself.

- ezBIDS: no hook. aimport's own run_ezbids runs the command in AIMPORT_EZBIDS_ARGV (the desktop's bundled
  preprocess.cjs, built from the same handler/preprocess.ts, run by Electron as node) in AIMPORT_EZBIDS_HANDLER_DIR.
- Staging: the input is copied (APFS clones on macOS, so no extra disk), not symlinked; parts a modality module
  claimed (``exclude``, e.g. microscopy read in place) are left out, as in aimport's own stage_input. Docker mounts the input
  read-only; here nothing does, and a copy means no tool can write through a link into the person's folder.
- Validator: the bundled `bids-validator` (@bids/validator 2.4.1 compiled with Deno) and the bundled schema.json.
- Defacing: adds `allineate`, ezBIDS desktop's registration of a face mask (handler/templates), because FSL and
  ROBEX cannot ship on macOS/Windows. aimport's own checks still apply: the tool output only marks the face
  voxels, the original data is kept byte for byte elsewhere, same shape/affine, at most 60% removed.

Environment (set by electron/main.ts):
  AIMPORT_DESKTOP_RUNTIME    folder with schema.json, bids-validator[.exe] and neuroglancer-client/
  AIMPORT_EZBIDS_ARGV        JSON list: the command that runs preprocess.cjs (staged dir and handler dir are appended)
  AIMPORT_EZBIDS_HANDLER_DIR the ezBIDS handler folder (ezBIDS_core/, templates/)
  AIMPORT_ALLINEATE          the allineate binary
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Literal, Sequence

RUNTIME = Path(os.environ.get("AIMPORT_DESKTOP_RUNTIME") or Path(__file__).resolve().parent)
EXE = ".exe" if os.name == "nt" else ""
SCHEMA = RUNTIME / "schema.json"
VALIDATOR = RUNTIME / f"bids-validator{EXE}"
DEFACE_METHODS = ("pydeface", "quickshear", "allineate")

os.environ.setdefault("AIMPORT_NEUROGLANCER_DIR", str(RUNTIME / "neuroglancer-client"))
os.environ.setdefault("DENO_NO_UPDATE_CHECK", "1")

import aimport.deface as deface_mod  # noqa: E402
import aimport.server as server_mod  # noqa: E402
import aimport.validate as validate_mod  # noqa: E402
from aimport.ezbids_runner import EzbidsError  # noqa: E402
from aimport.modality import ClaimedPaths  # noqa: E402
from aimport.schema import load_schema  # noqa: E402


def _need(module, name: str):
    if not hasattr(module, name):
        raise RuntimeError(f"aimport_desktop: {module.__name__}.{name} is gone; update the shim")
    return getattr(module, name)


# --- staging: a copy of the input, never links into it ---

def stage_input(input_dir: Path, work_dir: Path, exclude: Sequence[str] = ()) -> Path:
    staged = Path(work_dir) / "ezbids"
    staged.mkdir(parents=True, exist_ok=True)
    src = Path(input_dir).resolve()
    if exclude:
        # a modality module (e.g. microscopy) claimed part of the input and reads it in place: copy the rest,
        # never descending into a claimed root and skipping links that resolve into one (as aimport's own
        # stage_input does with symlinks)
        claimed = ClaimedPaths(src, exclude)
        try:
            for dirpath, dirs, files in os.walk(src, followlinks=False):
                here = Path(dirpath)
                out = staged / here.relative_to(src)
                out.mkdir(exist_ok=True)
                links = [d for d in dirs if (here / d).is_symlink()]
                dirs[:] = sorted(d for d in dirs if d not in links and not claimed.covers(here / d))
                for name in sorted(files + links):
                    path = here / name
                    if claimed.reaches(path) if name in links else claimed.covers(path):
                        continue
                    if path.is_dir():
                        shutil.copytree(path, out / name, dirs_exist_ok=True)
                    else:
                        shutil.copy2(path, out / name)
        except (OSError, shutil.Error) as e:
            raise EzbidsError(f"could not stage the input: {e}") from None
        return staged
    if sys.platform == "darwin":
        # clonefile(2): instant, no extra disk, and writes to the clone never reach the original
        proc = subprocess.run(["cp", "-cR", f"{src}/.", str(staged)], capture_output=True, text=True)
        if proc.returncode == 0:
            return staged
        shutil.rmtree(staged, ignore_errors=True)
        staged.mkdir(parents=True)
    try:
        shutil.copytree(src, staged, dirs_exist_ok=True)
    except (OSError, shutil.Error) as e:
        raise EzbidsError(f"could not stage the input: {e}") from None
    return staged


# --- validator and schema ---

_orig_validate_run = _need(validate_mod, "_run")


def _validate_run(cmd: list[str]) -> subprocess.CompletedProcess:
    # file:// + a Windows path is not a URL; give the validator a real file URI
    fixed = [Path(a[len("file://"):]).as_uri() if a.startswith("file://") else a for a in cmd]
    return _orig_validate_run(fixed)


# --- defacing: allineate ---

_orig_tool = _need(deface_mod, "_tool")


def _tool(method: str, src: Path, out: Path, workdir: Path, entry_id: str) -> None:
    if method != "allineate":
        return _orig_tool(method, src, out, workdir, entry_id)
    templates = Path(os.environ["AIMPORT_EZBIDS_HANDLER_DIR"]) / "templates"
    deface_mod._run([os.environ["AIMPORT_ALLINEATE"], str(templates / "mean_reg2mean.nii.gz"), str(src),
                     "-cost", "ls", "-skullstrip", str(templates / "facemask.nii.gz"), str(out)], entry_id)


def install() -> None:
    for module, name in ((server_mod, "stage_input"), (server_mod, "load_schema"),
                         (validate_mod, "VALIDATOR"), (validate_mod, "SCHEMA_PATH"), (deface_mod, "METHODS")):
        _need(module, name)
    server_mod.stage_input = stage_input
    server_mod.load_schema = lambda path=SCHEMA: load_schema(path)
    validate_mod.VALIDATOR = str(VALIDATOR)
    validate_mod.SCHEMA_PATH = SCHEMA
    validate_mod._run = _validate_run
    deface_mod.METHODS = DEFACE_METHODS
    deface_mod._tool = _tool
    body = _need(server_mod, "ApproveBody")
    body.model_fields["deface_method"].annotation = Literal[DEFACE_METHODS] | None  # type: ignore[valid-type]
    body.model_rebuild(force=True)


if __name__ == "__main__":
    install()
    from aimport.__main__ import main

    raise SystemExit(main())
