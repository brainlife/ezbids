"""Bad channels marked by a reviewer in the QA trace viewer (``POST /qa/channels/<entry id>``).

A mark is a channel's BIDS ``status`` (``good``/``bad``) and, for a bad channel, an optional short reason
(``status_description``). Marks are written into the recording's ``_channels.tsv`` in the output (atomically:
a temporary file, then a rename) and kept in ``<work>/ephys/bad_channels.json`` (local only, never served or
uploaded) by plan entry id, so a re-execute after plan edits applies them again; a new scan removes the
module folder, and with it the marks. Bad time segments are not marked here.

A reason is reviewer text: control characters, tabs and newlines are removed, it is at most ``MAX_REASON``
characters, and one that holds a run term is refused with a generic message (never echoed). The written file
then passes the ephys gate before it replaces the output file.
"""
from __future__ import annotations

import json
import os
import re
import unicodedata
from pathlib import Path

from .events import holds_term

MARKS_FILE = "bad_channels.json"
MAX_REASON = 80
QUICK_REASONS = ("flat", "noisy", "bridged", "disconnected")
STATUSES = ("good", "bad")
NA = "n/a"
TSV_SUFFIX = "_channels.tsv"
# the column descriptions added to a channels.json sidecar that lacks them (BIDS: status, status_description)
STATUS_TEXT = {
    "Description": "Data quality observed on the channel.",
    "Levels": {"good": "The channel's data are of good quality.", "bad": "The channel's data are of poor quality."},
}
STATUS_DESCRIPTION_TEXT = {"Description": "Why the channel was marked bad (set by a reviewer in the aimport QA viewer)."}
REASON_REFUSED = "a reason holds identifying text: use a short technical reason (flat, noisy, bridged, disconnected)"
_SPACES = re.compile(r"\s+")


class MarkError(ValueError):
    """A mark that cannot be applied (the route answers 400 with the message, which never quotes the input)."""


def clean_reason(text: str | None, terms: set[str]) -> str | None:
    """The reason as written: control and format characters (tabs, newlines) removed, spaces collapsed;
    None when empty. MarkError when longer than MAX_REASON or holding a run term."""
    if text is None:
        return None
    if not isinstance(text, str):
        raise MarkError("a reason must be text")
    kept = "".join(" " if ch in "\t\n\r\v\f" else ch for ch in text)
    kept = "".join(ch for ch in kept if unicodedata.category(ch) not in ("Cc", "Cf", "Cs", "Co", "Cn", "Zl", "Zp"))
    kept = _SPACES.sub(" ", kept).strip()
    if not kept or kept == NA:
        return None
    if len(kept) > MAX_REASON:
        raise MarkError(f"a reason is at most {MAX_REASON} characters")
    if holds_term(kept, terms):
        raise MarkError(REASON_REFUSED)
    return kept


def tsv_of(manifest_files: list[str]) -> str | None:
    """The recording's ``_channels.tsv`` among an entry's manifest files (output-relative), else None."""
    return next((r for r in manifest_files if r.endswith(TSV_SUFFIX)), None)


def _read(path: Path) -> tuple[list[str], list[list[str]]]:
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    if not lines:
        raise MarkError("the recording has no channel table")
    header = lines[0].split("\t")
    rows = [line.split("\t") for line in lines[1:] if line]
    return header, [r + [NA] * (len(header) - len(r)) for r in rows]


def table(path: Path) -> list[dict]:
    """``[{"name", "type", "status", "description"}]`` of a written ``channels.tsv`` (in its order)."""
    header, rows = _read(path)
    col = {c: i for i, c in enumerate(header)}

    def cell(row: list[str], name: str) -> str | None:
        v = row[col[name]].strip() if name in col else ""
        return v if v and v != NA else None

    return [{"name": row[col["name"]] if "name" in col else "", "type": cell(row, "type"),
             "status": (cell(row, "status") or "good").lower(), "description": cell(row, "status_description")}
            for row in rows]


