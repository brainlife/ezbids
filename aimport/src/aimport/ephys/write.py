"""The MNE-BIDS writer for eeg, ieeg, emg and meg (Task 9).

One recording at a time, already de-identified in memory (``deid.clean``):

1. ``write_raw_bids`` into the scratch folder ``work/ephys/scratch`` with an explicit output ``format`` and
   ``anonymize={"daysback": d, "keep_his": False, "keep_source": False}``, so the file is always converted
   (never a copy of the source);
2. the post-write header pass: ``headers.rewrite_edf`` (EDF/BDF), ``headers.rebuild_vhdr`` and
   ``headers.check_vmrk`` (BrainVision);
3. every JSON sidecar rebuilt from the schema's keys for its suffix (``rebuild_sidecar``), every TSV cell
   through ``scrub.redact``;
4. the recording's files and per-run sidecars moved to ``dest(rel)``. MNE-BIDS's own ``participants.*``,
   ``dataset_description.json``, ``README`` and ``scans.tsv`` are left in the scratch folder (deleted by the
   caller); ``*_headshape.pos`` only moves with ``keep_headshape``.
"""
from __future__ import annotations

import json
import shutil
from datetime import date, datetime
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Any, Callable

from ..scrub import redact, scrub_sidecar
from . import OUTPUT_FORMATS, headers

if TYPE_CHECKING:
    from ..plan import PlanEntry
    from ..schema import Schema

ANON_LIMIT = date(1924, 12, 31)  # the latest anonymized date: before 1925-01-01 (BIDS)
ALWAYS_DROP = frozenset({"InstitutionName", "InstitutionAddress", "InstitutionalDepartmentName",
                         "DeviceSerialNumber"})
# written by MNE-BIDS for the whole dataset or session: aimport writes its own (writer.py)
DISCARDED = frozenset({"README", "README.md", "README.rst", "README.txt", "dataset_description.json",
                       "participants.tsv", "participants.json"})
TABULAR = frozenset({"events", "channels", "electrodes", "optodes"})
EXTENSIONS = {"BrainVision": ".vhdr", "EDF": ".edf", "BDF": ".bdf", "FIF": ".fif"}
EMG_PLACEMENT = "Other"
EMG_PLACEMENT_TEXT = "not recorded in the source recording"


def daysback(dates: list[datetime], offset_days: int) -> int:
    """The smallest ``d`` with ``max(dates) - d days`` before 1925-01-01, plus ``abs(offset_days)``.

    The same ``d`` for every recording of a subject keeps the intervals between them. No date: just the
    offset (MNE-BIDS then has nothing to shift)."""
    days = [d.date() if isinstance(d, datetime) else d for d in dates if d is not None]
    base = max(0, (max(days) - ANON_LIMIT).days) if days else 0
    return base + abs(int(offset_days))


