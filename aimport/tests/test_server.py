"""The loopback API, with the pipeline functions replaced by fast fakes (the Docker end-to-end is test_image)."""
import json
import shutil
import threading
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from aimport import server
from aimport.pseudonyms import KeyLockedError, PseudonymKey
from aimport.server import create_app
from aimport.validate import ValidationResult
from conftest import NATIVE, PLANTED, tokens

FIXTURES = Path(__file__).parent / "fixtures"
TOKEN = "s3cret-token"
ORIGIN = "https://brainlife.io"
SCAN = {"project_id": "proj", "existing_subjects": [], "target": "bids"}


def planted_core() -> dict:
    """The committed ezBIDS output with sub-01/ses-1 folders and planted identifiers."""
    core = json.loads((FIXTURES / "ezbids_core_siemens.json").read_text())
    core["subjects"][0]["subject"] = "01"
    core["subjects"][0]["PatientInfo"] = [{"PatientID": "MRN0042", "PatientName": "Smith^John",
                                           "PatientBirthDate": "19700101", "InstitutionName": "Hospital X",
                                           "file_directory": "./sub-01/ses-1/anat"}]
    for o in core["objects"]:
        for item in o["items"]:
            item["path"] = item["path"].replace("./", "./sub-01/ses-1/", 1)
    for s in core["series"]:
        s["nifti_path"] = s["nifti_path"].replace("./", "./sub-01/ses-1/", 1)
        s["SeriesDescription"] = "Smith " + s["SeriesDescription"]
    return core


class Hooks:
    """Controls for the fake pipeline."""

    def __init__(self):
        self.gate = threading.Event()
        self.gate.set()
        self.write_error: Exception | None = None
        self.validation = ValidationResult(ok=True, validator_version="2.4.1", bids_version="1.11.2")


@pytest.fixture
def hooks(monkeypatch):
    h = Hooks()

    def stage(input_dir, work_dir):
        d = Path(work_dir) / "ezbids"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def run(staged, handler_dir=None, log=print, timeout_s=0):
        h.gate.wait(10)
        (Path(staged) / "ezBIDS_core.json").write_text(json.dumps(planted_core()))
        return Path(staged) / "ezBIDS_core.json"

    def write(plan, core, input_dir, terms, key, schema, out_dir, *, staged_dir, manifest=None, refused=None):
        h.gate.wait(10)
        if h.write_error:
            raise h.write_error
        key.date_offset_days("01")
        out = Path(out_dir)
        for e in plan.entries:
            if e.exclude or e.status != "ok" or not e.datatype:
                continue
            rel = f"sub-{e.subject}/ses-{e.session}/{e.datatype}/{e.id}.nii.gz"
            (out / rel).parent.mkdir(parents=True, exist_ok=True)
            (out / rel).write_bytes(b"original-" + e.id.encode())
            if manifest is not None:
                manifest.setdefault(e.id, []).append(rel)
        if refused is not None:
            refused.append("a/b.tsv: not written: no participant_id column")
        return []

    def fake_deface(bids_dir, plan, method, pre_deface_dir, manifest):
        done = {}
        for e in plan.entries:
            if e.deface:
                for rel in manifest.get(e.id, []):
                    saved = Path(pre_deface_dir) / rel
                    saved.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(Path(bids_dir) / rel), str(saved))
                    (Path(bids_dir) / rel).write_bytes(b"defaced-" + e.id.encode())
                    done.setdefault(e.id, []).append(saved)
        return done

    monkeypatch.setattr(server, "stage_input", stage)
    monkeypatch.setattr(server, "run_ezbids", run)
    monkeypatch.setattr(server, "write_bids", write)
    monkeypatch.setattr(server, "deface", fake_deface)
    monkeypatch.setattr(server, "validate_bids", lambda bids: h.validation)
    monkeypatch.setattr(server, "client_from_env", lambda: None)
    return h


@pytest.fixture
def apps():
    made = []
    yield made
    for app in made:
        app.state.server.close()


@pytest.fixture
def make_client(tmp_path, apps, hooks):
    shutil.copytree(FIXTURES / "ancillary", tmp_path / "in")

    def make(origins=(ORIGIN,), token=TOKEN, auth=True):
        app = create_app(tmp_path / "in", tmp_path / "work", tmp_path / "keys", TOKEN, list(origins), ["testserver"])
        apps.append(app)
        client = TestClient(app)
        if auth:
            client.headers["Authorization"] = f"Bearer {token}"
        return client

    return make


@pytest.fixture
def client(make_client):
    return make_client()


def wait_stage(c, stages, timeout=15):
    stages = {stages} if isinstance(stages, str) else set(stages)
    end = time.time() + timeout
    while time.time() < end:
        s = c.get("/status").json()
        if s["stage"] in stages:
            return s
        time.sleep(0.05)
    raise AssertionError(f"stage never reached {stages}: {s}")


@pytest.fixture
def planned(client):
    assert client.post("/scan", json=SCAN).status_code == 202
    wait_stage(client, "planned")
    return client


def first_id(c):
    return c.get("/plan").json()["entries"][0]["id"]


