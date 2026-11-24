"""Microscopy readers (Task 4): allowlisted metadata, lazy and memory-bounded pixel access."""
from __future__ import annotations

import gc
import math
import tracemalloc
from pathlib import Path

import numpy as np
import pytest
import tifffile
from conftest import MICR_PLANTED, tokens
from micr_fixtures import (
    MAT_V73_SHAPE,
    PLANTED_PIXEL_SIZE_UM,
    PLANTED_WAVELENGTHS_NM,
    ome_zarr,
    planted_ome_tiff,
    planted_svs,
    psoct_mat,
    psoct_nifti,
    sparse_bigtiff,
    striped_tiff,
    visor_tile,
)

from aimport import micr
from aimport.micr import readers
from aimport.micr.readers import (
    BIOFORMATS_MESSAGE,
    ChannelInfo,
    ImageInfo,
    ImageSource,
    UnsupportedFormat,
    open_image,
    plan_chunks,
    register_reader,
)

MiB = 2**20
# What planted_ome_tiff carries in its own bytes (the rest of MICR_PLANTED are folder names).
OME_TIFF_PLANTED = {"jane doe", "jdoe@example.org", "scope-sn-4711", "2025-02-15", "250215",
                    "slide 42 smith", "annotation secret", "lab-workstation-7"}


def _peak(fn):
    gc.collect()
    tracemalloc.start()
    try:
        result = fn()
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    return result, peak


def _block_bytes(arr) -> int:
    return math.prod(arr.chunksize) * arr.dtype.itemsize


def test_ome_tiff_info_allowlisted(tmp_path):
    with open_image(planted_ome_tiff(tmp_path / "x.ome.tif"), "ome-tiff") as src:
        info = src.info
        assert isinstance(src, ImageSource)
        assert info.family == "ome-tiff"
        assert (info.axes, info.shape, info.dtype) == ("czyx", (2, 4, 64, 64), "uint16")
        assert info.pixel_unit == "um"
        assert info.pixel_size == pytest.approx(PLANTED_PIXEL_SIZE_UM)
        assert [(c.excitation_nm, c.emission_nm) for c in info.channels] == list(PLANTED_WAVELENGTHS_NM)
        assert [c.name_code for c in info.channels] == ["ch488", "ch561"]
        assert (info.objective_magnification, info.objective_na, info.immersion) == (20.0, 0.8, "Water")
        assert info.acquired.isoformat() == "2025-02-15"
        assert info.levels == 1 and info.series_skipped == []
        # nothing identifying in the facts; every planted value among the dropped terms
        assert not tokens(repr(info)), tokens(repr(info))
        assert OME_TIFF_PLANTED <= tokens("\n".join(src.terms))
        assert "2025:02:15 10:00:00" in src.terms and "AcqSoft 9 lab-workstation-7" in src.terms
        # pixels match what was written
        with tifffile.TiffFile(tmp_path / "x.ome.tif") as tif:
            expected = tif.series[0].asarray()
        assert np.array_equal(src.level(0).compute(), expected)


def test_info_has_only_allowlisted_fields():
    assert set(ImageInfo.__dataclass_fields__) == {
        "family", "axes", "shape", "dtype", "pixel_size", "pixel_unit", "channels",
        "objective_magnification", "objective_na", "immersion", "levels", "zarr_format",
        "ngff_version", "acquired", "series_skipped"}
    assert set(ChannelInfo.__dataclass_fields__) == {"excitation_nm", "emission_nm", "name_code"}


