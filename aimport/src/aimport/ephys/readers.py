"""Open recordings lazily (``preload=False``) and summarise their headers.

``open_raw`` returns an ``mne.io.BaseRaw`` whose data stay on disk; ``read_info`` turns its header into a
``RecordingInfo``. Head-shape files are never read unless ``headshape=True``. ``RecordingInfo.view()`` is the
part that may leave ``work/ephys/``: it holds no dates, no annotation text and no names.
"""
from __future__ import annotations

import os
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from importlib.util import find_spec
from pathlib import Path

from .discover import REASON_MEF3, Recording

WARN_LOAD_BYTES = 2 * 2**30
MAX_LOAD_BYTES = 8 * 2**30
EEGLAB_MAX_MAT = 512 * 2**20
REASON_NEO = "Blackrock needs the neo extra: pip install aimport[neo]"
REASON_KIT_DIG = "KIT head shape needs the .elp file and the marker coils (.mrk)"
REASON_MFF = "EGI .mff needs the mffpy package"
REASON_EEGLAB_BIG = "EEGLAB .set above 512 MB with embedded data: save it as MATLAB v7.3 or with a separate .fdt"

SYSTEM_FAMILIES: dict[str, str] = {
    "edf": "EDF",
    "bdf": "BioSemi",
    "gdf": "GDF",
    "brainvision": "BrainVision",
    "eeglab": "EEGLAB",
    "cnt": "Neuroscan",
    "egi": "EGI",
    "nihon": "Nihon Kohden",
    "persyst": "Persyst",
    "mef3": "MEF3",
    "fif": "Neuromag/MEGIN",
    "ctf": "CTF",
    "bti": "BTi/4D",
    "kit": "KIT",
    "nirx": "NIRx",
    "hitachi": "Hitachi",
    "snirf": "SNIRF",
    "nwb": "NWB",
    "blackrock": "Blackrock",
}

LOCAL_FIELDS = ("meas_date", "birthday", "annotations")


