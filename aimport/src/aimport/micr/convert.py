"""Streaming conversion of a microscopy image to OME-Zarr, and the self-check of what was written.

``to_ome_zarr`` reads the source block by block (each block bounded by ``MAX_BLOCK_BYTES``, read at
call time): level 0 is written shard by shard from slices of ``src.level(0)`` computed on the
synchronous scheduler (dask fuses each slice into the source's own reads), and level k is the bin
shrink of level k-1 as written, read back in slabs. A whole array is never materialised. Each level
is written by ngff-zarr (``to_multiscales`` + ``to_ngff_zarr``, sharded for 0.5) and moved to
``<dest>/<k>`` with empty attributes; the group attributes are then rebuilt by
``metadata.ngff_attrs`` (ImageInfo only), so nothing from ngff-zarr's defaults or the source survives.

``check_ome_zarr`` re-opens a written store (zarr and ngff-zarr) and checks it against the sidecar:
the validator treats ``.ome.zarr`` as opaque, so aimport validates its own output. A failure raises
``NgffCheckError`` with a generic message (never a path).
"""
from __future__ import annotations

import itertools
import json
import math
import os
import shutil
from collections import OrderedDict
from pathlib import Path
from typing import Any, Callable, Sequence

import numpy as np

from .. import micr
from .metadata import AXES_ORDER, NGFF_UNITS, SPATIAL, ImageInfo, channel_count, ngff_attrs, pixel_sizes

__all__ = ["NgffCheckError", "check_ome_zarr", "pyramid_levels", "stack_sources", "to_ome_zarr",
           "write_layout"]

CHUNKS_PER_SHARD = 4  # per spatial axis (NGFF 0.5 only; 0.4 / Zarr v2 has no sharding)
DEFAULT_CHUNK_3D = 128
DEFAULT_CHUNK_2D = 1024
PYRAMID_MAX_SIDE = 512  # the coarsest level's largest spatial axis
PYRAMID_MAX_LEVELS = 8
WINDOW_SAMPLES = 2**20  # values per channel read from the coarsest level for the display window
WINDOW_PERCENTILES = (0.5, 99.5)
_METADATA_NAMES = frozenset({"zarr.json", ".zgroup", ".zattrs", ".zarray", ".zmetadata"})


class NgffCheckError(RuntimeError):
    """A written OME-Zarr failed aimport's own check. The message is generic: no path, no value."""


# --- layout -------------------------------------------------------------------------------------


