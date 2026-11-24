# aimport

brainlife.io/aimport is a local, agentic data importer: you point it at a folder of neuroimaging
data on your own computer, it works out what each series is, converts the data to BIDS, strips
identifiers and defaces the images, validates the result, and only then is anything uploaded to
brainlife.io. It lives in the ezBIDS repo and reuses ezBIDS's mapping, conversion and defacing tools,
but everything runs on your machine, so raw DICOMs with identifiers are never uploaded.

This directory is the engine: a Docker image and a small HTTP API on your own computer. The command
`bl aimport` and the brainlife-lite `/aimport` page that drive it are separate, upcoming work (see
"What's next"); until then you drive the API directly, as shown below.

## What aimport guarantees

- **Never leaves the machine:** your input folder (mounted read-only), the original DICOM headers and
  paths, the pre-defacing images, the pseudonym key, and every identifying value found in headers or
  tables.
- **What a language model sees:** only a de-identified summary of each series (description, protocol,
  acquisition parameters, with every known identifier replaced by `[x]`). Never pixels, raw headers or
  original file paths. With no model configured, nothing is sent anywhere and the built-in heuristics do the work.
- **What is uploaded** (by the front ends, later): only the validated, de-identified output folder.
  Never the source folder, the pseudonym key or the original images.
- **Review:** nothing is written to the output until a person has seen the plan and approved it. The
  agent only proposes: every guess, subject ID, defacing choice, ancillary file and README text can be
  edited, and an edit sets the plan back to not approved.
- **Validation:** the output must pass the BIDS validator before it counts as done (stage `validated`;
  with validator errors the stage is `invalid`). A failed run leaves no output folder to upload: what it
  wrote is moved to `<work>/output/bids.failed`.
- **Limits:** redaction works from the identifiers the engine can find; see "Known limitations" below for
  what it cannot catch.

An end-to-end test (`tests/test_end_to_end.py`) plants names, IDs, birth dates and institutions in real
DICOMs and in ancillary tables, runs the whole API, and checks that none of the planted or dataset-native
identifiers appears in any model request, any output file (by path and by content, including compressed
tables and NIfTI headers) or any API response.

## Requirements

- Docker. The image is built locally and never pushed.
- Disk: the work folder holds the staged input, the converted images, the output and the pre-defacing originals.
- Apple Silicon: the image is `linux/amd64`, so it runs under emulation and is slower. Defacing is the
  slow step: `pydeface` takes about 6 minutes per T1 there and `quickshear` about 40 seconds. On Intel or Linux
  amd64 hosts both are much faster. Always pass `--platform linux/amd64`.

## Build the image

From the repo root:

```
git submodule update --init bids-specification aimport/bids-specification
docker build --platform linux/amd64 -t ezbids-handler:local handler/
docker build --platform linux/amd64 -t brainlife/aimport:dev -f aimport/Dockerfile .
```

## Run the engine

Pick three folders on the host: your data (never modified), a work folder (intermediates, the output
and the pre-defacing originals; must not overlap the others), and a keys folder (the pseudonym key; keep
it outside the work folder). Then:

```
export AIMPORT_TOKEN=$(openssl rand -hex 24)
docker run --rm --platform linux/amd64 \
  -e AIMPORT_TOKEN -e ANTHROPIC_API_KEY \
  -p 127.0.0.1:8765:8765 \
  -v /path/to/data:/data:ro -v /path/to/work:/work -v /path/to/keys:/keys \
  brainlife/aimport:dev \
  python -m aimport serve --input /data --work /work --keys /keys --host 0.0.0.0 --port 8765
```

- Publish the port on `127.0.0.1` only, as above. The token is the only other protection, so never
  write `-p 8765:8765` (which listens on every network interface). Inside the container `--host 0.0.0.0` is
  allowed because `AIMPORT_IN_CONTAINER=1` is set by the image.
