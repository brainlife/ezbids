"""Format headers: the identifying-term harvest of one recording, and the post-write rewriters (Task 9).

``harvest(rec, input_dir, raw)`` collects every string a recording carries that the conversion drops: the
header fields of each format, comments, metadata tags, marker/event/annotation texts that are not safe
labels, and the terms of its paths. Free text is kept whole (it is a redaction term, matched as a
substring); name fields are also split into their parts; every date found becomes all its written forms.
Channel names are never harvested (Task 5 renames them against these terms). Only headers and metadata
are read; data arrays are not loaded.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from ..micr import names
from ..scrub import MIN_TERM_LEN, _date_forms
from .discover import EPHYS_EXTENSIONS, VOCAB, Recording
from .events import is_safe

_ACQ_TEXT_KEY = re.compile(r"^_(run_|seq_|operator|subject|patient|comment|descr|site|institut|user|study|procedure)",
                           re.I)
REASON_CTF_HEADER = "CTF header unreadable"
MAX_TEXT = 4 << 20  # bytes read from any text header or log
_VOCAB = frozenset(v.lower() for v in VOCAB)
EDF_ANON_DATE = date(1985, 1, 1)
EDF_SKIP = frozenset({"X", "Startdate", "M", "F"})
_GENERIC = frozenset({"x", "startdate", "unknown", "none", "null", "n/a", "na", "nan", "true", "false", "yes", "no",
                      "edf+c", "edf+d", "bdf+c", "bdf+d", "24bit", "male", "female", "left", "right",
                      # placeholders written by acquisition software
                      "name", "no_name", "no name", "noname", "anonymous", "anon", "patient", "subject"})
# manufacturer and format words: never identifying, and they appear in sidecars (Manufacturer)
SYSTEM_WORDS = ("ctf", "kit", "bti", "4d", "egi", "nirx", "neuromag", "megin", "elekta", "vectorview", "triux",
                "biosemi", "brainvision", "brainproducts", "eeglab", "neuroscan", "compumedics", "persyst", "nihon",
                "kohden", "nihonkohden", "hitachi", "blackrock", "snirf", "nwb", "natus", "micromed", "mef",
                "mff", "geodesic", "yokogawa", "ricoh", "artinis", "shimadzu", "mne", "matlab", "fieldtrip")
# generic file-name words of vendor folders (NIRx "nirx_15_3_recording", "<name>_config.txt") and companion
# extensions: as path terms they would redact sidecar keys such as RecordingDuration. Paths only (HARVEST_VOCAB):
# in a header or metadata field the same word ("Dat", "Mat") may be a name and stays a term
FILE_WORDS = ("recording", "recordings", "config", "probeinfo", "avg", "inf", "tpl", "txt", "dat", "evt", "hdr",
              "wl1", "wl2", "set", "mat", "csv", "json", "tsv",
              # BIDS entity keys of an input already in BIDS (sub-01_task-rest_acq-hd_eeg.edf)
              "acq", "ce", "rec", "dir", "echo", "flip", "inv", "mt", "part", "space", "split", "desc", "trc", "stain",
              "chunk", "mod", "hemi", "res", "den", "tracksys", "nuc", "voi")
# file extensions and file-name words: skipped in paths (HARVEST_VOCAB) but not in header or metadata text, where
# the same word ("Dat", "Mat", "Set") may be a name
PATH_ONLY_WORDS = frozenset(FILE_WORDS) | frozenset(EPHYS_EXTENSIONS) | frozenset({
    "ome", "zarr", "tif", "tiff", "btf", "nii", "gz", "dat", "mat", "json", "log", "svs", "czi", "nd2", "lif", "vsi"})
_VOCAB = (_VOCAB - PATH_ONLY_WORDS) | frozenset(SYSTEM_WORDS)
HARVEST_VOCAB = tuple(VOCAB) + SYSTEM_WORDS + FILE_WORDS
_MARKER_CODE = re.compile(r"^[SR]\s*\d{1,4}$")
_TIME = re.compile(r"^\d{1,2}:\d{2}(:\d{2})?([.,]\d+)?$")
_MONTHS = ("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC")
_DMY = re.compile(r"(?<!\d)(\d{1,2})-(" + "|".join(_MONTHS) + r")-(\d{4})(?!\d)", re.I)
_YMD = re.compile(r"(?<!\d)(\d{4})[-/.]?(\d{2})[-/.]?(\d{2})(?!\d)")
_US = re.compile(r"(?<!\d)(\d{1,2})/(\d{1,2})/(\d{4}|\d{2})(?!\d)")
_EDF_ANON = re.compile(r"^(startdate\s+)?(x(\s+|$))+$", re.I)  # "X X X X", "Startdate X X X X"
_DMY_NUM = re.compile(r"(?<!\d)(\d{2})[./](\d{2})[./](\d{4})(?!\d)")
_BV_BOILERPLATE = re.compile(
    r"pybv|vision recorder|brain ?vision|each entry|fields are|commas in|<|data orientation|sampling interval|"
    r"copyright|resolution in", re.I)
# a channel-table row: number, name, physical channel, resolution and unit ("1  Fp1  1  0.1 µV ...")
_BV_TABLE_ROW = re.compile(r"^\d+\s+\S+\s+\d+\s+[\d.]+\s*\S*V\b")
_BV_MARKER_TYPES = frozenset({"new segment", "stimulus", "response", "comment", "syncstatus", "time 0",
                              "bad interval", "dc correction", "segmentation", "voltage", "average"})


# --- dates ---------------------------------------------------------------------------------------

def edf_date_forms(d: date) -> set[str]:
    """``dd.mm.yy``, ``DD-MMM-YYYY`` (upper and lower case) and ``yymmdd`` of a date."""
    mon = _MONTHS[d.month - 1]
    dmy = f"{d.day:02d}-{mon}-{d.year:04d}"
    return {f"{d.day:02d}.{d.month:02d}.{d.year % 100:02d}", dmy, dmy.lower(),
            f"{d.year % 100:02d}{d.month:02d}{d.day:02d}"}


def _all_forms(d: date) -> set[str]:
    return _date_forms(d.strftime("%Y%m%d")) | edf_date_forms(d)


def _ymd(text: str) -> date | None:
    try:
        return datetime.strptime(text, "%Y%m%d").date()
    except ValueError:
        return None


def _dates_in(text: str, us: bool = False) -> list[date]:
    out = []
    if us:
        for m in _US.finditer(text):
            mo, d, y = int(m[1]), int(m[2]), int(m[3])
            if len(m[3]) == 2:
                y += 2000 if y < 70 else 1900
            try:
                out.append(date(y, mo, d))
            except ValueError:
                pass
    for m in _DMY.finditer(text):
        try:
            out.append(date(int(m[3]), _MONTHS.index(m[2].upper()) + 1, int(m[1])))
        except ValueError:
            pass
    for m in _YMD.finditer(text):
        y, mo, d = (int(x) for x in m.groups())
        if 1900 <= y <= 2100:
            try:
                out.append(date(y, mo, d))
            except ValueError:
                pass
    for m in _DMY_NUM.finditer(text):
        try:
            out.append(date(int(m[3]), int(m[2]), int(m[1])))
        except ValueError:
            pass
    return out


# --- term collection -----------------------------------------------------------------------------

class _Terms:
    """Collects terms by kind; ``result()`` applies the filters."""

    def __init__(self) -> None:
        self.terms: set[str] = set()
        self.short: set[str] = set()  # name parts of 2 characters (Li, Wu)
        self.ids: set[str] = set()  # identifiers, kept even when numeric
        # anonymized values a format writes itself (EDF 01.01.85): never a measurement-date term
        self.placeholders: set[date] = set()

    def date(self, d: date | datetime | None, real: bool = False) -> None:
        """Every written form of a date; ``real`` for a birth date, which is kept even when it equals a
        format's placeholder."""
        if isinstance(d, datetime):
            d = d.date()
        if not isinstance(d, date) or d.year < 1900:  # year-1 and 1900 placeholders are no one's date
            return
        if d in self.placeholders and not real:
            return
        self.terms |= _all_forms(d)

    def text(self, value: Any, us: bool = False) -> None:
        """Free text: the whole value and every date in it (``us``: also MM/DD/YY(YY), for US-format headers)."""
        for s in _strings(value):
            self.terms.add(s)
            for d in _dates_in(s, us=us):
                self.date(d)

    def ident(self, value: Any) -> None:
        for s in _strings(value):
            self.ids.add(s)
            self.text(s)

    def name(self, value: Any) -> None:
        """A personal name: the whole value, its underscore-free form and its parts (2+ characters)."""
        for s in _strings(value):
            self.text(s)
            self.terms.add(s.replace("_", " ").replace("^", " "))
            for p in re.split(r"[\s_^,;]+", s):
                p = p.strip(".,-=")
                if len(p) >= 2 and any(c.isalpha() for c in p):
                    (self.short if len(p) < MIN_TERM_LEN else self.terms).add(p)

    def label(self, value: Any) -> None:
        """A marker, event or annotation text: kept unless it is a safe label."""
        for s in _strings(value):
            if not is_safe(s) and not _MARKER_CODE.fullmatch(s):
                self.text(s)

    def path(self, value: Any) -> None:
        for s in _strings(value):
            self.text(s)
            self.terms |= names.path_terms([s.replace("\\", "/")], vocab=HARVEST_VOCAB)

    def paths(self, rels: Iterable[str]) -> None:
        rels = list(rels)
        self.terms |= names.path_terms(rels, vocab=HARVEST_VOCAB)
        for rel in rels:
            for d in names.facts(rel, vocab=VOCAB).dates:
                self.date(d)

    def result(self) -> set[str]:
        out = {t for t in self.short if not is_safe(t) and t.lower() not in _VOCAB and t.lower() not in _GENERIC}
        for t in self.terms | self.ids:
            t = t.strip()
            if not _keep(t, t in self.ids):
                continue
            out.add(t)
        return out


