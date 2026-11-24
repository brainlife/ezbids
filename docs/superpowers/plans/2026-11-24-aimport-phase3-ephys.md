# aimport Phase 3: electrophysiology and optical (BIDS `eeg`, `meg`, `ieeg`, `nirs`, `emg`) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The engine imports EEG, MEG, iEEG, fNIRS and EMG recordings into BIDS. Inputs are vendor files that MNE-Python reads, SNIRF, NWB iEEG and Blackrock (through neo). The output is de-identified and validated:
- EEG and iEEG are written as BrainVision (EDF on request);
- EMG as EDF or BDF;
- MEG as FIF;
- fNIRS as SNIRF;
- NWB iEEG as NWB.

No source byte is copied. Every output recording is written fresh from a recording that was de-identified in memory, and a final gate re-reads every header and sidecar. A reviewer checks the result in the engine's QA viewer, which shows PNG snapshots and an interactive uPlot trace page.

**Architecture:**
- `aimport/ephys/` is the second modality module. It uses the Phase 2 interface (`aimport/modality.py`: `Claim`, `ModulePlan`, `ModuleOutput`, `Module`, `modules()`), so claimed paths are never staged, walked for DICOM or copied.
- Flow: claim → scan records (local only) → plan entries → de-identify in memory → write. MNE-BIDS `write_raw_bids` writes into a private scratch BIDS root. aimport then cleans the headers, rebuilds the sidecars from an allowlist, and moves only the recording files and their sidecars into the output.
- The QA viewer (`viewer.py`, `server.py` `/viewer/*` and `/qa/*`) gains PNG routes, a trace-window JSON route and the uPlot page.

**Tech Stack:**
- Python 3.11, all pinned and hash-locked in `uv.lock`: mne (BSD-3), mne-bids (BSD-3), edfio (EDF/BDF export), pybv (BrainVision export), defusedxml (EGI `.mff`), h5py (already a Phase 2 dependency), pynwb, matplotlib (Agg), and neo as the optional extra `aimport[neo]`. pytest gets a new marker `ephys_data`.
- Viewer client: uPlot (MIT), pinned in `aimport/viewer-client/package.json` and `package-lock.json`, built into the image. No CDN.

**Spec:** `docs/superpowers/specs/2026-11-24-aimport-phase2-3-design.md`, sections "QA viewer", "Phase 3: electrophysiology and optical", "Tests that matter most" and "Test datasets". It extends `2026-11-23-aimport-design.md`: phases, de-identification rules, the mapping YAML rule, draft datatypes and the DATASETS.md rule all still hold. The original design's "autobidsify covers EEG and fNIRS" is superseded: phase 3 uses MNE and MNE-BIDS directly.

**Depends on:**
- Phase 2 (`2026-11-24-aimport-phase2-micr.md`) merged, specifically these hooks:
  - Task 2: `modality.py`, `stage_input(exclude=)`, claimed-path exclusion;
  - Task 6: `build_plan(modules=)`, `PlanEntry.modality`, `schema.SUPPORTED_DATATYPES` and `CHECK_EXTS`;
  - Task 7: `classify(system=, datatypes=)`;
  - Task 8: `write_bids(modules=)` and the participants and scans merge.
- The QA viewer plan (`2026-11-24-aimport-qa-viewer.md`) merged before Task 11.

## Global Constraints

**No source bytes in the output**
- MNE-BIDS is always called with an explicit `format=` and with `anonymize=` set, so it converts instead of copying.
- The one exception: SNIRF that aimport itself wrote to the scratch folder (Task 10) may be copied by MNE-BIDS.
- The gate (Task 8) refuses any output file whose size and SHA-256 equal a claimed source file.
- Readers open everything with `preload=False`. Planning reads headers and metadata only.
- Conversion loads one recording at a time:
  - above `WARN_LOAD_BYTES = 2 * 2**30` (`n_channels × n_times × 8`), the plan warns `"converting <BIDS name> loads about {N:.1f} GB into memory"`;
  - above `AIMPORT_EPHYS_MAX_LOAD_BYTES` (default `8 * 2**30`), the entry is `unsupported` with that reason.

**Identifying data stays local**
- Original paths, file names, meas dates, header strings, annotation text and channel names that were renamed live only in `work/ephys/`:
  - `claim.json`, `records.json`, `terms.json`;
  - `events.json` (code → original);
  - `channels.json` (new → old);
  - `scratch/` (deleted after each write);
  - `qa/` (PNGs and caches; derived from the output, never uploaded).
- None of it reaches `plan.json`, `scan.json`, `status.json`, an API response, an agent request or `work/output/bids/`.
- Raw annotation, marker or event text is **never** sent to the LLM.

**In-memory de-identification (before any write), `ephys/deid.py`**
- `info["subject_info"]` is replaced by `{"sex": <original code>, "hand": <original code>}`. Age goes to `participants.tsv` from the local birthday only. Cleared: `experimenter`, `description`, `proj_name`, `proj_id`, `device_info`, `helium_info`, `file_id`, `meas_id`, `utc_offset`.
- Then MNE-BIDS anonymize runs with `{"daysback": d, "keep_his": False, "keep_source": False}`:
  - `d = ephys.write.daysback(subject_dates, offset)`, the same for every recording of a subject;
  - it puts the latest recording before `1925-01-01` and keeps intervals between recordings.
- Annotations: every description goes through `events.code(...)`; `extras` are dropped; `ch_names` per annotation are mapped through the channel renames.
- Channels: a name is kept when it matches `CHANNEL_NAME_RE = r"^[A-Za-z0-9 _.\-+/'()]{1,32}$"` and `scrub.redact(name, terms) == name`. Otherwise it is renamed `<type>_<NNN>` (for example `eeg_007`).
- Digitization: points of kind `FIFFV_POINT_EXTRA` (head shape) are dropped unless `entry.keep_headshape`. Cardinal, HPI and EEG electrode points are kept. Head-shape files (`*.pos`, `*.hsp`, BTi `hs_file`) are claimed and never read into the output by default.

**Post-write header pass, `ephys/headers.py`**
- EDF and BDF:
  - patient field → `X X X X`;
  - recording field → `Startdate X X X X`;
  - startdate `01.01.85`, starttime `00.00.00`;
  - TAL annotations are re-checked against the code list.
- BrainVision: `DataFile=` and `MarkerFile=` must equal the BIDS names. The `.vhdr` is rebuilt with only the `[Common Infos]`, `[Binary Infos]`, `[Channel Infos]` and `[Coordinates]` sections plus pybv's channel table comment. `.vmrk` descriptions must be codes or safe labels.
- SNIRF: `/nirs*/metaDataTags` is rebuilt as exactly:
  - `SubjectID=<BIDS label>`, `MeasurementDate="unknown"`, `MeasurementTime="unknown"`;
  - `LengthUnit`, `TimeUnit`, `FrequencyUnit` (from the source);
  - no other tags.
  `/nirs*/stim*/name` holds codes or safe labels.
- FIF: re-read with `mne.io.read_info`. `subject_info` holds only `sex` and `hand`; experimenter, description and proj_name are empty; there is no `FIFFV_POINT_EXTRA` dig unless opted in.

**Dates**
- Original meas_date values live only in `records.json`.
- `scans.tsv` `acq_time` = original meas_date + `key.date_offset_days(subject)`, formatted `%Y-%m-%dT%H:%M:%S`, the same rule as phase 1. The MNE-BIDS `scans.tsv` is discarded.
- MNE-BIDS's date-labelled empty-room sessions are never used: `sub-emptyroom` has no session unless the input has sessions.
- Header dates are the MNE-BIDS anonymized date (before 1925), EDF `01.01.85`, or SNIRF `"unknown"`.

**Events (coded-label scheme, fixed here; the spec left it to the builder)**
- A description is kept verbatim when it is a safe label (`events.SAFE_PATTERNS`, Task 5).
- Otherwise it becomes `E<NNN>`, numbered across the dataset in order of first occurrence (recordings in sorted record order, then onset). Matching is on the casefolded, whitespace-collapsed text.
- `Plan.event_names: dict[str, str]` (code → display name, default the code itself) is the plan's coded label list. The written `trial_type` (`events.tsv`, `.vmrk`, EDF TAL, SNIRF stim name) is `event_names[code]`.

**Sidecars**
- Every sidecar (`*_eeg|meg|ieeg|nirs|emg.json`, `*_coordsystem.json`, `*_events.json`, `*_channels.json`) is rebuilt from `schema_sidecar_fields(schema, datatype, suffix)`, the metadata keys the pinned 1.11.2 schema lists for that suffix. Then `scrub.scrub_sidecar(..., terms)`.
- `InstitutionName`, `InstitutionAddress`, `InstitutionalDepartmentName` and `DeviceSerialNumber` are always dropped.
- `channels.tsv` and `electrodes.tsv` columns are written as MNE-BIDS gives them, with names already renamed. Every cell goes through `scrub.redact`.

