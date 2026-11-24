from __future__ import annotations

import os
from datetime import date
from pathlib import Path

from aimport.micr import discover, names
from fixtures.micr_fixtures import cmc_tree


def _fam(tmp_path):
    claim, found = discover.claim(cmc_tree(tmp_path), [])
    return claim, {f.rel: f.family for f in found}


def test_families(tmp_path):
    claim, fam = _fam(tmp_path)
    for c in ("Reflectivity", "Retardance", "Orientation", "Cross"):
        assert fam[f"PS-OCT/Enface/Registration/{c}/Slice_051_1.nii.gz"] == "nifti"
    assert fam["PS-OCT/250215/Slice_051_Tile_0001.dat"] == "raw-psoct"
    assert fam["Moe_Slice_051.ome.zarr"] == "ome-zarr"
    assert fam["exaSPIM.zarr/Pos0"] == "ome-zarr"
    assert fam["MN27_20250422_visor_488/visor_488_Pos0/visor_488_0001.tif"] == "tiff"
    (tmp_path / "x.vsi").touch()
    (tmp_path / "a.ome.tiff").touch()
    _, found = discover.claim(tmp_path, [])
    fams = {f.rel: f.family for f in found}
    assert fams["x.vsi"] == "unsupported" and fams["a.ome.tiff"] == "ome-tiff"


def test_nifti_without_hint_left_to_ezbids(tmp_path):
    (tmp_path / "sub-01" / "anat").mkdir(parents=True)
    (tmp_path / "sub-01" / "anat" / "T1.nii.gz").touch()
    (tmp_path / "dat.dat").touch()
    claim, found = discover.claim(tmp_path, [])
    assert claim.roots == [] and found == []


def test_zarr_root_not_walked(tmp_path, monkeypatch):
    store = tmp_path / "big.zarr"
    (store / "0" / "c").mkdir(parents=True)
    (store / "zarr.json").write_text("{}")
    for i in range(10_000):
        (store / "0" / "c" / str(i)).touch()
    calls = []
    real = os.scandir
    monkeypatch.setattr(os, "scandir", lambda *a, **k: (calls.append(a), real(*a, **k))[1])
    claim, found = discover.claim(tmp_path, [])
    assert [f.rel for f in found] == ["big.zarr"] and claim.roots == ["big.zarr"]
    assert len(calls) < 50


def test_tile_folder_shares_group_and_remote_passthrough(tmp_path):
    for i in (1, 2):
        d = tmp_path / "s" / "tiles"
        d.mkdir(parents=True, exist_ok=True)
        (d / f"t_{i}.tif").touch()
    claim, found = discover.claim(tmp_path, ["https://x/y"])
    assert {f.group for f in found} == {"s/tiles"} and claim.remote == ["https://x/y"]


def test_facts():
    f = names.facts("MN27_20250422_visor_488/visor_488_Pos3/visor_488_0012.tif")
    assert (f.donor, f.dates, f.position, f.tile, f.channel_nm) == ("MN27", [date(2025, 4, 22)], 3, 12, 488)
    f = names.facts("Moe_Slice_051.ome.zarr")
    assert (f.donor, f.slice) == ("Moe", 51)
    assert names.facts("PS-OCT/Enface/Registration/Orientation/Slice_051_1.nii.gz").contrast == "opticaxis"
    assert names.facts("PS-OCT/250215/Slice_051_Tile_0001.dat").dates == [date(2025, 2, 15)]
    assert names.facts("PS-OCT/250215/Slice_051_Tile_0001.dat").tile == 1
    assert names.facts("sub-H17/H17_x.tif").donor == "H17"


def test_path_terms():
    t = names.path_terms(["MN27_20250422_visor_488/visor_488_Pos3/visor_488_0012.tif",
                          "Moe_Slice_051.ome.zarr", "PS-OCT/250215/Slice_051_Tile_0001.dat"])
    assert {"MN27", "Moe", "20250422", "2025-04-22", "250215"} <= t
    assert "visor" not in t and "488" not in t


def test_visor_meta_claimed_not_entries(tmp_path):
    claim, found = discover.claim(cmc_tree(tmp_path), [])
    for n in ("acqinfo_metadata.json", "dbpost.json", "hh.log"):
        assert f"MN27_20250422_visor_488/{n}" in claim.roots
        assert all(not f.rel.endswith(n) for f in found)
