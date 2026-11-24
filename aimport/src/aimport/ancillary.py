"""Ancillary and metadata files: everything BIDS defines besides the imaging data.

Core files (README, CHANGES, LICENSE, CITATION.cff, genetic_info.json), tables (participants,
samples, sessions, scans, phenotype/*) with their JSON descriptions, inherited sidecars and
events at the dataset, subject and session levels, per-run companions inside datatype folders
(events, physio, stim, channels, ...), and the code/, docs/, stimuli/, logs/ folders.
dataset_description.json is not an entry: its editable fields go to Plan.dataset_description.

The BIDS root is the input folder, or the first folder up to two levels below it that holds a
dataset_description.json.

Privacy rules:
- Nothing is copied as it is. Tables are rebuilt row by row: participant_id/session_id/filename
  rewritten to the new labels, rows of people (and sessions, files) not in this import dropped,
  identifying, free-text and unshiftable date columns dropped by default, date columns shifted by
  the subject's offset in their own format, ages over 89 capped, and every cell that holds a term
  written as n/a. participants, samples and phenotype tables without a participant_id column, and
  tables whose rows do not match their header, are never uploaded. Every JSON value and every
  text file is redacted, the reviewer's edited content included.
- Symbolic links are never followed, anywhere. sourcedata/ and derivatives/ are never written,
  nor anything with aimport-key in its path; binary files leave code/, docs/ and logs/ never.
- The plan holds no original subject or session label: AncillaryEntry.source carries tokens
  (sub-<subject_idx>, ses-<session_idx>), and the destination is computed at write time from the
  current plan, so a subject renamed in review takes its files along. A file whose name holds a
  term is not listed.
"""
from __future__ import annotations

import gzip
import json
import os
import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Sequence

from .ezbids_runner import CoreResult
from .modality import ClaimedPaths
from .plan import (
    DATE_COLUMN,
    DESCRIPTION_FIELDS,
    KEY_COLUMNS,
    NEVER_KEEP,
    NOT_UPLOADABLE,
    REDACTED_MARK,
    AncillaryEntry,
    Plan,
    PlanEntry,
)
from .pseudonyms import PseudonymKey
from .schema import BIDS_VERSION, Schema
from .scrub import REDACTED, redact, scrub_sidecar

assert REDACTED == REDACTED_MARK

NA = "n/a"
PATH_NUMERIC_MIN = 4
AGE_CAP = 89
DATE_SHARE = 0.8  # a column is a date column when this share of its non-n/a cells are dates (and all date-ish ones parse)
DATEISH_SHARE = 0.5  # ... and is dropped by default when this share looks like dates that cannot all be read
FREE_TEXT_SHARE = 0.5  # a column is free text when more than this share of its cells have FREE_TEXT_WORDS words
FREE_TEXT_WORDS = 4
ROOT_DEPTH = 2  # how far below the input folder a dataset_description.json is looked for
FOLDERS = ("code", "docs", "stimuli", "logs") + NEVER_KEEP
TEXT_ONLY_FOLDERS = ("code", "docs", "logs")  # binary files are never uploaded from these
TABLE_STEMS = ("participants", "samples")
SUB_TABLES = ("sessions", "scans")
KEY_NAME = "aimport-key"
IMAGE_EXTS = (".nii.gz", ".nii")
COMPANION_EXTS = (".tsv.gz", ".tsv", ".json")
# Headers that name a person, a birth date, a record number, a place or free text. Matched as a
# substring, so first_name/surname/dateofbirth are caught; a false match only drops a column by default.
IDENTIFYING_COLUMNS = re.compile(
    r"name|birth|dob|mrn|ssn|address|street|zip|postal|e-?mail|phone|initials|notes?|comments?|remarks?"
    r"|observation|history|free.?text", re.IGNORECASE)
_ID_TOKEN = re.compile(r"(?:^|[^a-z0-9])id(?:$|[^a-z0-9])")  # hospital_id, id, record id (lowercased)
_ID_CAMEL = re.compile(r"[a-z]ID(?:$|[^a-zA-Z])")  # PatientID, StudyID
_AGE = re.compile(r"age(?![a-z])", re.IGNORECASE)
_AGE_PREFIXES = ("subject", "patient", "participant", "scan", "visit", "onset", "baseline", "enrollment",
                 "enrolment", "diagnosis", "death", "gestational")
_AGE_UNITS = (("month", 12), ("week", 52), ("day", 365))
_ENTITY_STEM = re.compile(r"^((?:[a-zA-Z0-9]+-[a-zA-Z0-9]+_)*)([a-zA-Z0-9]+)$")
_SUB_DIR = re.compile(r"^sub-[a-zA-Z0-9]+$")
_SES_DIR = re.compile(r"^ses-[a-zA-Z0-9]+$")
_TOKEN = re.compile(r"(sub|ses)-<(\d+)>")
_LEADING_NUMBER = re.compile(r"^\s*(\d+(?:\.\d+)?)")
_RECORDING = re.compile(r"_recording-[a-zA-Z0-9]+")

_MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
_MONTH_NAMES = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october",
                "november", "december"]
_MON = r"(?P<mon>[A-Za-z]{3,9})"
_DATE_FORMATS = [  # each names its y/m/d (or mon) groups; s = time or separator tail kept as it is
    re.compile(r"^(?P<y>\d{4})-(?P<m>\d{1,2})-(?P<d>\d{1,2})"
               r"(?P<t>[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:?\d{2})?)?$"),
    re.compile(r"^(?P<y>(?:19|20)\d{2})(?P<m>\d{2})(?P<d>\d{2})$"),
    re.compile(r"^(?P<y>\d{4})/(?P<m>\d{1,2})/(?P<d>\d{1,2})$"),
    re.compile(r"^(?P<y>\d{4})\.(?P<m>\d{1,2})\.(?P<d>\d{1,2})$"),
    re.compile(r"^(?P<d>\d{1,2})\.(?P<m>\d{1,2})\.(?P<y>\d{4})$"),
    re.compile(r"^(?P<d>\d{1,2})[ -]" + _MON + r"\.?(?:[ -]|, )(?P<y>\d{4})$"),
    re.compile(r"^" + _MON + r"\.? (?P<d>\d{1,2}),? (?P<y>\d{4})$"),
]
_SLASH = {  # MM/DD/YYYY or DD/MM/YYYY: one reading per column
    "mdy": re.compile(r"^(?P<m>\d{1,2})/(?P<d>\d{1,2})/(?P<y>\d{4})$"),
    "dmy": re.compile(r"^(?P<d>\d{1,2})/(?P<m>\d{1,2})/(?P<y>\d{4})$"),
}
_DATEISH = re.compile(r"\d{1,4}[-/.]\d{1,2}[-/.]\d{1,4}|^\d{8}$|(?:^|[^a-z])(?:jan|feb|mar|apr|may|jun|jul|aug|sep|"
                      r"oct|nov|dec)[a-z]*\.?,?\s+\d|\d\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)",
                      re.IGNORECASE)

