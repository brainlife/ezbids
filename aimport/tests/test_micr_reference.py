"""Task 9: reference datasets (OME-Zarr inputs): metadata written locally, chunks left at the source,
and the chunk map (micr/reference.py) that the upload and the QA viewer resolve through."""
from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import pytest
import zarr

from aimport import server
from aimport.micr import readers, reference
from aimport.micr.convert import NgffCheckError, check_ome_zarr
from aimport.micr.metadata import PixelSizeUnknown, sidecar, with_plan_pixel_size
from aimport.micr.reference import chunk_keys, key_ok, resolve, write_reference
from aimport.pseudonyms import PseudonymKey
from conftest import MICR_PLANTED
from fixtures.micr_fixtures import METADATA_FILES, ome_zarr
from test_micr_convert import _assert_no_planted, _server_execute, plan_and_write
from test_micr_remote import local_servers  # noqa: F401 - the local Range server fixture

KiB = 2**10


@pytest.fixture
def key(tmp_path):
    k = PseudonymKey.load(tmp_path / "keys", "proj")
    yield k
    k.close()


def _planted_v3(store: Path) -> Path:
    """An NGFF 0.5 store with planted array attributes and an OME-XML document."""
    from micr_fixtures import _planted_ome_xml

    ome_zarr(store, "0.5")
    for lvl in ("0", "1"):
        doc = json.loads((store / lvl / "zarr.json").read_text())
        doc["attributes"] = {"operator": "Jane Doe", "note": "annotation secret"}
        (store / lvl / "zarr.json").write_text(json.dumps(doc))
    (store / "OME").mkdir()
    (store / "OME" / "METADATA.ome.xml").write_text(_planted_ome_xml((2, 8, 64, 64)))
    return store


def _chunk_files(root: Path) -> list[Path]:
    return [p for p in root.rglob("*") if p.is_file() and p.name not in METADATA_FILES]


def _reference(tmp_path, version="0.5", store=None):
    store = store or ome_zarr(tmp_path / "in" / "Moe_Slice_051.ome.zarr", version)
    dest = tmp_path / "out" / "x.ome.zarr"
    with readers.open_image(store, "ome-zarr") as src:
        info = src.info
        arrays = write_reference(src, {"input": "Moe_Slice_051.ome.zarr"}, dest, info)
    return store, dest, info, arrays


# --- writing --------------------------------------------------------------------------------------


@pytest.mark.parametrize("version", ["0.5", "0.4"])
def test_reference_writes_metadata_only(tmp_path, version):
    store, dest, info, arrays = _reference(tmp_path, version)
    files = [p for p in dest.rglob("*") if p.is_file()]
    assert files and all(p.stat().st_size <= 64 * KiB for p in files)
    assert _chunk_files(dest) == []
    assert set(arrays) == {"0", "1"}
    car = sidecar(info, None)
    check_ome_zarr(dest, car, version, info.shape, info.dtype, reference=True)  # metadata only
    # the rebuilt arrays read the source's chunks unchanged
    for sub, meta in arrays.items():
        assert meta["source"] == {"input": f"Moe_Slice_051.ome.zarr/{sub}"}
        for k in chunk_keys(meta):
            src_obj = store / sub / k
            if src_obj.is_file():
                target = dest / sub / k
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(src_obj.read_bytes())
        np.testing.assert_array_equal(zarr.open_array(str(dest / sub), mode="r")[...],
                                      zarr.open_array(str(store / sub), mode="r")[...])


def test_array_attributes_dropped(tmp_path):
    store = _planted_v3(tmp_path / "in" / "Moe_Slice_051.ome.zarr")
    _, dest, _, _ = _reference(tmp_path, store=store)
    for lvl in ("0", "1"):
        doc = json.loads((dest / lvl / "zarr.json").read_text())
        assert "attributes" not in doc and doc["dimension_names"] == ["c", "z", "y", "x"]
    assert not (dest / "OME").exists()
    assert not list(dest.rglob("*.xml"))
    _assert_no_planted(dest)
    for p in dest.rglob("*"):
        if p.is_file():
            assert b"MICR_PLANTED" not in p.read_bytes()
            assert not {t for t in MICR_PLANTED if t.encode() in p.read_bytes().lower()}


def test_v3_source_stays_v3(tmp_path):
    _, dest, info, arrays = _reference(tmp_path, "0.5")
    root = json.loads((dest / "zarr.json").read_text())
    assert root["zarr_format"] == 3 and root["attributes"]["ome"]["version"] == "0.5"
    doc = json.loads((dest / "0" / "zarr.json").read_text())
    src = json.loads((tmp_path / "in" / "Moe_Slice_051.ome.zarr" / "0" / "zarr.json").read_text())
    for k in ("shape", "data_type", "chunk_grid", "chunk_key_encoding", "codecs", "fill_value"):
        assert doc[k] == src[k]
    assert arrays["0"]["zarr_format"] == 3 and arrays["0"]["chunk_grid"] == [1, 8, 64, 64]
    assert arrays["0"]["codec_bytes_hint"] == 8 * 64 * 64 * 2