**QA**
- Rendered only from the written output (manifest files). Titles carry the BIDS basename, never a source name.
- PNGs are saved with `metadata={"Software": None}`.
- `/qa/traces` limits: ≤ `MAX_CHANNELS = 64` channels, ≤ `MAX_POINTS = 4000` points per channel, window ≤ `MAX_WINDOW_S = 600` s.

**brainlife mapping**
- The 4 eeg rows and 2 meg rows become `active`. aimport writes only `.vhdr/.eeg` (BrainVision), `.edf`, `.bdf` and `.fif`, so `.set` and `.ds` are never produced, but the rows are facts about brainlife.
- ieeg, nirs and emg stay drafts.

**Repo rules**
- Branch `aimport-phase3-ephys` from `origin/master` after Phase 2 is merged; PR against `master`. Never deploy or push images. Tests first. Docs in the same PR.
- Host tests: `cd aimport && uv run pytest -q -m "not docker and not docker_offline and not network and not ephys_data"`. The `ephys_data` tests run on the host too (MNE is pure Python), with a download cache.
- Every dataset used is recorded in `aimport/tests/DATASETS.md` in the same commit. Mapping changes go in `data/bids_brainlife_map.yaml` in the same PR.
- New dependencies need Franco's OK at plan review: mne, mne-bids, edfio, pybv, defusedxml, pynwb, matplotlib, neo (extra), and uplot (npm).

## Review Focus

1. **Annotation free text leaking.** Planted text: an EDF+ TAL `"Smith John said hello"`, a `.vmrk` `Comment/Dr Jane Doe`, EEGLAB event type `"MRN0042 start"`, SNIRF `stim1/name = "Jane Doe tapping"`, and Persyst `[Comments]`. None may reach:
  - the agent payload or `plan.json`;
  - `/plan`, `/status` or `/qa/traces`;
  - `events.tsv`, `.vmrk`, the TAL, a SNIRF stim name or a PNG.
  Each must show up only as `E<NNN>`. Tests in Tasks 5, 7, 9, 10, 11 and 12.
2. **Format headers surviving conversion.**
  - EDF/BDF patient and recording fields: `MRN0042 M 01-JAN-1970 Smith_John`, `Startdate 15-FEB-2025 EEGtech_Jane Hospital_X`.
  - BrainVision `DataFile=Smith_John_rest.eeg`.
  - FIF `experimenter`, `description`, `proj_name`.
  - SNIRF `metaDataTags`.
  - EEGLAB `setname` and `filename`.
  Tests in Tasks 8, 9 and 10.
3. **meas_date and original dates.**
  - `2025-02-15` and every form of it from `scrub._date_forms` plus `headers.edf_date_forms` (`15.02.25`, `15-FEB-2025`, `20250215`);
  - the birthday `1970-01-01`;
  - MNE-BIDS's `ses-YYYYMMDD` for empty-room.
  None may appear in sidecars, `scans.tsv`, `.vmrk` "New Segment", FIF `meas_id`/`file_id`, SNIRF `MeasurementDate` or `participants.tsv`. Tests in Tasks 6, 8, 9 and 12.
4. **Channel names carrying identifiers.** A planted channel `Smith-Fp1` and an EGI event channel `JDOE` must be renamed in the data header, `channels.tsv`, `electrodes.tsv`, annotations `ch_names`, the agent payload (which carries no names at all), the `/qa/traces` JSON and the PNGs. Tests in Tasks 5, 7, 9 and 11.
5. **MEG head-shape digitization.** 200 `FIFFV_POINT_EXTRA` points in a planted FIF, a CTF `.pos` and a KIT `.hsp`:
  - by default none are in the output FIF, there is no `*_headshape.pos`, and `DigitizedHeadPoints` is `false`;
  - with `keep_headshape=True`, all 200 are kept.
  Fiducials and HPI are always kept. Tests in Tasks 9 and 12.

---

## File structure (under `ezbids/aimport/`; new unless marked)

| File | Responsibility |
|---|---|
| `src/aimport/ephys/__init__.py` | constants: `EPHYS_INDEX_BASE = 2_000_000`, `DATATYPES`, `OUTPUT_FORMATS`, load limits, QA limits |
| `src/aimport/ephys/discover.py` | `claim()`: recordings, multi-file groups, companions, empty-room, exclusions |
| `src/aimport/ephys/readers.py` | `open_raw()` (MNE, `preload=False`), neo fallback, allowlisted `RecordingInfo` |
| `src/aimport/ephys/headers.py` | per-format identifying-term harvest, EDF header parser and rewriter, `.vhdr` rebuild, date forms |
| `src/aimport/ephys/events.py` | safe labels, coding, counts |
| `src/aimport/ephys/channels.py` | channel-name rule and renames |
| `src/aimport/ephys/module.py` | `EphysModule`: scan → `records.json`, plan entries, agent view, write dispatch |
| `src/aimport/ephys/deid.py` | the in-memory pass on an `mne.io.Raw` |
| `src/aimport/ephys/write.py` | MNE-BIDS into scratch, sidecar allowlist, move to output, scans and participants |
| `src/aimport/ephys/snirf.py` | h5py SNIRF writer and rewriter |
| `src/aimport/ephys/nwb.py` | pynwb metadata, h5py de-identified NWB copy |
| `src/aimport/ephys/gate.py` | final re-read of every written file |
| `src/aimport/ephys/qa.py` | PNG rendering, trace windows, HbO/HbR cache |
| `src/aimport/static/traces.js`, `traces.css` | the trace page script (no inline script) |
| modified: `plan.py`, `planner.py`, `schema.py`, `agent.py`, `brainlife_map.py`, `ancillary.py`, `server.py`, `viewer.py`, `modality.py`, `data/bids_brainlife_map.yaml`, `viewer-client/{package.json,package-lock.json,build.mjs}`, `Dockerfile` | one hook each |
| `tests/fixtures/ephys_fixtures.py` | planted synthetic recordings, the `mne-testing-data` fetcher, the `bids-examples` fetcher |

---

### Task 1: Dependencies and the capability ruling

**Files:**
- Modify: `aimport/pyproject.toml`, `aimport/uv.lock`, `aimport/README.md` (versions).
- Create: `aimport/src/aimport/ephys/__init__.py`, `aimport/tests/test_ephys_capability.py`.

**Interfaces:**
- `ephys.OUTPUT_FORMATS: dict[str, tuple[str, ...]]`. The first value is the default:

  | Datatype | Formats |
  |---|---|
  | `eeg` | `BrainVision`, `EDF`, `BDF` |
  | `ieeg` | `BrainVision`, `EDF`, `NWB` (NWB only for NWB input) |
  | `emg` | `EDF`, `BDF` |
  | `meg` | `FIF` |
  | `nirs` | `SNIRF` |

  Adjusted by this task's ruling.
- `ephys.MNE_READERS: dict[str, str]` (family → `mne.io` function name).
- pytest marker `ephys_data` (downloads small pinned files the first time and caches them in `AIMPORT_EPHYS_CACHE`, default `/tmp/aimport-ephys-cache`).

- [ ] **Step 1:** Add the dependencies; `uv lock`. Check wheels for manylinux x86_64 and macOS arm64.
- [ ] **Step 2:** Capability tests on synthetic `RawArray`s (planted names in `subject_info`, meas_date 2025-02-15):
  - `test_readers_exist`: every family in `MNE_READERS` resolves to a callable in the pinned MNE. **MEF3 is the one to check.** If it is absent, MEF3 moves to the neo fallback (if neo reads it) or to `unsupported` with `"MEF3: export to EDF first"`.
  - `test_anonymize_forces_conversion[eeg-BrainVision, eeg-EDF, ieeg-BrainVision, meg-FIF]`: `write_raw_bids(..., anonymize={...}, format=F)` from an EDF/CTF source writes a new file whose SHA-256 differs from the source.
  - `test_emg_supported`: `write_raw_bids` accepts `datatype="emg"` with `format="EDF"`. With `format="BDF"`, either the file is written or MNE raises.
  - `test_nirs_from_snirf`: `write_raw_bids` on `read_raw_snirf` of an h5py-written SNIRF with `anonymize=None` writes `_nirs.snirf`, `_nirs.json`, `_channels.tsv` and `_optodes.tsv`.
  - `test_validator_ephys_examples` (docker): the pinned `bids-validator-2` passes each `bids-examples` set below with `EMPTY_FILE` ignored, as bids-examples' own CI does.
