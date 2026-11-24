import copy
import json
import sys
from dataclasses import asdict
from pathlib import Path

import pytest

from aimport.ezbids_runner import CoreObject, CoreResult, CoreSeries, CoreSubject, parse_core, run_ezbids, stage_input
from aimport.planner import AGENT_TEXT_MAX, DATASET_NAME_MAX, README_MAX, _is_date_like, build_plan
from aimport.pseudonyms import PseudonymKey
from conftest import NATIVE, PLANTED, tokens

FIXTURES = Path(__file__).parent / "fixtures"
sys.path.insert(0, str(FIXTURES))
from fetch_dcm_qa import fetch_dcm_qa  # noqa: E402

CORE_JSON = FIXTURES / "ezbids_core_siemens.json"
CACHE = Path("/tmp/aimport-dcm-qa-cache")  # docker runs mount the tarball cache here
T1W, BOLD, MAG1, PHASEDIFF, ASL = 0, 1, 2, 3, 16  # series_idx in the committed fixture


class Recorder:
    """A fake LLM client: replies by step ("classify" / "metadata"), records what it was sent."""

    name = "recorder"

    def __init__(self, classify="[]", metadata="nope"):
        self.replies = {"classify": classify, "metadata": metadata}
        self.users: list[str] = []

    def complete(self, system, user, step):
        self.users.append(user)
        return self.replies[step]


def answer(idx, datatype, suffix, entities=None, confidence=0.9, reason="r"):
    return {"series_idx": idx, "datatype": datatype, "suffix": suffix,
            "entities": entities or {}, "confidence": confidence, "reason": reason}


def classify_reply(*answers):
    return json.dumps(list(answers))


@pytest.fixture(scope="module")
def base_core():
    return parse_core(CORE_JSON)


@pytest.fixture
def fixture_core(base_core):
    return copy.deepcopy(base_core)


@pytest.fixture
def key(tmp_path):
    k = PseudonymKey.load(tmp_path / "keys", "proj")
    yield k
    k.close()


@pytest.fixture
def in_dir(tmp_path):
    d = tmp_path / "in"
    d.mkdir()
    return d


@pytest.fixture
def plan(fixture_core, in_dir, key, schema):
    return build_plan(fixture_core, in_dir, key, set(), None, schema, "bids")


def entries_for(p, series_idx):
    return [e for e in p.entries if e.series_idx == series_idx]


def one(p, series_idx):
    (e,) = entries_for(p, series_idx)
    return e


def set_type(core, idx, type_, entities=None):
    s = next(s for s in core.series if s.series_idx == idx)
    s.type = type_
    if entities is not None:
        s.entities = entities


def name_patient(core, name="Smith^John", pid="MRN0042", birth="19700101"):
    core.subjects[0].patient_info = [{"PatientID": pid, "PatientName": name, "PatientBirthDate": birth,
                                      "file_directory": "./5_anat-T1w_acq-tfl"}]


# --- the brief's tests -------------------------------------------------------

def test_heuristic_entries(plan):
    assert any(e.suffix == "T1w" and e.source == "heuristic" for e in plan.entries)
    t1 = one(plan, T1W)
    assert (t1.datatype, t1.status, t1.exclude, t1.confidence) == ("anat", "ok", False, 0.8)
    assert t1.entities == {"acquisition": "tfl"}
    assert t1.deface is True and t1.brainlife_datatype == "neuro/anat/t1w"
    assert t1.reason.startswith("Acquisition is believed to be anat/T1w")
    assert one(plan, 4).deface is False


def test_one_entry_per_series_subject_session(plan, fixture_core):
    triples = {(o.series_idx, o.subject_idx, o.session_idx) for o in fixture_core.objects}
    assert len(plan.entries) == len(triples)
    assert len({e.id for e in plan.entries}) == len(plan.entries)
    assert {e.subject for e in plan.entries} == {"01"}
    assert {e.session for e in plan.entries} == {"1"}  # one unlabeled session still gets ses-1


def test_excluded_without_agent_is_unknown(plan):
    bold = one(plan, BOLD)
    assert (bold.status, bold.exclude, bold.source, bold.datatype) == ("unknown", True, "none", None)


def test_subject_ids_avoid_existing(fixture_core, in_dir, key, schema):
    p = build_plan(fixture_core, in_dir, key, {"01"}, None, schema, "bids")
    assert "01" not in {e.subject for e in p.entries}


