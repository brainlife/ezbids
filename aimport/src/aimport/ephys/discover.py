"""Find electrophysiology and optical recordings under an input folder, reading headers only.

One ``Recording`` per recording: ``rel`` is its main file or folder, ``companions`` the files that
belong to it, ``headshape`` its head-shape files (never read into the output by default). All of
them are claim roots, so a multi-file recording is claimed as a unit. ``.ds``, ``.mff`` and ``.mefd``
folders, BTi and NIRx run folders and BIDS datatype folders are claimed as one root and not walked
more than needed. Remote sources are not supported for ephys; ``remote`` is ignored.
"""
from __future__ import annotations

import json
import math
import os
import re
from dataclasses import dataclass, field
from importlib.util import find_spec
from pathlib import Path

from ..micr import names
from ..modality import Claim

FAMILIES = ("edf", "bdf", "gdf", "brainvision", "eeglab", "cnt", "egi", "nihon", "persyst", "mef3", "fif", "ctf",
            "bti", "kit", "nirx", "hitachi", "snirf", "nwb", "blackrock", "unsupported")
EPHYS_VOCAB = ("eeg", "meg", "ieeg", "nirs", "fnirs", "emg", "rest", "resting", "task", "run", "noise", "emptyroom",
               "erm", "sleep", "oddball", "mmn", "motor", "tapping", "auditory", "visual", "faces", "nback",
               "eyes", "open", "closed")
# file extensions, so they are not read as names in paths
EPHYS_EXTENSIONS = ("edf", "bdf", "gdf", "vhdr", "vmrk", "fdt", "fif", "snirf", "nwb", "sqd", "con", "cnt", "lay",
                    "hdr", "wl1", "wl2", "evt", "tri", "ds", "mff", "mefd", "nev", "ns1", "ns2", "ns3", "ns4",
                    "ns5", "ns6", "set", "pos", "hsp", "mrk", "elp")
EPHYS_VOCAB = EPHYS_VOCAB + EPHYS_EXTENSIONS
VOCAB = names.VOCAB + EPHYS_VOCAB

DATATYPES = ("eeg", "meg", "ieeg", "nirs", "emg")
FIF_DERIVED = re.compile(r"-(ave|cov|epo|fwd|inv|trans|sol|proj)\.fif(\.gz)?$", re.I)
FIF_SPLIT = re.compile(r"^(?P<base>.+)-(?P<n>\d+)(?P<ext>\.fif(\.gz)?)$", re.I)
BIDS_SPLIT = re.compile(r"_split-(\d+)(?=_[A-Za-z0-9]+\.fif(\.gz)?$)", re.I)
MAX_SIDECAR = 1 << 20
UNSUPPORTED_EXT = (".oxy3", ".oxy4", ".oxy5", ".oxyproj", ".omm")
REASON_OPTICAL = "export to SNIRF first"
REASON_MEF3 = "MEF3: export to EDF first"
REASON_HZ = "CTF head-localisation run"
REASON_BV = "BrainVision data file outside its folder"
REASON_PERSYST = "Persyst data file outside its folder"
EMPTY_TOKENS = frozenset({"emptyroom", "erm", "noise"})
EGI_VERSIONS = (2, 3, 4, 5, 6, 7)
EEGREF_RE = re.compile(r"^[A-Za-z0-9 _/+-]{1,32}$")
LABEL_RE = re.compile(r"^[A-Za-z0-9]+$")
_TOKEN = re.compile(r"[^a-z0-9]+")


@dataclass
class Recording:
    rel: str
    family: str
    companions: list[str] = field(default_factory=list)
    headshape: list[str] = field(default_factory=list)
    empty_room: bool = False
    excluded: str | None = None
    meta: dict = field(default_factory=dict)  # from a BIDS input: task/run/acq and safe numeric fields


def _head(path: str | os.PathLike, n: int) -> bytes:
    try:
        with open(path, "rb") as fh:
            return fh.read(n)
    except OSError:
        return b""


def is_empty_room(rel: str) -> bool:
    low = rel.lower().replace("\\", "/")
    if "empty_room" in low or "empty-room" in low:
        return True
    return bool({t for t in _TOKEN.split(low) if t} & EMPTY_TOKENS)


def _plain_name(name: str) -> bool:
    return bool(name) and name not in (".", "..") and "/" not in name and "\\" not in name and "\0" not in name


def _ini_value(path: str, key: str, section: str | None = None) -> str | None:
    """First ``key=value`` in the text file (optionally within ``[section]``); header files only."""
    try:
        text = Path(path).read_bytes()[:1 << 20].decode("utf-8", "replace")
    except OSError:
        return None
    cur = None
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("[") and line.endswith("]"):
            cur = line[1:-1].strip().lower()
            continue
        if section is not None and cur != section.lower():
            continue
        k, sep, v = line.partition("=")
        if sep and k.strip().lower() == key.lower():
            return v.strip()
    return None