- [ ] **Step 3, ruling point (stop and report to Franco before Task 9):**
  - All pass → proceed.
  - MNE-BIDS lacks EMG → EMG is written by `mne.export.export_raw(fmt="edf")` plus aimport-generated sidecars (`write.emg_sidecars`). Task 9 grows by that function; report it.
  - BDF export is unavailable → remove `BDF` from `OUTPUT_FORMATS` (EMG is EDF only).
  - The validator rejects a datatype → stop and report its exact message.
- [ ] **Step 4:** Commit `aimport: ephys dependencies; capability ruling (readers, anonymize conversion, EMG, NIRS)`. The message records the outcome.

### Task 2: Fixtures, test data and the leak vocabulary

**Files:**
- Create: `tests/fixtures/ephys_fixtures.py`, `tests/test_ephys_fixtures.py`.
- Modify: `tests/conftest.py`, `tests/DATASETS.md`.

**Interfaces:**
- All synthetic planted builders sit under `dest/Smith_John_19700101/`, with meas_date `2025-02-15T10:00:00`, 10 s, 256 Hz:
  - `planted_edf(dest)` / `planted_bdf(dest)`:
    - header patient `MRN0042 M 01-JAN-1970 Smith_John`;
    - recording `Startdate 15-FEB-2025 EEGtech_Jane Hospital_X`;
    - EDF+ TAL annotations `"Smith John said hello"`, `"1"`, `"eyes closed"`;
    - channels `Fp1`, `Smith-Fp1`, `EMG1`.
  - `planted_brainvision(dest)`:
    - `.vhdr` `DataFile=Smith_John_rest.eeg`, plus a `[Comment]` section holding `Patient: Smith John, MRN0042`;
    - `.vmrk` with `Stimulus,S  1` and `Comment,Dr Jane Doe`.
  - `planted_eeglab(dest)`: `.set` with `setname="Smith John"`, `subject="MRN0042"`, `comments="Hospital X"`, event type `"MRN0042 start"`.
  - `planted_fif(dest)`:
    - `subject_info={"his_id":"MRN0042","first_name":"John","last_name":"Smith","birthday":date(1970,1,1),"sex":1}`;
    - `experimenter="Jane Doe"`, `description="Hospital X study"`, `proj_name="Smith pilot"`;
    - 3 fiducials, 4 HPI and 200 `EXTRA` dig points; MEG channels from `mne.io.read_info` of a testing-data FIF.
  - `planted_snirf(dest)`: h5py, CW amplitude, 2 sources × 2 detectors × 760/850 nm, `metaDataTags` `SubjectID=MRN0042`, `MeasurementDate=2025-02-15`, `MeasurementTime=10:00:00`, `Operator=Jane Doe`, `stim1/name="Jane Doe tapping"`.
  - `planted_ctf_pos(dest)` and `planted_kit_hsp(dest)`: head-shape companion files only.
  - `planted_nwb(dest)`: pynwb iEEG, 8 channels, `session_description="Smith John grid"`, `experimenter=["Jane Doe"]`, `institution="Hospital X"`, `subject.subject_id="MRN0042"`, `subject.date_of_birth=1970-01-01`, a `TimeIntervals` table with free-text `"seizure Dr Jane"`.
- `fetch_mne_testing(names: Iterable[str]) -> dict[str, Path]`:
  - raw GitHub downloads of single files and folders from `mne-tools/mne-testing-data` at the pinned commit `20cc221d737a37a6ee3a9c007e91bd69541fefe9`;
  - each file's SHA-256 is checked against `MNE_TESTING_FILES`;
  - total ≤ 80 MB.
  - Candidates (exact paths, sizes and hashes are pinned at task time, preferring the smallest file per family):
    - EDF, BDF and GDF test files;
    - `Brainvision/test_NO.vhdr` (with its `.vmrk`/`.eeg`);
    - `EEGLAB/test_raw.set` (with its `.fdt`);
    - `EGI/test_egi.mff/`;
    - `NihonKohden/MB0400FU.EEG` (with companions);
    - `Persyst/*.lay` (with `.dat`);
    - `CTF/testdata_ctf.ds/`;
    - `KIT/test.sqd`;
    - `BTi/erm_HFH/`;
    - `SNIRF/NIRx/NIRSport2/…snirf`;
    - `NIRx/nirscout/…/`;
    - `Hitachi/*.csv`.
- `fetch_bids_examples(names) -> dict[str, Path]`, from bids-examples at a pinned commit. Sets (exact names checked at task time): `eeg_cbm`, `eeg_rest_fmri`, `ieeg_epilepsy`, `ieeg_visual`, `ds000247` (MEG), `fnirs_tapping`, `fnirs_automaticity`, and the bids-examples EMG sets.
- `conftest.EPHYS_PLANTED = PLANTED | {"jane doe", "jdoe", "eegtech_jane", "dr jane", "said hello", "2025-02-15", "20250215", "15.02.25", "15-feb-2025", "01-jan-1970", "smith pilot", "smith-fp1", "tapping"}`; `tokens()` also checks it.
  - Leak tests use `ephys_tokens(text) -> set[str]` over `EPHYS_PLANTED`, which avoids clashes with the MRI vocabulary.
  - `"tapping"` is planted only in free text; the bids-examples task label `tapping` is never used in leak tests.

- [ ] **Step 1:** Tests:
  - `test_planted_edf_header`: re-reading bytes 8–168 gives the planted fields.
  - `test_planted_fif_dig_counts`: 3/4/200.
  - `test_planted_snirf_tags`.
  - `test_fetch_hashes` (`ephys_data`): every fetched file matches its hash; the total is under 80 MB.
- [ ] **Step 2:** DATASETS.md:
  - a new section "Electrophysiology and optical data", with a row per mne-testing-data file (path, bytes, SHA-256, the format it covers, licence BSD-3) and per bids-examples set (commit, "data files are empty: layout and validator only");
  - the planted values table;
  - OpenNeuro: "fNIRS/EMG runs only after licence check (CC0); none chosen yet".
- [ ] **Step 3:** Commit `aimport ephys: planted recordings, pinned test data and the ephys leak vocabulary`.

### Task 3: Discovery (`ephys/discover.py`)

**Files:**
- Create: `discover.py`, `tests/test_ephys_discover.py`.

**Interfaces:**
- `FAMILIES`. Detection uses extension, plus a sniff for `.csv`, `.raw` and folders:

  | Family | Matches (recording root, companions) |
  |---|---|
  | `edf`, `bdf`, `gdf` | `.edf`/`.rec`, `.bdf`, `.gdf` (8-byte version field checked) |
  | `brainvision` | `.vhdr`; the `.vmrk` and data file named inside it (resolved within the same folder only) |
  | `eeglab` | `.set`; the `.fdt` of the same stem |
  | `cnt` | `.cnt` |
  | `egi` | `.mff/` folder (holds `info.xml`); `.raw` with an EGI header |
  | `nihon` | `.EEG` with `.PNT`/`.LOG`/`.21E` of the same stem |
  | `persyst` | `.lay`; the `.dat` named in `[FileInfo] File=` (same folder only) |
  | `mef3` | `.mefd/` (subject to the Task 1 ruling) |
  | `fif` | `.fif`, `.fif.gz`, excluding `-ave`, `-cov`, `-epo`, `-fwd`, `-inv`, `-trans`, `-sol`, `-proj` and split continuations `-1.fif` (companions of the first file) |
  | `ctf` | `.ds/` folder, never walked inside; `hz.ds` excluded with the reason `"CTF head-localisation run"` (as ezBIDS `find_img_data.py`) |
  | `bti` | a folder holding `c,rfDC` (or `e,rf*`) and `config`; `hs_file` is a head-shape companion |
  | `kit` | `.sqd`/`.con`; `.mrk`, `.elp` and `.hsp` of the same folder (`.hsp` is head shape) |
  | `nirx` | a folder holding `*.hdr` with `.wl1`/`.wl2` (NIRScout), or NIRSport2 `*_config.json` and `.snirf` |
  | `hitachi` | `.csv` whose first line starts `Header` and contains `ETG` |
  | `snirf` | `.snirf` |
  | `nwb` | `.nwb` with an `ElectricalSeries` (checked with h5py, no pynwb load) |
  | `blackrock` | `.ns1`–`.ns6` with `.nev` (neo fallback) |
  | `unsupported` | Artinis `.oxy3/.oxy4/.oxy5/.oxyproj`; Shimadzu `.omm` or `.txt`/`.csv` with a Shimadzu header; reason `"export to SNIRF first"` |