def _keep(t: str, ident: bool) -> bool:
    if len(t) < MIN_TERM_LEN:
        return False
    low = t.lower()
    if low in _GENERIC or low in _VOCAB or _EDF_ANON.fullmatch(t):
        return False
    if not ident and (is_safe(t) or _MARKER_CODE.fullmatch(t)):
        return False  # an identifier stays a term even when it looks like a label ("6416")
    if not any(c.isalnum() for c in t):
        return False
    if not ident and _TIME.fullmatch(t):
        return False  # a time of day alone identifies nothing and appears in acq_time
    if not ident and not any(c.isalpha() for c in t) and sum(c.isdigit() for c in t) < 6:
        return False  # numbers, versions and times
    return True


def _strings(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, bytes):
        value = value.decode("utf-8", "replace")
    if isinstance(value, str):
        s = value.replace("\x00", " ").strip()
        return [s] if s else []
    if isinstance(value, dict):
        return [s for v in value.values() for s in _strings(v)]
    if isinstance(value, (list, tuple, set)):
        return [s for v in value for s in _strings(v)]
    try:
        import numpy as np

        if isinstance(value, np.ndarray):
            if value.dtype.kind in "OSU":
                return [s for v in value.ravel().tolist() for s in _strings(v)]
            return []
        if isinstance(value, np.bytes_ | np.str_):
            return _strings(value.item())
    except ImportError:  # pragma: no cover
        pass
    return []


def _read_text(path: Path, encoding: str = "utf-8") -> str:
    with open(path, "rb") as fh:
        data = fh.read(MAX_TEXT)
    for enc in (encoding, "utf-8", "latin-1"):
        try:
            return data.decode(enc).lstrip("﻿")
        except (UnicodeDecodeError, LookupError):
            continue
    return data.decode("latin-1")


def _ini(text: str) -> list[tuple[str, str, str]]:
    """(section, key, value) of an INI-like text; lines without ``=`` come with key ``""``."""
    out, section = [], ""
    for line in text.splitlines():
        s = line.strip()
        if not s:
            continue
        if s.startswith("[") and s.endswith("]"):
            section = s[1:-1].strip()
            continue
        k, sep, v = s.partition("=")
        out.append((section, k.strip(), v.strip()) if sep else (section, "", s))
    return out


# --- MNE info --------------------------------------------------------------------------------------

def _raw_terms(t: _Terms, raw) -> None:
    info = raw.info
    subject = info.get("subject_info") or {}
    for k, v in subject.items():
        if k in ("first_name", "middle_name", "last_name"):
            t.name(v)
        elif k == "his_id":
            t.ident(v)
        elif k == "birthday":
            t.date(v, real=True)
        elif isinstance(v, str):
            t.text(v)
    t.name(info.get("experimenter"))
    t.text(info.get("description"))
    t.text(info.get("proj_name"))
    dev = info.get("device_info") or {}
    t.ident(dev.get("serial"))
    t.text(dev.get("site"))
    helium = info.get("helium_info") or {}
    t.date(helium.get("meas_date"))
    for p in info.get("proc_history") or []:
        t.name(p.get("experimenter"))
        t.text(p.get("creator"))
        t.date(p.get("date") if isinstance(p.get("date"), (date, datetime)) else None)
    t.date(info.get("meas_date"))
    for key in ("file_id", "meas_id"):
        ident = info.get(key) or {}
        secs = ident.get("secs") if isinstance(ident, dict) else None
        if secs:
            try:
                t.date(datetime.fromtimestamp(int(secs), timezone.utc))
            except (ValueError, OverflowError, OSError):
                pass
    ann = raw.annotations
    for desc in ann.description:
        t.label(desc)
    for extra in getattr(ann, "extras", None) or []:
        for v in (extra or {}).values():
            if isinstance(v, str):
                t.label(v)


