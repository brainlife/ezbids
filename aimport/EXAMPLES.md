# Try aimport: three low-stakes examples

Three short walkthroughs on tiny, openly licensed test files, so nothing personal is at risk. Each run stops before
upload (`--no-upload`) and opens the local QA viewer (`--qa`), so you can see what aimport did and nothing leaves your
computer. The same commands are on the [ezBIDS landing page](https://brainlife.io/ezbids) ("Try it").

**Status:** aimport is in beta: run it from source today; packaged release coming. The engine image is not published
yet (you build it below), and `bl aimport` is on the [brainlife cli](https://github.com/brainlife/cli#bl-aimport)'s
`master` branch, not yet in a published npm release. Prefer an app? ezBIDS desktop runs the same engine as
**AI import (beta)** (build from source, tested on Mac; signed installers coming; see the
[README](../README.md#ezbids-desktop)); these examples use `bl aimport`.

## Set up once

You need Docker, Node.js 18 or newer, git, [uv](https://docs.astral.sh/uv/) (for example a) and a brainlife.io
account. On Colima (macOS), Docker mounts only folders under your home folder, so keep everything under `~`.

```
mkdir -p ~/aimport-try && cd ~/aimport-try
git clone --recursive https://github.com/brainlife/ezbids
(cd ezbids && docker build --platform linux/amd64 -t ezbids-handler:local handler/ \
  && docker build --platform linux/amd64 -t brainlife/aimport:dev -f aimport/Dockerfile .)
git clone https://github.com/brainlife/cli
(cd cli && npm install && npm link)
bl login
P=<your brainlife project id>
```

- `bl aimport` needs `--project` even with `--no-upload`: it reads the project's subject IDs so new IDs do not
  collide, and sends nothing to it.
- Every example uses its own work and keys folders (`~/aimport-try/work`, `~/aimport-try/keys`), so the test
  subjects never enter the pseudonym key of a real project.
- No AI key is needed: without one the built-in heuristics plan everything. To try the agent, set `AIMPORT_MODEL`
  and your provider's key first (see the cli README); it sees only de-identified plan text.
- At `Approve this plan? [y/N/e(dit)]`, read the plan and answer `y`. With `--qa --no-upload`, bl prints a
  one-time viewer link (`http://127.0.0.1:<port>/viewer/open?code=...`, valid for 60 s), opens it, and waits for
  Enter; then it stops the engine. Nothing is uploaded.

## a) MRI: Siemens DICOMs to a defaced T1w

Data: [neurolabusc/dcm_qa_xa30](https://github.com/neurolabusc/dcm_qa_xa30) (BSD-2-Clause; dcm2niix's Siemens XA30
test set, 44 MB) at the commit aimport's tests pin, as published: its headers carry their own identifiers (PatientName
`XAtest_sub-July11`, PatientID `12343@hucheng`, institution `Indiana University`), so you can check that they are gone.

```
cd ~/aimport-try
uv run --no-project --with pydicom python \
  ezbids/aimport/tests/fixtures/fetch_dcm_qa.py mri --plain
bl aimport mri --deface quickshear --project $P --qa --no-upload \
  --work ~/aimport-try/work --keys ~/aimport-try/keys
grep -ril -e xatest -e july11 -e hucheng work/output/bids || echo clean
```

What you should see:

- The plan: `anat/T1w` (two runs), `func/bold`, the field maps (`magnitude1`, `magnitude2`, `phasediff`) and two
  `dwi` series. The Siemens derived maps (ADC, TRACEW, FA, tensor) are left out as non-BIDS series, and ASL is
  excluded ("ASL needs aslcontext.tsv and labeling metadata the importer cannot derive yet"), each with its reason.
- `executing: defacing the anatomical images`, then `validated: no validation errors` (warnings are listed).
- In the QA viewer, "defaced vs original" shows the T1w with the face removed next to its original. Press Enter.
- The `grep` prints `clean`: the name and ID in its headers are in no output file.

`quickshear` takes about 40 seconds per T1w on Apple Silicon (the image runs under emulation); leave out
`--deface quickshear` to use `pydeface`, the default for real uploads (minutes per image).

## b) EEG: an EDF recording, one bad channel marked

Data: `EDF/test_reduced.edf` from [mne-tools/mne-testing-data](https://github.com/mne-tools/mne-testing-data)
(BSD-3-Clause, 0.8 MB) at the commit aimport's tests pin (SHA-256 `644acaf3...a39a`, in
[tests/DATASETS.md](tests/DATASETS.md)). It is saved as `rest.edf`: aimport takes the task label from a word in the
name (`rest`, `sleep`, `oddball`, ...), and without one the entry waits for you to set the task.

```
cd ~/aimport-try
mkdir -p eeg
curl -L -o eeg/rest.edf https://github.com/mne-tools/mne-testing-data/raw/20cc221d737a37a6ee3a9c007e91bd69541fefe9/EDF/test_reduced.edf
bl aimport eeg --project $P --qa --no-upload \
  --work ~/aimport-try/work --keys ~/aimport-try/keys
```

What you should see:

- The plan: one entry, `eeg` `task-rest`, "EDF → BrainVision, 139 ch (eeg 138, stim 1), 512 Hz, 6 s, 3 event codes".
  Event texts that are not safe labels become codes (`E001`, `E002`); the originals stay on your computer. A warning
  says the subject identity could not be established, so the subject gets a new ID for this import only.
- `validated`: `sub-01_task-rest_eeg.vhdr/.eeg/.vmrk`, `_channels.tsv`, `_events.tsv` and the sidecars.
- In the QA viewer, open **Traces** for the recording: pan and zoom, with the event codes as markers. In **Bad
  channels**, tick `A1`, pick the reason "noisy" and **Save**: aimport rewrites `channels.tsv` (`status` `bad`,
  `status_description` `noisy`), checks it again and validates the dataset again; the channel is drawn grey and dashed.
  Press Enter.

## c) Microscopy: light-sheet OME-TIFFs to OME-Zarr

Data: `micr_SPIM` from [bids-standard/bids-examples](https://github.com/bids-standard/bids-examples) (CC0, as its
`dataset_description.json` says; about 30 kB, extracted from the 16 MB bids-examples archive at the commit aimport's
tests pin).

```
cd ~/aimport-try
curl -L https://github.com/bids-standard/bids-examples/archive/5e00d47b6f1db106dda1b776d5243eb41b4cb95b.tar.gz \
  | tar xz --strip-components=1 bids-examples-5e00d47b6f1db106dda1b776d5243eb41b4cb95b/micr_SPIM
bl aimport micr_SPIM --project $P --qa --no-upload \
  --work ~/aimport-try/work --keys ~/aimport-try/keys
```

What you should see:

- The plan: 8 `micr` `SPIM` images, subject `01`, samples `A` and `B`, chunks `01` to `04`, named from the input's
  BIDS names; the two `photo.png` files are reported ("photographs are not imported").
- `validated`: each image as `sub-01_sample-<A|B>_chunk-<nn>_SPIM.ome.zarr` with its sidecar, plus `samples.tsv`.
- The QA viewer lists the eight images, each with a "Neuroglancer (OME-Zarr)" link. They are 1 x 1 pixel test
  images: this checks the pipeline, not the pixels. Press Enter.

Large microscopy stays where it is: an OME-Zarr input is read in place (only new metadata is written), and
`bl aimport --remote <https:// or s3:// URL>` reads a public remote OME-Zarr store by range requests, without
downloading it. We do not name a remote example here: the public store aimport's tests read states no licence.

## Afterwards

- `rm -rf ~/aimport-try/work ~/aimport-try/keys` removes everything the runs wrote; the downloaded data stay in
  `~/aimport-try`.
- On your own data, drop `--no-upload` when the plan and the viewer look right: bl then asks
  `Upload this dataset? [y/N/v(iewer link again)]` and uploads only on `y`. Use your own `--work`/`--keys` (or the
  defaults) and back up the keys folder: the pseudonym key is the only way back to the real identities.
- More: [aimport README](README.md) (what is guaranteed, the API, known limitations) and the
  [cli README](https://github.com/brainlife/cli#bl-aimport) (every `bl aimport` flag).
