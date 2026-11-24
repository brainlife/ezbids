"""The local QA viewer: the Neuroglancer client served by the engine itself (same origin, no third-party page).

The client is a standalone build of the pinned ``neuroglancer`` npm package (``aimport/viewer-client/``), made
by the image's node build stage into ``/opt/neuroglancer-client``; ``AIMPORT_NEUROGLANCER_DIR`` points elsewhere
(e.g. a build on the host).
"""
from __future__ import annotations

import os
from pathlib import Path

NEUROGLANCER_DIR = "/opt/neuroglancer-client"
# Content-Security-Policy of the viewer's HTML pages. 'unsafe-eval': the client compiles code with `new Function`
# (annotation property serializers in neuroglancer's lib/annotation/index.js, msgpackr); without it the slices
# stay blank, with no console error. Scripts still load only from this origin (no inline scripts); no wasm is
# bundled, so no 'wasm-unsafe-eval'.
VIEWER_CSP = ("default-src 'self'; script-src 'self' 'unsafe-eval'; img-src 'self' data: blob:; "
              "worker-src 'self' blob:; style-src 'self' 'unsafe-inline'")


def neuroglancer_client_dir() -> Path:
    """The built Neuroglancer client folder (holds index.html)."""
    client = Path(os.environ.get("AIMPORT_NEUROGLANCER_DIR") or NEUROGLANCER_DIR)
    if not (client / "index.html").is_file():
        raise RuntimeError("the neuroglancer client is not installed")
    return client.resolve()
