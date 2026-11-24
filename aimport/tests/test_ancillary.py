"""Ancillary and metadata files: participants, phenotype, core files, tables, inherited sidecars, folders.

The fixture (tests/fixtures/ancillary/, see DATASETS.md) is synthetic and plants identifiers in
every file and every column type.
"""
import gzip
import json
import os
import shutil
from dataclasses import asdict
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from aimport.ancillary import (LINK, NO_IMAGE, NO_PARTICIPANT_ID, RAGGED, UNLINKED, UNREVIEWED_TEXT, _age_cap,
                               find_ancillary, id_maps, plan_ancillary, read_dataset_description, shift_date)
from aimport.ezbids_runner import CoreObject, CoreResult, CoreSeries, CoreSubject
from aimport.plan import Plan
from aimport.planner import build_plan
from aimport.pseudonyms import PseudonymKey
from aimport.writer import write_bids
from conftest import NATIVE, PLANTED, tokens
from test_writer import entry, read_tsv, write_nifti

FIXTURE = Path(__file__).parent / "fixtures" / "ancillary"
TERMS = {"Smith^John", "Smith", "John", "MRN0042", "19700101", "1970-01-01", "Hospital X"}
FUNC_COMPANIONS = ("task-rest_events.tsv", "task-rest_events.json", "task-rest_recording-cardiac_physio.tsv.gz",
                   "task-rest_recording-cardiac_physio.json", "task-nback_events.tsv")


class AncWorld:
    """The fixture as input: sub-01 (two scans) -> aa, sub-MRN0042 (one scan) -> bb; sub-99 is not imported."""

    def __init__(self, base: Path, schema, folders: bool = True, nested: str = ""):
        self.schema = schema
        self.inp, self.staged, self.out = base / "in", base / "staged", base / "out"
        self.root = self.inp / nested if nested else self.inp
        shutil.copytree(FIXTURE, self.root)
        pre = f"{nested}/" if nested else ""
        specs = [(0, 0, "sub-01/ses-1/anat/sub-01_ses-1_T1w"), (1, 0, "sub-01/ses-1/func/sub-01_ses-1_task-rest_bold"),
                 (0, 1, "sub-MRN0042/ses-1/anat/sub-MRN0042_ses-1_T1w")]
        specs = [(i, s, pre + stem) for i, s, stem in specs]
        if not folders:  # pure DICOM-like input: no sub- folders
            specs = [(i, s, f"dicom{n}/img") for n, (i, s, _) in enumerate(specs)]
        objs = []
        for series_idx, subject_idx, stem in specs:
            write_nifti(self.staged / f"{stem}.nii.gz")
            (self.staged / f"{stem}.json").write_text("{}")
            objs.append(CoreObject(series_idx, subject_idx, 0, "2023-01-10", "09:00:00", {},
                                   [Path(f"./{stem}.json"), Path(f"./{stem}.nii.gz")], {"RepetitionTime": 2.0}))
        series = [CoreSeries(i, "x", {}, "", "d", {}, Path("x")) for i in range(2)]
        subjects = [CoreSubject(0, "01", [{"PatientID": "MRN0042"}], [{"session": "1"}]),
                    CoreSubject(1, "MRN0042", [{"PatientID": "P0002"}], [{"session": "1"}])]
        self.core = CoreResult(series, objs, subjects)
        self.plan = Plan(target="bids", approved=True, dataset_name="Study", entries=[
            entry(0, "anat", "T1w", subject="aa"),
            entry(1, "func", "bold", {"task": "rest"}, subject="aa"),
            entry(0, "anat", "T1w", subject_idx=1, subject="bb"),
        ])
        self.ids = id_maps(self.core, self.plan.entries)
        self.replan()

    def replan(self):
        self.plan.ancillary = plan_ancillary(find_ancillary(self.inp, self.schema), self.inp, TERMS, self.ids,
                                             self.schema)

    def edit(self, *edits):
        self.plan.apply_ancillary_edits(list(edits))
        self.plan.approved = True

    def entry_for(self, path):
        return next(a for a in self.plan.ancillary if a.path == path)

    def write(self, key):
        return write_bids(self.plan, self.core, self.inp, TERMS, key, self.schema, self.out, staged_dir=self.staged)


@pytest.fixture
def world(tmp_path, schema):
    return AncWorld(tmp_path, schema)


@pytest.fixture
def key(tmp_path):
    k = PseudonymKey.load(tmp_path / "keys", "proj")
    yield k
    k.close()


def shifted(iso: str, days: int) -> str:
    return (date.fromisoformat(iso) + timedelta(days=days)).isoformat()


# --- detection and defaults ----------------------------------------------------

