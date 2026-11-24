"""The electrophysiology and optical module (BIDS ``eeg``, ``meg``, ``ieeg``, ``nirs``, ``emg``): claim, scan
into local records, plan entries, write (``write_entries``: de-identify in memory, MNE-BIDS, the final gate).

Local-only files in ``<work>/ephys/`` (never served, uploaded or sent to the agent):

- ``records.json``: one record per recording (input-relative paths, family, companions, head-shape files,
  ``info`` with the header summary and its local fields: meas_date, birthday, his_id, name, coded
  annotations; the record's identifying terms; its event labels after coding);
- ``terms.json``: the union of the records' terms;
- ``events.json``: ``labels`` (normalised original description -> label) and ``codes`` (code -> normalised
  original description);
- ``channels.json``: per recording (``rel``), the renamed channels as new name -> original name.

Plan entries carry only generated text and labels: subject IDs from the pseudonym key, sessions from
input labels or numbers, task and acq labels from the input's entities or known vocabulary, event codes.
"""
from __future__ import annotations

import json
import logging
import re
import uuid
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Any, Callable

from ..micr import names
from ..modality import Claim, ModulePlan
from ..plan import EMPTY_ROOM_SUBJECT, PlanEntry
from . import OUTPUT_FORMATS, channels, discover, events, headers, readers
from .discover import DATATYPES, VOCAB, Recording

if TYPE_CHECKING:
    from ..agent import LLMClient
    from ..plan import Plan
    from ..pseudonyms import PseudonymKey
    from ..schema import Schema
    from ..scrub import ScrubbedSeries

log = logging.getLogger(__name__)

NAME = "ephys"
RECORDS_FILE = "records.json"
TERMS_FILE = "terms.json"
EVENTS_FILE = "events.json"
CHANNELS_FILE = "channels.json"
# ephys subject_idx/series_idx start here, so they never collide with ezBIDS's (or microscopy's, 1_000_000)
EPHYS_INDEX_BASE = 2_000_000
PROGRESS = "reading recording headers ({k} of {n})"
UNREADABLE_REASON = "could not be read as an electrophysiology recording"
HEADSHAPE_WARNING = "head-shape points found and dropped by default (keep_headshape to keep)"
LOAD_WARNING = "converting {name} loads about {n:.1f} GB into memory"
NO_IDENTITY = ("electrophysiology: subject identity could not be established for {n} subject(s): they get new "
               "subject IDs for this import only, not linked to earlier imports")
MRI_PREFIX = "mri:"  # an original that stands for an MRI subject of this import (never put in the key)
EMPTY_ROOM_TASK = "noise"
UNKNOWN_TASK = "unknown"
TASK_WORDS = ("rest", "sleep", "oddball", "mmn", "motor", "tapping", "auditory", "visual", "faces", "nback")
MEG_FAMILIES = frozenset({"fif", "ctf", "bti", "kit"})
NIRS_FAMILIES = frozenset({"nirx", "hitachi", "snirf"})
MEG_TYPES = frozenset({"mag", "grad", "ref_meg"})
IEEG_TYPES = frozenset({"seeg", "ecog", "dbs"})
DATA_TYPES = frozenset({"eeg", "emg"}) | IEEG_TYPES
# EDF/BDF signal label prefix ("SEEG LA1") -> channel type; MNE reads every EDF channel as eeg
EDF_LABEL_TYPES = {"EEG": "eeg", "SEEG": "seeg", "ECOG": "ecog", "DBS": "dbs", "EMG": "emg", "ECG": "ecg",
                   "EKG": "ecg", "EOG": "eog", "RESP": "resp", "STIM": "stim", "MISC": "misc"}
EDF_PLACEHOLDERS = frozenset({"x", "0"})
_TOKEN = re.compile(r"[^a-z0-9]+")
EXT_WORDS = frozenset({"edf", "bdf", "gdf", "vhdr", "vmrk", "fdt", "fif", "snirf", "nwb", "sqd", "con", "cnt", "lay",
                       "hdr", "wl1", "wl2", "evt", "tri", "ds", "mff", "mefd", "nev", "ns1", "ns2", "ns3", "ns4",
                       "ns5", "ns6", "set", "pos", "hsp", "mrk", "elp"})
_CODE = re.compile(rf"^{events.CODE_PREFIX}\d{{3}}$")


# --- scan: records ----------------------------------------------------------------------------


def label_types(ch_names: list[str], ch_types: list[str]) -> list[str]:
    """EDF/BDF channel types from the signal label prefix (``SEEG LA1`` -> seeg); others unchanged."""
    out = []
    for name, t in zip(ch_names, ch_types):
        prefix = str(name).strip().split(" ", 1)
        out.append(EDF_LABEL_TYPES.get(prefix[0].upper(), t) if len(prefix) == 2 else t)
    return out


def _path_terms(rec: Recording) -> set[str]:
    return names.path_terms([rec.rel, *rec.companions, *rec.headshape], vocab=headers.HARVEST_VOCAB)


def _subject_fields(raw) -> dict:
    """his_id and last^first from the header (local only)."""
    subject = raw.info.get("subject_info") or {}
    out: dict[str, Any] = {}
    his = subject.get("his_id")
    if isinstance(his, str) and his.strip():
        out["his_id"] = his.strip()
    last, first = (str(subject.get(k) or "").strip() for k in ("last_name", "first_name"))
    if last or first:
        out["name"] = f"{last}^{first}"
    return out


def _iso(value) -> str | None:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return None


