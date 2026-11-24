# aimport Phase 2: microscopy (BIDS `micr`) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The engine imports microscopy into BIDS `micr`. Inputs are vendor files (CZI, ND2, LIF), TIFF, OME-TIFF and SVS, existing OME-Zarr (local or `https://`/`s3://`), and reconstructed PS-OCT contrasts (NIfTI, `.mat`, TIFF stacks). The output is de-identified, validated OME-Zarr. Large inputs are never copied locally:
- an input that is already OME-Zarr becomes a **reference dataset** (new metadata written locally, plus a chunk map);
- the `bl aimport` upload streams the chunks from their source.

**Architecture:**
- A small **modality-module interface** (`aimport/modality.py`) sits beside the unchanged ezBIDS MRI path. A module claims input paths, scans them into local-only records, contributes plan entries, and writes its part of the output.
- `aimport/micr/` is the first module. The server, planner, writer and ancillary code each get one narrow hook.
- The QA viewer reads reference datasets through the chunk map (range proxy).
- The cli gains streamed reference upload.

**Tech Stack:**
- Python 3.11: bioio + bioio-czi / bioio-nd2 / bioio-lif, tifffile, ome-types, nibabel, scipy + h5py (`.mat`), zarr-python ≥ 3, fsspec[http], dask[array], ngff-zarr; pytest. A new `network` marker covers remote reads.
- cli: Node, `node:test`, archiver (already a dependency).

**Spec:** `docs/superpowers/specs/2026-11-24-aimport-phase2-3-design.md`, sections "Phase 2: microscopy", "Center for Mesoscale Connectomics (CMC) data" and "Tests that matter most". It extends `docs/superpowers/specs/2026-11-23-aimport-design.md`: phases, de-identification rules, the mapping YAML rule, draft datatypes and the DATASETS.md rule all still hold.

**Depends on:** the QA viewer plan (`2026-11-24-aimport-qa-viewer.md`) merged before Task 10. Tasks 1–9 and 11–12 do not need it.

## Global Constraints

**No large copies**
- Nothing a module claims is staged, symlinked, gzipped or copied.
- The ezBIDS stage, the DICOM term walk (`scrub._header_terms`) and the writer's DICOM walk (`writer.subject_dicoms`) all skip claimed roots.
- Planning reads only headers, metadata documents and at most the coarsest pyramid level.
- Conversion reads in blocks of at most `MAX_BLOCK_BYTES = 256 * 2**20` bytes and never materialises a whole array.

**Identifying data stays local**
- Original paths, file names, folder names and remote URLs never enter `plan.json`, `scan.json`, `status.json`, any API response, any agent request, or anything under `work/output/bids/`.
- They live only in `work/micr/` (`claim.json`, `records.json`, `sources.json`) and in the chunk map `work/output/bids.chunks.json`. Like `ezBIDS_core.json` and the pseudonym key, these are local-only and never uploaded.
- BIDS labels (subject, sample, chunk, stain, acquisition) are generated from parsed facts (numbers, known vocabulary, the pseudonym key), never copied from path text.

**De-identification**
- OME metadata is **rebuilt from an allowlist** (Task 4), never cleaned field by field.
- TIFF tags Artist, Software, HostComputer, DateTime and ImageDescription are never written.
- Slide label and macro images are never read past detection and never written.
- Dates found in names go only to `scans.tsv` `acq_time`, shifted by the subject's offset.
- Donor codes go through the pseudonym key with original `micr:id=<code>`. The `micr:` namespace keeps a donor from merging with an MRI PatientID in this phase.
- VISoR `acqinfo_metadata.json`, `dbpost.json` and `hh.log` are read for pixel size and channel only, and never copied or planned as ancillary.

**Remote sources**
- Only `https://` and `s3://` are accepted. `s3://b/k` becomes `https://b.s3.amazonaws.com/k`, and redirects are followed only to `*.amazonaws.com` or the same host.
- Anonymous reads only; no credentials are stored.
- Requests are range reads. Tests marked `network` assert fewer than `32 * 2**20` bytes fetched per test.

**Output format**
- NGFF **0.5 / Zarr v3, sharded**, by default (`AIMPORT_NGFF_VERSION=0.5|0.4`), subject to the Task 1 ruling.
- A reference dataset keeps its source's Zarr format (v3 → 0.5, v2 → 0.4), because its chunks are not re-encoded.
- Default chunking, which is left to the builder by the spec and fixed here:
  - chunks `(1, 128, 128, 128)` for `c,z,y,x` (2D: `(1, 1024, 1024)`), 4 chunks per spatial axis per shard;
  - pyramid down to the level whose largest spatial axis is ≤ 512, with at most 8 levels;
  - every output is OME-Zarr in this plan (no OME-TIFF output).

**Naming**
- Pattern: `sub-<label>[_ses-<label>]_sample-<label>[_acq-<label>][_stain-<label>][_run-<index>][_chunk-<index>]_<suffix>.ome.zarr`. The schema extension is `.ome.zarr/`; the writer strips the trailing slash.
- `samples.tsv` (`sample_id`, `participant_id`, `sample_type`) is always written.
- Every sidecar has `PixelSize` (x, y[, z]) and `PixelSizeUnits` (`mm`, `um` or `nm`).

**Repo rules**
- ezbids: branch `aimport-phase2-micr` from `origin/master`, PR against `master`. cli: branch from `aimport-cli`.
- Never deploy or push images. Tests first. Docs in the same PR.
- Host tests: `cd aimport && uv run pytest -q -m "not docker and not docker_offline and not network"`.
- Every dataset used is recorded in `aimport/tests/DATASETS.md` in the same commit.
- Mapping changes go in `data/bids_brainlife_map.yaml` in the same PR.
- New Python dependencies need Franco's OK at plan review: bioio, bioio-czi, bioio-nd2, bioio-lif, tifffile, ome-types, zarr≥3, fsspec[http], dask[array], ngff-zarr, scipy, h5py. No new cli dependency.

## Review Focus

1. **A 4 GB TIFF staged, copied or read whole.** A sparse 4 GB BigTIFF (`tifffile.memmap`) in the input:
   - the work folder stays under 1 MiB after scan, with no symlink to the file;
   - tracemalloc peak stays under 64 MiB during scan;
   - conversion peak stays under 3 × `MAX_BLOCK_BYTES`.
   Tests in Tasks 2, 4 and 8.
2. **Identifiers in folder names leaking** (`H17`, `Moe`, `250215`, `20250422`, an Experimenter name in OME-XML, a HostComputer tag). None may appear in:
   - the plan, `/status`, `/plan` or `/qa` responses;
   - the agent payload, `scan.json`, or any output byte.
   Tests in Tasks 3, 6, 7 and 11.
