import sys
from pathlib import Path

import pydicom
import pytest

sys.path.insert(0, str(Path(__file__).parent / "fixtures"))
from fetch_dcm_qa import NON_DICOM_SUFFIXES, fetch_dcm_qa  # noqa: E402


@pytest.mark.docker
def test_plant_round_trip(tmp_path):
    root = fetch_dcm_qa(tmp_path, plant=True)
    assert root == tmp_path / "Smith_John_19700101"
    n = 0
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() in NON_DICOM_SUFFIXES:
            continue
        ds = pydicom.dcmread(str(path))
        assert ds.PatientName == "Smith^John"
        assert ds.PatientID == "MRN0042"
        assert ds.PatientBirthDate == "19700101"
        assert ds.InstitutionName == "Hospital X"
        assert ds.SeriesDescription.startswith("Smith_John ")
        n += 1
    assert n > 0
