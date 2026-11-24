"""Task 8: streaming conversion to OME-Zarr, rebuilt metadata and sidecars, the self-check, and the
write hook (participants, samples.tsv, scans.tsv) in the BIDS writer."""
from __future__ import annotations

import csv
import gc
import json
import time
import tracemalloc
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pytest
import zarr

from aimport import micr, modality, server
from aimport.ancillary import find_ancillary
from aimport.ezbids_runner import CoreResult
from aimport.micr import convert, metadata, readers
from aimport.micr.convert import NgffCheckError, check_ome_zarr, to_ome_zarr
from aimport.micr.metadata import ChannelInfo, ImageInfo, ngff_attrs, sidecar
from aimport.micr.module import MicrModule
from aimport.plan import PlanEntry
from aimport.planner import apply_plan_edits, build_plan
from aimport.pseudonyms import PseudonymKey
from aimport.writer import SCANS_DATE_ONLY, write_bids
from conftest import MICR_PLANTED
from fixtures.micr_fixtures import (PLANTED_PIXEL_SIZE_UM, planted_ome_tiff, psoct_nifti, striped_tiff,
                                    visor_tile)

MiB = 2**20


@pytest.fixture
def key(tmp_path):
    k = PseudonymKey.load(tmp_path / "keys", "proj")
    yield k
    k.close()


def _sidecar_for(src) -> dict:
    return sidecar(src.info, None)


def _peak(fn):
    gc.collect()
    tracemalloc.start()
    try:
        result = fn()
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    return result, peak


def _group_attrs(store: Path, version: str) -> dict:
    if version == "0.5":
        return json.loads((store / "zarr.json").read_text())["attributes"]
    return json.loads((store / ".zattrs").read_text())


def _multiscale(attrs: dict, version: str) -> dict:
    return (attrs["ome"] if version == "0.5" else attrs)["multiscales"][0]


def _omero(attrs: dict, version: str) -> dict:
    return (attrs["ome"] if version == "0.5" else attrs)["omero"]


# --- conversion ----------------------------------------------------------------------------------


@pytest.mark.parametrize("version", [micr.NGFF_VERSION, "0.4"])
def test_convert_ome_tiff(tmp_path, version):
    tif = planted_ome_tiff(tmp_path / "in" / "stack.ome.tif")
    out = tmp_path / "x.ome.zarr"
    with readers.open_image(tif, "ome-tiff") as src:
        written = to_ome_zarr(src, out, version)
        info = src.info
    assert written == sum(p.stat().st_size for p in out.rglob("*") if p.is_file()) > 0
    group = zarr.open_group(str(out), mode="r")
    assert group.metadata.zarr_format == (3 if version == "0.5" else 2)
    attrs = _group_attrs(out, version)
    ms = _multiscale(attrs, version)
    assert (attrs["ome"]["version"] if version == "0.5" else ms["version"]) == version
    assert "".join(a["name"] for a in ms["axes"]) == info.axes == "czyx"
    assert group["0"].shape == info.shape == (2, 4, 64, 64)
    assert np.array_equal(np.asarray(group["0"][:]), src_pixels(tif))
    scale = ms["datasets"][0]["coordinateTransformations"][0]["scale"]
    assert scale == [1.0, PLANTED_PIXEL_SIZE_UM["z"], PLANTED_PIXEL_SIZE_UM["y"], PLANTED_PIXEL_SIZE_UM["x"]]
    assert [c["label"] for c in _omero(attrs, version)["channels"]] == ["ch488", "ch561"]
    check_ome_zarr(out, sidecar(info, None), version, info.shape, info.dtype)


def src_pixels(tif: Path) -> np.ndarray:
    import tifffile

    return tifffile.imread(str(tif)).reshape(2, 4, 64, 64)


