"""QA of the written electrophysiology output: three PNG snapshots per recording, and trace windows for the
interactive viewer (``/qa/traces``, ``/viewer/traces``).

Everything is read from the written output only (the manifest's files, their ``channels.tsv`` and
``events.tsv``), so names are the renamed ones and event labels are codes or safe labels. What this module
writes goes to ``<work>/ephys/qa/<entry id>/`` (local only, never under ``output/``, never uploaded):
``traces.png``, ``psd.png``, ``channels.png`` and, for NIRS, ``hb.npy``/``hb.json`` (HbO/HbR).
"""
from __future__ import annotations

import csv
import json
import re
import threading
from collections import OrderedDict
from pathlib import Path
from typing import Any

import numpy as np

QA_DIR = "qa"
KINDS = ("traces", "psd", "channels")
PRIMARY_EXTENSIONS = (".vhdr", ".edf", ".bdf", ".fif", ".snirf", ".nwb")

# /qa/traces limits
MAX_CHANNELS = 64
MAX_POINTS = 4000
MAX_WINDOW_S = 600.0
DEFAULT_CHANNELS = 32
DEFAULT_WINDOW_S = 10.0

# the snapshots
PNG_CHANNELS = 32
PNG_WINDOW_S = 10.0
PNG_START_S = 30.0
PSD_FMAX = 125.0
PSD_TMAX = 60.0

# NIRS: HbO/HbR computed at render time when the recording is small enough
HB_MAX_BYTES = 512 * 2**20
PPF = 6.0
HB_FILE = "hb.npy"
HB_INFO = "hb.json"

CACHE_SIZE = 4
READ_CHUNK_BYTES = 32 * 2**20

# display units: (scale from SI, unit)
DISPLAY: dict[str, tuple[float, str]] = {
    **{t: (1e6, "µV") for t in ("eeg", "seeg", "ecog", "dbs", "emg", "eog", "ecg")},
    "mag": (1e15, "fT"),
    "grad": (1e13, "fT/cm"),
    "hbo": (1e6, "µM"),
    "hbr": (1e6, "µM"),
}
# BIDS channels.tsv type -> MNE channel type (for NWB, whose file has no per-channel type)
BIDS_TYPES = {"EEG": "eeg", "SEEG": "seeg", "ECOG": "ecog", "DBS": "dbs", "EMG": "emg", "EOG": "eog",
              "ECG": "ecg", "MEGMAG": "mag", "MEGGRADPLANAR": "grad", "MEGGRADAXIAL": "grad"}

# brainlife-lite palette; trace colours per channel type in a fixed, colour-blind-safe order
PRIMARY = "#3d6a92"
TEXT = "#2d3748"
MUTED = "#718096"
GRID = "#e2e8f0"
PANEL = "#ffffff"
BAD = "#d55e00"
TYPE_COLOURS = ("#2f72b5", "#d55e00", "#009e73", "#cc79a7", "#b8860b", "#6a51a3")
TYPE_ORDER = ("eeg", "seeg", "ecog", "dbs", "mag", "grad", "emg", "eog", "ecg", "fnirs_cw_amplitude")
HBO = "#c0392b"
HBR = "#2f72b5"


class WindowError(ValueError):
    """A /qa/traces request outside the limits (the route answers 400)."""


def colour(ch_type: str) -> str:
    if ch_type == "hbo":
        return HBO
    if ch_type == "hbr":
        return HBR
    i = TYPE_ORDER.index(ch_type) if ch_type in TYPE_ORDER else len(TYPE_ORDER)
    return TYPE_COLOURS[i % len(TYPE_COLOURS)]


def qa_root(work: Path) -> Path:
    """``<work>/ephys/qa``."""
    return Path(work) / "ephys" / QA_DIR


def primary_file(manifest_files: list[str]) -> int:
    """The index of the recording's data file in an entry's manifest (a split FIF: its first part)."""
    hits = [i for i, f in enumerate(manifest_files) if f.lower().endswith(PRIMARY_EXTENSIONS)]
    if not hits:
        raise ValueError("no electrophysiology data file in the entry")
    fif = [i for i in hits if manifest_files[i].lower().endswith(".fif")]
    if len(fif) > 1:
        return min(fif, key=lambda i: manifest_files[i])  # _split-01_ sorts first
    return hits[0]


# --- the written sidecars ------------------------------------------------------------------------------


