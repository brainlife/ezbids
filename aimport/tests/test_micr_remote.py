"""Remote stores and files (micr/remote.py): URL rules, redirects, byte accounting.

Offline tests serve synthetic fixtures from a local threaded HTTP server with Range support;
``normalize_url`` is patched to let ``http://127.0.0.1`` through for those tests only. The
``network`` tests read the CMC public bucket (keys pinned in tests/DATASETS.md) by range request,
each under a byte cap asserted with its ByteCounter; nothing is downloaded whole.
"""
from __future__ import annotations

import gzip
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import nibabel as nib
import numpy as np
import pytest
import tifffile
import zarr
from micr_fixtures import ome_zarr

from aimport.micr import discover, readers, remote
from aimport.micr.readers import open_image

# --- local range server ------------------------------------------------------------------------


class _Handler(BaseHTTPRequestHandler):
    root: Path
    port: int

    def log_message(self, *args: object) -> None:  # keep test output quiet
        pass

    def _target(self) -> Path | None:
        rel = self.path.split("?", 1)[0].lstrip("/")
        path = (self.root / rel).resolve()
        if not str(path).startswith(str(self.root.resolve())) or not path.is_file():
            return None
        return path

    def _redirect(self) -> bool:
        if self.path.startswith("/redirect-other/"):  # another host, same port
            location = f"http://localhost:{self.port}/" + self.path[len("/redirect-other/"):]
        elif self.path.startswith("/redirect-same/"):
            location = "/" + self.path[len("/redirect-same/"):]
        else:
            return False
        self.send_response(302)
        self.send_header("Location", location)
        self.send_header("Content-Length", "0")
        self.end_headers()
        return True

    def _respond(self, body: bool) -> None:
        if self._redirect():
            return
        path = self._target()
        if path is None:
            self.send_response(404)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        size = path.stat().st_size
        start, end = 0, size - 1
        status = 200
        rng = self.headers.get("Range")
        if rng and rng.startswith("bytes="):
            a, _, b = rng[6:].partition("-")
            if a:
                start, end = int(a), min(int(b), size - 1) if b else size - 1
            else:  # suffix range
                start, end = max(0, size - int(b)), size - 1
            status = 206
        ctype = "image/tiff" if path.suffix == ".bin" else "application/octet-stream"
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(end - start + 1))
        if status == 206:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.end_headers()
        if body:
            with open(path, "rb") as fh:
                fh.seek(start)
                self.wfile.write(fh.read(end - start + 1))

    def do_GET(self) -> None:  # noqa: N802
        self._respond(True)

    def do_HEAD(self) -> None:  # noqa: N802
        self._respond(False)


@pytest.fixture
def server(tmp_path, monkeypatch):
    """(base URL, served folder). normalize_url lets this server's 127.0.0.1 URLs through."""
    root = tmp_path / "served"
    root.mkdir()
    handler = type("H", (_Handler,), {"root": root})
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    handler.port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{handler.port}"
    real = remote.normalize_url

    def normalize_for_tests(url: str) -> str:
        if url.startswith(base + "/") or url == base:
            return url.rstrip("/")
        return real(url)

    monkeypatch.setattr(remote, "normalize_url", normalize_for_tests)
    yield base, root
    httpd.shutdown()
    httpd.server_close()


def _store_bytes(store: Path) -> int:
    return sum(p.stat().st_size for p in store.rglob("*") if p.is_file())


# --- URL rules ---------------------------------------------------------------------------------

@pytest.mark.parametrize("url", [
    "file:///data/x.ome.zarr", "http://example.org/x.ome.zarr", "ftp://example.org/x.tif",
    "https://user@example.org/x.ome.zarr", "https://user:pw@example.org/x.ome.zarr",
    "https://127.0.0.1/x", "https://localhost/x", "https://[::1]/x", "https://10.0.0.1/x",
    "https://2130706433/x", "https://example.org/x.tif?X-Amz-Signature=1", "s3://", "",
])
def test_scheme_allowlist(url):
    with pytest.raises(ValueError):
        remote.normalize_url(url)


