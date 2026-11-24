"""The QA viewer routes: the served Neuroglancer client and the browser session."""
import pytest
from fastapi.testclient import TestClient

from aimport import server
from aimport.server import VIEWER_COOKIE, create_app
from aimport import viewer
from aimport.viewer import VIEWER_CSP, neuroglancer_client_dir

TOKEN = "s3cret-token"
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


@pytest.fixture
def make_client(tmp_path):
    made = []
    (tmp_path / "in").mkdir()

    def make(auth=True):
        app = create_app(tmp_path / "in", tmp_path / "work", tmp_path / "keys", TOKEN, [], ["testserver"])
        made.append(app)
        c = TestClient(app)
        if auth:
            c.headers["Authorization"] = f"Bearer {TOKEN}"
        return c

    yield make
    for app in made:
        app.state.server.close()


@pytest.fixture
def client(make_client):
    return make_client()


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
