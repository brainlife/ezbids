"""Task 6: microscopy scan records and plan entries (micr/module.py), the planner hook, mapping rows."""
from __future__ import annotations

import copy
import json
import shutil
import time
from dataclasses import asdict
from pathlib import Path

import numpy as np
import pytest
import tifffile

from aimport import modality, server
from aimport.brainlife_map import to_brainlife
from aimport.ezbids_runner import CoreResult, parse_core
from aimport.micr import module as micr_module
from aimport.micr.module import MICR_INDEX_BASE, RAW_REASON, MicrModule
from aimport.planner import MICR_DATATYPE_REASON, UNVERIFIED, apply_plan_edits, build_plan
from aimport.pseudonyms import PseudonymKey
from conftest import MICR_PLANTED, tokens
from test_micr_remote import local_servers  # noqa: F401 - the local Range server fixture
from fixtures.micr_fixtures import (PSOCT_CONTRASTS, cmc_tree, ome_zarr, planted_ome_tiff,
                                    psoct_nifti)

FIXTURES = Path(__file__).parent / "fixtures"
CONTRAST_FOLDERS = ("Reflectivity", "Retardance", "Orientation", "Cross")
# the real CMC acqinfo_metadata.json key names (DATASETS.md), synthetic values
ACQINFO = {"version": "0.0.3", "channels": [1], "excitation_wavelengths": ["488nm"],
           "positions": [{"x_start_um": 0, "x_end_um": 10, "y_start_um": 0, "z_start_um": 0, "x_step_um": 2.5}],
           "settings": {"sheet_angle": 45, "pixel_spacing_um": 0.96, "image_size_xy": [32, 32],
                        "frames_per_file": 4, "dtype": "uint16"}}


def micr_input(root: Path) -> Path:
    """cmc_tree with readable stand-ins: PS-OCT NIfTIs, OME-Zarr stores, two VISoR positions, and a
    planted OME-TIFF in H17_250215/."""
    cmc_tree(root)
    for contrast, folder in zip(PSOCT_CONTRASTS, CONTRAST_FOLDERS):
        psoct_nifti(root / "PS-OCT/Enface/Registration" / folder / "Slice_051_1.nii.gz", contrast)
    shutil.rmtree(root / "Moe_Slice_051.ome.zarr")
    ome_zarr(root / "Moe_Slice_051.ome.zarr", "0.5")
    shutil.rmtree(root / "exaSPIM.zarr")
    ome_zarr(root / "exaSPIM.zarr" / "Pos0", "0.4")
    visor = root / "MN27_20250422_visor_488"
    for pos in (0, 1):
        tile = visor / f"visor_488_Pos{pos}" / "visor_488_0001.tif"
        tile.parent.mkdir(parents=True, exist_ok=True)
        tifffile.imwrite(str(tile), np.zeros((4, 32, 32), dtype=np.uint16), photometric="minisblack",
                         metadata=None)
    (visor / "acqinfo_metadata.json").write_text(json.dumps(ACQINFO))
    planted_ome_tiff(root / "H17_250215" / "stack.ome.tif")
    return root


@pytest.fixture
def key(tmp_path):
    k = PseudonymKey.load(tmp_path / "keys", "proj")
    yield k
    k.close()


@pytest.fixture
def inp(tmp_path):
    return micr_input(tmp_path / "in")


def scan(inp: Path, work: Path, progress=None) -> tuple[MicrModule, modality.Claim]:
    m = MicrModule()
    claim = m.claim(inp, [])
    m.scan(inp, claim, work / "micr", progress or (lambda msg: None))
    return m, claim


def make_plan(inp, tmp_path, key, schema, core=None, target="bids"):
    work = tmp_path / "work"
    m, claim = scan(inp, work)
    return build_plan(core or CoreResult(), inp, key, set(), None, schema, target, exclude=claim.roots,
                      extra_terms=frozenset(m.terms(work / "micr")),
                      planners=[lambda: m.plan(work / "micr", key, set(), None, schema, target)])