def test_agent_fills_unknown(fixture_core, in_dir, key, schema):
    # the real BOLD (series 7) that ezBIDS excluded, and the T1w forced to "exclude"
    set_type(fixture_core, T1W, "exclude", {})
    rec = Recorder(classify_reply(answer(BOLD, "func", "bold", {"task": "rest"}, 0.7, "rest fMRI"),
                                  answer(T1W, "anat", "T1w", {}, 0.95, "MPRAGE")))
    p = build_plan(fixture_core, in_dir, key, set(), rec, schema, "bids")
    bold = one(p, BOLD)
    assert (bold.source, bold.datatype, bold.suffix, bold.entities) == ("agent", "func", "bold", {"task": "rest"})
    assert (bold.status, bold.exclude, bold.confidence, bold.reason) == ("ok", False, 0.7, "rest fMRI")
    assert bold.brainlife_datatype == "neuro/func/task" and bold.brainlife_tags == ["rest"]
    t1 = one(p, T1W)
    assert (t1.source, t1.suffix, t1.status, t1.deface) == ("agent", "T1w", "ok", True)


def test_low_confidence_agent_leaves_unknown(fixture_core, in_dir, key, schema):
    rec = Recorder(classify_reply(answer(BOLD, "func", "bold", {"task": "rest"}, 0.3)))
    bold = one(build_plan(fixture_core, in_dir, key, set(), rec, schema, "bids"), BOLD)
    assert (bold.status, bold.exclude) == ("unknown", True)


def test_agent_disagreement_kept_as_note(fixture_core, in_dir, key, schema):
    rec = Recorder(classify_reply(answer(T1W, "anat", "T2w", {}, 0.9, "long echo time")))
    t1 = one(build_plan(fixture_core, in_dir, key, set(), rec, schema, "bids"), T1W)
    assert (t1.suffix, t1.source, t1.confidence, t1.status) == ("T1w", "heuristic", 0.5, "ok")
    assert "T2w" in t1.agent_note and "long echo time" in t1.agent_note


def test_agent_agreement_raises_confidence(fixture_core, in_dir, key, schema):
    rec = Recorder(classify_reply(answer(T1W, "anat", "T1w", {}, 0.97)))
    t1 = one(build_plan(fixture_core, in_dir, key, set(), rec, schema, "bids"), T1W)
    assert (t1.source, t1.confidence, t1.entities) == ("heuristic", 0.97, {"acquisition": "tfl"})


def test_agent_fills_task_entity(fixture_core, in_dir, key, schema):
    set_type(fixture_core, BOLD, "func/bold", {"run": "1"})
    rec = Recorder(classify_reply(answer(BOLD, "func", "bold", {"task": "rest", "run": "2"}, 0.9)))
    bold = one(build_plan(fixture_core, in_dir, key, set(), rec, schema, "bids"), BOLD)
    assert bold.entities == {"task": "rest", "run": "1"}  # ezBIDS's run kept, agent fills task
    assert (bold.source, bold.status, bold.exclude) == ("heuristic", "ok", False)


def test_metadata_draft_redacted(fixture_core, in_dir, key, schema):
    name_patient(fixture_core)
    rec = Recorder(metadata=json.dumps({"name": "Smith lab T1w", "readme": "Smith scanned one T1w."}))
    p = build_plan(fixture_core, in_dir, key, set(), rec, schema, "bids")
    assert "[x]" in p.readme and "smith" not in (p.readme + p.dataset_name).lower()
    assert p.metadata_source == "agent"


def test_metadata_defaults_without_agent(plan):
    assert (plan.dataset_name, plan.readme, plan.metadata_source) == ("aimport dataset", "", "none")


def test_datatypes_target_excludes_unmapped(fixture_core, in_dir, key, schema):
    set_type(fixture_core, ASL, "pet/pet", {})
    p = build_plan(fixture_core, in_dir, key, set(), None, schema, "datatypes")
    pet = one(p, ASL)
    assert pet.datatype == "pet" and pet.exclude is True and pet.reason.endswith("; no brainlife datatype")
    assert one(p, T1W).exclude is False


def test_bids_target_keeps_unmapped(plan):
    asl = one(plan, ASL)
    assert (asl.datatype, asl.suffix, asl.exclude, asl.brainlife_datatype) == ("perf", "asl", True, None)  # excluded by default


def test_unsupported_datatype(fixture_core, in_dir, key, schema):
    set_type(fixture_core, ASL, "eeg/eeg", {"task": "rest"})
    e = one(build_plan(fixture_core, in_dir, key, set(), None, schema, "bids"), ASL)
    assert (e.status, e.exclude) == ("unsupported", True)


