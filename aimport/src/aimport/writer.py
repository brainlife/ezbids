"""The BIDS writer: turns an approved Plan into the output folder that gets uploaded.

Privacy and safety rules:
- Nothing is written outside out_dir, which must not exist or be empty; nothing is read from
  outside staged_dir (the staged tree symlinks into the read-only input, so the input folder is
  the one other place a source may resolve to).
- Every JSON, TSV and the README is redacted with the run's terms; NIfTI header text fields are
  cleared; dates are shifted by the subject's offset; the pseudonym key is never touched here.
- The top-level files (dataset_description, README, participants, scans) are generated here and
  written by ancillary.write_ancillary, merged with the supplied ancillary files the plan keeps.
  The caller owns the key's lock and must call key.save() afterwards, because date offsets are
  created on first use and the writer must not write key files.
"""
from __future__ import annotations

import gzip
import json
import os
import re
import shutil
from datetime import date, datetime, timedelta
from pathlib import Path

import nibabel as nib
import numpy as np

from .ancillary import Generated, id_maps, path_terms, write_ancillary
from .ezbids_runner import CoreObject, CoreResult
from .plan import Plan, PlanEntry
from .planner import is_placeholder
from .pseudonyms import PseudonymKey
from .schema import BIDS_VERSION, Schema
from .scrub import MAX_FILES_PER_DIR, _read_dicom, redact, scrub_sidecar

NA = "n/a"
NIFTI_EXTS = (".nii.gz", ".nii")
SIDE_EXTS = (".bval", ".bvec")
NIFTI_TEXT_FIELDS = ("descrip", "aux_file", "intent_name", "db_name")
INTENDED_DATATYPES = {"func", "dwi"}
PLACEHOLDER_DATES = {"", "n/a", "na", "anon", "anonymous", "unknown", "none", "0", "00000000"}
AGE_CAP = 89
_AGE = re.compile(r"^(\d{1,3})([DWMY])$")
_DAYS_PER_YEAR = 365.25
_UNIT_YEARS = {"D": 1 / _DAYS_PER_YEAR, "W": 7 / _DAYS_PER_YEAR, "M": 1 / 12, "Y": 1.0}


def _inside(path: Path, root: Path) -> bool:
    return root == path or root in path.parents


def _normal(path: Path) -> Path:
    return Path(os.path.normpath(path))


def _parse_age(raw) -> str:
    """DICOM PatientAge ("045Y", "018M", "006W", "100D") -> years; 89 or more -> 89 (BIDS maximum); else "n/a"."""
    m = _AGE.match(str(raw or "").strip().upper())
    if not m:
        return NA
    n, unit = int(m.group(1)), m.group(2)
    years = n * _UNIT_YEARS[unit]
    if years >= AGE_CAP:
        return str(AGE_CAP)
    return str(n) if unit == "Y" else f"{years:.1f}"


def _parse_sex(raw) -> str:
    value = str(raw or "").strip().upper()
    return value if value in {"M", "F", "O"} else NA


def _parse_date(value) -> date | None:
    text = str(value or "").strip()
    if "T" in text:
        text = text.split("T")[0]
    if text.lower() in PLACEHOLDER_DATES or text.startswith("0000"):
        return None
    try:
        return date.fromisoformat(text) if "-" in text else datetime.strptime(text, "%Y%m%d").date()
    except ValueError:
        return None


def _parse_time(value) -> tuple[int, int, int] | None:
    m = re.match(r"^(\d{2}):?(\d{2}):?(\d{2})", str(value or "").strip())
    if not m:
        return None
    h, mi, s = (int(g) for g in m.groups())
    return (h, mi, s) if h < 24 and mi < 60 and s < 60 else None


def _acq_time(obj: CoreObject, offset_days: int) -> str:
    day, clock = _parse_date(obj.acquisition_date), _parse_time(obj.acquisition_time)
    if day is None or clock is None:
        return NA
    try:
        shifted = datetime(day.year, day.month, day.day, *clock) + timedelta(days=offset_days)
    except OverflowError:
        return NA
    return shifted.strftime("%Y-%m-%dT%H:%M:%S")


