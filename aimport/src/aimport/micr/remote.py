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
    "ALLOWED_FAMILIES", "BLOCK_SIZE", "DEFAULT_MAX_BYTES", "close_store", "FILE_BLOCK_SIZE", "ByteBudgetExceeded", "ByteCounter",
    "RemoteRefused", "normalize_url", "open_file", "open_remote", "open_store", "probe",
    "redirect_allowed", "sibling_json", "open_stream", "MAX_REDIRECTS",
]

log = logging.getLogger(__name__)

BLOCK_SIZE = 2**20
DEFAULT_MAX_BYTES = 32 * 2**20  # every remote read has a byte cap; callers may pass another one
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
    """IP literals, localhost (and *.localhost) and single-label hosts; ``host`` has no trailing dot."""
    if not host or "." not in host:  # empty, or a single label: intranet, localhost
        return True
    if host == "localhost" or host.endswith(".localhost"):
        return True
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        pass
    last = host.rsplit(".", 1)[-1]
    return not re.search(r"[a-z]", last) or last.startswith("0x")  # 127.1, 0x7f.1


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
    host = (parts.hostname or "").lower().rstrip(".")  # "localhost." is localhost
    if scheme == "s3":
        if parts.port is not None or not _BUCKET.fullmatch(host):
            raise RemoteRefused("s3:// URLs must name a bucket")
        path = parts.path.strip("/")
        return f"https://{host}.s3.amazonaws.com" + (f"/{path}" if path else "")
    if _host_refused(host):
        raise RemoteRefused("remote host must be a dotted DNS name (not an IP address or localhost)")
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


MAX_REDIRECTS = 5
STREAM_TIMEOUT_S = 30.0
_RANGE = re.compile(r"bytes=(?:[0-9]{1,19}-[0-9]{0,19}|-[0-9]{1,19})")


class RangeUnsupported(ValueError):
    """A Range header that is not one ``bytes=`` range (a multi-range or another unit): never forwarded,
    and never turned into an un-ranged GET (the proxy answers 416)."""


def range_ok(range_header: str | None) -> bool:
    """Whether a Range header can be forwarded upstream: absent, or a single ``bytes=`` range."""
    return not range_header or _RANGE.fullmatch(range_header.strip()) is not None


def new_stream_client() -> Any:
    """A pooled httpx client for the QA viewer's chunk proxy (a TLS handshake per chunk would make the
    viewer crawl). The server owns one per app and closes it when the app stops."""
    import httpx

    return httpx.Client(follow_redirects=False, trust_env=False, timeout=STREAM_TIMEOUT_S,
                        limits=httpx.Limits(max_connections=32, max_keepalive_connections=16))


def open_stream(url: str, range_header: str | None, method: str, client: Any) -> Any:
    """A streamed anonymous GET (or HEAD) of one object for the QA viewer's chunk proxy, on ``client``
    (new_stream_client): the httpx response, not yet read (the caller reads it with ``iter_raw`` and closes
    it). Only ``Range`` is forwarded, and only a single ``bytes=`` range (anything else is RangeUnsupported),
    with ``Accept-Encoding: identity`` so the body is the stored bytes. Redirects are followed by the remote
    rule (``redirect_allowed``, at most MAX_REDIRECTS); another is ``RemoteRefused``. url is a
    ``reference.resolve`` result (already normalised). httpx errors propagate."""
    from urllib.parse import urljoin

    if method not in ("GET", "HEAD"):
        raise ValueError("GET or HEAD only")
    if not range_ok(range_header):
        raise RangeUnsupported("only a single bytes= range is forwarded")
    headers = {"Accept-Encoding": "identity"}
    if range_header:
        headers["Range"] = range_header.strip()
    import httpx

    def send(target: str) -> Any:
        try:
            return client.send(client.build_request(method, target, headers=headers), stream=True)
        except (httpx.ConnectError, httpx.RemoteProtocolError):  # a pooled connection dropped: once more
            return client.send(client.build_request(method, target, headers=headers), stream=True)

    for _ in range(MAX_REDIRECTS + 1):
        response = send(url)
        if not response.is_redirect:
            return response
        location = response.headers.get("location", "")
        response.close()
        if not redirect_allowed(url, location):
            raise RemoteRefused("redirect to another host refused")
        url = urljoin(url, location)
    raise RemoteRefused("too many redirects")


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