def test_find_ancillary(schema):
    found = {p.relative_to(FIXTURE).as_posix() for p in find_ancillary(FIXTURE, schema)}
    assert found == {
        "CHANGES", "CITATION.cff", "LICENSE", "README", "dataset_description.json", "genetic_info.json",
        "participants.json", "participants.tsv", "samples.tsv", "phenotype/moca.json", "phenotype/moca.tsv",
        "task-rest_bold.json", "task-rest_events.json", "task-smith_bold.json",
        "sub-01/sub-01_sessions.tsv", "sub-01/sub-01_sessions.json", "sub-01/ses-1/sub-01_ses-1_scans.tsv",
        "sub-01/ses-1/sub-01_ses-1_task-rest_bold.json", "sub-MRN0042/sub-MRN0042_sessions.tsv", "code",
        "sourcedata", "derivatives",
    } | {f"sub-01/ses-1/func/sub-01_ses-1_{n}" for n in FUNC_COMPANIONS}  # not notes.json (no BIDS suffix) nor proj.aimport-key.json


def test_plan_defaults(world):
    by_path = {a.path: a for a in world.plan.ancillary}
    assert set(by_path) == {
        "CHANGES", "CITATION.cff", "LICENSE", "README", "genetic_info.json", "participants.json", "participants.tsv",
        "samples.tsv", "phenotype/moca.json", "phenotype/moca.tsv", "task-rest_bold.json", "task-rest_events.json",
        "sub-aa/sub-aa_sessions.tsv", "sub-aa/sub-aa_sessions.json", "sub-aa/ses-1/sub-aa_ses-1_scans.tsv",
        "sub-aa/ses-1/sub-aa_ses-1_task-rest_bold.json", "sub-bb/sub-bb_sessions.tsv", "code", "sourcedata", "derivatives",
    } | {f"sub-aa/ses-1/func/sub-aa_ses-1_{n}" for n in FUNC_COMPANIONS}  # task-smith_bold.json cannot be named without the identifier; dataset_description goes to the plan
    assert len({a.id for a in world.plan.ancillary}) == len(world.plan.ancillary)
    p = by_path["participants.tsv"]
    assert p.kind == "table" and p.action == "keep"
    assert p.columns == {"participant_id": "keep", "age": "keep", "sex": "keep", "name": "drop", "dob": "drop",
                         "visit_date": "shift_date", "site": "keep", "handedness": "keep", "notes": "drop",
                         "email": "drop", "hospital_id": "drop"}
    assert any("name" in f for f in p.flags) and any("visit_date" in f for f in p.flags)
    assert by_path["phenotype/moca.tsv"].kind == "phenotype"
    assert by_path["phenotype/moca.tsv"].columns["assessment_date"] == "shift_date"
    assert by_path["phenotype/moca.tsv"].columns["examiner_initials"] == "drop"
    assert by_path["phenotype/moca.json"].kind == "phenotype_json"
    assert by_path["participants.json"].kind == "table_json"
    assert by_path["README"].kind == "core" and by_path["README"].action == "keep"
    assert by_path["task-rest_bold.json"].kind == "inherited_sidecar"
    assert by_path["task-rest_events.json"].kind == "events"
    assert by_path["sub-aa/sub-aa_sessions.tsv"].columns["acq_time"] == "shift_date"
    for folder in ("code", "sourcedata", "derivatives"):
        assert by_path[folder].kind == "folder" and by_path[folder].action == "drop" and by_path[folder].reason
    text = json.dumps([asdict(a) for a in world.plan.ancillary])
    assert not (PLANTED | NATIVE) & tokens(text)


def test_dataset_description_and_name_seeded_by_build_plan(tmp_path, schema, key):
    w = AncWorld(tmp_path, schema)
    w.core.subjects[0].patient_info = [{"PatientName": "Smith^John", "PatientID": "MRN0042",
                                        "PatientBirthDate": "19700101", "InstitutionName": "Hospital X"}]
    p = build_plan(w.core, w.inp, key, set(), None, schema, "bids")
    assert p.dataset_name == "Memory study at [x]"
    assert p.dataset_description == {"Authors": ["[x] [x]", "A. Researcher"], "License": "CC0",
                                      "Funding": ["Grant [x]"], "EthicsApprovals": ["[x] IRB [x]"],
                                      "Acknowledgements": "Thanks to [x] for the scans"}
    assert p.ancillary and not (PLANTED | NATIVE) & tokens(json.dumps(asdict(p)))
    assert UNLINKED not in p.warnings


def test_unlinked_tables_warned_by_build_plan(tmp_path, schema, key):
    w = AncWorld(tmp_path, schema, folders=False)
    p = build_plan(w.core, w.inp, key, set(), None, schema, "bids")
    assert UNLINKED in p.warnings
    assert not any(a.path.startswith("sub-") for a in p.ancillary)


# --- participants ------------------------------------------------------------------

