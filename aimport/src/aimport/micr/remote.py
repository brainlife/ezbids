"""Remote microscopy sources: OME-Zarr stores and single files read by HTTP range request.

Only ``https://`` and ``s3://`` URLs are accepted (``s3://b/k`` becomes
``https://b.s3.amazonaws.com/k``); reads are anonymous, redirects are followed only to the same
origin or to an ``https`` ``*.amazonaws.com`` host, and every fetched byte is counted by a
``ByteCounter``, which can also stop a read that goes over a byte budget. Large data is never
downloaded whole: a store is read through zarr (metadata and the chunks asked for), a file through
a block-cached file object.

Remote URLs are local-only (Global Constraints): no message raised here contains the URL.
"""
from __future__ import annotations

import ipaddress
import itertools
import json
import logging
import re
import weakref
from typing import Any
from urllib.parse import urlsplit

import aiohttp
import fsspec
from fsspec.implementations.http import HTTPFileSystem

__all__ = [
    "ALLOWED_FAMILIES", "BLOCK_SIZE", "FILE_BLOCK_SIZE", "ByteBudgetExceeded", "ByteCounter",
    "RemoteRefused", "normalize_url", "open_file", "open_remote", "open_store", "probe",
    "redirect_allowed", "sibling_json",
]

log = logging.getLogger(__name__)

BLOCK_SIZE = 2**20
FILE_BLOCK_SIZE = 2**16  # single files: headers are small, keep each range read small too
ALLOWED_FAMILIES = ("ome-zarr", "nifti", "tiff")
VISOR_META_MAX_BYTES = 2**20
_BUCKET = re.compile(r"[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]")


class RemoteRefused(ValueError):
    """A remote source or a redirect that the remote rules do not allow."""


class ByteBudgetExceeded(RuntimeError):
    """More bytes were fetched than the counter's budget allows."""


_COUNTERS: "weakref.WeakValueDictionary[int, ByteCounter]" = weakref.WeakValueDictionary()
_COUNTER_IDS = itertools.count()


def _counter(key: int, limit: int | None) -> "ByteCounter":
    found = _COUNTERS.get(key)
    return found if found is not None else ByteCounter(limit)


class ByteCounter:
    """Counts every response-body byte fetched; raises once ``limit`` (if set) is passed.

    A copy made by pickling in this process (dask copies the zarr store, and the filesystem with
    it, when it builds a graph) is the same counter, so reads through the copy are counted too.
    """

    def __init__(self, limit: int | None = None):
        self.total = 0
        self.requests = 0
        self.limit = limit
        self._key = next(_COUNTER_IDS)
        _COUNTERS[self._key] = self

    def __reduce__(self) -> tuple:
        return _counter, (self._key, self.limit)

    def add(self, n: int) -> None:
        self.total += n
        if self.limit is not None and self.total > self.limit:
            raise ByteBudgetExceeded(f"remote read over budget: {self.total} > {self.limit} bytes")

    def __repr__(self) -> str:
        return f"ByteCounter(total={self.total}, requests={self.requests})"


# --- URL rules --------------------------------------------------------------------------------

def _host_refused(host: str) -> bool:
    if not host or host == "localhost" or host.endswith(".localhost"):
        return True
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        pass
    last = host.rstrip(".").rsplit(".", 1)[-1]
    return not re.search(r"[a-z]", last) or last.startswith("0x")  # 2130706433, 127.1, 0x7f.1


def normalize_url(url: str) -> str:
    """The canonical https URL of a remote source; ``ValueError`` (``RemoteRefused``) otherwise."""
    if not isinstance(url, str) or any(c.isspace() for c in url):
        raise RemoteRefused("remote source is not a URL")
    parts = urlsplit(url.strip())
    scheme = parts.scheme.lower()
    if scheme not in ("https", "s3"):
        raise RemoteRefused("remote sources must be https:// or s3:// URLs")
    if "@" in parts.netloc or parts.username is not None or parts.password is not None:
        raise RemoteRefused("remote URLs must not carry user information")
    if parts.query or parts.fragment:
        raise RemoteRefused("remote URLs must not carry a query or fragment (anonymous reads only)")
    host = (parts.hostname or "").lower()
    if scheme == "s3":
        if parts.port is not None or not _BUCKET.fullmatch(host):
            raise RemoteRefused("s3:// URLs must name a bucket")
        path = parts.path.strip("/")
        return f"https://{host}.s3.amazonaws.com" + (f"/{path}" if path else "")
    if _host_refused(host):
        raise RemoteRefused("remote host must be a DNS name (not an IP address or localhost)")
    netloc = host if parts.port in (None, 443) else f"{host}:{parts.port}"
    return f"https://{netloc}{parts.path.rstrip('/')}"