def micr(plan):
    return [e for e in plan.entries if e.modality == "micr"]


def test_records_local_with_progress(inp, tmp_path):
    seen = []
    scan(inp, tmp_path / "work", seen.append)
    records = json.loads((tmp_path / "work" / "micr" / "records.json").read_text())
    n = len(records)
    assert seen == [f"reading microscopy metadata ({k} of {n})" for k in range(1, n + 1)]
    for msg in seen:
        assert not tokens(msg)
    # one record per image or tile group: 4 NIfTI, raw folder, 2 VISoR positions, 2 stores, OME-TIFF
    assert n == 10
    assert all(set(r) >= {"rel", "family", "group", "facts", "info", "terms"} for r in records)
    visor = [r for r in records if r["family"] == "visor"]
    assert len(visor) == 2 and all(len(r["members"]) == 1 for r in visor)
    tiff = next(r for r in records if r["family"] == "ome-tiff")
    assert tiff["info"]["acquired"] == "2025-02-15"  # local records only
    assert {"Jane Doe", "H17"} <= set(tiff["terms"])


def test_psoct_entries(inp, tmp_path, key, schema):
    plan = make_plan(inp, tmp_path, key, schema)
    octs = [e for e in micr(plan) if e.entities.get("sample") == "slice051" and "acquisition" in e.entities]
    assert len(octs) == 4
    assert {e.entities["acquisition"] for e in octs} == {"reflectivity", "retardance", "opticaxis", "cross"}
    for e in octs:
        assert e.suffix == "OCT" and e.datatype == "micr" and e.status == "ok" and not e.exclude
        assert e.deface is False and e.write_mode == "convert" and e.sample_type == "tissue"
        assert (e.brainlife_datatype, e.brainlife_tags) == ("neuro/ome-zarr", ["OCT"])
        assert "chunk" not in e.entities
    assert len({e.subject for e in octs}) == 1


def test_raw_dat_excluded(inp, tmp_path, key, schema):
    raw = [e for e in micr(make_plan(inp, tmp_path, key, schema)) if e.reason == RAW_REASON]
    assert len(raw) == 1
    (e,) = raw
    assert e.status == "unsupported" and e.exclude and e.write_mode == "" and e.output_bytes == 0


def test_visor_chunks(inp, tmp_path, key, schema):
    plan = make_plan(inp, tmp_path, key, schema)
    visor = [e for e in micr(plan) if e.entities.get("stain") == "ch488"]
    assert len(visor) == 2
    assert {e.entities["chunk"] for e in visor} == {"0", "1"}
    assert len({e.entities["sample"] for e in visor}) == 1
    for e in visor:
        assert e.suffix == "SPIM" and e.status == "ok" and e.write_mode == "convert" and e.output_bytes > 0
    assert any(w.startswith("conversion writes about ") and w.endswith(" GB to the work folder")
               for w in plan.warnings)


def test_ome_zarr_reference(inp, tmp_path, key, schema):
    stores = [e for e in micr(make_plan(inp, tmp_path, key, schema)) if e.description.startswith("OME-Zarr")]
    assert len(stores) == 2
    for e in stores:
        assert e.write_mode == "reference" and e.output_bytes == 0
        assert e.description.endswith("; reference (no copy)")
    exaspim = next(e for e in stores if e.suffix == "SPIM")
    assert exaspim.description.startswith("OME-Zarr 0.4, 2 channels, 64×64×8, 0.5 µm")


