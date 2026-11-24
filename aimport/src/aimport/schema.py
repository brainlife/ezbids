"""BIDS v1.11.2 schema helpers: validate datatype/suffix pairs and build filenames."""

from __future__ import annotations

import re
from pathlib import Path

from bidsschematools.schema import load_schema as _bst_load_schema

DEFAULT_SCHEMA = Path("/opt/bids-schema/schema.json")
SPEC_SCHEMA_DIR = Path(__file__).resolve().parents[2] / "bids-specification" / "src" / "schema"
PHASE1_DATATYPES = ("anat", "func", "dwi", "fmap", "perf", "pet")

_LABEL = re.compile(r"^[a-zA-Z0-9]+$")
_INDEX = re.compile(r"^[0-9]+$")
# Passed separately to Schema.filename, so never part of the ``entities`` dict.
_PATH_ENTITIES = ("subject", "session")


class Schema:
    def __init__(self, schema) -> None:
        self._s = schema

    def _groups(self, datatype: str, suffix: str):
        yield from self._walk(self._s.rules.files.raw, datatype, suffix)

    def _walk(self, node, datatype: str, suffix: str):
        # rules.files.raw.<group> is a rule or a dict of named rules (e.g. anat.parametric)
        if "suffixes" in node:
            if datatype in node.get("datatypes", []) and suffix in node["suffixes"]:
                yield node
            return
        for child in node.values():
            yield from self._walk(child, datatype, suffix)

    def is_valid(self, datatype: str, suffix: str) -> bool:
        return any(True for _ in self._groups(datatype, suffix))

    def allowed_entities(self, datatype: str, suffix: str) -> list[str]:
        """Union of entity names (e.g. ``task``, ``run``) over matching groups, in schema order.

        ``subject`` and ``session`` are excluded: ``filename`` takes them separately.
        """
        allowed: set[str] = set()
        for group in self._groups(datatype, suffix):
            allowed.update(group.get("entities", {}))
        return self._ordered(allowed)

    def required_entities(self, datatype: str, suffix: str) -> list[str]:
        """Entities required in EVERY matching group, in schema order (no subject/session)."""
        sets = [self._required(g) for g in self._groups(datatype, suffix)]
        return self._ordered(set.intersection(*sets) if sets else set())

    def _ordered(self, names) -> list[str]:
        return [e for e in self._s.rules.entities if e in names and e not in _PATH_ENTITIES]

    @staticmethod
    def _required(group) -> set[str]:
        return {e for e, level in group.get("entities", {}).items()
                if level == "required" and e not in _PATH_ENTITIES}

    def filename(self, subject: str, session: str | None, datatype: str, suffix: str,
                 entities: dict[str, str], ext: str) -> str:
        groups = list(self._groups(datatype, suffix))
        if not groups:
            raise ValueError(f"invalid datatype/suffix: {datatype}/{suffix}")
        problems = []
        for group in groups:
            gents = set(group.get("entities", {}))
            not_allowed = sorted(set(entities) - gents)
            missing = sorted(self._required(group) - set(entities))
            problem = []
            if not_allowed:
                problem.append(f"entities not allowed: {not_allowed}")
            if missing:
                problem.append(f"required entities missing: {missing}")
            if ext not in group.get("extensions", []):
                problem.append(f"extension not allowed: {ext!r}")
            if not problem:
                break
            problems.append("; ".join(problem))
        else:
            raise ValueError(f"invalid {datatype}/{suffix} filename: " + " | ".join(problems))
        parts = [("sub", self._label("subject", subject))]
        if session:
            parts.append(("ses", self._label("session", session)))
        for ent in self._ordered(entities):
            key = self._s.objects.entities[ent].name
            parts.append((key, self._label(ent, entities[ent])))
        stem = "_".join(f"{k}-{v}" for k, v in parts)
        directory = f"sub-{parts[0][1]}" + (f"/ses-{parts[1][1]}" if session else "")
        return f"{directory}/{datatype}/{stem}_{suffix}{ext}"

    def _label(self, entity: str, value: str) -> str:
        fmt = self._s.objects.entities[entity].get("format", "label")
        pattern = _INDEX if fmt == "index" else _LABEL
        if not isinstance(value, str) or not pattern.match(value):
            raise ValueError(f"invalid {entity} label: {value!r}")
        return value


def load_schema(path: Path = DEFAULT_SCHEMA) -> Schema:
    path = Path(path)
    if path.exists():
        return Schema(_bst_load_schema(path))
    if path == DEFAULT_SCHEMA and SPEC_SCHEMA_DIR.exists():
        return Schema(_bst_load_schema(SPEC_SCHEMA_DIR))
    raise FileNotFoundError(f"BIDS schema not found: {path}")
