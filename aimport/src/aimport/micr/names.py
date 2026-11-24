"""Facts parsed from microscopy input paths: donor, dates, slice, tile, position, channel, contrast.

Paths are identifying, so these facts are the only thing that may travel on from them: numbers,
known vocabulary and (through the pseudonym key) the donor code. Never copy path text into a label.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Iterable, Literal

from ..planner import _is_date_like
from ..scrub import _date_forms

Contrast = Literal["reflectivity", "retardance", "opticaxis", "cross"]

VOCAB: tuple[str, ...] = (
    "slice", "tile", "pos", "visor", "spim", "exaspim", "ps", "oct", "psoct", "enface", "registration",
    "reflectivity", "retardance", "orientation", "opticaxis", "cross", "micr", "channel", "ch", "laser",
    "nm", "raw", "ome", "zarr", "tif", "tiff", "btf", "nii", "gz", "dat", "mat", "json", "log", "svs",
    "czi", "nd2", "lif", "vsi", "sub", "ses", "sample", "acqinfo", "metadata", "dbpost", "hh", "data",
    "images", "image", "stitched", "stitch", "scan", "dapi", "gfp", "tdt",
)
_VOCAB = frozenset(VOCAB)
_CONTRAST: dict[str, Contrast] = {
    "reflectivity": "reflectivity", "retardance": "retardance", "orientation": "opticaxis",
    "opticaxis": "opticaxis", "cross": "cross",
}
_CHANNEL_WORDS = frozenset({"visor", "ch", "channel", "laser", "c"})
_DONOR = re.compile(r"[A-Za-z]{1,4}\d{0,4}")
_SPLIT = re.compile(r"[_\-.\s]+")
_EXT = re.compile(r"(\.ome)?\.(zarr|tiff?|btf|nii(\.gz)?|dat|mat|json|log|svs|czi|nd2|lif)$", re.I)


@dataclass
class NameFacts:
    donor: str | None = None
    dates: list[date] = field(default_factory=list)
    slice: int | None = None
    tile: int | None = None
    position: int | None = None
    channel_nm: int | None = None
    contrast: Contrast | None = None


def _tokens(text: str) -> list[str]:
    return [t for t in _SPLIT.split(text) if t]


def _alpha(token: str) -> str:
    return re.sub(r"\d+$", "", token).lower()


def is_vocab(token: str) -> bool:
    return token.lower() in _VOCAB or _alpha(token) in _VOCAB


def _date(token: str) -> date | None:
    if not token.isdigit() or not _is_date_like(token):
        return None
    try:
        if len(token) == 8:
            return date(int(token[:4]), int(token[4:6]), int(token[6:]))
        try:
            return date(2000 + int(token[:2]), int(token[2:4]), int(token[4:]))
        except ValueError:
            return date(int(token[:4]), int(token[4:]), 1)
    except ValueError:
        return None


def _parts(rel: str) -> list[str]:
    return [p for p in rel.replace("\\", "/").split("/") if p and p != "."]


def facts(rel: str) -> NameFacts:
    parts = _parts(rel)
    out = NameFacts()
    sub = next((p[4:] for p in parts if p.startswith("sub-") and len(p) > 4), None)
    if sub:
        out.donor = sub
    stems = [_EXT.sub("", p) for p in parts]
    for i, (part, stem) in enumerate(zip(parts, stems)):
        toks = _tokens(stem)
        for j, t in enumerate(toks):
            d = _date(t)
            if d is not None:
                if d not in out.dates:
                    out.dates.append(d)
                continue
            if out.donor is None and not t.isdigit() and not is_vocab(t) and _DONOR.fullmatch(t) \
                    and not t.startswith("sub-"):
                out.donor = t
            low = t.lower()
            if low in _CONTRAST:
                out.contrast = _CONTRAST[low]
            m = re.fullmatch(r"(?i)(pos)(\d+)", t)
            if m:
                out.position = int(m.group(2))
            if low == "slice" and j + 1 < len(toks) and toks[j + 1].isdigit():
                out.slice = int(toks[j + 1])
            if low == "tile" and j + 1 < len(toks) and toks[j + 1].isdigit():
                out.tile = int(toks[j + 1])
            if re.fullmatch(r"\d{3}", t) and 350 <= int(t) <= 900:
                near = {toks[k].lower() for k in (j - 1, j + 1) if 0 <= k < len(toks)}
                if near & _CHANNEL_WORDS:
                    out.channel_nm = int(t)
            m = re.fullmatch(r"(?i)(\d{3})nm", t)
            if m and 350 <= int(m.group(1)) <= 900:
                out.channel_nm = int(m.group(1))
        # a trailing tile index in a file name: visor_488_0012.tif
        if i == len(parts) - 1 and "." in part:
            if len(toks) >= 2 and toks[-1].isdigit() and out.tile is None:
                prev = toks[-2]
                if prev.lower() not in ("slice", "tile", "pos") and _date(toks[-1]) is None:
                    if not prev.isdigit() or int(prev) == out.channel_nm:
                        out.tile = int(toks[-1])
    return out


def path_terms(rels: Iterable[str]) -> set[str]:
    """Identifying terms from paths, for redaction: tokens, donors and every form of each date."""
    terms: set[str] = set()
    for rel in rels:
        for part in _parts(rel):
            for t in _tokens(_EXT.sub("", part)):
                if len(t) < 3 or is_vocab(t) or (t.isdigit() and len(t) < 6):
                    continue
                terms.add(t)
                d = _date(t)
                if d is not None:
                    terms |= _date_forms(d.strftime("%Y%m%d"))
        f = facts(rel)
        if f.donor:
            terms.add(f.donor)
        for d in f.dates:
            terms |= _date_forms(d.strftime("%Y%m%d"))
    return terms