def _origin(url: str) -> tuple[str, str]:
    p = urlsplit(url)
    return p.scheme.lower(), (p.netloc or "").lower()


def redirect_allowed(origin_url: str, location: str) -> bool:
    """Same origin as the request, or an https ``*.amazonaws.com`` host."""
    target = urlsplit(location)
    if not target.scheme and not target.netloc:  # relative: same origin
        return True
    if _origin(location) == _origin(origin_url):
        return True
    host = (target.hostname or "").lower()
    return (target.scheme.lower() == "https" and target.username is None and target.port in (None, 443)
            and host.endswith(".amazonaws.com"))


# --- HTTP plumbing ----------------------------------------------------------------------------

class _CountingStream:
    """Wraps an aiohttp StreamReader so every body byte read is counted (and capped) as it arrives."""

    def __init__(self, inner: Any, counter: ByteCounter):
        self._inner, self._counter = inner, counter

    async def read(self, n: int = -1) -> bytes:
        if n >= 0:
            data = await self._inner.read(n)
            self._counter.add(len(data))
            return data
        parts = []
        while True:  # read-to-end piecewise so the budget stops an oversized body early
            chunk = await self._inner.readany()
            if not chunk:
                return b"".join(parts)
            self._counter.add(len(chunk))
            parts.append(chunk)

    async def readany(self) -> bytes:
        data = await self._inner.readany()
        self._counter.add(len(data))
        return data

    async def readexactly(self, n: int) -> bytes:
        data = await self._inner.readexactly(n)
        self._counter.add(len(data))
        return data

    async def readchunk(self) -> tuple[bytes, bool]:
        data, end = await self._inner.readchunk()
        self._counter.add(len(data))
        return data, end

    async def readline(self) -> bytes:
        data = await self._inner.readline()
        self._counter.add(len(data))
        return data

    def iter_chunked(self, n: int) -> Any:
        async def gen() -> Any:
            while True:
                data = await self.read(n)
                if not data:
                    return
                yield data
        return gen()

    def iter_any(self) -> Any:
        async def gen() -> Any:
            while True:
                data = await self.readany()
                if not data:
                    return
                yield data
        return gen()

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)


def _client_factory(counter: ByteCounter) -> Any:
    class _Response(aiohttp.ClientResponse):
        async def start(self, connection: Any) -> Any:
            resp = await super().start(connection)
            counter.requests += 1
            self.content = _CountingStream(self.content, counter)  # type: ignore[assignment]
            return resp

    async def on_redirect(session: Any, ctx: Any, params: Any) -> None:
        location = params.response.headers.get("Location", "")
        if not redirect_allowed(str(params.url), location):
            raise RemoteRefused("redirect to another host refused")

    async def get_client(**kwargs: Any) -> aiohttp.ClientSession:
        trace = aiohttp.TraceConfig()
        trace.on_request_redirect.append(on_redirect)
        return aiohttp.ClientSession(response_class=_Response, trace_configs=[trace], **kwargs)

    return get_client


def _filesystem(counter: ByteCounter, asynchronous: bool = False) -> HTTPFileSystem:
    return HTTPFileSystem(block_size=BLOCK_SIZE, client_kwargs={"trust_env": False},
                          get_client=_client_factory(counter), skip_instance_cache=True,
                          asynchronous=asynchronous)


def open_store(url: str, max_bytes: int | None = None) -> tuple[fsspec.FSMap, ByteCounter]:
    """An fsspec mapper on a remote store, for ``readers.open_image(mapper, "ome-zarr")``.

    The filesystem is asynchronous so that zarr uses it as is: given a synchronous one, zarr
    rebuilds an asynchronous copy from its JSON form, which drops the counting client and the
    redirect rule. Use the mapper through zarr, not as a synchronous dict.
    """
    counter = ByteCounter(max_bytes)
    fs = _filesystem(counter, asynchronous=True)
    return fs.get_mapper(normalize_url(url)), counter


