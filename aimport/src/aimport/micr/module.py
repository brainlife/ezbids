"""The microscopy modality module: claim, scan into local records, plan entries, write.

Records (``<work>/micr/records.json``) hold input-relative paths, remote URLs, parsed name facts
(donor, dates) and the image facts (``ImageInfo``, acquisition date included). They are local-only,
like ``claim.json``. Plan entries carry only generated text and labels: subject IDs from the
pseudonym key (original ``micr:id=<donor>``), sample labels from numbers, entities from known
vocabulary. ``ImageInfo.acquired`` never leaves the records; scans.tsv dates are written from them.
"""
from __future__ import annotations

import json
import logging
import math
import re
import uuid
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Any, Callable
from urllib.parse import urlsplit

from ..modality import Claim, ModuleOutput, ModulePlan
from ..plan import PlanEntry
from . import discover, names
from .discover import Found

if TYPE_CHECKING:
    from ..agent import LLMClient
    from ..plan import Plan
    from ..pseudonyms import PseudonymKey
    from ..schema import Schema
    from ..scrub import ScrubbedSeries
    from .metadata import ImageInfo

log = logging.getLogger(__name__)

NAME = "micr"
RECORDS_FILE = "records.json"
# micr subject_idx/series_idx start here, so they never collide with ezBIDS's indices
MICR_INDEX_BASE = 1_000_000
CONVERT_OVERHEAD = 1.34  # pyramid levels plus chunk overhead over level 0
DEFAULT_SAMPLE_TYPE = "tissue"
PROGRESS = "reading microscopy metadata ({k} of {n})"
RAW_REASON = "raw interferometer data: reconstruct first"
UNREADABLE_REASON = "could not be read as a microscopy image"
NO_SUFFIX_REASON = "microscopy technique not recognised: choose the suffix"
SIZE_WARNING = "conversion writes about {n:.1f} GB to the work folder"
NO_DONOR = ("microscopy: no donor code was found for {n} subject(s): they get new subject IDs for this "
            "import only, not linked to earlier imports")

# OME Channel AcquisitionMode -> BIDS micr suffix (None: no BIDS suffix for it)
ACQUISITION_MODES: dict[str, str | None] = {
    "SingleMoleculeImaging": None, "LaserScanningConfocalMicroscopy": "CONF", "MultiPhotonMicroscopy": "2PE",
    "BrightField": "BF", "DarkField": "DF", "PhaseContrast": "PC", "DifferentialInterferenceContrast": "DIC",
    "WideField": "FLUO", "SPIM": "SPIM",
}
PSOCT_HINTS = frozenset({"ps-oct", "psoct", "oct", "enface", "reflectivity", "retardance", "orientation",
                         "opticaxis", "cross"})
SPIM_HINTS = frozenset({"visor", "exaspim", "spim", "lightsheet", "light-sheet"})
FORMAT_NAMES = {"ome-zarr": "OME-Zarr", "ome-tiff": "OME-TIFF", "tiff": "TIFF", "visor": "VISoR TIFF",
                "svs": "SVS", "czi": "CZI", "nd2": "ND2", "lif": "LIF", "nifti": "NIfTI", "mat": "MATLAB",
                "raw-psoct": "raw PS-OCT", "unsupported": "microscopy file"}
_UNIT_TEXT = {"um": "µm", "mm": "mm", "nm": "nm"}
_POS_DIR = re.compile(r"(?i)(^|[_\-.])pos\d+$")


# --- scan: records ----------------------------------------------------------------------------


@dataclass
class _Group:
    family: str
    group: str  # local: input-relative folder or file; remote: the URL
    members: list[str] = field(default_factory=list)  # local files read for this record, sorted
    remote: bool = False


def _family_of(input_dir: Path, rel: str) -> str | None:
    """A claimed root's family, again (claim.json keeps only the roots)."""
    path = input_dir / rel
    if path.is_dir():
        return "ome-zarr"
    return discover._family(path.name, path, rel)


def _has_visor_meta(input_dir: Path, folder: str) -> bool:
    here = input_dir / folder
    return any((d / "acqinfo_metadata.json").is_file() for d in (here, here.parent))


def _groups(input_dir: Path, found: list[Found], remote_urls: set[str]) -> list[_Group]:
    """At most one group per image or tile group: VISoR and numbered tiles of one folder share one;
    raw PS-OCT tiles share one per folder; anything else is its own."""
    out: dict[tuple[str, str], _Group] = {}
    for f in sorted(found, key=lambda f: f.rel):
        if f.family == "visor-meta":
            continue
        if f.rel in remote_urls:
            fam = f.family
            if fam == "tiff" and _hint_tokens(urlsplit(f.rel).path) & {"visor"}:
                fam = "visor"
            out[(fam, f.rel)] = _Group(fam, f.rel, [], True)
            continue
        folder = str(PurePosixPath(f.rel).parent)
        if f.family == "raw-psoct":
            out.setdefault(("raw-psoct", folder), _Group("raw-psoct", folder)).members.append(f.rel)
        elif f.family == "tiff" and _has_visor_meta(input_dir, folder):
            out.setdefault(("visor", folder), _Group("visor", folder)).members.append(f.rel)
        elif f.family == "tiff" and names.facts(f.rel).tile is not None:
            out.setdefault(("tiff", folder), _Group("tiff", folder)).members.append(f.rel)
        else:
            out[(f.family, f.rel)] = _Group(f.family, f.rel, [f.rel])
    groups = sorted(out.values(), key=lambda g: (g.group, g.family))
    for g in groups:
        g.members.sort()
    return groups


