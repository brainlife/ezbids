---
name: aimport-add-modality-or-format
description: Use when adding a new modality, datatype, file format, reader or vendor to aimport, or changing which BIDS datatypes or suffixes aimport supports or maps to brainlife datatypes.
---

# Add a modality or format to aimport

Everything below goes in the same PR. Load `aimport-deidentification-rules` first.

## Steps

1. **Code.** A new modality is a `Module` (`aimport/src/aimport/modality.py`: `claim`, `scan`, `terms`, `plan`, `write`) registered in `modality.modules()`. A new format of an existing modality goes in its package: `micr/` (`readers.py`, `convert.py`, `reference.py`) or `ephys/` (`readers.py`, `write.py`, `snirf.py`, `nwb.py`). Claimed roots are never staged, walked or copied.
2. **Terms.** The reader returns every identifying value it sees (headers, vendor XML, paths) to `terms`; keep only allowlisted metadata.
3. **Tests first**, with a synthetic planted fixture in `tests/fixtures/` and its identifiers in `tests/conftest.py`; extend the modality's end-to-end leak test.
4. **Mapping.** Add or change rows in `aimport/src/aimport/data/bids_brainlife_map.yaml` (`active` / `planned` / `draft`), then regenerate drafts: `cd aimport && uv run python tools/draft_datatypes.py --write-yaml`. Run `uv run pytest -q tests/test_brainlife_map.py tests/test_datatype_drafts.py`.
5. **Datasets.** Row in `aimport/tests/DATASETS.md` for every dataset used (pinned version, licence, tests).
6. **Credits.** New library: row in `CREDITS.md` (tool, what it does, licence, citation, source of the citation) and, if it has a paper, a `references` entry in `CITATION.cff`. Take the citation from the project's own `CITATION.cff`, README or docs, or the publisher/Crossref; if none, link the repo and list it under "Not verified". GPL or non-commercial licences go under "Licence notes". A GPL/AGPL reader library is an optional extra in `pyproject.toml` (as `czi = ["bioio-czi"]`), installed by `aimport/Dockerfile` (`--extra <name>`) and never by the desktop runtime; the reader raises `UnsupportedFormat` with a "not installed in this build" reason when the import fails, tested both ways (`monkeypatch.setitem(sys.modules, "<module>", None)`). See `ezbids-pinned-tools` "Extras".
7. **Docs and statuses.** `aimport/README.md` (modality section, known limitations), `aimport/EXAMPLES.md` if there is a walkthrough, root `README.md` lists, and `ui/src/features/landing/landing/data.ts` (`DATATYPES` `status`/`mapped`, `STATS` counts must match the YAML).
8. **QA viewer.** Make sure the output opens: images via Neuroglancer (`aimport/src/aimport/viewer.py`, `zarr_layer`/`nifti_layer`), recordings via the trace viewer (`traces_page`). Add a `tests/test_viewer*.py` case.
9. Run `ezbids-checks-before-pr`.

## Quick reference

| What | Where |
|---|---|
| Module interface | `aimport/src/aimport/modality.py` |
| BIDS -> brainlife map | `aimport/src/aimport/data/bids_brainlife_map.yaml` |
| Draft datatypes (generated) | `aimport/src/aimport/data/datatype_drafts/`, `aimport/tools/draft_datatypes.py` |
| Test datasets | `aimport/tests/DATASETS.md` |
| Citations / licences | `CREDITS.md`, `CITATION.cff` |
| Landing statuses | `ui/src/features/landing/landing/data.ts` |
| QA viewer | `aimport/src/aimport/viewer.py`, `aimport/viewer-client/` |

## Common mistakes

- Mapping YAML or drafts left for a later PR: the YAML is the single source of truth for uploads.
- Hand-editing the generated "draft datatypes" block in the YAML instead of rerunning `draft_datatypes.py`.
- Inventing or guessing a DOI. Every citation names its source in the last CREDITS.md column.
- Landing counts (`STATS`) or statuses not updated, so the page claims support that is not merged.
- New dependency added without asking, or without `uv lock` updating `aimport/uv.lock`.
- A GPL-licensed reader put in the main `dependencies`: the desktop app would ship it (`fetch-aimport.sh` fails).
- Format readable but not viewable in the QA viewer.
