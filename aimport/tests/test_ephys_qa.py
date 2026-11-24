"""Phase 3 Task 11: QA snapshots (PNGs) and trace windows of the written electrophysiology output."""
from __future__ import annotations

import json
import re
import struct
import time
from pathlib import Path

import numpy as np
import pytest

mne = pytest.importorskip("mne")
pytest.importorskip("mne_bids")
pytest.importorskip("matplotlib")

from aimport import server  # noqa: E402
from aimport.ephys import events, qa  # noqa: E402
from aimport.pseudonyms import PseudonymKey  # noqa: E402
from aimport.schema import load_schema  # noqa: E402
from conftest import ephys_tokens  # noqa: E402
from fixtures import ephys_fixtures as fx  # noqa: E402
from test_ephys_write import ephys, plan_and_write  # noqa: E402

CODE = re.compile(rf"^{events.CODE_PREFIX}\d{{3}}$")


@pytest.fixture(scope="module")
def written(tmp_path_factory):
    """The planted EDF (written as BrainVision), SNIRF and NWB, written once for the module, with snapshots."""
    tmp = tmp_path_factory.mktemp("qa")
    fx.planted_edf(tmp / "in" / "a")
    fx.planted_snirf(tmp / "in" / "b")
    fx.planted_nwb(tmp / "in" / "c")
    key = PseudonymKey.load(tmp / "keys", "proj")
    try:
        plan, out, manifest = plan_and_write(tmp / "in", tmp, key, load_schema())
    finally:
        key.close()
    files = {}
    for e in ephys(plan):
        rel = manifest[e.id][qa.primary_file(manifest[e.id])]
        files[Path(rel).suffix] = (e.id, out / rel, tmp / "qa" / e.id)
    assert set(files) == {".vhdr", ".snirf", ".nwb"}, files
    return plan, files


def _png_text_chunks(data: bytes) -> dict[str, bytes]:
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    pos, out = 8, {}
    while pos < len(data):
        (n,) = struct.unpack(">I", data[pos:pos + 4])
        kind = data[pos + 4:pos + 8]
        body = data[pos + 8:pos + 8 + n]
        if kind in (b"tEXt", b"iTXt", b"zTXt"):
            k, _, v = body.partition(b"\0")
            out[k.decode("latin-1")] = v
        pos += 12 + n
    return out


def test_primary_file():
    assert qa.primary_file(["a_channels.tsv", "a_eeg.vhdr", "a_eeg.eeg", "a_eeg.vmrk"]) == 1
    assert qa.primary_file(["x_coordsystem.json", "x_task-rest_nirs.snirf"]) == 1
    assert qa.primary_file(["m_task-a_split-02_meg.fif", "m_task-a_split-01_meg.fif", "m_channels.tsv"]) == 1
    assert qa.primary_file(["s_ieeg.json", "s_ieeg.nwb"]) == 1
    assert qa.primary_file(["e_eeg.edf"]) == 0 and qa.primary_file(["e_emg.bdf"]) == 0
    with pytest.raises(ValueError):
        qa.primary_file(["sub-01_T1w.nii.gz", "sub-01_T1w.json"])


def test_png_titles_bids_only(written, monkeypatch):
    from matplotlib.figure import Figure

    titles: list[str] = []
    real = Figure.suptitle

    def spy(self, t, *a, **k):
        titles.append(t)
        return real(self, t, *a, **k)

    monkeypatch.setattr(Figure, "suptitle", spy)
    _, files = written
    for eid, path, qa_dir in files.values():
        titles.clear()
        got = qa.render(eid, path, qa_dir)
        assert set(got) == set(qa.KINDS)
        assert titles == [path.name] * 3  # the BIDS basename, nothing else
        assert not ephys_tokens(" ".join(titles))
        for kind, png in got.items():
            assert Path(png) == qa_dir / f"{kind}.png"
            data = Path(png).read_bytes()
            assert "Software" not in _png_text_chunks(data)
            assert not ephys_tokens(data.decode("latin-1"))
    nirs_dir = files[".snirf"][2]
    assert (nirs_dir / qa.HB_FILE).is_file() and (nirs_dir / qa.HB_INFO).is_file()


def _fif(path: Path, data: np.ndarray, sfreq: float, types="eeg") -> Path:
    names = [f"ch{i}" for i in range(data.shape[0])]
    raw = mne.io.RawArray(data, mne.create_info(names, sfreq, types), verbose="error")
    raw.save(path, fmt="single", verbose="error")
    return path


