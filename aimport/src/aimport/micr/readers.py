"""Microscopy image readers: lazy, memory-bounded pixel access and allowlisted metadata.

``open_image(location, family)`` returns an ``ImageSource``: an ``ImageInfo`` holding only the
allowlisted facts, the ``terms`` (every dropped metadata string, for redaction), and
``level(i)``, a dask array per pyramid level in ``tczyx`` order whose blocks are at most
``aimport.micr.MAX_BLOCK_BYTES`` wherever the file layout allows. Opening a source reads headers
and metadata only; slide label and macro images are detected and never read.
"""
from __future__ import annotations

import json
import logging
import math
import re
from dataclasses import dataclass
from datetime import date, datetime
from importlib.metadata import entry_points
from pathlib import Path
from typing import Any, Callable, Protocol, runtime_checkable

import numpy as np

from .. import micr
from .metadata import (
    AXES_ORDER,
    ChannelInfo,
    ImageInfo,
    PixelUnit,
    channel_code,
    collect_terms,
    convert_length,
    date_terms,
    ome_allowlist,
)

__all__ = [
    "BIOFORMATS_MESSAGE", "MAT_V5_MAX_BYTES", "ChannelInfo", "ImageInfo", "ImageSource",
    "UnsupportedFormat", "apply_visor_meta", "open_image", "plan_chunks", "register_reader",
]

log = logging.getLogger(__name__)

BIOFORMATS_MESSAGE = "needs Bio-Formats (not included): export to OME-TIFF or OME-Zarr first"
MAT_V5_MESSAGE = "MATLAB v5 file too large to read lazily: save as v7.3"
MAT_V5_MAX_BYTES = 2 * 2**30
ENTRY_POINT_GROUP = "aimport.micr_readers"


class UnsupportedFormat(ValueError):
    """The input is microscopy, but aimport cannot read it; the message says what to do."""


@runtime_checkable
class ImageSource(Protocol):
    info: ImageInfo
    terms: set[str]

    def level(self, i: int) -> Any: ...  # dask.array.Array

    def close(self) -> None: ...


# --- shared helpers ---------------------------------------------------------------------------

def _limit() -> int:
    return int(micr.MAX_BLOCK_BYTES)  # read at call time so tests (and Task 8) can patch it


