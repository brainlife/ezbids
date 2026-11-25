# ezBIDS

ezBIDS web (`api/`, `handler/`, `ui/`), ezBIDS desktop (`electron/`) and aimport, the local importer (`aimport/`).

## Skills (`.claude/skills/`): load the matching one before you start

| Skill | Load it when |
|---|---|
| `ezbids-checks-before-pr` | committing, opening or merging a PR, red CI, merge conflicts |
| `aimport-deidentification-rules` | any change to what aimport reads, redacts, names, dates or writes |
| `aimport-add-modality-or-format` | adding a modality, datatype, format or reader to aimport |
| `ezbids-pinned-tools` | bumping dcm2niix, the validator, Deno, uv, Neuroglancer, binaries, `uv.lock` |
| `ezbids-ui-style` | anything users see in `ui/`, `electron/` or the QA viewer |
| `ezbids-release-and-deploy` | releases, tags, desktop builds, deploys, images, the `bl aimport` CLI |

## Hard rules

1. Branch from `origin/master`, PR against `master`; never commit to `master`. Merge only with all checks green.
2. Never deploy, push images or push `v*` tags. Never run anything that touches brainlife.io or test.brainlife.io.
3. Nothing identifying leaves the user's machine in aimport; BIDS words are never identifying terms.
4. One pin per tool (dcm2niix: `handler/dcm2niix.env` only). Official releases, sha256-checked.
5. Every test dataset is recorded in `aimport/tests/DATASETS.md` with its licence. Large or unlicensed data is read in place, never copied or committed.
6. Citations come from the project's own citation file or the publisher; never invent a DOI.
7. Docs, `CREDITS.md`, the brainlife mapping YAML and landing statuses change in the same PR as the code.
8. No new dependencies without asking. Tests first.
9. The only supported `bl aimport` CLI is the Python one (brainlife/pybrainlife `enh/cli`); never use or document the Node `brainlife/cli`.
10. UI: brainlife-lite tokens from `ui/src/theme.css`, `BrandLockup` always visible, no external windows; screenshots in UI PRs.