def rebuild_sidecar(path: Path, schema: "Schema", datatype: str, suffix: str, terms: set[str],
                    overrides: dict[str, Any] | None = None, columns: list[str] | None = None) -> dict:
    """Rewrite a JSON sidecar with only the keys the schema lists for ``<datatype>/<suffix>`` (and, for a
    tabular sidecar, the columns of its TSV), never the institution keys or ``DeviceSerialNumber``; then
    ``overrides`` (generated values) and ``scrub.scrub_sidecar``. Returns what was written."""
    path = Path(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    allowed = set(schema.sidecar_fields(datatype, suffix)) | set(columns or ())
    out = {k: v for k, v in (data if isinstance(data, dict) else {}).items()
           if k in allowed and k not in ALWAYS_DROP}
    for k, v in (overrides or {}).items():
        if v is None:
            out.pop(k, None)
        elif k in allowed and k not in ALWAYS_DROP:
            out[k] = v
    out = scrub_sidecar(out, terms)
    path.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return out


def redact_tsv(path: Path, terms: set[str]) -> list[str]:
    """Every cell through ``scrub.redact`` (in place); returns the header."""
    path = Path(path)
    lines = path.read_text(encoding="utf-8").splitlines()
    rows = [[redact(c, terms) for c in line.split("\t")] for line in lines]
    path.write_text("".join("\t".join(r) + "\n" for r in rows), encoding="utf-8")
    return rows[0] if rows else []


def _suffix_of(name: str) -> str:
    stem = name.split(".", 1)[0]
    return stem.rsplit("_", 1)[-1]


def _files(root: Path) -> dict[Path, tuple[int, int]]:
    return {p: (p.stat().st_mtime_ns, p.stat().st_size) for p in root.rglob("*") if p.is_file()}


def _session_prefix(bp) -> str:
    return f"sub-{bp.subject}" + (f"_ses-{bp.session}" if bp.session else "")


def _session_dir(bp) -> str:
    return f"sub-{bp.subject}" + (f"/ses-{bp.session}" if bp.session else "")


def write_recording(entry: "PlanEntry", rec: dict, raw, scratch: Path, dest: Callable[[str], Path],
                    schema: "Schema", terms: set[str], er_path=None, *, days_back: int,
                    labels: set[str], er_rel: str | None = None, keep: bool = False,
                    meta: dict | None = None, written: list | None = None) -> list[str]:
    """Write one de-identified recording through MNE-BIDS; returns the output rel paths (data file first).

    ``er_path``: the empty-room recording's BIDSPath in the same scratch root (passed to MNE-BIDS as
    ``empty_room``) and ``er_rel`` its output path, which ``AssociatedEmptyRoom`` is rewritten to.
    ``labels``: the event labels the recording may carry (EDF TAL, ``.vmrk``). ``keep``: copy the data
    file instead of moving it (an empty-room recording later MEG recordings refer to). ``written``: when
    given, the scratch BIDSPath is appended to it.
    """
    import mne_bids

    datatype, fmt = entry.datatype, entry.ephys_format
    if datatype not in ("eeg", "ieeg", "emg", "meg") or fmt not in OUTPUT_FORMATS.get(datatype, ()) \
            or fmt not in EXTENSIONS:
        raise ValueError(f"{fmt or 'no format'} cannot be written for {datatype or 'an unknown datatype'}")
    ents = entry.entities or {}
    scratch = Path(scratch)
    bp = mne_bids.BIDSPath(subject=entry.subject, session=entry.session, task=ents.get("task"),
                           acquisition=ents.get("acq"), run=ents.get("run"), datatype=datatype, root=scratch)
    before = _files(scratch) if scratch.exists() else {}
    kw: dict[str, Any] = {}
    if datatype == "emg":
        kw["emg_placement"] = EMG_PLACEMENT
    out_bp = mne_bids.write_raw_bids(
        raw, bp, anonymize={"daysback": int(days_back), "keep_his": False, "keep_source": False},
        format=fmt, empty_room=er_path, allow_preload=bool(raw.preload), overwrite=True, verbose=False, **kw)
    if written is not None:
        written.append(out_bp)
    after = _files(scratch)
    produced = sorted(p for p, st in after.items() if before.get(p) != st)

    # scratch name -> output name: the same entities, except the date session MNE-BIDS gives an empty room
    src_prefix, dst_prefix = _session_prefix(out_bp), _session_prefix(bp.copy().update(session=entry.session))
    src_dir, dst_dir = _session_dir(out_bp), _session_dir(bp.copy().update(session=entry.session))
    data_name = out_bp.fpath.name
    bids_stem = data_name[: -len(EXTENSIONS[fmt])].replace(src_prefix, dst_prefix, 1)
    plan: list[tuple[Path, str]] = []
    for p in produced:
        rel = p.relative_to(scratch).as_posix()
        name = p.name
        if PurePosixPath(rel).parent == PurePosixPath(".") or name in DISCARDED or name.endswith("_scans.tsv"):
            continue  # dataset- and session-level files: aimport writes its own
        if "_headshape" in name and not entry.keep_headshape:
            continue
        if not rel.startswith(src_dir + "/"):
            raise ValueError("MNE-BIDS wrote outside the recording's folder")
        out_rel = dst_dir + rel[len(src_dir):]
        out_rel = str(PurePosixPath(out_rel).parent / name.replace(src_prefix, dst_prefix, 1))
        plan.append((p, out_rel))
    if not any(p.name == data_name for p, _ in plan):
        raise ValueError("MNE-BIDS did not write the recording file")

    meta = meta or {}
    for p, out_rel in plan:
        ext = p.suffix.lower()
        if ext in (".edf", ".bdf"):
            headers.rewrite_edf(p, root=scratch, labels=labels)
        elif ext == ".vhdr":
            headers.rebuild_vhdr(p, bids_stem)
        elif ext == ".vmrk":
            headers.check_vmrk(p, labels, bids_stem)
        elif ext == ".tsv":
            redact_tsv(p, terms)
    empty: set[Path] = set()
    for p, out_rel in plan:
        if p.suffix.lower() != ".json":
            continue
        suffix = _suffix_of(p.name)
        overrides: dict[str, Any] = {}
        columns = None
        if suffix in TABULAR:
            tsv = p.with_suffix(".tsv")
            columns = tsv.read_text(encoding="utf-8").splitlines()[0].split("\t") if tsv.is_file() else []
        if suffix == datatype:
            overrides = _recording_overrides(entry, meta, er_rel)
        if not rebuild_sidecar(p, schema, datatype, suffix, terms, overrides, columns):
            empty.add(p)  # nothing the schema lists for raw data (an electrodes.json SpatialReference)
    plan = [(p, r) for p, r in plan if p not in empty]

    rels: list[str] = []
    for p, out_rel in sorted(plan, key=lambda x: (x[0].name != data_name, x[1])):
        target = dest(out_rel)
        if keep and p.name == data_name:
            shutil.copyfile(p, target)
        else:
            shutil.move(str(p), str(target))
        if out_rel not in rels:
            rels.append(out_rel)
    return rels


def _recording_overrides(entry: "PlanEntry", meta: dict, er_rel: str | None) -> dict[str, Any]:
    """Generated values of the recording sidecar: TaskName, the empty-room path in the output, the line
    frequency and reference from the (redacted) input BIDS sidecar, the EMG placement text."""
    out: dict[str, Any] = {"TaskName": (entry.entities or {}).get("task")}
    if entry.datatype == "meg":
        out["AssociatedEmptyRoom"] = er_rel  # None removes MNE-BIDS's scratch path
    if entry.datatype == "emg":
        out["EMGPlacementSchemeDescription"] = EMG_PLACEMENT_TEXT
    ref = meta.get("EEGReference")
    if isinstance(ref, str) and ref.strip():
        out[{"eeg": "EEGReference", "ieeg": "iEEGReference", "emg": "EMGReference"}.get(entry.datatype,
                                                                                         "EEGReference")] = ref
    return {k: v for k, v in out.items() if v is not None or k == "AssociatedEmptyRoom"}