def entry(c, entry_id):
    return next(e for e in c.get("/plan").json()["entries"] if e["id"] == entry_id)


def executed(c, method="quickshear"):
    assert c.post("/approve", json={"deface_method": method}).status_code == 200
    assert c.post("/execute").status_code == 202
    return wait_stage(c, ["validated", "invalid", "failed"])


# --- auth, CORS ---

def test_requires_token(make_client):
    c = make_client(auth=False)
    assert c.get("/plan").status_code == 401
    assert c.get("/status").status_code == 401
    assert c.post("/scan", json=SCAN).status_code == 401
    assert c.get("/events").status_code == 401
    c.headers["Authorization"] = "Bearer wrong"
    assert c.get("/plan").status_code == 401
    c.headers["Authorization"] = TOKEN  # no scheme
    assert c.get("/plan").status_code == 401


def test_empty_token_refused(tmp_path):
    with pytest.raises(ValueError):
        create_app(tmp_path / "in", tmp_path / "work", tmp_path / "keys", "", [])


def test_private_network_preflight(client):
    r = client.options("/plan", headers={"Origin": ORIGIN, "Access-Control-Request-Method": "GET",
                                         "Access-Control-Request-Private-Network": "true"})
    assert r.status_code == 200
    assert r.headers["access-control-allow-private-network"] == "true"
    assert r.headers["access-control-allow-origin"] == ORIGIN


