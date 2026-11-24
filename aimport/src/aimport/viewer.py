"""The local QA viewer: the Neuroglancer client served by the engine itself (same origin, no third-party page).

States reference only the engine's own origin (``base``): images come from ``/qa/data/``.

The client is a standalone build of the pinned ``neuroglancer`` npm package (``aimport/viewer-client/``), made
by the image's node build stage into ``/opt/neuroglancer-client``; ``AIMPORT_NEUROGLANCER_DIR`` points elsewhere
(e.g. a build on the host).
"""
from __future__ import annotations

import html
import json
import os
from pathlib import Path
from urllib.parse import quote

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


# Intensity presets for the image shader, as brainlife-lite's NEUROGLANCER_PRESETS (src/utils/neuroglancer.utils.ts);
# "default" leaves the range to Neuroglancer.
PRESETS: dict[str, dict] = {
    "bold": {"range": [0, 2000], "window": [-400, 2000]},
    "t1": {"range": [0, 1500], "window": [0, 1500]},
    "t2": {"range": [0, 3000], "window": [0, 3000]},
    "dwi": {"range": [0, 4000], "window": [0, 4000]},
    "default": {},
}
KINDS = {"T1w": "t1", "T2w": "t2", "FLAIR": "t2", "bold": "bold", "dwi": "dwi"}  # BIDS suffix -> preset


def kind_for(entry: dict) -> str:
    return KINDS.get(entry.get("suffix") or "", "default")


def _file_name(url: str) -> str:
    return url.split("?", 1)[0].rsplit("/", 1)[-1]


def nifti_layer(name: str, url: str, kind: str) -> dict:
    """An image layer for the NIfTI file at url (a .nii.gz is read through the gzip adapter)."""
    file = _file_name(url)
    source = url + ("|gzip:|nifti:" if file.endswith(".nii.gz") else "|nifti:")
    layer: dict = {"type": "image", "source": source, "name": name, "tab": "source"}
    preset = PRESETS.get(kind) or PRESETS["default"]
    if preset:
        layer["shaderControls"] = {"normalized": {"range": list(preset["range"]), "window": list(preset["window"])}}
    return layer


def entry_state(entry: dict, files: list[str], originals: list[str] | None, base: str,
                compare: bool = False) -> dict:
    """The Neuroglancer state for a written plan entry: its (first) image from the output, and for a defaced
    entry the pre-deface original as a second layer, hidden until switched on. compare (defaced entries): the
    two side by side instead, each in its own panel."""
    rel = files[0]
    file = rel.rsplit("/", 1)[-1]
    name = file.removesuffix(".gz").removesuffix(".nii")
    url = f"{base}/qa/data/{quote(entry['id'], safe='')}/0/{quote(file)}"
    kind = kind_for(entry)
    layers = [nifti_layer(name, url, kind)]
    if originals:
        original = nifti_layer(f"{name} (original)", url + "?which=original", kind)
        if compare:
            return {"layout": {"type": "row", "children": [
                {"type": "viewer", "layers": [name], "layout": "xy"},
                {"type": "viewer", "layers": [original["name"]], "layout": "xy"}]},
                "layers": [layers[0], original], "selectedLayer": {"visible": True, "layer": name}}
        original["visible"] = False
        layers.append(original)
    return {"layout": "4panel", "layers": layers, "selectedLayer": {"visible": True, "layer": name}}


def state_url(state: dict) -> str:
    return "/viewer/ng/#!" + quote(json.dumps(state, separators=(",", ":")))


def index_page(rows: list[dict]) -> str:
    """The QA index: one row per written entry, {"id", "paths", "nifti", "defaced"}. BIDS paths only."""
    def row(r: dict) -> str:
        eid = quote(r["id"], safe="")
        links = []
        if r["nifti"]:
            links.append(f'<a href="/viewer/entry/{eid}">Neuroglancer</a>')
            if r["defaced"]:
                links.append(f'<a href="/viewer/entry/{eid}?compare=1">defaced vs original</a>')
        paths = "<br>".join(f"<code>{html.escape(p)}</code>" for p in r["paths"])
        return f"<tr><td>{paths}</td><td>{' · '.join(links)}</td></tr>"

    body = ("".join(row(r) for r in rows) if rows
            else '<tr><td colspan="2">No images were written.</td></tr>')
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>aimport QA viewer</title>
<style>
body {{ font: 14px/1.5 system-ui, sans-serif; margin: 2rem; color: #1b1f24; }}
table {{ border-collapse: collapse; }}
td, th {{ padding: .35rem .8rem; border-bottom: 1px solid #d8dee4; text-align: left; vertical-align: top; }}
code {{ font-size: 13px; }}
</style></head>
<body><h1>aimport QA viewer</h1>
<p>The de-identified output, before upload. Defaced images open with the original as a hidden layer.</p>
<table><thead><tr><th>BIDS path</th><th>View</th></tr></thead><tbody>
{body}
</tbody></table></body></html>
"""
