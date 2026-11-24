# Test and validation datasets

Every dataset the aimport engine is tested or validated against, pinned so a
result can be reproduced later. Add a row whenever a dataset is added, replaced
or dropped, and say why.

## Imaging data

| Dataset | Pinned commit | Status | Used by |
|---|---|---|---|
| [neurolabusc/dcm_qa_xa30](https://github.com/neurolabusc/dcm_qa_xa30) | `371ab3071aa9270d23b99fca5f83fe0c35932182` | **current** | `tests/fixtures/fetch_dcm_qa.py`, the committed `tests/fixtures/ezbids_core_siemens.json`, all `docker` tests, the `bl aimport` manual run (cli `test/aimport-manual.js`) |
| [neurolabusc/dcm_qa](https://github.com/neurolabusc/dcm_qa) | `8215e3e` | dropped 2026-11-24 | first version of the fixture (Tasks 2–3) |
| Synthetic OME-Zarr (`tests/fixtures/micr_fixtures.py` `ome_zarr`, written for this repo; no real pixels) | generated at test time, seed 0 | **current** | `tests/test_micr_validator.py` (microscopy Task 1: validator ruling) |
| Synthetic sparse BigTIFF (`tests/fixtures/micr_fixtures.py` `sparse_bigtiff`, written for this repo; no pixels) | generated at test time | **current** | `tests/test_modality.py` (microscopy Task 2: claimed input is never staged or copied) |

### Synthetic OME-Zarr (current)

`ome_zarr(dest, version)` writes a 2-level `c,z,y,x` uint16 store, default shape `(2, 8, 64, 64)`,
pixel size 1.0 × 0.5 × 0.5 µm (z, y, x), random values from seed 0. NGFF `"0.5"` is Zarr v3 with one
shard per channel; `"0.4"` is Zarr v2. `strip_chunks` deletes every chunk and shard file, leaving only
Zarr metadata: what a reference dataset looks like locally.

### Synthetic sparse BigTIFF (current)

`sparse_bigtiff(size, dest)` writes a valid single-plane uint16 BigTIFF (rows of 32768 samples) whose
apparent size is `size` bytes (4 GiB in the tests) through `tifffile.memmap`, without writing any pixel:
the file is sparse and takes a few KiB on disk. Task 2 places it, together with planted folder names
(`H17_250215`) and a DICOM, under a claimed folder to show claimed input is never staged, walked or copied.

### dcm_qa_xa30 (current)

Public Siemens XA30 DICOMs from the dcm2niix test suite, about 44 MB (95 `.dcm`
files in 23 series folders, plus one non-DICOM file, `In/XA_validation.pdf`,
covered by `NON_DICOM_SUFFIXES`). ezBIDS first guess on the unplanted data (19
series; the committed fixture is 137 KB):

| Series folder | ezBIDS guess | Note |
|---|---|---|
| `5_anat-T1w_acq-tfl`, `6_anat-T1w_acq-tfl` | `anat/T1w` | one series, two runs |
| `7_func-bold_task-fa_run-1` | `exclude` | dcm2niix guesses `dwi/_FA` because of "task-fa"; stock ezBIDS crashes on it, so the core patch excludes it. A real BOLD series that the planner must reclassify as `func/bold` |
| `8_gre_field_mapping` | `fmap/magnitude1` | |
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

## Electrophysiology and optical data

| Dataset | Pinned commit | Status | Used by |
|---|---|---|---|
| [mne-tools/mne-testing-data](https://github.com/mne-tools/mne-testing-data) `CTF/testdata_ctf.ds` (licence BSD-3) | `20cc221d737a37a6ee3a9c007e91bd69541fefe9` | **current** | `tests/test_ephys_capability.py` `test_anonymize_forces_conversion[meg-FIF]` (`ephys_data`; Phase 3 Task 1 ruling) |
| [bids-standard/bids-examples](https://github.com/bids-standard/bids-examples); data files are empty: layout and validator only | `5e00d47b6f1db106dda1b776d5243eb41b4cb95b` (2026-10-09) | **current** | `tests/test_ephys_capability.py` `test_validator_ephys_examples` (`docker`) |
| Synthetic EDF / SNIRF (`tests/test_ephys_capability.py` `_edf_source`, `_write_snirf`; written for this repo, random signals, seed 0) | generated at test time | **current** | `tests/test_ephys_capability.py` (Phase 3 Task 1 ruling) |

### mne-testing-data CTF (current)

Fetched file by file from `raw.githubusercontent.com` into `AIMPORT_EPHYS_CACHE` (default
`/tmp/aimport-ephys-cache`) under `mne-testing-data-<commit>/CTF/testdata_ctf.ds/`, about 20 MB in all; each
file is checked against its SHA-256 (the two empty files `BadChannels` and `bad.segments` are not fetched).

| File | Bytes | SHA-256 |
|---|---|---|
| `ClassFile.cls` | 186 | `bd91e66437d53bfbb4cd03ce9394714b4ec4fd715bddfca3c4fabe965476378b` |
| `params.dsc` | 467 | `2b4dee7383882a1fc6f1d84d5ba4c3181c461f5d6aaf5af204cc534289e5fc92` |
| `processing.cfg` | 1185 | `c668cb17fbe4cfec9a29c3ec85ecaf7e61278df863fbe1a9ea8e77960db4baf4` |
| `testdata_ctf.acq` | 40798 | `e0837500432d5f8c5ff940a53778469c1a3bf83852355fa922f256c5adc08623` |
| `testdata_ctf.hc` | 824 | `37ee610fdcff3689b95c0e461fe7c18d5582109120bb39e6e12d651931eb515c` |
| `testdata_ctf.infods` | 2620 | `72d71ee90fea7a49b056a228101a9b84f91600585a000484061fbd7ea9f5c3b3` |
| `testdata_ctf.meg4` | 17088008 | `30ef47c85083ff3892d5565e487287f71146646a4bff6c283638939801c7f788` |
| `testdata_ctf.newds` | 350 | `5d2ace836414f294685574d3720f36ecd529b4b18668c8d54c9986e98b9e3cf9` |
| `testdata_ctf.res4` | 3260865 | `a75ccb0a74910d1f09f1e35944ced09591f3048a850718bcda95a83e16e27146` |

### bids-examples (current)

Shallow fetch of the pinned commit into `AIMPORT_BIDS_EXAMPLES_CACHE` (default
`/tmp/aimport-bids-examples-cache`) under `<commit>/`; the host copy lives in
`~/.cache/aimport-bids-examples/<commit>` and is mounted there. Sets used: `eeg_cbm`, `eeg_rest_fmri`,
`ieeg_epilepsy`, `ieeg_visual`, `ds000247` (MEG), `fnirs_tapping`, `fnirs_automaticity`,
`emg_ConcurrentIndependentUnits`, `emg_CustomBipolar`, `emg_CustomBipolarFace`, `emg_IndependentMod`,
`emg_MultiBodyParts`, `emg_Multimodal`, `emg_TwoHDsEMG`, `emg_TwoWristbands`. Validated with the repo's own
`default-config.json` (ignores `EMPTY_FILE`) and `--ignoreNiftiHeaders`, as its `run_tests.sh` does.

### Synthetic EDF and SNIRF (current)

`_edf_source` writes a 4-channel, 4 s, 256 Hz `RawArray` (eeg, seeg or emg) to `Smith_John_<type>.edf` with
`mne.export.export_raw`, after planting `subject_info` (`his_id` `MRN0042`, John Smith, birthday 1970-01-01)
and meas_date 2025-02-15 09:30 UTC. `_write_snirf` writes a CW SNIRF with h5py (2 sources, 2 detectors,
760/850 nm, 200 samples at 10 Hz) with `SubjectID` `Smith_John`, `MeasurementDate` 2025-02-15 and
`stim1/name` `Jane Doe tapping`.

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

- Host unit tests: `cd aimport && uv run pytest -m "not docker and not docker_offline"` (includes the
  `ephys_data` tests, which fetch the pinned mne-testing-data files once into `AIMPORT_EPHYS_CACHE`)
- In the image: `docker run --rm --platform linux/amd64 -v $PWD/aimport:/src brainlife/aimport:dev pytest -m docker /src/tests`
  (ephys: add `-v ~/.cache/aimport-bids-examples:/tmp/aimport-bids-examples-cache -v ~/.cache/aimport-ephys:/tmp/aimport-ephys-cache`
  so the bids-examples clone and the mne-testing-data files are reused)
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