def _read(rec: Recording, input_dir: Path) -> tuple[dict | None, set[str], str | None, list[str], list[str],
                                                    list[tuple[float, float, str]]]:
    """(info, terms, error, ch_names, ch_types, annotations) of one recording; headers only.

    A reader's ``Unsupported`` reason is safe to show; any other reader or harvest failure gives a generic
    reason (no path, no exception text), so a recording is never planned from a partial harvest.
    """
    if rec.excluded:
        try:
            terms = headers.harvest(rec, input_dir, None)
        except Exception:  # noqa: BLE001 - its terms still come from its paths
            terms = _path_terms(rec)
        return None, terms, rec.excluded, [], [], []
    if rec.family == "nwb":
        from . import nwb

        try:
            info = nwb.read_meta(input_dir / rec.rel)
            terms = headers.harvest(rec, input_dir, None)
            ch_names, ch_types = nwb.recording_channels(input_dir / rec.rel)
            his = nwb.subject_id(input_dir / rec.rel)
            group_types = nwb.guessed_types(input_dir / rec.rel)
        except Exception as exc:  # noqa: BLE001 - one unreadable recording must not stop the scan
            log.warning("NWB recording could not be read: %s", type(exc).__name__)
            return None, _path_terms(rec), UNREADABLE_REASON, [], [], []
        view = info.view()
        view.update(meas_date=_iso(info.meas_date), birthday=_iso(info.birthday), group_types=group_types,
                    **({"his_id": his} if his else {}))
        return view, terms, None, ch_names, ch_types, list(info.annotations)
    try:
        raw = readers.open_raw(rec, input_dir)
        info = readers.info_from_raw(rec, raw)
        terms = headers.harvest(rec, input_dir, raw)
        ch_names = [str(n) for n in raw.ch_names]
        ch_types = list(raw.get_channel_types())
        local = _subject_fields(raw)
    except readers.Unsupported as exc:
        return None, _path_terms(rec), exc.reason, [], [], []
    except Exception as exc:  # noqa: BLE001 - one unreadable recording must not stop the scan
        log.warning("recording could not be read: %s", type(exc).__name__)
        return None, _path_terms(rec), UNREADABLE_REASON, [], [], []
    if rec.family in ("edf", "bdf"):
        ch_types = label_types(ch_names, ch_types)
        info.ch_types = dict(Counter(ch_types))
    view = info.view()
    view.update(meas_date=_iso(info.meas_date), birthday=_iso(info.birthday), **local)
    return view, terms, None, ch_names, ch_types, list(info.annotations)


def _clean_meta(meta: dict, terms: set[str]) -> dict:
    """Recording.meta with every text value passed through scrub.redact: a task/acq/run label that
    redaction would change is dropped, EEGReference is redacted."""
    from ..scrub import redact

    out: dict[str, Any] = {}
    for k, v in (meta or {}).items():
        if isinstance(v, str):
            red = redact(v, terms)
            if k in ("task", "acq", "run"):
                if red == v:
                    out[k] = v
            else:
                out[k] = red
        else:
            out[k] = v
    return out


def scan_records(input_dir: Path, recordings: list[Recording], work: Path,
                 progress: Callable[[str], None]) -> list[dict]:
    """Read every recording's header, code the event labels across the dataset, rename identifying
    channels, and write records.json, terms.json, events.json and channels.json (all local-only)."""
    input_dir, work = Path(input_dir), Path(work)
    recordings = sorted(recordings, key=lambda r: r.rel)
    records: list[dict] = []
    channel_lists: list[tuple[list[str], list[str]]] = []
    annotations: list[list[tuple[float, float, str]]] = []
    for k, rec in enumerate(recordings, 1):
        progress(PROGRESS.format(k=k, n=len(recordings)))
        info, terms, error, ch_names, ch_types, ann = _read(rec, input_dir)
        records.append({"rel": rec.rel, "family": rec.family, "companions": list(rec.companions),
                        "headshape": list(rec.headshape), "empty_room": rec.empty_room, "meta": dict(rec.meta),
                        "info": info, "error": error, "terms": sorted(terms), "event_labels": []})
        channel_lists.append((ch_names, ch_types))
        annotations.append(sorted(ann, key=lambda a: a[0]))
    all_terms: set[str] = set()
    for r in records:
        all_terms |= set(r["terms"])
    mapping, codes = events.code([[a[2] for a in ann] for ann in annotations], all_terms)
    originals = {label: key for key, label in mapping.items() if _CODE.fullmatch(label)}
    renamed: dict[str, dict[str, str]] = {}
    for r, ann, (ch_names, ch_types) in zip(records, annotations, channel_lists):
        labels = [events.label(a[2], mapping) for a in ann]
        r["event_labels"] = labels
        if r["info"] is not None:
            r["info"]["annotations"] = [[a[0], a[1], lab] for a, lab in zip(ann, labels)]
        r["meta"] = _clean_meta(r["meta"], all_terms)
        old_new = channels.rename(ch_names, ch_types, all_terms) if ch_names else {}
        if old_new:
            renamed[r["rel"]] = {new: old for old, new in old_new.items()}
    work.mkdir(parents=True, exist_ok=True)
    (work / RECORDS_FILE).write_text(json.dumps(records, indent=1))
    (work / TERMS_FILE).write_text(json.dumps(sorted(all_terms), indent=1))
    (work / EVENTS_FILE).write_text(json.dumps({"labels": mapping, "codes": {c: originals[c] for c in codes}},
                                               indent=1))
    (work / CHANNELS_FILE).write_text(json.dumps(renamed, indent=1))
    return records


def load_records(work: Path) -> list[dict]:
    path = Path(work) / RECORDS_FILE
    if not path.is_file():
        return []
    return list(json.loads(path.read_text()))


def load_codes(work: Path) -> list[str]:
    path = Path(work) / EVENTS_FILE
    if not path.is_file():
        return []
    return [c for c in json.loads(path.read_text()).get("codes", {}) if _CODE.fullmatch(c)]


# --- plan ---------------------------------------------------------------------------------------


def _bids_datatype(rel: str) -> str | None:
    parts = rel.split("/")
    for k in range(1, len(parts) - 1):
        if parts[k] in DATATYPES and discover._is_bids_datatype_dir("/".join(parts[:k + 1])):
            return parts[k]
    return None


