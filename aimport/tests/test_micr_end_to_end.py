"""Microscopy, end to end: planted PS-OCT, OME-TIFF and SVS inputs through the real app, nothing identifying leaves.

Drives the real app through its API (TestClient, token, Host header) with the real BIDS validator and a
recording LLM client, as test_end_to_end.py does for MRI. Then re-imports the bids-examples micr datasets.
The end-to-end and bids-examples tests are docker tests (the validator is in the image); test_cmc_plan_remote is a
network test (the CMC public bucket, by range reads; run by hand, bytes recorded in DATASETS.md).
"""
from __future__ import annotations

import csv
import hashlib
import json
import sys
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from aimport import server
from aimport.micr.module import RAW_REASON
from aimport.server import create_app
from conftest import MICR_PLANTED

sys.path.insert(0, str(Path(__file__).parent / "fixtures"))
from fetch_bids_examples import MICR_EXAMPLES, fetch_bids_example  # noqa: E402
from micr_fixtures import METADATA_FILES, PLANTED_RAW, SVS_LABEL_TEXT, planted_ome_tiff, planted_psoct, planted_svs  # noqa: E402

TOKEN = "e2e-micr-token"
PORT = 8765
HOST = f"localhost:{PORT}"
TERMINAL = {"planned", "validated", "invalid", "failed"}
BIDS_EXAMPLES_CACHE = Path("/tmp/aimport-bids-examples-cache")
# what a reviewer types for the volume whose source has no pixel size (never invented by aimport)
MAT_PIXEL_SIZE = {"pixel_size": [10.0, 10.0, 2.5], "pixel_size_units": "um"}
SVS_LABEL_SHAPES = {(32, 28), (64, 28)}  # planted_svs label and macro (y, x)
MIB = 2**20


def found(text: str) -> set[str]:
    low = text.lower()
    return {t for t in MICR_PLANTED if t in low}


class Recorder:
    """An LLM client that records every request and answers like a sensible model."""

    name = "recorder"

    def __init__(self):
        self.requests: list[str] = []
        self.steps: list[str] = []

    def complete(self, system, user, step):
        self.requests.append(system + "\n" + user)
        self.steps.append(step)
        if step == "metadata":
            return json.dumps({"name": "Microscopy QA", "readme": "PS-OCT, confocal and slide images."})
        answers = []
        for s in json.loads(user)["series"]:
            guess = s.get("ezbids_guess") or {}
            fields = s.get("fields") or {}
            if guess.get("suffix"):
                suffix = guess["suffix"]
            elif fields.get("ExcitationWavelengths"):
                suffix = "CONF"  # fluorescence channels
            else:
                suffix = "BF"  # an RGB slide
            answers.append({"series_idx": s["series_idx"], "datatype": "micr", "suffix": suffix, "entities": {},
                            "confidence": 0.9, "reason": "image facts"})
        return json.dumps(answers)


class Api:
    """TestClient wrapper: bearer token, loopback Host, every response body (and redirect target) kept."""

    def __init__(self, app):
        self.app = app
        self.client = TestClient(app, base_url=f"http://{HOST}")
        self.client.headers["Authorization"] = f"Bearer {TOKEN}"
        self.bodies: list[str] = []

    def call(self, method, path, **kw):
        r = self.client.request(method, path, **kw)
        self.bodies.append(r.text + "\n" + r.headers.get("location", ""))
        return r

    def wait(self, timeout=1800):
        end = time.time() + timeout
        while time.time() < end:
            status = self.call("GET", "/status").json()
            if status["stage"] in TERMINAL:
                return status
            time.sleep(0.5)
        raise AssertionError("timed out")

    def events(self) -> list[dict]:
        r = self.call("GET", "/events")
        assert r.status_code == 200
        return [json.loads(line[6:]) for line in r.text.splitlines() if line.startswith("data: ")]

    def viewer(self) -> list[str]:
        """Every /viewer/* body a browser gets: the session exchange, the index, each entry's redirect."""
        code = self.call("POST", "/viewer/session").json()["code"]
        browser = TestClient(self.app, base_url=f"http://{HOST}")
        bodies = []
        r = browser.get(f"/viewer/open?code={code}", follow_redirects=False)
        assert r.status_code == 303, r.text
        bodies.append(r.text + r.headers.get("location", ""))
        index = browser.get("/viewer/")
        assert index.status_code == 200
        bodies.append(index.text)
        for eid in self.call("GET", "/status").json()["manifest"]:
            r = browser.get(f"/viewer/entry/{eid}", follow_redirects=False)
            assert r.status_code == 303, r.text
            bodies.append(r.text + r.headers["location"])
        return bodies