def test_secondary_capture_excluded_by_default(fixture_core, in_dir, key, schema):
    s = next(s for s in fixture_core.series if s.series_idx == T1W)
    s.sidecar = {**s.sidecar, "Modality": "OT", "ImageType": ["DERIVED", "SECONDARY"]}
    e = one(build_plan(fixture_core, in_dir, key, set(), None, schema, "bids"), T1W)
    assert (e.status, e.exclude, e.reason) == ("excluded_by_default", True, "may contain burned-in identifiers")


def test_description_redacted(fixture_core, in_dir, key, schema):
    name_patient(fixture_core)
    next(s for s in fixture_core.series if s.series_idx == T1W).series_description = "Smith_John T1"
    assert one(build_plan(fixture_core, in_dir, key, set(), None, schema, "bids"), T1W).description == "[x]_[x] T1"


# --- controller rulings ------------------------------------------------------

def test_warning_when_deidentification_unverified(plan):
    # in_dir holds no DICOMs and the committed fixture is already scrubbed
    assert any("de-identification could not be verified" in w for w in plan.warnings)


def test_guess_entity_with_identifier_not_sent(fixture_core, in_dir, key, schema):
    name_patient(fixture_core)
    set_type(fixture_core, T1W, "anat/T1w", {"acquisition": "smithT1"})
    rec = Recorder()
    p = build_plan(fixture_core, in_dir, key, set(), rec, schema, "bids")
    sent = json.loads(rec.users[0])["series"]
    guess = next(s for s in sent if s["series_idx"] == T1W)["ezbids_guess"]
    assert guess == {"datatype": "anat", "suffix": "T1w", "entities": {}}
    assert "smith" not in rec.users[0].lower()
    assert "acquisition" not in one(p, T1W).entities


def test_agent_text_redacted_and_truncated(fixture_core, in_dir, key, schema):
    name_patient(fixture_core)
    long = "Smith " + "y" * 600
    rec = Recorder(classify_reply(answer(BOLD, "func", "bold", {"task": "rest"}, 0.9, long),
                                  answer(T1W, "anat", "T2w", {}, 0.9, long)))
    p = build_plan(fixture_core, in_dir, key, set(), rec, schema, "bids")
    bold, t1 = one(p, BOLD), one(p, T1W)
    for text in (bold.reason, t1.agent_note):
        assert "smith" not in text.lower() and "[x]" in text
        assert len(text) <= AGENT_TEXT_MAX == 300


@pytest.mark.parametrize("other,expected", [("fmap/phase1", "2phasemag"), ("fmap/phasediff", "phasediff"),
                                            ("fmap/fieldmap", "single")])
def test_fmap_magnitude_tags_from_siblings(fixture_core, in_dir, key, schema, other, expected):
    set_type(fixture_core, PHASEDIFF, other, {})
    p = build_plan(fixture_core, in_dir, key, set(), None, schema, "datatypes")
    assert one(p, MAG1).brainlife_tags == [expected]


def test_func_bold_without_task_not_ok(fixture_core, in_dir, key, schema):
    set_type(fixture_core, BOLD, "func/bold", {})
    bold = one(build_plan(fixture_core, in_dir, key, set(), None, schema, "bids"), BOLD)
    assert (bold.status, bold.exclude) == ("unknown", True)
    assert "task" in bold.reason


def test_disallowed_ezbids_entity_not_ok(fixture_core, in_dir, key, schema):
    set_type(fixture_core, T1W, "anat/T1w", {"direction": "AP"})
    t1 = one(build_plan(fixture_core, in_dir, key, set(), None, schema, "bids"), T1W)
    assert (t1.status, t1.exclude) == ("unknown", True) and "direction" in t1.reason


def test_subject_original_is_patient_id(fixture_core, in_dir, key, schema):
    name_patient(fixture_core)
    p = build_plan(fixture_core, in_dir, key, set(), None, schema, "bids")
    assert key.subjects == {"id=MRN0042|name=Smith^John|dob=19700101": "01"}
    assert not PLANTED & tokens(json.dumps(asdict(p)))


def test_subject_original_name_and_birth_date_without_id(fixture_core, in_dir, key, schema):
    name_patient(fixture_core, pid="")
    build_plan(fixture_core, in_dir, key, set(), None, schema, "bids")
    assert key.subjects == {"name=Smith^John|dob=19700101": "01"}


def test_subject_label_proposed_from_sub_folder(fixture_core, in_dir, key, schema):
    fixture_core.subjects[0].label = "ctl07"
    fixture_core.subjects[0].patient_info[0]["file_directory"] = "./sub-ctl07/anat"
    p = build_plan(fixture_core, in_dir, key, set(), None, schema, "bids")
    assert {e.subject for e in p.entries} == {"ctl07"}


