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
- Network tests (CMC bucket, by hand; range reads under each test's byte cap): `cd aimport && uv run pytest -m network`
- bids-examples: the docker tests download the pinned tarball once into `/tmp/aimport-bids-examples-cache`; mount
  a host folder there (`-v <cache dir>:/tmp/aimport-bids-examples-cache`) to keep it between runs
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

