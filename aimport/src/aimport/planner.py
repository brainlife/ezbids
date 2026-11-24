"""The planner: merges ezBIDS's first guess, the LLM agent, de-identification and pseudonyms
into the reviewable Plan.

Privacy: nothing identifying enters the plan. Subject IDs come from the pseudonym key (the
original identifiers stay in the key), every free-text value is redacted with the run's terms,
entity labels that change under redaction are dropped, and text the agent wrote is redacted and
truncated. The caller owns the key's lock: build_plan saves the key but never closes it.
"""
from __future__ import annotations

import inspect
import re
import uuid
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Literal, Sequence

from .agent import Guess, LLMClient, classify, draft_metadata
from .ancillary import bids_root, ancillary_warnings, find_ancillary, id_maps, plan_ancillary, read_dataset_description
from .brainlife_map import no_datatype_reason, to_brainlife
from .ezbids_runner import CoreResult, CoreSeries, CoreSubject
from .plan import EMPTY_ROOM_SUBJECT, Plan, PlanEntry
from .pseudonyms import PseudonymKey
from .schema import CHECK_EXTS, EPHYS_DATATYPES, SUPPORTED_DATATYPES, Schema
from .scrub import _date_forms, identifying_terms, is_secondary_capture, redact, scrubbed_view

if TYPE_CHECKING:
    from .modality import ModulePlan

AGENT_TEXT_MAX = 300
AGREE_MIN = 0.8  # confidence when ezBIDS's guess stands (or the agent agrees with less)
DISAGREE_CONFIDENCE = 0.5  # ezBIDS's guess kept but the agent disputes it
AGENT_MIN = 0.5  # agent answers below this are not used
CHECK_EXT = ".nii.gz"  # every phase-1 image is written as NIfTI (CHECK_EXTS: other datatypes and formats)
MICR_DATATYPE_REASON = "microscopy input: datatype must be micr"
PIXEL_SIZE_REASON = "pixel size unknown: set it in the plan"
MRI_DATATYPE_REASON = "MRI input: datatype cannot be micr"
EPHYS_DATATYPE_REASON = "electrophysiology input: datatype must be one of eeg, meg, ieeg, nirs, emg"
MRI_EPHYS_REASON = "MRI input: datatype cannot be eeg, meg, ieeg, nirs or emg"
TASK_REASON = "set the task label"
# the extension each electrophysiology output format is mapped to brainlife by (bids-walker keys on eeg.eeg)
EPHYS_BRAINLIFE_EXTS = {"BrainVision": ".eeg", "EDF": ".edf", "BDF": ".bdf", "FIF": ".fif", "SNIRF": ".snirf",
                        "NWB": ".nwb"}
HIDDEN_ANCILLARY = ("{n} supplementary folder(s) of the input hold microscopy data, so they are not uploaded "
                    "as supplementary files")
_LABEL = re.compile(r"^[a-zA-Z0-9]+$")
_PATH_ENTITIES = {"subject", "session"}
UNVERIFIED = ("de-identification could not be verified: {why}; check descriptions and the README "
              "for names, IDs, dates and places before approving")

_MAGNITUDES = {"magnitude", "magnitude1", "magnitude2"}
ASL_SUFFIXES = ("asl", "m0scan", "aslcontext")
ASL_REASON = "ASL needs aslcontext.tsv and labeling metadata the importer cannot derive yet"
README_REASON = "used as the dataset README"
DATASET_NAME_MAX = 120
README_MAX = 5000
# ezBIDS and anonymizers fill missing identifiers with these; they identify no one
_PLACEHOLDERS = {"", "n/a", "na", "anon", "anonymous", "anonymized", "unknown", "none", "0",
                 "00000000", "0000-00-00"}
_ANON_WORDS = {"anonymized", "anonymised", "deidentified", "redacted", "removed", "subject", "patient", "test",
               "phantom", "unknown", "none", "null", "na", "n", "a"}
_TOKEN_SPLIT = re.compile(r"[\^\s_,.\-=/]+")
_FILLER = re.compile(r"^(x+|0+|-+)$")
_DOB_PLACEHOLDERS = {"00000000", "19000101", "18991230"}
_IDENTITY_FIELDS = (("PatientID", "id"), ("PatientName", "name"), ("PatientBirthDate", "dob"))
_DATE_FIELDS = ("AcquisitionDate", "StudyDate", "SeriesDate", "AcquisitionDateTime")
NO_IDENTITY = ("subject identity could not be established for {n} subject(s): they get new subject IDs "
               "for this import only, not linked to earlier imports")
SHARED_IDENTITY = ("{n} subjects share identical identifying values (ezBIDS may have split one person, or the "
                   "values are placeholders); they got separate IDs for this import")


