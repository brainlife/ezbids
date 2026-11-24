"""The import plan: one entry per series, editable by the person."""
from __future__ import annotations

import json
import math
import re
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Literal

LOCKED_FIELDS = {"id", "series_idx", "subject_idx", "session_idx"}
# the only PlanEntry fields a reviewer may edit, with the type each value must have ("?" also allows None).
# Everything else (status, source, confidence, reason, agent_note, description, deface_opt_out,
# brainlife_by_person and the indices) is derived: planner.apply_plan_edits re-derives it after every edit.
EDITABLE_FIELDS = {"subject": "label", "session": "label?", "datatype": "str?", "suffix": "str?",
                   "entities": "dict", "deface": "bool", "exclude": "bool", "brainlife_datatype": "str?",
                   "brainlife_tags": "list", "ephys_format": "str?", "keep_headshape": "bool", "channel_types": "dict",
                   "sample_type": "str?", "pixel_size": "sizes?", "pixel_size_units": "unit?"}
PIXEL_SIZE_UNITS = ("mm", "um", "nm")
_LABEL = re.compile(r"^[a-zA-Z0-9]+$")

# --- ancillary and metadata files (Task 10b) ---
ANCILLARY_ACTIONS = ("keep", "drop", "edit")
COLUMN_ACTIONS = ("keep", "drop", "shift_date")
ANCILLARY_EDITABLE = {"action", "columns", "content"}
ANCILLARY_REQUIRED = {"source", "locked", "locked_columns"}  # absent in plans written before these locks
# sourcedata/ holds the raw, identifying data; derivatives/ are out of scope for phase 1
NEVER_KEEP = ("sourcedata", "derivatives")
# columns that link rows to subjects, sessions, samples and files: rewritten, never dropped
KEY_COLUMNS = ("participant_id", "session_id", "sample_id", "filename")
# dataset_description.json fields the reviewer edits; Name lives in Plan.dataset_name
DESCRIPTION_FIELDS = ("Authors", "License", "Funding", "EthicsApprovals", "ReferencesAndLinks", "DatasetDOI",
                      "HowToAcknowledge", "Acknowledgements")
REDACTED_MARK = "[x]"  # scrub.REDACTED: a column header that held an identifying value
# Wording of reviewer-facing flags only; locks live in AncillaryEntry.locked/locked_columns, never in flag text.
NOT_UPLOADABLE = "not uploadable: "
DATE_COLUMN = "date column "
OLD_PLAN = "plan format from an older aimport; re-scan the input"
# a reviewer's display name for an event code (ephys events, Task 5)
# the BIDS subject of MEG empty-room recordings: a literal label, never from the key nor a project subject
EMPTY_ROOM_SUBJECT = "emptyroom"
EVENT_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _./+-]{0,39}$")


@dataclass
class PlanEntry:
    id: str
    series_idx: int
    subject_idx: int
    session_idx: int
    subject: str
    session: str | None
    datatype: str | None
    suffix: str | None
    entities: dict[str, str]
    brainlife_datatype: str | None
    brainlife_tags: list[str]
    source: Literal["heuristic", "agent", "person", "none"]
    confidence: float
    reason: str
    deface: bool
    exclude: bool
    status: Literal["ok", "unknown", "unsupported", "excluded_by_default"]
    description: str  # redacted SeriesDescription
    agent_note: str = ""  # set when the agent disagrees with the heuristic
    # True only when the reviewer turned defacing off for an anat entry; the writer refuses an anat
    # entry with deface=False unless this is set
    deface_opt_out: bool = False
    # True once the reviewer set brainlife_datatype or brainlife_tags; later edits keep that mapping
    # until the entry's datatype, suffix or entities change
    brainlife_by_person: bool = False
    # the input's modality: "mri" entries come from ezBIDS; microscopy ("micr") and electrophysiology
    # ("ephys") entries come from modality modules
    modality: Literal["mri", "micr", "ephys"] = "mri"
    sample_type: str | None = None  # micr: a value of the BIDS sample_type enum (planner checks it)
    # micr: "convert" (to OME-Zarr), "reference" (an OME-Zarr kept as is, no copy); "" = not writable
    write_mode: Literal["", "convert", "reference"] = ""
    output_bytes: int = 0  # micr: about how many bytes conversion writes to the work folder
    # ephys: the output format, one of ephys.OUTPUT_FORMATS[datatype]; "" = not writable (unsupported input)
    ephys_format: str = ""
    keep_headshape: bool = False  # ephys (meg, eeg): keep the head-shape digitization points
    event_counts: dict[str, int] = field(default_factory=dict)  # ephys: event label (after coding) -> count
    empty_room: str | None = None  # ephys meg: the id of the paired sub-emptyroom entry
    # ephys head-shape file (.pos/.hsp/.elp), listed but never written on its own: the id of its recording's entry
    # (None: no recording beside it) and the reason shown while that recording's keep_headshape is on
    headshape_of: str | None = None
    headshape_on_reason: str = ""
    # ephys from NWB: electrode group (generated name, group_001) -> channel type (seeg / ecog / dbs), guessed
    # from the group's name and description; the reviewer may change the values (not the groups)
    channel_types: dict[str, str] = field(default_factory=dict)
    # micr: the pixel size (x, y[, z]) in pixel_size_units, from the source or the reviewer; None when
    # the source does not give every spatial axis (the entry is then unknown until the reviewer sets it)
    pixel_size: list[float] | None = None
    pixel_size_units: Literal["mm", "um", "nm"] | None = None
    spatial_axes: str = ""  # micr: the image's spatial axes among "xyz" (derived; the length of pixel_size)


