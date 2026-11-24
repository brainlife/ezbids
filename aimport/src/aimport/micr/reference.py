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
import unicodedata
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


# --- what can be referenced: one predicate, used at planning (records) and at execute -----------

NOT_REFERENCEABLE = "OME-Zarr layout not referenceable: "
LAYOUT_UNKNOWN = "OME-Zarr layout not recorded: scan again"
KEY_ENCODINGS = ("default", "v2")


def _array_facts(doc: Mapping[str, Any]) -> dict[str, Any]:
    """The layout facts of one array metadata document (zarr's serialisation)."""
    if doc.get("zarr_format") == 3:
        enc = doc.get("chunk_key_encoding") or {}
        name = enc.get("name")
        sep = (enc.get("configuration") or {}).get("separator") or ("/" if name == "default" else ".")
        return {"zarr_format": 3, "grid": (doc.get("chunk_grid") or {}).get("name"), "key_encoding": name,
                "separator": sep, "storage_transformers": bool(doc.get("storage_transformers"))}
    return {"zarr_format": doc.get("zarr_format"), "grid": "regular", "key_encoding": "v2",
            "separator": doc.get("dimension_separator") or ".", "storage_transformers": False}


def _facts_of(arrays: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "zarr_formats": sorted({a["zarr_format"] for a in arrays}, key=str),
        "grids": sorted({str(a["grid"]) for a in arrays}),
        "key_encodings": sorted({str(a["key_encoding"]) for a in arrays}),
        "separators": sorted({str(a["separator"]) for a in arrays}),
        "storage_transformers": any(a["storage_transformers"] for a in arrays),
    }


def symlinked(root: Path, rel: str, subpaths: Any = ()) -> bool:
    """Whether a segment of ``root/rel`` or of ``root/rel/<subpath>`` (an array dir) is a symlink."""
    def walk(start: Path, segs: list[str]) -> bool:
        p = start
        for seg in segs:
            p = p / seg
            if p.is_symlink():
                return True
        return False

    try:
        segs = _segments(rel)
    except ValueError:
        return True
    if walk(Path(root), segs):
        return True
    store = Path(root).joinpath(*segs)
    for sub in subpaths:
        try:
            if walk(store, _segments(sub)):
                return True
        except ValueError:
            continue  # refused as a dataset path (paths_ok)
    return False


def dataset_dirs(layout: Any) -> list[str]:
    """Each level's array dir in the store (group path + dataset path), unchecked."""
    return [_join(layout.group_path, p) for p in layout.datasets]


def layout_facts(layout: Any, group_format: int | None, symlink: bool = False) -> dict[str, Any]:
    """The facts layout_refusal decides on (JSON, kept in the scan records): axis identity, each
    array's Zarr format (with the group's), chunk grid, key encoding, separator and storage
    transformers, whether the dataset paths are plain relative paths, and whether the store is
    reached through a symlink."""
    arrays = [_array_facts(_metadata_doc(a)) for a in layout.arrays]
    facts = _facts_of(arrays)
    facts["zarr_formats"] = sorted({group_format, *facts["zarr_formats"]}, key=str)
    paths_ok = True
    for sub in dataset_dirs(layout):
        try:
            _segments(sub)
        except ValueError:
            paths_ok = False
    return {"axes_identity": bool(layout.identity), **facts, "paths_ok": paths_ok, "symlink": bool(symlink)}


