"""Bad channels marked in the QA trace viewer: POST /qa/channels/<entry id> writes status/status_description
into the written channels.tsv (CSRF-checked for the viewer cookie), re-runs the gate and the validator, and the
marks survive a re-execute."""
from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

pytest.importorskip("mne")
pytest.importorskip("mne_bids")
pytest.importorskip("matplotlib")

from fastapi.testclient import TestClient  # noqa: E402

from aimport import server  # noqa: E402
from aimport.ephys import bad_channels as bc  # noqa: E402
from aimport.ephys import qa  # noqa: E402
from aimport.validate import ValidationResult  # noqa: E402
from conftest import ephys_tokens  # noqa: E402
from fixtures import ephys_fixtures as fx  # noqa: E402
from test_ephys_qa import _run  # noqa: E402
from test_viewer_routes import viewer_client  # noqa: E402

OWN = {"X-Aimport-Viewer": "1", "Origin": "http://testserver"}  # the TestClient's base URL is http://testserver


# --- the reason and the table, on their own ----------------------------------------------------------------


def test_clean_reason():
    assert bc.clean_reason("  flat\tline\n\x00now\u200b ", set()) == "flat line now"
    assert bc.clean_reason("", set()) is None and bc.clean_reason(" \t", set()) is None
    assert bc.clean_reason("n/a", set()) is None and bc.clean_reason(None, set()) is None
    assert bc.clean_reason("x" * 80, set()) == "x" * 80
    with pytest.raises(bc.MarkError, match="at most 80"):
        bc.clean_reason("x" * 81, set())
    for text in ("noisy near Smith", "SMITH", "jane_doe noisy", "janedoe"):
        with pytest.raises(bc.MarkError) as e:
            bc.clean_reason(text, {"smith", "jane doe"})
        assert "smith" not in str(e.value).lower() and "jane" not in str(e.value).lower()


def test_render_adds_status_description_and_describes_it(tmp_path):
    tsv = tmp_path / "sub-01_task-rest_channels.tsv"
    tsv.write_text("name\ttype\tunits\tstatus\nA1\tSEEG\tV\tgood\nA2\tSEEG\tV\tgood\nA3\tSEEG\tV\tbad\n")
    (tmp_path / "sub-01_task-rest_channels.json").write_text(json.dumps({"name": {"Description": "x"}}))
    bad = bc.apply(tsv, {"A1": {"status": "bad", "description": "flat"}, "A3": {"status": "good",
                                                                              "description": None},
                         "ZZ": {"status": "bad", "description": None}})
    assert bad == 1
    assert tsv.read_text() == ("name\ttype\tunits\tstatus\tstatus_description\nA1\tSEEG\tV\tbad\tflat\n"
                               "A2\tSEEG\tV\tgood\tn/a\nA3\tSEEG\tV\tgood\tn/a\n")
    side = json.loads((tmp_path / "sub-01_task-rest_channels.json").read_text())
    assert set(side) == {"name", "status", "status_description"}
    assert not list(tmp_path.glob(".*.tmp"))
    assert bc.table(tsv)[0] == {"name": "A1", "type": "SEEG", "status": "bad", "description": "flat"}


def test_check_marks(tmp_path):
    tsv = tmp_path / "x_channels.tsv"
    tsv.write_text("name\ttype\tunits\tstatus\tstatus_description\nFp1\tEEG\tV\tgood\tn/a\n")
    assert bc.check_marks(tsv, [{"name": "Fp1", "status": "good", "description": "flat"}], set()) == {
        "Fp1": {"status": "good", "description": None}}
    for marks, text in (([{"name": "Smith-Fp1", "status": "bad"}], "unknown channel"),
                        ([{"name": "Fp1", "status": "bad"}] * 2, "twice"),
                        ([{"name": "Fp1", "status": "maybe"}], "good or bad")):
        with pytest.raises(bc.MarkError, match=text) as e:
            bc.check_marks(tsv, marks, {"smith"})
        assert "smith" not in str(e.value).lower()


# --- the route ---------------------------------------------------------------------------------------------


def _eeg(c: TestClient, s: dict) -> tuple[str, Path]:
    """(entry id, written channels.tsv) of the planted EDF (written as BrainVision)."""
    eid = next(e for e, files in s["manifest"].items() if files[qa.primary_file(files)].endswith(".vhdr"))
    rel = bc.tsv_of(s["manifest"][eid])
    return eid, Path(s["output_dir"]) / rel