def test_participants_remapped_unknown_rows_dropped(world, key):
    world.write(key)
    lines = (world.out / "participants.tsv").read_text().splitlines()
    assert lines[0].split("\t")[0] == "participant_id"
    rows = read_tsv(world.out / "participants.tsv")
    assert [r["participant_id"] for r in rows] == ["sub-aa", "sub-bb"]


def test_identifying_columns_dropped_by_default(world, key):
    world.write(key)
    rows = read_tsv(world.out / "participants.tsv")
    assert set(rows[0]) == {"participant_id", "age", "sex", "visit_date", "site", "handedness"}
    assert [r["site"] for r in rows] == ["n/a", "Main campus"]  # "Hospital X" redacted
    pj = json.loads((world.out / "participants.json").read_text())
    assert set(pj) == {"participant_id", "age", "visit_date", "site", "handedness"}
    assert pj["site"]["Description"] == "site: [x] or Main campus"


def test_identifying_column_kept_on_edit_still_redacted(world, key):
    world.edit({"id": world.entry_for("participants.tsv").id, "columns": {"name": "keep", "notes": "keep"}})
    world.write(key)
    rows = read_tsv(world.out / "participants.tsv")
    assert [r["name"] for r in rows] == ["n/a", "Jane Doe"]
    assert [r["notes"] for r in rows] == ["n/a", "n/a"]
    assert "name" in json.loads((world.out / "participants.json").read_text())


def test_date_column_shifted_with_subject_offset(world, key):
    world.write(key)
    rows = read_tsv(world.out / "participants.tsv")
    assert rows[0]["visit_date"] == shifted("2023-01-10", key.date_offset_days("aa"))
    bb = date(2023, 2, 14) + timedelta(days=key.date_offset_days("bb"))
    assert rows[1]["visit_date"] == bb.strftime("%Y%m%d")  # same format as the input


def test_age_capped_and_supplied_values_win(world, key, monkeypatch):
    monkeypatch.setattr("aimport.writer._Writer.demographics", lambda self, items: ("50", "O"))
    world.write(key)
    rows = read_tsv(world.out / "participants.tsv")
    assert [(r["age"], r["sex"]) for r in rows] == [("45", "F"), ("89", "M")]


def test_generated_columns_appear_when_supplied_dropped(world, key, monkeypatch):
    monkeypatch.setattr("aimport.writer._Writer.demographics", lambda self, items: ("50", "O"))
    world.edit({"id": world.entry_for("participants.tsv").id, "columns": {"age": "drop"}})
    world.write(key)
    rows = read_tsv(world.out / "participants.tsv")
    assert [(r["age"], r["sex"]) for r in rows] == [("50", "F"), ("50", "M")]
    pj = json.loads((world.out / "participants.json").read_text())
    assert pj["age"]["Description"] == "age at first scan of this import"


def test_edited_participants_json_written_redacted(world, key):
    world.edit({"id": world.entry_for("participants.json").id,
                "content": {"site": {"Description": "where John Smith was scanned"}, "name": {"Description": "x"}}})
    world.write(key)
    pj = json.loads((world.out / "participants.json").read_text())
    assert pj == {"site": {"Description": "where [x] [x] was scanned"}}  # name is a dropped column


def test_unlinked_tables_rows_dropped_descriptions_kept(tmp_path, schema, key):
    w = AncWorld(tmp_path, schema, folders=False)
    w.write(key)
    rows = read_tsv(w.out / "participants.tsv")
    assert [r["participant_id"] for r in rows] == ["sub-aa", "sub-bb"]  # the generated rows only
    assert {r["visit_date"] for r in rows} == {"n/a"} and {r["handedness"] for r in rows} == {"n/a"}
    assert "handedness" in json.loads((w.out / "participants.json").read_text())
    assert (w.out / "phenotype/moca.tsv").read_text().splitlines() == [
        "participant_id\tmoca_total\tassessment_date\trater"]


# --- phenotype, sessions, scans, samples --------------------------------------------

def test_phenotype_written_and_redacted(world, key):
    world.write(key)
    rows = read_tsv(world.out / "phenotype/moca.tsv")
    assert [r["participant_id"] for r in rows] == ["sub-aa", "sub-bb"]
    assert set(rows[0]) == {"participant_id", "moca_total", "assessment_date", "rater"}
    assert [r["rater"] for r in rows] == ["n/a", "Lee"]
    assert rows[0]["assessment_date"] == shifted("2023-01-11", key.date_offset_days("aa"))
    bb = datetime(2023, 2, 15, 10) + timedelta(days=key.date_offset_days("bb"))
    assert rows[1]["assessment_date"] == bb.isoformat()
    pj = json.loads((world.out / "phenotype/moca.json").read_text())
    assert pj["MeasurementToolMetadata"]["Description"] == "MoCA given at [x]"
    assert set(pj) == {"MeasurementToolMetadata", "moca_total", "assessment_date", "rater"}


