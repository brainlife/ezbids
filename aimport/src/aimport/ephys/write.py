"""The electrophysiology writers: MNE-BIDS for eeg, ieeg, emg and meg (Task 9), SNIRF and NWB (Task 10).

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
   caller); ``*_headshape.pos`` only moves with ``keep_headshape``. Split FIF parts renamed from MNE-BIDS's
   empty-room date session are saved again under the output names (``_resave_split``).

``write_nirs``: ``snirf.write`` (a new file, aimport's own) -> MNE-BIDS ``format="auto"``, ``anonymize=None``
(it copies that file) -> ``headers.check_snirf`` and the same steps 3 and 4. ``write_nwb``: ``nwb.write`` and
the sidecars from ``ieeg_sidecars``.
"""
from __future__ import annotations

import json
import os
import re
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
CLEAN_SNIRF = "clean.snirf"
RESPLIT = "resplit"
FIF_SPLIT_SIZE = "2GB"  # MNE's default split size
_SPLIT = re.compile(r"_split-\d+_")


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


def _bids_path(entry: "PlanEntry", datatype: str, root: Path):
    import mne_bids

    ents = entry.entities or {}
    return mne_bids.BIDSPath(subject=entry.subject, session=entry.session, task=ents.get("task"),
                             acquisition=ents.get("acquisition"), run=ents.get("run"),
                             datatype=datatype, root=root)


def _taken_lazily(raw) -> bool:
    """Whether MNE-BIDS takes this lazily opened recording without ``allow_preload``: its input file extension, as
    MNE-BIDS parses it, is one MNE-BIDS knows. GDF, Nihon Kohden and the like are not; neither is a file name
    with more dots than its extension (``x.v2_rest.edf`` parses as ``.v2_rest.edf``). Mirrors ``write_raw_bids``."""
    from mne_bids.config import ALLOWED_INPUT_EXTENSIONS
    from mne_bids.path import _parse_ext

    if not raw.filenames or raw.filenames[0] is None:
        return False
    fname = str(raw.filenames[0])
    if ".ds" in os.path.dirname(fname):
        fname = os.path.dirname(fname)
    fname = fname.replace(".eeg", ".vhdr").replace(".fdt", ".set").replace(".dat", ".lay")
    ext = _parse_ext(fname)[1]
    if ext in (".EDF", ".BDF"):
        ext = ext.lower()
    return ext in ALLOWED_INPUT_EXTENSIONS


def write_recording(entry: "PlanEntry", rec: dict, raw, scratch: Path, dest: Callable[[str], Path],
                    schema: "Schema", terms: set[str], er_path=None, *, days_back: int,
                    labels: set[str], er_rel: str | None = None, keep: bool = False,
                    meta: dict | None = None, written: list | None = None) -> list[str]:
    """Write one de-identified recording through MNE-BIDS; returns the output rel paths (data file first).

    ``er_path``: an empty-room BIDSPath in the same scratch root (passed to MNE-BIDS as ``empty_room``; the
    module passes none) and ``er_rel`` its output path, which ``AssociatedEmptyRoom`` is set to.
    ``labels``: the event labels the recording may carry (EDF TAL, ``.vmrk``). ``keep``: copy the data
    file instead of moving it. ``written``: when given, the scratch BIDSPath is appended to it.
    """
    import mne_bids

    datatype, fmt = entry.datatype, entry.ephys_format
    if datatype not in ("eeg", "ieeg", "emg", "meg") or fmt not in OUTPUT_FORMATS.get(datatype, ()) \
            or fmt not in EXTENSIONS:
        raise ValueError(f"{fmt or 'no format'} cannot be written for {datatype or 'an unknown datatype'}")
    scratch = Path(scratch)
    bp = _bids_path(entry, datatype, scratch)
    before = _files(scratch) if scratch.exists() else {}
    kw: dict[str, Any] = {}
    if datatype == "emg":
        kw["emg_placement"] = EMG_PLACEMENT
    if not raw.preload and not _taken_lazily(raw):
        raw.load_data(verbose="error")  # the plan's load limit (AIMPORT_EPHYS_MAX_LOAD_BYTES) already applies
    out_bp = mne_bids.write_raw_bids(
        raw, bp, anonymize={"daysback": int(days_back), "keep_his": False, "keep_source": False},
        format=fmt, empty_room=er_path, allow_preload=bool(raw.preload), overwrite=True, verbose=False, **kw)
    if written is not None:
        written.append(out_bp)
    return _finish(entry, out_bp, bp, scratch, before, dest, schema, terms, EXTENSIONS[fmt], labels=labels,
                   er_rel=er_rel, keep=keep, meta=meta)