def test_refusal_never_names_the_url():
    secret = "https://user@h17-moe.example.org/MN27_250215/x.ome.zarr"
    with pytest.raises(ValueError) as exc:
        remote.normalize_url(secret)
    assert "h17" not in str(exc.value).lower() and "mn27" not in str(exc.value).lower()


def test_s3_rewrite():
    assert remote.normalize_url("s3://apex-connects/CMC/a.ome.zarr/") == \
        "https://apex-connects.s3.amazonaws.com/CMC/a.ome.zarr"
    assert remote.normalize_url("s3://apex-connects") == "https://apex-connects.s3.amazonaws.com"
    assert remote.normalize_url("HTTPS://Example.ORG:443/a/b/") == "https://example.org/a/b"


def test_redirect_rule():
    src = "https://bucket.s3.amazonaws.com/k"
    assert remote.redirect_allowed(src, "https://bucket.s3.us-east-2.amazonaws.com/k")
    assert remote.redirect_allowed(src, "/k2")
    assert remote.redirect_allowed("https://data.example.org/a", "https://data.example.org/b")
    assert not remote.redirect_allowed(src, "http://bucket.s3.us-east-2.amazonaws.com/k")
    assert not remote.redirect_allowed(src, "https://amazonaws.com.evil.example/k")
    assert not remote.redirect_allowed("https://data.example.org/a", "https://other.example.org/a")


# --- local server: redirects and byte accounting -----------------------------------------------

def test_redirect_to_other_host_refused(server):
    base, root = server
    ome_zarr(root / "s.ome.zarr", "0.5")
    mapper, counter = remote.open_store(f"{base}/redirect-other/s.ome.zarr")
    with pytest.raises(remote.RemoteRefused):
        zarr.open_group(mapper, mode="r")
    fh, _ = remote.open_file(f"{base}/s.ome.zarr/zarr.json")  # direct: fine
    fh.close()
    mapper, _ = remote.open_store(f"{base}/redirect-same/s.ome.zarr")  # same origin: followed
    assert zarr.open_group(mapper, mode="r").attrs["ome"]["version"] == "0.5"


def test_coarse_level_only(server):
    base, root = server
    store = ome_zarr(root / "s.ome.zarr", "0.5", shape=(1, 8, 256, 256), levels=4)
    mapper, counter = remote.open_store(f"{base}/s.ome.zarr")
    src = open_image(mapper, "ome-zarr")
    assert src.info.levels == 4 and src.info.ngff_version == "0.5"
    coarse = src.level(src.info.levels - 1).compute()
    assert coarse.shape[-2:] == (32, 32)
    expected = zarr.open_group(str(store), mode="r")["3"][...]
    assert np.array_equal(coarse.reshape(expected.shape), expected)
    assert 0 < counter.total < 0.05 * _store_bytes(store), (counter, _store_bytes(store))


def test_counter_counts_reads_through_dask_copies(server):
    """dask copies the store (and its filesystem) when building a graph; reads still count."""
    base, root = server
    store = ome_zarr(root / "s.ome.zarr", "0.5")
    mapper, counter = remote.open_store(f"{base}/s.ome.zarr")
    src = open_image(mapper, "ome-zarr")
    before = counter.total
    src.level(0).compute()
    shards = sum(p.stat().st_size for p in (store / "0").rglob("*") if p.is_file() and p.name != "zarr.json")
    assert counter.total - before >= shards  # the level's shards were counted, not zero