def snapshot(root: Path) -> dict[str, tuple[int, str]]:
    """Every file and folder under root: its mtime and (files) a content hash."""
    out = {}
    for p in sorted([root, *root.rglob("*")]):
        digest = hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else "dir"
        out[str(p.relative_to(root))] = (p.lstat().st_mtime_ns, digest)
    return out


def tree_bytes(root: Path, skip: Path | None = None) -> int:
    return sum(p.lstat().st_size for p in root.rglob("*")
               if p.is_file() and not (skip and (p == skip or skip in p.parents)))


def approve_and_execute(api: Api) -> dict:
    """Set what only the reviewer can (a pixel size the source lacks), approve and execute."""
    plan = api.call("GET", "/plan").json()
    edits = [{"id": e["id"], **MAT_PIXEL_SIZE} for e in plan["entries"]
             if e["status"] == "unknown" and e["reason"].startswith("pixel size")]
    if edits:
        assert api.call("PATCH", "/plan", json={"edits": edits}).status_code == 200
    assert api.call("POST", "/approve", json={}).status_code == 200
    assert api.call("POST", "/execute").status_code == 202
    return api.wait()


@pytest.fixture(scope="module")
def e2e(tmp_path_factory):
    """One run over planted_psoct + planted_ome_tiff + planted_svs: scan, review, approve, execute, view."""
    tmp = tmp_path_factory.mktemp("micr-e2e")
    inp, work, keys = tmp / "in", tmp / "work", tmp / "keys"
    planted_psoct(inp)
    planted_ome_tiff(inp / "confocal" / "stack.ome.tif")
    planted_svs(inp / "histology" / "slide.svs")
    before = snapshot(inp)
    rec = Recorder()
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(server, "client_from_env", lambda: rec)
        app = create_app(inp, work, keys, TOKEN, [], [HOST])
        api = Api(app)
        try:
            assert api.call("POST", "/scan", json={"project_id": "proj"}).status_code == 202
            planned = api.wait()
            assert planned["stage"] == "planned", planned
            plan_before = api.call("GET", "/plan").json()
            plan_json = (work / "plan.json").read_text()
            status = approve_and_execute(api)
            events = api.events()
            plan = api.call("GET", "/plan").json()
            viewer = api.viewer() if status["stage"] == "validated" else []
        finally:
            app.state.server.close()
    yield {"inp": inp, "work": work, "before": before, "rec": rec, "api": api, "status": status,
           "events": events, "plan": plan, "plan_before": plan_before, "plan_json": plan_json,
           "viewer": viewer, "out": work / "output" / "bids"}


@pytest.mark.docker
def test_micr_e2e_validated(e2e):
    s = e2e["status"]
    assert s["stage"] == "validated", s
    assert s["validation"]["ok"] is True, s["validation"]["errors"]
    assert e2e["events"] and e2e["events"][-1]["stage"] == "validated"
    written = {e["suffix"] for e in e2e["plan"]["entries"] if e["id"] in s["manifest"]}
    assert {"OCT", "CONF", "BF"} <= written, written
    assert e2e["rec"].requests and "classify" in e2e["rec"].steps


@pytest.mark.docker
def test_micr_e2e_no_leak(e2e):
    work, out = e2e["work"], e2e["out"]
    # positive controls: the identifiers are really in the input to leak
    inp = e2e["inp"]
    assert found(str(sorted(p.relative_to(inp) for p in inp.rglob("*")))) >= {"h17", "250215"}
    assert found((inp / "H17_250215" / "acqinfo_metadata.json").read_text()) >= {"jane doe", "lab-workstation-7"}
    # every LLM request
    for i, request in enumerate(e2e["rec"].requests):
        assert not found(request), (i, found(request))
    # the records the server keeps beside the run, and every API body (/plan, /status, /events, /viewer/*)
    for name in ("plan.json", "scan.json", "status.json"):
        assert not found((work / name).read_text()), name
    assert not found(e2e["plan_json"])
    assert len(e2e["viewer"]) >= 3
    bodies = e2e["api"].bodies + e2e["viewer"]
    assert len(bodies) > 10
    for body in bodies:
        assert not found(body), found(body)
    # every byte under output/bids: every name and metadata document for every term; pixel chunks (compressed
    # random data, where a 3-4 byte code such as "h17" turns up by chance: it did in the SVS chunk) for every term
    # of 6+ characters, the SVS label text and the raw tiles' bytes, before and after decoding
    assert out.is_dir() and any(out.rglob("*.ome.zarr"))
    assert not found("\n".join(str(p.relative_to(out)) for p in out.rglob("*")))
    long_terms = {t for t in MICR_PLANTED if len(t) >= 6}
    assert long_terms >= {"jane doe", "250215", "20250422", "slide 42 smith"}
    for p in out.rglob("*"):
        if not p.is_file():
            continue
        text = p.read_bytes().decode("latin-1")
        hits = found(text) if p.name in METADATA_FILES or ".ome.zarr" not in str(p) else found(text) & long_terms
        assert not hits, (p.relative_to(out), hits)
        assert SVS_LABEL_TEXT.decode() not in text and PLANTED_RAW.decode() not in text
    for store, arr in _arrays(out):
        pixels = arr[...].tobytes().decode("latin-1")
        assert SVS_LABEL_TEXT.decode() not in pixels and not found(pixels) & long_terms, store