- **Input already in BIDS:** a `sub-*/[ses-*/]{eeg,meg,ieeg,nirs,emg}/` folder that holds a recording is claimed **whole**, so its `_channels.tsv`, `_events.tsv` and so on never become ancillary. Its sidecars are read only for `task`, `run` and `acq` entities and for safe numeric fields (`PowerLineFrequency`, `EEGReference` when it matches `^[A-Za-z0-9 _/+-]{1,32}$`).
- `claim(input_dir: Path, remote: list[str]) -> tuple[Claim, list[Recording]]`, with `@dataclass Recording: rel: str; family: str; companions: list[str]; headshape: list[str]; empty_room: bool; excluded: str | None`.
  - Remote sources are not supported for ephys; `remote` is ignored.
  - `empty_room` is true for path tokens `emptyroom`, `empty_room`, `empty-room`, `noise`, `erm`, or a `sub-emptyroom` folder.
- `ephys/names.py` is not needed. Path facts reuse `micr.names.facts` and `micr.names.path_terms`. `names.VOCAB` is extended through a parameter `vocab=micr.names.VOCAB + EPHYS_VOCAB`, with `EPHYS_VOCAB = ("eeg","meg","ieeg","nirs","fnirs","emg","rest","resting","task","run","noise","emptyroom","erm","sleep","oddball","mmn","motor","tapping","auditory","visual","faces","nback","eyes","open","closed")`.

- [ ] **Step 1:** Tests on a tree combining all planted builders and stub files:
  - `test_families`: every row of the table gets its family.
  - `test_brainvision_companions_from_header`: `.vmrk`/`.eeg` are claimed with the `.vhdr`; a `DataFile=../../etc/passwd` is refused (`excluded="BrainVision data file outside its folder"`).
  - `test_ctf_hz_excluded`.
  - `test_headshape_listed`: `.pos`, `.hsp` and `hs_file` are in `headshape`, not `companions`.
  - `test_bids_datatype_folder_claimed_whole`: `find_ancillary` (with the claimed roots excluded) returns no `_channels.tsv`.
  - `test_ds_and_mff_not_walked`: fewer than 20 `os.scandir` calls on a `.ds` with 5,000 files.
  - `test_unsupported_artinis`.
  - `test_mri_untouched`: DICOM and NIfTI files stay unclaimed.
- [ ] **Step 2–4:** Implement, pass, commit `aimport ephys: discover recordings, companions and head-shape files`.

### Task 4: Readers and identifying-term harvest (`ephys/readers.py`, `ephys/headers.py`)

**Files:**
- Create: `readers.py`, `headers.py`, `tests/test_ephys_readers.py`.

**Interfaces:**
- `@dataclass RecordingInfo`. Only these fields exist:
  - `family: str; system: str` (`SYSTEM_FAMILIES`: `"EDF"`, `"BrainVision"`, `"EGI"`, `"Neuromag/MEGIN"`, `"CTF"`, `"KIT"`, `"BTi/4D"`, `"NIRx"`, `"Hitachi"`, `"NWB"`, `"Blackrock"`, …);
  - `sfreq: float; n_channels: int; n_times: int; duration_s: float`;
  - `ch_types: dict[str, int]` (MNE channel types);
  - `line_freq: float | None`; `has_dig: bool`; `n_headshape_points: int`;
  - `wavelengths: list[int]` (NIRS);
  - `meas_date: datetime | None` and `birthday: date | None` (**local only**; excluded from `view()`);
  - `sex: int | None; hand: int | None`;
  - `annotations: list[tuple[float, float, str]]` (local only, raw text; replaced by codes in `records.json` after Task 5).
- `open_raw(rec: Recording, input_dir: Path, *, headshape: bool = False) -> mne.io.BaseRaw`. MNE `read_raw_*` with `preload=False`:
  - `read_raw_bti(head_shape_fname=None)` unless `headshape`;
  - `read_raw_kit(hsp=None)` unless `headshape`;
  - `read_raw_ctf(system_clock="ignore")`;
  - `read_raw_egi` for `.mff`.
  - `blackrock` uses `open_neo(path)`, which builds `mne.io.RawArray` from `neo.rawio.BlackrockRawIO` and is allowed only below `MAX_LOAD_BYTES`. It is imported lazily; without `aimport[neo]`, the reason is `"Blackrock needs the neo extra: pip install aimport[neo]"`.
  - `nwb` never goes through `open_raw` (Task 10).
- `read_info(rec, input_dir) -> RecordingInfo` (headers only).
- `headers.harvest(rec, input_dir, raw) -> set[str]`, the identifying terms of one recording:
  - **every** family: `subject_info` strings (his_id, names); `experimenter`, `description`, `proj_name`; device serial; every annotation description that is not a safe label; `scrub._date_forms` plus `edf_date_forms` of meas_date and birthday; `micr.names.path_terms([rel] + companions)` with the ephys vocabulary.
  - `edf`/`bdf`: `read_edf_header(path) -> EdfHeader(patient: str, recording: str, startdate: str, starttime: str)`, tokens of patient and recording except `X`, `Startdate`, `M`, `F`; TAL texts.
  - `brainvision`: `[Comment]` lines, `DataFile`/`MarkerFile` stems, `.vmrk` descriptions.
  - `eeglab`: `scipy.io.loadmat(variable_names=["EEG"], squeeze_me=True)` or h5py for v7.3, reading `setname`, `subject`, `filename`, `filepath`, `comments`, `history`, `condition`, `group` and event `type` strings. A `.set` above `512 * 2**20` with embedded data is read through h5py only.
  - `nihon`: patient ID, name and birth date from `.PNT` at MNE's parser offsets; `.LOG` texts.
  - `persyst`: `.lay` `[Patient]` values; `File=`; `[Comments]` texts.
  - `egi`: `.mff/subject.xml` field values (defusedxml).
  - `ctf`: `.infods` values for keys starting `_PATIENT_`, `_PROCEDURE_`, `_DATASET_` (defusedxml); the `.ds` stem.
  - `nirx`: `.hdr` `[GeneralInfo]` `FileName`, `Date`, `Time`, `Subject`; NIRSport2 `*_description.json` strings.
  - `hitachi`: header rows `Name`, `ID`, `Comment`, `Date`.
  - `snirf`: every `metaDataTags` value except units; `stim*/name`.
- `headers.edf_date_forms(d: date) -> set[str]`: `dd.mm.yy`, `DD-MMM-YYYY` (upper and lower case), `yymmdd`.

- [ ] **Step 1:** Tests:
  - `test_planted_terms[edf,bdf,brainvision,eeglab,fif,snirf]`: `harvest` contains every applicable `EPHYS_PLANTED` value; it contains no channel name that is clean (`Fp1`), and neither `Stimulus` nor `eyes closed`.
  - `test_info_allowlisted`: `RecordingInfo.view()` (the dict without the local fields) holds none of `EPHYS_PLANTED`.
  - `test_preload_false`: tracemalloc peak < 16 MiB while `read_info` runs on a 64 MiB synthetic BDF.
  - `test_headshape_not_read_by_default`: KIT and BTi from testing data give `n_headshape_points == 0`; with `headshape=True`, more than 0.
  - `test_mne_testing_readers` (`ephys_data`), parametrised over the fetched files: `read_info` succeeds; `system` and `ch_types` are as expected; `sfreq > 0`.
  - `test_neo_missing_message` (neo import monkeypatched to fail).
- [ ] **Step 2–4:** Implement, pass, commit `aimport ephys: lazy readers and per-format identifying-term harvest`.

### Task 5: Event codes and channel names (`ephys/events.py`, `ephys/channels.py`, plan field)

**Files:**
- Create: `events.py`, `channels.py`, `tests/test_ephys_events.py`.
- Modify: `plan.py` (`Plan.event_names`, `set_event_names`), `server.py` (`PatchBody.event_names`).

**Interfaces:**
- `events.SAFE_PATTERNS`. Full match on stripped text, case-insensitive:
  - `^\d{1,6}$`;
  - `^(Stimulus|Response)/\s*[SR]\s*\d{1,4}$`;
  - `^BAD(_[A-Z_]{1,20})?$`, `^EDGE$`, `^boundary$`;
  - `^Sleep stage (W|N1|N2|N3|N4|R|\?)$`;
  - `^(DIN|TRSP|STI|STIM|TRIG|TR)\d{0,3}$`;
  - `^(<SAFE_WORDS>)([ _-]?\d{1,4})?$`, where `SAFE_WORDS` is a fixed tuple: `rest`, `eyes open`, `eyes closed`, `eo`, `ec`, `start`, `stop`, `begin`, `end`, `onset`, `offset`, `stimulus`, `response`, `target`, `standard`, `deviant`, `novel`, `cue`, `feedback`, `button`, `left`, `right`, `correct`, `incorrect`, `blink`, `artifact`, `movement`, `seizure`, `spike`, `sleep`, `wake`, `photic`, `hyperventilation`, `baseline`, `trigger`, `marker`, `task`.
