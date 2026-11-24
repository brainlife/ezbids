import pytest

from aimport.brainlife_map import to_brainlife


@pytest.mark.parametrize(
    "datatype,suffix,expected",
    [
        ("anat", "T1w", ("neuro/anat/t1w", [])),
        ("anat", "T2w", ("neuro/anat/t2w", [])),
        ("anat", "FLAIR", ("neuro/anat/flair", [])),
        ("anat", "MP2RAGE", ("neuro/anat/mp2rage", [])),
        ("dwi", "dwi", ("neuro/dwi", [])),
        ("fmap", "epi", ("neuro/fmap", ["pepolar"])),
        ("fmap", "phasediff", ("neuro/fmap", ["phasediff"])),
        ("fmap", "magnitude1", ("neuro/fmap", ["phasediff"])),
        ("fmap", "magnitude2", ("neuro/fmap", ["phasediff"])),
        ("fmap", "phase1", ("neuro/fmap", ["2phasemag"])),
        ("fmap", "phase2", ("neuro/fmap", ["2phasemag"])),
        ("fmap", "fieldmap", ("neuro/fmap", ["single"])),
        ("fmap", "magnitude", ("neuro/fmap", ["single"])),
        ("pet", "pet", (None, [])),
        ("perf", "asl", (None, [])),
        ("func", "events", (None, [])),
    ],
)
def test_table(datatype, suffix, expected):
    assert to_brainlife(datatype, suffix, {}, {}) == expected


def test_bold_task_lowercased():
    assert to_brainlife("func", "bold", {"task": "RestingState"}, {}) == (
        "neuro/func/task",
        ["restingstate"],
    )


def test_bold_without_task_is_unknown():
    assert to_brainlife("func", "bold", {}, {}) == ("neuro/func/task", ["unknown"])


# --- data file (single source of truth) ---

from importlib import resources  # noqa: E402

import yaml  # noqa: E402

from aimport.brainlife_map import load_table  # noqa: E402


def _yaml_doc():
    text = resources.files("aimport.data").joinpath("bids_brainlife_map.yaml").read_text()
    return yaml.safe_load(text)


def test_yaml_is_packaged():
    assert resources.files("aimport.data").joinpath("bids_brainlife_map.yaml").is_file()


def test_yaml_loads_and_validates():
    table = load_table()
    assert ("anat", "T1w") in table


def test_every_active_row_round_trips():
    n = 0
    for row in _yaml_doc()["mappings"]:
        if row["status"] != "active":
            continue
        n += 1
        bl = row["brainlife"]
        got = to_brainlife(row["bids"]["datatype"], row["bids"]["suffix"], {"task": "Rest"}, {})
        want = ["rest"] if "tags_from" in bl else bl["tags"]
        assert got == (bl["datatype"], want)
    assert n >= 13


def _write(tmp_path, body):
    p = tmp_path / "m.yaml"
    p.write_text(body)
    return p


_ROW = "  - bids: {datatype: anat, suffix: T1w}\n    brainlife: {datatype: neuro/anat/t1w, tags: []}\n    status: active\n"


def test_duplicate_active_key_raises(tmp_path):
    with pytest.raises(ValueError, match="duplicate"):
        load_table(_write(tmp_path, "version: 1\nmappings:\n" + _ROW + _ROW))


def test_missing_tags_raises(tmp_path):
    row = "  - bids: {datatype: anat, suffix: T1w}\n    brainlife: {datatype: neuro/anat/t1w}\n    status: active\n"
    with pytest.raises(ValueError, match="anat/T1w"):
        load_table(_write(tmp_path, "version: 1\nmappings:\n" + row))


def test_bad_version_and_status_raise(tmp_path):
    with pytest.raises(ValueError, match="version"):
        load_table(_write(tmp_path, "version: 2\nmappings: []\n"))
    with pytest.raises(ValueError, match="status"):
        load_table(_write(tmp_path, "version: 1\nmappings:\n" + _ROW.replace("active", "soon")))


def test_wheel_contains_yaml(tmp_path):
    import shutil
    import subprocess
    import zipfile
    from pathlib import Path

    uv = shutil.which("uv")
    if uv is None:
        pytest.skip("uv not available to build the wheel")
    root = Path(__file__).resolve().parent.parent
    subprocess.run(
        [uv, "build", "--wheel", "--out-dir", str(tmp_path)],
        cwd=root, check=True, capture_output=True,
    )
    wheels = list(tmp_path.glob("*.whl"))
    assert wheels
    with zipfile.ZipFile(wheels[0]) as z:
        assert "aimport/data/bids_brainlife_map.yaml" in z.namelist()


def test_bool_version_raises(tmp_path):
    with pytest.raises(ValueError, match="version"):
        load_table(_write(tmp_path, "version: true\nmappings: []\n"))


def test_non_string_tag_and_suffix_raise(tmp_path):
    with pytest.raises(ValueError, match="strings"):
        load_table(_write(tmp_path, "version: 1\nmappings:\n" + _ROW.replace("tags: []", "tags: [1]")))
    with pytest.raises(ValueError, match="suffix"):
        load_table(_write(tmp_path, "version: 1\nmappings:\n" + _ROW.replace("suffix: T1w", "suffix: 1")))


def test_both_tags_and_tags_from_raise(tmp_path):
    row = _ROW.replace("tags: []", "tags: [], tags_from: task")
    with pytest.raises(ValueError, match="exactly one"):
        load_table(_write(tmp_path, "version: 1\nmappings:\n" + row))


def test_missing_bids_datatype_raises(tmp_path):
    row = _ROW.replace("datatype: anat, ", "")
    with pytest.raises(ValueError, match="bids.datatype"):
        load_table(_write(tmp_path, "version: 1\nmappings:\n" + row))


def test_active_row_without_suffix_raises(tmp_path):
    row = _ROW.replace(", suffix: T1w", "")
    with pytest.raises(ValueError, match="suffix"):
        load_table(_write(tmp_path, "version: 1\nmappings:\n" + row))
