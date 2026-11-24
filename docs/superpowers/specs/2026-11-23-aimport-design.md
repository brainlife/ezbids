# brainlife.io/aimport — agentic data importer — design

Date: 2026-11-23 (revised 2026-11-24)
Owner: Franco Pestilli
Name: brainlife.io/aimport — CLI `bl aimport`, web page at `/aimport`, engine image `brainlife/aimport`

## Intent

A researcher points the importer at a folder of neuroimaging data on their own
computer. An agent works out what each file or series is and maps the set to BIDS or
to brainlife.io datatypes. The data is converted, defaced and stripped of participant
identifiers, then validated, and only then uploaded to brainlife.io. It runs from the
command line or from a page in brainlife-lite.

Today the two paths each miss half of this. ezBIDS maps well but runs on a server,
so raw DICOMs (with identifiers) are uploaded before anything is removed.
`bl bids upload` uploads locally but needs a finished BIDS folder. The importer
puts ezBIDS-style mapping, an LLM agent for the cases heuristics miss, and the
existing upload path together on the user's machine.

## Goals

- Local folder in; validated, de-identified data in a brainlife project out.
- Cover every datatype in the BIDS specification v1.11.2 (anat, func, dwi, fmap, perf,
  pet, micr, eeg, meg, ieeg, nirs, emg, beh, motion, mrs, phenotype), delivered in
  phases (below).
- Two targets: a BIDS dataset (uploaded with the existing `bl bids upload` path) or
  brainlife datatype objects (uploaded with the `bl data upload` path).
- One engine, two front ends: `bl aimport` on the command line, an aimport page at `/aimport` in
  brainlife-lite.
- The agent proposes the whole mapping; a person approves it before any output is
  produced or uploaded. Approval can be one step for a whole dataset.
- Validation before upload against:
  - BIDS specification **v1.11.2** (commit `fbe1af9aa1fa1bb32811d0e5f4be4bee3130bc3b`),
  - the BIDS validator release matching that schema,
  - the brainlife.io datatype validator of every datatype being uploaded.

## Phases

The engine is built so each BIDS datatype is a module that recognises, converts and
de-identifies its own files. Later phases add modules; they do not change the shared
stages (scrub, plan, review, validate, upload).

1. **MRI and PET:** anat, func, dwi, fmap, perf, pet. Inputs: DICOM, NIfTI.
   Builds and proves every shared stage end to end, on ezBIDS's existing heuristics.
2. **Microscopy:** micr, including OME-Zarr (`.ome.zarr/`) and already-reconstructed
   PS-OCT volumes (BIDS `OCT` suffix). Maps to `neuro/ome-zarr` on the brainlife side.
3. **Electrophysiology and optical:** eeg, meg, ieeg, nirs, emg (autobidsify covers EEG
   and fNIRS; ezBIDS covers MEG).
4. **The rest:** beh, motion, mrs, phenotype.

Each phase ships as its own set of PRs. Phase 1 is the one to plan in detail now.

The BIDS → brainlife datatype mapping lives in one data file,
`aimport/src/aimport/data/bids_brainlife_map.yaml`, which the engine reads. Every phase
that adds a modality updates it in the same PR: rows move from `planned` to `active`
when the engine supports them, and new brainlife datatypes are added with the source
they come from (e.g. a line in `cli/bids-walker.js` or the warehouse datatype).

When a BIDS (datatype, suffix) has no brainlife datatype, the importer drafts one
instead of leaving it unmapped. The draft uses BIDS as the datatype: its name is
`neuro/<bids datatype>/<suffix, lowercased>` (e.g. `neuro/perf/asl`, `neuro/pet/pet`),
its `files` and `bids` export spec are the BIDS files for that suffix from the pinned
schema, and it follows the warehouse `Datatypes` model (`warehouse-next/api/models.js`).
Drafts are generated from the schema into `aimport/src/aimport/data/datatype_drafts/`
and listed in the mapping YAML with `status: draft`. They are registered later through a
PR; before that PR, each draft is checked against the live registry so no existing
datatype is duplicated. Until a draft is registered, the "datatypes" target shows the
draft name and excludes that series from upload; the BIDS target is unaffected.
Coverage continues past phase 1 until every BIDS datatype the schema defines is mapped
or drafted.

## Non-goals

- Replacing the hosted ezBIDS web service. It keeps running as it is.
- Reconstructing raw PS-OCT acquisitions (the `cmc_ps-oct_processing` pipeline).
  The importer takes reconstructed volumes.
- Server-side conversion of any kind.

## Anti-goals (failure even if it works)

- Any identifying data leaving the machine before de-identification. This includes
  what is sent to the LLM, not only what is uploaded.
- Uploading anything that failed validation.
- The agent applying a guess no person has seen.

## Constraints

- brainlife workspace rules (`~/git/brainlife/CLAUDE.md`): branch + PR for human
  review, one purpose per PR, tests first, no deploys, no new dependencies or
  patterns without approval. The new dependencies named here (autobidsify, the
  ezBIDS handler toolchain in a local image) are approved as part of this design.