def test_subject_label_not_proposed_without_sub_folder(plan):
    assert {e.subject for e in plan.entries} == {"01"}  # ezBIDS label "july11" came from a name


def test_sessions_numbered_by_date(schema, in_dir, key):
    series = [CoreSeries(0, "anat/T1w", {}, "", "T1", {}, Path("x.nii.gz"))]
    objects = [CoreObject(0, 0, i, d, "", {}, [], {}) for i, d in enumerate(("2022-08-01", "2022-07-01"))]
    subjects = [CoreSubject(0, "x", [{"PatientID": "P1"}],
                            [{"session": "", "AcquisitionDate": "2022-08-01"},
                             {"session": "", "AcquisitionDate": "2022-07-01"}])]
    p = build_plan(CoreResult(series, objects, subjects), in_dir, key, set(), None, schema, "bids")
    assert {e.session_idx: e.session for e in p.entries} == {0: "2", 1: "1"}


def test_single_session_subject_gets_session_1(schema, in_dir, key):
    series = [CoreSeries(0, "anat/T1w", {}, "", "T1", {}, Path("x.nii.gz"))]
    objects = [CoreObject(0, 0, 0, "2022-07-01", "", {}, [], {})]
    subjects = [CoreSubject(0, "x", [{"PatientID": "P1"}], [{"session": "", "AcquisitionDate": "2022-07-01"}])]
    p = build_plan(CoreResult(series, objects, subjects), in_dir, key, set(), None, schema, "bids")
    assert p.entries[0].session == "1"


def test_alphanumeric_session_label_kept(schema, in_dir, key):
    series = [CoreSeries(0, "anat/T1w", {}, "", "T1", {}, Path("x.nii.gz"))]
    objects = [CoreObject(0, 0, 0, "", "", {}, [], {})]
    subjects = [CoreSubject(0, "x", [{"PatientID": "P1"}], [{"session": "pre", "AcquisitionDate": ""}])]
    p = build_plan(CoreResult(series, objects, subjects), in_dir, key, set(), None, schema, "bids")
    assert p.entries[0].session == "pre"


def mini_core(infos, sessions=None, objects=None, description="T1", entities=None, acq_date=""):
    """One T1w series; one subject per patient_info dict (one unlabeled session each by default)."""
    series = [CoreSeries(0, "anat/T1w", entities or {}, "", description, {}, Path("x.nii.gz"))]
    subjects = [CoreSubject(i, "", [info], sessions or [{"session": "", "AcquisitionDate": acq_date}])
                for i, info in enumerate(infos)]
    objects = objects or [CoreObject(0, i, 0, acq_date, "", {}, [], {}) for i in range(len(infos))]
    return CoreResult(series, objects, subjects)


ANON = {"PatientID": "anon", "PatientName": "ANON", "PatientBirthDate": "00000000"}


def subjects_of(p):
    return {e.subject_idx: e.subject for e in p.entries}


def test_two_anon_subjects_get_different_ids(schema, in_dir, key):
    p = build_plan(mini_core([ANON, {**ANON, "PatientID": "n/a"}]), in_dir, key, set(), None, schema, "bids")
    ids = subjects_of(p)
    assert ids[0] != ids[1]
    assert any("subject identity could not be established for 2 subject(s)" in w for w in p.warnings)


def test_shared_identity_in_one_run_gets_run_local_ids(schema, in_dir, key):
    info = {"PatientID": "P1", "PatientName": "Doe^Jane"}
    p = build_plan(mini_core([info, info]), in_dir, key, set(), None, schema, "bids")
    assert len(set(subjects_of(p).values())) == 2
    assert any(w.startswith("2 subjects share identical identifying values") for w in p.warnings)
    assert not any(k.startswith("id=") for k in key.subjects)


def test_same_identity_same_id_across_imports(fixture_core, in_dir, key, schema):
    name_patient(fixture_core)
    first = build_plan(fixture_core, in_dir, key, set(), None, schema, "bids")
    second = build_plan(fixture_core, in_dir, key, {"01"}, None, schema, "bids")
    assert {e.subject for e in first.entries} == {e.subject for e in second.entries} == {"01"}
    assert not any("subject identity" in w for w in first.warnings)


