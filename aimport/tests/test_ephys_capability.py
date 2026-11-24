"""Task 1 ruling (Phase 3): what the pinned MNE / MNE-BIDS / validator can do for each ephys datatype.

The outcomes decide ``ephys.OUTPUT_FORMATS`` and ``ephys.MNE_READERS``; see the module docstring of
``aimport.ephys`` and README "Electrophysiology and optical data".
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
import pytest

mne = pytest.importorskip("mne")
mne_bids = pytest.importorskip("mne_bids")

from aimport import ephys  # noqa: E402

MEAS_DATE = datetime(2025, 2, 15, 9, 30, 0, tzinfo=timezone.utc)
PLANTED_SUBJECT = {
    "his_id": "MRN0042",
    "first_name": "John",
    "last_name": "Smith",
    "birthday": date(1970, 1, 1),
    "sex": 1,
    "hand": 1,
}
ANONYMIZE = {"daysback": 40000, "keep_his": False, "keep_source": False}
SFREQ = 256.0

CACHE = Path(os.environ.get("AIMPORT_EPHYS_CACHE", "/tmp/aimport-ephys-cache"))

# mne-testing-data, pinned; the files of CTF/testdata_ctf.ds that read_raw_ctf needs (empty ones skipped)
MNE_TESTING_COMMIT = "20cc221d737a37a6ee3a9c007e91bd69541fefe9"
CTF_FILES = {
    "ClassFile.cls": "bd91e66437d53bfbb4cd03ce9394714b4ec4fd715bddfca3c4fabe965476378b",
    "params.dsc": "2b4dee7383882a1fc6f1d84d5ba4c3181c461f5d6aaf5af204cc534289e5fc92",
    "processing.cfg": "c668cb17fbe4cfec9a29c3ec85ecaf7e61278df863fbe1a9ea8e77960db4baf4",
    "testdata_ctf.acq": "e0837500432d5f8c5ff940a53778469c1a3bf83852355fa922f256c5adc08623",
    "testdata_ctf.hc": "37ee610fdcff3689b95c0e461fe7c18d5582109120bb39e6e12d651931eb515c",
    "testdata_ctf.infods": "72d71ee90fea7a49b056a228101a9b84f91600585a000484061fbd7ea9f5c3b3",
    "testdata_ctf.meg4": "30ef47c85083ff3892d5565e487287f71146646a4bff6c283638939801c7f788",
    "testdata_ctf.newds": "5d2ace836414f294685574d3720f36ecd529b4b18668c8d54c9986e98b9e3cf9",
    "testdata_ctf.res4": "a75ccb0a74910d1f09f1e35944ced09591f3048a850718bcda95a83e16e27146",
}

# bids-examples, pinned; data files are empty (layout and validator only)
BIDS_EXAMPLES_COMMIT = "5e00d47b6f1db106dda1b776d5243eb41b4cb95b"
BIDS_EXAMPLES_SETS = (
    "eeg_cbm",
    "eeg_rest_fmri",
    "ieeg_epilepsy",
    "ieeg_visual",
    "ds000247",
    "fnirs_tapping",
    "fnirs_automaticity",
    "emg_ConcurrentIndependentUnits",
    "emg_CustomBipolar",
    "emg_CustomBipolarFace",
    "emg_IndependentMod",
    "emg_MultiBodyParts",
    "emg_Multimodal",
    "emg_TwoHDsEMG",
    "emg_TwoWristbands",
)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _raw_array(ch_type: str, n_ch: int = 4, seconds: float = 4.0) -> "mne.io.RawArray":
    rng = np.random.default_rng(0)
    names = [f"{ch_type.upper()}{i + 1}" for i in range(n_ch)]
    info = mne.create_info(names, SFREQ, ch_type)
    raw = mne.io.RawArray(rng.standard_normal((n_ch, int(SFREQ * seconds))) * 1e-5, info, verbose=False)
    raw.set_meas_date(MEAS_DATE)
    with raw.info._unlock():
        raw.info["subject_info"] = dict(PLANTED_SUBJECT)
        raw.info["line_freq"] = 60.0
    return raw


def _edf_source(tmp_path: Path, ch_type: str) -> Path:
    src = tmp_path / "src" / f"Smith_John_{ch_type}.edf"
    src.parent.mkdir(parents=True, exist_ok=True)
    mne.export.export_raw(src, _raw_array(ch_type), fmt="edf", verbose=False)
    return src


def _read_edf(src: Path, ch_type: str):
    """EDF does not store MNE channel types; set them back as the planner would."""
    raw = mne.io.read_raw_edf(src, preload=False, verbose=False)
    if ch_type != "eeg":
        raw.set_channel_types({n: ch_type for n in raw.ch_names})
    return raw


def _fetch_ctf() -> Path:
    ds = CACHE / f"mne-testing-data-{MNE_TESTING_COMMIT}" / "CTF" / "testdata_ctf.ds"
    ds.mkdir(parents=True, exist_ok=True)
    base = f"https://raw.githubusercontent.com/mne-tools/mne-testing-data/{MNE_TESTING_COMMIT}/CTF/testdata_ctf.ds"
    for name, digest in CTF_FILES.items():
        dest = ds / name
        if not dest.exists() or _sha256(dest) != digest:
            tmp = dest.with_suffix(dest.suffix + ".part")
            urllib.request.urlretrieve(f"{base}/{name}", tmp)
            tmp.replace(dest)
        assert _sha256(dest) == digest, name
    return ds


def _write(raw, root: Path, datatype: str, fmt: str, **kw) -> "mne_bids.BIDSPath":
    bp = mne_bids.BIDSPath(subject="01", task="rest", datatype=datatype, root=root)
    return mne_bids.write_raw_bids(raw, bp, format=fmt, verbose=False, **kw)


def _assert_no_source_bytes(out_root: Path, sources: list[Path]) -> None:
    src_hashes = {_sha256(s) for s in sources}
    outputs = [p for p in out_root.rglob("*") if p.is_file()]
    assert outputs
    assert not [p for p in outputs if _sha256(p) in src_hashes]


# --- readers ---------------------------------------------------------------------------------


def test_readers_exist():
    missing = [f for f, fn in ephys.MNE_READERS.items() if not callable(getattr(mne.io, fn, None))]
    assert not missing, missing
    assert ephys.MNE_READERS["mef3"] == "read_raw_mef"


def test_mef3_reader_needs_pymef(tmp_path):
    """read_raw_mef exists but imports pymef (MNE's optional extra) when it opens a file.

    Ruling record: pymef is not an approved aimport dependency, and neo has no MEF3 reader
    (``neo.rawio`` has MedRawIO, not MEF3). Without pymef, MEF3 input cannot be read.
    """
    try:
        import pymef  # noqa: F401
    except ImportError:
        (tmp_path / "x.mefd").mkdir()
        with pytest.raises(Exception, match="pymef"):
            mne.io.read_raw_mef(tmp_path / "x.mefd")
    else:  # pragma: no cover - pymef present
        pass


def test_output_formats_table():
    assert ephys.OUTPUT_FORMATS == {
        "eeg": ("BrainVision", "EDF", "BDF"),
        "ieeg": ("BrainVision", "EDF", "NWB"),
        "emg": ("EDF", "BDF"),
        "meg": ("FIF",),
        "nirs": ("SNIRF",),
    }


# --- anonymize forces conversion ---------------------------------------------------------------


@pytest.mark.parametrize(
    "datatype,fmt,ch_type,ext",
    [
        pytest.param("eeg", "BrainVision", "eeg", ".vhdr", id="eeg-BrainVision"),
        pytest.param("eeg", "EDF", "eeg", ".edf", id="eeg-EDF"),
        pytest.param("ieeg", "BrainVision", "seeg", ".vhdr", id="ieeg-BrainVision"),
        # CTF source: mne-testing-data testdata_ctf.ds (about 20 MB, fetched once)
        pytest.param("meg", "FIF", "ctf", ".fif", id="meg-FIF", marks=pytest.mark.ephys_data),
    ],
)
def test_anonymize_forces_conversion(tmp_path, datatype, fmt, ch_type, ext):
    if ch_type == "ctf":
        ds = _fetch_ctf()
        sources = [p for p in ds.iterdir() if p.is_file()]
        raw = mne.io.read_raw_ctf(ds, system_clock="ignore", preload=False, verbose=False)
    else:
        sources = [_edf_source(tmp_path, ch_type)]
        raw = _read_edf(sources[0], ch_type)
    out = _write(raw, tmp_path / "bids", datatype, fmt, anonymize=dict(ANONYMIZE))
    assert out.fpath.suffix == ext and out.fpath.exists()
    _assert_no_source_bytes(tmp_path / "bids", sources)
    if datatype == "meg":
        info = mne.io.read_info(out.fpath, verbose=False)
        assert info["meas_date"].year < 1925
    else:
        back = mne_bids.read_raw_bids(out, verbose=False)
        assert back.info["meas_date"].year < 1925
        assert not (back.info.get("subject_info") or {}).get("last_name")


# --- EMG ---------------------------------------------------------------------------------------


def test_emg_supported(tmp_path):
    src = _edf_source(tmp_path, "emg")
    raw = _read_edf(src, "emg")
    out = _write(raw, tmp_path / "bids", "emg", "EDF", anonymize=dict(ANONYMIZE), emg_placement="Measured")
    assert out.fpath.name == "sub-01_task-rest_emg.edf" and out.fpath.exists()
    assert (out.fpath.parent / "sub-01_task-rest_emg.json").exists()
    assert (out.fpath.parent / "sub-01_task-rest_channels.tsv").exists()
    _assert_no_source_bytes(tmp_path / "bids", [src])


def test_emg_bdf(tmp_path):
    """Ruling: BDF export works (edfio), so BDF stays in OUTPUT_FORMATS for eeg and emg."""
    src = _edf_source(tmp_path, "emg")
    raw = _read_edf(src, "emg")
    out = _write(raw, tmp_path / "bids", "emg", "BDF", anonymize=dict(ANONYMIZE), emg_placement="Measured")
    assert out.fpath.name == "sub-01_task-rest_emg.bdf" and out.fpath.exists()
    assert out.fpath.read_bytes()[:8] == b"\xffBIOSEMI"
    mne.io.read_raw_bdf(out.fpath, preload=False, verbose=False)
    _assert_no_source_bytes(tmp_path / "bids", [src])


def test_eeg_bdf(tmp_path):
    src = _edf_source(tmp_path, "eeg")
    raw = _read_edf(src, "eeg")
    out = _write(raw, tmp_path / "bids", "eeg", "BDF", anonymize=dict(ANONYMIZE))
    assert out.fpath.suffix == ".bdf" and out.fpath.exists()
    _assert_no_source_bytes(tmp_path / "bids", [src])


# --- NIRS --------------------------------------------------------------------------------------


def _write_snirf(path: Path) -> Path:
    """A minimal continuous-wave SNIRF (2 sources, 2 detectors, 2 wavelengths) written with h5py."""
    import h5py

    n_t = 200
    pairs = [(1, 1), (1, 2), (2, 1), (2, 2)]
    rng = np.random.default_rng(0)
    with h5py.File(path, "w") as f:
        f.create_dataset("formatVersion", data=np.bytes_("1.0"))
        nirs = f.create_group("nirs")
        tags = nirs.create_group("metaDataTags")
        for k, v in {
            "SubjectID": "Smith_John",
            "MeasurementDate": "2025-02-15",
            "MeasurementTime": "09:30:00",
            "LengthUnit": "mm",
            "TimeUnit": "s",
            "FrequencyUnit": "Hz",
        }.items():
            tags.create_dataset(k, data=np.bytes_(v))
        data = nirs.create_group("data1")
        data.create_dataset("dataTimeSeries", data=1.0 + 0.01 * rng.standard_normal((n_t, 2 * len(pairs))))
        data.create_dataset("time", data=np.arange(n_t) / 10.0)
        k = 1
        for wl in (1, 2):
            for s, d in pairs:
                ml = data.create_group(f"measurementList{k}")
                ml.create_dataset("sourceIndex", data=np.int32(s))
                ml.create_dataset("detectorIndex", data=np.int32(d))
                ml.create_dataset("wavelengthIndex", data=np.int32(wl))
                ml.create_dataset("dataType", data=np.int32(1))
                ml.create_dataset("dataTypeIndex", data=np.int32(1))
                k += 1
        probe = nirs.create_group("probe")
        probe.create_dataset("wavelengths", data=np.array([760.0, 850.0]))
        probe.create_dataset("sourcePos3D", data=np.array([[0.0, 0.0, 80.0], [30.0, 0.0, 80.0]]))
        probe.create_dataset("detectorPos3D", data=np.array([[0.0, 30.0, 80.0], [30.0, 30.0, 80.0]]))
        probe.create_dataset("sourceLabels", data=np.array([b"S1", b"S2"]))
        probe.create_dataset("detectorLabels", data=np.array([b"D1", b"D2"]))
        stim = nirs.create_group("stim1")
        stim.create_dataset("name", data=np.bytes_("Jane Doe tapping"))
        stim.create_dataset("data", data=np.array([[2.0, 5.0, 1.0], [10.0, 5.0, 1.0]]))
    return path


def test_nirs_from_snirf(tmp_path):
    src = _write_snirf(tmp_path / "scratch.snirf")
    raw = mne.io.read_raw_snirf(src, preload=False, verbose=False)
    out = _write(raw, tmp_path / "bids", "nirs", "auto", anonymize=None)
    d = out.fpath.parent
    for name in (
        "sub-01_task-rest_nirs.snirf",
        "sub-01_task-rest_nirs.json",
        "sub-01_task-rest_channels.tsv",
        "sub-01_optodes.tsv",  # optodes and coordsystem carry no task entity
        "sub-01_coordsystem.json",
    ):
        assert (d / name).exists(), sorted(p.name for p in d.iterdir())


# --- validator on bids-examples (docker) ---------------------------------------------------------

BIDS_EXAMPLES_CACHE = Path(os.environ.get("AIMPORT_BIDS_EXAMPLES_CACHE", "/tmp/aimport-bids-examples-cache"))


def _fetch_bids_examples() -> Path:
    """Shallow fetch of bids-examples at the pinned commit (its data files are empty)."""
    dest = BIDS_EXAMPLES_CACHE / BIDS_EXAMPLES_COMMIT
    if not (dest / "default-config.json").exists():
        dest.mkdir(parents=True, exist_ok=True)
        git = ["git", "-C", str(dest)]
        subprocess.run([*git, "init", "-q"], check=True)
        subprocess.run(
            [*git, "fetch", "-q", "--depth", "1", "https://github.com/bids-standard/bids-examples.git", BIDS_EXAMPLES_COMMIT],
            check=True,
        )
        subprocess.run([*git, "checkout", "-q", "FETCH_HEAD"], check=True)
    return dest


@pytest.mark.docker
@pytest.mark.parametrize("name", BIDS_EXAMPLES_SETS)
def test_validator_ephys_examples(name):
    """The pinned validator (schema 1.11.2) accepts every ephys datatype's bids-examples layout,
    with the flags bids-examples' own CI uses (``--config default-config.json --ignoreNiftiHeaders``)."""
    from aimport.validate import SCHEMA_PATH, VALIDATOR, _run, parse_report

    root = _fetch_bids_examples()
    proc = _run(
        [
            VALIDATOR,
            str(root / name),
            "--format",
            "json",
            "--schema",
            f"file://{SCHEMA_PATH}",
            "--config",
            str(root / "default-config.json"),  # ignores EMPTY_FILE
            # as bids-examples' run_tests.sh: the anat NIfTIs beside the ephys data are empty files,
            # so their headers are unreadable (NIFTI_HEADER_UNREADABLE); not an ephys finding
            "--ignoreNiftiHeaders",
        ]
    )
    errors, _ = parse_report(proc.stdout)
    assert not errors, json.dumps(errors, indent=1)[:4000]