def _anon_word(token: str) -> bool:
    return token.startswith("anon") or token in _ANON_WORDS or bool(_FILLER.match(token))


def is_placeholder(field: str, value) -> bool:
    """Whether an identity value (PatientID, PatientName, PatientBirthDate) is a filler that identifies no one.

    The value is casefolded and split on ^, spaces, _ , . - = /; it is a placeholder when nothing is left,
    when every token is an anonymization word (anon*, redacted, subject, test, unknown, n/a, ...) or
    filler (xxx, 000, ---), or when every token is the same single character. A birth date is also a
    placeholder when it is 00000000, 19000101, 18991230 or before 1900.
    """
    text = str(value if value is not None else "").casefold().strip()
    tokens = [t for t in _TOKEN_SPLIT.split(text) if t]
    if not tokens or all(_anon_word(t) for t in tokens):
        return True
    if len(set(tokens)) == 1 and len(tokens[0]) == 1:
        return True
    if field == "PatientBirthDate":
        digits = "".join(ch for ch in text if ch.isdigit())
        if digits in _DOB_PLACEHOLDERS or (len(digits) >= 4 and int(digits[:4]) < 1900):
            return True
    return False


def _valid_date(y: int, m: int, d: int) -> bool:
    try:
        date(y, m, d)
    except ValueError:
        return False
    return True


def _is_date_like(label: str) -> bool:
    """YYYYMMDD (1900-2099), YYMMDD or YYYYMM with a valid month (and day)."""
    if len(label) == 8 and label.isdigit():
        y = int(label[:4])
        return 1900 <= y <= 2099 and _valid_date(y, int(label[4:6]), int(label[6:]))
    if len(label) == 6 and label.isdigit():
        yymmdd = _valid_date(2000 + int(label[:2]), int(label[2:4]), int(label[4:]))
        yyyymm = 1900 <= int(label[:4]) <= 2099 and 1 <= int(label[4:]) <= 12
        return yymmdd or yyyymm
    return False


def _date_terms(core: CoreResult) -> set[str]:
    """Scan dates (every written form) from the ezBIDS objects, sidecars and sessions."""
    raw: list = [o.acquisition_date for o in core.objects]
    for sidecar in [o.sidecar for o in core.objects] + [s.sidecar for s in core.series]:
        raw += [sidecar.get(f) for f in _DATE_FIELDS]
    for subject in core.subjects:
        raw += [s.get("AcquisitionDate") for s in subject.sessions]
    terms: set[str] = set()
    for value in raw:
        if not isinstance(value, str) or not value.strip():
            continue
        value = value.strip()
        if "T" in value:
            value = value[:10]
        elif re.match(r"^\d{12}", value):  # a DICOM DT without the T: YYYYMMDDHHMM[SS[.ffffff]]
            value = value[:8]
        if value in _PLACEHOLDERS or value.startswith("0000"):
            continue
        terms |= _date_forms(value)
    return terms


def run_terms(core: CoreResult, input_dir: Path, stats: dict | None = None, exclude: Sequence[str] = ()) -> set[str]:
    """Every term to redact in this run: identifying values plus the scan dates in every form.

    build_plan and the BIDS writer must use the same set; stats and exclude (claimed roots, never
    walked) are passed to identifying_terms.
    """
    return identifying_terms(core, input_dir, stats, exclude) | _date_terms(core)


def _agent_text(text: str, terms: set[str]) -> str:
    return redact(text, terms)[:AGENT_TEXT_MAX]


def _clean_entities(entities: dict, terms: set[str]) -> dict[str, str]:
    """Drop subject/session, empty values and any label that redaction would change."""
    out = {}
    for k, v in entities.items():
        if k in _PATH_ENTITIES or v in (None, ""):
            continue
        v = str(v)
        if redact(v, terms) != v or _is_date_like(v):
            continue
        out[k] = v
    return out


def _ezbids_type(series: CoreSeries, schema: Schema) -> tuple[str, str] | None:
    """ezBIDS's datatype/suffix when it is a valid BIDS pair, else None."""
    datatype, sep, suffix = series.type.partition("/")
    if not sep or series.type == "exclude" or not schema.is_valid(datatype, suffix):
        return None
    return datatype, suffix


def _subject_original(subject: CoreSubject) -> str | None:
    """"id=...|name=...|dob=..." from the non-placeholder identity fields; None without a PatientID or
    PatientName (a birth date alone identifies no one)."""
    parts = {}
    for field_name, prefix in _IDENTITY_FIELDS:
        value = next((str(v).strip() for v in (i.get(field_name) for i in subject.patient_info)
                      if not is_placeholder(field_name, v)), "")
        if value:
            parts[prefix] = value
    if not parts.get("id") and not parts.get("name"):
        return None
    return "|".join(f"{k}={v}" for k, v in parts.items())


