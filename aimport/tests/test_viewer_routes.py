"""The QA viewer routes: the served Neuroglancer client and the browser session."""
import pytest
from fastapi.testclient import TestClient

from aimport.server import create_app
from aimport.viewer import VIEWER_CSP, neuroglancer_client_dir

TOKEN = "s3cret-token"


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


# --- the Neuroglancer client ---

def test_client_dir_has_index():
    assert (neuroglancer_client_dir() / "index.html").is_file()


def test_serves_client(client):
    r = client.get("/viewer/ng/index.html")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
    assert r.headers["content-security-policy"] == VIEWER_CSP
    assert r.headers["cache-control"] == "no-store"
    assert r.headers["x-content-type-options"] == "nosniff"
    js = next(p.name for p in neuroglancer_client_dir().iterdir() if p.name.startswith("main.") and p.suffix == ".js")
    r = client.get(f"/viewer/ng/{js}")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/javascript")
    assert "content-security-policy" not in r.headers


def test_client_range(client):
    r = client.get("/viewer/ng/index.html", headers={"Range": "bytes=0-9"})
    assert r.status_code == 206
    assert r.content == b"<!doctype "


@pytest.mark.parametrize("path", ["/viewer/ng/../server.py", "/viewer/ng/%2e%2e/x", "/viewer/ng/%2e%2e/%2e%2e/viewer.py",
                                  "/viewer/ng//etc/passwd", "/viewer/ng/%2Fetc%2Fpasswd", "/viewer/ng/",
                                  "/viewer/ng/missing.js"])
def test_client_traversal(client, path):
    assert client.get(path).status_code == 404


def test_client_needs_auth(make_client):
    assert make_client(auth=False).get("/viewer/ng/index.html").status_code == 401


def test_client_not_installed(client, monkeypatch):
    from aimport import server

    def missing():
        raise RuntimeError("the neuroglancer client is not installed")

    monkeypatch.setattr(server, "neuroglancer_client_dir", missing)
    r = client.get("/viewer/ng/index.html")
    assert r.status_code == 404
    assert r.json()["detail"] == "the neuroglancer client is not installed"
