"""Neuroglancer states for the QA viewer (aimport.viewer)."""
import json
from urllib.parse import unquote

import pytest

from aimport.viewer import PRESETS, entry_state, kind_for, nifti_layer, state_url

BASE = "http://127.0.0.1:8765"
T1W = {"id": "s0-sub0-ses0", "suffix": "T1w", "datatype": "anat"}
FILES = ["sub-01/ses-1/anat/sub-01_ses-1_T1w.nii.gz"]
ORIGINALS = ["sub-01/ses-1/anat/sub-01_ses-1_T1w.nii.gz"]


def test_nifti_suffix():
    url = BASE + "/qa/data/e/0/a"
    assert nifti_layer("a", url + ".nii.gz", "t1")["source"] == url + ".nii.gz|gzip:|nifti:"
    assert nifti_layer("a", url + ".nii", "t1")["source"] == url + ".nii|nifti:"
    assert nifti_layer("a", BASE + "/qa/data/e/0/a.nii.gz?which=original", "t1")["source"].endswith(
        "?which=original|gzip:|nifti:")


def test_presets():
    layer = nifti_layer("a", BASE + "/a.nii.gz", "bold")
    assert layer["shaderControls"]["normalized"] == {"range": [0, 2000], "window": [-400, 2000]}
    assert nifti_layer("a", BASE + "/a.nii.gz", "t1")["shaderControls"]["normalized"]["range"] == [0, 1500]
    assert "shaderControls" not in nifti_layer("a", BASE + "/a.nii.gz", "default")
    assert "shaderControls" not in nifti_layer("a", BASE + "/a.nii.gz", "unknown")
    assert set(PRESETS) == {"t1", "t2", "bold", "dwi", "default"}
    assert kind_for(T1W) == "t1" and kind_for({"suffix": "bold"}) == "bold" and kind_for({"suffix": None}) == "default"


def check(state):
    for layer in state["layers"]:
        assert layer["source"].startswith(BASE + "/qa/data/")
    text = json.dumps(state)
    assert "appspot" not in text
    assert text.count("http") == text.count(BASE)


def test_t1w_with_original():
    state = entry_state(T1W, FILES, ORIGINALS, BASE)
    assert state["layout"] == "4panel"
    defaced, original = state["layers"]
    assert defaced["name"] == "sub-01_ses-1_T1w" and original["name"] == "sub-01_ses-1_T1w (original)"
    assert original["visible"] is False and defaced.get("visible", True)
    assert defaced["source"] == BASE + "/qa/data/s0-sub0-ses0/0/sub-01_ses-1_T1w.nii.gz|gzip:|nifti:"
    assert original["source"] == BASE + "/qa/data/s0-sub0-ses0/0/sub-01_ses-1_T1w.nii.gz?which=original|gzip:|nifti:"
    check(state)


def test_multi_file_and_no_original():
    files = ["sub-01/func/sub-01_echo-1_bold.nii.gz", "sub-01/func/sub-01_echo-2_bold.nii.gz"]
    state = entry_state({"id": "e1", "suffix": "bold"}, files, None, BASE)
    assert len(state["layers"]) == 1 and state["layers"][0]["name"] == "sub-01_echo-1_bold"
    check(state)


def test_compare():
    state = entry_state(T1W, FILES, ORIGINALS, BASE, compare=True)
    panels = [c["layers"] for c in state["layout"]["children"]]
    assert panels == [["sub-01_ses-1_T1w"], ["sub-01_ses-1_T1w (original)"]]
    assert all(layer.get("visible", True) for layer in state["layers"])
    check(state)


def test_state_url():
    state = entry_state(T1W, FILES, ORIGINALS, BASE)
    url = state_url(state)
    assert url.startswith("/viewer/ng/#!")
    assert json.loads(unquote(url.removeprefix("/viewer/ng/#!"))) == state
    assert "token" not in url.lower()