def test_byte_budget_stops_a_read(server):
    base, root = server
    (root / "big.tif").write_bytes(b"\0" * (3 * 2**20))
    fh, counter = remote.open_file(f"{base}/big.tif", max_bytes=2**20)
    fh.read(1000)
    with pytest.raises(remote.ByteBudgetExceeded):
        for _ in range(64):
            fh.seek(fh.tell() + remote.FILE_BLOCK_SIZE * 2)
            fh.read(remote.FILE_BLOCK_SIZE)
    assert counter.total < 2**20 + 4 * remote.FILE_BLOCK_SIZE  # stopped within one fetch
    fh.close()


def test_unbounded_read_refused(server):
    base, root = server
    (root / "big.tif").write_bytes(b"\0" * (3 * 2**20))
    fh, counter = remote.open_file(f"{base}/big.tif")
    with pytest.raises(remote.RemoteRefused):
        fh.read()
    assert counter.total == 0
    fh.close()


def test_remote_tiff_and_nifti_headers(server):
    base, root = server
    tifffile.imwrite(str(root / "t.tif"), np.arange(4 * 64 * 64, dtype=np.uint16).reshape(4, 64, 64),
                     photometric="minisblack", metadata=None)
    src, counter = remote.open_remote(f"{base}/t.tif", "tiff")
    assert src.info.shape[-2:] == (64, 64) and src.info.dtype == "uint16"
    assert int(src.level(0)[..., 0, 1, 1].compute()) == 64 + 1  # page 0, row 1, column 1
    src.close()
    img = nib.Nifti1Image(np.ones((32, 24, 4), np.float32), np.diag([0.01, 0.01, 0.0025, 1]))
    img.header.set_xyzt_units("mm")
    raw = img.to_bytes()
    (root / "e.nii.gz").write_bytes(gzip.compress(raw))
    src, counter = remote.open_remote(f"{base}/e.nii.gz", "nifti")
    assert src.info.shape[-3:] in {(4, 24, 32), (32, 24, 4)} and src.info.pixel_unit == "mm"
    assert counter.total < 2**20


def test_claim_probes_remote(server, tmp_path):
    base, root = server
    ome_zarr(root / "s.ome.zarr", "0.5")
    ome_zarr(root / "v2.ome.zarr", "0.4")
    tifffile.imwrite(str(root / "t.tif"), np.zeros((8, 8), np.uint16), metadata=None)
    (root / "tile.bin").write_bytes(b"II*\0" + b"\0" * 60)  # no extension: Content-Type image/tiff
    nib.save(nib.Nifti1Image(np.zeros((4, 4, 2), np.float32), np.eye(4)), str(root / "e.nii"))
    (root / "notes.txt").write_text("hello")
    urls = [f"{base}/{n}" for n in ("s.ome.zarr/", "v2.ome.zarr", "t.tif", "tile.bin", "e.nii",
                                    "notes.txt", "missing.ome.zarr")]
    claim, found = discover.claim(tmp_path / "empty", urls + ["file:///etc/passwd"])
    assert claim.remote == [f"{base}/{n}" for n in ("s.ome.zarr", "v2.ome.zarr", "t.tif", "tile.bin", "e.nii")]
    assert [f.family for f in found] == ["ome-zarr", "ome-zarr", "tiff", "tiff", "nifti"]
    assert claim.roots == []


# --- VISoR metadata key names (real CMC structure, synthetic values) ---------------------------

def test_visor_real_key_names():
    """acqinfo_metadata.json as CMC writes it (version 0.0.3; key names in DATASETS.md)."""
    meta = {
        "version": "0.0.3", "channels": 1, "excitation_wavelengths": ["488nm"],
        "positions": [{"x_start_um": -100.0, "x_end_um": 100.0, "y_start_um": -5.0,
                       "z_start_um": -40.0, "x_step_um": 2.5}],
        "settings": {"sheet_angle": 45.0, "pixel_spacing_um": 0.96, "image_size_xy": [2048, 1024],
                     "frames_per_file": 1025, "strip_overlap_pixels": -851.0, "dtype": "uint16",
                     "flipped": False, "rotated": False},
        "stripdirs": ["synthetic"], "file": "synthetic",
    }
    size, channel = readers.visor_facts(meta)
    assert size == {"x": 0.96, "y": 0.96, "z": 2.5} and channel == 488.0
    assert readers.visor_facts({"excitation_wavelengths": ["laser on"]}) == ({}, None)