3. **Chunk-map traversal.** All of these are refused by the engine (Task 9), by `/qa/data` (Task 10) and by the cli preflight (Task 12):
   - an output prefix outside a manifest `.ome.zarr` directory;
   - a `..`, absolute or symlinked source escaping the input folder;
   - a `file://` or `http://` source, a host not in the map, or a redirect elsewhere.
4. **Validator rejects NGFF 0.5, or a metadata-only reference store.** Task 1 makes this an explicit ruling before any writer work.
5. **Memory blow-up on one huge plane.** A striped TIFF whose single plane is larger than the block limit is read through `tifffile` `aszarr` in row blocks, never `imread`. Tests in Tasks 4 and 8.

---

## File structure (under `ezbids/aimport/`; new unless marked)

| File | Responsibility |
|---|---|
| `src/aimport/modality.py` | `Module` protocol, `Claim`, `ModulePlan`, `ModuleOutput`, `modules()` registry |
| `src/aimport/micr/__init__.py` | constants (`NGFF_VERSION`, chunking, `MAX_BLOCK_BYTES`, `MICR_INDEX_BASE`, `MICR_EXTS`, `MICR_SUFFIXES`) |
| `src/aimport/micr/discover.py` | `claim()`: which input paths and remote sources are microscopy; format family; exclusions |
| `src/aimport/micr/names.py` | path facts (donor, dates, slice, tile/position, channel, contrast) and path terms |
| `src/aimport/micr/readers.py` | `ImageSource` backends, allowlisted `ImageInfo`, lazy dask access |
| `src/aimport/micr/remote.py` | URL normalisation, fsspec stores, byte accounting |
| `src/aimport/micr/metadata.py` | NGFF `multiscales`/`omero` attrs and BIDS sidecars, built from `ImageInfo` only |
| `src/aimport/micr/module.py` | `MicrModule`: scan → records, plan entries, write dispatch |
| `src/aimport/micr/convert.py` | streaming conversion to OME-Zarr |
| `src/aimport/micr/reference.py` | reference datasets and the chunk map |
| modified: `ezbids_runner.py`, `scrub.py`, `planner.py`, `plan.py`, `writer.py`, `ancillary.py`, `agent.py`, `schema.py`, `server.py`, `viewer.py`, `data/bids_brainlife_map.yaml` | one hook each (below) |
| `tests/fixtures/micr_fixtures.py` | synthetic builders: CMC-shaped trees, planted OME-TIFF, planted PS-OCT, sparse BigTIFF, small OME-Zarr v2/v3 |

---

### Task 1: Dependencies and the validator ruling (NGFF 0.5, metadata-only stores)

**Files:**
- Modify: `aimport/pyproject.toml`, `aimport/uv.lock`, `aimport/README.md` (versions).
- Create: `aimport/src/aimport/micr/__init__.py`, `aimport/tests/fixtures/micr_fixtures.py` (OME-Zarr builders only, for now), `aimport/tests/test_micr_validator.py`.

**Interfaces:**
- Produces:
  - `micr.NGFF_VERSION: Literal["0.5","0.4"]`, read from `AIMPORT_NGFF_VERSION`. The default is set by this task's ruling.
  - `micr_fixtures.ome_zarr(dest: Path, version: str, shape=(2, 8, 64, 64), pixel_size_um=(1.0, 0.5, 0.5)) -> Path`
  - pytest marker `network` in `pyproject.toml`.

- [ ] **Step 1:** Add the dependencies; `uv lock`. Check that wheels exist for manylinux x86_64 and macOS arm64. If `bioio-czi` (pylibCZIrw) has no macOS arm64 wheel, mark CZI tests `docker` and say so in the commit message.
- [ ] **Step 2:** Docker tests, each building a minimal valid `sub-01/micr/sub-01_sample-A_SPIM.ome.zarr` with sidecar, `samples.tsv`, `participants.tsv` and `dataset_description.json`, then running `validate_bids`:
  - `test_validator_accepts_ngff_05` → `ok`.
  - `test_validator_accepts_ngff_04` → `ok`.
  - `test_validator_accepts_metadata_only_store` → `ok`. Same as 0.5, but every chunk/shard file is deleted (what a reference dataset looks like locally).
  - `test_validator_flags_missing_pixelsize` → error mentioning `PixelSize`. This is the positive control.
- [ ] **Step 3 — ruling point (stop and report to Franco before Task 8):**
  - 0.5 accepted, 0.4 accepted, metadata-only accepted → default `"0.5"`; proceed.
  - 0.5 rejected → set the default to `"0.4"` and **stop**. Zarr v3 sources (CMC PS-OCT, exaSPIM) could then not be reference datasets without a full re-encode. Franco chooses between a validator bump (later than 2.4.1, with schema still at 1.11.2) and conversion with a size warning. Record the validator's exact message in the report.
  - Metadata-only rejected → **stop**. Reference datasets would need to be validated with placeholder chunks; Franco decides.
- [ ] **Step 4:** Commit `aimport: microscopy dependencies; validator ruling on NGFF 0.5 and metadata-only stores`. The message records the outcome.

### Task 2: The modality-module interface and claimed-path exclusion

**Files:**
- Create: `aimport/src/aimport/modality.py`, `aimport/tests/test_modality.py`.
- Modify: `ezbids_runner.py` (`stage_input`), `scrub.py` (`identifying_terms`, `_header_terms`), `planner.py` (`run_terms`), `writer.py` (`subject_dicoms`), `server.py` (`ScanBody`, `Server.scan`, `get_terms`, `reset_output`).

**Interfaces:**
- Produces in `modality.py`:
  - `@dataclass Claim: roots: list[str]; remote: list[str]`. Roots are input-relative POSIX paths (files or folders); remote holds normalised URLs. Both are local-only.
  - `@dataclass ModulePlan: entries: list[PlanEntry]; warnings: list[str]; view: list[ScrubbedSeries]; labels: dict[int, str]; images: dict[str, str | None]`
  - `@dataclass ModuleOutput: manifest: dict[str, list[str]]; participants: dict[str, dict[str, str]]; scans: dict[tuple[str, str | None], list[tuple[str, str]]]; samples: list[dict[str, str]]; chunk_map: dict | None; images: dict[str, str]`
  - `class Module(Protocol)`:
    - `name: str`
    - `claim(input_dir: Path, remote: list[str]) -> Claim`
    - `scan(input_dir: Path, claim: Claim, work: Path, progress: Callable[[str], None]) -> None`
    - `terms(work: Path) -> set[str]`
    - `plan(work: Path, key: PseudonymKey, existing: set[str], client: LLMClient | None, schema: Schema, target: str) -> ModulePlan`
    - `write(plan: Plan, work: Path, input_dir: Path, terms: set[str], key: PseudonymKey, schema: Schema, dest: Callable[[str], Path]) -> ModuleOutput`
  - `modules() -> tuple[Module, ...]`. This task returns `()`; Task 6 registers `MicrModule()`. Tests monkeypatch it.
