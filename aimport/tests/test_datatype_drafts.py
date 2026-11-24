"""Draft brainlife datatypes for BIDS types that have no brainlife datatype (Task 7c)."""

import importlib.util
import json
import re
import shutil
from pathlib import Path

import pytest

from aimport import brainlife_map
from aimport.brainlife_map import draft_for, load_rows, to_brainlife

ROOT = Path(__file__).resolve().parents[1]
DRAFTS = ROOT / "src" / "aimport" / "data" / "datatype_drafts"
YAML_FILE = ROOT / "src" / "aimport" / "data" / "bids_brainlife_map.yaml"
NAME = re.compile(r"^neuro/[a-z0-9]+/[a-z0-9]+$")


def _tool():
    spec = importlib.util.spec_from_file_location("draft_datatypes", ROOT / "tools" / "draft_datatypes.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _drafts():
    files = sorted(DRAFTS.glob("*.json"))
    assert files, "no draft files generated"
    return [(f, json.loads(f.read_text())) for f in files]


def test_every_draft_validates():
    for f, d in _drafts():
        assert NAME.match(d["name"]), f
        assert f.name == d["name"].replace("/", ".") + ".json"
        assert d["draft"] is True and d["bids_version"] == "1.11.2"
        assert "DRAFT" in d["readme"] and "draft_datatypes.py" in d["readme"]
        assert "1.11.2" in d["readme"] and "registry" in d["readme"]
        assert d["datatype_tags"] == []
        files = d["files"]
        assert files, f
        if "Exactly one of:" in d["readme"]:
            assert not any(x["required"] for x in files if x["ext"] not in (".json",)), f
        else:
            assert any(x["required"] for x in files), f
        assert "Exactly one of:" not in d["readme"] or "Exactly one of:" in d["desc"], f
        assert d["readme"].count("DRAFT") == 1, f
        assert all(x["ext"] not in ("/", ".*") for x in files), f
        assert not any(m["src"].endswith(".*") or m["src"] in ("meg", "") for m in d["bids"]["maps"]), f
        assert len({x["id"] for x in files}) == len(files), f
        for x in files:
            assert ("filename" in x) != ("dirname" in x), f
        names = {x.get("filename") or x.get("dirname") for x in files}
        assert d["bids"]["derivatives"] == d["name"].split("/")[1]
        assert {m["src"] for m in d["bids"]["maps"]} == names, f
        assert all(m["src"] == m["dest"] for m in d["bids"]["maps"])


def _draft(name):
    return json.loads((DRAFTS / name).read_text())


def test_directory_extensions_become_dirname():
    d = _draft("neuro.anat.pdw.json")
    zarr = [x for x in d["files"] if x["id"] == "ome_zarr"][0]
    assert zarr["dirname"] == "PDw.ome.zarr" and not zarr["required"]


def test_single_format_has_exactly_one_required_data_file():
    d = _draft("neuro.mrs.svs.json")  # NIfTI only (.nii.gz/.nii are one format)
    req = [x["filename"] for x in d["files"] if x["required"] and x["ext"] != ".json"]
    assert req == ["svs.nii.gz"]
    assert "Exactly one of" not in d["readme"]
    n = _draft("neuro.nirs.nirs.json")
    assert [x["filename"] for x in n["files"] if x["required"] and x["ext"] != ".json"] == ["nirs.snirf"]


def test_multi_format_has_none_required_and_names_formats():
    d = _draft("neuro.ieeg.ieeg.json")
    assert not any(x["required"] for x in d["files"] if x["ext"] != ".json")
    for text in (d["readme"], d["desc"]):
        assert "Exactly one of:" in text
        assert ".vhdr + .eeg + .vmrk" in text and ".edf" in text and ".mefd" in text
    z = _draft("neuro.anat.pdw.json")
    assert "NIfTI" not in z["readme"] and ".nii.gz or .nii" in z["readme"] and ".ome.zarr" in z["readme"]
    assert not any(x["required"] for x in z["files"])


def test_required_sidecar_is_required_with_json_map():
    d = _draft("neuro.pet.pet.json")
    assert [x["required"] for x in d["files"] if x["id"] == "json"] == [True]
    maps = {m["src"]: m for m in d["bids"]["maps"]}
    assert maps["pet.nii.gz"]["json"] == "pet.json"
    assert "json" not in maps["pet.json"]


def test_optional_sidecar_still_mapped():
    d = _draft("neuro.anat.pdw.json")
    assert [x["required"] for x in d["files"] if x["id"] == "json"] == [False]
    assert {m["src"]: m for m in d["bids"]["maps"]}["PDw.nii.gz"]["json"] == "PDw.json"


def test_readme_lists_related_suffixes():
    assert "`blood`" in _draft("neuro.pet.pet.json")["readme"]
    r = _draft("neuro.perf.asl.json")["readme"]
    assert "`aslcontext`" in r and "`m0scan`" in r and "separate datatypes" in r


def test_wildcard_extension_skipped():
    d = _draft("neuro.meg.headshape.json")
    assert [x["filename"] for x in d["files"]] == ["headshape.pos"]


def test_tsv_only_suffix_has_tsv_required():
    d = json.loads((DRAFTS / "neuro.func.events.json").read_text())
    req = [x for x in d["files"] if x["required"]]
    assert [x["filename"] for x in req] == ["events.tsv"]


def test_generator_is_idempotent(tmp_path):
    tool = _tool()
    outs = []
    for n in (1, 2):
        out = tmp_path / f"out{n}"
        y = tmp_path / f"map{n}.yaml"
        shutil.copy(YAML_FILE, y)
        tool.main(["--out", str(out), "--yaml", str(y), "--write-yaml"])
        outs.append((out, y))
    (o1, y1), (o2, y2) = outs
    assert y1.read_bytes() == y2.read_bytes() == YAML_FILE.read_bytes()
    n1 = sorted(p.name for p in o1.glob("*.json"))
    assert n1 == sorted(p.name for p in o2.glob("*.json")) == sorted(p.name for p in DRAFTS.glob("*.json"))
    for name in n1:
        assert (o1 / name).read_bytes() == (o2 / name).read_bytes() == (DRAFTS / name).read_bytes()


def test_every_raw_pair_covered_exactly_once(schema):
    rows = load_rows()
    for (dt, suffix) in schema.raw_pairs():
        hits = [r for r in rows if brainlife_map.row_covers(r, dt, suffix)]
        assert len(hits) >= 1, (dt, suffix)
        drafts = [r for r in hits if r["status"] == "draft"]
        others = [r for r in hits if r["status"] != "draft"]
        # a pair is either drafted (exactly one draft row, no other row) or mapped (no draft)
        assert (len(drafts) == 1 and not others) or (not drafts and others), (dt, suffix, hits)


def test_draft_rows_shape():
    for r in load_rows():
        if r["status"] == "draft":
            assert r["brainlife"] == {"datatype": r["brainlife"]["datatype"], "tags": []}
            assert r["ref"] == "datatype_drafts/" + r["brainlife"]["datatype"].replace("/", ".") + ".json"
            assert (DRAFTS.parent / r["ref"]).exists()


def test_name_collision_fails_loudly():
    tool = _tool()
    with pytest.raises(ValueError, match="collide"):
        tool.check_collisions([("anat", "T1w"), ("anat", "t1w")])


def test_to_brainlife_ignores_drafts():
    assert to_brainlife("perf", "asl", {}, {}) == (None, [])
    assert to_brainlife("anat", "PDw", {}, {}) == (None, [])


def test_draft_for():
    assert draft_for("perf", "asl") == "neuro/perf/asl"
    assert draft_for("anat", "T1w") is None
    assert draft_for("nosuch", "x") is None