def _hint_tokens(rel: str) -> set[str]:
    toks: set[str] = set()
    for part in rel.split("/"):
        if part:
            toks |= discover._tokens(part)
    return toks


def _facts_dict(f: names.NameFacts) -> dict:
    d = asdict(f)
    d["dates"] = [x.isoformat() for x in f.dates]
    return d


def info_dict(info: "ImageInfo") -> dict:
    """ImageInfo as JSON for the local records (acquired as an ISO date). Never for the plan or an API."""
    d = asdict(info)
    d["shape"] = list(info.shape)
    d["acquired"] = info.acquired.isoformat() if isinstance(info.acquired, date) else None
    return d


def _remote_visor(url: str) -> tuple[Any, set[str]]:
    """A remote VISoR tile planned from its first page and ``settings.frames_per_file``: counting the
    pages of a remote multi-page TIFF walks every IFD, about one range read per page."""
    import numpy as np
    import tifffile

    from . import readers, remote
    from .metadata import ChannelInfo, ImageInfo, channel_code, collect_terms

    fh, _counter = remote.open_file(url)
    try:
        with tifffile.TiffFile(fh) as tif:
            page = tif.pages.first
            plane = tuple(int(s) for s in page.shape[-2:])
            dtype = str(np.dtype(page.dtype))
            terms, _when = readers._page_terms(page, False)
    finally:
        fh.close()
    meta = remote.sibling_json(url, "acqinfo_metadata.json") or {}
    settings = meta.get("settings") if isinstance(meta.get("settings"), dict) else {}
    frames = settings.get("frames_per_file")
    frames = int(frames) if isinstance(frames, (int, float)) and not isinstance(frames, bool) and frames > 0 else 1
    size, channel = readers.visor_facts(meta)
    terms |= collect_terms(meta)
    axes, shape = ("zyx", (frames, *plane)) if frames > 1 else ("yx", plane)
    channels = [ChannelInfo(channel, None, channel_code(channel, 0))] if channel else [ChannelInfo(None, None, "ch0")]
    info = ImageInfo(family="visor", axes=axes, shape=shape, dtype=dtype, pixel_size=size, pixel_unit="um",
                     channels=channels)
    return info, terms


def _read(input_dir: Path, g: _Group) -> tuple[dict | None, set[str], str | None]:
    """(info, terms, error) for a group: its first member (or the URL) opened for metadata only."""
    from . import readers

    if g.family == "raw-psoct":
        return None, set(), RAW_REASON
    try:
        if g.remote:
            from . import remote

            if g.family == "visor":
                info, terms = _remote_visor(g.group)
                return info_dict(info), terms, None
            src, _counter = remote.open_remote(g.group, g.family)
        else:
            src = readers.open_image(input_dir / g.members[0], g.family)
        try:
            info = info_dict(src.info)
            layout = getattr(src, "zarr_layout", None)
            if layout is not None:  # what layout_refusal decides on at planning (and again at execute)
                from .metadata import channel_count
                from .reference import dataset_dirs, has_source_windows, layout_facts, symlinked

                link = False if g.remote else symlinked(input_dir, g.group, dataset_dirs(layout))
                info["reference_layout"] = layout_facts(layout, src.info.zarr_format, link)
                # whether the written omero windows will be the source's (the QA viewer keeps them) or
                # placeholders (it computes a window from the coarsest level)
                info["reference_layout"]["source_windows"] = has_source_windows(layout.windows,
                                                                                channel_count(src.info))
            return info, set(src.terms), None
        finally:
            src.close()
    except readers.UnsupportedFormat as exc:
        return None, set(), str(exc)
    except Exception as exc:  # noqa: BLE001 - one unreadable input must not stop the scan
        log.warning("microscopy input could not be read: %s", type(exc).__name__)
        return None, set(), UNREADABLE_REASON


def _where(rec: dict) -> str:
    """The path text a record is planned from: its first file (input-relative), the raw folder, or
    the URL's path without the host. Local-only, like the record."""
    if "url" in rec:
        return urlsplit(rec["url"]).path.lstrip("/")
    if rec["family"] != "raw-psoct" and rec.get("members"):
        return rec["members"][0]
    return rec["rel"]


_PATH_STYLE_S3 = re.compile(r"s3(?:[.-][a-z0-9-]+)?\.amazonaws\.com", re.I)


def remote_key(url: str) -> str:
    """The object key of a remote source (its URL path without the bucket of a path-style S3 URL)."""
    parts = urlsplit(url)
    path = parts.path.lstrip("/")
    if _PATH_STYLE_S3.fullmatch(parts.hostname or ""):
        path = path.split("/", 1)[1] if "/" in path else ""
    return path