def open_file(url: str, max_bytes: int | None = None,
              block_size: int = FILE_BLOCK_SIZE) -> tuple[Any, ByteCounter]:
    """A seekable, block-cached file object on a remote file; only the blocks read are fetched,
    and ``read()`` with no size is refused unless what is left is at most ``BLOCK_SIZE``."""
    counter = ByteCounter(max_bytes)
    fs = _filesystem(counter)
    fh = fs.open(normalize_url(url), "rb", block_size=block_size, cache_type="bytes")
    if fh.size is None:
        fh.close()
        raise RemoteRefused("remote file has no known size (range reads need one)")
    return _RemoteFile(fh), counter


class _RemoteFile:
    """A remote file that refuses ``read()`` of everything at once (fsspec would fetch it whole)."""

    def __init__(self, fh: Any):
        self._fh = fh

    def read(self, n: int = -1) -> bytes:
        if n is None or n < 0:
            n = self._fh.size - self._fh.tell()
            if n > BLOCK_SIZE:
                raise RemoteRefused("unbounded read of a remote file refused")
        return self._fh.read(n)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._fh, name)

    def __enter__(self) -> "_RemoteFile":
        return self

    def __exit__(self, *exc: object) -> None:
        self._fh.close()


# --- probing and opening ----------------------------------------------------------------------

_MISSING = (FileNotFoundError, aiohttp.ClientResponseError)


def _family_from_name(path: str) -> str | None:
    low = path.lower().rsplit("/", 1)[-1]
    if low.endswith((".nii", ".nii.gz")):
        return "nifti"
    if low.endswith((".tif", ".tiff", ".btf")):
        return "tiff"
    return None


def _family_from_type(mimetype: str | None) -> str | None:
    mt = (mimetype or "").lower()
    if mt == "image/tiff":
        return "tiff"
    if mt in ("application/x-nifti", "application/nifti", "image/nifti"):
        return "nifti"
    return None


def probe(url: str, max_bytes: int = 2**20) -> str | None:
    """The family of a remote source (``ALLOWED_FAMILIES``), or None when it is none of them.

    Probes ``<url>/zarr.json``, then ``<url>/.zattrs``, then (single files) the extension and the
    HTTP Content-Type of a HEAD request. Reads at most ``max_bytes``.
    """
    norm = normalize_url(url)
    fs = _filesystem(ByteCounter(max_bytes))
    for marker in ("zarr.json", ".zattrs"):
        try:
            json.loads(fs.cat_file(f"{norm}/{marker}"))
            return "ome-zarr"
        except _MISSING:
            continue
        except ValueError as exc:  # not JSON: not a store marker
            if isinstance(exc, RemoteRefused):
                raise
            continue
    try:
        info = fs.info(norm)
    except _MISSING:
        return None
    if info.get("type") != "file":
        return None
    return _family_from_name(urlsplit(norm).path) or _family_from_type(info.get("mimetype"))


def sibling_json(url: str, name: str, max_bytes: int = VISOR_META_MAX_BYTES) -> dict | None:
    """``name`` next to the file at url or one folder up (VISoR acqinfo_metadata.json), or None."""
    base = url.rsplit("/", 1)[0]
    fs = _filesystem(ByteCounter(max_bytes))
    for folder in (base, base.rsplit("/", 1)[0]):
        try:
            data = fs.cat_file(f"{folder}/{name}")
        except _MISSING:
            continue
        try:
            meta = json.loads(data.decode("utf-8", errors="replace"))
        except ValueError:
            return None
        return meta if isinstance(meta, dict) else None
    return None


def open_remote(url: str, family: str, max_bytes: int | None = None) -> tuple[Any, ByteCounter]:
    """``readers.open_image`` on a remote source: (ImageSource, ByteCounter of its reads).

    ``family`` is ``ome-zarr``, ``nifti``, ``tiff`` or ``visor`` (a TIFF tile whose pixel size and
    channel come from ``acqinfo_metadata.json`` next to it or one folder up).
    """
    from . import readers

    fam = family.lower()
    if fam == "ome-zarr":
        mapper, counter = open_store(url, max_bytes)
        return readers.open_image(mapper, "ome-zarr"), counter
    if fam not in ("nifti", "tiff", "visor"):
        raise RemoteRefused(f"family {family!r} is not read remotely")
    fh, counter = open_file(url, max_bytes)
    try:
        src = readers.open_image(fh, fam)
    except BaseException:
        fh.close()
        raise
    if fam == "visor":
        meta = sibling_json(normalize_url(url), "acqinfo_metadata.json")
        if meta is not None:
            readers.apply_visor_meta(src, meta)
    return src, counter
