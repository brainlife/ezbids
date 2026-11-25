"""The whole engine, end to end, on planted real DICOMs: nothing identifying may leave in any form.

Drives the real app through its API (TestClient, token, Host header) with the real ezBIDS, writer,
defacer and BIDS validator, and a recording LLM client. Docker only: the tools are in the image.
"""
import gzip
import json
import os
import shutil
import stat
import sys
import time
from pathlib import Path

import nibabel as nib
import pytest
from fastapi.testclient import TestClient

from aimport import server
from aimport.server import create_app
from conftest import NATIVE, PLANTED, tokens

sys.path.insert(0, str(Path(__file__).parent / "fixtures"))
from fetch_dcm_qa import SUBJECT_DIR, _read_dicom, fetch_dcm_qa  # noqa: E402

pytestmark = pytest.mark.docker

HERE = Path(__file__).parent
TOKEN = "e2e-token"
PORT = 8765
HOST = f"localhost:{PORT}"
CACHE = Path(os.environ.get("AIMPORT_DCM_QA_CACHE", "/tmp/aimport-dcm-qa-cache"))
README_EDIT = "Resting and task scans. Contact john.smith@example.org about MRN0042 at Hospital X."
TERMINAL = {"planned", "validated", "invalid", "failed"}
# the default column decisions for the fixture tables (kept tables are checked against the output too)
EXPECTED_COLUMNS = {
    "participants.tsv": {"participant_id": "keep", "age": "keep", "sex": "keep", "name": "drop", "dob": "drop",
                         "visit_date": "shift_date", "site": "keep", "handedness": "keep", "notes": "drop",
                         "email": "drop", "hospital_id": "drop"},
    "samples.tsv": {"sample_id": "keep", "participant_id": "keep", "sample_type": "keep", "collected_by": "keep"},
    "phenotype/moca.tsv": {"participant_id": "keep", "moca_total": "keep", "assessment_date": "shift_date",
                           "rater": "keep", "examiner_initials": "drop", "comments": "drop"},
}


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
            return json.dumps({"name": "Siemens XA30 QA", "readme": "Anatomical and functional MRI acquisitions."})
        answers = []
        for s in json.loads(user)["series"]:
            guess = s.get("ezbids_guess") or {}
            text = (s["description"] + " " + (guess.get("suffix") or "")).lower()
            if "bold" in text or "fmri" in text or guess.get("datatype") == "func":
                answers.append({"series_idx": s["series_idx"], "datatype": "func", "suffix": "bold",
                                "entities": {"task": "fa"}, "confidence": 0.9, "reason": "BOLD EPI"})
            elif guess.get("datatype") and guess.get("suffix"):
                answers.append({"series_idx": s["series_idx"], "datatype": guess["datatype"],
                                "suffix": guess["suffix"], "entities": {}, "confidence": 0.8, "reason": "agrees"})
            else:
                answers.append({"series_idx": s["series_idx"], "datatype": None, "suffix": None,
                                "entities": {}, "confidence": 0.1, "reason": "unclear"})
        return json.dumps(answers)


class Api:
    """TestClient wrapper: bearer token, loopback Host, and every non-preview response body kept."""

    def __init__(self, app):
        self.client = TestClient(app, base_url=f"http://{HOST}")
        self.client.headers["Authorization"] = f"Bearer {TOKEN}"
        self.bodies: list[str] = []

    def call(self, method, path, **kw):
        r = self.client.request(method, path, **kw)
        if not path.startswith("/preview"):
            self.bodies.append(r.text)
        return r

    def wait(self, timeout=1800):
        end = time.time() + timeout
        while time.time() < end:
            status = self.call("GET", "/status").json()
            if status["stage"] in TERMINAL:
                return status
            time.sleep(1)
        raise AssertionError("timed out")

    def events(self) -> list[dict]:
        r = self.call("GET", "/events")
        assert r.status_code == 200
        return [json.loads(line[6:]) for line in r.text.splitlines() if line.startswith("data: ")]


def file_text(path: Path) -> str:
    """What to search for terms in a file: text content (gunzipped), plus the NIfTI header's text fields."""
    name = path.name
    raw = path.read_bytes()
    if name.endswith(".gz"):
        try:
            raw = gzip.decompress(raw)
        except OSError:
            pass
    if name.endswith((".nii", ".nii.gz")):
        header = nib.load(str(path)).header
        fields = [bytes(header[k]).decode("latin-1") for k in ("descrip", "aux_file", "intent_name", "db_name")]
        return "\n".join(fields) + "\n" + raw[:540].decode("latin-1")  # the header incl. extension flag
    return raw.decode("utf-8", errors="ignore")


def all_text_of(root: Path) -> list[tuple[str, str]]:
    return [(str(p.relative_to(root)), file_text(p)) for p in sorted(root.rglob("*")) if p.is_file()]