def write_clean_nifti(src: Path, dest: Path, zero_mask: np.ndarray | None = None) -> None:
    """A byte-exact copy of the stored data with a header cleared of text and extensions.

    descrip, aux_file, intent_name and db_name are emptied and header extensions dropped; the
    raw (unscaled) voxel bytes, scl_slope/scl_inter, affine and datatype are kept, so no
    value is re-quantised. NIfTI-2 is rejected: dcm2niix writes NIfTI-1 only. Voxels where
    zero_mask is True are set to the stored value that reads back as zero (raw 0 without an intercept).
    """
    img = nib.load(str(src))
    if not isinstance(img, nib.Nifti1Image) or isinstance(img, nib.Nifti2Image):
        raise ValueError(f"only NIfTI-1 images can be written, not {type(img).__name__}: {src.name}")
    hdr = img.header.copy()
    for name in NIFTI_TEXT_FIELDS:
        hdr[name] = b""
    hdr["scl_slope"], hdr["scl_inter"] = img.dataobj.slope, img.dataobj.inter
    hdr.set_data_offset(352)
    raw = np.asanyarray(img.dataobj.get_unscaled())
    if zero_mask is not None:
        if zero_mask.shape != raw.shape:
            raise ValueError("zero_mask does not match the image shape")
        slope, inter = img.dataobj.slope, img.dataobj.inter
        fill = 0 if not inter else (-inter / slope if np.issubdtype(raw.dtype, np.floating) else round(-inter / slope))
        if np.issubdtype(raw.dtype, np.integer) and not np.iinfo(raw.dtype).min <= fill <= np.iinfo(raw.dtype).max:
            raise ValueError(f"no {raw.dtype} value reads back as zero with intercept {inter} and slope {slope}")
        raw = np.where(zero_mask, np.asarray(fill, dtype=raw.dtype), raw)
    opener = gzip.open if dest.name.endswith(".gz") else open
    with opener(dest, "wb") as f:
        f.write(hdr.binaryblock + b"\0" * 4 + raw.tobytes(order="F"))


class _Item:
    """One object to write: its source files and its BIDS name."""

    def __init__(self, entry: PlanEntry, obj: CoreObject, nifti: Path, sources: dict[str, Path]):
        self.entry, self.obj, self.nifti, self.sources = entry, obj, nifti, sources
        self.entities = dict(entry.entities)
        self.suffix = entry.suffix  # magnitude1/2 may be reassigned by echo
        self.rel = ""  # path relative to out_dir, NIfTI extension included

    @property
    def ext(self) -> str:
        return next(e for e in NIFTI_EXTS if self.nifti.name.endswith(e))

    @property
    def stem(self) -> str:
        return self.rel[: -len(self.ext)]


