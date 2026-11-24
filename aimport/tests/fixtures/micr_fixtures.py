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
    levels: int = 2,
    dtype: str = "uint16",
) -> Path:
    """Write a c,z,y,x OME-Zarr pyramid (y, x halved per level; 2 levels by default) at dest
    (NGFF "0.5": Zarr v3 sharded; "0.4": Zarr v2). dtype float32: values in 0..1."""
    if version not in ("0.5", "0.4"):
        raise ValueError(f"version must be '0.5' or '0.4', got {version!r}")
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(0)
    data = rng.integers(0, 4096, size=shape, dtype=np.uint16)
    if dtype != "uint16":
        data = (data / 4096).astype(dtype)
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


# The CMC PS-OCT store's layout and metadata faults (Moe_Slice_051.ome.zarr, DATASETS.md), at a tenth of
# its size: c,y,x float32 at scale<k>/image, chunks (4, 256, 256), zstd; axes without units; a
# translation of 1.0 on the channel axis; levels 3, 4 and 5 declare 16, 64 and 256 (CMC: 512, which
# a tenth-size level 0 would still agree with) but hold 8, 16 and 425 (y) / 550 (x). Metadata only: no chunk is written (a reference reads none).
CMC_PSOCT_SHAPES = [(4, 850, 1100), (4, 425, 550), (4, 212, 275), (4, 106, 137), (4, 53, 68), (4, 2, 2)]
CMC_PSOCT_DECLARED = [1, 2, 4, 16, 64, 256]
CMC_PSOCT_FACTORS = [(1, 1), (2, 2), (4, 4), (8, 8), (16, 16), (425, 550)]  # (y, x) the arrays hold


def cmc_psoct_zarr(dest: Path) -> Path:
    from zarr.codecs import BytesCodec, ZstdCodec

    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    root = zarr.open_group(str(dest), mode="w", zarr_format=3)
    datasets = []
    for k, (shape, f) in enumerate(zip(CMC_PSOCT_SHAPES, CMC_PSOCT_DECLARED)):
        g = root.require_group(f"scale{k}")
        g.create_array("image", shape=shape, dtype="float32", chunks=tuple(min(n, c) for n, c in
                                                                           zip(shape, (4, 256, 256))),
                       compressors=ZstdCodec(), serializer=BytesCodec(), fill_value=0)
        datasets.append({"path": f"scale{k}/image", "coordinateTransformations": [
            {"scale": [1.0, f, f], "type": "scale"},
            {"translation": [1.0, (f - 1) / 2, (f - 1) / 2], "type": "translation"}]})
    root.attrs["ome"] = {"version": "0.5", "multiscales": [{
        "axes": [{"name": "c", "type": "channel"}, {"name": "y", "type": "space"}, {"name": "x", "type": "space"}],
        "datasets": datasets, "name": "image", "@type": "ngff:Image"}]}
    import warnings

    with warnings.catch_warnings():  # "consolidated metadata is not part of Zarr v3": CMC has it
        warnings.simplefilter("ignore")
        zarr.consolidate_metadata(str(dest))
    return dest


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


# --- Task 4: reader fixtures (synthetic; every identifier planted here is in conftest.MICR_PLANTED) ---

PLANTED_PIXEL_SIZE_UM = {"x": 0.5, "y": 0.5, "z": 2.0}
PLANTED_WAVELENGTHS_NM = ((488.0, 520.0), (561.0, 600.0))  # (excitation, emission) per channel


