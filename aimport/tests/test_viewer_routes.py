"""The QA viewer routes: the served Neuroglancer client, the browser session and the checked output data."""
import json
import os

import pytest
from fastapi.testclient import TestClient

from aimport import server, viewer
from aimport.server import VIEWER_COOKIE
from aimport.viewer import VIEWER_CSP, neuroglancer_client_dir
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
    (d / "assets" / "x.wasm").write_bytes(b"\0asm")
    monkeypatch.setenv("AIMPORT_NEUROGLANCER_DIR", str(d))
    return d


def viewer_client(client: TestClient) -> TestClient:
    """A browser-like client for client's app: no token, only the session cookie from the code exchange."""
    code = client.post("/viewer/session").json()["code"]
    browser = TestClient(client.app)
    r = browser.get(f"/viewer/open?code={code}", follow_redirects=False)
    assert r.status_code == 303, r.text
    assert browser.cookies.get(VIEWER_COOKIE)
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
    assert client.get("/viewer/ng/assets/x.wasm").headers["content-type"] == "application/wasm"


def test_client_range(client):
    r = client.get("/viewer/ng/index.html", headers={"Range": "bytes=0-9"})
    assert r.status_code == 206
    assert r.content == INDEX[:10]


@pytest.mark.parametrize("path", ["/viewer/ng/../server.py", "/viewer/ng/%2e%2e/x", "/viewer/ng/assets/%2e%2e/%2e%2e/ng/index.html/..",
                                  "/viewer/ng/assets", "/viewer/ng/%2e%2e/%2e%2e/%2e%2e/etc/passwd",
                                  "/viewer/ng//etc/passwd", "/viewer/ng/%2Fetc%2Fpasswd", "/viewer/ng/",
                                  "/viewer/ng/missing.js"])
def test_client_traversal(client, path):
    assert client.get(path).status_code == 404


def test_client_needs_auth(make_client):
    assert make_client(auth=False).get("/viewer/ng/index.html").status_code == 401


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
    assert name == VIEWER_COOKIE and len(value) == 64 and int(value, 16) >= 0
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
    browser.cookies.set(VIEWER_COOKIE, "0" * 64)
    assert browser.get("/viewer/ng/index.html").status_code == 401
    browser.cookies.set(VIEWER_COOKIE, "")
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