# --- EDF / BDF / GDF -------------------------------------------------------------------------------

@dataclass
class EdfHeader:
    patient: str
    recording: str
    startdate: str
    starttime: str


def read_edf_header(path: Path) -> EdfHeader:
    with open(path, "rb") as fh:
        head = fh.read(256)
    s = lambda a, b: head[a:b].decode("latin-1").strip()  # noqa: E731
    return EdfHeader(patient=s(8, 88), recording=s(88, 168), startdate=s(168, 176), starttime=s(176, 184))


def _edf_field(t: _Terms, field_text: str, name_index: int | None, date_index: int | None,
               birth: bool = False) -> None:
    """One EDF patient or recording field. EDF+ subfields: the name is split into parts, the date token
    gives its date forms, every other token (codes, IDs, numbers) is an identifier."""
    t.text(field_text)
    for i, tok in enumerate(field_text.split()):
        if tok in EDF_SKIP:
            continue
        if i == date_index:
            dates = _dates_in(tok)
            if birth or not set(dates) & t.placeholders:
                t.terms.add(tok)
            for d in dates:
                t.date(d, real=birth)
        elif i == name_index or name_index is None:
            t.name(tok)
            t.ident(tok)
        else:
            t.ident(tok)
            t.ident(tok.replace("_", " "))


def _edf(t: _Terms, path: Path, rec: Recording, input_dir: Path) -> None:
    h = read_edf_header(path)
    with open(path, "rb") as fh:
        head = fh.read(256)
    reserved = head[192:236].decode("latin-1").strip()
    plus = reserved.upper().startswith(("EDF+", "BDF+")) or h.recording.startswith("Startdate")
    if plus:
        _edf_field(t, h.patient, 3, 2, birth=True)
        _edf_field(t, h.recording, 3, 1)
    else:  # plain EDF: free text, any word may be a name or a code
        _edf_field(t, h.patient, None, None)
        _edf_field(t, h.recording, None, None)
    m = re.fullmatch(r"(\d{2})\.(\d{2})\.(\d{2})", h.startdate)
    if m:
        dd, mm, yy = (int(x) for x in m.groups())
        try:
            t.date(date(1900 + yy if yy >= 85 else 2000 + yy, mm, dd))
        except ValueError:
            pass
    t.text(reserved)
    with open(path, "rb") as fh:
        fh.seek(256)
        try:
            ns = int(head[252:256].decode("ascii").strip())
        except ValueError:
            return
        if not 0 < ns < 100000:
            return
        sig = fh.read(256 * ns)
    # per-signal fields: label 16, transducer 80, dim 8, pmin 8, pmax 8, dmin 8, dmax 8, prefilter 80, n 8, reserved 32
    off = {"transducer": 16, "prefilter": 16 + 80 + 8 * 5, "reserved": 16 + 80 + 8 * 5 + 80 + 8}
    width = {"transducer": 80, "prefilter": 80, "reserved": 32}
    for key, rel in off.items():
        base = rel * ns
        for i in range(ns):
            a = base + i * width[key]
            t.text(sig[a:a + width[key]].decode("latin-1"))


def _gdf(t: _Terms, path: Path, rec: Recording, input_dir: Path) -> None:
    with open(path, "rb") as fh:
        head = fh.read(256)
    try:
        major = float(head[4:8].decode("ascii"))
    except ValueError:
        major = 1.0
    if major < 2:
        pid, rid = head[8:88], head[88:168]
    else:
        pid, rid = head[8:74], head[88:152]
    pid_s = pid.decode("latin-1").replace("\x00", " ").strip()
    t.text(pid_s)
    parts = pid_s.split()
    if parts:
        t.ident(parts[0])
    for p in parts[1:]:
        t.name(p)
    t.text(rid.decode("latin-1").replace("\x00", " ").strip())


# --- BrainVision ------------------------------------------------------------------------------------

def _bv_comment_line(t: _Terms, line: str, boilerplate: bool = False) -> None:
    """One comment line, whole and its ``key: value`` value. Only the recorder's channel-table rows are
    skipped (they are regenerated in the output); ``boilerplate`` also skips the format's own ``;`` notes."""
    s = line.strip()
    if not s or _BV_TABLE_ROW.match(s) or (s.startswith("#") and "phys" in s.lower()):
        return
    if boilerplate and _BV_BOILERPLATE.search(s):
        return
    t.text(s)
    for sep in (":", "="):
        if sep in s:
            value = s.split(sep, 1)[1].strip()
            t.text(value)
            for part in value.split(","):
                t.text(part.strip())
            break


def _brainvision(t: _Terms, path: Path, rec: Recording, input_dir: Path) -> None:
    technical = {"common infos", "binary infos", "ascii infos", "channel infos", "coordinates", "marker infos"}
    text = _read_text(path)
    section = ""
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("[") and s.endswith("]"):
            section = s[1:-1].strip().lower()
            continue
        if s.startswith(";"):
            _bv_comment_line(t, s[1:], boilerplate=True)
            continue
        if section == "comment" or (section and section not in technical):
            _bv_comment_line(t, s)
            continue
        k, sep, v = s.partition("=")
        if sep and section == "common infos" and k.strip().lower() in ("datafile", "markerfile"):
            t.path(v.strip())
            t.text(Path(v.strip()).stem)
    marker = next((input_dir / c for c in rec.companions if c.lower().endswith(".vmrk")), None)
    if marker is not None and marker.is_file():
        _vmrk(t, marker)


def _vmrk(t: _Terms, path: Path) -> None:
    text = _read_text(path)
    section = ""
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("[") and s.endswith("]"):
            section = s[1:-1].strip().lower()
            continue
        if s.startswith(";"):
            _bv_comment_line(t, s[1:], boilerplate=True)
            continue
        k, sep, v = s.partition("=")
        if section == "marker infos" and sep and re.fullmatch(r"Mk\d+", k.strip(), re.I):
            fields = [f.replace(r"\1", ",") for f in v.split(",")]
            mtype = fields[0].strip() if fields else ""
            desc = fields[1].strip() if len(fields) > 1 else ""
            if mtype and mtype.lower() not in _BV_MARKER_TYPES:
                t.label(mtype)
            if desc and not is_safe(f"{mtype}/{desc}"):
                t.label(desc)
            if len(fields) > 5 and re.fullmatch(r"\d{8,}", fields[5].strip()):
                t.date(_ymd(fields[5].strip()[:8]))
        elif section == "common infos" and sep and k.strip().lower() == "datafile":
            t.path(v.strip())
            t.text(Path(v.strip()).stem)
        elif section and section not in ("common infos", "marker infos"):
            _bv_comment_line(t, s)


# --- EEGLAB -----------------------------------------------------------------------------------------

