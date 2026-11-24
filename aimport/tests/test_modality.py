"""Modality modules: claimed input is never staged, walked for DICOM headers, copied or served."""
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from aimport import modality, server
from aimport.ezbids_runner import CoreResult, has_files, stage_input
from aimport.modality import EMPTY_CORE, Claim, ClaimedPaths, claimed_roots, module_dir, normalize_root
from aimport.scrub import identifying_terms
from aimport.server import create_app
from aimport.writer import _Writer
from test_writer import write_dicom

sys.path.insert(0, str(Path(__file__).parent / "fixtures"))
from micr_fixtures import ome_zarr, sparse_bigtiff  # noqa: E402

TOKEN = "s3cret-token"
ROOTS = ["big", "a.zarr"]
SECRET = "H17_250215"  # a donor code and a date in a folder name: must never leave work/<name>/
REMOTE = "https://cmc-h17-bucket.s3.amazonaws.com/H17_250215/brain.ome.zarr"


class FakeModule:
    """Claims big/ and a.zarr/ when present, and the remote sources it is given."""

    name = "fake"

    def __init__(self):
        self.scanned: list[tuple[Path, Claim, Path]] = []

    def claim(self, input_dir, remote):
        return Claim(roots=[r for r in ROOTS if (Path(input_dir) / r).exists()], remote=list(remote))

    def scan(self, input_dir, claim, work, progress):
        self.scanned.append((Path(input_dir), claim, Path(work)))
        work.mkdir(parents=True, exist_ok=True)
        (work / "records.json").write_text(json.dumps({"roots": claim.roots}))
        progress(f"read 1 file under {claim.roots[0] if claim.roots else 'nothing'}")

    def terms(self, work):
        return set()

    def plan(self, *args, **kwargs):
        raise AssertionError("not used before Task 6")

    def write(self, *args, **kwargs):
        raise AssertionError("not used before Task 6")


def du_bytes(path: Path) -> int:
    """Disk usage (not apparent size) of path, without following links."""
    out = subprocess.run(["du", "-sk", str(path)], capture_output=True, text=True, check=True).stdout
    return int(out.split()[0]) * 1024


def gnu_cp() -> bool:
    return subprocess.run(["cp", "--version"], capture_output=True).returncode == 0


def make_input(root: Path, unclaimed: bool = True) -> Path:
    """An input folder with claimed big/ (a planted folder name, a DICOM) and a.zarr/, plus unclaimed files."""
    inp = root / "in"
    big = inp / "big" / SECRET
    big.mkdir(parents=True)
    (big / "notes.txt").write_text("H17 Moe 20250422")
    ome_zarr(inp / "a.zarr", "0.5", shape=(1, 2, 16, 16))
    if unclaimed:
        (inp / "sub" / "deep").mkdir(parents=True)
        (inp / "sub" / "deep" / "f.txt").write_text("x")
        (inp / "top.txt").write_text("y")
        (inp / ".hidden").write_text("z")
        (inp / "empty").mkdir()
        os.symlink(inp / "top.txt", inp / "sub" / "to_top")  # a link outside the claimed roots is staged
        os.symlink(big / "notes.txt", inp / "sub" / "to_big")  # resolves into big/: never staged
        os.symlink(inp / "big", inp / "dir_to_big")  # a folder link into big/: never staged
        os.symlink(inp, inp / "sub" / "dir_to_input")  # leads to a folder holding claimed roots: never staged
    return inp


def tree(root: Path) -> dict[str, str]:
    """rel path -> 'dir' or 'link:<normalised target>' for everything under root (links not followed)."""
    out = {}
    for dirpath, dirs, files in os.walk(root, followlinks=False):
        for name in dirs + files:
            p = Path(dirpath) / name
            rel = p.relative_to(root).as_posix()
            if p.is_symlink():
                out[rel] = "link:" + os.path.normpath(os.readlink(p))
            elif p.is_dir():
                out[rel] = "dir"
            else:
                out[rel] = "file"
    return out


def no_link_into_claimed(staged: Path, inp: Path) -> None:
    claimed = ClaimedPaths(inp, ROOTS)
    for dirpath, dirs, files in os.walk(staged, followlinks=False):
        for name in dirs + files:
            p = Path(dirpath) / name
            rel = p.relative_to(staged).as_posix()
            assert not any(rel == r or rel.startswith(r + "/") for r in ROOTS), rel
            if p.is_symlink():
                assert not claimed.reaches(Path(os.readlink(p))), rel


# --- paths ------------------------------------------------------------------