def remote_donor(path: str) -> str | None:
    """The donor of a remote source (``path``: its object key, ``remote_key``): the first donor-like
    segment walking down every folder from the top (``CMC/Derivatives/Moe/PS-OCT/...`` gives Moe), else
    the file or store name; names.facts applied to each segment alone. The top folder under the
    bucket is a project (``CMC/...``), never a donor. Folders come first because file names carry
    contrast codes that look like donors (``Slice_001_EnR_hdr``: EnR, hdr)."""
    parts = [p for p in path.split("/") if p]
    if not parts:
        return None
    for seg in [*parts[1:-1], parts[-1]]:
        if seg.startswith("sub-") and len(seg) > 4:
            return seg[4:]
        donor = names.facts(seg).donor
        if donor:
            return donor
    return None


def _remote_group(rec: dict) -> str:
    """The run-local subject of a remote record without a donor: records under the same parent folder
    (contrast folders such as Reflectivity/ and Retardance/ skipped) with the same slice share one."""
    parts = urlsplit(rec["url"])
    folders = [p for p in remote_key(rec["url"]).split("/") if p][:-1]
    while folders and names.facts(folders[-1]).contrast:
        folders.pop()
    return f"url:{parts.hostname}/{'/'.join(folders)}|slice={rec['facts'].get('slice')}"


def _url_terms(url: str) -> set[str]:
    parts = urlsplit(url)
    terms = {url, parts.netloc}
    terms |= {p for p in parts.netloc.split(".") if len(p) >= 3}
    terms |= names.path_terms([parts.path.lstrip("/")])
    return terms


def scan_records(input_dir: Path, claim: Claim, found: list[Found] | None,
                 progress: Callable[[str], None]) -> list[dict]:
    input_dir = Path(input_dir)
    if found is None:  # re-derive the families from the claim (claim.json keeps only roots and URLs)
        found = []
        for rel in claim.roots:
            fam = _family_of(input_dir, rel)
            if fam:
                found.append(Found(rel, fam, rel))
        from . import remote as _remote

        for url in claim.remote:
            try:
                fam = _remote.probe(url)
            except Exception as exc:  # noqa: BLE001
                log.warning("remote source skipped: %s", type(exc).__name__)
                continue
            if fam in _remote.ALLOWED_FAMILIES:
                found.append(Found(url, fam, url))
    groups = _groups(input_dir, found, set(claim.remote))
    records = []
    for k, g in enumerate(groups, 1):
        progress(PROGRESS.format(k=k, n=len(groups)))
        info, terms, error = _read(input_dir, g)
        rec: dict[str, Any] = {"url": g.group} if g.remote else {"rel": g.group}
        rec.update(family=g.family, group=g.group, members=list(g.members))
        where = _where(rec)
        facts = names.facts(g.members[0] if g.family == "raw-psoct" else where)
        terms |= names.path_terms([where, *g.members])
        if g.remote:
            facts.donor = remote_donor(remote_key(g.group))
            terms |= _url_terms(g.group)
            if facts.donor:
                terms.add(facts.donor)
        if error and error not in (RAW_REASON, UNREADABLE_REASON):
            error = _clean_error(error, terms)
        rec.update(facts=_facts_dict(facts), info=info, error=error, terms=sorted(terms))
        records.append(rec)
    return records


_QUOTED = re.compile("'[^']*'|\"[^\"]*\"")


def _clean_error(message: str, terms: set[str]) -> str:
    """A reader's UnsupportedFormat message for the plan: quoted values (axis names and the like,
    read from the file) dropped, then redacted with the record's terms."""
    from ..scrub import redact

    return redact(_QUOTED.sub("(value not shown)", message), terms)


def load_records(work: Path) -> list[dict]:
    path = Path(work) / RECORDS_FILE
    if not path.is_file():
        return []
    return list(json.loads(path.read_text()))


# --- plan ---------------------------------------------------------------------------------------


def _suffix(rec: dict, hints: set[str]) -> tuple[str | None, str]:
    facts, info = rec["facts"], rec.get("info") or {}
    if facts.get("contrast") or hints & PSOCT_HINTS:
        return "OCT", "PS-OCT contrast or name"
    if rec["family"] == "visor" or hints & SPIM_HINTS:
        return "SPIM", "light-sheet (VISoR, exaSPIM) name"
    mode = info.get("acquisition_mode")
    if mode in ACQUISITION_MODES and ACQUISITION_MODES[mode]:
        return ACQUISITION_MODES[mode], "OME acquisition mode"
    return None, NO_SUFFIX_REASON


OME_IMMERSION = frozenset({"Oil", "Water", "WaterDipping", "Air", "Multi", "Glycerol", "Other"})


