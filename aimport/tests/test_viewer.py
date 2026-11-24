"""Neuroglancer states for the QA viewer (aimport.viewer)."""
import json
from urllib.parse import unquote

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
