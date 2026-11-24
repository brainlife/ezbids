# aimport

brainlife.io/aimport: a local agentic data importer. Part of the ezBIDS repo.

Run tests with `cd aimport && uv run pytest`.

## Engine image

Local only (never pushed). Apple Silicon hosts build and run with `--platform linux/amd64`.
From the repo root:

```
git submodule update --init bids-specification aimport/bids-specification
docker build --platform linux/amd64 -t ezbids-handler:local handler/
docker build --platform linux/amd64 -t brainlife/aimport:dev -f aimport/Dockerfile .
docker run --rm --platform linux/amd64 -v $PWD/aimport:/src brainlife/aimport:dev pytest -m docker /src/tests/test_image.py
```

- ezBIDS lives at `/app` (its `bids-specification` submodule at the pinned `3537e9ed`); aimport is in `/opt/aimport-venv` (Python 3.11), last on `PATH`, so system `python3` stays 3.8 and `pytest` is the venv's.
- `aimport/bids-specification` (submodule, BIDS v1.11.2 at `fbe1af9a`) is exported to `/opt/bids-schema/schema.json` with `bst export`.
- BIDS validator: `@bids/validator` **2.4.1** (Deno 2.5.6), run through the `bids-validator-2` wrapper. That release bundles an older schema (it flags `BIDSVersion` 1.11.2 as unknown), so the wrapper defaults `--schema file:///opt/bids-schema/schema.json` unless `--schema`/`-s` is given. Works offline. Useful flags: `--format json` (`--json` is deprecated), `--schema <URL>`, `--ignoreNiftiHeaders`, `-o <file>`.
- Test data: `tests/fixtures/fetch_dcm_qa.py` fetches `neurolabusc/dcm_qa` at a pinned commit and plants fake PHI.
