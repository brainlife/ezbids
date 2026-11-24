"""Phase 3 Task 4: lazy readers (``ephys/readers.py``) and the identifying-term harvest (``ephys/headers.py``)."""
from __future__ import annotations

import json
import sys
import tracemalloc
from datetime import date
from importlib.util import find_spec
from pathlib import Path

import numpy as np
import pytest

from aimport.ephys import discover, headers, readers
from aimport.ephys.discover import Recording
from conftest import EPHYS_PLANTED, ephys_tokens
from fixtures import ephys_fixtures as fx

PLANTED_BUILDERS = {
    "edf": fx.planted_edf,
    "bdf": fx.planted_bdf,
    "brainvision": fx.planted_brainvision,
    "eeglab": fx.planted_eeglab,
    "fif": fx.planted_fif,
    "snirf": fx.planted_snirf,
}
DATES_2025 = {"2025-02-15", "20250215", "15.02.25", "15-feb-2025"}
# planted values a format does not carry; "smith-fp1" is a channel (renamed in Task 5), "jdoe" an EGI event
NOT_CARRIED = {
    "edf": {"dr jane", "jane doe", "smith pilot", "tapping"},
    "bdf": {"dr jane", "jane doe", "smith pilot", "tapping"},
    "brainvision": {"hospital x", "eegtech_jane", "said hello", "smith pilot", "tapping"},
    "eeglab": DATES_2025 | {"eegtech_jane", "said hello", "dr jane", "jane doe", "smith pilot", "tapping"},
    "fif": {"eegtech_jane", "said hello", "dr jane", "tapping"},
    "snirf": {"hospital x", "eegtech_jane", "said hello", "dr jane", "smith pilot"},
}


def _planted(tmp_path: Path, fmt: str) -> tuple[Recording, Path]:
    PLANTED_BUILDERS[fmt](tmp_path)
    _, recs = discover.claim(tmp_path)
    (rec,) = [r for r in recs if r.family == fmt]
    return rec, tmp_path


@pytest.mark.parametrize("fmt", sorted(PLANTED_BUILDERS))
def test_planted_terms(tmp_path, fmt):
    rec, root = _planted(tmp_path, fmt)
    raw = readers.open_raw(rec, root)
    terms = headers.harvest(rec, root, raw)
    expected = EPHYS_PLANTED - {"smith-fp1", "jdoe"} - NOT_CARRIED[fmt]
    assert expected <= ephys_tokens("\n".join(terms)), expected - ephys_tokens("\n".join(terms))
    low = {t.lower() for t in terms}
    for clean in ("fp1", "emg1"):
        assert clean not in low
    joined = "\n".join(low)
    assert "stimulus" not in joined and "eyes closed" not in joined


def test_edf_header_and_date_forms(tmp_path):
    h = headers.read_edf_header(fx.planted_edf(tmp_path))
    assert h == headers.EdfHeader(fx.EDF_PATIENT, fx.EDF_RECORDING, "15.02.25", "10.00.00")
    assert headers.edf_date_forms(date(2025, 2, 15)) == {"15.02.25", "15-FEB-2025", "15-feb-2025", "250215"}


def test_name_parts_and_skipped_tokens(tmp_path):
    rec, root = _planted(tmp_path, "edf")
    terms = headers.harvest(rec, root, readers.open_raw(rec, root))
    assert {"Smith", "John", "MRN0042", "Hospital X", "EEGtech_Jane", "Smith John said hello"} <= terms
    assert not {"X", "M", "F", "Startdate", "1", "eyes closed"} & terms


@pytest.mark.parametrize("fmt", sorted(PLANTED_BUILDERS))
def test_info_allowlisted(tmp_path, fmt):
    rec, root = _planted(tmp_path, fmt)
    info = readers.read_info(rec, root)
    view = info.view()
    assert not {"meas_date", "birthday", "annotations"} & set(view)
    assert not ephys_tokens(json.dumps(view))
    assert info.sfreq == fx.SFREQ and info.n_times == fx.N_SAMPLES and info.duration_s == pytest.approx(10)
    if fmt in ("edf", "bdf", "fif", "snirf"):
        assert info.meas_date is not None and info.meas_date.date() == date(2025, 2, 15)
    if fmt in ("edf", "bdf", "fif"):
        assert info.birthday == date(1970, 1, 1)
    if fmt == "fif":
        assert info.n_headshape_points == 200 and info.has_dig and info.line_freq == 60.0
    if fmt == "snirf":
        assert info.wavelengths == [760, 850]
    if fmt in ("edf", "bdf"):
        assert [a[2] for a in info.annotations] == list(fx.EDF_ANNOTATIONS)