- Changed signatures (old calls keep working):
  - `stage_input(input_dir, work_dir, exclude: Sequence[str] = ()) -> Path`. Uses an explicit walk (`os.walk`, `followlinks=False`) that symlinks only unclaimed files and never descends into a claimed root. Returns `None`-equivalent emptiness through `has_files(staged) -> bool`.
  - `identifying_terms(core, input_dir, stats=None, exclude: Sequence[str] = ())` and `run_terms(core, input_dir, stats=None, exclude=())`.
  - `ScanBody.remote: list[str] = []`, validated by `micr.remote.normalize_url` once Task 5 exists. Until then only the scheme is checked.
- `Server.scan` sequence:
  - `claims = {m.name: m.claim(...)}`, saved to `work/<name>/claim.json`;
  - `stage_input(..., exclude=all roots)`;
  - if the staged tree has no files, skip `run_ezbids` and write `EMPTY_CORE = {"series": [], "objects": [], "subjects": []}` to `staged/ezBIDS_core.json`;
  - `m.scan(...)` for each module;
  - `build_plan(..., modules=[m.plan(...)])` (Task 6).
- `get_terms` = `run_terms(core, input, exclude=roots) | ⋃ m.terms(work)`. `reset_output` and a new scan clear `work/<name>/`.

- [ ] **Step 1:** Tests, using a fake module that claims `big/` and `a.zarr/`:
  - `test_stage_excludes_claimed_roots`: nothing under `staged/big` or `staged/a.zarr`, and no symlink resolving into them.
  - `test_stage_unclaimed_files_unchanged`: same tree as `cp -rs` for the rest.
  - `test_sparse_4gb_tiff_not_staged`: a `micr_fixtures.sparse_bigtiff(4 * 2**30)` under `big/`; `du` of the work folder < 1 MiB.
  - `test_header_terms_skip_claimed`: a planted DICOM inside `big/` adds no term; `stats["dicom_files_read"]` counts only unclaimed files.
  - `test_ezbids_skipped_when_nothing_left`: `run_ezbids` is never called (monkeypatched to raise); stage reaches `planned`.
  - `test_claim_json_never_served`: `/plan` and `/status` contain no claimed path.
  - Phase-1 suites still pass with `modules()` empty.
- [ ] **Step 2–3:** Implement.
- [ ] **Step 4:** Commit `aimport: modality modules; claimed input is never staged, walked for DICOM or copied`.

### Task 3: Discovery and name facts (`micr/discover.py`, `micr/names.py`)

**Files:**
- Create: `discover.py`, `names.py`, `tests/test_micr_discover.py`.
- Extend: `micr_fixtures.py` with `cmc_tree(dest)`, which builds sparse/empty files in the CMC layouts:
  - `PS-OCT/Enface/Registration/{Reflectivity,Retardance,Orientation,Cross}/Slice_051_1.nii.gz`;
  - `PS-OCT/250215/Slice_051_Tile_0001.dat`;
  - `Moe_Slice_051.ome.zarr/`;
  - `MN27_20250422_visor_488/visor_488_Pos0/visor_488_0001.tif` with `acqinfo_metadata.json`, `dbpost.json` and `hh.log`;
  - `exaSPIM.zarr/Pos0`.

**Interfaces:**
- `discover.FAMILIES`. The entries marked `unsupported` are Bio-Formats-only:

  | Family | Matches |
  |---|---|
  | `ome-zarr` | a folder holding `zarr.json`, or `.zgroup`/`.zattrs` |
  | `ome-tiff` | `.ome.tif(f)`, `.ome.btf` |
  | `tiff` | `.tif(f)` that is not DICOM |
  | `svs` | `.svs` |
  | `czi`, `nd2`, `lif` | `.czi`, `.nd2`, `.lif` |
  | `nifti` | `.nii(.gz)`, claimed only with a micr hint (below) |
  | `mat` | `.mat` |
  | `raw-psoct` | `.dat` with a PS-OCT hint |
  | `unsupported` | `.vsi`, `.oib`, `.oif`, `.ims`, `.lsm`, `.scn`, `.mrxs` |
  | `visor-meta` | `acqinfo_metadata.json`, `dbpost.json`, `hh.log` |

- A **micr hint** is any of:
  - a path token in `{"ps-oct","psoct","oct","enface","reflectivity","retardance","orientation","opticaxis","cross","micr"}`;
  - a NIfTI with spatial units microns (`xyzt_units` code 3);
  - a BIDS `micr/` folder.
- `discover.claim(input_dir, remote) -> tuple[Claim, list[Found]]`, with `@dataclass Found: rel: str; family: str; group: str`:
  - an OME-Zarr folder or `exaSPIM.zarr/Pos*` is one root and is never walked inside;
  - a tile folder's `.tif` files share one `group`.
- `names.facts(rel: str) -> NameFacts`, with `@dataclass NameFacts`:
  - `donor: str | None`;
  - `dates: list[date]`: 6-digit tokens read as YYMMDD when valid, else YYYYMM; 8-digit as YYYYMMDD in 1900–2099; reuses `planner._is_date_like`;
  - `slice: int | None` (`Slice_(\d+)`); `tile: int | None` (`Tile_(\d+)`, or a trailing tile index); `position: int | None` (`Pos(\d+)`);
  - `channel_nm: int | None` (a 3-digit token 350–900 next to a channel word or `visor`);
  - `contrast: Literal["reflectivity","retardance","opticaxis","cross"] | None`. `Orientation` maps to `opticaxis`.
- **Donor rule:** a `sub-<label>` folder wins. Otherwise the first token of a sample-like name that is not vocabulary, a date or a pure number, and matches `^[A-Za-z]{1,4}\d{0,4}$` (`H17`, `MN27`, `Moe`). Vocabulary (`slice`, `tile`, `pos`, `visor`, `spim`, `exaspim`, …) is a fixed tuple in `names.VOCAB`.
- `names.path_terms(rels: Iterable[str]) -> set[str]`: every token of length ≥ 3 that is not in `VOCAB` and not purely numeric with fewer than 6 digits, plus donors and every `_date_forms` of each date including the raw 6-digit form.

