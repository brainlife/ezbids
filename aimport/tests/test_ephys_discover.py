from __future__ import annotations

import os
from pathlib import Path

import pytest

from aimport.ancillary import find_ancillary
from aimport.ephys import discover
from fixtures import ephys_fixtures as fx

EDF_HEAD = b"0       " + b" " * 248


def _w(path: Path, data: bytes | str = b"") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data.encode() if isinstance(data, str) else data)
    return path


def tree(tmp_path: Path) -> Path:
    root = tmp_path / "in"
    fx.planted_edf(root)
    fx.planted_bdf(root)
    fx.planted_brainvision(root)
    fx.planted_eeglab(root)
    fx.planted_snirf(root)
    fx.planted_nwb(root)
    fx.planted_ctf_pos(root)
    fx.planted_kit_hsp(root)
    s = root / fx.SUBJECT_DIR
    _w(s / "gdf" / "a.gdf", b"GDF 2.20" + b"\0" * 100)
    _w(s / "cnt" / "a.cnt", b"Version 3.0")
    _w(s / "egi" / "a.raw", (4).to_bytes(4, "big") + b"\0" * 100)
    _w(s / "egi" / "b.mff" / "info.xml", "<x/>")
    _w(s / "egi" / "b.mff" / "signal1.bin", b"0")
    _w(s / "nihon" / "A.EEG", b"x")
    for e in ("PNT", "LOG", "21E"):
        _w(s / "nihon" / f"A.{e}", b"x")
    _w(s / "persyst" / "p.lay", "[FileInfo]\nFile=p.dat\n[Comments]\nJane Doe seizure\n")
    _w(s / "persyst" / "p.dat", b"x")
    _w(s / "mef" / "a.mefd" / "x.timd" / "y", b"x")
    _w(s / "fif" / "a_raw.fif", b"x")
    _w(s / "fif" / "a_raw-1.fif", b"x")
    for suf in ("ave", "cov", "epo", "fwd", "inv", "trans", "sol", "proj"):
        _w(s / "fif" / f"a-{suf}.fif", b"x")
    _w(s / "meg" / "run1.ds" / "run1.res4", b"x")
    _w(s / "meg" / "hz.ds" / "hz.res4", b"x")
    _w(s / "bti" / "erm_HFH" / "c,rfDC", b"x")
    _w(s / "bti" / "erm_HFH" / "config", b"x")
    _w(s / "bti" / "erm_HFH" / "hs_file", b"x")
    _w(s / "kit" / "a.sqd", b"x")
    _w(s / "kit" / "a.mrk", b"x")
    _w(s / "kit" / "a.elp", b"x")
    _w(s / "kit" / "a.hsp", b"x")
    _w(s / "nirx" / "r1" / "N_001.hdr", b"x")
    _w(s / "nirx" / "r1" / "N_001.wl1", b"x")
    _w(s / "nirx" / "r1" / "N_001.wl2", b"x")
    _w(s / "nirx2" / "s_config.json", b"{}")
    _w(s / "nirx2" / "s.snirf", b"x")
    _w(s / "hitachi" / "h.csv", "Header,ETG-4000,x\n1,2\n")
    _w(s / "hitachi" / "other.csv", "a,b\n1,2\n")
    _w(s / "bk" / "r.ns2", b"x")
    _w(s / "bk" / "r.nev", b"x")
    _w(s / "art" / "a.oxy4", b"x")
    _w(s / "shim" / "s.txt", "Shimadzu OMM header\n")
    _w(s / "shim" / "notes.txt", "hello\n")
    _w(s / "shim" / "t.omm", b"x")
    _w(s / "mri" / "T1.nii.gz", b"\0" * 400)
    _w(s / "mri" / "IM0001", b"\0" * 128 + b"DICM")
    _w(s / "mri" / "x.dcm", b"\0" * 128 + b"DICM")
    _w(s / "pos" / "s.pos", b"1\n")
    return root


@pytest.fixture
def found(tmp_path):
    root = tree(tmp_path)
    c, recs = discover.claim(root, ["https://example.org/x"])
    return root, c, recs, {r.rel.split("/", 1)[1]: r for r in recs}