- `events.code(descriptions_by_recording: list[list[str]], terms: set[str]) -> tuple[dict[str, str], dict[str, str]]` returns (normalised original → label, code → code):
  - a safe label that `scrub.redact` leaves unchanged is kept;
  - anything else gets `E001`, `E002`, … in first-occurrence order;
  - the first map goes to `work/ephys/events.json`; the second seeds `Plan.event_names`.
- `events.counts(annotations, mapping) -> dict[str, int]` (label → count).
- `Plan.event_names: dict[str, str] = {}`. `Plan.set_event_names(edits: dict[str, str])` requires:
  - each key is an existing code (else `ValueError("unknown event code")`);
  - the value matches `^[A-Za-z0-9][A-Za-z0-9 _./+-]{0,39}$`.
  The server stores it through `srv.clean_obj` (run-term redaction). A value that redaction changes → 400 `"event name contains an identifying term"`. An edit after approval → 409, as for other plan edits.
- `channels.rename(ch_names: list[str], ch_types: list[str], terms: set[str]) -> dict[str, str]` (old → new, only for renamed channels). It is deterministic, `<type>_<NNN>` numbered within the type, and never collides with an existing name. The map goes to `work/ephys/channels.json`.

- [ ] **Step 1:** Tests:
  - `test_safe_labels_kept`: `"Stimulus/S  1"`, `"BAD_ACQ_SKIP"`, `"eyes closed"`, `"Sleep stage N2"`, `"12"`.
  - `test_free_text_coded`: `"Smith John said hello"` → `E001`, and a second occurrence in another recording → `E001`. `"MRN0042 start"` → `E002`, even though it starts with no safe word. `"rest Smith"` → coded.
  - `test_safe_word_with_term_coded`: if `"rest"` is a run term, it is coded too.
  - `test_patch_event_names`: OK path; unknown code → 400; `"Smith"` → 400; after approval → 409; `/plan` shows `event_names` and never an original.
  - `test_channel_rename`: `Smith-Fp1` → `eeg_002` (the next free); `Fp1` kept; `S1_D1 760` kept; names longer than 32 characters → renamed; no collisions over 1,000 random cases.
- [ ] **Step 2–4:** Implement, pass, commit `aimport ephys: coded event labels and identifier-free channel names`.

### Task 6: Scan records, plan entries, planner hook and mapping (`ephys/module.py`)

**Files:**
- Create: `module.py`, `tests/test_ephys_plan.py`.
- Modify: `plan.py`, `schema.py`, `planner.py` (`_check_nameable`, `_rederive`), `brainlife_map.py`, `data/bids_brainlife_map.yaml`, `tests/test_brainlife_map.py`, `ancillary.py`, `modality.modules()` (register `EphysModule()` after `MicrModule()`).

**Interfaces:**
- `PlanEntry` gains defaulted fields, so old plans still load:
  - `modality: Literal["mri","micr","ephys"]`;
  - `ephys_format: str = ""` (editable `"str?"`, must be in `OUTPUT_FORMATS[datatype]`; NWB only when `family == "nwb"`);
  - `keep_headshape: bool = False` (editable `"bool"`, meaningful for meg and eeg);
  - `event_counts: dict[str, int] = {}` (labels after coding; read only);
  - `empty_room: str | None = None` (the entry id of the paired `sub-emptyroom` entry).
- `schema.SUPPORTED_DATATYPES += ("eeg","meg","ieeg","nirs","emg")`. `CHECK_EXTS` becomes per format: `{"BrainVision": ".vhdr", "EDF": ".edf", "BDF": ".bdf", "FIF": ".fif", "SNIRF": ".snirf", "NWB": ".nwb"}`, looked up through `entry.ephys_format`. `_check_nameable` requires the `task` entity for all five datatypes.
- A `modality` and datatype mismatch gets status `unknown` with reason `"electrophysiology input: datatype must be one of eeg, meg, ieeg, nirs, emg"`, the same rule as micr.
- `EphysModule.scan` writes `records.json` (one record per recording: `rel`, `family`, `companions`, `headshape`, `info` with local fields, `terms`, `event_labels`) and `terms.json`. Progress messages are `"reading recording headers (k of n)"`.
- `EphysModule.terms(work)` = the union of record terms.
- `EphysModule.plan`:
  - **Datatype heuristic:**
    - BIDS datatype folder wins;
    - `system` in a MEG family → `meg`; NIRS family → `nirs`; `nwb` → `ieeg`;
    - else channel types: `seeg`+`ecog`+`dbs` ≥ 50% of data channels → `ieeg`; `emg` ≥ 50% → `emg`; else `eeg`.
  - **Subjects:**
    - `key.subject_id("ephys:id=" + his_id)` when his_id is not a placeholder (`planner.is_placeholder` plus the EDF `X` and `0` values);
    - else `"ephys:name=" + last^first`;
    - else the `sub-` folder label as `proposed` with a run-local original;
    - else the donor token from `micr.names.facts`;
    - else run-local, as in `_assign_subjects`.
    - Empty-room recordings get the literal subject `emptyroom`, never through the key.
  - **Indices:** `subject_idx`/`series_idx` = `EPHYS_INDEX_BASE + i`.
  - **Sessions:** input `ses-` labels when `planner._usable`; else, when a subject has recordings on more than one day, `01`, `02`, … in date order; else `None`.
  - **Task:**
    - input `task-` entity when usable;
    - else the first `EPHYS_VOCAB` task word in the path (`rest`, `sleep`, `oddball`, `mmn`, `motor`, `tapping`, `auditory`, `visual`, `faces`, `nback`);
    - else `task="unknown"` with status `unknown` and reason `"set the task label"`.
    - Empty-room: `task-noise`.
  - **Run:** set when more than one recording shares (subject, session, task, acq), numbered in meas_date order.
  - **Empty-room pairing:** each MEG entry gets the empty-room recording nearest in time on the same day, before or after (ezBIDS `convert_meg.py` logic), compared on local meas_dates only.
  - `ephys_format` is the first entry of `OUTPUT_FORMATS[datatype]`; EMG from a BDF source → `BDF` when allowed.
  - `description` is generated only, for example `"EDF → BrainVision, 64 ch (eeg 60, eog 2, ecg 1, stim 1), 1000 Hz, 612 s, 3 event codes"`.
  - **Warnings:** the load-size warning; `"head-shape points found and dropped by default (keep_headshape to keep)"` when any MEG or EEG record has `n_headshape_points > 0`.
  - **Exclusions:** `unsupported` and `excluded` records → one entry each with the reason; `deface=False` always.
  - `Plan.event_names` is seeded from `events.code`.
- `brainlife_map.to_brainlife(datatype, suffix, entities, sidecar, extension: str | None = None)` gains a second table, `_EXT_TABLE[(datatype, suffix, extension)]`, built from active extension rows. Lookup goes extension first, then (datatype, suffix). The output extension comes from `ephys_format`: BrainVision → `.eeg` (bids-walker keys on `eeg.eeg`).
- **Mapping YAML:** the eeg rows (`.bdf`, `.edf`, `.eeg`, `.set`) and the meg rows (`.ds`, `.fif`) change `planned` → `active`. Each gets a note: aimport writes `.vhdr/.eeg`, `.edf`, `.bdf` and `.fif` only. The ieeg, nirs and emg drafts are unchanged.
- **Ancillary:** inherited sidecars at the root, subject or session level with suffix in `{eeg, meg, ieeg, nirs, emg, channels, electrodes, coordsystem, optodes}` are planned `drop` with reason `"electrophysiology sidecars are generated by aimport"` and `locked=True`. Inherited `events.*` files are unchanged.