def _assign_subjects(core: CoreResult, key: PseudonymKey, existing: set[str],
                     terms: set[str]) -> tuple[dict[int, str], int, int]:
    """subject_idx -> subject ID, and how many subjects got a run-local identity because none could be
    established, and because another subject in this run shares it.

    A subject with no identity, or whose identity another subject in this run shares (ezBIDS
    split one person, or two people share placeholder-like values), gets a run-local original
    so it is never merged with another person, now or in a later import.
    """
    by_idx = {s.subject_idx: s for s in core.subjects}
    for o in core.objects:  # an object whose subject ezBIDS did not list
        by_idx.setdefault(o.subject_idx, CoreSubject(o.subject_idx, "", [], []))
    originals = {idx: _subject_original(s) for idx, s in by_idx.items()}
    counts = Counter(o for o in originals.values() if o is not None)
    run = uuid.uuid4().hex
    absent = [idx for idx, o in originals.items() if o is None]
    shared = [idx for idx, o in originals.items() if o is not None and counts[o] > 1]
    for idx in absent + shared:
        originals[idx] = f"run:{run}:{idx}"
    ids = {idx: key.subject_id(originals[idx], existing, _proposed_label(by_idx[idx], core, terms))
           for idx in sorted(by_idx)}
    _assert_distinct(ids)
    return ids, len(absent), len(shared)


def _assert_distinct(ids: dict[int, str]) -> None:
    seen: dict[str, int] = {}
    for idx, sid in ids.items():
        if sid in seen:
            raise ValueError(f"subjects {seen[sid]} and {idx} were both given subject ID {sid!r}")
        seen[sid] = idx


def _proposed_label(subject: CoreSubject, core: CoreResult, terms: set[str]) -> str | None:
    """ezBIDS's label, only when the input already had a sub-<label> folder for it."""
    label = subject.label
    if not _usable(label, terms):
        return None
    paths = [str(i.get("file_directory", "")) for i in subject.patient_info]
    paths += [str(p) for o in core.objects if o.subject_idx == subject.subject_idx for p in o.paths]
    want = f"sub-{label}".lower()
    for path in paths:
        if any(part.lower() == want for part in Path(path).parts):
            return label
    return None


def _day(value) -> date | None:
    text = str(value or "").strip().split("T")[0]
    for fmt in ("%Y-%m-%d", "%Y%m%d"):
        try:
            day = datetime.strptime(text, fmt).date()
        except ValueError:
            continue
        return day if day.year >= 1900 else None
    return None


def _session_keys(subject: CoreSubject, subject_id: str, idxs: list[int], core: CoreResult,
                  key: PseudonymKey) -> dict[int, str | None]:
    """session_idx -> what identifies the study in the key: "study:<StudyInstanceUID>", else
    "date:<acquisition date shifted by the subject's offset>", else None. A key two sessions of this
    run share (two studies on one day without UIDs) is dropped for both: they are numbered as new."""
    sessions = subject.sessions
    out: dict[int, str | None] = {}
    for idx in idxs:
        objs = [o for o in core.objects if o.subject_idx == subject.subject_idx and o.session_idx == idx]
        uids = sorted({str(o.sidecar.get("StudyInstanceUID")).strip() for o in objs
                       if not is_placeholder("StudyInstanceUID", o.sidecar.get("StudyInstanceUID"))})
        if uids:
            out[idx] = "study:" + uids[0]
            continue
        dates = [sessions[idx].get("AcquisitionDate")] if idx < len(sessions) else []
        day = next((d for d in map(_day, dates + [o.acquisition_date for o in objs]) if d), None)
        out[idx] = ("date:" + (day + timedelta(days=key.date_offset_days(subject_id))).isoformat()
                    if day else None)
    counts = Counter(v for v in out.values() if v)
    return {idx: (v if v and counts[v] == 1 else None) for idx, v in out.items()}