_EEGLAB_SKIP = frozenset({"data", "times", "icaact", "icawinv", "icasphere", "icaweights", "icachansind",
                          "chanlocs", "urchanlocs", "specdata", "specicaact", "stats", "reject", "datfile",
                          "ref", "saved", "nbchan", "trials", "pnts", "srate", "xmin", "xmax"})
_EEGLAB_LABELS = frozenset({"event", "urevent", "epoch", "eventdescription"})
_QUOTED = re.compile(r"'([^']*)'")


def _eeglab_value(t: _Terms, top: str, value: str) -> None:
    if top in _EEGLAB_LABELS:
        t.label(value)
    elif top == "history":
        for line in value.splitlines():
            t.text(line)
            for lit in _QUOTED.findall(line):  # file names and folders passed to EEGLAB functions
                if "/" in lit or "\\" in lit:
                    t.path(lit)
                elif "." in lit:
                    t.text(lit)
    elif top in ("filename", "filepath"):
        t.path(value)
    elif top == "subject":
        t.ident(value)
    else:
        t.text(value)


def _walk_py(obj: Any, depth: int = 0):
    """Strings of a loadmat(simplify_cells=True) value."""
    if depth > 12:
        return
    if isinstance(obj, (str, bytes)):
        yield from _strings(obj)
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from _walk_py(v, depth + 1)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            yield from _walk_py(v, depth + 1)
    else:
        try:
            import numpy as np

            if isinstance(obj, np.ndarray) and obj.dtype.kind in "OSU":
                for v in obj.ravel().tolist():
                    yield from _walk_py(v, depth + 1)
        except ImportError:  # pragma: no cover
            pass


def _h5_strings(f, obj, depth: int = 0):
    """Strings of a MATLAB v7.3 object, reading only char, cell and struct entries (never numeric arrays)."""
    import h5py
    import numpy as np

    if depth > 12:
        return
    if isinstance(obj, h5py.Group):
        for k, v in obj.items():
            if k in _EEGLAB_SKIP or k.startswith("#"):
                continue
            yield from _h5_strings(f, v, depth + 1)
        return
    cls = obj.attrs.get("MATLAB_class", b"")
    cls = cls.decode() if isinstance(cls, bytes) else str(cls)
    if cls == "char" and obj.size < (1 << 20):
        arr = np.asarray(obj[()])
        if arr.dtype.kind in "ui":
            text = "".join(chr(c) for c in arr.ravel(order="F") if c)
            yield from _strings(text)
    elif h5py.check_string_dtype(obj.dtype) is not None and obj.size < (1 << 20):
        yield from _strings(np.asarray(obj[()]))  # variable-length or fixed strings (non-MATLAB writers)
    elif h5py.check_ref_dtype(obj.dtype) is not None and obj.size < (1 << 20):
        # (a variable-length string dtype compares equal to h5py.ref_dtype: both are object dtypes)
        for ref in np.asarray(obj[()]).ravel():
            if ref:
                yield from _h5_strings(f, f[ref], depth + 1)


def _eeglab(t: _Terms, path: Path, rec: Recording, input_dir: Path) -> None:
    from .readers import EEGLAB_MAX_MAT, REASON_EEGLAB_BIG, Unsupported, _is_hdf5

    if _is_hdf5(path):
        import h5py

        with h5py.File(path, "r") as f:
            eeg = f["EEG"] if "EEG" in f else f
            for k, v in eeg.items():
                if k in _EEGLAB_SKIP or k.startswith("#"):
                    continue
                for s in _h5_strings(f, v):
                    _eeglab_value(t, k, s)
        return
    if path.stat().st_size > EEGLAB_MAX_MAT:
        raise Unsupported(REASON_EEGLAB_BIG)
    from scipy.io import loadmat

    mat = loadmat(path, variable_names=["EEG"], squeeze_me=True, simplify_cells=True)
    eeg = mat.get("EEG")
    if eeg is None:  # older files store the fields at the top level
        mat = loadmat(path, squeeze_me=True, simplify_cells=True)
        eeg = {k: v for k, v in mat.items() if not k.startswith("__")}
    if not isinstance(eeg, dict):
        return
    for k, v in eeg.items():
        if k in _EEGLAB_SKIP:
            continue
        for s in _walk_py(v):
            _eeglab_value(t, k, s)


# --- other EEG/iEEG formats ---------------------------------------------------------------------------

def _cnt(t: _Terms, path: Path, rec: Recording, input_dir: Path) -> None:
    with open(path, "rb") as fh:
        head = fh.read(260)
    s = lambda a, n: head[a:a + n].split(b"\x00")[0].decode("latin-1").strip()  # noqa: E731
    t.ident(s(21, 20))
    for off in (41, 61, 81, 121):  # operator, doctor, referral, patient
        t.name(s(off, 20))
    for off in (101, 145, 165, 185, 205):  # hospital, medication, category, state, session label
        t.text(s(off, 20))
    t.text(s(225, 10), us=True)  # Neuroscan writes MM/DD/YY


def _nihon(t: _Terms, path: Path, rec: Recording, input_dir: Path) -> None:
    pnt = next((input_dir / c for c in rec.companions if c.lower().endswith(".pnt")), None)
    if pnt is not None and pnt.is_file():
        with open(pnt, "rb") as fh:
            head = fh.read(0x700)
        s = lambda a, n: head[a:a + n].split(b"\x00")[0].decode("latin-1").strip()  # noqa: E731
        t.date(_ymd(s(0x40, 14)[:8]))  # measurement date (MNE's offset)
        t.ident(s(0x604, 12))  # patient ID
        t.name(s(0x62E, 22))  # patient name
        t.text(s(0x660, 10))  # birth date (YYYY/MM/DD)
    # .LOG event texts reach raw.annotations through MNE's reader


def _persyst(t: _Terms, path: Path, rec: Recording, input_dir: Path) -> None:
    for section, key, value in _ini(_read_text(path)):
        sec = section.lower()
        if sec == "patient":
            if key.lower() in ("fullname", "physician", "technician"):
                t.name(value)
            elif key.lower() in ("id", "medicalrecordn"):
                t.ident(value)
            else:
                t.text(value)
        elif sec == "fileinfo" and key.lower() == "file":
            t.path(value)
        elif sec == "comments":
            line = f"{key}={value}" if key else value
            fields = line.split(",", 4)
            t.label(fields[4] if len(fields) == 5 else line)