UNLINKED = ("participants.tsv and phenotype tables could not be linked to the imported subjects (the input has "
            "no sub- folders): their rows are dropped and only the column descriptions are kept")
UNREVIEWED_TEXT = "kept columns are only redacted for known identifiers; other personal text may remain"
NO_PARTICIPANT_ID = NOT_UPLOADABLE + "not linked by participant_id: cannot be de-identified per subject"
RAGGED = NOT_UPLOADABLE + "some rows do not have as many fields as the header"
LINK = NOT_UPLOADABLE + "a symbolic link (links are never followed)"
NO_IMAGE = NOT_UPLOADABLE + "no imaging file in this import matches it"


def path_terms(terms: set[str]) -> set[str]:
    """Terms checked in output names: short numbers ("01") would match the generated labels."""
    return {t for t in terms if not (t.isdigit() and len(t) < PATH_NUMERIC_MIN)}


def _inside(path: Path, root: Path) -> bool:
    return root == path or root in path.parents


def _skipped_name(name: str) -> bool:
    return name.startswith(".") or KEY_NAME in name


# --- the BIDS root, links and safe sources --------------------------------------------

def bids_root(input_dir: Path) -> Path:
    """input_dir, or the first folder up to ROOT_DEPTH levels below it with a dataset_description.json.

    Links, hidden folders, sourcedata/ and derivatives/ are not searched.
    """
    input_dir = Path(input_dir)
    level = [input_dir]
    for _ in range(ROOT_DEPTH + 1):
        nxt = []
        for d in level:
            dd = d / "dataset_description.json"
            if dd.is_file() and not dd.is_symlink():
                return d
            try:
                children = sorted(d.iterdir())
            except OSError:
                continue
            nxt += [c for c in children if c.is_dir() and not c.is_symlink() and not _skipped_name(c.name)
                    and c.name not in NEVER_KEEP]
        level = nxt
    return input_dir


def _forbidden(path: Path, root: Path) -> bool:
    """A path whose real location is under sourcedata/ or derivatives/, outside root, or names a key."""
    real, base = path.resolve(), root.resolve()
    if not _inside(real, base) or any(KEY_NAME in part for part in real.parts):
        return True
    rel = real.relative_to(base).parts
    return bool(rel) and rel[0] in NEVER_KEEP


def _safe_source(root: Path, rel: str) -> Path:
    """root/rel when no component below root is a link and it is not forbidden; ValueError otherwise."""
    cur = root
    for part in rel.split("/"):
        cur = cur / part
        if cur.is_symlink():
            raise ValueError(f"symbolic links are never followed: {rel}")
    if _forbidden(cur, root):
        raise ValueError(f"never read: {rel}")
    return cur


def _children(directory: Path) -> list[Path]:
    """Entries of directory, minus hidden files and key files (links included, never followed)."""
    try:
        return [c for c in sorted(directory.iterdir()) if not _skipped_name(c.name)]
    except OSError:
        return []


def _folder_walk(src: Path, root: Path) -> tuple[list[Path], list[Path]]:
    """(files, links) under a folder; links are listed, never followed; forbidden files are left out."""
    files, links = [], []
    for dirpath, dirnames, filenames in os.walk(src, followlinks=False):
        here = Path(dirpath)
        keep = []
        for d in sorted(dirnames):
            if (here / d).is_symlink():
                links.append(here / d)
            elif not _skipped_name(d):
                keep.append(d)
        dirnames[:] = keep
        for name in sorted(filenames):
            f = here / name
            if f.is_symlink():
                links.append(f)
            elif not _skipped_name(name) and not _forbidden(f, root):
                files.append(f)
    return files, links


# --- detection ---------------------------------------------------------------------

def _split_ext(name: str) -> tuple[str, str] | None:
    for ext in COMPANION_EXTS:
        if name.endswith(ext):
            return name[: -len(ext)], ext
    return None


def _entity_file(name: str, prefix: str, schema: Schema) -> tuple[str, str] | None:
    """(entities, suffix) of a .json/.tsv/.tsv.gz named prefix + entities + suffix, else None."""
    split = _split_ext(name)
    if not name.startswith(prefix) or split is None:
        return None
    m = _ENTITY_STEM.match(split[0][len(prefix):])
    if not m or not schema.is_suffix(m.group(2)):
        return None
    return m.group(1), m.group(2)


def _level_file(name: str, prefix: str, tables: tuple[str, ...], schema: Schema) -> bool:
    """A file directly in a sub-/ses- folder: a sessions/scans table or an inherited sidecar."""
    parts = _entity_file(name, prefix, schema)
    if parts is None or name.endswith(".tsv.gz"):
        return False
    entities, suffix = parts
    if suffix in SUB_TABLES:
        return suffix in tables and entities == ""
    return True


def _root_inherited(name: str, schema: Schema) -> bool:
    parts = _entity_file(name, "", schema)
    return (parts is not None and not name.startswith("sub-") and not name.endswith(".tsv.gz")
            and parts[1] not in SUB_TABLES)


def _root_names(schema: Schema) -> dict[str, str]:
    """File or folder name at the dataset root -> its rule in rules.files.common."""
    names = {}
    for rule_name, rule in schema.common_rules().items():
        if "path" in rule:
            names[rule["path"]] = rule_name
        elif "stem" in rule and not rule.get("datatypes"):
            for ext in rule.get("extensions", []):
                names[rule["stem"] + ext] = rule_name
    return names


def find_ancillary(input_dir: Path, schema: Schema, exclude: Sequence[str] = (),
                   hidden: list[Path] | None = None) -> list[Path]:
    """Ancillary files and folders under the BIDS root of input_dir (paths start with that root).

    The root: rules.files.common.core/tables (files, and code/ docs/ stimuli/ logs/ sourcedata/
    derivatives/ as folders), phenotype/*.tsv|json and inherited sidecars/events; sub-*/: sessions
    and scans tables and inherited sidecars; sub-*/ses-*/: scans and inherited sidecars;
    sub-*/[ses-*/]<datatype>/: per-run companions (events, physio, ...; not the images' own
    sidecars). Hidden files and *aimport-key* are skipped. Links that match are returned (and
    planned as not uploadable); links are never followed into. Nothing under a claimed root (exclude,
    input-relative), and no folder or link leading to one, is returned; hidden, when given, gets the
    folders and links left out only because they hold a claimed root (sourcedata/ with microscopy).
    """
    root = bids_root(input_dir)
    if not root.is_dir():
        return []
    names = _root_names(schema)
    pheno = next((r["datatypes"][0] for r in schema.common_rules().values() if r.get("datatypes")), "phenotype")
    found: list[Path] = []
    for child in _children(root):
        if child.is_symlink():
            if child.name in names or _root_inherited(child.name, schema):
                found.append(child)
        elif child.is_dir():
            if child.name in FOLDERS and child.name in names:
                found.append(child)
            elif child.name == pheno:
                found += [f for f in _children(child) if (f.is_symlink() or f.is_file())
                          and f.name.endswith((".tsv", ".json"))]
            elif _SUB_DIR.match(child.name):
                found += _subject_files(child, schema)
        elif child.is_file() and child.name not in FOLDERS and (child.name in names
                                                                or _root_inherited(child.name, schema)):
            found.append(child)
    if exclude:
        claimed = ClaimedPaths(input_dir, exclude)
        kept = []
        for p in found:
            if not claimed.reaches(p):
                kept.append(p)
            elif hidden is not None and not claimed.covers(p):
                hidden.append(p)
        found = kept
    return found


