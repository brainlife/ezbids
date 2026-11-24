# aimport engine (phase 1: MRI and PET) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A local engine, packaged as a Docker image, that turns a folder of MRI/PET DICOM or NIfTI into a reviewed, de-identified, defaced, BIDS-validated dataset and serves the plan and previews over a loopback API.

**Architecture:** A Python 3.11 package `aimport` in `ezbids/aimport/`, run in an image layered on the ezBIDS handler image. ezBIDS's `preprocess.sh` + `ezBIDS_core.py` run unchanged as a subprocess (system Python 3.8) to convert and make the first guess; `aimport` (its own venv) scrubs metadata, asks an LLM about what ezBIDS left unknown, builds a plan, waits for approval, writes BIDS itself, defaces, and runs the BIDS validator against v1.11.2. Upload and brainlife datatype validators are **not** in the engine; `bl aimport` (separate plan) does them on the host.

**Tech Stack:** Python 3.11 (uv venv), pydicom ≥2.4, nibabel, PyYAML ≥6, bidsschematools, autobidsify==0.9.9.1, anthropic, FastAPI + uvicorn, pytest; ezBIDS handler toolchain (dcm2niix, dcm2niix4pet, pydeface, quickshear, bids-validator 1.14.8 used only by preprocess.sh); Deno BIDS validator for v1.11.2.

**Spec:** `docs/superpowers/specs/2026-11-23-aimport-design.md`

## Global Constraints

- BIDS target spec: v1.11.2, commit `fbe1af9aa1fa1bb32811d0e5f4be4bee3130bc3b`. ezBIDS core keeps reading its own `bids-specification` submodule at `3537e9ed` (its schema layout differs); do not repoint it.
- Phase 1 datatypes: anat, func, dwi, fmap, perf, pet. Anything else → plan entry with `status="unsupported"`, excluded by default.
- Nothing identifying in: any LLM request, any file under the output folder, any API response except `/preview` image bytes. The pseudonym key file never goes under the output folder.
- The LLM sees only `ScrubbedSeries` (Task 5). The agent works like autobidsify's: it reviews every series (not only ezBIDS's unknowns), infers entities such as task labels, and drafts dataset metadata (name, README); every agent output is shown at review. Backends: Claude (default model `claude-opus-5-5`) plus every provider autobidsify supports (OpenAI `gpt*`/`o1*`/`o3*`, Qwen via Ollama, REST or DashScope), routed through autobidsify. No key/model configured → heuristics only, never an error.
- Engine API binds loopback only; every request needs `Authorization: Bearer <token>`.
- Workspace rules (`~/git/brainlife/CLAUDE.md`): work on branch `agentic-importer`, never commit to master, never deploy or push images, tests first, 4-space indent, docs updated in the same PR.
- New dependencies needing Franco's OK at plan review: anthropic, fastapi, uvicorn, bidsschematools, uv, Deno + BIDS validator (autobidsify and the ezBIDS toolchain are approved in the spec).
- Anyone writing the Claude client loads the `claude-api` skill first.
- Every dataset used for testing or validation — imaging data, fixtures, schemas, validators — is recorded in `aimport/tests/DATASETS.md` (source, pinned commit/version, contents, planted values, which tests use it, why added or dropped). A task that adds, replaces or drops one updates that file in the same commit.

## Review Focus