def test_index_picks_the_image():
    files = ["sub-01/anat/sub-01_run-1_T1w.nii.gz", "sub-01/anat/sub-01_run-2_T1w.nii.gz"]
    state = entry_state(T1W, files, list(files), BASE, index=1)
    defaced, original = state["layers"]
    assert defaced["name"] == "sub-01_run-2_T1w" and original["name"] == "sub-01_run-2_T1w (original)"
    assert defaced["source"] == BASE + "/qa/data/s0-sub0-ses0/1/sub-01_run-2_T1w.nii.gz|gzip:|nifti:"
    assert original["source"].startswith(BASE + "/qa/data/s0-sub0-ses0/1/")
    # an image beyond the originals list was not defaced: no original layer
    assert len(entry_state(T1W, files, files[:1], BASE, index=1)["layers"]) == 1
    check(state)


# --- microscopy (OME-Zarr) ---

from aimport.micr.metadata import ChannelInfo, ImageInfo, ngff_attrs  # noqa: E402
from aimport.viewer import oct_group, zarr_layer  # noqa: E402

WIN = [{"min": 0.0, "max": 65535.0, "start": 100.0, "end": 900.0},
       {"min": 0.0, "max": 65535.0, "start": 50.0, "end": 400.0}]


def _attrs(version="0.5", axes="czyx", shape=(2, 4, 64, 64), windows=WIN, channels=None):
    info = ImageInfo(family="ome-tiff", axes=axes, shape=shape, dtype="uint16",
                     pixel_size={"x": 0.5, "y": 0.5, "z": 2.0}, pixel_unit="um",
                     channels=channels or [ChannelInfo(488.0, 520.0, "ch488"),
                                           ChannelInfo(561.0, 600.0, "ch561")])
    return ngff_attrs(info, version, [{}, {"x": 2, "y": 2}], windows)


@pytest.mark.parametrize("version,codec", [("0.5", "|zarr3:"), ("0.4", "|zarr2:")])
def test_zarr_layer_channels_additive(version, codec):
    url = BASE + "/qa/data/e/0/"
    got = zarr_layer("img", url, _attrs(version), version)
    layers = got["layers"]
    assert len(layers) == 2
    for i, layer in enumerate(layers):
        assert layer["type"] == "image" and layer["source"] == url + codec
        assert layer["blend"] == "additive"
        assert layer["localDimensions"] == {"c'": [1, ""]} and layer["localPosition"] == [i + 0.5]
    assert layers[0]["shaderControls"]["normalized"]["range"] == [100.0, 900.0]
    assert layers[1]["shaderControls"]["normalized"]["range"] == [50.0, 400.0]
    assert layers[0]["shaderControls"]["color"] == "#00ff00"  # 520 nm emission: the omero colour
    assert layers[1]["shaderControls"]["color"] == "#ff8000"
    # x, y first (then z): the main panel is the xy plane
    assert list(got["dimensions"]) == ["x", "y", "z"]
    assert got["dimensions"]["x"] == [0.5e-6, "m"] and got["dimensions"]["z"] == [2e-6, "m"]


def test_zarr_layer_single_channel_grayscale():
    attrs = _attrs(axes="yx", shape=(64, 48), windows=[{"min": 0, "max": 1, "start": 0.1, "end": 0.7}],
                   channels=[ChannelInfo(None, None, "ch0")])
    layers = zarr_layer("en", BASE + "/qa/data/e/0/", attrs, "0.5")["layers"]
    assert len(layers) == 1
    assert "localDimensions" not in layers[0] and "blend" not in layers[0]
    assert "emitGrayscale" in layers[0]["shader"]
    assert layers[0]["shaderControls"]["normalized"]["range"] == [0.1, 0.7]


def _oct(contrast, sample="slice051", subject="01", chunk=None):
    ent = {"sample": sample, "acquisition": contrast}
    if chunk:
        ent["chunk"] = chunk
    return {"id": f"m-{contrast}-{sample}-{chunk}", "suffix": "OCT", "modality": "micr", "subject": subject,
            "session": None, "entities": ent}


def test_oct_group():
    entries = [_oct(c) for c in ("cross", "retardance", "reflectivity", "opticaxis")]
    entries += [_oct("retardance", sample="slice052"), _oct("retardance", subject="02"),
                {"id": "conf", "suffix": "CONF", "modality": "micr", "subject": "01", "session": None,
                 "entities": {"sample": "slice051"}}]
    group = oct_group(entries[1], entries)
    assert [e["entities"]["acquisition"] for e in group] == ["reflectivity", "retardance", "opticaxis", "cross"]
    assert oct_group(entries[-1], entries) == [entries[-1]]  # not OCT: alone
    assert oct_group(entries[4], entries) == [entries[4]]