def _subject_files(sub: Path, schema: Schema) -> list[Path]:
    found = []
    for f in _children(sub):
        if (f.is_symlink() or f.is_file()) and _level_file(f.name, sub.name + "_", SUB_TABLES, schema):
            found.append(f)
        elif f.is_dir() and not f.is_symlink() and _SES_DIR.match(f.name):
            prefix = f"{sub.name}_{f.name}_"
            for g in _children(f):
                if (g.is_symlink() or g.is_file()) and _level_file(g.name, prefix, ("scans",), schema):
                    found.append(g)
                elif g.is_dir() and not g.is_symlink() and schema.is_datatype(g.name):
                    found += _run_files(g, prefix, schema)
        elif f.is_dir() and not f.is_symlink() and schema.is_datatype(f.name):
            found += _run_files(f, sub.name + "_", schema)
    return found


def _run_files(folder: Path, prefix: str, schema: Schema) -> list[Path]:
    """Per-run companions in a datatype folder; an image's own .json sidecar is not one."""
    children = _children(folder)
    names = {c.name for c in children}
    found = []
    for f in children:
        if not (f.is_symlink() or f.is_file()) or _entity_file(f.name, prefix, schema) is None:
            continue
        stem, ext = _split_ext(f.name)
        if ext == ".json" and any(stem + e in names for e in IMAGE_EXTS):
            continue
        found.append(f)
    return found


# --- subjects, sessions and images of this import ------------------------------------------

@dataclass
class ImportMap:
    """Who and what this import holds. Never stored: labels are the input's own."""

    labels: dict[int, str] = field(default_factory=dict)  # subject_idx -> original sub- folder label
    subjects: dict[int, str] = field(default_factory=dict)  # subject_idx -> plan subject
    session_labels: dict[tuple[int, int], str] = field(default_factory=dict)  # -> original ses- folder label
    sessions: dict[tuple[int, int], str] = field(default_factory=dict)  # (subject_idx, session_idx) -> plan session
    images: dict[str, str | None] = field(default_factory=dict)  # input-relative image -> written path (or None)

    @property
    def subject_map(self) -> dict[str, str]:
        return {label: self.subjects[i] for i, label in self.labels.items() if i in self.subjects}

    @property
    def session_map(self) -> dict[tuple[str, str], str]:
        return {(self.labels[i], label): self.sessions[(i, j)] for (i, j), label in self.session_labels.items()
                if i in self.labels and (i, j) in self.sessions}

    def subject_idx(self, label: str) -> int | None:
        return next((i for i, lab in self.labels.items() if lab == label and i in self.subjects), None)

    def session_idx(self, i: int, label: str) -> int | None:
        return next((j for (si, j), lab in self.session_labels.items()
                     if si == i and lab == label and (i, j) in self.sessions), None)


def _folder(paths: list[str], prefix: str, label) -> str | None:
    """The label as spelled by a <prefix>-<label> folder in paths, else None."""
    if not isinstance(label, str) or not label:
        return None
    want = f"{prefix}-{label}".lower()
    for path in paths:
        for part in Path(path).parts:
            if part.lower() == want:
                return part[len(prefix) + 1:]
    return None


def id_maps(core: CoreResult, entries: list[PlanEntry], written: dict[str, str] | None = None) -> ImportMap:
    """The ImportMap of these plan entries.

    Only subjects whose input had a sub-<label> folder (and sessions with a ses-<label> folder) get
    an original label; a label or an index that would map two ways is left out, so its rows and
    files are dropped. written (input-relative image -> written path) comes from the writer; without
    it the images are those of the entries' ezBIDS objects.
    """
    by_idx = {s.subject_idx: s for s in core.subjects}
    ids = ImportMap()
    bad: set = set()
    for e in entries:
        if ids.subjects.setdefault(e.subject_idx, e.subject) != e.subject:
            bad.add(e.subject_idx)
        if e.session and ids.sessions.setdefault((e.subject_idx, e.session_idx), e.session) != e.session:
            bad.add((e.subject_idx, e.session_idx))
        s = by_idx.get(e.subject_idx)
        if s is None:
            continue
        paths = [str(i.get("file_directory", "")) for i in s.patient_info]
        paths += [str(p) for o in core.objects if o.subject_idx == e.subject_idx for p in o.paths]
        label = _folder(paths, "sub", s.label)
        if label is not None:
            ids.labels[e.subject_idx] = label
        if e.session and e.session_idx < len(s.sessions):
            ses_paths = [str(p) for o in core.objects if o.subject_idx == e.subject_idx
                         and o.session_idx == e.session_idx for p in o.paths]
            ses = _folder(ses_paths, "ses", s.sessions[e.session_idx].get("session"))
            if ses is not None:
                ids.session_labels[(e.subject_idx, e.session_idx)] = ses
    counts: dict[str, int] = {}
    for label in ids.labels.values():
        counts[label] = counts.get(label, 0) + 1
    for i in list(ids.labels):
        if counts[ids.labels[i]] > 1 or i in bad:
            del ids.labels[i]
    ses_counts: dict[tuple[int, str], int] = {}
    for (i, _), label in ids.session_labels.items():
        ses_counts[(i, label)] = ses_counts.get((i, label), 0) + 1
    for k in list(ids.session_labels):
        if ses_counts[(k[0], ids.session_labels[k])] > 1 or k in bad:
            del ids.session_labels[k]
    if written is not None:
        ids.images = dict(written)
    else:
        triples = {(e.series_idx, e.subject_idx, e.session_idx) for e in entries}
        ids.images = {os.path.normpath(str(p)): None for o in core.objects
                      if (o.series_idx, o.subject_idx, o.session_idx) in triples
                      for p in o.paths if str(p).endswith(IMAGE_EXTS)}
    return ids


def _tokenize(rel: str, ids: ImportMap) -> str | None:
    """rel with its sub-/ses- labels replaced by tokens; None when not in this import."""
    parts = rel.split("/")
    if not parts[0].startswith("sub-"):
        return rel
    i = ids.subject_idx(parts[0][4:])
    if i is None:
        return None
    pairs = [(parts[0], f"sub-<{i}>")]
    if len(parts) >= 3 and parts[1].startswith("ses-"):
        j = ids.session_idx(i, parts[1][4:])
        if j is None:
            return None
        pairs.append((parts[1], f"ses-<{j}>"))
    out = []
    for part in parts:
        for old, new in pairs:
            part = re.sub(rf"(^|_){re.escape(old)}(?=_|$)", lambda m, new=new: m.group(1) + new, part)
        out.append(part)
    return "/".join(out)