- Every request needs `Authorization: Bearer $AIMPORT_TOKEN`. Pass the token in the environment
  (`AIMPORT_TOKEN`), not with `--token`, which shows in the process list.
- Requests must carry a Host header of `127.0.0.1:<port>`, `localhost:<port>` or `[::1]:<port>` (anything
  else gets 421, against DNS rebinding). If you publish a different host port than `--port` (for
  example `-p 127.0.0.1:9000:8765`), use `--host-allow` (repeatable). It **replaces** the defaults, so list
  every name the client may use, e.g. `--host-allow 127.0.0.1:9000 --host-allow localhost:9000`.
- Outside the container, `--host` accepts only loopback addresses (`127.0.0.1`, `::1`, `localhost`); any
  other bind address needs `AIMPORT_IN_CONTAINER=1`.
- `--origin https://...` (repeatable) allows a web page at that origin to call the API (CORS).
- The server keeps its state in the work folder, so a restart resumes from the saved plan.

## The workflow

All examples use `T="Authorization: Bearer $AIMPORT_TOKEN"` and `U=http://localhost:8765`.

1. **Scan.** Runs ezBIDS on the staged input, asks the model about the series, builds the plan. The
   `project_id` names the pseudonym key (letters, digits, dots, dashes, underscores); `existing_subjects`
   lists subject IDs already in the brainlife project so new IDs do not collide; `existing_sessions` (subject
   ID to its session labels already in the project, e.g. `{"01": ["1", "2"]}`) does the same for session
   labels; `target` is `bids` (default) or `datatypes`.

   ```
   curl -s -X POST $U/scan -H "$T" -H 'Content-Type: application/json' \
     -d '{"project_id": "my-project", "existing_subjects": [], "target": "bids"}'
   ```

2. **Wait.** `GET /status` gives `stage` (`idle`, `scanning`, `planned`, `executing`, `validated`,
   `invalid`, `failed`), a message and warnings. `GET /events` is a server-sent-events stream of the same
   changes (it ends at `planned`, `validated`, `invalid` or `failed`). While a run is busy, editing or starting another gets 409.

   ```
   curl -s $U/status -H "$T"
   curl -sN $U/events -H "$T"
   ```

3. **Read the plan.** `GET /plan` returns the series entries and the ancillary files.

   ```
   curl -s $U/plan -H "$T"
   ```

   Fields of a series entry a reviewer can edit: `subject`, `session`, `datatype`, `suffix`, `entities`
   (for example `{"task": "rest", "run": "1"}`), `deface`, `exclude`, and the brainlife mapping
   (`brainlife_datatype`, `brainlife_tags`). Every other field is read-only and an edit to it is refused
   (422): `id`, `series_idx`, `subject_idx`, `session_idx`, `deface_opt_out` (set when a reviewer turns
   defacing off for an anatomical image; without it the writer refuses to write that image undefaced),
   `brainlife_by_person` (set when a reviewer sets the brainlife mapping; later edits keep that mapping
   until the entry's `datatype`, `suffix` or `entities` change), and
   the context the engine derives again after every edit: `source` (`heuristic`, `agent`, `person` or `none`), `confidence`, `reason`,
   `agent_note` (when the agent disagrees with the heuristic), `status` (`ok`, `unknown`, `unsupported`,
   `excluded_by_default`; secondary-capture and report series are excluded by default because identifiers
   can be burned into pixels). Plan-level fields: `dataset_name`, `readme`, `dataset_description`
   (Authors, License, Funding, EthicsApprovals, ReferencesAndLinks, DatasetDOI, HowToAcknowledge,
   Acknowledgements), `deface_method`, `warnings`.

4. **Edit.** `PATCH /plan` takes any of `edits`, `ancillary_edits`, `dataset_description`, `dataset_name`
   and `readme`. Edits are applied all or nothing; a bad one answers 422 and changes nothing. A `subject`
   edit renames that subject in every entry; an ID the key holds for another person, or one in
   `existing_subjects`, is refused, and the new ID is recorded in the pseudonym key when the plan is
   executed (so a later import of that person gets it).

   ```
   curl -s -X PATCH $U/plan -H "$T" -H 'Content-Type: application/json' \
     -d '{"edits": [{"id": "<entry id>", "entities": {"task": "rest"}, "exclude": false}],
          "dataset_name": "Resting-state pilot", "readme": "Pilot scans, 10 participants."}'
   ```

5. **Ancillary files.** The input's non-imaging files (participants, phenotype, README, CHANGES, LICENSE,
   CITATION, inherited sidecars, events, folders) are listed in the plan as `ancillary` entries with an
   `action` (`keep`, `drop`, `edit`), per-column actions for tables (`keep`, `drop`, `shift_date`) and
   `flags` explaining what the engine noticed. `GET /ancillary/<id>` shows the de-identified content as it
   will be written, with the reviewer's action, column choices and edited content applied (`content` is
   null for a dropped, locked or folder entry). Locked entries may only be dropped.

   ```
   curl -s $U/ancillary/a8 -H "$T"
   curl -s -X PATCH $U/plan -H "$T" -H 'Content-Type: application/json' \
     -d '{"ancillary_edits": [{"id": "a8", "columns": {"notes": "drop"}},
                              {"id": "a3", "content": "Plain text of the README"}]}'
   ```

