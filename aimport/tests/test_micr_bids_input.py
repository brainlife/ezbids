"""A BIDS micr dataset as input (Task 11, found re-importing bids-examples): its tables beside claimed images,
its suffix, its sample labels and its sidecars' pixel size."""
from __future__ import annotations

import json
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from aimport import server
from aimport.ezbids_runner import EzbidsError
from aimport.micr.module import MicrModule
from aimport.planner import build_plan
from aimport.ezbids_runner import CoreResult
from aimport.pseudonyms import PseudonymKey
from fixtures.micr_fixtures import ome_zarr, planted_ome_tiff

TOKEN = "t" * 32
NO_IMAGING = "Error: Could not find any MRI, PET, or MEG imaging files in upload."


@pytest.fixture
def key(tmp_path):
    k = PseudonymKey.load(tmp_path / "keys", "proj")
    yield k
    k.close()


def _plan(inp: Path, tmp_path: Path, key, schema):
    work = tmp_path / "work"
    m = MicrModule()
    claim = m.claim(inp, [])
    m.scan(inp, claim, work / "micr", lambda msg: None)
    plan = build_plan(CoreResult(), inp, key, set(), None, schema, "bids", exclude=claim.roots,
                      extra_terms=frozenset(m.terms(work / "micr")),
                      planners=[lambda: m.plan(work / "micr", key, set(), None, schema, "bids")])
    return [e for e in plan.entries if e.modality == "micr"]


def _scan_status(inp: Path, tmp_path: Path, monkeypatch, fake_ezbids) -> dict:
    monkeypatch.setattr(server, "client_from_env", lambda: None)
    monkeypatch.setattr(server, "run_ezbids", fake_ezbids)
    app = server.create_app(inp, tmp_path / "work", tmp_path / "keys", TOKEN, [], ["testserver"])
    try:
        c = TestClient(app)
        c.headers["Authorization"] = "Bearer " + TOKEN
        assert c.post("/scan", json={"project_id": "proj"}).status_code == 202
        end = time.time() + 60
        while (s := c.get("/status").json())["stage"] not in ("planned", "failed") and time.time() < end:
            time.sleep(0.05)
        return s
    finally:
        app.state.server.close()


def _no_imaging(staged, log=print, **kw):
    log("+ echo 'Error: Could not find any MRI, PET, or MEG imaging files in upload.'")
    log(NO_IMAGING)
    raise EzbidsError(NO_IMAGING)


def test_tables_beside_claimed_images_need_no_ezbids(tmp_path, monkeypatch):
    """Only tables and text are left for ezBIDS beside the claimed microscopy: its "no imaging files" error means
    an empty MRI side, not a failed scan."""
    inp = tmp_path / "in"
    planted_ome_tiff(inp / "sub-01" / "micr" / "sub-01_sample-A_CONF.ome.tif")
    (inp / "participants.tsv").write_text("participant_id\nsub-01\n")
    (inp / "samples.tsv").write_text("sample_id\tparticipant_id\tsample_type\nsample-A\tsub-01\ttissue\n")
    s = _scan_status(inp, tmp_path, monkeypatch, _no_imaging)
    assert s["stage"] == "planned", s


def test_no_imaging_without_claims_still_fails(tmp_path, monkeypatch):
    inp = tmp_path / "in"
    inp.mkdir()
    (inp / "participants.tsv").write_text("participant_id\nsub-01\n")
    s = _scan_status(inp, tmp_path, monkeypatch, _no_imaging)
    assert s["stage"] == "failed" and s["message"].startswith("EzbidsError"), s


def test_other_ezbids_errors_still_fail(tmp_path, monkeypatch):
    inp = tmp_path / "in"
    planted_ome_tiff(inp / "sub-01" / "micr" / "sub-01_sample-A_CONF.ome.tif")
    (inp / "participants.tsv").write_text("participant_id\nsub-01\n")

    def broken(staged, log=print, **kw):
        log("Traceback: something else")
        raise EzbidsError("something else")

    s = _scan_status(inp, tmp_path, monkeypatch, broken)
    assert s["stage"] == "failed", s