def micr_view(records: list[dict]) -> list["ScrubbedSeries"]:
    """The agent's view of each readable record: image facts and generic layout words only.

    Never a path, a name, a date, an OME string or the acquisition date (``acquired``). Hints are
    tokens of ``names.VOCAB``; the pixel size, wavelengths and objective are numbers and enums.
    """
    from ..scrub import ScrubbedSeries

    out = []
    for i, rec in enumerate(records):
        info = rec.get("info")
        if info is None:
            continue
        axes, shape = info.get("axes", ""), info.get("shape") or []
        channels = info.get("channels") or []
        hints = sorted(t for t in _hint_tokens(_where(rec)) if names.is_vocab(t))
        suffix, _ = _suffix(rec, set(hints))
        size = info.get("pixel_size") or {}
        fields = {
            "Dimensions": {a: int(n) for a, n in zip(axes, shape)},
            "PixelSize": [size[a] for a in "xyz" if a in size],
            "PixelSizeUnits": info.get("pixel_unit"),
            "ChannelCount": len(channels),
            "ExcitationWavelengths": [c["excitation_nm"] for c in channels if c.get("excitation_nm") is not None],
            "EmissionWavelengths": [c["emission_nm"] for c in channels if c.get("emission_nm") is not None],
            "ObjectiveMagnification": info.get("objective_magnification"),
            "ObjectiveNA": info.get("objective_na"),
            "Immersion": info.get("immersion") if info.get("immersion") in OME_IMMERSION else None,
            "FormatFamily": rec["family"],
            "Levels": info.get("levels", 1),
            "DataType": info.get("dtype"),
            "Hints": hints,
        }
        out.append(ScrubbedSeries(MICR_INDEX_BASE + i, "", "", f"micr/{suffix or 'unknown'}", fields))
    return out


def _apply_agent(mp: ModulePlan, records: list[dict], client: "LLMClient | None", schema: "Schema",
                 terms: set[str]) -> None:
    """Ask the agent about the readable entries and apply the planner's agreement rules."""
    from ..agent import MICR_CLASSIFY_SYSTEM, MICR_GENERATED, classify
    from ..planner import AGENT_MIN, AGREE_MIN, DISAGREE_CONFIDENCE, _agent_text, _guess_text, _usable

    if client is None:
        return
    view = micr_view(records)
    mp.view = view
    by_idx = {e.series_idx: e for e in mp.entries}
    heuristic = {s.series_idx: ("micr", by_idx[s.series_idx].suffix, {}) for s in view
                 if s.series_idx in by_idx and by_idx[s.series_idx].suffix}
    for g in classify(view, heuristic, client, schema, MICR_CLASSIFY_SYSTEM, ("micr",), MICR_GENERATED):
        e = by_idx.get(g.series_idx)
        if e is None or g.datatype is None or e.status not in ("ok", "unknown"):
            continue
        extra = {k: v for k, v in g.entities.items() if k in ("acquisition", "stain") and _usable(v, terms)}
        if e.suffix and g.suffix == e.suffix:
            e.confidence = max(AGREE_MIN, g.confidence)
            for k, v in extra.items():
                e.entities.setdefault(k, v)
        elif e.suffix:
            if g.confidence >= AGENT_MIN:
                e.confidence = DISAGREE_CONFIDENCE
                e.agent_note = _agent_text(_guess_text(g), terms)
        elif g.confidence >= AGENT_MIN:
            e.suffix, e.source, e.confidence = g.suffix, "agent", g.confidence
            e.status, e.exclude = "ok", False
            e.reason = _agent_text(g.reason, terms) or "agent"
            for k, v in extra.items():
                e.entities.setdefault(k, v)
        else:
            e.agent_note = _agent_text(_guess_text(g), terms)


def _level0_bytes(info: dict) -> int:
    import numpy as np

    try:
        itemsize = np.dtype(info.get("dtype")).itemsize
    except TypeError:
        itemsize = 2
    return math.prod(int(s) for s in info.get("shape") or [0]) * itemsize


def describe(rec: dict, write_mode: str) -> str:
    """Generated text only: format, channels, size, pixel size, how it is written. Never path text."""
    fam = rec["family"]
    info = rec.get("info")
    name = FORMAT_NAMES.get(fam, "microscopy image")
    n = len(rec.get("members") or [])
    if info is None:
        what = f"{name} ({n} files)" if n > 1 else name
        return f"{what}; not readable"
    if fam == "ome-zarr" and info.get("ngff_version"):
        name += f" {info['ngff_version']}"
    parts = [name]
    channels = len(info.get("channels") or [])
    if channels:
        parts.append(f"{channels} channel{'s' if channels != 1 else ''}")
    axes, shape = info.get("axes", ""), info.get("shape") or []
    dims = [str(shape[axes.index(a)]) for a in "xyz" if a in axes and axes.index(a) < len(shape)]
    if dims:
        parts.append("×".join(dims))
    x = (info.get("pixel_size") or {}).get("x")
    if x:
        unit = info.get("pixel_unit")
        parts.append(f"{x:g} {_UNIT_TEXT.get(unit, 'µm')}" if unit else f"{x:g} (unit unknown)")
    if n > 1:
        parts.append(f"{n} tiles")
    tail = "reference (no copy)" if write_mode == "reference" else "converted to OME-Zarr"
    return ", ".join(parts) + "; " + tail


def _sample_key(where: str) -> str:
    """Records with no slice or sample label share a sample when they come from one folder (tile
    positions Pos0, Pos1 ... of one acquisition included)."""
    parent = PurePosixPath(where).parent
    if _POS_DIR.search(parent.name):
        parent = parent.parent
    return str(parent)