- [ ] **Step 1:** Tests on `cmc_tree`:
  - `test_families`: each CMC case gets the expected family; raw `.dat` → `raw-psoct`; a `.vsi` → `unsupported`.
  - `test_nifti_without_hint_left_to_ezbids`: an MRI `T1.nii.gz` is not claimed.
  - `test_zarr_root_not_walked`: a store with 10,000 chunk files is listed with fewer than 50 `os.scandir` calls (counting monkeypatch).
  - `test_facts`: `facts("MN27_20250422_visor_488/visor_488_Pos3/visor_488_0012.tif")` → donor `MN27`, dates `[2025-04-22]`, position 3, tile 12, channel 488. `Moe_Slice_051.ome.zarr` → donor `Moe`, slice 51. `Orientation/Slice_051_1.nii.gz` → contrast `opticaxis`.
  - `test_path_terms`: contains `MN27`, `Moe`, `20250422`, `2025-04-22`, `250215`; contains no `visor` or `488`.
  - `test_visor_meta_claimed_not_entries`: these files are claimed but form no `Found` image.
- [ ] **Step 2–4:** Implement, pass, commit `aimport micr: discover microscopy inputs and parse name facts`.

### Task 4: Readers with allowlisted metadata (`micr/readers.py`)

**Files:**
- Create: `readers.py`, `metadata.py` (allowlist only, for now), `tests/test_micr_readers.py`.
- Extend `micr_fixtures`:
  - `planted_ome_tiff(dest)`. OME-XML carries Experimenter `Jane Doe` / `jdoe@example.org`, Instrument serial `SCOPE-SN-4711`, `AcquisitionDate` `2025-02-15T10:00:00`, Image Name `Slide 42 Smith`, Description `annotation secret`, a StructuredAnnotation and an ROI. TIFF tags: Artist `Jane Doe`, HostComputer `lab-workstation-7`, Software `AcqSoft 9 lab-workstation-7`, DateTime `2025:02:15 10:00:00`.
  - `planted_svs(dest)`, with `label` and `macro` series holding the text `Slide 42 Smith` in pixels (as rendered bytes).
  - `psoct_nifti(dest, contrast)`, in microns.
  - `psoct_mat(dest, v73: bool)`.
  - `sparse_bigtiff(size)` and `striped_tiff(dest, (6000, 6000), uint16)`.
- Add to `conftest.py`: `MICR_PLANTED = {"jane doe", "jdoe@example.org", "scope-sn-4711", "2025-02-15", "250215", "20250422", "slide 42 smith", "annotation secret", "lab-workstation-7", "h17", "moe", "mn27"}`; `tokens()` also checks it.

**Interfaces:**
- `@dataclass ImageInfo`. Only these fields exist:
  - `family: str; axes: str` (subset of `tczyx`); `shape: tuple[int, ...]; dtype: str`;
  - `pixel_size: dict[str, float]` (x/y/z); `pixel_unit: Literal["mm","um","nm"]`;
  - `channels: list[ChannelInfo]`, with `ChannelInfo(excitation_nm: float | None, emission_nm: float | None, name_code: str)`. `name_code` is `ch<excitation>` or `ch<i>`, never the OME name;
  - `objective_magnification: float | None; objective_na: float | None; immersion: str | None` (OME enum value only);
  - `levels: int; zarr_format: Literal[2, 3] | None; ngff_version: str | None`;
  - `acquired: date | None` (local only: goes to records, never to the view);
  - `series_skipped: list[str]` (`"label"`, `"macro"`, `"thumbnail"`).
- `class ImageSource(Protocol)`: `info: ImageInfo`; `terms: set[str]` (every dropped OME/TIFF string value, for redaction); `level(i: int) -> dask.array.Array`; `close()`.
- `open_image(location: str | Path, family: str) -> ImageSource`. The backends:
  - `tiff`/`ome-tiff`/`svs`: `tifffile.TiffFile` + `series[i].aszarr()` → `dask.array.from_zarr`. Label and macro series are skipped by `series.name`/`kind`.
  - `czi`/`nd2`/`lif`: bioio `BioImage(...).dask_data`, metadata via `ome_metadata`.
  - `nifti`: `nibabel` `dataobj` wrapped by `dask.array.from_array` (chunks ≤ `MAX_BLOCK_BYTES`).
  - `mat`: v7.3 through `h5py`, lazy. v5 through `scipy.io.loadmat`, refused above `2 * 2**30` bytes with `"MATLAB v5 file too large to read lazily: save as v7.3"`.
  - `ome-zarr`: `zarr.open_group` (v2/v3; local `Path` or an fsspec mapper from Task 5).
  - `visor`: tiles via `tiff`, with pixel size and channel from `acqinfo_metadata.json` numeric fields only. Record the key names found in DATASETS.md.
- `register_reader(family: str, opener: Callable[[str | Path], ImageSource])`, plus entry-point group `aimport.micr_readers`. This is the per-lab adapter hook.
- `metadata.ome_allowlist(ome: OME) -> tuple[ImageInfo-fields, set[str]]` rebuilds facts from `ome_types` objects and returns the dropped strings as terms.

- [ ] **Step 1:** Tests:
  - `test_ome_tiff_info_allowlisted`: info has the planted pixel sizes and wavelengths. `repr(info)` holds none of `MICR_PLANTED`, and `source.terms` holds all of them.
  - `test_svs_label_macro_skipped`: `series_skipped == ["label","macro"]`; no dask array is built for them.
  - `test_nifti_microns`: `pixel_unit == "um"`.
  - `test_mat_v73_lazy`: tracemalloc peak < 8 MiB for a 64 MiB dataset.
  - `test_mat_v5_too_large` (monkeypatched limit).
  - `test_sparse_bigtiff_open_bounded`: opening plus `info` on 4 GB sparse keeps the peak < 64 MiB.
  - `test_huge_plane_blocks`: `level(0).chunksize` bytes ≤ `MAX_BLOCK_BYTES` on `striped_tiff` with the limit patched to 4 MiB; computing one block keeps the peak < 12 MiB.
  - `test_ome_zarr_v2_v3_info`: `zarr_format` and `levels` are correct.
  - `test_unsupported_family_message`: `open_image(x, "unsupported")` raises `UnsupportedFormat("needs Bio-Formats (not included): export to OME-TIFF or OME-Zarr first")`.
  - `test_adapter_hook`: a registered fake family is used.
- [ ] **Step 2–4:** Implement, pass, commit `aimport micr: readers with allowlisted metadata, lazy and bounded`.

### Task 5: Remote stores (`micr/remote.py`)

**Files:**
- Create: `remote.py`, `tests/test_micr_remote.py`.

**Interfaces:**
- `normalize_url(url: str) -> str`. Raises `ValueError` for any scheme other than `https`/`s3`, for userinfo, and for a host that is an IP literal or `localhost`.
- `open_store(url: str) -> tuple[fsspec.FSMap, ByteCounter]`, using `HTTPFileSystem(block_size=2**20, client_kwargs={"trust_env": False})`. Redirects are checked against the rule in Global Constraints.
- `ByteCounter.total: int` counts every fetched byte.
- `discover.claim` handles each remote URL by probing `<url>/zarr.json`, then `.zattrs`, then the HTTP `Content-Type`/extension for single files. Only `ome-zarr`, `nifti` and `tiff` are allowed remote.