def datatype_of(rec: dict) -> tuple[str | None, str]:
    """(datatype, why) by the heuristic: a BIDS datatype folder wins; then the system family (MEG, NIRS,
    NWB); then the channel types (iEEG or EMG when at least half of the data channels, else EEG)."""
    bids = _bids_datatype(rec["rel"])
    if bids:
        return bids, "BIDS datatype folder"
    fam = rec["family"]
    types: dict[str, int] = (rec.get("info") or {}).get("ch_types") or {}
    if fam in MEG_FAMILIES and (not types or MEG_TYPES & set(types)):
        return "meg", "MEG system"
    if fam in NIRS_FAMILIES:
        return "nirs", "NIRS system"
    if fam == "nwb":
        return "ieeg", "NWB electrophysiology"
    if rec.get("info") is None:
        return None, ""
    data = sum(n for t, n in types.items() if t in DATA_TYPES)
    if data:
        if sum(n for t, n in types.items() if t in IEEG_TYPES) * 2 >= data:
            return "ieeg", "intracranial channel types"
        if types.get("emg", 0) * 2 >= data:
            return "emg", "EMG channel types"
    return "eeg", "EEG channel types"


def _hint_tokens(rel: str) -> list[str]:
    """The generic words of a path that are in the electrophysiology vocabulary (never other text)."""
    vocab = frozenset(discover.EPHYS_VOCAB)
    return sorted({t for t in _TOKEN.split(rel.lower()) if t in vocab and t not in EXT_WORDS})


def ephys_view(records: list[dict]) -> list["ScrubbedSeries"]:
    """The agent's view of each readable record: recording facts, coded event counts and generic layout
    words only.

    Never a path, a name, a date, a channel name or annotation text. ``Hints`` are tokens of
    ``discover.EPHYS_VOCAB`` (); the event labels are codes (E001) or
    safe labels; the rest are numbers and enums.
    """
    from ..scrub import ScrubbedSeries

    out = []
    for i, rec in enumerate(records):
        info = rec.get("info")
        if info is None or rec.get("error"):
            continue
        datatype, _ = datatype_of(rec)
        # a safe label such as "Stimulus/S  1" is sent as "Stimulus S 1": no slash, one space between words
        counts = Counter(" ".join(lab.replace("/", " ").split()) for lab in rec.get("event_labels") or []
                         if _CODE.fullmatch(lab) or events.is_safe(lab))
        fields = {
            "FormatFamily": rec["family"],
            "SystemFamily": readers.SYSTEM_FAMILIES.get(rec["family"], "electrophysiology").replace("/", " "),
            "SamplingFrequency": info.get("sfreq"),
            "ChannelCount": info.get("n_channels"),
            "ChannelTypes": dict(sorted((info.get("ch_types") or {}).items())),
            "DurationSeconds": round(float(info.get("duration_s") or 0)),
            "EventCounts": dict(sorted(counts.items())),
            "LineFrequency": info.get("line_freq"),
            "HasDigitization": bool(info.get("has_dig")),
            "Wavelengths": list(info.get("wavelengths") or []),
            "Hints": _hint_tokens(rec["rel"]),
        }
        out.append(ScrubbedSeries(EPHYS_INDEX_BASE + i, "", "", f"{datatype or 'unknown'}/{datatype or 'unknown'}",
                                  fields))
    return out


def _apply_agent(mp: ModulePlan, records: list[dict], kinds: list[tuple[str | None, str]], formats: list[str],
                 entities: list[dict[str, str]], client: "LLMClient | None", schema: "Schema",
                 terms: set[str]) -> dict[int, dict]:
    """Ask the agent about the readable recordings and apply the planner's agreement rules.

    Returns ``{record index: {"confidence", "note"}}``; a task the heuristic left unknown, and acq, are
    filled into ``entities`` in place (the task only from the record's own Hints).
    """
    from ..agent import EPHYS_CLASSIFY_SYSTEM, EPHYS_GENERATED, classify
    from ..planner import AGENT_MIN, AGREE_MIN, DISAGREE_CONFIDENCE, _agent_text, _guess_text, _usable

    out: dict[int, dict] = {}
    if client is None:
        return out
    view = ephys_view(records)
    mp.view = view
    ok = {EPHYS_INDEX_BASE + i for i in range(len(records)) if formats[i] and kinds[i][0]}
    heuristic = {s.series_idx: (kinds[s.series_idx - EPHYS_INDEX_BASE][0], kinds[s.series_idx - EPHYS_INDEX_BASE][0],
                                dict(entities[s.series_idx - EPHYS_INDEX_BASE]))
                 for s in view if s.series_idx in ok}
    for g in classify(view, heuristic, client, schema, EPHYS_CLASSIFY_SYSTEM, DATATYPES, EPHYS_GENERATED):
        if g.series_idx not in ok or g.datatype is None:
            continue
        i = g.series_idx - EPHYS_INDEX_BASE
        hints = set(next(s for s in view if s.series_idx == g.series_idx).fields["Hints"])
        task, acq = g.entities.get("task"), g.entities.get("acquisition")
        if g.datatype == kinds[i][0]:
            out[i] = {"confidence": max(AGREE_MIN, g.confidence), "note": ""}
            if entities[i].get("task") == UNKNOWN_TASK and task and task == task.lower() and task in hints \
                    and _usable(task, terms):
                entities[i]["task"] = task
            if acq and "acquisition" not in entities[i] and _usable(acq, terms):
                entities[i]["acquisition"] = acq
        elif g.confidence >= AGENT_MIN:
            out[i] = {"confidence": DISAGREE_CONFIDENCE, "note": _agent_text(_guess_text(g), terms)}
    return out