def _nwb_has_electrical_series(path: str) -> bool:
    try:
        import h5py

        with h5py.File(path, "r") as f:
            for group in ("acquisition", "processing"):
                if group not in f:
                    continue
                for child in f[group].values():
                    nt = child.attrs.get("neurodata_type", b"")
                    if isinstance(nt, bytes):
                        nt = nt.decode("utf-8", "replace")
                    if nt == "ElectricalSeries":
                        return True
                    if group == "processing" and hasattr(child, "values"):
                        for sub in child.values():
                            nt = sub.attrs.get("neurodata_type", b"")
                            nt = nt.decode("utf-8", "replace") if isinstance(nt, bytes) else nt
                            if nt == "ElectricalSeries":
                                return True
    except Exception:  # noqa: BLE001 - not an HDF5/NWB file
        return False
    return False


def _bids_meta(directory: Path, name: str) -> dict:
    """task/run/acq from a BIDS file name; PowerLineFrequency and EEGReference from its sidecar."""
    meta: dict = {}
    for part in re.split(r"[_.]", name):
        key, sep, val = part.partition("-")
        if sep and key in ("task", "run", "acq") and LABEL_RE.fullmatch(val):
            meta[key] = val
    stem = re.sub(r"\.(edf|bdf|vhdr|set|fif|snirf|nwb|gdf|cnt|sqd|con|lay)(\.gz)?$", "", name, flags=re.I)
    sidecar = directory / f"{stem}.json"
    try:
        data = (json.loads(sidecar.read_bytes()[:MAX_SIDECAR + 1].decode("utf-8"))
                if sidecar.is_file() and not sidecar.is_symlink() and sidecar.stat().st_size <= MAX_SIDECAR else {})
    except (OSError, ValueError):  # includes UnicodeDecodeError
        data = {}
    if isinstance(data, dict):
        v = data.get("PowerLineFrequency")
        if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and 0 < v < 1000:
            meta["PowerLineFrequency"] = v
        ref = data.get("EEGReference")
        if isinstance(ref, str) and EEGREF_RE.fullmatch(ref):
            meta["EEGReference"] = ref
    return meta


class _Scan:
    """Collects recordings and claim roots of one walk."""

    def __init__(self) -> None:
        self.recordings: list[Recording] = []
        self.roots: list[str] = []

    def add(self, rec: Recording, extra_roots: list[str] | None = None, claim_roots: bool = True) -> None:
        rec.empty_room = is_empty_room(rec.rel)
        self.recordings.append(rec)
        if claim_roots:
            for r in [rec.rel, *rec.companions, *rec.headshape, *(extra_roots or [])]:
                if r not in self.roots:
                    self.roots.append(r)


def _join(rel_dir: str, name: str) -> str:
    return f"{rel_dir}/{name}" if rel_dir else name


def _is_bids_datatype_dir(rel: str) -> bool:
    parts = rel.split("/")
    if parts[-1] not in DATATYPES or len(parts) < 2:
        return False
    up = parts[:-1][-2:]
    if len(up) == 2 and up[0].startswith("sub-") and up[1].startswith("ses-"):
        return True
    return up[-1].startswith("sub-") and len(up[-1]) > 4


def _folder_recording(entry: os.DirEntry, rel: str) -> Recording | None:
    low = entry.name.lower()
    if low.endswith(".ds"):
        if low == "hz.ds":
            return Recording(rel, "ctf", excluded=REASON_HZ)
        return Recording(rel, "ctf")
    if low.endswith(".mff"):
        if not os.path.isfile(os.path.join(entry.path, "info.xml")):
            return None
        return Recording(rel, "egi")
    if low.endswith(".mefd"):
        if find_spec("pymef") is not None:
            return Recording(rel, "mef3")
        return Recording(rel, "unsupported", excluded=REASON_MEF3)
    return None


def _run_folder(files: dict[str, os.DirEntry], rel: str) -> Recording | None:
    """A BTi or NIRx run folder, judged from its own entries."""
    low = sorted(files)
    if "config" in files and any(n.startswith(("c,rf", "e,rf")) for n in low):
        comp = [_join(rel, files[n].name) for n in low if n == "config" or n.startswith(("c,rf", "e,rf"))]
        shape = [_join(rel, files[n].name) for n in low if n == "hs_file"]
        # the folder is the root; its files are listed for the planner
        return Recording(rel, "bti", companions=comp, headshape=shape)
    hdrs = [n for n in low if n.endswith(".hdr")]
    if hdrs and any(n.endswith((".wl1", ".wl2")) for n in low):
        return Recording(rel, "nirx", companions=[_join(rel, files[n].name) for n in low if n != ".."])
    if any(n.endswith("_config.json") for n in low) and any(n.endswith(".snirf") for n in low):
        return Recording(rel, "nirx", companions=[_join(rel, files[n].name) for n in low if n != ".."])
    return None


