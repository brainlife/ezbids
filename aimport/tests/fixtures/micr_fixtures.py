"""Synthetic microscopy fixtures (no real data): minimal OME-Zarr stores (NGFF 0.5 or 0.4), sparse BigTIFF."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import tifffile
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


SPARSE_ROW = 32768  # uint16 samples per row of sparse_bigtiff (64 KiB)


def sparse_bigtiff(size: int, dest: Path) -> Path:
    """A valid single-plane uint16 BigTIFF of about size bytes at dest, written sparse.

    tifffile.memmap writes the header and extends the file without writing the pixels, so the
    file's apparent size is ~size while the disk holds only a few KiB (check with ``du``).
    """
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    rows = max(1, size // (SPARSE_ROW * 2))
    image = tifffile.memmap(str(dest), shape=(rows, SPARSE_ROW), dtype=np.uint16, bigtiff=True,
                            photometric="minisblack")
    del image  # never touched: no page is written
    return dest


def cmc_tree(dest: Path) -> Path:
    """Empty/sparse stand-ins for the CMC layouts (PS-OCT, OME-Zarr, VISoR, exaSPIM). No pixel data."""
    dest = Path(dest)
    files = [f"PS-OCT/Enface/Registration/{c}/Slice_051_1.nii.gz"
             for c in ("Reflectivity", "Retardance", "Orientation", "Cross")]
    files += [
        "PS-OCT/250215/Slice_051_Tile_0001.dat",
        "MN27_20250422_visor_488/visor_488_Pos0/visor_488_0001.tif",
        "MN27_20250422_visor_488/acqinfo_metadata.json",
        "MN27_20250422_visor_488/dbpost.json",
        "MN27_20250422_visor_488/hh.log",
    ]
    for rel in files:
        f = dest / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.touch()
    for store in ("Moe_Slice_051.ome.zarr", "exaSPIM.zarr/Pos0"):
        (dest / store).mkdir(parents=True, exist_ok=True)
        (dest / store / "zarr.json").write_text('{"zarr_format": 3, "node_type": "group"}')
    return dest
