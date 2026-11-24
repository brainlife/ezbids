"""The planner: merges ezBIDS's first guess, the LLM agent, de-identification and pseudonyms
into the reviewable Plan.

Privacy: nothing identifying enters the plan. Subject IDs come from the pseudonym key (the
original identifiers stay in the key), every free-text value is redacted with the run's terms,
entity labels that change under redaction are dropped, and text the agent wrote is redacted and
truncated. The caller owns the key's lock: build_plan saves the key but never closes it.
"""
from __future__ import annotations

import re
import uuid
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from typing import Literal

from .agent import Guess, LLMClient, classify, draft_metadata
from .ancillary import ancillary_warnings, find_ancillary, id_maps, plan_ancillary, read_dataset_description
from .brainlife_map import to_brainlife
from .ezbids_runner import CoreResult, CoreSeries, CoreSubject
from .plan import Plan, PlanEntry
from .pseudonyms import PseudonymKey
from .schema import PHASE1_DATATYPES, Schema
from .scrub import _date_forms, identifying_terms, is_secondary_capture, redact, scrubbed_view

AGENT_TEXT_MAX = 300
AGREE_MIN = 0.8  # confidence when ezBIDS's guess stands (or the agent agrees with less)
DISAGREE_CONFIDENCE = 0.5  # ezBIDS's guess kept but the agent disputes it
AGENT_MIN = 0.5  # agent answers below this are not used
CHECK_EXT = ".nii.gz"  # every phase-1 image is written as NIfTI
_LABEL = re.compile(r"^[a-zA-Z0-9]+$")
_PATH_ENTITIES = {"subject", "session"}
UNVERIFIED = ("de-identification could not be verified: {why}; check descriptions and the README "
              "for names, IDs, dates and places before approving")

_MAGNITUDES = {"magnitude", "magnitude1", "magnitude2"}
DATASET_NAME_MAX = 120
README_MAX = 5000
# ezBIDS and anonymizers fill missing identifiers with these; they identify no one
_PLACEHOLDERS = {"", "n/a", "na", "anon", "anonymous", "anonymized", "unknown", "none", "0",
                 "00000000", "0000-00-00"}
_IDENTITY_FIELDS = (("PatientID", "id"), ("PatientName", "name"), ("PatientBirthDate", "dob"))
_DATE_FIELDS = ("AcquisitionDate", "StudyDate", "SeriesDate", "AcquisitionDateTime")
NO_IDENTITY = ("subject identity could not be established for {n} subject(s): they get new subject IDs "
               "for this import only, not linked to earlier imports")


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
        value = value.strip()[:10] if "T" in value else value.strip()
        if value in _PLACEHOLDERS or value.startswith("0000"):
            continue
        terms |= _date_forms(value)
    return terms


def run_terms(core: CoreResult, input_dir: Path, stats: dict | None = None) -> set[str]:
    """Every term to redact in this run: identifying values plus the scan dates in every form.

    build_plan and the BIDS writer must use the same set; stats is passed to identifying_terms.
    """
    return identifying_terms(core, input_dir, stats) | _date_terms(core)


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


def _present(value) -> str:
    text = str(value if value is not None else "").strip()
    return "" if text.lower() in _PLACEHOLDERS else text


def _subject_original(subject: CoreSubject) -> str | None:
    """"id=...|name=...|dob=..." from the non-placeholder identity fields; None when all are absent."""
    parts = []
    for field_name, prefix in _IDENTITY_FIELDS:
        value = next((v for v in (_present(i.get(field_name)) for i in subject.patient_info) if v), "")
        if value:
            parts.append(f"{prefix}={value}")
    return "|".join(parts) or None


