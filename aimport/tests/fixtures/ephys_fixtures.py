"""Phase 3 test data: pinned downloads, bids-examples, and synthetic recordings with planted identifiers.

* ``fetch_mne_testing`` / ``fetch_bids_examples``: small pinned downloads (never committed; cached in
  ``AIMPORT_EPHYS_CACHE`` / ``AIMPORT_BIDS_EXAMPLES_CACHE``); every mne-testing-data file is checked
  against its SHA-256.
* ``planted_*``: synthetic recordings, all under ``dest/Smith_John_19700101/``, 10 s at 256 Hz, meas_date
  2025-02-15T10:00:00, carrying the identifiers of ``conftest.EPHYS_PLANTED`` in the places each format
  stores them (headers, annotations, channel names, comments, dig points).

Random signals use seed 0.  Imports of mne / pynwb / h5py are lazy, so importing this module is cheap.
"""
from __future__ import annotations

import hashlib
import os
import subprocess
import urllib.parse
import urllib.request
from collections.abc import Iterable
from datetime import date, datetime, time, timezone
from pathlib import Path

import numpy as np

SUBJECT_DIR = "Smith_John_19700101"
SFREQ = 256.0
DURATION_S = 10
N_SAMPLES = int(SFREQ * DURATION_S)
MEAS_DATE = datetime(2025, 2, 15, 10, 0, 0, tzinfo=timezone.utc)

CACHE = Path(os.environ.get("AIMPORT_EPHYS_CACHE", str(Path.home() / ".cache" / "aimport-ephys")))
BIDS_EXAMPLES_CACHE = Path(os.environ.get("AIMPORT_BIDS_EXAMPLES_CACHE", "/tmp/aimport-bids-examples-cache"))

MNE_TESTING_COMMIT = "20cc221d737a37a6ee3a9c007e91bd69541fefe9"
MAX_TOTAL_BYTES = 80 * 10**6