def test_bids_name_suffix(tmp_path, key, schema):
    """The input's own BIDS micr suffix (here XPCT, which no heuristic knows) is the entry's suffix."""
    inp = tmp_path / "in"
    ome_zarr(inp / "sub-01" / "ses-01" / "micr" / "sub-01_ses-01_sample-brain_XPCT.ome.zarr", "0.4")
    (e,) = _plan(inp, tmp_path, key, schema)
    assert e.suffix == "XPCT" and e.status == "ok", (e.suffix, e.status, e.reason)
    assert e.reason == "microscopy heuristic: the input's BIDS name"


def test_bids_sample_label_kept(tmp_path, key, schema):
    """A word label of the input's BIDS name (sample-brain) is kept; it is a term only because of that name."""
    inp = tmp_path / "in"
    ome_zarr(inp / "sub-01" / "ses-01" / "micr" / "sub-01_ses-01_sample-brain_XPCT.ome.zarr", "0.4")
    (e,) = _plan(inp, tmp_path, key, schema)
    assert e.entities["sample"] == "brain" and e.subject == "01" and e.session == "01"


def test_bids_sample_label_not_kept_when_identifying(tmp_path, key, schema):
    """A sample label that is also a term from elsewhere (a date, a donor, the image's own metadata) is not kept."""
    inp = tmp_path / "in"
    planted_ome_tiff(inp / "sub-01" / "micr" / "sub-01_sample-20250215_CONF.ome.tif")
    planted_ome_tiff(inp / "sub-01" / "micr" / "sub-01_sample-Smith_CONF.ome.tif")  # "Slide 42 Smith" in OME
    labels = {e.entities["sample"] for e in _plan(inp, tmp_path, key, schema)}
    assert not labels & {"20250215", "Smith"}, labels


def _units_unknown(store: Path) -> None:
    attrs_file = store / ".zattrs"
    attrs = json.loads(attrs_file.read_text())
    for axis in attrs["multiscales"][0]["axes"]:
        axis.pop("unit", None)
    attrs_file.write_text(json.dumps(attrs))


def test_bids_sidecar_pixel_size(tmp_path, key, schema):
    """The input's own BIDS sidecar gives the pixel size and unit the image does not state: a source value,
    not an invented one."""
    inp = tmp_path / "in"
    micr_dir = inp / "sub-01" / "ses-01" / "micr"
    _units_unknown(ome_zarr(micr_dir / "sub-01_ses-01_sample-A_SPIM.ome.zarr", "0.4"))
    (micr_dir / "sub-01_ses-01_sample-A_SPIM.json").write_text(json.dumps(
        {"PixelSize": [0.18, 0.18, 0.5], "PixelSizeUnits": "um", "Manufacturer": "Jane Doe"}))
    (e,) = _plan(inp, tmp_path, key, schema)
    assert (e.status, e.pixel_size, e.pixel_size_units) == ("ok", [0.18, 0.18, 0.5], "um"), e.reason


@pytest.mark.parametrize("car", [
    {"PixelSize": [0.18, 0.18, 0.5]},  # no unit
    {"PixelSize": [0.18, 0.18, 0.5], "PixelSizeUnits": "inch"},
    {"PixelSize": [0.18, -1, 0.5], "PixelSizeUnits": "um"},
    {"PixelSize": [0.18, 0.18], "PixelSizeUnits": "um"},  # 2 values for x, y, z
    {"PixelSize": "0.18", "PixelSizeUnits": "um"},
])
def test_bids_sidecar_pixel_size_refused(tmp_path, key, schema, car):
    inp = tmp_path / "in"
    micr_dir = inp / "sub-01" / "micr"
    _units_unknown(ome_zarr(micr_dir / "sub-01_sample-A_SPIM.ome.zarr", "0.4"))
    (micr_dir / "sub-01_sample-A_SPIM.json").write_text(json.dumps(car))
    (e,) = _plan(inp, tmp_path, key, schema)
    assert e.status == "unknown" and e.pixel_size_units is None