def test_end_to_end_no_identifier_leaves(tmp_path, monkeypatch):
    inp, work, keys = tmp_path / "in", tmp_path / "work", tmp_path / "keys"
    fetch_dcm_qa(inp, plant=True, cache=CACHE)
    # the ancillary fixtures (participants.tsv, phenotype, README, ... with planted identifiers) beside the DICOMs
    shutil.copytree(HERE / "fixtures" / "ancillary", inp, dirs_exist_ok=True)
    assert (inp / "participants.tsv").exists()
    # positive controls: the identifiers are really there to leak, so "none found" below means something
    dicoms = (_read_dicom(p) for p in sorted((inp / SUBJECT_DIR).rglob("*")) if p.is_file())
    header = next(str(ds) for ds in dicoms if ds is not None)
    assert {"smith", "mrn0042", "19700101", "hospital x"} <= tokens(header)
    assert PLANTED & tokens((inp / "README").read_text())
    assert PLANTED & tokens(README_EDIT)

    rec = Recorder()
    monkeypatch.setattr(server, "client_from_env", lambda: rec)
    app = create_app(inp, work, keys, TOKEN, [], [HOST])
    api = Api(app)
    try:
        # the loopback API needs the token and the right Host
        assert TestClient(app, base_url=f"http://{HOST}").get("/status").status_code == 401
        assert TestClient(app, base_url="http://evil.example:8765").get("/status").status_code == 421

        # scan
        assert api.call("POST", "/scan", json={"project_id": "proj"}).status_code == 202
        status = api.wait()
        assert status["stage"] == "planned", status
        assert any(ev["stage"] == "planned" for ev in api.events())

        # the model was consulted and saw only scrubbed requests, although the staged ezBIDS output still
        # holds the planted series descriptions (checked against the requests below)
        assert "classify" in rec.steps and rec.requests
        staged_core = json.loads((work / "ezbids" / "ezBIDS_core.json").read_text())
        staged_descriptions = " ".join(s.get("SeriesDescription", "") for s in staged_core["series"])
        assert PLANTED & tokens(staged_descriptions)
        plan = api.call("GET", "/plan").json()
        bold = [e for e in plan["entries"] if (e["datatype"], e["suffix"]) == ("func", "bold")]
        assert bold and all(e["entities"].get("task") == "fa" for e in bold)
        assert any(e["datatype"] == "anat" for e in plan["entries"])

        # every ancillary entry is readable; those the plan keeps carry no planted term
        assert plan["ancillary"], "the fixtures' files should be planned"
        for a in plan["ancillary"]:
            r = api.call("GET", f"/ancillary/{a['id']}")
            assert r.status_code == 200, (a["path"], r.text)
        # the files that do not belong to the DICOM subject cannot be linked to it: dropped or flagged
        tables = [a for a in plan["ancillary"] if a["kind"] == "table"]
        assert tables and all(a["action"] == "drop" or a["flags"] or a["columns"] for a in tables)
        by_path = {a["path"]: a for a in plan["ancillary"]}
        for path, columns in EXPECTED_COLUMNS.items():
            assert by_path[path]["columns"] == columns, (path, by_path[path]["columns"])

        # the reviewer drops what cannot be valid here: files of subjects that are not in the import
        drop = {"CITATION.cff", "genetic_info.json", "task-rest_bold.json", "task-rest_events.json",
                "phenotype/moca.tsv", "phenotype/moca.json"}
        edits = [{"id": a["id"], "action": "drop"} for a in plan["ancillary"] if a["path"] in drop]
        assert len(edits) == len(drop)
        assert api.call("PATCH", "/plan", json={"ancillary_edits": edits}).status_code == 200
        # ASL is excluded by default, and the input's README is the plan's README (not written twice)
        plan = api.call("GET", "/plan").json()
        assert all(e["exclude"] for e in plan["entries"] if e["suffix"] == "asl")
        readme_entry = next(a for a in plan["ancillary"] if a["path"] == "README")
        assert (readme_entry["action"], readme_entry["reason"]) == ("drop", "used as the dataset README")
        assert "Synthetic test dataset" in plan["readme"] and not (PLANTED | NATIVE) & tokens(plan["readme"])

        # a reviewer's README edit with identifiers comes back redacted
        r = api.call("PATCH", "/plan", json={"readme": README_EDIT})
        assert r.status_code == 200
        # reviewer text is redacted when accepted: the response already holds none of it
        assert r.json()["readme"].startswith("Resting and task scans") and not PLANTED & tokens(r.json()["readme"])
        assert "[x]" in r.json()["readme"]

        # approve (quickshear: fast) and execute
        r = api.call("POST", "/approve", json={"deface_method": "quickshear"})
        assert r.status_code == 200 and r.json()["approved"] is True and r.json()["deface_method"] == "quickshear"
        assert api.call("POST", "/execute").status_code == 202
        status = api.wait()
        assert status["stage"] == "validated", status
        v = status["validation"]
        assert v["ok"] is True, sorted({(e["code"], e.get("subCode") or "", (e.get("files") or [""])[0].split("/")[-1][:60]) for e in v["errors"]})
        events = api.events()
        assert events and events[-1]["stage"] == "validated"
        api.call("GET", "/plan")
        api.call("GET", "/status")

        out = Path(status["output_dir"])
        pre = work / "pre-deface"
        assert out.is_dir() and any(out.rglob("*.nii.gz"))
        # each kept table is written with exactly its kept columns (dropped ones gone, key columns kept)
        plan = api.call("GET", "/plan").json()
        kept = [a for a in plan["ancillary"] if a["path"] in EXPECTED_COLUMNS and a["action"] != "drop"]
        assert any(a["path"] == "participants.tsv" for a in kept)
        for a in kept:
            written = out / a["path"]
            if a["path"] != "participants.tsv" and not written.exists():
                assert any(r.startswith(a["path"]) for r in status["refused"]), a["path"]
                continue
            header = written.read_text().split("\n")[0].split("\t")
            assert set(header) == {c for c, act in a["columns"].items() if act != "drop"}, (a["path"], header)
    finally:
        app.state.server.close()

    # (a) every LLM request
    for i, request in enumerate(rec.requests):
        assert not PLANTED & tokens(request), (i, PLANTED & tokens(request))
        assert not NATIVE & tokens(request), (i, NATIVE & tokens(request))

    # (b) every file under the output: by path, and by content (gunzipped; NIfTI header text fields)
    assert not (PLANTED | NATIVE) & tokens("\n".join(str(p.relative_to(out)) for p in out.rglob("*")))
    for rel, text in all_text_of(out):
        found = (PLANTED | NATIVE) & tokens(text)
        assert not found, (rel, found)
    assert not list(out.rglob("*aimport-key*")), "the pseudonym key must never be in the output"
    assert not any(out in p.parents for p in [pre]), "originals must be outside the output"
    assert pre.is_dir() and any(pre.rglob("*.nii.gz")), "the pre-deface originals are kept outside the output"

    # the key lives in keys_dir, private
    key_files = [p for p in keys.iterdir() if "aimport-key" in p.name]
    assert key_files
    for p in key_files:
        assert stat.S_IMODE(p.stat().st_mode) == 0o600

    # (c) every JSON response and SSE event collected during the run
    assert len(api.bodies) > 10
    for body in api.bodies:
        assert not (PLANTED | NATIVE) & tokens(body), (PLANTED | NATIVE) & tokens(body)

    # the README the reviewer typed is in the output, with the identifiers redacted
    readmes = [p for p in out.iterdir() if p.name.startswith("README")]
    assert len(readmes) == 1, [p.name for p in out.iterdir()]
    readme = readmes[0].read_text()
    assert "scans" in readme and not (PLANTED | NATIVE) & tokens(readme)