- [ ] **Step 1:** Tests with `client=None` on all planted builders plus stub CTF and empty-room trees:
  - `test_datatypes`: EDF with `seeg` channel types → `ieeg`; FIF → `meg`; SNIRF → `nirs`; mostly-EMG EDF → `emg`; BrainVision → `eeg`.
  - `test_subject_pseudonymised`: `MRN0042` gets a key ID; a second scan reuses it; `json.dumps(asdict(plan))` holds none of `EPHYS_PLANTED`.
  - `test_task_unknown_needs_review`.
  - `test_emptyroom_paired_and_no_date_session`: `sub-emptyroom`, `task-noise`, `session is None`; `entry.empty_room` is set on the MEG entry; no `ses-2025…`.
  - `test_runs_by_date`.
  - `test_format_edit`: `ephys_format: "EDF"` on eeg is OK; `"FIF"` on eeg → `ValueError`; `"NWB"` on a non-NWB ieeg entry → `ValueError`.
  - `test_brainlife_ext_mapping`:
    - `to_brainlife("eeg","eeg",{"task":"rest"},{},".eeg") == ("neuro/eeg/brainvision", ["rest"])`;
    - `.fif` → `neuro/meg/fif`;
    - `ieeg` → `(None, [])` with `draft_for("ieeg","ieeg") == "neuro/ieeg/ieeg"`;
    - the YAML suite passes.
  - `test_inherited_ephys_sidecar_dropped`.
  - `test_indices_do_not_collide`: MRI + micr + ephys inputs together.
- [ ] **Step 2–4:** Implement, pass (with the phase-1 and micr planner suites), commit `aimport ephys: plan entries, pseudonymised subjects, empty-room pairing; eeg and meg rows active`.

### Task 7: The agent for electrophysiology

**Files:**
- Modify: `agent.py`, `module.py` (`ephys_view`).
- Test: `tests/test_ephys_agent.py`.

**Interfaces:**
- `agent.EPHYS_CLASSIFY_SYSTEM`:
  - the datatype is one of `eeg`, `meg`, `ieeg`, `nirs`, `emg`;
  - the suffix equals the datatype;
  - entities only `task`, `acq`, `run`; `task` must be a lowercase alphanumeric word chosen from `Hints` or `unknown`;
  - same JSON reply format.
  It is called through `classify(..., system=EPHYS_CLASSIFY_SYSTEM, datatypes=ephys.DATATYPES)`.
- `module.ephys_view(records) -> list[ScrubbedSeries]`:
  - `description=""`, `protocol=""`, `ezbids_type="<heuristic datatype>/<datatype>"`;
  - `fields` are exactly `{FormatFamily, SystemFamily, SamplingFrequency, ChannelCount, ChannelTypes, DurationSeconds (rounded to 1 s), EventCounts (labels after coding), LineFrequency, HasDigitization, Wavelengths, Hints}`;
  - `Hints` holds only tokens from `EPHYS_VOCAB`;
  - no channel names, no free text, no dates.
- The phase-1 agreement rule still applies.

- [ ] **Step 1:** Tests with a recording client:
  - `test_ephys_payload_allowlisted`: the keys are exactly the list above; `ephys_tokens(payload)` is empty; there is no `/`, no 6- or 8-digit date, no `:` time, and no channel name from the planted recordings (`Fp1` included).
  - `test_event_counts_coded_only`: `EventCounts` keys ⊆ safe labels ∪ `E\d{3}`.
  - `test_agent_fills_ambiguous_datatype`: an EDF with all-`eeg` types and the agent answering `ieeg` gives an `agent_note` and confidence < 0.8.
  - `test_agent_non_ephys_answer_rejected`.
  - `test_mri_and_micr_prompts_unchanged`.
- [ ] **Step 2–4:** Implement, pass, commit `aimport ephys: agent sees recording facts and coded event counts only`.

### Task 8: The final gate (`ephys/gate.py`)

Built before the writers so they fail closed from the start.

**Files:**
- Create: `gate.py`, `tests/test_ephys_gate.py`.

**Interfaces:**
- `gate.check(files: list[Path], out_root: Path, terms: set[str], forbidden_dates: set[str], sources: list[Path]) -> list[str]` returns violations as `"<BIDS rel path>: <field kind>"`. A violation never names the term.
  - Text files (`.json`, `.tsv`, `.vhdr`, `.vmrk`): the full text, folded with `scrub._fold`.
  - EDF/BDF: header bytes 0–256 + ns × 256, plus the decoded TAL channel.
  - FIF: every `FIFFT_STRING` tag outside data buffers (via `mne._fiff.open.fiff_open` tag directory); `read_info` checks on `subject_info` keys ⊆ {`sex`, `hand`}, empty experimenter, description and proj_name; `FIFFV_POINT_EXTRA` count recorded.
  - SNIRF/NWB: every string dataset and attribute (h5py `visititems`).
  - `.eeg` (BrainVision binary data): skipped.
  - Any file: size + SHA-256 equal to a source → `"copied source bytes"`. Sizes are compared first; only equal sizes are hashed.
- `gate.GateError(violations)`. The module's `write` raises it, and the server's existing failure path sets the output aside (as phase 1 `set_aside`). `/status` shows only the BIDS paths and field kinds.
- `forbidden_dates` = original meas_dates and birthdays in all `scrub._date_forms` and `edf_date_forms`. **Shifted** dates are allowed only in `scans.tsv` `acq_time`.

- [ ] **Step 1:** Tests:
  - `test_gate_flags_planted[edf,bdf,brainvision,fif,snirf,nwb]`: each raw planted file placed under `out/` → at least one violation naming its field kind, and no term in the message.
  - `test_gate_flags_copied_source`.
  - `test_gate_clean_passes`: a clean `RawArray` written by MNE-BIDS → `[]`.
  - `test_gate_shifted_date_only_in_scans`.
  - `test_gate_bounded`: a 256 MiB BDF is checked with a peak < 32 MiB.
- [ ] **Step 2–4:** Implement, pass, commit `aimport ephys: final gate re-reads every written header and sidecar`.

### Task 9: De-identification and the MNE-BIDS writer (eeg, ieeg, emg, meg)

**Files:**
- Create: `deid.py`, `write.py`, `tests/test_ephys_write.py`.
- Modify: `headers.py` (rewriters), `module.py` (`write`), `server.py` (`execute` passes the ephys module; `reset_output` clears `work/ephys/scratch`).

**Interfaces:**
- `deid.clean(raw, *, renames: dict[str, str], labels: dict[str, str], event_names: dict[str, str], keep_headshape: bool) -> mne.io.BaseRaw`. Mutates info and annotations as listed in Global Constraints, with no data load.
- `write.daysback(dates: list[datetime], offset_days: int) -> int`: the smallest `d` with `max(dates) - d days < 1925-01-01`, plus `abs(offset_days)`.
- `write.write_recording(entry, rec, raw, scratch: Path, dest: Callable[[str], Path], schema, terms, er_path: BIDSPath | None) -> list[str]` returns the output rel paths:
  - `BIDSPath(subject, session, task, acquisition, run, datatype, root=scratch)`;
  - `write_raw_bids(raw, bp, anonymize={"daysback": d, "keep_his": False, "keep_source": False}, format=<entry.ephys_format>, empty_room=er_path, allow_preload=<raw.preload>, overwrite=True, verbose=False)`;
  - then `headers.rewrite_edf(path)` / `headers.rebuild_vhdr(path, bids_stem)` / `headers.check_vmrk(path, allowed_labels)`;
  - `write.rebuild_sidecar(path, schema, datatype, suffix, terms)` for every JSON;
  - `scrub.redact` on every `.tsv` cell;
  - recording files and per-run sidecars are moved to `dest(rel)`. MNE-BIDS's `participants.*`, `dataset_description.json`, `README` and `scans.tsv` are discarded;
  - `*_headshape.pos` is never moved unless `keep_headshape`.
- The empty-room recording is written first. Its `BIDSPath` is passed as `empty_room`, so the sidecar gets `AssociatedEmptyRoom` as a BIDS-relative path.
- `EphysModule.write(...) -> ModuleOutput`:
  - for each included entry in record order: `open_raw` → `channels.rename` → `deid.clean` → `write_recording`;
  - then `gate.check` on everything written;
  - `scratch/` is deleted in a `finally`.
  - `ModuleOutput.participants[sub] = {"age": <years from the local birthday at meas_date, capped as writer._parse_age>, "sex": "M"|"F"|"n/a"}`, plus `emptyroom: n/a`.
  - `ModuleOutput.scans[(sub, ses)] = [(rel, shifted acq_time)]`.
- `headers.rewrite_edf(path)` writes in place inside the output only (never the source), with fixed-width space padding and a header length check.