def _xml_root(path: Path):
    from defusedxml import ElementTree

    return ElementTree.fromstring(Path(path).read_bytes()[:MAX_TEXT])


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _egi(t: _Terms, path: Path, rec: Recording, input_dir: Path) -> None:
    if not path.is_dir():
        return  # simple binary .raw: MNE reads its header; nothing else is stored there
    subject = path / "subject.xml"
    if subject.is_file():
        for field_ in _xml_root(subject).iter():
            if _local(field_.tag) != "field":
                continue
            fname = next((c.text or "" for c in field_ if _local(c.tag) == "name"), "")
            data = next((c.text or "" for c in field_ if _local(c.tag) == "data"), "")
            if re.search(r"name|technician|physician", fname, re.I):
                t.name(data)
            elif re.search(r"\bid\b", fname, re.I):
                t.ident(data)
            else:
                t.text(data)
    info = path / "info.xml"
    if info.is_file():
        for el in _xml_root(info).iter():
            tag = _local(el.tag)
            if tag == "ampSerialNumber":
                t.ident(el.text)
            elif tag == "recordTime":
                t.text((el.text or "")[:10])
    for ev in sorted(path.glob("Events*.xml")):
        for el in _xml_root(ev).iter():
            tag = _local(el.tag)
            if tag in ("code", "label", "description", "name") or (tag == "data" and el.text):
                t.label(el.text)
    categories = path / "categories.xml"
    if categories.is_file():
        for el in _xml_root(categories).iter():
            if _local(el.tag) in ("name", "description", "comment", "keyCode", "data") and el.text:
                t.label(el.text)
    for log in sorted(path.glob("log_*.txt")):
        t.paths([log.name])
        for line in _read_text(log).splitlines():
            m = re.search(r"\bName:\s*(.+)$", line)
            if m:
                t.path(m.group(1).strip())


# --- MEG -------------------------------------------------------------------------------------------

_INFODS_KEY = re.compile(rb"([\x00-\xff]{4})(_[A-Za-z0-9_]+)\x00\x00\x00\x0a([\x00-\xff]{4})")


def _infods(path: Path) -> list[tuple[str, str]]:
    """(key, value) of the string entries of a CTF ``.infods`` (big-endian, length-prefixed)."""
    data = path.read_bytes()[:MAX_TEXT]
    out = []
    for m in _INFODS_KEY.finditer(data):
        if int.from_bytes(m.group(1), "big") != len(m.group(2)):
            continue
        n = int.from_bytes(m.group(3), "big")
        start = m.end()
        if 0 < n < 65536 and start + n <= len(data):
            out.append((m.group(2).decode("ascii"), data[start:start + n].decode("latin-1").strip("\x00 ")))
    return out


def _ctf(t: _Terms, path: Path, rec: Recording, input_dir: Path) -> None:
    t.text(path.name[:-3] if path.name.lower().endswith(".ds") else path.stem)
    for f in sorted(path.glob("*.infods")):
        for key, value in _infods(f):
            if not key.startswith(("_PATIENT_", "_PROCEDURE_", "_DATASET_")):
                continue
            if "NAME" in key or key.endswith(("_OPERATOR", "_TECHNICIAN")):
                t.name(value)
            elif "/" in value:
                t.path(value)
            elif key.endswith("_ID") or key.endswith("_UID"):
                t.ident(value)
            else:
                t.text(value)
    from mne.io.ctf.res4 import _read_res4
    from mne.utils import use_log_level

    from .readers import Unsupported

    try:
        with use_log_level("error"):
            res4 = _read_res4(str(path))
    except Exception as e:  # noqa: BLE001 - never plan a recording whose header text was not read
        raise Unsupported(REASON_CTF_HEADER) from e
    for key in ("nf_run_name", "nf_run_title", "nf_collect_descriptor", "run_desc", "nf_instruments"):
        t.text(res4.get(key))
    t.ident(res4.get("nf_subject_id"))
    t.name(res4.get("nf_operator"))
    t.path(res4.get("nf_sensor_file_name"))
    for f in sorted(path.glob("*.newds")):
        for line in _read_text(f).splitlines():
            k, sep, v = line.partition(":")
            if sep and k.strip().lower() in ("site", "institute", "purpose", "run_title", "subject", "operator"):
                t.text(v.strip())
    for f in sorted(path.glob("*.acq")):  # acquisition parameters: run title, date, description, sequence
        for key, value in _infods(f):  # free-text keys only: the rest names channels and colours
            if _ACQ_TEXT_KEY.match(key):
                (t.path if "/" in value else t.text)(value)
    for f in sorted(path.glob("*.hist")):  # acquisition history: free text
        for line in _read_text(f).splitlines():
            t.text(line.strip())
    for name_ in ("MarkerFile.mrk", "ClassFile.cls"):
        f = path / name_
        if f.is_file():
            lines = _read_text(f).splitlines()
            for i, line in enumerate(lines[:-1]):
                if line.strip() in ("NAME:", "COMMENT:"):
                    t.label(lines[i + 1].strip())


def _kit(t: _Terms, path: Path, rec: Recording, input_dir: Path) -> None:
    """The system directory's free text (system name, model, comment) and creation date; the KIT
    format as MNE reads it has no patient or operator fields. Plus comment lines of .elp/.hsp files."""
    import numpy as np
    from mne.io.kit.constants import KIT
    from mne.io.kit.kit import _read_dirs, _read_name

    with open(path, "rb", buffering=0) as fid:
        dirs = _read_dirs(fid)
        fid.seek(dirs[KIT.DIR_INDEX_SYSTEM]["offset"])
        np.fromfile(fid, np.int32, 3)  # version, revision, system id
        texts = [_read_name(fid, n=128), _read_name(fid, n=128)]  # system name, model name
        np.fromfile(fid, np.int32, 1)  # channel count
        texts.append(_read_name(fid, n=256))  # comment
        for text in texts:
            t.text(text)
            t.text(text.splitlines())
        created = int(np.fromfile(fid, np.int32, 1)[0])
    if created > 0:
        t.date(datetime.fromtimestamp(created, timezone.utc))
    for rel in [*rec.companions, *rec.headshape]:
        if rel.lower().endswith((".elp", ".hsp", ".txt")):
            for line in _read_text(input_dir / rel).splitlines():
                s = line.strip()
                if s.startswith("%") and not re.match(r"%[A-Z]\s", s):
                    t.text(s.lstrip("% ").strip())


def _bti(t: _Terms, path: Path, rec: Recording, input_dir: Path) -> None:
    """Config and PDF header strings: site, DAP host, user-block user names and log folders, the
    configuration name, process users and file names, event names. Channel names are left to Task 5."""
    from mne.io.bti.bti import _read_bti_header
    from mne.utils import use_log_level

    pdf = next((input_dir / c for c in rec.companions if Path(c).name.lower().startswith(("c,rf", "e,rf"))), None)
    config = next((input_dir / c for c in rec.companions if Path(c).name.lower() == "config"), None)
    if pdf is None or config is None:
        return
    with use_log_level("error"):
        info = _read_bti_header(str(pdf), str(config))
    from mne.io.bti.bti import _read_config

    cfg = _read_config(str(config))
    hdr = cfg.get("hdr") or {}
    t.text(hdr.get("site_name"))
    t.ident(hdr.get("dap_hostname"))
    for block in (cfg.get("user_blocks") or {}).values():
        t.name((block.get("hdr") or {}).get("username"))
        t.text(block.get("logdir"))
        t.text(block.get("sysconfig_name"))
    for proc in info.get("processes") or []:
        t.name(proc.get("user"))
        t.path(proc.get("filename"))
    for ev in info.get("events") or []:
        t.label(ev.get("event_name"))
    for assoc in info.get("assocfiles") or []:
        if isinstance(assoc, dict):
            for v in assoc.values():
                if isinstance(v, str):
                    t.path(v)


