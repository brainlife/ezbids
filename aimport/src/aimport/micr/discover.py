"""Find microscopy inputs under an input folder without reading pixels or walking into stores."""
from __future__ import annotations

import gzip
import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path

from ..modality import Claim

log = logging.getLogger(__name__)

FAMILIES = ("ome-zarr", "ome-tiff", "tiff", "svs", "czi", "nd2", "lif", "nifti", "mat", "raw-psoct",
            "unsupported", "visor-meta")
UNSUPPORTED_EXT = (".vsi", ".oib", ".oif", ".ims", ".lsm", ".scn", ".mrxs")
VISOR_META = frozenset({"acqinfo_metadata.json", "dbpost.json", "hh.log"})
HINTS = frozenset({"ps-oct", "psoct", "oct", "enface", "reflectivity", "retardance", "orientation",
                   "opticaxis", "cross", "micr"})
BARE_HINTS = frozenset({"oct", "cross"})
ZARR_MARKERS = ("zarr.json", ".zgroup", ".zattrs")
_TOKEN = re.compile(r"[^a-z0-9]+")


@dataclass
class Found:
    rel: str
    family: str
    group: str


def _tokens(text: str) -> set[str]:
    low = text.lower()
    toks = {t for t in _TOKEN.split(low) if t}
    if low not in BARE_HINTS:  # Oct_2024, cross_sectional: bare oct/cross count only as a whole segment
        toks -= BARE_HINTS
    return toks | {low}


def has_hint(rel: str) -> bool:
    """A hint token in the file name or one of its two nearest folders, or a BIDS micr/ folder."""
    parts = rel.split("/")
    if "micr" in (p.lower() for p in parts[:-1]):
        return True
    near = set()
    for p in parts[-3:]:
        near |= _tokens(p)
    return bool(near & HINTS)


def _nifti_microns(path: Path) -> bool:
    """xyzt_units (header byte 123) has spatial code 3 (micrometer)."""
    try:
        opener = gzip.open if path.name.lower().endswith(".gz") else open
        with opener(path, "rb") as fh:
            head = fh.read(348)
    except (OSError, EOFError):
        return False
    return len(head) >= 124 and (head[123] & 7) == 3


def _is_dicom(path: Path) -> bool:
    try:
        with open(path, "rb") as fh:
            fh.seek(128)
            return fh.read(4) == b"DICM"
    except OSError:
        return False


def _family(name: str, path: Path, rel: str) -> str | None:
    low = name.lower()
    if name in VISOR_META:
        return "visor-meta"
    if low.endswith((".ome.tif", ".ome.tiff", ".ome.btf")):
        return "ome-tiff"
    if low.endswith((".tif", ".tiff")):
        return None if _is_dicom(path) else "tiff"
    if low.endswith(".svs"):
        return "svs"
    for ext in (".czi", ".nd2", ".lif"):
        if low.endswith(ext):
            return ext[1:]
    if low.endswith(UNSUPPORTED_EXT):
        return "unsupported"
    if low.endswith(".mat"):
        return "mat"
    if low.endswith((".nii", ".nii.gz")):
        return "nifti" if has_hint(rel) or _nifti_microns(path) else None
    if low.endswith(".dat"):
        return "raw-psoct" if has_hint(rel) else None
    return None


def claim_remote(urls: list[str] | None) -> tuple[list[str], list[Found]]:
    """Probe each remote URL (``remote.probe``); keep the ones that are OME-Zarr, NIfTI or TIFF.

    Returns the normalised URLs and their ``Found`` entries (``rel`` and ``group`` are the URL;
    local-only, like every other claim record). A refused or unreadable URL is skipped with a
    warning that does not name it.
    """
    from . import remote as _remote

    kept: list[str] = []
    found: list[Found] = []
    for i, url in enumerate(urls or []):
        try:
            norm = _remote.normalize_url(url)
            family = _remote.probe(norm)
        except Exception as exc:  # noqa: BLE001 - one bad source must not stop the scan
            log.warning("remote source %d skipped: %s", i + 1, type(exc).__name__)
            continue
        if family not in _remote.ALLOWED_FAMILIES:
            log.warning("remote source %d skipped: not OME-Zarr, NIfTI or TIFF", i + 1)
            continue
        if norm not in kept:
            kept.append(norm)
            found.append(Found(norm, family, norm))
    return kept, found


def claim(input_dir: Path, remote: list[str] | None = None) -> tuple[Claim, list[Found]]:
    """Claim microscopy inputs under input_dir, and the remote URLs that probe as microscopy."""
    input_dir = Path(input_dir)
    found: list[Found] = []
    roots: list[str] = []

    def add_root(rel: str, family: str, group: str | None = None) -> None:
        roots.append(rel)
        if family != "visor-meta":
            found.append(Found(rel, family, group or rel))

    def walk(directory: Path, rel_dir: str) -> None:
        try:
            with os.scandir(directory) as it:
                entries = sorted(it, key=lambda e: e.name)
        except OSError:
            return
        for e in entries:
            if e.is_symlink():
                continue
            rel = f"{rel_dir}/{e.name}" if rel_dir else e.name
            if e.is_dir(follow_symlinks=False):
                if any(os.path.exists(os.path.join(e.path, m)) for m in ZARR_MARKERS):
                    add_root(rel, "ome-zarr")  # a store: never walked inside
                elif rel_dir.lower().endswith(".zarr") and re.fullmatch(r"Pos\d+", e.name):
                    add_root(rel, "ome-zarr")  # exaSPIM.zarr/Pos*
                else:
                    walk(Path(e.path), rel)
            elif e.is_file(follow_symlinks=False):
                fam = _family(e.name, Path(e.path), rel)
                if fam:
                    add_root(rel, fam, (rel_dir or ".") if fam == "tiff" else None)

    walk(input_dir, "")
    urls, remote_found = claim_remote(remote)
    return Claim(roots=roots, remote=urls), found + remote_found