def _wait(c: TestClient, stages=("validated", "invalid", "failed", "planned")) -> dict:
    end = time.time() + 120
    while (s := c.get("/status").json())["stage"] not in stages and time.time() < end:
        time.sleep(0.05)
    return s


def test_csrf_and_auth(tmp_path, monkeypatch):
    app, c, s = _run(tmp_path, monkeypatch, fx.planted_edf)
    try:
        assert s["stage"] == "validated", s
        eid, tsv = _eeg(c, s)
        url = f"/qa/channels/{eid}"
        body = {"channels": [{"name": "Fp1", "status": "bad", "description": "flat"}]}
        before = tsv.read_bytes()
        browser = viewer_client(c)
        # the cookie alone, a wrong or missing Origin, a missing header: refused, nothing written
        for headers in ({}, {"X-Aimport-Viewer": "1"}, {"Origin": "http://testserver"},
                        {"X-Aimport-Viewer": "1", "Origin": "http://evil.example"},
                        {"X-Aimport-Viewer": "1", "Origin": "null"},
                        {"X-Aimport-Viewer": "0", "Origin": "http://testserver"},
                        {"X-Aimport-Viewer": "1", "Origin": "http://testserver.evil.example"}):
            r = browser.post(url, json=body, headers=headers)
            assert r.status_code == 403, (headers, r.text)
        assert tsv.read_bytes() == before
        # no cookie, no token
        assert TestClient(app).post(url, json=body, headers=OWN).status_code == 401
        # the cookie is still refused on every other write route (and on other methods of /qa, /viewer)
        assert browser.patch("/plan", json={"readme": "x"}, headers=OWN).status_code == 401
        assert browser.post("/approve", json={}, headers=OWN).status_code == 401
        assert browser.post("/execute", headers=OWN).status_code == 401
        assert browser.post("/scan", json={"project_id": "p"}, headers=OWN).status_code == 401
        assert browser.post("/viewer/session", headers=OWN).status_code == 401
        # no route (405, 404 come before the token check): never written either
        assert browser.post(f"/qa/traces/{eid}", headers=OWN).status_code == 405
        assert browser.put(url, json=body, headers=OWN).status_code == 405
        assert browser.post(url + "/x", json=body, headers=OWN).status_code == 404
        # reads with the cookie still work
        assert browser.get(f"/qa/channels/{eid}").status_code == 200
        assert browser.get(f"/qa/traces/{eid}").status_code == 200
        # content type and size
        r = browser.post(url, content=json.dumps(body), headers={**OWN, "Content-Type": "text/plain"})
        assert r.status_code == 415
        big = {"channels": [{"name": "Fp1", "status": "bad", "description": "x" * 70}] * 4000}
        assert len(json.dumps(big)) > 256 * 1024
        assert browser.post(url, json=big, headers=OWN).status_code == 413
        assert browser.post(url, content=b"{", headers={**OWN, "Content-Type": "application/json"}).status_code == 400
        assert tsv.read_bytes() == before
        # the viewer page's own request, then the bearer token (no CSRF headers needed)
        r = browser.post(url, json=body, headers=OWN)
        assert r.status_code == 200, r.text
        assert r.json()["bad"] == 1 and r.json()["stage"] == "validated"
        r = c.post(url, json={"channels": [{"name": "Fp1", "status": "good"}]})
        assert r.status_code == 200 and r.json()["bad"] == 0
    finally:
        app.state.server.close()


def test_before_execute_404(tmp_path):
    app = server.create_app(tmp_path / "in", tmp_path / "work", tmp_path / "keys", "t" * 32, [], ["testserver"])
    (tmp_path / "in").mkdir()
    c = TestClient(app)
    c.headers["Authorization"] = "Bearer " + "t" * 32
    try:
        r = c.post("/qa/channels/e1", json={"channels": [{"name": "Fp1", "status": "bad"}]})
        assert r.status_code == 404
        assert c.get("/qa/channels/e1").status_code == 404
    finally:
        app.state.server.close()