def test_other_origins_get_no_cors(client):
    r = client.options("/plan", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET",
                                         "Access-Control-Request-Private-Network": "true"})
    assert "access-control-allow-origin" not in r.headers
    assert "access-control-allow-private-network" not in r.headers
    r = client.get("/status", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in r.headers


def test_cors_on_actual_request(client):
    r = client.get("/status", headers={"Origin": ORIGIN})
    assert r.headers["access-control-allow-origin"] == ORIGIN


@pytest.mark.parametrize("keys,work,inp", [
    ("w/keys", "w", "in"),  # keys inside work (and so inside the output)
    ("keys", "keys/work", "in"),  # work inside keys
    ("keys", "w", "w/in"),  # input inside work
    ("keys", "w", "."),  # input contains work
    ("keys", "w", "keys/in"),  # input inside keys
    ("w", "w", "in"),
])
def test_refuses_overlapping_folders(tmp_path, keys, work, inp):
    with pytest.raises(ValueError):
        create_app(tmp_path / inp, tmp_path / work, tmp_path / keys, TOKEN, [])


# --- state machine ---

def test_idle_then_scan_then_planned(client):
    assert client.get("/status").json()["stage"] == "idle"
    assert client.get("/plan").status_code == 404
    assert client.post("/scan", json=SCAN).status_code == 202
    s = wait_stage(client, "planned")
    assert s["message"]
    plan = client.get("/plan").json()
    assert plan["entries"] and plan["target"] == "bids" and plan["approved"] is False


def test_scan_validates_body(client):
    assert client.post("/scan", json={"project_id": "../x"}).status_code == 422
    assert client.post("/scan", json={"project_id": "p", "target": "nope"}).status_code == 422
    assert client.post("/scan", json={}).status_code == 422


def test_scan_failure_message_is_generic(client, hooks, monkeypatch):
    def boom(staged, **kw):
        raise RuntimeError("could not read /in/Smith^John/MRN0042")

    monkeypatch.setattr(server, "run_ezbids", boom)
    client.post("/scan", json=SCAN)
    s = wait_stage(client, "failed")
    assert "RuntimeError" in s["message"] and not (PLANTED | NATIVE) & tokens(json.dumps(s))
    # the key is released: another import can start
    PseudonymKey.load(client.app.state.server.keys_dir, "proj").close()


def test_second_scan_while_busy_is_409(client, hooks):
    hooks.gate.clear()
    assert client.post("/scan", json=SCAN).status_code == 202
    assert client.post("/scan", json=SCAN).status_code == 409
    assert client.get("/status").json()["stage"] == "scanning"
    assert client.patch("/plan", json={"readme": "x"}).status_code == 409
    assert client.post("/execute").status_code == 409
    hooks.gate.set()
    wait_stage(client, "planned")


def test_scan_409_when_key_locked(client, tmp_path):
    other = PseudonymKey.load(tmp_path / "keys", "proj")
    try:
        r = client.post("/scan", json=SCAN)
        assert r.status_code == 409 and "key" in r.json()["detail"]
        assert client.get("/status").json()["stage"] == "idle"
    finally:
        other.close()


def test_scan_holds_key_until_execute_ends(planned, tmp_path):
    with pytest.raises(KeyLockedError):
        PseudonymKey.load(tmp_path / "keys", "proj")
    executed(planned)
    PseudonymKey.load(tmp_path / "keys", "proj").close()


def test_rescan_works_after_plan(planned):
    assert planned.post("/scan", json=SCAN).status_code == 202
    wait_stage(planned, "planned")


def test_execute_requires_approval(client):
    assert client.post("/execute").status_code == 409  # no plan at all


def test_execute_requires_approval_with_plan(planned):
    assert planned.post("/execute").status_code == 409
    assert planned.get("/status").json()["stage"] == "planned"


def test_approve_method_validated(planned):
    assert planned.post("/approve", json={"deface_method": "bogus"}).status_code == 422
    plan = planned.post("/approve", json={"deface_method": "quickshear"}).json()
    assert plan["approved"] is True and plan["deface_method"] == "quickshear"


# --- plan edits ---

def test_restart_keeps_edits(tmp_path, client, make_client):
    client.post("/scan", json=SCAN)
    wait_stage(client, "planned")
    eid = first_id(client)
    r = client.patch("/plan", json={"edits": [{"id": eid, "suffix": "T2w"}]})
    assert r.status_code == 200
    b = make_client()  # a new app over the same work_dir
    assert entry(b, eid)["suffix"] == "T2w"
    assert b.get("/status").json()["stage"] == "planned"


def test_patch_edits_unapprove_and_person_source(planned):
    planned.post("/approve", json={})
    eid = first_id(planned)
    plan = planned.patch("/plan", json={"edits": [{"id": eid, "exclude": True}]}).json()
    assert plan["approved"] is False
    assert next(e for e in plan["entries"] if e["id"] == eid)["source"] == "person"


def test_patch_bad_edits_are_422_and_change_nothing(planned):
    eid = first_id(planned)
    before = planned.get("/plan").json()
    assert planned.patch("/plan", json={"edits": [{"id": "nope", "suffix": "T2w"}]}).status_code == 422
    assert planned.patch("/plan", json={"edits": [{"id": eid, "subject_idx": 3}]}).status_code == 422
    assert planned.patch("/plan", json={"edits": [{"id": eid, "bogus": 1}]}).status_code == 422
    r = planned.patch("/plan", json={"edits": [{"id": eid, "suffix": "T2w"}],
                                     "ancillary_edits": [{"id": "nope", "action": "drop"}]})
    assert r.status_code == 422
    assert planned.patch("/plan", json={}).status_code == 422
    assert planned.patch("/plan", json={"surprise": 1}).status_code == 422
    assert planned.get("/plan").json() == before


def test_patch_dataset_fields(planned):
    planned.post("/approve", json={})
    plan = planned.patch("/plan", json={"dataset_name": " My study ", "readme": "About it",
                                        "dataset_description": {"License": "CC0", "Authors": ["A B"]}}).json()
    assert plan["dataset_name"] == "My study" and plan["readme"] == "About it"
    assert plan["dataset_description"]["License"] == "CC0"
    assert plan["metadata_source"] == "person" and plan["approved"] is False
    assert planned.patch("/plan", json={"dataset_description": {"Name": "x"}}).status_code == 422
    assert planned.patch("/plan", json={"dataset_name": " "}).status_code == 422
    assert planned.patch("/plan", json={"readme": "x" * 100000}).status_code == 422
    plan = planned.patch("/plan", json={"dataset_description": {"License": None}}).json()
    assert "License" not in plan["dataset_description"]


def test_patch_ancillary_edit(planned):
    ancillary = planned.get("/plan").json()["ancillary"]
    readme = next(a for a in ancillary if a["path"] == "README")
    plan = planned.patch("/plan", json={"ancillary_edits": [{"id": readme["id"], "content": "Hello"}]}).json()
    assert next(a for a in plan["ancillary"] if a["id"] == readme["id"])["action"] == "edit"
    src = next(a for a in ancillary if a["path"] == "sourcedata")
    assert planned.patch("/plan", json={"ancillary_edits": [{"id": src["id"], "action": "keep"}]}).status_code == 422


def test_no_edits_while_executing(planned, hooks):
    planned.post("/approve", json={})
    hooks.gate.clear()
    assert planned.post("/execute").status_code == 202
    assert planned.patch("/plan", json={"readme": "x"}).status_code == 409
    assert planned.post("/approve", json={}).status_code == 409
    assert planned.post("/execute").status_code == 409
    assert planned.post("/scan", json=SCAN).status_code == 409
    hooks.gate.set()
    wait_stage(planned, "validated")


# --- execute, status, preview ---

def test_execute_validates_and_reports(planned, tmp_path):
    s = executed(planned)
    assert s["stage"] == "validated"
    assert s["output_dir"] == str((tmp_path / "work" / "output" / "bids").resolve())
    assert s["validation"]["ok"] is True and s["validation"]["error_count"] == 0
    assert s["refused"] == ["a/b.tsv: not written: no participant_id column"]
    assert "warnings" in s


def test_execute_reports_validation_errors(planned, hooks):
    hooks.validation = ValidationResult(ok=False, errors=[{"code": "X", "message": "bad", "location": "/a"}],
                                        warnings=[{"code": "W", "message": "meh"}])
    s = executed(planned)
    assert s["stage"] == "invalid" and s["validation"]["ok"] is False
    assert s["validation"]["error_count"] == 1 and s["validation"]["errors"][0]["code"] == "X"
    assert s["validation"]["warning_count"] == 1
    assert [e["stage"] for e in sse(planned)] == ["invalid"]  # a terminal stage: the stream ends
    eid = next(e["id"] for e in planned.get("/plan").json()["entries"] if e["deface"] and e["status"] == "ok")
    assert planned.get(f"/preview/{eid}").status_code == 200  # the output can still be inspected
    planned.patch("/plan", json={"readme": "fix"})
    assert planned.get("/status").json()["stage"] == "planned"


def test_execute_failure_is_redacted(planned, hooks):
    hooks.write_error = RuntimeError("cannot read /in/Smith^John/MRN0042 born 1970-01-01 at Hospital X")
    s = executed(planned)
    assert s["stage"] == "failed" and s["message"].startswith("RuntimeError")
    assert not (PLANTED | NATIVE) & tokens(json.dumps(s))
    PseudonymKey.load(planned.app.state.server.keys_dir, "proj").close()  # released on failure


def test_execute_twice_replaces_own_output(planned):
    executed(planned)
    eid = first_id(planned)
    planned.patch("/plan", json={"readme": "again"})
    assert planned.get("/status").json()["stage"] == "planned"
    assert executed(planned)["stage"] == "validated"
    assert planned.get("/preview/" + eid, params={"which": "defaced"}).status_code in (200, 404)


def test_execute_refuses_foreign_output(planned, tmp_path):
    out = tmp_path / "work" / "output" / "bids"
    out.mkdir(parents=True)
    (out / "mine.txt").write_text("precious")
    planned.post("/approve", json={})
    assert planned.post("/execute").status_code == 409
    assert (out / "mine.txt").read_text() == "precious"
    assert planned.get("/status").json()["stage"] == "planned"


def test_execute_409_when_key_locked_after_restart(planned, make_client, tmp_path):
    planned.post("/approve", json={})
    b = make_client()  # restarted: no key held
    planned.app.state.server.release_key()
    other = PseudonymKey.load(tmp_path / "keys", "proj")
    try:
        r = b.post("/execute")
        assert r.status_code == 409 and "key" in r.json()["detail"]
    finally:
        other.close()
    assert b.post("/execute").status_code == 202  # the lock is free again: reacquired lazily
    wait_stage(b, "validated")


def test_preview(planned):
    eid = next(e["id"] for e in planned.get("/plan").json()["entries"] if e["deface"] and e["status"] == "ok"
               and not e["exclude"])
    other = next(e["id"] for e in planned.get("/plan").json()["entries"] if not e["deface"] and e["status"] == "ok"
                 and not e["exclude"])
    assert planned.get(f"/preview/{eid}").status_code == 404  # before execute
    executed(planned)
    assert planned.get(f"/preview/{eid}", params={"which": "original"}).content == b"original-" + eid.encode()
    assert planned.get(f"/preview/{eid}", params={"which": "defaced"}).content == b"defaced-" + eid.encode()
    assert planned.get(f"/preview/{eid}").content == b"defaced-" + eid.encode()
    # not defaced: both are the written file
    assert planned.get(f"/preview/{other}", params={"which": "original"}).content == b"original-" + other.encode()
    assert planned.get(f"/preview/{other}", params={"which": "defaced"}).content == b"original-" + other.encode()
    assert planned.get("/preview/nope").status_code == 404
    assert planned.get(f"/preview/{eid}", params={"which": "x"}).status_code == 422
    assert planned.get(f"/preview/{eid}", params={"index": 99}).status_code == 404


def test_preview_never_serves_outside_output(planned, tmp_path):
    executed(planned)
    state_path = tmp_path / "work" / "output-state.json"
    state = json.loads(state_path.read_text())
    eid = next(iter(state["manifest"]))
    state["manifest"][eid] = ["../../in/README"]
    state_path.write_text(json.dumps(state))
    assert planned.get(f"/preview/{eid}").status_code == 404


def test_restart_after_execute_keeps_output_and_preview(planned, make_client):
    executed(planned)
    eid = next(e["id"] for e in planned.get("/plan").json()["entries"] if e["deface"] and e["status"] == "ok"
               and not e["exclude"])
    b = make_client()
    assert b.get("/status").json()["stage"] == "validated"
    assert b.get(f"/preview/{eid}", params={"which": "original"}).status_code == 200


def test_interrupted_run_is_failed_after_restart(planned, make_client, tmp_path):
    (tmp_path / "work" / "status.json").write_text(json.dumps({"stage": "executing", "message": "x"}))
    b = make_client()
    s = b.get("/status").json()
    assert s["stage"] == "failed" and "restarted" in s["message"]


# --- events ---

def sse(c):
    out = []
    with c.stream("GET", "/events") as r:
        assert r.headers["content-type"].startswith("text/event-stream")
        for line in r.iter_lines():
            if line.startswith("data: "):
                out.append(json.loads(line[6:]))
    return out


def test_events_stream_ends_at_terminal_stage(client, hooks):
    hooks.gate.clear()
    client.post("/scan", json=SCAN)
    threading.Timer(0.5, hooks.gate.set).start()
    events = sse(client)
    assert events[0]["stage"] == "scanning" and events[-1]["stage"] == "planned"
    assert all(set(e) == {"stage", "message"} for e in events)
    assert [e["stage"] for e in sse(client)] == ["planned"]  # connecting when idle at a terminal stage: one line


# --- ancillary content ---

def test_ancillary_content_is_deidentified(planned):
    ancillary = {a["path"]: a for a in planned.get("/plan").json()["ancillary"]}
    r = planned.get("/ancillary/" + ancillary["participants.tsv"]["id"])
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"path", "kind", "content", "flags", "locked", "locked_columns"}
    assert body["path"] == "participants.tsv" and body["kind"] == "table" and body["locked"] is False
    assert isinstance(body["content"], str) and body["content"].startswith("participant_id")
    assert not (PLANTED | NATIVE) & tokens(json.dumps(body))
    assert "John Smith" not in body["content"] and "MRN0042" not in body["content"]
    r = planned.get("/ancillary/" + ancillary["CHANGES"]["id"]).json()
    assert isinstance(r["content"], str) and not (PLANTED | NATIVE) & tokens(r["content"])
    j = planned.get("/ancillary/" + ancillary["genetic_info.json"]["id"]).json()
    assert isinstance(j["content"], dict) and not (PLANTED | NATIVE) & tokens(json.dumps(j))


