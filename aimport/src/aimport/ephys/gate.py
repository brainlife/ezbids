"""The final gate: re-read every written recording file and sidecar for the run's identifying terms.

``check(files, out_root, terms, forbidden_dates, sources)`` returns the violations as
``"<BIDS rel path>: <field kind>"``; a violation never names the matched text. ``GateError`` carries them;
the module's ``write`` raises it and the server's failure path sets the output aside.

What is read, per file:

- text (``.json``, ``.tsv``, ``.vhdr``, ``.vmrk`` and other text): every JSON key and value, every TSV
  cell, every line (and its ``key=value`` fields), folded with ``scrub._fold``;
- EDF/BDF: every field of the header (bytes 0-256 and ns x 256) and the decoded TAL annotations, read
  record block by record block (bounded memory);
- FIF: every ``FIFFT_STRING`` tag (from the tag directory, never a data buffer); ``read_info``: subject_info
  keys within {sex, hand}, empty experimenter, description and proj_name (MNE's anonymize placeholders
  count as empty), channel names, meas_date before 1925, file_id/meas_id not an original date; the number
  of ``FIFFV_POINT_EXTRA`` points is recorded in ``extra_points``;
- SNIRF/NWB: every string dataset, attribute and object name (h5py ``visititems``);
- BrainVision ``.eeg`` (binary samples): skipped;
- anything else (and text above ``TEXT_MAX``): its bytes, as UTF-8, Latin-1 and UTF-16, in overlapping
  blocks; a JSON sidecar above ``JSON_MAX`` is refused unread (``oversized sidecar``).

Any file: size and SHA-256 equal to a source file -> ``copied source bytes`` (sizes first; only equal sizes
are hashed). The relative path itself is checked too. Text is matched with ``events.holds_term`` against the
terms, the ``LAST, FIRST`` forms of 2-3 word names and the original-date forms; terms of ``SQUASHED_MIN``+
characters with a letter are also found run together inside longer text (``JaneDoe tapping``); a full date from 1925 on (a shifted or real date) is allowed only in
``scans.tsv`` ``acq_time``. A file that cannot be read fails closed (``unreadable``).
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import unicodedata
from collections.abc import Iterable
from datetime import date, datetime, timezone
from pathlib import Path

from ..scrub import _compiled, _fold
from . import events
from .headers import _DMY, _MONTHS, EDF_ANON_DATE, VHDR_SECTIONS, _all_forms, _strings

ANON_BEFORE_YEAR = 1925  # MNE-BIDS anonymized dates are before 1925-01-01
TEXT_SUFFIXES = frozenset({".json", ".tsv", ".vhdr", ".vmrk", ".txt", ".csv", ".pos", ".md"})
SKIP_SUFFIXES = frozenset({".eeg"})  # BrainVision binary samples
EDF_SUFFIXES = frozenset({".edf", ".bdf"})
H5_SUFFIXES = frozenset({".snirf", ".nwb"})
TEXT_MAX = 4 << 20  # a larger text file is scanned in blocks
JSON_MAX = 4 << 20  # a larger sidecar is refused unread (sidecars are a few KB)
SQUASHED_MIN = 5  # terms this long without separators are also matched inside run-together text
BLOCK = 1 << 20
OVERLAP = 4096
FIELD_MAX = 1 << 16  # longer strings are matched in blocks
H5_ROWS = 4096
MAX_LISTED = 20
EMPTY_ALLOWED = frozenset({"", "mne_anonymize", "Anonymized using a time shift to preserve age at acquisition"})
SUBJECT_KEYS = frozenset({"sex", "hand"})
EDF_ANON_START = "01.01.85"
# fields of the EDF main header (start, width, kind)
_EDF_MAIN = ((0, 8, "version field"), (8, 80, "patient field"), (88, 80, "recording field"),
             (168, 8, "start date"), (176, 8, "start time"), (184, 8, "header size"), (192, 44, "reserved field"),
             (236, 8, "record count"), (244, 8, "record duration"), (252, 4, "signal count"))
# per-signal fields: label, transducer, dim, pmin, pmax, dmin, dmax, prefilter, samples per record, reserved
_EDF_SIGNAL_WIDTHS = (16, 80, 8, 8, 8, 8, 8, 80, 8, 32)
_ISO = re.compile(r"(?<!\d)(\d{4})[-/.](\d{2})[-/.](\d{2})(?!\d)")
_DMY_SEP = re.compile(r"(?<!\d)(\d{2})[./](\d{2})[./](\d{4})(?!\d)")
_COMPACT = re.compile(r"^\d{14,20}$")  # BrainVision "New Segment" YYYYMMDDhhmmss...
_FIELD_SPLIT = re.compile(r"[\n\r\t:;,=]+")
_ANNOT_LABELS = frozenset({"edf annotations", "bdf annotations"})
NWB_WRITE_TIME = frozenset({"file_create_date"})  # the time the file was written, not a measurement


class GateError(RuntimeError):
    """The written output holds identifying data. ``violations``: ``"<BIDS rel path>: <field kind>"``."""

    def __init__(self, violations: list[str]) -> None:
        self.violations = list(violations)
        shown = "; ".join(self.violations[:MAX_LISTED])
        more = len(self.violations) - MAX_LISTED
        super().__init__(f"the output failed the final check ({shown}"
                         + (f"; and {more} more" if more > 0 else "") + ")")


def forbidden_date_forms(dates: Iterable[date | datetime | None]) -> set[str]:
    """Every written form (``scrub._date_forms`` and ``headers.edf_date_forms``) of the original dates."""
    out: set[str] = set()
    for d in dates:
        if isinstance(d, datetime):
            d = d.date()
        if isinstance(d, date):
            out |= _all_forms(d)
    return out


_SQUASH = re.compile(r"[\W_]+")
_NAME_WORD = re.compile(r"[^\W\d_]{2,}")


_COMBINING: dict[int, None] | None = None


def _fold_fast(text: str) -> str:
    """``scrub._fold`` (NFKD, combining marks removed, casefold) on the whole string at C speed: no
    per-character objects, so a 1 MiB block stays a few MiB."""
    global _COMBINING
    if text.isascii():
        return text.lower()
    if _COMBINING is None:
        _COMBINING = {c: None for c in range(sys.maxunicode + 1) if unicodedata.combining(chr(c))}
    return unicodedata.normalize("NFKD", text).translate(_COMBINING).casefold()


def _reversed_names(term: str) -> set[str]:
    """``LAST, FIRST`` and ``LAST FIRST`` of a 2-3 word name term (``Doe, Jane`` for ``Jane Doe``)."""
    words = str(term).split()
    if not 2 <= len(words) <= 3 or not all(_NAME_WORD.fullmatch(w) for w in words):
        return set()
    rest = " ".join(words[:-1])
    return {f"{words[-1]}, {rest}", f"{words[-1]} {rest}"}


def _real_dates(text: str, allow: frozenset[date] = frozenset()) -> bool:
    """True when the text holds a full date from 1925 on (anonymized dates are earlier)."""
    found: list[date] = []
    for m in _ISO.finditer(text):
        try:
            found.append(date(int(m[1]), int(m[2]), int(m[3])))
        except ValueError:
            pass
    for m in _DMY_SEP.finditer(text):
        for dd, mm in ((m[1], m[2]), (m[2], m[1])):
            try:
                found.append(date(int(m[3]), int(mm), int(dd)))
            except ValueError:
                pass
    for m in _DMY.finditer(text):
        try:
            found.append(date(int(m[3]), _MONTHS.index(m[2].upper()) + 1, int(m[1])))
        except ValueError:
            pass
    return any(d.year >= ANON_BEFORE_YEAR and d not in allow for d in found)


class _Gate:
    def __init__(self, out_root: Path, terms: set[str], forbidden_dates: set[str], sources: list[Path],
                 extra_points: dict[str, int] | None, allowed_dates: Iterable[date] = ()) -> None:
        self.out_root = Path(out_root).resolve()
        self.allowed = frozenset(d.date() if isinstance(d, datetime) else d for d in allowed_dates)
        bad = {t for t in (set(terms) | set(forbidden_dates)) if str(t).strip()}
        for t in set(terms):
            bad |= _reversed_names(t)
        self.bad = frozenset(bad)
        self.forbidden = frozenset(forbidden_dates)
        squashed = {_SQUASH.sub("", _fold_fast(str(t))) for t in bad}
        # digit-only forms (dates, numbers) are left out: squashed, they would match inside decimal numbers
        squashed = sorted((q for q in squashed if len(q) >= SQUASHED_MIN and not q.isdigit()), key=len, reverse=True)
        self.squashed = re.compile("|".join(map(re.escape, squashed))) if squashed else None
        self.violations: list[str] = []
        self.rel = ""
        self.extra_points = extra_points
        self._sources = list(sources)
        self._sizes: dict[int, list[Path]] | None = None
        self._hashes: dict[Path, str] = {}

    # --- reporting ---

    def flag(self, kind: str) -> None:
        v = f"{self.rel}: {kind}"
        if v not in self.violations:
            self.violations.append(v)

    def holds(self, text: str) -> bool:
        if not self.bad or not text:
            return False
        if len(text) > FIELD_MAX:
            return self.holds_block(text)
        folded = _fold(text)
        return events.holds_term(folded, self.bad) or self.holds_squashed(folded)

    def holds_squashed(self, folded: str) -> bool:
        """A term of ``SQUASHED_MIN``+ characters without separators inside the text without separators
        (``JaneDoe tapping``, ``DOE,JANE``)."""
        return self.squashed is not None and bool(self.squashed.search(_SQUASH.sub("", folded)))

    def holds_block(self, text: str) -> bool:
        """A long block: the term pattern on the folded text, also with separators as spaces, and squashed."""
        _, pattern = _compiled(self.bad)
        if pattern is None:
            return False
        folded = _fold_fast(text)
        return bool(pattern.search(folded) or pattern.search(events.SEPARATORS.sub(" ", folded))
                    or self.holds_squashed(folded))

    def value(self, text, kind: str, dates: bool = True, allow: frozenset[date] = frozenset()) -> None:
        """One string field: the whole, its pieces, and (``dates``) any full date from 1925 on."""
        for s in _strings(text):
            if self.holds(s) or any(self.holds(p.strip()) for p in _FIELD_SPLIT.split(s) if p.strip() != s):
                self.flag(kind)
            if dates and _real_dates(s, allow | self.allowed):
                self.flag(kind)

    # --- copied bytes ---

    def _hash(self, path: Path) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as fh:
            while chunk := fh.read(BLOCK):
                h.update(chunk)
        return h.hexdigest()

    def copied(self, path: Path) -> bool:
        if self._sizes is None:
            self._sizes = {}
            for s in self._sources:
                try:
                    if Path(s).is_file():
                        self._sizes.setdefault(Path(s).stat().st_size, []).append(Path(s))
                except OSError:
                    continue
        same = self._sizes.get(path.stat().st_size)
        if not same:
            return False
        digest = self._hash(path)
        for s in same:
            if s not in self._hashes:
                self._hashes[s] = self._hash(s)
            if self._hashes[s] == digest:
                return True
        return False

    # --- per file ---

    def file(self, path: Path) -> None:
        path = Path(path)
        try:
            self.rel = path.resolve().relative_to(self.out_root).as_posix()
        except (ValueError, OSError):
            self.rel = "(a file outside the output)"
            self.flag("location")
            return
        if self.holds(self.rel) or _real_dates(self.rel) or any(self.holds(p) for p in re.split(r"[/_.-]", self.rel)):
            self.rel = "(a file name)"
            self.flag("file name")
            # the content is still checked under the withheld name
        try:
            if not path.is_file():
                self.flag("unreadable")
                return
            if self.copied(path):
                self.flag("copied source bytes")
            suffix = path.suffix.lower()
            if suffix in SKIP_SUFFIXES:
                return
            if suffix in EDF_SUFFIXES:
                self.edf(path)
            elif suffix == ".fif":
                self.fif(path)
            elif suffix in H5_SUFFIXES:
                self.h5(path)
            elif suffix in TEXT_SUFFIXES and (suffix == ".json" or path.stat().st_size <= TEXT_MAX):
                self.text(path, suffix)
            else:
                self.blocks(path)
        except Exception:  # noqa: BLE001 - fail closed, and never echo what was read
            self.flag("unreadable")

    # --- text ---

    @staticmethod
    def _decode(data: bytes) -> str:
        if data.startswith((b"\xff\xfe", b"\xfe\xff")):
            return data.decode("utf-16")
        try:
            return data.decode("utf-8").lstrip("﻿")
        except UnicodeDecodeError:
            return data.decode("latin-1")

    def text(self, path: Path, suffix: str) -> None:
        if suffix == ".json" and path.stat().st_size > JSON_MAX:
            self.flag("oversized sidecar")
            return
        text = self._decode(path.read_bytes())
        if suffix == ".json":
            self.json(json.loads(text))  # size-checked by the caller (JSON_MAX)
        elif suffix == ".tsv":
            self.tsv(text, scans=path.name.endswith("scans.tsv"))
        else:
            kind = {".vhdr": "header line", ".vmrk": "marker line"}.get(suffix, "text line")
            for line in text.splitlines():
                self.ini_line(line, kind, marker=suffix == ".vmrk")
            if suffix == ".vhdr":
                self.vhdr_layout(path, text)

    def vhdr_layout(self, path: Path, text: str) -> None:
        """A written ``.vhdr`` holds only the sections aimport rebuilds, and names its own BIDS files."""
        stem = path.name[: -len(".vhdr")]
        section = ""
        for line in text.splitlines():
            s = line.strip()
            if s.startswith("[") and s.endswith("]"):
                section = s[1:-1].strip()
                if section not in VHDR_SECTIONS:
                    self.flag("header section")
                continue
            key, sep, val = s.partition("=")
            if sep and section == "Common Infos" and key.strip().lower() in ("datafile", "markerfile"):
                ext = ".eeg" if key.strip().lower() == "datafile" else ".vmrk"
                if val.strip() != stem + ext:
                    self.flag("data file name")

    def json(self, obj, depth: int = 0) -> None:
        if depth > 64:
            self.flag("unreadable")
            return
        if isinstance(obj, dict):
            for k, v in obj.items():
                self.value(str(k), "sidecar key")
                self.json(v, depth + 1)
        elif isinstance(obj, list):
            for v in obj:
                self.json(v, depth + 1)
        elif isinstance(obj, str):
            self.value(obj, "sidecar value")
        elif isinstance(obj, int) and not isinstance(obj, bool):
            self.value(str(obj), "sidecar value")
        elif isinstance(obj, float):
            self.value(repr(obj), "sidecar value")
            if obj.is_integer():
                self.value(str(int(obj)), "sidecar value")

    def tsv(self, text: str, scans: bool) -> None:
        lines = text.splitlines()
        header = lines[0].split("\t") if lines else []
        acq = header.index("acq_time") if scans and "acq_time" in header else -1
        for n, line in enumerate(lines):
            for i, cell in enumerate(line.split("\t")):
                # scans.tsv acq_time holds the shifted date: only the original dates and terms are refused
                self.value(cell, "table cell", dates=not (n > 0 and i == acq))

    def ini_line(self, line: str, kind: str, marker: bool = False) -> None:
        s = line.strip()
        if not s:
            return
        self.value(s, kind)
        key, sep, val = s.partition("=")
        if not sep:
            return
        self.value(key, kind)
        fields = [f.replace(r"\1", ",").strip() for f in val.split(",")]
        for f in fields:
            self.value(f, kind)
        if marker and len(fields) > 5 and _COMPACT.fullmatch(fields[5]):
            try:
                if int(fields[5][:4]) >= ANON_BEFORE_YEAR:
                    self.flag("marker date")
            except ValueError:
                self.flag("marker date")

    # --- binary blocks (unknown files, oversized text) ---

    def blocks(self, path: Path) -> None:
        with open(path, "rb") as fh:
            tail = b""
            while True:
                chunk = fh.read(BLOCK)
                if not chunk:
                    break
                data = tail + chunk
                if any(self.holds_block(t) or _real_dates(t, self.allowed) for t in self._decodings(data)):
                    self.flag("file bytes")
                    return
                tail = data[-OVERLAP:]

    @staticmethod
    def _decodings(data: bytes):
        """The block as UTF-8 (errors ignored), Latin-1 and UTF-16 LE/BE at both byte alignments, one at a time."""
        yield data.decode("utf-8", "ignore")
        yield data.decode("latin-1")
        for start in (0, 1):
            part = data[start:]
            part = part[:len(part) - len(part) % 2]
            yield part.decode("utf-16-le", "replace")
            yield part.decode("utf-16-be", "replace")

    # --- EDF / BDF ---

    def edf(self, path: Path) -> None:
        anon = frozenset({EDF_ANON_DATE})
        with open(path, "rb") as fh:
            head = fh.read(256)
            if len(head) < 256:
                raise ValueError("short header")
            for start, width, kind in _EDF_MAIN:
                field = head[start:start + width].decode("latin-1").strip()
                if kind == "start date" and field == EDF_ANON_START:
                    continue
                self.value(field, kind, allow=anon)
            ns = int(head[252:256].decode("ascii").strip())
            if not 0 < ns < 100000:
                raise ValueError("signal count")
            sig = fh.read(256 * ns)
            if len(sig) < 256 * ns:
                raise ValueError("short signal header")
        cols: list[list[str]] = []
        pos = 0
        for width in _EDF_SIGNAL_WIDTHS:
            col = [sig[pos + i * width:pos + (i + 1) * width].decode("latin-1").strip() for i in range(ns)]
            for v in col:
                self.value(v, "signal header", allow=anon)
            cols.append(col)
            pos += width * ns
        labels, samples = cols[0], [int(n) for n in cols[8]]
        annot = [i for i, lab in enumerate(labels) if lab.lower() in _ANNOT_LABELS]
        if annot:
            self.tal(path, head, ns, samples, annot)

    def tal(self, path: Path, head: bytes, ns: int, samples: list[int], annot: list[int]) -> None:
        import numpy as np

        bps = 3 if head[0] == 0xFF else 2
        offsets, pos = [], 0
        for n in samples:
            offsets.append(pos)
            pos += n * bps
        rec_bytes = pos
        if rec_bytes <= 0:
            raise ValueError("record size")
        data_start = 256 * (ns + 1)
        per_block = max(1, BLOCK // rec_bytes)
        with open(path, "rb") as fh:
            fh.seek(data_start)
            while True:
                chunk = fh.read(per_block * rec_bytes)
                n = len(chunk) // rec_bytes
                if n == 0:
                    break
                arr = np.frombuffer(chunk[:n * rec_bytes], dtype=np.uint8).reshape(n, rec_bytes)
                for i in annot:
                    part = arr[:, offsets[i]:offsets[i] + samples[i] * bps]
                    for row in part:
                        self.tal_record(bytes(row))
                del arr, chunk

    def tal_record(self, raw: bytes) -> None:
        for tal in raw.split(b"\x00"):
            if not tal:
                continue
            pieces = tal.split(b"\x14")
            # pieces[0] is "+onset[\x15duration]" (numbers by format); the rest are annotation texts
            head = pieces[0] if re.search(rb"[^0-9+\-.\x15\s]", pieces[0]) else b""
            for p in [head, *pieces[1:]]:
                text = p.decode("utf-8", "replace").strip()
                if text:
                    self.value(text, "annotation")

    # --- FIF ---

    def fif(self, path: Path) -> None:
        import mne
        from mne._fiff.constants import FIFF
        from mne._fiff.open import fiff_open
        from mne._fiff.tag import read_tag

        fid, tree, _ = fiff_open(path, preload=False, verbose="error")
        with fid:
            stack = [tree]
            while stack:
                node = stack.pop()
                for ent in node.get("directory") or []:
                    if ent.type == FIFF.FIFFT_STRING and ent.kind != FIFF.FIFF_DATA_BUFFER:
                        self.value(read_tag(fid, ent.pos).data, "string tag")
                stack.extend(node.get("children") or [])
        info = mne.io.read_info(path, verbose="error")
        subject = info.get("subject_info") or {}
        if set(subject) - SUBJECT_KEYS:
            self.flag("subject info")
        for key, kind in (("experimenter", "experimenter"), ("description", "description"),
                          ("proj_name", "project name")):
            v = info.get(key)
            if v is not None and str(v).strip() not in EMPTY_ALLOWED:
                self.flag(kind)
        for name in info["ch_names"]:
            self.value(name, "channel name")
        meas = info.get("meas_date")
        if isinstance(meas, datetime) and meas.year >= ANON_BEFORE_YEAR:
            self.flag("measurement date")
        for key in ("file_id", "meas_id"):
            ident = info.get(key) or {}
            secs = int(ident.get("secs") or 0) if isinstance(ident, dict) else 0
            if self.original_date((secs,)):
                self.flag("file id")
        helium = info.get("helium_info") or {}
        if self.original_date(helium.get("meas_date")):
            self.flag("helium info")
        for record in info.get("proc_history") or []:
            block = record.get("block_id") or {}
            stamps = [record.get("date"), (block.get("secs"),) if isinstance(block, dict) else None]
            if any(self.original_date(s) for s in stamps):
                self.flag("processing history")
            self.value(record.get("experimenter"), "processing history", dates=False)
            self.value(record.get("creator"), "processing history", dates=False)
        if self.extra_points is not None:
            self.extra_points[self.rel] = sum(1 for d in info.get("dig") or []
                                              if d.get("kind") == FIFF.FIFFV_POINT_EXTRA)

    def original_date(self, value) -> bool:
        """True when a date, datetime or FIF stamp ``(secs, ...)`` is an original date (0 is MNE's anonymized
        stamp; DATE_NONE is no date)."""
        if isinstance(value, (tuple, list)) or (hasattr(value, "shape") and getattr(value, "size", 0) >= 1):
            try:
                secs = int(value[0])
            except (TypeError, ValueError, IndexError):
                return False
            if secs <= 0 or secs >= 2**31 - 1:
                return False
            value = datetime.fromtimestamp(secs, timezone.utc)
        if isinstance(value, (date, datetime)):
            return bool(forbidden_date_forms([value]) & self.forbidden)
        return False

    # --- SNIRF / NWB ---

    def h5(self, path: Path) -> None:
        import h5py
        import numpy as np

        def strings_of(value) -> list[str]:
            if isinstance(value, np.ndarray) and value.dtype.fields:
                return [s for name in value.dtype.names for s in strings_of(value[name])]
            return _strings(value)

        def kind_of(name: str) -> str:
            parts = name.split("/")
            if "metaDataTags" in parts:
                return "metaDataTags"
            if len(parts) >= 2 and re.fullmatch(r"stim\d*", parts[-2]) and parts[-1] == "name":
                return "stim name"
            return "string dataset"

        def is_text(dt) -> bool:
            if dt.fields:
                return any(is_text(f[0]) for f in dt.fields.values())
            return dt.kind in "SUO" or h5py.check_string_dtype(dt) is not None

        def attrs(obj) -> None:
            for k in obj.attrs:
                self.value(k, "attribute")
                try:
                    v = obj.attrs[k]
                except (OSError, TypeError, ValueError):
                    self.flag("unreadable")
                    continue
                for s in strings_of(v):
                    self.value(s, "attribute")

        def visit(name: str, obj) -> None:
            self.value(name.rsplit("/", 1)[-1], "object name")
            attrs(obj)
            if not isinstance(obj, h5py.Dataset) or not is_text(obj.dtype) \
                    or h5py.check_ref_dtype(obj.dtype) is not None:  # (object dtypes compare equal to refs)
                return
            kind = kind_of(name)
            dates = name not in NWB_WRITE_TIME  # only the root dataset (h5py names are relative to the root)
            if obj.shape == () or obj.shape is None:
                for s in strings_of(obj[()]):
                    self.value(s, kind, dates=dates)
                return
            for start in range(0, obj.shape[0], H5_ROWS):
                for s in strings_of(np.asarray(obj[start:start + H5_ROWS])):
                    self.value(s, kind, dates=dates)

        with h5py.File(path, "r") as f:
            attrs(f)
            f.visititems(visit)


def check(files: list[Path], out_root: Path, terms: set[str], forbidden_dates: set[str], sources: list[Path],
          extra_points: dict[str, int] | None = None, allowed_dates: Iterable[date] = ()) -> list[str]:
    """The violations of the written ``files`` (``"<BIDS rel path>: <field kind>"``); ``[]`` when clean.

    ``forbidden_dates``: every form of the original meas_dates and birthdays (``forbidden_date_forms``).
    ``sources``: the claimed source files (no output file may equal one byte for byte).
    ``extra_points``: when given, filled with BIDS rel path -> number of ``FIFFV_POINT_EXTRA`` points per FIF.
    ``allowed_dates``: the shifted dates aimport wrote itself (scans.tsv ``acq_time``); a full date from 1925
    on that is one of them is not refused anywhere (the original-date forms still are).
    """
    gate = _Gate(out_root, terms, forbidden_dates, sources, extra_points, allowed_dates)
    for path in sorted({Path(p) for p in files}):
        gate.file(path)
    return gate.violations