def _close_session(session: Any) -> None:
    """Close an aiohttp session from any thread (on its own loop when that loop still runs)."""
    if session is not None and not session.closed:
        HTTPFileSystem.close_session(getattr(session, "_loop", None), session)


_FILESYSTEMS: "weakref.WeakValueDictionary[int, _CountingHTTPFileSystem]" = weakref.WeakValueDictionary()


def _filesystem_copy(key: int, counter: ByteCounter, asynchronous: bool) -> "_CountingHTTPFileSystem":
    found = _FILESYSTEMS.get(key)
    return found if found is not None else _CountingHTTPFileSystem(counter, asynchronous)


class _CountingHTTPFileSystem(HTTPFileSystem):
    """HTTPFileSystem with the counting client and redirect rule; one aiohttp session, closed by
    ``close()`` or when the filesystem is collected. A pickled copy in this process (dask copies the
    zarr store when it builds a graph) is the same filesystem, so it shares the session."""

    cachable = False  # fsspec's instance cache would hand a new caller another caller's counter

    def __init__(self, counter: ByteCounter, asynchronous: bool = False):
        super().__init__(block_size=BLOCK_SIZE, client_kwargs={"trust_env": False},
                         get_client=_client_factory(counter), asynchronous=asynchronous)
        self.counter = counter
        self._key = next(_COUNTER_IDS)
        _FILESYSTEMS[self._key] = self
        self._finalizer: Any = None

    def __reduce__(self) -> tuple:
        return _filesystem_copy, (self._key, self.counter, self.asynchronous)

    async def set_session(self) -> Any:
        session = await super().set_session()
        if self._finalizer is None:
            self._finalizer = weakref.finalize(self, _close_session, session)
        return session

    def close(self) -> None:
        if self._finalizer is not None:
            self._finalizer()  # runs _close_session once
        self._session = None
        self._finalizer = None


def _filesystem(counter: ByteCounter, asynchronous: bool = False) -> _CountingHTTPFileSystem:
    return _CountingHTTPFileSystem(counter, asynchronous)


def _cap(max_bytes: int) -> int:
    if isinstance(max_bytes, bool) or not isinstance(max_bytes, int) or max_bytes <= 0:
        raise ValueError("max_bytes must be a positive number of bytes (remote reads are always capped)")
    return max_bytes


def open_store(url: str, max_bytes: int = DEFAULT_MAX_BYTES) -> tuple[fsspec.FSMap, ByteCounter]:
    """An fsspec mapper on a remote store, for ``readers.open_image(mapper, "ome-zarr")``.

    Reads stop with ``ByteBudgetExceeded`` past ``max_bytes``. The filesystem is asynchronous so
    that zarr uses it as is: given a synchronous one, zarr rebuilds an asynchronous copy from its
    JSON form, which drops the counting client and the redirect rule. Use the mapper through zarr,
    not as a synchronous dict, and ``close_store(mapper)`` when done.
    """
    counter = ByteCounter(_cap(max_bytes))
    fs = _filesystem(counter, asynchronous=True)
    return fs.get_mapper(normalize_url(url)), counter


def close_store(mapper: Any) -> None:
    """Close the HTTP session behind a mapper from ``open_store``."""
    fs = getattr(mapper, "fs", None)
    if isinstance(fs, _CountingHTTPFileSystem):
        fs.close()