def test_sessions_remapped_and_shifted(world, key):
    world.write(key)
    rows = read_tsv(world.out / "sub-aa/sub-aa_sessions.tsv")
    off = key.date_offset_days("aa")
    assert rows == [{"session_id": "ses-1", "acq_time": (datetime(2023, 1, 10, 9) + timedelta(days=off)).isoformat(),
                     "operator": "n/a"}]  # ses-2 is not in this import
    assert json.loads((world.out / "sub-aa/sub-aa_sessions.json").read_text())["operator"] == {
        "Description": "MR technologist, e.g. [x]"}
    assert read_tsv(world.out / "sub-bb/sub-bb_sessions.tsv")[0]["session_id"] == "ses-1"


def test_supplied_scans_merged_into_generated(world, key):
    world.write(key)
    rows = read_tsv(world.out / "sub-aa/ses-1/sub-aa_ses-1_scans.tsv")
    assert {r["filename"]: r["quality"] for r in rows} == {"anat/sub-aa_ses-1_T1w.nii.gz": "good",
                                                           "func/sub-aa_ses-1_task-rest_bold.nii.gz": "poor"}
    assert "comment" not in rows[0] and rows[0]["acq_time"] != "2023-01-10T09:00:00"


def test_samples_remapped(world, key):
    world.write(key)
    assert read_tsv(world.out / "samples.tsv") == [
        {"sample_id": "sample-01", "participant_id": "sub-aa", "sample_type": "tissue", "collected_by": "n/a"}]


# --- core files, sidecars, folders ------------------------------------------------------

def test_core_files_redacted_and_supplied_readme_wins(world, key):
    world.plan.readme = "Generated readme"
    world.write(key)
    assert (world.out / "README").read_text() == ("Synthetic test dataset: three participants scanned at [x].\n"
                                                  "Contact: [x] [x] ([x]), born [x].\n")
    assert not (world.out / "README.md").exists()
    assert (world.out / "CHANGES").read_text() == "1.0.0 2023-01-10\n  - [x] added data from [x].\n"
    assert "family-names: [x]" in (world.out / "CITATION.cff").read_text()
    gi = json.loads((world.out / "genetic_info.json").read_text())
    assert gi["Database"]["Descriptors"] == ["[x] biobank [x]"]


def test_edited_readme_written_redacted(world, key):
    world.edit({"id": world.entry_for("README").id, "action": "edit", "content": "Edited by John Smith"})
    world.write(key)
    assert (world.out / "README").read_text() == "Edited by [x] [x]"


def test_dropped_readme_falls_back_to_generated(world, key):
    world.plan.readme = "Generated by Smith"
    world.edit({"id": world.entry_for("README").id, "action": "drop"})
    world.write(key)
    assert not (world.out / "README").exists() and (world.out / "README.md").read_text() == "Generated by [x]"


def test_dataset_description_merges_plan_fields(world, key):
    world.plan.dataset_description = {"Authors": ["John Smith", "B. Author"], "License": "CC-BY-4.0",
                                      "BIDSVersion": "0.0", "GeneratedBy": "me"}
    world.write(key)
    dd = json.loads((world.out / "dataset_description.json").read_text())
    assert dd == {"Name": "Study", "BIDSVersion": "1.11.2", "DatasetType": "raw", "GeneratedBy": [{"Name": "brainlife.io/aimport"}],
                  "Authors": ["[x] [x]", "B. Author"], "License": "CC-BY-4.0"}


def test_inherited_sidecar_written_and_redacted(world, key):
    world.write(key)
    assert json.loads((world.out / "task-rest_bold.json").read_text()) == {
        "TaskName": "rest", "RepetitionTime": 2.0, "TaskDescription": "eyes open; run by [x] [x]",
        "Instructions": "Relax"}
    assert json.loads((world.out / "sub-aa/ses-1/sub-aa_ses-1_task-rest_bold.json").read_text()) == {
        "TaskDescription": "session-level instructions from [x]"}
    ev = json.loads((world.out / "task-rest_events.json").read_text())
    assert ev["trial_type"]["Levels"]["go"] == "go trial, designed by [x]"


def test_code_folder_only_on_opt_in_redacted(world, key):
    world.write(key)
    assert not (world.out / "code").exists()
    shutil.rmtree(world.out)
    world.edit({"id": world.entry_for("code").id, "action": "keep"})
    world.write(key)
    assert (world.out / "code/convert.py").read_text() == '# conversion script by [x] [x], [x]\nprint("convert")\n'


@pytest.mark.parametrize("folder", ["sourcedata", "derivatives"])
def test_never_kept_folder_raises(world, key, folder):
    with pytest.raises(ValueError):
        world.plan.apply_ancillary_edits([{"id": world.entry_for(folder).id, "action": "keep"}])
    world.entry_for(folder).action = "keep"  # a plan tampered with outside apply_ancillary_edits
    with pytest.raises(ValueError, match=folder):
        world.write(key)
    assert not world.out.exists()


