---
name: ezbids-release-and-deploy
description: Use when asked to release, tag, package, sign, publish or deploy ezBIDS web, ezBIDS desktop, the aimport engine image or the `bl aimport` command line, or when someone asks which CLI or image to use.
---

# Release and deploy

Agents never deploy, push images or tag releases: they prepare and test, a maintainer releases. Production config (Jetstream) is not in this repo; do not assume it matches the code.

## Web (brainlife.io/ezbids)

1. Merge to `master` only with CI green (`ezbids-checks-before-pr`).
2. Stack test on `master` first: `./dev.sh` (or `docker compose --profile development up`), open `http://localhost:3000/ezbids/`, convert one DICOM session end to end (upload, map, deface, finalize, download).
3. The handler runs TypeScript under ts-node: compose runs `node ../node_modules/ts-node-dev/lib/bin.js ... handler.ts`, which runs `preprocess.ts`, `bids.ts`, `deface.ts` the same way. It needs the root `node_modules` (`npm install`). `handler/start.sh` (pm2 `handler.js`) is legacy.
4. Images: API `Dockerfile` (context `.`), UI `ui/Dockerfile` (context `.`), handler `handler/Dockerfile` (context `handler/`; dcm2niix from `handler/dcm2niix.env`).
5. The production rollout itself is done by a maintainer. **Unverified:** the exact production steps are not documented in this repo.

## Desktop

| Workflow | Trigger | What it does |
|---|---|---|
| `desktop-smoke-test.yml` "Desktop pack smoke test" | `workflow_dispatch` (`gh workflow run desktop-smoke-test.yml --ref <branch>`) and `v*` tags | unsigned `--dir` pack on mac arm64, Linux x64, Windows x64; packaged binaries, aimport engine scan -> `validated`, app launch |
| `build-desktop.yml` "Build Desktop App" | `v*` tags only | creates the GitHub release, signs + notarizes mac, builds dmg / NSIS exe / AppImage + deb, uploads them |

1. Run the smoke test on the release branch by hand and get it green before anyone tags.
2. A maintainer pushes the `v*` tag; both workflows run. Check the release assets.

Open items (unverified): Linux needs `--no-sandbox` for a `--dir` build (`chrome-sandbox` not setuid); notarization of aimport's `.so`/`.dylib` and the Deno binary; NSIS installer, AppImage and deb never tested end to end; no GUI click tests. See `docs/aimport-electron.md`.

## aimport engine image and CLI

- Engine image: to be published as `docker.io/brainlife/aimport`; **not published yet, and there is no publishing workflow.** Today build it locally (`brainlife/aimport:dev`, see `aimport/README.md`). Never push it.
- CLI: the only supported CLI for `bl aimport` is the Python CLI in `brainlife/pybrainlife`, branch `enh/cli`. **Unverified:** that branch has no `aimport` command yet (checked 2026-11-24).
- The Node CLI (`brainlife/cli`) is **not supported**: never use, run, release or document it. Existing references in `README.md` and `aimport/README.md` are stale; replace them when you touch those lines.

## Common mistakes

- Tagging `v*` to "test the build": it creates a public release. Use `workflow_dispatch` on the smoke test.
- Running `npm run deploy*` scripts or anything that touches brainlife.io or test.brainlife.io.
- Pointing users to `brainlife/cli` or `npm link` for `bl aimport`.
- Saying the engine image is on Docker Hub.