def _placeholder(field_name: str, value) -> bool:
    from ..planner import is_placeholder

    return str(value or "").strip().casefold() in EDF_PLACEHOLDERS or is_placeholder(field_name, value)


def _input_label(rel: str, prefix: str) -> str | None:
    """The label of a ``<prefix>-<label>`` folder (sub, ses), else None."""
    for part in rel.split("/")[:-1]:
        if part.startswith(prefix + "-") and len(part) > len(prefix) + 1:
            return part[len(prefix) + 1:]
    return None


def _entity(rel: str, key: str) -> str | None:
    """A ``<key>-<label>`` entity in the path (file or folder name)."""
    m = re.search(rf"(?:^|[_/]){re.escape(key)}-([A-Za-z0-9]+)(?=[_./]|$)", rel)
    return m.group(1) if m else None


def _task_word(rel: str) -> str | None:
    for part in rel.split("/"):
        for tok in _TOKEN.split(part.lower()):
            if tok in TASK_WORDS:
                return tok
    return None


def _meas_date(rec: dict) -> datetime | None:
    text = (rec.get("info") or {}).get("meas_date")
    try:
        return datetime.fromisoformat(text) if text else None
    except ValueError:
        return None


def _type_text(types: dict[str, int]) -> str:
    return ", ".join(f"{t} {n}" for t, n in sorted(types.items(), key=lambda kv: (-kv[1], kv[0])))


def describe(rec: dict, fmt: str) -> str:
    """Generated text only: source system, output format, channels, rate, duration, event codes."""
    system = readers.SYSTEM_FAMILIES.get(rec["family"], "electrophysiology")
    info = rec.get("info")
    if info is None or not fmt:
        return f"{system} recording; not converted"
    n_codes = len(set(rec.get("event_labels") or []))
    return (f"{system} → {fmt}, {info['n_channels']} ch ({_type_text(info.get('ch_types') or {})}), "
            f"{info['sfreq']:g} Hz, {info['duration_s']:.0f} s, {n_codes} event code{'' if n_codes == 1 else 's'}")


def _default_format(datatype: str | None, family: str) -> str:
    """The datatype's first format; BDF for EMG from BDF; NWB for NWB iEEG (NWB is offered for NWB input only)."""
    formats = OUTPUT_FORMATS.get(datatype or "", ())
    if family == "nwb" and "NWB" in formats:
        return "NWB"
    if datatype == "emg" and family == "bdf" and "BDF" in formats:
        return "BDF"
    return next((f for f in formats if f != "NWB"), "")


def _load_bytes(info: dict) -> int:
    return int(info.get("n_channels") or 0) * int(info.get("n_times") or 0) * 8


def _identity(rec: dict) -> str | None:
    """The key original from a recording's header: its ID, else its name (placeholders skipped)."""
    info = rec.get("info") or {}
    his, name = info.get("his_id"), info.get("name")
    if his and not _placeholder("PatientID", his):
        return "ephys:id=" + his
    if name and not _placeholder("PatientName", name):
        return "ephys:name=" + name
    return None


