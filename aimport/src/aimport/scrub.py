"""De-identification: the only view of the data the LLM sees, and the sidecar scrub for output.

Nothing identifying may leave this module. ``ScrubbedSeries`` is built from an allowlist
(never from a blocklist), and every free-text value in it passes through ``redact``.
"""
from __future__ import annotations

import functools
import os
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pydicom

from .ezbids_runner import CoreResult, CoreSeries

MIN_TERM_LEN = 3
REDACTED = "[x]"

# Header fields whose values identify a person, a place or a device.
# Beyond the brief's list: StationName and DeviceSerialNumber (identify the scanner),
# PerformingPhysicianName and InstitutionAddress.
TERM_FIELDS = (
    "PatientName",
    "PatientID",
    "PatientBirthDate",
    "OtherPatientIDs",
    "InstitutionName",
    "InstitutionAddress",
    "OperatorsName",
    "ReferringPhysicianName",
    "PerformingPhysicianName",
    "StationName",
    "DeviceSerialNumber",
)
_DESCRIPTION_FIELDS = ("StudyDescription", "InstitutionalDepartmentName", "ProcedureStepDescription")
MAX_FILES_PER_DIR = 20
_NAME_FIELDS = {"PatientName", "OperatorsName", "ReferringPhysicianName", "PerformingPhysicianName"}

SCRUB_ALLOWLIST = {
    "Modality",
    "Manufacturer",
    "ManufacturersModelName",
    "MagneticFieldStrength",
    "ImageType",
    "ScanningSequence",
    "SequenceVariant",
    "SequenceName",
    "PulseSequenceName",
    "EchoTime",
    "RepetitionTime",
    "InversionTime",
    "FlipAngle",
    "PhaseEncodingDirection",
    "SliceThickness",
    "NumberOfVolumes",
    "Dimensions",
    "VoxelSize",
    "Units",
    "TracerName",
    "ImageComments_present",
}

# The brief's list plus PatientSize (height) and StudyDescription (free text, can name the study or PI).
SIDECAR_DROP = {
    "PatientName",
    "PatientID",
    "PatientBirthDate",
    "PatientSex",
    "PatientAge",
    "PatientWeight",
    "PatientSize",
    "InstitutionName",
    "InstitutionAddress",
    "InstitutionalDepartmentName",
    "StationName",
    "DeviceSerialNumber",
    "OperatorsName",
    "ReferringPhysicianName",
    "PerformingPhysicianName",
    "AccessionNumber",
    "StudyID",
    "StudyInstanceUID",
    "SeriesInstanceUID",
    "ImageComments",
    "ProcedureStepDescription",
    "StudyDescription",
    "AcquisitionDateTime",
    "AcquisitionDate",
    "ContentDate",
    "StudyDate",
    "SeriesDate",
}

_SC_SOP_CLASS = "1.2.840.10008.5.1.4.1.1.7"


def _values(raw: Any) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, (list, tuple, pydicom.multival.MultiValue)):
        return [s for item in raw for s in _values(item)]
    text = str(raw).strip()
    return [text] if text else []


def _date_forms(value: str) -> set[str]:
    m = re.fullmatch(r"(\d{4})[-/.]?(\d{2})[-/.]?(\d{2})", value)
    if not m:
        return set()
    y, mo, d = m.groups()
    return {
        f"{y}{mo}{d}", f"{y}-{mo}-{d}", f"{y}/{mo}/{d}", f"{y}.{mo}.{d}",
        f"{d}.{mo}.{y}", f"{d}/{mo}/{y}", f"{mo}/{d}/{y}", f"{d}-{mo}-{y}",
    }


def _terms_from(field_name: str, raw: Any) -> set[str]:
    """Terms for one header value, already length-filtered.

    Name parts of 2 characters are kept (Li, Wu, Ng; matched on boundaries only by redact);
    everything else needs MIN_TERM_LEN characters; 1-character parts are always dropped.
    """
    out: set[str] = set()
    min_len = MIN_TERM_LEN
    for value in _values(raw):
        out.add(value)
        if field_name in _NAME_FIELDS:
            min_len = 2
            out.update(p.strip(".,-=") for p in re.split(r"[\^\s_,=]+", value))  # whole components (O'Brien)
            out.update(p.strip(".,-=") for p in re.split(r"[\^\s_,.\-='\u2019]+", value))  # and their parts (O, Brien)
        elif field_name in {"PatientID", "OtherPatientIDs"}:
            out.update(re.split(r"[@\^ ]+", value))
        # description fields contribute the whole value only: parts ("MRI", "test") are generic words
        elif field_name == "PatientBirthDate":
            out |= _date_forms(value)
    return {t for t in out if len(t) >= min_len}


