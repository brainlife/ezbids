"""Map BIDS (datatype, suffix) to brainlife datatypes.

The table lives in data/bids_brainlife_map.yaml (single source of truth); this
module only loads, validates and looks it up.
"""

from importlib import resources
from pathlib import Path

import yaml

_FILE = "bids_brainlife_map.yaml"
_STATUSES = {"active", "planned"}

# (bids datatype, suffix) -> (brainlife datatype, fixed tags or None for tags_from: task)
Table = dict[tuple[str, str], tuple[str, list[str] | None]]


def _validate_row(i: int, row: object) -> None:
    where = f"mappings[{i}]"
    if not isinstance(row, dict):
        raise ValueError(f"{where}: row must be a mapping")
    bids, bl = row.get("bids"), row.get("brainlife")
    if not isinstance(bids, dict) or not bids.get("datatype"):
        raise ValueError(f"{where} ({row}): missing bids.datatype")
    where = f"mappings[{i}] ({bids['datatype']}/{bids.get('suffix') or bids.get('extension')})"
    if not isinstance(bl, dict) or not bl.get("datatype"):
        raise ValueError(f"{where}: missing brainlife.datatype")
    if row.get("status") not in _STATUSES:
        raise ValueError(f"{where}: status must be one of {sorted(_STATUSES)}")
    if ("tags" in bl) == ("tags_from" in bl):
        raise ValueError(f"{where}: exactly one of brainlife.tags / brainlife.tags_from")
    if "tags" in bl and not (
        isinstance(bl["tags"], list) and all(isinstance(t, str) for t in bl["tags"])
    ):
        raise ValueError(f"{where}: brainlife.tags must be a list of strings")
    if "suffix" in bids and not isinstance(bids["suffix"], str):
        raise ValueError(f"{where}: bids.suffix must be a string")
    if "tags_from" in bl and bl["tags_from"] != "task":
        raise ValueError(f"{where}: tags_from must be 'task'")


def load_table(path: Path | None = None) -> Table:
    """Load and validate the mapping file; return the active (datatype, suffix) rows."""
    if path is None:
        text = resources.files("aimport.data").joinpath(_FILE).read_text()
    else:
        text = Path(path).read_text()
    doc = yaml.safe_load(text)
    if not isinstance(doc, dict) or type(doc.get("version")) is not int or doc["version"] != 1:
        raise ValueError("mapping file: version must be 1")
    table: Table = {}
    for i, row in enumerate(doc.get("mappings") or []):
        _validate_row(i, row)
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


_TABLE = load_table()


def to_brainlife(
    datatype: str, suffix: str, entities: dict[str, str], sidecar: dict
) -> tuple[str | None, list[str]]:
    """Return (brainlife datatype, datatype_tags); (None, []) if unmapped."""
    hit = _TABLE.get((datatype, suffix))
    if hit is None:
        return None, []
    bl, tags = hit
    if tags is None:
        # bids-walker.js:1053-1072: task lowercased, "unknown" when absent
        return bl, [(entities.get("task") or "unknown").lower()]
    return bl, list(tags)