@pytest.mark.docker
def test_micr_e2e_no_copy(e2e):
    work, out = e2e["work"], e2e["out"]
    records = tree_bytes(work, skip=out)
    assert records < 2 * MIB, records
    assert not [p for p in work.rglob("*") if p.is_symlink()]
    assert not [p for p in work.rglob("*") if p.suffix in (".dat", ".mat", ".svs", ".tif", ".gz")]
    assert snapshot(e2e["inp"]) == e2e["before"]


@pytest.mark.docker
def test_micr_e2e_raw_excluded_and_reported(e2e):
    raw = [e for e in e2e["plan"]["entries"] if e["reason"] == RAW_REASON]
    assert len(raw) == 1, [e["reason"] for e in e2e["plan"]["entries"]]
    (e,) = raw
    assert (e["status"], e["exclude"], e["write_mode"]) == ("unsupported", True, "")
    assert e["description"] == "raw PS-OCT (2 files); not readable"
    assert e["id"] not in e2e["status"]["manifest"]
    assert not list(e2e["out"].rglob("*.dat"))
    # the plan also reports what conversion writes; the reference is not converted
    assert any(w.startswith("conversion writes about") for w in e2e["plan_before"]["warnings"])
    modes = {e["write_mode"] for e in e2e["plan"]["entries"] if e["id"] in e2e["status"]["manifest"]}
    assert modes == {"convert", "reference"}


def _arrays(out: Path):
    """(store, array) for every array of every OME-Zarr store written under out."""
    import zarr

    for store in sorted(out.rglob("*.ome.zarr")):
        for _name, arr in zarr.open_group(str(store), mode="r").arrays():
            yield store, arr


@pytest.mark.docker
def test_micr_e2e_label_macro_absent(e2e):
    shapes = [tuple(arr.shape) for _store, arr in _arrays(e2e["out"])]
    assert shapes
    assert not [s for s in shapes if tuple(s[-2:]) in SVS_LABEL_SHAPES or tuple(s[-3:-1]) in SVS_LABEL_SHAPES], shapes


# --- bids-examples: BIDS micr datasets re-imported --------------------------------------------


def _rows(path: Path) -> list[dict]:
    with open(path, newline="") as fh:
        return [{k.strip(): v for k, v in row.items()} for row in csv.DictReader(fh, delimiter="\t")]


def _labels(root: Path, entity: str) -> set[str]:
    out = set()
    for p in root.rglob("*"):
        for piece in p.name.split("_"):
            if piece.startswith(entity + "-"):
                out.add(piece.split(".")[0])
    return out


# bids-examples ships placeholder images (1 or 0 bytes) except micr_SPIM's small OME-TIFFs and the Zarr metadata.
# micr_SEM holds no image aimport writes: its SEM images are PNG placeholders (PNG is reported, never read) and
# its photo a 1-byte TIFF, so the output has no subject and the validator refuses its tables.
SEM_NOTHING_WRITTEN = pytest.mark.xfail(strict=True, reason="micr_SEM: every image is a PNG or 1-byte placeholder; "
                                        "nothing is written")


@pytest.mark.docker
@pytest.mark.parametrize("name", [pytest.param(n, marks=SEM_NOTHING_WRITTEN) if n == "micr_SEM" else n
                                  for n in MICR_EXAMPLES])