def test_ancillary_content_shows_reviewer_edits(planned):
    ancillary = {a["path"]: a for a in planned.get("/plan").json()["ancillary"]}
    rid, pid, jid = ancillary["CHANGES"]["id"], ancillary["participants.tsv"]["id"], ancillary["participants.json"]["id"]
    columns = ancillary["participants.tsv"]["columns"]
    col = next(c for c, act in columns.items() if act == "keep" and c != "participant_id"
               and c not in ancillary["participants.tsv"]["locked_columns"])
    assert col in planned.get("/ancillary/" + pid).json()["content"].split("\n")[0].split("\t")
    r = planned.patch("/plan", json={"ancillary_edits": [{"id": rid, "content": "edited by the reviewer"},
                                                         {"id": pid, "columns": {col: "drop"}},
                                                         {"id": jid, "action": "drop"}]})
    assert r.status_code == 200
    assert planned.get("/ancillary/" + rid).json()["content"] == "edited by the reviewer"
    assert col not in planned.get("/ancillary/" + pid).json()["content"].split("\n")[0].split("\t")
    assert planned.get("/ancillary/" + jid).json()["content"] is None  # dropped: nothing will be written
    readme = planned.get("/ancillary/" + ancillary["README"]["id"]).json()  # seeded into the plan README
    assert ancillary["README"]["action"] == "drop" and readme["content"] is None