def _input_label(where: str, prefix: str) -> str | None:
    """The input's own <prefix>-<label>: a folder, or an entity of a BIDS file name (sub-01_sample-A_...)."""
    for part in where.split("/"):
        for piece in part.split("_"):
            piece = piece.split(".")[0]
            if piece.startswith(prefix + "-") and len(piece) > len(prefix) + 1:
                return piece[len(prefix) + 1:]
    return None


def _stain(rec: dict) -> str | None:
    nm = rec["facts"].get("channel_nm")
    if nm:
        return f"ch{int(nm)}"
    channels = (rec.get("info") or {}).get("channels") or []
    if len(channels) == 1 and channels[0].get("excitation_nm"):
        return f"ch{round(channels[0]['excitation_nm'])}"
    return None


def plan_entries(records: list[dict], key: "PseudonymKey", existing: set[str], schema: "Schema",
                 target: str, client: "LLMClient | None" = None) -> ModulePlan:
    from ..brainlife_map import to_brainlife
    from ..planner import _check_nameable, _usable, check_pixel_size
    from .reference import layout_refusal

    terms: set[str] = set()
    for rec in records:
        terms |= set(rec.get("terms") or [])
    run = uuid.uuid4().hex
    mp = ModulePlan()

    # subjects: one per donor; records without one share a run-local subject per top-level folder
    wheres = [_where(r) for r in records]
    originals: list[str] = []
    no_donor: dict[str, str] = {}
    for rec, where in zip(records, wheres):
        donor = rec["facts"].get("donor")
        if donor:
            originals.append("micr:id=" + donor)
        else:
            top = _remote_group(rec) if "url" in rec else where.split("/")[0]
            originals.append(no_donor.setdefault(top, f"run:{run}:micr{len(no_donor)}"))
    order = list(dict.fromkeys(originals))
    subject_idx = {o: MICR_INDEX_BASE + i for i, o in enumerate(order)}
    subject_ids: dict[str, str] = {}
    for o in order:
        i = originals.index(o)
        donor = records[i]["facts"].get("donor")
        label = _input_label(wheres[i], "sub")
        # the input's own sub- label, when it is a plain number (a code like H17 identifies the donor)
        proposed = (label if label and label == donor and label.isdigit() and _usable(label, terms - {label})
                    else None)
        subject_ids[o] = key.subject_id(o, existing, proposed)
        if label and label == donor:
            mp.labels[subject_idx[o]] = label
    if no_donor:
        mp.warnings.append(NO_DONOR.format(n=len(no_donor)))

    # sessions: only when the input has ses- folders
    session_of: list[tuple[str | None, int]] = []
    ses_seen: dict[int, dict[str, tuple[str, int]]] = defaultdict(dict)
    for o, where in zip(originals, wheres):
        raw = _input_label(where, "ses")
        if raw is None:
            session_of.append((None, 0))
            continue
        seen = ses_seen[subject_idx[o]]
        if raw not in seen:
            n = len(seen)
            seen[raw] = (raw if _usable(raw, terms) else str(n + 1), n)
        session_of.append(seen[raw])

    # samples: slice<NNN>, else the input's sample- label, else 1, 2, ... per subject
    samples: list[str] = []
    numbered: dict[tuple[int, str], str] = {}
    taken: dict[int, set[str]] = defaultdict(set)
    pending: list[tuple[int, int, str]] = []
    for i, (rec, o, where) in enumerate(zip(records, originals, wheres)):
        sidx = subject_idx[o]
        if rec["facts"].get("slice") is not None:
            samples.append(f"slice{int(rec['facts']['slice']):03d}")
        else:
            label = _input_label(where, "sample")
            samples.append(label if label and _usable(label, terms) else "")
            if not samples[-1]:
                pending.append((i, sidx, _sample_key(where)))
        if samples[-1]:
            taken[sidx].add(samples[-1])
    for i, sidx, skey in pending:
        if (sidx, skey) not in numbered:
            n = 1
            while str(n) in taken[sidx]:
                n += 1
            numbered[(sidx, skey)] = str(n)
            taken[sidx].add(str(n))
        samples[i] = numbered[(sidx, skey)]

    entries: list[PlanEntry] = []
    convert_bytes = 0
    for i, (rec, o, where) in enumerate(zip(records, originals, wheres)):
        info = rec.get("info")
        hints = _hint_tokens(where)
        suffix, why = _suffix(rec, hints)
        session, session_idx = session_of[i]
        entities = {"sample": samples[i]}
        if rec["facts"].get("contrast"):
            entities["acquisition"] = rec["facts"]["contrast"]
        stain = _stain(rec)
        if stain:
            entities["stain"] = stain
        if rec["family"] == "raw-psoct":
            d = dict(status="unsupported", exclude=True, reason=RAW_REASON)
            write_mode = ""
        elif info is None:
            d = dict(status="unsupported", exclude=True, reason=rec.get("error") or UNREADABLE_REASON)
            write_mode = ""
        elif is_mosaic(rec):
            d = dict(status="unsupported", exclude=True, reason=MOSAIC_REASON)
            write_mode = ""
        elif rec["family"] == "ome-zarr" and layout_refusal(info.get("reference_layout")):
            d = dict(status="unsupported", exclude=True, reason=layout_refusal(info.get("reference_layout")))
            write_mode = ""
        else:
            write_mode = "reference" if rec["family"] == "ome-zarr" else "convert"
            d = (dict(status="ok", exclude=False, reason=f"microscopy heuristic: {why}") if suffix
                 else dict(status="unknown", exclude=True, reason=why))
        n_files = max(1, len(rec.get("members") or []))
        output = int(_level0_bytes(info) * n_files * CONVERT_OVERHEAD) if write_mode == "convert" else 0
        spatial, sizes, units = pixel_size_of(info)
        entries.append(PlanEntry(
            id=f"m{i}-sub{subject_idx[o]}-ses{session_idx}", series_idx=MICR_INDEX_BASE + i,
            subject_idx=subject_idx[o], session_idx=session_idx, subject=subject_ids[o], session=session,
            datatype="micr", suffix=suffix, entities=entities, brainlife_datatype=None, brainlife_tags=[],
            source="heuristic" if suffix else "none", confidence=0.8 if suffix else 0.0, reason=d["reason"],
            deface=False, exclude=d["exclude"], status=d["status"], description=describe(rec, write_mode),
            modality="micr", sample_type=DEFAULT_SAMPLE_TYPE, write_mode=write_mode, output_bytes=output,
            pixel_size=sizes, pixel_size_units=units, spatial_axes=spatial,
        ))
        if write_mode and "rel" in rec:
            for m in rec.get("members") or [rec["rel"]]:
                mp.images[m] = None

    _chunks(entries, records)
    mp.entries = entries
    _apply_agent(mp, records, client, schema, terms)
    for e in entries:
        if e.status == "ok":
            d = dict(datatype=e.datatype, suffix=e.suffix, entities=e.entities, status=e.status,
                     exclude=e.exclude, reason=e.reason)
            _check_nameable(d, e.subject, e.session, schema, "micr")
            check_pixel_size(d, e)
            e.status, e.exclude, e.reason = d["status"], d["exclude"], d["reason"]
        if e.status == "ok":
            e.brainlife_datatype, e.brainlife_tags = to_brainlife(e.datatype, e.suffix, e.entities, {})
            if target == "datatypes" and e.brainlife_datatype is None:
                e.exclude, e.reason = True, e.reason + "; no brainlife datatype"
        if e.write_mode == "convert" and not e.exclude:
            convert_bytes += e.output_bytes
    if any(e.write_mode == "convert" and not e.exclude for e in entries):
        mp.warnings.append(SIZE_WARNING.format(n=convert_bytes / 1e9))
    mp.entries = entries
    return mp


