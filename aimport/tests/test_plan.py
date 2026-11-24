import copy
import json

import pytest

from aimport.plan import Plan, PlanEntry


def entry(**kw):
    base = dict(
        id="e1", series_idx=0, subject_idx=0, session_idx=0,
        subject="01", session=None, datatype=None, suffix=None,
        entities={}, brainlife_datatype=None, brainlife_tags=[],
        source="heuristic", confidence=1.0, reason="", deface=False,
        exclude=False, status="ok", description="",
    )
    base.update(kw)
    return PlanEntry(**base)


def test_roundtrip(tmp_path):
    p = Plan(target="bids", entries=[entry(id="e1", datatype="anat", suffix="T1w")])
    p.save(tmp_path / "plan.json")
    assert Plan.load(tmp_path / "plan.json") == p


def test_roundtrip_keeps_warnings(tmp_path):
    p = Plan(target="bids", entries=[entry()], warnings=["de-identification could not be verified"])
    p.save(tmp_path / "plan.json")
    assert Plan.load(tmp_path / "plan.json").warnings == ["de-identification could not be verified"]
    assert Plan(target="bids", entries=[]).warnings == []


def test_edit_marks_person_and_unapproves():
    p = Plan(target="bids", entries=[entry(id="e1", suffix="T1w")], approved=True)
    p.apply_edits([{"id": "e1", "suffix": "T2w"}])
    assert p.entries[0].suffix == "T2w"
    assert p.entries[0].source == "person"
    assert p.approved is False


def test_edit_unknown_id_raises():
    with pytest.raises(KeyError):
        Plan(target="bids", entries=[]).apply_edits([{"id": "nope"}])


def test_edit_cannot_change_series_idx():
    p = Plan(target="bids", entries=[entry(id="e1", series_idx=3)])
    with pytest.raises(ValueError):
        p.apply_edits([{"id": "e1", "series_idx": 4}])


# --- ancillary files (Task 10b) -------------------------------------------------

from aimport.plan import AncillaryEntry  # noqa: E402


def ancillary_entry(**kw):
    base = dict(id="a0", path="participants.tsv", source="participants.tsv", kind="table", action="keep",
                columns={"participant_id": "keep", "name": "drop", "[x]": "drop", "visit": "shift_date"},
                content=None, flags=[], reason="", locked=False,
                locked_columns={"participant_id": ["keep"], "[x]": ["drop"], "visit": ["shift_date", "drop"]})
    base.update(kw)
    return AncillaryEntry(**base)


def ancillary_plan():
    return Plan(target="bids", entries=[entry()], approved=True, ancillary=[
        ancillary_entry(),
        ancillary_entry(id="a1", path="participants.json", source="participants.json", kind="table_json", columns={}),
        ancillary_entry(id="a2", path="README", source="README", kind="core", columns={}),
        ancillary_entry(id="a3", path="sourcedata", source="sourcedata", kind="folder", action="drop", columns={},
                        locked=True),
        ancillary_entry(id="a4", path="code", source="code", kind="folder", action="drop", columns={}),
        ancillary_entry(id="a5", path="derivatives", source="derivatives", kind="folder", action="drop", columns={},
                        locked=True),
    ], dataset_description={"Authors": ["A. Researcher"], "License": "CC0"})


def test_roundtrip_keeps_ancillary(tmp_path):
    p = ancillary_plan()
    p.ancillary[1].content = {"age": {"Description": "years"}}
    p.save(tmp_path / "plan.json")
    q = Plan.load(tmp_path / "plan.json")
    assert q == p and isinstance(q.ancillary[0], AncillaryEntry)
    assert Plan(target="bids", entries=[]).ancillary == [] and Plan(target="bids", entries=[]).dataset_description == {}