def _untokenize(source: str, ids: ImportMap, original: bool) -> str | None:
    """source with the tokens replaced by the original labels (or the plan's); None if one is unknown."""
    sub = None
    missing = False

    def label(m):
        nonlocal sub, missing
        n = int(m.group(2))
        if m.group(1) == "sub":
            sub = n
            value = ids.labels.get(n) if original else ids.subjects.get(n)
        else:
            value = ids.session_labels.get((sub, n)) if original else ids.sessions.get((sub, n))
        if value is None:
            missing = True
            return m.group(0)
        return f"{m.group(1)}-{value}"

    out = _TOKEN.sub(label, source)
    return None if missing else out


def _token_ids(source: str) -> tuple[int | None, int | None]:
    found = dict((k, int(v)) for k, v in _TOKEN.findall(source))
    return found.get("sub"), found.get("ses")


def _in_datatype(rel: str, schema: Schema) -> bool:
    """A per-run companion: a file inside sub-*/[ses-*/]<datatype>/."""
    parts = rel.split("/")
    return len(parts) >= 3 and parts[0].startswith("sub-") and schema.is_datatype(parts[-2])


def _run_key(path: str) -> tuple[str, str] | None:
    """(folder, entities without suffix and recording-) shared by an image and its companions."""
    folder, _, name = path.rpartition("/")
    for ext in IMAGE_EXTS + COMPANION_EXTS:
        if name.endswith(ext):
            stem = name[: -len(ext)]
            break
    else:
        return None
    if "_" not in stem:
        return None
    return folder, _RECORDING.sub("", stem.rsplit("_", 1)[0])


# --- tables --------------------------------------------------------------------------

def _read_tsv(path: Path) -> tuple[list[str], list[list[str]], bool]:
    """(header, rows, ragged): tab-separated, no quoting; ragged when a row's field count differs."""
    lines = path.read_text(encoding="utf-8-sig", errors="replace").split("\n")
    lines = [ln.rstrip("\r") for ln in lines]
    while lines and not lines[-1].strip():
        lines.pop()
    if not lines:
        return [], [], False
    header = [h.strip() for h in lines[0].split("\t")]
    rows = [[c.strip() for c in ln.split("\t")] for ln in lines[1:] if ln.strip()]
    ragged = any(len(r) != len(header) for r in rows)
    return header, [r + [""] * (len(header) - len(r)) for r in rows], ragged


def _read_gz_rows(path: Path) -> tuple[list[str], bool]:
    """Lines of a headerless .tsv.gz (physio, stim) and whether their field counts differ."""
    with gzip.open(path, "rt", encoding="utf-8", errors="replace") as f:
        lines = [ln.rstrip("\r\n") for ln in f]
    while lines and not lines[-1].strip():
        lines.pop()
    return lines, len({ln.count("\t") for ln in lines}) > 1


def _identifying(header: str) -> bool:
    return bool(IDENTIFYING_COLUMNS.search(header) or _ID_TOKEN.search(header.lower()) or _ID_CAMEL.search(header))


def _month(name: str) -> int | None:
    n = name.lower().rstrip(".")
    if n in _MONTHS:
        return _MONTHS.index(n) + 1
    if n in _MONTH_NAMES:
        return _MONTH_NAMES.index(n) + 1
    return None


def _match_date(value: str, slash: str):
    v = value.strip()
    for rx in [*_DATE_FORMATS, _SLASH[slash]]:
        m = rx.match(v)
        if not m:
            continue
        g = m.groupdict()
        month = _month(g["mon"]) if g.get("mon") else int(g["m"])
        if month is None:
            continue
        try:
            return m, date(int(g["y"]), month, int(g["d"]))
        except ValueError:
            continue
    return None


def _month_like(old: str, month: int) -> str:
    full = _MONTH_NAMES[month - 1] if len(old.rstrip(".")) > 3 else _MONTHS[month - 1]
    if old.isupper():
        return full.upper()
    return full.capitalize() if old[:1].isupper() else full


def shift_date(value: str, days: int, slash: str = "mdy") -> str | None:
    """value shifted by days in its own format, or None when it is not a date.

    Formats: YYYY-MM-DD[Thh:mm[:ss][zone]], YYYYMMDD, YYYY/MM/DD, YYYY.MM.DD, DD.MM.YYYY,
    "20 Sep 2014", "Sep 20, 2014" (month names abbreviated or full), and MM/DD/YYYY or DD/MM/YYYY
    as slash says. Field widths, month-name style and any time are kept.
    """
    found = _match_date(value, slash)
    if found is None:
        return None
    m, day = found
    try:
        new = day + timedelta(days=days)
    except OverflowError:
        return None
    v = value.strip()
    parts = {"y": f"{new.year:04d}"}
    fields = [k for k in ("m", "d") if m.groupdict().get(k) is not None]
    # two digits when the value pads (a leading zero, or an all-numeric date with no 1-digit field)
    padded = not m.groupdict().get("mon") and all(len(m.group(k)) == 2 for k in fields)
    for k, n in (("m", new.month), ("d", new.day)):
        if k in fields:
            parts[k] = f"{n:02d}" if padded or m.group(k).startswith("0") else str(n)
    if m.groupdict().get("mon"):
        parts["mon"] = _month_like(m.group("mon"), new.month)
    out = v
    for k in sorted(parts, key=lambda k: m.start(k), reverse=True):
        out = out[: m.start(k)] + parts[k] + out[m.end(k):]
    return out


def _date_reading(values: list[str]) -> tuple[str, bool]:
    """("mdy"|"dmy", ambiguous) for a column's slash dates: MM/DD unless only DD/MM reads every cell."""
    slashed = [v for v in values if _SLASH["mdy"].match(v.strip())]
    mdy = all(_match_date(v, "mdy") for v in slashed)
    dmy = all(_match_date(v, "dmy") for v in slashed)
    return ("dmy" if dmy and not mdy else "mdy"), bool(slashed) and mdy and dmy


def _date_kind(values: list[str]) -> tuple[str, str, bool] | None:
    """("dates"|"dateish", slash reading, ambiguous) for a column's non-n/a cells, else None."""
    vals = [v for v in values if v and v.lower() != NA]
    if not vals:
        return None
    slash, ambiguous = _date_reading(vals)
    parsed = [v for v in vals if _match_date(v, slash)]
    dateish = [v for v in vals if _DATEISH.search(v)]
    if len(parsed) >= DATE_SHARE * len(vals) and all(_match_date(v, slash) for v in dateish):
        return "dates", slash, ambiguous
    if len(dateish) >= DATEISH_SHARE * len(vals):
        return "dateish", slash, False
    return None


def _free_text(values: list[str]) -> bool:
    vals = [v for v in values if v and v.lower() != NA]
    return bool(vals) and sum(len(v.split()) >= FREE_TEXT_WORDS for v in vals) > FREE_TEXT_SHARE * len(vals)