def test_ancillary_preview_adds_no_offsets(planned):
    srv = planned.app.state.server
    subject = planned.get("/plan").json()["entries"][0]["subject"]
    srv.key.offsets.pop(subject, None)
    body = planned.get("/ancillary/" + ancillary_id(planned, "participants.tsv")).json()
    assert body["content"].startswith("participant_id")
    assert subject not in srv.key.offsets


def test_ancillary_never_returns_locked_or_sourcedata(planned):
    ancillary = {a["path"]: a for a in planned.get("/plan").json()["ancillary"]}
    for path in ("sourcedata", "derivatives", "code"):
        body = planned.get("/ancillary/" + ancillary[path]["id"]).json()
        assert body["content"] is None
        assert not (PLANTED | NATIVE) & tokens(json.dumps(body))
    assert planned.get("/ancillary/zzz").status_code == 404


# --- no identifying value in any JSON body ---

def test_no_identifiers_in_api(client, hooks):
    bodies = []

    def get(path):
        r = client.get(path)
        bodies.append(r.text)
        return r

    client.post("/scan", json=SCAN)
    bodies.append(json.dumps(wait_stage(client, "planned")))
    bodies.append(json.dumps(sse(client)))
    plan = get("/plan").json()
    assert plan["entries"]
    assert any(e["description"] for e in plan["entries"])
    for a in plan["ancillary"]:
        get("/ancillary/" + a["id"])
    bodies.append(client.patch("/plan", json={"edits": [{"id": first_id(client), "suffix": "T2w"}]}).text)
    bodies.append(client.patch("/plan", json={"edits": [{"id": "Smith^John", "suffix": "T2w"}]}).text)
    bodies.append(client.post("/approve", json={}).text)
    hooks.write_error = RuntimeError("Smith^John MRN0042 1970-01-01 Hospital X")
    assert client.post("/execute").status_code == 202
    bodies.append(json.dumps(wait_stage(client, "failed")))
    bodies.append(json.dumps(sse(client)))
    get("/status")
    text = "\n".join(bodies)
    assert not (PLANTED | NATIVE) & tokens(text), tokens(text)
    # the files in work_dir are no different
    work = Path(client.app.state.server.work)
    for name in ("plan.json", "status.json"):
        assert not (PLANTED | NATIVE) & tokens((work / name).read_text())


# --- Host header (DNS rebinding) ---

