"""Find microscopy inputs under an input folder without reading pixels or walking into stores."""
from __future__ import annotations

import gzip
import os
import re
from dataclasses import dataclass
from pathlib import Path

from ..modality import Claim

FAMILIES = ("ome-zarr", "ome-tiff", "tiff", "svs", "czi", "nd2", "lif", "nifti", "mat", "raw-psoct",
            "unsupported", "visor-meta")
UNSUPPORTED_EXT = (".vsi", ".oib", ".oif", ".ims", ".lsm", ".scn", ".mrxs")
VISOR_META = frozenset({"acqinfo_metadata.json", "dbpost.json", "hh.log"})
HINTS = frozenset({"ps-oct", "psoct", "oct", "enface", "reflectivity", "retardance", "orientation",
                   "opticaxis", "cross", "micr"})
ZARR_MARKERS = ("zarr.json", ".zgroup", ".zattrs")
_TOKEN = re.compile(r"[^a-z0-9]+")


@dataclass
class Found:
    rel: str
    family: str
    group: str


def _hint_tokens(rel: str) -> set[str]:
    low = rel.lower()
    toks = {t for p in low.split("/") for t in _TOKEN.split(p) if t}
    toks |= {p for p in low.split("/")}
    return toks


def has_hint(rel: str) -> bool:
    return bool(_hint_tokens(rel) & HINTS) or "micr" in rel.lower().split("/")


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


def claim(input_dir: Path, remote: list[str] | None = None) -> tuple[Claim, list[Found]]:
    """Claim microscopy inputs under input_dir. ``remote`` is passed through unprobed (Task 5)."""
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
                zarr_name = e.name.lower().endswith(".zarr")
                if zarr_name or rel_dir.lower().endswith(".zarr") and re.fullmatch(r"Pos\d+", e.name):
                    add_root_dir(Path(e.path), rel, e.name)
                else:
                    walk(Path(e.path), rel)
            elif e.is_file(follow_symlinks=False):
                fam = _family(e.name, Path(e.path), rel)
                if fam:
                    add_root(rel, fam, rel_dir or "." if fam == "tiff" else None)

    def add_root_dir(path: Path, rel: str, name: str) -> None:
        try:
            with os.scandir(path) as it:
                children = sorted(it, key=lambda e: e.name)
        except OSError:
            return
        if any(c.name in ZARR_MARKERS for c in children):
            add_root(rel, "ome-zarr")
            return
        pos = [c for c in children if c.is_dir(follow_symlinks=False) and re.fullmatch(r"Pos\d+", c.name)]
        if pos:  # exaSPIM.zarr/Pos*: each position is its own store
            for c in pos:
                add_root(f"{rel}/{c.name}", "ome-zarr")
        else:
            add_root(rel, "ome-zarr")

    walk(input_dir, "")
    return Claim(roots=roots, remote=list(remote or [])), found
