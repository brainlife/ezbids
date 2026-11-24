"""SNIRF 1.1 written from scratch with h5py (Task 10): continuous-wave amplitude only.

``write`` builds a new file from an opened, de-identified recording (``deid.clean``); nothing of the
source file is copied, so unknown groups, custom ``metaDataTags`` and free-text stim names cannot survive:

- ``/formatVersion`` = ``1.1``;
- ``/nirs/metaDataTags``: exactly ``SubjectID`` (the BIDS label), ``MeasurementDate`` and ``MeasurementTime``
  (``"unknown"``), ``LengthUnit``, ``TimeUnit`` and ``FrequencyUnit`` (from the source when it states a
  unit MNE reads, else ``m``, ``s``, ``Hz``);
- ``/nirs/data1``: ``dataTimeSeries`` (written in chunks of at most ``CHUNK_BYTES`` from
  ``raw.get_data(start, stop)``), ``time`` and one ``measurementList<k>`` per channel;
- ``/nirs/probe``: ``wavelengths``, ``sourcePos3D``, ``detectorPos3D``, ``sourceLabels`` (``S<n>``) and
  ``detectorLabels`` (``D<n>``);
- one ``/nirs/stim<k>`` per event label: ``name`` = the label, ``data`` rows ``[onset, duration, 1]``.

``rewrite`` reads an input SNIRF with ``read_raw_snirf`` (``preload=False``) and writes it again through
``write``; it never uses ``h5py.copy``.
"""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np

from . import events

FORMAT_VERSION = "1.1"
CHUNK_BYTES = 64 * 2**20
UNKNOWN = "unknown"
CW_AMPLITUDE = 1
TAGS = ("SubjectID", "MeasurementDate", "MeasurementTime", "LengthUnit", "TimeUnit", "FrequencyUnit")
DEFAULT_UNITS = {"LengthUnit": "m", "TimeUnit": "s", "FrequencyUnit": "Hz"}
LENGTH_SCALE = {"m": 1.0, "cm": 100.0, "mm": 1000.0}  # metres (MNE) -> the unit written
TIME_SCALE = {"s": 1.0, "ms": 1000.0}
FREQUENCY_UNITS = frozenset({"Hz", "kHz", "MHz"})
_CHANNEL = re.compile(r"^S(\d+)_D(\d+) (\d+)$")


def _text(value) -> str:
    if isinstance(value, np.ndarray):
        value = value.reshape(-1)[0] if value.size else ""
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    return str(value)


def source_units(path: Path) -> dict[str, str]:
    """The source's ``LengthUnit``/``TimeUnit``/``FrequencyUnit`` when they are units this writer converts
    to; anything else (or no tag) gives the default."""
    import h5py

    out = dict(DEFAULT_UNITS)
    allowed = {"LengthUnit": LENGTH_SCALE, "TimeUnit": TIME_SCALE, "FrequencyUnit": FREQUENCY_UNITS}
    with h5py.File(path, "r") as f:
        tags = f.get("nirs/metaDataTags")
        if tags is None:
            return out
        for k in DEFAULT_UNITS:
            if k in tags:
                v = _text(tags[k][()]).strip()
                if v in allowed[k]:
                    out[k] = v
    return out


def _str_ds(group, name: str, value) -> None:
    import h5py

    group.create_dataset(name, data=value, dtype=h5py.string_dtype("utf-8"))