# path in mne-testing-data -> (bytes, SHA-256).  Hitachi/*.csv do not exist at this commit.
MNE_TESTING_FILES: dict[str, tuple[int, str]] = {
    "EDF/test_reduced.edf": (820188, "644acaf3aa547d85d73ed4a7224008c55be1487227e5eb029274877e2c61a39a"),
    "EDF/test_utf8_annotations.edf": (47648, "e13bfacba83898370f38040f29a1503572686b33df680dd95147d87d19dfd7b8"),
    "BDF/test_bdf_stim_channel.bdf": (61280, "d555c9550069c0402835092ac3b2136ac238c8b8996069e11594350826d765a3"),
    "GDF/test_1ch.gdf": (18512, "a01faf7b73742a01deae89e2f4cd18c581ca5c1f719417bf80ac2ef8a2923762"),
    "Brainvision/test_NO.vhdr": (1451, "aa3f2d42a1ad3897e702c27d09abdd261f01ccdeb0dae2e674af25fe7be72261"),
    "Brainvision/test_NO.vmrk": (267, "fc02236e72a90124ea04f171a065ae94784ec707bbd96632a86a44499bf7cf27"),
    "Brainvision/test_NO.eeg": (581880, "894099d7ea0db262bd2dd84918ff96e5c81e39f7677f0405746faaed1623604b"),
    "EEGLAB/test_raw.set": (349568, "95593d49974d3ce8b0bd37e086536b9cedcf0abf38f2453092fd88de0bbde18e"),
    "EEGLAB/test_raw.fdt": (3904512, "3ec388b9a080c723c00cd380403d64cc754929d828375bbd53bd83b468136759"),
    "NihonKohden/MB0400FU.EEG": (308031, "a2900ceaa0479182e5845dc3f3f8ee4bd6800bd4ec9555a59008486253c42d0a"),
    "NihonKohden/MB0400FU.PNT": (7720, "d1bbf1ff13de54407f3f3afe18ae004c3e23747f82c2b76eea977efd13985684"),
    "NihonKohden/MB0400FU.21E": (24773, "4704c38a17c5e04c6b46ddc3fac2f2ef5cb46ca27f9a7f3df1c5a970ee9eb3a1"),
    "NihonKohden/MB0400FU.LOG": (495309, "60262a77a8136c595eae7a4c1fb71853d806a83ef0a40e2c9fc03f0fbc0fa714"),
    "Persyst/sub-pt1_ses-02_task-monitor_acq-ecog_run-01_clip2.lay": (1869, "fa1aae5c47fd6c0e7d282fd27ee8c6a5d3ae06bb74687268a5f64fc00834138b"),
    "Persyst/sub-pt1_ses-02_task-monitor_acq-ecog_run-01_clip2.dat": (281204, "b21b45af347f2fde710da46af66128be63058db2bcc6b566c2934fa42ce6b0ba"),
    "CTF/somMDYO-18av.ds_raw.fif": (516470, "dff9637b1a85e8de0066948756c9254b237ebcd20d5681222324861bf19f4e9f"),
    "KIT/test_as-raw.con": (169728, "4d3112d78286458e09beb2bdfd85cf9ee21f89abf9d02096704aebeaae0df23b"),
    "KIT/MQKIT_125.hsp": (54395, "f85eaaf44afaf71b5523a9a26f50df8d0838ea137b1b71c6e15e5226d00e4f4e"),
    "KIT/MQKIT_125.elp": (734, "833f7f20e452b822adad078207bba41b986b9594f58e0379f2d75bac38a51025"),
    "SNIRF/NIRx/NIRSport2/1.0.3/2021-05-05_001.snirf": (244038, "8867156c3b6e04a6abfaf5d14a86c2a4855f946bed0ef303ee589acb85d6bb31"),
    "CTF/testdata_ctf.ds/ClassFile.cls": (186, "bd91e66437d53bfbb4cd03ce9394714b4ec4fd715bddfca3c4fabe965476378b"),
    "CTF/testdata_ctf.ds/params.dsc": (467, "2b4dee7383882a1fc6f1d84d5ba4c3181c461f5d6aaf5af204cc534289e5fc92"),
    "CTF/testdata_ctf.ds/processing.cfg": (1185, "c668cb17fbe4cfec9a29c3ec85ecaf7e61278df863fbe1a9ea8e77960db4baf4"),
    "CTF/testdata_ctf.ds/testdata_ctf.acq": (40798, "e0837500432d5f8c5ff940a53778469c1a3bf83852355fa922f256c5adc08623"),
    "CTF/testdata_ctf.ds/testdata_ctf.hc": (824, "37ee610fdcff3689b95c0e461fe7c18d5582109120bb39e6e12d651931eb515c"),
    "CTF/testdata_ctf.ds/testdata_ctf.infods": (2620, "72d71ee90fea7a49b056a228101a9b84f91600585a000484061fbd7ea9f5c3b3"),
    "CTF/testdata_ctf.ds/testdata_ctf.meg4": (17088008, "30ef47c85083ff3892d5565e487287f71146646a4bff6c283638939801c7f788"),
    "CTF/testdata_ctf.ds/testdata_ctf.newds": (350, "5d2ace836414f294685574d3720f36ecd529b4b18668c8d54c9986e98b9e3cf9"),
    "CTF/testdata_ctf.ds/testdata_ctf.res4": (3260865, "a75ccb0a74910d1f09f1e35944ced09591f3048a850718bcda95a83e16e27146"),
    "EGI/test_egi.mff/Contents/Info.plist": (365, "6f27e762e8f58329bece4b4565ab93856edc8ce64a4b5e8994b7843562d80b1e"),
    "EGI/test_egi.mff/Contents/PkgInfo": (8, "ffe6cb5c0493916f026fb8ba01b7b07c7746ca6cb0cb499051ec45575a3bbadb"),
    "EGI/test_egi.mff/Events_255 DINs.xml": (4495, "a791b91c341a876b15cac3b9cf52f20e4f1f18d1910f0704af36224ff078af05"),
    "EGI/test_egi.mff/coordinates.xml": (30873, "3c49e412457581cf74b6627453a3ab182e1f29263f4d3beab4eb077200d1b9f7"),
    "EGI/test_egi.mff/epochs.xml": (330, "a887f8c70d2aa45a9a8f85b10108454b3dfd33f681d71740bc2fa499104bf262"),
    "EGI/test_egi.mff/info.xml": (403, "0bb8648abe34e06c1adeb6caebce4c71aacc0d94091f424e74476eaa15bcc0b4"),
    "EGI/test_egi.mff/info1.xml": (13539, "84a6d45f2848fe0463855f697b0bc6141d998e3589918014b72b517ba58af0e6"),
    "EGI/test_egi.mff/log_testfile23022017_20170223_113514.txt": (5683, "cab955b4ffd09896a1e5890e09d4ad6f181fa30e7df0f1b38fbc9190dce14482"),
    "EGI/test_egi.mff/recordingSettings.xml": (90218, "ac5aff6be185770496d890f18d8ab0d39a9d25aed3c4ca6486cbeff8d94c1eb2"),
    "EGI/test_egi.mff/sensorLayout.xml": (39497, "43e8e4423bc3fc56f85b7cf3ff3106010d1f674505b0e2d555117b07360f9965"),
    "EGI/test_egi.mff/signal1.bin": (11315960, "3069e20983ca2861bb16a6dc8e5edc32f988380ae9cd06821b7db221d43a0a33"),
    "EGI/test_egi.mff/subject.xml": (2458, "09ca61cd8ca308a2c836647ca455acac803050dbb82f071d7472f0d611340dd6"),
    "EGI/test_egi.mff/workspace.plist": (31271, "f91a4973940cac0e3bcfca88cf26d3df6e0990241413b5737386b3d7940a70cd"),
    "NIRx/nirscout/nirx_15_3_recording/NIRS-2020-08-18_001.avg": (1520, "b91ca552e15f28e8658df35916a72383977303573f26dec53092ae866913d787"),
    "NIRx/nirscout/nirx_15_3_recording/NIRS-2020-08-18_001.dat": (60022, "4d172da66436d9396ea4d4484dc49281ba3eb0b39503c66d5b85eb16e0e14e85"),
    "NIRx/nirscout/nirx_15_3_recording/NIRS-2020-08-18_001.evt": (60, "94c5dfe1b32742bc79d7b27ad65d4e10d2d1fc76d13e4576cee7721b4c7c8640"),
    "NIRx/nirscout/nirx_15_3_recording/NIRS-2020-08-18_001.hdr": (1913, "cd343473d1a2ca8f398e96036fc5fb7d7e4a5c7f8a75712e2148a128d16698b5"),
    "NIRx/nirscout/nirx_15_3_recording/NIRS-2020-08-18_001.inf": (157, "3f67ad9e5618992cf0d0a80e296a57aa77e8734ed1ba5aec148cbfab0be97a58"),
    "NIRx/nirscout/nirx_15_3_recording/NIRS-2020-08-18_001.set": (165, "1b20cedc00c50efdbccf2436e2a92edc2bb7bdf8895c9b4bc2bcc30ffa32c3d5"),
    "NIRx/nirscout/nirx_15_3_recording/NIRS-2020-08-18_001.tpl": (248, "73aec2693a044208d833591cd4792fedc2d3f9da5698b827dc3cfc3677dadf65"),
    "NIRx/nirscout/nirx_15_3_recording/NIRS-2020-08-18_001.wl1": (176220, "d10c33711c39fc24324044953417097e48c3ff15f62d764e0d8edf39c314488c"),
    "NIRx/nirscout/nirx_15_3_recording/NIRS-2020-08-18_001.wl2": (176220, "c05358bfa1180c03a5e826eb0382e248280f7c659063b91660ea847babcb728b"),
    "NIRx/nirscout/nirx_15_3_recording/NIRS-2020-08-18_001_config.txt": (378, "39bdc363ba37bf16f20fc1f247491acec03f26e61cf787ff5ee15e8699e178e6"),
    "NIRx/nirscout/nirx_15_3_recording/NIRS-2020-08-18_001_probeInfo.mat": (2429, "24f7eb2879d115c1c77da1adc9810c0a39fdf6f85d62d6ab612f450b5e7d293a"),
    "BTi/erm_HFH/c,rfDC": (5941296, "3d4582a3e0eb45820d902dd56dfcd1764285f3602da34e58f61e59cb38111b36"),
    "BTi/erm_HFH/config": (119608, "5cf549916dacd3ec3d0b006c64c39781d8e6114792b6a5add37c7d13b03e9c22"),
}

