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
STATIC_DIR = Path(__file__).parent / "static"  # the trace viewer's own script and stylesheet (/viewer/assets/)
# Content-Security-Policy of the viewer's HTML pages. 'unsafe-eval': the client compiles code with `new Function`
# (annotation property serializers in neuroglancer's lib/annotation/index.js, msgpackr); without it the slices
# stay blank, with no console error. Scripts still load only from this origin (no inline scripts); no wasm is
# bundled, so no 'wasm-unsafe-eval'.
VIEWER_CSP = ("default-src 'self'; script-src 'self' 'unsafe-eval'; img-src 'self' data: blob:; "
              "worker-src 'self' blob:; style-src 'self' 'unsafe-inline'; frame-ancestors 'none'")


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
                compare: bool = False, index: int = 0) -> dict:
    """The Neuroglancer state for image `index` of a written plan entry (files: the entry's manifest), and when
    that image was defaced, its pre-deface original as a second layer, hidden until switched on. compare: the
    two side by side instead, each in its own panel."""
    rel = files[index]
    file = rel.rsplit("/", 1)[-1]
    name = file.removesuffix(".gz").removesuffix(".nii")
    url = f"{base}/qa/data/{quote(entry['id'], safe='')}/{index}/{quote(file)}"
    kind = kind_for(entry)
    layers = [nifti_layer(name, url, kind)]
    if originals and index < len(originals):
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
    """The QA index: one row per written image, {"id", "index", "path", "nifti", "defaced"}. BIDS paths only."""
    def row(r: dict) -> str:
        href = f"/viewer/entry/{quote(r['id'], safe='')}" + (f"?index={r['index']}" if r["index"] else "")
        links = []
        if r["nifti"]:
            links.append(f'<a href="{href}">Neuroglancer</a>')
            if r["defaced"]:
                sep = "&amp;" if r["index"] else "?"
                links.append(f'<a href="{href}{sep}compare=1">defaced vs original</a>')
        if r.get("traces"):
            links.append(f'<a class="qa-traces" href="/viewer/traces/{quote(r["id"], safe="")}">Traces</a>')
        out = f"<tr><td><code>{html.escape(r['path'])}</code></td><td>{' · '.join(links)}</td></tr>"
        if r.get("traces") and r.get("pngs"):
            out += ephys_row(r)
        return out

    body = ("".join(row(r) for r in rows) if rows
            else '<tr><td colspan="2">No images were written.</td></tr>')
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>aimport QA viewer</title>
<style>
body {{ font: 14px/1.5 system-ui, sans-serif; margin: 2rem; color: #1b1f24; }}
table {{ border-collapse: collapse; }}
td, th {{ padding: .35rem .8rem; border-bottom: 1px solid #d8dee4; text-align: left; vertical-align: top; }}
code {{ font-size: 13px; }}
{EPHYS_CSS}
</style></head>
<body><h1>aimport QA viewer</h1>
<p>The de-identified output, before upload. Defaced images open with the original as a hidden layer.</p>
<table><thead><tr><th>BIDS path</th><th>View</th></tr></thead><tbody>
{body}
</tbody></table></body></html>
"""


# --- electrophysiology: snapshots in the index and the trace viewer page ---

# brainlife-lite tokens, scoped to the ephys rows of the index
EPHYS_CSS = """\
.qa-ephys td { background: #f5f5f5; border-bottom: 1px solid #e2e8f0; }
.qa-thumbs { display: flex; flex-wrap: wrap; gap: .6rem; }
.qa-thumbs a { display: block; background: #fff; border: 1px solid #e2e8f0; border-radius: 6px; padding: 4px; }
.qa-thumbs img { display: block; height: 96px; width: auto; }
a.qa-traces { color: #fff; background: #3d6a92; border-radius: 6px; padding: .1rem .55rem; text-decoration: none;
  font-family: 'DM Sans', system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif; }"""


def ephys_row(r: dict) -> str:
    """The snapshot thumbnails of an electrophysiology recording (a row under its data file)."""
    eid = quote(r["id"], safe="")
    thumbs = "".join(f'<a href="/qa/png/{eid}/{k}.png"><img src="/qa/png/{eid}/{k}.png" alt="{k}"></a>'
                     for k in r["pngs"])
    return f'<tr class="qa-ephys"><td colspan="2"><div class="qa-thumbs">{thumbs}</div></td></tr>'


def traces_page(entry_id: str, bids_name: str) -> str:
    """The interactive trace viewer of a written recording: uPlot and traces.js from this origin, no inline
    script (VIEWER_CSP unchanged); the data come from /qa/traces/<entry id>."""
    eid = html.escape(entry_id, quote=True)
    name = html.escape(bids_name)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{name} · traces</title>
<link rel="stylesheet" href="/viewer/assets/uplot/uPlot.min.css">
<link rel="stylesheet" href="/viewer/assets/traces.css">
</head>
<body data-entry="{eid}">
<header class="tr-bar"><a class="tr-back" href="/viewer/">QA viewer</a><h1>{name}</h1></header>
<main class="tr-main">
<section class="tr-panel tr-controls" aria-label="window">
  <button type="button" id="tr-left" title="earlier (←)">◀</button>
  <button type="button" id="tr-right" title="later (→)">▶</button>
  <button type="button" id="tr-zin" title="zoom in: shorter window (+)">+</button>
  <button type="button" id="tr-zout" title="zoom out: longer window (−)">−</button>
  <label>start <input id="tr-t0" type="number" min="0" step="any"> s</label>
  <label>length <input id="tr-len" type="number" min="0.01" max="600" step="any"> s</label>
  <button type="button" id="tr-go" class="tr-primary">Show</button>
  <span id="tr-info" class="tr-muted"></span>
</section>
<details class="tr-panel tr-picker" id="tr-picker"><summary>Channels <span id="tr-count"></span></summary>
  <div id="tr-channels" class="tr-channel-list"></div>
  <button type="button" id="tr-apply" class="tr-primary">Apply</button>
</details>
<p id="tr-status" class="tr-muted" role="status"></p>
<section class="tr-panel tr-plot-panel"><div id="tr-scales" class="tr-muted"></div><div id="tr-plot"></div></section>
</main>
<script src="/viewer/assets/uplot/uPlot.iife.min.js"></script>
<script src="/viewer/assets/traces.js"></script>
</body></html>
"""