6. **Approve.** Choose the defacing method here (see below). Any later edit un-approves the plan.

   ```
   curl -s -X POST $U/approve -H "$T" -H 'Content-Type: application/json' -d '{"deface_method": "pydeface"}'
   ```

7. **Execute.** Writes the BIDS output, defaces, validates. Poll `/status` or follow `/events` until
   `validated` (no validator errors), `invalid` (the output was written but the validator reported errors;
   it must not be uploaded: fix the plan and execute again) or `failed`. After `validated` or `invalid` the
   status has `output_dir`, `validation` with `ok`, error and warning counts and the issues, and `manifest`, the
   output files of each plan entry (`{entry_id: [paths relative to output_dir]}`). The output
   folder is `<work>/output/bids`; the pre-defacing originals go to `<work>/pre-deface`, outside it. When a
   run fails, what it wrote is moved to `<work>/output/bids.failed` (replacing an earlier one; named in the
   status message, never to be uploaded) and `<work>/output/bids` no longer exists. A failed scan names
   `<work>/ezbids.log`, where ezBIDS's own output is kept. Only the plan of the last scan can be executed: a
   new scan removes the previous plan, even if the scan then fails.

   ```
   curl -s -X POST $U/execute -H "$T"
   ```

8. **Preview.** After `validated` or `invalid`, `GET /preview/<entry id>?which=defaced|original&index=0` returns the image
   file (for a viewer such as NiiVue), so you can compare before and after defacing. This is the only route
   that returns image data, and only to this computer.

   ```
   curl -s "$U/preview/<entry id>?which=original" -H "$T" -o original.nii.gz
   ```

## AI model settings

The model is chosen with one setting, `AIMPORT_MODEL`. The default is `claude-opus-5-5`.

| `AIMPORT_MODEL` starts with | Provider | Environment needed |
|---|---|---|
| `claude` | Anthropic | `ANTHROPIC_API_KEY` |
| `gpt`, `o1`, `o3` | OpenAI | `OPENAI_API_KEY` |
| `qwen` | Qwen through Ollama or DashScope | `OLLAMA_BASE_URL` (a local model: nothing leaves the machine) or `DASHSCOPE_API_KEY` |

Pass the variables into the container with `-e` (for a local Ollama from Docker Desktop,
`OLLAMA_BASE_URL=http://host.docker.internal:11434`). The model sees only the scrubbed view described
above, once per scan for classification and once to draft the dataset name and README. Whatever text it
returns goes through the same redaction before it is kept. If the model is not configured, or its answer
is not valid BIDS, the series keep the heuristic guess (or are marked `unknown` for the reviewer) and the
scan still finishes.

