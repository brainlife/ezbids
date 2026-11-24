"""The QA viewer routes: the served Neuroglancer client, the browser session and the checked output data."""
import json
import os
from pathlib import Path
from urllib.parse import unquote, urlsplit

import pytest
from fastapi.testclient import TestClient

from aimport import server, viewer
from aimport.viewer import VIEWER_CSP, neuroglancer_client_dir
from conftest import NATIVE, PLANTED, tokens
from test_server import SCAN, TOKEN, apps, client, executed, hooks, make_client, planned, wait_stage  # noqa: F401
INDEX = b"<!doctype html><html><head><script type=module src=./assets/index-x.js></script></head></html>"


@pytest.fixture(autouse=True)
def ng_client(tmp_path, monkeypatch):
    """A stand-in for the built client (the image builds the real one into /opt/neuroglancer-client)."""
    d = tmp_path / "ng"
    (d / "assets").mkdir(parents=True)
    (d / "index.html").write_bytes(INDEX)
    (d / "assets" / "index-x.js").write_text("console.log(1)")
    (d / "assets" / "chunk_worker.bundle-x.js").write_text("")
    for name in ("x.wasm", "x.svg", "x.png", "x.woff2", "x.json"):
        (d / "assets" / name).write_bytes(b"\0")
    monkeypatch.setenv("AIMPORT_NEUROGLANCER_DIR", str(d))
    return d


def cookie_name(client: TestClient) -> str:
    return client.app.state.server.viewer_cookie


def viewer_client(client: TestClient) -> TestClient:
    """A browser-like client for client's app: no token, only the session cookie from the code exchange."""
    code = client.post("/viewer/session").json()["code"]
    browser = TestClient(client.app)
    r = browser.get(f"/viewer/open?code={code}", follow_redirects=False)
    assert r.status_code == 303, r.text
    assert browser.cookies.get(cookie_name(client))
    return browser


# --- the Neuroglancer client ---

def test_client_dir(ng_client, monkeypatch, tmp_path):
    assert neuroglancer_client_dir() == ng_client.resolve()
    monkeypatch.setenv("AIMPORT_NEUROGLANCER_DIR", str(tmp_path / "nowhere"))
    with pytest.raises(RuntimeError, match="the neuroglancer client is not installed"):
        neuroglancer_client_dir()
    monkeypatch.delenv("AIMPORT_NEUROGLANCER_DIR")
    monkeypatch.setattr(viewer, "NEUROGLANCER_DIR", str(ng_client))  # the image's default location
    assert neuroglancer_client_dir() == ng_client.resolve()


def test_serves_client(client):
    client = viewer_client(client)
    r = client.get("/viewer/ng/index.html")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
    assert r.headers["content-security-policy"] == VIEWER_CSP
    assert r.headers["cache-control"] == "no-store"
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.content == INDEX
    r = client.get("/viewer/ng/assets/index-x.js")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/javascript")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert "content-security-policy" not in r.headers
    for name, media in (("x.wasm", "application/wasm"), ("x.svg", "image/svg+xml"), ("x.png", "image/png"),
                        ("x.woff2", "font/woff2"), ("x.json", "application/json")):
        assert client.get(f"/viewer/ng/assets/{name}").headers["content-type"] == media


def test_client_root_is_index(client):
    r = client.get("/viewer/ng/")  # state_url points here
    assert r.status_code == 200 and r.content == INDEX
    assert r.headers["content-security-policy"] == VIEWER_CSP


def test_client_range(client):
    r = client.get("/viewer/ng/index.html", headers={"Range": "bytes=0-9"})
    assert r.status_code == 206
    assert r.content == INDEX[:10]


@pytest.mark.parametrize("path", ["/viewer/ng/%2e%2e/x",
                                  "/viewer/ng/assets/%2e%2e/%2e%2e/ng/index.html/..",
                                  "/viewer/ng/assets", "/viewer/ng/%2e%2e/%2e%2e/%2e%2e/etc/passwd",
                                  "/viewer/ng//etc/passwd", "/viewer/ng/%2Fetc%2Fpasswd",
                                  "/viewer/ng/missing.js"])
def test_client_traversal(client, path):
    assert client.get(path).status_code == 404


def test_client_needs_auth(make_client):
    assert make_client(auth=False).get("/viewer/ng/index.html").status_code == 401


@pytest.mark.parametrize("path", ["/viewer/ng/%2e%2e/secret.txt", "/viewer/ng/assets/%2e%2e/%2e%2e/secret.txt",
                                  "/viewer/ng/%2E%2E/secret.txt"])
def test_client_escape_to_existing_file(client, ng_client, path):
    (ng_client.parent / "secret.txt").write_text("secret")  # next to the client folder: one '..' away
    r = client.get(path)
    assert r.status_code == 404 and b"secret" not in r.content


def test_cookie_name_per_run(make_client):
    a, b = make_client(), make_client()
    assert cookie_name(a) != cookie_name(b) and cookie_name(a).startswith("aimport_viewer_")
    browser = viewer_client(a)
    browser.cookies.set(cookie_name(b), browser.cookies.get(cookie_name(a)))
    assert TestClient(b.app, cookies=dict(browser.cookies)).get("/viewer/ng/index.html").status_code == 401


def test_client_symlink_out(client, ng_client, tmp_path):
    (tmp_path / "secret.txt").write_text("secret")
    (ng_client / "assets" / "leak.js").symlink_to(tmp_path / "secret.txt")
    assert client.get("/viewer/ng/assets/leak.js").status_code == 404


def test_client_not_installed(client, monkeypatch, tmp_path):
    monkeypatch.setenv("AIMPORT_NEUROGLANCER_DIR", str(tmp_path / "nowhere"))
    r = client.get("/viewer/ng/index.html")
    assert r.status_code == 404
    assert r.json()["detail"] == "the neuroglancer client is not installed"


# --- the browser session ---

def exchange(client, code):
    browser = TestClient(client.app)
    return browser, browser.get(f"/viewer/open?code={code}", follow_redirects=False)


def test_session_code(client):
    r = client.post("/viewer/session")
    assert r.status_code == 200
    body = r.json()
    assert len(body["code"]) == 32 and int(body["code"], 16) >= 0
    assert body["url"] == f"/viewer/open?code={body['code']}"
    assert TOKEN not in r.text
    assert r.headers["cache-control"] == "no-store"


def test_session_needs_bearer(make_client, client):
    browser = viewer_client(client)
    assert browser.post("/viewer/session").status_code == 401  # the cookie is not enough
    assert make_client(auth=False).post("/viewer/session").status_code == 401


