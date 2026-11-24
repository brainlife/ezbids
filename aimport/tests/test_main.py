"""``python -m aimport serve``: bind address rules."""
import pytest

import uvicorn

from aimport.__main__ import main


@pytest.fixture
def served(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(uvicorn, "run", lambda app, host, port, **kw: calls.append(host))
    monkeypatch.setenv("AIMPORT_TOKEN", "t")
    monkeypatch.delenv("AIMPORT_IN_CONTAINER", raising=False)

    def serve(host):
        return main(["serve", "--input", str(tmp_path / "in"), "--work", str(tmp_path / "work"),
                     "--keys", str(tmp_path / "keys"), "--host", host])

    (tmp_path / "in").mkdir()
    return serve, calls


@pytest.mark.parametrize("host", ["127.0.0.1", "::1", "localhost"])
def test_loopback_binds_allowed(served, host):
    serve, calls = served
    assert serve(host) == 0 and calls == [host]


@pytest.mark.parametrize("host", ["0.0.0.0", "::", "192.168.1.5", "example.org", "127.0.0.1.example.org"])
def test_other_binds_need_the_container(served, monkeypatch, host):
    serve, calls = served
    with pytest.raises(SystemExit):
        serve(host)
    assert calls == []
    monkeypatch.setenv("AIMPORT_IN_CONTAINER", "1")
    assert serve(host) == 0 and calls == [host]