def test_svs_label_macro_skipped(tmp_path, monkeypatch):
    built: list[str] = []
    real = tifffile.TiffPageSeries.aszarr

    def spy(self, *args, **kwargs):
        built.append(self.name)
        return real(self, *args, **kwargs)

    monkeypatch.setattr(tifffile.TiffPageSeries, "aszarr", spy)
    with open_image(planted_svs(tmp_path / "x.svs"), "svs") as src:
        info = src.info
        assert info.series_skipped == ["label", "macro"]
        assert (info.axes, info.shape, info.levels) == ("cyx", (3, 512, 512), 2)
        assert info.pixel_size == {"x": 0.499, "y": 0.499}
        assert info.objective_magnification == 20.0
        for i in range(info.levels):
            src.level(i).compute()
        assert src.level(1).shape == (3, 256, 256)
        assert not tokens(repr(info))
        assert {"slide 42 smith", "jane doe"} <= tokens("\n".join(src.terms))
    assert built and set(built) == {"Baseline"}  # no array for Label, Macro (or Thumbnail)


def test_nifti_microns(tmp_path):
    path = psoct_nifti(tmp_path / "Slice_051_1.nii.gz", "retardance", descrip="Jane Doe 2025-02-15")
    with open_image(path, "nifti") as src:
        info = src.info
        assert info.pixel_unit == "um"
        assert info.pixel_size == {"x": 10.0, "y": 10.0, "z": 2.5}
        assert (info.axes, info.shape, info.dtype) == ("zyx", (4, 24, 32), "float32")
        assert "Jane Doe 2025-02-15" in src.terms and not tokens(repr(info))
        import nibabel as nib

        expected = np.asarray(nib.load(str(path)).dataobj).transpose(2, 1, 0)
        assert np.array_equal(src.level(0).compute(), expected)


def test_nifti_blocks_bounded(tmp_path, monkeypatch):
    monkeypatch.setattr(micr, "MAX_BLOCK_BYTES", 4096)
    with open_image(psoct_nifti(tmp_path / "a.nii", "cross"), "nifti") as src:
        arr = src.level(0)
        assert _block_bytes(arr) <= 4096
        assert arr.compute().shape == (4, 24, 32)


def test_mat_v73_lazy(tmp_path, monkeypatch):
    path = psoct_mat(tmp_path / "retardance.mat", v73=True, operator="Jane Doe")
    assert path.stat().st_size < MiB  # sparse: the 64 MiB dataset is never written
    assert math.prod(MAT_V73_SHAPE) * 4 == 64 * MiB

    def open_and_build():
        src = open_image(path, "mat")
        return src, src.info, src.level(0)

    (src, info, arr), peak = _peak(open_and_build)
    try:
        assert peak < 8 * MiB, peak
        assert (info.axes, info.shape, info.dtype) == ("zyx", MAT_V73_SHAPE, "float32")
        assert "Jane Doe" in src.terms and not tokens(repr(info))
        monkeypatch.setattr(micr, "MAX_BLOCK_BYTES", 4 * MiB)
        block = open_image(path, "mat").level(0)
        assert _block_bytes(block) <= 4 * MiB
        one, peak = _peak(lambda: block.blocks[(0,) * block.ndim].compute())
        assert one.nbytes <= 4 * MiB and peak < 12 * MiB, peak  # under 3 x the block limit
    finally:
        src.close()


def test_mat_v5_small(tmp_path):
    with open_image(psoct_mat(tmp_path / "r.mat", v73=False, operator="Jane Doe"), "mat") as src:
        assert (src.info.axes, src.info.shape) == ("zyx", (4, 16, 12))
        assert "Jane Doe" in src.terms
        assert src.level(0).compute().shape == (4, 16, 12)


def test_mat_v5_too_large(tmp_path, monkeypatch):
    path = psoct_mat(tmp_path / "r.mat", v73=False)
    monkeypatch.setattr(readers, "MAT_V5_MAX_BYTES", 16)
    with pytest.raises(UnsupportedFormat) as exc:
        open_image(path, "mat")
    assert str(exc.value) == "MATLAB v5 file too large to read lazily: save as v7.3"