1. **Input with junk and archives** (a `.zip` of DICOMs next to PDFs and `.DS_Store`): archives are expanded, non-imaging files are ignored, scan completes. → test in Task 3.
2. **Offline machine** (no network: ezBIDS's Cognitive Atlas lookup fails, no LLM): plan is still produced, unknown series marked `unknown`. → tests in Tasks 3 and 8.
3. **One person, two sessions on different dates in one import**: one pseudonym, one date offset, intervals between sessions preserved. → test in Task 6.
4. **Engine restarted after the plan was edited**: the edited plan is reloaded from the work folder, not regenerated. → test in Task 13.
5. **Identifiers in folder names** (`Smith_John_19700101/T1`): redacted in the plan, the API and output; never in a BIDS label. → test in Task 5.

---

## File structure (all under `ezbids/aimport/`)

| File | Responsibility |
|---|---|
| `pyproject.toml` | package `aimport`, Python ≥3.11, deps, pytest markers |
| `Dockerfile` | image `brainlife/aimport:dev` on top of the ezBIDS handler image |
| `bids-specification/` | git submodule at `fbe1af9` |
| `src/aimport/plan.py` | `Plan`, `PlanEntry`, JSON load/save |
| `src/aimport/ezbids_runner.py` | stage input, run `preprocess.sh`, parse `ezBIDS_core.json` |
| `src/aimport/schema.py` | v1.11.2 schema: valid datatype/suffix, BIDS filenames |
| `src/aimport/scrub.py` | identifying terms, redaction, scrubbed view, sidecar scrub |
| `src/aimport/pseudonyms.py` | per-project key: IDs and date offsets |
| `src/aimport/brainlife_map.py` | BIDS datatype/suffix → brainlife datatype + tags |
| `src/aimport/agent.py` | LLM clients and classification of unknown series |
| `src/aimport/planner.py` | merge ezBIDS guess + agent into a `Plan` |
| `src/aimport/writer.py` | write BIDS from an approved plan |
| `src/aimport/deface.py` | deface anat images |
| `src/aimport/validate.py` | BIDS validator v1.11.2 |
| `src/aimport/server.py` | loopback FastAPI app |
| `src/aimport/__main__.py` | `python -m aimport serve ...` |
| `tests/fixtures/fetch_dcm_qa.py` | download pinned public DICOMs and plant identifiers |
| `tests/fixtures/ezbids_core_siemens.json` | committed ezBIDS output for unit tests |
| `README.md` | how to build, run, test |

Unit tests run on the host venv (`cd aimport && uv run pytest -m "not docker"`). Tests marked `docker` run inside the image: `docker run --rm -v $PWD/aimport:/src brainlife/aimport:dev pytest -m docker /src/tests`.

---

### Task 1: Package skeleton and the plan model

**Files:**
- Create: `aimport/pyproject.toml`, `aimport/src/aimport/__init__.py`, `aimport/src/aimport/plan.py`, `aimport/README.md`
- Test: `aimport/tests/test_plan.py`

**Interfaces:**
- Produces:
  - `@dataclass PlanEntry: id: str; series_idx: int; subject_idx: int; session_idx: int; subject: str; session: str | None; datatype: str | None; suffix: str | None; entities: dict[str, str]; brainlife_datatype: str | None; brainlife_tags: list[str]; source: Literal["heuristic","agent","person","none"]; confidence: float; reason: str; deface: bool; exclude: bool; status: Literal["ok","unknown","unsupported","excluded_by_default"]; description: str` (description = redacted SeriesDescription)
  - `@dataclass Plan: version: int = 1; target: Literal["bids","datatypes"]; entries: list[PlanEntry]; approved: bool = False; deface_method: Literal["pydeface","quickshear"] = "pydeface"; dataset_name: str = "aimport dataset"; readme: str = ""; metadata_source: Literal["agent","person","none"] = "none"`
  - `PlanEntry` also has `agent_note: str = ""` (set when the agent disagrees with the heuristic).
  - `Plan.save(path: Path) -> None`, `Plan.load(path: Path) -> Plan`, `Plan.apply_edits(edits: list[dict]) -> None` (each edit has `id` plus any PlanEntry fields except `id`/`series_idx`/`subject_idx`/`session_idx`; sets `source="person"`, `approved=False`)

- [ ] **Step 1: Write the failing tests**

```python
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
```

(`entry(**kw)` is a test helper filling defaults.)

- [ ] **Step 2: Run** `cd aimport && uv run pytest tests/test_plan.py -v` — expect import errors.
- [ ] **Step 3: Implement** `plan.py`; `pyproject.toml` declares all Tech Stack Python deps and the `docker` and `docker_offline` pytest markers.
- [ ] **Step 4: Run** the same command — expect 4 passed.
- [ ] **Step 5: Commit** `git add aimport && git commit -m "aimport: package skeleton and plan model"`

---

### Task 2: Engine image and test data

**Files:**
- Create: `aimport/Dockerfile`, `aimport/tests/fixtures/fetch_dcm_qa.py`, `aimport/tests/test_image.py`
- Modify: `.gitmodules` (add `aimport/bids-specification` → `https://github.com/bids-standard/bids-specification` at `fbe1af9aa1fa1bb32811d0e5f4be4bee3130bc3b`)

**Interfaces:**
- Produces:
  - Host is Apple Silicon (Colima with Rosetta): build and run every image with `--platform linux/amd64`.
  - Image `brainlife/aimport:dev`, built by `docker build -t ezbids-handler:local handler/ && docker build -t brainlife/aimport:dev -f aimport/Dockerfile .` from the repo root. `FROM ezbids-handler:local`; ezBIDS repo at `/app` with its `bids-specification` submodule checked out at `3537e9ed`; `aimport` installed in `/opt/aimport-venv` (Python 3.11 via uv); `/opt/bids-schema/schema.json` exported from the v1.11.2 submodule with `bst export`; Deno BIDS validator on `PATH` as `bids-validator-2` (pin the release whose schema matches v1.11.2; record the version in README).
  - `fetch_dcm_qa(dest: Path, plant: bool = True) -> Path`: downloads `neurolabusc/dcm_qa` at a pinned commit (record it in the file), and with `plant=True` rewrites every file's `PatientName="Smith^John"`, `PatientID="MRN0042"`, `PatientBirthDate="19700101"`, `InstitutionName="Hospital X"`, prefixes `SeriesDescription` with `"Smith_John "`, and moves series under `dest/Smith_John_19700101/`. Returns the root.

- [ ] **Step 1: Write the failing docker test**

```python
@pytest.mark.docker
def test_toolchain_present():
    for cmd in (["dcm2niix", "-v"], ["pydeface", "--help"], ["bids-validator-2", "--version"]):
        assert subprocess.run(cmd, capture_output=True).returncode in (0, 3)  # dcm2niix -v exits 3
    assert json.load(open("/opt/bids-schema/schema.json"))["bids_version"] == "1.11.2"
```

- [ ] **Step 2: Build image and run** — expect FAIL until the Dockerfile exists.
- [ ] **Step 3: Write** the Dockerfile and `fetch_dcm_qa.py`.
- [ ] **Step 4: Run** `docker run --rm -v $PWD/aimport:/src brainlife/aimport:dev pytest -m docker /src/tests/test_image.py` — expect PASS.
- [ ] **Step 5: Commit** `git commit -m "aimport: engine image and DICOM test fixture"`

---

### Task 3: Run ezBIDS and parse its first guess

**Files:**
- Create: `aimport/src/aimport/ezbids_runner.py`, `aimport/tests/test_ezbids_runner.py`, `aimport/tests/fixtures/ezbids_core_siemens.json`

**Interfaces:**
- Produces:
  - `stage_input(input_dir: Path, work_dir: Path) -> Path`: makes `work_dir/ezbids` with a symlink tree of `input_dir` (`cp -rs`), so dcm2niix writes into `work_dir`, never into the read-only input.
  - `run_ezbids(staged: Path, handler_dir: Path = Path("/app/handler"), log: Callable[[str], None] = print) -> Path`: runs `preprocess.sh <staged>` with cwd `handler_dir` (which also runs `expand.sh` for archives), returns `staged / "ezBIDS_core.json"`; raises `EzbidsError(stderr_tail)` on non-zero exit.
  - `@dataclass CoreSeries: series_idx: int; type: str; entities: dict[str, str]; message: str; series_description: str; sidecar: dict; nifti_path: Path`
  - `@dataclass CoreObject: series_idx: int; subject_idx: int; session_idx: int; acquisition_date: str; acquisition_time: str; entities: dict; paths: list[Path]; sidecar: dict`
  - `@dataclass CoreSubject: subject_idx: int; label: str; patient_info: list[dict]; sessions: list[dict]`
  - `@dataclass CoreResult: series: list[CoreSeries]; objects: list[CoreObject]; subjects: list[CoreSubject]`
  - `parse_core(path: Path) -> CoreResult` (keys from `ezBIDS_core.json`: `series`, `objects` with `items[].path`/`items[].sidecar`, `subjects` with `PatientInfo`, `sessions`)

- [ ] **Step 1: Generate the fixture.** In the image, run `run_ezbids` on `fetch_dcm_qa(plant=False)`; copy `ezBIDS_core.json` to `tests/fixtures/ezbids_core_siemens.json`, rewriting absolute paths to relative. `grep -iE "smith|MRN|19700101"` on it must print nothing.
- [ ] **Step 2: Write the failing tests**

```python
def test_parse_core_series_and_objects():
    r = parse_core(FIXTURES / "ezbids_core_siemens.json")
    assert r.series and r.objects and r.subjects
    assert all(o.series_idx in {s.series_idx for s in r.series} for o in r.objects)
    assert any(s.type == "anat/T1w" for s in r.series)

@pytest.mark.docker
def test_run_on_planted_dicoms_with_junk(tmp_path):
    src = fetch_dcm_qa(tmp_path / "in")
    (src / "notes.pdf").write_bytes(b"%PDF-1.4")
    (src / ".DS_Store").write_bytes(b"\0")
    shutil.make_archive(src / "extra", "zip", first_dicom(src).parent)  # first file pydicom can read
    core = run_ezbids(stage_input(src, tmp_path / "work"))
    assert parse_core(core).series
    assert not any(p.name.endswith(".nii.gz") for p in src.rglob("*"))  # input untouched

@pytest.mark.docker_offline
def test_run_offline(tmp_path):
    core = run_ezbids(stage_input(fetch_dcm_qa(tmp_path / "in"), tmp_path / "work"))
    assert parse_core(core).series
```

`test_run_offline` is run with `docker run --network none` under marker `docker_offline`; assert `ezBIDS_core.json` exists. If ezBIDS core crashes on the Cognitive Atlas fetch, make `run_ezbids` set `EZBIDS_OFFLINE=1` and patch the fetch to tolerate failure in `handler/ezBIDS_core/ezBIDS_core.py:find_cog_atlas_tasks` (wrap `urlopen` in try/except returning `[]`) — the only edit to ezBIDS core in this plan, with its own commit.
- [ ] **Step 3: Run** unit + docker tests — expect FAIL.
- [ ] **Step 4: Implement** `ezbids_runner.py`.
- [ ] **Step 5: Run** — expect PASS for all three.
- [ ] **Step 6: Commit** `git commit -m "aimport: run ezBIDS and parse first guess"`

---

### Task 4: BIDS v1.11.2 schema helpers

**Files:**
- Create: `aimport/src/aimport/schema.py`, `aimport/tests/test_schema.py`

**Interfaces:**
- Produces:
  - `load_schema(path: Path = DEFAULT_SCHEMA) -> Schema` (`DEFAULT_SCHEMA` = `/opt/bids-schema/schema.json`, falling back to exporting from `aimport/bids-specification/src/schema` via `bidsschematools.schema.load_schema` on the host)
  - `Schema.is_valid(datatype: str, suffix: str) -> bool` (from `rules.files.raw.*`)
  - `Schema.allowed_entities(datatype: str, suffix: str) -> list[str]` (entity keys in schema order)
  - `Schema.filename(subject: str, session: str | None, datatype: str, suffix: str, entities: dict[str, str], ext: str) -> str` → relative path like `sub-01/ses-1/anat/sub-01_ses-1_acq-mprage_T1w.nii.gz`; raises `ValueError` for entities not allowed or labels that are not alphanumeric.
  - `PHASE1_DATATYPES = ("anat","func","dwi","fmap","perf","pet")`

- [ ] **Step 1: Write the failing tests**

```python
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
```
- [ ] **Step 2–4:** run (FAIL) → implement → run (3 passed).
- [ ] **Step 5: Commit** `git commit -m "aimport: BIDS v1.11.2 schema helpers"`

---

### Task 5: De-identification

**Files:**
- Create: `aimport/src/aimport/scrub.py`, `aimport/tests/test_scrub.py`, `aimport/tests/conftest.py` (shared `PLANTED` set and `tokens(text) -> set[str]` lowercase word/phrase matcher used by Tasks 5, 9, 10, 13, 14)

**Interfaces:**
- Consumes: `CoreResult`, `CoreSeries`, `CoreObject` (Task 3).
- Produces:
  - `identifying_terms(core: CoreResult, input_dir: Path) -> set[str]`: every `PatientName` (also split on `^`, space, `_`), `PatientID`, `PatientBirthDate` (as `YYYYMMDD` and `YYYY-MM-DD`), `OtherPatientIDs`, `InstitutionName`, `OperatorsName`, `ReferringPhysicianName` found in `subjects[].PatientInfo` and in a pydicom header read (`stop_before_pixels=True`) of the first readable DICOM in every directory under `input_dir`; terms shorter than 3 characters are dropped.
  - `redact(text: str, terms: set[str]) -> str`: case-insensitive replace of each term with `"[x]"`, longest first.
  - `@dataclass ScrubbedSeries: series_idx: int; description: str; protocol: str; ezbids_type: str; fields: dict[str, Any]`, where `fields` holds only `SCRUB_ALLOWLIST`: `Modality, Manufacturer, ManufacturersModelName, MagneticFieldStrength, ImageType, ScanningSequence, SequenceVariant, SequenceName, PulseSequenceName, EchoTime, RepetitionTime, InversionTime, FlipAngle, PhaseEncodingDirection, SliceThickness, NumberOfVolumes (from the NIfTI shape), Dimensions, VoxelSize, Units, TracerName, ImageComments_present (bool only)`.
  - `scrubbed_view(core: CoreResult, terms: set[str]) -> list[ScrubbedSeries]`
  - `SIDECAR_DROP = {"PatientName","PatientID","PatientBirthDate","PatientSex","PatientAge","PatientWeight","InstitutionName","InstitutionAddress","InstitutionalDepartmentName","StationName","DeviceSerialNumber","OperatorsName","ReferringPhysicianName","PerformingPhysicianName","AccessionNumber","StudyID","StudyInstanceUID","SeriesInstanceUID","ImageComments","ProcedureStepDescription","AcquisitionDateTime","AcquisitionDate","ContentDate","StudyDate","SeriesDate"}`
  - `scrub_sidecar(sidecar: dict, terms: set[str]) -> dict`: drops `SIDECAR_DROP` keys and runs `redact` on every string value (recursively).
  - `is_secondary_capture(series: CoreSeries) -> bool`: `"SECONDARY"` or `"DERIVED"` in `ImageType` together with Modality `OT`/`SC`, or SOPClassUID `1.2.840.10008.5.1.4.1.1.7*`.

- [ ] **Step 1: Write the failing tests**

```python
PLANTED = {"smith", "john", "mrn0042", "19700101", "1970-01-01", "hospital x"}

@pytest.mark.docker
def test_terms_found_from_planted_dicoms(core_planted):
    terms = {t.lower() for t in identifying_terms(core_planted.core, core_planted.input)}
    assert {"smith", "john", "mrn0042", "19700101", "hospital x"} <= terms

def test_redact_folder_name():
    assert redact("Smith_John_19700101/T1 MPRAGE", {"Smith", "John", "19700101"}) == "[x]_[x]_[x]/T1 MPRAGE"

def test_scrubbed_view_has_only_allowlisted_fields():
    view = scrubbed_view(fake_core(sidecar={"PatientName": "Smith^John", "EchoTime": 0.003}), {"Smith"})
    assert set(view[0].fields) <= SCRUB_ALLOWLIST
    assert "smith" not in json.dumps(asdict(view[0])).lower()

def test_scrub_sidecar_drops_and_redacts():
    out = scrub_sidecar({"InstitutionName": "Hospital X", "SeriesDescription": "Smith T1",
                         "nested": {"note": "MRN0042"}}, {"Smith", "MRN0042"})
    assert "InstitutionName" not in out
    assert out["SeriesDescription"] == "[x] T1"
    assert out["nested"]["note"] == "[x]"
```
- [ ] **Step 2–4:** run (FAIL) → implement → run (PASS).
- [ ] **Step 5: Commit** `git commit -m "aimport: de-identification"`

---

### Task 6: Pseudonym key

**Files:**
- Create: `aimport/src/aimport/pseudonyms.py`, `aimport/tests/test_pseudonyms.py`

**Interfaces:**
- Produces:
  - `PseudonymKey.load(keys_dir: Path, project_id: str) -> PseudonymKey` (file `keys_dir/<project_id>.aimport-key.json`, created with mode `0600` if missing)
  - `PseudonymKey.subject_id(original: str, existing: set[str], proposed: str | None = None) -> str`: returns the stored ID if `original` is known; else `proposed` if it is alphanumeric and not in `existing`; else the next zero-padded integer (`01`, `02`, …) not in `existing` or the key. `original` is `PatientID` or, if empty, `PatientName|PatientBirthDate`. Inputs whose ezBIDS subject label already matches `^[a-zA-Z0-9]+$` and came from a `sub-*` folder are passed as `proposed`.
  - `PseudonymKey.date_offset_days(subject_id: str) -> int`: random integer in `[-3650, -365]`, created once per subject and stored.
  - `PseudonymKey.save() -> None`

- [ ] **Step 1: Write the failing tests**

```python
def test_same_person_two_imports_same_id(tmp_path):
    k = PseudonymKey.load(tmp_path, "p1"); a = k.subject_id("MRN0042", existing=set()); k.save()
    k2 = PseudonymKey.load(tmp_path, "p1")
    assert k2.subject_id("MRN0042", existing={a}) == a

def test_skips_existing_project_ids(tmp_path):
    assert PseudonymKey.load(tmp_path, "p1").subject_id("X", existing={"01", "02"}) == "03"

def test_two_sessions_share_offset(tmp_path):
    k = PseudonymKey.load(tmp_path, "p1"); sid = k.subject_id("MRN0042", set())
    assert k.date_offset_days(sid) == k.date_offset_days(sid)
    assert -3650 <= k.date_offset_days(sid) <= -365

def test_key_file_private(tmp_path):
    k = PseudonymKey.load(tmp_path, "p1"); k.subject_id("A", set()); k.save()
    assert stat.S_IMODE((tmp_path / "p1.aimport-key.json").stat().st_mode) == 0o600
```
- [ ] **Step 2–4:** run (FAIL) → implement → run (PASS).
- [ ] **Step 5: Commit** `git commit -m "aimport: pseudonym key"`

---

### Task 7: BIDS → brainlife datatype mapping

**Files:**
- Create: `aimport/src/aimport/brainlife_map.py`, `aimport/tests/test_brainlife_map.py`

**Interfaces:**
- Produces: `to_brainlife(datatype: str, suffix: str, entities: dict[str, str], sidecar: dict) -> tuple[str | None, list[str]]`, with the table copied from `cli/bids-walker.js`: `anat/T1w→neuro/anat/t1w`, `anat/T2w→neuro/anat/t2w`, `anat/FLAIR→neuro/anat/flair`, `anat/MP2RAGE→neuro/anat/mp2rage`, `dwi/dwi→neuro/dwi`, `func/bold→neuro/func/task` (tags `[task]`, lowercased, as bids-walker.js:940-style), `fmap/epi→neuro/fmap ["pepolar"]`, `fmap/phasediff→neuro/fmap ["phasediff"]`, `fmap/magnitude1+phase1+…→neuro/fmap ["2phasemag"]`, `fmap/fieldmap→neuro/fmap ["single"]`. Anything else (including perf and pet) → `(None, [])`.

- [ ] **Step 1: Write the failing tests** — one assertion per table row above, plus `to_brainlife("pet","pet",{},{}) == (None, [])`.
- [ ] **Step 2–4:** run (FAIL) → implement → run (PASS).
- [ ] **Step 5: Commit** `git commit -m "aimport: brainlife datatype mapping"`

---

### Task 8: The agent

**Files:**
- Create: `aimport/src/aimport/agent.py`, `aimport/tests/test_agent.py`

**Interfaces:**
- Consumes: `ScrubbedSeries` (Task 5), `Schema` (Task 4).
- Produces:
  - `class LLMClient(Protocol): name: str; def complete(self, system: str, user: str, step: str) -> str`
  - `ClaudeClient(model: str = "claude-opus-5-5")` (anthropic SDK, `ANTHROPIC_API_KEY`).
  - `AutobidsifyClient(model: str)` calling `autobidsify.llm._call_llm(model, system, user, step=step)`; this gives every autobidsify backend — OpenAI (`gpt*`/`o1*`/`o3*`, `OPENAI_API_KEY`) and Qwen (`qwen*`, via Ollama `OLLAMA_BASE_URL`, REST, or DashScope `DASHSCOPE_API_KEY`) — with autobidsify's own routing (pinned at 0.9.9.1 because `_call_llm` is private).
  - `client_from_env() -> LLMClient | None`: `AIMPORT_MODEL` env (default `claude-opus-5-5`); `claude*` → `ClaudeClient`, anything autobidsify routes → `AutobidsifyClient`; returns `None` when that backend's key/endpoint is absent.
  - `@dataclass Guess: series_idx: int; datatype: str | None; suffix: str | None; entities: dict[str, str]; confidence: float; reason: str`
  - `classify(series: list[ScrubbedSeries], heuristic: dict[int, tuple[str, str, dict]], client: LLMClient | None, schema: Schema) -> list[Guess]`: one request (`step="classify"`) whose user message is exactly the JSON object `{"series": [...]}` with **all** series, each with ezBIDS's guess (from `heuristic`) attached so the agent can confirm or dispute it and fill entities such as `task`, `acq`, `dir`, `run`. Asks for a JSON array of `{series_idx, datatype, suffix, entities, confidence, reason}` limited to `PHASE1_DATATYPES`. Drops answers with `not schema.is_valid(...)` or entities outside `allowed_entities` (→ `datatype=None`, reason `"agent answer not valid BIDS"`). `client is None` or any client exception → every series gets `Guess(datatype=None, confidence=0, reason="no model configured")` / `"model error: <type>"`.
  - `@dataclass DatasetDraft: name: str; readme: str`
  - `draft_metadata(series: list[ScrubbedSeries], client: LLMClient | None) -> DatasetDraft | None`: one request (`step="metadata"`) for a dataset name and a README describing the acquisitions (modalities, sequences, counts); `None` without a client or on error. The reply is passed through `redact` with the run's terms before use.

- [ ] **Step 1: Write the failing tests**

```python
class Recorder:
    name = "recorder"
    def __init__(self, reply): self.reply, self.calls, self.users = reply, [], []
    def complete(self, system, user, step): self.calls.append(system + user); self.users.append(user); return self.reply

def test_payload_contains_only_scrubbed(schema):
    rec = Recorder('[{"series_idx":0,"datatype":"anat","suffix":"T1w","entities":{},"confidence":0.9,"reason":"MPRAGE"}]')
    classify([ScrubbedSeries(0, "[x] T1 MPRAGE", "", "", {"EchoTime": 0.003})], {}, rec, schema)
    assert "smith" not in rec.calls[0].lower()

def test_every_series_sent_with_heuristic(schema):
    rec = Recorder("[]")
    classify([ss(0), ss(1)], {0: ("anat", "T1w", {})}, rec, schema)
    sent = json.loads(rec.users[0])["series"]
    assert {s["series_idx"] for s in sent} == {0, 1}
    assert sent[0]["ezbids_guess"]["suffix"] == "T1w"

def test_invalid_answer_dropped(schema):
    rec = Recorder('[{"series_idx":0,"datatype":"anat","suffix":"bold","entities":{},"confidence":0.9,"reason":""}]')
    assert classify([ss(0)], {}, rec, schema)[0].datatype is None

def test_no_client_is_not_an_error(schema):
    g = classify([ss(0)], {}, None, schema)
    assert g[0].datatype is None and g[0].reason == "no model configured"
    assert draft_metadata([ss(0)], None) is None

def test_client_exception_is_not_an_error(schema):
    class Boom:
        name = "boom"
        def complete(self, s, u, step): raise TimeoutError()
    assert classify([ss(0)], {}, Boom(), schema)[0].reason == "model error: TimeoutError"

@pytest.mark.parametrize("model,cls", [("claude-opus-5-5", ClaudeClient), ("gpt-4o", AutobidsifyClient),
                                       ("qwen3-coder-next:latest", AutobidsifyClient)])
def test_backend_routing(monkeypatch, model, cls):
    for k in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "OLLAMA_BASE_URL"): monkeypatch.setenv(k, "x")
    monkeypatch.setenv("AIMPORT_MODEL", model)
    assert isinstance(client_from_env(), cls)
```
- [ ] **Step 2–4:** run (FAIL) → implement (load `claude-api` skill before writing `ClaudeClient`) → run (PASS).
- [ ] **Step 5: Commit** `git commit -m "aimport: LLM agent for unknown series"`

---

### Task 9: Planner

**Files:**
- Create: `aimport/src/aimport/planner.py`, `aimport/tests/test_planner.py`

**Interfaces:**
- Consumes: `parse_core`/`CoreResult` (3), `Schema` (4), `identifying_terms`/`scrubbed_view`/`redact`/`is_secondary_capture` (5), `PseudonymKey` (6), `to_brainlife` (7), `classify`/`LLMClient` (8), `Plan`/`PlanEntry` (1).
- Produces: `build_plan(core: CoreResult, input_dir: Path, key: PseudonymKey, existing_subjects: set[str], client: LLMClient | None, schema: Schema, target: Literal["bids","datatypes"]) -> Plan`. Rules, in order, per series:
  1. `is_secondary_capture` → `exclude=True`, `status="excluded_by_default"`, reason `"may contain burned-in identifiers"`.
  2. All series go to `classify` together with ezBIDS's guesses.
  3. ezBIDS `type` like `"anat/T1w"` with `schema.is_valid`: if the agent agrees (same datatype/suffix) → `source="heuristic"`, confidence `max(0.8, agent)`, entities merged (agent fills ones ezBIDS left empty, e.g. `task`); if the agent disagrees with confidence ≥ 0.5 → keep ezBIDS's mapping, confidence `0.5`, `agent_note` = the agent's alternative and reason, so the reviewer sees both; no answer → `source="heuristic"`, confidence `0.8`. Reason = ezBIDS `message` (redacted) or `"ezBIDS heuristic"`.
  4. ezBIDS `type == "exclude"` or invalid → an agent answer with confidence ≥ 0.5 → `source="agent"`; otherwise `status="unknown"`, `exclude=True`.
  5. Datatype outside `PHASE1_DATATYPES` → `status="unsupported"`, `exclude=True`.
  6. `draft_metadata` → `plan.dataset_name`/`plan.readme`, `metadata_source="agent"`; `None` → defaults, `metadata_source="none"`.
  7. `deface = (datatype == "anat")`; `brainlife_datatype, brainlife_tags = to_brainlife(...)`; with `target="datatypes"` and `brainlife_datatype is None` → `exclude=True`, reason appended `"; no brainlife datatype"`.
  One `PlanEntry` per (series, subject, session); `subject = key.subject_id(...)`, `session` = ezBIDS session label if alphanumeric, else `"1"`, `"2"` … by acquisition date order. `description = redact(SeriesDescription, terms)`.

- [ ] **Step 1: Write the failing tests** (on the committed fixture, `client=None` unless stated)

```python
def test_heuristic_entries(plan): assert any(e.suffix == "T1w" and e.source == "heuristic" for e in plan.entries)
@pytest.mark.docker
def test_no_identifiers_in_plan(plan_planted): assert not PLANTED & tokens(json.dumps(asdict(plan_planted)))
def test_subject_ids_avoid_existing(fixture_core, key, schema):
    p = build_plan(fixture_core, IN, key, {"01"}, None, schema, "bids")
    assert "01" not in {e.subject for e in p.entries}
def test_agent_fills_unknown(...): ...   # fixture series forced to type "exclude", Recorder returns valid guess → source "agent"
def test_agent_disagreement_kept_as_note(...): ...  # Recorder says T2w for ezBIDS's T1w → suffix stays T1w, confidence 0.5, agent_note mentions T2w
def test_agent_fills_task_entity(...): ...  # func series with empty task, agent returns task "rest" → entities["task"] == "rest"
def test_metadata_draft_redacted(...): ...  # Recorder README contains "Smith" → plan.readme contains "[x]", not "Smith"
def test_datatypes_target_excludes_unmapped(...): ...  # a pet entry is excluded with "no brainlife datatype"
```
- [ ] **Step 2–4:** run (FAIL) → implement → run (PASS).
- [ ] **Step 5: Commit** `git commit -m "aimport: planner"`

---

### Task 10: BIDS writer

**Files:**
- Create: `aimport/src/aimport/writer.py`, `aimport/tests/test_writer.py`

**Interfaces:**
- Consumes: `Plan` (approved), `CoreResult`, `Schema`, `scrub_sidecar`, `identifying_terms`, `PseudonymKey`.
- Produces: `write_bids(plan: Plan, core: CoreResult, input_dir: Path, terms: set[str], key: PseudonymKey, schema: Schema, out_dir: Path) -> list[Path]`. Raises `PermissionError` unless `plan.approved`. For each non-excluded entry and each matching `CoreObject`: copy NIfTI (and `.bval`/`.bvec`) to `schema.filename(...)`, write `scrub_sidecar(sidecar)`; add `run-<n>` when two objects would get the same name; write `dataset_description.json` (`Name: plan.dataset_name`, `BIDSVersion: "1.11.2"`, `GeneratedBy: [{"Name": "brainlife.io/aimport"}]`), `README.md` from `plan.readme` (when non-empty), `participants.tsv` (`participant_id`, `age`, `sex` from DICOM `PatientAge`/`PatientSex`, `n/a` when absent), `sub-*/[ses-*/]sub-*_scans.tsv` with `acq_time` = acquisition datetime shifted by `key.date_offset_days`, and `IntendedFor` on fmap sidecars as BIDS URIs (`bids::sub-01/func/...`) for func/dwi in the same session. `PatientAge`/`PatientSex` are read here with pydicom from DICOMs under `input_dir` whose `PatientID` matches the subject's `PatientInfo`, not carried in `ScrubbedSeries`.

- [ ] **Step 1: Write the failing tests**

```python
def test_refuses_unapproved(...):  with pytest.raises(PermissionError): write_bids(unapproved, ...)
def test_layout(...): assert (out / "sub-01/anat/sub-01_T1w.nii.gz").exists()  # fixture-specific names
def test_no_identifiers_in_output(planted...):
    for f in out.rglob("*"):
        if f.suffix in {".json", ".tsv"}: assert not PLANTED & tokens(f.read_text().lower())
def test_dates_shifted_intervals_kept(...): # two sessions → acq_time difference equals original difference
def test_participants_age_sex(...): ...
def test_key_never_in_output(...): assert not list(out.rglob("*aimport-key*"))
```
- [ ] **Step 2–4:** run (FAIL) → implement → run (PASS).
- [ ] **Step 5: Commit** `git commit -m "aimport: BIDS writer"`

---

### Task 11: Defacing

**Files:**
- Create: `aimport/src/aimport/deface.py`, `aimport/tests/test_deface.py`

**Interfaces:**
- Produces: `deface(bids_dir: Path, plan: Plan, method: Literal["pydeface","quickshear"], pre_deface_dir: Path) -> dict[str, Path]`: for each entry with `deface=True`, moves the original to `pre_deface_dir/<same relative path>` (must be outside `bids_dir`; the server passes `work_dir/pre-deface`), writes the defaced image in place, and returns `{entry_id: original_copy_path}` for before/after previews. Commands follow `handler/deface.sh` (`pydeface --force <in> --outfile <out>`; quickshear with `fslreorient2std` + mask as there). Timeout 600 s per image → raises `DefaceError(entry_id)`.

- [ ] **Step 1: Write the failing docker test**: on the T1w from the fixture run, after `deface`, the output differs from the original, has the same shape and affine, and the original is not under `bids_dir`.
- [ ] **Step 2–4:** run (FAIL) → implement → run (PASS).
- [ ] **Step 5: Commit** `git commit -m "aimport: defacing"`

---

### Task 12: BIDS validation (v1.11.2)

**Files:**
- Create: `aimport/src/aimport/validate.py`, `aimport/tests/test_validate.py`

**Interfaces:**
- Produces:
  - `@dataclass ValidationResult: ok: bool; errors: list[dict]; warnings: list[dict]; validator_version: str; bids_version: str`
  - `validate_bids(bids_dir: Path) -> ValidationResult`: runs `bids-validator-2 <bids_dir> --json --schema file:///opt/bids-schema/schema.json` (confirm flag names against `--help` of the pinned version), parses JSON issues by severity; `ok = not errors`.

- [ ] **Step 1: Write the failing docker tests**: writer output from Task 10 → `ok is True`, `bids_version == "1.11.2"`; same output with `dataset_description.json` deleted → `ok is False`.
- [ ] **Step 2–4:** run (FAIL) → implement → run (PASS).
- [ ] **Step 5: Commit** `git commit -m "aimport: BIDS validation against v1.11.2"`

---

### Task 13: Loopback API

**Files:**
- Create: `aimport/src/aimport/server.py`, `aimport/src/aimport/__main__.py`, `aimport/tests/test_server.py`

**Interfaces:**
- Consumes: everything above.
- Produces: `create_app(input_dir: Path, work_dir: Path, keys_dir: Path, token: str, allowed_origins: list[str]) -> FastAPI` and `python -m aimport serve --input /in --work /work --keys /keys --port 8765 --token <t> --origin https://brainlife.io --origin http://localhost:5173` (binds `0.0.0.0` inside the container; `bl aimport` publishes it as `127.0.0.1:<port>`). State lives in `work_dir` (`plan.json`, `status.json`), so a restart resumes.

| Method & path | Body / result |
|---|---|
| `POST /scan` | `{project_id, existing_subjects: [str], target}` → 202; runs Tasks 3, 5, 6, 9 in a background thread; writes `plan.json` |
| `GET /status` | `{stage: "idle"\|"scanning"\|"planned"\|"executing"\|"validated"\|"failed", message, output_dir?, validation?}` |
| `GET /events` | Server-Sent Events of `{stage, message}` lines |
| `GET /plan` | the `Plan` as JSON |
| `PATCH /plan` | `{edits: [...], dataset_name?, readme?}` → `Plan.apply_edits`; dataset fields are set directly, set `metadata_source="person"` and `approved=False`; 422 on bad ids |
| `POST /approve` | `{deface_method}` → `approved=True` |
| `POST /execute` | 409 unless approved; runs Tasks 10, 11, 12; final `output_dir` is `work_dir/output/bids` |
| `GET /preview/{entry_id}?which=original\|defaced` | NIfTI bytes |

Every route checks `Authorization: Bearer <token>` (401 otherwise, constant-time compare). CORS for `allowed_origins` only, and answers preflights with `Access-Control-Allow-Private-Network: true`.

- [ ] **Step 1: Write the failing tests** (FastAPI `TestClient`, pipeline functions monkeypatched to fast fakes):

```python
def test_requires_token(client): assert client.get("/plan").status_code == 401
def test_execute_requires_approval(authed): assert authed.post("/execute").status_code == 409
def test_restart_keeps_edits(tmp_path):
    a = authed_client(tmp_path); a.post("/scan", json=SCAN); wait_planned(a)
    a.patch("/plan", json={"edits": [{"id": first_id(a), "suffix": "T2w"}]})
    b = authed_client(tmp_path)   # new app, same work_dir
    assert entry(b, first_id(a))["suffix"] == "T2w"
def test_private_network_preflight(authed):
    r = authed.options("/plan", headers={"Origin": "https://brainlife.io",
        "Access-Control-Request-Method": "GET", "Access-Control-Request-Private-Network": "true"})
    assert r.headers["access-control-allow-private-network"] == "true"
def test_no_identifiers_in_api(planted_app): # /status, /plan, /events bodies contain no PLANTED term
```
- [ ] **Step 2–4:** run (FAIL) → implement → run (PASS).
- [ ] **Step 5: Commit** `git commit -m "aimport: loopback API"`

---

### Task 14: End-to-end leak test and docs

**Files:**
- Create: `aimport/tests/test_end_to_end.py`
- Modify: `aimport/README.md`, `README.md` (one paragraph pointing to `aimport/`)

- [ ] **Step 1: Write the docker test**: start the server in-process on planted `dcm_qa` data with a `Recorder` LLM client returning a valid guess, `POST /scan`, `POST /approve`, `POST /execute`; assert `stage == "validated"`, validation `ok`, and that no `PLANTED` term appears in: every recorded LLM call, every file under `output_dir` (text files by content; all files by path), every API response body except `/preview`.
- [ ] **Step 2: Run** `docker run --rm -v $PWD/aimport:/src brainlife/aimport:dev pytest -m docker /src/tests` — expect all docker tests PASS; `uv run pytest -m "not docker"` on the host — expect PASS.
- [ ] **Step 3: Write** `aimport/README.md`: build commands, `serve` usage, env vars (`AIMPORT_MODEL`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `OLLAMA_BASE_URL`, `DASHSCOPE_API_KEY`), what the agent does at each step, pinned validator version and spec commit, what is and isn't uploaded, how to run tests.
- [ ] **Step 4: Commit** `git commit -m "aimport: end-to-end leak test and docs"`

---

## After this plan

Separate plans, written once this engine's API is merged: `cli` (`bl aimport`: run the image, terminal review, datatype validators on the host, upload via the `bl bids upload` / `bl data upload` paths) and `brainlife-lite` (`/aimport` page).