MOSAIC_REASON = "tile mosaic: stitch first (aimport converts single images and VISoR stacks)"


def is_mosaic(rec: dict) -> bool:
    """Several files that are tiles of one plane (not VISoR frame stacks): aimport cannot stitch them."""
    return rec["family"] not in ("visor", "raw-psoct") and len(rec.get("members") or []) > 1


def pixel_size_of(info: dict | None) -> tuple[str, list[float] | None, str | None]:
    """(spatial axes among "xyz", pixel size x, y[, z] or None when an axis is missing, units)."""
    if not info:
        return "", None, None
    axes = info.get("axes") or ""
    spatial = "".join(a for a in "xyz" if a in axes)
    size = info.get("pixel_size") or {}
    values = [size.get(a) for a in spatial]
    if not spatial or any(not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v) or v <= 0
                          for v in values):
        return spatial, None, info.get("pixel_unit")
    return spatial, [float(v) for v in values], info.get("pixel_unit")


def _chunks(entries: list[PlanEntry], records: list[dict]) -> None:
    """chunk=<position or tile> for the entries of one sample that would otherwise share a name."""
    groups: dict[tuple, list[int]] = defaultdict(list)
    for i, e in enumerate(entries):
        if not e.write_mode:
            continue
        groups[(e.subject_idx, e.session, e.suffix, tuple(sorted(e.entities.items())))].append(i)
    for idxs in groups.values():
        if len(idxs) < 2:
            continue
        for field_name in ("position", "tile"):
            values = [records[i]["facts"].get(field_name) for i in idxs]
            if None not in values and len(set(values)) == len(values):
                break
        else:
            values = list(range(len(idxs)))
        for i, v in zip(idxs, values):
            entries[i].entities["chunk"] = str(int(v))


# --- the module ---------------------------------------------------------------------------------