@dataclass
class AncillaryEntry:
    """A non-imaging file or folder of the input, as it will be written (path relative to the output)."""

    id: str
    path: str  # posix, relative to the BIDS root, with the new labels at planning time (shown to the reviewer)
    # posix, relative to the input's BIDS root; sub-/ses- labels are tokens (sub-<subject_idx>, ses-<session_idx>)
    # so no original label is stored; the destination is computed again at write time from the current plan
    source: str
    kind: Literal["core", "table", "table_json", "phenotype", "phenotype_json", "inherited_sidecar", "events",
                  "companion", "folder"]
    action: Literal["keep", "drop", "edit"]
    columns: dict[str, Literal["keep", "drop", "shift_date"]]  # tables only; keyed by the (redacted) header
    content: dict | str | None  # edited JSON/text; None = the de-identified input
    flags: list[str]  # for the reviewer only: no code reads them
    reason: str
    locked: bool  # the entry may only be dropped
    locked_columns: dict[str, list[str]]  # column -> the only actions allowed for it


@dataclass
class Plan:
    target: Literal["bids", "datatypes"]
    entries: list[PlanEntry]
    version: int = 1
    approved: bool = False
    deface_method: Literal["pydeface", "quickshear"] = "pydeface"
    dataset_name: str = "aimport dataset"
    readme: str = ""
    metadata_source: Literal["agent", "person", "none"] = "none"
    warnings: list[str] = field(default_factory=list)  # shown to the reviewer
    ancillary: list[AncillaryEntry] = field(default_factory=list)
    dataset_description: dict = field(default_factory=dict)  # DESCRIPTION_FIELDS only are written
    scan_id: str = ""  # the scan that built this plan (scan.json); only that scan's plan can be executed
    # ephys event code -> display name (default the code); the written trial_type. Never holds original text.
    event_names: dict[str, str] = field(default_factory=dict)

    def save(self, path: Path) -> None:
        Path(path).write_text(json.dumps(asdict(self), indent=2))

    @classmethod
    def load(cls, path: Path) -> Plan:
        data = json.loads(Path(path).read_text())
        data["entries"] = [PlanEntry(**e) for e in data["entries"]]
        ancillary = data.get("ancillary", [])
        if any(not isinstance(a, dict) or not ANCILLARY_REQUIRED <= set(a) for a in ancillary):
            raise ValueError(OLD_PLAN)
        data["ancillary"] = [AncillaryEntry(**a) for a in ancillary]
        return cls(**data)

    def apply_edits(self, edits: list[dict]) -> list[PlanEntry]:
        """Apply reviewer edits to entries; returns every entry changed (a subject edit changes them all).

        Only EDITABLE_FIELDS may be edited, with values of the right type. A subject edit applies to
        every entry of that subject (subject_idx); two edits giving one subject different IDs, or two
        subjects one ID, are refused. A datatype or suffix edit without "deface" resets deface to
        datatype == "anat"; deface=False on an anat entry is recorded as deface_opt_out. A brainlife
        mapping set by the reviewer is kept (brainlife_by_person) until a datatype, suffix or entities
        edit without one. Status and the
        brainlife mapping are re-derived by planner.apply_plan_edits, which callers should use.
        Raises KeyError for an unknown id and ValueError for anything else; a bad edit changes nothing.
        """
        by_id = {e.id: e for e in self.entries}
        known = {f.name for f in fields(PlanEntry)}
        new_subjects: dict[int, str] = {}
        # validate everything first so a bad edit leaves the plan untouched
        for edit in edits:
            if not isinstance(edit, dict) or edit.get("id") not in by_id:
                raise KeyError(edit.get("id") if isinstance(edit, dict) else edit)
            for k, v in edit.items():
                if k == "id":
                    continue
                if k not in EDITABLE_FIELDS:
                    raise ValueError(f"cannot edit {k}" if k in known else f"unknown field {k}")
                _check_type(k, v)
            if "subject" in edit:
                sidx = by_id[edit["id"]].subject_idx
                if new_subjects.setdefault(sidx, edit["subject"]) != edit["subject"]:
                    raise ValueError("two edits give one subject different IDs")
        subjects = {e.subject_idx: e.subject for e in self.entries} | new_subjects
        if len(set(subjects.values())) != len(subjects):
            raise ValueError("two subjects would share one subject ID")
        touched: dict[str, PlanEntry] = {}
        for edit in edits:
            entry = by_id[edit["id"]]
            for k, v in edit.items():
                if k == "ephys_format" and v is None:
                    v = ""
                if k == "pixel_size" and v is not None:
                    v = [float(t) for t in v]
                if k not in ("id", "subject", "deface"):
                    setattr(entry, k, v)
            if "deface" in edit:
                entry.deface = edit["deface"]
                entry.deface_opt_out = not entry.deface and entry.datatype == "anat"
            elif "datatype" in edit or "suffix" in edit:
                entry.deface, entry.deface_opt_out = entry.datatype == "anat", False
            if edit.keys() & {"brainlife_datatype", "brainlife_tags"}:
                entry.brainlife_by_person = True
            elif edit.keys() & {"datatype", "suffix", "entities"}:
                entry.brainlife_by_person = False
            entry.source = "person"
            touched[entry.id] = entry
        for e in self.entries:
            if e.subject_idx in new_subjects and e.subject != new_subjects[e.subject_idx]:
                e.subject, e.source = new_subjects[e.subject_idx], "person"
                touched[e.id] = e
        self.approved = False
        return list(touched.values())

    def apply_ancillary_edits(self, edits: list[dict]) -> None:
        """Edit ancillary entries: action, columns (partial) and content. Paths cannot change.

        Raises KeyError for an unknown id and ValueError for anything else invalid: sourcedata/
        and derivatives/ set to anything but drop, an unknown or locked field, a changed path, an
        unknown column or action, dropping a key column, keeping a header with an identifying value or a
        column action outside its locked_columns list, anything but drop for a locked entry, content
        for a table or folder, or content of the wrong type. A bad edit leaves the plan untouched.
        """
        by_id = {a.id: a for a in self.ancillary}
        for edit in edits:
            if edit.get("id") not in by_id:
                raise KeyError(edit.get("id"))
            _check_ancillary_edit(by_id[edit["id"]], edit)
        for edit in edits:
            a = by_id[edit["id"]]
            if "content" in edit:
                a.content = edit["content"]
            if "columns" in edit:
                a.columns.update(edit["columns"])
            a.action = _edit_action(a, edit)
        self.approved = False

    def set_dataset_description(self, fields: dict) -> None:
        """Set dataset_description fields (DESCRIPTION_FIELDS only; None removes one); unapproves."""
        unknown = sorted(set(fields) - set(DESCRIPTION_FIELDS))
        if unknown:
            raise ValueError(f"not editable in dataset_description: {unknown}")
        for k, v in fields.items():
            if v is None:
                self.dataset_description.pop(k, None)
            else:
                self.dataset_description[k] = v
        self.approved = False

    def set_event_names(self, edits: dict[str, str]) -> None:
        """Rename event codes; each key must be an existing code and each value match EVENT_NAME_RE.

        Raises ValueError (naming no value) for anything invalid; a bad edit changes nothing. Unapproves.
        """
        if not isinstance(edits, dict):
            raise ValueError("event_names must be an object")
        for k, v in edits.items():
            if k not in self.event_names:
                raise ValueError("unknown event code")
            if not isinstance(v, str) or not EVENT_NAME_RE.fullmatch(v):
                raise ValueError("an event name is 1 to 40 letters, digits, spaces or _ . / + -, "
                                 "starting with a letter or digit")
        names = [v.casefold() for v in {**self.event_names, **edits}.values()]
        if len(set(names)) != len(names):
            raise ValueError("two event codes would share one name")
        self.event_names.update(edits)
        self.approved = False