class _Writer:
    def __init__(self, plan: Plan, core: CoreResult, input_dir: Path, terms: set[str], key: PseudonymKey,
                 schema: Schema, out_dir: Path, staged_dir: Path,
                 manifest: dict[str, list[str]] | None = None, refused: list[str] | None = None):
        self.refused = refused
        self.plan, self.core, self.terms, self.key, self.schema = plan, core, terms, key, schema
        self.input_dir = Path(input_dir).resolve()
        self.staged_dir = Path(staged_dir)
        self.out_dir = Path(out_dir).resolve()
        self.written: list[Path] = []
        self.manifest = manifest
        self.generated = Generated()  # top-level files, written by write_ancillary
        # short numbers ("01") would match the generated sub-/ses-/run- labels
        self.path_terms = path_terms(terms)

    # --- guarded paths ---------------------------------------------------------

    def source(self, rel: Path) -> Path:
        """A file under the staged tree; a symlink may lead into the input folder, nowhere else."""
        staged = self.staged_dir.resolve()
        path = _normal(staged / rel)
        if rel.is_absolute() or not _inside(path, staged):
            raise ValueError(f"source path outside the staged folder: {rel}")
        if not _inside(path.resolve(), staged) and not _inside(path.resolve(), self.input_dir):
            raise ValueError(f"source path outside the staged and input folders: {rel}")
        if not path.is_file():
            raise FileNotFoundError(path)
        return path

    def check_rel(self, rel: str) -> Path:
        path = _normal(self.out_dir / rel)
        if not _inside(path, self.out_dir) or path == self.out_dir:
            raise ValueError(f"destination outside the output folder: {rel}")
        if redact(rel, self.path_terms) != rel:
            raise ValueError(f"destination name contains an identifying value: {rel}")
        return path

    def dest(self, rel: str) -> Path:
        path = self.check_rel(rel)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.written.append(path)
        return path

    # --- items -----------------------------------------------------------------

    def items(self) -> list[_Item]:
        by_key: dict[tuple[int, int, int], list[CoreObject]] = {}
        for o in self.core.objects:
            by_key.setdefault((o.series_idx, o.subject_idx, o.session_idx), []).append(o)
        items = []
        for e in self.plan.entries:
            if e.exclude or e.status != "ok" or not e.datatype or not e.suffix:
                continue
            objs = sorted(by_key.get((e.series_idx, e.subject_idx, e.session_idx), []),
                          key=lambda o: (o.acquisition_date, o.acquisition_time))
            suffixes = self.echo_suffixes(e, objs)
            for o in objs:
                nifti = next((p for p in o.paths if p.name.endswith(NIFTI_EXTS)), None)
                if nifti is None:
                    continue
                sources = {s: p for p in o.paths for s in SIDE_EXTS if p.name.endswith(s)}
                item = _Item(e, o, nifti, sources)
                item.suffix = suffixes.get(id(o), e.suffix)
                items.append(item)
        self.name_items(items)
        return items

    @staticmethod
    def echo_suffixes(e: PlanEntry, objs: list[CoreObject]) -> dict[int, str]:
        """id(object) -> magnitude1/magnitude2 when one fmap series holds two distinct echoes."""
        if e.datatype != "fmap" or e.suffix not in {"magnitude1", "magnitude2"}:
            return {}
        for field in ("EchoNumber", "EchoTime"):
            values = {o.sidecar.get(field) for o in objs}
            if None not in values and len(values) >= 2:
                break
        else:
            return {}
        try:
            order = sorted(values, key=float)
        except (TypeError, ValueError):
            return {}
        return {id(o): f"magnitude{order.index(o.sidecar[field]) + 1}" for o in objs
                if order.index(o.sidecar[field]) < 2}

    def name_items(self, items: list[_Item]) -> None:
        def name(it: _Item) -> str:
            e = it.entry
            rel = self.schema.filename(e.subject, e.session, e.datatype, it.suffix, it.entities, it.ext)
            self.check_rel(rel)
            return rel

        names = [name(it) for it in items]
        counts = {n: names.count(n) for n in names}
        taken = {n for n in names if counts[n] == 1}
        for it, n in zip(items, names):
            if counts[n] > 1:
                for run in range(1, len(items) + 2):
                    it.entities["run"] = str(run)
                    n = name(it)
                    if n not in taken:
                        break
                else:
                    raise ValueError(f"cannot give {n} a unique name")
                taken.add(n)
            it.rel = n

    # --- writing ---------------------------------------------------------------

    def write_text(self, rel: str, text: str) -> None:
        self.dest(rel).write_text(text, encoding="utf-8")

    def write_json(self, rel: str, data: dict) -> None:
        self.write_text(rel, json.dumps(scrub_sidecar(data, self.terms), indent=2, ensure_ascii=False) + "\n")

    def write_nifti(self, src: Path, dest: Path) -> None:
        write_clean_nifti(src, dest)

    def run(self) -> list[Path]:
        items = self.items()
        by_session: dict[tuple[str, str | None], list[_Item]] = {}
        for it in items:
            by_session.setdefault((it.entry.subject, it.entry.session), []).append(it)
        for it in items:
            self.write_item(it, by_session[(it.entry.subject, it.entry.session)])
        self.generated.jsons["dataset_description.json"] = {
            "Name": self.plan.dataset_name, "BIDSVersion": BIDS_VERSION, "DatasetType": "raw",
            "GeneratedBy": [{"Name": "brainlife.io/aimport"}]}
        if self.plan.readme:
            self.generated.texts["README.md"] = self.plan.readme
        self.write_participants(items)
        self.write_scans(by_session)
        # only the subjects, sessions and images written here: rows and files of anyone else are dropped,
        # and companions (events, physio, scans rows) follow the image they belong to
        images = {os.path.normpath(str(it.nifti)): it.rel for it in items}
        ids = id_maps(self.core, [it.entry for it in items], written=images)
        self.written += write_ancillary(self.plan, self.input_dir, self.out_dir, self.terms, ids, self.key,
                                        schema=self.schema, generated=self.generated, refused=self.refused)
        stray = list(self.out_dir.rglob("*aimport-key*"))
        if stray:
            raise RuntimeError(f"pseudonym key found in the output folder: {stray}")
        return self.written

    def write_item(self, it: _Item, siblings: list[_Item]) -> None:
        self.write_nifti(self.source(it.nifti), self.dest(it.rel))
        if self.manifest is not None:
            self.manifest.setdefault(it.entry.id, []).append(it.rel)
        for ext, rel in it.sources.items():
            shutil.copyfile(self.source(rel), self.dest(it.stem + ext))
        sidecar = {k: v for k, v in it.obj.sidecar.items() if v is not None and k != "IntendedFor"}
        task = it.entry.entities.get("task")
        if task and "TaskName" not in sidecar:
            sidecar["TaskName"] = task  # BIDS requires it for task images (the label is a valid TaskName)
        if it.entry.datatype == "fmap":
            targets = sorted("bids::" + s.rel for s in siblings if s.entry.datatype in INTENDED_DATATYPES)
            if targets:
                sidecar["IntendedFor"] = targets
        self.write_json(it.stem + ".json", sidecar)

    def write_scans(self, by_session: dict[tuple[str, str | None], list[_Item]]) -> None:
        for (subject, session), items in by_session.items():
            offset = self.key.date_offset_days(subject)
            base = f"sub-{subject}" + (f"/ses-{session}" if session else "")
            rows = sorted((it.rel[len(base) + 1:], _acq_time(it.obj, offset)) for it in items)
            rel = f"{base}/sub-{subject}{f'_ses-{session}' if session else ''}_scans.tsv"
            self.generated.tables[rel] = [["filename", "acq_time"]] + [list(r) for r in rows]

    # --- participants ----------------------------------------------------------

    def write_participants(self, items: list[_Item]) -> None:
        subjects: dict[str, list[_Item]] = {}
        for it in items:
            subjects.setdefault(it.entry.subject, []).append(it)
        rows = [["participant_id", "age", "sex"]]
        for subject in sorted(subjects):
            age, sex = self.demographics(subjects[subject])
            rows.append([f"sub-{subject}", age, sex])
        self.generated.tables["participants.tsv"] = rows
        self.generated.jsons["participants.json"] = {
            "age": {"Description": "age at first scan of this import", "Units": "year"},
            "sex": {"Description": "sex from the DICOM header", "Levels": {"M": "male", "F": "female", "O": "other"}},
        }

    def demographics(self, items: list[_Item]) -> tuple[str, str]:
        """PatientAge/PatientSex from the DICOMs behind this subject's series, else by PatientID."""
        age = sex = NA
        for ds in self.subject_dicoms(items):
            age = age if age != NA else _parse_age(ds.get("PatientAge"))
            sex = sex if sex != NA else _parse_sex(ds.get("PatientSex"))
            if age != NA and sex != NA:
                break
        return age, sex

    def subject_dicoms(self, items: list[_Item]):
        dirs = []
        for it in items:
            for rel in (it.nifti, *it.obj.paths):
                d = _normal(self.input_dir / rel).parent
                if _inside(d, self.input_dir) and d not in dirs and d.is_dir():
                    dirs.append(d)
        for d in dirs:
            yield from self.read_dir(d)
        ids = {str(i.get("PatientID", "")).strip() for sidx in {it.obj.subject_idx for it in items}
               for s in self.core.subjects if s.subject_idx == sidx for i in s.patient_info
               if not is_placeholder("PatientID", i.get("PatientID"))}
        if ids:
            for dirpath, _dirs, _files in os.walk(self.input_dir):
                for ds in self.read_dir(Path(dirpath)):
                    if str(ds.get("PatientID", "")).strip() in ids:
                        yield ds
                        break

    @staticmethod
    def read_dir(directory: Path):
        for name in sorted(os.listdir(directory))[:MAX_FILES_PER_DIR]:
            if (directory / name).is_file():
                ds = _read_dicom(directory / name)
                if ds is not None:
                    yield ds