def test_image_pixel_size_wins_over_sidecar(tmp_path, key, schema):
    inp = tmp_path / "in"
    micr_dir = inp / "sub-01" / "micr"
    planted_ome_tiff(micr_dir / "sub-01_sample-A_CONF.ome.tif")
    (micr_dir / "sub-01_sample-A_CONF.json").write_text(json.dumps({"PixelSize": [9, 9, 9], "PixelSizeUnits": "nm"}))
    (e,) = _plan(inp, tmp_path, key, schema)
    assert (e.pixel_size, e.pixel_size_units) == ([0.5, 0.5, 2.0], "um")


def _big_endian_bytes(store: Path) -> Path:
    """Write the arrays' one-byte dtype as ">u1" (as bids-examples micr_SEMzarr does): zarr 3.1 (the image's)
    finds no data type for it."""
    for zarray in store.rglob(".zarray"):
        doc = json.loads(zarray.read_text())
        assert doc["dtype"] == "|u1"
        doc["dtype"] = ">u1"
        zarray.write_text(json.dumps(doc))
    return store


def test_one_byte_big_endian_v2_store_reads(tmp_path):
    from aimport.micr import readers

    store = _big_endian_bytes(ome_zarr(tmp_path / "s.ome.zarr", "0.4", dtype="uint8"))
    with readers.open_image(store, "ome-zarr") as src:
        assert src.info.dtype == "uint8" and src.info.shape == (2, 8, 64, 64)
        assert src.level(0).shape == (2, 8, 64, 64)


def test_one_byte_big_endian_reference_rebuilt(tmp_path, monkeypatch):
    """Executed as a reference: the rebuilt .zarray says "|u1" (the same bytes), which every zarr reads."""
    from aimport.validate import ValidationResult

    inp = tmp_path / "in"
    micr_dir = inp / "sub-01" / "micr"
    _big_endian_bytes(ome_zarr(micr_dir / "sub-01_sample-A_SPIM.ome.zarr", "0.4", dtype="uint8"))
    monkeypatch.setattr(server, "client_from_env", lambda: None)
    monkeypatch.setattr(server, "validate_bids", lambda bids: ValidationResult(
        ok=True, validator_version="2.4.1", bids_version="1.11.2"))
    app = server.create_app(inp, tmp_path / "work", tmp_path / "keys", TOKEN, [], ["testserver"])
    try:
        c = TestClient(app)
        c.headers["Authorization"] = "Bearer " + TOKEN
        assert c.post("/scan", json={"project_id": "proj"}).status_code == 202
        _wait(c, ("planned", "failed"))
        assert c.post("/approve", json={}).status_code == 200
        assert c.post("/execute").status_code == 202
        s = _wait(c, ("validated", "invalid", "failed"))
        assert s["stage"] == "validated", s
    finally:
        app.state.server.close()
    out = tmp_path / "work" / "output" / "bids"
    docs = [json.loads(p.read_text()) for p in out.rglob(".zarray")]
    assert docs and all(d["dtype"] == "|u1" for d in docs)
    assert (out / "sub-01" / "micr" / "sub-01_sample-A_SPIM.ome.zarr").is_dir()


def _wait(c, stages, timeout=60):
    end = time.time() + timeout
    while (s := c.get("/status").json())["stage"] not in stages and time.time() < end:
        time.sleep(0.05)
    return s


def test_bids_png_image_reported(tmp_path, key, schema):
    """A BIDS micr image aimport does not read (PNG, as in bids-examples micr_SEM) is a reported, excluded entry,
    not silently left out; a photo is not an image entry."""
    from aimport.micr.readers import PNG_MESSAGE

    inp = tmp_path / "in"
    micr_dir = inp / "sub-01" / "ses-01" / "micr"
    micr_dir.mkdir(parents=True)
    (micr_dir / "sub-01_ses-01_sample-A_SEM.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    (micr_dir / "sub-01_ses-01_sample-A_photo.jpg").write_bytes(b"\xff\xd8")
    (inp / "notes.png").write_bytes(b"\x89PNG\r\n\x1a\n")  # not a BIDS micr image: not claimed
    (e,) = _plan(inp, tmp_path, key, schema)
    assert (e.status, e.exclude, e.reason, e.suffix) == ("unsupported", True, PNG_MESSAGE, "SEM")
    assert e.description == "PNG; not readable"
