import json
import shutil
import sys
from dataclasses import asdict
from pathlib import Path

import pytest

from aimport.ezbids_runner import CoreObject, CoreResult, CoreSeries, CoreSubject, parse_core, run_ezbids, stage_input
from aimport.scrub import (
    SCRUB_ALLOWLIST,
    SIDECAR_DROP,
    identifying_terms,
    is_secondary_capture,
    redact,
    scrub_sidecar,
    scrubbed_view,
)
from conftest import NATIVE, PLANTED, tokens

FIXTURES = Path(__file__).parent / "fixtures"
sys.path.insert(0, str(FIXTURES))
from fetch_dcm_qa import fetch_dcm_qa  # noqa: E402

CACHE = Path("/tmp/aimport-dcm-qa-cache")  # docker runs mount the tarball cache here


def fake_core(sidecar=None, description="Smith T1", series_type="anat/T1w", nifti=Path("missing.nii.gz")):
    sidecar = sidecar or {}
    series = CoreSeries(0, series_type, {}, "", description, sidecar, nifti)
    return CoreResult(series=[series], objects=[], subjects=[])


def synthetic(sidecar):
    return CoreSeries(0, "exclude", {}, "", "x", sidecar, Path("x.nii.gz"))


@pytest.fixture(scope="module")
def core_planted(tmp_path_factory):
    base = tmp_path_factory.mktemp("planted")
    src = fetch_dcm_qa(base / "in", cache=CACHE)
    staged = stage_input(src, base / "work")
    core = parse_core(run_ezbids(staged, log=lambda line: None))
    return type("Planted", (), {"core": core, "input": src, "staged": staged})


def test_redact_folder_name():
    assert redact("Smith_John_19700101/T1 MPRAGE", {"Smith", "John", "19700101"}) == "[x]_[x]_[x]/T1 MPRAGE"


def test_redact_longest_first_and_case_insensitive():
    assert redact("at HOSPITAL X now", {"Hospital", "hospital x"}) == "at [x] now"
    assert redact("nothing", set()) == "nothing"


def test_scrubbed_view_has_only_allowlisted_fields():
    view = scrubbed_view(fake_core(sidecar={"PatientName": "Smith^John", "EchoTime": 0.003}), {"Smith"})
    assert set(view[0].fields) <= SCRUB_ALLOWLIST
    assert "smith" not in json.dumps(asdict(view[0])).lower()
    assert view[0].fields["EchoTime"] == 0.003
    assert view[0].description == "[x] T1"


def test_scrubbed_view_redacts_free_text_and_hides_image_comments():
    sidecar = {"SequenceName": "Smith_seq", "ImageType": ["ORIGINAL", "Smith"], "ImageComments": "Smith note",
               "ProtocolName": "Smith protocol", "StationName": "MRC1"}
    view = scrubbed_view(fake_core(sidecar=sidecar), {"Smith"})[0]
    assert view.fields["ImageComments_present"] is True
    assert "ImageComments" not in view.fields and "StationName" not in view.fields
    assert view.protocol == "[x] protocol"
    assert "smith" not in json.dumps(asdict(view)).lower()


def test_scrubbed_view_reads_nifti_shape(tmp_path):
    import nibabel as nib
    import numpy as np

    img = nib.Nifti1Image(np.zeros((4, 5, 6, 7), dtype="int16"), np.diag([2.0, 2.0, 3.0, 1.0]))
    img.header.set_xyzt_units("mm", "sec")
    img.header["descrip"] = b"Smith"
    nib.save(img, tmp_path / "a.nii.gz")
    view = scrubbed_view(fake_core(nifti=Path("a.nii.gz")), {"Smith"}, root=tmp_path)[0]
    assert view.fields["NumberOfVolumes"] == 7
    assert view.fields["Dimensions"] == [4, 5, 6, 7]
    assert view.fields["VoxelSize"] == [2.0, 2.0, 3.0]
    assert view.fields["Units"] == "mm"
    assert "smith" not in json.dumps(asdict(view)).lower()


