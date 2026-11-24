"""Task 1 ruling (Phase 3): what the pinned MNE / MNE-BIDS / validator can do for each ephys datatype.

The outcomes decide ``ephys.OUTPUT_FORMATS`` and ``ephys.MNE_READERS``; see the module docstring of
``aimport.ephys`` and README "Electrophysiology and optical data".
"""
from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
import pytest

mne = pytest.importorskip("mne")
mne_bids = pytest.importorskip("mne_bids")

from aimport import ephys  # noqa: E402
from ephys_fixtures import (  # noqa: E402
    BIDS_EXAMPLES_SETS,
    fetch_bids_examples,
    fetch_mne_testing,
    planted_snirf,
    sha256,
)

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


def _write(raw, root: Path, datatype: str, fmt: str, **kw) -> "mne_bids.BIDSPath":
    bp = mne_bids.BIDSPath(subject="01", task="rest", datatype=datatype, root=root)
    return mne_bids.write_raw_bids(raw, bp, format=fmt, verbose=False, **kw)


def _assert_no_source_bytes(out_root: Path, sources: list[Path]) -> None:
    src_hashes = {sha256(s) for s in sources}
    outputs = [p for p in out_root.rglob("*") if p.is_file()]
    assert outputs
    assert not [p for p in outputs if sha256(p) in src_hashes]


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
        ds = fetch_mne_testing(["CTF/testdata_ctf.ds/"])["CTF/testdata_ctf.ds/"]
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


def test_nirs_from_snirf(tmp_path):
    src = planted_snirf(tmp_path)
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

@pytest.mark.docker
@pytest.mark.parametrize("name", BIDS_EXAMPLES_SETS)
def test_validator_ephys_examples(name):
    """The pinned validator (schema 1.11.2) accepts every ephys datatype's bids-examples layout,
    with the flags bids-examples' own CI uses (``--config default-config.json --ignoreNiftiHeaders``)."""
    from aimport.validate import SCHEMA_PATH, VALIDATOR, _run, parse_report

    root = fetch_bids_examples([name])[name].parent
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