def plan_chunks(shape: tuple[int, ...], itemsize: int, limit: int | None = None,
                native: tuple[int, ...] | None = None, order: str = "C") -> tuple[int, ...]:
    """Chunk shape of at most ``limit`` bytes, splitting the slowest axes first.

    With ``native`` (the file's own chunks), a chunk is rounded down to whole native chunks
    along every axis where it is larger than one. ``order="F"`` treats the last axis as slowest.
    """
    limit = _limit() if limit is None else limit
    shape = tuple(int(s) for s in shape)
    if order == "F":
        rev = plan_chunks(shape[::-1], itemsize, limit, native[::-1] if native else None, "C")
        return rev[::-1]
    chunk = [max(1, s) for s in shape]
    for ax in range(len(chunk)):
        rest = itemsize * math.prod(chunk[ax + 1:])
        if rest * chunk[ax] <= limit:
            break
        chunk[ax] = max(1, limit // rest) if rest <= limit else 1
        if rest * chunk[ax] <= limit:
            break
    if native:
        for ax, n in enumerate(native):
            n = max(1, int(n))
            if n < chunk[ax] < shape[ax]:
                chunk[ax] = chunk[ax] // n * n
    return tuple(min(c, max(1, s)) for c, s in zip(chunk, shape))


def _chunk_bytes(chunks: tuple[int, ...], itemsize: int) -> int:
    return itemsize * math.prod(chunks)


class _AxisMap:
    """Maps a source's axes (any letters) onto ``tczyx``: rename, squeeze size-1 extras, transpose."""

    DIRECT = {"t": "t", "c": "c", "s": "c", "z": "z", "y": "y", "x": "x"}

    def __init__(self, src_axes: str, src_shape: tuple[int, ...], squeeze: str = ""):
        src = src_axes.lower()
        if len(src) != len(src_shape):
            raise UnsupportedFormat(f"axes {src_axes!r} do not match a {len(src_shape)}-d array")
        target: list[str | None] = [None] * len(src)
        owner: dict[str, int] = {}

        def assign(i: int, canon: str) -> bool:
            j = owner.get(canon)
            if j is None:
                owner[canon] = i
                target[i] = canon
                return True
            if src_shape[i] == 1:
                return True  # squeeze this one
            if src_shape[j] == 1:
                target[j] = None
                owner[canon] = i
                target[i] = canon
                return True
            return False

        others = []
        for i, a in enumerate(src):
            if a in squeeze and src_shape[i] == 1:
                continue  # dropped: a size-1 axis the caller does not want
            if a in self.DIRECT:
                if not assign(i, self.DIRECT[a]):
                    raise UnsupportedFormat(f"cannot map axes {src_axes!r} onto tczyx")
            else:
                others.append(i)
        for i in others:
            free = [c for c in ("z", "t", "c") if c not in owner]
            if free:
                assign(i, free[0])
            elif src_shape[i] != 1:
                raise UnsupportedFormat(f"cannot map axes {src_axes!r} onto tczyx")
        if "y" not in owner or "x" not in owner:
            raise UnsupportedFormat(f"axes {src_axes!r} have no y and x")
        self.index = tuple(slice(None) if t else 0 for t in target)
        kept = [(t, i) for i, t in enumerate(target) if t]
        order = sorted(range(len(kept)), key=lambda k: AXES_ORDER.index(kept[k][0]))
        self.perm = tuple(order)
        self.axes = "".join(kept[k][0] for k in order)
        self._src_shape = tuple(src_shape)
        self._kept_src = [kept[k][1] for k in order]

    def shape(self, src_shape: tuple[int, ...] | None = None) -> tuple[int, ...]:
        s = src_shape if src_shape is not None else self._src_shape
        return tuple(int(s[i]) for i in self._kept_src)

    def apply(self, arr: Any) -> Any:
        if any(not isinstance(ix, slice) for ix in self.index):
            arr = arr[self.index]
        if self.perm != tuple(range(len(self.perm))):
            arr = arr.transpose(self.perm)
        return arr


def _default_channels(axes: str, shape: tuple[int, ...]) -> list[ChannelInfo]:
    n = shape[axes.index("c")] if "c" in axes else 1
    return [ChannelInfo(None, None, f"ch{i}") for i in range(n)]


class _Source:
    def __init__(self, info: ImageInfo, terms: set[str], levels: list[Callable[[], Any]],
                 close: Callable[[], None] | None = None):
        self.info = info
        self.terms = terms
        self._levels = levels
        self._cache: dict[int, Any] = {}
        self._close = close

    def level(self, i: int) -> Any:
        if not 0 <= i < len(self._levels):
            raise IndexError(f"level {i} out of range (0..{len(self._levels) - 1})")
        if i not in self._cache:
            self._cache[i] = self._levels[i]()
        return self._cache[i]

    def close(self) -> None:
        self._cache.clear()
        if self._close is not None:
            close, self._close = self._close, None
            close()

    def __enter__(self) -> "_Source":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def __repr__(self) -> str:
        return f"<ImageSource {self.info.family} {self.info.axes} {self.info.shape}>"


def _from_array(arr: Any, chunks: tuple[int, ...]) -> Any:
    import dask.array as da

    meta = np.empty((0,) * len(chunks), dtype=arr.dtype)
    return da.from_array(arr, chunks=chunks, name=False, asarray=True, fancy=False, meta=meta)


def _parse_ome(xml: str) -> Any | None:
    from ome_types import from_xml

    for kwargs in ({}, {"validate": False}):
        try:
            return from_xml(xml, **kwargs)
        except Exception:  # noqa: BLE001 - fall back to a lenient parse, then to the raw terms
            continue
    return None


_XML_SKIP = re.compile(r"^([A-Za-z]+:\d+(:\d+)*|[-+]?\d+(\.\d+)?([eE][-+]?\d+)?)$")


def _xml_terms(xml: Any) -> set[str]:
    """Every attribute value and text node of an XML document (a string or a parsed element)."""
    import xml.etree.ElementTree as ET

    terms: set[str] = set()
    if isinstance(xml, (str, bytes)):
        try:
            root = ET.fromstring(xml)
        except ET.ParseError:
            return collect_terms(xml)
    else:
        root = xml
    for el in root.iter():
        for v in [*el.attrib.values(), el.text or ""]:
            v = v.strip()
            if v and not _XML_SKIP.match(v):
                terms.add(v)
    return terms


def _is_ome_xml(text: str) -> bool:
    head = text.lstrip()[:512]
    return head.startswith("<OME") or (head.startswith("<?xml") and "<OME" in text[:4096])


def _expand_text(text: str) -> set[str]:
    """Terms from one free-text value: XML is split into its values, JSON into its strings,
    and ``key = value`` / ``key: value`` lines (ImageJ Info, Aperio, MetaMorph) into values."""
    text = text.strip("\x00").strip()
    if not text:
        return set()
    if text.startswith("<"):
        return _xml_terms(text)
    if text[0] in "{[":
        try:
            return collect_terms(json.loads(text))
        except ValueError:
            pass
    terms = {text}
    for line in re.split(r"[\r\n|]+", text):
        line = line.strip()
        if not line:
            continue
        terms.add(line)
        for sep in ("=", ":"):
            if sep in line:
                terms.add(line.split(sep, 1)[1].strip())
                break
    return {t for t in terms if len(t) >= 2 and any(c.isalnum() for c in t)}


def _decode_text(value: bytes) -> str | None:
    """Bytes that are text (UTF-8, no inner NULs); binary blobs such as ICC profiles are None."""
    raw = value.rstrip(b"\x00")
    if not raw or b"\x00" in raw:
        return None
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return None
    printable = sum(c.isprintable() or c in "\r\n\t" for c in text)
    return text if printable >= 0.95 * len(text) else None


def deep_terms(obj: Any) -> set[str]:
    """collect_terms, with each string expanded by _expand_text and XML elements walked."""
    if hasattr(obj, "iter") and hasattr(obj, "attrib"):  # an ElementTree/lxml element
        return _xml_terms(obj)
    if isinstance(obj, bytes):
        text = _decode_text(obj)
        return _expand_text(text) if text else set()
    if isinstance(obj, str):
        return _expand_text(obj)
    if isinstance(obj, dict):
        out: set[str] = set()
        for v in obj.values():
            out |= deep_terms(v)
        return out
    if isinstance(obj, (list, tuple, set, frozenset)):
        out = set()
        for v in obj:
            out |= deep_terms(v)
        return out
    out = set()
    for t in collect_terms(obj):
        out |= _expand_text(t)
    return out


# --- TIFF / OME-TIFF / SVS ---------------------------------------------------------------------

_SKIP_WORD = re.compile(r"\b(label|macro|thumbnail)\b")
# Series kinds whose names come from the file's author (OME Image Name, tifffile 'Name'
# metadata), not from tifffile's vendor parser: a name there is never a label/macro signal.
_USER_NAMED_KINDS = frozenset({"ome", "shaped", "generic", "uniform", "imagej", "mmstack", "ndtiff"})
# Pages whose tags are walked for terms, per series (plus each series' last page): enough for
# per-page descriptions without reading every IFD of a huge stack.
TERM_PAGES = 64
# tifffile's parsed vendor metadata (TiffFile.<name>_metadata), walked for terms. OME is not
# here: it goes through the allowlist.
_TIFF_METADATA = ("imagej", "micromanager", "lsm", "fluoview", "metaseries", "stk", "shaped",
                  "nih", "fei", "sem", "sis", "mdgel", "scanimage", "andor", "epics", "tvips",
                  "pilatus", "streak", "flimage", "huron", "eer", "nuvu", "trestle", "gdal",
                  "scn", "philips", "indica", "qpi", "bif", "avs")


def _skip_kind(series: Any) -> str | None:
    if series.kind in _USER_NAMED_KINDS:
        return None
    name = (series.name or "").strip().lower()
    m = _SKIP_WORD.search(name)
    if not m:
        return None
    if series.kind == "svs" and m.group(1) == "thumbnail":
        return "svs-thumbnail"  # a reduced copy of the scanned area: unused, not a privacy skip
    return m.group(1)


def _tiff_datetime(text: str) -> datetime | None:
    for fmt in ("%Y:%m:%d %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(text.strip()[:19], fmt)
        except ValueError:
            continue
    return None


def _page_terms(page: Any, ome: bool) -> tuple[set[str], datetime | None]:
    """Every text value of every tag of one page header (no pixels are read)."""
    terms: set[str] = set()
    when = None
    for tag in page.tags:
        value = tag.value
        if isinstance(value, bytes):
            value = _decode_text(value)
            if value is None:
                continue
        if isinstance(value, str):
            value = value.strip("\x00").strip()
            if not value:
                continue
            if tag.code == 270 and ome and _is_ome_xml(value):
                continue  # OME-XML: handled by the allowlist
            if tag.code == 306:
                when = _tiff_datetime(value)
                if when:
                    terms |= date_terms(when)
            terms |= _expand_text(value)
        elif isinstance(value, (dict, list, tuple)):  # parsed tags: EXIF, Micro-Manager, ...
            terms |= deep_terms(value)
    return terms, when


def _tiff_terms(tif: Any, series: list[Any]) -> tuple[set[str], datetime | None]:
    """Terms from the tags of the first TERM_PAGES pages and the last page of each series, and
    from tifffile's parsed vendor metadata."""
    terms: set[str] = set()
    when = None
    indices: list[int] = []
    for s in series:
        pages = [p for p in s.pages if p is not None]
        for p in pages[:TERM_PAGES] + pages[-1:]:
            if p.index not in indices:
                indices.append(p.index)
    if 0 not in indices:
        indices.insert(0, 0)
    for i in indices:
        try:
            page = tif.pages.get(i, cache=False, aspage=True)
        except Exception:  # noqa: BLE001 - a broken IFD must not stop the import
            continue
        t, w = _page_terms(page, tif.is_ome)
        terms |= t
        when = when or w
    for name in _TIFF_METADATA:
        try:
            meta = getattr(tif, f"{name}_metadata", None)
        except Exception:  # noqa: BLE001
            continue
        if meta:
            terms |= deep_terms(meta)
    return terms, when


def _tiff_pixel_size(tif: Any, page: Any) -> dict[str, float]:
    """Pixel size in um from SVS MPP, ImageJ unit/spacing, or the resolution tags."""
    from tifffile.tifffile import svs_description_metadata

    size: dict[str, float] = {}
    if page.is_svs:
        try:
            meta = svs_description_metadata(page.description)
            if isinstance(meta.get("MPP"), (int, float)) and meta["MPP"] > 0:
                return {"x": float(meta["MPP"]), "y": float(meta["MPP"])}
        except Exception:  # noqa: BLE001
            pass
    xres, yres = page.tags.get(282), page.tags.get(283)
    unit = page.tags.get(296)
    unit = int(unit.value) if unit is not None else 2
    ij = tif.imagej_metadata or {}
    ij_unit = str(ij.get("unit", "")).replace("\\u00B5", "µ").lower()

    def per_px(tag: Any) -> float | None:
        try:
            num, den = tag.value
            return den / num if num else None
        except (TypeError, ValueError):
            return None

    if xres is not None and yres is not None:
        fx, fy = per_px(xres), per_px(yres)
        if fx and fy:
            screen_dpi = any(abs(1 / fx - dpi) < 1e-6 for dpi in (1.0, 72.0, 96.0))
            if ij_unit in ("micron", "um", "µm"):
                size = {"x": fx, "y": fy}
            elif unit == 3:  # centimetre
                size = {"x": fx * 1e4, "y": fy * 1e4}
            elif unit == 2 and not screen_dpi:  # inch; 1, 72 and 96 dpi are defaults, not sizes
                size = {"x": fx * 25400, "y": fy * 25400}
    if ij_unit in ("micron", "um", "µm") and isinstance(ij.get("spacing"), (int, float)):
        size["z"] = float(ij["spacing"])
    return size


def _svs_extra(page: Any) -> tuple[float | None, date | None]:
    from tifffile.tifffile import svs_description_metadata

    try:
        meta = svs_description_metadata(page.description)
    except Exception:  # noqa: BLE001
        return None, None
    mag = meta.get("AppMag")
    when = None
    if isinstance(meta.get("Date"), str):
        try:
            when = datetime.strptime(meta["Date"], "%m/%d/%y").date()
        except ValueError:
            pass
    return (float(mag) if isinstance(mag, (int, float)) else None), when


def _tiff_level(tif: Any, series: Any, i: int, amap: _AxisMap, path: Path | None) -> Any:
    import dask.array as da
    import zarr

    lvl = series.levels[i]
    itemsize = np.dtype(lvl.dtype).itemsize
    limit = _limit()
    z = zarr.open_array(series.aszarr(level=i), mode="r")
    native = tuple(int(c) for c in z.chunks)
    if _chunk_bytes(native, itemsize) <= limit:
        arr = da.from_zarr(z, chunks=plan_chunks(z.shape, itemsize, limit, native))
    elif lvl.dataoffset is not None:
        # one strip/tile larger than the block limit, stored uncompressed and contiguous:
        # map the file (or, for a remote file, range-read it) in row blocks, never the whole plane.
        dtype = np.dtype(lvl.dtype).newbyteorder(tif.byteorder)
        shape = tuple(lvl.shape)
        if path is not None:
            mm = np.memmap(path, dtype=dtype, mode="r", offset=lvl.dataoffset, shape=shape)
        else:
            mm = _ContiguousFile(tif.filehandle, lvl.dataoffset, dtype, shape)
        arr = _from_array(mm, plan_chunks(shape, itemsize, limit))
    elif _chunk_bytes(native, itemsize) > 4 * limit:
        raise UnsupportedFormat("compressed tiles larger than the block limit: re-save with smaller tiles")
    else:
        log.warning("TIFF chunks (%d bytes) exceed the block limit and are compressed",
                    _chunk_bytes(native, itemsize))
        arr = da.from_zarr(z)
    return amap.apply(arr)


class _ContiguousFile:
    """Array view of a contiguous, uncompressed C-order block of a file object (remote TIFFs)."""

    def __init__(self, fh: Any, offset: int, dtype: np.dtype, shape: tuple[int, ...]):
        self.fh, self.offset, self.dtype, self.shape, self.ndim = fh, offset, dtype, shape, len(shape)

    def __getitem__(self, key: Any) -> Any:
        key = key if isinstance(key, tuple) else (key,)
        lead = key[0] if key else slice(None)
        start, stop, _ = lead.indices(self.shape[0]) if isinstance(lead, slice) else (lead, lead + 1, 1)
        row = int(np.prod(self.shape[1:], dtype=np.int64)) * self.dtype.itemsize
        with self.fh.lock:
            self.fh.seek(self.offset + start * row)
            buf = self.fh.read((stop - start) * row)
        block = np.frombuffer(buf, dtype=self.dtype).reshape((stop - start,) + self.shape[1:])
        rest = (slice(None),) + tuple(key[1:])
        out = block[rest]
        return out if isinstance(lead, slice) else out[0]


def _is_path(location: Any) -> bool:
    return isinstance(location, (str, Path))


def _open_tiff(location: Any, family: str) -> _Source:
    """``location``: a path, or a seekable binary file object (a remote file, ``micr.remote``)."""
    import tifffile

    path = Path(location) if _is_path(location) else None
    tif = tifffile.TiffFile(str(path) if path is not None else location)
    try:
        series = tif.series
        skipped: list[str] = []
        main, main_index = None, 0
        for i, s in enumerate(series):
            kind = _skip_kind(s)
            if kind:
                if kind != "svs-thumbnail":
                    skipped.append(kind)
                continue
            if main is None:
                main, main_index = s, i
        if main is None:
            raise UnsupportedFormat("no image series besides slide label, macro or thumbnail")
        terms, when = _tiff_terms(tif, list(series))
        amap = _AxisMap(main.axes, tuple(main.shape))
        shape = amap.shape()
        fields: dict[str, Any] = {}
        if tif.is_ome and tif.ome_metadata:
            ome = _parse_ome(tif.ome_metadata)
            if ome is not None:
                fields, ome_terms = ome_allowlist(ome, image=main_index)
                terms |= ome_terms
            else:
                terms |= _xml_terms(tif.ome_metadata)
        elif tif.pages.first.description and _is_ome_xml(tif.pages.first.description):
            terms |= _xml_terms(tif.pages.first.description)  # OME-XML tifffile did not take
        page0 = main.pages[0]
        if not fields.get("pixel_size"):
            fields["pixel_size"] = _tiff_pixel_size(tif, page0)
            fields["pixel_unit"] = "um"
        if page0.is_svs:
            mag, svs_date = _svs_extra(page0)
            fields.setdefault("objective_magnification", mag)
            when = when or (datetime.combine(svs_date, datetime.min.time()) if svs_date else None)
        if not fields.get("acquired") and when is not None:
            fields["acquired"] = when.date()
        if fields.get("acquired"):
            terms |= date_terms(fields["acquired"])
        channels = fields.pop("channels", None) or _default_channels(amap.axes, shape)
        info = ImageInfo(
            family=family, axes=amap.axes, shape=shape, dtype=str(np.dtype(main.dtype)),
            channels=channels, levels=len(main.levels), series_skipped=skipped,
            **{k: v for k, v in fields.items() if v is not None},
        )
    except BaseException:
        tif.close()
        raise

    levels = [lambda i=i: _tiff_level(tif, main, i, amap, path) for i in range(len(main.levels))]
    return _Source(info, terms, levels, tif.close)


# --- VISoR tiles: TIFF pixels, pixel size and channel from acqinfo_metadata.json --------------

# Key-name patterns for numeric fields of acqinfo_metadata.json (flattened, lowercased; the last
# path component, list indices included). The real CMC files (version 0.0.3, DATASETS.md) have
# settings.pixel_spacing_um, positions[i].x_step_um (VISoR scans the stage along x, so x_step is
# the spacing between the frames of a raw tile) and excitation_wavelengths[i] as text ("488nm").
_VISOR_XY = re.compile(r"(pixel|voxel)[ _]?(size|spacing|res(olution)?)(?![ _]?z)|resolution[ _]?xy?\b|um[ _]?per[ _]?pixel")
_VISOR_Z = re.compile(r"(z[ _]?(step|spacing|res(olution)?)|step[ _]?z|slice[ _]?(thickness|spacing|interval)|(pixel|voxel)[ _]?(size|spacing)[ _]?z|\bx[ _]?step)")
_VISOR_CH = re.compile(r"(wave[ _]?length|laser|excitation|channel|ex\b)")
_WAVELENGTH_TEXT = re.compile(r"\s*(\d{3}(?:\.\d+)?)\s*(?:nm)?\s*", re.IGNORECASE)


def _flatten(obj: Any, prefix: str = "") -> list[tuple[str, Any]]:
    out: list[tuple[str, Any]] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            out += _flatten(v, f"{prefix}.{k}" if prefix else str(k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            out += _flatten(v, f"{prefix}[{i}]")
    else:
        out.append((prefix, obj))
    return out


def visor_facts(meta: dict) -> tuple[dict[str, float], float | None]:
    """(pixel_size in um, excitation nm) from acqinfo_metadata.json: numeric fields, and wavelengths
    written as text ("488nm"). Other strings are never read for facts."""
    size: dict[str, float] = {}
    channel = None
    for key, value in _flatten(meta):
        k = key.lower().rsplit(".", 1)[-1]
        if isinstance(value, str) and _VISOR_CH.search(k):  # "488nm": a wavelength as text
            m = _WAVELENGTH_TEXT.fullmatch(value)
            value = float(m.group(1)) if m else None
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
            continue
        if "z" not in size and _VISOR_Z.search(k):
            size["z"] = float(value)
        elif "x" not in size and _VISOR_XY.search(k):
            size["x"] = size["y"] = float(value)
        elif channel is None and _VISOR_CH.search(k) and 350 <= value <= 900:
            channel = float(value)
    return size, channel


def apply_visor_meta(src: Any, meta: dict) -> None:
    """Pixel size and channel from a parsed acqinfo_metadata.json; its strings become terms."""
    src.terms |= collect_terms(meta)
    size, channel = visor_facts(meta)
    if size:
        src.info.pixel_size = size
        src.info.pixel_unit = "um"
    if channel is not None and len(src.info.channels) == 1:
        src.info.channels = [ChannelInfo(channel, None, channel_code(channel, 0))]


def _open_visor(location: Any) -> _Source:
    """A VISoR tile. For a file object (remote), ``micr.remote`` reads the metadata JSON itself."""
    src = _open_tiff(location, "visor")
    if not _is_path(location):
        return src
    tile = Path(location)
    for folder in (tile.parent, tile.parent.parent):
        meta_path = folder / "acqinfo_metadata.json"
        if meta_path.is_file():
            try:
                meta = json.loads(meta_path.read_text(errors="replace"))
            except (OSError, ValueError):
                break
            if isinstance(meta, dict):
                apply_visor_meta(src, meta)
            break
    return src


# --- CZI / ND2 / LIF through bioio -----------------------------------------------------------

def _bioimage(location: str | Path, family: str) -> Any:
    from bioio import BioImage

    if family == "czi":
        from bioio_czi import Reader
    elif family == "nd2":
        from bioio_nd2 import Reader
    else:
        from bioio_lif import Reader
    try:
        return BioImage(str(location), reader=Reader, chunk_dims=["Y", "X"])
    except TypeError:
        return BioImage(str(location), reader=Reader)


def _open_bioio(location: str | Path, family: str) -> _Source:
    img = _bioimage(location, family)
    order = img.dims.order
    shape = tuple(int(s) for s in img.shape)
    amap = _AxisMap(order, shape, squeeze="t")  # bioio is always 5-d: drop a single time point
    terms: set[str] = set()
    fields: dict[str, Any] = {}
    try:
        ome = img.ome_metadata
    except Exception:  # noqa: BLE001 - not every plugin converts to OME
        ome = None
    if ome is not None:
        fields, terms = ome_allowlist(ome)
    if not fields.get("pixel_size"):
        pps = getattr(img, "physical_pixel_sizes", None)
        size = {}
        for axis in ("x", "y", "z"):
            v = getattr(pps, axis.upper(), None) if pps is not None else None
            if v:
                size[axis] = float(v)
        fields["pixel_size"] = size
        fields["pixel_unit"] = "um"
    try:
        raw = img.metadata  # the vendor's own metadata (CZI/LIF XML, ND2 objects)
    except Exception:  # noqa: BLE001
        raw = None
    if raw is not None:
        terms |= deep_terms(raw)
    for name in getattr(img, "channel_names", None) or []:
        terms |= collect_terms(name)
    if fields.get("acquired"):
        terms |= date_terms(fields["acquired"])
    out_shape = amap.shape(shape)
    channels = fields.pop("channels", None) or _default_channels(amap.axes, out_shape)
    try:
        n_levels = max(1, len(img.resolution_levels))
    except Exception:  # noqa: BLE001
        n_levels = 1
    info = ImageInfo(family=family, axes=amap.axes, shape=out_shape, dtype=str(np.dtype(img.dtype)),
                     channels=channels, levels=n_levels,
                     **{k: v for k, v in fields.items() if v is not None})

    def level(i: int) -> Any:
        if n_levels > 1:
            img.set_resolution_level(i)
        lvl_map = _AxisMap(img.dims.order, tuple(int(s) for s in img.shape), squeeze="t")
        return lvl_map.apply(img.dask_data)

    close = getattr(img, "close", None)
    return _Source(info, terms, [lambda i=i: level(i) for i in range(n_levels)], close)


# --- NIfTI (PS-OCT en-face contrasts) ---------------------------------------------------------

_NIFTI_TEXT = ("descrip", "aux_file", "intent_name", "db_name")
_NIFTI_UNIT: dict[str, tuple[PixelUnit, float]] = {
    "micron": ("um", 1.0), "mm": ("mm", 1.0), "meter": ("mm", 1000.0), "unknown": ("mm", 1.0),
}


def _load_nifti(location: Any) -> Any:
    import gzip

    import nibabel as nib

    if _is_path(location):
        return nib.load(str(location))
    # a seekable binary file object (a remote file): gzip is detected from its magic bytes
    pos = location.tell()
    magic = location.read(2)
    location.seek(pos)
    stream = gzip.GzipFile(fileobj=location, mode="rb") if magic == b"\x1f\x8b" else location
    return nib.Nifti1Image.from_stream(stream)


def _open_nifti(location: Any) -> _Source:
    img = _load_nifti(location)
    hdr = img.header
    proxy = img.dataobj
    shape = tuple(int(s) for s in img.shape)
    if not 2 <= len(shape) <= 5:
        raise UnsupportedFormat(f"NIfTI with {len(shape)} dimensions")
    amap = _AxisMap("xyztc"[: len(shape)], shape)
    space_unit = hdr.get_xyzt_units()[0]
    unit, factor = _NIFTI_UNIT.get(space_unit, ("mm", 1.0))
    zooms = hdr.get_zooms()
    pixel_size = {a: float(zooms[i]) * factor for i, a in enumerate("xyz"[: min(3, len(shape))])
                  if zooms[i] > 0}
    terms: set[str] = set()
    for key in _NIFTI_TEXT:
        if key in hdr:
            terms |= collect_terms(np.asarray(hdr[key]).tobytes())
    for ext in getattr(hdr, "extensions", []) or []:
        try:
            content = ext.get_content()
        except Exception:  # noqa: BLE001
            continue
        if isinstance(content, (bytes, str)) and len(content) <= 65536:
            terms |= collect_terms(content)
    # scaled data (scl_slope/inter) comes back as float: take the dtype a read returns
    dtype = np.asarray(proxy[(slice(0, 1),) * len(shape)]).dtype
    out_shape = amap.shape(shape)
    info = ImageInfo(family="nifti", axes=amap.axes, shape=out_shape, dtype=str(dtype),
                     pixel_size=pixel_size, pixel_unit=unit,
                     channels=_default_channels(amap.axes, out_shape), levels=1)

    def level0() -> Any:
        chunks = plan_chunks(shape, dtype.itemsize, order="F")  # NIfTI is stored x-fastest

        class _Proxy:  # gives dask the scaled dtype without reading
            def __init__(self) -> None:
                self.shape, self.dtype, self.ndim = shape, dtype, len(shape)

            def __getitem__(self, key: Any) -> Any:
                return np.asarray(proxy[key], dtype=dtype)

        return amap.apply(_from_array(_Proxy(), chunks))

    return _Source(info, terms, [level0])


# --- MATLAB (PS-OCT volumes) ------------------------------------------------------------------

_MAT_AXES = {2: "yx", 3: "yxz", 4: "yxzt"}


def _mat_axes(matlab_shape: tuple[int, ...]) -> str:
    axes = _MAT_AXES.get(len(matlab_shape))
    if axes is None:
        raise UnsupportedFormat(f"MATLAB array with {len(matlab_shape)} dimensions")
    return axes


def _open_mat(location: str | Path) -> _Source:
    import h5py

    path = Path(location)
    if h5py.is_hdf5(str(path)):
        return _open_mat73(path)
    if path.stat().st_size > MAT_V5_MAX_BYTES:
        raise UnsupportedFormat(MAT_V5_MESSAGE)
    import scipy.io

    data = scipy.io.loadmat(str(path))
    terms: set[str] = set()
    best: np.ndarray | None = None
    for key, value in data.items():
        if key.startswith("__"):
            if key == "__header__":
                terms |= collect_terms(value)
            continue
        if isinstance(value, np.ndarray) and value.dtype.kind in "biuf":
            if value.ndim >= 2 and (best is None or value.size > best.size):
                best = value
        else:
            terms |= collect_terms(value.tolist() if isinstance(value, np.ndarray) else value)
    if best is None:
        raise UnsupportedFormat("MATLAB file holds no numeric image array")
    arr = np.squeeze(best) if best.ndim > 4 else best
    amap = _AxisMap(_mat_axes(arr.shape), arr.shape)
    out_shape = amap.shape()
    info = ImageInfo(family="mat", axes=amap.axes, shape=out_shape, dtype=str(arr.dtype),
                     channels=_default_channels(amap.axes, out_shape), levels=1)
    return _Source(info, terms,
                   [lambda: amap.apply(_from_array(arr, plan_chunks(arr.shape, arr.dtype.itemsize)))])


def _open_mat73(path: Path) -> _Source:
    import h5py

    f = h5py.File(str(path), "r")
    try:
        terms: set[str] = set()
        datasets: list[Any] = []

        def visit(name: str, obj: Any) -> None:
            for k, v in obj.attrs.items():
                if not k.startswith("MATLAB_"):
                    terms.update(collect_terms(v.tolist() if isinstance(v, np.ndarray) else v))
            if not isinstance(obj, h5py.Dataset) or name.startswith("#refs#"):
                return
            cls = obj.attrs.get("MATLAB_class", b"")
            cls = cls.decode() if isinstance(cls, bytes) else str(cls)
            if cls == "char":
                if obj.size <= 65536:
                    terms.update(collect_terms("".join(map(chr, np.asarray(obj).ravel()))))
                return
            if obj.dtype.kind in "biuf" and obj.ndim >= 2:
                datasets.append(obj)

        for k, v in f.attrs.items():
            terms |= collect_terms(v.tolist() if isinstance(v, np.ndarray) else v)
        f.visititems(visit)
        if not datasets:
            raise UnsupportedFormat("MATLAB file holds no numeric image array")
        ds = max(datasets, key=lambda d: d.size)
        # h5py sees MATLAB's column-major arrays with the axes reversed
        amap = _AxisMap(_mat_axes(tuple(ds.shape[::-1]))[::-1], tuple(ds.shape))
        out_shape = amap.shape()
        info = ImageInfo(family="mat", axes=amap.axes, shape=out_shape, dtype=str(ds.dtype),
                         channels=_default_channels(amap.axes, out_shape), levels=1)
    except BaseException:
        f.close()
        raise

    def level0() -> Any:
        chunks = plan_chunks(tuple(ds.shape), ds.dtype.itemsize, native=ds.chunks)
        return amap.apply(_from_array(ds, chunks))

    return _Source(info, terms, [level0], f.close)


# --- OME-Zarr (NGFF 0.4 / Zarr v2, NGFF 0.5 / Zarr v3) ------------------------------------------

NGFF_VERSIONS_KNOWN = frozenset({"0.1", "0.2", "0.3", "0.4", "0.5"})
_NGFF_UNIT: dict[str, PixelUnit] = {"micrometer": "um", "millimeter": "mm", "nanometer": "nm"}


def _ngff_scale(ms: dict, dataset: dict, ndim: int) -> list[float]:
    scale = [1.0] * ndim
    for transforms in (dataset.get("coordinateTransformations") or [],
                       ms.get("coordinateTransformations") or []):
        for t in transforms:
            if t.get("type") == "scale" and len(t.get("scale", [])) == ndim:
                scale = [a * float(b) for a, b in zip(scale, t["scale"])]
    return scale


def _ngff_terms(attrs: dict) -> set[str]:
    """Strings in OME-Zarr attributes that are not NGFF structure (axes, datasets, rendering)."""
    keep: dict[str, Any] = {}
    for key, value in attrs.items():
        if key in ("ome", "multiscales", "omero"):
            continue
        keep[key] = value
    ome = attrs.get("ome") if isinstance(attrs.get("ome"), dict) else attrs
    for ms in ome.get("multiscales") or []:
        if isinstance(ms, dict):
            keep.setdefault("_ms", []).append({k: ms.get(k) for k in ("name", "metadata") if k in ms})
    omero = ome.get("omero")
    if isinstance(omero, dict):
        keep["_omero"] = [omero.get("name")] + [
            {k: c.get(k) for k in ("label", "name")} for c in omero.get("channels") or []
            if isinstance(c, dict)
        ]
    if isinstance(ome, dict) and ome is not attrs:
        keep["_ome"] = {k: v for k, v in ome.items()
                        if k not in ("version", "multiscales", "omero", "bioformats2raw.layout")}
    return collect_terms(keep)


def _open_ome_zarr(location: Any) -> _Source:
    import dask.array as da
    import zarr

    if isinstance(location, str) and "://" not in location:
        location = Path(location)  # a local path: the OME/METADATA.ome.xml check below applies
    store = str(location) if isinstance(location, Path) else location
    root = zarr.open_group(store, mode="r")
    group = root
    attrs = dict(group.attrs)
    ome = attrs.get("ome", attrs)
    if not ome.get("multiscales") and "0" in group:  # bioformats2raw layout: the image is "0"
        group = group["0"]
        attrs = dict(group.attrs)
        ome = attrs.get("ome", attrs)
    multiscales = ome.get("multiscales")
    if not multiscales:
        raise UnsupportedFormat("Zarr store has no OME-NGFF multiscales")
    ms = multiscales[0]
    raw_version = ome.get("version") or ms.get("version")
    version = str(raw_version) if raw_version is not None else None
    terms_extra: set[str] = set()
    if version not in NGFF_VERSIONS_KNOWN:  # an unknown value is free text: a term, not a fact
        terms_extra = collect_terms(version) if version else set()
        version = None
    zarr_format = group.metadata.zarr_format
    axes_meta = ms.get("axes") or ["t", "c", "z", "y", "x"][-len(group[ms["datasets"][0]["path"]].shape):]
    names = "".join((a["name"] if isinstance(a, dict) else a)[0] for a in axes_meta)
    units = [a.get("unit") if isinstance(a, dict) else None for a in axes_meta]
    arrays = [group[d["path"]] for d in ms["datasets"]]
    terms = _ngff_terms(dict(root.attrs)) | (_ngff_terms(attrs) if group is not root else set())
    terms |= terms_extra
    for arr in arrays:
        terms |= collect_terms(dict(arr.attrs))
    a0 = arrays[0]
    amap = _AxisMap(names, tuple(a0.shape))
    scale = _ngff_scale(ms, ms["datasets"][0], a0.ndim)
    lower = names.lower()
    x_unit = units[lower.index("x")] if "x" in lower else None
    unit: PixelUnit = _NGFF_UNIT.get(str(x_unit), "um")
    pixel_size: dict[str, float] = {}
    for axis in "xyz":
        if axis in lower:
            i = lower.index(axis)
            value = convert_length(scale[i], units[i], unit) if units[i] else scale[i]
            if value:
                pixel_size[axis] = value
    out_shape = amap.shape()
    fields: dict[str, Any] = {}
    if isinstance(location, Path):
        xml_path = location / "OME" / "METADATA.ome.xml"
        if xml_path.is_file():
            parsed = _parse_ome(xml_path.read_text(errors="replace"))
            if parsed is not None:
                fields, ome_terms = ome_allowlist(parsed)
                terms |= ome_terms
    channels = fields.get("channels")
    if not channels or ("c" in amap.axes and len(channels) != out_shape[amap.axes.index("c")]):
        channels = _default_channels(amap.axes, out_shape)
    if fields.get("acquired"):
        terms |= date_terms(fields["acquired"])
    info = ImageInfo(
        family="ome-zarr", axes=amap.axes, shape=out_shape, dtype=str(a0.dtype),
        pixel_size=pixel_size, pixel_unit=unit, channels=channels, levels=len(arrays),
        zarr_format=zarr_format, ngff_version=version,
        objective_magnification=fields.get("objective_magnification"),
        objective_na=fields.get("objective_na"), immersion=fields.get("immersion"),
        acquisition_mode=fields.get("acquisition_mode"), acquired=fields.get("acquired"),
    )

    def level(i: int) -> Any:
        arr = arrays[i]
        lvl_map = _AxisMap(names, tuple(arr.shape))
        chunks = plan_chunks(tuple(arr.shape), arr.dtype.itemsize, native=tuple(arr.chunks))
        return lvl_map.apply(da.from_zarr(arr, chunks=chunks))

    out = _Source(info, terms, [lambda i=i: level(i) for i in range(len(arrays))])
    omero = ome.get("omero") if isinstance(ome, dict) else None
    # what a reference dataset needs (micr/reference.py): the image group's path in the store, each
    # level's dataset path, opened array and scale, whether the source axes are already the image's
    # (no squeeze or transpose), and the source's display windows (numbers only)
    out.zarr_layout = ZarrLayout(
        group_path=group.path, datasets=[str(d["path"]) for d in ms["datasets"]], arrays=arrays,
        scales=[_ngff_scale(ms, d, len(axes_meta)) for d in ms["datasets"]],
        identity=(amap.perm == tuple(range(len(amap.perm))) and all(isinstance(ix, slice) for ix in amap.index)
                  and len(amap.axes) == a0.ndim),
        windows=_omero_windows(omero),
    )
    return out


@dataclass
class ZarrLayout:
    group_path: str
    datasets: list[str]
    arrays: list[Any]
    scales: list[list[float]]
    identity: bool
    windows: list[dict[str, float] | None]


def _omero_windows(omero: Any) -> list[dict[str, float] | None]:
    """Per channel, the source's omero window as four finite numbers, else None. Nothing else is kept."""
    out: list[dict[str, float] | None] = []
    channels = omero.get("channels") if isinstance(omero, dict) else None
    for ch in channels if isinstance(channels, list) else []:
        w = ch.get("window") if isinstance(ch, dict) else None
        vals = {k: w.get(k) for k in ("min", "max", "start", "end")} if isinstance(w, dict) else {}
        ok = len(vals) == 4 and all(isinstance(v, (int, float)) and not isinstance(v, bool)
                                    and math.isfinite(v) for v in vals.values())
        out.append({k: float(v) for k, v in vals.items()} if ok else None)
    return out


# --- registry ---------------------------------------------------------------------------------

Opener = Callable[[Any], ImageSource]

_BUILTIN: dict[str, Opener] = {
    "tiff": lambda loc: _open_tiff(loc, "tiff"),
    "ome-tiff": lambda loc: _open_tiff(loc, "ome-tiff"),
    "svs": lambda loc: _open_tiff(loc, "svs"),
    "czi": lambda loc: _open_bioio(loc, "czi"),
    "nd2": lambda loc: _open_bioio(loc, "nd2"),
    "lif": lambda loc: _open_bioio(loc, "lif"),
    "nifti": _open_nifti,
    "mat": _open_mat,
    "ome-zarr": _open_ome_zarr,
    "visor": _open_visor,
}
_ADAPTERS: dict[str, Opener] = {}
_entry_points_loaded = False


def register_reader(family: str, opener: Callable[[str | Path], ImageSource]) -> None:
    """Register a per-lab reader for ``family``; it takes precedence over the built-in one.

    Packages can do the same through the ``aimport.micr_readers`` entry-point group
    (name = family, value = the opener).
    """
    _ADAPTERS[family.lower()] = opener


def _load_entry_points() -> None:
    global _entry_points_loaded
    if _entry_points_loaded:
        return
    _entry_points_loaded = True
    for ep in entry_points(group=ENTRY_POINT_GROUP):
        try:
            _ADAPTERS.setdefault(ep.name.lower(), ep.load())
        except Exception as exc:  # noqa: BLE001 - a broken adapter must not stop the import
            log.warning("micr reader entry point %r failed to load: %s", ep.name, type(exc).__name__)


def open_image(location: str | Path, family: str) -> ImageSource:
    """Open a microscopy image of ``family`` (a ``discover.FAMILIES`` value, or ``visor``)."""
    _load_entry_points()
    fam = family.lower()
    if fam in _ADAPTERS:
        return _ADAPTERS[fam](location)
    if fam == "unsupported":
        raise UnsupportedFormat(BIOFORMATS_MESSAGE)
    if fam == "raw-psoct":
        raise UnsupportedFormat("raw PS-OCT tiles are not reconstructed images: reconstruct them first")
    opener = _BUILTIN.get(fam)
    if opener is None:
        raise UnsupportedFormat(f"no reader for {family!r}")
    return opener(location)