- [ ] **Step 1:** Tests on planted EDF, BDF, BrainVision, EEGLAB and FIF:
  - `test_edf_header_cleared`: the output EDF (`ephys_format="EDF"`) header patient is `X X X X`, recording `Startdate X X X X`, startdate `01.01.85`.
  - `test_brainvision_rebuilt`: `DataFile`/`MarkerFile` equal the BIDS names; no `[Comment]` Patient line; `.vmrk` descriptions ⊆ labels.
  - `test_events_tsv_coded`: `trial_type` ⊆ `event_names` values; a renamed code (`E001` → `"greeting"`) shows `greeting`.
  - `test_channels_renamed_everywhere`: `Smith-Fp1` is absent from the `.vhdr`, `channels.tsv`, `electrodes.tsv` and `events.tsv`.
  - `test_fif_subject_info_minimal` and `test_meg_headshape_dropped`: no `EXTRA` points by default; 200 with `keep_headshape=True`; fiducials and HPI kept in both; `DigitizedHeadPoints` matches.
  - `test_ctf_kit_bti_to_fif` (`ephys_data`): `ephys_format == "FIF"`; `.fif` output; the gate is clean.
  - `test_emg_edf`: an EMG entry writes `_emg.edf`; BrainVision is refused for EMG.
  - `test_scans_shifted_and_no_original_date`: `acq_time == 2025-02-15T10:00:00 + offset`; `EPHYS_PLANTED` is absent from every output byte (text and headers via the gate).
  - `test_sidecar_allowlist`: `_eeg.json` keys ⊆ schema keys; no `InstitutionName`; `TaskName` set.
  - `test_emptyroom_written_and_referenced`.
  - `test_source_unchanged`: the input mtimes and SHA-256 are unchanged after write.
  - `test_gate_failure_sets_aside`: a monkeypatched `rebuild_vhdr` no-op → stage `invalid`, output set aside, `/status` names `.vhdr` and holds no term.
  - Docker: `test_ephys_output_validates` → `validate_bids(...).ok` for an output with eeg, ieeg, emg and meg.
- [ ] **Step 2–4:** Implement, pass (with the phase-1 and micr writer suites), commit `aimport ephys: de-identify in memory and write EEG, iEEG, EMG and MEG through MNE-BIDS`.

### Task 10: SNIRF and NWB writers (`ephys/snirf.py`, `ephys/nwb.py`)

**Files:**
- Create: `snirf.py`, `nwb.py`, `tests/test_ephys_snirf_nwb.py`.
- Modify: `module.py`, `write.py`.

**Interfaces:**
- `snirf.write(raw, dest: Path, subject_label: str, labels: dict[str, str]) -> None`. h5py, SNIRF 1.1, CW amplitude only:
  - `/formatVersion`;
  - `/nirs/data1/{dataTimeSeries,time,measurementList*}`;
  - `/nirs/probe/{wavelengths,sourcePos3D,detectorPos3D,sourceLabels,detectorLabels}` (labels through the channel rule);
  - `/nirs/stim*` per label: `name` = label, `data` `[onset, duration, 1]`;
  - `metaDataTags` as in Global Constraints;
  - data written in chunks of ≤ 64 MiB from `raw.get_data(start, stop)`.
- `snirf.rewrite(src: Path, dest: Path, ...)`: an input SNIRF is read with `read_raw_snirf` (`preload=False`) and written again through `snirf.write`. It is never `h5py.copy`, so unknown groups and tags cannot survive.
- The NIRS write path: `snirf.write` → `scratch/clean.snirf` → `write_raw_bids(read_raw_snirf(clean), bp, anonymize=None, format="auto")` (the Task 1 ruling). Then the sidecar rebuild, the move, and a `snirf` header check. `optodes.tsv` labels go through the channel rule.
- `nwb.read_meta(path) -> RecordingInfo` (pynwb, lazy) and `nwb.harvest(path) -> set[str]`:
  - `session_description`, `experimenter`, `institution`, `lab`, `notes`, `experiment_description`, `protocol`, `identifier`;
  - `subject.*` strings and `date_of_birth`;
  - every string cell of `TimeIntervals` tables;
  - `session_start_time` date forms.
- `nwb.write(src, dest, subject_label, labels, renames)`. An h5py copy of `/acquisition` `ElectricalSeries` datasets and the `/general/extracellular_ephys` electrodes table only, chunk by chunk, with:
  - `/general` rebuilt with `session_description="n/a"`;
  - `session_start_time` and `timestamps_reference_time` = `"1900-01-01T00:00:00+00:00"`;
  - a new `identifier` (uuid4);
  - `subject` reduced to `subject_id=<BIDS label>`, `species` and `sex`;
  - `file_create_date` the same 1900 value;
  - interval tables rebuilt with a coded `label` column only;
  - electrodes `location` and `group_name` through `scrub.redact`; electrode `label` values through the channel rule;
  - no `/processing`, `/analysis`, `/stimulus` or `/specifications` beyond the core and hdmf-common namespaces.
  BIDS sidecars for NWB (`_ieeg.json`, `_channels.tsv`, `_electrodes.tsv`, `_events.tsv`) are generated by `write.ieeg_sidecars(info, entry, schema)`.

- [ ] **Step 1:** Tests:
  - `test_snirf_planted_cleared`: the output `metaDataTags` key set is exactly the required six; no `Operator`; `stim1/name` is a code; the gate is clean.
  - `test_snirf_roundtrip`: `read_raw_snirf(output)` has the same channel count, sfreq and wavelengths, and data equal within 1e-6 relative.
  - `test_nirx_hitachi_to_snirf` (`ephys_data`): the output validates in docker; `_optodes.tsv` is present.
  - `test_nwb_planted_cleared`: h5py string walk ∩ `EPHYS_PLANTED` = ∅; `pynwb.NWBHDF5IO(output).read()` succeeds; `ElectricalSeries` data are equal; the interval labels are codes.
  - `test_nwb_bounded`: a 256 MiB series is copied with a peak < 96 MiB.
  - Docker: `test_nirs_and_nwb_validate`.
- [ ] **Step 2–4:** Implement, pass, commit `aimport ephys: SNIRF and NWB written from scratch, never copied`.

### Task 11: QA viewer for traces (PNGs, `/qa/traces`, uPlot page)

Requires the QA viewer plan merged.

**Files:**
- Create: `ephys/qa.py`, `src/aimport/static/traces.js`, `src/aimport/static/traces.css`, `tests/test_ephys_qa.py`.
- Modify: `server.py`, `viewer.py`, `viewer-client/package.json`, `package-lock.json`, `build.mjs`, `Dockerfile` (no new stage; the existing client build copies uPlot), `tests/test_viewer_routes.py`.

**Interfaces:**
- `qa.primary_file(manifest_files: list[str]) -> int`: the index of the `.vhdr`, `.edf`, `.bdf`, `.fif` (first split), `.snirf` or `.nwb` file.
- `qa.render(entry_id: str, bids_path: Path, out_dir: Path) -> dict[str, str]`. matplotlib Agg; `mne.io.read_raw(bids_path, preload=False)`, or `nwb.open_series` for NWB. It writes:
  - `traces.png`: 10 s from `t = min(30, duration/2)`, ≤ 32 channels, offset-stacked, events from the written `events.tsv`;
  - `psd.png`: `raw.compute_psd(fmax=min(sfreq/2, 125), tmax=min(60, duration))`, one line per channel type;
  - `channels.png`: a bar of channel-type counts, with bad channels from `channels.tsv` `status == "bad"` in a second colour.
  The figure title is the BIDS basename. `savefig(..., metadata={"Software": None})`.
  - Rendering runs in `Server.execute` after the write, before validation. The output is `work/ephys/qa/<entry id>/` (never under `output/`). Render failures are logged by type only and do not fail the run.
- `qa.window(entry_id, path, t0: float, t1: float, ch: list[int]) -> dict`:
  - returns `{"name", "sfreq", "t0", "t1", "duration", "channels": [{"i","name","type","unit","bad"}], "x": [...], "y": [[...]], "events": [{"onset","duration","label"}], "pairs": [[hbo_i, hbr_i]]}`;
  - when samples > `MAX_POINTS`, min/max decimation in `MAX_POINTS // 2` bins;
  - values are in display units (µV for eeg/ieeg/emg/eog/ecg, fT for mag, fT/cm for grad, µM for hbo/hbr), rounded to 4 significant digits;
  - an LRU cache of 4 open raws.
  - NIRS: HbO/HbR come from `work/ephys/qa/<id>/hb.npy`. It is built at render time by `optical_density` → `beer_lambert_law(ppf=6.0)` when the recording is ≤ `512 * 2**20` sample bytes; otherwise the raw wavelength pairs are returned with `pairs` over 760/850.
