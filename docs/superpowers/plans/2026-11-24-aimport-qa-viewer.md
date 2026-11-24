# aimport QA viewer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The aimport engine serves a local Neuroglancer viewer (same origin, no third-party page) so a person can check the de-identified output, and the defaced versus original anatomy, before upload; `bl aimport --qa` opens it and asks before uploading.

**Architecture:** New `aimport/src/aimport/viewer.py` builds Neuroglancer states and an index page; `server.py` gains `/viewer/*` and `/qa/*` routes, a one-time-code → cookie session for the browser, and serves the Neuroglancer client bundled in the pinned `neuroglancer` wheel. The cli adds `--qa`.

**Tech Stack:** Python 3.11, FastAPI 0.165 / Starlette 1.10 (`FileResponse` handles `Range`), `neuroglancer` wheel (static client only; the Python server part is not used), pytest + httpx TestClient; cli: Node, `node:test`.

**Spec:** `docs/superpowers/specs/2026-11-24-aimport-phase2-3-design.md` (section "QA viewer"), extending `docs/superpowers/specs/2026-11-23-aimport-design.md`.

## Global Constraints

- Loopback only; the existing Host check and bearer token stay on every route. Only `/viewer/*` and `/qa/*` also accept the session cookie; every other route stays bearer-only.
- The bearer token never appears in a URL, page or redirect. Browser access goes `POST /viewer/session` (bearer) → `{"code": <random 32 hex>, "url": "/viewer/open?code=<code>"}`; the code is single use and expires after 60 s.
- `GET /viewer/open?code=` sets cookie `aimport_viewer_<hex>=<random 32-byte hex>; HttpOnly; SameSite=Strict; Path=/` (no `Secure`, loopback http) and redirects (303) to `/viewer/`. The cookie name has a random 8-hex suffix chosen per server run (ruling after Tasks 1-2: cookies ignore the port, so two engines on one host would otherwise replace each other's session). Sessions live in memory for the server run.
- Data is served only after the stage is `validated` or `invalid` and the output state is complete (same rule as `/preview`), only for paths listed in the output manifest (or the `defaced` originals map), resolved inside the output (or pre-deface) root, never through a symlink. `staged/`, `sourcedata/`, the key folder and `scan.json` are never served.
- The Neuroglancer client is a standalone vite build of the `neuroglancer` npm package 2.41.2 (`aimport/viewer-client/`: exact versions, integrity hashes in `package-lock.json`, built by a digest-pinned node stage of the Dockerfile with `npm ci --ignore-scripts` into `/opt/neuroglancer-client`; `AIMPORT_NEUROGLANCER_DIR` overrides it on the host). Ruling after Task 1: the `neuroglancer` wheel's `static/client/` is the Python-integration build (it needs the Python server's `/v/<token>/` endpoints), so the wheel is not used. Generated states reference only the engine's own origin (no `neuroglancer-demo.appspot.com`, no other host).
- Responses on `/viewer/*` and `/qa/*` carry `Cache-Control: no-store` and `X-Content-Type-Options: nosniff`; the HTML pages carry the CSP `default-src 'self'; script-src 'self' 'unsafe-eval'; img-src 'self' data: blob:; worker-src 'self' blob:; style-src 'self' 'unsafe-inline'; frame-ancestors 'none'`. `'unsafe-eval'` is the one relaxation the client needs (it compiles code with `new Function`; without it the slices stay blank); no wasm is bundled, so no `'wasm-unsafe-eval'`.
- The QA index (`/viewer/`) lists each written image, with a Neuroglancer link (`/viewer/entry/{id}?index=N`) and, for a defaced image, "defaced vs original" (`?compare=1`: the defaced image and its original side by side). The single view keeps the original as a hidden layer.
- Repo rules: branch from `origin/master`, PR against `master`, never deploy, docs in the same PR, host tests `cd aimport && uv run pytest -q -m "not docker and not docker_offline"`.

## Review Focus

1. A cookie-authenticated request to any non-viewer route (e.g. `PATCH /plan`, `POST /execute`) → 401; test in Task 2.
2. `/qa/data` with `..`, absolute paths, URL-encoded traversal, a symlink inside the output, or a file not in the manifest → 404; test in Task 3.
3. Viewer requested before execute, or after a re-scan cleared the output → 404 with a clear message, not a stale file; test in Task 3.
4. A reused or expired one-time code → 401, no cookie set; test in Task 2.
5. The generated Neuroglancer state for the T1w entry has the defaced and original layers, both pointing at this origin; test in Task 4.

