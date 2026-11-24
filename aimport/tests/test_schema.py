import pytest

from aimport.schema import PHASE1_DATATYPES


def test_valid_pairs(schema):
    assert schema.is_valid("anat", "T1w")
    assert schema.is_valid("pet", "pet")
    assert not schema.is_valid("anat", "bold")


def test_filename_orders_entities(schema):
    assert schema.filename("01", "1", "func", "bold", {"run": "2", "task": "rest"}, ".nii.gz") \
        == "sub-01/ses-1/func/sub-01_ses-1_task-rest_run-2_bold.nii.gz"


def test_filename_rejects_bad_label(schema):
    with pytest.raises(ValueError):
        schema.filename("Smith_John", None, "anat", "T1w", {}, ".nii.gz")


def test_filename_no_session_and_acq(schema):
    assert schema.filename("01", None, "anat", "T1w", {"acquisition": "mprage"}, ".nii.gz") \
        == "sub-01/anat/sub-01_acq-mprage_T1w.nii.gz"


def test_filename_rejects_disallowed_entity_and_bad_index(schema):
    with pytest.raises(ValueError):
        schema.filename("01", None, "anat", "T1w", {"task": "x", "bogus": "1"}, ".nii.gz")
    with pytest.raises(ValueError):
        schema.filename("01", None, "func", "bold", {"task": "rest", "run": "a"}, ".nii.gz")


def test_allowed_entities_schema_order(schema):
    ents = schema.allowed_entities("func", "bold")
    assert ents.index("task") < ents.index("acquisition") < ents.index("run")
    assert "subject" not in ents


def test_phase1_datatypes_have_pairs(schema):
    assert PHASE1_DATATYPES == ("anat", "func", "dwi", "fmap", "perf", "pet")


def test_required_entities(schema):
    assert schema.required_entities("func", "bold") == ["task"]
    assert schema.required_entities("anat", "T1w") == []


def test_filename_requires_task_for_bold(schema):
    with pytest.raises(ValueError, match="task"):
        schema.filename("01", None, "func", "bold", {}, ".nii.gz")
    assert schema.filename("01", None, "func", "bold", {"task": "rest"}, ".nii.gz") \
        == "sub-01/func/sub-01_task-rest_bold.nii.gz"


def test_filename_rejects_bad_extension(schema):
    with pytest.raises(ValueError, match="extension"):
        schema.filename("01", None, "anat", "T1w", {}, ".txt")


def test_filename_checks_entities_per_group():
    # No suffix shares two groups in the phase-1 datatypes of the real schema, so use a
    # synthetic schema: "x" is allowed only by group a, "y" is required only by group b.
    from bidsschematools.types import Namespace

    from aimport.schema import Schema
    fake = Namespace({
        "rules": {"entities": ["subject", "session", "x", "y"], "files": {"raw": {"g": {
            "a": {"suffixes": ["s"], "datatypes": ["anat"], "extensions": [".nii"],
                  "entities": {"subject": "required", "x": "optional"}},
            "b": {"suffixes": ["s"], "datatypes": ["anat"], "extensions": [".nii"],
                  "entities": {"subject": "required", "y": "required"}},
        }}}},
        "objects": {"entities": {"subject": {"name": "sub", "format": "label"},
                                 "x": {"name": "x", "format": "label"},
                                 "y": {"name": "y", "format": "label"}}},
    })
    s = Schema(fake)
    assert s.required_entities("anat", "s") == []
    assert s.allowed_entities("anat", "s") == ["x", "y"]
    assert s.filename("01", None, "anat", "s", {"x": "1"}, ".nii").endswith("x-1_s.nii")
    assert s.filename("01", None, "anat", "s", {"y": "1"}, ".nii").endswith("y-1_s.nii")
    with pytest.raises(ValueError):
        s.filename("01", None, "anat", "s", {"x": "1", "y": "1"}, ".nii")