def test_sparse_bigtiff_open_bounded(tmp_path, monkeypatch):
    path = sparse_bigtiff(4 * 2**30, tmp_path / "big.tif")

    def open_info():
        src = open_image(path, "tiff")
        return src, src.info

    (src, info), peak = _peak(open_info)
    try:
        assert peak < 64 * MiB, peak
        assert info.axes == "yx" and info.shape == (65536, 32768)
        monkeypatch.setattr(micr, "MAX_BLOCK_BYTES", 4 * MiB)
        arr = src.level(0)  # one 4 GiB strip: read through a map, in row blocks
        assert _block_bytes(arr) <= 4 * MiB
        _, peak = _peak(lambda: arr.blocks[0, 0].compute())
        assert peak < 12 * MiB, peak
    finally:
        src.close()


def test_huge_plane_blocks(tmp_path, monkeypatch):
    path = striped_tiff(tmp_path / "striped.tif", (6000, 6000), np.uint16)
    monkeypatch.setattr(micr, "MAX_BLOCK_BYTES", 4 * MiB)
    with open_image(path, "tiff") as src:
        arr = src.level(0)
        assert arr.shape == (6000, 6000)
        assert 6000 * 6000 * 2 > 4 * MiB  # one plane is larger than the block limit
        assert _block_bytes(arr) <= 4 * MiB
        one, peak = _peak(lambda: arr.blocks[0, 0].compute())
        assert one.nbytes <= 4 * MiB
        assert peak < 12 * MiB, peak


@pytest.mark.parametrize("version,fmt", [("0.5", 3), ("0.4", 2)])
def test_ome_zarr_v2_v3_info(tmp_path, version, fmt):
    store = ome_zarr(tmp_path / "x.ome.zarr", version)
    with open_image(store, "ome-zarr") as src:
        info = src.info
        assert info.zarr_format == fmt and info.ngff_version == version
        assert info.levels == 2
        assert (info.axes, info.shape) == ("czyx", (2, 8, 64, 64))
        assert info.pixel_size == {"x": 0.5, "y": 0.5, "z": 1.0} and info.pixel_unit == "um"
        assert [c.name_code for c in info.channels] == ["ch0", "ch1"]
        assert src.level(1).shape == (2, 8, 32, 32)
        assert src.level(1).compute().dtype == np.uint16


def test_visor_numeric_fields_only(tmp_path):
    tile = visor_tile(tmp_path / "MN27_20250422_visor_488")
    with open_image(tile, "visor") as src:
        info = src.info
        assert info.pixel_size == {"x": 1.0, "y": 1.0, "z": 3.5}
        assert [(c.excitation_nm, c.name_code) for c in info.channels] == [(488.0, "ch488")]
        assert {"jane doe", "lab-workstation-7", "20250422"} <= tokens("\n".join(src.terms))
        assert not tokens(repr(info))


def test_bioio_family_through_ome(tmp_path, monkeypatch):
    """czi/nd2/lif go through bioio; its OME metadata is allowlisted like an OME-TIFF's."""
    import xml.etree.ElementTree as ET

    import dask.array as da
    from micr_fixtures import _planted_ome_xml
    from ome_types import from_xml

    class FakeDims:
        order = "TCZYX"

    class FakeImage:
        dims = FakeDims()
        shape = (1, 2, 4, 64, 64)
        dtype = np.dtype("uint16")
        dask_data = da.zeros(shape, dtype="uint16", chunks=(1, 1, 1, 64, 64))
        ome_metadata = from_xml(_planted_ome_xml((2, 4, 64, 64)))
        metadata = ET.fromstring("<ImageDocument><User><Name>czi-operator-xyz</Name></User>"
                                 "<Info Host='czi-host-xyz'/></ImageDocument>")
        channel_names = ["Slide 42 Smith ch0", "Slide 42 Smith ch1"]
        resolution_levels = (0,)

    monkeypatch.setattr(readers, "_bioimage", lambda loc, fam: FakeImage())
    with open_image(tmp_path / "x.czi", "czi") as src:
        assert (src.info.family, src.info.axes, src.info.shape) == ("czi", "czyx", (2, 4, 64, 64))
        assert [c.name_code for c in src.info.channels] == ["ch488", "ch561"]
        assert src.level(0).shape == (2, 4, 64, 64)
        assert not tokens(repr(src.info))
        assert {"jane doe", "slide 42 smith", "scope-sn-4711"} <= tokens("\n".join(src.terms))
        assert {"czi-operator-xyz", "czi-host-xyz"} <= src.terms  # raw vendor metadata


