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

# Structural words may carry a digit suffix (Slice051, Pos3, ch1); every other word matches exactly.
STRUCTURAL = ("slice", "tile", "pos", "ch")
VOCAB: tuple[str, ...] = STRUCTURAL + (
    "visor", "spim", "exaspim", "ps", "hh", "oct", "psoct", "enface", "registration",
    "reflectivity", "retardance", "orientation", "opticaxis", "cross", "micr", "channel", "laser",
    "raw", "ome", "zarr", "tif", "tiff", "btf", "nii", "gz", "dat", "mat", "json", "log", "svs",
    "czi", "nd2", "lif", "vsi", "sub", "ses", "sample", "acqinfo", "metadata", "dbpost", "data",
    "images", "image", "stitched", "stitch", "scan", "dapi",
)
_VOCAB = frozenset(VOCAB)
DONOR_STOP = frozenset({"test", "run", "scan", "data", "raw", "new", "old", "final"})
_SEP_DATE = re.compile(r"(?<!\d)(?:(\d{4})[-_.](\d{2})[-_.](\d{2})|(\d{2})[-_.](\d{2})[-_.](\d{4}))(?!\d)")
_CONTRAST: dict[str, Contrast] = {
    "reflectivity": "reflectivity", "retardance": "retardance", "orientation": "opticaxis",
    "opticaxis": "opticaxis", "cross": "cross",
}
VISOR_META_NAMES = frozenset({"acqinfo_metadata.json", "dbpost.json", "hh.log"})
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


def is_vocab(token: str, vocab: Iterable[str] | None = None) -> bool:
    """Exact vocabulary match; only STRUCTURAL words may carry a digit suffix (Slice051, Pos3, ch1)."""
    words = _VOCAB if vocab is None else vocab if isinstance(vocab, frozenset) else frozenset(vocab)
    low = token.lower()
    if low in words:
        return True
    m = re.fullmatch(r"([a-z]+)\d+", low)
    return bool(m) and m.group(1) in STRUCTURAL


def _valid(y: int, m: int, d: int) -> date | None:
    if not 1900 <= y <= 2099:
        return None
    try:
        return date(y, m, d)
    except ValueError:
        return None


def separator_dates(rel: str) -> list[tuple[str, list[date]]]:
    """(matched text, readings) for dates written with - _ . separators; invalid ones are dropped."""
    out = []
    for m in _SEP_DATE.finditer(rel.replace("\\", "/")):
        g = m.groups()
        if g[0]:
            reads = [_valid(int(g[0]), int(g[1]), int(g[2]))]
        else:  # dd-mm-yyyy first, else mm-dd-yyyy
            reads = [_valid(int(g[5]), int(g[4]), int(g[3])), _valid(int(g[5]), int(g[3]), int(g[4]))]
        reads = [r for r in reads if r]
        if reads:
            out.append((m.group(0), reads[:1] if g[0] else reads))
    return out


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


def _trailing_tile(toks: list[str]) -> int | None:
    """A trailing tile index in a file name (visor_488_0012, visor_488_000123); never a date or slice."""
    if len(toks) < 2 or not toks[-1].isdigit():
        return None
    prev = toks[-2]
    if prev.lower() in ("slice", "tile", "pos"):
        return None
    channel = prev.isdigit() and len(prev) == 3 and 350 <= int(prev) <= 900
    if prev.isdigit() and not channel:
        return None
    if _date(toks[-1]) is not None and not (channel or prev.lower() in _CHANNEL_WORDS):
        return None
    return int(toks[-1])


def facts(rel: str, vocab: Iterable[str] | None = None) -> NameFacts:
    parts = _parts(rel)
    vocab = None if vocab is None else frozenset(vocab)
    out = NameFacts()
    out.donor = next((p[4:] for p in parts if p.startswith("sub-") and len(p) > 4), None)
    stems = [_EXT.sub("", p) for p in parts]
    for text, reads in separator_dates(rel):
        for d in reads:
            if d not in out.dates:
                out.dates.append(d)
    donor_from = {0, len(parts) - 1}
    for i, (part, stem) in enumerate(zip(parts, stems)):
        toks = _tokens(stem)
        last = i == len(parts) - 1
        trail = _trailing_tile(toks) if last and "." in part else None
        if trail is not None:
            out.tile = trail
        for j, t in enumerate(toks):
            if trail is not None and j == len(toks) - 1:
                continue
            d = _date(t)
            if d is not None:
                if d not in out.dates:
                    out.dates.append(d)
                continue
            if (out.donor is None and i in donor_from and part not in VISOR_META_NAMES
                    and not t.isdigit() and not is_vocab(t, vocab) and t.lower() not in DONOR_STOP
                    and _DONOR.fullmatch(t)):
                out.donor = t
            low = t.lower()
            if low in _CONTRAST:
                out.contrast = _CONTRAST[low]
            m = re.fullmatch(r"(?i)pos(\d+)", t)
            if m:
                out.position = int(m.group(1))
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
    return out


def path_terms(rels: Iterable[str], vocab: Iterable[str] | None = None) -> set[str]:
    """Identifying terms from paths, for redaction: tokens, donors and every form of each date."""
    terms: set[str] = set()
    vocab = None if vocab is None else frozenset(vocab)
    for rel in rels:
        for part in _parts(rel):
            for t in _tokens(_EXT.sub("", part)):
                if len(t) < 3 or is_vocab(t, vocab) or (t.isdigit() and len(t) < 6):
                    continue
                terms.add(t)
                d = _date(t)
                if d is not None:
                    terms |= _date_forms(d.strftime("%Y%m%d"))
        for text, reads in separator_dates(rel):
            terms.add(text)
            for d in reads:
                terms |= _date_forms(d.strftime("%Y%m%d"))
        f = facts(rel, vocab)
        if f.donor:
            terms.add(f.donor)
        for d in f.dates:
            terms |= _date_forms(d.strftime("%Y%m%d"))
    return terms