## De-identification

What the engine does, deterministically and without a model:

- Drops identifying fields following DICOM PS3.15 (a curated subset), and institution and
  operator names. Sidecars keep only acquisition parameters.
- Redacts every identifying header value (name, ID, birth date, institution) wherever it also appears in
  free text: series descriptions, protocol names, folder and file names, table cells, README text.
  Redacted text shows as `[x]`.
- Replaces subject IDs with pseudonyms; inputs already named `sub-*` keep their IDs.
- Shifts acquisition and table dates by a fixed offset per subject; intervals are kept.
- Keeps age and sex (in `participants.tsv`); ages above 89 are written as 89 (HIPAA).
- Clears NIfTI header text fields (`descrip`, `aux_file`, and the other text fields).
- Excludes secondary-capture and report series by default and flags them.
- Defaces anatomical images.

### The pseudonym key

The key (original ID to pseudonym, each subject's date offset, and each subject's session labels per
study) is one file per project, `<project_id>.aimport-key.json`, in the keys folder (mode 0600), so a later
import of the same person reuses their ID and offset, the same study keeps its session label, and a new
study gets the next free label (never one the key or `existing_sessions` already holds). A study is
recognised by its StudyInstanceUID, or by its shifted scan date when the UID was removed. The key format is
version 2; a version-1 key (from an earlier aimport, without session records) is refused with a clear error. **Keep it safe and back it up: it is the only way back to the real identities,
and it is never uploaded or written to the output** (the writer refuses to finish if a key file is found in the
output). A lock file beside it stops two imports into the same project from running at once: the second
gets 409 until the first finishes.

### Defacing

Set `deface_method` at approval; entries with `deface: true` (by default the anatomical images) are defaced.

- `pydeface` (default): registers a face template with FSL flirt. Most robust across contrasts and fields of
  view; minutes per image. Use it for the final upload.
- `quickshear`: ROBEX brain mask, then quickshear. Faster (about 40 seconds on Apple Silicon under
  emulation); a good choice for a quick check, or when pydeface fails on an unusual field of view.

Defacing is lossless outside the face: the tool's output only decides which voxels are face, those are
zeroed in the original's stored data, and every other voxel stays byte-identical (affine, shape and data type
kept). Sanity bounds reject a result that removes more than 60% of the non-zero voxels or is not a
valid NIfTI-1 image, and fail the run rather than keep a bad face mask. The originals are moved to
`<work>/pre-deface`, outside the output.

### Ancillary and metadata files

Tables are de-identified, not copied: `participant_id` values are rewritten to the pseudonyms; rows for
people who are not in this import are dropped (if no row can be linked to an imported subject the rows
are dropped and only the column descriptions are kept); columns that look identifying (name, birth date,
MRN or ID, address, email, phone, free-text notes) are dropped by default and flagged; date columns are
shifted; every text cell is redacted. The README, dataset description, sidecars and events files are
redacted. `sourcedata/` and `derivatives/` are never kept, and `code/`, `docs/` and `stimuli/` are kept
only if the reviewer opts in, with text files redacted. Three behaviours to know in review:

- **Typed text is redacted when accepted.** Anything a reviewer types (README, dataset name, dataset
  description values, edited ancillary content) is redacted with the run's identifying terms before it is
  stored, so `plan.json` and every response hold `[x]` instead of the identifier.
- **ASL is excluded by default.** `perf` `asl` (and `m0scan`, `aslcontext`) series are excluded with the reason
  "ASL needs aslcontext.tsv and labeling metadata the importer cannot derive yet", unless the input supplies an
  `*_aslcontext.tsv` (the check is for any such file in the input, not per run).
- **One README.** If the input has a README, its de-identified text becomes the plan's README (the agent drafts
  one only when there is none) and the README entry is dropped by default with the reason "used as the dataset
  README", so it is not written twice. If you set that entry back to keep, the supplied file is written as is
  and replaces the plan's README.