def test_placeholder_only_subject_is_run_local(fixture_core, in_dir, key, schema):
    # the committed fixture's PatientInfo is anon / anon / 00000000
    first = build_plan(fixture_core, in_dir, key, set(), None, schema, "bids")
    second = build_plan(fixture_core, in_dir, key, set(), None, schema, "bids")
    assert {e.subject for e in first.entries} != {e.subject for e in second.entries}
    assert any("for 1 subject(s)" in w for w in first.warnings)
    assert all(k.startswith("run:") for k in key.subjects)


def test_duplicate_subject_id_guard(schema, in_dir, key, monkeypatch):
    monkeypatch.setattr(key, "subject_id", lambda *a, **k: "01")
    core = mini_core([{"PatientID": "P1"}, {"PatientID": "P2"}])
    with pytest.raises(ValueError, match="both given subject ID"):
        build_plan(core, in_dir, key, set(), None, schema, "bids")


@pytest.mark.parametrize("label,expected", [
    ("20230115", True), ("19991231", True), ("230115", True), ("202301", True),
    ("20231340", False), ("18991231", False), ("123456", False), ("1", False), ("ctl01", False), ("2023", False),
])
def test_is_date_like(label, expected):
    assert _is_date_like(label) is expected


def test_date_session_label_is_numbered(schema, in_dir, key):
    core = mini_core([{"PatientID": "P1"}], sessions=[{"session": "20230115", "AcquisitionDate": "2023-01-15"}])
    p = build_plan(core, in_dir, key, set(), None, schema, "bids")
    assert p.entries[0].session == "1"


def test_date_entity_dropped(schema, in_dir, key):
    core = mini_core([{"PatientID": "P1"}], entities={"acquisition": "20230115"})
    assert build_plan(core, in_dir, key, set(), None, schema, "bids").entries[0].entities == {}


def test_scan_date_redacted_from_description(schema, in_dir, key):
    core = mini_core([{"PatientID": "P1"}], description="T1 20230115 and 2023-01-15", acq_date="2023-01-15")
    assert build_plan(core, in_dir, key, set(), None, schema, "bids").entries[0].description == "T1 [x] and [x]"


def test_unlisted_session_skips_used_labels(schema, in_dir, key):
    objects = [CoreObject(0, 0, 0, "", "", {}, [], {}), CoreObject(0, 0, 1, "", "", {}, [], {})]
    core = mini_core([{"PatientID": "P1"}], sessions=[{"session": "2", "AcquisitionDate": ""}], objects=objects)
    p = build_plan(core, in_dir, key, set(), None, schema, "bids")
    assert {e.session_idx: e.session for e in p.entries} == {0: "2", 1: "1"}


def test_metadata_capped(fixture_core, in_dir, key, schema):
    rec = Recorder(metadata=json.dumps({"name": "n" * 500, "readme": "r" * 9000}))
    p = build_plan(fixture_core, in_dir, key, set(), rec, schema, "bids")
    assert len(p.dataset_name) == DATASET_NAME_MAX == 120 and len(p.readme) == README_MAX == 5000


def test_key_left_open(plan, key):
    key.save()  # still holds the lock: build_plan must not close it


# --- docker: the whole pipeline on planted DICOMs ---------------------------

@pytest.fixture(scope="module")
def plan_planted(tmp_path_factory, schema):
    base = tmp_path_factory.mktemp("planted")
    src = fetch_dcm_qa(base / "in", cache=CACHE)
    staged = stage_input(src, base / "work")
    core = parse_core(run_ezbids(staged, log=lambda line: None))
    with PseudonymKey.load(base / "keys", "proj") as key:
        return build_plan(core, src, key, set(), None, schema, "bids", staged_dir=staged)


@pytest.mark.docker
def test_no_identifiers_in_plan(plan_planted):
    text = json.dumps(asdict(plan_planted))
    assert not PLANTED & tokens(text)
    assert not NATIVE & tokens(text)


@pytest.mark.docker
def test_planted_plan_has_entries_and_no_warning(plan_planted):
    assert plan_planted.warnings == []
    assert any(e.suffix == "T1w" and e.status == "ok" for e in plan_planted.entries)


def test_run_terms_agree_with_build_plan(fixture_core, in_dir, key, schema, monkeypatch):
    from aimport import planner

    name_patient(fixture_core)
    fixture_core.objects[0].acquisition_date = "2023-01-15"
    seen = []
    real = planner.run_terms
    monkeypatch.setattr(planner, "run_terms", lambda *a, **k: seen.append(real(*a, **k)) or seen[-1])
    build_plan(fixture_core, in_dir, key, set(), None, schema, "bids")
    terms = real(fixture_core, in_dir)
    assert seen == [terms]
    assert {"smith", "john", "mrn0042"} <= {t.lower() for t in terms}
    assert "20230115" in terms and "2023-01-15" in terms