def test_v2_source_stays_v2(tmp_path):
    _, dest, _, arrays = _reference(tmp_path, "0.4")
    assert json.loads((dest / ".zgroup").read_text())["zarr_format"] == 2
    attrs = json.loads((dest / ".zattrs").read_text())
    assert attrs["multiscales"][0]["version"] == "0.4"
    doc = json.loads((dest / "0" / ".zarray").read_text())
    assert doc["zarr_format"] == 2 and doc["dimension_separator"] == "."
    assert not (dest / "0" / ".zattrs").exists()
    assert arrays["0"]["separator"] == "." and arrays["0"]["zarr_format"] == 2


def test_reference_pixel_size_from_plan(tmp_path):
    """The NGFF scale comes from the plan entry's pixel size, never from the source as is."""
    store = ome_zarr(tmp_path / "in" / "s.ome.zarr", "0.5")

    class Entry:
        pixel_size, pixel_size_units, suffix, entities = [0.25, 0.25, 3.0], "um", "SPIM", {}

    dest = tmp_path / "out" / "x.ome.zarr"
    with readers.open_image(store, "ome-zarr") as src:
        info = with_plan_pixel_size(src.info, Entry)
        write_reference(src, {"input": "s.ome.zarr"}, dest, info)
    ms = json.loads((dest / "zarr.json").read_text())["attributes"]["ome"]["multiscales"][0]
    assert ms["datasets"][0]["coordinateTransformations"][0]["scale"] == [1.0, 3.0, 0.25, 0.25]
    assert ms["datasets"][1]["coordinateTransformations"][0]["scale"] == [1.0, 3.0, 0.5, 0.5]
    check_ome_zarr(dest, sidecar(info, Entry), "0.5", info.shape, info.dtype, reference=True)
    with pytest.raises(NgffCheckError):
        check_ome_zarr(dest, {**sidecar(info, Entry), "PixelSize": [1.0, 1.0, 1.0]}, "0.5",
                       info.shape, info.dtype, reference=True)


def test_wrong_source_scale_follows_the_sizes(tmp_path):
    """A source level whose scale disagrees with its size (as in the CMC PS-OCT store) is described
    by the factor its size gives; a level that agrees keeps the source's factor."""
    from aimport.micr.reference import _factor

    store = ome_zarr(tmp_path / "in" / "s.ome.zarr", "0.5", shape=(1, 4, 64, 64), levels=3)
    doc = json.loads((store / "zarr.json").read_text())
    ds = doc["attributes"]["ome"]["multiscales"][0]["datasets"]
    ds[2]["coordinateTransformations"][0]["scale"][-2:] = [8.0, 8.0]  # the size says 4
    (store / "zarr.json").write_text(json.dumps(doc))
    _, dest, info, _ = _reference(tmp_path, store=store)
    ms = json.loads((dest / "zarr.json").read_text())["attributes"]["ome"]["multiscales"][0]
    assert [d["coordinateTransformations"][0]["scale"][-1] for d in ms["datasets"]] == [0.5, 1.0, 2.0]
    check_ome_zarr(dest, sidecar(info, None), "0.5", info.shape, info.dtype, reference=True)
    assert _factor(8500, 16, 512.0) == 512 and _factor(11000, 21, 512.0) == 512
    assert _factor(8500, 1062, 16.0) == 8 and _factor(5, 3, 2.0) == 2 and _factor(9, 7, 1.3) == 1.3


def test_reference_reads_no_chunk(tmp_path, monkeypatch):
    """Planning and writing a reference never read a chunk: the source's chunks may be absent."""
    from fixtures.micr_fixtures import strip_chunks

    store = strip_chunks(ome_zarr(tmp_path / "in" / "s.ome.zarr", "0.5"))
    dest = tmp_path / "out" / "x.ome.zarr"
    with readers.open_image(store, "ome-zarr") as src:
        write_reference(src, {"input": "s.ome.zarr"}, dest, src.info)
    check_ome_zarr(dest, sidecar(src.info, None), "0.5", src.info.shape, src.info.dtype, reference=True)


# --- the chunk map through the writer and the server ----------------------------------------------