class MicrModule:
    """BIDS ``micr``: OME-Zarr (referenced), OME-TIFF, TIFF, VISoR, SVS, CZI/ND2/LIF, PS-OCT NIfTI/MAT."""

    name = NAME

    def __init__(self) -> None:
        self._found: tuple[Claim, list[Found]] | None = None

    def claim(self, input_dir: Path, remote: list[str]) -> Claim:
        c, found = discover.claim(Path(input_dir), remote)
        self._found = (Claim(list(c.roots), list(c.remote)), found)
        return c

    def scan(self, input_dir: Path, claim: Claim, work: Path, progress: Callable[[str], None]) -> None:
        found = None
        if self._found is not None and self._found[0].roots == list(claim.roots) \
                and self._found[0].remote == list(claim.remote):
            found = self._found[1]
        records = scan_records(Path(input_dir), claim, found, progress)
        work = Path(work)
        work.mkdir(parents=True, exist_ok=True)
        (work / RECORDS_FILE).write_text(json.dumps(records, indent=1))

    def terms(self, work: Path) -> set[str]:
        terms: set[str] = set()
        for rec in load_records(work):
            terms |= set(rec.get("terms") or [])
        return terms

    def plan(self, work: Path, key: "PseudonymKey", existing: set[str], client: "LLMClient | None",
             schema: "Schema", target: str) -> ModulePlan:
        return plan_entries(load_records(work), key, existing, schema, target, client)

    def write(self, plan: "Plan", work: Path, input_dir: Path, terms: set[str], key: "PseudonymKey",
              schema: "Schema", dest: Callable[[str], Path],
              progress: Callable[[str], None] | None = None) -> ModuleOutput:
        return write_entries(plan, load_records(work), Path(input_dir), terms, key, schema, dest, progress)


# --- write ----------------------------------------------------------------------------------------

WRITE_PROGRESS = "writing microscopy image {k} of {n}"


def _acquired(rec: dict) -> date | None:
    """The record's acquisition date (ImageInfo.acquired), else the first date in its name. Used for
    scans.tsv acq_time only, shifted by the subject's offset; never written anywhere else."""
    raw = (rec.get("info") or {}).get("acquired") or next(iter(rec["facts"].get("dates") or []), None)
    try:
        return date.fromisoformat(raw) if raw else None
    except (TypeError, ValueError):
        return None


def _acq_time(day: date | None, offset_days: int) -> str:
    if day is None:
        return "n/a"
    try:
        return (day + timedelta(days=offset_days)).isoformat() + "T00:00:00"
    except OverflowError:
        return "n/a"


def _inside_input(input_dir: Path, rel: str) -> Path:
    """An input-relative member path, refused when it leaves the input folder (also through links)."""
    root = input_dir.resolve()
    path = (input_dir / rel).resolve()
    if root != path and root not in path.parents:
        raise ValueError("a microscopy input lies outside the input folder")
    return path


CONVERT_BLOCK_SIZE = 2**12  # remote read-ahead while converting (each block is read once, in pieces)


def _remote_cap(rec: dict) -> int:
    from .remote import DEFAULT_MAX_BYTES

    return max(DEFAULT_MAX_BYTES, 2 * _level0_bytes(rec.get("info") or {}) + 64 * 2**20)


def open_record(rec: dict, input_dir: Path) -> Any:
    """The ImageSource of a record for conversion: its file, its tiles stacked along z (VISoR), or
    its URL read by range requests."""
    from . import readers
    from .convert import stack_sources

    if "url" in rec:
        from . import remote

        src, _counter = remote.open_remote(rec["url"], rec["family"], max_bytes=_remote_cap(rec),
                                           block_size=CONVERT_BLOCK_SIZE)
        return src
    members = list(rec.get("members") or [rec["rel"]])
    if len(members) > 1 and rec["family"] != "visor":
        raise NotImplementedError("tile groups other than VISoR positions cannot be converted yet")
    sources = []
    try:
        for m in members:
            sources.append(readers.open_image(_inside_input(input_dir, m), rec["family"]))
        return stack_sources(sources)
    except BaseException:
        for s in sources:
            s.close()
        raise


def open_reference(rec: dict, input_dir: Path) -> Any:
    """The OME-Zarr ImageSource of a reference record, for its metadata only (no chunk is read):
    the store in the input folder, or the remote store under the default byte cap."""
    from . import readers

    if rec.get("family") != "ome-zarr":
        raise ValueError("only an OME-Zarr input can be referenced")
    if "url" in rec:
        from . import remote

        src, _counter = remote.open_remote(rec["url"], "ome-zarr")
        return src
    return readers.open_image(_inside_input(input_dir, rec["rel"]), "ome-zarr")


def reference_location(rec: dict) -> dict[str, str]:
    """The chunk-map source of a reference record's store: its input-relative folder or its URL."""
    if "url" in rec:
        from .remote import normalize_url

        return {"url": normalize_url(rec["url"])}
    return {"input": PurePosixPath(rec["rel"]).as_posix()}


def with_plan_pixel_size_check(e: PlanEntry) -> None:
    from .metadata import PixelSizeUnknown, _UNIT_M

    if e.pixel_size is None or e.pixel_size_units not in _UNIT_M or \
            (e.spatial_axes and len(e.pixel_size) != len(e.spatial_axes)):
        raise PixelSizeUnknown("pixel size unknown: set it in the plan")


def _names(entries: list[PlanEntry], schema: "Schema") -> dict[str, str]:
    """entry id -> output path (relative to the BIDS folder); a run- index for names that would clash."""
    def name(e: PlanEntry, entities: dict[str, str]) -> str:
        return schema.filename(e.subject, e.session, "micr", e.suffix, entities, ".ome.zarr/").rstrip("/")

    names = {e.id: name(e, e.entities) for e in entries}
    counts: dict[str, int] = defaultdict(int)
    for n in names.values():
        counts[n] += 1
    taken = {n for n, c in counts.items() if c == 1}
    for e in entries:
        if counts[names[e.id]] > 1:
            for run in range(1, len(entries) + 2):
                n = name(e, {**e.entities, "run": str(run)})
                if n not in taken:
                    break
            names[e.id] = n
            taken.add(n)
    return names