- The workspace rule "new interface features are not in scope" has an exception for
  the brainlife-lite aimport page, approved by Franco on 2026-11-23.
- brainlife-lite conventions in its `AGENTS.md` (folder layout, one job per file,
  tests). NiiVue is pinned there at `1.0.0-rc.16`; brainlife-lite already has a Zarr
  thumbnail and maps S3 Zarr to datatypes (`MapS3DataToDatatypeDialog.tsx`).
- brainlife datatype validators are brainlife apps (`validator`, `validator_branch`
  on the datatype in `warehouse-next/api/models.js`). Example: `validator-neuro-anat/main`
  runs `singularity exec docker://brainlife/dipy:1.1.1 ./run.py` and reads brainlife's
  `config.json` (`_inputs`). The server re-runs the validator when an upload is
  finalized (`warehouse-next/api/controllers/dataset.js`).
- The spec pin moves off `3537e9ed` (ezBIDS's submodule pin, May 2022), which has no
  OME-Zarr. ezBIDS's own pin is not changed by this work.

## Approaches considered

1. **Python engine, called by both front ends (chosen).** Reuses ezBIDS's Python
   core (`handler/ezBIDS_core/ezBIDS_core.py`), its defacing (`handler/deface.sh`:
   quickshear, pydeface) and autobidsify (MIT, `pip install autobidsify`, staged
   ingest → classify → plan → execute → validate with a plan file). Cost: users need
   Docker (also needed to run datatype validators locally).
2. **Everything in the browser** (NiiVue's WebAssembly dcm2niix, BIDS validator in
   JS). Nothing to install, but datatype validators are containers, browser defacing
   is immature, and the CLI would need a second implementation. Rejected.
3. **Rewrite in Node inside the `bl` CLI.** Matches the CLI language but ports all of
   ezBIDS's mapping and creates a second copy that drifts. Rejected.

## Design

### Where the code goes (phase 1: three PRs, in order)

1. **ezbids** — the engine, in a new `aimport/` directory, plus a local Docker image
   built on the existing `handler/Dockerfile` toolchain (dcm2niix, pydeface,
   quickshear, ezBIDS core) with autobidsify and the v1.11.2 BIDS schema and validator
   added.
2. **cli** — `bl aimport`, which runs the engine image and drives it.
3. **brainlife-lite** — an aimport feature (`src/features/Aimport/`) that talks to the
   engine running on the user's machine.

### Engine stages

Everything runs locally inside the engine container, with the user's folder mounted
read-only and a separate work folder for intermediates and output.

1. **Scan.** Find data files and archives, read headers, group into series.
2. **Scrub metadata (deterministic, no LLM).** Build a de-identified view of the
   metadata (rules below). The agent and everything downstream use only this view.
3. **First guess.** The datatype module's heuristics (phase 1: ezBIDS core) map each
   series to a BIDS datatype, suffix and entities. ezBIDS maps from dcm2niix output, so
   conversion into the work folder happens here. Writing intermediates to the work
   folder before approval is allowed; producing the final output or uploading is not.
4. **Agent.** Works like autobidsify's agent, on the scrubbed view only (never raw
   headers, pixels or original paths): it reviews every series alongside ezBIDS's guess,
   confirms or disputes it, fills in entities such as task labels, resolves what the
   heuristics left unknown, and drafts the dataset name and README. Each mapping records
   its source (heuristic, agent or person), a confidence and a one-line reason;
   disagreements are kept as a note for the reviewer.
5. **Plan.** One plan file: per series, the BIDS path, the brainlife datatype and tags
   (same mapping as `cli/bids-walker.js`), proposed subject/session IDs, whether it
   will be defaced, confidence and reason.
6. **Review (human).** The plan is shown in the CLI or the web page. The person
   accepts all, edits entries, or excludes series. Nothing past this point runs without
   an approved plan.
7. **Execute.** Write BIDS (or datatype folders) from the approved plan, strip
   identifying fields from sidecars, deface anatomical images (method chosen at
   review; default pydeface, as ezBIDS offers).
8. **Validate.** BIDS validator against v1.11.2: any error blocks upload, warnings are
   shown. Then each brainlife datatype's validator, run locally as a pre-check (see
   below).
9. **Upload.** BIDS target: the `bl bids upload` path. Datatype target: the
   `bl data upload` path. Only the validated output folder is uploaded — never the
   source folder, the pseudonym key or original paths.

### LLM

- Backends: Claude, plus every provider autobidsify supports (OpenAI; Qwen via Ollama,
  REST or DashScope), selected with one setting. Default: Claude with the user's own
  key, sent only the scrubbed view.
- A local model through Ollama for sites that allow nothing to leave.
- With no model configured: heuristics only; unknown series go to the reviewer marked
  unknown. The importer never fails for lack of a model.
- Claude support is added inside aimport for now; contributing it upstream to
  autobidsify is a follow-up.