def layout_refusal(facts: Mapping[str, Any] | None) -> str | None:
    """Why an OME-Zarr cannot be referenced as is (its chunks would need re-encoding, or its path is
    unsafe), or None. Shared by the planner (unsupported entry) and write_reference (refusal)."""
    if not isinstance(facts, Mapping):
        return LAYOUT_UNKNOWN
    if facts.get("symlink"):
        return NOT_REFERENCEABLE + "the store is reached through a symlink"
    if not facts.get("axes_identity"):
        return NOT_REFERENCEABLE + "axes need reordering"
    if not facts.get("paths_ok"):
        return NOT_REFERENCEABLE + "a dataset path leaves the store"
    formats = facts.get("zarr_formats") or []
    if len(formats) != 1 or formats[0] not in (2, 3):
        return NOT_REFERENCEABLE + "arrays mix Zarr formats"
    if facts.get("storage_transformers"):
        return NOT_REFERENCEABLE + "storage transformers"
    if facts.get("grids") != ["regular"]:
        return NOT_REFERENCEABLE + "irregular chunk grid"
    if not set(facts.get("key_encodings") or ["?"]) <= set(KEY_ENCODINGS):
        return NOT_REFERENCEABLE + "unknown chunk key encoding"
    if not set(facts.get("separators") or ["?"]) <= set(SEPARATORS):
        return NOT_REFERENCEABLE + "unknown chunk key separator"
    return None


def _rebuild(arr: Any, axes: str) -> tuple[dict, dict]:
    """(the rebuilt metadata document, the chunk-map facts) of one source array. Only structure is
    kept: shape, data type, chunk grid, key encoding, codecs or compressor and filters, fill value,
    order; dimension names are the image's axes. ``attributes`` are dropped. The store passed
    layout_refusal; this array is refused by it again here (defence in depth)."""
    doc = _metadata_doc(arr)
    a = _array_facts(doc)
    reason = layout_refusal({**_facts_of([a]), "axes_identity": True, "paths_ok": True})
    if reason:
        raise ReferenceRefused(reason)
    shape = [int(n) for n in doc["shape"]]
    if len(shape) != len(axes):
        raise ReferenceRefused(NOT_REFERENCEABLE + "axes need reordering")
    itemsize = int(np.dtype(arr.dtype).itemsize)
    facts: dict[str, Any] = {"zarr_format": int(doc["zarr_format"]), "shape": shape}
    sep = a["separator"]
    if doc["zarr_format"] == 3:
        chunk = [int(n) for n in doc["chunk_grid"]["configuration"]["chunk_shape"]]
        out = {k: doc[k] for k in _V3_KEYS if k in doc}
        out["dimension_names"] = list(axes)
        if a["key_encoding"] == "v2":
            facts["key_encoding"] = "v2"
    else:
        chunk = [int(n) for n in doc["chunks"]]
        out = {k: doc[k] for k in _V2_KEYS if k in doc}
        out["dimension_separator"] = sep
    if len(chunk) != len(shape) or any(c <= 0 for c in chunk):
        raise ReferenceRefused(NOT_REFERENCEABLE + "irregular chunk grid")
    facts.update(chunk_grid=chunk, separator=sep, codec_bytes_hint=itemsize * math.prod(chunk))
    return out, facts


# --- the term scan of what was written ----------------------------------------------------------

_GENERATED = re.compile(r"ch\d+|[0-9A-F]{6}")  # omero labels and colours that ngff_attrs generates
_METADATA_NAMES = ("zarr.json", ".zarray", ".zattrs", ".zgroup")
TERM_REFUSED = "OME-Zarr metadata not referenceable: it holds identifying text"


def _squash(text: str) -> str:
    folded = unicodedata.normalize("NFKD", text).casefold()
    return "".join(ch for ch in folded if ch.isalnum())