def _session_labels(subject: CoreSubject, subject_id: str, core: CoreResult, key: PseudonymKey,
                    existing: list[str], terms: set[str]) -> dict[int, str]:
    """session_idx -> label, recorded in the key per study so a re-import never reuses a label.

    A study the key already holds for this subject keeps its label. Otherwise ezBIDS's label is used
    when alphanumeric and not taken; else "1", "2", ... by acquisition date, skipping every label the
    key holds for this subject and the project's existing sessions (existing). Single-session subjects
    get "1" too, so a later import adding a session keeps one layout.
    """
    sessions = subject.sessions or [{}]
    idxs = sorted(set(range(len(sessions))) | {o.session_idx for o in core.objects
                                               if o.subject_idx == subject.subject_idx})
    recorded = key.sessions.setdefault(subject_id, {})
    skeys = _session_keys(subject, subject_id, idxs, core, key)
    labels: dict[int, str] = {idx: recorded[skeys[idx]] for idx in idxs if skeys[idx] in recorded}
    taken = set(recorded.values()) | set(existing) | set(labels.values())
    for idx in idxs:
        label = sessions[idx].get("session") if idx < len(sessions) else None
        if idx not in labels and _usable(label, terms) and label not in taken:
            labels[idx] = label
            taken.add(label)
    n = 0

    def when(i: int) -> tuple[str, int]:
        return (str(sessions[i].get("AcquisitionDate", "")) if i < len(sessions) else "", i)

    for idx in sorted((i for i in idxs if i not in labels), key=when):
        n += 1
        while str(n) in taken:
            n += 1
        labels[idx] = str(n)
    run = uuid.uuid4().hex
    for idx in idxs:  # a session with nothing to recognise it by still reserves its label
        recorded[skeys[idx] or f"run:{run}:{idx}"] = labels[idx]
    return labels


def _usable(label, terms: set[str]) -> bool:
    return (isinstance(label, str) and bool(_LABEL.match(label)) and redact(label, terms) == label
            and not _is_date_like(label))


def _guess_text(g: Guess) -> str:
    ents = "".join(f" {k}-{v}" for k, v in g.entities.items())
    return f"agent suggests {g.datatype}/{g.suffix}{ents} (confidence {g.confidence:.2f}): {g.reason}"


def _decide(series: CoreSeries, guess: Guess | None, schema: Schema, terms: set[str]) -> dict:
    """datatype/suffix/entities/source/confidence/status/reason/agent_note for one series."""
    if is_secondary_capture(series):
        return dict(datatype=None, suffix=None, entities={}, source="none", confidence=0.0,
                    status="excluded_by_default", exclude=True, reason="may contain burned-in identifiers",
                    agent_note="")
    heuristic = _ezbids_type(series, schema)
    has_answer = guess is not None and guess.datatype is not None
    agent_reason = _agent_text(guess.reason, terms) if guess is not None else ""
    if heuristic is not None:
        entities = _clean_entities(series.entities, terms)
        reason = redact(series.message, terms) if series.message else "ezBIDS heuristic"
        out = dict(datatype=heuristic[0], suffix=heuristic[1], entities=entities, source="heuristic",
                   confidence=AGREE_MIN, status="ok", exclude=False, reason=reason, agent_note="")
        if has_answer and (guess.datatype, guess.suffix) == heuristic:
            out["confidence"] = max(AGREE_MIN, guess.confidence)
            for k, v in _clean_entities(guess.entities, terms).items():
                entities.setdefault(k, v)
        elif has_answer and guess.confidence >= AGENT_MIN:
            out["confidence"] = DISAGREE_CONFIDENCE
            out["agent_note"] = _agent_text(_guess_text(guess), terms)
        return out
    if has_answer and guess.confidence >= AGENT_MIN:
        return dict(datatype=guess.datatype, suffix=guess.suffix, entities=_clean_entities(guess.entities, terms),
                    source="agent", confidence=guess.confidence, status="ok", exclude=False,
                    reason=agent_reason or "agent", agent_note="")
    reason = redact(series.message, terms) if series.message else f"ezBIDS type {series.type!r} is not BIDS"
    return dict(datatype=None, suffix=None, entities={}, source="none", confidence=0.0, status="unknown",
                exclude=True, reason=reason, agent_note=_agent_text(_guess_text(guess), terms) if has_answer else "")


def _modality_reason(modality: str, datatype: str | None) -> str | None:
    """Why an entry's datatype does not fit its input's modality (micr input <-> micr datatype, ephys input
    <-> ephys datatypes)."""
    if modality == "micr":
        return None if datatype == "micr" else MICR_DATATYPE_REASON
    if modality == "ephys":
        return None if datatype in EPHYS_DATATYPES else EPHYS_DATATYPE_REASON
    if datatype == "micr":
        return MRI_DATATYPE_REASON
    if datatype in EPHYS_DATATYPES:
        return MRI_EPHYS_REASON
    return None