def _big_bdf(path: Path, n_ch: int = 64, sfreq: int = 2048, target: int = 64 * 2**20) -> Path:
    rec_bytes = n_ch * sfreq * 3
    n_rec = -(-target // rec_bytes)
    f = lambda s, w: str(s).ljust(w)[:w].encode("ascii")  # noqa: E731
    head = (b"\xffBIOSEMI" + f("X X X X", 80) + f("Startdate X X X X", 80) + f("15.02.25", 8) + f("10.00.00", 8)
            + f(256 * (n_ch + 1), 8) + f("24BIT", 44) + f(n_rec, 8) + f(1, 8) + f(n_ch, 4))
    sig = b"".join([
        b"".join(f(f"EEG{i:03d}", 16) for i in range(n_ch)),
        f("", 80) * n_ch, f("uV", 8) * n_ch, f(-8000, 8) * n_ch, f(8000, 8) * n_ch,
        f(-8388608, 8) * n_ch, f(8388607, 8) * n_ch, f("", 80) * n_ch, f(sfreq, 8) * n_ch, f("", 32) * n_ch,
    ])
    with open(path, "wb") as fh:
        fh.write(head + sig)
        fh.truncate(len(head) + len(sig) + n_rec * rec_bytes)
    return path


def test_preload_false(tmp_path):
    path = _big_bdf(tmp_path / "big.bdf")
    assert path.stat().st_size >= 64 * 2**20
    rec = Recording("big.bdf", "bdf")
    tracemalloc.start()
    try:
        info = readers.read_info(rec, tmp_path)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert info.n_channels == 64 and info.sfreq == 2048
    assert peak < 16 * 2**20, peak


def test_neo_missing_message(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "neo", None)
    monkeypatch.setitem(sys.modules, "neo.rawio", None)
    with pytest.raises(readers.Unsupported) as e:
        readers.open_neo(tmp_path / "r.ns5")
    assert e.value.reason == readers.REASON_NEO == "Blackrock needs the neo extra: pip install aimport[neo]"
    # a file MNE's read_raw_nsx cannot read falls back to neo, which is missing
    (tmp_path / "r.ns5").write_bytes(b"NOTNSX" + b"\0" * 64)
    (tmp_path / "r.nev").write_bytes(b"\0" * 64)
    with pytest.raises(readers.Unsupported) as e:
        readers.open_raw(Recording("r.ns5", "blackrock", companions=["r.nev"]), tmp_path)
    assert e.value.reason == readers.REASON_NEO


def test_unsupported_reasons(tmp_path):
    with pytest.raises(readers.Unsupported) as e:
        readers.open_raw(Recording("x.mefd", "unsupported", excluded=discover.REASON_MEF3), tmp_path)
    assert e.value.reason == discover.REASON_MEF3
    if find_spec("pymef") is None:
        with pytest.raises(readers.Unsupported) as e:
            readers.open_raw(Recording("x.mefd", "mef3"), tmp_path)
        assert e.value.reason == discover.REASON_MEF3
    with pytest.raises(ValueError):
        readers.open_raw(Recording("x.nwb", "nwb"), tmp_path)


def test_eeglab_v73_harvest(tmp_path):
    """MATLAB v7.3 .set: strings read through h5py (char arrays, cells of refs); the data are never read."""
    import h5py

    def char(group, name, text):
        ds = group.create_dataset(name, data=np.array([[ord(c)] for c in text], dtype=np.uint16))
        ds.attrs["MATLAB_class"] = np.bytes_("char")
        return ds

    path = tmp_path / "Doe_rest.set"
    with h5py.File(path, "w", userblock_size=512) as f:
        eeg = f.create_group("EEG")
        char(eeg, "setname", "Smith John")
        char(eeg, "comments", "Hospital X")
        data = eeg.create_dataset("data", data=np.zeros((3, 10), dtype=np.float32))
        data.attrs["MATLAB_class"] = np.bytes_("single")
        refs = f.create_group("#refs#")
        a = char(refs, "a", "MRN0042 start")
        b = char(refs, "b", "boundary")
        ev = eeg.create_group("event")
        ev.create_dataset("type", data=np.array([[a.ref], [b.ref]], dtype=h5py.ref_dtype))
    terms = headers.harvest(Recording(path.name, "eeglab"), tmp_path)
    assert {"Smith John", "Hospital X", "MRN0042 start"} <= terms
    assert "boundary" not in terms


def test_snirf_custom_tags(tmp_path):
    path = fx.planted_snirf(tmp_path)
    import h5py

    with h5py.File(path, "a") as f:
        f["nirs/metaDataTags"].create_dataset("StudyNotes", data=np.bytes_("seen by Dr Who"))
        f["nirs/metaDataTags"].create_dataset("AreaUnit", data=np.bytes_("mm2"))
    rec = Recording(str(path.relative_to(tmp_path)), "snirf")
    terms = headers.harvest(rec, tmp_path)
    assert {"seen by Dr Who", "Jane Doe", "MRN0042", "Jane Doe tapping"} <= terms
    assert not {"mm", "mm2", "s", "Hz"} & terms


# --- pinned MNE testing data ------------------------------------------------------------------------

# rel -> (system, ch_types)
TESTING_EXPECTED = {
    "EDF/test_reduced.edf": ("EDF", {"eeg": 138, "stim": 1}),
    "EDF/test_utf8_annotations.edf": ("EDF", {"eeg": 11}),
    "BDF/test_bdf_stim_channel.bdf": ("BioSemi", {"eeg": 3, "stim": 1}),
    "GDF/test_1ch.gdf": ("GDF", {"eeg": 1}),
    "Brainvision/test_NO.vhdr": ("BrainVision", {"eeg": 65}),
    "EEGLAB/test_raw.set": ("EEGLAB", {"eeg": 32}),
    "EGI/test_egi.mff": ("EGI", None),
    "NihonKohden/MB0400FU.EEG": ("Nihon Kohden", {"eeg": 22, "bio": 1, "misc": 2}),
    "Persyst/sub-pt1_ses-02_task-monitor_acq-ecog_run-01_clip2.lay": ("Persyst", {"eeg": 83}),
    "CTF/testdata_ctf.ds": ("CTF", {"mag": 273, "ref_meg": 28, "eeg": 8, "misc": 44, "stim": 3}),
    "CTF/somMDYO-18av.ds_raw.fif": ("Neuromag/MEGIN", {"mag": 151, "ref_meg": 29, "stim": 1}),
    "KIT/test_as-raw.con": ("KIT", {"mag": 157, "ref_meg": 3, "eeg": 32, "misc": 64, "stim": 1}),
    "BTi/erm_HFH": ("BTi/4D", {"mag": 148, "ref_meg": 11, "eeg": 31, "ecg": 1, "misc": 1, "stim": 2}),
    "SNIRF/NIRx/NIRSport2/1.0.3/2021-05-05_001.snirf": ("SNIRF", {"fnirs_cw_amplitude": 40}),
    "NIRx/nirscout/nirx_15_3_recording": ("NIRx", {"fnirs_cw_amplitude": 26}),
}


@pytest.fixture(scope="module")
def testing_recs():
    fx.fetch_mne_testing([n for names in fx.MNE_TESTING_FAMILIES.values() for n in names])
    root = fx.mne_testing_root()
    _, recs = discover.claim(root)
    return root, {r.rel: r for r in recs}


@pytest.mark.ephys_data
@pytest.mark.parametrize("rel", sorted(TESTING_EXPECTED))
def test_mne_testing_readers(testing_recs, rel):
    root, recs = testing_recs
    rec = recs[rel]
    system, ch_types = TESTING_EXPECTED[rel]
    if rec.family == "egi" and find_spec("mffpy") is None:
        with pytest.raises(readers.Unsupported) as e:
            readers.read_info(rec, root)
        assert e.value.reason == readers.REASON_MFF
        terms = headers.harvest(rec, root)  # the harvest needs no reader
        assert {"testfile23022017", "A15530448"} <= terms
        return
    info = readers.read_info(rec, root)
    assert info.system == system and info.sfreq > 0 and info.n_times > 0
    if ch_types is not None:
        assert info.ch_types == ch_types
    assert info.n_headshape_points == 0
    headers.harvest(rec, root, readers.open_raw(rec, root))


@pytest.mark.ephys_data
def test_testing_data_terms(testing_recs):
    root, recs = testing_recs
    nihon = recs["NihonKohden/MB0400FU.EEG"]
    terms = headers.harvest(nihon, root, readers.open_raw(nihon, root))
    assert {"6416", "Test_no_cap Asdf", "2019/01/01", "20190101"} <= terms
    ctf = recs["CTF/testdata_ctf.ds"]
    terms = headers.harvest(ctf, root, readers.open_raw(ctf, root))
    assert {"Anonymized4952_1448272040_0", "testdata_ctf"} <= terms
    assert not {"CTF", "ctf"} & terms  # manufacturer words are not terms
    persyst = recs["Persyst/sub-pt1_ses-02_task-monitor_acq-ecog_run-01_clip2.lay"]
    terms = headers.harvest(persyst, root, readers.open_raw(persyst, root))
    assert {"0 X 19-NOV-1997 No_Name", "19-NOV-1997", "19971119"} <= terms
    assert "No_Name" not in terms  # a placeholder, not a name
    nirx = recs["NIRx/nirscout/nirx_15_3_recording"]
    terms = headers.harvest(nirx, root, readers.open_raw(nirx, root))
    assert {"testMontage ATestMontage", "NIRS-2020-08-18_001", "20200818"} <= terms


@pytest.mark.ephys_data
def test_headshape_not_read_by_default(testing_recs, monkeypatch):
    root, recs = testing_recs
    kit, bti = recs["KIT/test_as-raw.con"], recs["BTi/erm_HFH"]
    assert kit.headshape and readers.read_info(kit, root).n_headshape_points == 0
    assert readers.read_info(bti, root).n_headshape_points == 0
    # the pinned .con stores no marker-coil positions: without a .mrk, headshape=True is refused...
    with pytest.raises(readers.Unsupported) as e:
        readers.open_raw(kit, root, headshape=True)
    assert e.value.reason == readers.REASON_KIT_DIG
    # ...and with markers (here the .elp's HPI points), the .hsp points are read
    from mne.io.kit.coreg import _read_dig_kit

    elp = _read_dig_kit(root / "KIT/MQKIT_125.elp")
    monkeypatch.setattr(readers, "_kit_markers", lambda path: elp[3:8])
    raw = readers.open_raw(kit, root, headshape=True)
    assert readers.info_from_raw(kit, raw).n_headshape_points > 0


def test_other_format_headers(tmp_path):
    """Header parsers that have no pinned test file: Hitachi, Persyst comments, Neuroscan CNT, Blackrock NEV."""
    (tmp_path / "h.csv").write_text(
        "Header,,,\nFile Version,1.25\nPatient Information,\nID,MRN0042\nName,Smith John\nComment,seen by Dr Jane\n"
        "Age,  55y\nDate,2025/02/15 10:00\nProbe1,\nData,\n1,2,3\n", encoding="latin-1")
    terms = headers.harvest(Recording("h.csv", "hitachi"), tmp_path)
    assert {"MRN0042", "Smith John", "Smith", "John", "seen by Dr Jane", "20250215", "15-FEB-2025"} <= terms

    (tmp_path / "p.lay").write_text("[FileInfo]\nFile=p.dat\n[Patient]\nFullName=Smith_John\nID=MRN0042\n"
                                    "[Comments]\n1.0,0,0,0,Jane Doe seizure\n2.0,0,0,0,seizure\n")
    terms = headers.harvest(Recording("p.lay", "persyst", companions=["p.dat"]), tmp_path)
    assert {"Smith", "John", "MRN0042", "Jane Doe seizure"} <= terms and "seizure" not in terms

    head = bytearray(900)
    for off, text in ((21, b"MRN0042"), (41, b"EEGtech Jane"), (101, b"Hospital X"), (121, b"Smith John"),
                      (225, b"02/15/25")):
        head[off:off + len(text)] = text
    (tmp_path / "a.cnt").write_bytes(bytes(head))
    terms = headers.harvest(Recording("a.cnt", "cnt"), tmp_path)
    assert {"MRN0042", "Jane", "Hospital X", "Smith", "John"} <= terms

    nsx = bytearray(400)
    nsx[:8] = b"NEURALCD"
    nsx[30:44] = b"Smith pilot 01"
    (tmp_path / "r.ns5").write_bytes(bytes(nsx))
    pkt = 104
    nev = bytearray(336 + 2 * pkt)
    nev[:8] = b"NEURALEV"
    nev[8] = 2
    nev[12:16] = (336).to_bytes(4, "little")
    nev[16:20] = pkt.to_bytes(4, "little")
    nev[76:84] = b"Dr Jane "
    p1 = 336
    nev[p1 + 4:p1 + 6] = (0xFFFF).to_bytes(2, "little")
    nev[p1 + 12:p1 + 30] = b"Smith John grimace"
    p2 = 336 + pkt
    nev[p2 + 4:p2 + 6] = (5).to_bytes(2, "little")
    nev[p2 + 12:p2 + 20] = b"spikeXYZ"
    (tmp_path / "r.nev").write_bytes(bytes(nev))
    terms = headers.harvest(Recording("r.ns5", "blackrock", companions=["r.nev"]), tmp_path)
    assert {"Smith pilot 01", "Dr Jane", "Smith John grimace"} <= terms and "spikeXYZ" not in terms