def test_marks_written_gated_validated_and_kept(tmp_path, monkeypatch):
    validations: list[Path] = []
    renders: list[str] = []

    def validator(bids):
        validations.append(Path(bids))
        return ValidationResult(ok=True, validator_version="2.4.1", bids_version="1.11.2")

    real_render = qa.render

    def render(entry_id, bids_path, out_dir, **kw):
        renders.append(entry_id)
        return real_render(entry_id, bids_path, out_dir, **kw)

    app, c, s = _run(tmp_path, monkeypatch, fx.planted_edf, render=render)
    monkeypatch.setattr(server, "validate_bids", validator)
    try:
        assert s["stage"] == "validated", s
        eid, tsv = _eeg(c, s)
        url = f"/qa/channels/{eid}"
        rows = c.get(url).json()
        names = [r["name"] for r in rows["channels"]]
        assert names[0] == "Fp1" and len(names) == 3 and all(r["status"] == "good" for r in rows["channels"])
        assert rows["max_reason"] == 80 and rows["reasons"] == ["flat", "noisy", "bridged", "disconnected"]
        assert not ephys_tokens(json.dumps(rows))
        before = tsv.read_bytes()
        png = tmp_path / "work" / "ephys" / "qa" / eid / "channels.png"
        png_before = png.read_bytes()

        # refusals: nothing written, the stage unchanged, no input echoed
        for marks, code in (([{"name": "Smith-Fp1", "status": "bad"}], 400),
                            ([{"name": "Fp1", "status": "bad", "description": "noisy since Smith left"}], 400),
                            ([{"name": "Fp1", "status": "bad", "description": "John_Smith"}], 400),
                            ([{"name": "Fp1", "status": "bad", "description": "x" * 81}], 400),
                            ([{"name": "Fp1", "status": "bad", "description": "noisy since 1999-03-04"}], 400),
                            ([{"name": "Fp1", "status": "maybe"}], 400),
                            ([{"name": "Fp1", "status": "bad", "extra": 1}], 400),
                            ([{"name": "Fp1", "status": "bad"}, {"name": "Fp1", "status": "good"}], 400)):
            r = c.post(url, json={"channels": marks})
            assert r.status_code == code, (marks, r.text)
            assert not ephys_tokens(r.text) and "1999" not in r.text and "Smith" not in r.text
        assert tsv.read_bytes() == before
        assert c.get("/status").json()["stage"] == "validated"
        assert not validations
        assert not (tmp_path / "work" / "ephys" / bc.MARKS_FILE).exists()

        # two channels marked bad
        marks = [{"name": names[0], "status": "bad", "description": "flat\tline"},
                 {"name": names[1], "status": "bad", "description": "noisy"}]
        r = c.post(url, json={"channels": marks})
        assert r.status_code == 200, r.text
        out = r.json()
        assert out["bad"] == 2 and out["stage"] == "validated" and out["validation"] == {"ok": True, "error_count": 0}
        lines = [line.split("\t") for line in tsv.read_text().splitlines()]
        col = {k: i for i, k in enumerate(lines[0])}
        got = {row[col["name"]]: (row[col["status"]], row[col["status_description"]]) for row in lines[1:]}
        assert got == {names[0]: ("bad", "flat line"), names[1]: ("bad", "noisy"), names[2]: ("good", "n/a")}
        assert not ephys_tokens(tsv.read_text())
        # the validator ran again on the output, the gate passed, the snapshots were rendered again
        assert validations == [Path(s["output_dir"])]
        status = c.get("/status").json()
        assert status["stage"] == "validated" and status["output_dir"] == s["output_dir"]
        assert status["manifest"] == s["manifest"] and status["validation"]["ok"]
        assert renders.count(eid) == 2 and png.read_bytes() != png_before
        # the trace window shows them bad (the cache was dropped)
        w = c.get(f"/qa/traces/{eid}").json()
        assert [ch["bad"] for ch in w["channels"]] == [True, True, False]
        # the plan: a count only
        plan = c.get("/plan").json()
        entry = next(e for e in plan["entries"] if e["id"] == eid)
        assert entry["bad_channels"] == 2 and entry["description"].endswith("· 2 bad channels")
        assert "flat" not in json.dumps(plan) and "noisy" not in json.dumps(plan)
        saved = json.loads((tmp_path / "work" / "ephys" / bc.MARKS_FILE).read_text())
        assert saved["entries"][eid]["bad"] == 2

        # an invalid dataset after a mark: the stage follows the validator
        monkeypatch.setattr(server, "validate_bids", lambda bids: ValidationResult(
            ok=False, errors=[{"code": "X"}], validator_version="2.4.1", bids_version="1.11.2"))
        r = c.post(url, json={"channels": [{"name": names[2], "status": "bad", "description": "bridged"}]})
        assert r.status_code == 200 and r.json()["stage"] == "invalid" and r.json()["bad"] == 3
        assert c.get("/status").json()["stage"] == "invalid"
        assert c.get(url).status_code == 200  # still after execute
        r = c.post(url, json={"channels": [{"name": names[2], "status": "good"}]})
        assert r.status_code == 200 and r.json()["bad"] == 2
        monkeypatch.setattr(server, "validate_bids", validator)

        # a plan edit and a re-execute (a new task label: new file names) keep the marks
        edits = [{"id": eid, "entities": {**entry["entities"], "task": "eyes"}}]
        assert c.patch("/plan", json={"edits": edits}).status_code == 200
        assert c.post("/approve", json={}).status_code == 200
        assert c.post("/execute").status_code == 202
        s2 = _wait(c, ("validated", "invalid", "failed"))
        assert s2["stage"] == "validated", s2
        tsv2 = Path(s2["output_dir"]) / bc.tsv_of(s2["manifest"][eid])
        assert "task-eyes" in tsv2.name and not tsv.exists()
        assert [(r["name"], r["status"], r["description"]) for r in c.get(url).json()["channels"]] == [
            (names[0], "bad", "flat line"), (names[1], "bad", "noisy"), (names[2], "good", None)]
        assert c.get("/plan").json()["entries"][0]["bad_channels"] == 2

        # a new scan clears them
        assert c.post("/scan", json={"project_id": "proj"}).status_code == 202
        assert _wait(c, ("planned", "failed"))["stage"] == "planned"
        assert not (tmp_path / "work" / "ephys" / bc.MARKS_FILE).exists()
        assert all(e.get("bad_channels", 0) == 0 for e in c.get("/plan").json()["entries"])
    finally:
        app.state.server.close()