Entries the validator would reject for this
import (for example phenotype rows of people who are not imported, or a top-level sidecar with no matching
image) are better dropped in review; the validation result tells you which.

### Known limitations

- A name that appears **only in free text**, with no match in any header or table the engine read, cannot be
  detected: redaction works from known identifiers. Read the README, notes and descriptions in review.
- Columns a reviewer **explicitly keeps** (against the default drop) are only redacted for known
  identifiers; other personal text in them may remain. The plan flags this.
- NIfTI-2 files are rejected (dcm2niix and this engine write NIfTI-1).
- `derivatives/` is out of scope for phase 1 and never imported.
- `bet` (FSL) is not in the image; defacing uses `pydeface` or `quickshear` only.
- Session label edits are not recorded in the pseudonym key (subject ID edits are): a later import of the
  same study gets the label the key recorded at scan time.
- `<work>/ezbids.log` (ezBIDS's own output, kept for troubleshooting) holds original paths and names, like the
  input; it stays in the work folder and is never uploaded or returned by the API.
- Phase 1 covers MRI and PET (anat, func, dwi, fmap, perf, pet) from DICOM and NIfTI; other modalities come in later phases.

## BIDS version, validator and the brainlife mapping

- Output follows **BIDS v1.11.2** (the `aimport/bids-specification` submodule at `fbe1af9a`, exported to the
  image as `/opt/bids-schema/schema.json`) and is validated with `@bids/validator` **2.4.1** (see the image
  notes below). Any validator error makes the stage `invalid`, not `validated`; warnings are listed.
- `src/aimport/data/bids_brainlife_map.yaml` maps each BIDS datatype and suffix to a brainlife datatype and tags (rows are
  `active`, `planned` or `draft`). BIDS types with no brainlife datatype get a draft in
  `src/aimport/data/datatype_drafts/`, generated by `tools/draft_datatypes.py` (see "Draft brainlife
  datatypes" below).

## Image details

- ezBIDS lives at `/app` (its `bids-specification` submodule at the pinned `3537e9ed`); aimport is in `/opt/aimport-venv` (Python 3.11), last on `PATH`, so system `python3` stays 3.8 and `pytest` is the venv's.
- `aimport/bids-specification` (submodule, BIDS v1.11.2 at `fbe1af9a`) is exported to `/opt/bids-schema/schema.json` with `bst export`.
- BIDS validator: `@bids/validator` **2.4.1** (Deno 2.5.6), run through the `bids-validator-2` wrapper. That release bundles an older schema (it flags `BIDSVersion` 1.11.2 as unknown), so the wrapper defaults `--schema file:///opt/bids-schema/schema.json` unless `--schema`/`-s` is given. Works offline. Useful flags: `--format json` (`--json` is deprecated), `--schema <URL>`, `--ignoreNiftiHeaders`, `-o <file>`.
- Test data: `tests/fixtures/fetch_dcm_qa.py` fetches `neurolabusc/dcm_qa_xa30` at a pinned commit and plants fake PHI.
- Python packages are installed exactly as `uv.lock` pins them (with hashes); the Deno download is checked against its sha256.

## Defacing details

`aimport.deface.deface` defaces the images of plan entries with `deface=True` (found through the manifest `write_bids` fills), moving the originals to a folder outside the BIDS folder and keeping affine and shape. Choose with `Plan.deface_method`:

- `pydeface` (default): registers to a face template with FSL flirt. Most robust across contrasts and fields of view; minutes per image. Use it for the final upload.
- `quickshear`: ROBEX brain mask, then quickshear. Needs no registration (about 40 seconds per T1 under emulation on Apple Silicon); a good choice when pydeface fails on an unusual field of view.

The tool's output only decides which voxels are face: those are zeroed in the original's stored data and every other voxel stays byte-identical (no re-quantisation).

Unlike ezBIDS, no `fslreorient2std` is applied. Docker tests: `quickshear` runs under `-m docker`; the pydeface test is `-m docker_slow`.

## Draft brainlife datatypes

BIDS raw-data types that have no brainlife datatype get a draft in `src/aimport/data/datatype_drafts/` (warehouse `Datatypes` shape, named `neuro/<datatype>/<suffix lowercased>`), plus a `status: draft` row in `src/aimport/data/bids_brainlife_map.yaml`. Drafts are to be registered later through a PR to brainlife; check the registry for an existing datatype first. The engine ignores them for uploads (`to_brainlife` returns `(None, [])`; `draft_for` returns the draft name).

Regenerate after changing the schema submodule or an active/planned row (output is deterministic, so no change means no diff):

```
cd aimport && uv run python tools/draft_datatypes.py --write-yaml
```

`--schema PATH`, `--out DIR` and `--yaml PATH` override the defaults; without `--write-yaml` the YAML rows are printed. A pair is covered (no draft) when an active or planned row has the same BIDS datatype and either the same suffix or no suffix (the `micr` row, keyed by extension, covers every micr suffix).

Rules for the files of a draft:

- One entry per schema extension. Directory extensions (ending in `/`) become `dirname` entries. Wildcard (`.*`) and bare `/` extensions name no concrete file and are skipped; the only effects are that `meg/headshape` lists just `.pos`, and that the `/` extension of `meg/meg` is not drafted (that pair has planned `.ds`/`.fif` rows, so it gets no draft anyway; other MEG formats are not drafted).
- Data formats: non-sidecar extensions (sidecars are `.json`, `.bval`, `.bvec`) are grouped into alternative formats. `.nii.gz`/`.nii`, BrainVision `.vhdr`+`.eeg`+`.vmrk` and EEGLAB `.set`+`.fdt` each count as one format; any other extension is a format of its own.
- A suffix with a single format requires the first extension of that format (e.g. `.nii.gz`). A suffix with several formats (e.g. NIfTI or OME-Zarr; `ieeg` `.edf`/BrainVision/`.mefd`/...) requires none of them; `desc` and the readme say "Exactly one of: ... must be present".
- `.json` is required when `rules.sidecars` has unconditional required metadata for the pair (selectors decidable from datatype, suffix, modality and extension only; entity- or sidecar-conditional entries are ignored). Otherwise it is optional. When a `.json` extension exists, `bids.maps` sets `json: <suffix>.json` on the main file of each format.
- The readme lists the other raw suffixes of the same BIDS datatype as related files; they are separate datatypes.
- `draft` and `bids_version` are extra keys for tooling; the warehouse model drops unknown keys at registration.

## Test datasets and running the tests

The datasets used, their pinned versions and the planted identifiers are listed in
[tests/DATASETS.md](tests/DATASETS.md).

Host (no Docker needed):

```
cd aimport && uv run pytest -m "not docker and not docker_offline and not docker_slow"
```

In the image (needs network the first time, to fetch the pinned test DICOMs, which are cached):

```
docker run --rm --platform linux/amd64 -v $PWD/aimport:/src \
  -v ~/.cache/aimport-dcm-qa:/tmp/aimport-dcm-qa-cache brainlife/aimport:dev pytest -m docker /src/tests
docker run --rm --platform linux/amd64 -v $PWD/aimport:/src brainlife/aimport:dev pytest -m docker_slow /src/tests  # pydeface, minutes
```

The end-to-end leak test is `tests/test_end_to_end.py` (about two minutes under emulation).

## What's next

`bl aimport` (the command-line front end: runs this image, shows the plan in the terminal, runs the
brainlife datatype validators on your host) and the brainlife-lite `/aimport` page (plan review with image
previews) are separate, upcoming work. **Uploading to brainlife.io happens there, not in this engine**: the
engine only produces the validated, de-identified output folder.
