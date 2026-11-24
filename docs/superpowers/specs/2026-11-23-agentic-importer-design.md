# Agentic data importer for brainlife.io — design

Date: 2026-11-23 (revised 2026-11-24)
Owner: Franco Pestilli

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
- One engine, two front ends: `bl import` on the command line, an Import page in
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
  the brainlife-lite Import page, approved by Franco on 2026-11-23.
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

1. **ezbids** — the engine, in a new `importer/` directory, plus a local Docker image
   built on the existing `handler/Dockerfile` toolchain (dcm2niix, pydeface,
   quickshear, ezBIDS core) with autobidsify and the v1.11.2 BIDS schema and validator
   added.
2. **cli** — `bl import`, which runs the engine image and drives it.
3. **brainlife-lite** — an Import feature (`src/features/Import/`) that talks to the
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
4. **Agent.** For series the heuristics leave unknown or low-confidence, run the
   autobidsify classify/plan stages on the scrubbed view only — never raw headers,
   pixels or original paths. Each mapping records its source (heuristic or agent), a
   confidence and a one-line reason.
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

- Default: a remote model (Claude or OpenAI) with the user's own API key, sent only
  the scrubbed view. autobidsify supports OpenAI and Ollama today; Claude support is
  added as a small provider, contributed upstream to autobidsify.
- Setting: a local model through Ollama, for sites that allow nothing to leave.
- Fallback: with no model configured, heuristics only; unknown series go to the
  reviewer marked unknown. The importer never fails for lack of a model.

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

- **CLI:** `bl import <folder> --project <id> [--target bids|datatypes] [--ui]`.
  Without `--ui` it prints the plan as a table and asks for approval in the terminal;
  with `--ui` it opens the brainlife-lite Import page (production address by default,
  configurable; tests use a local dev server).
- **Engine API:** a small HTTP API on `127.0.0.1` only, guarded by a random per-run
  token. Both front ends use it: get plan, edit plan, approve, run, stream progress,
  fetch previews.
- **Web page:** connects to the local API (port and token handed over by
  `bl import --ui`), shows the plan with NiiVue previews (including before/after
  defacing) and the same accept/edit/exclude controls. Image data reaches the browser
  only from the local engine.

### Release

The engine image is published under a fixed version tag by maintainers after merge;
each `bl` release pins the engine tag it works with. Nothing in this work deploys or
publishes.

### Tests that matter most

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