def host_client(tmp_path, apps, hosts):
    app = create_app(tmp_path / "in", tmp_path / "work", tmp_path / "keys", TOKEN, [ORIGIN], hosts)
    apps.append(app)
    return TestClient(app)


def test_host_header_allowlist(tmp_path, apps):
    c = host_client(tmp_path, apps, ["127.0.0.1:8765", "localhost:8765", "[::1]:8765"])
    for bad in ("evil.example:8765", "evil.example", "127.0.0.1:9999", "localhost", "127.0.0.1.evil.example:8765"):
        assert c.get("/status", headers={"Host": bad}).status_code == 421, bad
        assert c.get("/status", headers={"Host": bad, "Authorization": f"Bearer {TOKEN}"}).status_code == 421
    for good in ("localhost:8765", "127.0.0.1:8765", "[::1]:8765", "LOCALHOST:8765"):
        assert c.get("/status", headers={"Host": good}).status_code == 401  # reaches the token check
        assert c.get("/status", headers={"Host": good, "Authorization": f"Bearer {TOKEN}"}).status_code == 200
    # the check comes before CORS: a preflight for a bad host is refused too
    r = c.options("/plan", headers={"Host": "evil.example:8765", "Origin": ORIGIN,
                                    "Access-Control-Request-Method": "GET"})
    assert r.status_code == 421


def test_default_hosts_are_loopback_names(tmp_path, apps):
    c = host_client(tmp_path, apps, None)
    assert c.get("/status", headers={"Host": "evil.example:80"}).status_code == 421
    assert c.get("/status", headers={"Host": "localhost:1234"}).status_code == 401


# --- the key is released before the terminal status is visible ---

def test_key_released_before_terminal_status(planned, tmp_path, monkeypatch):
    srv = planned.app.state.server
    seen = []
    real = server.Server.set_status

    def spy(self, stage, message, **extra):
        if stage in ("validated", "failed"):
            try:  # a different file description: fails while this worker still holds the key
                PseudonymKey.load(tmp_path / "keys", "proj").close()
                seen.append((stage, "free"))
            except KeyLockedError:
                seen.append((stage, "held"))
        real(self, stage, message, **extra)

    monkeypatch.setattr(server.Server, "set_status", spy)
    executed(planned)
    assert seen == [("validated", "free")]
    assert srv.key is None


def test_failed_scan_releases_key_before_status(client, tmp_path, monkeypatch):
    seen = []
    real = server.Server.set_status

    def spy(self, stage, message, **extra):
        if stage == "failed":
            try:
                PseudonymKey.load(tmp_path / "keys", "proj").close()
                seen.append("free")
            except KeyLockedError:
                seen.append("held")
        real(self, stage, message, **extra)

    monkeypatch.setattr(server, "run_ezbids", lambda staged, **kw: (_ for _ in ()).throw(RuntimeError("x")))
    monkeypatch.setattr(server.Server, "set_status", spy)
    client.post("/scan", json=SCAN)
    wait_stage(client, "failed")
    assert seen == ["free"]


def test_new_run_right_after_terminal_status_has_its_own_key(planned):
    executed(planned)
    assert planned.post("/scan", json=SCAN).status_code == 202  # loads a fresh key at once
    wait_stage(planned, "planned")
    assert planned.app.state.server.key is not None
    executed(planned)
    assert planned.app.state.server.key is None


# --- events survive truncation ---

def test_events_stream_survives_truncation(client, monkeypatch):
    monkeypatch.setattr(server, "MAX_EVENTS", 5)
    srv = client.app.state.server
    srv.set_status("scanning", "start")

    def burst():
        for i in range(30):
            srv.set_status("scanning", f"m{i}")
        srv.set_status("planned", "done")

    threading.Timer(0.4, burst).start()
    events = sse(client)
    assert events[-1]["stage"] == "planned"


# --- ancillary preview uses the real offsets ---

def row(content, participant):
    header = content.split("\n")[0].split("\t")
    line = next(ln for ln in content.split("\n") if ln.startswith(participant + "\t"))
    return dict(zip(header, line.split("\t")))


def ancillary_id(c, path):
    return next(a["id"] for a in c.get("/plan").json()["ancillary"] if a["path"] == path)


def expected_date(c, key):
    from datetime import date, timedelta
    subject = c.get("/plan").json()["entries"][0]["subject"]
    return (date(2023, 1, 10) + timedelta(days=key.offsets[subject])).isoformat(), subject


def test_ancillary_dates_use_the_real_offsets(planned):
    srv = planned.app.state.server
    srv.key.date_offset_days(planned.get("/plan").json()["entries"][0]["subject"])
    body = planned.get("/ancillary/" + ancillary_id(planned, "participants.tsv")).json()
    want, subject = expected_date(planned, srv.key)
    assert row(body["content"], f"sub-{subject}")["visit_date"] == want


def test_ancillary_acquires_the_key_lazily_after_restart(planned, make_client):
    executed(planned)  # the key is released
    srv = planned.app.state.server
    assert srv.key is None
    body = planned.get("/ancillary/" + ancillary_id(planned, "participants.tsv")).json()
    assert srv.key is None  # loaded for the preview, then released
    with PseudonymKey.load(srv.keys_dir, "proj") as key:
        want, subject = expected_date(planned, key)
    assert row(body["content"], f"sub-{subject}")["visit_date"] == want