- [ ] **Step 1:** Offline tests, against a local threaded HTTP server with Range support serving a `micr_fixtures.ome_zarr` tree. `normalize_url` is monkeypatched to allow `127.0.0.1` for these tests only:
  - `test_scheme_allowlist`: `file://`, `http://`, `ftp://` and `https://user@h/` all fail.
  - `test_s3_rewrite`.
  - `test_redirect_to_other_host_refused`.
  - `test_coarse_level_only`: reading `info` plus the coarsest level fetches less than 5% of the store's bytes.
- [ ] **Step 2:** `network` tests on CMC (paths pinned at task time by listing `apex-connects` and recording the exact keys in DATASETS.md):
  - `test_cmc_psoct_zarr_metadata`: NGFF 0.5, axes `cyx`, 6 levels, and `ByteCounter.total < 32 * 2**20`.
  - `test_cmc_exaspim_position`: zarr v3 sharded; same byte cap.
  - `test_cmc_visor_tile_header`: header plus one strip only; under 8 MiB.
  - `test_cmc_enface_nifti_header`: header only; under 1 MiB.
- [ ] **Step 3–4:** Implement, pass (host offline; `-m network` once by hand, with the result in the commit message), commit `aimport micr: remote OME-Zarr and file reads by range request`.

### Task 6: Scan records and plan entries (`micr/module.py`, planner hook, mapping YAML)

**Files:**
- Create: `module.py`, `tests/test_micr_plan.py`.
- Modify: `plan.py` (fields), `schema.py` (`SUPPORTED_DATATYPES`, `CHECK_EXTS`), `planner.py` (`build_plan(modules=)`, `_check_nameable`, `_rederive`), `modality.modules()` (register), `data/bids_brainlife_map.yaml`, `tests/test_brainlife_map.py`.

**Interfaces:**
- `PlanEntry` gains defaulted fields, so old plans still load:
  - `modality: Literal["mri","micr"] = "mri"`;
  - `sample_type: str | None = None`. Editable as `"str?"`; must be in the schema's `sample_type` enum, default `"tissue"` for micr;
  - `write_mode: Literal["","convert","reference"] = ""`;
  - `output_bytes: int = 0`.
  - `EDITABLE_FIELDS["sample_type"] = "str?"`.
- `schema.SUPPORTED_DATATYPES = PHASE1_DATATYPES + ("micr",)` and `CHECK_EXTS = {"micr": ".ome.zarr/"}` (default `.nii.gz`). `_check_nameable` uses both. An entry whose `modality == "micr"` with a datatype other than `micr` gets `status="unknown"` and reason `"microscopy input: datatype must be micr"`. The reverse case (an MRI entry set to `micr`) gets the same treatment.
- `MicrModule.scan` writes `work/micr/records.json` (local only). Each record is `{rel|url, family, group, facts, info, terms}`, at most one per image or tile group. It emits progress `"reading microscopy metadata (k of n)"`, with counts only.
- `MicrModule.plan`:
  - **Subjects:** `key.subject_id("micr:id=" + donor, existing, proposed=<sub- label or None>)`. No donor → a run-local original, as in `_assign_subjects`.
  - **Indices:** `subject_idx`/`series_idx` = `MICR_INDEX_BASE (1_000_000) + i`; `session_idx = 0`; session is `None` unless the input has `ses-` folders.
  - **Sample labels:** `slice<NNN>` when `facts.slice` is set, else the input's `sample-<label>` when usable (`planner._usable`), else `1, 2, …` per subject in sorted record order.
  - **Entities:** `acquisition=<contrast>` (PS-OCT); `stain=ch<nm>` (channel); `chunk=<tile or position>` when a sample has more than one.
  - **Suffix heuristic:** `OCT` for a PS-OCT hint or contrast; `SPIM` for `visor`/`exaspim`/light-sheet hints; the OME `AcquisitionMode` enum mapped through `{"SingleMoleculeImaging": None, "LaserScanningConfocalMicroscopy": "CONF", "MultiPhotonMicroscopy": "2PE", "BrightField": "BF", "DarkField": "DF", "PhaseContrast": "PC", "DifferentialInterferenceContrast": "DIC", "WideField": "FLUO", "SPIM": "SPIM"}`; else `None` (status `unknown`).
  - `write_mode = "reference"` for the `ome-zarr` family (local or remote), else `"convert"`. `output_bytes` = level-0 bytes × 1.34 for convert, and 0 for reference.
  - `description`: generated only, e.g. `"OME-Zarr 0.5, 3 channels, 2048×2048×300, 0.5 µm; reference (no copy)"`. Never path text.
  - **Exclusions:**
    - `raw-psoct` groups → one `unsupported` entry per folder, reason `"raw interferometer data: reconstruct first"`;
    - `unsupported` → reason `UnsupportedFormat`'s message;
    - `deface=False` always.
  - **Warnings:** `"conversion writes about {N:.1f} GB to the work folder"` when any convert entry is included.
- `build_plan(..., modules: Sequence[ModulePlan] = (), extra_terms: frozenset[str] = frozenset())` changes:
  - appends module entries and warnings;
  - merges views for `draft_metadata`;
  - merges `labels`/`images` into the `ImportMap` for ancillary;
  - suppresses the phase-1 `UNVERIFIED` "no DICOM headers were read" warning when `core.series` is empty and modules exist.
- **Mapping YAML:** the `micr extension .ome.zarr planned` row is replaced by 18 `active` rows, `bids: {datatype: micr, suffix: <S>}` → `brainlife: {datatype: neuro/ome-zarr, tags: [<S>]}`, ref `brainlife-lite (ProjectDataS3, Zarr viewers)`. Here S is one of TEM, SEM, uCT, BF, DF, PC, DIC, FLUO, CONF, PLI, CARS, 2PE, MPE, SR, NLO, OCT, SPIM, XPCT.