def write(raw, dest: Path, subject_label: str, labels: dict[str, str],
          units: dict[str, str] | None = None) -> None:
    """Write ``raw`` (continuous-wave amplitude channels ``S<i>_D<j> <wavelength>``) as a new SNIRF file.

    ``labels``: annotation description -> the stim name written; a description not in it raises
    ValueError (without its text). ``units``: the metaDataTags units (``source_units``).
    """
    import h5py

    units = {**DEFAULT_UNITS, **(units or {})}
    length = LENGTH_SCALE.get(units["LengthUnit"])
    tscale = TIME_SCALE.get(units["TimeUnit"])
    if length is None or tscale is None or units["FrequencyUnit"] not in FREQUENCY_UNITS:
        raise ValueError("unsupported SNIRF unit")
    types = raw.get_channel_types()
    if not types or any(t != "fnirs_cw_amplitude" for t in types):
        raise ValueError("SNIRF output holds continuous-wave amplitude channels only")
    chans = []
    for ch in raw.info["chs"]:
        m = _CHANNEL.fullmatch(ch["ch_name"])
        if m is None:
            raise ValueError("an fNIRS channel name is not S<i>_D<j> <wavelength>")
        chans.append((int(m.group(1)), int(m.group(2)), int(m.group(3)), ch["loc"]))
    sources = sorted({c[0] for c in chans})
    detectors = sorted({c[1] for c in chans})
    wavelengths = sorted({c[2] for c in chans})
    src_pos = np.zeros((len(sources), 3))
    det_pos = np.zeros((len(detectors), 3))
    for s, d, _, loc in chans:
        src_pos[sources.index(s)] = loc[3:6]
        det_pos[detectors.index(d)] = loc[6:9]

    ann = raw.annotations
    base = raw.first_time if ann.orig_time is not None else 0.0
    stims: dict[str, list[list[float]]] = {}
    for onset, duration, desc in zip(ann.onset, ann.duration, ann.description):
        if desc not in labels:
            raise ValueError("an annotation description is not in the event map")
        stims.setdefault(labels[desc], []).append([(float(onset) - base) * tscale, float(duration) * tscale, 1.0])

    n_ch, n_t = len(chans), int(raw.n_times)
    step = max(1, CHUNK_BYTES // (8 * n_ch))
    dest = Path(dest)
    with h5py.File(dest, "w") as f:
        _str_ds(f, "formatVersion", FORMAT_VERSION)
        nirs = f.create_group("nirs")
        tags = nirs.create_group("metaDataTags")
        for k, v in (("SubjectID", subject_label), ("MeasurementDate", UNKNOWN), ("MeasurementTime", UNKNOWN),
                     ("LengthUnit", units["LengthUnit"]), ("TimeUnit", units["TimeUnit"]),
                     ("FrequencyUnit", units["FrequencyUnit"])):
            _str_ds(tags, k, v)
        data = nirs.create_group("data1")
        series = data.create_dataset("dataTimeSeries", shape=(n_t, n_ch), dtype="f8",
                                     chunks=(min(n_t, max(1, 2**20 // (8 * n_ch))), n_ch))
        time = data.create_dataset("time", shape=(n_t,), dtype="f8")
        sfreq = float(raw.info["sfreq"])
        for start in range(0, n_t, step):
            stop = min(n_t, start + step)
            series[start:stop] = raw.get_data(start=start, stop=stop).T
            time[start:stop] = np.arange(start, stop) / sfreq * tscale
        for k, (s, d, w, _) in enumerate(chans, 1):
            ml = data.create_group(f"measurementList{k}")
            ml.create_dataset("sourceIndex", data=np.int32(sources.index(s) + 1))
            ml.create_dataset("detectorIndex", data=np.int32(detectors.index(d) + 1))
            ml.create_dataset("wavelengthIndex", data=np.int32(wavelengths.index(w) + 1))
            ml.create_dataset("dataType", data=np.int32(CW_AMPLITUDE))
            ml.create_dataset("dataTypeIndex", data=np.int32(1))
        probe = nirs.create_group("probe")
        probe.create_dataset("wavelengths", data=np.array(wavelengths, dtype="f8"))
        probe.create_dataset("sourcePos3D", data=src_pos * length)
        probe.create_dataset("detectorPos3D", data=det_pos * length)
        _str_ds(probe, "sourceLabels", [f"S{s}" for s in sources])
        _str_ds(probe, "detectorLabels", [f"D{d}" for d in detectors])
        for k, (name, rows) in enumerate(stims.items(), 1):
            stim = nirs.create_group(f"stim{k}")
            _str_ds(stim, "name", name)
            stim.create_dataset("data", data=np.array(rows, dtype="f8"))


def rewrite(src: Path, dest: Path, subject_label: str, labels: dict[str, str],
            units: dict[str, str] | None = None) -> None:
    """An input SNIRF read with ``read_raw_snirf`` (``preload=False``) and written again through ``write``.

    ``labels`` maps the normalised original stim name to the name written (``events.label``)."""
    import mne

    raw = mne.io.read_raw_snirf(src, preload=False, verbose="error")
    names = {d: events.label(d, labels) for d in set(raw.annotations.description)}
    write(raw, dest, subject_label, names, units if units is not None else source_units(src))
