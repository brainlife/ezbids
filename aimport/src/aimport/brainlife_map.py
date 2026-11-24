"""Map BIDS (datatype, suffix) to brainlife datatypes.

The table lives in data/bids_brainlife_map.yaml (single source of truth); this
module only loads, validates and looks it up.
"""

from importlib import resources
from pathlib import Path

import yaml

_FILE = "bids_brainlife_map.yaml"
_STATUSES = {"active", "planned", "draft"}

# (bids datatype, suffix) -> (brainlife datatype, fixed tags or None for tags_from: task)
Table = dict[tuple[str, str], tuple[str, list[str] | None]]
# (bids datatype, suffix, extension) -> the same; rows keyed by file format (eeg, meg)
ExtTable = dict[tuple[str, str, str], tuple[str, list[str] | None]]


def _validate_row(i: int, row: object) -> None:
    where = f"mappings[{i}]"
    if not isinstance(row, dict):
        raise ValueError(f"{where}: row must be a mapping")
    bids, bl = row.get("bids"), row.get("brainlife")
    if not isinstance(bids, dict) or not bids.get("datatype"):
        raise ValueError(f"{where} ({row}): missing bids.datatype")
    where = f"mappings[{i}] ({bids['datatype']}/{bids.get('suffix') or bids.get('extension')})"
    if row.get("status") not in _STATUSES:
        raise ValueError(f"{where}: status must be one of {sorted(_STATUSES)}")
    if bl is None and row["status"] == "planned":
        if "suffix" in bids and not isinstance(bids["suffix"], str):
            raise ValueError(f"{where}: bids.suffix must be a string")
        return  # a placeholder: the pair is accounted for, no brainlife datatype chosen yet
    if not isinstance(bl, dict) or not bl.get("datatype"):
        raise ValueError(f"{where}: missing brainlife.datatype")
    if ("tags" in bl) == ("tags_from" in bl):
        raise ValueError(f"{where}: exactly one of brainlife.tags / brainlife.tags_from")
    if "tags" in bl and not (
        isinstance(bl["tags"], list) and all(isinstance(t, str) for t in bl["tags"])
    ):
        raise ValueError(f"{where}: brainlife.tags must be a list of strings")
    if "suffix" in bids and not isinstance(bids["suffix"], str):
        raise ValueError(f"{where}: bids.suffix must be a string")
    if row["status"] == "draft" and not (bids.get("suffix") and row.get("ref")):
        raise ValueError(f"{where}: draft row needs bids.suffix and ref")
    if "tags_from" in bl and bl["tags_from"] != "task":
        raise ValueError(f"{where}: tags_from must be 'task'")


def _load_doc(path: Path | None) -> dict:
    if path is None:
        text = resources.files("aimport.data").joinpath(_FILE).read_text()
    else:
        text = Path(path).read_text()
    doc = yaml.safe_load(text)
    if not isinstance(doc, dict) or type(doc.get("version")) is not int or doc["version"] != 1:
        raise ValueError("mapping file: version must be 1")
    for i, row in enumerate(doc.get("mappings") or []):
        _validate_row(i, row)
    return doc


def load_rows(path: Path | None = None) -> list[dict]:
    """Every validated row of the mapping file, whatever its status."""
    return list(_load_doc(path).get("mappings") or [])


def row_covers(row: dict, datatype: str, suffix: str) -> bool:
    """Whether a row accounts for the BIDS pair (datatype, suffix).

    Matching rule: same BIDS datatype, and either the row names the same suffix (any
    extension: eeg/meg rows are keyed by datatype+extension+suffix) or it names no suffix
    (e.g. the micr row, keyed by extension only, covers every micr suffix).
    """
    bids = row["bids"]
    return bids["datatype"] == datatype and bids.get("suffix") in (None, suffix)


def load_table(path: Path | None = None) -> Table:
    """Load and validate the mapping file; return the active (datatype, suffix) rows."""
    doc = _load_doc(path)
    table: Table = {}
    for i, row in enumerate(doc.get("mappings") or []):
        if row["status"] != "active" or "extension" in row["bids"]:
            continue
        bids, bl = row["bids"], row["brainlife"]
        key = (bids["datatype"], bids.get("suffix"))
        if key[1] is None:
            raise ValueError(f"mappings[{i}] ({key[0]}): active row needs bids.suffix")
        if key in table:
            raise ValueError(f"mappings[{i}] ({key[0]}/{key[1]}): duplicate active key")
        table[key] = (bl["datatype"], None if "tags_from" in bl else list(bl["tags"]))
    return table


def load_ext_table(path: Path | None = None) -> ExtTable:
    """The active rows keyed by (datatype, suffix, extension): brainlife datatypes chosen by file format."""
    doc = _load_doc(path)
    table: ExtTable = {}
    for i, row in enumerate(doc.get("mappings") or []):
        if row["status"] != "active" or "extension" not in row["bids"]:
            continue
        bids, bl = row["bids"], row["brainlife"]
        key = (bids["datatype"], bids.get("suffix"), bids["extension"])
        if key[1] is None:
            raise ValueError(f"mappings[{i}] ({key[0]}{key[2]}): active row needs bids.suffix")
        if key in table:
            raise ValueError(f"mappings[{i}] ({key[0]}/{key[1]}{key[2]}): duplicate active key")
        table[key] = (bl["datatype"], None if "tags_from" in bl else list(bl["tags"]))
    return table


_TABLE = load_table()
_EXT_TABLE = load_ext_table()
_DRAFTS = {
    (r["bids"]["datatype"], r["bids"]["suffix"]): r["brainlife"]["datatype"]
    for r in load_rows()
    if r["status"] == "draft"
}


def draft_for(datatype: str, suffix: str) -> str | None:
    """Name of the draft (not yet registered) brainlife datatype for a BIDS pair, if any."""
    return _DRAFTS.get((datatype, suffix))


def no_datatype_reason(datatype: str | None, suffix: str | None) -> str:
    """The text added to a reason when the datatypes target excludes an entry: names the draft, if any."""
    draft = draft_for(datatype, suffix) if datatype and suffix else None
    return f"; no brainlife datatype (draft {draft}, not registered yet)" if draft else "; no brainlife datatype"


def to_brainlife(
    datatype: str, suffix: str, entities: dict[str, str], sidecar: dict, extension: str | None = None
) -> tuple[str | None, list[str]]:
    """Return (brainlife datatype, datatype_tags); (None, []) if unmapped.

    extension (the written data file's, e.g. ".eeg" for BrainVision) is looked up first among the rows
    keyed by file format, then the (datatype, suffix) rows."""
    hit = _EXT_TABLE.get((datatype, suffix, extension)) if extension else None
    if hit is None:
        hit = _TABLE.get((datatype, suffix))
    if hit is None:
        return None, []
    bl, tags = hit
    if tags is None:
        # bids-walker.js:1053-1072: task lowercased, "unknown" when absent
        return bl, [(entities.get("task") or "unknown").lower()]
    return bl, list(tags)