---

### Task 1: pin Neuroglancer and serve its client

**Files:** Modify `aimport/pyproject.toml`, `aimport/uv.lock`; Modify `aimport/src/aimport/server.py`; Test `aimport/tests/test_viewer_routes.py` (new).

**Interfaces:**
- Produces: `GET /viewer/ng/{path:path}` serves files from `neuroglancer_client_dir()`; `aimport.viewer.neuroglancer_client_dir() -> Path` (in a new `viewer.py`), raising `RuntimeError("the neuroglancer client is not installed")` if missing.

- [ ] **Step 1:** Add `neuroglancer==<latest that has both manylinux x86_64 and macOS arm64 abi3 wheels>` to dependencies; `uv lock`. Record the version and why in the commit message.
- [ ] **Step 2:** Tests: `neuroglancer_client_dir()/"index.html"` exists; with a valid session (use the Task 2 helper once it exists; until then the bearer header), `GET /viewer/ng/index.html` → 200 `text/html` and has the CSP header; `GET /viewer/ng/../server.py` and `/viewer/ng/%2e%2e/x` → 404; no session → 401.
- [ ] **Step 3:** Implement with a path check (resolved path inside the client dir, regular file) and `FileResponse`.
- [ ] **Step 4:** Host suite passes. Commit `aimport: serve the pinned Neuroglancer client from the engine`.

### Task 2: browser session (one-time code → cookie)

**Files:** Modify `aimport/src/aimport/server.py` (authorize, routes); Test `aimport/tests/test_viewer_routes.py`.

**Interfaces:**
- Produces: `POST /viewer/session` → `{"code", "url"}`; `GET /viewer/open?code=` → 303 to `/viewer/` with the cookie; `authorize(request)` accepts the cookie only when `request.url.path` starts with `/viewer/` or `/qa/` (and is not `/viewer/session`, which stays bearer-only).
- Test helper `viewer_client(client) -> TestClient` in `tests/conftest.py` or the test module that performs the code exchange.

- [ ] **Step 1:** Tests:
  - the exchange sets the cookie with `HttpOnly`, `SameSite=Strict` and `Path=/`;
  - the code works once (second use → 401) and not after 60 s (monkeypatch the clock);
  - the cookie works on `GET /viewer/ng/index.html` and → 401 on `GET /plan`, `PATCH /plan` and `POST /execute`;
  - the bearer still works everywhere;
  - a wrong cookie → 401;
  - a code that never existed → 401.
- [ ] **Step 2–3:** Implement (`secrets.token_hex`, `hmac.compare_digest` for the cookie, codes stored with expiry in `Server` under its lock).
- [ ] **Step 4:** Commit `aimport: viewer sessions without putting the token in a URL`.

### Task 3: `/qa/data` — manifest-checked file serving with Range

**Files:** Modify `aimport/src/aimport/server.py`; Test `aimport/tests/test_viewer_routes.py`.

**Interfaces:**
- Consumes: `OUTPUT_STATE` (`manifest`, `defaced`, `complete`, `scan_id`), `srv.out`, `srv.pre`, `DONE`.
- Produces: `GET /qa/data/{entry_id}/{index}/{subpath:path}?which=defaced|original`. `index` picks the manifest file (or directory, for later OME-Zarr entries); `subpath` is empty for a file or a path inside a manifest directory. The same resolution helper is used by `/preview` (refactor `get_preview` onto it; `/preview` behaviour unchanged).

- [ ] **Step 1:** Tests (reuse the stubbed execute fixtures in `test_server.py`):
  - before execute → 404 `nothing to preview: execute the plan first`;
  - after execute, the T1w file → 200 with the right bytes;
  - `Range: bytes=0-15` → 206 with 16 bytes and `Content-Range`;
  - `which=original` → the pre-deface file;
  - an index out of range → 404;
  - traversal in `subpath` → 404, with `..`, `%2e%2e` and an absolute path;
  - a symlink planted in the output → 404;
  - an entry id not in the manifest → 404;
  - after a new `POST /scan` → 404;
  - `Cache-Control: no-store` is present.
- [ ] **Step 2–3:** Implement.
- [ ] **Step 4:** Commit `aimport: /qa/data serves the checked output to the viewer`.

### Task 4: Neuroglancer states and the viewer pages

