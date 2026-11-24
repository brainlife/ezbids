"""The electrophysiology and optical module (BIDS ``eeg``, ``meg``, ``ieeg``, ``nirs``, ``emg``): claim, scan
into local records, plan entries.

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
from datetime import date, datetime
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
NWB_REASON = "NWB input is read by a later aimport version"
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
        try:
            terms = headers.harvest(rec, input_dir, None)
        except Exception:  # noqa: BLE001
            terms = _path_terms(rec)
        return None, terms, NWB_REASON, [], [], []
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
    formats = OUTPUT_FORMATS.get(datatype or "", ())
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
                 mri_subjects: dict[str, dict] | None = None) -> ModulePlan:
    """The ephys plan. mri_subjects: the MRI path's subjects by their input sub- folder label,
    ``{label: {"idx", "id", "sessions": {ses folder label: (session_idx, session)}, "only": (session_idx,
    session) | None}}``; recordings in that folder join that subject."""
    from ..brainlife_map import to_brainlife
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
            ents["acq"] = acq
        entities.append(ents)

    formats = [_default_format(dt, rec["family"]) if rec.get("info") is not None and not rec.get("error") else ""
               for rec, (dt, _) in zip(records, kinds)]

    # runs: recordings sharing (subject, session, task, acq) in one datatype (so one BIDS name) keep the
    # input's run labels when every one has a usable, distinct one; else, when there are several, they are
    # numbered by meas_date
    groups: dict[tuple, list[int]] = defaultdict(list)
    for i in range(len(records)):
        if formats[i]:
            groups[(originals[i], sessions[i], entities[i]["task"], entities[i].get("acq"), kinds[i][0])].append(i)
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
                d["exclude"], d["reason"] = True, d["reason"] + "; no brainlife datatype"
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
        ))
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
        return plan_entries(load_records(work), key, existing, schema, target, load_codes(work), subjects)

    def write(self, plan: "Plan", work: Path, input_dir: Path, terms: set[str], key: "PseudonymKey",
              schema: "Schema", dest: Callable[[str], Path]):
        raise NotImplementedError("electrophysiology output is written by a later aimport version")