def test_convert_pyramid_levels(tmp_path):
    info = ImageInfo(family="tiff", axes="zyx", shape=(40, 3000, 2000), dtype="uint16",
                     pixel_size={"x": 0.5, "y": 0.5, "z": 4.0})
    levels = convert.pyramid_levels(info)
    assert levels[0] == {} and len(levels) <= convert.PYRAMID_MAX_LEVELS
    last = levels[-1]
    assert max(3000 // last["y"], 2000 // last["x"]) <= convert.PYRAMID_MAX_SIDE
    assert all(f.get("z", 1) == 1 for f in levels[:3])  # z (4 um) is coarser than the plane until 4 um
    # a 2D stripe: one level per halving down to 512
    flat = ImageInfo(family="tiff", axes="yx", shape=(6000, 6000), dtype="uint16")
    assert [f.get("x", 1) for f in convert.pyramid_levels(flat)] == [1, 2, 4, 8, 16]


def test_write_layout_defaults_and_budget(monkeypatch):
    info = ImageInfo(family="tiff", axes="czyx", shape=(2, 1000, 4000, 4000), dtype="uint16")
    chunks, per_shard = convert.write_layout(info, "0.5")
    assert chunks == {"c": 1, "z": 128, "y": 128, "x": 128}
    assert per_shard == {"z": 2, "y": 4, "x": 4}  # a shard is written whole: at most half the block limit
    assert convert.write_layout(info, "0.4") == (chunks, {"z": 1, "y": 1, "x": 1})
    flat = ImageInfo(family="tiff", axes="yx", shape=(60000, 60000), dtype="uint16")
    assert convert.write_layout(flat, "0.5") == ({"y": 1024, "x": 1024}, {"y": 4, "x": 4})
    monkeypatch.setattr(micr, "MAX_BLOCK_BYTES", 4 * MiB)  # read at call time
    chunks, per_shard = convert.write_layout(flat, "0.5")
    assert 2 * np.prod(list(chunks.values())) * np.prod(list(per_shard.values())) <= 2 * MiB


def test_convert_bounded_memory(tmp_path, monkeypatch):
    monkeypatch.setattr(micr, "MAX_BLOCK_BYTES", 4 * MiB)
    big = striped_tiff(tmp_path / "striped.tif", (6000, 6000), np.uint16)
    assert 6000 * 6000 * 2 > 4 * MiB
    # warm up once (imports and first-call caches of dask, zarr and ngff-zarr are not conversion memory)
    with readers.open_image(striped_tiff(tmp_path / "small.tif", (600, 600)), "tiff") as small:
        to_ome_zarr(small, tmp_path / "small.ome.zarr", "0.5")
    seen = []
    with readers.open_image(big, "tiff") as src:
        _, peak = _peak(lambda: to_ome_zarr(src, tmp_path / "big.ome.zarr", "0.5", seen.append))
    assert peak < 12 * MiB, peak
    assert zarr.open_array(str(tmp_path / "big.ome.zarr" / "0"), mode="r").shape == (6000, 6000)
    # progress per level and per block, numbers only
    assert any(m.startswith("converting: level 1 of 5, block 1 of ") for m in seen)
    assert any(m.startswith("converting: level 5 of 5") for m in seen)


def test_convert_never_reads_whole_array(tmp_path, monkeypatch):
    """Every read of the source is one block of the shard grid, never the whole level."""
    monkeypatch.setattr(micr, "MAX_BLOCK_BYTES", 4 * MiB)
    big = striped_tiff(tmp_path / "striped.tif", (3000, 3000), np.uint16)
    sizes = []
    real = convert._Blocks.__getitem__

    def spy(self, k):
        block = real(self, k)
        sizes.append(block.nbytes)
        return block

    monkeypatch.setattr(convert._Blocks, "__getitem__", spy)
    with readers.open_image(big, "tiff") as src:
        to_ome_zarr(src, tmp_path / "o.ome.zarr", "0.5")
    assert sizes and max(sizes) <= 2 * MiB < 3000 * 3000 * 2


def test_visor_tiles_stacked_along_z(tmp_path, key, schema):
    """The tiles of one VISoR position are consecutive frame stacks: one image, stacked along z."""
    import tifffile

    inp = tmp_path / "in"
    first = visor_tile(inp / "MN27_20250422_visor_488")
    frames = []
    for n in (1, 2):
        data = np.full((4, 32, 32), n, dtype=np.uint16)
        tifffile.imwrite(str(first.parent / f"visor_488_000{n}.tif"), data, photometric="minisblack", metadata=None)
        frames.append(data)
    plan, out, manifest = plan_and_write(inp, tmp_path, key, schema)
    (e,) = [e for e in plan.entries if e.modality == "micr" and not e.exclude]
    arr = zarr.open_array(str(out / manifest[e.id][0] / "0"), mode="r")
    assert arr.shape == (8, 32, 32)
    assert np.array_equal(np.asarray(arr[:]), np.concatenate(frames))


def test_other_tile_groups_not_converted(tmp_path):
    from aimport.micr.module import open_record

    rec = {"rel": "t", "family": "tiff", "members": ["t/Tile_0001.tif", "t/Tile_0002.tif"]}
    with pytest.raises(NotImplementedError):
        open_record(rec, tmp_path)


def _variants(term: str) -> set[str]:
    return {term, term.upper(), term.title(), term.capitalize()}


def _assert_no_planted(root: Path) -> None:
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        data = p.read_bytes()
        for term in MICR_PLANTED:
            for v in _variants(term):
                assert v.encode("utf-8") not in data, (p.name, v)
                assert v.encode("utf-16-le") not in data, (p.name, v)
        assert not [t for t in MICR_PLANTED if t in p.relative_to(root).as_posix().lower()]


def test_attrs_rebuilt(tmp_path):
    tif = planted_ome_tiff(tmp_path / "stack.ome.tif")
    for version, allowed in (("0.5", {"ome"}), ("0.4", {"multiscales", "omero"})):
        out = tmp_path / f"{version}.ome.zarr"
        with readers.open_image(tif, "ome-tiff") as src:
            to_ome_zarr(src, out, version)
            info = src.info
        attrs = _group_attrs(out, version)
        assert set(attrs) <= allowed
        assert attrs == ngff_attrs(info, version, convert.pyramid_levels(info), _windows(attrs, version))
        ms = _multiscale(attrs, version)
        assert not {"name", "metadata", "type", "_creator"} & set(ms)
        if version == "0.5":
            assert set(attrs["ome"]) == {"version", "multiscales", "omero"}
        # no OME-XML group, no ngff-zarr group nodes, arrays without attributes
        assert not (out / "OME").exists()
        assert sorted(p.name for p in out.iterdir()) == (["0", "zarr.json"] if version == "0.5"
                                                         else [".zattrs", ".zgroup", "0"])
        if version == "0.5":
            assert json.loads((out / "0" / "zarr.json").read_text())["attributes"] == {}
        else:
            assert not (out / "0" / ".zattrs").exists()


def _windows(attrs: dict, version: str) -> list[dict]:
    return [c["window"] for c in _omero(attrs, version)["channels"]]


def test_sidecar_required_fields():
    info = ImageInfo(family="nifti", axes="zyx", shape=(4, 24, 32), dtype="float32",
                     pixel_size={"x": 10.0, "y": 10.0, "z": 2.5}, pixel_unit="um",
                     objective_magnification=20.0, objective_na=0.8, immersion="Water")
    oct_entry = PlanEntry("m0", 1_000_000, 1_000_000, 0, "01", None, "micr", "OCT",
                          {"sample": "slice051", "acquisition": "retardance"}, None, [], "heuristic", 0.8, "",
                          False, False, "ok", "")
    car = sidecar(info, oct_entry)
    assert car["PixelSize"] == [10.0, 10.0, 2.5] and car["PixelSizeUnits"] == "um"
    assert (car["Magnification"], car["NumericalAperture"], car["Immersion"]) == (20.0, 0.8, "Water")
    assert car["OCTContrast"] == "retardance" and car["OCTRetardanceKind"] == "retardance"
    assert car["OCTOpticAxisConvention"] == "n/a"
    oct_entry.entities["acquisition"] = "reflectivity"
    assert sidecar(info, oct_entry)["OCTRetardanceKind"] == "n/a"
    oct_entry.suffix = "SPIM"
    plain = sidecar(ImageInfo(family="tiff", axes="yx", shape=(8, 8), dtype="uint8"), oct_entry)
    assert plain == {"PixelSize": [1.0, 1.0], "PixelSizeUnits": "um"}  # 2D: x, y only; no OCT fields


# --- self-check ----------------------------------------------------------------------------------


@pytest.fixture
def written(tmp_path):
    tif = planted_ome_tiff(tmp_path / "stack.ome.tif")
    out = tmp_path / "x.ome.zarr"
    with readers.open_image(tif, "ome-tiff") as src:
        to_ome_zarr(src, out, "0.5")
        return out, src.info, sidecar(src.info, None)


def test_self_check_passes(written):
    out, info, car = written
    check_ome_zarr(out, car, "0.5", info.shape, info.dtype)


def test_self_check_corrupt_zarr_json(written):
    out, info, car = written
    (out / "zarr.json").write_text("{not json")
    with pytest.raises(NgffCheckError) as exc:
        check_ome_zarr(out, car, "0.5", info.shape, info.dtype)
    assert str(out) not in str(exc.value) and "x.ome.zarr" not in str(exc.value)


def test_self_check_pixel_size_mismatch(written):
    out, info, car = written
    with pytest.raises(NgffCheckError, match="pixel size"):
        check_ome_zarr(out, {**car, "PixelSize": [9.0, 9.0, 9.0]}, "0.5", info.shape, info.dtype)
    with pytest.raises(NgffCheckError, match="unit"):
        check_ome_zarr(out, {**car, "PixelSizeUnits": "mm"}, "0.5", info.shape, info.dtype)


def test_self_check_structure(written):
    out, info, car = written
    meta = json.loads((out / "zarr.json").read_text())
    bad = json.loads(json.dumps(meta))
    bad["attributes"]["ome"]["omero"]["channels"].pop()
    (out / "zarr.json").write_text(json.dumps(bad))
    with pytest.raises(NgffCheckError, match="omero channel count"):
        check_ome_zarr(out, car, "0.5", info.shape, info.dtype)
    (out / "zarr.json").write_text(json.dumps(meta))
    with pytest.raises(NgffCheckError, match="shape"):
        check_ome_zarr(out, car, "0.5", (2, 4, 64, 65), info.dtype)
    with pytest.raises(NgffCheckError, match="type"):
        check_ome_zarr(out, car, "0.5", info.shape, "float32")
    with pytest.raises(NgffCheckError):
        check_ome_zarr(out, car, "0.4", info.shape, info.dtype)  # not the configured version
    import shutil

    shutil.rmtree(out / "0")
    with pytest.raises(NgffCheckError):
        check_ome_zarr(out, car, "0.5", info.shape, info.dtype)


# --- the write hook ------------------------------------------------------------------------------


def micr_input(root: Path) -> Path:
    """A planted OME-TIFF in H17_250215/ (AcquisitionDate 2025-02-15), a PS-OCT NIfTI, a VISoR tile
    of donor MN27 (folder date 20250422), and a supplied samples.tsv."""
    planted_ome_tiff(root / "H17_250215" / "stack.ome.tif")
    psoct_nifti(root / "PS-OCT/Enface/Registration/Retardance/Slice_051_1.nii.gz", "retardance")
    visor_tile(root / "MN27_20250422_visor_488")
    return root


def plan_and_write(inp: Path, tmp_path: Path, key, schema, suffix: str = "CONF", **kw):
    work = tmp_path / "work"
    m = MicrModule()
    claim = m.claim(inp, [])
    m.scan(inp, claim, work / "micr", lambda msg: None)
    plan = build_plan(CoreResult(), inp, key, set(), None, schema, "bids", exclude=claim.roots,
                      extra_terms=frozenset(m.terms(work / "micr")),
                      planners=[lambda: m.plan(work / "micr", key, set(), None, schema, "bids")])
    apply_plan_edits(plan, [{"id": e.id, "suffix": suffix} for e in plan.entries if e.status == "unknown"], schema)
    plan.approved = True
    staged = tmp_path / "staged"
    staged.mkdir(exist_ok=True)
    out = tmp_path / "out"
    manifest: dict = {}
    write_bids(plan, CoreResult(), inp, m.terms(work / "micr"), key, schema, out, staged_dir=staged,
               exclude=claim.roots, manifest=manifest, modules=modality.modules(), work_dir=work, **kw)
    return plan, out, manifest


def read_tsv(path: Path) -> list[dict]:
    with open(path, newline="") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def test_write_hook_outputs(tmp_path, key, schema):
    seen = []
    plan, out, manifest = plan_and_write(micr_input(tmp_path / "in"), tmp_path, key, schema, progress=seen.append)
    micr_entries = [e for e in plan.entries if e.modality == "micr" and not e.exclude]
    assert len(micr_entries) == 3
    for e in micr_entries:
        (rel,) = manifest[e.id]
        assert rel.endswith(".ome.zarr") and (out / rel / "zarr.json").is_file()
        car = json.loads((out / rel.replace(".ome.zarr", ".json")).read_text())
        assert "PixelSize" in car and "PixelSizeUnits" in car
    assert {r["participant_id"] for r in read_tsv(out / "participants.tsv")} == {
        f"sub-{e.subject}" for e in micr_entries}
    assert all(r["age"] == "n/a" and r["sex"] == "n/a" for r in read_tsv(out / "participants.tsv"))
    assert seen[0] == "writing microscopy image 1 of 3"
    assert any("converting: level 1 of 1, block 1 of" in m for m in seen)


def test_no_planted_bytes_in_output(tmp_path, key, schema):
    _, out, _ = plan_and_write(micr_input(tmp_path / "in"), tmp_path, key, schema)
    assert list(out.rglob("*.ome.zarr"))
    _assert_no_planted(out)


def test_scans_shifted(tmp_path, key, schema):
    plan, out, manifest = plan_and_write(micr_input(tmp_path / "in"), tmp_path, key, schema)
    by_suffix = {e.suffix: e for e in plan.entries if e.modality == "micr"}
    conf = by_suffix["CONF"]  # the planted OME-TIFF: AcquisitionDate 2025-02-15 (folder H17_250215)
    offset = key.date_offset_days(conf.subject)
    rows = read_tsv(out / f"sub-{conf.subject}" / f"sub-{conf.subject}_scans.tsv")
    assert rows == [{"filename": manifest[conf.id][0].split("/", 1)[1],
                     "acq_time": (date(2025, 2, 15) + timedelta(days=offset)).isoformat() + "T00:00:00"}]
    spim = by_suffix["SPIM"]  # the VISoR tile: the date in its folder name, 2025-04-22
    rows = read_tsv(out / f"sub-{spim.subject}" / f"sub-{spim.subject}_scans.tsv")
    shifted = date(2025, 4, 22) + timedelta(days=key.date_offset_days(spim.subject))
    assert rows[0]["acq_time"] == shifted.isoformat() + "T00:00:00"
    octe = by_suffix["OCT"]  # no date anywhere: n/a
    assert read_tsv(out / f"sub-{octe.subject}" / f"sub-{octe.subject}_scans.tsv")[0]["acq_time"] == "n/a"
    scans_json = json.loads((out / f"sub-{conf.subject}" / f"sub-{conf.subject}_scans.json").read_text())
    assert scans_json == {"acq_time": {"Description": SCANS_DATE_ONLY}} and SCANS_DATE_ONLY == \
        "date only; time not recorded"
    for p in out.rglob("*"):
        if p.is_file():
            data = p.read_bytes()
            for raw in (b"250215", b"20250422", b"2025-02-15", b"2025-04-22", b"2025:02:15"):
                assert raw not in data, p.name


def test_samples_tsv(tmp_path, key, schema):
    """A BIDS micr input with a supplied samples.tsv: one generated row per (subject, sample), merged
    with the supplied rows by (participant_id, sample_id); supplied columns kept; other subjects dropped."""
    inp = tmp_path / "in"
    planted_ome_tiff(inp / "sub-01" / "micr" / "sub-01_sample-A_CONF.ome.tif")
    (inp / "sub-01" / "micr" / "sub-01_sample-A_CONF.json").write_text(json.dumps({"PixelSize": [1, 1, 1]}))
    psoct_nifti(inp / "sub-01" / "micr" / "sub-01_sample-B_acq-retardance_OCT.nii.gz", "retardance")
    (inp / "samples.tsv").write_text("sample_id\tparticipant_id\tsample_type\tcollected_by\n"
                                     "sample-A\tsub-01\tcell line\tlab B\n"
                                     "sample-Z\tsub-99\ttissue\tlab C\n")
    (inp / "dataset_description.json").write_text(json.dumps({"Name": "x", "BIDSVersion": "1.11.2"}))
    plan, out, _ = plan_and_write(inp, tmp_path, key, schema)
    subjects = {e.subject for e in plan.entries if e.modality == "micr" and not e.exclude}
    assert len(subjects) == 1
    (subject,) = subjects
    rows = read_tsv(out / "samples.tsv")
    assert rows == [
        {"sample_id": "sample-A", "participant_id": f"sub-{subject}", "sample_type": "cell line",
         "collected_by": "lab B"},
        {"sample_id": "sample-B", "participant_id": f"sub-{subject}", "sample_type": "tissue",
         "collected_by": "n/a"},
    ]


def test_samples_tsv_generated_without_supplied(tmp_path, key, schema):
    _, out, _ = plan_and_write(micr_input(tmp_path / "in"), tmp_path, key, schema)
    rows = read_tsv(out / "samples.tsv")
    assert list(rows[0]) == ["sample_id", "participant_id", "sample_type"]
    assert len(rows) == len({(r["participant_id"], r["sample_id"]) for r in rows}) == 3
    assert {r["sample_type"] for r in rows} == {"tissue"}


def test_bids_micr_sidecar_not_companion(tmp_path, schema):
    inp = tmp_path / "in"
    planted_ome_tiff(inp / "sub-01" / "micr" / "sub-01_sample-A_CONF.ome.tif")
    (inp / "sub-01" / "micr" / "sub-01_sample-A_CONF.json").write_text("{}")
    (inp / "sub-01" / "micr" / "sub-01_sample-A_photo.png").write_bytes(b"\x89PNG")
    (inp / "sub-01" / "micr" / "sub-01_sample-A_photo.json").write_text("{}")
    claim = MicrModule().claim(inp, [])
    found = {p.relative_to(inp).as_posix() for p in find_ancillary(inp, schema, claim.roots)}
    assert "sub-01/micr/sub-01_sample-A_CONF.json" not in found
    assert "sub-01/micr/sub-01_sample-A_photo.json" not in found


def test_reference_entries_wait_for_task_9(tmp_path, key, schema):
    from fixtures.micr_fixtures import ome_zarr

    inp = tmp_path / "in"
    ome_zarr(inp / "Moe_Slice_051.ome.zarr", "0.5")
    with pytest.raises(NotImplementedError, match="reference datasets: Task 9"):
        plan_and_write(inp, tmp_path, key, schema, suffix="SPIM")
    assert not (tmp_path / "out").exists()


def test_self_check_failure_fails_the_write(tmp_path, key, schema, monkeypatch):
    real = metadata.sidecar
    monkeypatch.setattr(metadata, "sidecar", lambda info, entry: {**real(info, entry), "PixelSize": [9.0, 9.0, 9.0]})
    inp = tmp_path / "in"
    planted_ome_tiff(inp / "H17_250215" / "stack.ome.tif")
    with pytest.raises(NgffCheckError) as exc:
        plan_and_write(inp, tmp_path, key, schema)
    assert str(tmp_path) not in str(exc.value)
    assert not (tmp_path / "out").exists()  # a failed write removes what it created


@pytest.mark.docker
def test_converted_dataset_validates(tmp_path, key, schema):
    """The converted dataset (OME-Zarr, sidecars, samples.tsv, scans.tsv) passes the BIDS validator."""
    from aimport.validate import validate_bids

    _, out, _ = plan_and_write(micr_input(tmp_path / "in"), tmp_path, key, schema)
    r = validate_bids(out)
    assert r.ok, json.dumps({"errors": r.errors, "warnings": r.warnings}, indent=1)


# --- execute through the server -------------------------------------------------------------------


def _server_execute(tmp_path, monkeypatch, inp):
    from fastapi.testclient import TestClient

    from aimport.server import create_app
    from aimport.validate import ValidationResult

    monkeypatch.setattr(server, "client_from_env", lambda: None)
    monkeypatch.setattr(server, "run_ezbids", lambda *a, **k: pytest.fail("nothing is left for ezBIDS"))
    monkeypatch.setattr(server, "validate_bids", lambda bids: ValidationResult(
        ok=True, validator_version="2.4.1", bids_version="1.11.2"))
    app = create_app(inp, tmp_path / "work", tmp_path / "keys", "t" * 32, ["https://brainlife.io"], ["testserver"])
    events = []
    try:
        c = TestClient(app)
        c.headers["Authorization"] = "Bearer " + "t" * 32
        assert c.post("/scan", json={"project_id": "proj"}).status_code == 202
        s = _wait(c, ("planned", "failed"))
        assert s["stage"] == "planned", s
        edits = [{"id": e["id"], "suffix": "CONF"} for e in c.get("/plan").json()["entries"]
                 if e["status"] == "unknown"]
        if edits:
            assert c.patch("/plan", json={"edits": edits}).status_code == 200
        assert c.post("/approve", json={}).status_code == 200
        assert c.post("/execute").status_code == 202
        s = _wait(c, ("validated", "invalid", "failed"))
        events = list(app.state.server.events)
        return s, events
    finally:
        app.state.server.close()


def _wait(c, stages, timeout=60):
    end = time.time() + timeout
    while (s := c.get("/status").json())["stage"] not in stages and time.time() < end:
        time.sleep(0.05)
    return s


def test_server_execute_micr(tmp_path, monkeypatch):
    inp = micr_input(tmp_path / "in")
    s, events = _server_execute(tmp_path, monkeypatch, inp)
    assert s["stage"] == "validated", s
    out = tmp_path / "work" / "output" / "bids"
    assert len(list(out.rglob("*.ome.zarr"))) == 3 and (out / "samples.tsv").is_file()
    texts = [e["message"] for e in events]
    assert any(t.startswith("writing microscopy image") for t in texts)
    for t in texts + [json.dumps(s)]:
        assert not {x for x in MICR_PLANTED if x in t.lower()}
    _assert_no_planted(out)


def test_server_execute_self_check_failure(tmp_path, monkeypatch):
    real = metadata.sidecar
    monkeypatch.setattr(metadata, "sidecar", lambda info, entry: {**real(info, entry), "PixelSizeUnits": "nm"})
    inp = tmp_path / "in"
    planted_ome_tiff(inp / "H17_250215" / "stack.ome.tif")
    s, _ = _server_execute(tmp_path, monkeypatch, inp)
    assert s["stage"] == "failed"
    head = s["message"].split(";")[0]
    assert head.startswith("NgffCheckError: OME-Zarr self-check failed")
    assert str(inp) not in s["message"] and "H17" not in s["message"] and "stack" not in s["message"]
