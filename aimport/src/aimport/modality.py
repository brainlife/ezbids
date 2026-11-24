"""Modality modules: non-MRI importers that sit beside the ezBIDS MRI path.

A module claims input paths (and remote sources), scans them into local-only records, contributes
plan entries and writes its part of the output. What a module claims is never staged for ezBIDS,
never walked for DICOM headers and never copied: ``stage_input``, ``scrub._header_terms``,
``planner.build_plan`` and the writer's DICOM walk all skip claimed roots (``ClaimedPaths``).

Claims hold original paths and URLs, so they are local-only: ``<work>/<name>/claim.json`` is never
served, uploaded or sent to the agent. Every ``work`` passed to a module is its own folder
``<work>/<name>``, which a new scan and ``reset_output`` clear.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Callable, Iterable, Protocol, Sequence

if TYPE_CHECKING:
    from .agent import LLMClient
    from .plan import Plan, PlanEntry
    from .pseudonyms import PseudonymKey
    from .schema import Schema
    from .scrub import ScrubbedSeries

CLAIM_FILE = "claim.json"
# ezBIDS_core.json when nothing is left for ezBIDS after the claimed roots are excluded
EMPTY_CORE = {"series": [], "objects": [], "subjects": []}


@dataclass
class Claim:
    """roots: input-relative POSIX paths (files or folders); remote: normalised URLs. Local-only."""
    roots: list[str] = field(default_factory=list)
    remote: list[str] = field(default_factory=list)

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2))

    @classmethod
    def load(cls, path: Path) -> "Claim":
        raw = json.loads(Path(path).read_text())
        return cls(roots=[str(r) for r in raw.get("roots", [])], remote=[str(u) for u in raw.get("remote", [])])


@dataclass
class ModulePlan:
    entries: list["PlanEntry"] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    view: list["ScrubbedSeries"] = field(default_factory=list)
    labels: dict[int, str] = field(default_factory=dict)
    images: dict[str, str | None] = field(default_factory=dict)


@dataclass
class ModuleOutput:
    manifest: dict[str, list[str]] = field(default_factory=dict)
    participants: dict[str, dict[str, str]] = field(default_factory=dict)
    scans: dict[tuple[str, str | None], list[tuple[str, str]]] = field(default_factory=dict)
    samples: list[dict[str, str]] = field(default_factory=list)
    chunk_map: dict | None = None
    images: dict[str, str] = field(default_factory=dict)
    labels: dict[int, str] = field(default_factory=dict)  # subject_idx -> the input's own sub- label


class Module(Protocol):
    """A modality module. ``work`` is always the module's own folder ``<work>/<name>``.

    ``progress`` messages end up in the status (claimed path components are redacted from them,
    but a module must still never put paths, names or URLs in them).
    """

    name: str

    def claim(self, input_dir: Path, remote: list[str]) -> Claim: ...

    def scan(self, input_dir: Path, claim: Claim, work: Path, progress: Callable[[str], None]) -> None: ...

    def terms(self, work: Path) -> set[str]: ...

    def plan(self, work: Path, key: "PseudonymKey", existing: set[str], client: "LLMClient | None",
             schema: "Schema", target: str) -> ModulePlan: ...

    def write(self, plan: "Plan", work: Path, input_dir: Path, terms: set[str], key: "PseudonymKey",
              schema: "Schema", dest: Callable[[str], Path],
              progress: Callable[[str], None] | None = None) -> ModuleOutput:
        """Write the module's entries of the approved plan. ``dest(rel)`` checks an output path
        (relative to the BIDS folder), creates its parent folder and records it; nothing may be
        written elsewhere. Returns the rows and paths the writer merges into the top-level files."""
        ...


def modules() -> tuple[Module, ...]:
    """The registered modality modules: microscopy (``micr``)."""
    from .micr.module import MicrModule

    return (MicrModule(),)


# --- claimed paths -------------------------------------------------------------


def normalize_root(root: str) -> str:
    """A claimed root as a clean input-relative POSIX path; ValueError for absolute, '..' or empty."""
    text = str(root).replace("\\", "/")
    p = PurePosixPath(text)
    if p.is_absolute() or ".." in p.parts:
        raise ValueError(f"a claimed root must be a relative path inside the input: {root!r}")
    parts = [part for part in p.parts if part not in ("", ".")]
    if not parts:
        raise ValueError("a claimed root cannot be the whole input folder")
    return "/".join(parts)


def claimed_roots(claims: Iterable[Claim]) -> list[str]:
    roots: list[str] = []
    for c in claims:
        for r in c.roots:
            r = normalize_root(r)
            if r not in roots:
                roots.append(r)
    return roots


def _under(path: Path, roots: frozenset[str]) -> bool:
    """path is one of roots or lies below one: a set lookup per ancestor, never a scan of roots."""
    return str(path) in roots or any(str(a) in roots for a in path.parents)


class ClaimedPaths:
    """Membership test for paths under input_dir against the claimed roots.

    A path is claimed when it lies under a root lexically, or when it resolves (through symlinks)
    to a root or below one. ``reaches`` is for directory symlinks: also true when the link leads to
    a folder that contains a claimed root. Lookups go through sets (per ancestor), so thousands of
    per-file roots (tiles) cost no more than one.
    """

    def __init__(self, input_dir: Path, roots: Sequence[str] = ()):
        self.roots = [normalize_root(r) for r in roots]
        self.lexical_input = Path(os.path.abspath(input_dir))
        self.input = Path(input_dir).resolve()
        self.lexical = [self.lexical_input / r for r in self.roots] + [self.input / r for r in self.roots]
        self.resolved = [(self.input / r).resolve() for r in self.roots]
        self._lexical = frozenset(str(p) for p in self.lexical)
        self._resolved = frozenset(str(p) for p in self.resolved)
        # every resolved root and each of its ancestors: the folders that hold (or are) a root
        self._holders = frozenset(str(a) for r in self.resolved for a in (r, *r.parents))

    def __bool__(self) -> bool:
        return bool(self.roots)

    def covers(self, path: Path) -> bool:
        if not self.roots:
            return False
        p = Path(os.path.abspath(path))
        if _under(p, self._lexical):
            return True
        try:
            real = p.resolve()
        except (OSError, RuntimeError):
            return True  # a link loop or unreadable link: treat as claimed, never follow it
        return _under(real, self._resolved)

    def reaches(self, path: Path) -> bool:
        if self.covers(path):
            return True
        if not self.roots:
            return False
        try:
            real = Path(path).resolve()
        except (OSError, RuntimeError):
            return True
        return str(real) in self._holders

    def prune(self, dirpath: Path, dirs: list[str]) -> None:
        """For os.walk: drop claimed sub-folders in place, so the walk never descends into them."""
        if self.roots:
            dirs[:] = [d for d in dirs if not self.covers(Path(dirpath) / d)]


def claim_terms(claims: Iterable[Claim]) -> set[str]:
    """Path components of the claimed roots and the remote URLs: redacted from module progress text."""
    terms: set[str] = set()
    for c in claims:
        for r in c.roots:
            for part in PurePosixPath(str(r)).parts:
                if part not in ("", ".", "/"):
                    terms.add(part)
        terms.update(u for u in c.remote if u)
    return terms


_MODULE_NAME = re.compile(r"[a-z][a-z0-9_]{0,31}")
# work-folder entries a module name must not take over
RESERVED_NAMES = frozenset({"ezbids", "output", "preview", "pre_deface"})


def module_dir(work: Path, module: Module) -> Path:
    """The module's own work folder, <work>/<name>; ValueError for a name that could escape or collide."""
    name = module.name
    if not isinstance(name, str) or not _MODULE_NAME.fullmatch(name) or name in RESERVED_NAMES:
        raise ValueError(f"invalid modality module name: {name!r}")
    return Path(work) / name


_PATH_TAIL = r"""(?:/[^\s'"`,;:)\]}>]*|(?![\w.-]))"""


def redact_paths(text: str, prefixes: Iterable[str], mark: str = "[x]") -> str:
    """text with every path that starts with one of prefixes (a folder, claimed root or URL), tail
    included, replaced by mark; so "<input>/big/H17/x.tif" leaves nothing of the path."""
    items = sorted({p.rstrip("/") for p in prefixes if p and p.rstrip("/")}, key=len, reverse=True)
    if not items:
        return text
    pattern = re.compile(r"(?<![\w.-])(?:" + "|".join(re.escape(p) for p in items) + r")" + _PATH_TAIL)
    return pattern.sub(mark, text)
