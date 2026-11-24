"""Phase 3 Task 2: the planted recordings, the pinned test-data table and the ephys leak vocabulary."""
from __future__ import annotations

from collections import Counter

import pytest

from conftest import EPHYS_PLANTED, PLANTED, ephys_tokens, tokens
from ephys_fixtures import (
    BIDS_EXAMPLES_SETS,
    EDF_PATIENT,
    EDF_RECORDING,
    FIF_DIG_COUNTS,
    MAX_TOTAL_BYTES,
    MNE_TESTING_FAMILIES,
    MNE_TESTING_FILES,
    SUBJECT_DIR,
    fetch_mne_testing,
    mne_testing_root,
    planted_bdf,
    planted_brainvision,
    planted_ctf_pos,
    planted_edf,
    planted_eeglab,
    planted_fif,
    planted_kit_hsp,
    planted_snirf,
    sha256,
)


def test_vocabulary():
    assert PLANTED < EPHYS_PLANTED
    assert {"jane doe", "jdoe", "said hello", "15.02.25", "smith-fp1", "tapping"} <= EPHYS_PLANTED
    assert ephys_tokens("Dr Jane saw JDOE, 15-FEB-2025") == {"dr jane", "jdoe", "15-feb-2025"}
    assert not ephys_tokens("sub-01_task-rest_eeg.edf E001")
    assert "jane doe" in tokens("Jane Doe") and "smith" in ephys_tokens("Smith")


@pytest.mark.parametrize("planted,ext", [(planted_edf, "edf"), (planted_bdf, "bdf")])
def test_planted_edf_header(tmp_path, planted, ext):
    path = planted(tmp_path)
    assert path == tmp_path / SUBJECT_DIR / f"Smith_John_rest.{ext}"
    head = path.read_bytes()[8:168]
    assert head[:80].decode().strip() == EDF_PATIENT == "MRN0042 M 01-JAN-1970 Smith_John"
    assert head[80:].decode().strip() == EDF_RECORDING == "Startdate 15-FEB-2025 EEGtech_Jane Hospital_X"
    mne = pytest.importorskip("mne")
    raw = (mne.io.read_raw_edf if ext == "edf" else mne.io.read_raw_bdf)(path, preload=False, verbose=False)
    assert raw.ch_names == ["Fp1", "Smith-Fp1", "EMG1"]
    assert list(raw.annotations.description) == ["Smith John said hello", "1", "eyes closed"]
    assert raw.info["meas_date"].replace(tzinfo=None).isoformat() == "2025-02-15T10:00:00"
    assert raw.times[-1] == pytest.approx(10, abs=0.01) and raw.info["sfreq"] == 256.0


def test_planted_brainvision(tmp_path):
    vhdr = planted_brainvision(tmp_path)
    text = vhdr.read_text()
    assert "DataFile=Smith_John_rest.eeg" in text and "Patient: Smith John, MRN0042" in text
    vmrk = vhdr.with_suffix(".vmrk").read_text()
    assert "Stimulus,S  1," in vmrk and "Comment,Dr Jane Doe," in vmrk
    mne = pytest.importorskip("mne")
    raw = mne.io.read_raw_brainvision(vhdr, preload=False, verbose=False)
    assert raw.ch_names == ["Fp1", "Smith-Fp1", "EMG1"] and raw.n_times == 2560


def test_planted_eeglab(tmp_path):
    path = planted_eeglab(tmp_path)
    scipy_io = pytest.importorskip("scipy.io")
    eeg = scipy_io.loadmat(path, struct_as_record=False, squeeze_me=True)["EEG"]
    assert (eeg.setname, eeg.subject, eeg.comments) == ("Smith John", "MRN0042", "Hospital X")
    assert eeg.event[0].type == "MRN0042 start"
    mne = pytest.importorskip("mne")
    raw = mne.io.read_raw_eeglab(path, preload=False, verbose=False)
    assert "MRN0042 start" in raw.annotations.description