def test_donor_pseudonymised(inp, tmp_path, key, schema):
    plan = make_plan(inp, tmp_path, key, schema)
    for donor in ("H17", "MN27", "Moe"):
        assert f"micr:id={donor}" in key.subjects
    subjects = {e.subject for e in micr(plan)}
    assert {key.subjects[f"micr:id={d}"] for d in ("H17", "MN27", "Moe")} <= subjects
    first = dict(key.subjects)
    again = make_plan(inp, tmp_path, key, schema)  # re-import: the key gives the same IDs
    for donor in ("H17", "MN27", "Moe"):
        assert key.subjects[f"micr:id={donor}"] == first[f"micr:id={donor}"]
    assert {e.subject for e in micr(again)} >= {first[f"micr:id={d}"] for d in ("H17", "MN27", "Moe")}
    # donor-less input (PS-OCT, exaSPIM) gets run-local identities and a warning
    assert any(w.startswith("microscopy: no donor code") for w in plan.warnings)


def test_no_identifiers_in_plan(inp, tmp_path, key, schema):
    plan = make_plan(inp, tmp_path, key, schema)
    text = json.dumps(asdict(plan))
    assert not MICR_PLANTED & tokens(text)
    for word in ("MN27", "Registration", "visor_488", "Slice_051", ".zarr", ".tif", ".nii", "acquired"):
        assert word not in text
    assert not any(UNVERIFIED.format(why="no DICOM headers were read") == w for w in plan.warnings)


def test_brainlife_mapping(tmp_path):
    assert to_brainlife("micr", "OCT", {}, {}) == ("neuro/ome-zarr", ["OCT"])
    for suffix in ("TEM", "SEM", "uCT", "BF", "DF", "PC", "DIC", "FLUO", "CONF", "PLI", "CARS", "2PE", "MPE",
                   "SR", "NLO", "OCT", "SPIM", "XPCT"):
        assert to_brainlife("micr", suffix, {}, {}) == ("neuro/ome-zarr", [suffix])
    import importlib.util

    tool_path = Path(__file__).resolve().parents[1] / "tools" / "draft_datatypes.py"
    spec = importlib.util.spec_from_file_location("draft_datatypes_t6", tool_path)
    tool = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tool)
    yaml = tmp_path / "m.yaml"
    shutil.copy(tool.DEFAULT_YAML, yaml)
    tool.main(["--out", str(tmp_path / "out"), "--yaml", str(yaml)])
    assert not [p.name for p in (tmp_path / "out").glob("neuro.micr.*")]


def test_edit_micr_entry(inp, tmp_path, key, schema):
    plan = make_plan(inp, tmp_path, key, schema)
    e = next(e for e in micr(plan) if e.suffix == "SPIM" and e.write_mode == "convert")
    apply_plan_edits(plan, [{"id": e.id, "suffix": "CONF"}], schema)
    assert e.status == "ok" and not e.exclude and e.brainlife_tags == ["CONF"]
    apply_plan_edits(plan, [{"id": e.id, "datatype": "anat"}], schema)
    assert e.status == "unknown" and e.exclude and e.reason == MICR_DATATYPE_REASON
    apply_plan_edits(plan, [{"id": e.id, "datatype": "micr"}], schema)
    assert e.status == "ok" and not e.exclude
    with pytest.raises(ValueError):
        apply_plan_edits(plan, [{"id": e.id, "sample_type": "bogus"}], schema)
    with pytest.raises(ValueError):
        apply_plan_edits(plan, [{"id": e.id, "sample_type": None}], schema)
    with pytest.raises(ValueError):
        apply_plan_edits(plan, [{"id": e.id, "deface": True}], schema)
    assert e.deface is False
    assert e.sample_type == "tissue"
    apply_plan_edits(plan, [{"id": e.id, "sample_type": "organoid"}], schema)
    assert e.sample_type == "organoid"
    raw = next(x for x in micr(plan) if x.reason == RAW_REASON)
    apply_plan_edits(plan, [{"id": raw.id, "suffix": "OCT", "exclude": False}], schema)
    assert raw.status == "unsupported"  # unreadable input is never written