def test_bids_examples_micr(name, tmp_path, monkeypatch):
    inp = fetch_bids_example(name, tmp_path / "in", cache=BIDS_EXAMPLES_CACHE)
    monkeypatch.setattr(server, "client_from_env", lambda: None)
    app = create_app(inp, tmp_path / "work", tmp_path / "keys", TOKEN, [], [HOST])
    api = Api(app)
    try:
        assert api.call("POST", "/scan", json={"project_id": "proj"}).status_code == 202
        planned = api.wait()
        assert planned["stage"] == "planned", planned
        status = approve_and_execute(api)
        plan = api.call("GET", "/plan").json()
    finally:
        app.state.server.close()
    # every image of the input is an entry: written, or reported with its reason (a PNG, a placeholder)
    unread = [e for e in plan["entries"] if e["status"] == "unsupported"]
    assert all(e["exclude"] and e["reason"] for e in unread)
    assert status["stage"] == "validated", status
    assert status["validation"]["ok"] is True, status["validation"]["errors"]
    out = Path(status["output_dir"])
    assert status["manifest"], "nothing was written"
    images = [p for p in out.rglob("*") if p.name.endswith(".ome.zarr")]
    # the subject and sample labels are kept
    written = [e for e in plan["entries"] if e["id"] in status["manifest"]]
    assert {f"sub-{e['subject']}" for e in written} <= _labels(inp, "sub")
    assert {f"sample-{e['entities']['sample']}" for e in written} <= _labels(inp, "sample")
    assert _labels(out, "sub") <= _labels(inp, "sub")
    assert {lab for lab in _labels(out, "sample")} <= _labels(inp, "sample")
    # samples.tsv rows are preserved (the rows of the subjects in the import)
    want = {(r["sample_id"], r["participant_id"], r["sample_type"]) for r in _rows(inp / "samples.tsv")}
    got = {(r["sample_id"], r["participant_id"], r["sample_type"]) for r in _rows(out / "samples.tsv")}
    assert got == want, (got, want)
    if images:
        assert {f"sample-{e['entities']['sample']}" for e in written} <= {r[0] for r in got}


# --- network: a remote CMC subset planned through the API (keys pinned in DATASETS.md) ---------------

CMC = "s3://apex-connects/CMC/Derivatives/Moe/PS-OCT/"
CMC_ENFACE = [CMC + f"Enface/Registration/{folder}/Slice_001_{code}_hdr.nii.gz"
              for folder, code in (("Reflectivity", "EnRef"), ("Retardance", "EnR"), ("Orientation", "EnAO"),
                                   ("Cross", "EnCr"))]
CMC_PSOCT_ZARR = CMC + "Zarr/Moe_Slice_051.ome.zarr"
CMC_EXASPIM = "s3://apex-connects/axonal_connectomics/deskewed/H17_PO10_S5_20250417/exaSPIM.zarr/Pos0"
CMC_CAP = 32 * MIB


@pytest.mark.network
def test_cmc_plan_remote(tmp_path, monkeypatch):
    """One en-face NIfTI per contrast, the PS-OCT store and one exaSPIM position, scanned through the API: the plan
    builds, the NIfTIs are converted and the stores referenced, and every remote read together stays under 32 MiB."""
    from aimport.micr import remote

    counters = []

    class Counted(remote.ByteCounter):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            counters.append(self)

    monkeypatch.setattr(remote, "ByteCounter", Counted)
    monkeypatch.setattr(server, "client_from_env", lambda: None)
    monkeypatch.setattr(server, "run_ezbids", lambda *a, **k: pytest.fail("nothing is left for ezBIDS"))
    inp = tmp_path / "in"
    inp.mkdir()
    app = create_app(inp, tmp_path / "work", tmp_path / "keys", TOKEN, [], [HOST])
    api = Api(app)
    try:
        urls = [*CMC_ENFACE, CMC_PSOCT_ZARR, CMC_EXASPIM]
        assert api.call("POST", "/scan", json={"project_id": "proj", "remote": urls}).status_code == 202
        status = api.wait(timeout=600)
        assert status["stage"] == "planned", status
        plan = api.call("GET", "/plan").json()
    finally:
        app.state.server.close()
    entries = plan["entries"]
    assert len(entries) == 6, [(e["description"], e["reason"]) for e in entries]
    octs = [e for e in entries if e["description"].startswith("NIfTI")]
    stores = [e for e in entries if e["description"].startswith("OME-Zarr")]
    assert len(octs) == 4 and {e["write_mode"] for e in octs} == {"convert"}
    assert {e["suffix"] for e in octs} == {"OCT"}
    assert {e["entities"].get("acquisition") for e in octs} == {"reflectivity", "retardance", "opticaxis", "cross"}
    assert len(stores) == 2 and {e["write_mode"] for e in stores} == {"reference"}
    assert len({e["subject"] for e in octs}) == 1  # one donor (Moe) for the four contrasts of slice 1
    for body in api.bodies:
        assert "amazonaws" not in body and "apex-connects" not in body and not found(body)
    total = sum(c.total for c in counters)
    print(f"cmc plan remote: {len(counters)} counters, bytes={total}")
    assert counters and total < CMC_CAP