def test_nwb_table_gets_status_description(tmp_path, monkeypatch):
    """The NWB writer's channels.tsv has no status_description column: the mark adds it."""
    app, c, s = _run(tmp_path, monkeypatch, fx.planted_nwb)
    try:
        assert s["stage"] == "validated", s
        eid = next(iter(s["manifest"]))
        tsv = Path(s["output_dir"]) / bc.tsv_of(s["manifest"][eid])
        assert "status_description" not in tsv.read_text().splitlines()[0]
        name = c.get(f"/qa/channels/{eid}").json()["channels"][0]["name"]
        r = c.post(f"/qa/channels/{eid}", json={"channels": [{"name": name, "status": "bad",
                                                              "description": "disconnected"}]})
        assert r.status_code == 200, r.text
        header, first = tsv.read_text().splitlines()[:2]
        assert header.split("\t")[-2:] == ["status", "status_description"]
        assert first.split("\t")[-2:] == ["bad", "disconnected"]
    finally:
        app.state.server.close()


@pytest.mark.docker
def test_marks_pass_the_bids_validator(tmp_path, monkeypatch):
    """In the image: the real BIDS validator on BrainVision and NWB output after two channels are marked bad."""
    def planted(dest: Path) -> None:
        fx.planted_edf(dest / "a")
        fx.planted_nwb(dest / "c")

    app, c, s = _run(tmp_path, monkeypatch, planted, fake_validator=False)
    try:
        assert s["stage"] == "validated", s
        for eid in s["manifest"]:
            rows = c.get(f"/qa/channels/{eid}").json()["channels"]
            marks = [{"name": rows[0]["name"], "status": "bad", "description": "flat"},
                     {"name": rows[1]["name"], "status": "bad", "description": None}]
            r = c.post(f"/qa/channels/{eid}", json={"channels": marks})
            assert r.status_code == 200, r.text
            assert r.json()["stage"] == "validated", c.get("/status").json().get("validation")
            assert r.json()["bad"] == 2
    finally:
        app.state.server.close()