# family -> names for fetch_mne_testing (a name ending in "/" is a folder: every pinned file below it)
MNE_TESTING_FAMILIES: dict[str, tuple[str, ...]] = {
    "edf": ("EDF/test_reduced.edf", "EDF/test_utf8_annotations.edf"),
    "bdf": ("BDF/test_bdf_stim_channel.bdf",),
    "gdf": ("GDF/test_1ch.gdf",),
    "brainvision": ("Brainvision/test_NO.vhdr", "Brainvision/test_NO.vmrk", "Brainvision/test_NO.eeg"),
    "eeglab": ("EEGLAB/test_raw.set", "EEGLAB/test_raw.fdt"),
    "egi": ("EGI/test_egi.mff/",),
    "nihon": ("NihonKohden/MB0400FU.EEG", "NihonKohden/MB0400FU.PNT", "NihonKohden/MB0400FU.21E", "NihonKohden/MB0400FU.LOG"),
    "persyst": (
        "Persyst/sub-pt1_ses-02_task-monitor_acq-ecog_run-01_clip2.lay",
        "Persyst/sub-pt1_ses-02_task-monitor_acq-ecog_run-01_clip2.dat",
    ),
    "ctf": ("CTF/testdata_ctf.ds/",),
    "kit": ("KIT/test_as-raw.con", "KIT/MQKIT_125.hsp", "KIT/MQKIT_125.elp"),
    "bti": ("BTi/erm_HFH/",),
    "snirf": ("SNIRF/NIRx/NIRSport2/1.0.3/2021-05-05_001.snirf",),
    "nirx": ("NIRx/nirscout/nirx_15_3_recording/",),
    "fif_info": ("CTF/somMDYO-18av.ds_raw.fif",),
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


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def mne_testing_root() -> Path:
    return CACHE / f"mne-testing-data-{MNE_TESTING_COMMIT}"


def _members(name: str) -> list[str]:
    if name.endswith("/"):
        found = [p for p in MNE_TESTING_FILES if p.startswith(name)]
    else:
        found = [name] if name in MNE_TESTING_FILES else []
    if not found:
        raise KeyError(f"{name!r} is not a pinned mne-testing-data file or folder")
    return found


def fetch_mne_testing(names: Iterable[str]) -> dict[str, Path]:
    """Download (once) the named pinned files or folders and return ``{name: local path}``.

    A name is a path in mne-testing-data (``"EDF/test_reduced.edf"``) or a folder ending in ``/``
    (``"CTF/testdata_ctf.ds/"``, every pinned file below it).  Each file's SHA-256 is checked.
    """
    root = mne_testing_root()
    out: dict[str, Path] = {}
    for name in names:
        for rel in _members(name):
            size, digest = MNE_TESTING_FILES[rel]
            dest = root / rel
            if not dest.exists() or dest.stat().st_size != size or sha256(dest) != digest:
                dest.parent.mkdir(parents=True, exist_ok=True)
                url = (
                    f"https://raw.githubusercontent.com/mne-tools/mne-testing-data/{MNE_TESTING_COMMIT}/"
                    + urllib.parse.quote(rel)
                )
                tmp = dest.with_name(dest.name + ".part")
                urllib.request.urlretrieve(url, tmp)
                tmp.replace(dest)
            if sha256(dest) != digest:
                raise RuntimeError(f"SHA-256 mismatch for {rel}")
        out[name] = root / name.rstrip("/")
    return out


def fetch_bids_examples(names: Iterable[str]) -> dict[str, Path]:
    """Shallow fetch of bids-examples at the pinned commit (once); ``{name: dataset folder}``.

    The repository root (``default-config.json``) is ``dest.parent`` of any returned folder.
    """
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
    out = {}
    for name in names:
        if not (dest / name).is_dir():
            raise KeyError(f"{name!r} is not a bids-examples dataset at {BIDS_EXAMPLES_COMMIT}")
        out[name] = dest / name
    return out


# --- planted synthetic recordings --------------------------------------------------------------

CHANNELS = ("Fp1", "Smith-Fp1", "EMG1")
EDF_PATIENT = "MRN0042 M 01-JAN-1970 Smith_John"
EDF_RECORDING = "Startdate 15-FEB-2025 EEGtech_Jane Hospital_X"
EDF_ANNOTATIONS = ("Smith John said hello", "1", "eyes closed")
FIF_DIG_COUNTS = {"cardinal": 3, "hpi": 4, "extra": 200}


def _subject_dir(dest: Path) -> Path:
    d = Path(dest) / SUBJECT_DIR
    d.mkdir(parents=True, exist_ok=True)
    return d


def _eeg_data(n_ch: int = len(CHANNELS)) -> np.ndarray:
    """Microvolt-scale random signals (n_ch, N_SAMPLES), seed 0."""
    return np.random.default_rng(0).standard_normal((n_ch, N_SAMPLES)) * 20.0


def _planted_edf_like(dest: Path, bdf: bool) -> Path:
    import edfio

    sig_cls = edfio.BdfSignal if bdf else edfio.EdfSignal
    file_cls = edfio.Bdf if bdf else edfio.Edf
    rng = (-8000.0, 8000.0) if bdf else (-500.0, 500.0)
    signals = [
        sig_cls(row, sampling_frequency=SFREQ, label=label, physical_dimension="uV", physical_range=rng)
        for row, label in zip(_eeg_data(), CHANNELS)
    ]
    edf = file_cls(
        signals,
        patient=edfio.Patient(code="MRN0042", sex="M", birthdate=date(1970, 1, 1), name="Smith_John"),
        recording=edfio.Recording(
            startdate=date(2025, 2, 15),
            hospital_administration_code="EEGtech_Jane",
            investigator_technician_code="Hospital_X",
        ),
        starttime=time(10, 0, 0),
        annotations=[
            edfio.EdfAnnotation(onset=float(i + 1), duration=None, text=t) for i, t in enumerate(EDF_ANNOTATIONS)
        ],
    )
    path = _subject_dir(dest) / f"Smith_John_rest.{'bdf' if bdf else 'edf'}"
    edf.write(path)
    # edfio appends an equipment code ("X"); the planted field is exactly EDF_RECORDING
    raw = bytearray(path.read_bytes())
    raw[88:168] = EDF_RECORDING.encode("ascii").ljust(80)
    path.write_bytes(bytes(raw))
    return path


def planted_edf(dest: Path) -> Path:
    """EDF+: patient/recording fields, TAL annotations and the channels ``Fp1``, ``Smith-Fp1``, ``EMG1``."""
    return _planted_edf_like(dest, bdf=False)


def planted_bdf(dest: Path) -> Path:
    """BDF with the same planted header, annotations and channels as ``planted_edf``."""
    return _planted_edf_like(dest, bdf=True)


def planted_brainvision(dest: Path) -> Path:
    """``Smith_John_rest.vhdr`` with ``.vmrk`` and ``.eeg`` (float32, multiplexed); returns the ``.vhdr``."""
    d = _subject_dir(dest)
    data = _eeg_data().astype("<f4")
    (d / "Smith_John_rest.eeg").write_bytes(data.T.tobytes())
    vhdr = [
        "Brain Vision Data Exchange Header File Version 1.0",
        "; Data created by the test fixtures",
        "",
        "[Common Infos]",
        "Codepage=UTF-8",
        "DataFile=Smith_John_rest.eeg",
        "MarkerFile=Smith_John_rest.vmrk",
        "DataFormat=BINARY",
        "DataOrientation=MULTIPLEXED",
        f"NumberOfChannels={len(CHANNELS)}",
        f"SamplingInterval={1e6 / SFREQ:g}",
        "",
        "[Binary Infos]",
        "BinaryFormat=IEEE_FLOAT_32",
        "",
        "[Channel Infos]",
        *(f"Ch{i + 1}={c},,1,\u00b5V" for i, c in enumerate(CHANNELS)),
        "",
        "[Comment]",
        "",
        "Patient: Smith John, MRN0042",
        "",
    ]
    (d / "Smith_John_rest.vhdr").write_text("\n".join(vhdr), encoding="utf-8")
    vmrk = [
        "Brain Vision Data Exchange Marker File, Version 1.0",
        "",
        "[Common Infos]",
        "Codepage=UTF-8",
        "DataFile=Smith_John_rest.eeg",
        "",
        "[Marker Infos]",
        "Mk1=New Segment,,1,1,0,20250215100000000000",
        "Mk2=Stimulus,S  1,256,1,0",
        "Mk3=Comment,Dr Jane Doe,512,1,0",
        "",
    ]
    (d / "Smith_John_rest.vmrk").write_text("\n".join(vmrk), encoding="utf-8")
    return d / "Smith_John_rest.vhdr"


def planted_eeglab(dest: Path) -> Path:
    """Single-file EEGLAB ``.set`` (data inside) with setname, subject, comments and an event type planted."""
    from scipy.io import savemat

    d = _subject_dir(dest)
    labels = np.array([(c,) for c in CHANNELS], dtype=[("labels", "O")])
    events = np.array(
        [("MRN0042 start", 1.0, 0.0), ("S  1", 257.0, 0.0)],
        dtype=[("type", "O"), ("latency", "f8"), ("duration", "f8")],
    )
    eeg = {
        "setname": "Smith John",
        "filename": "Smith_John_rest.set",
        "filepath": "",
        "subject": "MRN0042",
        "group": "",
        "condition": "",
        "session": [],
        "comments": "Hospital X",
        "nbchan": float(len(CHANNELS)),
        "trials": 1.0,
        "pnts": float(N_SAMPLES),
        "srate": SFREQ,
        "xmin": 0.0,
        "xmax": (N_SAMPLES - 1) / SFREQ,
        "times": np.arange(N_SAMPLES) / SFREQ * 1000.0,
        "data": _eeg_data().astype("<f4"),
        "chanlocs": labels,
        "event": events,
        "urevent": events,
        "epoch": [],
        "icaact": [],
        "icawinv": [],
        "icasphere": [],
        "icaweights": [],
        "icachansind": [],
        "chaninfo": {"plotrad": []},
        "ref": "common",
        "saved": "yes",
    }
    path = d / "Smith_John_rest.set"
    savemat(path, {"EEG": eeg}, appendmat=False)
    return path


def planted_fif(dest: Path) -> Path:
    """Raw FIF: planted subject_info/experimenter/description/proj_name, MEG channels from a testing-data
    FIF, and 3 fiducials + 4 HPI + 200 EXTRA dig points."""
    import mne
    from mne._fiff._digitization import _make_dig_points

    src = fetch_mne_testing(MNE_TESTING_FAMILIES["fif_info"])["CTF/somMDYO-18av.ds_raw.fif"]
    info = mne.io.read_info(src, verbose=False)
    info = mne.pick_info(info, mne.pick_types(info, meg=True, ref_meg=False, exclude=[]), verbose=False)
    rng = np.random.default_rng(0)
    n_ch = len(info["ch_names"])
    rad = lambda n: (rng.standard_normal((n, 3)) * 0.02 + [0, 0, 0.05])  # noqa: E731
    dig = _make_dig_points(
        nasion=[0.0, 0.1, 0.0],
        lpa=[-0.08, 0.0, 0.0],
        rpa=[0.08, 0.0, 0.0],
        hpi=[[0.0, 0.09, 0.02], [-0.07, 0.0, 0.02], [0.07, 0.0, 0.02], [0.0, -0.05, 0.05]],
        extra_points=rad(FIF_DIG_COUNTS["extra"]),
        dig_ch_pos=None,
        coord_frame="head",
    )
    with info._unlock():
        info["sfreq"] = SFREQ
        info["lowpass"] = 100.0
        info["highpass"] = 0.1
        info["dig"] = dig
        info["subject_info"] = {
            "his_id": "MRN0042",
            "first_name": "John",
            "last_name": "Smith",
            "birthday": date(1970, 1, 1),
            "sex": 1,
        }
        info["experimenter"] = "Jane Doe"
        info["description"] = "Hospital X study"
        info["proj_name"] = "Smith pilot"
        info["line_freq"] = 60.0
    raw = mne.io.RawArray(rng.standard_normal((n_ch, N_SAMPLES)) * 1e-13, info, verbose=False)
    raw.set_meas_date(MEAS_DATE)
    path = _subject_dir(dest) / "Smith_John_rest_raw.fif"
    raw.save(path, overwrite=True, verbose=False)
    return path


def planted_snirf(dest: Path) -> Path:
    """Continuous-wave SNIRF (2 sources x 2 detectors x 760/850 nm), planted metaDataTags and stim name."""
    import h5py

    path = _subject_dir(dest) / "Smith_John_rest.snirf"
    n_t = N_SAMPLES
    pairs = [(1, 1), (1, 2), (2, 1), (2, 2)]
    rng = np.random.default_rng(0)
    with h5py.File(path, "w") as f:
        f.create_dataset("formatVersion", data=np.bytes_("1.0"))
        nirs = f.create_group("nirs")
        tags = nirs.create_group("metaDataTags")
        for k, v in {
            "SubjectID": "MRN0042",
            "MeasurementDate": "2025-02-15",
            "MeasurementTime": "10:00:00",
            "Operator": "Jane Doe",
            "LengthUnit": "mm",
            "TimeUnit": "s",
            "FrequencyUnit": "Hz",
        }.items():
            tags.create_dataset(k, data=np.bytes_(v))
        data = nirs.create_group("data1")
        data.create_dataset("dataTimeSeries", data=1.0 + 0.01 * rng.standard_normal((n_t, 2 * len(pairs))))
        data.create_dataset("time", data=np.arange(n_t) / SFREQ)
        k = 1
        for wl in (1, 2):
            for s, dt in pairs:
                ml = data.create_group(f"measurementList{k}")
                ml.create_dataset("sourceIndex", data=np.int32(s))
                ml.create_dataset("detectorIndex", data=np.int32(dt))
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


def _head_shape_points(n: int = 200) -> np.ndarray:
    pts = np.random.default_rng(1).standard_normal((n, 3))
    pts /= np.linalg.norm(pts, axis=1, keepdims=True)
    return pts * 0.09  # metres on a sphere


def planted_ctf_pos(dest: Path) -> Path:
    """CTF/Polhemus head-shape ``.pos`` (count line, then ``index x y z`` in cm); companion file only."""
    pts = _head_shape_points() * 100
    lines = [str(len(pts))] + [f"{i + 1}\t{x:.4f}\t{y:.4f}\t{z:.4f}" for i, (x, y, z) in enumerate(pts)]
    path = _subject_dir(dest) / "Smith_John_rest.pos"
    path.write_text("\n".join(lines) + "\n")
    return path


def planted_kit_hsp(dest: Path) -> Path:
    """KIT/Polhemus head-shape ``.hsp`` (``%`` header, then ``x y z`` in mm); companion file only."""
    pts = _head_shape_points() * 1000
    lines = ["% Shape file", "% Digitized points", f"% {len(pts)} points", "//Position of fiducials"]
    lines += [f"{x:.3f}\t{y:.3f}\t{z:.3f}" for x, y, z in pts]
    path = _subject_dir(dest) / "Smith_John_rest.hsp"
    path.write_text("\n".join(lines) + "\n")
    return path


def planted_nwb(dest: Path) -> Path:
    """NWB iEEG: 8 channels, planted session/experimenter/institution/subject and a free-text trial note."""
    from pynwb import NWBFile, NWBHDF5IO
    from pynwb.ecephys import ElectricalSeries
    from pynwb.file import Subject

    nwb = NWBFile(
        session_description="Smith John grid",
        identifier="aimport-planted-nwb",
        session_start_time=MEAS_DATE,
        experimenter=["Jane Doe"],
        institution="Hospital X",
        subject=Subject(
            subject_id="MRN0042",
            date_of_birth=datetime(1970, 1, 1, tzinfo=timezone.utc),
            species="Homo sapiens",
            sex="M",
        ),
    )
    device = nwb.create_device(name="grid_amp")
    group = nwb.create_electrode_group(name="grid", description="8-contact grid", location="cortex", device=device)
    for i in range(8):
        nwb.add_electrode(group=group, location="cortex", x=float(i), y=0.0, z=0.0, imp=1000.0, filtering="none")
    region = nwb.create_electrode_table_region(list(range(8)), "all contacts")
    nwb.add_acquisition(
        ElectricalSeries(
            name="ieeg",
            data=_eeg_data(8).T.astype("float32"),
            electrodes=region,
            rate=SFREQ,
            starting_time=0.0,
        )
    )
    nwb.add_trial_column(name="note", description="free text")
    nwb.add_trial(start_time=2.0, stop_time=3.0, note="seizure Dr Jane")
    path = _subject_dir(dest) / "Smith_John_rest.nwb"
    with NWBHDF5IO(path, "w") as io:
        io.write(nwb)
    return path