def test_ancillary_edit_applies_and_unapproves():
    p = ancillary_plan()
    p.apply_ancillary_edits([{"id": "a0", "columns": {"name": "keep"}},
                             {"id": "a1", "content": {"age": {"Description": "years"}}},
                             {"id": "a2", "action": "edit", "content": "Hello"},
                             {"id": "a4", "action": "keep"}])
    assert p.ancillary[0].columns["name"] == "keep"
    assert p.ancillary[1].action == "edit" and p.ancillary[1].content == {"age": {"Description": "years"}}
    assert p.ancillary[2].content == "Hello" and p.ancillary[3].action == "drop"
    assert p.ancillary[4].action == "keep"
    assert p.approved is False


def test_ancillary_edit_unknown_id_raises():
    with pytest.raises(KeyError):
        ancillary_plan().apply_ancillary_edits([{"id": "nope", "action": "drop"}])


@pytest.mark.parametrize("edit", [
    {"id": "a3", "action": "keep"},  # sourcedata is never uploaded
    {"id": "a3", "action": "edit", "content": "x"},
    {"id": "a5", "action": "keep"},  # derivatives: phase 1
    {"id": "a0", "path": "../secret.tsv"},  # paths are not editable
    {"id": "a0", "path": "sourcedata/participants.tsv"},
    {"id": "a0", "kind": "core"},
    {"id": "a0", "flags": []},
    {"id": "a0", "action": "publish"},
    {"id": "a0", "columns": {"unknown": "keep"}},
    {"id": "a0", "columns": {"name": "rename"}},
    {"id": "a0", "columns": {"[x]": "keep"}},  # a header with an identifying value
    {"id": "a0", "columns": {"participant_id": "drop"}},
    {"id": "a0", "content": "a\tb\n"},  # tables are edited by column
    {"id": "a1", "content": "not a dict"},
    {"id": "a2", "content": {"not": "text"}},
    {"id": "a2", "action": "edit"},  # edit without content
    {"id": "a4", "content": "x"},  # folders have no content
    {"id": "a1", "columns": {"age": "keep"}},  # not a table
])
def test_ancillary_bad_edit_raises_and_leaves_plan(edit):
    p = ancillary_plan()
    snapshot = copy.deepcopy(p.ancillary)
    with pytest.raises(ValueError):
        p.apply_ancillary_edits([{"id": "a2", "action": "drop"}, edit])
    assert p.ancillary == snapshot and p.approved is True


def test_ancillary_same_path_allowed():
    p = ancillary_plan()
    p.apply_ancillary_edits([{"id": "a0", "path": "participants.tsv", "action": "drop"}])
    assert p.ancillary[0].action == "drop"


def test_set_dataset_description():
    p = ancillary_plan()
    p.set_dataset_description({"Funding": ["NSF 1"], "License": None})
    assert p.dataset_description == {"Authors": ["A. Researcher"], "Funding": ["NSF 1"]} and p.approved is False
    p.approved = True
    with pytest.raises(ValueError, match="BIDSVersion"):
        p.set_dataset_description({"BIDSVersion": "1.0", "Authors": []})
    assert p.dataset_description["Authors"] == ["A. Researcher"] and p.approved is True


def test_ancillary_source_not_editable():
    with pytest.raises(ValueError, match="source"):
        ancillary_plan().apply_ancillary_edits([{"id": "a0", "source": "sourcedata/x.tsv"}])


def test_locked_entry_and_date_column():
    p = ancillary_plan()
    p.ancillary[0].locked = True
    p.ancillary[0].flags = ["wording that no code reads"]
    with pytest.raises(ValueError, match="only be dropped"):
        p.apply_ancillary_edits([{"id": "a0", "action": "keep"}])
    p.ancillary[0].locked = False
    p.ancillary[0].flags = []  # flags carry no locks: the column lock is structured
    with pytest.raises(ValueError, match="shift_date or drop"):
        p.apply_ancillary_edits([{"id": "a0", "columns": {"visit": "keep"}}])
    p.apply_ancillary_edits([{"id": "a0", "columns": {"visit": "drop"}}])
    assert p.ancillary[0].columns["visit"] == "drop"


@pytest.mark.parametrize("field,value", [("locked", False), ("locked_columns", {}), ("flags", [])])
def test_locks_and_flags_not_editable(field, value):
    with pytest.raises(ValueError, match=f"cannot edit {field}"):
        ancillary_plan().apply_ancillary_edits([{"id": "a3", field: value}])