def write_bids(plan: Plan, core: CoreResult, input_dir: Path, terms: set[str], key: PseudonymKey,
               schema: Schema, out_dir: Path, *, staged_dir: Path,
               manifest: dict[str, list[str]] | None = None, refused: list[str] | None = None) -> list[Path]:
    """Write the approved plan as a BIDS dataset in out_dir; returns every file written.

    When manifest is given it is filled with entry id -> the NIfTI paths written for that entry
    (posix, relative to out_dir), so later steps (defacing) find exactly those files. When refused is
    given, ancillary files the plan kept but the writer would not write are appended with the reason.
    Raises PermissionError unless plan.approved, FileExistsError when out_dir is not empty, ValueError
    for a written anat entry with deface=False whose reviewer did not opt out (deface_opt_out).
    A failed write removes what it created.
    """
    if not plan.approved:
        raise PermissionError("the plan has not been approved")
    for e in plan.entries:  # defence in depth: an anat image is written with its face only on request
        if e.datatype == "anat" and e.status == "ok" and not e.exclude and not e.deface and not e.deface_opt_out:
            raise ValueError(f"{e.id}: anatomical image without defacing and the reviewer did not opt out")
    out = Path(out_dir)
    if out.exists() and (not out.is_dir() or any(out.iterdir())):
        raise FileExistsError(f"output folder exists and is not empty: {out}")
    existed = out.exists()
    out.mkdir(parents=True, exist_ok=True)
    try:
        return _Writer(plan, core, input_dir, terms, key, schema, out, staged_dir, manifest, refused).run()
    except BaseException:
        if manifest is not None:
            manifest.clear()
        if existed:
            for child in out.iterdir():
                shutil.rmtree(child) if child.is_dir() and not child.is_symlink() else child.unlink()
        else:
            shutil.rmtree(out, ignore_errors=True)
        raise