def test_ancillary_409_when_key_locked(planned, tmp_path):
    executed(planned)
    other = PseudonymKey.load(tmp_path / "keys", "proj")
    try:
        r = planned.get("/ancillary/" + ancillary_id(planned, "participants.tsv"))
        assert r.status_code == 409 and "key" in r.json()["detail"]
        # entries without dates need no key... but still go through the same path: also 409
    finally:
        other.close()


def test_ancillary_dates_masked_while_busy(planned, hooks):
    pid = ancillary_id(planned, "participants.tsv")
    planned.post("/approve", json={})
    hooks.gate.clear()
    assert planned.post("/execute").status_code == 202
    body = planned.get("/ancillary/" + pid).json()
    hooks.gate.set()
    wait_stage(planned, "validated")
    content = body["content"]
    assert row(content, "sub-" + planned.get("/plan").json()["entries"][0]["subject"])["visit_date"] \
        == server.SHIFTED_AT_WRITE
    assert "2023-01-10" not in content and "2023-02-14" not in content
    assert not (PLANTED | NATIVE) & tokens(json.dumps(body))


def test_reviewer_text_is_stored_redacted(planned):
    ancillary = planned.get("/plan").json()["ancillary"]
    readme = next(a for a in ancillary if a["path"] == "README")
    r = planned.patch("/plan", json={
        "readme": "Smith ran this at Hospital X.", "dataset_name": "Smith study",
        "dataset_description": {"Authors": ["John Smith"]},
        "ancillary_edits": [{"id": readme["id"], "content": "Notes from MRN0042"}]})
    assert r.status_code == 200
    for plan in (r.json(), planned.get("/plan").json()):
        assert plan["readme"].startswith("[x] ran this at [x]")
        assert "smith" not in plan["dataset_name"].lower()
        assert "smith" not in json.dumps(plan["dataset_description"]).lower()
        edited = next(a for a in plan["ancillary"] if a["id"] == readme["id"])
        assert edited["content"] == "Notes from [x]"
    assert "smith" not in (planned.app.state.server.work / "plan.json").read_text().lower()


# --- reviewer edits are re-derived (status, deface) ---

def test_edit_unknown_to_anat_is_written_and_defaced(planned, tmp_path):
    plan = planned.get("/plan").json()
    unknown = next(e for e in plan["entries"] if e["status"] == "unknown")
    dwi = next(e for e in plan["entries"] if e["datatype"] == "dwi" and e["status"] == "ok")
    r = planned.patch("/plan", json={"edits": [
        {"id": unknown["id"], "datatype": "anat", "suffix": "T1w", "entities": {}},
        {"id": dwi["id"], "datatype": "anat", "suffix": "T2w", "entities": {}}]})
    assert r.status_code == 200
    for eid in (unknown["id"], dwi["id"]):
        e = entry(planned, eid)
        assert (e["status"], e["exclude"], e["deface"]) == ("ok", False, True)
    assert executed(planned)["stage"] == "validated"
    for eid in (unknown["id"], dwi["id"]):
        assert planned.get(f"/preview/{eid}").content == b"defaced-" + eid.encode()
        assert planned.get(f"/preview/{eid}", params={"which": "original"}).content == b"original-" + eid.encode()


def test_edit_status_and_bad_types_are_422(planned):
    eid = first_id(planned)
    before = planned.get("/plan").json()
    for edit in ({"status": "ok"}, {"deface": "no"}, {"entities": {"task": 3}}, {"source": "person"}):
        assert planned.patch("/plan", json={"edits": [{"id": eid, **edit}]}).status_code == 422, edit
    assert planned.get("/plan").json() == before


# --- a failed execute leaves no uploadable output ---

def test_failed_deface_moves_output_aside(planned, tmp_path, monkeypatch):
    def broken_deface(bids_dir, plan, method, pre_deface_dir, manifest):
        raise RuntimeError("defacing crashed")

    fake = server.deface
    monkeypatch.setattr(server, "deface", broken_deface)
    work = tmp_path / "work"
    (work / "output" / "bids.failed").mkdir(parents=True)
    (work / "output" / "bids.failed" / "old.txt").write_text("from an earlier failure")
    s = executed(planned)
    assert s["stage"] == "failed" and "bids.failed" in s["message"]
    assert not (work / "output" / "bids").exists()
    failed = work / "output" / "bids.failed"
    assert any(failed.rglob("*.nii.gz")) and not (failed / "old.txt").exists()  # replaced
    state = json.loads((work / "output-state.json").read_text())
    assert state["complete"] is False and state["failed_output"] == str(failed.resolve())
    monkeypatch.setattr(server, "deface", fake)  # the next execute starts clean
    assert executed(planned)["stage"] == "validated" and (work / "output" / "bids").is_dir()
    assert not failed.exists()


# --- a failed re-scan leaves nothing executable ---