def test_unknown_suffix_then_edited(inp, tmp_path, key, schema):
    plan = make_plan(inp, tmp_path, key, schema)
    e = next(e for e in micr(plan) if e.description.startswith("OME-TIFF"))
    assert e.suffix is None and e.status == "unknown" and e.exclude
    apply_plan_edits(plan, [{"id": e.id, "suffix": "CONF"}], schema)
    assert e.status == "ok" and not e.exclude


def test_acquisition_mode_suffix():
    rec = {"family": "ome-tiff", "facts": {}, "info": {"acquisition_mode": "LaserScanningConfocalMicroscopy"}}
    assert micr_module._suffix(rec, set())[0] == "CONF"
    rec["info"]["acquisition_mode"] = "SingleMoleculeImaging"
    assert micr_module._suffix(rec, set())[0] is None


def test_indices_do_not_collide(inp, tmp_path, key, schema):
    core = copy.deepcopy(parse_core(FIXTURES / "ezbids_core_siemens.json"))
    plan = make_plan(inp, tmp_path, key, schema, core=core)
    mri = [e for e in plan.entries if e.modality == "mri"]
    assert mri and micr(plan)
    assert not {e.subject_idx for e in mri} & {e.subject_idx for e in micr(plan)}
    assert all(e.subject_idx >= MICR_INDEX_BASE and e.series_idx >= MICR_INDEX_BASE for e in micr(plan))
    assert len({e.id for e in plan.entries}) == len(plan.entries)
    # MRI subject IDs are those of an MRI-only plan of the same core (micr is planned after them)
    with PseudonymKey.load(tmp_path / "keys-mri-only", "proj") as other:
        mri_only = build_plan(copy.deepcopy(parse_core(FIXTURES / "ezbids_core_siemens.json")), tmp_path / "empty",
                              other, set(), None, schema, "bids")
    assert [(e.id, e.subject, e.session) for e in mri] == [(e.id, e.subject, e.session) for e in mri_only.entries]
    before = [(e.id, e.subject, e.status) for e in micr(plan)]
    apply_plan_edits(plan, [{"id": mri[0].id, "subject": "zz9"}], schema)
    assert [(e.id, e.subject, e.status) for e in micr(plan)] == before
    # an MRI entry set to micr gets the same treatment
    apply_plan_edits(plan, [{"id": mri[0].id, "datatype": "micr", "suffix": "OCT"}], schema)
    assert mri[0].status == "unknown" and mri[0].exclude
    with pytest.raises(ValueError):
        apply_plan_edits(plan, [{"id": mri[0].id, "sample_type": "tissue"}], schema)


def test_claimed_root_hides_ancillary_folder(tmp_path, key, schema):
    inp = tmp_path / "in"
    (inp / "sourcedata" / "H17").mkdir(parents=True)
    (inp / "dataset_description.json").write_text(json.dumps({"Name": "x", "BIDSVersion": "1.11.2"}))
    planted_ome_tiff(inp / "sourcedata" / "H17" / "stack.ome.tif")
    plan = make_plan(inp, tmp_path, key, schema)
    hidden = [w for w in plan.warnings if "supplementary folder" in w]
    assert hidden and hidden[0].startswith("1 ")
    assert "sourcedata" not in " ".join(plan.warnings)
    assert not [a for a in plan.ancillary if a.path.startswith("sourcedata")]


def test_old_plan_loads(tmp_path):
    from aimport.plan import Plan, PlanEntry

    e = PlanEntry(id="s0", series_idx=0, subject_idx=0, session_idx=0, subject="01", session=None,
                  datatype="anat", suffix="T1w", entities={}, brainlife_datatype=None, brainlife_tags=[],
                  source="heuristic", confidence=0.8, reason="r", deface=True, exclude=False, status="ok",
                  description="")
    raw = asdict(Plan(target="bids", entries=[e]))
    for k in ("modality", "sample_type", "write_mode", "output_bytes"):
        del raw["entries"][0][k]
    (tmp_path / "p.json").write_text(json.dumps(raw))
    loaded = Plan.load(tmp_path / "p.json")
    assert loaded.entries[0].modality == "mri" and loaded.entries[0].write_mode == ""