def _check_nameable(d: dict, subject: str, session: str | None, schema: Schema, modality: str = "mri",
                    ephys_format: str = "") -> None:
    """Rule: an "ok" entry must be one the writer can name; otherwise it becomes unknown. A microscopy
    entry must stay micr and an electrophysiology entry must keep an electrophysiology datatype (and an MRI
    entry must take neither); an electrophysiology entry needs a task label."""
    if d["status"] != "ok":
        return
    why = _modality_reason(modality, d["datatype"])
    if why is not None:
        d.update(status="unknown", exclude=True, reason=why)
        return
    if d["datatype"] not in SUPPORTED_DATATYPES:
        d.update(status="unsupported", exclude=True)
        return
    if d["datatype"] in EPHYS_DATATYPES and d["entities"].get("task") in (None, "", "unknown"):
        d.update(status="unknown", exclude=True, reason=TASK_REASON)
        return
    try:
        schema.filename(subject, session, d["datatype"], d["suffix"], d["entities"],
                        CHECK_EXTS.get(ephys_format) or CHECK_EXTS.get(d["datatype"], CHECK_EXT))
    except ValueError as exc:
        d.update(status="unknown", exclude=True,
                 reason=f"{d['reason']}; cannot name {d['datatype']}/{d['suffix']}: {exc}")


def check_pixel_size(d: dict, e: PlanEntry) -> None:
    """Rule: an "ok" microscopy entry has a pixel size for every spatial axis, and units; otherwise it
    becomes unknown (never an invented size)."""
    if d["status"] != "ok" or e.modality != "micr":
        return
    n = len(e.spatial_axes) or None
    if e.pixel_size is None or e.pixel_size_units is None or (n is not None and len(e.pixel_size) != n):
        d.update(status="unknown", exclude=True, reason=PIXEL_SIZE_REASON)


def _fmap_tags(entries: list[PlanEntry]) -> None:
    """Magnitude images take their brainlife tag from the fieldmap they belong to."""
    groups: dict[tuple[int, int], list[PlanEntry]] = defaultdict(list)
    for e in entries:
        if e.datatype == "fmap" and not e.exclude:
            groups[(e.subject_idx, e.session_idx)].append(e)
    for group in groups.values():
        suffixes = {e.suffix for e in group}
        if suffixes & {"phase1", "phase2"}:
            tag = "2phasemag"
        elif "phasediff" in suffixes:
            tag = "phasediff"
        elif "fieldmap" in suffixes:
            tag = "single"
        else:
            continue
        for e in group:
            if e.suffix in _MAGNITUDES and e.brainlife_datatype is not None and not e.brainlife_by_person:
                e.brainlife_tags = [tag]


EDITED = "edited by the reviewer"
_NAMING = {"subject", "session", "datatype", "suffix", "entities"}


def apply_plan_edits(plan: Plan, edits: list[dict], schema: Schema) -> None:
    """Apply reviewer edits (Plan.apply_edits) and re-derive what depends on them.

    For every changed entry: the status comes from the same nameable check as build_plan (an entry
    the writer cannot name becomes unknown and excluded; one that becomes nameable is included unless
    the edit says otherwise), the brainlife datatype and tags are recomputed unless the reviewer set them (brainlife_by_person),
    and the datatypes target excludes an entry with no brainlife datatype. Secondary captures stay
    excluded_by_default. Raises like Plan.apply_edits; a bad edit changes nothing. sample_type must be a
    value of the schema's sample_type enum, and pixel_size/pixel_size_units are set on microscopy
    entries only; a microscopy entry without a pixel size for each spatial axis stays unknown.
    ephys_format must be an output format of the entry's (new) datatype, and keep_headshape and
    ephys_format apply to electrophysiology entries only.
    """
    _check_sample_types(plan, edits, schema)
    _check_ephys_edits(plan, edits)
    was_ok = {e.id: e.status == "ok" for e in plan.entries}
    keys: dict[str, set[str]] = defaultdict(set)
    for edit in edits:
        if isinstance(edit, dict):
            keys[edit.get("id")] |= set(edit)
    for e in plan.apply_edits(edits):
        _rederive(e, schema, plan.target, keys[e.id], was_ok[e.id])
    _fmap_tags(plan.entries)


def _check_sample_types(plan: Plan, edits: list[dict], schema: Schema) -> None:
    """Microscopy-only edit rules: sample_type is a value of the schema enum (never None) and only
    for micr entries; deface is never turned on for a micr entry."""
    by_id = {e.id: e for e in plan.entries}
    allowed = None
    for edit in edits:
        if not isinstance(edit, dict):
            continue
        e = by_id.get(edit.get("id"))
        if e is None:
            continue  # Plan.apply_edits raises KeyError
        if e.modality == "micr" and edit.get("deface") is True:
            raise ValueError("microscopy images are never defaced")
        for k in ("pixel_size", "pixel_size_units"):
            if e.modality != "micr" and edit.get(k) is not None:
                raise ValueError(f"{k} applies to microscopy entries only")
        if "sample_type" not in edit:
            continue
        if e.modality != "micr":
            if edit["sample_type"] is None:
                continue
            raise ValueError("sample_type applies to microscopy entries only")
        allowed = schema.sample_types() if allowed is None else allowed
        if edit["sample_type"] not in allowed:
            raise ValueError(f"sample_type must be one of {allowed}")