def test_unsupported_family_message(tmp_path):
    with pytest.raises(UnsupportedFormat) as exc:
        open_image(tmp_path / "x.vsi", "unsupported")
    assert str(exc.value) == BIOFORMATS_MESSAGE
    assert BIOFORMATS_MESSAGE == "needs Bio-Formats (not included): export to OME-TIFF or OME-Zarr first"


def test_adapter_hook(tmp_path, monkeypatch):
    monkeypatch.setattr(readers, "_ADAPTERS", {})
    seen: list[Path] = []
    info = ImageInfo(family="labfmt", axes="yx", shape=(2, 2), dtype="uint8")

    class Fake:
        def __init__(self, loc):
            seen.append(loc)
            self.info, self.terms = info, set()

        def level(self, i):
            import dask.array as da

            return da.zeros((2, 2), dtype="uint8")

        def close(self):
            pass

    register_reader("labfmt", Fake)
    src = open_image(tmp_path / "a.lab", "labfmt")
    assert seen == [tmp_path / "a.lab"] and src.info is info
    assert isinstance(src, ImageSource)
    # an adapter can also take over a built-in family
    register_reader("unsupported", Fake)
    assert open_image(tmp_path / "b.vsi", "unsupported").info is info


def test_plan_chunks():
    assert plan_chunks((6000, 6000), 2, 4 * MiB, native=(16, 6000)) == (336, 6000)
    assert plan_chunks((10, 10), 1, 1000) == (10, 10)
    c = plan_chunks((4, 3000, 3000), 2, MiB)
    assert math.prod(c) * 2 <= MiB and c[0] == 1
    assert plan_chunks((32, 24, 4), 4, 1024, order="F") == (32, 8, 1)


# --- fix round 1: every dropped string is a term; NGFF version allowlist; local str stores ---

def test_tiff_terms_every_tag_and_vendor_metadata(tmp_path):
    """Per-page descriptions (second and last page), Micro-Manager JSON and XMP are all terms."""
    xmp = (b'<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/'
           b'22-rdf-syntax-ns#" xmlns:dc="http://purl.org/dc/elements/1.1/"><rdf:Description>'
           b'<dc:creator>Slide 42 Smith</dc:creator></rdf:Description></rdf:RDF></x:xmpmeta>')
    mm = '{"Operator": "jdoe@example.org", "Computer": "lab-workstation-7"}'
    path = tmp_path / "stack.tif"
    n = readers.TERM_PAGES + 6
    with tifffile.TiffWriter(str(path)) as tw:
        for i in range(n):
            desc = {1: "annotation secret", n - 1: "Operator = SCOPE-SN-4711"}.get(i, "plain")
            extratags = [(700, "B", len(xmp), xmp, True), (51123, "s", 0, mm, True)] if i == 0 else []
            tw.write(np.zeros((4, 4), np.uint8), description=desc, metadata=None,
                     photometric="minisblack", extratags=extratags)
    with open_image(path, "tiff") as src:
        found = tokens("\n".join(src.terms))
        assert {"annotation secret", "slide 42 smith", "jdoe@example.org", "lab-workstation-7",
                "scope-sn-4711"} <= found, found
        assert "SCOPE-SN-4711" in src.terms  # "key = value" lines give their value too
        assert not tokens(repr(src.info))


