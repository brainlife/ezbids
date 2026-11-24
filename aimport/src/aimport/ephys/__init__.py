"""Electrophysiology and optical module (BIDS ``eeg``, ``meg``, ``ieeg``, ``nirs``, ``emg``): shared constants.

The values below follow the Task 1 capability ruling (``tests/test_ephys_capability.py``), run against
the pinned MNE 1.13.2 and MNE-BIDS 0.20.0:

- every family below resolves to an ``mne.io`` reader, including MEF3 (``read_raw_mef``), which needs
  the optional ``pymef`` package at read time;
- MNE-BIDS anonymize converts EDF/CTF input to a new BrainVision, EDF or FIF file (no source bytes);
- MNE-BIDS writes ``datatype="emg"`` as EDF and as BDF;
- MNE-BIDS writes NIRS from a SNIRF read by ``read_raw_snirf`` with ``anonymize=None``.
"""
from __future__ import annotations

# Output formats per BIDS datatype; the first one is the default.
# ieeg "NWB" is only offered for NWB input (Task 10).
OUTPUT_FORMATS: dict[str, tuple[str, ...]] = {
    "eeg": ("BrainVision", "EDF", "BDF"),
    "ieeg": ("BrainVision", "EDF", "NWB"),
    "emg": ("EDF", "BDF"),
    "meg": ("FIF",),
    "nirs": ("SNIRF",),
}

# Discovery family -> mne.io reader function name. NWB (h5py, Task 10) and Blackrock (neo extra) are
# not read through MNE.
MNE_READERS: dict[str, str] = {
    "edf": "read_raw_edf",
    "bdf": "read_raw_bdf",
    "gdf": "read_raw_gdf",
    "brainvision": "read_raw_brainvision",
    "eeglab": "read_raw_eeglab",
    "cnt": "read_raw_cnt",
    "egi": "read_raw_egi",
    "nihon": "read_raw_nihon",
    "persyst": "read_raw_persyst",
    "mef3": "read_raw_mef",
    "fif": "read_raw_fif",
    "ctf": "read_raw_ctf",
    "bti": "read_raw_bti",
    "kit": "read_raw_kit",
    "nirx": "read_raw_nirx",
    "hitachi": "read_raw_hitachi",
    "snirf": "read_raw_snirf",
}