def write_layout(info: ImageInfo, version: str, limit: int | None = None) -> tuple[dict[str, int], dict[str, int]]:
    """(chunks, chunks per shard) per axis.

    Chunks: 1 for c and t; spatial 128 (3D) or 1024 (2D) per axis. Shards (NGFF 0.5 only; Zarr v2
    has none): 4 chunks per spatial axis. A shard (0.5) or a chunk (0.4) is written whole, so it must
    fit half the block limit (conversion holds a shard and its source blocks at once): first the
    chunks per shard are halved (z first, then the axis with the most), then the chunks themselves.
    """
    limit = int(micr.MAX_BLOCK_BYTES) if limit is None else int(limit)
    budget = max(1, limit // 2)
    itemsize = np.dtype(info.dtype).itemsize
    spatial = [a for a in info.axes if a in SPATIAL]
    side = DEFAULT_CHUNK_3D if len(spatial) == 3 else DEFAULT_CHUNK_2D
    shape = dict(zip(info.axes, info.shape))
    chunks = {a: (min(side, max(1, int(shape[a]))) if a in SPATIAL else 1) for a in info.axes}
    per_shard = {a: (CHUNKS_PER_SHARD if version == "0.5" else 1) for a in spatial}

    def nbytes() -> int:
        return itemsize * math.prod(chunks.values()) * math.prod(per_shard.values())

    while nbytes() > budget and any(n > 1 for n in per_shard.values()):
        a = "z" if per_shard.get("z", 1) > 1 else max(per_shard, key=lambda k: per_shard[k])
        per_shard[a] //= 2
    while nbytes() > budget and any(chunks[a] > 1 for a in spatial):
        big = max(spatial, key=lambda a: chunks[a])
        chunks[big] = max(1, chunks[big] // 2)
    # level 0 is written in slabs along the slowest spatial axis, full extent on the others, so each
    # source block (strips, planes) is read once: a slab is one shard deep. When a full-extent slab
    # does not fit the budget, the shard (then the chunk, down to an eighth of the default) gets
    # thinner along that axis, but only if that makes it fit; otherwise the defaults stay and level 0
    # goes shard by shard.
    lead, rest = spatial[0], spatial[1:]
    row = itemsize * math.prod(int(shape[a]) for a in rest)
    floor = max(1, side // 8)
    if row * min(chunks[lead], floor) <= budget < row * chunks[lead] * per_shard[lead]:
        while row * chunks[lead] * per_shard[lead] > budget and per_shard[lead] > 1:
            per_shard[lead] //= 2
        while row * chunks[lead] > budget and chunks[lead] > floor:
            chunks[lead] //= 2
    return chunks, per_shard


def level0_slab(info: ImageInfo, grid: tuple[int, ...], budget: int,
                source: tuple[tuple[int, ...], ...] | None = None) -> tuple[tuple[int, ...], bool]:
    """(blocks level 0 is written in, whether they cut through shards).

    Preferred: one shard deep along the first spatial axis and the full extent along the others, so
    each block is whole shards and the source (strips, plane stacks) is read once in order. When that
    does not fit the budget but one full-extent slice does, the blocks are full-extent slabs as deep
    as the budget and the source's own blocks allow: each source block is still read once, and the
    shards they cut through are completed by later slabs (read, merged, rewritten). When even one
    slice is larger than the budget, level 0 goes shard by shard (a source block may then be read
    again for each shard it overlaps)."""
    itemsize = np.dtype(info.dtype).itemsize
    spatial = [i for i, a in enumerate(info.axes) if a in SPATIAL]
    lead = spatial[0]
    full = list(grid)
    for i in spatial[1:]:
        full[i] = int(info.shape[i])
    slice_bytes = itemsize * math.prod(min(s, int(n)) for i, (s, n) in enumerate(zip(full, info.shape))
                                       if i != lead)
    if slice_bytes * min(grid[lead], int(info.shape[lead])) <= budget:
        return tuple(full), False
    if slice_bytes <= budget:
        depth = budget // slice_bytes
        if source is not None:
            depth = min(depth, max(int(c) for c in source[lead]))
        full[lead] = max(1, depth)
        return tuple(full), True
    return tuple(grid), False


def pyramid_levels(info: ImageInfo) -> list[dict[str, int]]:
    """Absolute downsampling factors per level, level 0 included (``{}``), down to the level whose
    largest spatial axis is at most 512, with at most 8 levels. y and x halve every level; z halves
    only while its pixels are not coarser than the in-plane ones (anisotropic stacks keep their z)."""
    size = pixel_sizes(info)
    shape = {a: int(n) for a, n in zip(info.axes, info.shape) if a in SPATIAL}
    if not shape:
        return [{}]
    factors = {a: 1 for a in shape}
    levels: list[dict[str, int]] = [{}]
    while len(levels) < PYRAMID_MAX_LEVELS and max(shape[a] // factors[a] for a in shape) > PYRAMID_MAX_SIDE:
        plane = max(size[a] * factors[a] for a in shape if a != "z")
        nxt = dict(factors)
        for a in shape:
            if shape[a] // factors[a] < 2:
                continue
            if a == "z" and size[a] * factors[a] > plane:
                continue
            nxt[a] = factors[a] * 2
        if nxt == factors:
            break
        factors = nxt
        levels.append(dict(factors))
    return levels


# --- block reading ------------------------------------------------------------------------------


class _Blocks:
    """Array-like over a source dask array for level 0. A read assembles its region from whole source
    blocks, each computed on the synchronous scheduler; the most recent blocks are kept (at most
    ``cache_bytes``, at least one block), so with level 0 written in slabs along the slowest axis each
    source block is read once."""

    def __init__(self, arr: Any, report: Callable[[], None], cache_bytes: int):
        self.arr, self.shape, self.dtype, self.ndim = arr, tuple(arr.shape), np.dtype(arr.dtype), arr.ndim
        self.report, self.cache_bytes = report, max(1, cache_bytes)
        self.bounds = [np.cumsum((0,) + tuple(int(c) for c in cs)) for cs in arr.chunks]
        self.cache: OrderedDict[tuple[int, ...], np.ndarray] = OrderedDict()

    def _block(self, idx: tuple[int, ...]) -> np.ndarray:
        if idx in self.cache:
            self.cache.move_to_end(idx)
            return self.cache[idx]
        need = self.dtype.itemsize * math.prod(int(b[i + 1] - b[i]) for b, i in zip(self.bounds, idx))
        while self.cache and sum(b.nbytes for b in self.cache.values()) + need > self.cache_bytes:
            self.cache.popitem(last=False)  # room first: never two large blocks at once
        block = np.asarray(self.arr.blocks[idx].compute(scheduler="synchronous"))
        self.cache[idx] = block
        return block

    def __getitem__(self, key: Any) -> np.ndarray:
        key = key if isinstance(key, tuple) else (key,)
        region = [k.indices(n)[:2] for k, n in zip(key, self.shape)]
        out = np.empty(tuple(b - a for a, b in region), dtype=self.dtype)
        ranges = []
        for (a, b), bounds in zip(region, self.bounds):
            first = int(np.searchsorted(bounds, a, side="right")) - 1
            last = int(np.searchsorted(bounds, b, side="left")) - 1
            ranges.append(range(first, max(first, last) + 1))
        needed = list(itertools.product(*ranges))
        for idx in [i for i in self.cache if i not in set(needed)]:
            del self.cache[idx]  # behind the writer: never needed again (regions go forward)
        for idx in needed:
            block = self._block(idx)
            src, dst = [], []
            for (a, b), bounds, i in zip(region, self.bounds, idx):
                lo, hi = max(a, int(bounds[i])), min(b, int(bounds[i + 1]))
                src.append(slice(lo - int(bounds[i]), hi - int(bounds[i])))
                dst.append(slice(lo - a, hi - a))
            out[tuple(dst)] = block[tuple(src)]
            # regions go forward (C order): a block that ends inside this region is not read again
            if all(int(bounds[i + 1]) <= b for (a, b), bounds, i in zip(region, self.bounds, idx)):
                self.cache.pop(idx, None)
            del block
        self.report()
        return out

    def release(self) -> None:
        self.cache.clear()


class _Downsample:
    """Array-like for pyramid level k from the level k-1 array just written: the mean of each
    ``factors`` box (bin shrink; trailing pixels that do not fill a box are dropped). A region is
    computed from input slabs of at most ``budget`` bytes, so a read never holds more than one slab
    of the finer level besides its own output."""

    def __init__(self, prev: Any, factors: tuple[int, ...], budget: int, report: Callable[[], None]):
        self.prev, self.factors, self.budget, self.report = prev, factors, max(1, budget), report
        self.shape = tuple(int(n) // f for n, f in zip(prev.shape, factors))
        self.dtype, self.ndim = np.dtype(prev.dtype), len(self.shape)

    def __getitem__(self, key: Any) -> np.ndarray:
        key = key if isinstance(key, tuple) else (key,)
        region = [k.indices(n)[:2] for k, n in zip(key, self.shape)]
        out = np.empty(tuple(b - a for a, b in region), dtype=self.dtype)
        # slabs along the slowest axis whose output rows read at most `budget` bytes of input
        lead = next((i for i, f in enumerate(self.factors) if out.shape[i] > 1), 0)
        row_in = self.dtype.itemsize * math.prod(
            (b - a) * f for i, ((a, b), f) in enumerate(zip(region, self.factors)) if i != lead) * self.factors[lead]
        rows = max(1, self.budget // 2 // max(1, row_in))
        start, stop = region[lead]
        for r0 in range(start, stop, rows):
            r1 = min(stop, r0 + rows)
            sub = list(region)
            sub[lead] = (r0, r1)
            src = np.asarray(self.prev[tuple(slice(a * f, b * f) for (a, b), f in zip(sub, self.factors))])
            shaped = src.reshape([n for (a, b), f in zip(sub, self.factors) for n in (b - a, f)])
            mean = box_mean(shaped, tuple(range(1, 2 * self.ndim, 2)), self.dtype)
            out[tuple(slice(a - start, b - start) if i == lead else slice(None)
                      for i, (a, b) in enumerate(sub))] = mean
            del src, shaped, mean
        self.report()
        return out


def box_mean(x: np.ndarray, axes: tuple[int, ...], dtype: np.dtype) -> np.ndarray:
    """The mean over ``axes`` (the boxes), in ``dtype``. Booleans: majority vote (a tie is False).
    Integers: exact, without floating point (round half up): sum(x // n) + (sum(x % n) + n // 2) // n,
    which cannot overflow because each x // n is at most max / n. Floats: float64 mean."""
    n = math.prod(x.shape[a] for a in axes)
    if dtype == np.bool_:
        return (np.count_nonzero(x, axis=axes) * 2 > n)
    if np.issubdtype(dtype, np.integer):
        q = (x // n).sum(axis=axes, dtype=dtype)
        r = (x % n).sum(axis=axes, dtype=np.int64)
        return (q + ((r + n // 2) // n).astype(dtype)).astype(dtype, copy=False)
    return x.mean(axis=axes, dtype=np.float64).astype(dtype, copy=False)


def _counter(progress: Callable[[str], None] | None, level: int, n_levels: int, total: int) -> Callable[[], None]:
    """Progress per level and per block, at most about once per percent."""
    state = {"done": 0, "pct": -1}
    total = max(1, total)

    def report() -> None:
        state["done"] += 1
        pct = state["done"] * 100 // total
        if progress is not None and (pct != state["pct"] or state["done"] == total):
            state["pct"] = pct
            progress(f"converting: level {level + 1} of {n_levels}, block {min(state['done'], total)} of {total}")

    return report


# --- conversion ---------------------------------------------------------------------------------


def to_ome_zarr(src: Any, dest: Path, version: str | None = None,
                progress: Callable[[str], None] | None = None) -> int:
    """Convert ``src`` (an ``ImageSource``) to an OME-Zarr image at ``dest``; returns the bytes written.

    ``dest`` must not exist. Level 0 is ``src.level(0)`` read block by block; level k is the bin
    shrink of level k-1 as written. Each level is written by ngff-zarr (``to_multiscales`` +
    ``to_ngff_zarr``, sharded for 0.5) into a scratch store inside ``dest`` and moved to ``dest/<k>``;
    then the group metadata is rebuilt from ``src.info`` only.
    """
    import zarr

    version = version or micr.NGFF_VERSION
    if version not in ("0.5", "0.4"):
        raise ValueError(f"unsupported NGFF version: {version!r}")
    dest = Path(dest)
    if dest.exists():
        raise FileExistsError("the OME-Zarr destination exists")
    info: ImageInfo = src.info
    arr = src.level(0)
    if tuple(int(s) for s in arr.shape) != tuple(int(s) for s in info.shape) or len(info.axes) != arr.ndim:
        raise ValueError("the image's pixel array does not match its metadata")
    chunks, per_shard = write_layout(info, version)
    grid = tuple(chunks[a] * per_shard.get(a, 1) for a in info.axes)
    levels = pyramid_levels(info)
    budget = max(1, int(micr.MAX_BLOCK_BYTES) // 2)
    dest.mkdir(parents=True)
    try:
        prev = None
        for k, factors in enumerate(levels):
            if k == 0:
                shape = tuple(int(n) for n in info.shape)
            else:
                rel = tuple(factors.get(a, 1) // levels[k - 1].get(a, 1) for a in info.axes)
                shape = tuple(int(n) // f for n, f in zip(prev.shape, rel))
            blocks, partial = level0_slab(info, grid, budget, arr.chunks) if k == 0 else (grid, False)
            total = math.prod(math.ceil(n / g) for n, g in zip(shape, blocks))
            report = _counter(progress, k, len(levels), total)
            data = (_Blocks(arr, report, int(micr.MAX_BLOCK_BYTES)) if k == 0
                    else _Downsample(prev, rel, budget, report))
            _write_level(dest, k, data, info.axes, chunks, blocks, per_shard, version, partial)
            if k == 0:
                data.release()
            prev = zarr.open_array(str(dest / str(k)), mode="r")
        windows = _windows(dest, info, len(levels) - 1)
        _write_group(dest, version, ngff_attrs(info, version, levels, windows))
    except BaseException:
        shutil.rmtree(dest, ignore_errors=True)
        raise
    return sum(p.stat().st_size for p in dest.rglob("*") if p.is_file())


def _write_level(dest: Path, k: int, data: Any, axes: str, chunks: dict[str, int], blocks: tuple[int, ...],
                 per_shard: dict[str, int], version: str, partial: bool = False) -> None:
    """One level: ngff-zarr creates the array (shape, dtype, chunks, shards and codecs; metadata only)
    in ``dest/.level``, it is moved to ``dest/<k>`` with empty attributes, and the pixels are then
    written region by region (``blocks``, whole shards each) in C order, so reads of the source move
    forward through it. The scratch store (and every group node ngff-zarr made) is removed."""
    import dask.array as da
    import ngff_zarr as nz
    import zarr

    shape = tuple(int(n) for n in data.shape)
    template = da.zeros(shape, chunks=tuple(min(chunks[a], max(1, n)) for a, n in zip(axes, shape)),
                        dtype=data.dtype)  # never computed: metadata only
    image = nz.to_ngff_image(template, dims=list(axes))
    ms = nz.to_multiscales(image, scale_factors=[], chunks={a: chunks[a] for a in axes}, cache=False,
                           axis_order="preserve")
    scratch = dest / ".level"
    shard = {a: n for a, n in per_shard.items() if n > 1} if version == "0.5" else None
    nz.to_ngff_zarr(scratch, ms, version=version, chunks_per_shard=shard or None, consolidate_metadata=False,
                    metadata_only=True)
    paths = _ngff_paths(scratch, version)
    if len(paths) != 1:
        raise _fail("ngff-zarr wrote an unexpected number of levels")
    array = (scratch / paths[0]).resolve()
    if scratch.resolve() not in array.parents:
        raise _fail("a level lies outside the image")
    target = dest / str(k)
    os.replace(array, target)
    shutil.rmtree(scratch)
    if version == "0.5":
        meta_json = json.loads((target / "zarr.json").read_text())
        meta_json["attributes"] = {}
        (target / "zarr.json").write_text(json.dumps(meta_json, indent=2))
    else:
        (target / ".zattrs").unlink(missing_ok=True)
    z = zarr.open_array(str(target), mode="r+")
    if tuple(z.shape) != shape:
        raise _fail("ngff-zarr created an array of an unexpected shape")
    starts = [range(0, n, max(1, b)) for n, b in zip(shape, blocks)]
    # blocks that cut through shards (or chunks) make zarr read, merge and rewrite them: one at a time
    with zarr.config.set({"async.concurrency": 1} if partial else {}):
        for corner in itertools.product(*starts):
            region = tuple(slice(c, min(n, c + b)) for c, n, b in zip(corner, shape, blocks))
            z[region] = data[region]


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise NgffCheckError("OME-Zarr self-check failed: group metadata is missing or not valid JSON") from exc


def _ngff_paths(dest: Path, version: str) -> list[str]:
    """The dataset paths ngff-zarr wrote, from its own group metadata (discarded right after)."""
    if version == "0.5":
        attrs = (_read_json(dest / "zarr.json").get("attributes") or {}).get("ome") or {}
    else:
        attrs = _read_json(dest / ".zattrs")
    ms = (attrs.get("multiscales") or [{}])[0]
    return [str(d["path"]) for d in ms.get("datasets") or []]


def _write_group(dest: Path, version: str, attrs: dict) -> None:
    if version == "0.5":
        (dest / "zarr.json").write_text(json.dumps(
            {"zarr_format": 3, "node_type": "group", "attributes": attrs}, indent=2))
    else:
        (dest / ".zgroup").write_text(json.dumps({"zarr_format": 2}, indent=2))
        (dest / ".zattrs").write_text(json.dumps(attrs, indent=2))


def _windows(dest: Path, info: ImageInfo, level: int) -> list[dict[str, float]]:
    """Display window per channel: the 0.5/99.5 percentiles of a strided sample of the coarsest level
    (at most WINDOW_SAMPLES values per channel); min/max is the dtype's range (data range for floats)."""
    import zarr

    z = zarr.open_array(str(dest / str(level)), mode="r")
    dtype = np.dtype(z.dtype)
    count = channel_count(info)
    out = []
    for c in range(count):
        index: list[Any] = []
        rest = [n for a, n in zip(info.axes, z.shape) if a != "c"]
        step = max(1, math.ceil((math.prod(rest) / WINDOW_SAMPLES) ** (1 / max(1, len(rest)))))
        for a in info.axes:
            index.append(c if a == "c" else slice(None, None, step))
        sample = np.asarray(z[tuple(index)], dtype=np.float64).ravel()
        sample = sample[np.isfinite(sample)]
        if sample.size == 0:
            out.append({"min": 0.0, "max": 1.0, "start": 0.0, "end": 1.0})
            continue
        lo, hi = (float(v) for v in np.percentile(sample, WINDOW_PERCENTILES))
        if np.issubdtype(dtype, np.integer):
            mn, mx = float(np.iinfo(dtype).min), float(np.iinfo(dtype).max)
        else:
            mn, mx = float(sample.min()), float(sample.max())
        out.append({"min": mn, "max": mx, "start": lo, "end": hi if hi > lo else lo + 1.0})
    return out


# --- tile groups --------------------------------------------------------------------------------


class _Stack:
    """Tiles of one group (VISoR: consecutive frame stacks of one position) as one image along z."""

    def __init__(self, sources: Sequence[Any]):
        import dask.array as da
        from dataclasses import replace

        first = sources[0].info
        base = [(s.info.axes, tuple(s.info.shape[i] for i, a in enumerate(s.info.axes) if a != "z"),
                 s.info.dtype) for s in sources]
        if len({b for b in base}) != 1:
            raise ValueError("the tiles of a group differ in shape or type")
        arrays = [s.level(0) for s in sources]
        if "z" in first.axes:
            axes = first.axes
            data = da.concatenate(arrays, axis=axes.index("z"))
        else:
            axes = "".join(sorted(first.axes + "z", key=AXES_ORDER.index))
            data = da.stack(arrays, axis=axes.index("z"))
        self.info = replace(first, axes=axes, shape=tuple(int(n) for n in data.shape), levels=1)
        self.terms = set().union(*(s.terms for s in sources))
        self._data, self._sources = data, list(sources)

    def level(self, i: int) -> Any:
        if i != 0:
            raise IndexError("a tile group has one level")
        return self._data

    def close(self) -> None:
        for s in self._sources:
            s.close()


def stack_sources(sources: Sequence[Any]) -> Any:
    """One ImageSource for the tiles of a group, stacked along z in the order given."""
    if len(sources) == 1:
        return sources[0]
    return _Stack(sources)


# --- self-check ---------------------------------------------------------------------------------


def _fail(what: str) -> NgffCheckError:
    return NgffCheckError(f"OME-Zarr self-check failed: {what}")


def _close(a: float, b: float) -> bool:
    return math.isclose(float(a), float(b), rel_tol=1e-6, abs_tol=1e-12)


def check_ome_zarr(dest: Path, sidecar: dict, version: str, shape: Sequence[int] | None = None,
                   dtype: str | None = None, reference: bool = False) -> None:
    """Re-open a written OME-Zarr image and check it; raises NgffCheckError on the first failure.

    Checks: group metadata valid for ``version`` (Zarr v3 ``zarr.json`` with ``attributes.ome`` for
    0.5, Zarr v2 ``.zgroup``/``.zattrs`` for 0.4), ngff-zarr opens it and its structural rules pass;
    axes are named from tczyx in order with the sidecar's unit; level 0's scale equals the sidecar's
    PixelSize and each level is a whole-factor downsampling of level 0; every dataset path is present
    with the expected shape and dtype; the omero channel count equals the channel axis length.
    ``reference``: a reference dataset's metadata-only store (micr/reference.py), whose pyramid was
    made by another tool: a level's shape may also be the rounded-up division of level 0's. No chunk
    is read either way.
    """
    import ngff_zarr as nz
    import zarr

    dest = Path(dest)
    if version == "0.5":
        root = _read_json(dest / "zarr.json")
        if not isinstance(root, dict) or root.get("zarr_format") != 3 or root.get("node_type") != "group":
            raise _fail("the group metadata is not a Zarr v3 group")
        attrs = root.get("attributes") or {}
        ome = attrs.get("ome") if isinstance(attrs, dict) else None
        if set(attrs) != {"ome"} or not isinstance(ome, dict) or ome.get("version") != "0.5":
            raise _fail("the group attributes are not NGFF 0.5")
        multiscales, omero = ome.get("multiscales"), ome.get("omero")
    elif version == "0.4":
        group = _read_json(dest / ".zgroup")
        attrs = _read_json(dest / ".zattrs")
        if not isinstance(group, dict) or group.get("zarr_format") != 2 or not isinstance(attrs, dict):
            raise _fail("the group metadata is not a Zarr v2 group")
        multiscales, omero = attrs.get("multiscales"), attrs.get("omero")
        if not set(attrs) <= {"multiscales", "omero"} or not isinstance(multiscales, list) \
                or not multiscales or not isinstance(multiscales[0], dict) or multiscales[0].get("version") != "0.4":
            raise _fail("the group attributes are not NGFF 0.4")
    else:
        raise _fail("unsupported NGFF version")
    if not isinstance(multiscales, list) or len(multiscales) != 1 or not isinstance(multiscales[0], dict):
        raise _fail("there is not exactly one multiscales image")
    ms = multiscales[0]
    axes = ms.get("axes")
    if not isinstance(axes, list) or not axes or not all(isinstance(a, dict) for a in axes):
        raise _fail("the axes are not valid")
    names = "".join(str(a.get("name")) for a in axes)
    if len(names) != len(axes) or any(n not in AXES_ORDER for n in names) \
            or list(names) != sorted(names, key=AXES_ORDER.index) or len(set(names)) != len(names):
        raise _fail("the axes are not a subset of t, c, z, y, x in that order")
    unit = NGFF_UNITS.get(str(sidecar.get("PixelSizeUnits")))
    for a in axes:
        kind = "space" if a["name"] in SPATIAL else "channel" if a["name"] == "c" else "time"
        if a.get("type") != kind or (kind == "space" and a.get("unit") != unit):
            raise _fail("an axis type or unit does not match the sidecar")
    pixel = sidecar.get("PixelSize")
    spatial = [n for n in "xyz" if n in names]
    if not isinstance(pixel, list) or len(pixel) != len(spatial):
        raise _fail("the sidecar PixelSize does not match the spatial axes")
    expected = dict(zip(spatial, pixel))
    datasets = ms.get("datasets")
    if not isinstance(datasets, list) or not datasets:
        raise _fail("there are no datasets")
    try:
        opened = nz.from_ngff_zarr(str(dest), validate=False, version=version)
        nz.validate_structural(opened.metadata, version=version)
    except NgffCheckError:
        raise
    except Exception as exc:  # noqa: BLE001 - any parse or rule failure is a failed check
        raise _fail("ngff-zarr cannot open the image or its structure is not valid") from exc
    base_shape: tuple[int, ...] | None = None
    base_scale: list[float] | None = None
    for i, ds in enumerate(datasets):
        path = ds.get("path") if isinstance(ds, dict) else None
        transforms = ds.get("coordinateTransformations") if isinstance(ds, dict) else None
        if not isinstance(path, str) or not path or not isinstance(transforms, list) or not transforms:
            raise _fail("a dataset entry is not valid")
        first = transforms[0]
        scale = first.get("scale") if isinstance(first, dict) and first.get("type") == "scale" else None
        if not isinstance(scale, list) or len(scale) != len(names) \
                or not all(isinstance(v, (int, float)) and v > 0 for v in scale):
            raise _fail("a dataset has no valid scale transform")
        for t in transforms[1:]:
            vec = t.get("translation") if isinstance(t, dict) and t.get("type") == "translation" else None
            if not isinstance(vec, list) or len(vec) != len(names):
                raise _fail("a dataset has an invalid translation transform")
        target = (dest / path).resolve()
        if dest.resolve() not in target.parents:
            raise _fail("a dataset path lies outside the image")
        try:
            arr = zarr.open_array(str(target), mode="r")
        except Exception as exc:  # noqa: BLE001
            raise _fail("a dataset array is missing or cannot be opened") from exc
        if arr.ndim != len(names) or (dtype is not None and np.dtype(arr.dtype) != np.dtype(dtype)):
            raise _fail("a dataset array has the wrong number of axes or the wrong type")
        if i == 0:
            base_shape, base_scale = tuple(int(n) for n in arr.shape), [float(v) for v in scale]
            if shape is not None and base_shape != tuple(int(n) for n in shape):
                raise _fail("the full-resolution array does not have the image's shape")
            for n, v in zip(names, scale):
                if n in expected and not _close(v, expected[n]):
                    raise _fail("the pixel size in the sidecar does not match the NGFF scale")
            continue
        assert base_shape is not None and base_scale is not None
        for k, n in enumerate(names):
            ratio = float(scale[k]) / base_scale[k]
            f = round(ratio)
            if f < 1 or not _close(ratio, f) or (n not in SPATIAL and f != 1):
                raise _fail("a pyramid level's scale is not a whole multiple of the full resolution")
            if int(arr.shape[k]) != base_shape[k] // f and not (reference and int(arr.shape[k]) == -(-base_shape[k] // f)):
                raise _fail("a pyramid level's shape does not match its scale")
    channels = (omero or {}).get("channels") if isinstance(omero, dict) else None
    count = base_shape[names.index("c")] if "c" in names and base_shape else 1
    if not isinstance(channels, list) or len(channels) != count:
        raise _fail("the omero channel count does not match the channel axis")
    stray = [p for p in dest.rglob("*") if p.is_file() and p.name in _METADATA_NAMES
             and p.parent != dest and not any(p.parent == dest / str(d.get("path")) for d in datasets)]
    if stray:
        raise _fail("the image holds metadata outside its group and arrays")
