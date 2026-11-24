import json
from pathlib import Path

import pytest

from aimport import validate
from aimport.validate import ValidationError, parse_report, validate_bids

SAMPLE = (Path(__file__).parent / "fixtures" / "validator_sample.json").read_text()


def test_parse_report_splits_by_severity_and_keeps_fields():
    errors, warnings = parse_report(SAMPLE)
    assert [e["code"] for e in errors] == ["MISSING_DATASET_DESCRIPTION"]
    assert errors[0]["files"] == ["dataset_description.json"]
    assert "required" in errors[0]["message"]
    assert [w["code"] for w in warnings] == ["README_FILE_MISSING", "SIDECAR_KEY_RECOMMENDED"]
    assert warnings[1]["sub_code"] == "Manufacturer"
    assert warnings[1]["files"] == ["sub-01/anat/sub-01_T1w.nii.gz"]
    assert warnings[1]["severity"] == "warning"


def test_parse_report_rejects_non_json():
    with pytest.raises(ValidationError):
        parse_report("Deno crashed")
    with pytest.raises(ValidationError):
        parse_report(json.dumps({"nope": 1}))


def test_validate_bids_crash_is_error_not_ok(monkeypatch):
    class P:
        stdout, stderr, returncode = "", "boom", 1

    monkeypatch.setattr(validate, "_run", lambda cmd: P())
    with pytest.raises(ValidationError):
        validate_bids(Path("/nonexistent"))


def _dataset(root: Path, description: bool = True) -> Path:
    import nibabel as nib
    import numpy as np

    anat = root / "sub-01" / "anat"
    anat.mkdir(parents=True)
    nib.save(
        nib.Nifti1Image(np.zeros((4, 4, 4), dtype=np.int16), np.eye(4)),
        anat / "sub-01_T1w.nii.gz",
    )
    (anat / "sub-01_T1w.json").write_text("{}")
    (root / "participants.tsv").write_text("participant_id\nsub-01\n")
    if description:
        (root / "dataset_description.json").write_text(
            json.dumps({"Name": "t", "BIDSVersion": "1.11.2", "DatasetType": "raw"})
        )
    return root


@pytest.mark.docker
def test_valid_dataset_passes(tmp_path):
    r = validate_bids(_dataset(tmp_path / "ds"))
    assert r.ok is True, r.errors
    assert r.errors == []
    assert r.bids_version == "1.11.2"
    assert r.validator_version.startswith("2.")


@pytest.mark.docker
def test_missing_dataset_description_fails(tmp_path):
    r = validate_bids(_dataset(tmp_path / "ds", description=False))
    assert r.ok is False
    assert "MISSING_DATASET_DESCRIPTION" in {e["code"] for e in r.errors}