def _planted_ome_xml(shape_czyx: tuple[int, int, int, int]) -> str:
    from datetime import datetime

    from ome_types import model as m

    c, z, y, x = shape_czyx
    objective = m.Objective(id="Objective:0", nominal_magnification=20.0, lens_na=0.8,
                            immersion="Water", serial_number="SCOPE-SN-4711", model="Plan 20x")
    instrument = m.Instrument(id="Instrument:0", objectives=[objective],
                              microscope=m.Microscope(serial_number="SCOPE-SN-4711",
                                                      manufacturer="AcqSoft"))
    experimenter = m.Experimenter(id="Experimenter:0", first_name="Jane", last_name="Doe",
                                  user_name="Jane Doe", email="jdoe@example.org",
                                  institution="lab-workstation-7")
    channels = [
        m.Channel(id=f"Channel:0:{i}", name=f"Slide 42 Smith ch{i}", samples_per_pixel=1,
                  excitation_wavelength=ex, emission_wavelength=em)
        for i, (ex, em) in enumerate(PLANTED_WAVELENGTHS_NM[:c])
    ]
    pixels = m.Pixels(
        id="Pixels:0", dimension_order="XYZCT", type="uint16",
        size_x=x, size_y=y, size_z=z, size_c=c, size_t=1,
        physical_size_x=PLANTED_PIXEL_SIZE_UM["x"], physical_size_y=PLANTED_PIXEL_SIZE_UM["y"],
        physical_size_z=PLANTED_PIXEL_SIZE_UM["z"],
        channels=channels, tiff_data_blocks=[m.TiffData(plane_count=c * z)],
    )
    image = m.Image(
        id="Image:0", name="Slide 42 Smith", description="annotation secret",
        acquisition_date=datetime(2025, 2, 15, 10, 0, 0), pixels=pixels,
        experimenter_ref=m.ExperimenterRef(id="Experimenter:0"),
        instrument_ref=m.InstrumentRef(id="Instrument:0"),
        objective_settings=m.ObjectiveSettings(id="Objective:0"),
        roi_refs=[m.ROIRef(id="ROI:0")],
    )
    roi = m.ROI(id="ROI:0", name="Jane Doe region",
                union=[m.Label(id="Shape:0", x=1.0, y=1.0, text="Slide 42 Smith")])
    annotations = m.StructuredAnnotations(
        comment_annotations=[m.CommentAnnotation(id="Annotation:0", value="annotation secret",
                                                 description="by Jane Doe")])
    ome = m.OME(images=[image], instruments=[instrument], experimenters=[experimenter],
                rois=[roi], structured_annotations=annotations, creator="AcqSoft 9 lab-workstation-7")
    return ome.to_xml()


def planted_ome_tiff(dest: Path, shape: tuple[int, int, int, int] = (2, 4, 64, 64)) -> Path:
    """An OME-TIFF (c, z, y, x uint16) whose OME-XML and TIFF tags carry planted identifiers.

    OME-XML: Experimenter ``Jane Doe`` / ``jdoe@example.org``, serial ``SCOPE-SN-4711``,
    AcquisitionDate ``2025-02-15T10:00:00``, Image Name ``Slide 42 Smith``, Description
    ``annotation secret``, a CommentAnnotation and an ROI. TIFF tags: Artist ``Jane Doe``,
    HostComputer ``lab-workstation-7``, Software ``AcqSoft 9 lab-workstation-7``,
    DateTime ``2025:02:15 10:00:00``. Pixel size 0.5 x 0.5 x 2.0 um; channels 488/520, 561/600 nm.
    """
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    data = np.random.default_rng(0).integers(0, 4096, size=shape, dtype=np.uint16)
    xml = _planted_ome_xml(shape)
    with tifffile.TiffWriter(str(dest)) as tw:
        for i, plane in enumerate(data.reshape(-1, *shape[2:])):
            tw.write(
                plane, photometric="minisblack", metadata=None,
                description=xml if i == 0 else None,
                software="AcqSoft 9 lab-workstation-7", datetime="2025:02:15 10:00:00",
                extratags=[(315, "s", 0, "Jane Doe", True), (316, "s", 0, "lab-workstation-7", True)],
            )
    return dest


SVS_LABEL_TEXT = b"Slide 42 Smith"


def planted_svs(dest: Path) -> Path:
    """An Aperio SVS-like file: tiled RGB baseline + one level, thumbnail, label and macro.

    The label and macro images hold the bytes of ``Slide 42 Smith`` as pixels (as a rendered
    label would hold it), and the Aperio description carries ``Filename = Slide 42 Smith``.
    """
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(0)
    head = "Aperio Image Library v12.0.0\n"
    desc = (head + "512x512 [0,0 512x512] (256x256) RAW|AppMag = 20|MPP = 0.4990|"
            "Filename = Slide 42 Smith|User = Jane Doe|Date = 02/15/25|Time = 10:00:00")
    label = np.frombuffer(SVS_LABEL_TEXT * 64, dtype=np.uint8).reshape(32, -1)  # 32 x 28
    macro = np.frombuffer(SVS_LABEL_TEXT * 128, dtype=np.uint8).reshape(64, -1)  # 64 x 28
    with tifffile.TiffWriter(str(dest)) as tw:
        tw.write(rng.integers(0, 255, (512, 512, 3), dtype=np.uint8), tile=(256, 256),
                 photometric="rgb", description=desc, metadata=None)
        tw.write(rng.integers(0, 255, (64, 64, 3), dtype=np.uint8), photometric="rgb",
                 description=head + "thumbnail 64x64", metadata=None)
        tw.write(rng.integers(0, 255, (256, 256, 3), dtype=np.uint8), tile=(256, 256),
                 photometric="rgb", description=head + "256x256 (256x256) RAW", metadata=None)
        tw.write(label, photometric="minisblack", subfiletype=1,
                 description=head + "label 28x32", metadata=None)
        tw.write(macro, photometric="minisblack", subfiletype=9,
                 description=head + "macro 28x64", metadata=None)
    return dest