def test_normalize_root_rejects_escapes():
    assert normalize_root("./big/") == "big"
    assert normalize_root("a\\b.zarr") == "a/b.zarr"
    for bad in ("/abs", "../x", "a/../../x", ".", ""):
        with pytest.raises(ValueError):
            normalize_root(bad)
    assert claimed_roots([Claim(["big", "./big/"]), Claim(["a.zarr"])]) == ["big", "a.zarr"]


def test_module_dir_names():
    class M:
        name = "micr"
    assert module_dir(Path("/w"), M()) == Path("/w/micr")
    for bad in ("ezbids", "output", "../x", "a/b", "", "Micr"):
        M.name = bad
        with pytest.raises(ValueError):
            module_dir(Path("/w"), M())


def test_modules_empty_until_registered():
    assert modality.modules() == ()


# --- staging ------------------------------------------------------------------


def test_stage_excludes_claimed_roots(tmp_path):
    inp = make_input(tmp_path)
    staged = stage_input(inp, tmp_path / "work", exclude=ROOTS)
    assert not (staged / "big").exists() and not (staged / "a.zarr").exists()
    assert not (staged / "big").is_symlink() and not (staged / "a.zarr").is_symlink()
    no_link_into_claimed(staged, inp)
    assert not (staged / "sub" / "to_big").is_symlink()
    assert not (staged / "dir_to_big").is_symlink()
    assert not (staged / "sub" / "dir_to_input").is_symlink()
    assert SECRET not in json.dumps(tree(staged))


def test_stage_unclaimed_files_unchanged(tmp_path):
    inp = make_input(tmp_path)
    staged = stage_input(inp, tmp_path / "work", exclude=ROOTS)
    real = inp.resolve()
    got = tree(staged)
    expected = {
        "sub": "dir", "sub/deep": "dir", "empty": "dir",
        "sub/deep/f.txt": f"link:{real}/sub/deep/f.txt",
        "top.txt": f"link:{real}/top.txt",
        ".hidden": f"link:{real}/.hidden",
        "sub/to_top": f"link:{real}/sub/to_top",
    }
    assert got == expected
    assert (staged / "sub" / "to_top").read_text() == "y"
    if gnu_cp():  # the image: compare with what phase 1 staged (cp -rs), minus the claimed roots
        ref = tmp_path / "ref"
        ref.mkdir()
        subprocess.run(["cp", "-rs", f"{real}/.", str(ref)], check=True)
        want = {k: v for k, v in tree(ref).items()
                if k not in ("sub/to_big", "dir_to_big", "sub/dir_to_input")
                and not any(k == r or k.startswith(r + "/") for r in ROOTS)}
        assert got == want


def test_stage_without_exclude_matches_phase1(tmp_path):
    inp = make_input(tmp_path, unclaimed=False)
    (inp / "x").mkdir()
    (inp / "x" / "1.dcm").write_bytes(b"d")
    staged = stage_input(inp, tmp_path / "work")
    real = inp.resolve()
    got = tree(staged)
    assert got["x/1.dcm"] == f"link:{real}/x/1.dcm"
    assert got["big/" + SECRET + "/notes.txt"] == f"link:{real}/big/{SECRET}/notes.txt"
    assert got["a.zarr/zarr.json"] == f"link:{real}/a.zarr/zarr.json"
    if gnu_cp():
        ref = tmp_path / "ref"
        ref.mkdir()
        subprocess.run(["cp", "-rs", f"{real}/.", str(ref)], check=True)
        assert got == tree(ref)


def test_has_files(tmp_path):
    (tmp_path / "a" / "b").mkdir(parents=True)
    assert not has_files(tmp_path)
    os.symlink(tmp_path / "a", tmp_path / "a" / "b" / "link")
    assert has_files(tmp_path)


def test_sparse_bigtiff_is_sparse(tmp_path):
    path = sparse_bigtiff(4 * 2**30, tmp_path / "s.tif")
    assert path.stat().st_size >= 4 * 2**30
    assert du_bytes(path) < 2**20
    import tifffile
    with tifffile.TiffFile(path) as tif:
        assert tif.is_bigtiff and tif.pages[0].dtype.name == "uint16"


# --- DICOM walks ----------------------------------------------------------------