def open_file(url: str, max_bytes: int = DEFAULT_MAX_BYTES,
              block_size: int = FILE_BLOCK_SIZE) -> tuple[Any, ByteCounter]:
    """A seekable, block-cached file object on a remote file; only the blocks read are fetched.

    ``read()`` with no size is refused unless what is left is at most ``BLOCK_SIZE``, and a read
    larger than what is left of the byte cap is refused. Closing it closes its HTTP session.
    """
    counter = ByteCounter(_cap(max_bytes))
    fs = _filesystem(counter)
    try:
        fh = fs.open(normalize_url(url), "rb", block_size=block_size, cache_type="bytes")
    except BaseException:
        fs.close()
        raise
    if fh.size is None:
        fh.close()
        fs.close()
        raise RemoteRefused("remote file has no known size (range reads need one)")
    return _RemoteFile(fh, fs, counter), counter


class _RemoteFile:
    """A remote file that refuses unbounded reads and reads beyond its byte cap."""

    def __init__(self, fh: Any, fs: _CountingHTTPFileSystem, counter: ByteCounter):
        self._fh, self._fs, self._counter = fh, fs, counter

    def read(self, n: int = -1) -> bytes:
        if n is None or n < 0:
            n = self._fh.size - self._fh.tell()
            if n > BLOCK_SIZE:
                raise RemoteRefused("unbounded read of a remote file refused")
        left = self._counter.limit - self._counter.total if self._counter.limit is not None else n
        if n > left:
            raise ByteBudgetExceeded(f"read of {n} bytes refused: {left} bytes left of the byte cap")
        return self._fh.read(n)

    def readinto(self, buffer: Any) -> int:
        view = memoryview(buffer).cast("B")
        data = self.read(len(view))
        view[: len(data)] = data
        return len(data)

    def close(self) -> None:
        try:
            self._fh.close()
        finally:
            self._fs.close()

    def __getattr__(self, name: str) -> Any:
        return getattr(self._fh, name)

    def __enter__(self) -> "_RemoteFile":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


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
    fs = _filesystem(ByteCounter(_cap(max_bytes)))
    try:
        return _probe(fs, norm)
    finally:
        fs.close()


def _probe(fs: HTTPFileSystem, norm: str) -> str | None:
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
    fs = _filesystem(ByteCounter(_cap(max_bytes)))
    try:
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
    finally:
        fs.close()


def _close_also(src: Any, closer: Any) -> None:
    """Make ``src.close()`` also run closer (the source's HTTP session)."""
    inner = src.close

    def close() -> None:
        try:
            inner()
        finally:
            closer()

    src.close = close


def open_remote(url: str, family: str, max_bytes: int = DEFAULT_MAX_BYTES,
                block_size: int = FILE_BLOCK_SIZE) -> tuple[Any, ByteCounter]:
    """``readers.open_image`` on a remote source: (ImageSource, ByteCounter of its reads).

    ``family`` is ``ome-zarr``, ``nifti``, ``tiff`` or ``visor`` (a TIFF tile whose pixel size and
    channel come from ``acqinfo_metadata.json`` next to it or one folder up). Closing the source
    closes its HTTP session. ``block_size`` is a file's read-ahead (conversion passes a small one:
    its strips are read concurrently, so read-ahead would mostly be fetched and dropped).
    """
    from . import readers

    fam = family.lower()
    if fam == "ome-zarr":
        mapper, counter = open_store(url, max_bytes)
        try:
            src = readers.open_image(mapper, "ome-zarr")
        except BaseException:
            close_store(mapper)
            raise
        _close_also(src, lambda: close_store(mapper))
        return src, counter
    if fam not in ("nifti", "tiff", "visor"):
        raise RemoteRefused(f"family {family!r} is not read remotely")
    fh, counter = open_file(url, max_bytes, block_size)
    try:
        src = readers.open_image(fh, fam)
    except BaseException:
        fh.close()
        raise
    _close_also(src, fh.close)
    if fam == "visor":
        meta = sibling_json(normalize_url(url), "acqinfo_metadata.json")
        if meta is not None:
            readers.apply_visor_meta(src, meta)
    return src, counter