def test_scrub_sidecar_drops_and_redacts():
    out = scrub_sidecar({"InstitutionName": "Hospital X", "SeriesDescription": "Smith T1",
                         "nested": {"note": "MRN0042"}}, {"Smith", "MRN0042"})
    assert "InstitutionName" not in out
    assert out["SeriesDescription"] == "[x] T1"
    assert out["nested"]["note"] == "[x]"


def test_scrub_sidecar_lists_and_input_untouched():
    src = {"PatientSize": 1.7, "StationName": "s", "Tags": ["Smith a", {"k": "smith"}], "EchoTime": 0.1}
    out = scrub_sidecar(src, {"Smith"})
    assert out == {"Tags": ["[x] a", {"k": "[x]"}], "EchoTime": 0.1}
    assert src["Tags"][0] == "Smith a"


def test_sidecar_drop_covers_height_and_device():
    assert {"PatientSize", "StationName", "DeviceSerialNumber"} <= SIDECAR_DROP


def test_identifying_terms_from_patient_info_and_sidecar(tmp_path):
    core = CoreResult(
        series=[],
        objects=[CoreObject(0, 0, 0, "", "", {}, [], {"StationName": "MRC35062", "DeviceSerialNumber": 67093})],
        subjects=[CoreSubject(0, "01", [{
            "PatientName": "Smith^John", "PatientID": "12343@hucheng", "PatientBirthDate": "19700101",
            "OtherPatientIDs": ["AB1234", "x"], "OperatorsName": "Doe^Jane", "InstitutionName": "Hospital X",
        }], [])],
    )
    terms = {t.lower() for t in identifying_terms(core, tmp_path)}
    assert {"smith^john", "smith", "john", "12343@hucheng", "hucheng", "19700101", "1970-01-01",
            "ab1234", "doe", "jane", "hospital x", "mrc35062", "67093"} <= terms
    assert not any(len(t) < 2 for t in terms)


def test_identifying_terms_read_dicom_headers(tmp_path):
    import pydicom
    from pydicom.dataset import FileDataset, FileMetaDataset
    from pydicom.uid import ExplicitVRLittleEndian

    sub = tmp_path / "a" / "b"
    sub.mkdir(parents=True)
    (sub / "0.txt").write_text("notes")  # skipped: not a DICOM
    meta = FileMetaDataset()
    meta.TransferSyntaxUID = ExplicitVRLittleEndian
    ds = FileDataset(str(sub / "1.dcm"), {}, file_meta=meta, preamble=b"\0" * 128)
    ds.PatientName, ds.PatientBirthDate, ds.StationName = "Roe^Rita", "19800203", "STN9"
    ds.save_as(str(sub / "1.dcm"))
    assert pydicom.dcmread(str(sub / "1.dcm")).PatientName == "Roe^Rita"
    terms = {t.lower() for t in identifying_terms(CoreResult(), tmp_path)}
    assert {"roe^rita", "roe", "rita", "19800203", "1980-02-03", "stn9"} <= terms


def test_secondary_capture_true_cases():
    assert is_secondary_capture(synthetic({"ImageType": ["DERIVED", "SECONDARY"], "Modality": "OT"}))
    assert is_secondary_capture(synthetic({"ImageType": ["ORIGINAL", "SECONDARY"], "Modality": "SC"}))
    assert is_secondary_capture(synthetic({"SOPClassUID": "1.2.840.10008.5.1.4.1.1.7"}))
    assert is_secondary_capture(synthetic({"SOPClassUID": "1.2.840.10008.5.1.4.1.1.7.2"}))


def test_secondary_capture_false_cases():
    assert not is_secondary_capture(synthetic({"ImageType": ["ORIGINAL", "PRIMARY"], "Modality": "MR"}))
    assert not is_secondary_capture(synthetic({"ImageType": ["DERIVED"], "Modality": "MR"}))  # ADC maps are MR
    assert not is_secondary_capture(synthetic({"ImageType": ["PRIMARY"], "Modality": "OT"}))
    assert not is_secondary_capture(synthetic({"SOPClassUID": "1.2.840.10008.5.1.4.1.1.4"}))
    assert not is_secondary_capture(synthetic({"SOPClassUID": "1.2.840.10008.5.1.4.1.1.77.1.1"}))
    assert not is_secondary_capture(synthetic({}))


