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


# --- fix round 1 --------------------------------------------------------------------------------------

def _patch_edf(path: Path, patient: str | None = None, recording: str | None = None,
               startdate: str | None = None) -> Path:
    raw = bytearray(path.read_bytes())
    for off, width, value in ((8, 80, patient), (88, 80, recording), (168, 8, startdate)):
        if value is not None:
            raw[off:off + width] = value.encode("ascii").ljust(width)
    path.write_bytes(bytes(raw))
    return path


def test_corrupt_ctf_res4_refused(tmp_path):
    ds = tmp_path / "run1.ds"
    ds.mkdir()
    (ds / "run1.res4").write_bytes(b"MEG42RS\0" + b"\xff" * 40)
    (ds / "run1.meg4").write_bytes(b"MEG41CP\0")
    with pytest.raises(readers.Unsupported) as e:
        headers.harvest(Recording("run1.ds", "ctf"), tmp_path)
    assert e.value.reason == headers.REASON_CTF_HEADER == "CTF header unreadable"


def test_edf_numeric_tokens_are_terms(tmp_path):
    path = _patch_edf(fx.planted_edf(tmp_path), patient="4711 M 01-JAN-1970 Smith_John MRN 55512",
                      recording="Startdate 15-FEB-2025 98765 EEGtech_Jane Hospital_X")
    terms = headers.harvest(Recording(str(path.relative_to(tmp_path)), "edf"), tmp_path)
    assert {"4711", "55512", "98765", "MRN", "EEGtech_Jane", "Smith", "John", "19700101", "20250215"} <= terms
    assert not {"M", "X", "Startdate", "01-JAN-1970 "} & terms

    plain = _patch_edf(fx.planted_edf(tmp_path / "plain"), patient="Smith 4711", recording="lab 12345 visit")
    raw = bytearray(plain.read_bytes())
    raw[192:236] = b" " * 44  # not EDF+
    plain.write_bytes(bytes(raw))
    terms = headers.harvest(Recording(str(plain.relative_to(tmp_path / "plain")), "edf"), tmp_path / "plain")
    assert {"Smith", "4711", "12345"} <= terms


def test_edf_anonymized_values_not_terms(tmp_path):
    """A source already written as Task 9 writes (01.01.85, X X X X) gives no term the gate would find in
    aimport's own output; a real birth date of 1985-01-01 is still a term."""
    path = _patch_edf(fx.planted_edf(tmp_path), patient="X X X X", recording="Startdate 01-JAN-1985 X X X",
                      startdate="01.01.85")
    rec = Recording(str(path.relative_to(tmp_path)), "edf")
    terms = headers.harvest(rec, tmp_path, readers.open_raw(rec, tmp_path))
    assert not {"01.01.85", "01-JAN-1985", "19850101", "1985-01-01", "X X X X", "Startdate X X X X"} & terms
    _patch_edf(path, patient="MRN0042 M 01-JAN-1985 Smith_John")
    terms = headers.harvest(rec, tmp_path, readers.open_raw(rec, tmp_path))
    assert {"01.01.85", "19850101", "01-JAN-1985"} <= terms


def test_nirx_folder_snirf_harvested(tmp_path):
    root = tmp_path / "in"
    src = fx.planted_snirf(tmp_path / "src")
    run = root / "run1"
    run.mkdir(parents=True)
    (run / "2025-02-15_001.snirf").write_bytes(src.read_bytes())
    (run / "2025-02-15_001_config.json").write_text("{}")
    _, recs = discover.claim(root)
    (rec,) = recs
    assert rec.family == "nirx"
    terms = headers.harvest(rec, root)
    assert {"MRN0042", "Jane Doe", "Jane Doe tapping"} <= terms


def test_snirf_labels(tmp_path):
    import h5py

    path = fx.planted_snirf(tmp_path)
    with h5py.File(path, "a") as f:
        f["nirs/probe"].create_dataset("landmarkLabels", data=np.array([b"Nz", b"LPA", b"Smith ear"]))
        f["nirs/stim1"].create_dataset("dataLabels", data=np.array([b"Onset", b"Duration", b"Amplitude",
                                                                    b"JDoe note"]))
    terms = headers.harvest(Recording(str(path.relative_to(tmp_path)), "snirf"), tmp_path)
    assert {"Smith ear", "JDoe note"} <= terms
    assert not {"Nz", "LPA", "S1", "D1", "Duration", "Amplitude", "Onset"} & terms


