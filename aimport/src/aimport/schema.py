"""BIDS v1.11.2 schema helpers: validate datatype/suffix pairs and build filenames."""

from __future__ import annotations

import functools
import re
from pathlib import Path

from bidsschematools.schema import load_schema as _bst_load_schema

DEFAULT_SCHEMA = Path("/opt/bids-schema/schema.json")
SPEC_SCHEMA_DIR = Path(__file__).resolve().parents[2] / "bids-specification" / "src" / "schema"
PHASE1_DATATYPES = ("anat", "func", "dwi", "fmap", "perf", "pet")
MICR_DATATYPES = ("micr",)
EPHYS_DATATYPES = ("eeg", "meg", "ieeg", "nirs", "emg")
SUPPORTED_DATATYPES = PHASE1_DATATYPES + MICR_DATATYPES + EPHYS_DATATYPES
# the extension a file is written with (checked when naming): microscopy by datatype, electrophysiology by
# output format (PlanEntry.ephys_format); default NIfTI
CHECK_EXTS = {"micr": ".ome.zarr/", "BrainVision": ".vhdr", "EDF": ".edf", "BDF": ".bdf", "FIF": ".fif",
              "SNIRF": ".snirf", "NWB": ".nwb"}
DEFAULT_CHECK_EXT = ".nii.gz"
BIDS_VERSION = "1.11.2"

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

    def raw_pairs(self) -> dict[tuple[str, str], list[str]]:
        """Every raw-data (datatype, suffix) with its extensions (schema order, deduplicated)."""
        pairs: dict[tuple[str, str], list[str]] = {}
        for group in self._leaves(self._s.rules.files.raw):
            for datatype in group.get("datatypes", []):
                for suffix in group["suffixes"]:
                    exts = pairs.setdefault((datatype, suffix), [])
                    exts.extend(e for e in group.get("extensions", []) if e not in exts)
        return pairs

    def required_sidecar_fields(self, datatype: str, suffix: str, extension: str) -> list[str]:
        """Sidecar fields the schema always requires for this pair's data file.

        Walks rules.sidecars. An entry counts only when every selector is one of the forms
        decidable from (datatype, suffix, extension) alone: ``datatype == "x"``,
        ``suffix ==/!= "x"``, ``modality == "x"``, ``intersects([datatype|suffix|modality]
        or datatype|suffix, [...])``, their negations, and ``match(extension, re)``. An entry
        with any other selector (entities, sidecar values, dataset properties) is
        conditional and ignored, so only unconditional requirements are returned.
        Fields are those whose ``level`` is ``required`` (``level_addendum`` makes it
        conditional, but those carry ``level: recommended``/``optional``, so are excluded).
        """
        modalities = [m for m, v in self._s.rules.modalities.items() if datatype in v.datatypes]
        values = {"datatype": [datatype], "suffix": [suffix], "modality": modalities}
        ext = extension.rstrip("/")
        found: list[str] = []
        for entry in self._leaves_sidecars(self._s.rules.sidecars):
            verdicts = [self._selector(x, values, ext) for x in entry.get("selectors", [])]
            if not verdicts or not all(v is True for v in verdicts):
                continue
            for field, spec in entry.get("fields", {}).items():
                level = spec if isinstance(spec, str) else spec.get("level")
                if level == "required" and field not in found:
                    found.append(field)
        return found

    def sidecar_fields(self, datatype: str, suffix: str) -> list[str]:
        """Every metadata key the schema lists for a ``<datatype>/<suffix>.json`` sidecar (any level), and,
        for a tabular suffix (events, channels, electrodes, ...), its column names (a column-description
        sidecar is keyed by them).

        Walks rules.sidecars, rules.json and rules.tabular_data; an entry counts when one of its selectors
        is decidably true and none is decidably false (conditional selectors count as possible).
        """
        modalities = [m for m, v in self._s.rules.modalities.items() if datatype in v.datatypes]
        values = {"datatype": [datatype], "suffix": [suffix], "modality": modalities}
        found: list[str] = []
        for rules, key, objects in ((self._s.rules.sidecars, "fields", self._s.objects.metadata),
                                    (self._s.rules.json, "fields", self._s.objects.metadata),
                                    (self._s.rules.tabular_data, "columns", self._s.objects.columns)):
            for entry in self._leaves_sidecars(rules):
                verdicts = [self._selector(x, values, ".json") for x in entry.get("selectors", [])]
                if False in verdicts or True not in verdicts:
                    continue
                for field in entry.get(key, {}) or {}:
                    obj = objects.get(field)
                    name = str(obj.get("name", field)) if obj else str(field)
                    if name not in found:
                        found.append(name)
        return found

    def _leaves_sidecars(self, node):
        if "selectors" in node or "fields" in node or "columns" in node:
            yield node
            return
        for child in node.values():
            yield from self._leaves_sidecars(child)

    @staticmethod
    def _selector(sel: str, values: dict, ext: str):
        """True/False for a decidable selector, None when it is conditional."""
        sel = sel.strip()
        m = re.fullmatch(r'(datatype|suffix|modality) (==|!=) ["\'](.*?)["\']', sel)
        if m:
            hit = m[3] in values[m[1]]
            return hit if m[2] == "==" else not hit
        m = re.fullmatch(r'(!?)intersects\(\[?(datatype|suffix|modality)\]?, \[(.*)\]\)', sel)
        if m:
            wanted = re.findall(r'["\']([^"\']*)["\']', m[3])
            hit = bool(set(wanted) & set(values[m[2]]))
            return not hit if m[1] else hit
        m = re.fullmatch(r'match\(extension, ["\'](.*)["\']\)', sel)
        if m:
            return re.search(m[1], ext) is not None
        return None

    def common_rules(self) -> dict[str, dict]:
        """rules.files.common.core and .tables by name (dataset_description, README, participants, ...)."""
        common = self._s.rules.files.common
        return {name: dict(rule) for group in (common.core, common.tables) for name, rule in group.items()}

    def sample_types(self) -> list[str]:
        """The values the samples.tsv sample_type column may take (schema enum)."""
        col = self._s.objects.columns.get("sample_type")
        return [str(v) for v in (col.get("enum") or [])] if col else []

    def is_datatype(self, name: str) -> bool:
        return any(v.get("value") == name for v in self._s.objects.datatypes.values())

    def is_suffix(self, suffix: str) -> bool:
        return any(v.get("value") == suffix for v in self._s.objects.suffixes.values())

    def suffix_description(self, suffix: str) -> str:
        """Schema description of a suffix, whitespace-normalised ('' if undocumented)."""
        obj = self._s.objects.suffixes.get(suffix)
        return " ".join(str(obj.get("description", "")).split()) if obj else ""

    def _leaves(self, node):
        if "suffixes" in node:
            yield node
            return
        for child in node.values():
            yield from self._leaves(child)

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



@functools.cache
def _objects():
    """The schema's objects (entities, datatypes, suffixes): the pinned schema, else bidsschematools' own."""
    try:
        return load_schema()._s.objects
    except FileNotFoundError:
        return _bst_load_schema().objects


@functools.cache
def bids_words() -> frozenset[str]:
    """The BIDS schema's structural words, casefolded: entity keys and names (``sub``/``subject``, ``ses``,
    ``task``, ``acq``, ``run``, ``trc``/``tracer`` ...), datatypes (``anat``, ``eeg``, ``micr`` ...) and
    suffixes (``T1w``, ``bold``, ``events`` ...). Never an identifying term on their own, in any modality."""
    o = _objects()
    words = set()
    for group in (o.entities, o.datatypes, o.suffixes):
        for name, obj in group.items():
            words |= {name, obj.get("name") or obj.get("value") or name}
    return frozenset(w.casefold() for w in words if w)


@functools.cache
def entity_keys() -> frozenset[str]:
    """The entity keys of BIDS names (``sub``, ``ses``, ``task`` ...), casefolded."""
    return frozenset(e.name.casefold() for e in _objects().entities.values())