def test_tokens_helper_catches_phrases_and_punctuated_values():
    assert PLANTED & tokens("Folder Hospital X/Smith_John") == {"hospital x", "smith", "john"}
    assert NATIVE & tokens("id 12343@HuCheng") >= {"12343@hucheng", "hucheng"}
    assert not tokens("T1 MPRAGE 0.9mm")


def _write_dicom(path, preamble=True, **attrs):
    from pydicom.dataset import FileDataset, FileMetaDataset
    from pydicom.uid import ExplicitVRLittleEndian

    meta = FileMetaDataset()
    meta.TransferSyntaxUID = ExplicitVRLittleEndian
    meta.MediaStorageSOPClassUID = "1.2.840.10008.5.1.4.1.1.4"
    meta.MediaStorageSOPInstanceUID = "1.2.3.4"
    ds = FileDataset(str(path), {}, file_meta=meta, preamble=b"\0" * 128)
    for k, v in attrs.items():
        setattr(ds, k, v)
    ds.save_as(str(path), enforce_file_format=True)
    if not preamble:  # drop the 128-byte preamble and the DICM marker, keep the file meta group
        path.write_bytes(path.read_bytes()[132:])


def test_header_walk_continues_past_files_without_terms(tmp_path):
    _write_dicom(tmp_path / "A0.dcm", Modality="PR")
    _write_dicom(tmp_path / "B1.dcm", PatientName="Roe^Rita")
    stats = {}
    terms = {t.lower() for t in identifying_terms(CoreResult(), tmp_path, stats)}
    assert {"roe", "rita"} <= terms
    assert stats["dicom_files_read"] == 2 and stats["term_count"] == len(terms)


def test_stats_zero_when_nothing_found(tmp_path):
    (tmp_path / "n.txt").write_text("x")
    stats = {}
    assert identifying_terms(CoreResult(), tmp_path, stats) == set()
    assert stats == {"dicom_files_read": 0, "term_count": 0}


def test_header_walk_reads_preamble_less_dicom(tmp_path):
    _write_dicom(tmp_path / "raw.dcm", preamble=False, PatientName="Roe^Rita", SOPClassUID="1.2.840.10008.5.1.4.1.1.4")
    assert (tmp_path / "raw.dcm").read_bytes()[128:132] != b"DICM"
    (tmp_path / "junk.bin").write_bytes(b"hello world, not dicom at all" * 10)
    stats = {}
    terms = {t.lower() for t in identifying_terms(CoreResult(), tmp_path, stats)}
    assert {"roe", "rita"} <= terms
    assert stats["dicom_files_read"] == 1


def _name_terms(name):
    core = CoreResult(subjects=[CoreSubject(0, "01", [{"PatientName": name}], [])])
    return {t.lower() for t in identifying_terms(core, Path("/nonexistent"))}


def test_name_splitting_variants():
    assert {"smith", "john"} <= _name_terms("Smith, John")
    assert {"smith", "jones", "mary", "smith-jones"} <= _name_terms("Smith-Jones^Mary")
    assert {"yamada", "tarou", "山田", "太郎"} <= _name_terms("Yamada^Tarou=山田^太郎")
    full = _name_terms("Yamada^Tarou=山田^太郎")
    assert "yamada^tarou=山田^太郎" in full and "tarou=山田" not in full  # full value kept, no glued part


def test_two_char_name_parts_kept_one_char_dropped_matched_on_boundaries():
    terms = _name_terms("Li^A^Wu")
    assert {"li", "wu"} <= terms and "a" not in terms
    assert redact("Li_Wu T1 Lily Wuhan", {"Li", "Wu"}) == "[x]_[x] T1 Lily Wuhan"
    assert redact("Li", {"Li"}) == "[x]"