# --- network: the CMC public bucket (keys pinned in DATASETS.md) -------------------------------

CMC = "s3://apex-connects/"
CAP = 32 * 2**20
PSOCT_ZARR = CMC + "CMC/Derivatives/Moe/PS-OCT/Zarr/Moe_Slice_051.ome.zarr"
EXASPIM_POS = CMC + "axonal_connectomics/deskewed/H17_PO10_S5_20250417/exaSPIM.zarr/Pos0"
VISOR_TILE = CMC + ("CMC/Raw/Moe/tract-tracing/MN27_FH_S100_250215_visor_488/visor_488_Pos0/"
                    "visor_488_0_0.tif")
ENFACE_NIFTI = CMC + "CMC/Derivatives/Moe/PS-OCT/Enface/Registration/Retardance/Slice_001_EnR_hdr.nii.gz"


@pytest.mark.network
def test_cmc_psoct_zarr_metadata():
    src, counter = remote.open_remote(PSOCT_ZARR, "ome-zarr", max_bytes=CAP)
    info = src.info
    assert (info.ngff_version, info.zarr_format, info.axes, info.levels) == ("0.5", 3, "cyx", 6)
    coarse = src.level(info.levels - 1).compute()
    assert coarse.shape == (4, 16, 21)
    print(f"psoct bytes={counter.total}")
    assert counter.total < CAP


@pytest.mark.network
def test_cmc_exaspim_position():
    mapper, counter = remote.open_store(EXASPIM_POS, max_bytes=CAP)
    src = open_image(mapper, "ome-zarr")
    info = src.info
    assert info.zarr_format == 3 and info.axes == "tczyx" and info.levels == 6
    assert info.pixel_unit == "um" and info.pixel_size["z"] == pytest.approx(0.65)
    group = zarr.open_group(mapper, mode="r")
    assert all(group[str(i)].shards is not None for i in range(info.levels))  # sharded
    coarse = src.level(info.levels - 1)
    block = coarse[0, 0, :64, :64, :64].compute()  # one inner chunk of the coarsest level
    assert block.shape == (64, 64, 64)
    print(f"exaspim bytes={counter.total}")
    assert counter.total < CAP


@pytest.mark.network
def test_cmc_visor_tile_header():
    """Header plus one strip of a 4.3 GB VISoR tile; pixel size and channel from acqinfo."""
    limit = 8 * 2**20
    fh, counter = remote.open_file(VISOR_TILE, max_bytes=limit)
    with tifffile.TiffFile(fh) as tif:
        page = tif.pages.first
        assert (page.shape, str(page.dtype), page.compression, len(page.dataoffsets)) == \
            ((1024, 2048), "uint16", 1, 1)
        strip = page.asarray()  # the page's one strip: 4 MiB
        assert strip.shape == (1024, 2048)
    meta = remote.sibling_json(remote.normalize_url(VISOR_TILE), "acqinfo_metadata.json")
    assert meta is not None
    size, channel = readers.visor_facts(meta)
    assert size == {"x": 0.96, "y": 0.96, "z": 2.5} and channel == 488.0
    print(f"visor bytes={counter.total}")
    assert counter.total < limit


@pytest.mark.network
def test_cmc_enface_nifti_header():
    limit = 2**20
    src, counter = remote.open_remote(ENFACE_NIFTI, "nifti", max_bytes=limit)
    info = src.info
    assert info.dtype == "float32" and info.pixel_unit == "mm" and 11000 in info.shape
    print(f"enface bytes={counter.total}")
    assert counter.total < limit