def _ds_terms(get) -> set[str]:
    terms: set[str] = set()
    for field_name in TERM_FIELDS + _DESCRIPTION_FIELDS:
        terms |= _terms_from(field_name, get(field_name))
    return terms


def _read_dicom(path: Path):
    """The dataset when path is a DICOM (with or without preamble), else None."""
    try:
        return pydicom.dcmread(str(path), stop_before_pixels=True)
    except pydicom.errors.InvalidDicomError:
        pass
    except Exception:
        return None
    try:  # raw / implicit-VR DICOM without the DICM preamble
        ds = pydicom.dcmread(str(path), stop_before_pixels=True, force=True)
    except Exception:
        return None
    return ds if ("PatientName" in ds or "SOPClassUID" in ds) else None


def _header_terms(input_dir: Path, stats: dict) -> set[str]:
    """Identifying values from DICOM headers under input_dir.

    In every directory files are read until one yields a term (DICOMDIR, presentation
    states and already-anonymized objects yield none), at most MAX_FILES_PER_DIR files;
    everything read is unioned.
    """
    terms: set[str] = set()
    for dirpath, _dirs, files in os.walk(input_dir):
        for name in sorted(files)[:MAX_FILES_PER_DIR]:
            ds = _read_dicom(Path(dirpath) / name)
            if ds is None:
                continue
            stats["dicom_files_read"] += 1
            terms |= _ds_terms(ds.get)
            if any(_terms_from(f, ds.get(f)) for f in TERM_FIELDS):  # descriptions alone do not end the search
                break
    return terms


def identifying_terms(core: CoreResult, input_dir: Path, stats: dict | None = None) -> set[str]:
    """Every identifying value in the ezBIDS output and in the input DICOM headers.

    Terms keep their original case (``redact`` ignores case and accents). When stats is
    given it is filled with {"dicom_files_read": int, "term_count": int}.
    """
    counts = {"dicom_files_read": 0}
    terms: set[str] = set()
    for subject in core.subjects:
        for info in subject.patient_info:
            terms |= _ds_terms(info.get)
    for sidecar in [s.sidecar for s in core.series] + [o.sidecar for o in core.objects]:
        terms |= _ds_terms(sidecar.get)
    terms |= _header_terms(Path(input_dir), counts)
    if stats is not None:
        stats["dicom_files_read"] = counts["dicom_files_read"]
        stats["term_count"] = len(terms)
    return terms


def _fold_char(ch: str) -> str:
    decomposed = unicodedata.normalize("NFKD", ch)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).casefold()


def _fold(text: str) -> str:
    return "".join(_fold_char(c) for c in text)


@functools.lru_cache(maxsize=32)
def _compiled(terms: frozenset) -> tuple[frozenset, re.Pattern | None]:
    """Folded terms and the one alternation pattern for them, built once per term set."""
    folded_terms = {_fold(t) for t in terms}
    folded_terms.discard("")
    if not folded_terms:
        return frozenset(), None
    parts = []
    for t in sorted(folded_terms, key=len, reverse=True):
        esc = re.escape(t)
        if len(t) < MIN_TERM_LEN and t.isascii() and t.isalnum():
            esc = rf"(?<![^\W_]){esc}(?![^\W_])"
        parts.append(esc)
    return frozenset(folded_terms), re.compile("|".join(parts))


def redact(text: str, terms: set[str]) -> str:
    """Replace each term with ``[x]``, longest first.

    Matching is case-, accent- and compatibility-insensitive (NFKD, combining marks removed,
    casefold: Strauss matches STRAUSS and Strauß, NFD matches NFC). The match is mapped back
    to the original text, so the rest of the output is not normalized. ASCII terms shorter
    than 3 characters match only as whole alphanumeric runs (Li but not "Lily").
    """
    _, pattern = _compiled(frozenset(terms))
    if pattern is None:
        return text
    folded, origin = [], []
    for i, ch in enumerate(text):
        f = _fold_char(ch)
        folded.append(f)
        origin.extend([i] * len(f))
    flat = "".join(folded)
    out, pos = [], 0
    for m in pattern.finditer(flat):
        if m.end() == m.start():
            continue
        start, end = origin[m.start()], origin[m.end() - 1] + 1
        while end < len(text) and _fold_char(text[end]) == "":  # trailing combining marks
            end += 1
        if start < pos:
            continue
        out.append(text[pos:start])
        out.append(REDACTED)
        pos = end
    out.append(text[pos:])
    return "".join(out)