def write_nirs(entry: "PlanEntry", raw, scratch: Path, dest: Callable[[str], Path], schema: "Schema",
               terms: set[str], *, labels: set[str], units: dict[str, str] | None = None,
               meta: dict | None = None) -> list[str]:
    """Write one de-identified fNIRS recording: ``snirf.write`` -> ``scratch/clean.snirf`` (aimport's own
    file) -> ``write_raw_bids(read_raw_snirf(clean), anonymize=None, format="auto")``, which copies it; then
    the SNIRF header check, the sidecar rebuild and the move. Optode names must pass the channel rule."""
    import mne
    import mne_bids

    from . import snirf

    if entry.datatype != "nirs" or entry.ephys_format != "SNIRF":
        raise ValueError(f"{entry.ephys_format or 'no format'} cannot be written for {entry.datatype or 'nirs'}")
    scratch = Path(scratch)
    scratch.mkdir(parents=True, exist_ok=True)
    clean = scratch / CLEAN_SNIRF
    try:
        snirf.write(raw, clean, entry.subject, {n: n for n in labels}, units)
        bp = _bids_path(entry, "nirs", scratch)
        before = _files(scratch)
        out_bp = mne_bids.write_raw_bids(mne.io.read_raw_snirf(clean, preload=False, verbose="error"), bp,
                                         anonymize=None, format="auto", overwrite=True, verbose=False)
        return _finish(entry, out_bp, bp, scratch, before, dest, schema, terms, ".snirf", labels=labels,
                       meta=meta)
    finally:
        clean.unlink(missing_ok=True)


