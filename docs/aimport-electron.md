# aimport in the desktop app (plan)

Goal: the local, privacy-preserving AI importer (`aimport/`, from master) runs inside ezBIDS desktop, no Docker.
`aimport/` is copied unchanged from master; desktop differences live in one shim, `electron/aimport/aimport_desktop.py`.

**Bundled** (`extraResources` → `Resources/aimport/`, built by `fetch-aimport.sh <platform> <arch>`)
- Python 3.11 (relocatable python-build-standalone, via a pinned `uv`) with aimport's deps installed from `uv.lock` (`--require-hashes`).
- Deno (pinned, sha256-checked) + `jsr:@bids/validator@2.4.1` pre-cached (works offline) + BIDS 1.11.2 `schema.json` (`bst export`).
- The Neuroglancer QA client, built from `aimport/viewer-client` (`npm ci`, lockfile hashes).
- Reused from ezBIDS desktop (already bundled): dcm2niix, 7z, Python 3.8 runtime (ezBIDS_core via `preprocess.cjs`), allineate + face template.

**Start/stop**: `electron/main.ts` starts `python -m aimport_desktop serve` lazily (first click on "AI import"), on a random
`127.0.0.1` port with a fresh random token in `AIMPORT_TOKEN` (env, never argv or a URL). Work and keys folders live in the
app's userData. The child is tree-killed with the API and handler. No telemetry; no model key unless the user sets one (then
heuristics + model; without a key nothing leaves the machine).

**UI ↔ engine**: the renderer gets `{port, token}` over IPC (preload `window.aimport`), and calls the engine's own API:
`/scan`, `/status`, `/plan` (PATCH edits), `/approve`, `/execute`, `/viewer/session`. The QA viewer opens in a new window
via the one-time code. No engine logic in TypeScript.

**What the shim changes** (to upstream to master later as env hooks): ezBIDS runs as `preprocess.cjs` instead of
`preprocess.sh`; staging copies the input (APFS clones on mac) instead of `cp -rs`, so nothing can write through to the
user's folder; validator = bundled Deno; schema path; defacing adds `allineate` (ezBIDS desktop's face mask) since FSL
(pydeface) and ROBEX (quickshear) are not shippable on mac/Windows.

**Per-platform risks**
- mac: notarization of the new Python/Deno binaries (extra signing of `.so`/`.dylib`; Deno needs JIT entitlement, already set for Electron).
- Windows: path/`file://` URIs, no `killpg` (tree-kill), long paths in `site-packages`; unverified.
- Linux: AppImage size; unverified.

**Size**: estimate +450-600 MB unpacked per platform (Python 3.11 + deps ~300, Deno ~110, client ~10). Measured in the PR.

**Open items for Nicholas**: OK to add `Resources/aimport` and a lazy 3rd child? notarization of the new binaries;
Windows/Linux CI run; upload to brainlife from the result folder (later step); upstreaming the shim hooks into `aimport/`.
