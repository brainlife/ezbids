# Test and validation datasets

Every dataset the aimport engine is tested or validated against, pinned so a
result can be reproduced later. Add a row whenever a dataset is added, replaced
or dropped, and say why.

## Imaging data

| Dataset | Pinned commit | Status | Used by |
|---|---|---|---|
| [neurolabusc/dcm_qa_xa30](https://github.com/neurolabusc/dcm_qa_xa30) | `371ab3071aa9270d23b99fca5f83fe0c35932182` | **current** | `tests/fixtures/fetch_dcm_qa.py`, the committed `tests/fixtures/ezbids_core_siemens.json`, all `docker` tests, the `bl aimport` manual run (cli `test/aimport-manual.js`) |
| [neurolabusc/dcm_qa](https://github.com/neurolabusc/dcm_qa) | `8215e3e` | dropped 2026-11-24 | first version of the fixture (Tasks 2–3) |

### dcm_qa_xa30 (current)

Public Siemens XA30 DICOMs from the dcm2niix test suite, about 44 MB (95 `.dcm`
files in 23 series folders, plus one non-DICOM file, `In/XA_validation.pdf`,
covered by `NON_DICOM_SUFFIXES`). ezBIDS first guess on the unplanted data (20
series; the committed fixture is 137 KB and was made before the two core fixes noted
below, so it has 19 series, series 7 `exclude` and both magnitudes in one `magnitude1` series):

| Series folder | ezBIDS guess | Note |
|---|---|---|
| `5_anat-T1w_acq-tfl`, `6_anat-T1w_acq-tfl` | `anat/T1w` | one series, two runs |
| `7_func-bold_task-fa_run-1` | `func/bold` | dcm2niix guesses `dwi/_FA` because of "task-fa"; ezBIDS core ignores that guess for a non-derived image and finds `func/bold` from "bold" in the description (it excluded the series before, and the committed fixture still records `exclude`) |
| `8_gre_field_mapping` | `fmap/magnitude1` (`_e1`), `fmap/magnitude2` (`_e2`) | two series: ezBIDS core groups series by EchoTime in 0.1 ms (TE 10 and 12.46 ms); before, both echoes were one `magnitude1` series written as `run-1`/`run-2` |
| `9_gre_field_mapping` | `fmap/phasediff` | |
| `10_DWI_dir80_PA`, `17_DWI_dir80_AP` | `dwi/dwi` | 21 volumes each, with bvec/bval |
| `11`-`16_DWI_dir80_PA`, `19`-`24_DWI_dir80_AP` | `exclude` | Siemens derived maps (ADC, TRACEW, FA, tensor/B0); two FA maps have an improper data array. `15` and `23` produce no NIfTI at all |
| `25_asl_2d_tra` | `perf/asl` | 7 volumes |
| `27_asl_2d_tra`, `28_asl_2d_tra` | `exclude` | derived ASL (subtraction, rCBF) |
| `99_Phoenix_Document` | not a series | 7 DICOM files that dcm2niix does not convert; ezBIDS never sees them |

No PET data yet; a public PET DICOM set is still needed for the pet datatype.

### dcm_qa (dropped)

Public Siemens DICOMs, 50 series. ezBIDS mapped them to func/bold, dwi/dwi and
fmap/epi only. Dropped because it has **no T1w**, which the planner, writer and
defacing tests need. Its `In/` folder also contains a stray `.nii` file.

## Ancillary and metadata files

| Dataset | Pinned commit | Status | Used by |
|---|---|---|---|
| `tests/fixtures/ancillary/` (synthetic, written for this repo) | committed with Task 10b | **current** | `tests/test_ancillary.py` |

### ancillary (current)

A synthetic BIDS top level with no imaging data and no real person in it, added (Task 10b)
so every ancillary file type and every column type has a planted identifier to find. The
tests pair it with small generated NIfTIs for `sub-01` (two scans) and `sub-MRN0042` (one
scan); `sub-99` appears only in the tables, as a person not in the import.

| File | What it holds | Planted |
|---|---|---|
| `dataset_description.json` | Name, Authors, Funding, EthicsApprovals, Acknowledgements, a stray `PatientName` | `Hospital X`, `John Smith`, `MRN0042`, `19700101`, `Smith^John` |
| `README`, `CHANGES`, `LICENSE`, `CITATION.cff` | free text, a CFF author | `John Smith`, `MRN0042`, `19700101`, `1970-01-01`, `Hospital X` |
| `genetic_info.json` | nested Database descriptors | `Hospital X`, `MRN0042` |
| `participants.tsv` / `.json` | `participant_id` (`sub-01`, `sub-MRN0042`, `sub-99`), age (one over 89), sex, name, dob (ISO and compact), visit_date (ISO and compact), site, handedness, notes, email, hospital_id | in every identifying column, in `site` and in the descriptions |
| `samples.tsv` | sample_id, participant_id, collected_by | `Smith` |
| `phenotype/moca.tsv` / `.json` | score, assessment_date (date and datetime), rater, examiner_initials, comments, MeasurementToolMetadata | `Smith`, `John`, `Hospital X` |
| `sub-01/sub-01_sessions.tsv` / `.json`, `sub-MRN0042/sub-MRN0042_sessions.tsv` | session_id (`ses-2` not imported), acq_time, operator | `Smith`, `John`, `Hospital X`; the folder name `sub-MRN0042` |
| `sub-01/ses-1/sub-01_ses-1_scans.tsv` | filename, acq_time, quality, comment | `Smith` |
| `sub-01/ses-1/sub-01_ses-1_task-rest_bold.json`, `task-rest_bold.json`, `task-rest_events.json` | inherited sidecars | `Smith`, `John Smith`, `Hospital X` (also as `InstitutionName`) |
| `sub-01/ses-1/func/sub-01_ses-1_task-rest_events.tsv` / `.json` | per-run events for the imported BOLD run (a free-text `response_note` column) | `John`, `Smith` |
| `sub-01/ses-1/func/sub-01_ses-1_task-rest_recording-cardiac_physio.tsv.gz` / `.json` | headerless physio for the same run | `19700101` in one cell, `Hospital X` |
| `sub-01/ses-1/func/sub-01_ses-1_task-nback_events.tsv` | events with no imported image (dropped, never written) | none |
| `task-smith_bold.json` | a sidecar whose name holds an identifier (never listed or written) | `smith` |
| `notes.json` | not a BIDS file (ignored) | `John Smith` |
| `proj.aimport-key.json` | a stray pseudonym key (never written) | `Smith^John` |
| `code/convert.py` | a script (kept only on opt-in, redacted) | `John Smith`, `MRN0042` |
| `sourcedata/sub-01/info.txt` | raw data notes (never written) | all planted values |
| `derivatives/fmriprep/dataset_description.json` | a derivative (never written in phase 1) | `Smith` |

Some tests (review round 1) change a copy of it at run time instead of adding files:
`phenotype/iq.tsv` keyed by `subject` (no `participant_id`), symbolic links in `code/` to a key
file and into `sourcedata/`, a `CHANGES` link, ragged, free-text and many-date-format
`participants.tsv` variants, a binary file in `code/` and `stimuli/`, and the whole fixture
nested two folders below the input (`study/bids/`).

## Planted identifiers

`fetch_dcm_qa(dest, plant=True)` rewrites every DICOM so the leak tests have
something to find. These values must never appear in an LLM request, the plan,
an API response (except `/preview` image bytes) or any output file.

| Field | Planted value |
|---|---|
| PatientName | `Smith^John` |
| PatientID | `MRN0042` |
| PatientBirthDate | `19700101` |
| InstitutionName | `Hospital X` |
| SeriesDescription | prefixed with `Smith_John ` |
| Folder | series moved under `Smith_John_19700101/` |

Only standard DICOM tags are planted. Siemens private (CSA) headers are left as
they are.

### Native identifiers in dcm_qa_xa30

The published data is not anonymous. Its own identifiers are listed as
`NATIVE_IDENTIFIERS` in `tests/fixtures/fetch_dcm_qa.py` and must never reach the
LLM, the plan, an API response or any output file either (later leak tests check
them together with the planted values):

| Field | Native value |
|---|---|
| PatientID | `12343@hucheng` (contains `hucheng`) |
| PatientName | `XAtest_sub-July11` |
| PatientBirthDate | `19910101` / `1991-01-01` |
| InstitutionName | `Indiana University Psychology Department` |
| StationName | `MRC35062` |
| DeviceSerialNumber | `67093` |
| StudyDescription, ProcedureStepDescription | `Cheng test` |

Acquisition dates are 2022-07-11 (also in the dcm2niix `time-2022...` file names).

## The committed fixture

Committed fixtures carry no identifiers, upstream-public or not.
`tests/fixtures/make_ezbids_core_fixture.py <raw ezBIDS_core.json> <out>` turns the
raw ezBIDS output of unplanted xa30 into `tests/fixtures/ezbids_core_siemens.json`:
patient fields (including `PatientSize`, set to 0) become `anon` / `n/a`, institution, station, serial, UIDs and the
sequence build stamp are dropped, dates move to 2000-01-01 (times kept), bulky NIfTI
`headers` are stripped, paths stay relative. The script refuses to write if any
native or planted term is still present, and the host test
`test_fixture_has_no_identifiers` re-checks the committed file.

To regenerate: run `run_ezbids(stage_input(fetch_dcm_qa(d, plant=False), w))` in the
image, then the script on `w/ezbids/ezBIDS_core.json`.

## Leak-test vocabularies

`tests/conftest.py` exports `PLANTED` (the planted values, lowercase), `NATIVE` (lowercased
`NATIVE_IDENTIFIERS`) and `tokens(text)`, which returns the members of `PLANTED | NATIVE`
found in the lowercased text by substring (so phrases like `hospital x` and values like
`12343@hucheng` are caught). Leak tests assert `not PLANTED & tokens(text)` and
`not NATIVE & tokens(text)`.

## Specifications and validators

| Item | Version | Where |
|---|---|---|
| BIDS specification (aimport target) | v1.11.2, `fbe1af9aa1fa1bb32811d0e5f4be4bee3130bc3b` | submodule `aimport/bids-specification`, exported to `/opt/bids-schema/schema.json` in the image |
| BIDS specification (ezBIDS core's own) | `3537e9edbc81545614d3ee605c398361099b6977` | submodule `bids-specification`; the image build checks its digest |
| BIDS validator (aimport) | `@bids/validator` 2.4.1 on Deno 2.5.6, run with `--schema file:///opt/bids-schema/schema.json` | `bids-validator-2` in the image |
| BIDS validator (ezBIDS preprocess only) | `bids-validator` 1.14.8 (npm) | handler image |

## How the tests are run

- Host unit tests: `cd aimport && uv run pytest -m "not docker and not docker_offline"`
- In the image: `docker run --rm --platform linux/amd64 -v $PWD/aimport:/src brainlife/aimport:dev pytest -m docker /src/tests`
- Offline: the same with `--network none -m docker_offline`, plus a cache mount holding the xa30 tarball, because
  the fetch cannot download: `-v <cache dir>:/tmp/aimport-dcm-qa-cache` (the tarball is
  `dcm_qa_xa30-371ab3071aa9270d23b99fca5f83fe0c35932182.tar.gz`, created by any earlier online run).
  The same mount avoids re-downloading in the online run.

### Manual runs of `bl aimport`

dcm_qa_xa30 (planted, `plant=True`) is also the input of the `bl aimport` manual run (cli repo,
`test/aimport-manual.js`: real engine container, no upload, no AI model so heuristics only, quickshear defacing).
2026-11-24: final stage `validated`, 0 validator errors (55 warnings), 5 objects and 6 project files ready to
upload, about 110 s under emulation on Apple silicon; the console output contained none of the planted
identifiers. The run used a thin derived image because `python` in `brainlife/aimport:dev` is the system Python 2.7 and `PYTHONPATH=/src/src` is set, so `python -m aimport serve` fails without a source mount.

### QA viewer check (Task 5 of the QA viewer plan)

2026-11-24, image `brainlife/aimport:qa` built from this branch, real engine container (`-p 127.0.0.1:8766:8766`,
folders under `~/.cache/aimport-qa/`), planted dcm_qa_xa30, no AI model (heuristics only): scan → approve
(`quickshear`) → execute gave `validated`, 0 validator errors (55 warnings), 5 written entries (T1w with two
runs, magnitude1/2, phasediff, two dwi). Then `POST /viewer/session` and the URL in headless Chromium
(Playwright on the host): `/viewer/` listed the 5 entries by BIDS path, with none of the planted or native
identifiers in its HTML; the T1w opened in Neuroglancer with the defaced image rendered, and switching on the
hidden original layer showed the face; the "defaced vs original" view rendered both. Every request went to
`127.0.0.1:8766`; the console had no errors (only WebGL performance warnings). The committed screenshots
(`docs/qa-viewer-index.png`, `docs/qa-viewer-t1w.png`) show the defaced output only. CSP relaxation needed by
the client: `'unsafe-eval'` in `script-src` (found earlier against the same build).