def test_families(found):
    _, c, _, by = found
    want = {
        "Smith_John_rest.edf": "edf", "Smith_John_rest.bdf": "bdf", "gdf/a.gdf": "gdf",
        "Smith_John_rest.vhdr": "brainvision", "Smith_John_rest.set": "eeglab", "cnt/a.cnt": "cnt",
        "egi/a.raw": "egi", "egi/b.mff": "egi", "nihon/A.EEG": "nihon", "persyst/p.lay": "persyst",
        "fif/a_raw.fif": "fif", "meg/run1.ds": "ctf", "bti/erm_HFH": "bti", "kit/a.sqd": "kit",
        "nirx/r1": "nirx", "nirx2": "nirx", "hitachi/h.csv": "hitachi", "Smith_John_rest.snirf": "snirf",
        "Smith_John_rest.nwb": "nwb", "bk/r.ns2": "blackrock", "art/a.oxy4": "unsupported",
        "shim/s.txt": "unsupported", "shim/t.omm": "unsupported", "mef/a.mefd": "unsupported",
    }
    for rel, fam in want.items():
        assert by[rel].family == fam, rel
    assert by["art/a.oxy4"].excluded == "export to SNIRF first"
    assert by["mef/a.mefd"].excluded == "MEF3: export to EDF first"
    assert "hitachi/other.csv" not in by and "shim/notes.txt" not in by
    assert by["persyst/p.lay"].companions == [by["persyst/p.lay"].rel[:-3] + "dat"]
    assert by["nihon/A.EEG"].companions == [f"{fx.SUBJECT_DIR}/nihon/A.{e}" for e in ("PNT", "LOG", "21E")]
    assert by["Smith_John_rest.set"].companions == []
    assert c.remote == []
    for rec in by.values():
        assert rec.rel in c.roots


def test_fif_derived_and_split(found):
    _, _, _, by = found
    assert by["fif/a_raw.fif"].companions == [f"{fx.SUBJECT_DIR}/fif/a_raw-1.fif"]
    assert "fif/a_raw-1.fif" not in by
    for suf in ("ave", "cov", "epo", "fwd", "inv", "trans", "sol", "proj"):
        assert by[f"fif/a-{suf}.fif"].excluded.startswith("derived FIF")


def test_brainvision_companions_from_header(found, tmp_path):
    _, c, _, by = found
    r = by["Smith_John_rest.vhdr"]
    assert sorted(Path(x).name for x in r.companions) == ["Smith_John_rest.eeg", "Smith_John_rest.vmrk"]
    assert r.excluded is None
    for x in r.companions:
        assert x in c.roots
    bad = tmp_path / "bad"
    _w(bad / "a.vhdr", "[Common Infos]\nDataFile=../../etc/passwd\nMarkerFile=a.vmrk\n")
    _w(bad / "a.vmrk", b"x")
    _, recs = discover.claim(bad, [])
    assert recs[0].excluded == "BrainVision data file outside its folder"
    assert [Path(x).name for x in recs[0].companions] == ["a.vmrk"]


def test_ctf_hz_excluded(found):
    _, c, _, by = found
    assert by["meg/hz.ds"].excluded == "CTF head-localisation run"
    assert by["meg/hz.ds"].family == "ctf"
    assert by["meg/run1.ds"].excluded is None
    assert by["meg/hz.ds"].rel in c.roots


def test_headshape_listed(found):
    _, _, _, by = found
    assert by["bti/erm_HFH"].headshape == [f"{fx.SUBJECT_DIR}/bti/erm_HFH/hs_file"]
    assert not any(x.endswith("hs_file") for x in by["bti/erm_HFH"].companions)
    assert by["kit/a.sqd"].headshape == [f"{fx.SUBJECT_DIR}/kit/a.hsp"]
    assert sorted(Path(x).name for x in by["kit/a.sqd"].companions) == ["a.elp", "a.mrk"]


def test_ctf_pos_beside_ds(tmp_path):
    _w(tmp_path / "a" / "r.ds" / "r.res4", b"x")
    _w(tmp_path / "a" / "head.pos", b"1\n")
    c, recs = discover.claim(tmp_path, [])
    assert recs[0].headshape == ["a/head.pos"] and recs[0].companions == []
    assert "a/head.pos" in c.roots


def test_empty_room(found):
    _, _, _, by = found
    assert by["bti/erm_HFH"].empty_room
    assert not by["Smith_John_rest.edf"].empty_room
    assert discover.is_empty_room("sub-emptyroom/meg/x.fif")
    assert discover.is_empty_room("a/empty-room/x.fif") and discover.is_empty_room("a/noise_1.fif")
    assert not discover.is_empty_room("a/noisy_1.fif")


def test_bids_datatype_folder_claimed_whole(tmp_path, schema):
    d = tmp_path / "in"
    _w(d / "dataset_description.json", '{"Name":"x","BIDSVersion":"1.11.2"}')
    eeg = d / "sub-01" / "ses-1" / "eeg"
    _w(eeg / "sub-01_ses-1_task-rest_run-02_acq-hd_eeg.edf", EDF_HEAD)
    _w(eeg / "sub-01_ses-1_task-rest_run-02_acq-hd_eeg.json",
       '{"PowerLineFrequency": 50, "EEGReference": "Cz", "TaskName": "Smith"}')
    _w(eeg / "sub-01_ses-1_task-rest_run-02_acq-hd_channels.tsv", "name\nFp1\n")
    _w(eeg / "sub-01_ses-1_task-rest_run-02_acq-hd_events.tsv", "onset\n1\n")
    c, recs = discover.claim(d, [])
    assert c.roots == ["sub-01/ses-1/eeg"]
    assert recs[0].meta == {"task": "rest", "run": "02", "acq": "hd", "PowerLineFrequency": 50, "EEGReference": "Cz"}
    anc = find_ancillary(d, schema, exclude=c.roots)
    assert not [p for p in anc if p.name.endswith(("_channels.tsv", "_events.tsv"))]


