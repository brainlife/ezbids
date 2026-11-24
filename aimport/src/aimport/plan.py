"""The import plan: one entry per series, editable by the person."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Literal

LOCKED_FIELDS = {"id", "series_idx", "subject_idx", "session_idx"}


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

    def save(self, path: Path) -> None:
        Path(path).write_text(json.dumps(asdict(self), indent=2))

    @classmethod
    def load(cls, path: Path) -> Plan:
        data = json.loads(Path(path).read_text())
        data["entries"] = [PlanEntry(**e) for e in data["entries"]]
        return cls(**data)

    def apply_edits(self, edits: list[dict]) -> None:
        by_id = {e.id: e for e in self.entries}
        valid = {f.name for f in fields(PlanEntry)}
        # validate everything first so a bad edit leaves the plan untouched
        for edit in edits:
            if edit["id"] not in by_id:
                raise KeyError(edit["id"])
            for k in edit:
                if k == "id":
                    continue
                if k in LOCKED_FIELDS:
                    raise ValueError(f"cannot edit {k}")
                if k not in valid:
                    raise ValueError(f"unknown field {k}")
        for edit in edits:
            entry = by_id[edit["id"]]
            for k, v in edit.items():
                if k != "id":
                    setattr(entry, k, v)
            entry.source = "person"
        self.approved = False