def plan_entries(records: list[dict], key: "PseudonymKey", existing: set[str], schema: "Schema",
                 target: str, codes: list[str] | None = None,
                 mri_subjects: dict[str, dict] | None = None,
                 client: "LLMClient | None" = None) -> ModulePlan:
    """The ephys plan. mri_subjects: the MRI path's subjects by their input sub- folder label,
    ``{label: {"idx", "id", "sessions": {ses folder label: (session_idx, session)}, "only": (session_idx,
    session) | None}}``; recordings in that folder join that subject."""
    from ..brainlife_map import no_datatype_reason, to_brainlife
    from ..planner import EPHYS_BRAINLIFE_EXTS, _check_nameable, _usable

    terms: set[str] = set()
    for rec in records:
        terms |= set(rec.get("terms") or [])
    run = uuid.uuid4().hex
    mp = ModulePlan(event_names={c: c for c in codes or []})

    kinds = [datatype_of(rec) for rec in records]
    empty = [bool(rec.get("empty_room")) and dt == "meg" for rec, (dt, _) in zip(records, kinds)]

    # subjects: recordings in one sub-<label> folder are one person. A label the MRI path used maps to
    # that MRI subject (same folder, same person); else the header's ID (or name) of any recording in the
    # folder, else a run-local subject. Outside sub- folders: the header's ID, else its name, else a donor
    # token, else run-local.
    mri_subjects = mri_subjects or {}
    labels = [None if empty[i] else _input_label(rec["rel"], "sub") for i, rec in enumerate(records)]
    folder_identity: dict[str, str] = {}
    for rec, label in zip(records, labels):
        if label and label not in mri_subjects:
            ident = _identity(rec)
            if ident:
                folder_identity.setdefault(label, ident)
    originals: list[str | None] = []
    proposed: dict[str, str | None] = {}
    sub_labels: dict[str, set[str]] = defaultdict(set)
    local = f"run:{run}:"
    for i, rec in enumerate(records):
        label = labels[i]
        if empty[i]:
            originals.append(None)
            continue
        if label in mri_subjects:
            originals.append(MRI_PREFIX + label)
            continue
        if label:
            original = folder_identity.get(label) or f"{local}sub-{label}"
        else:
            original = _identity(rec)
            if original is None:
                donor = names.facts(rec["rel"], vocab=VOCAB).donor
                original = "ephys:id=" + donor if donor else f"{local}ephys{i}"
        usable = label if label and label != EMPTY_ROOM_SUBJECT and (
            _usable(label, terms) or (label.isdigit() and _usable(label, terms - {label}))) else None
        originals.append(original)
        proposed.setdefault(original, usable)
        if label:
            sub_labels[original].add(label)
    order = list(dict.fromkeys(o for o in originals if o is not None))
    subject_idx: dict[str, int] = {}
    subject_ids: dict[str, str] = {}
    n_new = 0
    for o in order:
        if o.startswith(MRI_PREFIX):
            mri = mri_subjects[o[len(MRI_PREFIX):]]
            subject_idx[o], subject_ids[o] = mri["idx"], mri["id"]
            continue
        subject_idx[o] = EPHYS_INDEX_BASE + n_new
        n_new += 1
        subject_ids[o] = key.subject_id(o, existing, proposed.get(o))
        if len(sub_labels[o]) == 1:
            mp.labels[subject_idx[o]] = next(iter(sub_labels[o]))
    empty_idx = EPHYS_INDEX_BASE + n_new
    n_local = sum(1 for o in order if o.startswith(local))
    if n_local:
        mp.warnings.append(NO_IDENTITY.format(n=n_local))

    # sessions: the input's ses- labels (an MRI subject's own sessions when the folder is the same; a lone MRI
    # session takes the session-less recordings); else numbered by recording day when a subject has several
    # days. A ses- label that is not usable (identifying, or a date such as MNE-BIDS's ses-YYYYMMDD) counts
    # as no label.
    sessions: list[str | None] = [None] * len(records)
    fixed: dict[int, int] = {}  # record -> the MRI session_idx it joins
    days: dict[str, set[date]] = defaultdict(set)
    taken: dict[str, set[str]] = defaultdict(set)
    for i, rec in enumerate(records):
        o = originals[i]
        raw = _input_label(rec["rel"], "ses")
        mri = mri_subjects.get(o[len(MRI_PREFIX):]) if o and o.startswith(MRI_PREFIX) else None
        if mri is not None:
            taken[o] |= {lab for _, lab in mri["sessions"].values() if lab}
            if raw is not None and raw in mri["sessions"]:
                fixed[i], sessions[i] = mri["sessions"][raw]
                continue
            if raw is None and mri.get("only") is not None:
                fixed[i], sessions[i] = mri["only"]
                continue
        if raw is not None and _usable(raw, terms):
            sessions[i] = raw
            if o is not None:
                taken[o].add(raw)
        elif o is not None:
            when = _meas_date(rec)
            if when is not None:
                days[o].add(when.date())
    numbers: dict[tuple[str, date | None], str] = {}
    for i, rec in enumerate(records):
        o = originals[i]
        if sessions[i] is not None or i in fixed or o is None or len(days[o]) < 2:
            continue
        when = _meas_date(rec)
        day = when.date() if when is not None else None
        if (o, day) not in numbers:
            for d in sorted(days[o]) + [None]:
                if (o, d) in numbers:
                    continue
                n = len([k for k in numbers if k[0] == o]) + 1
                while f"{n:02d}" in taken[o]:
                    n += 1
                numbers[(o, d)] = f"{n:02d}"
                taken[o].add(numbers[(o, d)])
        sessions[i] = numbers[(o, day)]
    session_idx: list[int] = []
    seen: dict[Any, dict[str | None, int]] = defaultdict(dict)
    for i in range(len(records)):
        o = originals[i]
        if i in fixed:
            session_idx.append(fixed[i])
            continue
        per = seen[o if o is not None else EMPTY_ROOM_SUBJECT]
        # beside an MRI subject's sessions, ephys sessions are numbered apart from them
        base = EPHYS_INDEX_BASE if o is not None and o.startswith(MRI_PREFIX) else 0
        session_idx.append(base + per.setdefault(sessions[i], len(per)))

    # entities: task (input entity, else a task word, else unknown), acq
    entities: list[dict[str, str]] = []
    for i, rec in enumerate(records):
        meta = rec.get("meta") or {}
        if empty[i]:
            ents = {"task": EMPTY_ROOM_TASK}
        else:
            task = meta.get("task") or _entity(rec["rel"], "task")
            if not (task and _usable(task, terms)):
                task = _task_word(rec["rel"]) or UNKNOWN_TASK
            ents = {"task": task}
        acq = meta.get("acq") or _entity(rec["rel"], "acq")
        if acq and _usable(acq, terms):
            ents["acquisition"] = acq  # the schema's entity name, as MRI and micr entries use
        entities.append(ents)

    formats = [_default_format(dt, rec["family"]) if rec.get("info") is not None and not rec.get("error") else ""
               for rec, (dt, _) in zip(records, kinds)]
    agent = _apply_agent(mp, records, kinds, formats, entities, client, schema, terms)

    # runs: recordings sharing (subject, session, task, acq) in one datatype (so one BIDS name) keep the
    # input's run labels when every one has a usable, distinct one; else, when there are several, they are
    # numbered by meas_date
    groups: dict[tuple, list[int]] = defaultdict(list)
    for i in range(len(records)):
        if formats[i]:
            groups[(originals[i], sessions[i], entities[i]["task"], entities[i].get("acquisition"), kinds[i][0])].append(i)
    for idxs in groups.values():
        given = [(records[i].get("meta") or {}).get("run") or _entity(records[i]["rel"], "run") for i in idxs]
        if all(r and _usable(r, terms) for r in given) and len(set(given)) == len(given):
            for i, r in zip(idxs, given):
                entities[i]["run"] = r
            continue
        if len(idxs) < 2:
            continue
        idxs.sort(key=lambda i: (_meas_date(records[i]) is None, _meas_date(records[i]) or datetime.min,
                                 records[i]["rel"]))
        for n, i in enumerate(idxs, 1):
            entities[i]["run"] = str(n)

    entries: list[PlanEntry] = []
    headshape = False
    for i, rec in enumerate(records):
        datatype, why = kinds[i]
        fmt = formats[i]
        o = originals[i]
        sidx = subject_idx[o] if o is not None else empty_idx
        subject = subject_ids[o] if o is not None else EMPTY_ROOM_SUBJECT
        info = rec.get("info") or {}
        if not fmt:
            d = dict(status="unsupported", exclude=True, reason=rec.get("error") or UNREADABLE_REASON)
        else:
            d = dict(datatype=datatype, suffix=datatype, entities=entities[i], status="ok", exclude=False,
                     reason=f"electrophysiology heuristic: {why}")
            _check_nameable(d, subject, session=sessions[i], schema=schema, modality="ephys", ephys_format=fmt)
            need = _load_bytes(info)
            if need > readers.WARN_LOAD_BYTES:
                bids_name = _bids_name(schema, subject, sessions[i], datatype, entities[i], fmt)
                text = LOAD_WARNING.format(name=bids_name, n=need / 2**30)
                if need > readers.max_load_bytes():
                    d.update(status="unsupported", exclude=True, reason=text)
                    fmt = ""
                else:
                    mp.warnings.append(text)
        bl_datatype, bl_tags = None, []
        if d["status"] == "ok":
            bl_datatype, bl_tags = to_brainlife(datatype, datatype, entities[i], {}, EPHYS_BRAINLIFE_EXTS.get(fmt))
            if target == "datatypes" and bl_datatype is None:
                d["exclude"], d["reason"] = True, d["reason"] + no_datatype_reason(datatype, datatype)
        if d["status"] == "ok" and not d["exclude"] and datatype in ("meg", "eeg") and (
                info.get("n_headshape_points") or rec.get("headshape")):
            headshape = True  # only for recordings that will be written
        entries.append(PlanEntry(
            id=f"e{i}-sub{sidx}-ses{session_idx[i]}", series_idx=EPHYS_INDEX_BASE + i, subject_idx=sidx,
            session_idx=session_idx[i], subject=subject, session=sessions[i], datatype=datatype, suffix=datatype,
            entities=entities[i] if datatype else {}, brainlife_datatype=bl_datatype, brainlife_tags=bl_tags,
            source="heuristic" if datatype else "none", confidence=0.8 if d["status"] == "ok" else 0.0,
            reason=d["reason"], deface=False, exclude=d["exclude"], status=d["status"],
            description=describe(rec, fmt), modality="ephys", ephys_format=fmt,
            event_counts=dict(Counter(rec.get("event_labels") or [])),
            channel_types=dict(info.get("group_types") or {}) if d["status"] == "ok" else {},
        ))
        if i in agent and d["status"] == "ok":
            entries[-1].confidence = agent[i]["confidence"]
            entries[-1].agent_note = agent[i]["note"]
    _pair_empty_room(entries, records, empty)
    if headshape:
        mp.warnings.append(HEADSHAPE_WARNING)
    mp.entries = entries
    return mp


