"""NWB iEEG input (Task 10): metadata (``read_meta``), identifying text (``harvest``) and a de-identified copy
(``write``), never the source file.

``write`` builds a new NWB file with pynwb and streams only the ``/acquisition`` ``ElectricalSeries``
samples (and timestamps) from the source, chunk by chunk (``CHUNK_BYTES`` per read), plus the
``/general/extracellular_ephys`` electrodes table:

- ``session_description="n/a"``, a new ``identifier`` (uuid4), ``session_start_time``,
  ``timestamps_reference_time`` and ``file_create_date`` all ``1900-01-01T00:00:00+00:00``;
- ``subject`` reduced to ``subject_id`` (the BIDS label), ``species`` and ``sex``;
- electrode ``location`` kept only when it is made of anatomical words (``ANATOMY_WORDS``), else ``n/a``;
  electrode groups, series and non-standard interval tables get generated names (``group_001``,
  ``ElectricalSeries``, ``intervals_001``); electrode ``label`` values through the channel rule
  (``renames``); one device ``amplifier``; group descriptions ``n/a``;
- every ``TimeIntervals`` table rebuilt with ``start_time``, ``stop_time`` and a coded ``label`` column only;
- nothing under ``/processing``, ``/analysis``, ``/stimulus``; no cached ``/specifications`` (readers use
  their own core and hdmf-common schema), and ``_prune`` drops any namespace other than those two.

The text of an interval row (its string cells joined with ``" / "``, or the table name when it has none) is
what the event coding sees, in ``read_meta`` (annotations) and in ``write`` (labels) alike.
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from ..scrub import redact
from . import events

EPOCH = datetime(1900, 1, 1, tzinfo=timezone.utc)
EPOCH_TEXT = "1900-01-01T00:00:00+00:00"
NA = "n/a"
CHUNK_BYTES = 16 * 2**20
KEPT_NAMESPACES = ("core", "hdmf-common")
EMPTIED_GROUPS = ("processing", "analysis", "stimulus")
GENERAL_TEXT = ("session_description", "experimenter", "institution", "lab", "notes", "experiment_description",
                "protocol", "identifier", "session_id", "keywords", "related_publications", "surgery", "virus",
                "pharmacology", "slices", "stimulus", "data_collection", "source_script")
INTERVAL_COLUMNS = ("start_time", "stop_time")
SEX = {"M": 1, "F": 2}
TYPE_WORDS = (("dbs", "dbs"), ("depth", "seeg"), ("seeg", "seeg"), ("shaft", "seeg"), ("grid", "ecog"),
              ("strip", "ecog"), ("ecog", "ecog"))
DEFAULT_TYPE = "seeg"
CHANNEL_TYPES = ("seeg", "ecog", "dbs")
STANDARD_TABLES = ("trials", "epochs", "invalid_times")
# words an electrode location may hold to be written (anything else is n/a): brain regions and sides
ANATOMY_WORDS = frozenset("""
cortex cortical subcortical gray grey white matter frontal temporal parietal occipital insula insular cingulate
anterior posterior superior inferior middle medial lateral mesial left right l r lh rh hemisphere lobe gyrus
sulcus pole hippocampus hippocampal amygdala parahippocampal entorhinal fusiform lingual cuneus precuneus
precentral postcentral central orbitofrontal orbital prefrontal premotor motor sensory sensorimotor
supplementary area thalamus thalamic caudate putamen pallidus globus nucleus subthalamic accumbens striatum
basal ganglia cerebellum cerebellar brainstem pons midbrain ventricle opercular operculum rectus angular
supramarginal calcarine heschl transverse dorsal ventral rostral caudal anteromedial unknown and of
""".split())
PYNWB_DEFAULTS = frozenset({"no description", "no comments"})


def _text(value) -> str:
    if isinstance(value, np.ndarray):
        value = value.reshape(-1)[0] if value.size else ""
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    return str(value)


def _texts(ds) -> list[str]:
    value = ds[()]
    if isinstance(value, np.ndarray):
        return [_text(v) for v in value.reshape(-1).tolist()]
    return [_text(value)]


def _ntype(obj) -> str:
    return _text(obj.attrs.get("neurodata_type", ""))


def _is_string(ds) -> bool:
    import h5py

    return ds.dtype.kind in "SUO" and h5py.check_ref_dtype(ds.dtype) is None


# --- reading (h5py, lazy) -----------------------------------------------------------------------------


def _series(f) -> list[Any]:
    acq = f.get("acquisition")
    if acq is None:
        return []
    return [acq[k] for k in sorted(acq) if _ntype(acq[k]) == "ElectricalSeries" and "data" in acq[k]]


def _electrodes(f) -> dict[str, list]:
    """Columns of the electrodes table: ``group_name``, ``location``, ``label`` (strings), ``x``/``y``/``z``/``imp``
    (floats, or absent), the group descriptions, and the electrode labels used as channel names."""
    table = f.get("general/extracellular_ephys/electrodes")
    out: dict[str, list] = {}
    if table is None:
        return out
    n = len(table["id"]) if "id" in table else 0
    for col in ("location", "group_name", "label"):
        if col in table and _is_string(table[col]):
            out[col] = _texts(table[col])
    for col in ("x", "y", "z", "imp"):
        if col in table and table[col].dtype.kind in "fiu":
            out[col] = [float(v) for v in table[col][()]]
    if "group_name" not in out and "group" in table:
        out["group_name"] = [f[ref].name.rsplit("/", 1)[-1] for ref in table["group"][()]]
    out["group_name"] = out.get("group_name") or ["group"] * n
    groups = f.get("general/extracellular_ephys")
    out["group_description"] = [
        _text(groups[g].attrs.get("description", "")) if g in groups else "" for g in out["group_name"]]
    out["n"] = [n]
    return out


def channel_names(f) -> list[str]:
    """The electrode labels (the ``label`` column), else ``ch001``, ``ch002``, ... by row."""
    cols = _electrodes(f)
    n = cols.get("n", [0])[0]
    labels = cols.get("label")
    if labels and len(labels) == n and len(set(labels)) == n and all(s.strip() for s in labels):
        return [s.strip() for s in labels]
    return [f"ch{i + 1:03d}" for i in range(n)]


def group_names(f) -> dict[str, str]:
    """Original electrode group name -> the generated one (``group_001``, ... in order of first use)."""
    out: dict[str, str] = {}
    for g in _electrodes(f).get("group_name", []):
        out.setdefault(g, f"group_{len(out) + 1:03d}")
    return out


def group_types(f) -> dict[str, str]:
    """Generated group name -> the guessed channel type (seeg / ecog / dbs, from the group's name and
    description; default seeg). The plan shows it (``PlanEntry.channel_types``) and the reviewer may edit it."""
    cols = _electrodes(f)
    names = group_names(f)
    out: dict[str, str] = {}
    for name, desc in zip(cols.get("group_name", []), cols.get("group_description", [])):
        low = f"{name} {desc}".lower()
        out.setdefault(names[name], next((t for word, t in TYPE_WORDS if word in low), DEFAULT_TYPE))
    return out


def channel_types(f, types: dict[str, str] | None = None) -> list[str]:
    """seeg / ecog / dbs per electrode: ``types`` (generated group name -> type, the plan's) over the guess."""
    cols = _electrodes(f)
    names = group_names(f)
    guessed = group_types(f)
    chosen = {**guessed, **{k: v for k, v in (types or {}).items() if v in CHANNEL_TYPES}}
    return [chosen[names[g]] for g in cols.get("group_name", [])]


def safe_location(text: str) -> str:
    """The location when every word of it is an anatomical word, else ``n/a``."""
    words = re.split(r"[^a-z]+", str(text).lower())
    words = [w for w in words if w]
    return str(text).strip() if words and all(w in ANATOMY_WORDS for w in words) else NA


def _region(series) -> list[int]:
    n_ch = series["data"].shape[1] if series["data"].ndim > 1 else 1
    if "electrodes" in series:
        return [int(i) for i in series["electrodes"][()]]
    return list(range(n_ch))


def _sfreq(series) -> float:
    if "starting_time" in series:
        return float(series["starting_time"].attrs.get("rate", 0.0))
    ts = series.get("timestamps")
    if ts is not None and ts.shape[0] > 1:
        head = np.asarray(ts[: min(ts.shape[0], 10001)], dtype=float)
        step = float(np.median(np.diff(head)))
        return 1.0 / step if step > 0 else 0.0
    return 0.0


def _row_texts(table, name: str) -> list[str]:
    """The text of each row: its string cells joined with " / " (ragged columns expanded)."""
    n = len(table["id"]) if "id" in table else (table["start_time"].shape[0] if "start_time" in table else 0)
    cells: list[list[str]] = [[] for _ in range(n)]
    colnames = [_text(c) for c in table.attrs.get("colnames", [])] or sorted(table)
    for col in colnames:
        if col in INTERVAL_COLUMNS or col not in table or not hasattr(table[col], "dtype") \
                or not _is_string(table[col]):
            continue
        values = _texts(table[col])
        index = table.get(f"{col}_index")
        if index is not None:
            bounds = [int(b) for b in index[()]]
            start = 0
            for i, stop in enumerate(bounds[:n]):
                cells[i] += values[start:stop]
                start = stop
        else:
            for i, v in enumerate(values[:n]):
                cells[i].append(v)
    return [" / ".join(s.strip() for s in row if s.strip()) or name for row in cells]


def intervals(f) -> list[tuple[str, float, float, str]]:
    """(table, start, stop, row text) of every ``TimeIntervals`` row (local only: the text is raw)."""
    group = f.get("intervals")
    out: list[tuple[str, float, float, str]] = []
    if group is None:
        return out
    for name in sorted(group):
        table = group[name]
        if _ntype(table) != "TimeIntervals" or "start_time" not in table:
            continue
        starts = [float(v) for v in table["start_time"][()]]
        stops = [float(v) for v in table["stop_time"][()]] if "stop_time" in table else starts
        for s, e, text in zip(starts, stops, _row_texts(table, name)):
            out.append((name, s, e, text))
    return out


def _date(value: str):
    try:
        return datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def read_meta(path: Path):
    """``readers.RecordingInfo`` of an NWB file (pynwb, lazy: no sample is read)."""
    from collections import Counter

    import h5py
    from pynwb import NWBHDF5IO

    from .readers import SYSTEM_FAMILIES, RecordingInfo

    with NWBHDF5IO(str(path), "r", load_namespaces=False) as io:
        nwb = io.read()
        meas = nwb.session_start_time
        subject = nwb.subject
        birthday = getattr(subject, "date_of_birth", None) if subject is not None else None
        sex = SEX.get(str(getattr(subject, "sex", "") or "").strip().upper()[:1]) if subject is not None else None
    with h5py.File(path, "r") as f:
        series = _series(f)
        if not series:
            raise ValueError("no ElectricalSeries in the NWB file")
        s = series[0]
        data = s["data"]
        n_times = int(data.shape[0])
        region = _region(s)
        types = channel_types(f)
        sfreq = _sfreq(s)
        rows = intervals(f)
    ch_types = [types[i] if i < len(types) else DEFAULT_TYPE for i in region]
    return RecordingInfo(
        family="nwb", system=SYSTEM_FAMILIES["nwb"], sfreq=sfreq, n_channels=len(region), n_times=n_times,
        duration_s=n_times / sfreq if sfreq else 0.0, ch_types=dict(Counter(ch_types)),
        meas_date=meas, birthday=birthday.date() if isinstance(birthday, datetime) else birthday,
        sex=sex, annotations=[(start, stop - start, text) for _, start, stop, text in rows])


def subject_id(path: Path) -> str | None:
    import h5py

    with h5py.File(path, "r") as f:
        ds = f.get("general/subject/subject_id")
        return _text(ds[()]).strip() or None if ds is not None else None


def recording_channels(path: Path, types: dict[str, str] | None = None) -> tuple[list[str], list[str]]:
    """(names, types) of the first ElectricalSeries' channels, in data column order (``types``: the plan's
    generated group name -> type)."""
    import h5py

    with h5py.File(path, "r") as f:
        series = _series(f)
        if not series:
            return [], []
        names, types = channel_names(f), channel_types(f, types)
        region = _region(series[0])
    return ([names[i] if i < len(names) else f"ch{i + 1:03d}" for i in region],
            [types[i] if i < len(types) else DEFAULT_TYPE for i in region])


def collect(t, path: Path) -> None:
    """Fill a ``headers._Terms`` with the file's identifying text."""
    import h5py

    with h5py.File(path, "r") as f:
        general = f.get("general")
        for key in GENERAL_TEXT:
            if key in ("session_description", "identifier"):
                obj = f.get(key)
            else:
                obj = general.get(key) if general is not None else None
            if obj is None or not hasattr(obj, "dtype") or not _is_string(obj):
                continue
            values = _texts(obj)
            if key == "experimenter":
                t.name(values)
            elif key == "identifier":
                t.ident(values)
            else:
                t.text(values)
        subject = f.get("general/subject")
        if subject is not None:
            for key in subject:
                obj = subject[key]
                if not hasattr(obj, "dtype") or not _is_string(obj):
                    continue
                values = _texts(obj)
                if key == "subject_id":
                    t.ident(values)
                elif key == "date_of_birth":
                    for v in values:
                        d = _date(v)
                        if d is not None:
                            t.date(d, real=True)
                elif key in ("species", "sex"):
                    continue
                else:
                    t.text(values)
        for key in ("session_start_time", "timestamps_reference_time"):
            if key in f:
                for v in _texts(f[key]):
                    t.date(_date(v))
        ephys = f.get("general/extracellular_ephys")
        if ephys is not None:
            for name in ephys:
                if _ntype(ephys[name]) == "ElectrodeGroup":
                    t.text(_text(ephys[name].attrs.get("description", "")))
                    location = _text(ephys[name].attrs.get("location", ""))
                    if safe_location(location) == NA:
                        t.text(location)
        cols = _electrodes(f)
        for location in set(cols.get("location", [])):
            if safe_location(location) == NA:
                t.text(location)
        for name in set(cols.get("group_name", [])):
            t.label(name)  # group names are never written (generated names): harvested for redaction elsewhere
        acq = f.get("acquisition")
        for name in (acq or {}):
            t.label(name)
        group = f.get("intervals")
        for name in (group or {}):
            if name not in STANDARD_TABLES:
                t.label(name)
        devices = f.get("general/devices")
        if devices is not None:
            for name in devices:
                for k in ("description", "manufacturer"):
                    t.text(_text(devices[name].attrs.get(k, "")))
        for _, _, _, text in intervals(f):
            t.label(text)
        for s in _series(f):
            for k in ("description", "comments"):
                value = _text(s.attrs.get(k, ""))
                if value not in PYNWB_DEFAULTS:
                    t.text(value)


def harvest(path: Path) -> set[str]:
    """The identifying terms of an NWB file (local use only)."""
    from .headers import _Terms

    t = _Terms()
    collect(t, Path(path))
    return t.result()


# --- writing ------------------------------------------------------------------------------------------


def _iterator(ds, chunk_bytes: int):
    """A pynwb data iterator reading ``ds`` (an h5py dataset) a block of rows at a time."""
    from hdmf.data_utils import GenericDataChunkIterator

    class _Rows(GenericDataChunkIterator):
        def __init__(self, source) -> None:
            self._source = source
            row = int(np.prod(source.shape[1:])) * source.dtype.itemsize if source.ndim > 1 else source.dtype.itemsize
            rows = max(1, min(source.shape[0], chunk_bytes // max(1, row)))
            shape = (rows, *source.shape[1:])
            chunk = (max(1, min(rows, 2**20 // max(1, row))), *source.shape[1:])
            super().__init__(buffer_shape=shape, chunk_shape=chunk, display_progress=False)

        def _get_data(self, selection):
            return self._source[selection]

        def _get_maxshape(self):
            return self._source.shape

        def _get_dtype(self):
            return self._source.dtype

    return _Rows(ds)


def _location(text: str, terms: set[str]) -> str:
    """An anatomical location (``safe_location``) that also holds no run term, else ``n/a``."""
    loc = safe_location(text)
    return loc if loc == NA or redact(loc, terms) == loc else NA


def write(src: Path, dest: Path, subject_label: str, labels: dict[str, str], renames: dict[str, str], *,
          terms: set[str] | None = None, chunk_bytes: int = CHUNK_BYTES,
          group_types: dict[str, str] | None = None) -> dict:
    """Write a de-identified NWB file at ``dest``; returns what the BIDS sidecars need (``ieeg_sidecars``).

    ``labels``: normalised original row text -> the label written (``events.label``); ``renames``: original
    electrode label -> new name (channels.json inverted). ``group_types``: the plan's generated group name ->
    channel type (seeg / ecog / dbs), over the guess.
    """
    group_types_ = group_types
    import h5py
    from pynwb import NWBHDF5IO, NWBFile
    from pynwb.ecephys import ElectricalSeries
    from pynwb.epoch import TimeIntervals
    from pynwb.file import Subject

    terms = set(terms or ())
    src, dest = Path(src), Path(dest)
    with h5py.File(src, "r") as f:
        series = _series(f)
        if not series:
            raise ValueError("no ElectricalSeries in the NWB file")
        cols = _electrodes(f)
        names = [renames.get(n, n) for n in channel_names(f)]
        types = channel_types(f, group_types_)
        generated = group_names(f)
        rows = intervals(f)
        subj = f.get("general/subject")
        species = _text(subj["species"][()]).strip() if subj is not None and "species" in subj else None
        sex = _text(subj["sex"][()]).strip().upper()[:1] if subj is not None and "sex" in subj else None

        nwb = NWBFile(session_description=NA, identifier=str(uuid.uuid4()), session_start_time=EPOCH,
                      timestamps_reference_time=EPOCH, file_create_date=[EPOCH])
        nwb.subject = Subject(subject_id=subject_label,
                              species=redact(species, terms) if species else None,
                              sex=sex if sex in ("M", "F", "U", "O") else "U")
        device = nwb.create_device(name="amplifier", description=NA)
        n = cols.get("n", [0])[0]
        groups: dict[str, Any] = {}
        for g, loc in zip(cols["group_name"], cols.get("location", [NA] * n)):
            if g not in groups:
                groups[g] = nwb.create_electrode_group(name=generated[g], description=NA,
                                                       location=_location(loc, terms), device=device)
        nwb.add_electrode_column(name="label", description="electrode label")
        coords = {k: cols.get(k) for k in ("x", "y", "z", "imp")}
        for i in range(n):
            kw = {k: (v[i] if v else None) for k, v in coords.items() if v}
            nwb.add_electrode(group=groups[cols["group_name"][i]],
                              location=_location(cols.get("location", [NA] * n)[i], terms),
                              label=names[i], **kw)

        written_series = []
        for k, s in enumerate(series, 1):
            region = _region(s)
            data_attrs = s["data"].attrs
            kw: dict[str, Any] = dict(
                name="ElectricalSeries" if k == 1 else f"ElectricalSeries{k}",
                data=_iterator(s["data"], chunk_bytes),
                electrodes=nwb.create_electrode_table_region(region, "the recorded electrodes"),
                conversion=float(data_attrs.get("conversion", 1.0)),
                offset=float(data_attrs.get("offset", 0.0)),
                resolution=float(data_attrs.get("resolution", -1.0)),
                description=NA, comments=NA)
            if "starting_time" in s:
                kw.update(rate=float(s["starting_time"].attrs["rate"]), starting_time=float(s["starting_time"][()]))
            else:
                kw.update(timestamps=_iterator(s["timestamps"], chunk_bytes))
            if "channel_conversion" in s:
                kw["channel_conversion"] = np.asarray(s["channel_conversion"][()], dtype=float)
            nwb.add_acquisition(ElectricalSeries(**kw))
            written_series.append((kw["name"], region))

        tables: dict[str, list[tuple[float, float, str]]] = {}
        for table, start, stop, text in rows:
            tables.setdefault(table, []).append((start, stop, events.label(text, labels)))
        for k, (table, items) in enumerate(tables.items(), 1):
            name = table if table in STANDARD_TABLES else f"intervals_{k:03d}"
            ti = TimeIntervals(name=name, description=NA)
            ti.add_column(name="label", description="event label (coded)")
            for start, stop, lab in items:
                ti.add_interval(start_time=start, stop_time=stop, label=lab)
            if name == "trials":
                nwb.trials = ti
            elif name == "epochs":
                nwb.epochs = ti
            elif name == "invalid_times":
                nwb.invalid_times = ti
            else:
                nwb.add_time_intervals(ti)

        dest.parent.mkdir(parents=True, exist_ok=True)
        with NWBHDF5IO(str(dest), "w") as io:
            io.write(nwb, cache_spec=False)  # no cached schema text (library authors, examples)
        first = series[0]
        sfreq = _sfreq(first)
        n_times = int(first["data"].shape[0])
        unit = _text(first["data"].attrs.get("unit", "volts"))
    _prune(dest)
    region = written_series[0][1]
    return {
        "sfreq": sfreq, "n_times": n_times, "unit": unit,
        "channels": [(names[i], types[i] if i < len(types) else DEFAULT_TYPE) for i in region],
        "electrodes": [(names[i], *(coords[c][i] if coords[c] else None for c in ("x", "y", "z")),
                        groups[cols["group_name"][i]].name) for i in range(n)],
        "events": sorted((start, stop - start, events.label(text, labels)) for _, start, stop, text in rows),
    }


def _prune(path: Path) -> None:
    """Drop cached namespaces other than core and hdmf-common."""
    import h5py

    with h5py.File(path, "a") as f:
        spec = f.get("specifications")
        if spec is not None:
            for ns in list(spec):
                if ns not in KEPT_NAMESPACES:
                    del spec[ns]


def to_raw(path: Path, group_types: dict[str, str] | None = None):
    """The first ElectricalSeries as an ``mne.io.RawArray`` (loaded: the plan's load limit applies), for NWB
    input written as BrainVision or EDF. Channel names are the electrode labels, types from the groups,
    annotations the interval rows (raw text: ``deid.clean`` codes them), no measurement date."""
    import h5py
    import mne

    with h5py.File(path, "r") as f:
        series = _series(f)
        if not series:
            raise ValueError("no ElectricalSeries in the NWB file")
        s = series[0]
        names, types = recording_channels(path, group_types)
        sfreq = _sfreq(s)
        attrs = s["data"].attrs
        data = np.asarray(s["data"][()], dtype=float)
        if data.ndim == 1:
            data = data[:, None]
        data = data * float(attrs.get("conversion", 1.0)) + float(attrs.get("offset", 0.0))
        if "channel_conversion" in s:
            data = data * np.asarray(s["channel_conversion"][()], dtype=float)[None, :]
        rows = intervals(f)
    info = mne.create_info(names, sfreq, types, verbose=False)
    raw = mne.io.RawArray(data.T, info, verbose=False)
    if rows:
        raw.set_annotations(mne.Annotations([r[1] for r in rows], [r[2] - r[1] for r in rows],
                                            [r[3] for r in rows]), verbose="error")
    return raw


def guessed_types(path: Path) -> dict[str, str]:
    """``group_types`` of an NWB file on disk (generated group name -> guessed channel type)."""
    import h5py

    with h5py.File(path, "r") as f:
        return group_types(f)


class Series:
    """The first ElectricalSeries of an NWB file, open lazily for the QA viewer (``open_series``): channel names
    (electrode labels), seeg/ecog/dbs types, sfreq, length, and ``read`` of a sample range in volts."""

    def __init__(self, path: Path):
        import h5py

        self._f = h5py.File(path, "r")
        try:
            series = _series(self._f)
            if not series:
                raise ValueError("no ElectricalSeries in the NWB file")
            s = series[0]
            self._data = s["data"]
            names, types = channel_names(self._f), channel_types(self._f)
            region = _region(s)
            self.ch_names = [names[i] if i < len(names) else f"ch{i + 1:03d}" for i in region]
            self.ch_types = [types[i] if i < len(types) else DEFAULT_TYPE for i in region]
            self.sfreq = _sfreq(s)
            self.n_times = int(self._data.shape[0])
            attrs = self._data.attrs
            self._conversion = float(attrs.get("conversion", 1.0))
            self._offset = float(attrs.get("offset", 0.0))
            self._channel_conversion = (np.asarray(s["channel_conversion"][()], dtype=float)
                                        if "channel_conversion" in s else None)
        except Exception:
            self._f.close()
            raise

    def read(self, picks: list[int], start: int, stop: int) -> np.ndarray:
        """(len(picks), stop - start) samples in volts. Only the picked columns are read (an h5py selection of
        the sorted unique picks), never the full width."""
        picks = [int(i) for i in picks]
        if self._data.ndim == 1:
            block = np.asarray(self._data[start:stop], dtype=float)[:, None][:, picks]
        else:
            cols = sorted(set(picks))
            block = np.asarray(self._data[start:stop, cols], dtype=float)
            where = {c: k for k, c in enumerate(cols)}
            block = block[:, [where[i] for i in picks]]
        block = block * self._conversion + self._offset
        if self._channel_conversion is not None:
            block = block * self._channel_conversion[picks][None, :]
        return block.T

    def close(self) -> None:
        self._f.close()


def open_series(path: Path) -> Series:
    """The first ElectricalSeries of an NWB file, open lazily (close it when done)."""
    return Series(Path(path))