# --- ASL excluded by default; the input's README seeds the plan's README ----------

def asl_entry(p):
    (e,) = [e for e in p.entries if e.series_idx == ASL]
    return e


def test_asl_excluded_by_default(plan):
    e = asl_entry(plan)
    assert (e.datatype, e.suffix) == ("perf", "asl")
    assert e.exclude is True
    assert e.reason == "ASL needs aslcontext.tsv and labeling metadata the importer cannot derive yet"


def test_asl_kept_when_input_supplies_aslcontext(fixture_core, in_dir, key, schema):
    perf = in_dir / "sub-01" / "perf"
    perf.mkdir(parents=True)
    (perf / "sub-01_aslcontext.tsv").write_text("volume_type\ncontrol\nlabel\n")
    assert asl_entry(build_plan(fixture_core, in_dir, key, set(), None, schema, "bids")).exclude is False


def test_input_readme_seeds_plan_readme(fixture_core, in_dir, key, schema):
    name_patient(fixture_core)
    (in_dir / "README").write_text("Study of Smith at Hospital X. Two T1w scans.")
    rec = Recorder(metadata=json.dumps({"name": "Agent name", "readme": "Agent readme"}))
    p = build_plan(fixture_core, in_dir, key, set(), rec, schema, "bids")
    assert p.readme.startswith("Study of [x]") and "Two T1w scans." in p.readme
    assert "smith" not in p.readme.lower() and "Agent readme" not in p.readme
    entry = next(a for a in p.ancillary if a.path == "README")
    assert (entry.action, entry.reason, entry.locked) == ("drop", "used as the dataset README", False)


def test_agent_readme_when_input_has_none(fixture_core, in_dir, key, schema):
    rec = Recorder(metadata=json.dumps({"name": "n", "readme": "Agent readme"}))
    assert build_plan(fixture_core, in_dir, key, set(), rec, schema, "bids").readme == "Agent readme"


# --- reviewer edits are re-derived ------------------------------------------------

from aimport.planner import apply_plan_edits  # noqa: E402


def test_func_to_anat_edit_is_defaced(fixture_core, in_dir, key, schema):
    set_type(fixture_core, BOLD, "func/bold", {"task": "rest"})
    p = build_plan(fixture_core, in_dir, key, set(), None, schema, "bids")
    bold = one(p, BOLD)
    assert (bold.status, bold.deface) == ("ok", False)
    apply_plan_edits(p, [{"id": bold.id, "datatype": "anat", "suffix": "T1w", "entities": {}}], schema)
    bold = one(p, BOLD)
    assert (bold.status, bold.exclude, bold.deface, bold.source) == ("ok", False, True, "person")
    assert bold.brainlife_datatype == "neuro/anat/t1w"


def test_unknown_to_anat_becomes_ok(plan, schema):
    bold = one(plan, BOLD)
    assert (bold.status, bold.exclude) == ("unknown", True)
    apply_plan_edits(plan, [{"id": bold.id, "datatype": "anat", "suffix": "T1w", "entities": {}}], schema)
    bold = one(plan, BOLD)
    assert (bold.status, bold.exclude, bold.deface) == ("ok", False, True)
    assert bold.brainlife_datatype == "neuro/anat/t1w" and bold.reason.startswith("edited by the reviewer")


def test_edit_to_unnameable_becomes_unknown(plan, schema):
    t1 = one(plan, T1W)
    apply_plan_edits(plan, [{"id": t1.id, "datatype": "func", "suffix": "bold", "entities": {}}], schema)
    t1 = one(plan, T1W)
    assert (t1.status, t1.exclude, t1.brainlife_datatype) == ("unknown", True, None) and "task" in t1.reason
    apply_plan_edits(plan, [{"id": t1.id, "suffix": "nonsense"}], schema)
    assert one(plan, T1W).status == "unknown"


def test_edit_keeps_explicit_exclude(plan, schema):
    bold = one(plan, BOLD)
    apply_plan_edits(plan, [{"id": bold.id, "datatype": "anat", "suffix": "T1w", "entities": {},
                             "exclude": True}], schema)
    assert (one(plan, BOLD).status, one(plan, BOLD).exclude) == ("ok", True)


def test_edit_status_rejected(plan, schema):
    bold = one(plan, BOLD)
    with pytest.raises(ValueError, match="cannot edit status"):
        apply_plan_edits(plan, [{"id": bold.id, "status": "ok", "exclude": False}], schema)
    assert one(plan, BOLD).status == "unknown"


