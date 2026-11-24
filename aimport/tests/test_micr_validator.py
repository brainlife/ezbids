"""Task 1 ruling: does @bids/validator 2.4.1 (schema 1.11.2) accept NGFF 0.5, 0.4 and metadata-only stores?"""
import json
from pathlib import Path

import pytest

from aimport.validate import validate_bids
from micr_fixtures import ome_zarr, strip_chunks

STORE = "sub-01/micr/sub-01_sample-A_SPIM.ome.zarr"


def _micr_dataset(root: Path, version: str, sidecar: dict | None = None) -> Path:
    micr = root / "sub-01" / "micr"
    micr.mkdir(parents=True)
    ome_zarr(root / STORE, version)
    if sidecar is None:
        sidecar = {"PixelSize": [0.5, 0.5, 1.0], "PixelSizeUnits": "um"}
    (micr / "sub-01_sample-A_SPIM.json").write_text(json.dumps(sidecar))
    (root / "dataset_description.json").write_text(
        json.dumps({"Name": "micr fixture", "BIDSVersion": "1.11.2", "DatasetType": "raw"})
    )
    (root / "participants.tsv").write_text("participant_id\nsub-01\n")
    (root / "samples.tsv").write_text("sample_id\tparticipant_id\tsample_type\nsample-A\tsub-01\ttissue\n")
    return root


def _report(r) -> str:
    return json.dumps({"errors": r.errors, "warnings": r.warnings}, indent=1)


@pytest.mark.docker
def test_validator_accepts_ngff_05(tmp_path):
    r = validate_bids(_micr_dataset(tmp_path / "ds", "0.5"))
    assert r.ok, _report(r)


@pytest.mark.docker
def test_validator_accepts_ngff_04(tmp_path):
    r = validate_bids(_micr_dataset(tmp_path / "ds", "0.4"))
    assert r.ok, _report(r)


@pytest.mark.docker
def test_validator_accepts_metadata_only_store(tmp_path):
    ds = _micr_dataset(tmp_path / "ds", "0.5")
    store = strip_chunks(ds / STORE)
    assert not [p for p in store.rglob("*") if p.is_file() and p.name != "zarr.json"]
    r = validate_bids(ds)
    assert r.ok, _report(r)


@pytest.mark.docker
def test_validator_flags_missing_pixelsize(tmp_path):
    r = validate_bids(_micr_dataset(tmp_path / "ds", "0.5", sidecar={"PixelSizeUnits": "um"}))
    assert not r.ok
    assert any(
        "PixelSize" in (e.get("sub_code", "") + e["message"]) for e in r.errors
    ), _report(r)


@pytest.mark.docker
def test_validator_treats_ome_zarr_as_opaque(tmp_path):
    """2.4.1 does not read NGFF metadata: a store with a corrupt zarr.json still passes, so aimport
    must check its own OME-Zarr metadata. If this starts failing, the validator began reading it."""
    ds = _micr_dataset(tmp_path / "ds", "0.5")
    (ds / STORE / "zarr.json").write_text("{not json")
    r = validate_bids(ds)
    assert r.ok, _report(r)


def test_ome_zarr_fixture_versions(tmp_path):
    v5 = ome_zarr(tmp_path / "a.ome.zarr", "0.5")
    attrs = json.loads((v5 / "zarr.json").read_text())["attributes"]["ome"]
    assert attrs["version"] == "0.5"
    v4 = ome_zarr(tmp_path / "b.ome.zarr", "0.4")
    assert json.loads((v4 / ".zattrs").read_text())["multiscales"][0]["version"] == "0.4"
    stripped = strip_chunks(v4)
    assert {p.name for p in stripped.rglob("*") if p.is_file()} <= {".zgroup", ".zattrs", ".zarray"}


def test_ngff_version_env(monkeypatch):
    import importlib

    import aimport.micr as micr

    monkeypatch.setenv("AIMPORT_NGFF_VERSION", "0.4")
    assert importlib.reload(micr).NGFF_VERSION == "0.4"
    monkeypatch.setenv("AIMPORT_NGFF_VERSION", "0.6")
    with pytest.raises(ValueError):
        importlib.reload(micr)
    monkeypatch.delenv("AIMPORT_NGFF_VERSION")
    assert importlib.reload(micr).NGFF_VERSION == micr.DEFAULT_NGFF_VERSION