def test_traces_limits(tmp_path):
    qa.clear_cache()
    hour = _fif(tmp_path / "hour_raw.fif", np.zeros((2, 3600 * 1000), dtype=np.float32), 1000.0)
    with pytest.raises(qa.WindowError):
        qa.window("e", hour, 0, 10, list(range(65)))
    with pytest.raises(qa.WindowError):
        qa.window("e", hour, 0, 601, [0])
    with pytest.raises(qa.WindowError):
        qa.window("e", hour, 5, 5, [0])
    with pytest.raises(qa.WindowError):
        qa.window("e", hour, 0, 10, [2])  # out of range
    w = qa.window("e", hour, 0, 600, [0, 1])
    assert len(w["x"]) <= qa.MAX_POINTS and all(len(row) == len(w["x"]) for row in w["y"])
    assert w["x"] == sorted(w["x"]) and w["x"][-1] <= 600
    w = qa.window("e", hour, 100, 103, None)  # few samples: every one
    assert len(w["x"]) == 3000 and [c["i"] for c in w["channels"]] == [0, 1]
    assert w["channels"][0]["unit"] == "µV" and w["duration"] == 3600


def test_traces_min_max_keeps_peaks(tmp_path):
    qa.clear_cache()
    data = np.zeros((1, 200_000))
    data[0, 123_457] = 1e-3  # one sample, 1000 µV
    data[0, 77_001] = -2.5e-4
    path = _fif(tmp_path / "spike_raw.fif", data, 1000.0)
    w = qa.window("e", path, 0, 200, [0])
    assert len(w["x"]) == qa.MAX_POINTS
    assert max(w["y"][0]) == 1000.0 and min(w["y"][0]) == -250.0
    i = w["y"][0].index(1000.0)
    assert abs(w["x"][i] - 123.457) < 200 / (qa.MAX_POINTS // 2)


def test_round_sig():
    got = qa.round_sig(np.array([123456.0, 0.000123456, -98.7654, 0.0, np.nan, 1.0]))
    assert got[:4].tolist() == [123500.0, 0.0001235, -98.77, 0.0] and np.isnan(got[4]) and got[5] == 1.0


def test_traces_no_identifiers(written):
    plan, files = written
    for eid, path, qa_dir in files.values():
        w = qa.window(eid, path, 0, 10, None, qa_dir=qa_dir)
        text = json.dumps(w, ensure_ascii=False)
        assert not ephys_tokens(text), (path.name, ephys_tokens(text))
        for e in w["events"]:
            assert (CODE.match(e["label"]) and e["label"] in plan.event_names) or events.is_safe(e["label"]), e
    eeg = qa.window(*files[".vhdr"][:2], 0, 10, None)
    names = [c["name"] for c in eeg["all_channels"]]
    assert "eeg_002" in names and not any("smith" in n.lower() for n in names)
    assert any(CODE.match(e["label"]) for e in eeg["events"])  # "Smith John said hello", coded
    nwb = qa.window(*files[".nwb"][:2], 0, 1, None)
    assert {c["type"] for c in nwb["channels"]} <= {"seeg", "ecog", "dbs"} and nwb["channels"][0]["unit"] == "µV"


def test_traces_nirs_pairs(written, tmp_path, monkeypatch):
    _, files = written
    eid, path, qa_dir = files[".snirf"]
    qa.render(eid, path, qa_dir)
    w = qa.window(eid, path, 0, 10, None, qa_dir=qa_dir)
    by_i = {c["i"]: c for c in w["channels"]}
    assert {c["type"] for c in w["channels"]} == {"hbo", "hbr"} and {c["unit"] for c in w["channels"]} == {"µM"}
    assert len(w["pairs"]) == 4
    for hbo, hbr in w["pairs"]:
        assert by_i[hbo]["type"] == "hbo" and by_i[hbr]["type"] == "hbr"
        assert by_i[hbo]["name"].split()[0] == by_i[hbr]["name"].split()[0]
    # only the picked channels' pairs
    one = qa.window(eid, path, 0, 10, [w["pairs"][0][0], w["pairs"][0][1], w["pairs"][1][0]], qa_dir=qa_dir)
    assert one["pairs"] == [w["pairs"][0]]
    # too large for HbO/HbR: the raw wavelengths, paired 760/850
    monkeypatch.setattr(qa, "HB_MAX_BYTES", 10)
    big = tmp_path / "qa"
    qa.render(eid, path, big)
    assert not (big / qa.HB_FILE).exists()
    raw = qa.window(eid, path, 0, 10, None, qa_dir=big)
    names = {c["i"]: c["name"] for c in raw["channels"]}
    assert len(raw["pairs"]) == 4
    assert all(names[a].endswith(" 760") and names[b].endswith(" 850") for a, b in raw["pairs"])


# --- the engine: snapshots after execute, routes ------------------------------------------------------------


def _run(tmp_path, monkeypatch, make_input, render=None):
    from fastapi.testclient import TestClient

    from aimport.server import create_app
    from aimport.validate import ValidationResult

    make_input(tmp_path / "in")
    monkeypatch.setattr(server, "client_from_env", lambda: None)
    monkeypatch.setattr(server, "run_ezbids", lambda *a, **k: pytest.fail("nothing is left for ezBIDS"))
    monkeypatch.setattr(server, "validate_bids", lambda bids: ValidationResult(
        ok=True, validator_version="2.4.1", bids_version="1.11.2"))
    if render is not None:
        monkeypatch.setattr(qa, "render", render)
    app = create_app(tmp_path / "in", tmp_path / "work", tmp_path / "keys", "t" * 32, [], ["testserver"])
    c = TestClient(app)
    c.headers["Authorization"] = "Bearer " + "t" * 32
    assert c.post("/scan", json={"project_id": "proj"}).status_code == 202
    end = time.time() + 120
    while c.get("/status").json()["stage"] not in ("planned", "failed") and time.time() < end:
        time.sleep(0.05)
    edits = [{"id": e["id"], "entities": {**e["entities"], "task": "rest"}} for e in c.get("/plan").json()["entries"]
             if e.get("modality") == "ephys" and e["entities"].get("task") == "unknown"]
    if edits:
        assert c.patch("/plan", json={"edits": edits}).status_code == 200
    assert c.post("/approve", json={}).status_code == 200
    assert c.post("/execute").status_code == 202
    while (s := c.get("/status").json())["stage"] not in ("validated", "invalid", "failed") and time.time() < end:
        time.sleep(0.05)
    return app, c, s


def _planted(dest: Path) -> None:
    fx.planted_edf(dest / "a")
    fx.planted_snirf(dest / "b")


def test_qa_after_execute_and_routes(tmp_path, monkeypatch):
    from test_viewer_routes import viewer_client

    app, c, s = _run(tmp_path, monkeypatch, _planted)
    try:
        assert s["stage"] == "validated", s
        manifest = s["manifest"]
        ids = {Path(files[qa.primary_file(files)]).suffix: eid for eid, files in manifest.items()}
        assert set(ids) == {".vhdr", ".snirf"}
        root = tmp_path / "work" / "ephys" / "qa"
        for eid in ids.values():
            assert sorted(p.name for p in (root / eid).glob("*.png")) == ["channels.png", "psd.png", "traces.png"]
        assert not list((tmp_path / "work" / "output").rglob("*.png"))  # never under output/
        browser = viewer_client(c)
        page = browser.get("/viewer/").text
        for eid in ids.values():
            assert f'href="/viewer/traces/{eid}">Traces</a>' in page
            for kind in qa.KINDS:
                assert f'<img src="/qa/png/{eid}/{kind}.png"' in page
        assert not ephys_tokens(page)
        r = browser.get(f"/qa/png/{ids['.vhdr']}/traces.png")
        assert r.status_code == 200 and r.headers["content-type"] == "image/png"
        assert browser.get(f"/qa/png/{ids['.vhdr']}/other.png").status_code == 404
        r = browser.get(f"/qa/traces/{ids['.vhdr']}")
        assert r.status_code == 200, r.text
        w = r.json()
        assert w["t0"] == 0 and w["t1"] == 10 and len(w["channels"]) == 3 and w["name"].endswith("_eeg.vhdr")
        assert not ephys_tokens(r.text)
        nirs = browser.get(f"/qa/traces/{ids['.snirf']}?t0=1&t1=4&ch=0,4").json()
        assert nirs["pairs"] == [[0, 4]] and len(nirs["x"]) == 3 * 256
        eid = ids[".vhdr"]
        for q in ("t0=5&t1=5", "t0=6&t1=5", "t0=0&t1=601", "ch=" + ",".join(["0"] * 65), "ch=3", "ch=a",
                  "ch=-1", "ch=0,"):
            assert browser.get(f"/qa/traces/{eid}?{q}").status_code == 400, q
        r = browser.get(f"/viewer/traces/{eid}")
        assert r.status_code == 200 and f'data-entry="{eid}"' in r.text
        assert r.headers["content-security-policy"] == server.VIEWER_CSP
        assert "sub-01_task-rest_eeg.vhdr" in r.text
        assert TestClientNoAuth(c).get(f"/qa/traces/{eid}").status_code == 401
    finally:
        app.state.server.close()


def TestClientNoAuth(c):
    from fastapi.testclient import TestClient

    return TestClient(c.app)


def test_render_failure_does_not_fail_the_run(tmp_path, monkeypatch, caplog):
    def broken(entry_id, bids_path, out_dir):
        raise RuntimeError("Smith John was here")  # never logged: the type only

    app, c, s = _run(tmp_path, monkeypatch, fx.planted_edf, render=broken)
    try:
        assert s["stage"] == "validated", s
        assert "QA snapshot failed: RuntimeError" in caplog.text and "Smith" not in caplog.text
        eid = next(iter(s["manifest"]))
        assert c.get(f"/qa/png/{eid}/traces.png").status_code == 404
        assert c.get(f"/qa/traces/{eid}").status_code == 200  # the trace window does not need the snapshots
    finally:
        app.state.server.close()