def test_datatypes_target_edit_without_brainlife_type_excluded(fixture_core, in_dir, key, schema):
    p = build_plan(fixture_core, in_dir, key, set(), None, schema, "datatypes")
    bold = one(p, BOLD)
    apply_plan_edits(p, [{"id": bold.id, "datatype": "anat", "suffix": "T1w", "entities": {}}], schema)
    assert one(p, BOLD).exclude is False
    apply_plan_edits(p, [{"id": bold.id, "suffix": "PDT2"}], schema)
    assert one(p, BOLD).exclude is True and "no brainlife datatype" in one(p, BOLD).reason



def test_reviewer_brainlife_mapping_survives_later_edits(fixture_core, in_dir, key, schema):
    p = build_plan(fixture_core, in_dir, key, set(), None, schema, "datatypes")
    t1 = one(p, T1W)
    apply_plan_edits(p, [{"id": t1.id, "brainlife_datatype": "neuro/anat/t2w", "brainlife_tags": ["mine"]}], schema)
    apply_plan_edits(p, [{"id": t1.id, "exclude": False}], schema)
    apply_plan_edits(p, [{"id": t1.id, "subject": "renamed"}], schema)
    t1 = one(p, T1W)
    assert (t1.brainlife_datatype, t1.brainlife_tags, t1.brainlife_by_person) == ("neuro/anat/t2w", ["mine"], True)
    apply_plan_edits(p, [{"id": t1.id, "entities": {}}], schema)  # a naming edit: derived again
    t1 = one(p, T1W)
    assert (t1.brainlife_datatype, t1.brainlife_by_person) == ("neuro/anat/t1w", False)


def test_reviewer_fmap_tags_survive_later_edits(fixture_core, in_dir, key, schema):
    p = build_plan(fixture_core, in_dir, key, set(), None, schema, "datatypes")
    mag = next(e for e in p.entries if e.datatype == "fmap" and e.suffix.startswith("magnitude"))
    apply_plan_edits(p, [{"id": mag.id, "brainlife_tags": ["custom"]}], schema)
    apply_plan_edits(p, [{"id": mag.id, "exclude": False}], schema)
    assert next(e for e in p.entries if e.id == mag.id).brainlife_tags == ["custom"]


def test_brainlife_by_person_is_read_only(plan, schema):
    with pytest.raises(ValueError, match="cannot edit brainlife_by_person"):
        apply_plan_edits(plan, [{"id": plan.entries[0].id, "brainlife_by_person": True}], schema)


# --- placeholder identities ---------------------------------------------------

from aimport.planner import is_placeholder  # noqa: E402

PLACEHOLDER_FORMS = ["", "  ", "anon", "ANONYMOUS", "Anonymous^Anonymous", "anonymized", "Anonymised", "DEIDENTIFIED",
                     "redacted", "REMOVED", "Subject", "PATIENT", "test^test", "Phantom", "unknown", "NONE", "null",
                     "N/A", "n.a.", "NA", "xxxx", "XXXXXX", "000000", "0", "---", "a^a", "1^1", "Z", "anon_anon",
                     "Test Subject", "Anonymized=Patient", "x/x"]


@pytest.mark.parametrize("value", PLACEHOLDER_FORMS)
def test_placeholder_forms(value):
    assert is_placeholder("PatientID", value) and is_placeholder("PatientName", value)


@pytest.mark.parametrize("value", ["MRN0042", "Smith^John", "subject 12", "anon_01", "Xu^Li", "P1", "00042"])
def test_real_identifiers_are_not_placeholders(value):
    assert not is_placeholder("PatientID", value)


@pytest.mark.parametrize("value,absent", [("00000000", True), ("19000101", True), ("18991230", True),
                                          ("18500101", True), ("anon", True), ("", True), ("19700101", False),
                                          ("1970-01-01", False)])
def test_birth_date_placeholders(value, absent):
    assert is_placeholder("PatientBirthDate", value) is absent


@pytest.mark.parametrize("value", PLACEHOLDER_FORMS)
def test_placeholder_identity_never_links_imports(schema, in_dir, key, value):
    info = {"PatientID": value, "PatientName": value, "PatientBirthDate": "19800202"}
    first = build_plan(mini_core([info]), in_dir, key, set(), None, schema, "bids")
    second = build_plan(mini_core([info]), in_dir, key, set(), None, schema, "bids")
    assert subjects_of(first) != subjects_of(second)
    assert all(k.startswith("run:") for k in key.subjects)


