# aimport in the desktop app

Goal: the local, privacy-preserving AI importer (`aimport/`, from master) runs inside ezBIDS desktop, no Docker.
`aimport/` is copied unchanged from master; desktop differences live in one shim, `electron/aimport/aimport_desktop.py`.

**Bundled** (`extraResources` → `Resources/aimport/`, built by `./fetch-aimport.sh <platform> <arch>`, host platform only)
- Python 3.11.18 (python-build-standalone, via pinned `uv` 0.13.9) with aimport's deps from `uv.lock` (`--require-hashes`).
- `bids-validator`: `@bids/validator` 2.4.1 compiled with Deno 2.5.6 (zip sha256-pinned); runs offline. BIDS 1.11.2 `schema.json`.
- The Neuroglancer QA client, built from `aimport/viewer-client` (`npm ci --ignore-scripts`, lockfile hashes).
- Reused from ezBIDS desktop: dcm2niix, 7z, Python 3.8 runtime + ezBIDS_core (`preprocess.cjs`), allineate + face template.

**Start/stop** (`electron/aimport/engine.ts`): picking a folder starts `python -I -B aimport_desktop.py serve` on a random
`127.0.0.1` port with a fresh 256-bit token in `AIMPORT_TOKEN` (env only). Work folder per input folder, keys folder shared,
both in userData. Tree-killed on quit with the API and handler. No telemetry; no model key is set, so nothing leaves the machine.

**UI ↔ engine**: the token stays in the main process. The renderer calls `window.aimport.api(method, path, body)` (IPC
proxy) for `/scan`, `/status`, `/plan`, `/approve`, `/execute`. The QA viewer is a modal in the main window: a sandboxed
`WebContentsView` laid over the dialog body, opened with the one-time code (`/viewer/session`, never shown to the renderer),
held to the engine's loopback origin (no new windows). No engine logic in TypeScript.

**What the shim changes** (to upstream as env settings in `aimport/`): ezBIDS runs as `preprocess.cjs` instead of
`preprocess.sh`; staging copies the input (APFS clones on mac, no extra disk) instead of `cp -rs`, since nothing mounts it
read-only here; validator and schema paths; defacing adds `allineate` (ezBIDS desktop's face mask), because FSL (pydeface)
and ROBEX (quickshear) cannot ship on mac/Windows. aimport's own deface checks still apply.

**Size** (mac arm64, measured): `Resources/aimport` 438-475 MB unpacked (Python + deps 303, validator 133, client 1.4),
136 MB gzip. App 1.8 GB unpacked total.

**Per-platform**: mac arm64 dev and unsigned `--dir` build tested end to end (scan → validated). Unverified: notarization of
the new `.so`/`.dylib` and the Deno binary (entitlements already allow JIT); Windows (`python.exe` layout, `taskkill`,
long paths, `file:` URIs); Linux AppImage size.

**Open items for Nicholas**: the desktop `preprocess.ts` aborts on a folder with only a non-image DICOM (dcm_qa_xa30's
`*_Raw.dcm`; `preprocess.sh` skipped it); a crash of Electron (not a normal quit) leaves detached children running, as for
the API/handler; CI run on Windows/Linux; upload to brainlife (later step).