def test_header_terms_skip_claimed(tmp_path):
    inp = make_input(tmp_path)
    write_dicom(inp / "big" / SECRET / "1.dcm", PatientName="Hidden^Donor", PatientID="H17")
    write_dicom(inp / "sub" / "deep" / "2.dcm", PatientName="Roe^Rita")
    stats: dict = {}
    terms = {t.lower() for t in identifying_terms(CoreResult(), inp, stats, exclude=ROOTS)}
    assert "roe" in terms and not {"hidden", "donor", "h17"} & terms
    assert stats["dicom_files_read"] == 1
    # without the claim the planted DICOM is found: the walk really skipped it
    stats = {}
    terms = {t.lower() for t in identifying_terms(CoreResult(), inp, stats)}
    assert "hidden" in terms and stats["dicom_files_read"] == 2


def test_writer_dicom_walk_skips_claimed(tmp_path):
    inp = make_input(tmp_path)
    write_dicom(inp / "big" / SECRET / "1.dcm", PatientName="Hidden^Donor")
    write_dicom(inp / "sub" / "2.dcm", PatientName="Roe^Rita")
    claimed = ClaimedPaths(inp, ROOTS)
    assert list(_Writer.read_dir(inp / "big" / SECRET, claimed)) == []
    assert [str(d.PatientName) for d in _Writer.read_dir(inp / "sub", claimed)] == ["Roe^Rita"]
    assert len(list(_Writer.read_dir(inp / "big" / SECRET))) == 1


# --- server -------------------------------------------------------------------


@pytest.fixture
def fake(monkeypatch):
    m = FakeModule()
    monkeypatch.setattr(modality, "modules", lambda: (m,))
    monkeypatch.setattr(server, "client_from_env", lambda: None)

    def no_ezbids(*a, **kw):
        raise AssertionError("ezBIDS must not run when nothing is left to stage")

    monkeypatch.setattr(server, "run_ezbids", no_ezbids)
    return m


@pytest.fixture
def make_app(tmp_path):
    apps = []

    def make(inp: Path):
        app = create_app(inp, tmp_path / "work", tmp_path / "keys", TOKEN, ["https://brainlife.io"], ["testserver"])
        apps.append(app)
        c = TestClient(app)
        c.headers["Authorization"] = f"Bearer {TOKEN}"
        return c

    yield make
    for app in apps:
        app.state.server.close()


def wait_stage(c, stages, timeout=20):
    end = time.time() + timeout
    while time.time() < end:
        s = c.get("/status").json()
        if s["stage"] in stages:
            return s
        time.sleep(0.05)
    raise AssertionError(f"stage never reached {stages}: {s}")


def claimed_only_input(tmp_path: Path) -> Path:
    inp = make_input(tmp_path, unclaimed=False)
    sparse_bigtiff(4 * 2**30, inp / "big" / SECRET / "slab.tif")
    return inp


def test_ezbids_skipped_when_nothing_left(tmp_path, fake, make_app):
    inp = claimed_only_input(tmp_path)
    c = make_app(inp)
    assert c.post("/scan", json={"project_id": "proj"}).status_code == 202
    s = wait_stage(c, ("planned", "failed"))
    assert s["stage"] == "planned", s
    work = tmp_path / "work"
    assert json.loads((work / "ezbids" / "ezBIDS_core.json").read_text()) == EMPTY_CORE
    assert not (work / "ezbids.log").exists()
    assert c.get("/plan").json()["entries"] == []
    assert len(fake.scanned) == 1
    _, claim, mwork = fake.scanned[0]
    assert claim.roots == ROOTS and mwork == work / "fake"
    assert Claim.load(work / "fake" / "claim.json").roots == ROOTS


def test_sparse_4gb_tiff_not_staged(tmp_path, fake, make_app):
    inp = claimed_only_input(tmp_path)
    tif = inp / "big" / SECRET / "slab.tif"
    assert tif.stat().st_size >= 4 * 2**30
    c = make_app(inp)
    c.post("/scan", json={"project_id": "proj"})
    assert wait_stage(c, ("planned", "failed"))["stage"] == "planned"
    work = tmp_path / "work"
    assert du_bytes(work) < 2**20
    real = tif.resolve()
    for dirpath, dirs, files in os.walk(work, followlinks=False):
        for name in dirs + files:
            p = Path(dirpath) / name
            if p.is_symlink():
                assert Path(os.readlink(p)).resolve() != real and not str(Path(os.readlink(p))).startswith(str(inp))
            elif p.is_file():
                assert p.stat().st_size < 2**20