- [ ] **Step 1:** Tests. With `client=None` and `cmc_tree` plus `planted_ome_tiff` inside an `H17_250215/` folder:
  - `test_psoct_entries`: 4 entries for slice 51, with `acquisition` in {reflectivity, retardance, opticaxis, cross}, suffix `OCT`, `entities["sample"] == "slice051"`.
  - `test_raw_dat_excluded`: one entry, `status == "unsupported"`, `exclude`, with the exact reason.
  - `test_visor_chunks`: suffix `SPIM`, `stain == "ch488"`, `chunk` per position; `write_mode == "convert"`; `output_bytes > 0`; size warning present.
  - `test_ome_zarr_reference`: `write_mode == "reference"`; `output_bytes == 0`.
  - `test_donor_pseudonymised`: `H17`, `MN27` and `Moe` each get a key ID. A second scan reuses them (re-import).
  - `test_no_identifiers_in_plan`: `json.dumps(asdict(plan))` holds none of `MICR_PLANTED`.
  - `test_brainlife_mapping`: `to_brainlife("micr","OCT",{},{}) == ("neuro/ome-zarr", ["OCT"])`. YAML tests pass; `tools/draft_datatypes.py --check` reports no micr drafts.
  - `test_edit_micr_entry`: `apply_plan_edits` on `suffix: "CONF"` keeps `ok`; on `datatype: "anat"` → `unknown` with the modality reason; `sample_type: "bogus"` → `ValueError`.
  - `test_indices_do_not_collide`: a mixed MRI + micr input gives distinct `subject_idx`, and a subject edit on the MRI subject leaves micr entries unchanged.
- [ ] **Step 2–4:** Implement, pass (with the phase-1 planner suite), commit `aimport micr: plan entries, pseudonymised donors and samples; micr rows active in the brainlife mapping`.

### Task 7: The agent for microscopy

**Files:**
- Modify: `agent.py`, `scrub.py` (`ScrubbedSeries` unchanged; a builder in `module.py`).
- Test: `tests/test_micr_agent.py`.

**Interfaces:**
- `agent.MICR_CLASSIFY_SYSTEM`: datatype is always `micr`; the suffix must be one of the 18; entities only `sample`, `acquisition`, `stain`, `chunk`, `run`; same JSON reply format.
- `classify(series, heuristic, client, schema, system: str = CLASSIFY_SYSTEM, datatypes: tuple[str, ...] = PHASE1_DATATYPES)`. `_checked` takes `datatypes`.
- `module.micr_view(records) -> list[ScrubbedSeries]`:
  - `description=""`, `protocol=""`, `ezbids_type="micr/<heuristic suffix or unknown>"`;
  - `fields` = `{Dimensions: {axis: size}, PixelSize, PixelSizeUnits, ChannelCount, ExcitationWavelengths, EmissionWavelengths, ObjectiveMagnification, ObjectiveNA, Immersion, FormatFamily, Levels, DataType, Hints}`;
  - `Hints` holds only tokens from `names.VOCAB`.
- The planner rule from phase 1 still applies: heuristic and agent agreement → confidence ≥ 0.8; disagreement → `agent_note`.

- [ ] **Step 1:** Tests with a recording client:
  - `test_micr_payload_allowlisted`: payload keys are exactly the list above; `tokens(payload)` and `MICR_PLANTED` are disjoint; there is no `/` path, no 6- or 8-digit date, no file extension other than in `FormatFamily`.
  - `test_agent_fills_unknown_suffix`: a `tiff` with no hints and the agent answering `CONF` gives `source == "agent"`.
  - `test_agent_non_micr_answer_rejected`: `anat/T1w` gives no guess.
  - `test_mri_prompt_unchanged`: `CLASSIFY_SYSTEM` is byte-identical to before.
- [ ] **Step 2–4:** Implement, pass, commit `aimport micr: agent sees allowlisted image facts only`.

### Task 8: Conversion writer and the write hook (`micr/convert.py`, `micr/metadata.py`)

**Files:**
- Create: `convert.py`, `tests/test_micr_convert.py`.
- Modify: `metadata.py`, `module.py` (`write`), `writer.py` (`write_bids(modules=)`), `ancillary.py` (`IMAGE_EXTS`, samples merge), `server.py` (`execute` passes modules).

**Interfaces:**
- `convert.to_ome_zarr(src: ImageSource, dest: Path, version: str = NGFF_VERSION, progress=None) -> int` returns bytes written:
  - builds `ngff_zarr.to_multiscales` from `src.level(0)` with block-wise dask and the pyramid rule above;
  - writes with `ngff_zarr.to_ngff_zarr(..., version=version, chunks_per_shard=4)`;
  - then **overwrites** the group attributes with `metadata.ngff_attrs(info, version)`, so nothing from ngff-zarr defaults or the source survives;
  - progress per level and per tile.
- `metadata.ngff_attrs(info, version) -> dict`: `multiscales` (axes, scale transforms from `pixel_size`) and an `omero` block with one channel per `ChannelInfo`. Labels are `name_code`; windows come from the coarsest level's 0.5/99.5 percentiles. No `name`, no `metadata`, no `_creator`, no OME-XML group.
- `metadata.sidecar(info, entry) -> dict`:
  - `PixelSize` (x, y[, z]) and `PixelSizeUnits`;
  - `Magnification`, `NumericalAperture` and `Immersion` when known;
  - for `OCT`, the custom fields `OCTContrast`, `OCTRetardanceKind` (`"retardance"`, `"birefringence"` or `"n/a"`) and `OCTOpticAxisConvention` (`"n/a"` until the reviewer sets it through the sidecar edit path).
- `write_bids(..., modules: Sequence[Module] = ())`. In `_Writer.run`, after the MRI items:
  - `out = m.write(plan, ..., dest=self.dest)`;
  - manifest merged;
  - participants rows are added (`age`/`sex` `n/a`; MRI demographics win);
  - `scans` rows merged per (subject, session), with `acq_time = shifted date + "T00:00:00"` and `scans.json` `acq_time` Description `"date only; time not recorded"`;
  - `Generated.tables["samples.tsv"]` = `[["sample_id","participant_id","sample_type"], …]`;
  - `out.images` goes into `ids.images`.
- `ancillary.IMAGE_EXTS += (".ome.zarr", ".ome.tif", ".ome.btf", ".png", ".tif")`, so an image's own sidecar is not a companion. Generated `samples.tsv` merges with a supplied one keyed by (`participant_id`, `sample_id`), with supplied values winning, as for participants.

- [ ] **Step 1:** Tests:
  - `test_convert_ome_tiff`: output opens with `zarr.open_group`; NGFF version as configured; shape and pixel scale match; channel labels `ch488`/`ch561`.
  - `test_convert_bounded_memory`: `striped_tiff` with `MAX_BLOCK_BYTES` patched to 4 MiB; tracemalloc peak < 12 MiB.
  - `test_no_planted_bytes_in_output`: every file under the output (binary included) is searched for each `MICR_PLANTED` term in UTF-8 and UTF-16LE → none found.
  - `test_attrs_rebuilt`: group attrs keys ⊆ `{"ome"}` for 0.5 or `{"multiscales","omero"}` for 0.4, with nothing else.
  - `test_sidecar_required_fields`: `PixelSize`/`PixelSizeUnits` present; OCT fields present for OCT.
  - `test_scans_shifted`: `acq_time` is `2025-02-15 + offset`; `250215` never written.
  - `test_samples_tsv`: one row per (subject, sample); a supplied `samples.tsv` merged; `collected_by` from the ancillary fixture kept as in phase 1.
  - `test_bids_micr_sidecar_not_companion`: a BIDS micr input's `_SPIM.json` is not planned as ancillary.
  - Docker: `test_converted_dataset_validates` → `validate_bids(...).ok`.
