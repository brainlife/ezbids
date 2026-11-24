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


# --- microscopy: OME-Zarr images ---------------------------------------------------------------

# NGFF axis units -> Neuroglancer's (factor to the base unit, base unit)
_NG_UNITS = {"millimeter": (1e-3, "m"), "micrometer": (1e-6, "m"), "nanometer": (1e-9, "m"),
             "meter": (1.0, "m"), "second": (1.0, "s"), "millisecond": (1e-3, "s")}
_DIMENSION_ORDER = ("x", "y", "z", "t")  # x and y first: the main panel is the xy plane
OCT_CONTRASTS = ("reflectivity", "retardance", "opticaxis", "cross")  # PS-OCT contrasts: one panel each
_GRAY_SHADER = "#uicontrol invlerp normalized\nvoid main() {\n  emitGrayscale(normalized());\n}\n"
_COLOR_SHADER = ("#uicontrol invlerp normalized\n#uicontrol vec3 color color(default=\"white\")\n"
                 "void main() {\n  emitRGB(color * normalized());\n}\n")


def ngff_parts(attrs: dict) -> tuple[dict, dict]:
    """(the first multiscale, the omero block or {}) of NGFF group attributes (0.5: under "ome"; 0.4: top)."""
    ome = attrs.get("ome") if isinstance(attrs.get("ome"), dict) else attrs
    multiscales = ome.get("multiscales") or [{}]
    omero = ome.get("omero") if isinstance(ome.get("omero"), dict) else {}
    return multiscales[0], omero


def ngff_version(attrs: dict) -> str:
    return "0.5" if isinstance(attrs.get("ome"), dict) else "0.4"


def _dimensions(multiscale: dict) -> dict:
    axes = [a.get("name") for a in multiscale.get("axes") or []]
    units = {a.get("name"): a.get("unit") for a in multiscale.get("axes") or []}
    datasets = multiscale.get("datasets") or [{}]
    scale = next((t.get("scale") for t in datasets[0].get("coordinateTransformations") or []
                  if t.get("type") == "scale"), None) or [1.0] * len(axes)
    out = {}
    for name in _DIMENSION_ORDER:
        if name in axes:
            factor, unit = _NG_UNITS.get(units.get(name) or "", (1.0, "s" if name == "t" else "m"))
            out[name] = [float(scale[axes.index(name)]) * factor, unit]
    return out


def zarr_layer(name: str, url: str, info: dict, version: str, blend: bool = True) -> dict:
    """The image layers of the OME-Zarr group at url (info: its NGFF group attributes, as written), as
    ``{"layers": [...], "dimensions": {...}}``. The source is ``url|zarr3:`` (NGFF 0.5) or ``url|zarr2:`` (0.4).
    One layer per channel; several are blended additively, each in its omero colour (blend=False: grayscale and
    not blended, for channels that are separate PS-OCT contrasts, each shown in its own panel). Each shader window
    is the omero channel window (start..end). The dimensions put x and y first."""
    multiscale, omero = ngff_parts(info)
    source = url + ("|zarr3:" if version == "0.5" else "|zarr2:")
    has_c = "c" in [a.get("name") for a in multiscale.get("axes") or []]
    channels = omero.get("channels") or []
    count = max(1, len(channels)) if has_c else 1
    layers = []
    for i in range(count):
        ch = channels[i] if i < len(channels) else {}
        label = ch.get("label") or f"ch{i}"
        layer: dict = {"type": "image", "source": source, "name": name if count == 1 else f"{name} {label}",
                       "tab": "rendering", "shader": _GRAY_SHADER}
        controls: dict = {}
        window = ch.get("window") or {}
        if all(isinstance(window.get(k), (int, float)) for k in ("start", "end")) and window["end"] > window["start"]:
            controls["normalized"] = {"range": [float(window["start"]), float(window["end"])]}
        if count > 1 and blend:
            color = str(ch.get("color") or "").lower()
            layer["shader"] = _COLOR_SHADER
            controls["color"] = "#" + (color if len(color) == 6 else "ffffff")
            layer["blend"] = "additive"
        if has_c:
            layer["localDimensions"] = {"c'": [1, ""]}
            # an integer: Neuroglancer rounds a channel position, so i + 0.5 would show channel i + 1 (checked in
            # Chromium on the 4-channel CMC PS-OCT store: i + 0.5 drew the next contrast, the last one blank)
            layer["localPosition"] = [i]
        if controls:
            layer["shaderControls"] = controls
        layers.append(layer)
    return {"layers": layers, "dimensions": _dimensions(multiscale)}