def write_nwb(entry: "PlanEntry", src: Path, scratch: Path, dest: Callable[[str], Path], schema: "Schema",
              terms: set[str], *, labels: dict[str, str], renames: dict[str, str],
              meta: dict | None = None, group_types: dict[str, str] | None = None) -> list[str]:
    """Write one NWB iEEG recording as a new NWB file (``nwb.write``) with generated BIDS sidecars
    (``ieeg_sidecars``); returns the output rel paths (the ``.nwb`` first). ``labels``: normalised original
    interval text -> the label written."""
    from . import nwb

    if entry.datatype != "ieeg" or entry.ephys_format != "NWB":
        raise ValueError(f"{entry.ephys_format or 'no format'} cannot be written for {entry.datatype or 'ieeg'}")
    scratch = Path(scratch)
    bp = _bids_path(entry, "ieeg", scratch).update(suffix="ieeg", extension=".nwb")
    out_dir = scratch / _session_dir(bp) / "ieeg"
    out_dir.mkdir(parents=True, exist_ok=True)
    data = out_dir / bp.basename
    info = nwb.write(src, data, entry.subject, labels, renames, terms=terms, group_types=group_types)
    info["meta"] = meta or {}
    files: list[Path] = [data]
    for name, content in ieeg_sidecars(info, entry, schema, stem=bp.basename[: -len("_ieeg.nwb")],
                                       prefix=_session_prefix(bp)).items():
        path = out_dir / name
        if name.endswith(".json"):
            path.write_text(json.dumps(content, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        else:
            path.write_text("".join("\t".join(str(c) for c in row) + "\n" for row in content), encoding="utf-8")
        files.append(path)
    plan = [(p, p.relative_to(scratch).as_posix()) for p in files]
    for p, _ in plan:
        if p.suffix == ".tsv":
            redact_tsv(p, terms)
    for p, _ in plan:
        if p.suffix == ".json":
            suffix = _suffix_of(p.name)
            columns = None
            if suffix in TABULAR:
                tsv = p.with_suffix(".tsv")
                columns = tsv.read_text(encoding="utf-8").splitlines()[0].split("\t") if tsv.is_file() else []
            rebuild_sidecar(p, schema, "ieeg", suffix, terms, columns=columns)
    rels = []
    for p, rel in plan:
        shutil.move(str(p), str(dest(rel)))
        rels.append(rel)
    return rels


IEEG_TYPES = {"seeg": "SEEG", "ecog": "ECOG", "dbs": "DBS"}
NWB_UNITS = {"volts": "V", "v": "V", "millivolts": "mV", "microvolts": "uV"}
NWB_COORDS_TEXT = "electrode positions from the NWB electrodes table (micrometres, converted to millimetres)"


def ieeg_sidecars(info: dict, entry: "PlanEntry", schema: "Schema", *, stem: str, prefix: str) -> dict:
    """The BIDS sidecars of an NWB recording, generated from ``nwb.write``'s summary (no source text):
    ``<stem>_ieeg.json``, ``<stem>_channels.tsv``, ``<prefix>_electrodes.tsv`` and ``<prefix>_coordsystem.json``
    (when the table has positions), and ``<stem>_events.tsv`` (when there are intervals). TSVs come back as
    rows (header first)."""
    na = "n/a"
    channels = info["channels"]
    counts: dict[str, int] = {}
    for _, t in channels:
        counts[t] = counts.get(t, 0) + 1
    meta = info.get("meta") or {}
    line = meta.get("PowerLineFrequency")
    ref = meta.get("iEEGReference") or meta.get("EEGReference")
    sidecar: dict[str, Any] = {
        "TaskName": (entry.entities or {}).get("task"),
        "iEEGReference": ref if isinstance(ref, str) and ref.strip() else na,
        "SamplingFrequency": info["sfreq"],
        "PowerLineFrequency": line if isinstance(line, (int, float)) and not isinstance(line, bool) else na,
        "SoftwareFilters": na,
        "RecordingDuration": round(info["n_times"] / info["sfreq"], 6) if info["sfreq"] else na,
        "RecordingType": "continuous",
        "ECOGChannelCount": counts.get("ecog", 0),
        "SEEGChannelCount": counts.get("seeg", 0),  # BIDS 1.11.2 has no DBS count key
    }
    unit = NWB_UNITS.get(str(info.get("unit", "")).lower(), "V")
    out: dict[str, Any] = {
        f"{stem}_ieeg.json": sidecar,
        f"{stem}_channels.tsv": [("name", "type", "units", "low_cutoff", "high_cutoff", "status")] + [
            (name, IEEG_TYPES.get(t, "MISC"), unit, na, na, "good") for name, t in channels],
    }
    electrodes = info.get("electrodes") or []
    if electrodes:
        has_xyz = any(x is not None for _, x, _, _, _ in electrodes)

        def mm(v) -> str:
            return f"{v / 1000.0:.6g}" if v is not None and has_xyz else na

        out[f"{prefix}_electrodes.tsv"] = [("name", "x", "y", "z", "size", "group")] + [
            (name, mm(x), mm(y), mm(z), na, group) for name, x, y, z, group in electrodes]
        out[f"{prefix}_coordsystem.json"] = {
            "iEEGCoordinateSystem": "Other",
            "iEEGCoordinateSystemDescription": NWB_COORDS_TEXT,
            "iEEGCoordinateUnits": "mm" if has_xyz else na,
        }
    if info.get("events"):
        out[f"{stem}_events.tsv"] = [("onset", "duration", "trial_type")] + [
            (f"{o:.6g}", f"{d:.6g}", lab) for o, d, lab in info["events"]]
    return out


def _resave_split(parts: list[Path], out_name: str, scratch: Path) -> list[Path]:
    """Split FIF parts named for a scratch session: read and saved again under the output names (the part
    names are written inside each part, so a renamed part would not find the next one). Returns the new
    parts (named as the output, in a scratch subfolder), in order. ``out_name``: the first part's output name."""
    import mne
    import mne_bids.write as mbw

    tmp = scratch / RESPLIT
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    raw = mne.io.read_raw_fif(parts[0], preload=False, allow_maxshield=True, verbose="error")
    target = tmp / _SPLIT.sub("_", out_name)
    # the split size MNE-BIDS used (a private name: MNE's own default when it is gone)
    split_size = getattr(mbw, "_FIFF_SPLIT_SIZE", FIF_SPLIT_SIZE)
    raw.save(target, fmt=raw.orig_format, split_size=split_size, split_naming="bids", overwrite=True,
             verbose="error")
    del raw
    return sorted(tmp.iterdir())


def _finish(entry: "PlanEntry", out_bp, bp, scratch: Path, before: dict, dest: Callable[[str], Path],
            schema: "Schema", terms: set[str], ext: str, *, labels: set[str], er_rel: str | None = None,
            keep: bool = False, meta: dict | None = None) -> list[str]:
    """After MNE-BIDS: the header pass, the sidecar rebuild and the move of what it wrote to ``dest``."""
    datatype = entry.datatype
    after = _files(scratch)
    produced = sorted(p for p, st in after.items() if before.get(p) != st)

    # scratch name -> output name: the same entities, except the date session MNE-BIDS gives an empty room
    src_prefix, dst_prefix = _session_prefix(out_bp), _session_prefix(bp.copy().update(session=entry.session))
    src_dir, dst_dir = _session_dir(out_bp), _session_dir(bp.copy().update(session=entry.session))
    data_name = out_bp.fpath.name
    stem = data_name[: -len(ext)]
    split = re.compile(re.escape(stem.rsplit("_", 1)[0]) + r"_split-\d+_" + re.escape(stem.rsplit("_", 1)[-1] + ext)
                       + "$")
    bids_stem = stem.replace(src_prefix, dst_prefix, 1)
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
    data = [(p, r) for p, r in plan if p.name == data_name or split.fullmatch(p.name)]
    if not data:
        raise ValueError("MNE-BIDS did not write the recording file")
    if len(data) > 1 and src_prefix != dst_prefix:
        # split parts renamed from the scratch session: saved again under the output names
        data.sort()
        folder = PurePosixPath(data[0][1]).parent
        plan = [(p, r) for p, r in plan if (p, r) not in data]
        new = _resave_split([p for p, _ in data], PurePosixPath(data[0][1]).name, scratch)
        data = [(p, str(folder / p.name)) for p in new]
        plan = data + plan
    data_files = {p for p, _ in data}

    meta = meta or {}
    for p, out_rel in plan:
        suffix = p.suffix.lower()
        if suffix in (".edf", ".bdf"):
            headers.rewrite_edf(p, root=scratch, labels=labels)
        elif suffix == ".vhdr":
            headers.rebuild_vhdr(p, bids_stem)
        elif suffix == ".vmrk":
            headers.check_vmrk(p, labels, bids_stem)
        elif suffix == ".snirf":
            headers.check_snirf(p, entry.subject, labels)
        elif suffix == ".tsv":
            redact_tsv(p, terms)
            if p.name.endswith("_optodes.tsv"):
                _check_optodes(p, terms)
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
    for p, out_rel in sorted(plan, key=lambda x: (x[0] not in data_files, x[1])):
        target = dest(out_rel)
        if keep and p in data_files:
            shutil.copyfile(p, target)
        else:
            shutil.move(str(p), str(target))
        if out_rel not in rels:
            rels.append(out_rel)
    shutil.rmtree(Path(scratch) / RESPLIT, ignore_errors=True)
    return rels


def _check_optodes(path: Path, terms: set[str]) -> None:
    """Optode names pass the channel rule (aimport writes ``S<n>``/``D<n>``; anything else is refused)."""
    from .channels import is_kept

    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines:
        return
    header = lines[0].split("\t")
    if "name" not in header:
        return
    k = header.index("name")
    for line in lines[1:]:
        cells = line.split("\t")
        if k < len(cells) and not is_kept(cells[k], terms):
            raise headers.HeaderError("optode name")


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
