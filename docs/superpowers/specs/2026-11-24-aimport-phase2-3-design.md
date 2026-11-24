# aimport phases 2 and 3: readers, de-identification and QA viewers — design

Extends `2026-11-23-aimport-design.md` (phases, shared stages, de-identification rules, the
mapping YAML and DATASETS.md rules all still hold). Written 2026-11-24 from three research
passes (brainlife-lite's Neuroglancer code; microscopy readers and viewers; electrophysiology and
optical readers and viewers). Sources are listed at the end.

## Intent

Phase 1 imports MRI and PET. Phases 2 and 3 add the next BIDS datatypes with the same
guarantees: nothing identifying leaves the computer, a person approves a plan, and only a
validated BIDS dataset is uploaded. The user asked for good readers and visualizers, and for
**Neuroglancer** to help check the data before upload (QA). Phase 3 needs a chosen viewer.

## Goals

- Phase 2, `micr`: vendor microscopy files and OME-TIFF/OME-Zarr in, BIDS microscopy out
  (OME-Zarr by default), including already reconstructed PS-OCT volumes (suffix `OCT`).
- Phase 3, `eeg`, `meg`, `ieeg`, `nirs`, `emg`: vendor recordings in, BIDS-accepted formats out.
- A **QA viewer** in the engine for every datatype: Neuroglancer for volumes (microscopy and MRI),
  a trace viewer for time series. It shows the data as it will be uploaded (de-identified), and,
  where something was removed (defacing), the original next to it.
- Mapping YAML rows move from `planned`/`draft` to `active` for what each phase supports, and
  every test dataset is recorded in `aimport/tests/DATASETS.md`.

## Non-goals and anti-goals

- No raw PS-OCT reconstruction (spectra to retardance/optic axis): labs reconstruct with their
  own code; aimport imports reconstructed volumes.
- No viewer page loaded from a third-party site, and no image or signal data sent anywhere for
  viewing. (Anti-goal: brainlife-lite's pattern of iframing Google's hosted
  `neuroglancer-demo.appspot.com` must not be used for local, pre-upload data.)
- No raw annotation, marker or OME-XML free text sent to the AI model.
- No Java in the default path (Bio-Formats is GPL and heavy); it is an optional fallback.

## Approaches considered (QA viewer)

1. **Engine serves its own viewer, same origin (chosen).** The Python `neuroglancer` wheel ships
   the built client (`neuroglancer/static/client/`, 2.40.1, Apache-2.0); the engine serves it and
   the data from `http://127.0.0.1:<port>`, so no CORS, no third-party page, and auth can be a
   cookie. Trace viewer: a small page with uPlot (MIT) fed by downsampled JSON windows.
2. Hosted Neuroglancer pointed at the loopback API: needs CORS, Private Network Access and a token
   in every data URL; the viewer code comes from Google at view time. Rejected.
3. Viv/Avivator for microscopy (can send a bearer header): good, but a second viewer stack for
   one modality, and the user asked for Neuroglancer. Kept as a later option.
4. Neurosift for time series: NWB only; converting EDF/FIF/SNIRF to NWB just to preview is
   weight without benefit. Rejected for phase 3; revisit if iEEG NWB output becomes common.

## Design

### QA viewer (shared, built first)

- **Routes** (engine API, loopback only, existing token rules):
  - `POST /viewer/session` (bearer) → a one-time code (random, 60 s, single use).
  - `GET /viewer/open?code=…` → sets an `HttpOnly; SameSite=Strict; Path=/` session cookie bound
    to this server run, redirects to the viewer page. The bearer token never appears in a URL.
  - `GET /viewer/ng/*` → the Neuroglancer client files from the installed wheel (pinned version,
    hash-locked in `uv.lock`).
  - `GET /viewer/traces/<entry id>` → the trace viewer page; `GET /qa/traces/<entry id>?t0&t1&ch`
    → a downsampled JSON window (≤ 64 channels, ≤ 4,000 points per channel).
  - `GET /qa/data/<entry id>/<path>` → files of that entry's output (NIfTI, OME-Zarr chunks) with
    `Range` support; `which=original` serves the pre-deface copy, as `/preview` does today.
  - Cookie or bearer accepted on `/viewer/*` and `/qa/*` only; all other routes keep bearer-only.
- **What is served**: only after `validated`/`invalid` (as `/preview`), only files listed in the
  output manifest, never `staged/`, `sourcedata/` or the key. Paths are checked against the
  manifest, not joined from the URL.