def _sibling(path: Path, suffix: str) -> Path:
    """The BIDS sidecar of a data file: ``sub-01_task-rest_split-01_meg.fif`` -> ``sub-01_task-rest_<suffix>``."""
    base = path.name.rsplit("_", 1)[0]
    base = re.sub(r"_split-\d+$", "", base)
    return path.with_name(f"{base}_{suffix}")


def _tsv(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def _float(text) -> float | None:
    try:
        v = float(text)
    except (TypeError, ValueError):
        return None
    return v if np.isfinite(v) else None


def read_events(data_file: Path) -> list[dict]:
    """``[{"onset", "duration", "label"}]`` from the written ``events.tsv`` (labels: codes or safe labels)."""
    out = []
    for row in _tsv(_sibling(data_file, "events.tsv")):
        onset = _float(row.get("onset"))
        if onset is None:
            continue
        label = row.get("trial_type") or "n/a"
        if label == "n/a":
            label = row.get("value") or "n/a"
        out.append({"onset": onset, "duration": _float(row.get("duration")) or 0.0, "label": label})
    return out


def read_channels(data_file: Path) -> list[dict]:
    return _tsv(_sibling(data_file, "channels.tsv"))


# --- recordings ------------------------------------------------------------------------------------------


class _Recording:
    """A written recording, open lazily: names, types, sfreq, length, ``read`` (SI units), events, bad
    channels and NIRS pairs."""

    name: str
    sfreq: float
    n_times: int
    ch_names: list[str]
    ch_types: list[str]
    raw: Any = None  # the mne Raw, when there is one (compute_psd)

    def read(self, picks: list[int], start: int, stop: int) -> np.ndarray:
        raise NotImplementedError

    def close(self) -> None:
        pass

    @property
    def duration(self) -> float:
        return self.n_times / self.sfreq if self.sfreq else 0.0

    def finish(self, path: Path) -> None:
        self.name = path.name
        self.events = read_events(path)
        rows = read_channels(path)
        bad_names = {r.get("name") for r in rows if (r.get("status") or "").strip().lower() == "bad"}
        bad_prefixes = {n.rsplit(" ", 1)[0] for n in bad_names if n}
        self.bad = [n in bad_names or (t in ("hbo", "hbr") and n.rsplit(" ", 1)[0] in bad_prefixes)
                    for n, t in zip(self.ch_names, self.ch_types)]
        self.pairs = _pairs(self.ch_names, self.ch_types)


class _MneRecording(_Recording):
    def __init__(self, path: Path):
        import mne

        self.raw = mne.io.read_raw(path, preload=False, verbose="error")
        self.sfreq = float(self.raw.info["sfreq"])
        self.n_times = int(self.raw.n_times)
        self.ch_names = list(self.raw.ch_names)
        self.ch_types = list(self.raw.get_channel_types())

    def read(self, picks, start, stop):
        return self.raw.get_data(picks=list(picks), start=start, stop=stop, verbose="error")

    def close(self):
        self.raw.close()


class _NwbRecording(_Recording):
    def __init__(self, path: Path):
        from . import nwb

        self._s = nwb.open_series(path)
        self.sfreq, self.n_times = self._s.sfreq, self._s.n_times
        self.ch_names = list(self._s.ch_names)
        types = {r.get("name"): BIDS_TYPES.get((r.get("type") or "").upper()) for r in read_channels(path)}
        self.ch_types = [types.get(n) or t for n, t in zip(self.ch_names, self._s.ch_types)]

    def read(self, picks, start, stop):
        return self._s.read(list(picks), start, stop)

    def close(self):
        self._s.close()


class _HbRecording(_Recording):
    """HbO/HbR of a NIRS recording, from ``hb.npy`` (memory-mapped) and ``hb.json``."""

    def __init__(self, qa_dir: Path):
        info = json.loads((qa_dir / HB_INFO).read_text())
        self._data = np.load(qa_dir / HB_FILE, mmap_mode="r")
        self.sfreq = float(info["sfreq"])
        self.ch_names, self.ch_types = list(info["names"]), list(info["types"])
        self.n_times = int(self._data.shape[1])

    def read(self, picks, start, stop):
        return np.asarray(self._data[list(picks), start:stop], dtype=float)

    def close(self):
        del self._data


def _pairs(names: list[str], types: list[str]) -> list[list[int]]:
    """NIRS pairs by source-detector: [HbO, HbR], or the raw [lower, higher] wavelength (760/850)."""
    groups: dict[str, list[tuple[str, int]]] = {}
    for i, (n, t) in enumerate(zip(names, types)):
        if t in ("hbo", "hbr", "fnirs_cw_amplitude", "fnirs_od") and " " in n:
            prefix, tail = n.rsplit(" ", 1)
            groups.setdefault(prefix, []).append((tail, i))
    out = []
    for members in groups.values():
        if len(members) != 2:
            continue
        tails = dict(members)
        if set(tails) == {"hbo", "hbr"}:
            out.append([tails["hbo"], tails["hbr"]])
        else:
            def wl(tail: str) -> float:
                return _float(tail) or 0.0

            a, b = sorted(members, key=lambda m: wl(m[0]))
            out.append([a[1], b[1]])
    return sorted(out)


def open_recording(path: Path, qa_dir: Path | None = None) -> _Recording:
    """The written recording at ``path`` (NIRS: its HbO/HbR when ``qa_dir`` holds them)."""
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".snirf" and qa_dir is not None and (Path(qa_dir) / HB_FILE).is_file():
        rec: _Recording = _HbRecording(Path(qa_dir))
    elif suffix == ".nwb":
        rec = _NwbRecording(path)
    else:
        rec = _MneRecording(path)
    try:
        rec.finish(path)
    except Exception:
        rec.close()
        raise
    return rec


# --- windows ---------------------------------------------------------------------------------------------


def _scale(ch_type: str) -> tuple[float, str]:
    return DISPLAY.get(ch_type, (1.0, "V" if ch_type == "fnirs_cw_amplitude" else "a.u."))


def round_sig(a: np.ndarray, digits: int = 4) -> np.ndarray:
    """Each value rounded to ``digits`` significant digits (0 and non-finite values unchanged)."""
    a = np.asarray(a, dtype=float)
    out = a.copy()
    ok = np.isfinite(a) & (a != 0)
    if not ok.any():
        return out
    v = a[ok]
    p = digits - 1 - np.floor(np.log10(np.abs(v))).astype(int)
    r = np.empty_like(v)
    pos = p >= 0
    r[pos] = np.round(v[pos] * 10.0 ** p[pos]) / 10.0 ** p[pos]
    r[~pos] = np.round(v[~pos] / 10.0 ** (-p[~pos])) * 10.0 ** (-p[~pos])
    out[ok] = r
    return out


def _chunk_samples(rec: _Recording, n_picks: int) -> int:
    width = max(n_picks, len(rec.ch_names) if isinstance(rec, _NwbRecording) else n_picks, 1)
    return max(1, READ_CHUNK_BYTES // (8 * width))


def window_data(rec: _Recording, start: int, stop: int, picks: list[int]) -> tuple[np.ndarray, np.ndarray]:
    """(x seconds, y SI) of samples [start, stop): every sample, or when there are more than ``MAX_POINTS``,
    the min and max of each of ``MAX_POINTS // 2`` bins (so a one-sample spike survives). Read in chunks."""
    n = stop - start
    limit = _chunk_samples(rec, len(picks))
    if n <= MAX_POINTS:
        return np.arange(start, stop) / rec.sfreq, rec.read(picks, start, stop)
    bins = MAX_POINTS // 2
    edges = start + np.round(np.linspace(0, n, bins + 1)).astype(np.int64)
    mins = np.empty((len(picks), bins))
    maxs = np.empty((len(picks), bins))
    a = 0
    while a < bins:
        b = a + 1
        while b < bins and edges[b + 1] - edges[a] <= limit:
            b += 1
        data = rec.read(picks, int(edges[a]), int(edges[b]))
        local = (edges[a:b] - edges[a]).astype(np.intp)
        mins[:, a:b] = np.minimum.reduceat(data, local, axis=1)
        maxs[:, a:b] = np.maximum.reduceat(data, local, axis=1)
        a = b
    x = np.empty(2 * bins)
    x[0::2] = edges[:-1] / rec.sfreq
    x[1::2] = (edges[1:] - 1) / rec.sfreq
    y = np.empty((len(picks), 2 * bins))
    y[:, 0::2] = mins
    y[:, 1::2] = maxs
    return x, y


def _jsonable(row: np.ndarray) -> list:
    values = row.tolist()
    if not np.isfinite(row).all():
        values = [v if np.isfinite(v) else None for v in values]
    return values


_CACHE: "OrderedDict[tuple, _Recording]" = OrderedDict()
_LOCK = threading.Lock()


def _cached(path: Path, qa_dir: Path | None) -> _Recording:
    hb = Path(qa_dir) / HB_FILE if qa_dir is not None else None
    key = (str(path), path.stat().st_mtime_ns, str(qa_dir),
           hb.stat().st_mtime_ns if hb is not None and hb.is_file() else None)
    rec = _CACHE.get(key)
    if rec is not None:
        _CACHE.move_to_end(key)
        return rec
    rec = open_recording(path, qa_dir)
    _CACHE[key] = rec
    while len(_CACHE) > CACHE_SIZE:
        _, old = _CACHE.popitem(last=False)
        old.close()
    return rec


def clear_cache() -> None:
    with _LOCK:
        while _CACHE:
            _CACHE.popitem()[1].close()


def check_request(t0: float, t1: float, ch: list[int] | None) -> None:
    if not (np.isfinite(t0) and np.isfinite(t1)) or t1 <= t0:
        raise WindowError("t1 must be after t0")
    if t1 - t0 > MAX_WINDOW_S:
        raise WindowError(f"the window is longer than {MAX_WINDOW_S:g} s")
    if ch is not None and len(ch) > MAX_CHANNELS:
        raise WindowError(f"more than {MAX_CHANNELS} channels")
    if ch is not None and not ch:
        raise WindowError("no channels")


def window(entry_id: str, path: Path, t0: float, t1: float, ch: list[int] | None, *,
           qa_dir: Path | None = None) -> dict:
    """The samples of channels ``ch`` (default the first ``DEFAULT_CHANNELS``) between t0 and t1 seconds, in
    display units rounded to 4 significant digits; ``WindowError`` outside the limits."""
    check_request(t0, t1, ch)
    with _LOCK:
        rec = _cached(Path(path), qa_dir)
        n_ch = len(rec.ch_names)
        picks = list(range(min(DEFAULT_CHANNELS, n_ch))) if ch is None else list(ch)
        if any(not 0 <= i < n_ch for i in picks):
            raise WindowError("a channel index is out of range")
        start = min(max(0, int(round(max(t0, 0.0) * rec.sfreq))), max(rec.n_times - 1, 0))
        stop = min(rec.n_times, max(start + 1, int(round(t1 * rec.sfreq))))
        x, y = window_data(rec, start, stop, picks)
        channels, rows = [], []
        for k, i in enumerate(picks):
            factor, unit = _scale(rec.ch_types[i])
            channels.append({"i": i, "name": rec.ch_names[i], "type": rec.ch_types[i], "unit": unit,
                             "bad": bool(rec.bad[i])})
            rows.append(_jsonable(round_sig(y[k] * factor)))
        picked = set(picks)
        lo, hi = start / rec.sfreq, stop / rec.sfreq
        return {
            "name": rec.name,
            "sfreq": rec.sfreq,
            "t0": lo,
            "t1": hi,
            "duration": rec.duration,
            "channels": channels,
            "all_channels": [{"i": i, "name": n, "type": t, "bad": bool(b)}
                             for i, (n, t, b) in enumerate(zip(rec.ch_names, rec.ch_types, rec.bad))],
            "x": [round(v, 6) for v in x.tolist()],
            "y": rows,
            "events": [e for e in rec.events if e["onset"] <= hi and e["onset"] + e["duration"] >= lo],
            "pairs": [p for p in rec.pairs if p[0] in picked and p[1] in picked],
        }


# --- the snapshots ---------------------------------------------------------------------------------------


def _hb(path: Path, qa_dir: Path) -> None:
    """HbO/HbR (optical density, then the modified Beer-Lambert law) into ``hb.npy`` when the recording's
    samples fit ``HB_MAX_BYTES``; otherwise nothing (the viewer shows the raw wavelengths)."""
    import mne

    raw = mne.io.read_raw(path, preload=False, verbose="error")
    try:
        if len(raw.ch_names) * raw.n_times * 8 > HB_MAX_BYTES:
            return
        od = mne.preprocessing.nirs.optical_density(raw, verbose="error")
        hb = mne.preprocessing.nirs.beer_lambert_law(od, ppf=PPF)
        np.save(qa_dir / HB_FILE, hb.get_data().astype(np.float32))
        (qa_dir / HB_INFO).write_text(json.dumps({"sfreq": float(hb.info["sfreq"]), "names": list(hb.ch_names),
                                                  "types": list(hb.get_channel_types())}))
    finally:
        raw.close()


def _figure(width: float, height: float):
    from matplotlib.figure import Figure

    fig = Figure(figsize=(width, height), dpi=100, facecolor=PANEL)
    return fig


def _style(ax) -> None:
    ax.set_facecolor(PANEL)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=MUTED, labelsize=8)
    ax.xaxis.label.set_color(MUTED)
    ax.yaxis.label.set_color(MUTED)


def _title(fig, title: str) -> None:
    fig.suptitle(title, x=0.01, ha="left", fontsize=11, color=TEXT, fontweight="bold")


def _save(fig, dest: Path) -> None:
    fig.savefig(dest, format="png", facecolor=PANEL, metadata={"Software": None})


def _offsets(y: np.ndarray, types: list[str]) -> tuple[np.ndarray, dict[str, float]]:
    """Each row centred and divided by its type's typical range (the median 5-95 % range), so rows of one
    type keep their relative size; returns the scaled rows and the scale per type."""
    centred = y - np.nanmedian(y, axis=1, keepdims=True)
    spans = np.nanpercentile(centred, 95, axis=1) - np.nanpercentile(centred, 5, axis=1)
    scale: dict[str, float] = {}
    for t in set(types):
        s = float(np.nanmedian([spans[k] for k, tt in enumerate(types) if tt == t]))
        scale[t] = s if np.isfinite(s) and s > 0 else 1.0
    return np.array([centred[k] / scale[t] * 0.8 for k, t in enumerate(types)]), scale


def _traces_png(rec: _Recording, dest: Path, title: str) -> None:
    picks = list(range(min(PNG_CHANNELS, len(rec.ch_names))))
    t0 = min(PNG_START_S, rec.duration / 2)
    start = int(round(t0 * rec.sfreq))
    stop = min(rec.n_times, start + max(1, int(round(PNG_WINDOW_S * rec.sfreq))))
    x, y = window_data(rec, start, stop, picks)
    types = [rec.ch_types[i] for i in picks]
    y = y * np.array([[_scale(t)[0]] for t in types])
    rows, scale = _offsets(y, types)
    fig = _figure(11, max(3.0, 0.9 + 0.24 * len(picks)))
    ax = fig.add_axes((0.12, 0.12 if len(picks) > 8 else 0.2, 0.86, 0.72 if len(picks) > 8 else 0.6))
    _style(ax)
    for k, i in enumerate(picks):
        ax.plot(x, rows[k] - k, color=MUTED if rec.bad[i] else colour(types[k]), linewidth=0.7,
                linestyle="--" if rec.bad[i] else "-")
    ax.set_yticks([-k for k in range(len(picks))])
    ax.set_yticklabels([rec.ch_names[i] for i in picks], fontsize=7, color=TEXT)
    ax.set_ylim(-len(picks) + 0.2, 0.8)
    ax.set_xlim(x[0] if len(x) else 0, x[-1] if len(x) else 1)
    ax.set_xlabel("time (s)")
    for e in rec.events:
        if x[0] <= e["onset"] <= x[-1]:
            ax.axvline(e["onset"], color=PRIMARY, linewidth=0.8, alpha=0.8)
            ax.text(e["onset"], 0.82, e["label"], color=PRIMARY, fontsize=7, va="bottom", ha="left",
                    clip_on=False)
    note = " · ".join(f"{t}: {scale[t]:.3g} {_scale(t)[1]} per row" for t in sorted(scale))
    fig.text(0.12, 0.01, note, fontsize=7, color=MUTED)
    _title(fig, title)
    _save(fig, dest)


def _psd_png(rec: _Recording, dest: Path, title: str, raw=None) -> None:
    import mne

    raw = raw if raw is not None else rec.raw
    by_type: dict[str, list[int]] = {}
    for i, t in enumerate(rec.ch_types if raw is None else raw.get_channel_types()):
        if t in DISPLAY or t == "fnirs_cw_amplitude":
            by_type.setdefault(t, []).append(i)
    by_type = {t: [ix[k] for k in np.unique(np.linspace(0, len(ix) - 1, min(len(ix), MAX_CHANNELS)).astype(int))]
               for t, ix in by_type.items()}
    fig = _figure(8, 4)
    ax = fig.add_axes((0.1, 0.14, 0.86, 0.72))
    _style(ax)
    sfreq = raw.info["sfreq"] if raw is not None else rec.sfreq
    fmax = min(sfreq / 2, PSD_FMAX)
    for t in sorted(by_type, key=lambda t: (TYPE_ORDER + ("hbo", "hbr")).index(t)
                    if t in TYPE_ORDER + ("hbo", "hbr") else 99):
        picks = by_type[t]
        if raw is not None:
            tmax = min(PSD_TMAX, raw.times[-1])
            spec = raw.compute_psd(picks=picks, fmax=fmax, tmax=tmax, verbose="error")
        else:
            n = min(rec.n_times, int(PSD_TMAX * rec.sfreq))
            data = rec.read(picks, 0, n)
            arr = mne.io.RawArray(data, mne.create_info(len(picks), rec.sfreq, t if t in DISPLAY else "misc"),
                                  verbose="error")
            spec = arr.compute_psd(picks="all", fmax=fmax, verbose="error")
        psd, freqs = spec.get_data(picks="all", return_freqs=True)
        factor, unit = _scale(t)
        mean = np.nanmean(psd * factor**2, axis=0)
        with np.errstate(divide="ignore"):
            ax.plot(freqs, 10 * np.log10(mean), color=colour(t), linewidth=1.5,
                    label=f"{t} ({len(picks)} ch)")
    ax.set_xlabel("frequency (Hz)")
    ax.set_ylabel("power (dB re 1 unit²/Hz)")
    ax.grid(color=GRID, linewidth=0.6)
    if by_type:
        ax.legend(frameon=False, fontsize=8, labelcolor=TEXT)
    _title(fig, title)
    _save(fig, dest)


def _channels_png(rec: _Recording, path: Path, dest: Path, title: str) -> None:
    rows = read_channels(path)
    if rows:
        pairs = [((r.get("type") or "n/a"), (r.get("status") or "").strip().lower() == "bad") for r in rows]
    else:
        pairs = list(zip(rec.ch_types, rec.bad))
    types = sorted({t for t, _ in pairs})
    good = [sum(1 for t, b in pairs if t == tt and not b) for tt in types]
    bad = [sum(1 for t, b in pairs if t == tt and b) for tt in types]
    fig = _figure(8, 3.2)
    ax = fig.add_axes((0.1, 0.2, 0.86, 0.62))
    _style(ax)
    xs = np.arange(len(types))
    ax.bar(xs, good, color=PRIMARY, width=0.5, label="good", linewidth=0)
    ax.bar(xs, bad, bottom=good, color=BAD, width=0.5, label="bad (channels.tsv status)", linewidth=0)
    ax.set_xlim(-0.75, max(len(types), 4) - 0.25)
    for x_, g, b in zip(xs, good, bad):
        ax.text(x_, g + b, f"{g + b}" + (f" ({b} bad)" if b else ""), ha="center", va="bottom", fontsize=8,
                color=TEXT)
    ax.set_xticks(xs)
    ax.set_xticklabels(types, fontsize=8, color=TEXT)
    ax.set_ylabel("channels")
    ax.set_ylim(0, max([g + b for g, b in zip(good, bad)] + [1]) * 1.15)
    ax.legend(frameon=False, fontsize=8, labelcolor=TEXT, ncol=2, loc="lower right", bbox_to_anchor=(1, 1.0))
    _title(fig, title)
    _save(fig, dest)


def render(entry_id: str, bids_path: Path, out_dir: Path) -> dict[str, str]:
    """traces.png, psd.png and channels.png of the written recording at ``bids_path`` into ``out_dir``
    (``<work>/ephys/qa/<entry id>/``); NIRS: also hb.npy. Returns kind -> PNG path."""
    import matplotlib

    matplotlib.use("Agg", force=False)
    bids_path, out_dir = Path(bids_path), Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    if bids_path.suffix.lower() == ".snirf":
        _hb(bids_path, out_dir)
    title = bids_path.name
    rec = open_recording(bids_path, out_dir)
    hb_raw = None
    try:
        if isinstance(rec, _HbRecording):
            import mne

            info = mne.create_info(rec.ch_names, rec.sfreq, "misc")
            n = min(rec.n_times, int(PSD_TMAX * rec.sfreq) + 1)
            hb_raw = mne.io.RawArray(rec.read(list(range(len(rec.ch_names))), 0, n), info, verbose="error")
            hb_raw.set_channel_types(dict(zip(rec.ch_names, rec.ch_types)), on_unit_change="ignore",
                                     verbose="error")
        out = {k: out_dir / f"{k}.png" for k in KINDS}
        _traces_png(rec, out["traces"], title)
        _psd_png(rec, out["psd"], title, raw=hb_raw)
        _channels_png(rec, bids_path, out["channels"], title)
    finally:
        rec.close()
    return {k: str(v) for k, v in out.items()}