def _output_formats(datatype: str | None) -> tuple[str, ...]:
    from .ephys import OUTPUT_FORMATS

    return OUTPUT_FORMATS.get(datatype or "", ())


def _nwb_source(e: PlanEntry) -> bool:
    """An entry read from NWB input (its generated description names the source format first)."""
    return e.description.startswith("NWB ")


NWB_CHANNEL_TYPES = ("seeg", "ecog", "dbs")  # ephys.nwb.CHANNEL_TYPES


def _check_ephys_edits(plan: Plan, edits: list[dict]) -> None:
    """Electrophysiology edit rules: ephys_format is one of the output formats of the entry's datatype
    after the edit (NWB only for NWB input, never None), only for a writable ephys entry; keep_headshape
    only for ephys entries; channel_types (NWB input) keeps its groups and takes seeg, ecog or dbs; deface is never
    turned on for one."""
    by_id = {e.id: e for e in plan.entries}
    for edit in edits:
        if not isinstance(edit, dict):
            continue
        e = by_id.get(edit.get("id"))
        if e is None:
            continue  # Plan.apply_edits raises KeyError
        ephys = e.modality == "ephys"
        if "subject" in edit and (e.subject == EMPTY_ROOM_SUBJECT and ephys) != (edit["subject"] == EMPTY_ROOM_SUBJECT):
            raise ValueError(f"the subject {EMPTY_ROOM_SUBJECT!r} holds the empty-room recordings: it is not "
                             "renamed, and no other subject takes its ID")
        if ephys and edit.get("deface") is True:
            raise ValueError("electrophysiology recordings are never defaced")
        if "keep_headshape" in edit and not ephys and edit["keep_headshape"] is not False:
            raise ValueError("keep_headshape applies to electrophysiology entries only")
        if "channel_types" in edit:
            types = edit["channel_types"]
            if not ephys or not e.channel_types:
                if types:
                    raise ValueError("channel_types applies to electrophysiology entries read from NWB only")
            elif set(types) != set(e.channel_types) or any(v not in NWB_CHANNEL_TYPES for v in types.values()):
                raise ValueError(f"channel_types keeps the groups {sorted(e.channel_types)} and gives each one of "
                                 f"{list(NWB_CHANNEL_TYPES)}")
        if "ephys_format" not in edit:
            continue
        fmt = edit["ephys_format"]
        if not ephys:
            if fmt is None:
                continue
            raise ValueError("ephys_format applies to electrophysiology entries only")
        if not e.ephys_format:
            raise ValueError("this recording cannot be written, so it has no output format")
        datatype = edit.get("datatype", e.datatype)
        allowed = [f for f in _output_formats(datatype) if f != "NWB" or _nwb_source(e)]
        if fmt not in allowed:
            raise ValueError(f"ephys_format for {datatype} must be one of {allowed}")


def _ephys_format(e: PlanEntry) -> None:
    """A writable ephys entry whose datatype changed keeps its format only when the new datatype allows
    it; else it takes the new datatype's default."""
    allowed = [f for f in _output_formats(e.datatype) if f != "NWB" or _nwb_source(e)]
    if e.ephys_format not in allowed:
        e.ephys_format = allowed[0] if allowed else e.ephys_format


def _rederive(e: PlanEntry, schema: Schema, target: str, keys: set[str], was_ok: bool) -> None:
    if e.status == "excluded_by_default":  # may hold burned-in identifiers: never written
        return
    if e.modality == "micr" and not e.write_mode:  # unreadable or unsupported input: never written
        return
    if e.modality == "ephys" and not e.ephys_format:  # unreadable or unsupported input: never written
        return
    if not keys and not was_ok:  # renamed with its subject only: still not writable, reason unchanged
        return
    if e.modality == "ephys":
        _ephys_format(e)
    reason = EDITED if keys & _NAMING or not was_ok else e.reason
    d = dict(datatype=e.datatype, suffix=e.suffix, entities=e.entities, status="ok", exclude=e.exclude,
             reason=reason)
    why = _modality_reason(e.modality, e.datatype)
    if why is not None:
        d.update(status="unknown", exclude=True, reason=why)
    elif not (e.datatype and e.suffix and schema.is_valid(e.datatype, e.suffix)):
        d.update(status="unknown", exclude=True, reason=f"{reason}; {e.datatype}/{e.suffix} is not BIDS")
    else:
        if not was_ok and "exclude" not in keys:
            d["exclude"] = False
        _check_nameable(d, e.subject, e.session, schema, e.modality, e.ephys_format)
    check_pixel_size(d, e)
    e.status, e.exclude, e.reason = d["status"], d["exclude"], d["reason"]
    if not e.brainlife_by_person:
        e.brainlife_datatype, e.brainlife_tags = (
            to_brainlife(e.datatype, e.suffix, e.entities, {}, EPHYS_BRAINLIFE_EXTS.get(e.ephys_format))
            if e.status == "ok" else (None, []))
    if target == "datatypes" and e.brainlife_datatype is None and not e.exclude:
        # an ephys entry names its draft datatype (MRI reasons are unchanged)
        gap = no_datatype_reason(e.datatype, e.suffix) if e.modality == "ephys" else "; no brainlife datatype"
        e.exclude, e.reason = True, f"{e.reason}{gap}"