def _redact_value(value: Any, terms: set[str]) -> Any:
    if isinstance(value, str):
        return redact(value, terms)
    if isinstance(value, dict):
        return {k: _redact_value(v, terms) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_redact_value(v, terms) for v in value]
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if _fold(str(value)) in _compiled(frozenset(terms))[0]:  # equal to a term, not merely containing it
            return REDACTED
    return value


_DROP_LOWER = {k.lower() for k in SIDECAR_DROP}


def _drop_keys(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _drop_keys(v) for k, v in value.items() if str(k).lower() not in _DROP_LOWER}
    if isinstance(value, (list, tuple)):
        return [_drop_keys(v) for v in value]
    return value


def scrub_sidecar(sidecar: dict, terms: set[str]) -> dict:
    """Drop SIDECAR_DROP keys (recursively, case-insensitively), redact string values and
    numbers equal to a term, recursively. Keys are kept as they are. Returns a new dict."""
    return _redact_value(_drop_keys(sidecar), terms)


@dataclass
class ScrubbedSeries:
    series_idx: int
    description: str
    protocol: str
    ezbids_type: str
    fields: dict[str, Any] = field(default_factory=dict)


def _nifti_fields(nifti_path: Path, root: Path | None) -> dict[str, Any]:
    """Shape facts from the NIfTI header only (never its description or extensions)."""
    path = Path(nifti_path)
    if not path.is_absolute() and root is not None:
        path = Path(root) / path
    if not path.is_file():
        return {}
    try:
        import nibabel as nib

        header = nib.load(str(path)).header
        shape = [int(n) for n in header.get_data_shape()]
        zooms = [float(z) for z in header.get_zooms()[:3]]
        unit = header.get_xyzt_units()[0]
    except Exception:
        return {}
    return {
        "NumberOfVolumes": shape[3] if len(shape) > 3 else 1,
        "Dimensions": shape,
        "VoxelSize": zooms,
        "Units": unit,
    }


def scrubbed_view(core: CoreResult, terms: set[str], root: Path | None = None) -> list[ScrubbedSeries]:
    """The LLM's only view of the series: allowlisted fields, every string redacted.

    root is the staged input directory that relative NIfTI paths resolve against; without
    it (or when the file is missing) the NIfTI-derived fields are left out.
    """
    view = []
    for s in core.series:
        sidecar = s.sidecar
        fields = {k: sidecar[k] for k in SCRUB_ALLOWLIST if k in sidecar and k != "ImageComments_present"}
        for k, v in _nifti_fields(s.nifti_path, root).items():
            fields.setdefault(k, v)
        fields["ImageComments_present"] = bool(sidecar.get("ImageComments"))
        view.append(
            ScrubbedSeries(
                series_idx=s.series_idx,
                description=redact(s.series_description, terms),
                protocol=redact(str(sidecar.get("ProtocolName", "")), terms),
                ezbids_type=s.type,
                fields=_redact_value(fields, terms),
            )
        )
    return view


def is_secondary_capture(series: CoreSeries) -> bool:
    """Secondary or derived screen captures: not source acquisitions.

    ImageType containing SECONDARY or DERIVED with Modality OT/SC, or a SOPClassUID in the
    Secondary Capture family (1.2.840.10008.5.1.4.1.1.7 and its .7.x multi-frame children;
    not the unrelated .77 visible-light classes).
    """
    sidecar = series.sidecar
    image_type = sidecar.get("ImageType") or []
    if isinstance(image_type, str):
        image_type = re.split(r"[\\/ ,]+", image_type)
    flags = {str(t).upper() for t in image_type}
    if flags & {"SECONDARY", "DERIVED"} and str(sidecar.get("Modality", "")).upper() in {"OT", "SC"}:
        return True
    sop = str(sidecar.get("SOPClassUID", ""))
    return sop == _SC_SOP_CLASS or sop.startswith(_SC_SOP_CLASS + ".")