def oct_group(entry: dict, entries: list[dict]) -> list[dict]:
    """The PS-OCT contrasts shown with entry: the written OCT entries of its subject, session and sample (and
    chunk and run), one per contrast, in OCT_CONTRASTS order. Any other entry is shown alone."""
    def key(e: dict) -> tuple | None:
        ent = e.get("entities") or {}
        if e.get("suffix") != "OCT" or ent.get("acquisition") not in OCT_CONTRASTS:
            return None
        return (e.get("subject"), e.get("session"), ent.get("sample"), ent.get("chunk"), ent.get("run"))

    k = key(entry)
    if k is None:
        return [entry]
    group: dict[str, dict] = {entry["entities"]["acquisition"]: entry}
    for e in entries:
        if key(e) == k:
            group.setdefault(e["entities"]["acquisition"], e)
    return [group[c] for c in OCT_CONTRASTS if c in group]


def _grid(panels: list[dict]) -> dict:
    """Panels in rows of two."""
    rows = [{"type": "row", "children": panels[i:i + 2]} for i in range(0, len(panels), 2)]
    return rows[0] if len(rows) == 1 else {"type": "column", "children": rows}


def zarr_state(images: list[dict], base: str, selected: str | None = None, oct: bool = False) -> dict:
    """The state for written OME-Zarr images, each ``{"id", "index", "file", "attrs"[, "shape_xy"]}`` (its plan
    entry, manifest index, BIDS path, written group attributes and level-0 x, y sizes, used to fit the view). One image: its channels in an xy layout (with the orthogonal
    planes for a 3-D image). Several (the contrasts of one PS-OCT sample): each in its own xy panel, never
    blended together; likewise the channels of one PS-OCT image (suffix OCT: its channels are contrasts).
    selected: the entry whose layer is selected (default the first)."""
    layers: list[dict] = []
    panels: list[dict] = []
    dimensions: dict = {}
    chosen = None
    for img in images:
        name = img["file"].rsplit("/", 1)[-1].removesuffix(".ome.zarr")
        url = f"{base}/qa/data/{quote(img['id'], safe='')}/{int(img['index'])}/"
        got = zarr_layer(name, url, img["attrs"], ngff_version(img["attrs"]), blend=not oct)
        layers += got["layers"]
        if oct:
            panels += [{"type": "viewer", "layers": [layer["name"]], "layout": "xy"} for layer in got["layers"]]
        else:
            panels.append({"type": "viewer", "layers": [layer["name"] for layer in got["layers"]], "layout": "xy"})
        for k, v in got["dimensions"].items():
            dimensions.setdefault(k, v)
        if chosen is None and img["id"] == selected:
            chosen = got["layers"][0]["name"]
    if len(panels) > 1:
        layout: dict | str = _grid(panels)
    else:
        layout = "4panel" if "z" in dimensions else "xy"
    state = {"dimensions": dimensions, "layout": layout, "layers": layers, "crossSectionBackgroundColor": "#000000",
             "selectedLayer": {"visible": True, "layer": chosen or layers[0]["name"]}}
    # zoom out to the whole plane (Neuroglancer opens at one voxel per screen pixel): voxels per screen pixel
    extents = [max(int(n) for n in img["shape_xy"]) for img in images if img.get("shape_xy")]
    if extents:
        small = len(panels) > 1 or layout == "4panel"
        state["crossSectionScale"] = max(1.0, max(extents) / (400 if small else 800))
    return state