def _bids_name(schema: "Schema", subject: str, session: str | None, datatype: str, entities: dict, fmt: str) -> str:
    from ..schema import CHECK_EXTS

    try:
        return PurePosixPath(schema.filename(subject, session, datatype, datatype, entities,
                                             CHECK_EXTS.get(fmt, ""))).name
    except ValueError:
        return f"a {datatype} recording of sub-{subject}"


def _pair_empty_room(entries: list[PlanEntry], records: list[dict], empty: list[bool]) -> None:
    """Each MEG entry gets the empty-room recording nearest in time on the same day, before or after
    (ezBIDS convert_meg.py), compared on the local meas_dates only."""
    rooms = [(i, _meas_date(records[i])) for i in range(len(records)) if empty[i] and entries[i].ephys_format]
    rooms = [(i, when) for i, when in rooms if when is not None]
    for i, e in enumerate(entries):
        if empty[i] or e.datatype != "meg" or not e.ephys_format:
            continue
        when = _meas_date(records[i])
        if when is None:
            continue
        same_day = [(abs((w - when).total_seconds()), j) for j, w in rooms if w.date() == when.date()]
        if same_day:
            e.empty_room = entries[min(same_day)[1]].id


# --- the module ---------------------------------------------------------------------------------


class EphysModule:
    """BIDS ``eeg``, ``meg``, ``ieeg``, ``nirs`` and ``emg`` from local recordings (remote sources are not
    supported for electrophysiology)."""

    name = NAME

    def __init__(self) -> None:
        self._found: tuple[list[str], list[Recording]] | None = None

    def claim(self, input_dir: Path, remote: list[str]) -> Claim:
        c, found = discover.claim(Path(input_dir), [])
        self._found = (list(c.roots), found)
        return c

    def scan(self, input_dir: Path, claim: Claim, work: Path, progress: Callable[[str], None]) -> None:
        if self._found is not None and self._found[0] == list(claim.roots):
            found = self._found[1]
        else:  # claim.json keeps only the roots: discover again, keeping what lies under them
            _, found = discover.claim(Path(input_dir), [])
            roots = set(claim.roots)
            found = [r for r in found if any(r.rel == x or r.rel.startswith(x + "/") for x in roots)]
        scan_records(Path(input_dir), found, Path(work), progress)

    def terms(self, work: Path) -> set[str]:
        terms: set[str] = set()
        for rec in load_records(work):
            terms |= set(rec.get("terms") or [])
        return terms

    def plan(self, work: Path, key: "PseudonymKey", existing: set[str], client: "LLMClient | None",
             schema: "Schema", target: str, subjects: dict[str, dict] | None = None) -> ModulePlan:
        """subjects: the MRI subjects by input sub- folder label (planner.build_plan passes them)."""
        return plan_entries(load_records(work), key, existing, schema, target, load_codes(work), subjects, client)

    def write(self, plan: "Plan", work: Path, input_dir: Path, terms: set[str], key: "PseudonymKey",
              schema: "Schema", dest: Callable[[str], Path], progress: Callable[[str], None] | None = None):
        return write_entries(plan, Path(work), Path(input_dir), terms, key, schema, dest, progress)


# --- write --------------------------------------------------------------------------------------