def test_end_to_end_plain_dcm_qa_xa30_validates(tmp_path, monkeypatch):
    """The public dcm_qa_xa30 download as is, nothing planted: its own PatientName XAtest_sub-July11 holds the BIDS
    key `sub`, which is never a term, so execute writes sub-01... (defaced), validates, and neither value leaves."""
    inp, work, keys = tmp_path / "in", tmp_path / "work", tmp_path / "keys"
    root = fetch_dcm_qa(inp, plant=False, cache=CACHE)
    header = next(str(ds) for ds in (_read_dicom(p) for p in sorted(root.rglob("*")) if p.is_file()) if ds is not None)
    assert "XAtest_sub-July11" in header  # positive control: the set's own identifiers are there to leak
    native = NATIVE | {"xatest", "july11"}

    rec = Recorder()
    monkeypatch.setattr(server, "client_from_env", lambda: rec)
    app = create_app(inp, work, keys, TOKEN, [], [HOST])
    api = Api(app)
    try:
        assert api.call("POST", "/scan", json={"project_id": "proj"}).status_code == 202
        status = api.wait()
        assert status["stage"] == "planned", status
        plan = api.call("GET", "/plan").json()
        assert {e["subject"] for e in plan["entries"]} == {"01"}
        assert any(e["datatype"] == "anat" and not e["exclude"] for e in plan["entries"])
        r = api.call("POST", "/approve", json={"deface_method": "quickshear"})
        assert r.status_code == 200 and r.json()["approved"] is True
        assert api.call("POST", "/execute").status_code == 202
        status = api.wait()
        assert status["stage"] == "validated", status
        assert status["validation"]["ok"] is True
        out = Path(status["output_dir"])
    finally:
        app.state.server.close()

    assert any(out.glob("sub-01/**/anat/*_T1w.nii.gz"))
    assert (work / "pre-deface").is_dir() and any((work / "pre-deface").rglob("*.nii.gz")), "the T1w was defaced"
    assert not native & tokens("\n".join(str(p.relative_to(out)) for p in out.rglob("*")))
    for rel, text in all_text_of(out):
        low = text.lower()
        found = (native & tokens(text)) | {t for t in ("xatest", "july11") if t in low}
        assert not found, (rel, found)
    for request in rec.requests:
        assert not {t for t in ("xatest", "july11") if t in request.lower()}
    for body in api.bodies:
        assert not {t for t in ("xatest", "july11") if t in body.lower()}, body[:200]
