"""Synthetic microscopy fixtures (no real data): minimal OME-Zarr stores, NGFF 0.5 or 0.4."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import zarr

AXES = [
    {"name": "c", "type": "channel"},
    {"name": "z", "type": "space", "unit": "micrometer"},
    {"name": "y", "type": "space", "unit": "micrometer"},
    {"name": "x", "type": "space", "unit": "micrometer"},
]
# Zarr metadata files; everything else in a store is a chunk or shard
METADATA_FILES = {"zarr.json", ".zgroup", ".zarray", ".zattrs", ".zmetadata"}


def _multiscales(version: str, pixel_size_um: tuple[float, float, float], levels: int) -> dict:
    datasets = [
        {
            "path": str(i),
            "coordinateTransformations": [
                {
                    "type": "scale",
                    "scale": [1.0, pixel_size_um[0], pixel_size_um[1] * 2**i, pixel_size_um[2] * 2**i],
                }
            ],
        }
        for i in range(levels)
    ]
    ms = {"name": "image", "axes": AXES, "datasets": datasets}
    if version == "0.4":
        ms = {"version": "0.4", **ms}
    return ms


def ome_zarr(
    dest: Path,
    version: str,
    shape: tuple[int, int, int, int] = (2, 8, 64, 64),
    pixel_size_um: tuple[float, float, float] = (1.0, 0.5, 0.5),
) -> Path:
    """Write a 2-level c,z,y,x OME-Zarr at dest (NGFF "0.5": Zarr v3 sharded; "0.4": Zarr v2)."""
    if version not in ("0.5", "0.4"):
        raise ValueError(f"version must be '0.5' or '0.4', got {version!r}")
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(0)
    data = rng.integers(0, 4096, size=shape, dtype=np.uint16)
    levels = 2
    ms = _multiscales(version, pixel_size_um, levels)
    if version == "0.5":
        root = zarr.open_group(str(dest), mode="w", zarr_format=3)
        root.attrs["ome"] = {"version": "0.5", "multiscales": [ms]}
    else:
        root = zarr.open_group(str(dest), mode="w", zarr_format=2)
        root.attrs["multiscales"] = [ms]
    for i in range(levels):
        level = data[:, :, :: 2**i, :: 2**i]
        chunks = (1, level.shape[1], level.shape[2] // 2, level.shape[3] // 2)
        kwargs = {"shards": (1, *level.shape[1:])} if version == "0.5" else {}
        if version == "0.5":
            kwargs["dimension_names"] = [a["name"] for a in AXES]
        arr = root.create_array(str(i), shape=level.shape, dtype=level.dtype, chunks=chunks, **kwargs)
        arr[...] = level
    return dest


def strip_chunks(store: Path) -> Path:
    """Delete every chunk/shard file, leaving only Zarr metadata (a reference dataset's local shape)."""
    for p in sorted(Path(store).rglob("*"), reverse=True):
        if p.is_file() and p.name not in METADATA_FILES:
            p.unlink()
        elif p.is_dir() and not any(p.iterdir()):
            p.rmdir()
    return Path(store)