def _fif(t: _Terms, path: Path, rec: Recording, input_dir: Path) -> None:
    """Every string tag outside channel lists, projectors and annotations (those are handled elsewhere)."""
    from mne._fiff.constants import FIFF
    from mne._fiff.open import fiff_open
    from mne._fiff.tag import read_tag

    skip_blocks = {FIFF.FIFFB_PROJ, FIFF.FIFFB_PROJ_ITEM, FIFF.FIFFB_MNE_BAD_CHANNELS, FIFF.FIFFB_MNE_CTF_COMP,
                   FIFF.FIFFB_MNE_CTF_COMP_DATA, FIFF.FIFFB_MNE_ANNOTATIONS, FIFF.FIFFB_CHANNEL_DECOUPLER}
    skip_kinds = {FIFF.FIFF_MNE_CH_NAME_LIST, FIFF.FIFF_MNE_ROW_NAMES, FIFF.FIFF_MNE_COL_NAMES,
                  FIFF.FIFF_PROJ_ITEM_CH_NAME_LIST}
    for part in [path, *(input_dir / c for c in rec.companions)]:
        fid, tree, _ = fiff_open(part, preload=False, verbose="error")
        with fid:
            stack = [tree]
            while stack:
                node = stack.pop()
                if node.get("block") in skip_blocks:
                    continue
                for ent in node.get("directory") or []:
                    if ent.type == FIFF.FIFFT_STRING and ent.kind not in skip_kinds:
                        tag = read_tag(fid, ent.pos)
                        if ent.kind in (FIFF.FIFF_SUBJ_FIRST_NAME, FIFF.FIFF_SUBJ_MIDDLE_NAME,
                                        FIFF.FIFF_SUBJ_LAST_NAME, FIFF.FIFF_EXPERIMENTER):
                            t.name(tag.data)
                        else:
                            t.text(tag.data)
                stack.extend(node.get("children") or [])


# --- NIRS --------------------------------------------------------------------------------------------

def _nirx(t: _Terms, path: Path, rec: Recording, input_dir: Path) -> None:
    for rel in rec.companions:
        low = rel.lower()
        f = input_dir / rel
        if low.endswith(".hdr"):
            for section, key, value in _ini(_read_text(f)):
                if section.lower() == "generalinfo" and key.lower() in ("filename", "date", "time", "subject"):
                    t.text(value.strip('"'))
                elif section.lower() in ("experimentnotes", "paradigm") and key:
                    t.text(value.strip('"'))
        elif low.endswith(".inf"):
            for _, key, value in _ini(_read_text(f)):
                v = value.strip('"').replace("\\0", " ")
                (t.name if key.lower() == "name" else t.text)(v)
        elif low.endswith(".snirf"):  # NIRSport2 folders: the recording is a SNIRF file
            _snirf(t, f, rec, input_dir)
        elif low.endswith("_description.json"):
            try:
                t.text(list(_walk_py(json.loads(_read_text(f)))))
            except ValueError:
                pass


def _hitachi(t: _Terms, path: Path, rec: Recording, input_dir: Path) -> None:
    for line in _read_text(path, "latin-1").splitlines():
        cells = [c.strip() for c in line.split(",")]
        if not cells or cells[0] == "Probe1" or cells[0].startswith("Data"):
            break
        key, values = cells[0], [c for c in cells[1:] if c]
        if key == "Name":
            t.name(values)
        elif key == "ID":
            t.ident(values)
        elif key in ("Comment", "Date"):
            t.text(values)


# the standard stim columns, and optode/landmark codes (S1, D12, Nz, LPA, Cz): these name channels and
# fiducials, so as terms they would rename every channel built from them
_SNIRF_DATA_LABELS = frozenset({"onset", "duration", "amplitude", "value", "trial_type"})
_PROBE_CODE = re.compile(r"[A-Za-z]{1,3}\d{0,4}[a-z]?|[SD]\d+[_-]?[SD]?\d*|nasion|inion|lpa|rpa", re.I)


def _snirf(t: _Terms, path: Path, rec: Recording, input_dir: Path) -> None:
    import h5py
    import numpy as np

    with h5py.File(path, "r") as f:
        for gname, group in f.items():
            if not (isinstance(group, h5py.Group) and re.fullmatch(r"nirs\d*", gname)):
                continue
            tags = group.get("metaDataTags")
            if isinstance(tags, h5py.Group):
                for key, ds in tags.items():
                    if key.endswith("Unit") or not isinstance(ds, h5py.Dataset) or ds.size > 4096:
                        continue
                    value = ds[()]
                    if isinstance(value, np.ndarray):
                        value = value.tolist()
                    if isinstance(value, (int, float)) and not isinstance(value, bool):
                        value = str(value)
                    if key == "SubjectID":
                        t.ident(value)
                    else:
                        t.text(value)
            for sname, stim in group.items():
                if sname.startswith("stim") and isinstance(stim, h5py.Group):
                    if "name" in stim:
                        t.label(stim["name"][()])
                    if "dataLabels" in stim and stim["dataLabels"].size <= 4096:
                        t.label([v for v in _strings(stim["dataLabels"][()]) if v.lower() not in _SNIRF_DATA_LABELS])
            probe = group.get("probe")
            if isinstance(probe, h5py.Group):
                for key in ("sourceLabels", "detectorLabels", "landmarkLabels"):
                    if key in probe and probe[key].size <= 65536:
                        t.label([v for v in _strings(probe[key][()]) if not _PROBE_CODE.fullmatch(v)])


# --- Blackrock -----------------------------------------------------------------------------------------