def _check_type(k: str, v) -> None:
    kind = EDITABLE_FIELDS[k]
    if kind.endswith("?") and v is None:
        return
    kind = kind.rstrip("?")
    ok = {"bool": type(v) is bool,
          "str": isinstance(v, str) and bool(v),
          "label": isinstance(v, str) and bool(_LABEL.fullmatch(v)),
          "dict": isinstance(v, dict) and all(isinstance(a, str) and isinstance(b, str) for a, b in v.items()),
          "list": isinstance(v, list) and all(isinstance(t, str) for t in v),
          "sizes": isinstance(v, list) and len(v) in (2, 3) and all(
              isinstance(t, (int, float)) and not isinstance(t, bool) and math.isfinite(t) and t > 0 for t in v),
          "unit": v in PIXEL_SIZE_UNITS}[kind]
    if not ok:
        want = {"bool": "true or false", "str": "a non-empty string", "label": "letters and digits only",
                "dict": "an object of strings", "list": "a list of strings",
                "sizes": "a list of 2 or 3 positive numbers (x, y[, z])",
                "unit": f"one of {', '.join(PIXEL_SIZE_UNITS)}"}[kind]
        raise ValueError(f"{k} must be {want}")


def _edit_action(a: AncillaryEntry, edit: dict) -> str:
    if "action" in edit:
        return edit["action"]
    if edit.get("content") is not None:
        return "edit"
    if "content" in edit and a.action == "edit":  # content cleared: back to the de-identified input
        return "keep"
    return a.action