def _age_cap(header: str) -> int | None:
    """The cap for an age column (89 years, or in months/weeks/days), else None.

    "age" not followed by a letter, at the start or after a non-letter (age, age_months, Scan_Age)
    or after a known prefix in any case (PatientAge, SCANAGE, subjectage); not image, STAGE,
    TUMOR_STAGE, percentage or AverageAge.
    """
    lower = header.lower()
    for m in _AGE.finditer(header):
        i = m.start()
        if i == 0 or not lower[i - 1].isalpha() or lower[:i].endswith(_AGE_PREFIXES):
            return AGE_CAP * next((n for unit, n in _AGE_UNITS if unit in lower), 1)
    return None


def _cap(value: str, cap: int) -> str:
    m = _LEADING_NUMBER.match(value)
    return str(cap) if m and float(m.group(1)) > cap else value


def _label(value: str, prefix: str) -> str:
    v = value.strip()
    return v[len(prefix) + 1:] if v.startswith(prefix + "-") else v


def column_lock(header: str, values: list[str], terms: set[str]) -> list[str] | None:
    """The only actions a column allows, derived from the file itself (planner and writer both use it).

    A header holding a term: drop. A key column: keep (it is rewritten). Dates: shift_date or drop.
    Date-like values that cannot all be read: drop. Anything else: None (no lock).
    """
    if redact(header, terms) != header:
        return ["drop"]
    if header in KEY_COLUMNS:
        return ["keep"]
    dates = _date_kind(values)
    if dates is None:
        return None
    return ["shift_date", "drop"] if dates[0] == "dates" else ["drop"]


def _needs_participant_id(rel: str) -> bool:
    """participants, samples and phenotype tables must link their rows by participant_id."""
    parts = rel.split("/")
    return parts[0] == "phenotype" or (len(parts) == 1 and parts[0][: -len(".tsv")] in TABLE_STEMS)


def _column_defaults(header: list[str], rows: list[list[str]],
                     terms: set[str]) -> tuple[dict, list[str], dict[str, list[str]]]:
    columns, flags, locks = {}, [], {}
    for i, h in enumerate(header):
        if not h:
            continue  # never written
        values = [r[i] for r in rows]
        lock = column_lock(h, values, terms)
        key = redact(h, terms)
        if lock is not None:
            locks[key] = lock
        if key != h:
            columns[key] = "drop"
            flags.append("a column name holds an identifying value: it is always dropped")
            continue
        if h in KEY_COLUMNS:
            columns[h] = "keep"
            continue
        dates = _date_kind(values)
        if dates is not None and dates[0] == "dates":
            note = " (read as MM/DD/YYYY; could also be DD/MM/YYYY)" if dates[2] else ""
            flags.append(f"{DATE_COLUMN}{h!r}: shifted by each subject's date offset{note}")
        elif dates is not None:
            flags.append(f"{DATE_COLUMN}{h!r} looks like dates that cannot all be read: dropped by default")
        if _identifying(h):
            columns[h] = "drop"
            flags.append(f"column {h!r} looks identifying: dropped by default (if kept, its values are still redacted)")
        elif dates is not None:
            columns[h] = "shift_date" if dates[0] == "dates" else "drop"
        elif _free_text(values):
            columns[h] = "drop"
            flags.append(f"column {h!r} holds free text: dropped by default")
        else:
            columns[h] = "keep"
    flags.append(UNREVIEWED_TEXT)
    return columns, flags, locks


# --- planning ------------------------------------------------------------------------

def _kind(rel: str, is_dir: bool, names: dict[str, str], schema: Schema) -> str:
    parts = rel.split("/")
    name = parts[-1]
    split = _split_ext(name)
    stem, ext = split if split else (name, "")
    suffix = stem.rsplit("_", 1)[-1]
    if is_dir:
        return "folder"
    if parts[0] == "phenotype":
        return "phenotype" if ext == ".tsv" else "phenotype_json"
    if len(parts) == 1 and stem in TABLE_STEMS:
        return "table" if ext == ".tsv" else "table_json"
    if len(parts) >= 2 and schema.is_datatype(parts[-2]):
        return "events" if suffix == "events" else "companion"
    if parts[0].startswith("sub-") and suffix in SUB_TABLES:
        return "table" if ext == ".tsv" else "table_json"
    if len(parts) == 1 and name in names:
        return "core"
    return "events" if suffix == "events" else "inherited_sidecar"


def _is_text(data: bytes) -> str | None:
    if b"\0" in data:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None


def _head(path: Path, size: int = 8192) -> bytes:
    with open(path, "rb") as f:
        data = f.read(size)
    while data and (data[-1] & 0xC0) == 0x80:  # do not cut a UTF-8 character in two
        data = data[:-1]
    return data[:-1] if data and data[-1] >= 0xC0 else data


def plan_ancillary(paths: list[Path], input_dir: Path, terms: set[str], ids: ImportMap,
                   schema: Schema) -> list[AncillaryEntry]:
    """Default entries for the files find_ancillary found (see the module docstring)."""
    input_dir = Path(input_dir)
    root = bids_root(input_dir)
    prefix = _prefix(input_dir, root)
    names = _root_names(schema)
    pterms = path_terms(terms)
    image_keys = {_run_key(p) for p in ids.images}
    entries: list[AncillaryEntry] = []
    for p in paths:
        p = Path(p)
        rel = p.relative_to(root).as_posix()
        if rel == "dataset_description.json":
            continue  # its fields are Plan.dataset_description
        source = _tokenize(rel, ids)
        out = _untokenize(source, ids, original=False) if source is not None else None
        if out is None or redact(out, pterms) != out or redact(source, pterms) != source:
            continue  # not in this import, or the name itself is identifying
        kind = _kind(rel, p.is_dir() and not p.is_symlink(), names, schema)
        a = AncillaryEntry(id=f"a{len(entries)}", path=out, source=source, kind=kind, action="keep", columns={},
                           content=None, flags=[], reason="redacted copy", locked=False, locked_columns={})
        if p.is_symlink():
            _lock(a, LINK)
        elif _in_datatype(rel, schema) and _run_key(prefix + rel) not in image_keys:
            _lock(a, NO_IMAGE)
        else:
            _defaults(a, p, rel, root, terms, ids)
            if _in_datatype(rel, schema):
                a.reason = "written next to its imaging file, under that file's new name; " + a.reason
        entries.append(a)
    locked = {e.source for e in entries if e.locked}
    for e in entries:  # the description of a table that is not uploaded is not uploaded either
        if e.source.endswith(".json") and e.source[: -len(".json")] + ".tsv" in locked:
            _lock(e, NOT_UPLOADABLE + "its table is not uploaded")
    return entries


def _lock(a: AncillaryEntry, flag: str) -> None:
    """Not uploadable: dropped, and no edit can keep it."""
    a.action, a.reason, a.locked = "drop", "not uploaded", True
    a.flags.insert(0, flag)


def _prefix(input_dir: Path, root: Path) -> str:
    rel = root.relative_to(input_dir).as_posix()
    return "" if rel == "." else rel + "/"


