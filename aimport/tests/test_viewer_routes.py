"""The QA viewer routes: the served Neuroglancer client, the browser session and the checked output data."""
import json
import os
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
