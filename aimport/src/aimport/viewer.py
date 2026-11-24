"""The local QA viewer: the Neuroglancer client served by the engine itself (same origin, no third-party page).

Only the static client bundled in the pinned ``neuroglancer`` wheel (``neuroglancer/static/client/``) is used;
the package's Python server is never imported.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

# Content-Security-Policy of the viewer's HTML pages
VIEWER_CSP = ("default-src 'self'; img-src 'self' data: blob:; worker-src 'self' blob:; "
              "style-src 'self' 'unsafe-inline'")


def neuroglancer_client_dir() -> Path:
    """The installed Neuroglancer client folder (holds index.html), found without importing the package."""
    spec = importlib.util.find_spec("neuroglancer")
    for base in (spec.submodule_search_locations or []) if spec else []:
        client = Path(base) / "static" / "client"
        if (client / "index.html").is_file():
            return client.resolve()
    raise RuntimeError("the neuroglancer client is not installed")