def test_ds_and_mff_not_walked(tmp_path, monkeypatch):
    ds = tmp_path / "x" / "big.ds"
    ds.mkdir(parents=True)
    for i in range(5000):
        (ds / f"f{i}.dat").write_bytes(b"")
    _w(tmp_path / "x" / "p.mff" / "info.xml", "<x/>")
    for i in range(5000):
        (tmp_path / "x" / "p.mff" / f"s{i}.bin").write_bytes(b"")
    calls = []
    real = os.scandir
    monkeypatch.setattr(os, "scandir", lambda p=".": calls.append(str(p)) or real(p))
    c, recs = discover.claim(tmp_path, [])
    assert sorted(r.family for r in recs) == ["ctf", "egi"]
    assert len(calls) < 20
    assert not [p for p in calls if p.endswith((".ds", ".mff"))]


def test_unsupported_artinis(tmp_path):
    for n in ("a.oxy3", "b.oxy4", "c.oxy5", "d.oxyproj"):
        _w(tmp_path / n, b"x")
    c, recs = discover.claim(tmp_path, [])
    assert {r.family for r in recs} == {"unsupported"}
    assert {r.excluded for r in recs} == {"export to SNIRF first"}
    assert len(c.roots) == 4


def test_mri_untouched(found):
    _, c, _, _ = found
    assert not [r for r in c.roots if r.startswith(f"{fx.SUBJECT_DIR}/mri")]
    assert f"{fx.SUBJECT_DIR}/pos/s.pos" not in c.roots


def test_edf_version_checked(tmp_path):
    _w(tmp_path / "a.edf", b"notedf  ")
    _, recs = discover.claim(tmp_path, [])
    assert recs == []


def test_vocab_param():
    from aimport.micr import names
    assert names.facts("rest_Jon").donor == "rest"
    assert names.facts("rest_Jon", discover.VOCAB).donor == "Jon"
    assert "rest" not in names.path_terms(["rest_Jon"], discover.VOCAB)


def test_rejected_siblings_still_claimed(tmp_path):
    _w(tmp_path / "a.vhdr", "[Common Infos]\nDataFile=../../etc/passwd\nMarkerFile=a.vmrk\n")
    _w(tmp_path / "a.vmrk", "Mk1=Comment,Dr Jane Doe,1,1,0")
    _w(tmp_path / "a.eeg", b"x")
    _w(tmp_path / "p.lay", "[FileInfo]\nFile=..\\p.dat\n")
    _w(tmp_path / "p.dat", b"x")
    c, recs = discover.claim(tmp_path, [])
    assert {"a.vhdr", "a.vmrk", "a.eeg", "p.lay", "p.dat"} <= set(c.roots)
    assert all(r.excluded for r in recs)


def test_ephys_extensions_not_names():
    from aimport.micr import names
    assert names.facts("rest.edf", discover.VOCAB).donor is None
    assert "edf" not in names.path_terms(["rest.edf"], discover.VOCAB)
    assert "ns2" not in names.path_terms(["rest.ns2"], discover.VOCAB)


def test_fif_split_parts(tmp_path):
    for n in ("s_split-01_meg.fif", "s_split-02_meg.fif", "x.fif", "x-1.fif", "y-1.fif", "z.fif", "z-2.fif"):
        _w(tmp_path / n, b"x")
    _, recs = discover.claim(tmp_path, [])
    by = {r.rel: r for r in recs}
    assert by["s_split-01_meg.fif"].companions == ["s_split-02_meg.fif"]
    assert "s_split-02_meg.fif" not in by
    assert by["x.fif"].companions == ["x-1.fif"] and "x-1.fif" not in by
    assert "y-1.fif" in by  # no y.fif first part
    assert by["z.fif"].companions == [] and "z-2.fif" in by  # chain broken at -1


def test_sidecar_read_capped(tmp_path):
    d = tmp_path / "sub-01" / "eeg"
    _w(d / "sub-01_task-a_eeg.edf", EDF_HEAD)
    _w(d / "sub-01_task-a_eeg.json", '{"PowerLineFrequency": 50, "pad": "' + "x" * (2 << 20) + '"}')
    _, recs = discover.claim(tmp_path, [])
    assert recs[0].meta == {"task": "a"}