def test_claim_json_never_served(tmp_path, fake, make_app):
    inp = claimed_only_input(tmp_path)
    c = make_app(inp)
    r = c.post("/scan", json={"project_id": "proj", "remote": [REMOTE]})
    assert r.status_code == 202
    assert wait_stage(c, ("planned", "failed"))["stage"] == "planned"
    work = tmp_path / "work"
    claim = (work / "fake" / "claim.json").read_text()
    assert '"big"' in claim and REMOTE in claim  # local-only: the claim keeps the original names
    leaks = (SECRET, "H17", "250215", "cmc-h17-bucket", REMOTE, "a.zarr", "slab.tif")
    served = json.dumps([c.get("/plan").json(), c.get("/status").json()])
    on_disk = "".join((work / f).read_text() for f in ("scan.json", "status.json", "plan.json"))
    events = c.get("/events")  # the stream ends at a terminal stage
    for leak in leaks:
        assert leak not in served and leak not in on_disk and leak not in events.text, leak
    assert '"big"' not in served and "big/" not in served
    assert "remote" not in json.loads((work / "scan.json").read_text())


def test_progress_redacts_claimed_names(tmp_path, fake, make_app, monkeypatch):
    inp = claimed_only_input(tmp_path)
    c = make_app(inp)
    messages = []
    orig = server.Server.set_status

    def spy(self, stage, message, **extra):
        messages.append(message)
        orig(self, stage, message, **extra)

    monkeypatch.setattr(server.Server, "set_status", spy)
    c.post("/scan", json={"project_id": "proj"})
    wait_stage(c, ("planned", "failed"))
    assert any(m.startswith("read 1 file under") for m in messages)
    assert not any("big" in m.split() for m in messages)


def test_remote_scheme_checked_and_not_echoed(tmp_path, fake, make_app):
    c = make_app(claimed_only_input(tmp_path))
    for bad in ("http://h17.example.org/x.zarr", "file:///data/H17/x.zarr", "s3:/nohost", "H17_250215"):
        r = c.post("/scan", json={"project_id": "proj", "remote": [bad]})
        assert r.status_code == 422 and bad not in r.text and "H17" not in r.text
    assert c.post("/scan", json={"project_id": "proj", "remote": ["s3://bucket/key.zarr"]}).status_code == 202
    wait_stage(c, ("planned", "failed"))


def test_new_scan_clears_module_folder(tmp_path, fake, make_app):
    inp = claimed_only_input(tmp_path)
    c = make_app(inp)
    c.post("/scan", json={"project_id": "proj"})
    wait_stage(c, ("planned", "failed"))
    stale = tmp_path / "work" / "fake" / "stale.json"
    stale.write_text("{}")
    srv = c.app.state.server
    srv.reset_output()
    assert not (tmp_path / "work" / "fake").exists()
    stale.parent.mkdir()
    stale.write_text("{}")
    c.post("/scan", json={"project_id": "proj"})
    assert wait_stage(c, ("planned", "failed"))["stage"] == "planned"
    assert not stale.exists() and (tmp_path / "work" / "fake" / "claim.json").exists()


def test_terms_exclude_claimed_roots_after_restart(tmp_path, fake, make_app):
    inp = claimed_only_input(tmp_path)
    write_dicom(inp / "big" / SECRET / "1.dcm", PatientName="Hidden^Donor")
    c = make_app(inp)
    c.post("/scan", json={"project_id": "proj"})
    assert wait_stage(c, ("planned", "failed"))["stage"] == "planned"
    c.app.state.server.close()
    c2 = make_app(inp)  # a restarted server reads the roots back from claim.json
    terms = {t.lower() for t in c2.app.state.server.get_terms()}
    assert "hidden" not in terms


def test_unclaimed_input_still_runs_ezbids(tmp_path, monkeypatch, make_app):
    """With a module that claims part of the input, ezBIDS still runs on what is left."""
    m = FakeModule()
    monkeypatch.setattr(modality, "modules", lambda: (m,))
    monkeypatch.setattr(server, "client_from_env", lambda: None)
    seen = []

    def run(staged, **kw):
        seen.append(sorted(p.relative_to(staged).as_posix() for p in Path(staged).rglob("*")))
        (Path(staged) / "ezBIDS_core.json").write_text(json.dumps(EMPTY_CORE))
        return Path(staged) / "ezBIDS_core.json"

    monkeypatch.setattr(server, "run_ezbids", run)
    inp = make_input(tmp_path)
    c = make_app(inp)
    c.post("/scan", json={"project_id": "proj"})
    assert wait_stage(c, ("planned", "failed"))["stage"] == "planned"
    assert seen and "top.txt" in seen[0]
    assert not any(p.startswith(("big", "a.zarr")) for p in seen[0])
    shutil.rmtree(tmp_path / "work")