def check_marks(path: Path, marks: list[dict], terms: set[str]) -> dict[str, dict]:
    """The request's marks as ``name -> {"status", "description"}``, checked against the written table:
    each name once and present, status good or bad, the reason cleaned (``clean_reason``; a good channel
    keeps none). MarkError otherwise (the message never quotes a name or a reason)."""
    names = {r["name"] for r in table(path)}
    out: dict[str, dict] = {}
    for m in marks:
        name, status = m.get("name"), m.get("status")
        if not isinstance(name, str) or name not in names:
            raise MarkError("unknown channel: names must be as in the recording's channels.tsv")
        if name in out:
            raise MarkError("a channel is listed twice")
        if status not in STATUSES:
            raise MarkError("status must be good or bad")
        reason = clean_reason(m.get("description"), terms)
        out[name] = {"status": status, "description": reason if status == "bad" else None}
    return out


def render(path: Path, marks: dict[str, dict]) -> tuple[str, int, bool]:
    """(the new ``channels.tsv`` text, its number of bad channels, whether a column was added) with ``marks``
    (name -> {"status", "description"}) applied; names not in the table are skipped. ``status`` and
    ``status_description`` are appended to the header when absent (unmarked rows: good, n/a)."""
    header, rows = _read(path)
    added = False
    for column in ("status", "status_description"):
        if column not in header:
            header.append(column)
            default = "good" if column == "status" else NA
            for r in rows:
                r.append(default)
            added = True
    col = {c: i for i, c in enumerate(header)}
    for r in rows:
        m = marks.get(r[col["name"]])
        if m is None:
            continue
        r[col["status"]] = m["status"]
        r[col["status_description"]] = (m.get("description") or NA) if m["status"] == "bad" else NA
    bad = sum(1 for r in rows if r[col["status"]].strip().lower() == "bad")
    text = "".join("\t".join(r) + "\n" for r in [header, *rows])
    return text, bad, added


def sidecar(path: Path) -> Path:
    """The recording's ``_channels.json`` (beside its ``_channels.tsv``)."""
    return Path(path).with_suffix(".json")


def described(json_path: Path) -> str | None:
    """The ``channels.json`` text with ``status`` and ``status_description`` described, when the file exists
    and lacks a description of either; else None (nothing to change)."""
    if not Path(json_path).is_file():
        return None
    data = json.loads(Path(json_path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return None
    changed = False
    for key, text in (("status", STATUS_TEXT), ("status_description", STATUS_DESCRIPTION_TEXT)):
        if key not in data:
            data[key] = text
            changed = True
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n" if changed else None


def write_atomic(path: Path, text: str) -> None:
    """``text`` into ``path`` through a temporary file in the same folder and a rename."""
    path = Path(path)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def apply(path: Path, marks: dict[str, dict]) -> int:
    """Write ``marks`` into the ``channels.tsv`` at ``path`` (and describe the columns in its channels.json, if
    there is one), in place and atomically; returns the number of bad channels."""
    text, bad, _ = render(path, marks)
    write_atomic(path, text)
    doc = described(sidecar(path))
    if doc is not None:
        write_atomic(sidecar(path), doc)
    return bad


# --- the local record of the marks (<work>/ephys/bad_channels.json) ---


def load(ephys_dir: Path) -> dict[str, dict]:
    """entry id -> ``{"channels": {name: {"status", "description"}}, "bad": <count in the written table>}``."""
    path = Path(ephys_dir) / MARKS_FILE
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    entries = data.get("entries") if isinstance(data, dict) else None
    return entries if isinstance(entries, dict) else {}


def save(ephys_dir: Path, entries: dict[str, dict]) -> None:
    Path(ephys_dir).mkdir(parents=True, exist_ok=True)
    write_atomic(Path(ephys_dir) / MARKS_FILE, json.dumps({"version": 1, "entries": entries}, indent=1))


def counts(ephys_dir: Path) -> dict[str, int]:
    """entry id -> number of bad channels in its written table (entries with marks only)."""
    out = {}
    for eid, e in load(ephys_dir).items():
        if isinstance(e, dict) and isinstance(e.get("bad"), int):
            out[eid] = e["bad"]
    return out


def reapply(ephys_dir: Path, written: dict[str, Path]) -> None:
    """After a (re-)execute: each entry's saved marks applied again to its written table (``written``: entry
    id -> its channels.tsv path), and the counts updated. Names no longer in a table are skipped."""
    entries = load(ephys_dir)
    if not entries:
        return
    for eid, path in written.items():
        e = entries.get(eid)
        if isinstance(e, dict) and isinstance(e.get("channels"), dict) and e["channels"]:
            e["bad"] = apply(path, e["channels"])
    save(ephys_dir, entries)