def test_chunk_map_outside_output(tmp_path, key, schema):
    inp = tmp_path / "in"
    _planted_v3(inp / "Moe_Slice_051.ome.zarr")
    chunks: dict = {}
    plan, out, manifest = plan_and_write(inp, tmp_path, key, schema, suffix="SPIM", chunk_map=chunks)
    (e,) = [e for e in plan.entries if e.modality == "micr" and not e.exclude]
    assert e.write_mode == "reference"
    (rel,) = manifest[e.id]
    assert set(chunks["arrays"]) == {f"{rel}/0", f"{rel}/1"}
    assert chunks["arrays"][f"{rel}/0"]["source"] == {"input": "Moe_Slice_051.ome.zarr/0"}
    assert not list(out.rglob("*.chunks.json"))
    assert _chunk_files(out / rel) == []
    _assert_no_planted(out)
    car = json.loads((out / (rel[: -len(".ome.zarr")] + ".json")).read_text())
    assert car["PixelSize"] == [0.5, 0.5, 1.0] and car["PixelSizeUnits"] == "um"
    # every output chunk path resolves inside the input
    meta = chunks["arrays"][f"{rel}/0"]
    for k in chunk_keys(meta):
        assert resolve(chunks, f"{rel}/0/{k}", inp) == (inp / "Moe_Slice_051.ome.zarr" / "0" / k).resolve()


def test_server_execute_reference(tmp_path, monkeypatch):
    inp = tmp_path / "in"
    _planted_v3(inp / "Moe_Slice_051.ome.zarr")
    s, events = _server_execute(tmp_path, monkeypatch, inp)
    assert s["stage"] == "validated", s
    work = tmp_path / "work"
    assert s["chunk_map"] == "output/bids.chunks.json"
    assert "Moe" not in json.dumps(s) and "arrays" not in json.dumps(s)
    state = json.loads((work / server.OUTPUT_STATE).read_text())
    assert state["chunk_map"] == "output/bids.chunks.json"
    cm = json.loads((work / "output" / "bids.chunks.json").read_text())
    assert cm["version"] == 1 and len(cm["arrays"]) == 2
    out = work / "output" / "bids"
    assert not list(out.rglob("*.chunks.json")) and _chunk_files(out / next(iter(cm["arrays"])).rsplit("/", 1)[0]) == []
    for t in [e["message"] for e in events]:
        assert "moe" not in t.lower()


def test_rescan_clears_chunk_map(tmp_path, monkeypatch):
    inp = tmp_path / "in"
    ome_zarr(inp / "Moe_Slice_051.ome.zarr", "0.5")
    s, _ = _server_execute(tmp_path, monkeypatch, inp)
    assert s["stage"] == "validated", s
    cm = tmp_path / "work" / "output" / "bids.chunks.json"
    assert cm.is_file()
    srv = server.Server(inp, tmp_path / "work", tmp_path / "keys")
    srv.reset_output()
    assert not cm.exists() and not (tmp_path / "work" / server.OUTPUT_STATE).exists()