def test_redact_unicode_normalization():
    import unicodedata

    nfd = unicodedata.normalize("NFD", "Müller_José/T1")
    assert redact(nfd, {"Müller", "José"}) == "[x]_[x]/T1"
    assert redact("Müller", {unicodedata.normalize("NFD", "Müller")}) == "[x]"
    assert redact("STRAUSS and Strauß", {"Strauß"}) == "[x] and [x]"
    assert redact("Strauss", {"STRAUSS"}) == "[x]"
    assert redact("Zoë Zoe", {"Zoe"}) == "[x] [x]"


def test_birth_date_formats():
    core = CoreResult(subjects=[CoreSubject(0, "01", [{"PatientBirthDate": "19700131"}], [])])
    terms = identifying_terms(core, Path("/nonexistent"))
    assert {"19700131", "1970-01-31", "1970/01/31", "1970.01.31", "31.01.1970", "31/01/1970",
            "01/31/1970"} <= terms


def test_description_fields_harvested():
    core = CoreResult(subjects=[CoreSubject(0, "01", [{
        "StudyDescription": "Cheng test", "InstitutionalDepartmentName": "Psychology Dept",
        "ProcedureStepDescription": "Zebra^Study"}], [])])
    terms = {t.lower() for t in identifying_terms(core, Path("/nonexistent"))}
    assert {"cheng test", "psychology dept", "zebra^study"} <= terms
    assert not terms & {"cheng", "test", "psychology", "dept", "zebra", "study"}  # whole value only


def test_description_terms_do_not_over_redact():
    core = CoreResult(subjects=[CoreSubject(0, "01", [{
        "StudyDescription": "Brain MRI protocol", "ProcedureStepDescription": "Cheng test"}], [])])
    terms = identifying_terms(core, Path("/nonexistent"))
    for text in ("fMRI rest", "T1w MPRAGE brain", "DWI test-retest"):
        assert redact(text, terms) == text
    assert redact("x Brain MRI protocol y", terms) == "x [x] y"


def test_description_only_file_does_not_end_header_walk(tmp_path):
    _write_dicom(tmp_path / "A0.dcm", Modality="PR", StudyDescription="Brain MRI")
    _write_dicom(tmp_path / "B1.dcm", PatientName="Roe^Rita")
    stats = {}
    terms = {t.lower() for t in identifying_terms(CoreResult(), tmp_path, stats)}
    assert {"roe", "rita", "brain mri"} <= terms
    assert stats["dicom_files_read"] == 2


def test_apostrophe_is_a_name_separator():
    terms = _name_terms("O'Brien^Pat")
    assert {"o'brien", "brien", "pat"} <= terms and "o" not in terms


def test_scrub_sidecar_recursive_case_insensitive_drop_and_numbers():
    out = scrub_sidecar({"patientname": "x", "Nested": {"StationName": "s", "PATIENTID": "i", "Keep": 1},
                         "L": [{"institutionname": "h"}], "Serial": 67093, "EchoTime": 0.00241, "ok": True},
                        {"67093"})
    assert out == {"Nested": {"Keep": 1}, "L": [{}], "Serial": "[x]", "EchoTime": 0.00241, "ok": True}


@pytest.mark.docker
def test_terms_found_from_planted_dicoms(core_planted):
    terms = {t.lower() for t in identifying_terms(core_planted.core, core_planted.input)}
    assert {"smith", "john", "mrn0042", "19700101", "hospital x"} <= terms
    assert {"mrc35062", "67093"} <= terms  # native StationName and DeviceSerialNumber


@pytest.mark.docker
def test_scrubbed_view_of_planted_run_has_no_identifier(core_planted):
    terms = identifying_terms(core_planted.core, core_planted.input)
    view = scrubbed_view(core_planted.core, terms, root=core_planted.staged)
    assert view
    # positive control on the fields the view carries: description, ProtocolName, allowlisted fields
    raw = json.dumps([
        [s.series_description, s.sidecar.get("ProtocolName", ""), {k: s.sidecar.get(k) for k in SCRUB_ALLOWLIST}]
        for s in core_planted.core.series
    ])
    assert PLANTED & tokens(raw)  # positive control: the unscrubbed input really contains identifiers
    text = json.dumps([asdict(v) for v in view])
    assert not PLANTED & tokens(text)
    assert not NATIVE & tokens(text)
    assert any("NumberOfVolumes" in v.fields for v in view)