**Files:** Create/extend `aimport/src/aimport/viewer.py`; Modify `server.py`; Test `aimport/tests/test_viewer.py` (unit) and `test_viewer_routes.py`.

**Interfaces:**
- Produces:
  - `viewer.nifti_layer(name: str, url: str, kind: str) -> dict`: `source` is `url + "|gzip:|nifti:"` for `.nii.gz` and `url + "|nifti:"` for `.nii`; the shader preset comes from `kind` (`t1`, `t2`, `bold`, `dwi`, `default`), mirroring brainlife-lite's `NEUROGLANCER_PRESETS`.
  - `viewer.entry_state(entry: dict, files: list[str], originals: list[str] | None, base: str) -> dict`:
    - a `4panel` layout;
    - one layer per file (the first file of a multi-file entry);
    - for an entry with originals, a second layer `"<name> (original)"` that is not visible by default.
  - `viewer.state_url(state: dict) -> str` → `"/viewer/ng/#!" + quote(json.dumps(state, separators=(",", ":")))`.
  - `GET /viewer/` → an HTML index of the plan's written entries: BIDS path, a "Neuroglancer" link per NIfTI entry, and "defaced vs original" for defaced ones. It uses the page CSP and no external assets.
  - `GET /viewer/entry/{entry_id}` → 303 to that entry's `state_url`. `base` is the request's own origin (`str(request.base_url).rstrip("/")`).
- [ ] **Step 1:** Unit tests:
  - `.nii.gz` gets the gzip suffix and `.nii` does not;
  - the T1w entry with an original gives two layers, the original not visible;
  - every `source` starts with `base + "/qa/data/"`;
  - `json.dumps(state)` contains no `appspot`, no `http` other than `base`, and no token.
- [ ] **Step 2:** Route tests:
  - `/viewer/` lists every written entry and no excluded one;
  - it contains none of the `PLANTED`/`NATIVE` terms;
  - `/viewer/entry/<id>` redirects to `/viewer/ng/#!…` whose decoded state passes the unit checks.
- [ ] **Step 3–4:** Implement, pass, commit `aimport: Neuroglancer states and a QA index for the written dataset`.

### Task 5: real viewer check in the image (manual, recorded)

**Files:** Modify `aimport/README.md` (new section "Checking the output (QA viewer)"); Modify `aimport/tests/DATASETS.md` (note the viewer check on dcm_qa_xa30).

- [ ] **Step 1:** Rebuild the image. Run the engine on planted `dcm_qa_xa30` (folders under `$HOME` for Colima), scan → approve (`quickshear`) → execute.
- [ ] **Step 2:** Get a code with `POST /viewer/session` and open the URL in a headless browser (Playwright on the host).
  - Screenshot `/viewer/` and the T1w entry. Neuroglancer must render the image; toggling the original layer must show the face.
  - Save the screenshots under `aimport/docs/` (`qa-viewer-index.png`, `qa-viewer-t1w.png`). Use defaced views only in committed images; the original layer is checked but not committed.
  - Record any CSP relaxation the client needed.
- [ ] **Step 3:** README section:
  - how to open the viewer: `POST /viewer/session`, then the URL;
  - what it serves, and why it is local only;
  - that the defaced/original toggle is for the reviewer's eyes only.

  Commit.

### Task 6: `bl aimport --qa` (cli repo)

**Files:** Modify `cli/bl-aimport.js`, `cli/aimport/engine.js` (if a helper is needed), `cli/README.md`; Test `cli/test/aimport-command.test.js`.

**Interfaces:**
- Consumes: `POST /viewer/session` → `{code, url}`.
- Produces: with `--qa`, after `validated` and before stopping the engine:
  - print `QA viewer: http://127.0.0.1:<port><url>` and try to open it with the OS opener (`open` on macOS, `xdg-open` on Linux, `start` on Windows; failure only prints);
  - prompt `Upload this dataset? [y/N]` (`--yes` does not skip this prompt when `--qa` is given);
  - `n` exits 0 with nothing uploaded;
  - the engine stops after the answer.

- [ ] **Step 1:** Tests with fake deps:
  - the session call happens after validated;
  - the printed URL has no token;
  - `n` → no upload, exit 0, the engine stopped;
  - `y` → upload as before;
  - without `--qa`, no session call.
- [ ] **Step 2–4:** Implement, `node --test test/aimport-*.test.js` passes, commit `bl aimport --qa: check the output in the local viewer before upload`.