def test_never_written(world, key):
    world.write(key)
    names = {p.relative_to(world.out).as_posix() for p in world.out.rglob("*")}
    assert not any(n.startswith(("sourcedata", "derivatives", "sub-01", "sub-MRN0042", "sub-99")) for n in names)
    assert not any("aimport-key" in n or "smith" in n.lower() or n == "notes.json" for n in names)


def test_written_list_is_every_file(world, key):
    written = world.write(key)
    assert {p.resolve() for p in written} == {p.resolve() for p in world.out.rglob("*") if p.is_file()}


def test_no_identifiers_with_everything_kept(world, key):
    """Ruling 8: every file kept, every column kept where allowed, edited content too: no planted term anywhere."""
    edits = []
    for a in world.plan.ancillary:
        if a.locked:
            continue
        edit = {"id": a.id, "action": "keep"}
        if a.columns:
            edit["columns"] = {c: "keep" if "keep" in a.locked_columns.get(c, ["keep"]) else a.locked_columns[c][0]
                               for c in a.columns}
        edits.append(edit)
    world.edit(*edits)
    world.edit({"id": world.entry_for("LICENSE").id, "action": "edit", "content": "Owned by Hospital X, MRN0042"},
               {"id": world.entry_for("phenotype/moca.json").id, "content": {"rater": {"Description": "Smith^John 19700101"}}})
    written = world.write(key)
    assert (world.out / "code/convert.py").exists() and (world.out / "participants.tsv").exists()
    texts = [p for p in written if not p.name.endswith((".nii.gz", ".nii"))]
    assert len(texts) > 20
    for p in texts:
        text = gzip.open(p, "rt").read() if p.name.endswith(".gz") else p.read_text()
        assert not (PLANTED | NATIVE) & tokens(text), p
    assert read_tsv(world.out / "participants.tsv")[1]["hospital_id"] == "H-7"


def test_folder_file_named_like_a_folder_rule_ignored(tmp_path, schema):
    (tmp_path / "code").write_text("John Smith")
    assert find_ancillary(tmp_path, schema) == []


def test_never_kept_folder_flags_count_binary(world):
    code = world.entry_for("code")
    assert code.flags == ["1 files, 0 of them binary"]


# --- review round 1 regressions -------------------------------------------------------



def test_c1_table_without_participant_id_never_uploaded(tmp_path, schema, key):
    w = AncWorld(tmp_path, schema)
    (w.inp / "phenotype/iq.tsv").write_text("subject\tiq\n01\t100\n99\t120\nJaneDoe\t90\n")
    (w.inp / "phenotype/iq.json").write_text('{"iq": {"Description": "IQ"}}')
    w.replan()
    iq = w.entry_for("phenotype/iq.tsv")
    assert iq.action == "drop" and NO_PARTICIPANT_ID in iq.flags
    assert w.entry_for("phenotype/iq.json").action == "drop"
    assert iq.locked and w.entry_for("phenotype/iq.json").locked
    with pytest.raises(ValueError, match="only be dropped"):
        w.plan.apply_ancillary_edits([{"id": iq.id, "action": "keep"}])
    iq.action = "keep"  # tampered
    with pytest.raises(ValueError, match="not uploadable"):
        w.write(key)
    iq.action = "drop"
    w.write(key)
    assert not (w.out / "phenotype/iq.tsv").exists()


def test_c2_links_never_followed(tmp_path, schema, key):
    w = AncWorld(tmp_path, schema)
    (w.inp / "secret.aimport-key.json").write_text('{"Jane Q Public": "aa"}')
    os.symlink(w.inp / "secret.aimport-key.json", w.inp / "code/keycopy.txt")
    os.symlink(w.inp / "sourcedata/sub-01/info.txt", w.inp / "code/raw.txt")
    (w.inp / "CHANGES").unlink()
    os.symlink(w.inp / "sourcedata/sub-01/info.txt", w.inp / "CHANGES")
    w.replan()
    code, changes = w.entry_for("code"), w.entry_for("CHANGES")
    assert any("code/keycopy.txt" in f for f in code.flags) and any("code/raw.txt" in f for f in code.flags)
    assert changes.action == "drop" and LINK in changes.flags
    with pytest.raises(ValueError, match="only be dropped"):
        w.plan.apply_ancillary_edits([{"id": changes.id, "action": "keep"}])
    w.edit({"id": code.id, "action": "keep"})
    w.write(key)
    assert sorted(p.name for p in (w.out / "code").iterdir()) == ["convert.py"]
    assert not (w.out / "CHANGES").exists()
    shutil.rmtree(w.out)
    changes.action, changes.flags, changes.locked = "keep", [], False  # tampered: the writer itself refuses a link
    with pytest.raises(ValueError, match="link"):
        w.write(key)