def _fif_continuations(low: str, names_: list[str]) -> list[str] | None:
    """Later parts of the FIF recording ``low`` (``x-1.fif`` chains after ``x.fif``, BIDS ``split-02`` after
    ``split-01``); None when ``low`` is itself a later part."""
    present = set(names_)
    bids = BIDS_SPLIT.search(low)
    if bids:
        def part(n: int) -> str:
            return low[:bids.start()] + f"_split-{n:0{len(bids.group(1))}d}" + low[bids.end():]
        nums = sorted(int(m.group(1)) for n in names_ if (m := BIDS_SPLIT.search(n)) and BIDS_SPLIT.sub("", n) == BIDS_SPLIT.sub("", low))
        if int(bids.group(1)) != nums[0]:
            return None
        return [part(n) for n in nums[1:] if part(n) in present]
    m = FIF_SPLIT.match(low)
    if m:
        base = m["base"] + m["ext"]
        k = int(m["n"])
        if base in present and all(f"{m['base']}-{i}{m['ext']}" in present for i in range(1, k + 1)):
            return None
    out = []
    stem, ext = re.match(r"^(.+?)(\.fif(?:\.gz)?)$", low).groups()
    i = 1
    while f"{stem}-{i}{ext}" in present:
        out.append(f"{stem}-{i}{ext}")
        i += 1
    return out


def _file_recordings(files: dict[str, os.DirEntry], rel_dir: str, scan: _Scan) -> None:
    """Recognise the recordings among the files of one folder (companions are matched by name)."""
    low_names = sorted(files)

    def rel(n: str) -> str:
        return _join(rel_dir, files[n].name)

    def same_stem(stem: str, *exts: str) -> list[str]:
        return [rel(stem + e) for e in exts if (stem + e) in files]

    def dir_files(*exts: str) -> list[str]:
        return [rel(n) for n in low_names if n.endswith(exts)]

    taken: set[str] = set()  # lowercase names already claimed as companions of another recording
    deferred: list[Recording] = []
    for low in low_names:
        e = files[low]
        path = e.path
        stem, dot, ext = low.rpartition(".")
        ext = dot + ext
        if low in taken:
            continue
        if low.endswith((".edf", ".rec")):
            if _head(path, 8) == b"0       ":
                scan.add(Recording(rel(low), "edf"))
        elif low.endswith(".bdf"):
            if _head(path, 8) == b"\xffBIOSEMI":
                scan.add(Recording(rel(low), "bdf"))
        elif low.endswith(".gdf"):
            if _head(path, 3) == b"GDF":
                scan.add(Recording(rel(low), "gdf"))
        elif low.endswith(".vhdr"):
            deferred.append(_brainvision(path, files, rel_dir, rel(low), taken))
        elif low.endswith(".set"):
            if _head(path, 6) == b"MATLAB" or _head(path, 4) == b"\x89HDF":
                scan.add(Recording(rel(low), "eeglab", companions=same_stem(stem, ".fdt")))
        elif low.endswith(".cnt"):
            scan.add(Recording(rel(low), "cnt"))
        elif low.endswith(".raw"):
            head = _head(path, 4)
            if len(head) == 4 and int.from_bytes(head, "big") in EGI_VERSIONS:
                scan.add(Recording(rel(low), "egi"))
        elif low.endswith(".eeg"):
            comp = same_stem(stem, ".pnt", ".log", ".21e")
            if any(c.lower().endswith((".pnt", ".21e")) for c in comp):
                scan.add(Recording(rel(low), "nihon", companions=comp))
        elif low.endswith(".lay"):
            scan.add(_persyst(path, files, rel_dir, rel(low)))
        elif re.search(r"\.fif(\.gz)?$", low):
            if FIF_DERIVED.search(low):
                scan.add(Recording(rel(low), "fif", excluded=f"derived FIF ({FIF_DERIVED.search(low).group(1)})"))
                continue
            splits = _fif_continuations(low, low_names)
            if splits is None:
                continue  # a later part of another recording
            splits = [rel(n) for n in splits]
            taken.update(Path(x).name.lower() for x in splits)
            scan.add(Recording(rel(low), "fif", companions=splits))
        elif low.endswith((".sqd", ".con")):
            scan.add(Recording(rel(low), "kit", companions=dir_files(".mrk", ".elp"), headshape=dir_files(".hsp")))
        elif low.endswith(".snirf"):
            scan.add(Recording(rel(low), "snirf"))
        elif low.endswith(".nwb"):
            if _nwb_has_electrical_series(path):
                scan.add(Recording(rel(low), "nwb"))
        elif re.fullmatch(r"\.ns[1-6]", ext):
            nev = same_stem(stem, ".nev")
            if nev:
                scan.add(Recording(rel(low), "blackrock", companions=nev))
        elif low.endswith(UNSUPPORTED_EXT):
            scan.add(Recording(rel(low), "unsupported", excluded=REASON_OPTICAL))
        elif low.endswith((".csv", ".txt")):
            first = _head(path, 1024)
            line = first.split(b"\n", 1)[0].decode("latin-1", "replace")
            if low.endswith(".csv") and line.startswith("Header") and "ETG" in line:
                scan.add(Recording(rel(low), "hitachi"))
            elif b"shimadzu" in first.lower():
                scan.add(Recording(rel(low), "unsupported", excluded=REASON_OPTICAL))
    for rec in deferred:
        scan.add(rec)


