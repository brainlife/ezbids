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
    ignore_range = False  # answer 200 with the whole body, whatever Range asks
    other_base = ""  # where /redirect-to-other-server/ points

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
        elif self.path.startswith("/redirect-to-other-server/") and self.other_base:
            location = self.other_base + "/" + self.path[len("/redirect-to-other-server/"):]
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
        if rng and rng.startswith("bytes=") and not self.ignore_range:
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


def _start(root: Path, **attrs: object) -> tuple[str, ThreadingHTTPServer, type]:
    root.mkdir(parents=True, exist_ok=True)
    handler = type("H", (_Handler,), {"root": root, **attrs})
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    handler.port = httpd.server_address[1]
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{handler.port}", httpd, handler


@pytest.fixture
def local_servers(tmp_path, monkeypatch):
    """start(name, **handler attrs) -> (base URL, served folder, handler class). normalize_url
    lets these servers' http://127.0.0.1 URLs through (these tests only)."""
    started: list[ThreadingHTTPServer] = []
    real = remote.normalize_url

    def normalize_for_tests(url: str) -> str:
        if url.startswith("http://127.0.0.1:"):
            return url.rstrip("/")
        return real(url)

    monkeypatch.setattr(remote, "normalize_url", normalize_for_tests)

    def start(name: str, **attrs: object) -> tuple[str, Path, type]:
        base, httpd, handler = _start(tmp_path / name, **attrs)
        started.append(httpd)
        return base, tmp_path / name, handler

    yield start
    for httpd in started:
        httpd.shutdown()
        httpd.server_close()


@pytest.fixture
def server(local_servers):
    """(base URL, served folder) of one Range-supporting local server."""
    base, root, _ = local_servers("served")
    return base, root


def _store_bytes(store: Path) -> int:
    return sum(p.stat().st_size for p in store.rglob("*") if p.is_file())


# --- URL rules ---------------------------------------------------------------------------------