- **Routes** (cookie or bearer, existing rules; 404 before execute and for entries not in the manifest, through `output_state()`/`output_file()`):
  - `GET /qa/png/{entry_id}/{kind}.png`, with `kind` ∈ {traces, psd, channels};
  - `GET /qa/traces/{entry_id}?t0=&t1=&ch=1,2,3`:
    - 400 when `t1 <= t0`, `t1 - t0 > MAX_WINDOW_S`, more than `MAX_CHANNELS` channels, or an index out of range;
    - the default is the first 32 channels and the first 10 s;
  - `GET /viewer/traces/{entry_id}` → `viewer.traces_page(entry_id, bids_name) -> str` (HTML, `data-entry` attribute, `<script src="/viewer/assets/uplot/uPlot.iife.min.js">` and `/viewer/assets/traces.js`, no inline script, so the existing `VIEWER_CSP` is unchanged);
  - `GET /viewer/assets/{path}`, from `src/aimport/static/` and `<neuroglancer_client_dir()>/vendor/uplot/`, with the same resolve-inside check as `/viewer/ng/`.
- `/viewer/` index: ephys rows show the three PNG thumbnails and a `"Traces"` link; MRI and micr rows are unchanged.
- `viewer-client`: `"uplot"` is pinned to the exact current 1.6.x (recorded in the commit). `build.mjs` copies `node_modules/uplot/dist/uPlot.iife.min.js` and `uPlot.min.css` to `<out>/vendor/uplot/`.
- `traces.js`:
  - fetches `/qa/traces/<entry>` with `credentials: "same-origin"`;
  - channel picker (≤ 64), pan and zoom by new window requests, event markers as vertical lines labelled with the label text (set with `textContent`, never `innerHTML`), HbO/HbR pairs in red and blue;
  - no other origin.

- [ ] **Step 1:** Tests:
  - `test_png_titles_bids_only`: PNG `tEXt` chunks hold no `Software`; OCR is not needed, because the title string passed to matplotlib is asserted through a spy; `ephys_tokens(png_bytes.decode("latin-1"))` is empty.
  - `test_traces_limits`: 65 channels → 400; a 601 s window → 400; a 1-hour 1 kHz recording window gives `len(x) <= 4000`.
  - `test_traces_min_max_keeps_peaks`: a single-sample spike survives decimation.
  - `test_traces_no_identifiers`: the JSON holds none of `EPHYS_PLANTED`; channel names are the renamed ones; event labels are codes or names.
  - `test_traces_nirs_pairs`.
  - `test_qa_routes_refuse`: before execute → 404; unknown entry → 404; MRI entry → 404 on `/qa/traces`; `/viewer/assets/../server.py` → 404.
  - `test_cookie_only_on_viewer_and_qa`: unchanged; it now also covers `/qa/traces` and `/qa/png`.
  - `test_traces_page_same_origin`: every `src`/`href` starts with `/`; no `http`.
- [ ] **Step 2–4:** Implement, pass, commit `aimport ephys: QA snapshots and an interactive uPlot trace viewer from the de-identified output`.
- [ ] **Step 5 (manual, recorded):** in the image, open the trace page for the planted EDF and SNIRF outputs. Save `aimport/docs/qa-viewer-traces.png` (synthetic data only). Note the uPlot version and any CSP change in the commit.

### Task 12: End-to-end leak test, bids-examples, datasets and docs

**Files:**
- Create: `tests/test_ephys_end_to_end.py`.
- Modify: `tests/DATASETS.md`, `aimport/README.md`.

**Tests**
- Docker, using the real app through the API with a recording LLM client, as `test_end_to_end.py` does. The input is every planted builder, plus an empty-room FIF, plus an Artinis `.oxy4` stub, plus the planted MRI DICOMs from phase 1 (mixed input):
  - `test_ephys_e2e_validated`: the stage reaches `validated`.
  - `test_ephys_e2e_no_leak`. None of `EPHYS_PLANTED` (or `PLANTED`) appears in:
    - any LLM request, `plan.json`, `scan.json` or `status.json`;
    - the bodies of `/plan`, `/status`, `/events`, `/viewer/*`, `/qa/traces/*` and `/qa/png/*`;
    - any byte under `output/bids/`, checked with the gate plus a raw byte search of every non-data file.
  - `test_ephys_e2e_events_named`: `PATCH /plan {"event_names": {"E001": "greeting"}}` → `events.tsv` shows `greeting`.
  - `test_ephys_e2e_headshape_opt_in`: two runs, with the default and with `keep_headshape`.
  - `test_ephys_e2e_unsupported_reported`: Artinis → `unsupported` with `"export to SNIRF first"`.
  - `test_ephys_e2e_no_source_copy`: the work folder minus `output/bids` and `ephys/qa` is under 2 MiB once scratch is deleted; the input is unchanged.
  - `test_ephys_e2e_datatypes_target`: with `target="datatypes"`, eeg and meg entries map to `neuro/eeg/brainvision` and `neuro/meg/fif` with the task tag; ieeg, nirs and emg entries show their draft name and are excluded from upload.
- `test_mne_testing_e2e` (`docker` + `ephys_data`): one parametrised import per fetched mne-testing-data family → `validated`.
- `test_bids_examples_ephys` (docker): their data files are empty, so the test checks layout only:
  - for each example, plan a synthetic recording with the example's entities (subject, session, task, acq, run) on a `RawArray` with the example's channel types;
  - the written relative paths for the recording and sidecars equal the example's file names for that run;
  - the output validates without ignores.

**DATASETS.md**
- Final rows for the mne-testing-data files (pinned commit `20cc221d737a37a6ee3a9c007e91bd69541fefe9`, paths, bytes, SHA-256, used by), the bids-examples sets, every synthetic builder with its planted values, and the empty-room pairing fixture.
- OpenNeuro: one CC0 fNIRS run and one CC0 EMG run, each under 30 MB, only after the licence is recorded. Otherwise the row says `"none used: no CC0 run under 30 MB found"`.

**README**
- A new "Electrophysiology and optical" section:
  - accepted formats per datatype, output formats and how to change them, and unsupported formats with their messages;
  - what is removed (headers, dates, annotations → codes, channel renames, head shape);
  - naming event codes;
  - the QA snapshots and the trace page;
  - the memory warning and limit.

- [ ] **Step 1–3:** Write the tests, pass them in the image, commit `aimport ephys: end-to-end leak test, bids-examples layout, datasets and docs`.

---

## Not in this plan

- Linking an ephys subject to the same person's MRI subject automatically. The `ephys:` namespace keeps them apart; the reviewer can merge them with a subject edit.
- Remote (`https://`/`s3://`) ephys sources and reference datasets.
- Epoched or averaged data (`-epo.fif`, `-ave.fif`); continuous data only.
- NIRS frequency-domain and time-domain SNIRF (CW only); MEF3 if the Task 1 ruling finds no reader.
- Neurosift or NWB output for EEG.
- A headless-browser test of the uPlot page (manual check in Task 11; automated later together with the Neuroglancer one).
- Registering the ieeg, nirs and emg brainlife datatypes (drafts stay drafts).

### Critical Files for Implementation
- /Users/fp4834/git/brainlife/ezbids-micr/aimport/src/aimport/modality.py
- /Users/fp4834/git/brainlife/ezbids-micr/aimport/src/aimport/planner.py
- /Users/fp4834/git/brainlife/ezbids-micr/aimport/src/aimport/brainlife_map.py
- /Users/fp4834/git/brainlife/ezbids-qa/aimport/src/aimport/server.py
- /Users/fp4834/git/brainlife/ezbids-qa/aimport/src/aimport/viewer.py

---

**Notes for the controller (not part of the plan file):**
- **The eeg and meg rows would map to nothing.** `brainlife_map.load_table()` skips every row that has an `extension` key, even an active one. Without the extension-aware lookup in Task 6 (`_EXT_TABLE` plus the new `extension` argument to `to_brainlife`), making those rows active would have no effect.
- **Choices I made that the spec left open:**
  - CTF, KIT and BTi are converted to FIF, because MNE-BIDS anonymize needs FIF for MEG. So the `.ds` row becomes active but is never produced.
  - SNIRF is written by h5py first, then handed to MNE-BIDS so it writes the sidecars.
  - NWB iEEG is a rebuilt h5py copy.
  - Empty-room never gets MNE-BIDS's date-labelled sessions.
- **Library behaviour to check, all in Task 1:**
  - whether MNE has a MEF3 reader;
  - whether MNE-BIDS supports EMG;
  - whether BDF export works;
  - whether MNE-BIDS writes NIRS from SNIRF with `anonymize=None`.
- **The mne-testing-data paths in Task 2 are candidates.** They are pinned at task time with SHA-256. I found no existing reference to commit `20cc221d…` in the local repos.
- **Phase 2 is not committed yet.** Its Task 2 is uncommitted work in ezbids-micr (`modality.py` is untracked). The other Phase 2 hooks this plan depends on (`build_plan(modules=)`, `PlanEntry.modality`, `classify(system=, datatypes=)`, `write_bids(modules=)`) come from Phase 2 Tasks 6–8, which are not implemented yet.
