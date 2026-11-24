"""Reference datasets: an OME-Zarr input is not copied.

aimport writes only new metadata for it under ``bids/`` (the NGFF group attributes rebuilt from
``ImageInfo``, and each array's ``zarr.json`` or ``.zarray`` rebuilt from its structure, without
``attributes``), plus a **chunk map** that says where each array's chunks are. The chunks stay at
the source (a folder in the input, or an https URL) and are streamed later by the upload and the QA
viewer. The source's Zarr format, chunk grid and codecs are kept, so a chunk key under an array is
the same in the source and the output.

The chunk map is per array prefix (a terabyte store would otherwise give millions of lines)::

    {"version": 1, "arrays": {"<out rel array dir>": {
        "source": {"input": "<input-relative dir>"} | {"url": "<https URL>"},
        "zarr_format": 2 | 3, "shape": [...], "chunk_grid": [...], "separator": "/" | ".",
        "codec_bytes_hint": int}}}

``chunk_grid`` is the shape of one stored object (the shard for a sharded Zarr v3 array, else the
chunk); ``codec_bytes_hint`` is that object's decoded size in bytes (an upper bound for buffers,
not its stored size). A Zarr v3 array whose chunk keys use the ``v2`` encoding also has
``"key_encoding": "v2"`` (keys without the ``c`` prefix). The map holds input paths and URLs, so it
lives at ``<work>/output/bids.chunks.json`` (never under ``bids/``) and is never uploaded.
``resolve`` is the one resolver of an output chunk path to its source, shared by the engine and the
viewer.
"""
from __future__ import annotations

import itertools
import json
import math
import re
from pathlib import Path
from typing import Any, Iterator, Mapping
from urllib.parse import unquote, urlsplit

import numpy as np

from .metadata import ImageInfo, channel_count, ngff_attrs

CHUNK_MAP_VERSION = 1
CHUNK_MAP_NAME = "bids.chunks.json"  # in <work>/output/, next to bids/
SEPARATORS = ("/", ".")
_INDEX = re.compile(r"0|[1-9][0-9]*")
_V3_KEYS = ("zarr_format", "node_type", "shape", "data_type", "chunk_grid", "chunk_key_encoding",
            "fill_value", "codecs")
_V2_KEYS = ("zarr_format", "shape", "chunks", "dtype", "compressor", "fill_value", "order", "filters",
            "dimension_separator")


class ReferenceRefused(ValueError):
    """An OME-Zarr input that cannot be referenced as is (its chunks would have to be re-encoded)."""


def ngff_version_for(zarr_format: int | None) -> str:
    """A reference keeps its source's Zarr format: v3 is written as NGFF 0.5, v2 as 0.4."""
    if zarr_format == 3:
        return "0.5"
    if zarr_format == 2:
        return "0.4"
    raise ReferenceRefused("the OME-Zarr input has no known Zarr format")


def _segments(path: str) -> list[str]:
    """The segments of a relative posix path; ValueError for an absolute path, or a segment that is
    '.', '..' (also percent-encoded) or empty."""
    if not isinstance(path, str) or not path or path.startswith("/") or "\\" in path or "\x00" in path:
        raise ValueError("not a relative path")
    parts = path.split("/")
    if any(p in ("", ".", "..") or unquote(p) in (".", "..") for p in parts):  # also %2e%2e
        raise ValueError("not a plain relative path")
    return parts


def _join(*parts: str) -> str:
    return "/".join(p for p in parts if p)


# --- writing ------------------------------------------------------------------------------------


def _metadata_doc(arr: Any) -> dict:
    """The array's metadata document as zarr itself would write it (fill values encoded)."""
    from zarr.core.buffer import default_buffer_prototype

    bufs = arr.metadata.to_buffer_dict(default_buffer_prototype())
    name = "zarr.json" if arr.metadata.zarr_format == 3 else ".zarray"
    return json.loads(bufs[name].to_bytes())


def _rebuild(arr: Any, axes: str) -> tuple[dict, dict]:
    """(the rebuilt metadata document, the chunk-map facts) of one source array. Only structure is
    kept: shape, data type, chunk grid, key encoding, codecs or compressor and filters, fill value,
    order; dimension names are the image's axes. ``attributes`` are dropped."""
    doc = _metadata_doc(arr)
    shape = [int(n) for n in doc["shape"]]
    if len(shape) != len(axes):
        raise ReferenceRefused("an OME-Zarr array does not have the image's axes")
    itemsize = int(np.dtype(arr.dtype).itemsize)
    facts: dict[str, Any] = {"zarr_format": int(doc["zarr_format"]), "shape": shape}
    if doc["zarr_format"] == 3:
        if doc.get("storage_transformers"):
            raise ReferenceRefused("an OME-Zarr array uses storage transformers")
        grid = doc.get("chunk_grid") or {}
        enc = doc.get("chunk_key_encoding") or {}
        if grid.get("name") != "regular" or enc.get("name") not in ("default", "v2"):
            raise ReferenceRefused("an OME-Zarr array has an irregular chunk grid or key encoding")
        chunk = [int(n) for n in grid["configuration"]["chunk_shape"]]
        sep = (enc.get("configuration") or {}).get("separator") or ("/" if enc["name"] == "default" else ".")
        out = {k: doc[k] for k in _V3_KEYS if k in doc}
        out["dimension_names"] = list(axes)
        if enc["name"] == "v2":
            facts["key_encoding"] = "v2"
    else:
        chunk = [int(n) for n in doc["chunks"]]
        sep = doc.get("dimension_separator") or "."
        out = {k: doc[k] for k in _V2_KEYS if k in doc}
        out["dimension_separator"] = sep
    if sep not in SEPARATORS or len(chunk) != len(shape) or any(c <= 0 for c in chunk):
        raise ReferenceRefused("an OME-Zarr array has an unknown chunk layout")
    facts.update(chunk_grid=chunk, separator=sep, codec_bytes_hint=itemsize * math.prod(chunk))
    return out, facts