- [ ] **Step 2–4:** Implement, pass (with the phase-1 writer suite), commit `aimport micr: stream TIFF, vendor, NIfTI and MATLAB images to OME-Zarr with rebuilt metadata`.

### Task 9: Reference datasets and the chunk map (`micr/reference.py`)

**Files:**
- Create: `reference.py`, `tests/test_micr_reference.py`.
- Modify: `module.py`, `server.py` (`execute`, `OUTPUT_STATE`, `set_aside`, `reset_output`, `/status`).

**Interfaces:**
- **Ruling point for Franco (format):** the chunk map is per **array prefix**, not per chunk, so a terabyte exaSPIM store does not give a map with millions of lines. The spec's "{output chunk path: source}" is preserved key by key, because chunk keys under a prefix are identical in source and output: the Zarr format is unchanged and the codecs are copied. Format:

  ```
  {"version": 1, "arrays": {"<out rel array dir>": {"source": {"input": "<input-relative dir>"} | {"url": "<https URL>"},
    "zarr_format": 2|3, "shape": [...], "chunk_grid": [...], "separator": "/"|".", "codec_bytes_hint": int}}}
  ```

  It is written to `work/output/bids.chunks.json` (never under `bids/`). `OUTPUT_STATE` gains `"chunk_map": "output/bids.chunks.json"`, and `/status` exposes that work-relative path only.