def test_a_renamed_subject_takes_its_files(world, key):
    for e in world.plan.entries:
        if e.subject == "aa":
            e.subject = "cc"
    world.write(key)
    names = {p.relative_to(world.out).as_posix() for p in world.out.rglob("*") if p.is_file()}
    assert not any(n.startswith("sub-aa") for n in names)
    for n in ["sub-cc/sub-cc_sessions.tsv", "sub-cc/sub-cc_sessions.json", "sub-cc/ses-1/sub-cc_ses-1_task-rest_bold.json",
              "sub-cc/ses-1/func/sub-cc_ses-1_task-rest_events.tsv"]:
        assert n in names, n
    assert read_tsv(world.out / "sub-cc/ses-1/sub-cc_ses-1_scans.tsv")[0]["quality"] == "good"
    assert [r["participant_id"] for r in read_tsv(world.out / "participants.tsv")] == ["sub-bb", "sub-cc"]
    assert all("<" not in a.source or "sub-<" in a.source for a in world.plan.ancillary)
    assert not any("MRN0042" in a.source or "sub-01" in a.source for a in world.plan.ancillary)


def test_b_dataset_nested_two_levels(tmp_path, schema, key):
    w = AncWorld(tmp_path, schema, nested="study/bids")
    assert {a.path for a in w.plan.ancillary} >= {"participants.tsv", "sub-aa/sub-aa_sessions.tsv", "README"}
    assert read_dataset_description(w.inp, TERMS)[0] == "Memory study at [x]"
    w.write(key)
    assert [r["participant_id"] for r in read_tsv(w.out / "participants.tsv")] == ["sub-aa", "sub-bb"]
    assert (w.out / "sub-aa/ses-1/func/sub-aa_ses-1_task-rest_events.tsv").exists()


def test_c_run_companions_follow_their_image(world, key):
    world.write(key)
    func = world.out / "sub-aa/ses-1/func"
    events = read_tsv(func / "sub-aa_ses-1_task-rest_events.tsv")
    assert events == [{"onset": "0.0", "duration": "2.0", "trial_type": "go"},
                      {"onset": "4.0", "duration": "2.0", "trial_type": "stop"}]  # response_note dropped
    assert json.loads((func / "sub-aa_ses-1_task-rest_events.json").read_text()) == {
        "trial_type": {"Description": "condition chosen by [x]"}}
    physio = gzip.open(func / "sub-aa_ses-1_task-rest_recording-cardiac_physio.tsv.gz", "rt").read()
    assert physio == "0.1\t1.0\n0.2\t1.1\n0.3\tn/a\n"
    assert json.loads((func / "sub-aa_ses-1_task-rest_recording-cardiac_physio.json").read_text())[
        "Manufacturer"] == "[x] lab"
    nback = world.entry_for("sub-aa/ses-1/func/sub-aa_ses-1_task-nback_events.tsv")
    assert nback.action == "drop" and NO_IMAGE in nback.flags
    assert not (func / "sub-aa_ses-1_task-nback_events.tsv").exists()


def test_c_companion_follows_a_new_image_name(world, key):
    world.plan.entries[1].entities = {"task": "rest", "acquisition": "mb"}
    world.write(key)
    assert (world.out / "sub-aa/ses-1/func/sub-aa_ses-1_task-rest_acq-mb_events.tsv").exists()


@pytest.mark.parametrize("header,cap", [("PatientAge", 89), ("ScanAge", 89), ("subjectage", 89), ("age", 89),
                                        ("age_at_scan", 89), ("AGE", 89), ("age_months", 89 * 12),
                                        ("agent", None), ("agency", None), ("image", None), ("percentage", None),
                                        ("stage", None), ("STAGE", None), ("IMAGE", None), ("TUMOR_STAGE", None),
                                        ("AverageAge", None), ("PATIENTAGE", 89), ("Scan_Age", 89)])
def test_6_age_headers(header, cap):
    assert _age_cap(header) == cap


def test_6_patient_age_capped(tmp_path, schema, key):
    w = AncWorld(tmp_path, schema)
    (w.inp / "participants.tsv").write_text("participant_id\tPatientAge\nsub-01\t95\nsub-MRN0042\t40\n")
    w.replan()
    w.write(key)
    assert [r["PatientAge"] for r in read_tsv(w.out / "participants.tsv")] == ["89", "40"]


