"""Fetch the microscopy examples (micr_*) of bids-standard/bids-examples at a pinned commit.

Runs on the host and inside the engine image (standard library only). The downloaded tarball
(about 16 MB) is cached, and only the micr_* folders are extracted.
"""
from __future__ import annotations

import shutil
import tarfile
import tempfile
import urllib.request
from pathlib import Path

BIDS_EXAMPLES_REPO = "bids-examples"
BIDS_EXAMPLES_COMMIT = "5e00d47b6f1db106dda1b776d5243eb41b4cb95b"  # master, 2026-10-09
BIDS_EXAMPLES_URL = f"https://github.com/bids-standard/{BIDS_EXAMPLES_REPO}/archive/{BIDS_EXAMPLES_COMMIT}.tar.gz"
MICR_EXAMPLES = ("micr_SPIM", "micr_SEMzarr", "micr_XPCTzarr", "micr_SEM")


def _download(cache: Path) -> Path:
    cache.mkdir(parents=True, exist_ok=True)
    tarball = cache / f"{BIDS_EXAMPLES_REPO}-{BIDS_EXAMPLES_COMMIT}.tar.gz"
    if not tarball.exists():
        tmp = tarball.with_suffix(".part")
        with urllib.request.urlopen(BIDS_EXAMPLES_URL, timeout=120) as r, open(tmp, "wb") as f:
            shutil.copyfileobj(r, f)
        tmp.replace(tarball)
    return tarball


def fetch_bids_example(name: str, dest: Path, cache: Path | None = None) -> Path:
    """Extract bids-examples/<name> (a micr_* folder) at the pinned commit into dest/<name>; return it."""
    if name not in MICR_EXAMPLES:
        raise ValueError(f"not a pinned micr example: {name!r}")
    cache = Path(cache) if cache else Path(tempfile.gettempdir()) / "aimport-bids-examples-cache"
    tarball = _download(cache)
    root = Path(dest) / name
    prefix = f"{BIDS_EXAMPLES_REPO}-{BIDS_EXAMPLES_COMMIT}/{name}/"
    found = 0
    with tarfile.open(tarball) as tf:
        for member in tf:
            if not member.isfile() or not member.name.startswith(prefix):
                continue
            rel = Path(member.name[len(prefix):])
            if ".." in rel.parts or rel.is_absolute():
                continue
            target = root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            with tf.extractfile(member) as src, open(target, "wb") as out:
                shutil.copyfileobj(src, out)
            found += 1
    if not found:
        raise RuntimeError(f"{name} not found in bids-examples {BIDS_EXAMPLES_COMMIT}")
    return root


if __name__ == "__main__":
    import sys

    for n in MICR_EXAMPLES:
        print(fetch_bids_example(n, Path(sys.argv[1])))
