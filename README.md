# ezBIDS

The secure, semi-automated mapping of neuroscience data (neurophysiology, neuroimaging and microscopy) to the Brain Imaging Data Structure ([BIDS](https://bids.neuroimaging.io/)) standard.  

<img width="1420" alt="The ezBIDS landing page" src="docs/images/ezbids-landing.png">

### Three ways to use ezBIDS

| | What it is | Where your data goes | Status |
|---|---|---|---|
| **ezBIDS on the web** | [brainlife.io/ezbids](https://brainlife.io/ezbids): guided conversion of MRI, PET and MEG in the browser | uploaded to the ezBIDS server for conversion ([security FAQ](https://brainlife.io/docs/using_ezBIDS/#faq)) | in service |
| **ezBIDS desktop** ([`electron/`](electron/)) | the same converter as an app, plus **AI import (beta)**: aimport inside, no Docker; no CZI (its reader is GPL-licensed: export to OME-TIFF) | stays on your computer: local store, no telemetry, no AI model | beta: build from source (tested on Mac); signed installers coming |
| **aimport** via `bl aimport` ([`aimport/`](aimport/README.md), [Python CLI](https://github.com/brainlife/pybrainlife/tree/enh/cli#bl-aimport)) | a local importer with an optional AI agent, for neurophysiology (EEG, MEG, iEEG, NIRS, EMG), neuroimaging (MRI, PET) and microscopy | stays on your computer until you approve the upload of the validated, de-identified dataset to brainlife.io | beta: run it from source today; packaged release coming |

**Privacy first.** With ezBIDS desktop and aimport, raw data never leaves your computer. Identifiers are stripped
from headers, tables and text, faces are removed, dates shifted and event names coded; the output must pass a final
check and the BIDS validator before anything can be uploaded, and you review every decision. The AI model is
optional: it sees only de-identified plan text (identifiers replaced by `[x]`), never headers, file paths or
pixels, and without one the built-in heuristics do the work. Try it on public sample data first:
**[aimport/EXAMPLES.md](aimport/EXAMPLES.md)** has three low-stakes walkthroughs (MRI, EEG, microscopy) that upload
nothing.

#### ezBIDS desktop

ezBIDS desktop ([`electron/`](electron/)) is built from the same code as the web service: the converter (a local
store instead of MongoDB) and aimport run on your own computer, with no Docker and no telemetry. Its **AI import
(beta)** runs the aimport engine bundled in the app (Python, the BIDS validator and the QA viewer included), with no
AI model, so nothing leaves the machine; uploading from the app comes in a later version. Status: beta, build from
source (tested end to end on Mac arm64; Windows and Linux not yet); signed installers coming. To build it, see
[Building the Electron app](#building-the-electron-app-artifacts--installers) below (run
`./fetch-aimport.sh <platform> <arch>` too) and [docs/aimport-electron.md](docs/aimport-electron.md).

### About

This is the repository for ezBIDS, which converts neuroscience data files (neurophysiology, neuroimaging and microscopy) to [BIDS](https://bids.neuroimaging.io/). It has three parts:

- **The ezBIDS web service**, securely hosted at [brainlife.io/ezbids](https://brainlife.io/ezbids), a semi-supervised conversion of MRI, PET and MEG data in the browser. For additional details on security features, please see [here](https://brainlife.io/docs/using_ezBIDS/#faq).
- **aimport** ([`aimport/`](aimport/README.md), beta), a local importer that runs on your own computer with an optional AI agent and de-identifies data before anything is uploaded. Besides MRI and PET it imports microscopy (OME-TIFF, CZI, ND2, LIF, SVS, PS-OCT, light-sheet; OME-Zarr datasets read in place; CZI in the Docker engine and `bl aimport` only, not in the desktop app) and EEG, MEG, iEEG, NIRS and EMG recordings (BrainVision, EDF, BDF, FIF, SNIRF, NWB and more), with viewers to check the result (Neuroglancer for images, a trace viewer for recordings).
- **ezBIDS desktop** ([`electron/`](electron/), beta), built from the same code: the converter (local store instead of MongoDB) and aimport run on your own computer, with no Docker and no telemetry.

Unlike other BIDS converters, ezBIDS eliminates the need for coding and command line interfaces (CLI), doing the bulk of the work behind the scenes to save users time. Importantly, ezBIDS does not require an organizational structure for uploaded data.

A series of inferenial heuritics analyze the uploaded data to provide a _first guess_ BIDS structure, which is presented to users through the web-browser user interface. Users verify the _first guess_ and modify the information provided as needed so as to best match the final BIDS structure.

Data from all major scanner vendors are accepted by ezBIDS. ezBIDS enables pseudo-anonymization by providing options for the defacing of anatomical sequences, and removes all identifying metadata information (e.g. `PatientName`) before final conversion to BIDS.

The BIDS output can then be downloaded back to the user's computer, or uploaded to open repositories such as
[brainlife.io](https://brainlife.io/) or [OpenNeuro.org](https://openneuro.org/).

Helpful links:

1. [ezBIDS website](https://brainlife.io/ezbids) (Chrome or Firefox browsers preferred)
2. [ezBIDS user documentation](https://brainlife.io/docs/using_ezBIDS/)
3. [ezBIDS tutorial](https://brainlife.io/docs/tutorial/ezBIDS/)
4. [ezBIDS tutorial video](https://www.youtube.com/embed/L8rWA8qgnpo)

### Usage

To access the ezBIDS web service, please visit https://brainlife.io/ezbids. If you do not have a brainlife.io account, you will be prompted to create one for authentication purposes.

Users do not need to organize their uploaded data in any specific manner, and users may choose to compress (e.g. zip, tar) their uploaded data.

Should users feel the need to anonymize data before uploading, we strongly recommend that subjects (and sessions, if applicable) be organized into subject (and session) folders, with explicit labeling of the preferred subjects (and sessions) IDs (e.g. `MRI_data/sub-01/ses-01/DICOMS`). Failure to do so for non-anonymized data may result in an inaccurate _first guess_ and require additional edits in the web browser.

If users wish to install ezBIDS locally, to ensure that data do not leave their institution site, please see [here](https://brainlife.io/docs/using_ezBIDS/#installing-ezbids-locally).

The raw JSON debug panels on the Subjects, Series and Objects pages show DICOM header values such as PatientName, PatientID and PatientBirthDate, so they are off by default, including in a local `docker compose` install. Developers can turn them on with `VITE_DEBUG=true docker compose up`.

aimport ([`aimport/`](aimport/README.md), brainlife.io/aimport) is the local, agentic alternative, in **beta: run it from source today; packaged release coming**. Its engine (a Docker image with a loopback API, built from this repository) scans a folder on your own computer, proposes the BIDS mapping (with an optional language model that only sees de-identified metadata), de-identifies and defaces the data, validates it against BIDS v1.11.2 and leaves a reviewed output folder ready to upload. `bl aimport` from the brainlife Python CLI ([pybrainlife](https://github.com/brainlife/pybrainlife/tree/enh/cli#bl-aimport), branch `enh/cli`; `pip install "git+https://github.com/brainlife/pybrainlife@enh/cli"`) drives it and uploads the result; it is not yet in a published release. Nothing identifying leaves your machine. Start with the low-stakes walkthroughs in [aimport/EXAMPLES.md](aimport/EXAMPLES.md); the engine's README has the details.

### Development

ezBIDS is developed as a **monorepo** with **npm workspaces** at the repository root. A single `package-lock.json` ties versions together; **`npm install` is always run from the repo root** (not inside `ui/` or `electron/` alone). Workspace packages are **`ui`** (Vite + Vue) and **`ezbids-electron`** (Electron shell under `electron/`). The Node API lives under **`api/`**, the conversion worker under **`handler/`**, and both are consumed by the root package and by the Electron bundling scripts.

---

#### Prerequisites

-   **Node.js** (project targets Node 20; align local and CI versions).
-   **Docker** and **Docker Compose** for the containerized stack.
-   **Git submodules** (run `git submodule update --init --recursive` before first build; `dev.sh` does this for you).

---

#### Configuration model

ezBIDS can be started up in two different ways.

| Area             | How it is configured                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| ---------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Docker stack** | **`docker-compose.yml`**: services, ports, bind mounts, and **`environment:`** blocks (e.g. `MONGO_CONNECTION_STRING`, `BRAINLIFE_AUTHENTICATION`, `VITE_APIHOST`). Values can reference a **`.env`** file in the project directory (Compose variable substitution, e.g. `${BRAINLIFE_AUTHENTICATION}`).                                                                                                                                                                                                     |
| **Electron**     | **`electron/main.ts`** builds an **`env`** object (`Record<string, string>`) that is passed to spawned backend and handler processes and merged with `process.env`. A smaller **`rendererEnv`** subset (`IS_ELECTRON`, `API_HOST`, `BRAINLIFE_AUTHENTICATION`) is assigned onto **`process.env`** for the main process and preload. Adjust behavior by changing env before launch or extending that object—not by expecting Compose env vars unless you export them into the shell before starting Electron. |

---

#### Persistence: Docker vs Electron

The API chooses storage based on **`IS_ELECTRON`** (see `api/config.ts` and `api/store/index.ts`):

-   **Docker / web-style run**: **`IS_ELECTRON` is unset or not `true`**. Session and ezBIDS state use **MongoDB** via **`MONGO_CONNECTION_STRING`** (Compose wires this to the `mongodb` service).
-   **Electron**: Main sets **`IS_ELECTRON: 'true'`** and clears Mongo for the desktop path (`MONGO_CONNECTION_STRING: ''` in the spawned env). The API then uses **`electron-store`** on disk instead of Mongo.

So “which database” is really **MongoDB vs local electron-store**, keyed off Electron mode.

---

#### Local stack with Docker Compose

This runs **MongoDB**, the **API** (TypeScript via `api/dev.sh` + `tsc-watch` inside the container), the **handler** (`handler/handler.ts` run with `ts-node-dev`; it runs the TypeScript steps `preprocess.ts`, `bids.ts`, `deface.ts` the same way), and the **UI** (Vite dev server) together.

1. Start the stack, either:
    - **`./dev.sh`** — updates submodules, runs **`npm install`** (workspaces), Husky prep, `./generate_keys.sh`, then **`docker compose --profile development up`** (or `docker-compose` if that is the binary you have), **or**
    - Manually: **`docker compose --profile development up`** (add `-d` for detached). Run **`npm install`** at the repo root first if you skipped `dev.sh` and need host-side tooling (Husky, scripts, etc.).

**Useful defaults from `docker-compose.yml`:**

-   **API**: `http://localhost:8082` (health check on `/health`). **`MONGO_CONNECTION_STRING`** points at the `mongodb` service. **`BRAINLIFE_AUTHENTICATION`** comes from your host env / `.env`.
-   **UI**: `http://localhost:3000/ezbids/`; `ui/docker-entrypoint.sh` writes **`API_HOST`** and **`BRAINLIFE_AUTHENTICATION`** into `public/runtime-env.js`. A static web build served without that file falls back to the build-time **`VITE_APIHOST`** / **`VITE_BRAINLIFE_AUTHENTICATION`** (`ui/src/runtimeEnv.ts`). Google Analytics loads only in the web UI, never in the desktop app.
-   **Handler**: repo is bind-mounted at `/app` (it uses the host's root `node_modules`, so run `npm install` first); MongoDB store, no Electron code is loaded. The image provides the tools in the desktop bundle layout (`EZBIDS_BIN_DIR=/opt/ezbids-bin`: dcm2niix pinned, 7z, allineate) and its own `python3`. Telemetry is off unless **`EZBIDS_TELEMETRY_URL`** is set (never in the desktop app).

API and UI images are built with **`context: .`** at the repo root; see **`.dockerignore`** for what is excluded from the build context. The **handler** image uses **`build: ./handler`** (its own context).

---

#### Electron desktop (development)

Desktop dev uses the **Electron main process** to spawn the **API** and **handler** as child processes and opens a window.

1. **Install** (from repo root): **`npm install`**.
2. **UI in dev**: Electron’s main window loads **`http://localhost:3000`** in development. Start Vite in a **separate terminal**: **`npm run ui:dev`** (or `npm run dev -w ui`).
3. **Electron**: In another terminal from the repo root: **`npm run electron:start-dev`** (runs the **`start-dev`** script in the **`ezbids-electron`** workspace).

**`start-dev`** (see `electron/package.json`) runs **`build:electron-preload`** and **`build:electron-main`** (esbuild bundles **`preload/preload.ts`** and **`electron/main.ts`**), then starts **`electron .`**. Those two entry files are **not** run through `ts-node-dev`; **after you edit `main.ts` or `preload.ts`, rerun `npm run electron:start-dev`** (or the individual `build:electron-main` / `build:electron-preload` scripts) so the bundles under `electron/dist` / preload output stay in sync.

**Hot reload** applies to almost everything else in dev: **`main.ts`** spawns **`ts-node-dev`** for **`api/ezbids.ts`** and **`handler/handler.ts`** with **`--watch`** on those directories, so changes under **`api/`** and **`handler/`** reload without restarting Electron (see `startBackend` / `startHandler` in `electron/main.ts`).

**Packaged / production-style Electron** uses pre-bundled `.cjs` files and the built UI; that path is heavier—see **`npm run electron:pack`** and **`fetch-binaries.sh`** when you need native binaries under `handler/bin`.

For **local Electron development**, local RSA private/public keys and signing/notarization keys are **not utilized**. You can run `npm run electron:start-dev` without them.

---

#### Building the Electron app (artifacts + installers)

Electron build and packaging logic is split between root workspace scripts (`package.json`) and Electron-local scripts (`electron/package.json`).

**Root helper scripts (run from repo root):**

-   **`npm run fetch-binaries:macos`** -> `./fetch-binaries.sh darwin arm64`
-   **`npm run fetch-binaries:linux`** -> `./fetch-binaries.sh linux amd64`
-   **`npm run fetch-binaries:windows`** -> `./fetch-binaries.sh windows amd64`
-   **`npm run electron:pack-test`** -> run Electron build, then `electron-builder --dir` (unsigned/unpacked app output for testing packaging contents; run a `fetch-binaries:*` script first if `handler/bin` is missing)
-   **`npm run electron:pack`** -> full build + `electron-builder` distributables (DMG/EXE/AppImage/DEB depending on platform/target)

Note: packaging/signing keys (for example Apple certificate/API key variables) are only needed for signed release workflows, not for local desktop development.

**Electron workspace scripts (in `electron/package.json`):**

-   **`build:electron-api`** bundles `api/ezbids.ts` -> `electron/dist/ezbids.cjs`
-   **`build:electron-handler`** and **`build:electron-handler-scripts`** bundle `handler/*.ts` entry points -> `electron/dist/handler/*.cjs`
-   **`build:electron-python`**, **`build:electron-templates`**, **`build:electron-bids-spec`** copy runtime resources into `electron/dist`
-   **`build:electron-frontend`** triggers the UI workspace build for Electron output
-   **`build:electron-main`** and **`build:electron-preload`** build desktop entry files
-   **`build:electron`** runs the full chain above
-   **`app:dir`** and **`app:dist`** invoke `electron-builder`; **`app:build-dist`** runs full build then dist

**About `fetch-binaries.sh`:**

-   Fetches native/runtime assets from `brainlife/ezbids-binaries` release `vX.X.X` and extracts to **`handler/bin`** (0.0.5 at the time of writing this).
-   Usage: **`./fetch-binaries.sh <platform> [arch]`**, where `platform` is one of `darwin|linux|windows` and `arch` is `amd64|arm64`.
-   Requires `curl`, `jq`, `tar`, `unzip`; for private repo access set **`GITHUB_TOKEN`**.
-   Run this before packaging whenever `handler/bin` is missing/outdated for your target platform.

---

#### Other developer workflow notes

-   **API only (no Docker)**: **`npm run dev`** runs **`ts-node-dev`** on **`./api/ezbids.ts`** (you must provide Mongo and paths yourself, e.g. `MONGO_CONNECTION_STRING`, upload/workdir env vars as in `api/config.ts`).
-   **Transpile / production API**: **`npm run prod`** (TypeScript compile then Node on `./build/ezbids.js`).
-   **Tests / style**: **`npm test`**, **`npm run lint-check`**, **`npm run style-check`** at the root; **Husky** is set up via **`npm run prepare-husky`** (also invoked from `dev.sh`).
-   **Desktop release builds**: CI and local packaging use scripts under **`electron/package.json`** (e.g. **`build:electron`**, **`app:dist`**); see **`.github/workflows/build-desktop.yml`**.

### Authors

-   [Daniel Levitas](djlevitas208@gmail.com)\*
-   [Soichi Hayashi](soichih@gmail.com)\*
-   [Sophia Vinci-Booher](sophia.vinci-booher@vanderbilt.edu)
-   [Anibal Heinsfeld](anibalsolon@utexas.edu)
-   [Dheeraj Bhatia](dheeraj.bhatia@utexas.edu)
-   [Nicholas Lee](niconal902@gmail.com)
-   [Anthony Galassi](niconal902@gmail.com)
-   [Guiomar Niso](guiomar.niso@ctb.upm.es)
-   [Franco Pestilli]([@francopestilli](https://github.com/francopestilli))

*   _Both authors contributed equally to this project_

### Funding Acknowledgement

brainlife.io is publicly funded, and for the sustainability of the project it is helpful to acknowledge the use of the platform. We kindly ask that you acknowledge the funding below in your code and publications. Copy and past the following lines into your repository when using this code.

ezBIDS and aimport are developed by the Pestilli Lab at The University of Texas at Austin; please also acknowledge The University of Texas at Austin.

[![NIH-NINDS-U24NS140384](https://img.shields.io/badge/NIH_NINDS-U24NS140384-green.svg)](https://reporter.nih.gov/project-details/U24NS140384)
[![NIH-NIMH-R01MH126699](https://img.shields.io/badge/NIH_NIMH-R01MH126699-green.svg)](https://reporter.nih.gov/project-details/R01MH126699)
[![NIH-NIBIB-R01EB030896](https://img.shields.io/badge/NIH_NIBIB-R01EB030896-green.svg)](https://reporter.nih.gov/project-details/R01EB030896)
[![NIH-NIBIB-R01EB029272](https://img.shields.io/badge/NIH_NIBIB-R01EB029272-green.svg)](https://reporter.nih.gov/project-details/R01EB029272)
[![NSF-BCS-1636893](https://img.shields.io/badge/NSF_BCS-1636893-blue.svg)](https://www.nsf.gov/awardsearch/showAward?AWD_ID=1636893)
[![NSF-2148729](https://img.shields.io/badge/NSF-2148729-blue.svg)](https://www.nsf.gov/awardsearch/showAward?AWD_ID=2148729)
[![NSF-BCS-1734853](https://img.shields.io/badge/NSF_BCS-1734853-blue.svg)](https://www.nsf.gov/awardsearch/showAward?AWD_ID=1734853)
[![NSF-2203524](https://img.shields.io/badge/NSF-2203524-blue.svg)](https://www.nsf.gov/awardsearch/showAward?AWD_ID=2203524)
[![NSF-IIS-1912270](https://img.shields.io/badge/NSF_IIS-1912270-blue.svg)](https://www.nsf.gov/awardsearch/showAward?AWD_ID=1912270)
[![NSF-2148700](https://img.shields.io/badge/NSF-2148700-blue.svg)](https://www.nsf.gov/awardsearch/showAward?AWD_ID=2148700)
[![NSF-ACI-1916518](https://img.shields.io/badge/NSF_ACI-1916518-blue.svg)](https://www.nsf.gov/awardsearch/showAward?AWD_ID=1916518)
[![Wellcome-226486](https://img.shields.io/badge/Wellcome_Trust-226486-purple.svg)](https://grantnav.threesixtygiving.org/grant/360G-Wellcome-226486_Z_22_Z)

### Built on and how to cite

Please cite the ezBIDS paper when you publish data converted with ezBIDS or aimport:

> Levitas, D., Hayashi, S., Vinci-Booher, S., Heinsfeld, A., Bhatia, D., Lee, N., Galassi, A., Niso, G. & Pestilli, F. (2024). ezBIDS: Guided standardization of neuroimaging data interoperable with major data archives and platforms. *Scientific Data*, 11, 179. [doi:10.1038/s41597-024-02959-0](https://doi.org/10.1038/s41597-024-02959-0)

ezBIDS and aimport are developed by the Pestilli Lab at The University of Texas at Austin and built on many open-source tools. **[CREDITS.md](CREDITS.md)** lists the BIDS papers to cite for your data type and every tool we build on, with its licence and citation ([`CITATION.cff`](CITATION.cff) is the machine-readable version).

Copyright © 2022 brainlife.io at The University of Texas at Austin