def _defaults(a: AncillaryEntry, p: Path, rel: str, root: Path, terms: set[str], ids: ImportMap) -> None:
    if a.kind == "folder":
        a.action = "drop"
        if rel == "sourcedata":
            a.reason, a.locked = "sourcedata/ holds the raw, identifying data and is never uploaded", True
        elif rel == "derivatives":
            a.reason, a.locked = "derivatives are not imported in phase 1", True
        else:
            _folder_defaults(a, p, rel, root, terms)
        return
    if a.path.endswith(".json"):
        try:
            ok = isinstance(json.loads(p.read_text(encoding="utf-8-sig")), dict)
        except (ValueError, UnicodeDecodeError):
            ok = False
        if not ok:
            a.action, a.reason = "drop", "not a valid JSON object: not uploaded"
        return
    if a.path.endswith(".tsv.gz"):
        _, ragged = _read_gz_rows(p)
        if ragged:
            _lock(a, RAGGED)
        else:
            a.reason = "every line holding an identifying value is cleared field by field"
        return
    if not a.path.endswith(".tsv"):
        return
    header, rows, ragged = _read_tsv(p)
    if not header:
        a.action, a.reason = "drop", "empty table: not uploaded"
        return
    a.columns, a.flags, a.locked_columns = _column_defaults(header, rows, terms)
    a.reason = "rebuilt: IDs rewritten, rows of people not in this import dropped, every cell redacted"
    if ragged:
        _lock(a, RAGGED)
        return
    if _needs_participant_id(rel) and "participant_id" not in header:
        _lock(a, NO_PARTICIPANT_ID)
        return
    if rel.split("/")[-1].endswith("_scans.tsv"):
        a.reason = "merged into the scans.tsv the importer writes; rows for files it does not write are dropped"
    subject_map, session_map = ids.subject_map, ids.session_map
    if "participant_id" in header:
        i = header.index("participant_id")
        unknown = sum(_label(r[i], "sub") not in subject_map for r in rows)
        if not subject_map:
            a.flags.append("rows cannot be linked to the imported subjects: rows dropped, column descriptions kept")
        elif unknown:
            a.flags.append(f"{unknown} row(s) for people not in this import are dropped")
    if "session_id" in header and rel.startswith("sub-"):
        i, sub = header.index("session_id"), rel.split("/")[0][4:]
        unknown = sum((sub, _label(r[i], "ses")) not in session_map for r in rows)
        if unknown:
            a.flags.append(f"{unknown} row(s) for sessions not in this import are dropped")


def _folder_defaults(a: AncillaryEntry, p: Path, rel: str, root: Path, terms: set[str]) -> None:
    files, links = _folder_walk(p, root)
    text_only = rel in TEXT_ONLY_FOLDERS
    a.reason = (f"{rel}/ is uploaded only if you keep it; text files are redacted"
                + ("; binary files are never uploaded from it" if text_only else
                   "; binary files are copied as they are"))
    binary = [f for f in files if _is_text(_head(f)) is None]
    a.flags.append(f"{len(files)} files, {len(binary)} of them binary")
    for f in binary:
        name = redact(f.relative_to(root).as_posix(), terms)
        a.flags.append(f"binary file not uploaded: {name}" if text_only else
                       f"binary file copied as it is if kept: {name}")
    for f in links:
        a.flags.append(f"symbolic link skipped (links are never followed): {redact(f.relative_to(root).as_posix(), terms)}")


def ancillary_warnings(entries: list[AncillaryEntry], ids: ImportMap) -> list[str]:
    if not ids.subject_map and any("participant_id" in a.columns for a in entries):
        return [UNLINKED]
    return []


def clean_json(data: dict, terms: set[str]) -> dict:
    """scrub_sidecar (drop identifying keys, redact values), then drop keys that hold a term."""
    def keys(value):
        if isinstance(value, dict):
            return {k: keys(v) for k, v in value.items() if redact(str(k), terms) == str(k)}
        if isinstance(value, list):
            return [keys(v) for v in value]
        return value

    return keys(scrub_sidecar(data, terms))


def read_dataset_description(input_dir: Path, terms: set[str]) -> tuple[str | None, dict]:
    """(redacted Name or None, the redacted DESCRIPTION_FIELDS) from the BIDS root's dataset_description.json."""
    root = bids_root(input_dir)
    path = root / "dataset_description.json"
    if path.is_symlink() or not path.is_file() or _forbidden(path, root):
        return None, {}
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (ValueError, UnicodeDecodeError):
        return None, {}
    if not isinstance(data, dict):
        return None, {}
    data = clean_json(data, terms)
    name = data.get("Name")
    name = name.strip() if isinstance(name, str) and name.strip() else None
    return name, {k: data[k] for k in DESCRIPTION_FIELDS if k in data}


# --- writing -------------------------------------------------------------------------

@dataclass
class Generated:
    """What the BIDS writer generates for the top level; merged here with the supplied files."""

    tables: dict[str, list[list[str]]] = field(default_factory=dict)  # rel -> rows, header first
    jsons: dict[str, dict] = field(default_factory=dict)
    texts: dict[str, str] = field(default_factory=dict)


def _merge(generated: list[list[str]], header: list[str], rows: list[dict], key: str) -> tuple[list[str], list[dict]]:
    """Generated participants rows (in their order) with the supplied columns; supplied values win
    unless empty or n/a; supplied rows of other subjects are appended."""
    g_header, g_rows = generated[0], [dict(zip(generated[0], r)) for r in generated[1:]]
    out_header = [key] + [h for h in header if h != key] + [h for h in g_header if h not in header and h != key]
    by_key: dict[str, dict] = {}
    for r in rows:
        by_key.setdefault(r.get(key, ""), r)
    out = []
    for g in g_rows:
        s = by_key.pop(g.get(key, ""), {})
        row = {}
        for h in out_header:
            first, second = s.get(h), g.get(h)
            row[h] = first if first not in (None, "", NA) else (second if second not in (None, "") else NA)
        out.append(row)
    out += [{h: r.get(h, NA) for h in out_header} for r in by_key.values()]
    return out_header, out