def test_remote_visor_planned_from_first_page(tmp_path, monkeypatch):
    from aimport.micr import remote

    tile = tmp_path / "t.tif"
    tifffile.imwrite(str(tile), np.zeros((32, 48), dtype=np.uint16), photometric="minisblack", metadata=None)
    calls = []
    monkeypatch.setattr(remote, "open_file", lambda url, *a, **k: (calls.append(url), open(tile, "rb"))[1:] + (None,))
    monkeypatch.setattr(remote, "sibling_json", lambda url, name, *a, **k: ACQINFO | {"operator": "Jane Doe"})
    monkeypatch.setattr(remote, "open_remote", lambda *a, **k: pytest.fail("pages must not be counted"))
    info, terms = micr_module._remote_visor("https://bucket.s3.amazonaws.com/x/visor_488_0_0.tif")
    assert info.shape == (4, 32, 48) and info.axes == "zyx"  # frames_per_file, not a page count
    assert info.pixel_size["x"] == 0.96 and info.channels[0].name_code == "ch488"
    assert "Jane Doe" in terms and calls


def test_server_scan_micr_only(tmp_path, inp, monkeypatch):
    from fastapi.testclient import TestClient

    from aimport.server import create_app

    monkeypatch.setattr(server, "client_from_env", lambda: None)
    monkeypatch.setattr(server, "run_ezbids", lambda *a, **k: pytest.fail("nothing is left for ezBIDS"))
    app = create_app(inp, tmp_path / "work", tmp_path / "keys", "t" * 32, ["https://brainlife.io"], ["testserver"])
    try:
        c = TestClient(app)
        c.headers["Authorization"] = "Bearer " + "t" * 32
        assert c.post("/scan", json={"project_id": "proj"}).status_code == 202
        end = time.time() + 30
        while (s := c.get("/status").json())["stage"] not in ("planned", "failed") and time.time() < end:
            time.sleep(0.05)
        assert s["stage"] == "planned", s
        body = c.get("/plan").json()
        assert len([e for e in body["entries"] if e["modality"] == "micr"]) == 10
        for text in (json.dumps(body), json.dumps(s), (tmp_path / "work" / "plan.json").read_text()):
            assert not MICR_PLANTED & tokens(text)
            assert "acquired" not in text
        scan_json = tmp_path / "work" / "scan.json"
        if scan_json.exists():
            assert not MICR_PLANTED & tokens(scan_json.read_text())
    finally:
        app.state.server.close()


def test_claimed_paths_lookup_is_per_ancestor(tmp_path):
    roots = [f"tiles/t{i:05d}.tif" for i in range(20_000)]
    claimed = modality.ClaimedPaths(tmp_path, roots)
    start = time.perf_counter()
    hits = sum(claimed.covers(tmp_path / r) for r in roots[::10])
    misses = sum(claimed.covers(tmp_path / "other" / f"x{i}.tif") for i in range(2_000))
    assert hits == 2_000 and misses == 0
    assert claimed.reaches(tmp_path / "tiles") and not claimed.reaches(tmp_path / "other")
    assert time.perf_counter() - start < 5  # linear scans over 20,000 roots would take minutes


@pytest.mark.parametrize("url", [
    "https://apex-connects.s3.amazonaws.com/CMC/Derivatives/Moe/PS-OCT/Zarr/Moe_Slice_051.ome.zarr",
    "https://s3.amazonaws.com/apex-connects/CMC/Derivatives/Moe/PS-OCT/Zarr/Moe_Slice_051.ome.zarr",
])
def test_remote_donor_from_name_tail_psoct(url):
    assert micr_module.remote_key(url) == "CMC/Derivatives/Moe/PS-OCT/Zarr/Moe_Slice_051.ome.zarr"
    assert micr_module.remote_donor(micr_module.remote_key(url)) == "Moe"