@pytest.mark.parametrize("value,slash,expected", [
    ("2014-09-20", "mdy", "2014-09-25"), ("2014-09-20T10:00:00", "mdy", "2014-09-25T10:00:00"),
    ("20140920", "mdy", "20140925"), ("2014/09/20", "mdy", "2014/09/25"), ("2014.09.20", "mdy", "2014.09.25"),
    ("09/20/2014", "mdy", "09/25/2014"), ("9/20/2014", "mdy", "9/25/2014"), ("20/09/2014", "dmy", "25/09/2014"),
    ("20.09.2014", "mdy", "25.09.2014"), ("20 Sep 2014", "mdy", "25 Sep 2014"),
    ("Sep 20, 2014", "mdy", "Sep 25, 2014"), ("September 28, 2014", "mdy", "October 3, 2014"),
    ("20/09/2014", "mdy", None), ("09/20/14", "mdy", None), ("hello", "mdy", None)])
def test_7_shift_date_formats(value, slash, expected):
    assert shift_date(value, 5, slash) == expected


def test_7_date_columns(tmp_path, schema, key):
    w = AncWorld(tmp_path, schema)
    (w.inp / "participants.tsv").write_text(
        "participant_id\tus\teu\tamb\ttwo_digit\twords\n"
        "sub-01\t09/20/2014\t20/09/2014\t03/04/2014\t09/20/14\t20 Sep 2014\n"
        "sub-MRN0042\t10/01/2014\t13/10/2014\t05/06/2014\t10/01/14\tOct 1, 2014\n")
    w.replan()
    p = w.entry_for("participants.tsv")
    assert p.columns == {"participant_id": "keep", "us": "shift_date", "eu": "shift_date", "amb": "shift_date",
                         "two_digit": "drop", "words": "shift_date"}
    assert any("'amb'" in f and "DD/MM" in f for f in p.flags)
    assert any(f.startswith("date column 'two_digit'") for f in p.flags)
    with pytest.raises(ValueError, match="can only be drop"):  # 8: a date column is shifted or dropped, never kept
        w.plan.apply_ancillary_edits([{"id": p.id, "columns": {"two_digit": "keep"}}])
    w.edit({"id": p.id, "columns": {"us": "drop"}})
    w.write(key)
    rows = read_tsv(w.out / "participants.tsv")
    off = key.date_offset_days("aa")
    assert "us" not in rows[0]
    assert rows[0]["eu"] == (date(2014, 9, 20) + timedelta(days=off)).strftime("%d/%m/%Y")
    assert rows[0]["amb"] == (date(2014, 3, 4) + timedelta(days=off)).strftime("%m/%d/%Y")


def test_9_10_free_text_and_flag(tmp_path, schema, key):
    w = AncWorld(tmp_path, schema)
    (w.inp / "participants.tsv").write_text(
        "participant_id\tremarks\tsummary\tgroup\n"
        "sub-01\tok\tparticipant arrived late and anxious\tcontrol\n"
        "sub-MRN0042\tfine\tlives near the clinic with family\tpatient\n")
    w.replan()
    p = w.entry_for("participants.tsv")
    assert p.columns == {"participant_id": "keep", "remarks": "drop", "summary": "drop", "group": "keep"}
    assert UNREVIEWED_TEXT in p.flags and any("'summary' holds free text" in f for f in p.flags)


def test_11_ragged_table_not_uploadable(tmp_path, schema, key):
    w = AncWorld(tmp_path, schema)
    (w.inp / "participants.tsv").write_text("participant_id\tage\nsub-01\t45\tJohn Smith\nsub-MRN0042\t40\n")
    w.replan()
    p = w.entry_for("participants.tsv")
    assert p.action == "drop" and RAGGED in p.flags
    with pytest.raises(ValueError, match="only be dropped"):
        w.plan.apply_ancillary_edits([{"id": p.id, "action": "keep"}])


def test_12_binary_files(tmp_path, schema, key):
    w = AncWorld(tmp_path, schema)
    (w.inp / "code/model.bin").write_bytes(b"\x00\x01Smith")
    (w.inp / "stimuli").mkdir()
    (w.inp / "stimuli/face.png").write_bytes(b"\x89PNG\x00\x00")
    (w.inp / "stimuli/instructions.txt").write_text("Read by John")
    w.replan()
    assert "binary file not uploaded: code/model.bin" in w.entry_for("code").flags
    assert "binary file copied as it is if kept: stimuli/face.png" in w.entry_for("stimuli").flags
    w.edit({"id": w.entry_for("code").id, "action": "keep"}, {"id": w.entry_for("stimuli").id, "action": "keep"})
    w.write(key)
    assert not (w.out / "code/model.bin").exists() and (w.out / "code/convert.py").exists()
    assert (w.out / "stimuli/face.png").read_bytes() == b"\x89PNG\x00\x00"
    assert (w.out / "stimuli/instructions.txt").read_text() == "Read by [x]"


