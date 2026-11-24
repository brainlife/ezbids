# Test and validation datasets

Every dataset the aimport engine is tested or validated against, pinned so a
result can be reproduced later. Add a row whenever a dataset is added, replaced
or dropped, and say why.

## Imaging data

| Dataset | Pinned commit | Status | Used by |
|---|---|---|---|
| [neurolabusc/dcm_qa_xa30](https://github.com/neurolabusc/dcm_qa_xa30) | `371ab3071aa9270d23b99fca5f83fe0c35932182` | **current** | `tests/fixtures/fetch_dcm_qa.py`, the committed `tests/fixtures/ezbids_core_siemens.json`, all `docker` tests (with the planted recordings in the mixed import of `tests/test_ephys_end_to_end.py`), the `bl aimport` manual run (cli `test/aimport-manual.js`) |
| [neurolabusc/dcm_qa](https://github.com/neurolabusc/dcm_qa) | `8215e3e` | dropped 2026-11-24 | first version of the fixture (Tasks 2–3) |
| Synthetic OME-Zarr (`tests/fixtures/micr_fixtures.py` `ome_zarr`, written for this repo; no real pixels) | generated at test time, seed 0 | **current** | `tests/test_micr_validator.py` (microscopy Task 1: validator ruling) |
| Synthetic sparse BigTIFF (`tests/fixtures/micr_fixtures.py` `sparse_bigtiff`, written for this repo; no pixels) | generated at test time | **current** | `tests/test_modality.py` (microscopy Task 2: claimed input is never staged or copied), `tests/test_micr_readers.py` (Task 4: bounded open) |
| Synthetic microscopy reader fixtures (`tests/fixtures/micr_fixtures.py` `planted_ome_tiff`, `planted_svs`, `psoct_nifti`, `psoct_mat`, `striped_tiff`, `visor_tile`; written for this repo, planted identifiers only) | generated at test time, seed 0 | **current** | `tests/test_micr_readers.py` (microscopy Task 4: readers, allowlisted metadata, bounded memory), `tests/test_micr_plan.py` (Task 6: plan entries, composite input below), `tests/test_micr_convert.py` (Task 8: conversion, self-check and write hook; inputs below) |
| CMC public bucket `apex-connects` (us-east-2; keys below). No licence stated: read only, network-marked tests, nothing committed or downloaded whole | keys pinned by listing, 2026-11-24 | **current** | `tests/test_micr_remote.py` `network` tests (microscopy Task 5: remote reads by range request), `tests/test_micr_plan.py`, `tests/test_micr_reference.py` and `tests/test_micr_end_to_end.py` `network` tests |
| [bids-standard/bids-examples](https://github.com/bids-standard/bids-examples) `micr_SPIM`, `micr_SEMzarr`, `micr_XPCTzarr`, `micr_SEM` only | `5e00d47b6f1db106dda1b776d5243eb41b4cb95b` (master, 2026-10-09) | **current** | `tests/fixtures/fetch_bids_examples.py`, `tests/test_micr_end_to_end.py` `test_bids_examples_micr` and `test_bids_example_micr_sem_nothing_to_write` (docker; microscopy Task 11) |
| Synthetic PS-OCT set (`tests/fixtures/micr_fixtures.py` `planted_psoct`, written for this repo; planted identifiers only) | generated at test time, seed 0 | **current** | `tests/test_micr_end_to_end.py` (microscopy Task 11: end-to-end leak test, with `planted_ome_tiff` and `planted_svs`) |

### Synthetic OME-Zarr (current)

`ome_zarr(dest, version, levels=2)` writes a `c,z,y,x` uint16 pyramid (y and x halved per level; 2
levels by default, 4 in `test_micr_remote.py` `test_coarse_level_only`), default shape `(2, 8, 64, 64)`,
pixel size 1.0 × 0.5 × 0.5 µm (z, y, x), random values from seed 0. NGFF `"0.5"` is Zarr v3 with one
shard per channel; `"0.4"` is Zarr v2. `strip_chunks` deletes every chunk and shard file, leaving only
Zarr metadata: what a reference dataset looks like locally.

### Synthetic sparse BigTIFF (current)

`sparse_bigtiff(size, dest)` writes a valid single-plane uint16 BigTIFF (rows of 32768 samples) whose
apparent size is `size` bytes (4 GiB in the tests) through `tifffile.memmap`, without writing any pixel:
the file is sparse and takes a few KiB on disk. Task 2 places it, together with planted folder names
(`H17_250215`) and a DICOM, under a claimed folder to show claimed input is never staged, walked or copied.

### Synthetic microscopy reader fixtures (current)

Written for Task 4; every identifier in them is listed in `tests/conftest.py` `MICR_PLANTED`.

| Fixture | What it is | Planted |
|---|---|---|
| `planted_ome_tiff(dest)` | OME-TIFF, `c,z,y,x` = 2 x 4 x 64 x 64 uint16 (seed 0), 0.5 x 0.5 x 2.0 um, channels 488/520 and 561/600 nm, 20x/0.8 water objective | OME-XML: Experimenter `Jane Doe` / `jdoe@example.org`, serial `SCOPE-SN-4711`, AcquisitionDate `2025-02-15T10:00:00`, Image Name and channel names `Slide 42 Smith`, Description `annotation secret`, a CommentAnnotation and an ROI label. TIFF tags: Artist `Jane Doe`, HostComputer `lab-workstation-7`, Software `AcqSoft 9 lab-workstation-7`, DateTime `2025:02:15 10:00:00` |
| `planted_svs(dest)` | Aperio-style SVS: tiled 512 x 512 RGB baseline plus a 256 x 256 level, thumbnail, label (subfiletype 1), macro (subfiletype 9); MPP 0.499, AppMag 20 | label and macro pixels are the bytes of `Slide 42 Smith`; description `Filename = Slide 42 Smith`, `User = Jane Doe` |
| `psoct_nifti(dest, contrast)` | float32 NIfTI 32 x 24 x 4, zooms 10 x 10 x 2.5, `xyzt_units` micron | optional `descrip` |
| `psoct_mat(dest, v73)` | v7.3: HDF5 with a 512-byte MATLAB header and a 256^3 float32 (64 MiB) `retardance` dataset whose chunks are never written (a few KiB on disk). v5: 16 x 12 x 4 float32 via `scipy.io.savemat` | optional `operator` string |
| `striped_tiff(dest, (6000, 6000), uint16)` | uncompressed single plane, 16 rows per strip, pixels never written (sparse, ~30 KiB on disk) | none |
| `visor_tile(dest_dir)` | `visor_488_Pos0/visor_488_0001.tif` (4 x 32 x 32 uint16) plus `acqinfo_metadata.json` | `operator` `Jane Doe`, `host` `lab-workstation-7`, `date` `20250422` |

**VISoR `acqinfo_metadata.json` key names.** The fixture's keys are synthetic: `pixel_size`,
`z_step`, `wavelength` (numeric, kept) and `operator`, `host`, `date` (strings, dropped as terms). The
reader (`readers.visor_facts`) matches key names by pattern: pixel/voxel size, spacing or resolution
(x, y); z step, slice thickness/spacing, or `x_step` (z); wavelength, laser, excitation or channel
between 350 and 900 (excitation nm, numeric or text such as `488nm`). The real CMC key names are
recorded under "CMC public bucket" below; `test_visor_real_key_names` uses them with synthetic values.

**Task 6 composite input (`tests/test_micr_plan.py` `micr_input`).** `cmc_tree` (the CMC layouts,
empty stand-ins) with readable files written over it: the four `psoct_nifti` contrasts of slice 51,
`ome_zarr` stores at `Moe_Slice_051.ome.zarr` (0.5) and `exaSPIM.zarr/Pos0` (0.4), two VISoR positions
(`visor_488_Pos0/1`, 4 x 32 x 32 uint16 zeros) with an `acqinfo_metadata.json` using the real CMC key
names and synthetic values (0.96 um, `x_step_um` 2.5, `488nm`, `frames_per_file` 4), and
`planted_ome_tiff` in `H17_250215/`. The raw `.dat` tile stays empty. Planted: the folder names
(`H17`, `250215`, `MN27`, `20250422`, `Moe`) and the OME-TIFF's own identifiers, all in `MICR_PLANTED`.

**Task 8 inputs (`tests/test_micr_convert.py`).** `micr_input`: `planted_ome_tiff` in `H17_250215/`
(AcquisitionDate 2025-02-15), one `psoct_nifti` retardance volume under
`PS-OCT/Enface/Registration/Retardance/`, and `visor_tile` in `MN27_20250422_visor_488/` (folder date
2025-04-22). `test_samples_tsv` and `test_bids_micr_sidecar_not_companion`: a BIDS-shaped micr input,
`sub-01/micr/sub-01_sample-A_CONF.ome.tif` (`planted_ome_tiff`) with its own `.json` sidecar, a
`psoct_nifti` named `sub-01_sample-B_acq-retardance_OCT.nii.gz`, a `photo` PNG stand-in (4 bytes) with
a sidecar, and a supplied `samples.tsv` (`sample-A`/`sub-01`/`cell line`/`lab B`, plus `sample-Z` of a
`sub-99` not in the import). `test_convert_bounded_memory` converts `striped_tiff` 6000 x 6000 with the
block limit patched to 4 MiB (after a 600 x 600 warm-up). All synthetic, generated at test time.

**Task 9 inputs (`tests/test_micr_reference.py`).** `ome_zarr` stores (0.5 and 0.4) at
`Moe_Slice_051.ome.zarr`; one 0.5 store with planted array `attributes` (`operator` "Jane Doe",
`note` "annotation secret") and an `OME/METADATA.ome.xml` from `_planted_ome_xml`; one with a level-2
scale of 8 where the size says 4; one with its chunks stripped (`strip_chunks`); and the same store
served by the local Range server for the remote reference. All synthetic, generated at test time.

**Task 10 inputs (`tests/test_viewer_routes.py`, `tests/test_viewer.py`, `tests/test_micr_readers.py`,
`tests/test_micr_convert.py`).** The QA viewer's `/qa/data` tests add an `ome_zarr` 0.5 store at
`Moe_Slice_051.ome.zarr` (in the input folder, or under `CMC/` on the local Range server, which also sends
`X-Amz-*`, `ETag` and `Server` headers) as a reference entry of the executed MRI fixture run. `micr_run` scans and
executes, through the server, the four `psoct_nifti` contrasts under `PS-OCT/Enface/Registration/<Contrast>/`, an
`ome_zarr` 0.5 store `Moe_Slice_051.ome.zarr` (a reference, no omero block) and `planted_ome_tiff` in
`H17_250215/`. The en-face tests use `psoct_nifti` with shapes 32 x 1 x 24, 1 x 32 x 24 and 64 x 1 x 48 (as the
CMC en-face files are stored). All synthetic, generated at test time.
`docs/qa-viewer-micr.png` shows `planted_ome_tiff` with shape 2 x 8 x 256 x 256 (seed 0), converted by a real
engine run and opened in the built client in headless Chromium; no CMC pixel is committed.

**Task 10b inputs.** `cmc_psoct_zarr` (`tests/fixtures/micr_fixtures.py`, used by
`test_cmc_metadata_faults_corrected`): metadata only (no chunk), a tenth-size copy of the CMC PS-OCT store's layout
and faults read from its public `zarr.json`: `c,y,x` float32 at `PS-OCT/Zarr/Moe_Slice_051.ome.zarr/scale<k>/image`,
level 0 4 x 850 x 1100, chunks 4 x 256 x 256, zstd, consolidated, axes without units, a translation of 1.0 on `c`,
and levels 3, 4, 5 declaring 16, 64 and 256 for arrays reduced 8, 16 and 425/550 times. `ome_zarr` gained a
`dtype` (float32: values in 0..1) for `test_real_omero_window_kept_by_the_viewer`, whose store has an omero
window of 0..1 per channel. `test_micr_input_executes_with_uint16_references` executes `micr_input` (with its
VISoR `acqinfo_metadata.json` saying `dtype: "uint16"`) through the server. The remote donor tests use the real
CMC key names (listed anonymously, 2026-11-24) without reading them; `test_remote_without_donor_grouped_by_folder_and_slice`
uses made-up `lab.s3.amazonaws.com` URLs, never fetched. `docs/qa-viewer-index-micr.png` is the restyled
`/viewer/` index of a real engine run over synthetic input only (the `micr_run` inputs); `docs/qa-viewer-micr.png`
was re-shot from the same run after the channel-position fix (both channels now drawn).
`test_reference_window_level_and_nan`: an `ome_zarr` float32 0.5 store with 4 levels, channel 1 of level 1 set to
NaN and four ±inf/NaN values planted in channel 0. All synthetic,
generated at test time.

### bids-examples micr datasets (current)

`fetch_bids_example(name, dest)` downloads the bids-examples tarball at the pinned commit (about 16 MB, cached in
`/tmp/aimport-bids-examples-cache`, or the `cache` argument) and extracts only `<name>/`. The four datasets are
BIDS `micr` layouts whose image files are mostly placeholders (the validator does not read pixels):

| Dataset | Contents | Re-imported as |
|---|---|---|
| `micr_SPIM` | `sub-01`, samples `A` and `B`, `stain-LFB`, `chunk-01`..`04` `_SPIM.ome.tif` (2,668 bytes each: real 1 x 1 OME-TIFFs), sidecars with `PixelSize`, 1-byte `photo.png` placeholders, `samples.tsv` (2 rows) | 8 converted `SPIM` entries, `validated`; subject `01`, samples `A`, `B`, `chunk-01`..`04` and the `samples.tsv` rows kept; the photos reported ("photographs are not imported") |
| `micr_SEMzarr` | `sub-01`, `ses-01`/`ses-02`, sample `A`: a Zarr v2 / NGFF 0.4 `_SPIM.ome.zarr` (64 x 64, dtype `>u1`, axes with `units` instead of `unit`, scale 1; one 128-byte chunk), 1-byte `_SEM.png` placeholders, sidecars (`PixelSize` 0.18 um) | the store referenced (pixel size and unit from its sidecar, dtype read as `|u1`), the PNGs reported unsupported, `validated` |
| `micr_XPCTzarr` | `sub-01`, `ses-01`, sample `brain`: a Zarr v2 / NGFF 0.4 `_XPCT.ome.zarr` whose metadata says 6991 x 5965 x 5965 uint16 (one empty chunk file), axes with `units`, a sidecar (`PixelSize`, `um`), a 133 KB photo JPEG, `code/`, `samples.tsv` with free-text columns | the store referenced as `XPCT` (the suffix from its BIDS name, sample `brain` kept, unit from the sidecar), `validated`; the free-text `samples.tsv` columns dropped by the default column rules, the rows kept |
| `micr_SEM` | `sub-01`, `ses-01`/`ses-02`, sample `A`: 1-byte `_SEM.png` and photo placeholders | no image can be written (the SEM PNGs are reported, never read; the photos are not imported): `POST /execute` is refused with 400 "nothing to write: every entry is excluded or unsupported" (`test_bids_example_micr_sem_nothing_to_write`) |

### CMC public bucket `apex-connects` (current)

Public S3 bucket `apex-connects` (region us-east-2), read anonymously over
`https://apex-connects.s3.amazonaws.com/`. **No licence stated: read only, network-marked tests,
nothing committed or downloaded whole.** Every `network` test passes a byte cap to its
`ByteCounter` (reads stop past it) and asserts the total. Keys were pinned on 2026-11-24 by listing
the bucket anonymously (S3 ListObjectsV2, prefixes only); there is no commit to pin, so a
changed or removed key shows up as a failing `network` test.

| Test | Key (under `s3://apex-connects/`) | What it is | Read | Cap | Bytes read (2026-11-24) |
|---|---|---|---|---|---|
| `test_cmc_psoct_zarr_metadata` | `CMC/Derivatives/Moe/PS-OCT/Zarr/Moe_Slice_051.ome.zarr` | PS-OCT slice, NGFF 0.5 / Zarr v3 with consolidated metadata, axes `c,y,x`, 6 levels (`scale0/image` 4 x 8500 x 11000 float32 to `scale5/image` 4 x 16 x 21), zstd, not sharded | metadata plus the whole coarsest level | 32 MiB | 15,271 |
| `test_cmc_psoct_zarr_reference` (`tests/test_micr_reference.py`, Task 9) | `CMC/Derivatives/Moe/PS-OCT/Zarr/Moe_Slice_051.ome.zarr` | the same PS-OCT store, referenced: its scales say 16 and 64 for levels 3 and 4, whose sizes are 1/8 and 1/16 of level 0 (the rebuilt metadata follows the sizes); its axes have no units (planned unit unknown; the test sets um) and its translation has 1.0 on `c` (Task 10b asserts units, scales and translation in the rebuilt metadata) | group and array metadata only (no chunk) | 1 MiB | 13,118 |
| `test_cmc_exaspim_position` | `axonal_connectomics/deskewed/H17_PO10_S5_20250417/exaSPIM.zarr/Pos0` | exaSPIM position, Zarr v3 **sharded** (`sharding_indexed`, inner chunks 64^3, blosc), NGFF 0.4-style `multiscales` attributes (no `ome` key), axes `t,c,z,y,x`, 6 levels (level 0 1 x 1 x 45256 x 14192 x 2660 uint16), 0.65 x 0.748 x 0.748 um | metadata plus one 64^3 inner chunk of the coarsest level | 32 MiB | 23,595 |
| `test_cmc_visor_tile_header` | `CMC/Raw/Moe/tract-tracing/MN27_FH_S100_250215_visor_488/visor_488_Pos0/visor_488_0_0.tif` (4,286,188,560 bytes) and `.../MN27_FH_S100_250215_visor_488/acqinfo_metadata.json` (4,127 bytes) | VISoR raw tile: classic (not Big) TIFF written by Micro-Manager (NDTiff v3 header, `MicroManagerMetadata` tag per page, no index map in the file), pages 1024 x 2048 uint16, uncompressed, one 4 MiB strip per page, ~1025 pages (`frames_per_file`) | first IFD, the first page's one strip, and the metadata JSON (only that small JSON; never `dbpost.json` or `hh.log`) | 8 MiB | 4,325,380 |
| manual QA viewer render (Task 10; not a test, screenshots not committed) | `CMC/Derivatives/Moe/PS-OCT/Zarr/Moe_Slice_051.ome.zarr` and `.../Enface/Registration/Retardance/Slice_001_EnR_hdr.nii.gz` | the PS-OCT store referenced and viewed through `/qa/data` (only the chunks Neuroglancer asks for at the zoom shown, plus the whole coarsest level for the display window); the en-face file converted (it is read whole: 14 MB) to check the n x 1 x m squeeze | chunks in view, coarsest level, one en-face file | 32 MiB window read; 64 MiB per proxied response | not counted |
| `test_cmc_enface_contrasts_one_subject` (`tests/test_micr_plan.py`, Task 10b) | `CMC/Derivatives/Moe/PS-OCT/Enface/Registration/Reflectivity/Slice_001_EnRef_hdr.nii.gz` (13,091,561 bytes) and `.../Retardance/Slice_001_EnR_hdr.nii.gz` | PS-OCT en-face reflectivity and retardance of slice 1, scanned and planned: one subject (donor `Moe`, from the folder) | header and the first voxel of each | 32 MiB (asserted on the sum) | 524,292 |
| `test_cmc_plan_remote` (`tests/test_micr_end_to_end.py`, Task 11) | `CMC/Derivatives/Moe/PS-OCT/Enface/Registration/Reflectivity/Slice_001_EnRef_hdr.nii.gz`, `.../Retardance/Slice_001_EnR_hdr.nii.gz`, `.../Orientation/Slice_001_EnAO_hdr.nii.gz` (14,924,392 bytes), `.../Cross/Slice_001_EnCr_hdr.nii.gz` (2,618,514 bytes), `CMC/Derivatives/Moe/PS-OCT/Zarr/Moe_Slice_051.ome.zarr` and `axonal_connectomics/deskewed/H17_PO10_S5_20250417/exaSPIM.zarr/Pos0` | one en-face NIfTI per contrast, the PS-OCT store and one exaSPIM position, given as `remote` to `POST /scan` and planned through the API: 4 `OCT` entries to convert (one subject), 2 references | discovery probes, NIfTI headers, store metadata (every `ByteCounter` of the run summed) | 32 MiB | 1,092,042 (12 counters) |
| `test_cmc_enface_nifti_header` | `CMC/Derivatives/Moe/PS-OCT/Enface/Registration/Retardance/Slice_001_EnR_hdr.nii.gz` (14,011,625 bytes) | PS-OCT en-face retardance, gzipped NIfTI-1, float32, 11000 x 1 x 8740, units mm | header and the first voxel (gzip from the start) | 1 MiB | 262,146 |

**Real VISoR `acqinfo_metadata.json` key names** (read from the JSON above; values shown only for
the facts used): `version` (`"0.0.3"`), `channels` (1), `excitation_wavelengths` (list of text,
`["488nm"]`), `positions[]` with `x_start_um`, `x_end_um`, `y_start_um`, `z_start_um`, `x_step_um`
(2.5), `settings` with `sheet_angle` (45.0), `pixel_spacing_um` (0.96), `image_size_xy` ([2048, 1024]),
`frames_per_file` (1025), `strip_overlap_pixels`, `dtype` (`"uint16"`), `flipped`, `rotated`, and
`stripdirs`, `file` (strings). These differ from the synthetic fixture's names, so `visor_facts` now
also reads wavelengths written as text and takes `x_step` (the stage step between the frames of a
raw tile; VISoR scans along stage x) as the z spacing: 0.96 x 0.96 x 2.5 um, excitation 488 nm.

**Reading a whole remote multi-page TIFF is not cheap.** The tile's IFDs sit one per 4 MiB page and
are not evenly spaced (each page carries a variable-length `MicroManagerMetadata` tag), so counting
the pages walks the IFD chain: one range read per page (~64 MiB at the 64 KiB file block size).
`open_remote(url, "tiff")` does that under its byte cap; the network test reads the first page only.

**Task 11 inputs.** `planted_psoct(dest)` writes `dest/H17_250215/` (donor `H17`, date `250215` in the folder
name):

| File | What it is | Planted |
|---|---|---|
| `PS-OCT/Enface/<Reflectivity, Retardance, Orientation, Cross>/Slice_051_1.nii.gz` | the four `psoct_nifti` contrasts (32 x 24 x 4 float32, microns) | `descrip` `Jane Doe 2025-02-15` |
| `PS-OCT/Volume/Slice_051_retardance.mat` | `psoct_mat` v7.3, 256^3 float32 never written (sparse; no pixel size: the test sets 10 x 10 x 2.5 um as a reviewer would) | `operator` attribute `Jane Doe` |
| `PS-OCT/raw/Slice_051_Tile_000<1,2>.dat` | raw interferometer tiles (planned `unsupported`, never read) | the bytes `operator=Jane Doe;host=lab-workstation-7;date=2025-02-15;` repeated |
| `acqinfo_metadata.json` | VISoR-style metadata beside no tile | `operator` `Jane Doe`, `host` `lab-workstation-7`, `date` `20250422` |
| `PS-OCT/Zarr/H17_Slice_051.ome.zarr` | `ome_zarr` 0.5 (referenced) | array attributes `operator` `Jane Doe`, `note` `annotation secret` |

The end-to-end run adds `planted_ome_tiff` at `confocal/stack.ome.tif` and `planted_svs` at `histology/slide.svs`.
The leak check reads every name and metadata document under `output/bids` for every `MICR_PLANTED` term, and the
pixel chunks for every term of 6 or more characters, the SVS label text and the raw tiles' bytes (before and after
decoding): a 3-4 byte code such as `h17` does turn up by chance in compressed random pixels (it did, in the SVS
chunk). `tests/test_micr_bids_input.py` (host) uses `ome_zarr` and `planted_ome_tiff` under BIDS names
(`sub-01_ses-01_sample-brain_XPCT.ome.zarr`, `sub-01_sample-A_SPIM.ome.zarr` with units removed and a sidecar,
`>u1` uint8 stores, 8-byte PNG and 2-byte JPEG stand-ins). The display-window tests (`test_micr_convert.py`,
`test_viewer_routes.py`) use tissue values 57..66 (seed 0) on a zero or fill-value (7) background. All synthetic.

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

## Electrophysiology and optical data

| Dataset | Pinned commit | Status | Used by |
|---|---|---|---|
| [mne-tools/mne-testing-data](https://github.com/mne-tools/mne-testing-data) (licence BSD-3): the 55 files below | `20cc221d737a37a6ee3a9c007e91bd69541fefe9` | **current** | `tests/fixtures/ephys_fixtures.py` `fetch_mne_testing`; `tests/test_ephys_fixtures.py` `test_fetch_hashes` (`ephys_data`); `tests/test_ephys_capability.py` `test_anonymize_forces_conversion[meg-FIF]`; `tests/test_ephys_readers.py` `test_mne_testing_readers`, `test_testing_data_terms`, `test_headshape_not_read_by_default`, `test_meg_system_header_terms` (`ephys_data`; EGI `.mff` is expected `Unsupported` while `mffpy` is not installed; BTi `erm_HFH` has no `hs_file`, so only KIT checks `headshape=True`); `tests/test_ephys_end_to_end.py` `test_mne_testing_e2e` (`docker`, `ephys_data`: one import through the API per family of `MNE_TESTING_FAMILIES`, each `validated`; EGI is expected `unsupported` with `EGI .mff needs the mffpy package`); `tests/test_ephys_write.py` `test_gdf_written` (`ephys_data`) |
| [bids-standard/bids-examples](https://github.com/bids-standard/bids-examples); data files are empty: layout and validator only | `5e00d47b6f1db106dda1b776d5243eb41b4cb95b` (2026-10-09) | **current** | `tests/fixtures/ephys_fixtures.py` `fetch_bids_examples`; `tests/test_ephys_capability.py` `test_validator_ephys_examples` (`docker`); `tests/test_ephys_end_to_end.py` `test_bids_examples_ephys` (`docker`: the layout of one run per set, below) |
| Synthetic planted recordings (`planted_edf`, `planted_bdf`, `planted_brainvision`, `planted_eeglab`, `planted_fif`, `planted_snirf`, `planted_ctf_pos`, `planted_kit_hsp`, `planted_nwb`; written for this repo, random signals, seed 0) | generated at test time | **current** | `tests/test_ephys_fixtures.py`; `tests/test_ephys_readers.py`; the ephys leak tests of Phase 3; all nine in the mixed import of `tests/test_ephys_end_to_end.py` (`docker`) |
| Synthetic recordings written inside `tests/test_ephys_write.py` (written for this repo, random signals, seed 0): small EDF+ files with `SEEG`/`EMG` label prefixes (`edf`, patient code, sex F, birth date 1980-06-30), 4-channel MEG FIFs with fiducials, HPI and optional head-shape points (`meg_fif`, one as an empty room), and a MATLAB v7.3 EEGLAB `.set` holding a variable-length string dataset | generated at test time | **current** | `tests/test_ephys_write.py` (the writer, leak and validator tests; `test_ephys_output_validates` is `docker`); `planted_edf`, `planted_brainvision`, `planted_fif` and the mne-testing-data CTF/KIT/BTi files are also used there (`ephys_data` for the downloads) |
| Synthetic recordings written inside `tests/test_ephys_snirf_nwb.py` (written for this repo): a 256 MiB 64-channel float32 NWB `ElectricalSeries` (`_big_nwb`, ramp values, filled chunk by chunk with h5py), a 20-channel 60 s MEG empty-room FIF (random, seed 0) split by MNE-BIDS at a 3 MB `split_size`, two empty rooms 100 days apart (`meg_fif`), a copy of `planted_snirf` as a second run, and a `planted_snirf` with an extra `lastName` tag, an `aux1` group and a root `notes` dataset | generated at test time | **current** | `tests/test_ephys_snirf_nwb.py` (`test_nwb_bounded`, `test_split_emptyroom_readable`, `test_each_emptyroom_has_its_own_daysback`, `test_session_files_listed_once`, `test_snirf_rewrite_drops_unknown`); `planted_snirf`, `planted_nwb` and the mne-testing-data NIRx NIRScout folder and NIRSport2 SNIRF are also used there (`test_nirx_hitachi_to_snirf`, `ephys_data`; `test_nirs_and_nwb_validate`, `docker`). No Hitachi file exists at the pinned commit |
| Synthetic recordings written inside `tests/test_ephys_qa.py` (written for this repo): a 2-channel 1-hour 1 kHz FIF of zeros (float32, 29 MB, deleted with the test folder) and a 1-channel 200 s 1 kHz FIF with one +1000 µV and one -250 µV single-sample spike | generated at test time | **current** | `tests/test_ephys_qa.py` (`test_traces_limits`, `test_traces_min_max_keeps_peaks`); `planted_edf`, `planted_snirf` and `planted_nwb` written through the module give the snapshot, trace-window and route tests their output, and the README screenshot `docs/qa-viewer-traces.png` (planted EDF and SNIRF only) |
| Synthetic channel tables written inside `tests/test_ephys_bad_channels.py` (written for this repo): a 3-row iEEG `channels.tsv` without `status_description` and its `channels.json`, a 1-row EEG table; `planted_edf` and `planted_nwb` written through the API give the bad-channel route tests their output, and the README screenshot `docs/qa-viewer-bad-channels.png` (planted EDF, `Fp1` and the renamed `eeg_002` marked bad) | generated at test time | **current** | `tests/test_ephys_bad_channels.py` (`test_marks_pass_the_bids_validator` is `docker`) |
| Synthetic headers written inside `tests/test_ephys_readers.py` (written for this repo): a 64 MiB sparse 64-channel BDF (`_big_bdf`, zero data), a MATLAB v7.3 EEGLAB `.set` (h5py), a SNIRF with a custom `metaDataTags` entry, and Hitachi `.csv`, Persyst `.lay`, Neuroscan `.cnt`, Blackrock `.ns5`/`.nev` headers carrying the planted values; patched copies of `planted_edf` (numeric codes, an anonymized `01.01.85`/`X X X X` source), a corrupt CTF `.res4`, a NIRSport2-style folder holding `planted_snirf`, SNIRF landmark/data labels, typed BrainVision comments, an EGI `categories.xml` | generated at test time | **current** | `tests/test_ephys_readers.py` `test_preload_false`, `test_eeglab_v73_harvest`, `test_snirf_custom_tags`, `test_other_format_headers` and the fix-round tests |
| Synthetic inputs of `tests/test_ephys_end_to_end.py` (written for this repo): the empty-room pairing fixture (`meg_fif(..., his_id=None)` named `emptyroom_raw.fif`, 4 magnetometers, 2 s, 2025-02-15 09:00 UTC, one hour before `planted_fif` on the same day, so the planted MEG run pairs with it); an Artinis `Smith_John_rest.oxy4` stub (`OXY4` and 60 zero bytes, never read); an EMG EDF+ (`edf`, `EMG L1`/`EMG L2`, patient code `P3333333`) for the datatypes target; and per bids-examples set one recording under a neutral name (`synthetic/recording_raw.fif`: a `RawArray` of the example's channel names and types from its `channels.tsv`, at most 64, random seed 0, 10 s at 256 Hz, two annotations when the example has `events.tsv`; a clean CW SNIRF for `nirs`; `meg_fif` for `ds000247`, whose CTF axial gradiometers have no `RawArray` form) | generated at test time | **current** | `tests/test_ephys_end_to_end.py` (`docker`) |
| Synthetic EDF+ written inside `tests/test_ephys_write.py` `test_dotted_name_written`: `grid.v2_rest.edf` (`edf`, `Fz`/`Cz`), a file name with more dots than its extension | generated at test time | **current** | `tests/test_ephys_write.py` |

### mne-testing-data files (current)

Downloaded file by file from `raw.githubusercontent.com` into `AIMPORT_EPHYS_CACHE` (default
`~/.cache/aimport-ephys`, which Colima mounts since it mounts only `$HOME`) under
`mne-testing-data-<commit>/<path>`; each file is checked against the SHA-256 below, and the total
(46,300,216 bytes, about 46 MB) stays under 80 MB (`MAX_TOTAL_BYTES`). Nothing is committed. Chosen as the
smallest file per format family; the planned `Hitachi/*.csv` does not exist at this commit, so Hitachi is not
covered. The empty CTF files `BadChannels` and `bad.segments` are not fetched, and neither are the macOS
`._*` resource forks of the EGI folder.

| Path | Bytes | SHA-256 | Covers | Licence |
|---|---|---|---|---|
| `EDF/test_reduced.edf` | 820188 | `644acaf3aa547d85d73ed4a7224008c55be1487227e5eb029274877e2c61a39a` | EDF / EDF+ (`read_raw_edf`) | BSD-3 |
| `EDF/test_utf8_annotations.edf` | 47648 | `e13bfacba83898370f38040f29a1503572686b33df680dd95147d87d19dfd7b8` | EDF / EDF+ (`read_raw_edf`) | BSD-3 |
| `BDF/test_bdf_stim_channel.bdf` | 61280 | `d555c9550069c0402835092ac3b2136ac238c8b8996069e11594350826d765a3` | BDF (`read_raw_bdf`) | BSD-3 |
| `GDF/test_1ch.gdf` | 18512 | `a01faf7b73742a01deae89e2f4cd18c581ca5c1f719417bf80ac2ef8a2923762` | GDF (`read_raw_gdf`) | BSD-3 |
| `Brainvision/test_NO.vhdr` | 1451 | `aa3f2d42a1ad3897e702c27d09abdd261f01ccdeb0dae2e674af25fe7be72261` | BrainVision (`read_raw_brainvision`) | BSD-3 |
| `Brainvision/test_NO.vmrk` | 267 | `fc02236e72a90124ea04f171a065ae94784ec707bbd96632a86a44499bf7cf27` | BrainVision (`read_raw_brainvision`) | BSD-3 |
| `Brainvision/test_NO.eeg` | 581880 | `894099d7ea0db262bd2dd84918ff96e5c81e39f7677f0405746faaed1623604b` | BrainVision (`read_raw_brainvision`) | BSD-3 |
| `EEGLAB/test_raw.set` | 349568 | `95593d49974d3ce8b0bd37e086536b9cedcf0abf38f2453092fd88de0bbde18e` | EEGLAB `.set` + `.fdt` (`read_raw_eeglab`) | BSD-3 |
| `EEGLAB/test_raw.fdt` | 3904512 | `3ec388b9a080c723c00cd380403d64cc754929d828375bbd53bd83b468136759` | EEGLAB `.set` + `.fdt` (`read_raw_eeglab`) | BSD-3 |
| `NihonKohden/MB0400FU.EEG` | 308031 | `a2900ceaa0479182e5845dc3f3f8ee4bd6800bd4ec9555a59008486253c42d0a` | Nihon Kohden (`read_raw_nihon`) | BSD-3 |
| `NihonKohden/MB0400FU.PNT` | 7720 | `d1bbf1ff13de54407f3f3afe18ae004c3e23747f82c2b76eea977efd13985684` | Nihon Kohden (`read_raw_nihon`) | BSD-3 |
| `NihonKohden/MB0400FU.21E` | 24773 | `4704c38a17c5e04c6b46ddc3fac2f2ef5cb46ca27f9a7f3df1c5a970ee9eb3a1` | Nihon Kohden (`read_raw_nihon`) | BSD-3 |
| `NihonKohden/MB0400FU.LOG` | 495309 | `60262a77a8136c595eae7a4c1fb71853d806a83ef0a40e2c9fc03f0fbc0fa714` | Nihon Kohden (`read_raw_nihon`) | BSD-3 |
| `Persyst/sub-pt1_ses-02_task-monitor_acq-ecog_run-01_clip2.lay` | 1869 | `fa1aae5c47fd6c0e7d282fd27ee8c6a5d3ae06bb74687268a5f64fc00834138b` | Persyst `.lay` + `.dat` (`read_raw_persyst`) | BSD-3 |
| `Persyst/sub-pt1_ses-02_task-monitor_acq-ecog_run-01_clip2.dat` | 281204 | `b21b45af347f2fde710da46af66128be63058db2bcc6b566c2934fa42ce6b0ba` | Persyst `.lay` + `.dat` (`read_raw_persyst`) | BSD-3 |
| `CTF/somMDYO-18av.ds_raw.fif` | 516470 | `dff9637b1a85e8de0066948756c9254b237ebcd20d5681222324861bf19f4e9f` | FIF info source for `planted_fif` (MEG channel definitions; `read_info`) | BSD-3 |
| `KIT/test_as-raw.con` | 169728 | `4d3112d78286458e09beb2bdfd85cf9ee21f89abf9d02096704aebeaae0df23b` | KIT `.con` (`read_raw_kit`) | BSD-3 |
| `KIT/MQKIT_125.hsp` | 54395 | `f85eaaf44afaf71b5523a9a26f50df8d0838ea137b1b71c6e15e5226d00e4f4e` | KIT head-shape / electrode companions (`.hsp`, `.elp`; claimed, never read into output) | BSD-3 |
| `KIT/MQKIT_125.elp` | 734 | `833f7f20e452b822adad078207bba41b986b9594f58e0379f2d75bac38a51025` | KIT head-shape / electrode companions (`.hsp`, `.elp`; claimed, never read into output) | BSD-3 |
| `SNIRF/NIRx/NIRSport2/1.0.3/2021-05-05_001.snirf` | 244038 | `8867156c3b6e04a6abfaf5d14a86c2a4855f946bed0ef303ee589acb85d6bb31` | SNIRF (`read_raw_snirf`) | BSD-3 |
| `CTF/testdata_ctf.ds/ClassFile.cls` | 186 | `bd91e66437d53bfbb4cd03ce9394714b4ec4fd715bddfca3c4fabe965476378b` | CTF `.ds` MEG (`read_raw_ctf`) | BSD-3 |
| `CTF/testdata_ctf.ds/params.dsc` | 467 | `2b4dee7383882a1fc6f1d84d5ba4c3181c461f5d6aaf5af204cc534289e5fc92` | CTF `.ds` MEG (`read_raw_ctf`) | BSD-3 |
| `CTF/testdata_ctf.ds/processing.cfg` | 1185 | `c668cb17fbe4cfec9a29c3ec85ecaf7e61278df863fbe1a9ea8e77960db4baf4` | CTF `.ds` MEG (`read_raw_ctf`) | BSD-3 |
| `CTF/testdata_ctf.ds/testdata_ctf.acq` | 40798 | `e0837500432d5f8c5ff940a53778469c1a3bf83852355fa922f256c5adc08623` | CTF `.ds` MEG (`read_raw_ctf`) | BSD-3 |
| `CTF/testdata_ctf.ds/testdata_ctf.hc` | 824 | `37ee610fdcff3689b95c0e461fe7c18d5582109120bb39e6e12d651931eb515c` | CTF `.ds` MEG (`read_raw_ctf`) | BSD-3 |
| `CTF/testdata_ctf.ds/testdata_ctf.infods` | 2620 | `72d71ee90fea7a49b056a228101a9b84f91600585a000484061fbd7ea9f5c3b3` | CTF `.ds` MEG (`read_raw_ctf`) | BSD-3 |
| `CTF/testdata_ctf.ds/testdata_ctf.meg4` | 17088008 | `30ef47c85083ff3892d5565e487287f71146646a4bff6c283638939801c7f788` | CTF `.ds` MEG (`read_raw_ctf`) | BSD-3 |
| `CTF/testdata_ctf.ds/testdata_ctf.newds` | 350 | `5d2ace836414f294685574d3720f36ecd529b4b18668c8d54c9986e98b9e3cf9` | CTF `.ds` MEG (`read_raw_ctf`) | BSD-3 |
| `CTF/testdata_ctf.ds/testdata_ctf.res4` | 3260865 | `a75ccb0a74910d1f09f1e35944ced09591f3048a850718bcda95a83e16e27146` | CTF `.ds` MEG (`read_raw_ctf`) | BSD-3 |
| `EGI/test_egi.mff/Contents/Info.plist` | 365 | `6f27e762e8f58329bece4b4565ab93856edc8ce64a4b5e8994b7843562d80b1e` | EGI MFF (`read_raw_egi`) | BSD-3 |
| `EGI/test_egi.mff/Contents/PkgInfo` | 8 | `ffe6cb5c0493916f026fb8ba01b7b07c7746ca6cb0cb499051ec45575a3bbadb` | EGI MFF (`read_raw_egi`) | BSD-3 |
| `EGI/test_egi.mff/Events_255 DINs.xml` | 4495 | `a791b91c341a876b15cac3b9cf52f20e4f1f18d1910f0704af36224ff078af05` | EGI MFF (`read_raw_egi`) | BSD-3 |
| `EGI/test_egi.mff/coordinates.xml` | 30873 | `3c49e412457581cf74b6627453a3ab182e1f29263f4d3beab4eb077200d1b9f7` | EGI MFF (`read_raw_egi`) | BSD-3 |
| `EGI/test_egi.mff/epochs.xml` | 330 | `a887f8c70d2aa45a9a8f85b10108454b3dfd33f681d71740bc2fa499104bf262` | EGI MFF (`read_raw_egi`) | BSD-3 |
| `EGI/test_egi.mff/info.xml` | 403 | `0bb8648abe34e06c1adeb6caebce4c71aacc0d94091f424e74476eaa15bcc0b4` | EGI MFF (`read_raw_egi`) | BSD-3 |
| `EGI/test_egi.mff/info1.xml` | 13539 | `84a6d45f2848fe0463855f697b0bc6141d998e3589918014b72b517ba58af0e6` | EGI MFF (`read_raw_egi`) | BSD-3 |
| `EGI/test_egi.mff/log_testfile23022017_20170223_113514.txt` | 5683 | `cab955b4ffd09896a1e5890e09d4ad6f181fa30e7df0f1b38fbc9190dce14482` | EGI MFF (`read_raw_egi`) | BSD-3 |
| `EGI/test_egi.mff/recordingSettings.xml` | 90218 | `ac5aff6be185770496d890f18d8ab0d39a9d25aed3c4ca6486cbeff8d94c1eb2` | EGI MFF (`read_raw_egi`) | BSD-3 |
| `EGI/test_egi.mff/sensorLayout.xml` | 39497 | `43e8e4423bc3fc56f85b7cf3ff3106010d1f674505b0e2d555117b07360f9965` | EGI MFF (`read_raw_egi`) | BSD-3 |
| `EGI/test_egi.mff/signal1.bin` | 11315960 | `3069e20983ca2861bb16a6dc8e5edc32f988380ae9cd06821b7db221d43a0a33` | EGI MFF (`read_raw_egi`) | BSD-3 |
| `EGI/test_egi.mff/subject.xml` | 2458 | `09ca61cd8ca308a2c836647ca455acac803050dbb82f071d7472f0d611340dd6` | EGI MFF (`read_raw_egi`) | BSD-3 |
| `EGI/test_egi.mff/workspace.plist` | 31271 | `f91a4973940cac0e3bcfca88cf26d3df6e0990241413b5737386b3d7940a70cd` | EGI MFF (`read_raw_egi`) | BSD-3 |
| `NIRx/nirscout/nirx_15_3_recording/NIRS-2020-08-18_001.avg` | 1520 | `b91ca552e15f28e8658df35916a72383977303573f26dec53092ae866913d787` | NIRx NIRScout (`read_raw_nirx`) | BSD-3 |
| `NIRx/nirscout/nirx_15_3_recording/NIRS-2020-08-18_001.dat` | 60022 | `4d172da66436d9396ea4d4484dc49281ba3eb0b39503c66d5b85eb16e0e14e85` | NIRx NIRScout (`read_raw_nirx`) | BSD-3 |
| `NIRx/nirscout/nirx_15_3_recording/NIRS-2020-08-18_001.evt` | 60 | `94c5dfe1b32742bc79d7b27ad65d4e10d2d1fc76d13e4576cee7721b4c7c8640` | NIRx NIRScout (`read_raw_nirx`) | BSD-3 |
| `NIRx/nirscout/nirx_15_3_recording/NIRS-2020-08-18_001.hdr` | 1913 | `cd343473d1a2ca8f398e96036fc5fb7d7e4a5c7f8a75712e2148a128d16698b5` | NIRx NIRScout (`read_raw_nirx`) | BSD-3 |
| `NIRx/nirscout/nirx_15_3_recording/NIRS-2020-08-18_001.inf` | 157 | `3f67ad9e5618992cf0d0a80e296a57aa77e8734ed1ba5aec148cbfab0be97a58` | NIRx NIRScout (`read_raw_nirx`) | BSD-3 |
| `NIRx/nirscout/nirx_15_3_recording/NIRS-2020-08-18_001.set` | 165 | `1b20cedc00c50efdbccf2436e2a92edc2bb7bdf8895c9b4bc2bcc30ffa32c3d5` | NIRx NIRScout (`read_raw_nirx`) | BSD-3 |
| `NIRx/nirscout/nirx_15_3_recording/NIRS-2020-08-18_001.tpl` | 248 | `73aec2693a044208d833591cd4792fedc2d3f9da5698b827dc3cfc3677dadf65` | NIRx NIRScout (`read_raw_nirx`) | BSD-3 |
| `NIRx/nirscout/nirx_15_3_recording/NIRS-2020-08-18_001.wl1` | 176220 | `d10c33711c39fc24324044953417097e48c3ff15f62d764e0d8edf39c314488c` | NIRx NIRScout (`read_raw_nirx`) | BSD-3 |
| `NIRx/nirscout/nirx_15_3_recording/NIRS-2020-08-18_001.wl2` | 176220 | `c05358bfa1180c03a5e826eb0382e248280f7c659063b91660ea847babcb728b` | NIRx NIRScout (`read_raw_nirx`) | BSD-3 |
| `NIRx/nirscout/nirx_15_3_recording/NIRS-2020-08-18_001_config.txt` | 378 | `39bdc363ba37bf16f20fc1f247491acec03f26e61cf787ff5ee15e8699e178e6` | NIRx NIRScout (`read_raw_nirx`) | BSD-3 |
| `NIRx/nirscout/nirx_15_3_recording/NIRS-2020-08-18_001_probeInfo.mat` | 2429 | `24f7eb2879d115c1c77da1adc9810c0a39fdf6f85d62d6ab612f450b5e7d293a` | NIRx NIRScout (`read_raw_nirx`) | BSD-3 |
| `BTi/erm_HFH/c,rfDC` | 5941296 | `3d4582a3e0eb45820d902dd56dfcd1764285f3602da34e58f61e59cb38111b36` | BTi / 4D (`read_raw_bti`) | BSD-3 |
| `BTi/erm_HFH/config` | 119608 | `5cf549916dacd3ec3d0b006c64c39781d8e6114792b6a5add37c7d13b03e9c22` | BTi / 4D (`read_raw_bti`) | BSD-3 |

### bids-examples (current)

Shallow fetch of the pinned commit into `AIMPORT_BIDS_EXAMPLES_CACHE` (default
`/tmp/aimport-bids-examples-cache`) under `<commit>/`; the host copy lives in
`~/.cache/aimport-bids-examples/<commit>` and is mounted there. Data files are empty: layout and validator
only. All 15 names exist at the pinned commit. Sets used: `eeg_cbm`, `eeg_rest_fmri`,
`ieeg_epilepsy`, `ieeg_visual`, `ds000247` (MEG), `fnirs_tapping`, `fnirs_automaticity`,
`emg_ConcurrentIndependentUnits`, `emg_CustomBipolar`, `emg_CustomBipolarFace`, `emg_IndependentMod`,
`emg_MultiBodyParts`, `emg_Multimodal`, `emg_TwoHDsEMG`, `emg_TwoWristbands`. Validated with the repo's own
`default-config.json` (ignores `EMPTY_FILE`) and `--ignoreNiftiHeaders`, as its `run_tests.sh` does. The
`fnirs_tapping` task label `tapping` is never used in a leak test.

`test_bids_examples_ephys` takes, per set, the first raw recording (sorted) in an `eeg`, `meg`, `ieeg`, `nirs` or
`emg` folder whose entities are only `sub`, `ses`, `task`, `acq` and `run`, gives a synthetic recording those
entities by plan edits (labels that are not generic words are identifying path words by design, so the input
name is neutral), and checks that the recording and every sidecar the example has for that run are written under
the example's names (`space-` is not compared: the synthetic recording has no positions), then validates without
ignores. `emg_ConcurrentIndependentUnits` has no such run (every recording carries `recording-`) and is skipped
with that reason. A `.ds` example is written as FIF and a `.set` one as BrainVision under the same stem.

### Synthetic planted recordings (current)

`tests/fixtures/ephys_fixtures.py` writes each one to `dest/Smith_John_19700101/Smith_John_rest.<ext>`
(`planted_fif`: `Smith_John_rest_raw.fif`): 10 s at 256 Hz, meas_date 2025-02-15T10:00:00, random signals seed 0.
`tests/test_ephys_capability.py` still builds its own 4-channel EDF sources (`_edf_source`: `RawArray`, `his_id`
`MRN0042`, John Smith, birthday 1970-01-01, meas_date 2025-02-15 09:30 UTC) for the conversion rulings.

| Builder | Planted values |
|---|---|
| `planted_edf`, `planted_bdf` | patient `MRN0042 M 01-JAN-1970 Smith_John`; recording `Startdate 15-FEB-2025 EEGtech_Jane Hospital_X`; EDF+/BDF+ annotations `Smith John said hello`, `1`, `eyes closed`; channels `Fp1`, `Smith-Fp1`, `EMG1` |
| `planted_brainvision` | `.vhdr` `DataFile=Smith_John_rest.eeg` and a `[Comment]` section `Patient: Smith John, MRN0042`; `.vmrk` `Stimulus,S  1`, `Comment,Dr Jane Doe`, `New Segment` stamped 20250215100000 |
| `planted_eeglab` | `.set` `setname` `Smith John`, `subject` `MRN0042`, `comments` `Hospital X`, event type `MRN0042 start` |
| `planted_fif` | `subject_info` `his_id` `MRN0042`, John Smith, birthday 1970-01-01, sex 1; `experimenter` `Jane Doe`; `description` `Hospital X study`; `proj_name` `Smith pilot`; MEG channels of `CTF/somMDYO-18av.ds_raw.fif`; 3 fiducials, 4 HPI, 200 `EXTRA` dig points |
| `planted_snirf` | CW amplitude, 2 sources x 2 detectors x 760/850 nm; `metaDataTags` `SubjectID` `MRN0042`, `MeasurementDate` `2025-02-15`, `MeasurementTime` `10:00:00`, `Operator` `Jane Doe`; `stim1/name` `Jane Doe tapping` |
| `planted_ctf_pos`, `planted_kit_hsp` | 200 head-shape points each; companion files only |
| `planted_nwb` | iEEG, 8 channels; `session_description` `Smith John grid`; `experimenter` `Jane Doe`; `institution` `Hospital X`; `subject_id` `MRN0042`; `date_of_birth` 1970-01-01; trials note `seizure Dr Jane` |

The leak vocabulary is `conftest.EPHYS_PLANTED` (`PLANTED` plus `jane doe`, `jdoe`, `eegtech_jane`, `dr jane`,
`said hello`, `2025-02-15`, `20250215`, `15.02.25`, `15-feb-2025`, `01-jan-1970`, `smith pilot`, `smith-fp1`,
`tapping`); `ephys_tokens(text)` checks it alone. `tapping` is planted only in free text.

### OpenNeuro

| Run | Snapshot | Licence | Bytes | SHA-256 | Used by |
|---|---|---|---|---|---|
| fNIRS: `ds005929` (Motion-Yucel2014) `sub-6023/ses-1/nirs/sub-6023_ses-1_task-MA_run-01_nirs.snirf`, fetched alone by its versioned S3 URL (`versionId=lmKQm_w2QxdzkgxA28KQIfNoPDUqlv26`; `fetch_openneuro_fnirs`, cached under `AIMPORT_EPHYS_CACHE/openneuro/ds005929-1.0.1/`) | `1.0.1`, doi:10.18112/openneuro.ds005929.v1.0.1 | **CC0** (`License` in its `dataset_description.json`, checked 2026-11-24 before use) | 7333288 | `de264684c26f7e4294a22c23593f47fa44e1de2cf103190ffca96f0836820543` | `tests/test_ephys_end_to_end.py` `test_openneuro_fnirs_e2e` (`docker`, `ephys_data`): a Homer3 SNIRF with `aux` and 14 `stim` groups; its `MeasurementDate` 2024-11-14 must not reach the output |
| EMG | | | | | none used: no CC0 run under 30 MB found (OpenNeuro's GraphQL `modality` filter does not list EMG; not searched further) |

Only the one data file is downloaded, never the dataset; its sidecars are not used (aimport writes its own).

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
`NATIVE_IDENTIFIERS`), `MICR_PLANTED` (the microscopy fixtures' planted values and the CMC-like donors and dates:
`jane doe`, `jdoe@example.org`, `scope-sn-4711`, `2025-02-15`, `250215`, `20250422`, `slide 42 smith`,
`annotation secret`, `lab-workstation-7`, `h17`, `moe`, `mn27`) and `tokens(text)`, which returns the members of
`PLANTED | NATIVE | MICR_PLANTED` found in the lowercased text by substring (so phrases like `hospital x` and values like
`12343@hucheng` are caught). Leak tests assert `not PLANTED & tokens(text)` and
`not NATIVE & tokens(text)`. The ephys tests use `EPHYS_PLANTED` and `ephys_tokens(text)` instead (see
"Electrophysiology and optical data"); `tokens` also reports the `EPHYS_PLANTED` members, which the intersection
with `PLANTED` or `NATIVE` ignores.

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
- Network tests (CMC bucket, by hand; range reads under each test's byte cap): `cd aimport && uv run pytest -m network`
- bids-examples: the docker tests download the pinned tarball once into `/tmp/aimport-bids-examples-cache`; mount
  a host folder there (`-v <cache dir>:/tmp/aimport-bids-examples-cache`) to keep it between runs
- In the image: `docker run --rm --platform linux/amd64 -v $PWD/aimport:/src brainlife/aimport:dev pytest -m docker /src/tests`
  (ephys: add `-v ~/.cache/aimport-bids-examples:/tmp/aimport-bids-examples-cache -v ~/.cache/aimport-ephys:/tmp/aimport-ephys-cache -e AIMPORT_EPHYS_CACHE=/tmp/aimport-ephys-cache`
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