WRITE_PROGRESS = "writing electrophysiology recording {k} of {n}"
SCRATCH = "scratch"
WRITTEN_DATATYPES = ("eeg", "ieeg", "emg", "meg", "nirs")
NO_FORMAT = "an included electrophysiology entry has no output format: plan again"
SEX_CODES = {1: "M", 2: "F"}
SEX_SOURCE = "the recording header"
SCANS_FORMAT = "%Y-%m-%dT%H:%M:%S"


def _date_of(text) -> datetime | None:
    try:
        return datetime.fromisoformat(text) if text else None
    except (TypeError, ValueError):
        return None


def _birthday(rec: dict) -> date | None:
    text = (rec.get("info") or {}).get("birthday")
    try:
        return date.fromisoformat(str(text)[:10]) if text else None
    except ValueError:
        return None


def _age(birthday: date | None, when: datetime | None) -> str:
    """Whole years at ``when`` from the local birthday; 89 or more -> 89 (as writer._parse_age); else n/a."""
    from ..writer import AGE_CAP, NA

    if birthday is None or when is None:
        return NA
    day = when.date()
    years = day.year - birthday.year - ((day.month, day.day) < (birthday.month, birthday.day))
    if years < 0:
        return NA
    return str(min(years, AGE_CAP))


def _source_files(rec: dict, input_dir: Path) -> list[Path]:
    """Every claimed file of a recording (folders such as a CTF .ds expanded): no output may equal one."""
    out: list[Path] = []
    for rel in [rec["rel"], *(rec.get("companions") or []), *(rec.get("headshape") or [])]:
        p = input_dir / rel
        if p.is_dir():
            out += [q for q in p.rglob("*") if q.is_file()]
        elif p.is_file():
            out.append(p)
    return out


def _recording(rec: dict) -> Recording:
    return Recording(rel=rec["rel"], family=rec["family"], companions=list(rec.get("companions") or []),
                     headshape=list(rec.get("headshape") or []), empty_room=bool(rec.get("empty_room")))


def _snirf_units(rec: dict, input_dir: Path) -> dict[str, str] | None:
    """The source SNIRF's units (a SNIRF file, or the SNIRF of a NIRSport2 folder); None for other inputs."""
    from . import snirf

    files = [rec["rel"]] if rec["family"] == "snirf" else [c for c in rec.get("companions") or []
                                                            if c.lower().endswith(".snirf")]
    return snirf.source_units(input_dir / files[0]) if files else None


def _open_clean(e: PlanEntry, rec: dict, input_dir: Path, renames: dict[str, str], labels: dict[str, str],
                event_names: dict[str, str]):
    """The recording opened lazily (NWB input written as another format: loaded through ``nwb.to_raw``),
    channel types as planned, de-identified in memory (deid.clean)."""
    from . import deid

    if rec["family"] == "nwb":
        from . import nwb

        raw = nwb.to_raw(input_dir / rec["rel"], e.channel_types)
    else:
        raw = readers.open_raw(_recording(rec), input_dir, headshape=e.keep_headshape)
    if rec["family"] in ("edf", "bdf"):  # MNE reads every EDF channel as eeg: the planned types by label prefix
        names_, types = list(raw.ch_names), list(raw.get_channel_types())
        changed = {n: t for n, t, old in zip(names_, label_types(names_, types), types) if t != old}
        if changed:
            raw.set_channel_types(changed, on_unit_change="ignore", verbose="error")
    deid.clean(raw, renames=renames, labels=labels, event_names=event_names, keep_headshape=e.keep_headshape)
    line = (rec.get("meta") or {}).get("PowerLineFrequency")
    if raw.info.get("line_freq") is None and isinstance(line, (int, float)) and not isinstance(line, bool):
        with raw.info._unlock():
            raw.info["line_freq"] = float(line)
    return raw