def test_13_scans_rows_follow_the_written_file(world, key):
    world.plan.entries[0].entities = {"acquisition": "mprage"}  # the written name differs from the supplied one
    world.write(key)
    rows = read_tsv(world.out / "sub-aa/ses-1/sub-aa_ses-1_scans.tsv")
    assert {r["filename"]: r["quality"] for r in rows} == {"anat/sub-aa_ses-1_acq-mprage_T1w.nii.gz": "good",
                                                           "func/sub-aa_ses-1_task-rest_bold.nii.gz": "poor"}


# --- review round 2: locks are structured, and the writer does not trust the plan -------------

def reword_flags(w):
    for a in w.plan.ancillary:
        a.flags = [f.replace("not uploadable: ", "Not uploadable - ").replace("date column ", "Date column ")
                   for f in a.flags]


def test_reworded_flags_do_not_unlock(tmp_path, schema, key):
    """probe_v3: a saved plan whose flag wording changed must not let a locked table or date column be kept."""
    w = AncWorld(tmp_path, schema)
    (w.inp / "phenotype/iq.tsv").write_text(
        "subject\tiq\tvisit\n01\t100\t09/20/2014\nMRN0042\t110\t10/01/2014\n99\t120\t11/11/2014\n"
        "JaneDoe\t90\t12/12/2014\n")
    w.replan()
    reword_flags(w)
    iq, parts = w.entry_for("phenotype/iq.tsv"), w.entry_for("participants.tsv")
    with pytest.raises(ValueError, match="only be dropped"):
        w.plan.apply_ancillary_edits([{"id": iq.id, "action": "keep", "columns": {"visit": "keep"}}])
    with pytest.raises(ValueError, match="shift_date or drop"):
        w.plan.apply_ancillary_edits([{"id": parts.id, "columns": {"visit_date": "keep"}}])
    w.write(key)
    assert not (w.out / "phenotype/iq.tsv").exists()
    assert read_tsv(w.out / "participants.tsv")[0]["visit_date"] == shifted("2023-01-10", key.date_offset_days("aa"))


def test_writer_rederives_rules_from_the_source(tmp_path, schema, key):
    """A plan stripped of every lock (as if hand-edited) still cannot write what the file itself forbids."""
    w = AncWorld(tmp_path, schema)
    (w.inp / "phenotype/iq.tsv").write_text("subject\tiq\n01\t100\n99\t120\n")
    (w.inp / "phenotype/iq.json").write_text('{"iq": {"Description": "IQ"}}')
    (w.inp / "samples.tsv").write_text("sample_id\tparticipant_id\nsample-01\tsub-01\textra\n")
    (w.inp / "participants.tsv").write_text(
        "participant_id\tvisit_date\tseen\tgroup\nsub-01\t2023-01-10\t09/20/14\tA\nsub-MRN0042\t2023-02-14\t10/01/14\tB\n")
    w.replan()
    for a in w.plan.ancillary:
        if a.source.split("/")[0] in ("sourcedata", "derivatives"):
            continue
        a.locked, a.locked_columns, a.flags = False, {}, []
        a.action = "keep"
        a.columns = {c: "keep" for c in a.columns}
    refused = []
    write_bids(w.plan, w.core, w.inp, TERMS, key, schema, w.out, staged_dir=w.staged, refused=refused)
    assert not (w.out / "phenotype/iq.tsv").exists() and not (w.out / "phenotype/iq.json").exists()
    assert not (w.out / "samples.tsv").exists()  # ragged
    rows = read_tsv(w.out / "participants.tsv")
    assert set(rows[0]) == {"participant_id", "group", "age", "sex"}  # dates kept as they are: never written
    assert any(r.startswith("phenotype/iq.tsv: not written") for r in refused)
    assert any(r.startswith("samples.tsv: not written") for r in refused)
    assert any(r.startswith("phenotype/iq.json: not written") for r in refused)


def test_root_events_keep_rows_person_table_refused(tmp_path, schema, key):
    """Only person tables need participant_id; inherited events keep their rows, every cell redacted."""
    w = AncWorld(tmp_path, schema)
    (w.inp / "task-rest_events.tsv").write_text("onset\tduration\ttrial_type\n0\t1\tgo by Smith\n2\t1\tstop\n")
    (w.inp / "phenotype/iq.tsv").write_text("subject\tiq\n01\t100\n")
    w.replan()
    iq = w.entry_for("phenotype/iq.tsv")
    iq.action, iq.locked = "keep", False  # tampered: the writer refuses it on its own
    refused = []
    write_bids(w.plan, w.core, w.inp, TERMS, key, schema, w.out, staged_dir=w.staged, refused=refused)
    assert read_tsv(w.out / "task-rest_events.tsv") == [{"onset": "0", "duration": "1", "trial_type": "n/a"},
                                                        {"onset": "2", "duration": "1", "trial_type": "stop"}]
    assert not (w.out / "phenotype/iq.tsv").exists()
    assert any(r.startswith("phenotype/iq.tsv: not written") for r in refused)