def _images(entries, attrs=None):
    return [{"id": e["id"], "index": 0, "file": f"sub-01/micr/sub-01_sample-slice051_acq-{e['entities']['acquisition']}_OCT.ome.zarr",
             "attrs": attrs or _attrs(axes="yx", shape=(64, 48), windows=[{"min": 0, "max": 1, "start": 0, "end": 1}],
                                      channels=[ChannelInfo(None, None, "ch0")])}
            for e in entries]


def test_oct_grouped_state():
    entries = [_oct(c) for c in ("reflectivity", "retardance", "opticaxis", "cross")]
    state = entry_state(entries[1], [], None, BASE, zarr=_images(entries))
    assert len(state["layers"]) == 4
    assert all("blend" not in layer for layer in state["layers"])  # never an additive blend of contrasts
    panels = [p for row in state["layout"]["children"] for p in row["children"]]
    assert len(panels) == 4
    assert [p["layers"] for p in panels] == [[layer["name"]] for layer in state["layers"]]
    assert all(p["type"] == "viewer" and p["layout"] == "xy" for p in panels)
    assert [layer["name"].rsplit("acq-", 1)[1] for layer in state["layers"]] == [
        "reflectivity_OCT", "retardance_OCT", "opticaxis_OCT", "cross_OCT"]
    assert state["selectedLayer"]["layer"] == state["layers"][1]["name"]  # the entry asked for
    check(state)


def test_zarr_layer_sources_same_origin():
    entries = [_oct(c) for c in ("reflectivity", "retardance")]
    state = entry_state(entries[0], [], None, BASE, zarr=_images(entries))
    for layer in state["layers"]:
        assert layer["source"].startswith(BASE + "/qa/data/")
        assert layer["source"].endswith("/|zarr3:")
    text = json.dumps(state).lower()
    assert "amazonaws" not in text and "appspot" not in text and "token" not in text and "s3://" not in text
    check(state)


def test_single_micr_image_state():
    img = {"id": "conf", "index": 0, "file": "sub-01/micr/sub-01_sample-A_CONF.ome.zarr", "attrs": _attrs()}
    state = entry_state({"id": "conf", "suffix": "CONF", "modality": "micr"}, [img["file"]], None, BASE, zarr=[img])
    assert len(state["layers"]) == 2 and state["layout"] == "4panel"
    assert list(state["dimensions"]) == ["x", "y", "z"]
    assert state["layers"][0]["source"] == BASE + "/qa/data/conf/0/|zarr3:"
    two_d = dict(img, attrs=_attrs(axes="yx", shape=(64, 48), windows=WIN[:1], channels=[ChannelInfo(None, None, "ch0")]))
    assert entry_state({"id": "conf"}, [img["file"]], None, BASE, zarr=[two_d])["layout"] == "xy"


def test_multichannel_oct_store_split_into_panels():
    """A PS-OCT store whose channels are the contrasts (the CMC OME-Zarr): one grayscale panel per channel."""
    img = {"id": "oct", "index": 0, "file": "sub-01/micr/sub-01_sample-slice051_OCT.ome.zarr", "attrs": _attrs()}
    state = entry_state({"id": "oct", "suffix": "OCT"}, [img["file"]], None, BASE, zarr=[img])
    assert len(state["layers"]) == 2 and all("blend" not in layer for layer in state["layers"])
    assert all("emitGrayscale" in layer["shader"] for layer in state["layers"])
    assert [p["layers"] for p in state["layout"]["children"]] == [[layer["name"]] for layer in state["layers"]]
    assert [layer["localPosition"] for layer in state["layers"]] == [[0.5], [1.5]]


def test_view_fits_the_plane():
    img = {"id": "c", "index": 0, "file": "sub-01/micr/x_CONF.ome.zarr", "shape_xy": [11000, 8500],
           "attrs": _attrs(axes="yx", shape=(8500, 11000), windows=WIN[:1], channels=[ChannelInfo(None, None, "ch0")])}
    assert entry_state({"id": "c"}, [], None, BASE, zarr=[img])["crossSectionScale"] == 11000 / 800
    assert "crossSectionScale" not in entry_state({"id": "c"}, [], None, BASE, zarr=[dict(img, shape_xy=None)])
