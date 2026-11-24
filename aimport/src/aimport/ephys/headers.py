"""Format headers: the identifying-term harvest of one recording (and, from Task 9, the post-write rewriters).

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
from .discover import VOCAB, Recording
from .events import is_safe

MAX_TEXT = 4 << 20  # bytes read from any text header or log
_VOCAB = frozenset(v.lower() for v in VOCAB)
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
_VOCAB = _VOCAB | frozenset(SYSTEM_WORDS)
HARVEST_VOCAB = tuple(VOCAB) + SYSTEM_WORDS
_MARKER_CODE = re.compile(r"^[SR]\s*\d{1,4}$")
_TIME = re.compile(r"^\d{1,2}:\d{2}(:\d{2})?([.,]\d+)?$")
_MONTHS = ("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC")
_DMY = re.compile(r"(?<!\d)(\d{1,2})-(" + "|".join(_MONTHS) + r")-(\d{4})(?!\d)", re.I)
_YMD = re.compile(r"(?<!\d)(\d{4})[-/.]?(\d{2})[-/.]?(\d{2})(?!\d)")
_DMY_NUM = re.compile(r"(?<!\d)(\d{2})[./](\d{2})[./](\d{4})(?!\d)")
_BV_BOILERPLATE = re.compile(
    r"pybv|vision recorder|brain ?vision|each entry|fields are|commas in|<|data orientation|sampling interval|"
    r"copyright|resolution in", re.I)
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


def _dates_in(text: str) -> list[date]:
    out = []
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

    def date(self, d: date | datetime | None) -> None:
        if isinstance(d, datetime):
            d = d.date()
        if isinstance(d, date) and d.year >= 1900:  # year-1 and 1900 placeholders are no one's date
            self.terms |= _all_forms(d)

    def text(self, value: Any) -> None:
        """Free text: the whole value and every date in it."""
        for s in _strings(value):
            self.terms.add(s)
            for d in _dates_in(s):
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
    if low in _GENERIC or low in _VOCAB:
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
            t.date(v)
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


def _edf_field(t: _Terms, field_text: str, name_index: int | None) -> None:
    t.text(field_text)
    for i, tok in enumerate(field_text.split()):
        if tok in EDF_SKIP:
            continue
        if i == name_index:
            t.name(tok)
        else:
            t.text(tok)
            t.text(tok.replace("_", " "))


def _edf(t: _Terms, path: Path, rec: Recording, input_dir: Path) -> None:
    h = read_edf_header(path)
    with open(path, "rb") as fh:
        head = fh.read(256)
    reserved = head[192:236].decode("latin-1").strip()
    plus = reserved.upper().startswith(("EDF+", "BDF+")) or h.recording.startswith("Startdate")
    _edf_field(t, h.patient, 3 if plus else None)
    _edf_field(t, h.recording, 3 if plus else None)
    if not plus:  # plain EDF: the patient field is free text, any word may be a name
        for tok in h.patient.split():
            t.name(tok)
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

def _bv_comment_line(t: _Terms, line: str) -> None:
    s = line.strip()
    if not s or s.startswith("#") or s[0].isdigit() or _BV_BOILERPLATE.search(s):
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
            _bv_comment_line(t, s[1:])
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
            _bv_comment_line(t, s[1:])
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
    elif obj.dtype == h5py.ref_dtype and obj.size < (1 << 20):
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
    t.text(s(225, 10))


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
    for log in sorted(path.glob("log_*.txt")):
        t.paths([log.name])
        for line in _read_text(log).splitlines():
            m = re.search(r"\bName:\s*(.+)$", line)
            if m:
                t.path(m.group(1).strip())


# --- MEG -------------------------------------------------------------------------------------------

_INFODS_KEY = re.compile(rb"([\x00-\xff]{4})(_[A-Z0-9_]+)\x00\x00\x00\x0a([\x00-\xff]{4})")


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
    try:
        from mne.io.ctf.res4 import _read_res4
        from mne.utils import use_log_level

        with use_log_level("error"):
            res4 = _read_res4(str(path))
    except Exception:  # noqa: BLE001 - MNE has read the header already; this is the extra text
        res4 = {}
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
    for name_ in ("MarkerFile.mrk", "ClassFile.cls"):
        f = path / name_
        if f.is_file():
            lines = _read_text(f).splitlines()
            for i, line in enumerate(lines[:-1]):
                if line.strip() in ("NAME:", "COMMENT:"):
                    t.label(lines[i + 1].strip())


def _kit(t: _Terms, path: Path, rec: Recording, input_dir: Path) -> None:
    for rel in [*rec.companions, *rec.headshape]:
        if rel.lower().endswith((".elp", ".hsp", ".txt")):
            for line in _read_text(input_dir / rel).splitlines():
                s = line.strip()
                if s.startswith("%") and not re.match(r"%[A-Z]\s", s):
                    t.text(s.lstrip("% ").strip())


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
                if sname.startswith("stim") and isinstance(stim, h5py.Group) and "name" in stim:
                    t.label(stim["name"][()])


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
    "nirx": _nirx,
    "hitachi": _hitachi,
    "snirf": _snirf,
    "blackrock": _blackrock,
}


def harvest(rec: Recording, input_dir: Path, raw=None) -> set[str]:
    """The identifying terms of one recording (headers, metadata, free text, paths); local use only.

    ``raw`` is the recording opened by ``readers.open_raw`` (``None`` for NWB, which Task 10 reads).
    A header that cannot be parsed raises, so a recording is never planned with a partial harvest.
    """
    input_dir = Path(input_dir)
    t = _Terms()
    t.paths([rec.rel, *rec.companions, *rec.headshape])
    if raw is not None:
        _raw_terms(t, raw)
    fn = _FAMILY.get(rec.family)
    if fn is not None and not rec.excluded:
        fn(t, input_dir / rec.rel, rec, input_dir)
    return t.result()
