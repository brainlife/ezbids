---
name: ezbids-pinned-tools
description: Use when bumping, adding or questioning the version of dcm2niix, the BIDS validator, Deno, uv, Python, Neuroglancer, uPlot, the ezbids-binaries release or aimport's Python dependencies, or when a build fails on a checksum or version check.
---

# Pinned tools in ezBIDS

Each tool has one pin. Bump it there, update every mirror listed, and run the guard.

## Quick reference

| Tool | The pin | Mirrors to update with it | Guard |
|---|---|---|---|
| dcm2niix (web image + desktop) | `handler/dcm2niix.env`: `DCM2NIIX_VERSION` + `DCM2NIIX_ASSET_*` / `DCM2NIIX_SHA256_*` per platform | none: `handler/Dockerfile` and `fetch-binaries.sh` both call `handler/fetch-dcm2niix.sh` | `npx jest handler/dcm2niix.version.spec.ts` (fails if any other `v1.0.YYYYMMDD` tag is written in tracked files); `fetch-dcm2niix.sh` checks sha256 and `dcm2niix -v` at build |
| pypet2bids' dcm2niix | uses ours: `handler/utils.ts` `pet2bidsEnv()`; its bundled zips are deleted (`handler/Dockerfile`, both desktop workflows) | | `handler/utils.spec.ts` |
| `@bids/validator` (aimport) + Deno | `aimport/Dockerfile` `ARG BIDS_VALIDATOR_VERSION`, `DENO_VERSION`, `DENO_ZIP_SHA256` | `fetch-aimport.sh` (same versions + per-platform Deno sha256), `docs/aimport-electron.md`, `aimport/README.md`, `CREDITS.md`, `aimport/tests/DATASETS.md` | image build; desktop smoke test |
| bids-validator 1.14.8 (classic web) | `package.json`, `electron/package.json`, `handler/Dockerfile` | `CREDITS.md` | |
| uv / Python 3.11 (desktop runtime) | `fetch-aimport.sh` `UV_VERSION`, `PYTHON_VERSION`; `aimport/Dockerfile` `ARG UV_VERSION` | `setup-uv` `version:` in `build-desktop.yml` and `desktop-smoke-test.yml` | |
| aimport Python deps | `aimport/uv.lock` (`uv lock` after editing `pyproject.toml`) | `CREDITS.md` if a library is added | desktop installs with `--require-hashes` |
| Neuroglancer, uPlot (QA viewer) | `aimport/viewer-client/package.json` + `package-lock.json` | `CREDITS.md` version | `npm ci --ignore-scripts` in the image and `fetch-aimport.sh` |
| Native binaries (7z, allineate, Python 3.8 runtime) | `fetch-binaries.sh` `RELEASE_TAG` (brainlife/ezbids-binaries) | `README.md` "About fetch-binaries.sh" | `npm run electron:smoke-test` |
| BIDS schema | submodules `bids-specification` (web) and `aimport/bids-specification` (aimport, v1.11.2) | `bids_brainlife_map.yaml` header, landing `BIDS_VERSION`, drafts (`tools/draft_datatypes.py`) | `git submodule status` |

## Bump dcm2niix

1. Take the tag and the asset digests from the official `rordenlab/dcm2niix` GitHub release only (never a fork, conda or a PyPI wheel).
2. Change every line of `handler/dcm2niix.env` together, plus its "checked" date.
3. Do not write the old or new tag anywhere else (docs say "the pinned dcm2niix"); the guard fails on any other tag.
4. `npx jest handler/dcm2niix.version.spec.ts handler/utils.spec.ts`; `handler/fetch-dcm2niix.sh darwin arm64 /tmp/d2n` on a Mac prints `ok: ... prints <tag>`.
5. Rebuild `ezbids-handler:local` and run the aimport docker tests (`ezbids-checks-before-pr`).

## Common mistakes

- Bumping `fetch-aimport.sh` and forgetting `aimport/Dockerfile` (or the reverse): the image and the desktop app then validate with different versions.
- Copying a sha256 from a third-party page instead of the release's own digest / `.sha256sum` file.
- Writing an example dcm2niix tag in a doc or skill: the guard test fails.
- Letting pypet2bids fall back to its own dcm2niix.
- Editing `pyproject.toml` without `uv lock`.