def entry_state(entry: dict, files: list[str], originals: list[str] | None, base: str,
                compare: bool = False, index: int = 0, zarr: list[dict] | None = None) -> dict:
    """The Neuroglancer state for image `index` of a written plan entry (files: the entry's manifest), and when
    that image was defaced, its pre-deface original as a second layer, hidden until switched on. compare: the
    two side by side instead, each in its own panel. zarr: for a microscopy entry, the OME-Zarr images to show
    instead (zarr_state; the server passes the entry's PS-OCT contrast group, oct_group)."""
    if zarr:
        return zarr_state(zarr, base, selected=entry.get("id"), oct=entry.get("suffix") == "OCT")
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
    """The QA index: one row per written image, {"id", "index", "path", "nifti", "defaced"} and, for microscopy,
    "zarr" (an OME-Zarr) and "reference" (its chunks are read from the source). BIDS paths only."""
    def row(r: dict) -> str:
        href = f"/viewer/entry/{quote(r['id'], safe='')}" + (f"?index={r['index']}" if r["index"] else "")
        links = []
        if r.get("zarr"):
            links.append(f'<a href="{href}">Neuroglancer (OME-Zarr)</a>'
                         + (" (read from source)" if r.get("reference") else ""))
        if r["nifti"]:
            links.append(f'<a href="{href}">Neuroglancer</a>')
            if r["defaced"]:
                sep = "&amp;" if r["index"] else "?"
                links.append(f'<a href="{href}{sep}compare=1">defaced vs original</a>')
        return f"<tr><td><code>{html.escape(r['path'])}</code></td><td>{' · '.join(links)}</td></tr>"

    body = ("".join(row(r) for r in rows) if rows
            else '<tr><td colspan="2">No images were written.</td></tr>')
    # brainlife-lite look; no font is fetched (DM Sans when installed, else the system stack) and the logo
    # is the engine's own /viewer/brainlife-mark.svg: the page's CSP stays 'self'
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>aimport QA viewer</title>
<style>
:root {{ --primary: #3d6a92; --ink: #1d2230; --muted: #5b6573; --line: #e3e6ea; }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; background: #f5f5f5; color: var(--ink);
  font: 14px/1.5 "DM Sans", system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; }}
header {{ display: flex; align-items: center; gap: 12px; height: 56px; padding: 0 24px; background: #fff;
  border-bottom: 1px solid var(--line); }}
header .mark {{ height: 32px; width: auto; }}
header .brand {{ font-weight: 600; font-size: 15px; color: var(--ink); }}
header .sep {{ width: 1px; height: 22px; background: var(--line); }}
header .app {{ font-weight: 600; font-size: 15px; color: var(--primary); }}
main {{ max-width: 1100px; margin: 24px auto; padding: 0 16px; }}
.panel {{ background: #fff; border: 1px solid var(--line); border-radius: 6px; padding: 20px 24px; }}
h1 {{ margin: 0 0 4px; font-size: 20px; font-weight: 600; }}
p.lead {{ margin: 0 0 16px; color: var(--muted); }}
table {{ width: 100%; border-collapse: collapse; }}
th {{ font-size: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: .04em; color: var(--muted); }}
td, th {{ padding: 8px 10px; border-bottom: 1px solid var(--line); text-align: left; vertical-align: top; }}
tbody tr:hover {{ background: #f8fafc; }}
code {{ font: 13px/1.4 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; word-break: break-all; }}
a {{ color: var(--primary); text-decoration: none; font-weight: 500; }}
a:hover {{ text-decoration: underline; }}
</style></head>
<body><header><img class="mark" src="/viewer/brainlife-mark.svg" alt="brainlife.io">
<span class="brand">brainlife.io</span><span class="sep"></span><span class="app">aimport QA viewer</span></header>
<main><div class="panel"><h1>Output to check before upload</h1>
<p class="lead">The de-identified output, before upload. Defaced images open with the original as a hidden layer.
Microscopy images open as OME-Zarr; a reference dataset is read from its source, never copied.</p>
<table><thead><tr><th>BIDS path</th><th>View</th></tr></thead><tbody>
{body}
</tbody></table></div></main></body></html>
"""
