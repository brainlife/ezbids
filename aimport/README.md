# aimport

brainlife.io/aimport: a local agentic data importer. Part of the ezBIDS repo.

Run tests with `cd aimport && uv run pytest`.

## Engine image

Local only (never pushed). Apple Silicon hosts build and run with `--platform linux/amd64`.
From the repo root:

```
git submodule update --init bids-specification aimport/bids-specification
docker build --platform linux/amd64 -t ezbids-handler:local handler/
docker build --platform linux/amd64 -t brainlife/aimport:dev -f aimport/Dockerfile .
docker run --rm --platform linux/amd64 -v $PWD/aimport:/src brainlife/aimport:dev pytest -m docker /src/tests/test_image.py
```

- ezBIDS lives at `/app` (its `bids-specification` submodule at the pinned `3537e9ed`); aimport is in `/opt/aimport-venv` (Python 3.11), last on `PATH`, so system `python3` stays 3.8 and `pytest` is the venv's.
- `aimport/bids-specification` (submodule, BIDS v1.11.2 at `fbe1af9a`) is exported to `/opt/bids-schema/schema.json` with `bst export`.
- BIDS validator: `@bids/validator` **2.4.1** (Deno 2.5.6), run through the `bids-validator-2` wrapper. That release bundles an older schema (it flags `BIDSVersion` 1.11.2 as unknown), so the wrapper defaults `--schema file:///opt/bids-schema/schema.json` unless `--schema`/`-s` is given. Works offline. Useful flags: `--format json` (`--json` is deprecated), `--schema <URL>`, `--ignoreNiftiHeaders`, `-o <file>`.
- Test data: `tests/fixtures/fetch_dcm_qa.py` fetches `neurolabusc/dcm_qa` at a pinned commit and plants fake PHI.

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
