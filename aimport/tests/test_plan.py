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