def write_entries(plan: "Plan", work: Path, input_dir: Path, terms: set[str], key: "PseudonymKey",
                  schema: "Schema", dest: Callable[[str], Path],
                  progress: Callable[[str], None] | None = None):
    """Write every included ephys entry (empty rooms first), run the final gate on what was written, and
    return the participants and scans rows. ``work/ephys/scratch`` is removed in every case."""
    import shutil

    from ..modality import ModuleOutput
    from ..scrub import redact
    from . import gate
    from .write import daysback, write_nirs, write_nwb, write_recording

    entries = [e for e in plan.entries if e.modality == "ephys" and e.status == "ok" and not e.exclude
               and e.datatype]
    out = ModuleOutput(scans_with_time=True, sex_source=SEX_SOURCE)
    if not entries:
        return ModuleOutput()
    if any(not e.ephys_format for e in entries):
        raise ValueError(NO_FORMAT)
    if any(e.datatype not in WRITTEN_DATATYPES for e in entries):
        raise ValueError("an electrophysiology entry has a datatype aimport does not write")
    records = load_records(work)
    for e in entries:
        i = e.series_idx - EPHYS_INDEX_BASE
        if not 0 <= i < len(records) or records[i].get("info") is None or records[i].get("error"):
            raise ValueError("an electrophysiology plan entry has no scan record: scan again")
    rec_of = {e.id: records[e.series_idx - EPHYS_INDEX_BASE] for e in entries}
    ev = json.loads((work / EVENTS_FILE).read_text()) if (work / EVENTS_FILE).is_file() else {}
    label_map: dict[str, str] = ev.get("labels") or {}
    channel_map: dict[str, dict[str, str]] = (json.loads((work / CHANNELS_FILE).read_text())
                                              if (work / CHANNELS_FILE).is_file() else {})
    event_names = dict(plan.event_names or {})
    allowed_labels = {event_names.get(lab, lab) for lab in label_map.values()}

    # the same daysback for every recording of a subject. Each empty room has its own (its date alone, no key
    # offset): one shared shift would keep the real gaps between the rooms, and so between subjects' sessions
    offsets: dict[str, int] = {}
    dates: dict[str, list[datetime]] = defaultdict(list)
    for e in entries:
        when = _date_of((rec_of[e.id]["info"] or {}).get("meas_date"))
        if when is not None and e.subject != EMPTY_ROOM_SUBJECT:
            dates[e.subject].append(when)
        if e.subject not in offsets:
            offsets[e.subject] = 0 if e.subject == EMPTY_ROOM_SUBJECT else key.date_offset_days(e.subject)
    back: dict[str, int] = {}
    for e in entries:
        if e.subject == EMPTY_ROOM_SUBJECT:
            when = _date_of((rec_of[e.id]["info"] or {}).get("meas_date"))
            back[e.id] = daysback([when] if when is not None else [], 0)
        else:
            back[e.id] = daysback(dates[e.subject], offsets[e.subject])

    paths: dict[str, Path] = {}

    def guarded(rel: str) -> Path:
        """dest(rel) once per output file: a session file written again for another run (coordsystem,
        electrodes) is overwritten in place, not counted twice."""
        if rel not in paths:
            paths[rel] = dest(rel)
        return paths[rel]

    order = sorted(entries, key=lambda e: (e.subject != EMPTY_ROOM_SUBJECT, e.series_idx))
    scratch = work / SCRATCH
    shutil.rmtree(scratch, ignore_errors=True)
    scratch.mkdir(parents=True)
    rooms: dict[str, str] = {}  # empty-room entry id -> its output rel
    listed: set[str] = set()  # rels already in an entry's manifest
    rel_entry: dict[str, PlanEntry] = {}
    shifted: list[date] = []
    try:
        for k, e in enumerate(order, 1):
            if progress is not None:
                progress(WRITE_PROGRESS.format(k=k, n=len(order)))
            rec = rec_of[e.id]
            renames = {old: new for new, old in (channel_map.get(rec["rel"]) or {}).items()}
            meta = {k2: redact(v, terms) if isinstance(v, str) else v for k2, v in (rec.get("meta") or {}).items()}
            if e.ephys_format == "NWB":
                written_labels = {k2: event_names.get(v, v) for k2, v in label_map.items()}
                rels = write_nwb(e, input_dir / rec["rel"], scratch, guarded, schema, terms, labels=written_labels,
                                 renames=renames, meta=meta, group_types=e.channel_types)
            else:
                raw = _open_clean(e, rec, input_dir, renames, label_map, event_names)
                if e.datatype == "nirs":
                    rels = write_nirs(e, raw, scratch, guarded, schema, terms, labels=allowed_labels,
                                      units=_snirf_units(rec, input_dir), meta=meta)
                else:
                    rels = write_recording(e, rec, raw, scratch, guarded, schema, terms, days_back=back[e.id],
                                           labels=allowed_labels, er_rel=rooms.get(e.empty_room or "")
                                           if e.datatype == "meg" else None, meta=meta)
                del raw
            if e.subject == EMPTY_ROOM_SUBJECT:
                rooms[e.id] = rels[0]
            for r in rels:
                rel_entry.setdefault(r, e)
            out.manifest.setdefault(e.id, []).extend(r for r in rels if r not in listed)
            listed.update(rels)
            out.images[rec["rel"]] = rels[0]
            base = f"sub-{e.subject}" + (f"/ses-{e.session}" if e.session else "")
            when = _date_of((rec["info"] or {}).get("meas_date"))
            acq = "n/a"
            if when is not None and e.subject != EMPTY_ROOM_SUBJECT:
                moved = when + timedelta(days=offsets[e.subject])
                acq = moved.strftime(SCANS_FORMAT)
                shifted.append(moved.date())
            out.scans.setdefault((e.subject, e.session), []).append((rels[0][len(base) + 1:], acq))
            label = _input_label(rec["rel"], "sub")
            if label and e.subject != EMPTY_ROOM_SUBJECT and e.subject_idx >= EPHYS_INDEX_BASE:
                out.labels.setdefault(e.subject_idx, label)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)

    # the final gate: every written file re-read for the run's terms, the original dates and copied bytes
    if paths:
        some_rel, some_path = next(iter(paths.items()))
        out_root = some_path
        for _ in PurePosixPath(some_rel).parts:
            out_root = out_root.parent
        originals: list = []
        for r in records:
            info = r.get("info") or {}
            originals += [_date_of(info.get("meas_date")), _birthday(r)]
        sources = [p for e in entries for p in _source_files(rec_of[e.id], input_dir)]
        extra: dict[str, int] = {}
        violations = gate.check(list(paths.values()), out_root, terms, gate.forbidden_date_forms(originals),
                                sources, extra_points=extra, allowed_dates=shifted)
        for rel, n in sorted(extra.items()):
            e = rel_entry.get(rel)
            if n and (e is None or not e.keep_headshape):
                violations.append(f"{rel}: head-shape points")
        if violations:
            raise gate.GateError(violations)

    # participants: age from the local birthday at the first recording, sex from the header
    for e in entries:
        if e.subject == EMPTY_ROOM_SUBJECT:
            out.participants[e.subject] = {"age": "n/a", "sex": "n/a"}
            continue
        row = out.participants.setdefault(e.subject, {"age": "n/a", "sex": "n/a"})
        info = rec_of[e.id]["info"] or {}
        if row["sex"] == "n/a":
            row["sex"] = SEX_CODES.get(info.get("sex"), "n/a")
    for subject, row in out.participants.items():
        if subject == EMPTY_ROOM_SUBJECT:
            continue
        mine = [rec_of[e.id] for e in entries if e.subject == subject]
        first = min((d for d in (_date_of((r["info"] or {}).get("meas_date")) for r in mine) if d is not None),
                    default=None)
        birthday = next((b for b in (_birthday(r) for r in mine) if b is not None), None)
        row["age"] = _age(birthday, first)
    return out