### De-identification rules

- Drop identifying DICOM tags per the PS3.15 basic confidentiality profile; drop
  institution and operator names.
- Redact any identifying header value (name, ID, birth date) wherever it also appears
  in free text: SeriesDescription, ProtocolName, folder and file names.
- Shift acquisition dates by a fixed offset per subject; keep intervals.
- Keep age and sex, in `participants.tsv`.
- Clear NIfTI header text fields (`descrip`, `aux_file`).
- Exclude secondary-capture and report-screen series by default and flag them to the
  reviewer (identifiers may be burned into pixels).
- Deface anatomical images.

### Ancillary and metadata files

Every non-imaging file BIDS v1.11.2 defines is supported, both when the user supplies it
and when the importer writes it, and the reviewer can edit it before upload:

- Core files: `dataset_description.json`, `README`, `CHANGES`, `LICENSE`, `CITATION.cff`,
  `genetic_info.json`.
- Tables with their JSON descriptions: `participants`, `samples`, `sessions`, `scans`
  (`.tsv` + `.json`), and `phenotype/*.tsv` + `phenotype/*.json`.
- Top-level (inherited) sidecars, e.g. `task-rest_bold.json`, and `*_events.tsv`/`.json`.
- Folders: `code/`, `docs/`, `stimuli/` are kept only if the reviewer opts in, with text files
  redacted; `sourcedata/` is never uploaded (it holds the raw, identifying data);
  `derivatives/` is out of scope for phase 1.

Tables are de-identified, not copied: `participant_id` values are rewritten to the
pseudonyms and rows for people not in this import are dropped; columns that look
identifying (name, birth date, MRN/ID, address, email, phone, free-text notes) are dropped
by default and flagged; date columns are shifted with the per-subject offset; every text
cell is redacted. The importer's own `age`/`sex` columns are merged with supplied ones (the
user's values win). In review the person can keep or drop each column, edit the JSON
descriptions (participants, phenotype), the README and the dataset description (authors,
license, funding, ethics). The BIDS validator checks all of it before upload.

### Subject IDs and the pseudonym key

- At review the engine proposes IDs that don't collide with subjects already in the
  target brainlife project; the person can change them. Inputs already named `sub-*`
  keep their IDs.
- The key (original → pseudonym) is kept per project in a folder the user chooses, so
  later imports of the same person reuse their ID. It is never uploaded.

### Datatype validators

- Run locally as a pre-check, in Docker, from the datatype's `validator` and
  `validator_branch`. A failure blocks that object.
- If a datatype has no validator, or its validator can't be run locally, the object is
  uploaded with a warning and the server's validation on finalize decides.

### Front ends

- **CLI:** `bl aimport <folder> --project <id> [--target bids|datatypes] [--ui]`.
  Without `--ui` it prints the plan as a table and asks for approval in the terminal;
  with `--ui` it opens brainlife.io/aimport (production address by default,
  configurable; tests use a local dev server).
- **Engine API:** a small HTTP API on `127.0.0.1` only, guarded by a random per-run
  token. Both front ends use it: get plan, edit plan, approve, run, stream progress,
  fetch previews.
- **Web page:** connects to the local API (port and token handed over by
  `bl aimport --ui`), shows the plan with NiiVue previews (including before/after
  defacing) and the same accept/edit/exclude controls. Image data reaches the browser
  only from the local engine.

### Release

The engine image (`brainlife/aimport`) is published under a fixed version tag by maintainers after merge;
each `bl` release pins the engine tag it works with. Nothing in this work deploys or
publishes.

### Tests that matter most

Every dataset used to test or validate the importer, in every phase (MRI and PET,
microscopy/OME-Zarr/PS-OCT, electrophysiology, the rest) and in every repo (`ezbids`,
`cli`, `brainlife-lite`), is recorded in `aimport/tests/DATASETS.md`: source, pinned
commit or version, contents, planted identifiers, which tests use it, and why it was
added or dropped.


- A synthetic DICOM set with planted identifiers in tags, in SeriesDescription and in
  folder names. Assert none appear in any LLM request, any output file, or anything
  handed to the upload step.
- Plan round-trip: the CLI and the web page produce the same approved plan for the
  same edits.
- Validation gate: an output with a BIDS error, and one failing a datatype validator,
  are not uploaded.
- Re-import: a second session for an existing subject gets the same pseudonym.

## Left to the builder

- The engine's internal module layout, the datatype-module interface, and the plan
  file format (autobidsify's `BIDSPlan.yaml` is a reasonable starting point).
- Which BIDS validator release matches the v1.11.2 schema.
- How brainlife-lite, served over HTTPS, reaches `http://127.0.0.1` across browsers
  (Chrome's Private Network Access preflight, Safari's mixed-content rules); if a
  browser can't, the engine may serve the same page itself.
- How each datatype validator is run outside brainlife (inputs, `config.json` shape),
  starting from `validator-neuro-anat`.
- Whether to call autobidsify as a library or through its CLI.