def test_blackrock_other_errors_propagate(tmp_path, monkeypatch):
    import mne

    def boom(*a, **k):
        raise ValueError("Invalid stim_channel")

    monkeypatch.setattr(mne.io, "read_raw_nsx", boom)
    (tmp_path / "r.ns5").write_bytes(b"NEURALCD" + b"\0" * 64)
    with pytest.raises(ValueError, match="stim_channel"):
        readers.open_raw(Recording("r.ns5", "blackrock", companions=["r.nev"]), tmp_path)


def test_brainvision_typed_comments(tmp_path):
    vhdr = fx.planted_brainvision(tmp_path)
    with open(vhdr, "a", encoding="utf-8") as fh:
        fh.write("12 March: seen by Dr Who <who@clinic.org>\n"
                 "1     Fp1          1        0.1 µV             10              1000              Off\n")
    rec = Recording(str(vhdr.relative_to(tmp_path)), "brainvision",
                    companions=[str(vhdr.with_suffix(".vmrk").relative_to(tmp_path))])
    terms = headers.harvest(rec, tmp_path)
    assert {"12 March: seen by Dr Who <who@clinic.org>", "seen by Dr Who <who@clinic.org>"} <= terms
    assert not any("Fp1" in t for t in terms)


def test_cnt_us_date_and_egi_categories(tmp_path):
    head = bytearray(900)
    head[225:233] = b"02/15/25"
    (tmp_path / "a.cnt").write_bytes(bytes(head))
    assert {"20250215", "15-FEB-2025"} <= headers.harvest(Recording("a.cnt", "cnt"), tmp_path)
    mff = tmp_path / "r.mff"
    mff.mkdir()
    (mff / "info.xml").write_text("<fileInfo/>")
    (mff / "categories.xml").write_text(
        '<categories xmlns="http://www.egi.com/categories_mff"><cat><name>Smith rest</name>'
        "<segments><seg><description>JDOE visit</description></seg></segments></cat>"
        "<cat><name>standard</name></cat></categories>")
    terms = headers.harvest(Recording("r.mff", "egi"), tmp_path)
    assert {"Smith rest", "JDOE visit"} <= terms and "standard" not in terms


@pytest.mark.ephys_data
def test_meg_system_header_terms(testing_recs):
    root, recs = testing_recs
    bti = headers.harvest(recs["BTi/erm_HFH"], root)
    assert {"Henry Ford", "btiwd99", "msimap", "HFH_March2016", "Calib_09-Mar-16_14:15"} <= bti
    assert not {"A1", "TRIGGER", "MxA", "WH2500", "Mar"} & bti  # channel names and month words are not terms
    kit = headers.harvest(recs["KIT/test_as-raw.con"], root)
    assert {"Academia Sinica", "Institute of Linguistics"} <= kit
    assert "20120416" in kit  # the system directory's creation date
    ctf = headers.harvest(recs["CTF/testdata_ctf.ds"], root)
    assert {"run title", "20130429", "29-APR-2013"} <= ctf  # .acq _run_title and _run_date
    assert not {"EEG057", "black"} & ctf  # .acq channel names and colours are not terms


def test_bids_words_in_header_text_are_never_terms(tmp_path):
    """dcm_qa_xa30's PatientName style in an EDF+ header, and a subject code written as a BIDS label: the
    values are terms, the BIDS keys (sub, task) and short labels (01) are not."""
    path = _patch_edf(fx.planted_edf(tmp_path), patient="sub-01 M 01-JAN-1970 XAtest_sub-July11",
                      recording="Startdate 15-FEB-2025 task-rest sub EEGtech_Jane")
    terms = headers.harvest(Recording(str(path.relative_to(tmp_path)), "edf"), tmp_path)
    assert {"XAtest", "July11", "EEGtech_Jane"} <= terms
    assert not {t.lower() for t in terms} & {"sub", "task", "eeg", "sub-01", "01", "task-rest"}
    from aimport.ancillary import path_terms
    from aimport.scrub import redact
    rel = "sub-01/eeg/sub-01_task-rest_eeg.edf"
    assert redact(rel, path_terms(terms)) == rel


def test_bids_named_input_path_words_are_never_terms():
    from aimport.micr import names
    t = names.path_terms(["XAtest_sub-July11/sub-01_task-rest_acq-hd_eeg.edf"], vocab=headers.HARVEST_VOCAB)
    assert {"XAtest", "July11"} <= t
    assert not {x.lower() for x in t} & {"sub", "task", "acq", "eeg", "rest"}