class Unsupported(Exception):
    """The recording cannot be opened here; ``reason`` is safe to show (no names, no paths)."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass
class RecordingInfo:
    family: str
    system: str
    sfreq: float
    n_channels: int
    n_times: int
    duration_s: float
    ch_types: dict[str, int] = field(default_factory=dict)
    line_freq: float | None = None
    has_dig: bool = False
    n_headshape_points: int = 0
    wavelengths: list[int] = field(default_factory=list)
    meas_date: datetime | None = None  # local only
    birthday: date | None = None  # local only
    sex: int | None = None
    hand: int | None = None
    annotations: list[tuple[float, float, str]] = field(default_factory=list)  # local only, raw text

    def view(self) -> dict:
        """The fields that may leave ``work/ephys/`` (no dates, no annotation text)."""
        out = asdict(self)
        for k in LOCAL_FIELDS:
            out.pop(k)
        return out


def max_load_bytes() -> int:
    try:
        return int(os.environ.get("AIMPORT_EPHYS_MAX_LOAD_BYTES", MAX_LOAD_BYTES))
    except ValueError:
        return MAX_LOAD_BYTES


def _companion(rec: Recording, input_dir: Path, *suffixes: str) -> Path | None:
    for c in rec.companions:
        if c.lower().endswith(suffixes):
            return input_dir / c
    return None


def _kit_markers(path: Path):
    """The 5 marker-coil positions stored in a KIT ``.sqd``/``.con`` (MNE's ``read_mrk`` refuses ``.con``)."""
    import numpy as np
    from mne.io.kit.constants import KIT
    from mne.io.kit.kit import _read_dirs

    with open(path, "rb", buffering=0) as fid:
        dirs = _read_dirs(fid)
        fid.seek(dirs[KIT.DIR_INDEX_COREG]["offset"])
        fid.seek(KIT.INT + (2 * KIT.DOUBLE * 16), os.SEEK_CUR)
        count = int(np.fromfile(fid, np.int32, 1)[0])
        pts = []
        for _ in range(count):
            _, _, _, meg_done = np.fromfile(fid, np.int32, 4)
            _, meg = np.fromfile(fid, np.float64, 6).reshape(2, 3)
            if meg_done:
                pts.append(meg)
    return np.array(pts)


def open_neo(path: Path):
    """A ``RawArray`` built through ``neo.rawio.BlackrockRawIO``; loads the signal, so only below the load limit."""
    try:
        from neo.rawio import BlackrockRawIO
    except ImportError as e:
        raise Unsupported(REASON_NEO) from e
    import mne
    import numpy as np

    path = Path(path)
    io = BlackrockRawIO(filename=str(path.with_suffix("")), nsx_to_load=int(path.suffix[-1]))
    io.parse_header()
    stream = 0
    chans = io.header["signal_channels"]
    chans = chans[chans["stream_id"] == io.header["signal_streams"]["id"][stream]]
    n_times = io.get_signal_size(block_index=0, seg_index=0, stream_index=stream)
    need = len(chans) * n_times * 8
    if need > max_load_bytes():
        raise Unsupported(f"Blackrock recording needs about {need / 2**30:.1f} GB in memory")
    raw_chunk = io.get_analogsignal_chunk(block_index=0, seg_index=0, stream_index=stream)
    data = io.rescale_signal_raw_to_float(raw_chunk, dtype="float64", stream_index=stream).T
    scale = np.array([1e-6 if str(u).strip() in ("uV", "µV") else 1e-3 if str(u).strip() == "mV" else 1.0
                      for u in chans["units"]])
    sfreq = float(io.get_signal_sampling_rate(stream_index=stream))
    info = mne.create_info([str(n) for n in chans["name"]], sfreq, "seeg", verbose=False)
    return mne.io.RawArray(data * scale[:, None], info, verbose=False)


def open_raw(rec: Recording, input_dir: Path, *, headshape: bool = False):
    """Open one recording with ``preload=False``. Raises ``Unsupported`` with a safe reason when it cannot."""
    import mne

    input_dir = Path(input_dir)
    path = input_dir / rec.rel
    fam = rec.family
    kw = {"preload": False, "verbose": "error"}
    if rec.excluded:
        raise Unsupported(rec.excluded)
    if fam == "edf":
        return mne.io.read_raw_edf(path, **kw)
    if fam == "bdf":
        return mne.io.read_raw_bdf(path, **kw)
    if fam == "gdf":
        return mne.io.read_raw_gdf(path, **kw)
    if fam == "brainvision":
        return mne.io.read_raw_brainvision(path, **kw)
    if fam == "eeglab":
        if path.stat().st_size > EEGLAB_MAX_MAT and not _is_hdf5(path):
            raise Unsupported(REASON_EEGLAB_BIG)
        return mne.io.read_raw_eeglab(path, **kw)
    if fam == "cnt":
        return mne.io.read_raw_cnt(path, **kw)
    if fam == "egi":
        if path.is_dir() and find_spec("mffpy") is None:
            raise Unsupported(REASON_MFF)
        return mne.io.read_raw_egi(path, **kw)
    if fam == "nihon":
        return mne.io.read_raw_nihon(path, **kw)
    if fam == "persyst":
        return mne.io.read_raw_persyst(path, **kw)
    if fam == "mef3":
        if find_spec("pymef") is None:
            raise Unsupported(REASON_MEF3)
        return mne.io.read_raw_mef(path, **kw)
    if fam == "fif":
        return mne.io.read_raw_fif(path, **kw)
    if fam == "ctf":
        return mne.io.read_raw_ctf(path, system_clock="ignore", **kw)
    if fam == "bti":
        pdf = next((input_dir / c for c in rec.companions if Path(c).name.lower().startswith(("c,rf", "e,rf"))), None)
        config = next((input_dir / c for c in rec.companions if Path(c).name.lower() == "config"), None)
        hs = input_dir / rec.headshape[0] if (headshape and rec.headshape) else None
        return mne.io.read_raw_bti(pdf, config, head_shape_fname=hs, **kw)
    if fam == "kit":
        dig = {}
        if headshape and rec.headshape:
            elp = _companion(rec, input_dir, ".elp")
            mrk = _companion(rec, input_dir, ".mrk")
            markers = mrk if mrk is not None else _kit_markers(path)
            if elp is None or (mrk is None and len(markers) < 3):
                raise Unsupported(REASON_KIT_DIG)
            dig = {"mrk": markers, "elp": elp, "hsp": input_dir / rec.headshape[0]}
        return mne.io.read_raw_kit(path, **dig, **kw)
    if fam == "nirx":
        if any(c.lower().endswith(".hdr") for c in rec.companions):
            return mne.io.read_raw_nirx(path, **kw)
        snirf = _companion(rec, input_dir, ".snirf")
        if snirf is None:
            raise Unsupported("NIRx folder without a header or SNIRF file")
        return mne.io.read_raw_snirf(snirf, **kw)
    if fam == "hitachi":
        return mne.io.read_raw_hitachi(path, **kw)
    if fam == "snirf":
        return mne.io.read_raw_snirf(path, **kw)
    if fam == "blackrock":
        try:
            return mne.io.read_raw_nsx(path, **kw)
        except NotImplementedError:  # NSx 2.1 (NEURALSG): MNE does not read it; neo does
            return open_neo(path)
        except ValueError as e:
            if "NSx file id" not in str(e):  # MNE's "not an NSx file id it supports"
                raise
            return open_neo(path)
    if fam == "nwb":
        raise ValueError("NWB recordings are read by ephys.nwb, not open_raw")
    raise Unsupported(f"no reader for {fam}")


def _is_hdf5(path: Path) -> bool:
    try:
        with open(path, "rb") as fh:
            head = fh.read(520)
    except OSError:
        return False
    return head[:4] == b"\x89HDF" or head[512:516] == b"\x89HDF"


def info_from_raw(rec: Recording, raw) -> RecordingInfo:
    """``RecordingInfo`` from an opened raw (headers only; the data are not touched)."""
    from mne._fiff.constants import FIFF

    info = raw.info
    sfreq = float(info["sfreq"])
    types = raw.get_channel_types()
    subject = info.get("subject_info") or {}
    dig = info.get("dig") or []
    waves = sorted({int(round(float(ch["loc"][9]))) for ch, t in zip(info["chs"], types)
                    if t.startswith("fnirs") and float(ch["loc"][9]) > 0})
    line = info.get("line_freq")
    if line is None:
        line = rec.meta.get("PowerLineFrequency")
    birthday = subject.get("birthday")
    if isinstance(birthday, datetime):
        birthday = birthday.date()
    ann = raw.annotations
    return RecordingInfo(
        family=rec.family,
        system=SYSTEM_FAMILIES.get(rec.family, rec.family),
        sfreq=sfreq,
        n_channels=len(types),
        n_times=int(raw.n_times),
        duration_s=float(raw.n_times) / sfreq if sfreq else 0.0,
        ch_types=dict(Counter(types)),
        line_freq=float(line) if line is not None else None,
        has_dig=bool(dig),
        n_headshape_points=sum(1 for d in dig if d["kind"] == FIFF.FIFFV_POINT_EXTRA),
        wavelengths=waves,
        meas_date=info.get("meas_date"),
        birthday=birthday if isinstance(birthday, date) else None,
        sex=subject.get("sex"),
        hand=subject.get("hand"),
        annotations=[(float(o), float(d), str(s)) for o, d, s in zip(ann.onset, ann.duration, ann.description)],
    )


def read_info(rec: Recording, input_dir: Path) -> RecordingInfo:
    """Header summary of one recording (``preload=False``; head shapes not read)."""
    return info_from_raw(rec, open_raw(rec, input_dir))
