"""Fetch the public neurolabusc/dcm_qa_xa30 DICOM set and optionally plant fake PHI.

Runs on the host and inside the engine image. Needs only the standard library
and pydicom. The downloaded tarball is cached so repeated calls are cheap.
"""
from __future__ import annotations

import shutil
import tarfile
import tempfile
import urllib.request
from pathlib import Path

import pydicom

# Pinned commit of https://github.com/neurolabusc/dcm_qa_xa30 (Siemens XA30: T1w, BOLD, fieldmaps, DWI, ASL)
DCM_QA_REPO = "dcm_qa_xa30"
DCM_QA_COMMIT = "371ab3071aa9270d23b99fca5f83fe0c35932182"
DCM_QA_URL = f"https://github.com/neurolabusc/{DCM_QA_REPO}/archive/{DCM_QA_COMMIT}.tar.gz"

PLANTED = {
    "PatientName": "Smith^John",
    "PatientID": "MRN0042",
    "PatientBirthDate": "19700101",
    "InstitutionName": "Hospital X",
}
# Identifiers dcm_qa_xa30 carries itself (upstream-public, still never allowed in committed
# fixtures or in any engine output). Matched case-insensitively as substrings.
NATIVE_IDENTIFIERS = {
    "12343@hucheng",
    "hucheng",
    "XAtest_sub-July11",
    "19910101",
    "1991-01-01",
    "Indiana University",
    "MRC35062",  # StationName
    "67093",  # DeviceSerialNumber
    "Cheng",  # StudyDescription / ProcedureStepDescription
}
SUBJECT_DIR = "Smith_John_19700101"
SERIES_PREFIX = "Smith_John "


# dcm_qa ships notes and documents next to the series; everything else must be DICOM
NON_DICOM_SUFFIXES = {".txt", ".pdf", ".xlsx", ".nii"}


def _read_dicom(path: Path):
    """Return the dataset when path is a DICOM file (extension or not).

    Known non-DICOM files (notes, PDFs, spreadsheets) give None; any other file
    that pydicom rejects raises, so a changed dataset cannot silently skip planting.
    """
    if path.suffix.lower() in NON_DICOM_SUFFIXES:
        return None
    return pydicom.dcmread(str(path))


def _download(cache: Path) -> Path:
    cache.mkdir(parents=True, exist_ok=True)
    tarball = cache / f"{DCM_QA_REPO}-{DCM_QA_COMMIT}.tar.gz"
    if not tarball.exists():
        tmp = tarball.with_suffix(".part")
        with urllib.request.urlopen(DCM_QA_URL, timeout=120) as r, open(tmp, "wb") as f:
            shutil.copyfileobj(r, f)
        tmp.replace(tarball)
    return tarball


def fetch_dcm_qa(dest: Path, plant: bool = True, cache: Path | None = None) -> Path:
    """Download dcm_qa_xa30 at the pinned commit into dest and return the root.

    The DICOM series live under dcm_qa's In/ directory (In/<group>/<series>/files).
    With plant=True every DICOM gets fake PHI (PatientName Smith^John, PatientID
    MRN0042, PatientBirthDate 19700101, InstitutionName Hospital X, SeriesDescription
    prefixed with "Smith_John ") and the series move under dest/Smith_John_19700101/.
    With plant=False the series are left as downloaded under dest/dcm_qa/.
    """
    dest = Path(dest)
    cache = Path(cache) if cache else Path(tempfile.gettempdir()) / "aimport-dcm-qa-cache"
    tarball = _download(cache)
    root = dest / (SUBJECT_DIR if plant else "dcm_qa")
    root.mkdir(parents=True, exist_ok=True)
    prefix = f"{DCM_QA_REPO}-{DCM_QA_COMMIT}/In/"
    with tarfile.open(tarball) as tf:
        for member in tf:
            if not member.isfile() or not member.name.startswith(prefix):
                continue
            rel = Path(member.name[len(prefix):])
            if ".." in rel.parts:
                continue
            target = root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            with tf.extractfile(member) as src, open(target, "wb") as out:
                shutil.copyfileobj(src, out)
    if plant:
        planted = 0
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            ds = _read_dicom(path)
            if ds is None:
                continue
            for key, value in PLANTED.items():
                setattr(ds, key, value)
            ds.SeriesDescription = SERIES_PREFIX + str(getattr(ds, "SeriesDescription", ""))
            ds.save_as(str(path))
            planted += 1
        if planted == 0:
            raise RuntimeError(f"no DICOM files found to plant under {root}")
    return root


if __name__ == "__main__":
    import sys

    # fetch_dcm_qa.py DEST [--plain]: --plain leaves the set as downloaded (DEST/dcm_qa), nothing planted
    args = [a for a in sys.argv[1:] if a != "--plain"]
    print(fetch_dcm_qa(Path(args[0]), plant="--plain" not in sys.argv[1:]))
