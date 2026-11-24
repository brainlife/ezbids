"""Defacing of the written BIDS images (pydeface or quickshear), following handler/deface.sh.

Only the files listed in the writer's manifest for entries with deface=True are touched. The
originals are moved to pre_deface_dir (outside bids_dir, same relative paths) and the defaced
image replaces each one in place under the same name. Every tool run happens first, into a
temporary folder next to pre_deface_dir, so bids_dir is not touched until all images are done;
if the swap itself fails, everything moved is put back. bids_dir is never left with a missing or
half-defaced image.

Lossless: the tool's output only decides which voxels are the face; those are zeroed in the original's
stored data and every other voxel stays byte-identical.

Unlike ezBIDS, no fslreorient2std is applied: the converted orientation and data are kept.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Literal

import nibabel as nib
import numpy as np

from .plan import Plan
from .writer import NIFTI_EXTS, write_clean_nifti

TIMEOUT_S = 600
METHODS = ("pydeface", "quickshear")
ZERO_EPS = 1e-6
MAX_FACE_FRACTION = 0.6  # of the original's non-zero voxels; real runs remove 21-35%
ROBEX = "/ROBEX/runROBEX.sh"
STDERR_TAIL = 1000


class DefaceError(RuntimeError):
    def __init__(self, entry_id: str, message: str):
        super().__init__(f"defacing failed for {entry_id}: {message}")
        self.entry_id = entry_id


def _device(path: Path) -> int:
    return os.stat(path).st_dev


def _run(argv: list[str], entry_id: str) -> None:
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=TIMEOUT_S, check=False)
    except subprocess.TimeoutExpired:
        raise DefaceError(entry_id, f"{argv[0]} timed out after {TIMEOUT_S} s") from None
    except OSError as e:
        raise DefaceError(entry_id, f"cannot run {argv[0]}: {e}") from None
    if proc.returncode != 0:
        tail = (proc.stderr or "")[-STDERR_TAIL:].strip()
        raise DefaceError(entry_id, f"{argv[0]} exited with {proc.returncode}: {tail}")


def _tool(method: str, src: Path, out: Path, workdir: Path, entry_id: str) -> None:
    if method == "pydeface":
        _run(["pydeface", "--force", str(src), "--outfile", str(out)], entry_id)
        return
    mask = workdir / "mask.nii.gz"
    _run([ROBEX, str(src), str(mask)], entry_id)
    _run(["quickshear", str(src), str(mask), str(out)], entry_id)


def _defaced_copy(src: Path, tmp: Path, method: str, entry_id: str, n: int) -> Path:
    """Run the tool on src; returns a copy of src in tmp with only the voxels the tool removed zeroed."""
    ext = next(e for e in NIFTI_EXTS if src.name.endswith(e))
    workdir = tmp / str(n)
    workdir.mkdir()
    raw, final = workdir / f"defaced{ext}", workdir / f"final{ext}"
    _tool(method, src, raw, workdir, entry_id)
    if not raw.is_file():
        raise DefaceError(entry_id, "the tool wrote no output")
    try:
        a, b = nib.load(str(src)), nib.load(str(raw))
        if a.shape != b.shape or not np.array_equal(a.affine, b.affine):
            raise DefaceError(entry_id, "the defaced image differs in shape or affine from the original")
        scaled_in, scaled_out = np.asanyarray(a.dataobj), np.asanyarray(b.dataobj)
        face = (np.abs(scaled_out) < ZERO_EPS) & (scaled_in != 0)
        nonzero, removed = int(np.count_nonzero(scaled_in)), int(np.count_nonzero(face))
        if removed == 0:
            raise DefaceError(entry_id, "the tool removed no voxels (output equals the original)")
        if removed > MAX_FACE_FRACTION * nonzero:
            raise DefaceError(entry_id, f"the tool removed {removed / nonzero:.0%} of the non-zero voxels "
                                        f"(more than {MAX_FACE_FRACTION:.0%}); the output is not a defaced head")
        # the tool's own output is only used to find the face voxels; the original's stored data is
        # kept byte for byte everywhere else, so no tool re-quantisation reaches the dataset
        write_clean_nifti(src, final, zero_mask=face)
    except DefaceError:
        raise
    except Exception as e:  # unreadable output, NIfTI-2, ...
        raise DefaceError(entry_id, f"the defaced image is unusable: {e}") from None
    return final


def deface(bids_dir: Path, plan: Plan, method: Literal["pydeface", "quickshear"], pre_deface_dir: Path,
           manifest: dict[str, list[str]]) -> dict[str, list[Path]]:
    """Deface the images of every plan entry with deface=True; returns {entry_id: [original copies]}.

    manifest is the one write_bids filled (entry id -> NIfTI paths relative to bids_dir); an entry
    with deface=True that was not written (excluded) is skipped. The returned list for an entry
    holds, in manifest order, the paths under pre_deface_dir the originals were moved to, for
    before/after previews. Raises ValueError for an unknown method or a pre_deface_dir inside
    bids_dir (or on another filesystem than it: the swap relies on same-filesystem renames),
    DefaceError(entry_id) when a tool fails, times out (600 s), gives a bad image, or removes no
    voxels or more than 60% of the non-zero ones; in every failure bids_dir is left exactly as it
    was (RuntimeError, chained, if a restore step itself fails, listing what was not restored).
    """
    if method not in METHODS:
        raise ValueError(f"unknown defacing method: {method}")
    bids, pre = Path(bids_dir).resolve(), Path(pre_deface_dir).resolve()
    if pre == bids or bids in pre.parents:
        raise ValueError(f"pre_deface_dir must be outside the BIDS folder: {pre_deface_dir}")
    jobs = [(e.id, rel) for e in plan.entries if e.deface for rel in manifest.get(e.id, [])]
    for eid, rel in jobs:
        path = (bids / rel).resolve()
        if bids not in path.parents or not path.is_file():
            raise DefaceError(eid, f"no such image in the BIDS folder: {rel}")
        if (pre / rel).exists():
            raise FileExistsError(f"already in pre_deface_dir: {pre / rel}")
    result: dict[str, list[Path]] = {}
    if not jobs:
        return result
    pre.parent.mkdir(parents=True, exist_ok=True)
    if _device(pre.parent) != _device(bids):
        raise ValueError("pre_deface_dir must be on the same filesystem as the BIDS folder")
    tmp = Path(tempfile.mkdtemp(prefix=".deface-tmp-", dir=pre.parent))
    moved: list[tuple[Path, Path, bool]] = []  # (original in bids, copy in pre, defaced image placed)
    try:
        finals = [_defaced_copy(bids / rel, tmp, method, eid, n) for n, (eid, rel) in enumerate(jobs)]
        for (eid, rel), final in zip(jobs, finals):
            target, saved = bids / rel, pre / rel
            saved.parent.mkdir(parents=True, exist_ok=True)
            moved.append((target, saved, False))  # recorded first: an interrupt must not lose the original
            shutil.move(str(target), str(saved))
            shutil.move(str(final), str(target))
            moved[-1] = (target, saved, True)
            result.setdefault(eid, []).append(saved)
    except BaseException as exc:
        failed = []
        for target, saved, placed in reversed(moved):
            try:
                if placed:
                    target.unlink(missing_ok=True)
                if saved.exists():
                    shutil.move(str(saved), str(target))
            except Exception as e:  # keep restoring the others
                failed.append(f"{target} ({e})")
        if failed:
            raise RuntimeError("defacing failed and these originals were not restored, "
                               f"find them under {pre}: " + "; ".join(failed)) from exc
        raise
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return result