def _strings(obj: Any) -> Iterator[str]:
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield str(k)
            yield from _strings(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _strings(v)


def check_terms(dest: Path, terms: Any) -> None:
    """Refuse (ReferenceRefused, a generic message) when a string in a metadata document under
    ``dest`` (keys, codec and filter configurations, string fill values ...) holds a run term,
    compared case-insensitively with separators squashed (casefold, alphanumerics only).
    Generated omero labels (``ch<n>``) and colours are exempt. Terms shorter than 3 characters,
    and numbers shorter than ancillary.PATH_NUMERIC_MIN digits, are not checked (they would match
    generated vocabulary)."""
    from ..ancillary import PATH_NUMERIC_MIN

    wanted = set()
    for t in terms or ():
        sq = _squash(str(t))
        if len(sq) >= 3 and not (sq.isdigit() and len(sq) < PATH_NUMERIC_MIN):
            wanted.add(sq)
    if not wanted:
        return
    for p in sorted(Path(dest).rglob("*")):
        if not p.is_file() or p.name not in _METADATA_NAMES:
            continue
        try:
            doc = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ReferenceRefused(TERM_REFUSED) from exc
        for text in _strings(doc):
            if _GENERATED.fullmatch(text):
                continue
            sq = _squash(text)
            if any(t in sq for t in wanted):
                raise ReferenceRefused(TERM_REFUSED)


def _factor(base: int, n: int, ratio: float) -> float:
    """The downsampling factor of one axis of a level: the source's scale ratio when the level's
    size agrees with it, else the whole factor (level 0's size over the level's, then a power of
    two) that gives the level's size from level 0's, rounded down or up. Source pyramids carry wrong scales (a PS-OCT store says 16
    for a level halved three times), and the size is what the chunks hold. Else the ratio as is,
    which the self-check refuses."""
    def fits(f: int) -> bool:
        return f >= 1 and n in (base // f, -(-base // f))

    whole = int(round(ratio))
    candidates = [whole] if math.isclose(ratio, whole, rel_tol=1e-6) else []
    if n > 0:
        candidates += [base // n, int(round(base / n))]
    candidates += [2**k for k in range(40)]
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


def source_factors(info: ImageInfo, layout: Any) -> list[dict[str, int]]:
    """Per level, the spatial factors the source's own scales declare, for the axes where the
    declared factor is whole and agrees with the level's size: what the written scales must equal
    (times the plan's level-0 pixel size), independently of the fitting in _levels."""
    base, scales = layout.arrays[0].shape, layout.scales
    out = []
    for arr, scale in zip(layout.arrays, scales):
        known: dict[str, int] = {}
        for k, a in enumerate(info.axes):
            if a in "zyx" and scales[0][k] > 0:
                ratio = scale[k] / scales[0][k]
                f = int(round(ratio))
                if f >= 1 and math.isclose(ratio, f, rel_tol=1e-6) and \
                        int(arr.shape[k]) in (int(base[k]) // f, -(-int(base[k]) // f)):
                    known[a] = f
        out.append(known)
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


def write_reference(src: Any, location: Mapping[str, str], dest: Path, info: ImageInfo,
                    terms: Any = (), symlink: bool = False) -> dict:
    """Write the metadata of a reference dataset at ``dest`` (no chunk bytes) and return the
    ``arrays`` part of its chunk map, keyed by the array's path under ``dest`` (``"0"``, ``"1"``, ...).

    ``src`` is the OME-Zarr ``ImageSource`` (readers); ``location`` the store's source,
    ``{"input": <input-relative store dir>}`` or ``{"url": <https URL of the store>}``; ``info`` the
    image facts with the plan's pixel size (metadata.with_plan_pixel_size). The group attributes are
    ``metadata.ngff_attrs`` in the source's format (Zarr v3 → NGFF 0.5, v2 → 0.4). ``symlink``:
    whether the store is reached through a symlink (``symlinked``). The layout is refused by
    ``layout_refusal`` as at planning, and the written metadata by ``check_terms(terms)``.
    """
    from .convert import _write_group

    layout = getattr(src, "zarr_layout", None)
    if layout is None:
        raise ReferenceRefused("only an OME-Zarr input can be referenced")
    reason = layout_refusal(layout_facts(layout, info.zarr_format, symlink))
    if reason:
        raise ReferenceRefused(reason)
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
            raise ReferenceRefused(NOT_REFERENCEABLE + "arrays mix Zarr formats")
        out_dir = dest / str(i)
        out_dir.mkdir()
        (out_dir / ("zarr.json" if facts["zarr_format"] == 3 else ".zarray")).write_text(
            json.dumps(doc, indent=2), encoding="utf-8")
        arrays[str(i)] = {"source": {kind: f"{base}/{sub}"}, **facts}
    check_terms(dest, terms)
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