def test_roundtrip_keeps_locks(tmp_path):
    p = ancillary_plan()
    p.save(tmp_path / "plan.json")
    q = Plan.load(tmp_path / "plan.json")
    assert q.ancillary[3].locked is True and q.ancillary[0].locked_columns["visit"] == ["shift_date", "drop"]


@pytest.mark.parametrize("missing", ["source", "locked", "locked_columns"])
def test_old_plan_format_rejected_clearly(tmp_path, missing):
    p = ancillary_plan()
    p.save(tmp_path / "plan.json")
    data = json.loads((tmp_path / "plan.json").read_text())
    del data["ancillary"][0][missing]
    (tmp_path / "plan.json").write_text(json.dumps(data))
    with pytest.raises(ValueError, match="older aimport; re-scan"):
        Plan.load(tmp_path / "plan.json")


# --- reviewer edits: editable fields only, typed, subject-wide ----------------------

@pytest.mark.parametrize("field,value", [
    ("status", "ok"), ("source", "agent"), ("confidence", 1.0), ("reason", "x"), ("agent_note", "x"),
    ("description", "x"), ("series_idx", 1), ("subject_idx", 1), ("session_idx", 1), ("deface_opt_out", True),
])
def test_derived_fields_not_editable(field, value):
    p = Plan(target="bids", entries=[entry()], approved=True)
    with pytest.raises(ValueError, match=f"cannot edit {field}"):
        p.apply_edits([{"id": "e1", field: value}])
    assert p.entries[0] == entry() and p.approved is True


@pytest.mark.parametrize("field,value", [
    ("deface", "yes"), ("deface", 1), ("exclude", "false"), ("exclude", None), ("subject", 7), ("subject", "a-b"),
    ("subject", None), ("session", "1_2"), ("datatype", 3), ("suffix", ["T1w"]), ("entities", {"task": 1}),
    ("entities", ["task"]), ("brainlife_tags", "x"), ("brainlife_tags", [1]), ("brainlife_datatype", 5),
])
def test_bad_types_rejected(field, value):
    p = Plan(target="bids", entries=[entry()])
    with pytest.raises(ValueError, match=field):
        p.apply_edits([{"id": "e1", field: value}])
    assert p.entries[0] == entry()


def test_datatype_edit_resets_deface():
    p = Plan(target="bids", entries=[entry(datatype="func", suffix="bold")])
    p.apply_edits([{"id": "e1", "datatype": "anat", "suffix": "T1w"}])
    assert p.entries[0].deface is True and p.entries[0].deface_opt_out is False
    p.apply_edits([{"id": "e1", "deface": False}])
    assert p.entries[0].deface is False and p.entries[0].deface_opt_out is True
    p.apply_edits([{"id": "e1", "datatype": "dwi", "suffix": "dwi"}])
    assert p.entries[0].deface is False and p.entries[0].deface_opt_out is False
    p.apply_edits([{"id": "e1", "datatype": "anat", "suffix": "T2w", "deface": False}])
    assert p.entries[0].deface is False and p.entries[0].deface_opt_out is True


def test_subject_edit_applies_to_the_whole_subject():
    p = Plan(target="bids", entries=[entry(id="a"), entry(id="b", series_idx=1),
                                     entry(id="c", subject_idx=1, subject="02")])
    touched = p.apply_edits([{"id": "a", "subject": "ctl01"}])
    assert [e.subject for e in p.entries] == ["ctl01", "ctl01", "02"]
    assert {e.id for e in touched} == {"a", "b"}
    with pytest.raises(ValueError, match="different IDs"):
        p.apply_edits([{"id": "a", "subject": "x1"}, {"id": "b", "subject": "x2"}])
    with pytest.raises(ValueError, match="share one subject ID"):
        p.apply_edits([{"id": "c", "subject": "ctl01"}])
    p.apply_edits([{"id": "a", "subject": "02"}, {"id": "c", "subject": "ctl01"}])  # a swap is fine
    assert [e.subject for e in p.entries] == ["02", "02", "ctl01"]