- **Neuroglancer state** is built by the engine (`aimport/viewer.py`), not the browser:
  - MRI: NIfTI layer, `|gzip:|nifti:` suffix, 1 mm dims, a 4-panel layout; the anatomical entry
    gets two layers (defaced and original) so a reviewer can toggle.
  - Microscopy: OME-Zarr layer (NGFF 0.4 via `zarr://`), one layer per channel with an additive
    blend and per-channel contrast windows from `omero` metadata (same approach as
    brainlife-lite's `generateOmeZarrNeuroglancerUrl`).
  - PS-OCT: reflectivity, retardance and optic-axis layers of the same sample, aligned.
- **Front ends**: `bl aimport` gains `v` at the approval prompt (opens the viewer for the plan
  after execute) and `--qa` (open it after validation, before upload); the brainlife-lite page
  later iframes the same local URLs.
- **Phase 3 viewer (picked)**: server-rendered PNGs with MNE (matplotlib Agg) for each recording,
  namely a 10 s trace snippet, the power spectrum, and a channel-type/bad-channel bar. Next to
  them goes the interactive uPlot trace page (pan/zoom by window requests), with channel picker,
  event markers (coded labels only), and HbO/HbR pairs for NIRS. Rendered from the de-identified
  output, titles carry the BIDS name, never the source file name.

### Phase 2: microscopy (`micr`)

- **Readers** (pure Python, default): `bioio` with `bioio-czi` (pylibCZIrw, LGPL-3), `bioio-nd2`,
  `bioio-lif`, and `tifffile` (TIFF stacks, OME-TIFF, SVS); `ome-types` for OME-XML.
  Formats needing Bio-Formats (VSI, OIB, IMS, others) are planned as `unsupported` with a clear
  message; an optional `bioformats2raw` (Java, GPL-2) image stage can be added later, run as a
  subprocess.
- **Writer**: `ngff-zarr` (MIT, Python ≥ 3.11) writes OME-Zarr **NGFF 0.5 / Zarr v3** with a
  multiscale pyramid and sharding by default, because the CMC data below (PS-OCT, exaSPIM) are
  already NGFF 0.5 / Zarr v3. NGFF 0.4 / Zarr v2 remains an option. The first plan task checks the
  pinned BIDS validator accepts 0.5; if it does not, 0.4 becomes the default until it does.
  Small 2D images may stay OME-TIFF. An input that is already OME-Zarr is rewritten (metadata
  rebuilt from the allowlist) without re-encoding chunks where possible.
- **Large data is never copied locally** (PS-OCT, VISoR, exaSPIM; the user's rule). For these:
  - no staging copy: the reader opens the input in place (read-only mount), or reads a remote
    store (`s3://`, `https://`) through fsspec with range requests, without downloading it;
  - when the input is already OME-Zarr (v2 or v3), the output is a **reference dataset**:
    aimport writes only the new, de-identified metadata (`zarr.json`/`.zattrs`, sidecars,
    `samples.tsv`, names) locally, plus a chunk map `{output chunk path: source chunk path or URL}`.
    The upload streams each chunk from its source to brainlife.io, so chunk data never lands on
    local disk. The preflight treats the chunk map as the only allowed source list, never
    symlinks.
  - When conversion is unavoidable (TIFF tiles to OME-Zarr), it streams block by block. The only
    local copy is the converted output, and the user is told the size first. A remote
    destination (the brainlife project's storage) can be the write target, so even that copy is
    skipped.
  - The QA viewer reads the same sources through `/qa/data`, which proxies range reads from the
    chunk map. Neuroglancer never needs the full volume.
- **Scale**: inputs reach gigabytes per file (VISoR raw TIFF tiles, about 4.3 GB) and terabytes
  per dataset (exaSPIM). Conversion streams with dask (block-wise reads, never a whole volume in
  memory), writes sharded chunks, and reports progress per tile. Planning reads metadata and a
  coarse level only.
- **Naming**: `sub-<label>[_ses-<label>]_sample-<label>[_acq-…][_stain-…][_run-…][_chunk-…]_<suffix>.ome.zarr`,
  suffix from the BIDS list (`TEM, SEM, uCT, BF, DF, PC, DIC, FLUO, CONF, PLI, CARS, 2PE, MPE, SR,
  NLO, OCT, SPIM, XPCT`). `samples.tsv` is required and is written from the plan.
  `PixelSize`/`PixelSizeUnits` are required sidecar fields, filled from the reader.
- **PS-OCT**: one OME-Zarr per reconstructed contrast with `acq-reflectivity`, `acq-retardance`,
  `acq-opticaxis`, suffix `OCT`. The sidecar records units, whether retardance or birefringence
  is stored, and the optic-axis convention (custom fields until BIDS defines them). Readers:
  NIfTI (nibabel), `.mat` (scipy/h5py for v7.3), TIFF stacks. A per-lab adapter hook takes the
  rest. aimport does not reconstruct raw spectra.
- **De-identification**: the OME-XML is **rebuilt from an allowlist** with ome-types (dimensions,
  pixel sizes, channel names/wavelengths, objective magnification/NA), not cleaned field by
  field. Dropped: Experimenter(s), groups, instrument and detector serials, `AcquisitionDate`
  (shifted with the subject's offset into `scans.tsv` instead), image/dataset/project names,
  descriptions, StructuredAnnotations, original-metadata maps, ROIs. TIFF tags Artist, Software,
  HostComputer, DateTime and ImageDescription are dropped. Slide label and macro images (SVS,
  VSI) are never written (identifiers can be in the pixels, like secondary-capture DICOM).
  The OME-Zarr `.zattrs`/`omero` block is written by aimport, not copied.
- **Agent summary**: dimensions, pixel size, channel count and wavelengths, objective, modality
  hints from the reader. No names or descriptions.
- **brainlife mapping**: `micr/*` → `neuro/ome-zarr` (with the suffix as a tag); the planned row
  becomes active.

### Phase 3: electrophysiology and optical

- **Readers**: MNE-Python (BSD-3) for all its formats with `preload=False`: EDF/BDF, BrainVision,
  EEGLAB, Neuroscan CNT, EGI, Nihon Kohden, Persyst, GDF, MEF3, NeuroScan, FIF, CTF, BTi, KIT,
  NIRx, Hitachi, SNIRF (continuous wave). `h5py` for SNIRF metadata and edits. `pynwb` for NWB
  iEEG metadata. `neo` only as a fallback for formats MNE lacks. Artinis `.oxy` and Shimadzu are
  `unsupported` (export to SNIRF first). ezBIDS keeps handling MEG on the web; aimport uses MNE
  directly.
- **Writer**: MNE-BIDS `write_raw_bids` (BSD-3, Python ≥ 3.11). It copies BIDS-legal formats and
  converts the rest: EEG/iEEG to BrainVision (or EDF), EMG to BDF/EDF (BrainVision is not allowed
  for EMG), MEG to FIF. SNIRF is written with h5py where MNE-BIDS does not.
- **De-identification**: MNE-BIDS `anonymize` (daysback to before 1925, `keep_his=False`,
  `keep_source=False`), then aimport's own pass, because the tools miss:
  - EDF/BDF header patient and recording fields (rewritten as `X X X X` / `Startdate X X X X`).
  - Annotation, marker and event text (EDF Annotations channel, `.vmrk` descriptions,
    EEGLAB events): kept only if they match the plan's coded label list, otherwise replaced by
    a code. The reviewer sees the codes and can name them.
  - BrainVision header comments and embedded file names.
  - SNIRF `/nirs/metaDataTags` (SubjectID, MeasurementDate/Time and custom tags).
  - FIF subject info, experimenter and description (anonymize covers them), and **digitized head
    points**, which are dropped by default and kept only on opt-in (they describe head shape).
  - `scans.tsv` `acq_time` shifted with the subject's date offset, as in phase 1.
  - A final gate re-reads every written header and sidecar for the run's identifying terms.
- **Agent summary**: sampling rate, channel-type histogram, channel count, duration, coded event
  counts, recording-system family. No free text, no dates.
- **brainlife mapping**: eeg/meg rows planned → active; ieeg, nirs, emg drafts stay drafts until
  registered (BIDS target unaffected).

### Center for Mesoscale Connectomics (CMC) data

The CMC publication on brainlife (`connects.brainlife.io/publications/CMC`, doi
10.25663/brainlife.pub.64) has public data in the `apex-connects` S3 bucket (us-east-2) for
three phase 2 cases. These datasets are large and **must not be copied locally**. Tests read
only metadata and coarse levels over HTTP range requests (network-marked tests), never whole
files; nothing is committed. The record states no licence.

| Case | Source in `apex-connects` | Format | Maps to |
|---|---|---|---|
| PS-OCT, reconstructed | `CMC/Derivatives/Moe/PS-OCT/Enface/Registration/{Reflectivity,Retardance,Orientation,Cross}/Slice_*_*.nii.gz` | NIfTI per slice and contrast (14–60 MB) | `micr`, suffix `OCT`, `acq-reflectivity/retardance/opticaxis/cross`, `sample-<slice>` |
| PS-OCT, stitched | `CMC/Derivatives/Moe/PS-OCT/Zarr/Moe_Slice_051.ome.zarr` | OME-Zarr NGFF 0.5 (c, y, x; 6 scales) | same, rewritten |
| PS-OCT, raw | `CMC/Raw/Moe/PS-OCT/<date>/Slice_*_Tile_*.dat` | raw interferometer tiles | out of scope (not reconstructed); excluded with a reason |
| Tract-tracing | `CMC/Raw/Moe/tract-tracing/MN27_*_visor_488/visor_488_Pos*/visor_488_*.tif` + `acqinfo_metadata.json` | VISoR light-sheet TIFF tiles (about 4.3 GB) | `micr`, suffix `SPIM`, `stain-<tracer or channel>`, `chunk-<tile>`; tracer and injection details in `samples.tsv`/sidecar |
| Axonal connectomics | `axonal_connectomics/deskewed/<sample>/exaSPIM.zarr/Pos*` and `contrast_adjusted/<sample>/Pos*` | exaSPIM Zarr v3, sharded multiscale | `micr`, suffix `SPIM`, `chunk-<position>` |

Notes for de-identification:
- Sample and folder names carry acquisition dates (`250215`, `20250422`) and donor codes (`H17`).
  Dates move to the shifted `scans.tsv`, and donor codes go through the pseudonym key like a
  PatientID.
- VISoR `acqinfo_metadata.json`, `dbpost.json` and `hh.log` are read for pixel size and channel
  only; they are not copied.
- The QA viewer opens these with Neuroglancer's `zarr3` driver, like the CMC page's own states.

## Tests that matter most

- Leak tests per phase, as in phase 1: identifiers planted in OME-XML (Experimenter, serials,
  dates, annotations, image names), TIFF tags, EDF header fields and annotations, BrainVision
  comments and markers, SNIRF metaDataTags and FIF subject info. None of them may reach the AI
  model, the plan, an API response, a viewer response, or any output file.
- Viewer tests:
  - `/qa/*` refuses anything not in the manifest and anything before execute;
  - the cookie works only on `/viewer` and `/qa`;
  - the one-time code is single use;
  - Neuroglancer is served from the engine (no external host in the generated state);
  - a headless browser loads the viewer and renders a NIfTI and an OME-Zarr layer from the engine.
- BIDS validation of each phase's output against v1.11.2.

## Test datasets (to record in DATASETS.md)

- Microscopy:
  - `bids-examples` `micr_SPIM` (OME-TIFF), `micr_SEMzarr`, `micr_XPCTzarr`, `micr_SEM` (PNG);
  - an IDR public OME-Zarr sample;
  - **CMC, read remotely** (see above): `zarr.json` and the coarsest level of
    `Moe_Slice_051.ome.zarr` and of one exaSPIM position, the header and one strip of a VISoR TIFF
    tile, and the header of one en-face NIfTI. Everything is read over HTTP ranges and nothing is
    downloaded whole;
  - a synthetic PS-OCT fixture with planted identifiers for the leak test.
- Electrophysiology:
  - `mne-testing-data` for reader coverage (EDF, BDF, BrainVision, EEGLAB, EGI, Nihon Kohden,
    CTF, KIT, BTi, SNIRF, NIRx);
  - `bids-examples` eeg/ieeg/meg/fnirs/emg sets for layout and validator tests (their data files
    are empty);
  - real fNIRS/EMG files from OpenNeuro after checking each licence.

## Delivery

Three plans, each its own PR set:
1. QA viewer.
2. Phase 2 microscopy.
3. Phase 3 electrophysiology and optical.

The QA viewer goes first because both phases use it, and it adds Neuroglancer QA for MRI.

## Left to the builder

- Pyramid level count and chunk sizes for OME-Zarr.
- uPlot page layout.
- The exact coded-label scheme for events.
- Whether small 2D micrographs stay OME-TIFF.

## Sources

- BIDS microscopy and EMG/iEEG pages (bids-specification.readthedocs.io).
- bids-examples.
- PyPI pages: bioio, ngff-zarr, ome-zarr, pylibCZIrw, nd2, mne, mne-bids, pysnirf2.
- mne.tools: `write_raw_bids` and `Raw.anonymize`.
- github.com/NeuroJSON/autobidsify.
- github.com/mne-tools/mne-testing-data.
- github.com/flatironinstitute/neurosift.
- github.com/kai-neuhaus/oct_file_tools.
- brainlife-lite `src/utils/neuroglancer.utils.ts`.
- The neuroglancer 2.40.1 wheel (bundled client).