def test_planted_fif_dig_counts(tmp_path):
    mne = pytest.importorskip("mne")
    path = planted_fif(tmp_path)
    info = mne.io.read_info(path, verbose=False)
    kinds = Counter(d["kind"] for d in info["dig"])
    F = mne.io.constants.FIFF
    assert kinds[F.FIFFV_POINT_CARDINAL] == FIF_DIG_COUNTS["cardinal"] == 3
    assert kinds[F.FIFFV_POINT_HPI] == FIF_DIG_COUNTS["hpi"] == 4
    assert kinds[F.FIFFV_POINT_EXTRA] == FIF_DIG_COUNTS["extra"] == 200
    si = info["subject_info"]
    assert (si["his_id"], si["first_name"], si["last_name"], si["sex"]) == ("MRN0042", "John", "Smith", 1)
    assert si["birthday"].isoformat() == "1970-01-01"
    assert (info["experimenter"], info["description"], info["proj_name"]) == ("Jane Doe", "Hospital X study", "Smith pilot")
    assert info["meas_date"].replace(tzinfo=None).isoformat() == "2025-02-15T10:00:00"
    assert info["sfreq"] == 256.0 and mne.pick_types(info, meg=True, exclude=[]).size == info["nchan"] > 50


def test_planted_snirf_tags(tmp_path):
    h5py = pytest.importorskip("h5py")
    path = planted_snirf(tmp_path)
    with h5py.File(path, "r") as f:
        tags = {k: v[()].decode() for k, v in f["nirs/metaDataTags"].items()}
        assert tags["SubjectID"] == "MRN0042"
        assert (tags["MeasurementDate"], tags["MeasurementTime"], tags["Operator"]) == ("2025-02-15", "10:00:00", "Jane Doe")
        assert f["nirs/stim1/name"][()].decode() == "Jane Doe tapping"
        assert list(f["nirs/probe/wavelengths"][()]) == [760.0, 850.0]
        assert f["nirs/data1/dataTimeSeries"].shape == (2560, 8)
    mne = pytest.importorskip("mne")
    assert len(mne.io.read_raw_snirf(path, preload=False, verbose=False).ch_names) == 8


def test_planted_headshape_files(tmp_path):
    pos, hsp = planted_ctf_pos(tmp_path), planted_kit_hsp(tmp_path)
    assert pos.parent == hsp.parent == tmp_path / SUBJECT_DIR
    assert pos.read_text().splitlines()[0] == "200" and len(pos.read_text().splitlines()) == 201
    assert len([ln for ln in hsp.read_text().splitlines() if not ln.startswith(("%", "//"))]) == 200


def test_planted_nwb(tmp_path):
    pynwb = pytest.importorskip("pynwb")
    from ephys_fixtures import planted_nwb

    path = planted_nwb(tmp_path)
    with pynwb.NWBHDF5IO(path, "r") as io:
        nwb = io.read()
        assert nwb.session_description == "Smith John grid" and nwb.experimenter == ("Jane Doe",)
        assert nwb.institution == "Hospital X" and nwb.subject.subject_id == "MRN0042"
        assert nwb.subject.date_of_birth.year == 1970 and len(nwb.electrodes) == 8
        assert nwb.acquisition["ieeg"].data.shape == (2560, 8)
        assert list(nwb.trials["note"][:]) == ["seizure Dr Jane"]


def test_pinned_table_shape():
    assert sum(size for size, _ in MNE_TESTING_FILES.values()) <= MAX_TOTAL_BYTES
    assert all(len(h) == 64 for _, h in MNE_TESTING_FILES.values())
    for names in MNE_TESTING_FAMILIES.values():
        for n in names:
            assert any(p == n or (n.endswith("/") and p.startswith(n)) for p in MNE_TESTING_FILES), n
    assert "ds000247" in BIDS_EXAMPLES_SETS and sum(s.startswith("emg_") for s in BIDS_EXAMPLES_SETS) == 8


@pytest.mark.ephys_data
def test_fetch_hashes():
    names = [n for fam in MNE_TESTING_FAMILIES.values() for n in fam]
    got = fetch_mne_testing(names)
    assert set(got) == set(names)
    total = 0
    for rel, (size, digest) in MNE_TESTING_FILES.items():
        local = mne_testing_root() / rel
        assert local.stat().st_size == size and sha256(local) == digest, rel
        total += size
    assert total < MAX_TOTAL_BYTES

