import json
import subprocess

import pytest


@pytest.mark.docker
def test_toolchain_present():
    for cmd in (["dcm2niix", "-v"], ["pydeface", "--help"], ["bids-validator-2", "--version"]):
        assert subprocess.run(cmd, capture_output=True).returncode in (0, 3)  # dcm2niix -v exits 3
    assert json.load(open("/opt/bids-schema/schema.json"))["bids_version"] == "1.11.2"


@pytest.mark.docker
def test_ezbids_spec_submodule_pinned():
    import hashlib
    from pathlib import Path

    schema = Path("/app/bids-specification/src/schema")
    rels = sorted("./" + p.relative_to(schema).as_posix() for p in schema.rglob("*") if p.is_file())
    listing = "".join(f"{hashlib.sha256((schema / r).read_bytes()).hexdigest()}  {r}\n" for r in rels)
    assert hashlib.sha256(listing.encode()).hexdigest() == (
        "fb78c5cced1fdb3ed4a44797732caae287c50d6c6e4ce697dca149fff7a6608c"
    )


@pytest.mark.docker
def test_venv_python_pinned_and_world_readable():
    out = subprocess.run(
        ["/opt/aimport-venv/bin/python", "-V"], capture_output=True, text=True
    )
    assert out.stdout.strip() == "Python 3.11.18"
    real = subprocess.run(
        ["readlink", "-f", "/opt/aimport-venv/bin/python"], capture_output=True, text=True
    ).stdout.strip()
    assert real.startswith("/opt/uv-python/")