def test_failed_execute_removes_chunk_map(tmp_path, monkeypatch):
    inp = tmp_path / "in"
    ome_zarr(inp / "Moe_Slice_051.ome.zarr", "0.5")
    monkeypatch.setattr(server, "deface", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    s, _ = _server_execute(tmp_path, monkeypatch, inp)
    assert s["stage"] == "failed"
    assert not (tmp_path / "work" / "output" / "bids.chunks.json").exists()
    assert "chunk_map" not in s


def test_chunk_map_path(tmp_path):
    """The chunk map is next to bids/, never inside it; a new server has none."""
    srv = server.Server(tmp_path / "in", tmp_path / "work", tmp_path / "keys")
    assert srv.chunk_map == tmp_path / "work" / "output" / "bids.chunks.json"
    assert not srv.chunk_map.exists()


# --- chunk keys and resolve -------------------------------------------------------------------------


def test_chunk_keys_v2_v3():
    v2 = {"zarr_format": 2, "shape": [2, 5], "chunk_grid": [1, 2], "separator": "."}
    assert list(chunk_keys(v2)) == ["0.0", "0.1", "0.2", "1.0", "1.1", "1.2"]
    v2s = {**v2, "separator": "/"}
    assert list(chunk_keys(v2s))[:2] == ["0/0", "0/1"]
    v3 = {"zarr_format": 3, "shape": [3, 4, 4], "chunk_grid": [3, 2, 4], "separator": "/"}
    assert list(chunk_keys(v3)) == ["c/0/0/0", "c/0/1/0"]
    assert list(chunk_keys({**v3, "separator": "."})) == ["c.0.0.0", "c.0.1.0"]
    assert list(chunk_keys({**v3, "key_encoding": "v2", "separator": "."})) == ["0.0.0", "0.1.0"]
    assert list(chunk_keys({"zarr_format": 3, "shape": [], "chunk_grid": [], "separator": "/"})) == ["c"]
    assert list(chunk_keys({"zarr_format": 2, "shape": [], "chunk_grid": [], "separator": "."})) == ["0"]
    assert list(chunk_keys({**v2, "shape": [0, 5]})) == []
    for meta in (v2, v2s, v3):
        assert all(key_ok(meta, k) for k in chunk_keys(meta))
    assert not key_ok(v3, "c/0/2/0") and not key_ok(v3, "c/00/0/0") and not key_ok(v3, "0/0/0")
    assert not key_ok(v2, "0.0.0") and not key_ok(v2, "c.0.0") and not key_ok(v2, "0/0")


def _map(source):
    return {"version": 1, "arrays": {"sub-01/micr/x.ome.zarr/0": {
        "source": source, "zarr_format": 3, "shape": [4, 4], "chunk_grid": [2, 2], "separator": "/",
        "codec_bytes_hint": 8}}}


def test_resolve(tmp_path):
    inp = tmp_path / "in"
    (inp / "s.zarr" / "0").mkdir(parents=True)
    m = _map({"input": "s.zarr/0"})
    assert resolve(m, "sub-01/micr/x.ome.zarr/0/c/1/0", inp) == inp.resolve() / "s.zarr/0/c/1/0"
    u = _map({"url": "s3://bucket-name/CMC/s.zarr/0"})
    assert resolve(u, "sub-01/micr/x.ome.zarr/0/c/0/1", inp) == \
        "https://bucket-name.s3.amazonaws.com/CMC/s.zarr/0/c/0/1"


@pytest.mark.parametrize("out_rel", [
    "../x", "/etc/passwd", "sub-01/micr/x.ome.zarr/0/%2e%2e/x", "sub-01/micr/x.ome.zarr/0/c/0/../../x",
    "sub-01/micr/x.ome.zarr/0/0/../../x", "sub-01/micr/x.ome.zarr/0", "sub-01/micr/x.ome.zarr/0/",
    "sub-01/micr/x.ome.zarr/0/zarr.json", "sub-01/micr/x.ome.zarr/1/c/0/0", "sub-01/micr/x.ome.zarr/0/c/2/0",
    "sub-01/micr/x.ome.zarr/0/c//0", "sub-01/micr/x.ome.zarr/0/c\\0\\0", "sub-01/micr/x.ome.zarr/0/c/0/0\x00",
    "sub-01/micr/x.ome.zarr/0x/c/0/0",
])
def test_resolve_refuses(tmp_path, out_rel):
    inp = tmp_path / "in"
    (inp / "s.zarr" / "0").mkdir(parents=True)
    with pytest.raises(ValueError):
        resolve(_map({"input": "s.zarr/0"}), out_rel, inp)


@pytest.mark.parametrize("source", [
    {"input": "../outside"}, {"input": "/etc"}, {"input": "s.zarr/../../outside"}, {"input": "%2e%2e/x"},
    {"url": "file:///etc/passwd"}, {"url": "http://example.org/s.zarr"}, {"url": "https://127.0.0.1/s"},
    {"url": "https://example.org/a/%2e%2e/b"}, {"input": "s.zarr", "url": "https://example.org/s"}, {},
    "s.zarr",
])
def test_resolve_refuses_sources(tmp_path, source):
    inp = tmp_path / "in"
    (inp / "s.zarr").mkdir(parents=True)
    (tmp_path / "outside").mkdir()
    with pytest.raises(ValueError):
        resolve(_map(source), "sub-01/micr/x.ome.zarr/0/c/0/0", inp)


def test_resolve_refuses_symlink(tmp_path):
    inp = tmp_path / "in"
    inp.mkdir()
    outside = tmp_path / "outside" / "s.zarr"
    (outside / "c" / "0").mkdir(parents=True)
    (outside / "c" / "0" / "0").write_bytes(b"secret")
    os.symlink(outside, inp / "s.zarr")
    with pytest.raises(ValueError, match="symlink"):
        resolve(_map({"input": "s.zarr"}), "sub-01/micr/x.ome.zarr/0/c/0/0", inp)
    (inp / "t.zarr" / "c" / "0").mkdir(parents=True)  # a symlinked chunk inside a real folder
    os.symlink(outside / "c" / "0" / "0", inp / "t.zarr" / "c" / "0" / "0")
    with pytest.raises(ValueError):
        resolve(_map({"input": "t.zarr"}), "sub-01/micr/x.ome.zarr/0/c/0/0", inp)


# --- remote ---------------------------------------------------------------------------------------


def test_remote_reference_reads_metadata_only(tmp_path, local_servers):
    base, root, _ = local_servers("served")
    ome_zarr(root / "CMC" / "s.ome.zarr", "0.5")
    from aimport.micr import remote

    src, counter = remote.open_remote(f"{base}/CMC/s.ome.zarr", "ome-zarr")
    try:
        dest = tmp_path / "out" / "x.ome.zarr"
        arrays = write_reference(src, {"url": f"{base}/CMC/s.ome.zarr"}, dest, src.info)
    finally:
        src.close()
    assert arrays["0"]["source"] == {"url": f"{base}/CMC/s.ome.zarr/0"}
    stored = sum(p.stat().st_size for p in _chunk_files(root))
    assert counter.total < stored  # metadata only
    assert _chunk_files(dest) == []


# --- docker -----------------------------------------------------------------------------------------


@pytest.mark.docker
@pytest.mark.parametrize("version", ["0.5", "0.4"])
def test_reference_dataset_validates(tmp_path, key, schema, version):
    """The metadata-only reference dataset passes the BIDS validator (Task 1 ruling)."""
    from aimport.validate import validate_bids

    inp = tmp_path / "in"
    ome_zarr(inp / "Moe_Slice_051.ome.zarr", version)
    _, out, _ = plan_and_write(inp, tmp_path, key, schema, suffix="SPIM", chunk_map={})
    (store,) = list(out.rglob("*.ome.zarr"))
    assert _chunk_files(store) == []
    r = validate_bids(out)
    assert r.ok, json.dumps({"errors": r.errors, "warnings": r.warnings}, indent=1)


# --- network (public CMC bucket; see tests/DATASETS.md) ---------------------------------------------


@pytest.mark.network
def test_cmc_psoct_zarr_reference(tmp_path):
    """The real PS-OCT store (Zarr v3, consolidated, scale<k>/image) is referenced from its metadata
    alone: under 1 MiB fetched, nothing but metadata written, the self-check passes."""
    from aimport.micr import remote

    from types import SimpleNamespace

    url = "s3://apex-connects/CMC/Derivatives/Moe/PS-OCT/Zarr/Moe_Slice_051.ome.zarr"
    src, counter = remote.open_remote(url, "ome-zarr", max_bytes=2**20)
    try:
        # its axes have no units: never assumed; the reviewer's unit (here um) is what is written
        assert src.info.pixel_unit is None and src.info.pixel_size == {"x": 1.0, "y": 1.0}
        info = with_plan_pixel_size(src.info, SimpleNamespace(pixel_size=[10.0, 10.0], pixel_size_units="um"))
        dest = tmp_path / "x.ome.zarr"
        arrays = write_reference(src, {"url": url}, dest, info)
        # its faults (translation on c, levels 3 and 4 declaring 16 and 64 for arrays halved 3 and 4
        # times, no units) are corrected in the rebuilt metadata
        assert_cmc_faults_corrected(dest, info, 10.0, [(1, 1), (2, 2), (4, 4), (8, 8), (16, 16), (512, 512)])
    finally:
        src.close()
    assert counter.total < 2**20, counter
    assert arrays["0"]["source"]["url"].startswith("https://apex-connects.s3.amazonaws.com/CMC/")
    assert _chunk_files(dest) == []


# --- fix round 1: plan-time refusal, the term scan, factors, merging ----------------------------------


def _scan_plan(inp: Path, work: Path, key, schema, mutate=None):
    from aimport.micr.module import MicrModule, RECORDS_FILE

    m = MicrModule()
    claim = m.claim(inp, [])
    m.scan(inp, claim, work, lambda msg: None)
    if mutate is not None:
        records = json.loads((work / RECORDS_FILE).read_text())
        for rec in records:
            mutate(rec)
        (work / RECORDS_FILE).write_text(json.dumps(records))
    return m.plan(work, key, set(), None, schema, "bids").entries


def _reorder_axes(store: Path) -> None:
    doc = json.loads((store / "zarr.json").read_text())
    ms = doc["attributes"]["ome"]["multiscales"][0]
    ms["axes"][0], ms["axes"][1] = ms["axes"][1], ms["axes"][0]  # z, c, y, x: needs a transpose
    (store / "zarr.json").write_text(json.dumps(doc))


def test_plan_refuses_reordered_axes(tmp_path, key, schema):
    store = ome_zarr(tmp_path / "in" / "s.ome.zarr", "0.5")
    _reorder_axes(store)
    (e,) = _scan_plan(tmp_path / "in", tmp_path / "work", key, schema)
    assert (e.status, e.exclude, e.write_mode) == ("unsupported", True, "")
    assert e.reason == "OME-Zarr layout not referenceable: axes need reordering"
    with readers.open_image(store, "ome-zarr") as src:  # and at execute (defence in depth)
        with pytest.raises(reference.ReferenceRefused, match="axes need reordering"):
            write_reference(src, {"input": "s.ome.zarr"}, tmp_path / "out" / "x.ome.zarr", src.info)


def test_plan_refuses_symlinked_store(tmp_path, key, schema):
    real = ome_zarr(tmp_path / "elsewhere" / "s.ome.zarr", "0.5")
    (tmp_path / "in").mkdir()
    os.symlink(real.parent, tmp_path / "in" / "linked")
    entries = _scan_plan(tmp_path / "in", tmp_path / "work", key, schema)
    assert [(e.status, e.reason) for e in entries] in (
        [], [("unsupported", "OME-Zarr layout not referenceable: the store is reached through a symlink")])
    # a symlinked array dir inside a real store
    store = ome_zarr(tmp_path / "in2" / "t.ome.zarr", "0.5")
    os.rename(store / "1", tmp_path / "lvl1")
    os.symlink(tmp_path / "lvl1", store / "1")
    (e,) = _scan_plan(tmp_path / "in2", tmp_path / "work2", key, schema)
    assert (e.status, e.reason) == ("unsupported", "OME-Zarr layout not referenceable: the store is reached "
                                                   "through a symlink")
    assert reference.symlinked(tmp_path / "in2", "t.ome.zarr", ["1"])
    assert not reference.symlinked(tmp_path / "in2", "t.ome.zarr", ["0"])


@pytest.mark.parametrize("change,reason", [
    ({"zarr_formats": [2, 3]}, "arrays mix Zarr formats"),
    ({"storage_transformers": True}, "storage transformers"),
    ({"grids": ["rectilinear", "regular"]}, "irregular chunk grid"),
    ({"key_encodings": ["custom"]}, "unknown chunk key encoding"),
    ({"separators": ["|"]}, "unknown chunk key separator"),
    ({"paths_ok": False}, "a dataset path leaves the store"),
    ({"axes_identity": False}, "axes need reordering"),
    ({"symlink": True}, "the store is reached through a symlink"),
])
def test_plan_refusal_classes(tmp_path, key, schema, change, reason):
    """Each layout fact the scan records makes the entry unsupported at planning, with its reason."""
    ome_zarr(tmp_path / "in" / "s.ome.zarr", "0.5")

    def mutate(rec):
        rec["info"]["reference_layout"].update(change)

    (e,) = _scan_plan(tmp_path / "in", tmp_path / "work", key, schema, mutate)
    assert (e.status, e.exclude) == ("unsupported", True)
    assert e.reason == "OME-Zarr layout not referenceable: " + reason
    assert reference.layout_refusal({**_good_facts(), **change}) == e.reason


def _good_facts():
    return {"axes_identity": True, "zarr_formats": [3], "grids": ["regular"], "key_encodings": ["default"],
            "separators": ["/"], "storage_transformers": False, "paths_ok": True, "symlink": False}


def test_plan_ok_layout_and_old_records(tmp_path, key, schema):
    ome_zarr(tmp_path / "in" / "s.ome.zarr", "0.4")
    (e,) = _scan_plan(tmp_path / "in", tmp_path / "work", key, schema)
    assert e.write_mode == "reference" and e.status != "unsupported"
    (e,) = _scan_plan(tmp_path / "in", tmp_path / "work", key, schema,
                      lambda rec: rec["info"].pop("reference_layout"))
    assert (e.status, e.reason) == ("unsupported", "OME-Zarr layout not recorded: scan again")
    assert reference.layout_refusal(_good_facts()) is None


def test_rebuild_refuses_at_execute(tmp_path, monkeypatch):
    """_rebuild applies the same predicate to each array document (defence in depth)."""
    store = ome_zarr(tmp_path / "in" / "s.ome.zarr", "0.5")
    real = reference._metadata_doc
    with readers.open_image(store, "ome-zarr") as src:
        arr = src.zarr_layout.arrays[0]
        for change, reason in (({"storage_transformers": [{"name": "x"}]}, "storage transformers"),
                               ({"chunk_grid": {"name": "rectilinear"}}, "irregular chunk grid"),
                               ({"chunk_key_encoding": {"name": "custom"}}, "unknown chunk key encoding")):
            monkeypatch.setattr(reference, "_metadata_doc", lambda a, c=change: {**real(a), **c})
            with pytest.raises(reference.ReferenceRefused, match=reason):
                reference._rebuild(arr, "czyx")


def test_term_scan_refuses_filter_labels_and_fill_value(tmp_path):
    store = ome_zarr(tmp_path / "in" / "s.ome.zarr", "0.4")
    z = json.loads((store / "1" / ".zarray").read_text())
    z["filters"] = [{"id": "categorize", "labels": ["Jane-Doe", "x"], "dtype": "<U8", "astype": "|u1"}]
    (store / "1" / ".zarray").write_text(json.dumps(z))
    with readers.open_image(store, "ome-zarr") as src:
        with pytest.raises(reference.ReferenceRefused) as exc:
            write_reference(src, {"input": "s.ome.zarr"}, tmp_path / "a.ome.zarr", src.info, terms={"jane doe"})
    assert "jane" not in str(exc.value).lower()

    store = ome_zarr(tmp_path / "in" / "t.ome.zarr", "0.5")
    z = json.loads((store / "1" / "zarr.json").read_text())
    z.update(data_type="string", fill_value="JANE_DOE", codecs=[{"name": "vlen-utf8"}])
    (store / "1" / "zarr.json").write_text(json.dumps(z))
    with readers.open_image(store, "ome-zarr") as src:
        with pytest.raises(reference.ReferenceRefused):
            write_reference(src, {"input": "t.ome.zarr"}, tmp_path / "b.ome.zarr", src.info, terms={"Jane Doe"})


def test_term_scan_passes_clean_metadata(tmp_path):
    """Generated vocabulary (ch<n> labels, colours, codec names) never trips the scan."""
    store = _planted_v3(tmp_path / "in" / "Moe_Slice_051.ome.zarr")
    with readers.open_image(store, "ome-zarr") as src:
        terms = set(src.terms) | {"Moe", "Slice_051", "ch488", "00FF00", "12"}
        write_reference(src, {"input": "Moe_Slice_051.ome.zarr"}, tmp_path / "x.ome.zarr", src.info, terms=terms)


def test_format_vocabulary_is_never_a_term(tmp_path):
    """Data-type, unit, axis, NGFF and codec words are vocabulary: never collected as terms, and never
    matched by the term scan (a VISoR acqinfo dtype "uint16" refused every uint16 store)."""
    from aimport.micr.metadata import collect_terms, format_vocab

    meta = {"settings": {"dtype": "uint16", "unit": "micrometer", "axis": "space", "codec": "zstd",
                         "operator": "Jane Doe"}, "kind": "Float32", "u": "µm"}
    assert collect_terms(meta) == {"Jane Doe"}
    assert all(format_vocab(w) for w in ("uint16", "UInt16", "float32", "micrometer", "µm", "channel",
                                         "sharding_indexed", "bytes", "scale", "translation"))
    assert not any(format_vocab(w) for w in ("Moe", "H17", "Jane Doe", "uint16x", "250215"))
    store = ome_zarr(tmp_path / "in" / "s.ome.zarr", "0.5")
    with readers.open_image(store, "ome-zarr") as src:
        assert src.info.dtype == "uint16"
        write_reference(src, {"input": "s.ome.zarr"}, tmp_path / "x.ome.zarr", src.info,
                        terms={"uint16", "UINT16", "micrometer", "zstd", "space", "regular", "little"})
        with pytest.raises(reference.ReferenceRefused):  # a real term is still refused
            write_reference(src, {"input": "s.ome.zarr"}, tmp_path / "y.ome.zarr", src.info,
                            terms={"uint16", "regul"})


def _attrs_multiscale(dest: Path) -> dict:
    return json.loads((dest / "zarr.json").read_text())["attributes"]["ome"]["multiscales"][0]


def assert_cmc_faults_corrected(dest: Path, info, pixel: float, factors) -> None:
    """The rebuilt metadata of a CMC-like store: spatial axes carry the plan's unit, no translation on
    the channel axis, and each level's scale is the plan's pixel size times the factor its array holds."""
    ms = _attrs_multiscale(dest)
    assert ms["axes"] == [{"name": "c", "type": "channel"},
                          {"name": "y", "type": "space", "unit": "micrometer"},
                          {"name": "x", "type": "space", "unit": "micrometer"}]
    assert len(ms["datasets"]) == len(factors)
    for ds, (fy, fx) in zip(ms["datasets"], factors):
        by_type = {t["type"]: t for t in ds["coordinateTransformations"]}
        assert by_type["scale"]["scale"] == pytest.approx([1.0, pixel * fy, pixel * fx])
        if "translation" in by_type:
            assert by_type["translation"]["translation"][0] == 0.0
    check_ome_zarr(dest, sidecar(info, None), "0.5", info.shape, info.dtype, reference=True)


def test_cmc_metadata_faults_corrected(tmp_path, key, schema):
    """The CMC PS-OCT faults (no units, a translation on c, coarse scales that disagree with the array
    sizes) are planned as unit unknown and corrected in the rebuilt reference metadata."""
    from micr_fixtures import CMC_PSOCT_FACTORS, cmc_psoct_zarr

    from aimport.planner import PIXEL_UNIT_REASON, apply_plan_edits
    from aimport.plan import Plan

    store = cmc_psoct_zarr(tmp_path / "in" / "PS-OCT" / "Zarr" / "Moe_Slice_051.ome.zarr")
    (e,) = _scan_plan(tmp_path / "in", tmp_path / "work", key, schema)
    assert e.write_mode == "reference" and (e.status, e.exclude) == ("unknown", True)
    assert e.reason == PIXEL_UNIT_REASON and e.pixel_size == [1.0, 1.0] and e.pixel_size_units is None
    assert "unit unknown" in e.description and "µm" not in e.description
    plan = Plan(target="bids", entries=[e])
    apply_plan_edits(plan, [{"id": e.id, "pixel_size_units": "um"}], schema)  # the pixel size edit path
    assert (e.status, e.exclude, e.pixel_size) == ("ok", False, [1.0, 1.0])
    apply_plan_edits(plan, [{"id": e.id, "pixel_size_units": None}], schema)
    assert (e.status, e.reason) == ("unknown", PIXEL_UNIT_REASON)
    apply_plan_edits(plan, [{"id": e.id, "pixel_size_units": "um", "pixel_size": [10.0, 10.0]}], schema)
    assert (e.status, e.exclude) == ("ok", False)
    with readers.open_image(store, "ome-zarr") as src:
        assert src.info.pixel_unit is None
        with pytest.raises(PixelSizeUnknown, match="unit unknown"):  # never assumed to be um
            write_reference(src, {"input": "PS-OCT/Zarr/Moe_Slice_051.ome.zarr"}, tmp_path / "no.ome.zarr", src.info)
        info = with_plan_pixel_size(src.info, e)
        write_reference(src, {"input": "PS-OCT/Zarr/Moe_Slice_051.ome.zarr"}, tmp_path / "x.ome.zarr", info)
    assert_cmc_faults_corrected(tmp_path / "x.ome.zarr", info, 10.0, CMC_PSOCT_FACTORS)


@pytest.mark.parametrize("version", ["0.5", "0.4"])
def test_read_array_caps_decoded_size_without_hint(tmp_path, version):
    """read_array: without codec_bytes_hint the decoded size is the shape times the item size, and the cap holds."""
    store, dest, info, arrays = _reference(tmp_path, version)
    bids = tmp_path / "out"
    chunks = reference.chunk_map({f"x.ome.zarr/{k}": v for k, v in arrays.items()})
    level1 = chunks["arrays"]["x.ome.zarr/1"]
    size = int(np.prod(level1["shape"])) * 2  # uint16
    for meta in (level1, {k: v for k, v in level1.items() if k != "codec_bytes_hint"}):
        chunks["arrays"]["x.ome.zarr/1"] = meta
        with pytest.raises(ValueError, match="too large"):
            reference.read_array(chunks, bids, "x.ome.zarr/1", tmp_path / "in", size - 1)
        got = reference.read_array(chunks, bids, "x.ome.zarr/1", tmp_path / "in", 64 * 2**20)
        np.testing.assert_array_equal(got, zarr.open_array(str(store / "1"), mode="r")[...])
    assert reference._decoded_bytes({"shape": [10, 10]}, {"zarr_format": 3, "data_type": "float32"}, 1) == 400
    with pytest.raises(ValueError, match="data type"):
        reference._decoded_bytes({"shape": [10]}, {"zarr_format": 3, "data_type": "vlen-utf8"}, 1)


def test_factor_prefers_the_size_ratio():
    from aimport.micr.reference import _factor

    assert _factor(11, 3, 2.5) == 3
    assert _factor(8500, 1062, 16.0) == 8 and _factor(8500, 16, 512.0) == 512


def test_level_scale_checked_against_source_factors(tmp_path):
    """With level_factors, a level's scale must be the plan's pixel size times the source's factor."""
    _, dest, info, _ = _reference(tmp_path, "0.5")
    car = sidecar(info, None)
    check_ome_zarr(dest, car, "0.5", info.shape, info.dtype, reference=True,
                   level_factors=[{}, {"x": 2, "y": 2}])
    with pytest.raises(NgffCheckError, match="pixel size times its factor"):
        check_ome_zarr(dest, car, "0.5", info.shape, info.dtype, reference=True,
                       level_factors=[{}, {"x": 4, "y": 2}])
    with readers.open_image(tmp_path / "in" / "Moe_Slice_051.ome.zarr", "ome-zarr") as src:
        assert reference.source_factors(src.info, src.zarr_layout) == [{"z": 1, "y": 1, "x": 1},
                                                                         {"z": 1, "y": 2, "x": 2}]


def test_module_chunk_maps_must_be_disjoint(tmp_path):
    from aimport.modality import ModuleOutput
    from aimport.writer import _Writer

    class Fake:
        name = "fake"

        def write(self, *a, **k):
            return ModuleOutput(chunk_map={"version": 1, "arrays": {"sub-01/micr/x.ome.zarr/0": {}}})

    w = object.__new__(_Writer)
    w.modules, w.work_dir, w.manifest, w.chunk_map = [Fake(), Fake()], tmp_path, None, {}
    w.plan = w.input_dir = w.terms = w.key = w.schema = w.progress = None
    w.dest = lambda rel: tmp_path / rel
    with pytest.raises(ValueError, match="same output array"):
        w.write_modules()


def test_server_uses_the_reference_chunk_map_name():
    assert server.CHUNK_MAP_NAME is reference.CHUNK_MAP_NAME == "bids.chunks.json"


def test_reference_term_scan_skips_bids_words(tmp_path):
    """A run term that is BIDS vocabulary (sub, sample, micr) never refuses a reference; its values still do."""
    from aimport.micr.reference import ReferenceRefused, check_terms

    (tmp_path / "zarr.json").write_text(json.dumps({"attributes": {"note": "sub-01 sample-A micr July11"}}))
    check_terms(tmp_path, {"sub", "sample", "micr", "sub-01"})
    with pytest.raises(ReferenceRefused):
        check_terms(tmp_path, {"sub", "XAtest_sub-July11", "July11"})