@pytest.mark.parametrize("url", [
    "https://apex-connects.s3.amazonaws.com/CMC/Raw/Moe/tract-tracing/MN27_FH_S100_250215_visor_488/"
    "visor_488_Pos0/visor_488_0_0.tif",
    "https://s3.us-east-2.amazonaws.com/apex-connects/CMC/Raw/Moe/tract-tracing/MN27_FH_S100_250215_visor_488/"
    "visor_488_Pos0/visor_488_0_0.tif",
])
def test_remote_donor_from_nearest_folder(url):
    """The nearest donor-like folder wins: MN27_... (under Moe/)."""
    assert micr_module.remote_donor(micr_module.remote_key(url)) == "MN27"


_ENFACE_CODES = {"Reflectivity": "EnRef", "Retardance": "EnR"}  # the real CMC key names (DATASETS.md)


def ENFACE(contrast: str, n: int) -> str:  # noqa: N802
    return ("https://apex-connects.s3.amazonaws.com/CMC/Derivatives/Moe/PS-OCT/Enface/Registration/"
            f"{contrast}/Slice_{n:03d}_{_ENFACE_CODES[contrast]}_hdr.nii.gz")


def test_remote_donor_walks_every_folder():
    """Folders first, nearest to the file walking up, every folder up to (not including) the top one: the donor
    folder Moe is found six levels up (it was 3 at most). The file name is used only when no folder is
    donor-like, and its format/vendor fragments (hdr, EnR, EnRef ...) never are donors."""
    for contrast in ("Reflectivity", "Retardance"):
        assert micr_module.remote_donor(micr_module.remote_key(ENFACE(contrast, 1))) == "Moe"
    for name in ("Slice_001_EnR_hdr.nii.gz", "Slice_001_EnRef_hdr.nii.gz", "Slice_004_EnCr_hdr.nii",
                 "Slice_001_EnAO_hdr.nii.gz"):
        assert micr_module.remote_donor(f"CMC/Registration/{name}") is None, name
    assert micr_module.remote_donor("CMC/Registration/H17_Slice_001_EnR_hdr.nii.gz") == "H17"
    path_style = "https://s3.us-east-2.amazonaws.com/apex-connects/CMC/Derivatives/stitched/data/image.ome.zarr"
    assert micr_module.remote_key(path_style) == "CMC/Derivatives/stitched/data/image.ome.zarr"
    assert micr_module.remote_donor(micr_module.remote_key(path_style)) is None
    assert micr_module.remote_donor("CMC/Raw/Moe/Registration/Enface/data/images/MN27_x/tile_0.tif") == "MN27"
    assert micr_module.remote_donor("CMC/Raw/Moe/Registration/Enface/data/images/tile_0.tif") == "Moe"
    assert micr_module.remote_donor("Moe/image.tif") is None  # the top folder alone
    assert micr_module.remote_donor("axonal_connectomics/deskewed/H17_PO10_S5_20250417/exaSPIM.zarr/Pos0") == "H17"


def _remote_plan(tmp_path, key, schema, monkeypatch, urls):
    monkeypatch.setattr(micr_module, "_read", lambda input_dir, g: (None, set(), micr_module.UNREADABLE_REASON))
    claim = modality.Claim(roots=[], remote=urls)
    found = [micr_module.Found(u, "nifti", u) for u in urls]
    records = micr_module.scan_records(tmp_path, claim, found, lambda msg: None)
    return records, micr_module.plan_entries(records, key, set(), schema, "bids")