def test_failed_rescan_drops_the_old_plan(planned, tmp_path, monkeypatch):
    old = (tmp_path / "work" / "plan.json").read_text()
    assert planned.post("/approve", json={}).status_code == 200
    monkeypatch.setattr(server, "run_ezbids", lambda staged, **kw: (_ for _ in ()).throw(RuntimeError("x")))
    planned.post("/scan", json=SCAN)
    wait_stage(planned, "failed")
    assert planned.get("/plan").status_code == 404
    assert planned.post("/execute").status_code == 409
    # an approved plan from an earlier scan put back in place is refused too
    data = json.loads(old)
    data["approved"] = True
    (tmp_path / "work" / "plan.json").write_text(json.dumps(data))
    r = planned.post("/execute")
    assert r.status_code == 409 and "scan" in r.json()["detail"]


def test_plan_records_its_scan(planned, tmp_path):
    scan_id = json.loads((tmp_path / "work" / "scan.json").read_text())["scan_id"]
    assert planned.get("/plan").json()["scan_id"] == scan_id


def test_scan_takes_existing_sessions(client):
    assert client.post("/scan", json={**SCAN, "existing_sessions": {"01": ["1", "2"]}}).status_code == 202
    wait_stage(client, "planned")
    plan = client.get("/plan").json()
    assert {e["subject"] for e in plan["entries"]} == {"01"} and {e["session"] for e in plan["entries"]} == {"3"}
    assert client.post("/scan", json={**SCAN, "existing_sessions": {"01": [3]}}).status_code == 422


# --- subject ID edits and the key ---

def subject_ids(c):
    return {e["subject"] for e in c.get("/plan").json()["entries"]}


def test_subject_edit_is_recorded_in_the_key_on_execute(planned, tmp_path):
    srv = planned.app.state.server
    entries = planned.get("/plan").json()["entries"]
    assert subject_ids(planned) == {"01"}
    offset = srv.key.date_offset_days("01")
    r = planned.patch("/plan", json={"edits": [{"id": entries[0]["id"], "subject": "ctl07"}]})
    assert r.status_code == 200 and subject_ids(planned) == {"ctl07"}  # every entry of the subject
    assert "ctl07" not in srv.key.subjects.values()  # not before execute
    assert executed(planned)["stage"] == "validated"
    with PseudonymKey.load(tmp_path / "keys", "proj") as key:
        assert key.subjects == {"id=MRN0042|name=Smith^John|dob=19700101": "ctl07"}
        assert key.offsets["ctl07"] == offset and "ctl07" in key.sessions
    ids_file = tmp_path / "work" / "subject-ids.json"
    assert json.loads(ids_file.read_text()) == {"0": "ctl07"}
    assert not (PLANTED | NATIVE) & tokens(ids_file.read_text())
    # a re-import of the same person gets the edited ID
    assert planned.post("/scan", json=SCAN).status_code == 202
    wait_stage(planned, "planned")
    assert subject_ids(planned) == {"ctl07"}


def test_subject_edit_refuses_ids_of_others(client, tmp_path):
    with PseudonymKey.load(tmp_path / "keys", "proj") as key:
        key.subject_id("id=SOMEONE-ELSE", set(), "07")
        key.save()
    client.post("/scan", json={**SCAN, "existing_subjects": ["ctl01"]})
    wait_stage(client, "planned")
    entries = client.get("/plan").json()["entries"]
    before = client.get("/plan").json()
    for sid in ("07", "ctl01"):
        r = client.patch("/plan", json={"edits": [{"id": entries[0]["id"], "subject": sid}]})
        assert r.status_code == 422 and "already" in r.json()["detail"], sid
    r = client.patch("/plan", json={"edits": [{"id": entries[0]["id"], "subject": "a1"},
                                              {"id": entries[1]["id"], "subject": "a2"}]})
    assert r.status_code == 422
    assert client.get("/plan").json() == before
    # its own recorded ID is fine
    assert client.patch("/plan", json={"edits": [{"id": entries[0]["id"], "subject": "01"}]}).status_code == 200


def test_subject_edit_after_execute_releases_the_key(planned, tmp_path):
    executed(planned)
    eid = first_id(planned)
    assert planned.patch("/plan", json={"edits": [{"id": eid, "subject": "x9"}]}).status_code == 200
    assert planned.app.state.server.key is None
    PseudonymKey.load(tmp_path / "keys", "proj").close()  # free


def test_scan_failure_names_the_ezbids_log(client, tmp_path, monkeypatch):
    def noisy(staged, log=print, **kw):
        log("dcm2niix: converting /in/Smith^John/MRN0042")
        raise RuntimeError("preprocess.sh failed: /in/Smith^John")

    monkeypatch.setattr(server, "run_ezbids", noisy)
    client.post("/scan", json=SCAN)
    s = wait_stage(client, "failed")
    log_path = tmp_path / "work" / "ezbids.log"
    assert str(log_path.resolve()) in s["message"]
    assert "converting /in/Smith^John/MRN0042" in log_path.read_text()
    assert not (PLANTED | NATIVE) & tokens(json.dumps(s))