def _seed_readme(plan: Plan, supplied: list[Path], input_dir: Path, terms: set[str]) -> None:
    """The input's own README (de-identified) becomes plan.readme; its entry is then not written twice."""
    root = bids_root(input_dir)
    for a in plan.ancillary:
        if a.kind != "core" or a.path.split(".")[0] != "README" or a.locked or a.action != "keep":
            continue
        src = next((p for p in supplied if p.relative_to(root).as_posix().split(".")[0] == "README"
                    and p.is_file() and not p.is_symlink()), None)
        if src is None:
            continue
        text = redact(src.read_text(encoding="utf-8", errors="replace"), terms)[:README_MAX]
        plan.readme, plan.metadata_source = text, "person"
        a.action, a.reason = "drop", README_REASON
        return


def _mri_subjects(core: CoreResult, entries: list[PlanEntry]) -> dict[str, dict]:
    """The MRI subjects by their input sub- folder label: {label: {"idx", "id", "sessions": {ses folder label:
    (session_idx, session)}, "only": (session_idx, session) when the subject has exactly one session}}."""
    ids = id_maps(core, entries)
    out: dict[str, dict] = {}
    for idx, label in ids.labels.items():
        if idx not in ids.subjects:
            continue
        sessions = {lab: (j, ids.sessions[(i, j)]) for (i, j), lab in ids.session_labels.items()
                    if i == idx and (i, j) in ids.sessions}
        all_sessions = sorted({(e.session_idx, e.session) for e in entries if e.subject_idx == idx},
                              key=lambda t: t[0])
        out[label] = {"idx": idx, "id": ids.subjects[idx], "sessions": sessions,
                      "only": all_sessions[0] if len(all_sessions) == 1 else None}
    return out


def _call_planner(plan_module: Callable, mri_subjects: dict[str, dict]) -> "ModulePlan":
    """A planner that takes an argument gets the MRI subjects by folder label; one that takes none is called
    as is (phase 2 planners)."""
    try:
        takes = bool(inspect.signature(plan_module).parameters)
    except (TypeError, ValueError):
        takes = False
    return plan_module(mri_subjects) if takes else plan_module()