class _AncillaryWriter:
    def __init__(self, plan: Plan, input_dir: Path, out_dir: Path, terms: set[str], ids: ImportMap,
                 key: PseudonymKey, schema: Schema, generated: Generated | None):
        self.plan, self.terms, self.key, self.ids, self.schema = plan, terms, key, ids, schema
        self.pterms = path_terms(terms)
        self.input_dir = Path(input_dir)
        self.root = bids_root(self.input_dir)
        self.prefix = _prefix(self.input_dir, self.root)
        self.out_dir = Path(out_dir).resolve()
        self.subject_map, self.session_map = ids.subject_map, ids.session_map
        self.gen = generated or Generated()
        self.written: list[Path] = []
        self.headers: dict[str, list[str]] = {}  # written table -> its header
        self.from_generated: dict[str, set[str]] = {}  # written table -> columns that came from the importer
        self.scans_extra: dict[str, tuple[list[str], dict[str, dict]]] = {}  # generated scans -> supplied columns
        self.refused: list[str] = []  # files not written although the plan kept them, and why
        self.refused_paths: set[str] = set()
        self.found: dict[str, str] = {}  # source (tokens) -> path relative to the BIDS root
        for p in find_ancillary(self.input_dir, schema):
            rel = p.relative_to(self.root).as_posix()
            source = _tokenize(rel, ids)
            if source is not None:
                self.found[source] = rel
        self.images: dict[tuple[str, str], list[str]] = {}  # run key -> written images
        for src, dest in ids.images.items():
            k = _run_key(src)
            if k is not None and dest is not None:
                self.images.setdefault(k, []).append(dest)

    # --- guarded paths ---

    def dest(self, rel: str) -> Path:
        path = Path(os.path.normpath(self.out_dir / rel))
        if not _inside(path, self.out_dir) or path == self.out_dir:
            raise ValueError(f"destination outside the output folder: {rel}")
        if redact(rel, self.pterms) != rel:
            raise ValueError(f"destination name contains an identifying value: {rel}")
        if rel.split("/")[0] in NEVER_KEEP or KEY_NAME in rel:
            raise ValueError(f"never written: {rel}")
        if path.exists():
            raise FileExistsError(f"already written: {rel}")
        path.parent.mkdir(parents=True, exist_ok=True)
        self.written.append(path)
        return path

    def source(self, a: AncillaryEntry) -> Path:
        return _safe_source(self.root, self.found[a.source])

    def destination(self, a: AncillaryEntry) -> str | None:
        """Where an entry goes in this import (from the current plan), None when nowhere."""
        rel = self.found[a.source]
        if _in_datatype(rel, self.schema):
            return self.companion_dest(rel)
        return _untokenize(a.source, self.ids, original=False)

    def companion_dest(self, rel: str) -> str | None:
        """The written image's new name with the companion's own recording- entity, suffix and extension."""
        images = self.images.get(_run_key(self.prefix + rel), [])
        bases = {i.rsplit("/", 1)[0] + "/" + i.rsplit("/", 1)[1].split(".")[0].rsplit("_", 1)[0] for i in images}
        if len(bases) != 1:
            return None
        stem, ext = _split_ext(rel.rsplit("/", 1)[-1])
        recording = _RECORDING.search(stem)
        return bases.pop() + (recording.group(0) if recording else "") + "_" + stem.rsplit("_", 1)[1] + ext

    def refuse(self, a: AncillaryEntry, dest: str, why: str) -> None:
        self.refused.append(f"{a.path}: not written: {why}")
        self.refused_paths.add(dest)

    def write_text(self, rel: str, text: str) -> None:
        self.dest(rel).write_text(redact(text, self.terms), encoding="utf-8")

    def write_json(self, rel: str, data: dict) -> None:
        self.dest(rel).write_text(json.dumps(clean_json(data, self.terms), indent=2, ensure_ascii=False) + "\n",
                                  encoding="utf-8")

    def cell(self, column: str, value) -> str:
        v = str(value if value is not None else "").strip()
        if not v:
            return NA
        terms = self.pterms if column in KEY_COLUMNS else self.terms  # pseudonyms: short numbers are labels
        return v if redact(v, terms) == v else NA

    def write_rows(self, rel: str, header: list[str], rows: list[dict]) -> None:
        lines = ["\t".join(header)] + ["\t".join(self.cell(h, r.get(h)) for h in header) for r in rows]
        self.dest(rel).write_text("".join(ln + "\n" for ln in lines), encoding="utf-8")
        self.headers[rel] = header

    # --- run ---

    def run(self) -> list[Path]:
        for a in self.plan.ancillary:
            if a.action == "drop":
                continue
            if a.path.split("/")[0] in NEVER_KEEP or a.source.split("/")[0] in NEVER_KEEP:
                raise ValueError(f"{a.path}/ is never uploaded")
            if a.locked:
                raise ValueError(f"{a.path} is not uploadable: it can only be dropped ({a.reason})")
        todo = []
        for a in self.plan.ancillary:
            if a.action != "drop" and a.source in self.found:
                dest = self.destination(a)
                if dest is not None:
                    todo.append((a, dest))
        self.table_entries = {dest: a for a, dest in todo if dest.endswith(".tsv")}
        for a, dest in todo:
            if a.kind != "folder" and dest.endswith((".tsv", ".tsv.gz")):
                self.table(a, dest)
        for rel, rows in list(self.gen.tables.items()):
            header, extra = rows[0], self.scans_extra.get(rel)
            body = [dict(zip(rows[0], r)) for r in rows[1:]]
            if extra:
                header = header + [h for h in extra[0] if h not in header]
                body = [{**extra[1].get(r.get("filename"), {}), **r} for r in body]
            self.write_rows(rel, header, body)
            self.from_generated[rel] = set(rows[0])
        for a, dest in todo:
            if a.kind != "folder" and dest.endswith(".json"):
                self.json_file(a, dest)
        for rel, data in list(self.gen.jsons.items()):
            if rel == "dataset_description.json":
                continue
            data = self.describe_generated(rel, data, {})
            if data:
                self.write_json(rel, data)
        dd = self.gen.jsons.get("dataset_description.json") or {
            "Name": self.plan.dataset_name, "BIDSVersion": BIDS_VERSION, "GeneratedBy": [{"Name": "brainlife.io/aimport"}]}
        dd = {**dd, **{k: self.plan.dataset_description[k] for k in DESCRIPTION_FIELDS
                       if k in self.plan.dataset_description}}
        self.write_json("dataset_description.json", dd)
        readme = False
        for a, dest in todo:
            if a.kind == "folder":
                self.folder(a, dest)
            elif not dest.endswith((".tsv", ".tsv.gz", ".json")):
                text = a.content if a.content is not None else self.source(a).read_text(encoding="utf-8",
                                                                                         errors="replace")
                self.write_text(dest, text)
                readme |= dest.split(".")[0] == "README"
        for rel, text in self.gen.texts.items():
            if not (readme and rel.split(".")[0] == "README"):  # the supplied README wins
                self.write_text(rel, text)
        return self.written

    def table(self, a: AncillaryEntry, dest: str) -> None:
        src, rel = self.source(a), self.found[a.source]
        if dest.endswith(".tsv.gz"):
            if _read_gz_rows(src)[1]:
                self.refuse(a, dest, "its rows do not all have the same number of fields")
                return
            self.gz_table(src, dest)
            return
        # the privacy rules again, from the file itself: the plan is not trusted for them
        header, rows, ragged = _read_tsv(src)
        if ragged:
            self.refuse(a, dest, "some rows do not have as many fields as the header")
            return
        if _needs_participant_id(rel) and "participant_id" not in header:
            self.refuse(a, dest, "no participant_id column: rows cannot be de-identified per subject")
            return
        sub_i, ses_j = _token_ids(a.source)
        file_sub = self.ids.labels.get(sub_i) if sub_i is not None else None
        file_ses = self.ids.session_labels.get((sub_i, ses_j)) if ses_j is not None else None
        keep = []
        for i, h in enumerate(header):
            act = a.columns.get(h)  # a column the plan does not name is dropped
            lock = column_lock(h, [r[i] for r in rows], self.terms) if h else ["drop"]
            if act in ("keep", "shift_date") and (lock is None or act in lock):
                keep.append((i, h, act))
        slash = {h: _date_reading([r[i] for r in rows])[0] for i, h, act in keep if act == "shift_date"}
        idx = {h: i for i, h in reversed(list(enumerate(header)))}
        out_header = list(dict.fromkeys(h for _, h, _ in keep))
        scans = dest.endswith("_scans.tsv")
        unique = dest.endswith(("participants.tsv", "_sessions.tsv")) or scans
        out, seen = [], set()
        for row in rows:
            ids = self.row_ids(row, idx, file_sub, file_ses, self.found[a.source])
            if ids is None:
                continue
            sub, values = ids
            if unique and tuple(sorted(values.items())) in seen:
                continue
            seen.add(tuple(sorted(values.items())))
            offset = self.key.date_offset_days(sub) if sub else None
            for i, h, act in keep:
                if h in values:
                    continue
                v = row[i]
                if act == "shift_date":
                    v = (shift_date(v, offset, slash[h]) if offset is not None else None) or NA
                cap = _age_cap(h)
                values[h] = _cap(v, cap) if cap else v
            out.append(values)
        if scans:  # merged into the generated scans tables by written file
            for values in out:
                gen_rel, filename = values.pop("filename")
                extra = self.scans_extra.setdefault(gen_rel, ([], {}))
                extra[0].extend(h for h in out_header if h != "filename" and h not in extra[0])
                extra[1].setdefault(filename, values)
            return
        gen = self.gen.tables.pop(dest, None)
        supplied = set(out_header)
        if gen is not None and "participant_id" in gen[0]:
            out_header, out = _merge(gen, out_header, out, "participant_id")
            self.from_generated[dest] = {h for h in out_header if h not in supplied}
        self.write_rows(dest, out_header, out)

    def gz_table(self, src: Path, dest: str) -> None:
        lines, _ = _read_gz_rows(src)
        out = []
        for ln in lines:
            if redact(ln, self.terms) != ln:
                ln = "\t".join(c if redact(c, self.terms) == c else NA for c in ln.split("\t"))
            out.append(ln + "\n")
        with gzip.open(self.dest(dest), "wt", encoding="utf-8") as f:
            f.write("".join(out))

    def row_ids(self, row: list[str], idx: dict[str, int], file_sub: str | None, file_ses: str | None,
                rel: str) -> tuple[str | None, dict] | None:
        """(new subject, rewritten key columns) for a row, or None when the row is not in this import."""
        if "participant_id" not in idx and _needs_participant_id(rel):
            return None  # a person table links its rows by participant_id or not at all
        orig_sub = file_sub
        sub = self.subject_map.get(file_sub) if file_sub else None
        values: dict = {}
        if "participant_id" in idx:
            orig_sub = _label(row[idx["participant_id"]], "sub")
            sub = self.subject_map.get(orig_sub)
            if sub is None:
                return None
            values["participant_id"] = f"sub-{sub}"
        if "session_id" in idx:
            ses = self.session_map.get((orig_sub, _label(row[idx["session_id"]], "ses")))
            if ses is None:
                return None
            values["session_id"] = f"ses-{ses}"
        if "filename" in idx:
            target = self.scans_target(rel, row[idx["filename"]])
            if target is None:
                return None
            values["filename"] = target
        return sub, values

    def scans_target(self, rel: str, filename: str) -> tuple[str, str] | None:
        """(generated scans table, its filename) of the image a supplied scans row names, via what was written."""
        image = os.path.normpath(self.prefix + rel.rsplit("/", 1)[0] + "/" + filename.strip())
        written = self.ids.images.get(image)
        if written is None:
            return None
        for gen_rel in self.gen.tables:
            base = gen_rel.rsplit("/", 1)[0] + "/"
            if gen_rel.endswith("_scans.tsv") and written.startswith(base):
                return gen_rel, written[len(base):]
        return None

    def json_file(self, a: AncillaryEntry, dest: str) -> None:
        if a.content is not None:
            data = a.content
        else:
            try:
                data = json.loads(self.source(a).read_text(encoding="utf-8-sig"))
            except (ValueError, UnicodeDecodeError) as exc:
                raise ValueError(f"{a.path}: not valid JSON") from exc
        if not isinstance(data, dict):
            raise ValueError(f"{a.path}: not a JSON object")
        data = clean_json(data, self.terms)
        table = dest[: -len(".json")] + ".tsv"
        if table in self.refused_paths:
            self.refuse(a, dest, "its table is not uploaded")
            return
        companion = self.table_entries.get(table) or next(
            (t for t in self.plan.ancillary if t.source == a.source[: -len(".json")] + ".tsv"), None)
        if companion is not None:  # descriptions of supplied columns that are not written (or now generated)
            kept = set(self.headers.get(table, [])) - self.from_generated.get(table, set())
            gone = set(companion.columns) - kept
            data = {k: v for k, v in data.items() if k not in gone}
        data = self.describe_generated(dest, self.gen.jsons.pop(dest, {}), data)
        self.write_json(dest, data)

    def describe_generated(self, rel: str, generated: dict, data: dict) -> dict:
        """data plus the importer's descriptions of the columns the importer filled."""
        table = rel[: -len(".json")] + ".tsv"
        filled = self.from_generated.get(table)
        out = dict(data)
        for k, v in generated.items():
            if k not in out and (filled is None or k in filled):
                out[k] = v
        return out

    def folder(self, a: AncillaryEntry, dest: str) -> None:
        src = self.source(a)
        text_only = dest in TEXT_ONLY_FOLDERS
        files, _links = _folder_walk(src, self.root)
        for f in files:
            rel = f"{dest}/{f.relative_to(src).as_posix()}"
            if redact(rel, self.pterms) != rel:
                continue  # its name is identifying
            data = f.read_bytes()
            text = _is_text(data)
            if text is not None:
                self.write_text(rel, text)
            elif not text_only:
                self.dest(rel).write_bytes(data)


def write_ancillary(plan: Plan, input_dir: Path, out_dir: Path, terms: set[str], ids: ImportMap,
                    key: PseudonymKey, *, schema: Schema, generated: Generated | None = None,
                    refused: list[str] | None = None) -> list[Path]:
    """Write the plan's ancillary entries, merged with what the writer generated; returns the files written.

    ids holds only the subjects, sessions and images written in this import (with the written
    image paths), so rows and files of anyone else are dropped and companions follow their images.
    Raises ValueError for an entry that is not uploadable but not set to drop (sourcedata/,
    derivatives/, links, unlinked or ragged tables), a source reached through a link, and any
    destination outside out_dir or with an identifying name. The table and column rules are derived
    again from each source file (participant_id required, no ragged rows, dates only shifted); a
    table refused here is skipped and its reason appended to refused.
    """
    writer = _AncillaryWriter(plan, input_dir, out_dir, terms, ids, key, schema, generated)
    written = writer.run()
    if refused is not None:
        refused.extend(writer.refused)
    return written
