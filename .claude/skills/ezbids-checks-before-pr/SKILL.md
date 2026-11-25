---
name: ezbids-checks-before-pr
description: Use when about to commit, push, open, update or merge a pull request in brainlife/ezbids, when CI (Codespell, Jest Unit Tests) is red, or when resolving a merge conflict.
---

# Checks before a PR

CI runs only codespell and jest. Run those plus the checks CI does not run, for the parts you touched, from the repo root.

## Steps

1. Submodules present: `git submodule update --init` (`bids-specification`, `aimport/bids-specification`).
2. Run the checks in the table. Fix, rerun, then commit.
3. Merge conflicts in this repo are mostly additive (docs, CREDITS.md, DATASETS.md, YAML rows, tests): keep both sides, then rerun the checks.
4. Before merging (a maintainer merges), open the PR's checks: `gh pr checks <n>`. Merge only when all are green. Branch protection is off, so a red check does not block the button: a red codespell was merged once (#204).

## Quick reference

| Check | Command | In CI |
|---|---|---|
| Spelling (CI's version, tracked files only) | `git ls-files -z ':!:bids-specification' ':!:aimport/bids-specification' \| xargs -0 uvx --from codespell==2.4.1 codespell` | yes |
| Unit tests (api, handler, ui `*.spec.ts`) | `npm ci` once, then `npm test -- --ci` | yes |
| Web UI builds | `cd ui && npx vite build` | no |
| Desktop typecheck | `cd electron && npx tsc --noEmit` | no |
| aimport, host | `cd aimport && uv run pytest -q -m "not docker and not docker_offline and not docker_slow"` | no |
| aimport, engine image | build images (below), then `docker run --rm --platform linux/amd64 -v $PWD/aimport:/src -v ~/.cache/aimport-dcm-qa:/tmp/aimport-dcm-qa-cache brainlife/aimport:dev pytest -m "docker or docker_offline" /src/tests` | no |
| aimport pydeface (minutes) | same `docker run`, `pytest -m docker_slow /src/tests` | no |
| Desktop pack | `gh workflow run desktop-smoke-test.yml --ref <branch>` (see `ezbids-release-and-deploy`) | by hand |

Build the images (needed after any change to `handler/` or `aimport/`):

```
docker build --platform linux/amd64 -t ezbids-handler:local handler/
docker build --platform linux/amd64 -t brainlife/aimport:dev -f aimport/Dockerfile .
```

Other aimport markers: `network` (range reads of public remote data, under 32 MiB a test) and `ephys_data` (downloads small pinned ephys files to `AIMPORT_EPHYS_CACHE`, default `~/.cache/aimport-ephys`) run on the host; deselect them with `and not network and not ephys_data` when offline.

## Codespell

- Plain `codespell` or `uvx codespell` at the root also reads untracked `./tmp`, `handler/bin`, `node_modules`, and `git ls-files` alone includes the initialized submodules: both give false failures.
- CI pins codespell 2.4.1 (the action); newer versions flag words CI accepts (2.4.3: `indiciation` in `ui/test/events/lib.js`).
- A real domain word (DICOM value, file extension, library attribute) goes in `.codespellrc` `ignore-words-list` **and** on the comment line above it saying what it is.
- Never rename an identifier a library or format requires to please codespell (fsspec's `cachable`, DICOM `ND`, CTF `.anc`).

## Common mistakes

- Merging with codespell red because "only jest is required".
- Running codespell without the tracked-file filter and "fixing" files in `handler/bin` or the BIDS submodule.
- Running aimport docker tests against a stale `brainlife/aimport:dev` built before your change.
- Skipping `vite build` / `tsc --noEmit`: CI never builds the UI or the desktop app.