def _factor(base: int, n: int, ratio: float) -> float:
    """The downsampling factor of one axis of a level: the source's scale ratio when the level's
    size agrees with it, else the whole factor (a power of two first) that gives the level's size
    from level 0's, rounded down or up. Source pyramids carry wrong scales (a PS-OCT store says 16
    for a level halved three times), and the size is what the chunks hold. Else the ratio as is,
    which the self-check refuses."""
    def fits(f: int) -> bool:
        return f >= 1 and n in (base // f, -(-base // f))

    whole = int(round(ratio))
    candidates = ([whole] if math.isclose(ratio, whole, rel_tol=1e-6) else []) + [2**k for k in range(40)]
    if n > 0:
        candidates.append(int(round(base / n)))
    for f in candidates:
        if fits(f):
            return f
    return ratio


def _levels(info: ImageInfo, layout: Any) -> list[dict[str, float]]:
    """Per level, the downsampling factor of each spatial axis (see _factor)."""
    base, scales = layout.arrays[0].shape, layout.scales
    out = []
    for arr, scale in zip(layout.arrays, scales):
        factors: dict[str, float] = {}
        for k, a in enumerate(info.axes):
            if a in "zyx":
                ratio = scale[k] / scales[0][k] if scales[0][k] > 0 else 1.0
                factors[a] = _factor(int(base[k]), int(arr.shape[k]), ratio)
        out.append(factors)
    return out


def _windows(info: ImageInfo, source: list) -> list[dict[str, float]]:
    """The source's display windows (numbers only) when there is one per channel; else the dtype's
    range (no chunk is read for a reference)."""
    n = channel_count(info)
    if len(source) == n and all(source):
        return list(source)
    dt = np.dtype(info.dtype)
    lo, hi = (float(np.iinfo(dt).min), float(np.iinfo(dt).max)) if dt.kind in "iu" else (0.0, 1.0)
    return [{"min": lo, "max": hi, "start": lo, "end": hi}] * n


def write_reference(src: Any, location: Mapping[str, str], dest: Path, info: ImageInfo) -> dict:
    """Write the metadata of a reference dataset at ``dest`` (no chunk bytes) and return the
    ``arrays`` part of its chunk map, keyed by the array's path under ``dest`` (``"0"``, ``"1"``, ...).

    ``src`` is the OME-Zarr ``ImageSource`` (readers); ``location`` the store's source,
    ``{"input": <input-relative store dir>}`` or ``{"url": <https URL of the store>}``; ``info`` the
    image facts with the plan's pixel size (metadata.with_plan_pixel_size). The group attributes are
    ``metadata.ngff_attrs`` in the source's format (Zarr v3 → NGFF 0.5, v2 → 0.4).
    """
    from .convert import _write_group

    layout = getattr(src, "zarr_layout", None)
    if layout is None:
        raise ReferenceRefused("only an OME-Zarr input can be referenced")
    if not layout.identity:
        raise ReferenceRefused("the OME-Zarr axes are not t, c, z, y, x in order: convert it instead")
    if set(location) == {"input"}:
        kind, base = "input", location["input"]
        _segments(base)
    elif set(location) == {"url"}:
        from .remote import normalize_url

        kind, base = "url", normalize_url(location["url"])
    else:
        raise ValueError("a reference source is {'input': dir} or {'url': URL}")
    version = ngff_version_for(info.zarr_format)
    attrs = ngff_attrs(info, version, _levels(info, layout), _windows(info, layout.windows))
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    if any(dest.iterdir()):
        raise FileExistsError("the reference image's folder is not empty")
    _write_group(dest, version, attrs)
    arrays: dict[str, dict] = {}
    for i, (path, arr) in enumerate(zip(layout.datasets, layout.arrays)):
        sub = _join(*_segments(_join(layout.group_path, path)))
        doc, facts = _rebuild(arr, info.axes)
        if facts["zarr_format"] != info.zarr_format:
            raise ReferenceRefused("the OME-Zarr arrays do not share the group's Zarr format")
        out_dir = dest / str(i)
        out_dir.mkdir()
        (out_dir / ("zarr.json" if facts["zarr_format"] == 3 else ".zarray")).write_text(
            json.dumps(doc, indent=2), encoding="utf-8")
        arrays[str(i)] = {"source": {kind: f"{base}/{sub}"}, **facts}
    return arrays


def chunk_map(arrays: Mapping[str, dict]) -> dict:
    return {"version": CHUNK_MAP_VERSION, "arrays": dict(arrays)}


def write_chunk_map(path: Path, arrays: Mapping[str, dict]) -> None:
    Path(path).write_text(json.dumps(chunk_map(arrays), indent=1, sort_keys=True), encoding="utf-8")


def load_chunk_map(path: Path) -> dict | None:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) and data.get("version") == CHUNK_MAP_VERSION else None