def test_remote_contrasts_of_one_slice_share_a_subject(tmp_path, key, schema, monkeypatch):
    """CMC Moe slice001 reflectivity and retardance (and slice 51's store) are one subject, not 06 and 07."""
    urls = [ENFACE("Reflectivity", 1), ENFACE("Retardance", 1),
            "https://apex-connects.s3.amazonaws.com/CMC/Derivatives/Moe/PS-OCT/Zarr/Moe_Slice_051.ome.zarr"]
    records, mp = _remote_plan(tmp_path, key, schema, monkeypatch, urls)
    assert [r["facts"]["donor"] for r in records] == ["Moe"] * 3
    assert len({e.subject for e in mp.entries}) == 1 and len(mp.entries) == 3


def test_remote_without_donor_grouped_by_folder_and_slice(tmp_path, key, schema, monkeypatch):
    base = "https://lab.s3.amazonaws.com/proj/ps/oct/{}/Slice_{:03d}.nii.gz"
    urls = [base.format("Reflectivity", 1), base.format("Retardance", 1), base.format("Retardance", 2),
            "https://lab.s3.amazonaws.com/proj/other/Slice_001.nii.gz"]
    records, mp = _remote_plan(tmp_path, key, schema, monkeypatch, urls)
    assert all(r["facts"]["donor"] is None for r in records)
    by_url = {records[e.series_idx - micr_module.MICR_INDEX_BASE]["url"]: e.subject for e in mp.entries}
    subjects = [by_url[u] for u in urls]
    assert subjects[0] == subjects[1] and len(set(subjects)) == 3, subjects


def test_remote_records_never_take_bucket_or_project_as_donor(tmp_path, key, schema, monkeypatch):
    urls = ["https://s3.amazonaws.com/apex-connects/CMC/Derivatives/Moe/PS-OCT/Zarr/Moe_Slice_051.ome.zarr",
            "https://apex-connects.s3.amazonaws.com/CMC/Raw/Moe/tract-tracing/MN27_FH_S100_250215_visor_488/"
            "visor_488_Pos0/visor_488_0_0.tif",
            "https://apex-connects.s3.amazonaws.com/CMC/Derivatives/stitched/data/0/image.ome.zarr"]
    families = ["ome-zarr", "tiff", "ome-zarr"]
    monkeypatch.setattr(micr_module, "_read", lambda input_dir, g: (None, set(), micr_module.UNREADABLE_REASON))
    claim = modality.Claim(roots=[], remote=urls)
    found = [micr_module.Found(u, f, u) for u, f in zip(urls, families)]
    records = micr_module.scan_records(tmp_path, claim, found, lambda msg: None)
    donors = [r["facts"]["donor"] for r in records]
    assert sorted(d for d in donors if d) == ["MN27", "Moe"] and donors.count(None) == 1
    mp = micr_module.plan_entries(records, key, set(), schema, "bids")
    assert {"micr:id=Moe", "micr:id=MN27"} <= set(key.subjects)
    assert not [o for o in key.subjects if o.startswith("micr:id=") and o not in ("micr:id=Moe", "micr:id=MN27")]
    assert any(w.startswith("microscopy: no donor code was found for 1 ") for w in mp.warnings)
    text = json.dumps([asdict(e) for e in mp.entries] + mp.warnings)
    assert "apex" not in text and "amazonaws" not in text and "CMC" not in text


def test_unsupported_reason_redacted(inp, tmp_path, key, schema, monkeypatch):
    from aimport.micr import readers

    def broken(location):
        raise readers.UnsupportedFormat("cannot map axes 'Jane Doe' onto tczyx in H17_250215 for H17")

    monkeypatch.setitem(readers._ADAPTERS, "ome-tiff", broken)
    plan = make_plan(inp, tmp_path, key, schema)
    e = next(e for e in micr(plan) if e.description.startswith("OME-TIFF"))
    assert e.status == "unsupported" and e.exclude
    assert "cannot map axes" in e.reason
    assert not MICR_PLANTED & tokens(e.reason) and "Jane" not in e.reason