def test_tiff_terms_imagej_info(tmp_path):
    path = tmp_path / "ij.tif"
    tifffile.imwrite(str(path), np.zeros((3, 8, 8), np.uint16), imagej=True,
                     metadata={"axes": "ZYX", "Info": "Experimenter: Jane Doe\nSample = H17"})
    with open_image(path, "tiff") as src:
        assert {"jane doe", "h17"} <= tokens("\n".join(src.terms))
        assert {"Jane Doe", "H17"} <= src.terms


def test_ome_xml_without_prolog_is_not_kept(tmp_path):
    from micr_fixtures import _planted_ome_xml

    xml = _planted_ome_xml((1, 1, 8, 8))
    xml = xml[xml.index("<OME"):] if not xml.startswith("<OME") else xml
    path = tmp_path / "noprolog.ome.tif"
    tifffile.imwrite(str(path), np.zeros((8, 8), np.uint16), description=xml, metadata=None)
    with open_image(path, "ome-tiff") as src:
        assert {"jane doe", "slide 42 smith", "annotation secret"} <= tokens("\n".join(src.terms))
        assert not tokens(repr(src.info))
        assert not any(t.lstrip().startswith("<OME") for t in src.terms)  # values, not the document


def test_series_name_is_not_a_skip_signal(tmp_path):
    """A user's own series name (shaped/OME) never makes a series a label or macro."""
    path = tmp_path / "named.tif"
    tifffile.imwrite(str(path), np.zeros((8, 8), np.uint16), metadata={"Name": "label"})
    with open_image(path, "tiff") as src:
        assert src.info.series_skipped == [] and src.info.shape == (8, 8)


def test_oversized_compressed_chunks_refused(tmp_path, monkeypatch):
    path = tmp_path / "zlib.tif"
    tifffile.imwrite(str(path), np.zeros((512, 512), np.uint16), compression="zlib",
                     rowsperstrip=512, metadata=None)
    monkeypatch.setattr(micr, "MAX_BLOCK_BYTES", 64 * 1024)  # a 512 KiB strip > 4 x 64 KiB
    with open_image(path, "tiff") as src:
        with pytest.raises(UnsupportedFormat) as exc:
            src.level(0)
    assert str(exc.value) == "compressed tiles larger than the block limit: re-save with smaller tiles"


def _set_ngff_version(store: Path, version: str, value: str) -> None:
    import json

    if version == "0.5":
        meta = json.loads((store / "zarr.json").read_text())
        meta["attributes"]["ome"]["version"] = value
        (store / "zarr.json").write_text(json.dumps(meta))
    else:
        attrs = json.loads((store / ".zattrs").read_text())
        attrs["multiscales"][0]["version"] = value
        (store / ".zattrs").write_text(json.dumps(attrs))


@pytest.mark.parametrize("version", ["0.5", "0.4"])
def test_ngff_version_allowlisted(tmp_path, version):
    store = ome_zarr(tmp_path / "x.ome.zarr", version)
    _set_ngff_version(store, version, "0.4-Jane Doe")
    with open_image(store, "ome-zarr") as src:
        assert src.info.ngff_version is None
        assert "0.4-Jane Doe" in src.terms and not tokens(repr(src.info))


def test_ome_zarr_str_location_reads_ome_xml(tmp_path):
    from micr_fixtures import _planted_ome_xml

    store = ome_zarr(tmp_path / "x.ome.zarr", "0.5")
    (store / "OME").mkdir()
    (store / "OME" / "METADATA.ome.xml").write_text(_planted_ome_xml((2, 8, 64, 64)))
    with open_image(str(store), "ome-zarr") as src:
        assert [c.name_code for c in src.info.channels] == ["ch488", "ch561"]
        assert src.info.objective_magnification == 20.0
        assert {"jane doe", "slide 42 smith", "scope-sn-4711"} <= tokens("\n".join(src.terms))
        assert not tokens(repr(src.info))