def write_entries(plan: "Plan", records: list[dict], input_dir: Path, terms: set[str], key: "PseudonymKey",
                  schema: "Schema", dest: Callable[[str], Path],
                  progress: Callable[[str], None] | None = None) -> ModuleOutput:
    """Write every included micr entry with its sidecar, check what was written, and return the rows
    for participants, samples and scans. Convert entries become OME-Zarr in the configured version;
    reference entries (OME-Zarr inputs) get only new metadata (micr/reference.py), in their source's
    format, and their arrays go into ``out.chunk_map``."""
    from ..scrub import redact
    from . import NGFF_VERSION
    from .convert import check_ome_zarr, to_ome_zarr
    from .metadata import sidecar, with_plan_pixel_size
    from .reference import (chunk_map, dataset_dirs, ngff_version_for, source_factors, symlinked,
                            write_reference)

    out = ModuleOutput()
    entries = [e for e in plan.entries if e.modality == "micr" and e.datatype == "micr" and e.status == "ok"
               and not e.exclude and e.suffix and e.write_mode]
    for e in entries:  # defence in depth: the planner makes these unsupported or unknown
        i = e.series_idx - MICR_INDEX_BASE
        if 0 <= i < len(records) and is_mosaic(records[i]):
            raise NotImplementedError(MOSAIC_REASON)
        with_plan_pixel_size_check(e)
    names = _names(entries, schema)
    samples: dict[tuple[str, str], dict[str, str]] = {}
    arrays: dict[str, dict] = {}
    for k, e in enumerate(entries, 1):
        i = e.series_idx - MICR_INDEX_BASE
        if not 0 <= i < len(records) or records[i].get("info") is None:
            raise ValueError("a microscopy plan entry has no scan record: scan again")
        rec = records[i]
        if progress is not None:
            progress(WRITE_PROGRESS.format(k=k, n=len(entries)))
        rel = names[e.id]
        reference = e.write_mode == "reference"
        src = open_reference(rec, input_dir) if reference else open_record(rec, input_dir)
        try:
            src.info.acquired = None
            # the plan's pixel size (from the source or the reviewer); never an invented one
            info = src.info = with_plan_pixel_size(src.info, e)
            path = dest(rel)
            levels = None
            if reference:  # the source's Zarr format; metadata only, the chunks stay at the source
                version = ngff_version_for(info.zarr_format)
                layout = src.zarr_layout
                link = "rel" in rec and symlinked(input_dir, rec["rel"], dataset_dirs(layout))
                written = write_reference(src, reference_location(rec), path, info, terms=terms, symlink=link)
                for sub, facts in written.items():
                    if f"{rel}/{sub}" in arrays:
                        raise ValueError("two referenced arrays share an output path")
                    arrays[f"{rel}/{sub}"] = facts
                levels = source_factors(info, layout)
            else:
                version = NGFF_VERSION
                step = (lambda msg, k=k: progress(f"{WRITE_PROGRESS.format(k=k, n=len(entries))}: {msg}")) \
                    if progress is not None else None
                to_ome_zarr(src, path, version, step)
            # numbers and vocabulary only; strings are redacted anyway (numbers are not: a pixel size
            # equal to a path number is not identifying, and must match the NGFF scale)
            car = {k: redact(v, terms) if isinstance(v, str) else v for k, v in sidecar(info, e).items()}
            check_ome_zarr(path, car, version, info.shape, info.dtype, reference=reference, level_factors=levels)
        finally:
            src.close()
        stem = rel[: -len(".ome.zarr")]
        dest(stem + ".json").write_text(json.dumps(car, indent=2) + "\n", encoding="utf-8")
        out.manifest.setdefault(e.id, []).append(rel)
        out.participants.setdefault(e.subject, {"age": "n/a", "sex": "n/a"})
        base = f"sub-{e.subject}" + (f"/ses-{e.session}" if e.session else "")
        offset = key.date_offset_days(e.subject)
        out.scans.setdefault((e.subject, e.session), []).append(
            (rel[len(base) + 1:], _acq_time(_acquired(rec), offset)))
        sample = e.entities.get("sample")
        if sample:
            samples.setdefault((e.subject, sample), {
                "sample_id": f"sample-{sample}", "participant_id": f"sub-{e.subject}",
                "sample_type": e.sample_type or DEFAULT_SAMPLE_TYPE})
        if "rel" in rec:
            for m in rec.get("members") or [rec["rel"]]:
                out.images[m] = rel
        label = _input_label(_where(rec), "sub")
        if label and label == rec["facts"].get("donor"):
            out.labels[e.subject_idx] = label  # as planned: supplied tables link their rows by it
    out.samples = [samples[k] for k in sorted(samples)]
    if arrays:
        out.chunk_map = chunk_map(arrays)
    return out