def test_birth_date_alone_is_run_local(schema, in_dir, key):
    info = {"PatientID": "anon", "PatientName": "", "PatientBirthDate": "19800202"}
    first = build_plan(mini_core([info]), in_dir, key, set(), None, schema, "bids")
    second = build_plan(mini_core([info]), in_dir, key, set(), None, schema, "bids")
    assert subjects_of(first) != subjects_of(second)
    assert any("identity could not be established for 1 subject(s)" in w for w in first.warnings)


def test_shared_values_warning_differs_from_missing_identity(schema, in_dir, key):
    info = {"PatientID": "P1", "PatientName": "Doe^Jane"}
    p = build_plan(mini_core([info, info, ANON]), in_dir, key, set(), None, schema, "bids")
    assert any(w.startswith("2 subjects share identical identifying values") and "separate IDs" in w
               for w in p.warnings)
    assert any("could not be established for 1 subject(s)" in w for w in p.warnings)


def test_dicom_datetime_without_t_gives_date_terms(schema, in_dir, key):
    core = mini_core([{"PatientID": "P1"}], description="T1 20230115 run")
    core.objects[0].sidecar["AcquisitionDateTime"] = "20230115093000.000000"
    assert build_plan(core, in_dir, key, set(), None, schema, "bids").entries[0].description == "T1 [x] run"


# --- re-import: session labels per study ---------------------------------------

def study_core(uid="", acq_date="2023-01-10", pid="P1"):
    series = [CoreSeries(0, "anat/T1w", {}, "", "T1", {}, Path("x.nii.gz"))]
    sidecar = {"StudyInstanceUID": uid} if uid else {}
    objects = [CoreObject(0, 0, 0, acq_date, "", {}, [], sidecar)]
    subjects = [CoreSubject(0, "", [{"PatientID": pid}], [{"session": "", "AcquisitionDate": acq_date}])]
    return CoreResult(series, objects, subjects)


def reimport(tmp_path, schema, in_dir, *cores, existing_sessions=None):
    labels = []
    for core in cores:
        with PseudonymKey.load(tmp_path / "keys2", "proj") as k:
            p = build_plan(core, in_dir, k, set(), None, schema, "bids", existing_sessions=existing_sessions)
            labels.append((p.entries[0].subject, p.entries[0].session))
    return labels


def test_new_study_gets_next_session(tmp_path, schema, in_dir):
    assert reimport(tmp_path, schema, in_dir, study_core("1.2.3"), study_core("1.2.4", "2023-03-01")) \
        == [("01", "1"), ("01", "2")]


def test_same_study_reimported_keeps_its_session(tmp_path, schema, in_dir):
    assert reimport(tmp_path, schema, in_dir, study_core("1.2.3"), study_core("1.2.4"), study_core("1.2.3")) \
        == [("01", "1"), ("01", "2"), ("01", "1")]


def test_session_by_date_without_study_uid(tmp_path, schema, in_dir):
    cores = study_core(acq_date="2023-01-10"), study_core(acq_date="2023-02-10"), study_core(acq_date="2023-01-10")
    assert [s for _, s in reimport(tmp_path, schema, in_dir, *cores)] == ["1", "2", "1"]
    with PseudonymKey.load(tmp_path / "keys2", "proj") as k:
        assert not any("2023" in s for s in k.sessions["01"])  # stored shifted


def test_placeholder_study_uid_falls_back_to_date(tmp_path, schema, in_dir):
    cores = study_core("anon", "2023-01-10"), study_core("anon", "2023-02-10")
    assert [s for _, s in reimport(tmp_path, schema, in_dir, *cores)] == ["1", "2"]


def test_existing_sessions_are_skipped(tmp_path, schema, in_dir):
    labels = reimport(tmp_path, schema, in_dir, study_core("1.2.3"), existing_sessions={"01": ["1", "2"]})
    assert labels == [("01", "3")]


def test_input_session_label_kept_unless_taken(tmp_path, schema, in_dir):
    a, b = study_core("1.2.3"), study_core("1.2.4")
    a.subjects[0].sessions[0]["session"] = b.subjects[0].sessions[0]["session"] = "pre"
    assert [s for _, s in reimport(tmp_path, schema, in_dir, a, b)] == ["pre", "1"]


def test_subject_rename_leaves_unknown_siblings_alone(plan, schema):
    bold, t1 = one(plan, BOLD), one(plan, T1W)
    reason = bold.reason
    apply_plan_edits(plan, [{"id": t1.id, "subject": "ctl01"}], schema)
    bold = one(plan, BOLD)
    assert (bold.subject, bold.status, bold.reason) == ("ctl01", "unknown", reason)
    assert one(plan, T1W).status == "ok"