@pytest.mark.parametrize("url", [
    "file:///data/x.ome.zarr", "http://example.org/x.ome.zarr", "ftp://example.org/x.tif",
    "https://user@example.org/x.ome.zarr", "https://user:pw@example.org/x.ome.zarr",
    "https://127.0.0.1/x", "https://localhost/x", "https://[::1]/x", "https://10.0.0.1/x",
    "https://2130706433/x", "https://example.org/x.tif?X-Amz-Signature=1", "s3://", "",
    "https://localhost./x", "https://LOCALHOST./x", "https://foo.localhost/x", "https://foo.localhost./x",
    "https://intranet/x", "https://intranet./x", "https://127.0.0.1./x",
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
    assert remote.normalize_url("https://example.org./a") == "https://example.org/a"


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


def test_redirect_to_allowed_host_followed(local_servers, monkeypatch):
    """A redirect to a host the rule allows is followed (the rule is patched to allow server two)."""
    base2, root2, _ = local_servers("two")
    base1, _, handler1 = local_servers("one")
    handler1.other_base = base2
    ome_zarr(root2 / "s.ome.zarr", "0.5")
    real = remote.redirect_allowed
    monkeypatch.setattr(remote, "redirect_allowed",
                        lambda origin, location: location.startswith(base2 + "/") or real(origin, location))
    mapper, counter = remote.open_store(f"{base1}/redirect-to-other-server/s.ome.zarr")
    src = open_image(mapper, "ome-zarr")
    assert src.info.levels == 2 and counter.total > 0
    remote.close_store(mapper)
    monkeypatch.setattr(remote, "redirect_allowed", real)  # without the patch: refused
    mapper, _ = remote.open_store(f"{base1}/redirect-to-other-server/s.ome.zarr")
    with pytest.raises(remote.RemoteRefused):
        zarr.open_group(mapper, mode="r")
    remote.close_store(mapper)


def test_default_byte_cap(server):
    base, root = server
    (root / "f.tif").write_bytes(b"\0" * 1000)
    for opener in (remote.open_store, remote.open_file):
        handle, counter = opener(f"{base}/f.tif")
        assert counter.limit == remote.DEFAULT_MAX_BYTES == 32 * 2**20
        handle.close() if hasattr(handle, "close") else remote.close_store(handle)
    for bad in (None, 0, -1):
        with pytest.raises(ValueError):
            remote.open_file(f"{base}/f.tif", max_bytes=bad)


def test_read_beyond_remaining_cap_refused(server):
    base, root = server
    (root / "f.tif").write_bytes(b"\1" * (2 * 2**20))
    fh, counter = remote.open_file(f"{base}/f.tif", max_bytes=2**20)
    assert len(fh.read(1000)) == 1000
    with pytest.raises(remote.ByteBudgetExceeded):
        fh.read(2**20)  # more than is left of the cap: refused before any fetch
    total = counter.total
    with pytest.raises(remote.ByteBudgetExceeded):
        fh.readinto(bytearray(2**20))
    assert counter.total == total
    fh.close()


def test_server_ignoring_range_is_stopped_by_the_cap(local_servers):
    """A server that answers every Range request with 200 and the whole body: the cap stops it."""
    base, root, _ = local_servers("norange", ignore_range=True)
    store = root / "big.ome.zarr"
    group = zarr.open_group(str(store), mode="w", zarr_format=3)
    big = group.create_array("0", shape=(40 * 2**20,), dtype="uint8", chunks=(2**20,),
                             shards=(40 * 2**20,), compressors=None)
    big[...] = np.random.default_rng(0).integers(0, 255, size=big.shape, dtype=np.uint8)
    mapper, counter = remote.open_store(f"{base}/big.ome.zarr")  # default cap: 32 MiB
    arr = zarr.open_group(mapper, mode="r")["0"]
    with pytest.raises(remote.ByteBudgetExceeded):
        arr[:16]  # one inner chunk: a range read of the shard, answered with all 40 MiB
    assert counter.total <= remote.DEFAULT_MAX_BYTES + 2**20
    remote.close_store(mapper)
    fh, counter = remote.open_file(f"{base}/big.ome.zarr/0/c/0")
    assert len(fh.read(100)) == 100  # from the start: fsspec stops reading after the first MiB
    with pytest.raises(ValueError):
        fh.seek(5 * 2**20)
        fh.read(100)  # past the start: refused, the body is not read
    assert counter.total <= 2 * 2**20
    fh.close()


def test_sessions_closed(server, caplog):
    """Closing a store, a file or a source closes its aiohttp session: no 'Unclosed' warnings."""
    import gc
    import warnings

    base, root = server
    ome_zarr(root / "s.ome.zarr", "0.5")
    tifffile.imwrite(str(root / "t.tif"), np.zeros((8, 8), np.uint16), metadata=None)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        src, _ = remote.open_remote(f"{base}/s.ome.zarr", "ome-zarr")
        src.level(1).compute()
        src.close()
        with remote.open_remote(f"{base}/t.tif", "tiff")[0] as tsrc:
            tsrc.level(0).compute()
        assert remote.probe(f"{base}/t.tif") == "tiff"
        del src, tsrc
        gc.collect()
    messages = [str(w.message) for w in caught] + [r.getMessage() for r in caplog.records]
    assert not [m for m in messages if "Unclosed" in m], messages
    # explicitly closed at close(), not only when collected
    mapper, _ = remote.open_store(f"{base}/s.ome.zarr")
    zarr.open_group(mapper, mode="r")
    session = mapper.fs._session
    assert session is not None and not session.closed
    remote.close_store(mapper)
    assert session.closed
    fh, _ = remote.open_file(f"{base}/t.tif")
    fh.read(10)
    session = fh._fs._session
    assert not session.closed
    fh.close()
    assert session.closed


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