def build_plan(core: CoreResult, input_dir: Path, key: PseudonymKey, existing_subjects: set[str],
               client: LLMClient | None, schema: Schema, target: Literal["bids", "datatypes"],
               staged_dir: Path | None = None, existing_sessions: dict[str, list[str]] | None = None,
               exclude: Sequence[str] = (), modules: Sequence["ModulePlan"] = (),
               extra_terms: frozenset[str] = frozenset(),
               planners: Sequence[Callable[..., "ModulePlan"]] = ()) -> Plan:
    """The reviewable plan. existing_subjects and existing_sessions (subject id -> session labels) are what
    the brainlife project already holds, so new subject IDs and session labels do not collide with them.
    exclude: claimed roots (input-relative), never walked for DICOM headers or planned as ancillary.
    modules: the modality modules' plans (entries, warnings, views, subject labels, images, event names),
    appended; planners: module planners, called once the MRI subjects hold their IDs in the key, so the MRI
    subject IDs and session labels are those of an MRI-only plan (a planner taking one argument gets the MRI
    subjects by input sub- folder label, see _mri_subjects); extra_terms: the modules' identifying
    terms, redacted like the run's own (not used for the MRI subject and session labels, for the same reason)."""
    stats: dict = {}
    mri_terms = run_terms(core, input_dir, stats, exclude)
    terms = mri_terms | set(extra_terms)
    warnings = []
    if stats.get("dicom_files_read", 0) == 0:
        if core.series or not (modules or planners):  # a module-only scan has no DICOM headers to read
            warnings.append(UNVERIFIED.format(why="no DICOM headers were read"))
    elif stats.get("term_count", 0) == 0:
        warnings.append(UNVERIFIED.format(why="no identifying values were found"))

    view = scrubbed_view(core, terms, root=staged_dir)
    heuristic = {}
    for s in core.series:
        ht = _ezbids_type(s, schema)
        if ht is not None:
            heuristic[s.series_idx] = (ht[0], ht[1], _clean_entities(s.entities, terms))
    guesses = {g.series_idx: g for g in classify(view, heuristic, client, schema)}

    hidden: list[Path] = []
    supplied = find_ancillary(input_dir, schema, exclude, hidden=hidden)
    if hidden:
        warnings.append(HIDDEN_ANCILLARY.format(n=len(hidden)))
    has_aslcontext = any(p.name.endswith("_aslcontext.tsv") for p in supplied)  # anywhere in the input
    sub_ids, n_absent, n_shared = _assign_subjects(core, key, existing_subjects, mri_terms)
    if n_shared:
        warnings.append(SHARED_IDENTITY.format(n=n_shared))
    if n_absent:
        warnings.append(NO_IDENTITY.format(n=n_absent))
    by_idx = {s.subject_idx: s for s in core.subjects}
    ses_labels = {idx: _session_labels(by_idx.get(idx, CoreSubject(idx, "", [], [])), sid, core, key,
                                       (existing_sessions or {}).get(sid, []), mri_terms)
                  for idx, sid in sub_ids.items()}
    series_by_idx = {s.series_idx: s for s in core.series}
    triples = sorted({(o.series_idx, o.subject_idx, o.session_idx) for o in core.objects})
    entries = []
    for series_idx, subject_idx, session_idx in triples:
        series = series_by_idx.get(series_idx)
        if series is None:
            continue
        subject = sub_ids[subject_idx]
        session = ses_labels[subject_idx][session_idx]
        d = _decide(series, guesses.get(series_idx), schema, terms)
        if d["datatype"] == "perf" and d["suffix"] in ASL_SUFFIXES and not has_aslcontext:
            d["exclude"], d["reason"] = True, ASL_REASON
        _check_nameable(d, subject, session, schema)
        bl_datatype, bl_tags = (None, [])
        if d["datatype"] and d["suffix"]:
            bl_datatype, bl_tags = to_brainlife(d["datatype"], d["suffix"], d["entities"], series.sidecar)
            if target == "datatypes" and bl_datatype is None:
                d["exclude"] = True
                d["reason"] += "; no brainlife datatype"
        entries.append(PlanEntry(
            id=f"s{series_idx}-sub{subject_idx}-ses{session_idx}",
            series_idx=series_idx,
            subject_idx=subject_idx,
            session_idx=session_idx,
            subject=subject,
            session=session,
            datatype=d["datatype"],
            suffix=d["suffix"],
            entities=d["entities"],
            brainlife_datatype=bl_datatype,
            brainlife_tags=bl_tags,
            source=d["source"],
            confidence=d["confidence"],
            reason=d["reason"],
            deface=d["datatype"] == "anat",
            exclude=d["exclude"],
            status=d["status"],
            description=redact(series.series_description, terms),
            agent_note=d["agent_note"],
        ))
    key.save()
    _fmap_tags(entries)
    # module planners run once the MRI subjects hold their IDs in the key, and learn which input sub- folders
    # those subjects came from (a module's recordings in the same folder are the same person)
    mri_subjects = _mri_subjects(core, entries)
    modules = list(modules) + [_call_planner(plan_module, mri_subjects) for plan_module in planners]
    draft = draft_metadata(view + [v for mp in modules for v in mp.view], client, terms)

    event_names: dict[str, str] = {}
    for mp in modules:
        entries += mp.entries
        warnings += mp.warnings
        event_names.update(mp.event_names)
    plan = Plan(target=target, entries=entries, warnings=warnings, event_names=event_names)
    if draft is not None:
        plan.dataset_name = draft.name[:DATASET_NAME_MAX]
        plan.readme = draft.readme[:README_MAX]
        plan.metadata_source = "agent"
    # supplied ancillary files (participants, phenotype, README, ...) and dataset_description fields
    ids = id_maps(core, entries)
    for mp in modules:
        for idx, label in mp.labels.items():
            if label not in ids.labels.values():  # a label mapping two ways is left out (see id_maps)
                ids.labels[idx] = label
        ids.images.update(mp.images)
    plan.ancillary = plan_ancillary(supplied, input_dir, terms, ids, schema)
    _seed_readme(plan, supplied, input_dir, terms)
    plan.warnings += ancillary_warnings(plan.ancillary, ids)
    name, plan.dataset_description = read_dataset_description(input_dir, terms)
    if name:  # the dataset's own name wins over the agent's draft
        plan.dataset_name = name[:DATASET_NAME_MAX]
    return plan