def test_exchange_sets_cookie(client):
    code = client.post("/viewer/session").json()["code"]
    _, r = exchange(client, code)
    assert r.status_code == 303
    assert r.headers["location"] == "/viewer/"
    cookie = r.headers["set-cookie"]
    name, _, rest = cookie.partition("=")
    value = rest.split(";")[0]
    assert name == cookie_name(client) and len(value) == 64 and int(value, 16) >= 0
    attrs = {a.strip().lower() for a in cookie.split(";")[1:]}  # attribute names and SameSite values: any case
    assert {"httponly", "samesite=strict", "path=/"} <= attrs
    assert "secure" not in cookie.lower()
    assert TOKEN not in cookie and TOKEN not in r.headers["location"]


def test_code_single_use(client):
    code = client.post("/viewer/session").json()["code"]
    assert exchange(client, code)[1].status_code == 303
    browser, r = exchange(client, code)
    assert r.status_code == 401
    assert "set-cookie" not in r.headers
    assert not browser.cookies


def test_code_expires(client, monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(server, "_now", lambda: now[0])
    code = client.post("/viewer/session").json()["code"]
    now[0] += 59
    assert exchange(client, code)[1].status_code == 303
    code = client.post("/viewer/session").json()["code"]
    now[0] += 60
    browser, r = exchange(client, code)
    assert r.status_code == 401
    assert "set-cookie" not in r.headers


@pytest.mark.parametrize("query", ["?code=" + "0" * 32, "?code=", ""])
def test_unknown_code(client, query):
    browser = TestClient(client.app)
    r = browser.get(f"/viewer/open{query}", follow_redirects=False)
    assert r.status_code == 401
    assert "set-cookie" not in r.headers


def test_cookie_only_on_viewer_routes(client):
    browser = viewer_client(client)
    assert browser.get("/viewer/ng/index.html").status_code == 200
    assert browser.get("/plan").status_code == 401
    assert browser.patch("/plan", json={"readme": "x"}).status_code == 401
    assert browser.post("/execute").status_code == 401
    assert browser.get("/status").status_code == 401
    assert browser.post("/scan", json={"project_id": "p"}).status_code == 401


def test_bearer_still_works(client):
    viewer_client(client)
    assert client.get("/status").status_code == 200
    assert client.get("/viewer/ng/index.html").status_code == 200


def test_wrong_cookie(client):
    viewer_client(client)
    browser = TestClient(client.app)
    browser.cookies.set(cookie_name(client), "0" * 64)
    assert browser.get("/viewer/ng/index.html").status_code == 401
    browser.cookies.set(cookie_name(client), "")
    assert browser.get("/viewer/ng/index.html").status_code == 401


# --- /qa/data: the checked output ---

def t1w(c):
    """The id of a written, defaced entry (the T1w in the fixture plan)."""
    return next(e["id"] for e in c.get("/plan").json()["entries"]
                if e["deface"] and e["status"] == "ok" and not e["exclude"])


def data_url(c, eid, index=0):
    return f"/qa/data/{eid}/{index}/"


def test_qa_data_before_execute(planned):
    r = planned.get(data_url(planned, t1w(planned)))
    assert r.status_code == 404
    assert r.json()["detail"] == "nothing to preview: execute the plan first"


def test_qa_data_serves_output(planned):
    eid = t1w(planned)
    executed(planned)
    rel = planned.get("/status").json()["manifest"][eid][0]
    r = planned.get(data_url(planned, eid))
    assert r.status_code == 200 and r.content == b"defaced-" + eid.encode()
    assert r.headers["cache-control"] == "no-store"
    assert r.headers["x-content-type-options"] == "nosniff"
    # the file's own name as subpath: the same file (so a viewer URL can end in .nii.gz)
    assert planned.get(data_url(planned, eid) + rel.rsplit("/", 1)[1]).content == r.content
    r = planned.get(data_url(planned, eid), params={"which": "original"})
    assert r.status_code == 200 and r.content == b"original-" + eid.encode()
    assert r.headers["cache-control"] == "no-store"


def test_qa_data_range(planned):
    eid = t1w(planned)
    executed(planned)
    whole = b"defaced-" + eid.encode()
    r = planned.get(data_url(planned, eid), headers={"Range": "bytes=0-15"})
    assert r.status_code == 206
    assert r.content == whole[:16] and len(r.content) == 16
    assert r.headers["content-range"] == f"bytes 0-15/{len(whole)}"


def test_qa_data_not_found(planned):
    eid = t1w(planned)
    executed(planned)
    assert planned.get(data_url(planned, eid, 1)).status_code == 404  # index out of range
    assert planned.get(data_url(planned, "nope")).status_code == 404  # not in the manifest
    assert planned.get(data_url(planned, eid) + "other.nii.gz").status_code == 404  # a file has no inside


@pytest.mark.parametrize("subpath", ["..", "../x", "%2e%2e", "%2e%2e/%2e%2e/scan.json", "%2Fetc%2Fpasswd",
                                     "/etc/passwd", "./x", "a/../b"])
def test_qa_data_traversal(planned, tmp_path, subpath):
    eid = t1w(planned)
    executed(planned)
    # a manifest directory (as an OME-Zarr entry will be) so a subpath is meaningful
    state_path = tmp_path / "work" / "output-state.json"
    state = json.loads(state_path.read_text())
    out = tmp_path / "work" / "output" / "bids"
    (out / "sub-01" / "x.zarr").mkdir(parents=True)
    (out / "sub-01" / "x.zarr" / "a").write_text("inside")
    state["manifest"]["zarr"] = ["sub-01/x.zarr"]
    state_path.write_text(json.dumps(state))
    assert planned.get("/qa/data/zarr/0/a").content == b"inside"
    assert planned.get(f"/qa/data/zarr/0/{subpath}").status_code == 404
    assert planned.get(f"/qa/data/{eid}/0/{subpath}").status_code == 404


def test_qa_data_symlink(planned, tmp_path):
    eid = t1w(planned)
    executed(planned)
    out = tmp_path / "work" / "output" / "bids"
    rel = planned.get("/status").json()["manifest"][eid][0]
    target = out / rel
    target.unlink()
    (tmp_path / "secret.nii.gz").write_bytes(b"secret")
    target.symlink_to(tmp_path / "secret.nii.gz")
    assert planned.get(data_url(planned, eid)).status_code == 404
    # a symlinked folder on the way, pointing back inside the output, is refused too
    target.unlink()
    folder = target.parent
    os.rename(folder, folder.with_name("real"))
    folder.symlink_to(folder.with_name("real"))
    (folder.with_name("real") / target.name).write_bytes(b"x")
    assert planned.get(data_url(planned, eid)).status_code == 404


def test_qa_data_after_rescan(planned):
    eid = t1w(planned)
    executed(planned)
    assert planned.get(data_url(planned, eid)).status_code == 200
    assert planned.post("/scan", json=SCAN).status_code == 202
    assert planned.get(data_url(planned, eid)).status_code == 404
    wait_stage(planned, "planned")
    assert planned.get(data_url(planned, eid)).status_code == 404


def test_qa_data_with_cookie_only(planned):
    eid = t1w(planned)
    executed(planned)
    browser = viewer_client(planned)
    assert browser.get(data_url(planned, eid)).status_code == 200
    assert browser.get(f"/preview/{eid}").status_code == 401  # bearer-only route


# --- the QA index and the entry states ---

def decoded_state(location: str) -> dict:
    assert location.startswith("/viewer/ng/#!")
    return json.loads(unquote(urlsplit(location).fragment[1:]))


def test_viewer_index(planned):
    assert planned.get("/viewer/").status_code == 404  # before execute
    executed(planned)
    manifest = planned.get("/status").json()["manifest"]
    entries = planned.get("/plan").json()["entries"]
    written = [e["id"] for e in entries if not e["exclude"] and e["status"] == "ok" and e["datatype"]]
    assert set(manifest) == set(written) and written
    excluded = [e["id"] for e in entries if e["id"] not in manifest]
    assert excluded  # the fixture plan has entries that are not written
    browser = viewer_client(planned)
    r = browser.get("/viewer/")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
    assert r.headers["content-security-policy"] == VIEWER_CSP
    assert r.headers["cache-control"] == "no-store"
    page = r.text
    for eid, paths in manifest.items():
        assert f'href="/viewer/entry/{eid}"' in page
        assert all(p in page for p in paths)
    for eid in excluded:
        assert f"/viewer/entry/{eid}\"" not in page
    defaced = t1w(planned)
    assert f'href="/viewer/entry/{defaced}?compare=1">defaced vs original' in page
    defaced_files = json.loads((planned.app.state.server.work / "output-state.json").read_text())["defaced"]
    assert page.count("defaced vs original</a>") == sum(len(v) for v in defaced_files.values())
    assert not (PLANTED | NATIVE) & tokens(page)
    assert "http://" not in page and "https://" not in page and "<script" not in page  # no external assets


def test_viewer_index_brainlife_look(planned):
    """The index has the brainlife-lite look (DM Sans fallback stack, primary #3d6a92, 6px radius, a white panel
    on #f5f5f5) and the brainlife.io logo top-left, served by the engine: no external font or asset (CSP 'self')."""
    executed(planned)
    browser = viewer_client(planned)
    page = browser.get("/viewer/").text
    assert '<img class="mark" src="/viewer/brainlife-mark.svg" alt="brainlife.io"' in page
    header = page[page.index("<header"):page.index("</header>")]
    assert "brainlife.io" in header and "aimport QA viewer" in header
    for token in ('"DM Sans"', "#3d6a92", "border-radius: 6px", "background: #f5f5f5", "background: #fff"):
        assert token in page, token
    assert "@import" not in page and "@font-face" not in page and "url(" not in page
    assert "http://" not in page and "https://" not in page and "<script" not in page
    r = browser.get("/viewer/brainlife-mark.svg")
    assert r.status_code == 200 and r.headers["content-type"] == "image/svg+xml"
    assert r.headers["content-security-policy"] == "default-src 'none'; style-src 'unsafe-inline'"
    assert r.headers["x-content-type-options"] == "nosniff" and b"<script" not in r.content
    assert r.content.lstrip().startswith(b"<svg")
    assert TestClient(planned.app).get("/viewer/brainlife-mark.svg").status_code == 401  # the session, as for pages


def test_viewer_entry_redirect(planned):
    eid = t1w(planned)
    executed(planned)
    browser = viewer_client(planned)
    r = browser.get(f"/viewer/entry/{eid}", follow_redirects=False)
    assert r.status_code == 303
    state = decoded_state(r.headers["location"])
    base = "http://testserver"
    assert state["layout"] == "4panel"
    names = [layer["name"] for layer in state["layers"]]
    assert len(names) == 2 and names[1] == names[0] + " (original)"
    assert state["layers"][1]["visible"] is False and "visible" not in state["layers"][0]
    for layer in state["layers"]:
        assert layer["source"].startswith(base + "/qa/data/")
    assert state["layers"][0]["source"].endswith(".nii.gz|gzip:|nifti:")
    assert state["layers"][1]["source"].endswith(".nii.gz?which=original|gzip:|nifti:")
    text = json.dumps(state)
    assert "appspot" not in text and TOKEN not in text
    assert text.count("http") == text.count(base)
    # the sources are served, to the cookie, as the defaced and the original image
    for layer, want in zip(state["layers"], (b"defaced-", b"original-")):
        url = layer["source"].split("|", 1)[0].removeprefix(base)
        assert browser.get(url).content == want + eid.encode()
    r = browser.get(f"/viewer/entry/{eid}", params={"compare": 1}, follow_redirects=False)
    state = decoded_state(r.headers["location"])
    assert state["layout"]["type"] == "row"
    assert all(layer.get("visible", True) for layer in state["layers"])


def test_viewer_entry_not_defaced_and_missing(planned):
    executed(planned)
    manifest = planned.get("/status").json()["manifest"]
    defaced = json.loads((planned.app.state.server.work / "output-state.json").read_text())["defaced"]
    other = next(eid for eid in manifest if eid not in defaced)
    state = decoded_state(planned.get(f"/viewer/entry/{other}", follow_redirects=False).headers["location"])
    assert len(state["layers"]) == 1
    assert planned.get("/viewer/entry/nope", follow_redirects=False).status_code == 404


def test_viewer_pages_need_auth(planned, make_client):
    executed(planned)
    anon = make_client(auth=False)
    assert anon.get("/viewer/").status_code == 401
    assert anon.get(f"/viewer/entry/{t1w(planned)}", follow_redirects=False).status_code == 401


def add_second_image(planned, eid, tmp_path, defaced=True):
    """Give entry eid a second written image (as a multi-echo or two-run entry has), defaced or not."""
    work = tmp_path / "work"
    state = json.loads((work / "output-state.json").read_text())
    first = state["manifest"][eid][0]
    second = first.replace(".nii.gz", "_2.nii.gz")
    (work / "output" / "bids" / second).write_bytes(b"defaced2-" + eid.encode())
    state["manifest"][eid].append(second)
    if defaced:
        (work / "pre-deface" / second).write_bytes(b"original2-" + eid.encode())
        state["defaced"][eid].append(second)
    (work / "output-state.json").write_text(json.dumps(state))
    return second


def test_viewer_entry_second_image(planned, tmp_path):
    eid = t1w(planned)
    executed(planned)
    second = add_second_image(planned, eid, tmp_path)
    browser = viewer_client(planned)
    page = browser.get("/viewer/").text
    assert second in page
    assert f'href="/viewer/entry/{eid}?index=1">Neuroglancer' in page
    assert f'href="/viewer/entry/{eid}?index=1&amp;compare=1">defaced vs original' in page
    r = browser.get(f"/viewer/entry/{eid}", params={"index": 1}, follow_redirects=False)
    assert r.status_code == 303
    state = decoded_state(r.headers["location"])
    name = second.rsplit("/", 1)[1].removesuffix(".nii.gz")
    assert [layer["name"] for layer in state["layers"]] == [name, name + " (original)"]
    base = "http://testserver"
    for layer, want in zip(state["layers"], (b"defaced2-", b"original2-")):
        assert layer["source"].startswith(f"{base}/qa/data/{eid}/1/")
        assert browser.get(layer["source"].split("|", 1)[0].removeprefix(base)).content == want + eid.encode()
    for bad in (2, 99, -1):
        assert browser.get(f"/viewer/entry/{eid}", params={"index": bad}, follow_redirects=False).status_code == 404


def test_viewer_entry_second_image_not_defaced(planned, tmp_path):
    eid = t1w(planned)
    executed(planned)
    add_second_image(planned, eid, tmp_path, defaced=False)
    page = planned.get("/viewer/").text
    assert f'href="/viewer/entry/{eid}?index=1">Neuroglancer' in page
    assert f"?index=1&amp;compare=1" not in page
    state = decoded_state(planned.get(f"/viewer/entry/{eid}", params={"index": 1},
                                      follow_redirects=False).headers["location"])
    assert len(state["layers"]) == 1


def test_qa_data_original_needs_an_original(planned):
    executed(planned)
    manifest = planned.get("/status").json()["manifest"]
    defaced = json.loads((planned.app.state.server.work / "output-state.json").read_text())["defaced"]
    other = next(eid for eid in manifest if eid not in defaced)
    r = planned.get(f"/qa/data/{other}/0/", params={"which": "original"})
    assert r.status_code == 404 and r.json()["detail"] == "no original for this image"
    assert planned.get(f"/qa/data/{other}/0/").status_code == 200
    # /preview keeps its behaviour: the written file stands in for the original
    assert planned.get(f"/preview/{other}", params={"which": "original"}).content == b"original-" + other.encode()


# --- microscopy: OME-Zarr output and reference datasets read through the chunk map ---

import contextlib  # noqa: E402
import time  # noqa: E402

from micr_fixtures import PSOCT_CONTRASTS, ome_zarr, planted_ome_tiff, psoct_nifti  # noqa: E402

from aimport.micr import readers  # noqa: E402
from aimport.micr.reference import write_chunk_map, write_reference  # noqa: E402
from conftest import MICR_PLANTED  # noqa: E402
from http.server import BaseHTTPRequestHandler  # noqa: E402

from test_micr_remote import local_servers  # noqa: E402,F401 - the local Range server fixture

REF = "ref"
REF_REL = "sub-01/micr/sub-01_sample-A_CONF.ome.zarr"
STORE = "Moe_Slice_051.ome.zarr"


def add_reference(planned, tmp_path, location=None, store=None):
    """Give the executed MRI run a reference OME-Zarr entry (manifest + rebuilt metadata + chunk map).
    location: the chunk map source of the store (default the input folder's copy of it)."""
    work, inp = tmp_path / "work", tmp_path / "in"
    store = store or ome_zarr(inp / STORE, "0.5")
    dest = work / "output" / "bids" / REF_REL
    with readers.open_image(store, "ome-zarr") as src:
        arrays = write_reference(src, location or {"input": STORE}, dest, src.info)
    write_chunk_map(work / "output" / "bids.chunks.json", {f"{REF_REL}/{k}": v for k, v in arrays.items()})
    state_path = work / "output-state.json"
    state = json.loads(state_path.read_text())
    state["manifest"][REF] = [REF_REL]
    state["chunk_map"] = "output/bids.chunks.json"
    state_path.write_text(json.dumps(state))
    return store


CHUNK = "0/c/1/0/0/0"  # level 0, channel 1: one shard of the fixture store


def test_qa_chunk_from_input(planned, tmp_path):
    executed(planned)
    store = add_reference(planned, tmp_path)
    whole = (store / CHUNK).read_bytes()
    browser = viewer_client(planned)
    r = browser.get(f"/qa/data/{REF}/0/{CHUNK}")
    assert r.status_code == 200 and r.content == whole
    assert r.headers["cache-control"] == "no-store" and r.headers["x-content-type-options"] == "nosniff"
    r = browser.get(f"/qa/data/{REF}/0/{CHUNK}", headers={"Range": "bytes=4-19"})
    assert r.status_code == 206 and r.content == whole[4:20]
    assert r.headers["content-range"] == f"bytes 4-19/{len(whole)}"
    r = browser.get(f"/qa/data/{REF}/0/{CHUNK}", headers={"Range": "bytes=-16"})  # a shard index
    assert r.status_code == 206 and r.content == whole[-16:]
    r = browser.head(f"/qa/data/{REF}/0/{CHUNK}")  # Neuroglancer's size probe before a suffix read
    assert r.status_code == 200 and r.headers["content-length"] == str(len(whole)) and not r.content
    # the metadata is the rebuilt one under bids/, never the source's
    written = (tmp_path / "work" / "output" / "bids" / REF_REL / "zarr.json").read_bytes()
    assert browser.get(f"/qa/data/{REF}/0/zarr.json").content == written != (store / "zarr.json").read_bytes()
    # a chunk key with no source object (the fill value) is a plain 404
    (store / CHUNK).unlink()
    r = browser.get(f"/qa/data/{REF}/0/{CHUNK}")
    assert r.status_code == 404 and r.json()["detail"] == "no such chunk"


def _amz_end_headers(self) -> None:
    """The local Range server, with the headers S3 adds."""
    self.send_header("X-Amz-Request-Id", "REQ123")
    self.send_header("X-Amz-Id-2", "abc")
    self.send_header("ETag", '"e"')
    BaseHTTPRequestHandler.end_headers(self)


def _served_reference(planned, tmp_path, local_servers, **attrs):  # noqa: F811
    attrs.setdefault("end_headers", _amz_end_headers)
    base, root, handler = local_servers("served", **attrs)
    store = ome_zarr(root / "CMC" / STORE, "0.5")
    add_reference(planned, tmp_path, {"url": f"{base}/CMC/{STORE}"}, store)
    return base, store


def _no_upstream(r, base):
    for h in r.headers:
        assert h.lower() not in ("location", "server", "etag") and not h.lower().startswith("x-amz"), h
    assert base.encode() not in r.content and b"CMC" not in r.content and b"127.0.0.1" not in r.content
    assert all(base not in v and "CMC" not in v for v in r.headers.values())


def test_qa_chunk_from_url(planned, tmp_path, local_servers):  # noqa: F811
    executed(planned)
    base, store = _served_reference(planned, tmp_path, local_servers)
    whole = (store / CHUNK).read_bytes()
    browser = viewer_client(planned)
    r = browser.get(f"/qa/data/{REF}/0/{CHUNK}")
    assert r.status_code == 200 and r.content == whole
    _no_upstream(r, base)
    r = browser.get(f"/qa/data/{REF}/0/{CHUNK}", headers={"Range": "bytes=0-0"})  # Neuroglancer's size probe
    assert r.status_code == 206 and r.content == whole[:1]
    assert r.headers["content-range"] == f"bytes 0-0/{len(whole)}"
    _no_upstream(r, base)
    r = browser.get(f"/qa/data/{REF}/0/{CHUNK}", headers={"Range": "bytes=-16"})
    assert r.status_code == 206 and r.content == whole[-16:]
    r = browser.head(f"/qa/data/{REF}/0/{CHUNK}")
    assert r.status_code == 200 and r.headers["content-length"] == str(len(whole)) and not r.content
    _no_upstream(r, base)
    (store / CHUNK).unlink()
    r = browser.get(f"/qa/data/{REF}/0/{CHUNK}")
    assert r.status_code == 404 and r.json()["detail"] == "no such chunk"
    _no_upstream(r, base)


def test_qa_chunk_redirects(planned, tmp_path, local_servers, monkeypatch):  # noqa: F811
    executed(planned)
    base, store = _served_reference(planned, tmp_path, local_servers)
    browser = viewer_client(planned)
    cm_path = tmp_path / "work" / "output" / "bids.chunks.json"
    cm = json.loads(cm_path.read_text())
    whole = (store / CHUNK).read_bytes()
    # same-origin redirect: followed, and its Location never reaches the browser
    cm["arrays"][f"{REF_REL}/0"]["source"] = {"url": f"{base}/redirect-same/CMC/{STORE}/0"}
    cm_path.write_text(json.dumps(cm))
    r = browser.get(f"/qa/data/{REF}/0/{CHUNK}")
    assert r.status_code == 200 and r.content == whole
    _no_upstream(r, base)
    # a redirect to another host: refused
    cm["arrays"][f"{REF_REL}/0"]["source"] = {"url": f"{base}/redirect-other/CMC/{STORE}/0"}
    cm_path.write_text(json.dumps(cm))
    r = browser.get(f"/qa/data/{REF}/0/{CHUNK}")
    assert r.status_code == 404 and r.json()["detail"] == "no such chunk"
    _no_upstream(r, base)


def test_qa_size_cap(planned, tmp_path, local_servers, monkeypatch):  # noqa: F811
    executed(planned)
    base, store = _served_reference(planned, tmp_path, local_servers, ignore_range=True)
    whole = (store / CHUNK).read_bytes()
    assert len(whole) > 1000
    monkeypatch.setattr(server, "QA_MAX_RESPONSE_BYTES", 1000)
    browser = viewer_client(planned)
    r = browser.get(f"/qa/data/{REF}/0/{CHUNK}", headers={"Range": "bytes=0-99"})  # ignored upstream
    assert r.status_code == 502 and len(r.content) < 1000
    _no_upstream(r, base)


def test_qa_size_cap_default():
    assert server.QA_MAX_RESPONSE_BYTES == 64 * 2**20


def test_qa_head_reports_full_length_get_capped(planned, tmp_path, local_servers, monkeypatch):  # noqa: F811
    """HEAD reports the object's full Content-Length whatever its size; a GET past the cap is 502 (the README
    says so)."""
    executed(planned)
    base, store = _served_reference(planned, tmp_path, local_servers)
    whole = (store / CHUNK).read_bytes()
    monkeypatch.setattr(server, "QA_MAX_RESPONSE_BYTES", 100)
    browser = viewer_client(planned)
    r = browser.head(f"/qa/data/{REF}/0/{CHUNK}")
    assert r.status_code == 200 and int(r.headers["content-length"]) == len(whole) > 100
    assert browser.get(f"/qa/data/{REF}/0/{CHUNK}").status_code == 502
    r = browser.get(f"/qa/data/{REF}/0/{CHUNK}", headers={"Range": "bytes=0-99"})  # a range under the cap
    assert r.status_code == 206 and r.content == whole[:100]
    readme = (Path(__file__).resolve().parents[1] / "README.md").read_text()
    assert "reports the object's full `Content-Length`" in readme and "at most 64 MiB per GET" in readme


@pytest.mark.parametrize("case", ["dotdot", "encoded", "absolute", "array-dir", "key-range", "not-a-key",
                                  "outside-manifest", "group-as-array", "source-dotdot", "source-absolute", "source-symlink",
                                  "file-url", "http-url", "original"])
def test_qa_chunk_traversal_404(planned, tmp_path, case):
    """Review Focus 3: every escape from a manifest .ome.zarr directory, its mapped arrays, the input folder
    or the remote rules is a 404 that names nothing."""
    executed(planned)
    store = add_reference(planned, tmp_path)
    work, inp = tmp_path / "work", tmp_path / "in"
    (tmp_path / "secret").mkdir()
    (tmp_path / "secret" / "c").mkdir()
    cm_path = work / "output" / "bids.chunks.json"
    cm = json.loads(cm_path.read_text())
    level0 = cm["arrays"][f"{REF_REL}/0"]
    path = f"/qa/data/{REF}/0/{CHUNK}"
    params = {}
    if case == "dotdot":
        path = f"/qa/data/{REF}/0/{CHUNK}/../../x"  # (the client normalises a literal '..'; see "encoded")
    elif case == "encoded":
        path = f"/qa/data/{REF}/0/0/%2e%2e/0/{CHUNK[2:]}"
    elif case == "absolute":
        path = f"/qa/data/{REF}/0/%2F{tmp_path}/in/{STORE}/{CHUNK}"
    elif case == "array-dir":
        path = f"/qa/data/{REF}/0/0"
    elif case == "key-range":
        path = f"/qa/data/{REF}/0/0/c/9/0/0/0"
    elif case == "not-a-key":
        path = f"/qa/data/{REF}/0/0/c/1/0/0/0/x"
    elif case == "outside-manifest":  # a mapped array that is not under this entry's .ome.zarr
        cm["arrays"]["sub-01/micr/other.ome.zarr/0"] = level0
        path = f"/qa/data/{REF}/0/%2e%2e/other.ome.zarr/{CHUNK}"
    elif case == "group-as-array":  # an array mapped at the entry's folder itself, not strictly inside it
        cm["arrays"][REF_REL] = dict(level0)
        path = f"/qa/data/{REF}/0/{CHUNK[2:]}"
    elif case == "source-dotdot":
        leak = tmp_path / "secret" / "c" / "1" / "0" / "0" / "0"
        leak.parent.mkdir(parents=True)
        leak.write_text("secret")
        level0["source"] = {"input": "../secret"}
    elif case == "source-absolute":
        level0["source"] = {"input": str(store / "0")}
    elif case == "source-symlink":
        (inp / "linked").symlink_to(store, target_is_directory=True)
        level0["source"] = {"input": "linked/0"}
    elif case == "file-url":
        level0["source"] = {"url": f"file://{store}/0"}
    elif case == "http-url":
        level0["source"] = {"url": "http://example.org/CMC/x/0"}
    elif case == "original":
        params = {"which": "original"}
    cm_path.write_text(json.dumps(cm))
    r = planned.get(path, params=params)
    assert r.status_code == 404, (case, r.status_code)
    assert str(tmp_path) not in r.text and "secret" not in r.text and "example.org" not in r.text
    if case in ("outside-manifest", "original", "dotdot", "encoded"):  # the chunk itself is served
        assert planned.get(f"/qa/data/{REF}/0/{CHUNK}").status_code == 200


# --- Task 10b: proxy hardening ---

class _FakeUpstream:
    """An upstream chunk response of 64 parts of 1 KiB that records how much was read and whether it was closed."""

    status_code = 200
    headers = {"content-length": str(64 * 1024)}

    def __init__(self):
        self.read, self.closed = 0, False

    def iter_raw(self):
        for _ in range(64):
            if self.closed:
                return
            self.read += 1
            yield b"x" * 1024

    def close(self):
        self.closed = True


def _asgi_get(app, path, cookie, spec_version):
    """GET path through the raw ASGI app, the client leaving after the first body part: with ASGI 2.4 the
    next send fails (OSError), before 2.4 the server reports http.disconnect."""
    import asyncio

    async def run():
        left = asyncio.Event()
        sent = []

        async def receive():
            if not sent:
                sent.append("request")
                return {"type": "http.request", "body": b"", "more_body": False}
            await left.wait()
            return {"type": "http.disconnect"}

        async def send(message):
            if message["type"] == "http.response.body" and message.get("body"):
                if left.is_set() and spec_version == "2.4":
                    raise OSError("client went away")
                left.set()

        scope = {"type": "http", "asgi": {"version": "3.0", "spec_version": spec_version}, "http_version": "1.1",
                 "method": "GET", "scheme": "http", "path": path, "raw_path": path.encode(), "query_string": b"",
                 "root_path": "", "headers": [(b"host", b"testserver"), (b"cookie", cookie.encode())],
                 "client": ("127.0.0.1", 50000), "server": ("testserver", 80)}
        try:
            await asyncio.wait_for(app(scope, receive, send), 10)
        except OSError:
            pass
        except Exception as e:  # noqa: BLE001 - starlette's ClientDisconnect
            if type(e).__name__ != "ClientDisconnect":
                raise
    asyncio.run(run())


@pytest.mark.parametrize("spec_version", ["2.4", "2.3"])
def test_qa_proxy_closes_upstream_on_disconnect(planned, tmp_path, local_servers, monkeypatch, spec_version):  # noqa: F811
    """A viewer that cancels a chunk mid-stream: the upstream response is closed at once (it would otherwise
    hold a pooled connection until garbage collection) and the rest of the body is never read."""
    from aimport.micr import remote

    executed(planned)
    _served_reference(planned, tmp_path, local_servers)
    browser = viewer_client(planned)
    fakes = []

    def fake_open(url, range_header, method, client):
        fakes.append(_FakeUpstream())
        return fakes[-1]

    monkeypatch.setattr(remote, "open_stream", fake_open)
    name = cookie_name(planned)
    _asgi_get(planned.app, f"/qa/data/{REF}/0/{CHUNK}", f"{name}={browser.cookies.get(name)}", spec_version)
    (up,) = fakes
    assert up.closed and up.read < 64, up.read


@pytest.mark.parametrize("value", ["bytes=0-1,4-5", "bytes=0-1, -4", "items=0-1", "bytes=a-b", "bytes=5"])
def test_qa_unsupported_range_is_416(planned, tmp_path, local_servers, value):  # noqa: F811
    """A multi-range or another unit is answered 416 here: never an un-ranged GET of the whole object upstream."""
    executed(planned)
    _served_reference(planned, tmp_path, local_servers)
    browser = viewer_client(planned)
    srv = planned.app.state.server
    sends = []

    class Spy:
        def build_request(self, *a, **k):
            sends.append((a, k))
            raise AssertionError("nothing may go upstream")

        def close(self):
            pass

    srv._stream_client = Spy()
    r = browser.get(f"/qa/data/{REF}/0/{CHUNK}", headers={"Range": value})
    assert r.status_code == 416 and not r.content and sends == []


def test_qa_stream_client_per_app_and_closed(tmp_path, monkeypatch):
    """Each app has its own pooled client, made on first use and closed when the app stops (lifespan)."""
    apps = [server.create_app(tmp_path / "in", tmp_path / f"work{i}", tmp_path / f"keys{i}", TOKEN, [],
                              ["testserver"]) for i in (1, 2)]
    (tmp_path / "in").mkdir(exist_ok=True)
    a, b = (app.state.server for app in apps)
    assert a._stream_client is None
    ca, cb = a.stream_client(), b.stream_client()
    assert ca is a.stream_client() and ca is not cb and not ca.is_closed
    with TestClient(apps[0]):
        pass  # startup and shutdown: the lifespan closes the client
    assert ca.is_closed and a._stream_client is None and not cb.is_closed
    b.close()
    assert cb.is_closed


# --- the micr QA index and states, through a real scan and execute ---

def _wait(c, stages, timeout=90):
    end = time.time() + timeout
    while (s := c.get("/status").json())["stage"] not in stages and time.time() < end:
        time.sleep(0.05)
    return s


@pytest.fixture
def micr_run(tmp_path, monkeypatch):
    """A micr-only run executed through the server: the four PS-OCT contrasts of one slice (NIfTI, converted),
    a planted OME-TIFF in H17_250215/ (converted) and Moe_Slice_051.ome.zarr (a reference)."""
    inp = tmp_path / "in"
    folders = ("Reflectivity", "Retardance", "Orientation", "Cross")
    for contrast, folder in zip(PSOCT_CONTRASTS, folders):
        psoct_nifti(inp / "PS-OCT/Enface/Registration" / folder / "Slice_051_1.nii.gz", contrast)
    ome_zarr(inp / STORE, "0.5")
    planted_ome_tiff(inp / "H17_250215" / "stack.ome.tif")
    with _executed_micr(inp, tmp_path, monkeypatch) as c:
        yield c


@contextlib.contextmanager
def _executed_micr(inp, tmp_path, monkeypatch):
    """inp scanned, planned (unknown suffixes set to CONF), approved and executed through the server."""
    from aimport.validate import ValidationResult

    monkeypatch.setattr(server, "client_from_env", lambda: None)
    monkeypatch.setattr(server, "run_ezbids", lambda *a, **k: pytest.fail("nothing is left for ezBIDS"))
    monkeypatch.setattr(server, "validate_bids", lambda bids: ValidationResult(
        ok=True, validator_version="2.4.1", bids_version="1.11.2"))
    app = server.create_app(inp, tmp_path / "work", tmp_path / "keys", TOKEN, [], ["testserver"])
    c = TestClient(app)
    c.headers["Authorization"] = "Bearer " + TOKEN
    try:
        assert c.post("/scan", json={"project_id": "proj"}).status_code == 202
        assert _wait(c, ("planned", "failed"))["stage"] == "planned"
        edits = [{"id": e["id"], "suffix": "CONF"} for e in c.get("/plan").json()["entries"] if e["status"] == "unknown"]
        if edits:
            assert c.patch("/plan", json={"edits": edits}).status_code == 200
        assert c.post("/approve", json={}).status_code == 200
        assert c.post("/execute").status_code == 202
        s = _wait(c, ("validated", "invalid", "failed"))
        assert s["stage"] == "validated", s
        yield c
    finally:
        app.state.server.close()


def _entries(c):
    return {e["id"]: e for e in c.get("/plan").json()["entries"]}


def test_viewer_index_no_identifiers(micr_run):
    browser = viewer_client(micr_run)
    page = browser.get("/viewer/").text
    entries = _entries(micr_run)
    manifest = micr_run.get("/status").json()["manifest"]
    assert manifest and all(p.endswith(".ome.zarr") for ps in manifest.values() for p in ps)
    for eid, paths in manifest.items():
        assert f'href="/viewer/entry/{eid}">Neuroglancer (OME-Zarr)</a>' in page
        assert all(p in page for p in paths)
    refs = [eid for eid in manifest if entries[eid]["write_mode"] == "reference"]
    assert len(refs) == 1 and page.count("(read from source)") == 1
    assert not {t for t in MICR_PLANTED if t in page.lower()}
    assert "http://" not in page and "https://" not in page and "<script" not in page


def test_viewer_oct_entry_state(micr_run):
    browser = viewer_client(micr_run)
    entries = _entries(micr_run)
    octs = [e for e in entries.values() if e["suffix"] == "OCT"]
    assert len(octs) == 4
    r = browser.get(f"/viewer/entry/{octs[0]['id']}", follow_redirects=False)
    assert r.status_code == 303
    state = decoded_state(r.headers["location"])
    assert len(state["layers"]) == 4
    panels = [p for row in state["layout"]["children"] for p in row["children"]]
    assert len(panels) == 4 and all(len(p["layers"]) == 1 for p in panels)
    assert [layer["name"].split("_acq-")[1] for layer in state["layers"]] == [
        f"{c}_OCT" for c in PSOCT_CONTRASTS]
    assert list(state["dimensions"])[:2] == ["x", "y"]
    base = "http://testserver"
    for layer in state["layers"]:
        assert layer["source"].startswith(base + "/qa/data/") and layer["source"].endswith("/|zarr3:")
        url = layer["source"].removesuffix("|zarr3:").removeprefix(base)
        doc = browser.get(url + "zarr.json")
        assert doc.status_code == 200 and doc.json()["node_type"] == "group"
    text = json.dumps(state).lower()
    assert "amazonaws" not in text and TOKEN not in text and not {t for t in MICR_PLANTED if t in text}


def test_viewer_reference_entry_state(micr_run):
    browser = viewer_client(micr_run)
    entries = _entries(micr_run)
    ref = next(e for e in entries.values() if e["write_mode"] == "reference")
    state = decoded_state(browser.get(f"/viewer/entry/{ref['id']}", follow_redirects=False).headers["location"])
    assert len(state["layers"]) == 2 and all(layer["blend"] == "additive" for layer in state["layers"])
    assert list(state["dimensions"]) == ["x", "y", "z"] and state["layout"] == "4panel"
    # the fixture store has no omero block: the window is the coarsest level's 0.5/99.5 percentiles,
    # not the uint16 range
    for layer in state["layers"]:
        lo, hi = layer["shaderControls"]["normalized"]["range"]
        assert 0 <= lo < hi <= 4096 and (lo, hi) != (0.0, 65535.0)
    # its chunks are served from the input, through the chunk map
    url = state["layers"][0]["source"].removesuffix("|zarr3:").removeprefix("http://testserver")
    store = micr_run.app.state.server.input_dir / STORE
    assert browser.get(url + CHUNK).content == (store / CHUNK).read_bytes()


def test_micr_input_executes_with_uint16_references(tmp_path, monkeypatch):
    """A VISoR acqinfo_metadata.json says dtype "uint16": a data-type name is vocabulary, never a
    term, so the uint16 reference stores of the same run are not refused by the term scan."""
    from test_micr_plan import micr_input

    with _executed_micr(micr_input(tmp_path / "in"), tmp_path, monkeypatch) as c:
        entries = _entries(c)
        refs = [e for e in entries.values() if e["write_mode"] == "reference" and not e["exclude"]]
        assert len(refs) == 2
        manifest = c.get("/status").json()["manifest"]
        assert all(e["id"] in manifest for e in refs)


def _ref_window(browser, ref_id):
    state = decoded_state(browser.get(f"/viewer/entry/{ref_id}", follow_redirects=False).headers["location"])
    return tuple(state["layers"][0]["shaderControls"]["normalized"]["range"])


def test_window_cache_skips_failures_and_follows_execute(micr_run, monkeypatch):
    """A failed window read is not cached (the next view tries again); a cached window belongs to one
    execute (the output state's generation)."""
    browser = viewer_client(micr_run)
    ref = next(e for e in _entries(micr_run).values() if e["write_mode"] == "reference")
    real = server.micr_reference.read_array
    calls = []

    def flaky(*a, **k):
        calls.append(1)
        if len(calls) == 1:
            raise ValueError("the source did not answer")
        return real(*a, **k)

    monkeypatch.setattr(server.micr_reference, "read_array", flaky)
    assert _ref_window(browser, ref["id"]) == (0.0, 65535.0) and len(calls) == 1  # the written placeholder
    good = _ref_window(browser, ref["id"])
    assert good != (0.0, 65535.0) and len(calls) == 2  # tried again
    assert _ref_window(browser, ref["id"]) == good and len(calls) == 2  # cached
    state = micr_run.app.state.server.work / server.OUTPUT_STATE
    later = state.stat().st_mtime_ns + 2_000_000_000
    os.utime(state, ns=(later, later))  # another execute
    assert _ref_window(browser, ref["id"]) == good and len(calls) == 3


def test_default_window_rule():
    """0..1 (or the dtype's range) is a placeholder only when the source had no omero window; a real one is kept."""
    w01 = {"min": 0.0, "max": 1.0, "start": 0.0, "end": 1.0}
    assert server._default_window(w01, "float32", source_windows=True) is False
    assert server._default_window(w01, "float32", source_windows=False) is True
    assert server._default_window(w01, "float32") is True  # not recorded: judged by the values
    full = {"min": 0, "max": 65535, "start": 0, "end": 65535}
    assert server._default_window(full, "uint16", source_windows=True) is False
    assert server._default_window(full, "uint16", source_windows=False) is True
    assert server._default_window({"start": 3, "end": 9}, "uint16") is False
    assert server._default_window(None, "uint16", source_windows=True) is True


def test_real_omero_window_kept_by_the_viewer(tmp_path, monkeypatch):
    """A float32 reference whose source omero window is 0..1: recorded at scan as the source's, and the
    viewer keeps it (no percentile read)."""
    from aimport.micr.module import RECORDS_FILE

    inp = tmp_path / "in"
    store = ome_zarr(inp / STORE, "0.5", dtype="float32")
    doc = json.loads((store / "zarr.json").read_text())
    doc["attributes"]["ome"]["omero"] = {"channels": [
        {"window": {"min": 0.0, "max": 1.0, "start": 0.0, "end": 1.0}, "color": "FFFFFF"} for _ in range(2)]}
    (store / "zarr.json").write_text(json.dumps(doc))
    monkeypatch.setattr(server.micr_reference, "read_array",
                        lambda *a, **k: pytest.fail("a real window is kept, never recomputed"))
    with _executed_micr(inp, tmp_path, monkeypatch) as c:
        (rec,) = json.loads((tmp_path / "work" / "micr" / RECORDS_FILE).read_text())
        assert rec["info"]["reference_layout"]["source_windows"] is True
        ref = next(e for e in _entries(c).values() if e["write_mode"] == "reference")
        assert _ref_window(viewer_client(c), ref["id"]) == (0.0, 1.0)


def test_reference_window_level_and_nan(tmp_path, monkeypatch):
    """The window comes from the level whose largest x/y is closest to the target within the cap, NaN ignored;
    a channel that is all NaN there comes from the next finer level that fits, else keeps the written default."""
    import numpy as np
    import zarr

    from aimport.micr.convert import window_of

    inp = tmp_path / "in"
    store = ome_zarr(inp / STORE, "0.5", levels=4, dtype="float32")  # x/y 64, 32, 16, 8
    level1 = zarr.open_array(str(store / "1"), mode="r+")
    level1[1] = np.nan  # channel 1 is all NaN at level 1
    level1[0, 0, 0, :4] = [np.inf, -np.inf, np.nan, np.nan]
    monkeypatch.setattr(server, "QA_WINDOW_TARGET_SIDE", 30)  # level 1 (32) is the closest
    real = server.micr_reference.read_array
    reads = []

    def spy(chunks, bids, array_rel, *a, **k):
        reads.append(array_rel.rsplit("/", 1)[1])
        return real(chunks, bids, array_rel, *a, **k)

    monkeypatch.setattr(server.micr_reference, "read_array", spy)
    with _executed_micr(inp, tmp_path, monkeypatch) as c:
        browser = viewer_client(c)
        ref = next(e for e in _entries(c).values() if e["write_mode"] == "reference")

        def windows():
            loc = browser.get(f"/viewer/entry/{ref['id']}", follow_redirects=False).headers["location"]
            return [tuple(layer["shaderControls"]["normalized"]["range"]) for layer in decoded_state(loc)["layers"]]

        w = windows()
        want0 = window_of(zarr.open_array(str(store / "1"), mode="r")[0], "float32")
        want1 = window_of(zarr.open_array(str(store / "0"), mode="r")[1], "float32")
        assert reads == ["1", "0"]
        assert w[0] == pytest.approx((want0["start"], want0["end"]))
        assert w[1] == pytest.approx((want1["start"], want1["end"]))
        # level 0 past the cap: channel 1 keeps the written default (0..1); level 1 is still used for channel 0
        monkeypatch.setattr(server, "QA_WINDOW_MAX_BYTES", 100_000)
        state = c.app.state.server.work / server.OUTPUT_STATE
        later = state.stat().st_mtime_ns + 2_000_000_000
        os.utime(state, ns=(later, later))
        reads.clear()
        w = windows()
        assert reads == ["1"] and w[1] == (0.0, 1.0) and w[0] == pytest.approx((want0["start"], want0["end"]))
        # the target past every level that fits: the closest that fits (a coarser one) is used
        monkeypatch.setattr(server, "QA_WINDOW_TARGET_SIDE", 1024)
        os.utime(state, ns=(later + 2_000_000_000,) * 2)
        reads.clear()
        windows()
        assert reads[0] == "1"