def test_czi_without_the_extra_planned_unsupported(inp, tmp_path, key, schema, monkeypatch):
    """Without bioio-czi (the desktop app), a .czi file is planned unsupported with the reason, and the scan goes on."""
    import sys

    from aimport.micr.readers import CZI_MISSING_MESSAGE

    monkeypatch.setitem(sys.modules, "bioio_czi", None)
    (inp / "H17_250215" / "slide_03.czi").write_bytes(b"ZISRAWFILE" + bytes(64))
    plan = make_plan(inp, tmp_path, key, schema)
    (e,) = [e for e in micr(plan) if e.description.startswith("CZI")]
    assert (e.status, e.exclude, e.write_mode, e.reason) == ("unsupported", True, "", CZI_MISSING_MESSAGE)
    assert any(e.description.startswith("OME-TIFF") and e.status != "unsupported" for e in micr(plan))


def test_photo_row_has_no_brainlife_datatype():
    from aimport.brainlife_map import load_rows

    (row,) = [r for r in load_rows() if r["bids"] == {"datatype": "micr", "suffix": "photo"}]
    assert row["status"] == "planned" and row["brainlife"] is None
    assert to_brainlife("micr", "photo", {}, {}) == (None, [])


def test_remote_visor_reads_first_page_only(local_servers, monkeypatch):  # noqa: F811
    from aimport.micr import remote

    base, root, _ = local_servers("served")
    folder = root / "MN27_x_visor_488" / "visor_488_Pos0"
    folder.mkdir(parents=True)
    tile = folder / "visor_488_0_0.tif"
    with tifffile.TiffWriter(str(tile)) as tw:  # 64 pages of 512 KiB, each with its own description
        for i in range(64):
            tw.write(np.full((512, 512), i, dtype=np.uint16), photometric="minisblack", metadata=None,
                     description=f"frame {i} " + "x" * (i * 37))
    (root / "MN27_x_visor_488" / "acqinfo_metadata.json").write_text(json.dumps(ACQINFO))
    counters = []
    real_open = remote.open_file

    def counted(url, *a, **k):
        fh, counter = real_open(url, *a, **k)
        counters.append(counter)
        return fh, counter

    monkeypatch.setattr(remote, "open_file", counted)
    info, _terms = micr_module._remote_visor(f"{base}/MN27_x_visor_488/visor_488_Pos0/visor_488_0_0.tif")
    assert info.shape == (4, 512, 512) and info.channels[0].name_code == "ch488"
    assert tile.stat().st_size > 32 * 2**20
    assert counters and counters[0].total < 2**20  # the first IFD only, never the page chain


@pytest.mark.network
def test_cmc_enface_contrasts_one_subject(tmp_path, key, schema, monkeypatch):
    """The real CMC Moe slice001 reflectivity and retardance en-face NIfTIs (headers only) plan as one subject
    (they were 06 and 07: the file names' EnRef/hdr and EnR looked like donors)."""
    from aimport.micr import remote

    counters = []
    real_open = remote.open_remote

    def counted(*a, **k):
        src, counter = real_open(*a, **k)
        counters.append(counter)
        return src, counter

    monkeypatch.setattr(remote, "open_remote", counted)
    urls = [ENFACE("Reflectivity", 1), ENFACE("Retardance", 1)]
    claim = modality.Claim(roots=[], remote=urls)
    found = [micr_module.Found(u, "nifti", u) for u in urls]
    records = micr_module.scan_records(tmp_path, claim, found, lambda msg: None)
    assert [r["facts"]["donor"] for r in records] == ["Moe", "Moe"]
    assert all(r["info"] is not None for r in records)
    mp = micr_module.plan_entries(records, key, set(), schema, "bids")
    assert len(mp.entries) == 2 and len({e.subject for e in mp.entries}) == 1
    assert {e.entities["sample"] for e in mp.entries} == {"slice001"}
    assert len(counters) == 2 and sum(c.total for c in counters) < 32 * 2**20