def _blackrock(t: _Terms, path: Path, rec: Recording, input_dir: Path) -> None:
    import numpy as np

    with open(path, "rb") as fh:
        head = fh.read(400)
    if head[:8] == b"NEURALCD":
        t.text(head[14:30].split(b"\x00")[0].decode("latin-1"))
        t.text(head[30:286].split(b"\x00")[0].decode("latin-1"))
    elif head[:8] == b"NEURALSG":
        t.text(head[8:24].split(b"\x00")[0].decode("latin-1"))
    for rel in rec.companions:
        if not rel.lower().endswith(".nev"):
            continue
        nev = input_dir / rel
        with open(nev, "rb") as fh:
            h = fh.read(336)
            if h[:8] != b"NEURALEV":
                continue
            major = h[8]
            hdr_bytes = int.from_bytes(h[12:16], "little")
            pkt = int.from_bytes(h[16:20], "little")
            t.text(h[44:76].split(b"\x00")[0].decode("latin-1"))  # application
            t.text(h[76:332].split(b"\x00")[0].decode("latin-1"))  # comment
            n_ext = int.from_bytes(h[332:336], "little")
            ext = fh.read(32 * n_ext)
            for i in range(n_ext):
                e = ext[i * 32:(i + 1) * 32]
                if e[:8] == b"NEUEVLBL":
                    t.label(e[10:26].split(b"\x00")[0].decode("latin-1"))
                elif e[:8] == b"DIGLABEL":
                    t.label(e[8:24].split(b"\x00")[0].decode("latin-1"))
            if not 12 < pkt < 1 << 16:
                continue
            id_off = 8 if major >= 3 else 4
            text_off = id_off + 2 + 6
            fh.seek(hdr_bytes)
            while True:  # comment packets (id 0xFFFF); read in chunks, ids only
                chunk = fh.read(pkt * 65536)
                n = len(chunk) // pkt
                if n == 0:
                    break
                arr = np.frombuffer(chunk[:n * pkt], dtype=np.uint8).reshape(n, pkt)
                ids = arr[:, id_off].astype(np.uint16) | (arr[:, id_off + 1].astype(np.uint16) << 8)
                for row in np.nonzero(ids == 0xFFFF)[0]:
                    t.label(bytes(arr[row, text_off:]).split(b"\x00")[0].decode("latin-1", "replace"))


def _nwb(t: _Terms, path: Path, rec: Recording, input_dir: Path) -> None:
    from . import nwb

    nwb.collect(t, path)


_FAMILY = {
    "edf": _edf,
    "bdf": _edf,
    "gdf": _gdf,
    "brainvision": _brainvision,
    "eeglab": _eeglab,
    "cnt": _cnt,
    "egi": _egi,
    "nihon": _nihon,
    "persyst": _persyst,
    "fif": _fif,
    "ctf": _ctf,
    "kit": _kit,
    "bti": _bti,
    "nirx": _nirx,
    "hitachi": _hitachi,
    "snirf": _snirf,
    "blackrock": _blackrock,
    "nwb": _nwb,
}


def harvest(rec: Recording, input_dir: Path, raw=None) -> set[str]:
    """The identifying terms of one recording (headers, metadata, free text, paths); local use only.

    ``raw`` is the recording opened by ``readers.open_raw`` (``None`` for NWB, read by ``nwb.collect``).
    A header that cannot be parsed raises, so a recording is never planned with a partial harvest.
    """
    input_dir = Path(input_dir)
    t = _Terms()
    if rec.family in ("edf", "bdf"):
        t.placeholders.add(EDF_ANON_DATE)  # 01.01.85, what Task 9 writes; a source already anonymized
    t.paths([rec.rel, *rec.companions, *rec.headshape])
    if raw is not None:
        _raw_terms(t, raw)
    fn = _FAMILY.get(rec.family)
    if fn is not None and not rec.excluded:
        fn(t, input_dir / rec.rel, rec, input_dir)
    return t.result()


# --- post-write rewriters (Task 9): files aimport wrote itself, inside its scratch or output folder ------

EDF_PATIENT_ANON = "X X X X"
EDF_RECORDING_ANON = "Startdate X X X X"
EDF_START_DATE = "01.01.85"
EDF_START_TIME = "00.00.00"
VHDR_SECTIONS = ("Common Infos", "Binary Infos", "Channel Infos", "Coordinates")
VHDR_FIRST_LINE = "Brain Vision Data Exchange Header File Version 1.0"
_VHDR_KEYS = {
    "common infos": frozenset({"codepage", "datafile", "markerfile", "dataformat", "dataorientation", "datatype",
                               "numberofchannels", "samplinginterval", "averaged", "averagedsegments",
                               "segmentdatapoints", "segmentationtype"}),
    "binary infos": frozenset({"binaryformat", "usebigendianorder"}),
}
_CH_KEY = re.compile(r"^Ch\d+$", re.I)
_MK_KEY = re.compile(r"^Mk\d+$", re.I)
# pybv's own comment lines in the kept sections (the channel table notes); any other comment is dropped
_PYBV_COMMENT = re.compile(r"^;\s*(written using pybv|exported using pybv|data orientation|sampling interval|each entry|"
                           r"<resolution|fields are delimited|commas in|<channel|<date|\s*<size in data points)", re.I)


class HeaderError(ValueError):
    """A written header is not what aimport writes; the message names the field kind, never its text."""


def _inside(path: Path, root: Path) -> bool:
    path, root = Path(path).resolve(), Path(root).resolve()
    return path == root or root in path.parents


def rewrite_edf(path: Path, *, root: Path, labels: Iterable[str] | None = None) -> None:
    """Clear the EDF/BDF header aimport wrote, in place: patient ``X X X X``, recording ``Startdate X X X X``,
    startdate ``01.01.85``, starttime ``00.00.00``, every field space-padded to its fixed width.

    ``root``: the folder the file must lie in (aimport's scratch or output folder; never a source). The
    header length is checked against the signal count first. ``labels``: when given, every TAL annotation
    text must be one of them (``HeaderError`` otherwise).
    """
    path = Path(path)
    if not _inside(path, root) or path.is_symlink():
        raise HeaderError("an EDF header can only be rewritten inside the output")
    with open(path, "r+b") as fh:
        head = bytearray(fh.read(256))
        if len(head) != 256:
            raise HeaderError("EDF header length")
        try:
            ns = int(head[252:256].decode("ascii").strip())
            size = int(head[184:192].decode("ascii").strip())
        except ValueError:
            raise HeaderError("EDF header length") from None
        if not 0 < ns < 100000 or size != 256 * (ns + 1) or path.stat().st_size < size:
            raise HeaderError("EDF header length")
        for start, width, value in ((8, 80, EDF_PATIENT_ANON), (88, 80, EDF_RECORDING_ANON),
                                    (168, 8, EDF_START_DATE), (176, 8, EDF_START_TIME)):
            field = value.encode("ascii").ljust(width, b" ")
            assert len(field) == width
            head[start:start + width] = field
        fh.seek(0)
        fh.write(bytes(head))
    if labels is not None:
        allowed = {str(x) for x in labels}
        if any(text not in allowed for text in edf_annotation_texts(path)):
            raise HeaderError("EDF annotation not in the event list")