def _assign_subjects(core: CoreResult, key: PseudonymKey, existing: set[str],
                     terms: set[str]) -> tuple[dict[int, str], int]:
    """subject_idx -> subject ID, and how many subjects got a run-local identity.

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
    local = [idx for idx, o in originals.items() if o is None or counts[o] > 1]
    for idx in local:
        originals[idx] = f"run:{run}:{idx}"
    ids = {idx: key.subject_id(originals[idx], existing, _proposed_label(by_idx[idx], core, terms))
           for idx in sorted(by_idx)}
    _assert_distinct(ids)
    return ids, len(local)


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


def _session_labels(subject: CoreSubject, terms: set[str]) -> dict[int, str]:
    """session_idx -> label: ezBIDS's when alphanumeric, else "1", "2", ... by acquisition date.

    Single-session subjects get "1" too, so a later import adding a session keeps one layout.
    """
    sessions = subject.sessions or [{}]
    # always a ses- level, even for one session: a later import may add a second one
    labels: dict[int, str] = {}
    for idx, s in enumerate(sessions):
        if _usable(s.get("session"), terms):
            labels[idx] = s["session"]
    taken = set(labels.values())
    n = 0
    todo = [i for i in range(len(sessions)) if i not in labels]
    for idx in sorted(todo, key=lambda i: (str(sessions[i].get("AcquisitionDate", "")), i)):
        n += 1
        while str(n) in taken:
            n += 1
        labels[idx] = str(n)
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


def _check_nameable(d: dict, subject: str, session: str | None, schema: Schema) -> None:
    """Rule: an "ok" entry must be one the writer can name; otherwise it becomes unknown."""
    if d["status"] != "ok":
        return
    if d["datatype"] not in PHASE1_DATATYPES:
        d.update(status="unsupported", exclude=True)
        return
    try:
        schema.filename(subject, session, d["datatype"], d["suffix"], d["entities"], CHECK_EXT)
    except ValueError as exc:
        d.update(status="unknown", exclude=True,
                 reason=f"{d['reason']}; cannot name {d['datatype']}/{d['suffix']}: {exc}")


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
            if e.suffix in _MAGNITUDES and e.brainlife_datatype is not None:
                e.brainlife_tags = [tag]


def build_plan(core: CoreResult, input_dir: Path, key: PseudonymKey, existing_subjects: set[str],
               client: LLMClient | None, schema: Schema, target: Literal["bids", "datatypes"],
               staged_dir: Path | None = None) -> Plan:
    stats: dict = {}
    terms = run_terms(core, input_dir, stats)
    warnings = []
    if stats.get("dicom_files_read", 0) == 0:
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
    draft = draft_metadata(view, client, terms)

    sub_ids, n_local = _assign_subjects(core, key, existing_subjects, terms)
    if n_local:
        warnings.append(NO_IDENTITY.format(n=n_local))
    ses_labels: dict[int, dict[int, str]] = {s.subject_idx: _session_labels(s, terms) for s in core.subjects}

    series_by_idx = {s.series_idx: s for s in core.series}
    triples = sorted({(o.series_idx, o.subject_idx, o.session_idx) for o in core.objects})
    entries = []
    for series_idx, subject_idx, session_idx in triples:
        series = series_by_idx.get(series_idx)
        if series is None:
            continue
        subject = sub_ids[subject_idx]
        labels = ses_labels.setdefault(subject_idx, {})
        if session_idx not in labels:  # a session ezBIDS did not list: the next free number
            n = 1
            while str(n) in labels.values():
                n += 1
            labels[session_idx] = str(n)
        session = labels[session_idx]
        d = _decide(series, guesses.get(series_idx), schema, terms)
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

    plan = Plan(target=target, entries=entries, warnings=warnings)
    if draft is not None:
        plan.dataset_name = draft.name[:DATASET_NAME_MAX]
        plan.readme = draft.readme[:README_MAX]
        plan.metadata_source = "agent"
    # supplied ancillary files (participants, phenotype, README, ...) and dataset_description fields
    ids = id_maps(core, entries)
    plan.ancillary = plan_ancillary(find_ancillary(input_dir, schema), input_dir, terms, ids, schema)
    plan.warnings += ancillary_warnings(plan.ancillary, ids)
    name, plan.dataset_description = read_dataset_description(input_dir, terms)
    if name:  # the dataset's own name wins over the agent's draft
        plan.dataset_name = name[:DATASET_NAME_MAX]
    return plan