PSOCT_CONTRASTS = ("reflectivity", "retardance", "opticaxis", "cross")


def psoct_nifti(dest: Path, contrast: str, shape: tuple[int, int, int] = (32, 24, 4),
                zooms_um: tuple[float, float, float] = (10.0, 10.0, 2.5), descrip: str = "") -> Path:
    """A small float32 PS-OCT contrast NIfTI with spatial units in microns (xyzt_units code 3)."""
    import nibabel as nib

    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    seed = PSOCT_CONTRASTS.index(contrast) if contrast in PSOCT_CONTRASTS else 0
    data = np.random.default_rng(seed).random(shape, dtype=np.float32)
    img = nib.Nifti1Image(data, np.diag([*zooms_um, 1.0]))
    img.header.set_zooms(zooms_um)
    img.header.set_xyzt_units("micron")
    if descrip:
        img.header["descrip"] = descrip.encode()
    nib.save(img, str(dest))
    return dest


MAT_V73_SHAPE = (256, 256, 256)  # float32: 64 MiB, stored sparse (chunks never written)


def psoct_mat(dest: Path, v73: bool, operator: str | None = None) -> Path:
    """A PS-OCT retardance volume as a MATLAB file.

    ``v73=True``: an HDF5-based v7.3 file (512-byte MATLAB header) holding a 64 MiB float32
    dataset ``retardance`` whose chunks are never written, so the file stays a few KiB on disk.
    ``v73=False``: a small v5 file (scipy.io.savemat). ``operator`` plants a string attribute.
    """
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not v73:
        import scipy.io

        data = np.random.default_rng(0).random((16, 12, 4)).astype(np.float32)
        mdict = {"retardance": data}
        if operator:
            mdict["operator"] = operator
        scipy.io.savemat(str(dest), mdict)
        return dest
    import h5py

    with h5py.File(str(dest), "w", userblock_size=512) as f:
        ds = f.create_dataset("retardance", shape=MAT_V73_SHAPE, dtype="f4", chunks=(8, 128, 128))
        ds.attrs["MATLAB_class"] = np.bytes_(b"single")
        if operator:
            ds.attrs["operator"] = np.bytes_(operator.encode())
    header = b"MATLAB 7.3 MAT-file, Platform: GLNXA64, Created on: synthetic HDF5 schema 1.00 ."
    with open(dest, "r+b") as fh:
        fh.write(header.ljust(116, b" ") + b"\x00" * 8 + b"\x00\x02" + b"IM")
    return dest


def striped_tiff(dest: Path, shape: tuple[int, int] = (6000, 6000), dtype=np.uint16,
                 rowsperstrip: int = 16) -> Path:
    """A single-plane, uncompressed, stripped TIFF whose pixels are never written (sparse on disk)."""
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tifffile.imwrite(str(dest), shape=shape, dtype=dtype, rowsperstrip=rowsperstrip,
                     photometric="minisblack", metadata=None)
    return dest


def visor_tile(dest_dir: Path, acqinfo: dict | None = None) -> Path:
    """A VISoR-like tile folder: ``<dest_dir>/visor_488_Pos0/visor_488_0001.tif`` (small uint16)
    plus ``<dest_dir>/acqinfo_metadata.json``. Key names are synthetic (see DATASETS.md)."""
    import json

    dest_dir = Path(dest_dir)
    tile = dest_dir / "visor_488_Pos0" / "visor_488_0001.tif"
    tile.parent.mkdir(parents=True, exist_ok=True)
    tifffile.imwrite(str(tile), np.zeros((4, 32, 32), dtype=np.uint16), photometric="minisblack",
                     metadata=None)
    info = acqinfo if acqinfo is not None else {
        "operator": "Jane Doe", "host": "lab-workstation-7", "date": "20250422",
        "pixel_size": 1.0, "z_step": 3.5, "wavelength": 488, "exposure_ms": 10,
    }
    (dest_dir / "acqinfo_metadata.json").write_text(json.dumps(info))
    return tile