def _brainvision(path: str, files: dict[str, os.DirEntry], rel_dir: str, rel: str, taken: set[str]) -> Recording:
    stem = Path(path).stem
    data = _ini_value(path, "DataFile", "Common Infos")
    marker = _ini_value(path, "MarkerFile", "Common Infos")
    rec = Recording(rel, "brainvision")
    for value, fallback_ext in ((data, ".eeg"), (marker, ".vmrk")):
        name = value if value else stem + fallback_ext
        if not _plain_name(name):
            if value is data:
                rec.excluded = REASON_BV
            continue
        e = files.get(name.lower())
        if e is not None:
            rec.companions.append(_join(rel_dir, e.name))
            taken.add(e.name.lower())
    if rec.excluded:  # refused: claim the same-stem siblings so their text and data stay out of ezBIDS
        rec.companions = [_join(rel_dir, files[stem.lower() + x].name) for x in (".eeg", ".vmrk")
                          if stem.lower() + x in files]
    return rec


def _persyst(path: str, files: dict[str, os.DirEntry], rel_dir: str, rel: str) -> Recording:
    value = _ini_value(path, "File", "FileInfo")
    rec = Recording(rel, "persyst")
    name = value if value else Path(path).stem + ".dat"
    if not _plain_name(name):
        rec.excluded = REASON_PERSYST
        sib = files.get(Path(path).stem.lower() + ".dat")
        if sib is not None:
            rec.companions.append(_join(rel_dir, sib.name))
        return rec
    e = files.get(name.lower())
    if e is not None:
        rec.companions.append(_join(rel_dir, e.name))
    return rec


def _ctf_headshape(files: dict[str, os.DirEntry], rel_dir: str) -> list[str]:
    return [_join(rel_dir, e.name) for k, e in sorted(files.items()) if k.endswith(".pos")]


def _walk(directory: str, rel_dir: str, scan: _Scan) -> None:
    try:
        with os.scandir(directory) as it:
            entries = sorted(it, key=lambda e: e.name)
    except OSError:
        return
    files: dict[str, os.DirEntry] = {}
    subdirs: list[os.DirEntry] = []
    for e in entries:
        if e.name.startswith(".") or e.is_symlink():
            continue
        if e.is_dir(follow_symlinks=False):
            subdirs.append(e)
        elif e.is_file(follow_symlinks=False):
            files[e.name.lower()] = e

    run = _run_folder(files, rel_dir) if rel_dir else None
    if run is not None:
        scan.add(run)
        return

    _file_recordings(files, rel_dir, scan)
    # CTF head shapes sit beside the .ds folders
    ctf_here = []
    for e in subdirs:
        rec = _folder_recording(e, _join(rel_dir, e.name))
        if rec is not None:
            scan.add(rec)
            if rec.family == "ctf":
                ctf_here.append(rec)
    shape = _ctf_headshape(files, rel_dir)
    for rec in ctf_here:
        rec.headshape = list(shape)
        for r in shape:
            if r not in scan.roots:
                scan.roots.append(r)
    for e in subdirs:
        if _folder_recording(e, "") is not None:
            continue
        rel = _join(rel_dir, e.name)
        if _is_bids_datatype_dir(rel):
            inner = _Scan()
            _walk(e.path, rel, inner)
            if inner.recordings:
                for rec in inner.recordings:
                    rec.meta = _bids_meta(Path(e.path), Path(rec.rel).name) if rec.family not in ("ctf", "bti", "nirx", "egi", "mef3") else {}
                    scan.add(rec, claim_roots=False)
                scan.roots.append(rel)
            continue
        _walk(e.path, rel, scan)


def claim(input_dir: Path, remote: list[str] | None = None) -> tuple[Claim, list[Recording]]:
    """Claim recordings under input_dir. ``remote`` is ignored: remote sources are not supported for ephys."""
    scan = _Scan()
    _walk(str(input_dir), "", scan)
    return Claim(roots=scan.roots, remote=[]), scan.recordings
