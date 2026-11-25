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
    store = tmp_path / "foo"
    (store / "0" / "c").mkdir(parents=True)
    (store / "zarr.json").write_text("{}")
    for i in range(10_000):
        (store / "0" / "c" / str(i)).touch()
    calls = []
    real = os.scandir
    monkeypatch.setattr(os, "scandir", lambda *a, **k: (calls.append(a), real(*a, **k))[1])
    claim, found = discover.claim(tmp_path, [])
    assert [f.rel for f in found] == ["foo"] and claim.roots == ["foo"]
    assert len(calls) < 50


def test_tile_folder_shares_group_and_remote_probed(tmp_path, monkeypatch):
    from aimport.micr import remote

    for i in (1, 2):
        d = tmp_path / "s" / "tiles"
        d.mkdir(parents=True, exist_ok=True)
        (d / f"t_{i}.tif").touch()
    probes = {"https://x.org/y": "ome-zarr", "https://x.org/z": None}
    monkeypatch.setattr(remote, "probe", lambda url: probes[url])
    claim, found = discover.claim(tmp_path, ["https://x.org/y/", "https://x.org/z", "http://x.org/w"])
    assert {f.group for f in found if f.family == "tiff"} == {"s/tiles"}
    assert claim.remote == ["https://x.org/y"]
    assert [(f.rel, f.family) for f in found if f.rel.startswith("https:")] == [("https://x.org/y", "ome-zarr")]


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


def test_vocabulary_exact_except_structural():
    for w in ("HH3", "PS12", "NM5", "MAT2", "DAT1", "RAW7", "SCAN4"):
        assert not names.is_vocab(w)
        assert w in names.path_terms([f"{w}_x.tif"])
        assert names.facts(f"{w}_x.tif").donor == w
    for w in ("Slice051", "Pos3", "ch1", "Tile7"):
        assert names.is_vocab(w)


def test_separator_dates():
    for p in ("a/2025-04-22/x.tif", "a/2025_04_22/x.tif"):
        assert date(2025, 4, 22) in names.facts(p).dates
        t = names.path_terms([p])
        assert "2025-04-22" in t and "20250422" in t
    assert names.facts("22.04.2025_x.tif").dates == [date(2025, 4, 22)]
    assert names.facts("2025-13-45/x.tif").dates == []


def test_nifti_claim_is_narrow(tmp_path):
    for rel in ("Oct_2024/sub-01/anat/T1.nii.gz", "cross_sectional/study/x/y/T1.nii.gz", "Oct_2024/T1.nii.gz",
                "Oct_2024/sub-01/T1.nii.gz", "cross_sectional/study/T1.nii.gz",
                "PS-OCT/Enface/Cross/Slice_051_1.nii.gz",
                "PS-OCT/Enface/Retardance/Slice_051_1.nii.gz"):
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).touch()
    claim, _ = discover.claim(tmp_path, [])
    assert sorted(claim.roots) == ["PS-OCT/Enface/Cross/Slice_051_1.nii.gz",
                                   "PS-OCT/Enface/Retardance/Slice_051_1.nii.gz"]
    assert not discover.has_hint("Oct_2024/T1.nii.gz") and discover.has_hint("OCT/a.dat")


def test_trailing_six_digit_tile_and_donor_scope():
    f = names.facts("MN27_20250422_visor_488/visor_488_Pos3/visor_488_000123.tif")
    assert f.tile == 123 and f.dates == [date(2025, 4, 22)]
    assert names.facts("Zed1/Mid2/test_x.tif").donor == "Zed1"
    assert names.facts("run/Mid2/final_scan_12.tif").donor is None


def test_bids_words_in_micr_names_are_never_terms():
    """A donor folder written like dcm_qa_xa30's PatientName: its values are terms, the BIDS keys,
    datatype and suffix are not."""
    t = names.path_terms(["XAtest_sub-July11/micr/sub-01_sample-A_SEM.ome.tif", "SPIM_stack/sub/img.tif"])
    assert {"XAtest", "July11"} <= t
    assert not {x.lower() for x in t} & {"sub", "sample", "micr", "sem", "spim"}
    for w in ("sub", "ses", "sample", "micr", "SEM", "T1w", "chunk", "stain"):
        assert names.is_vocab(w), w