# --- chunk keys and resolving -------------------------------------------------------------------


def _counts(meta: Mapping[str, Any]) -> list[int]:
    shape, grid = meta["shape"], meta["chunk_grid"]
    if len(shape) != len(grid) or any(not isinstance(g, int) or g <= 0 for g in grid):
        raise ValueError("the chunk map entry has no valid chunk grid")
    return [-(-int(s) // int(g)) for s, g in zip(shape, grid)]


def _prefixed(meta: Mapping[str, Any]) -> bool:
    return meta.get("zarr_format") == 3 and meta.get("key_encoding", "default") == "default"


def _separator(meta: Mapping[str, Any]) -> str:
    sep = meta.get("separator")
    if sep not in SEPARATORS:
        raise ValueError("the chunk map entry has no valid separator")
    return sep


def chunk_keys(array_meta: Mapping[str, Any]) -> Iterator[str]:
    """Every chunk (or shard) key of an array, from its shape and grid: Zarr v2 ``0.0.0``/``0/0/0``,
    Zarr v3 ``c/0/0/0`` (or ``c.0.0.0``). A key with no source object is the fill value: consumers
    skip it."""
    sep, prefixed = _separator(array_meta), _prefixed(array_meta)
    for idx in itertools.product(*(range(n) for n in _counts(array_meta))):
        body = sep.join(str(i) for i in idx)
        if prefixed:
            yield "c" + (sep + body if idx else "")
        else:
            yield body if idx else "0"


def key_ok(array_meta: Mapping[str, Any], key: str) -> bool:
    """Whether key is one of ``chunk_keys(array_meta)`` (digits and separators only), without
    enumerating them."""
    sep, counts = _separator(array_meta), _counts(array_meta)
    if not isinstance(key, str):
        return False
    if _prefixed(array_meta):
        if not key.startswith("c"):
            return False
        key = key[1:]
        if not counts:
            return key == ""
        if not key.startswith(sep):
            return False
        key = key[1:]
    elif not counts:
        return key == "0"
    parts = key.split(sep)
    return len(parts) == len(counts) and all(
        _INDEX.fullmatch(p) is not None and int(p) < n for p, n in zip(parts, counts))


def _array_of(chunks: Mapping[str, Any], out_rel: str) -> tuple[str, dict, str]:
    arrays = chunks.get("arrays") if isinstance(chunks, Mapping) else None
    if not isinstance(arrays, Mapping):
        raise ValueError("not a chunk map")
    _segments(out_rel)
    best = None
    for prefix, meta in arrays.items():
        if isinstance(prefix, str) and out_rel.startswith(prefix + "/") and (best is None or len(prefix) > len(best[0])):
            best = (prefix, meta)
    if best is None or not isinstance(best[1], Mapping):
        raise ValueError("the path is not inside a referenced array")
    _segments(best[0])
    return best[0], dict(best[1]), out_rel[len(best[0]) + 1:]


def resolve(chunks: Mapping[str, Any], out_rel: str, input_dir: Path) -> Path | str:
    """The source of an output chunk path (relative to the BIDS folder): a Path inside
    ``input_dir`` or an https URL. ValueError when the path is not strictly inside a mapped array,
    the key is not a chunk key of that array, an input source leaves ``input_dir`` or goes through a
    symlink, or a URL is refused by ``remote.normalize_url``."""
    _prefix, meta, key = _array_of(chunks, out_rel)
    if not key_ok(meta, key):
        raise ValueError("not a chunk key of the referenced array")
    source = meta.get("source")
    if not isinstance(source, Mapping) or len(source) != 1:
        raise ValueError("the chunk map entry has no valid source")
    if "input" in source:
        root = Path(input_dir).resolve()
        path = root
        for seg in [*_segments(source["input"]), *key.split("/")]:
            path = path / seg
            if path.is_symlink():
                raise ValueError("a referenced source goes through a symlink")
        if root not in path.resolve().parents:
            raise ValueError("a referenced source lies outside the input folder")
        return path
    if "url" in source:
        from .remote import normalize_url

        url = normalize_url(source["url"])
        if any(unquote(seg) in (".", "..") for seg in urlsplit(url).path.split("/")):
            raise ValueError("a referenced URL has a relative or encoded path segment")
        return f"{url}/{key}"
    raise ValueError("the chunk map entry has no valid source")