- `reference.write_reference(src: ImageSource, location, dest: Path, info: ImageInfo) -> dict` (the `arrays` part):
  - writes the group metadata (`metadata.ngff_attrs` in the source's format);
  - each array's `zarr.json` or `.zarray` is **rebuilt** from shape, dtype, chunk grid, codecs/compressor, fill value and dimension names, with `attributes` dropped;
  - writes no chunk bytes.
- `reference.chunk_keys(array_meta) -> Iterator[str]` enumerates every chunk or shard key from the shape and grid (v2 with separator `.`/`/`, v3 `c/…`). Missing source objects are fill values and are skipped by consumers.
- `reference.resolve(map, out_rel: str, input_dir: Path) -> Path | str` is the one resolver shared by the engine and the viewer. It raises `ValueError` when:
  - `out_rel` is not strictly inside a mapped array dir;
  - the key does not match `chunk_keys` syntax (digits and separators only);
  - an input source resolves outside `input_dir` or through a symlink;
  - a URL fails `normalize_url`.

- [ ] **Step 1:** Tests:
  - `test_reference_writes_metadata_only`: no file under the output is larger than 64 KiB; the chunk file count is 0.
  - `test_array_attributes_dropped`: an OME-Zarr v3 fixture with planted `attributes` (`{"operator": "Jane Doe"}`) and an OME-XML `OME/METADATA.ome.xml` → neither is in the output; `MICR_PLANTED` is absent from every output byte.
  - `test_chunk_map_outside_output`, and the cli-style check that nothing in `bids/` is named `*.chunks.json`.
  - `test_chunk_keys_v2_v3`.
  - `test_resolve_refuses` with: `../x`, `/etc/passwd`, `%2e%2e`, a key `0/../../x`, an input symlink pointing outside, a `file://` URL.
  - `test_v3_source_stays_v3`.
  - Docker: `test_reference_dataset_validates`, according to the Task 1 ruling.
  - `test_rescan_clears_chunk_map`.
- [ ] **Step 2–4:** Implement, pass, commit `aimport micr: reference datasets for OME-Zarr inputs (metadata local, chunk map for the upload)`.

### Task 10: QA viewer for microscopy (range proxy and zarr layers)

Requires the QA viewer plan merged.

**Files:**
- Modify: `server.py` (`/qa/data` resolution), `viewer.py`.
- Tests: `tests/test_viewer_routes.py`, `tests/test_viewer.py`.

**Interfaces:**
- `/qa/data/{entry_id}/{index}/{subpath}` for a manifest `.ome.zarr` directory:
  - a `subpath` that exists locally (metadata) is served as before;
  - otherwise `reference.resolve` decides:
    - an input source → `FileResponse` (Range honoured);
    - a URL → an `httpx` streamed GET forwarding only `Range`; at most `64 * 2**20` bytes per response; status and `Content-Range` passed through; redirects follow the remote rule.
  - Upstream URLs and input paths never appear in any response header or body. A 404 from the source → 404 with body `"no such chunk"`.
- `viewer.zarr_layer(name: str, url: str, info: dict, version: str) -> dict`:
  - `source` is `url + "|zarr3:"` (0.5) or `url + "|zarr2:"` (0.4);
  - one layer per channel with an additive blend; shader windows from the written `omero` block.
- `viewer.entry_state(...)`: micr entries use `zarr_layer`. OCT entries of one (subject, sample) are grouped into one state with the `reflectivity`, `retardance`, `opticaxis` and `cross` layers, sharing dimensions.
- `/viewer/` lists micr entries as `"Neuroglancer (OME-Zarr)"`, and reference entries as `"(read from source)"`.

- [ ] **Step 1:** Tests:
  - `test_qa_chunk_from_input`: the bytes equal the source chunk; a Range request gives 206.
  - `test_qa_chunk_from_url`: against the local HTTP fixture server; the response holds no `Location`, `Server` or `X-Amz-*` upstream header, and no URL in the body.
  - `test_qa_chunk_traversal_404`: each Review Focus 3 case.
  - `test_qa_size_cap`.
  - `test_zarr_layer_sources_same_origin`: every `source` starts with `base + "/qa/data/"`; there is no `amazonaws`, no `appspot`, no token.
  - `test_oct_grouped_state`: 4 layers.
  - `test_viewer_index_no_identifiers`: `MICR_PLANTED` absent.
- [ ] **Step 2–4:** Implement, pass, commit `aimport micr: QA viewer reads reference datasets through the chunk map`.
- [ ] **Step 5 (manual, recorded):** in the image, open the CMC `Moe_Slice_051.ome.zarr` reference entry and the converted planted OME-TIFF in Neuroglancer. Save `aimport/docs/qa-viewer-micr.png` from the converted fixture only (no CMC pixels committed). Record any CSP change.

### Task 11: End-to-end leak test, datasets and docs

**Files:**
- Create: `tests/test_micr_end_to_end.py`.
- Extend: `micr_fixtures.planted_psoct(dest)`. This is a synthetic PS-OCT set in a `H17_250215/` folder: four contrast NIfTIs (microns, `descrip="Jane Doe 2025-02-15"`), a `.mat` v7.3 retardance volume with a planted `operator` attribute, raw `.dat` tiles, an `acqinfo_metadata.json` with an `operator` field, and a v3 OME-Zarr with planted array attributes.
- Modify: `tests/DATASETS.md`, `aimport/README.md`.

**Tests**
- Docker, using the real app through the API with a recording LLM client, as `test_end_to_end.py` does, run on `planted_psoct` + `planted_ome_tiff` + `planted_svs`:
  - `test_micr_e2e_validated`: the stage reaches `validated`.
  - `test_micr_e2e_no_leak`. None of `MICR_PLANTED` appears in:
    - any LLM request, `plan.json`, `scan.json`, `status.json`, or the bodies of `/plan`, `/status`, `/events` and `/viewer/*`;
    - any byte under `output/bids/`.
  - `test_micr_e2e_no_copy`: the work folder minus `output/bids` is under 2 MiB (records only); the input mtime and contents are unchanged.
  - `test_micr_e2e_raw_excluded_and_reported`.
  - `test_micr_e2e_label_macro_absent`: no array has the label or macro shape.
  - `test_bids_examples_micr`: one parametrised docker test re-imports each of `micr_SPIM`, `micr_SEMzarr`, `micr_XPCTzarr` and `micr_SEM` from `bids-examples` at a pinned commit. Each gives `validated`; the subject and sample labels are kept; `samples.tsv` rows are preserved.
- `network` (manual run, recorded): `test_cmc_plan_remote` scans a remote CMC subset (one en-face NIfTI per contrast, `Moe_Slice_051.ome.zarr`, one exaSPIM position). It checks that the plan builds, the reference/convert modes are right, and `ByteCounter.total < 32 * 2**20`.

**DATASETS.md**
- `bids-examples` micr sets: commit, contents, used by.
- CMC remote-read subsets: exact keys, `apex-connects` us-east-2, "no licence stated: read only, network-marked tests, nothing committed or downloaded whole", bytes read per test.
- The synthetic fixtures with their planted values.
- The sparse BigTIFF.

**README**
- A new "Microscopy" section:
  - accepted formats and unsupported ones (with the message);
  - reference datasets vs conversion, and the size report;
  - `--remote`;
  - what is never copied;
  - the NGFF version and the Task 1 ruling.

- [ ] **Step 1–3:** Write the tests, pass in the image, commit `aimport micr: end-to-end leak test, datasets and docs`.

### Task 12: `bl aimport` streamed upload of reference datasets and `--remote` (cli repo)

**Files:**
- Create: `cli/aimport/chunks.js`, `cli/aimport/micr-walk.js`, `cli/test/aimport-chunks.test.js`.
- Modify: `cli/aimport/upload.js` (`preflight`), `cli/bids-upload.js` (`do_upload` appends chunk streams), `cli/bl-aimport.js`, `cli/README.md`.

**Interfaces:**
- `loadChunkMap(work, bidsDir, inputDir, manifest) -> ChunkMap | null` reads the `chunk_map` path from `/status` (relative to `work`).
- `preflight(outputDir, {chunkMap, manifest, inputDir})`: the existing checks, plus:
  - every `arrays` key is a normalised path strictly inside a manifest entry ending in `.ome.zarr`;
  - `input` sources resolve (`fs.realpathSync`) inside `inputDir`;
  - `url` sources are `https:` with no userinfo;
  - the chunk map is the **only** extra source list, so symlinks remain refused;
  - nothing named `*.chunks.json` sits under `outputDir`.
- `openSource(src, key) -> {stream, size}`:
  - local: `fs.createReadStream` with the size from `fstat`;
  - URL: `fetch` with `redirect: "manual"`; same-host or `*.amazonaws.com` redirects only; size from `Content-Length`;
  - 404 → `null` (fill value, skipped).
- `micrDatasets(bidsDir, plan, manifest, datatypesByName) -> datasets`: one `neuro/ome-zarr` object per micr entry, with `datatype_tags = entry.brainlife_tags` and `meta.subject`/`session`/`sample`. The file id is read from the registered datatype's `files[0].id`.
- `do_upload(..., {chunkMap})`: metadata files are appended as today. Chunks are appended one at a time with `archive.append(stream, {name, stats: {size, mode: 0o644, mtime}})`, so archiver's tar plugin streams them without buffering. There is no new dependency, and no chunk is written to disk.
- `--remote <url>` (repeatable) is passed to `POST /scan` as `remote`.
- The size report: before upload, print `"<n> objects, <GB> from local output, <GB> streamed from sources"` and follow the existing `--yes`/prompt rules.

**Tests** (`node:test`, local HTTP server, fake deps)
- `test_preflight_refuses` with: a prefix outside the manifest dir, a `..` source, a symlink source escaping the input, an `http:` or `file:` URL, a `*.chunks.json` inside the output.
- `test_streams_without_buffering`: a 64 MiB source; heap growth stays under 16 MiB during `do_upload` into a counting sink.
- `test_missing_chunk_skipped`.
- `test_redirect_other_host_refused`.
- `test_micr_objects_mapped`: tags `["OCT"]`, datatype `neuro/ome-zarr`.
- `test_remote_flag_forwarded`.
- `test_no_chunk_map_unchanged`: phase-1 MRI uploads behave as before.

- [ ] **Step 1–4:** Implement, pass with `node --test test/aimport-*.test.js`, commit `bl aimport: stream reference-dataset chunks from their source; --remote`.

---

## Not in this plan

- Writing to a remote destination (brainlife project storage) as the conversion target. The spec allows it; it is a follow-up.
- Registering brainlife "external" (S3-pointer) datasets instead of streaming. Warehouse supports `storage: "external"` for `neuro/ome-zarr`; that is an alternative to raise with Franco, not a change here.
- OME-TIFF output for small 2D images (left to the builder by the spec; everything is OME-Zarr here).
- A Bio-Formats (`bioformats2raw`) stage.
- Linking a microscopy donor to an MRI subject of the same person (`micr:` namespace).
- Full-scale upload tests of terabyte stores: only subsets are exercised.

### Critical Files for Implementation
- /Users/fp4834/git/brainlife/ezbids/aimport/src/aimport/server.py
- /Users/fp4834/git/brainlife/ezbids/aimport/src/aimport/planner.py
- /Users/fp4834/git/brainlife/ezbids/aimport/src/aimport/writer.py
- /Users/fp4834/git/brainlife/ezbids/aimport/src/aimport/ezbids_runner.py
- /Users/fp4834/git/brainlife/cli/aimport/upload.js