def _check_ancillary_edit(a: AncillaryEntry, edit: dict) -> None:
    for k in edit:
        if k == "id":
            continue
        if k == "path":
            if edit[k] != a.path:
                raise ValueError(f"{a.id}: the path of an ancillary file cannot be changed")
            continue
        if k not in ANCILLARY_EDITABLE:
            raise ValueError(f"cannot edit {k}")
    action = _edit_action(a, edit)
    if action not in ANCILLARY_ACTIONS:
        raise ValueError(f"unknown action {action!r}")
    if a.path.split("/")[0] in NEVER_KEEP and action != "drop":
        raise ValueError(f"{a.path}/ is never uploaded")
    if a.locked and action != "drop":
        raise ValueError(f"{a.path} is not uploadable: it can only be dropped ({a.reason})")
    is_json = a.path.endswith(".json")
    content = edit.get("content")
    if content is not None:
        if a.kind == "folder" or a.path.endswith((".tsv", ".tsv.gz")):
            raise ValueError(f"{a.path}: no content edits (tables are edited by column)")
        if is_json and not isinstance(content, dict):
            raise ValueError(f"{a.path}: content must be a JSON object")
        if not is_json and not isinstance(content, str):
            raise ValueError(f"{a.path}: content must be text")
    if action == "edit" and (content if "content" in edit else a.content) is None:
        raise ValueError(f"{a.path}: an edit needs content")
    if "columns" in edit:
        columns = edit["columns"]
        if not isinstance(columns, dict) or not a.columns:
            raise ValueError(f"{a.path}: not a table")
        for col, act in columns.items():
            if col not in a.columns:
                raise ValueError(f"{a.path}: unknown column {col!r}")
            if act not in COLUMN_ACTIONS:
                raise ValueError(f"unknown column action {act!r}")
            if REDACTED_MARK in col and act != "drop":
                raise ValueError(f"{a.path}: a column whose name holds an identifying value is always dropped")
            if col in KEY_COLUMNS and act != "keep":
                raise ValueError(f"{a.path}: {col} is always kept (it is rewritten)")
            allowed = a.locked_columns.get(col)
            if allowed is not None and act not in allowed:
                raise ValueError(f"{a.path}: column {col!r} can only be {' or '.join(allowed)}")