@pytest.mark.docker
def test_scrub_sidecar_of_planted_run_has_no_identifier(core_planted):
    terms = identifying_terms(core_planted.core, core_planted.input)
    raw = json.dumps([s.sidecar for s in core_planted.core.series] + [o.sidecar for o in core_planted.core.objects])
    assert PLANTED & tokens(raw)  # positive control
    assert NATIVE & tokens(raw)
    text = json.dumps([scrub_sidecar(s.sidecar, terms) for s in core_planted.core.series] +
                      [scrub_sidecar(o.sidecar, terms) for o in core_planted.core.objects])
    assert not PLANTED & tokens(text)
    assert not NATIVE & tokens(text)


# --- BIDS vocabulary is never an identifying term ------------------------------------------------

def test_bids_words_come_from_the_schema():
    from aimport.schema import bids_words, entity_keys

    words = bids_words()
    for w in ("sub", "ses", "task", "acq", "ce", "rec", "dir", "run", "mod", "echo", "flip", "inv", "mt", "part",
              "proc", "hemi", "space", "split", "recording", "chunk", "sample", "stain", "desc", "trc", "res", "den",
              "label", "tracer", "nuc", "voi", "anat", "func", "dwi", "fmap", "perf", "pet", "eeg", "meg", "ieeg",
              "nirs", "emg", "micr", "beh", "motion", "mrs", "t1w", "bold", "events", "channels", "photo"):
        assert w in words, w
    assert {"sub", "ses", "task", "run"} <= entity_keys() and "t1w" not in entity_keys()
    assert not {"smith", "xatest", "july11", "hucheng"} & words


def test_without_bids_words_keeps_the_values():
    from aimport.scrub import without_bids_words

    assert without_bids_words({"sub", "SES", "T1w", "anat", "XAtest", "July11"}) == {"XAtest", "July11"}
    assert without_bids_words({"sub-July11"}) == {"July11"}
    assert without_bids_words({"sub-01", "ses-1_run-2", "sub-07_T1w"}) == set()  # short numbers are no terms
    assert without_bids_words({"sub-Li_ses-MRN0042_bold"}) == {"Li", "MRN0042"}
    # not a BIDS name: kept whole (its values stay findable as the whole value)
    assert without_bids_words({"XAtest_sub-July11", "foo-bar", "Smith-Jones"}) == {
        "XAtest_sub-July11", "foo-bar", "Smith-Jones"}


def test_dcm_qa_xa30_patient_name_terms():
    """dcm_qa_xa30's real PatientName: its values are terms, the BIDS key between them is not."""
    terms = _name_terms("XAtest_sub-July11")
    assert {"xatest", "july11", "xatest_sub-july11"} <= terms
    assert not {"sub", "sub-july11"} & terms
    assert redact("sub-01/anat/sub-01_T1w.nii.gz", _name_terms("XAtest_sub-July11")) == "sub-01/anat/sub-01_T1w.nii.gz"
    assert redact("XAtest_sub-July11 T1", _name_terms("XAtest_sub-July11")) == "[x] T1"


@pytest.mark.parametrize("pid", ["sub-01", "sub-07", "ses-1_run-2", "sub-01_ses-1"])
def test_bids_like_patient_id_gives_no_term_that_blocks_bids_names(pid):
    core = CoreResult(subjects=[CoreSubject(0, "01", [{"PatientID": pid, "PatientName": pid}], [])])
    terms = identifying_terms(core, Path("/nonexistent"))
    assert terms == set()
    path = "sub-01/ses-1/func/sub-01_ses-1_task-rest_run-2_bold.nii.gz"
    assert redact(path, terms) == path


def test_redact_never_redacts_a_bare_bids_word():
    assert redact("sub-01_task-rest_bold", {"sub", "task", "bold", "rest"}) == "sub-01_task-[x]_bold"