def edf_annotation_texts(path: Path) -> list[str]:
    """The TAL annotation texts of an EDF+/BDF+ file (onsets and the empty time-keeping texts left out)."""
    with open(path, "rb") as fh:
        head = fh.read(256)
        ns = int(head[252:256].decode("ascii").strip())
        sig = fh.read(256 * ns)
    labels = [sig[16 * i:16 * (i + 1)].decode("latin-1").strip().lower() for i in range(ns)]
    base = 216 * ns  # samples per record: after label 16, transducer 80, dim/pmin/pmax/dmin/dmax 5 x 8, prefilter 80
    samples = [int(sig[base + 8 * i:base + 8 * (i + 1)].decode("ascii").strip()) for i in range(ns)]
    annot = [i for i, lab in enumerate(labels) if lab in ("edf annotations", "bdf annotations")]
    if not annot:
        return []
    bps = 3 if head[0] == 0xFF else 2
    offsets, pos = [], 0
    for n in samples:
        offsets.append(pos)
        pos += n * bps
    out: list[str] = []
    with open(path, "rb") as fh:
        fh.seek(256 * (ns + 1))
        while True:
            record = fh.read(pos)
            if len(record) < pos or pos == 0:
                break
            for i in annot:
                for tal in record[offsets[i]:offsets[i] + samples[i] * bps].split(b"\x00"):
                    for piece in tal.split(b"\x14")[1:]:
                        text = piece.decode("utf-8", "replace").strip()
                        if text:
                            out.append(text)
    return out


def rebuild_vhdr(path: Path, bids_stem: str) -> None:
    """Rebuild a written BrainVision ``.vhdr`` with only ``[Common Infos]``, ``[Binary Infos]``, ``[Channel
    Infos]`` and ``[Coordinates]`` (their known keys and channel lines, plus pybv's table comments).
    ``DataFile``/``MarkerFile`` become ``<bids_stem>.eeg``/``.vmrk``; every other section ([Comment]) is
    dropped."""
    path = Path(path)
    text = _read_text(path)
    sections: dict[str, list[str]] = {s.lower(): [] for s in VHDR_SECTIONS}
    current: str | None = None
    for line in text.splitlines()[1:]:
        s = line.strip()
        if s.startswith("[") and s.endswith("]"):
            name = s[1:-1].strip().lower()
            current = name if name in sections else None
            continue
        if current is None or not s:
            continue
        if s.startswith(";"):
            if _PYBV_COMMENT.match(s):
                sections[current].append(s)
            continue
        key, sep, _ = s.partition("=")
        key = key.strip()
        if not sep:
            continue
        if current in _VHDR_KEYS:
            if key.lower() == "datafile":
                s = f"DataFile={bids_stem}.eeg"
            elif key.lower() == "markerfile":
                s = f"MarkerFile={bids_stem}.vmrk"
            elif key.lower() not in _VHDR_KEYS[current]:
                continue
        elif not _CH_KEY.match(key):
            continue
        sections[current].append(s)
    common = sections["common infos"]
    if not any(x.lower().startswith("datafile=") for x in common):
        raise HeaderError("BrainVision header without a data file")
    if not any(x.lower().startswith("markerfile=") for x in common):
        common.append(f"MarkerFile={bids_stem}.vmrk")
    out = [VHDR_FIRST_LINE, ""]
    for name in VHDR_SECTIONS:
        lines = sections[name.lower()]
        if lines:
            out += [f"[{name}]", *lines, ""]
    path.write_text("\n".join(out), encoding="utf-8")


def check_vmrk(path: Path, allowed_labels: Iterable[str], bids_stem: str | None = None) -> None:
    """A written ``.vmrk``: every marker description is an allowed label or a safe ``Stimulus/S  1`` code,
    no marker carries a date from 1925 on, and ``DataFile`` is the BIDS name. ``HeaderError`` otherwise."""
    allowed = {str(x) for x in allowed_labels}
    section = ""
    for line in _read_text(Path(path)).splitlines():
        s = line.strip()
        if s.startswith("[") and s.endswith("]"):
            section = s[1:-1].strip().lower()
            continue
        if not s or s.startswith(";"):
            continue
        key, sep, value = s.partition("=")
        if not sep:
            continue
        if section == "common infos" and key.strip().lower() == "datafile":
            if bids_stem is not None and value.strip() != f"{bids_stem}.eeg":
                raise HeaderError("BrainVision marker file names another data file")
        elif section == "marker infos" and _MK_KEY.match(key.strip()):
            fields = [f.replace(r"\1", ",") for f in value.split(",")]
            mtype = fields[0].strip()
            desc = fields[1].strip() if len(fields) > 1 else ""
            if mtype.lower() not in _BV_MARKER_TYPES:
                raise HeaderError("BrainVision marker type")
            if desc and desc not in allowed and not is_safe(f"{mtype}/{desc}"):
                raise HeaderError("BrainVision marker description")
            when = fields[5].strip() if len(fields) > 5 else ""
            if when and (not when.isdigit() or int(when[:4]) >= 1925):
                raise HeaderError("BrainVision marker date")


SNIRF_TAGS = ("SubjectID", "MeasurementDate", "MeasurementTime", "LengthUnit", "TimeUnit", "FrequencyUnit")
SNIRF_GROUPS = frozenset({"metaDataTags", "data1", "probe"})


def check_snirf(path: Path, subject_label: str, allowed_labels: Iterable[str]) -> None:
    """A written SNIRF: ``/nirs*/metaDataTags`` holds exactly the six tags (``SubjectID`` the BIDS label, the
    measurement date and time ``unknown``), every ``stim*/name`` is an allowed label, and ``/nirs`` holds no
    other group. ``HeaderError`` otherwise (the message names the field kind, never its text)."""
    import h5py

    allowed = {str(x) for x in allowed_labels}

    def text(ds) -> str:
        v = ds[()]
        if hasattr(v, "reshape") and getattr(v, "size", 1):
            v = v.reshape(-1)[0]
        return v.decode("utf-8", "replace") if isinstance(v, bytes) else str(v)

    with h5py.File(path, "r") as f:
        groups = [k for k in f if re.fullmatch(r"nirs\d*", k)]
        if set(f) - set(groups) - {"formatVersion"} or not groups:
            raise HeaderError("SNIRF root")
        for g in groups:
            nirs = f[g]
            tags = nirs.get("metaDataTags")
            if tags is None or sorted(tags) != sorted(SNIRF_TAGS):
                raise HeaderError("SNIRF metaDataTags")
            if text(tags["SubjectID"]) != subject_label:
                raise HeaderError("SNIRF SubjectID")
            if text(tags["MeasurementDate"]) != "unknown" or text(tags["MeasurementTime"]) != "unknown":
                raise HeaderError("SNIRF measurement date")
            for name in nirs:
                if re.fullmatch(r"stim\d+", name):
                    if text(nirs[name]["name"]) not in allowed:
                        raise HeaderError("SNIRF stim name")
                elif name not in SNIRF_GROUPS:
                    raise HeaderError("SNIRF group")
