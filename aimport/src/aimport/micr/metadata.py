"""Microscopy metadata rebuilt from an allowlist.

Nothing in a source's metadata is cleaned field by field: the facts aimport keeps (pixel size,
wavelengths, objective, acquisition date) are read out into a fresh ``ImageInfo``, and every
other string value is dropped and returned as a *term* so later steps can redact it.
"""
from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Any, Literal

PixelUnit = Literal["mm", "um", "nm"]
AXES_ORDER = "tczyx"
SKIPPED_SERIES = ("label", "macro", "thumbnail")

# Length units to metres (OME UnitsLength values and NGFF/UDUNITS axis unit names).
_LENGTH_M = {
    "m": 1.0, "meter": 1.0, "dm": 1e-1, "cm": 1e-2, "centimeter": 1e-2, "mm": 1e-3, "millimeter": 1e-3,
    "µm": 1e-6, "um": 1e-6, "micron": 1e-6, "micrometer": 1e-6, "nm": 1e-9, "nanometer": 1e-9,
    "Å": 1e-10, "angstrom": 1e-10, "pm": 1e-12, "picometer": 1e-12,
}
_UNIT_M = {"mm": 1e-3, "um": 1e-6, "nm": 1e-9}


@dataclass
class ChannelInfo:
    excitation_nm: float | None
    emission_nm: float | None
    name_code: str  # "ch<excitation>" or "ch<i>"; never a name from the source


@dataclass
class ImageInfo:
    family: str
    axes: str  # a subset of "tczyx", in that order
    shape: tuple[int, ...]
    dtype: str
    pixel_size: dict[str, float] = field(default_factory=dict)  # keys among x, y, z
    pixel_unit: PixelUnit | None = "um"  # None: the source has no unit (set in the plan, never assumed)
    channels: list[ChannelInfo] = field(default_factory=list)
    objective_magnification: float | None = None
    objective_na: float | None = None
    immersion: str | None = None  # OME Objective Immersion enum value only
    levels: int = 1
    zarr_format: Literal[2, 3] | None = None
    ngff_version: str | None = None
    acquisition_mode: str | None = None  # OME Channel AcquisitionMode enum value only
    acquired: date | None = field(default=None, repr=False)  # local only: records, never the view
    series_skipped: list[str] = field(default_factory=list)


def length_factor(unit: Any) -> float | None:
    """Metres per unit for an OME UnitsLength or an axis unit name; None when unknown."""
    if unit is None:
        return None
    key = unit.value if isinstance(unit, Enum) else str(unit)
    return _LENGTH_M.get(key) or _LENGTH_M.get(key.lower())


def convert_length(value: float, unit: Any, to: PixelUnit) -> float | None:
    factor = length_factor(unit)
    if factor is None:
        return None
    return float(value) * factor / _UNIT_M[to]


def wavelength_nm(value: float | None, unit: Any = None) -> float | None:
    if value is None:
        return None
    if unit is None:
        return float(value)
    nm = convert_length(value, unit, "nm")
    return round(nm, 3) if nm is not None else None


def channel_code(excitation_nm: float | None, index: int) -> str:
    return f"ch{round(excitation_nm)}" if excitation_nm else f"ch{index}"


def date_terms(value: date | datetime) -> set[str]:
    """The spellings a date can take in a name or a header: 2025-02-15, 20250215, 250215, 2025:02:15."""
    d = value.date() if isinstance(value, datetime) else value
    terms = {d.isoformat(), d.strftime("%Y%m%d"), d.strftime("%y%m%d"), d.strftime("%Y:%m:%d")}
    if isinstance(value, datetime):
        terms.add(value.isoformat())
    return terms


# Format vocabulary: data-type names, length and time unit names, axis names and types, and the
# words of NGFF, Zarr and codec metadata. Like the BIDS-name vocabulary, these never identify anyone,
# so they are never terms: a source that says dtype "uint16" must not make every uint16 store's
# rebuilt metadata look identifying. Compared casefolded with separators squashed (format_vocab).
_DTYPES = {f"{k}{n}" for k in ("int", "uint") for n in (8, 16, 32, 64)} | {
    "float16", "float32", "float64", "float128", "complex64", "complex128", "complex256", "bool", "byte",
    "ubyte", "short", "ushort", "int", "uint", "long", "ulong", "float", "double", "single", "half",
    "u1", "u2", "u4", "u8", "i1", "i2", "i4", "i8", "f2", "f4", "f8", "c8", "c16", "uint8clamped",
    "bfloat16", "rgb", "rgba", "bit", "boolean", "string", "str", "bytes", "unsigned", "signed", "integer",
}
_PREFIXES = ("", "yotta", "zetta", "exa", "peta", "tera", "giga", "mega", "kilo", "hecto", "deca", "deci",
             "centi", "milli", "micro", "nano", "pico", "femto", "atto", "zepto", "yocto")
_UNITS = ({p + "meter" for p in _PREFIXES} | {p + "metre" for p in _PREFIXES} | {p + "second" for p in _PREFIXES}
          | {"angstrom", "foot", "inch", "mile", "yard", "parsec", "micron", "microns", "minute", "hour", "day",
             "um", "µm", "mm", "nm", "cm", "pm", "km", "ms", "us", "µs", "ns", "sec", "min", "pixel", "pixels",
             "px", "hz", "khz", "mhz", "degree", "degrees", "radian", "radians", "unit", "units"})
_FORMAT_WORDS = {
    # axes
    "space", "time", "channel", "channels", "axis", "axes", "x", "y", "z", "c", "t",
    # NGFF / OME-Zarr
    "ome", "ngff", "multiscales", "multiscale", "datasets", "dataset", "coordinatetransformations",
    "scale", "translation", "identity", "omero", "rdefs", "window", "start", "end", "min", "max",
    "color", "active", "inverted", "coefficient", "family", "linear", "label", "labels", "image",
    "images", "model", "greyscale", "grayscale", "defaultt", "defaultz", "version", "name", "path",
    "type", "metadata", "method", "mean", "gaussian", "nearest", "local_mean", "localmean", "downscale",
    "bioformats2raw", "layout", "plate", "well", "wells", "fields", "field", "ngffimage",
    # Zarr v2 / v3 metadata
    "zarr", "zarray", "zattrs", "zgroup", "zarrjson", "array", "group", "nodetype", "node_type",
    "zarrformat", "shape", "datatype", "data_type", "dtype", "chunks", "chunk", "chunkgrid", "regular",
    "rectilinear", "chunkshape", "chunkkeyencoding", "default", "v2", "v3", "separator", "fillvalue",
    "codecs", "codec", "configuration", "dimensionnames", "dimensionseparator", "storagetransformers",
    "attributes", "compressor", "filters", "order", "nan", "infinity", "inf", "consolidated",
    "consolidatedmetadata", "kind", "inline", "id", "level", "levels",
    # codecs and their settings
    "bytes", "endian", "little", "big", "zstd", "blosc", "gzip", "zlib", "lz4", "lz4hc", "lzma", "bz2",
    "crc32c", "crc32", "adler32", "fletcher32", "shardingindexed", "sharding_indexed", "sharding",
    "transpose", "vlenutf8", "vlenbytes", "shuffle", "noshuffle", "bitshuffle", "cname", "clevel",
    "typesize", "blocksize", "checksum", "indexcodecs", "indexlocation", "numcodecs", "delta", "quantize",
    "fixedscaleoffset", "packbits", "categorize", "astype", "zfpy", "jpeg", "png", "jpeg2k", "imagecodecs",
}


def squash(text: str) -> str:
    """text casefolded (NFKD) with everything but letters and digits removed."""
    folded = unicodedata.normalize("NFKD", str(text)).casefold()
    return "".join(ch for ch in folded if ch.isalnum())


FORMAT_VOCAB = frozenset(squash(w) for w in _DTYPES | _UNITS | _FORMAT_WORDS)


def format_vocab(text: str) -> bool:
    """Whether text is format vocabulary (FORMAT_VOCAB), never an identifying term."""
    return squash(text) in FORMAT_VOCAB


def _keep_term(text: str) -> bool:
    return len(text) >= 2 and any(ch.isalnum() for ch in text) and not format_vocab(text)


def collect_terms(obj: Any, terms: set[str] | None = None, _seen: set[int] | None = None) -> set[str]:
    """Every string (and date) value inside obj: pydantic models, dataclasses, dicts, lists, XML-ish
    objects. Enum members are vocabulary, not free text, and are skipped."""
    terms = set() if terms is None else terms
    seen = set() if _seen is None else _seen
    if obj is None or isinstance(obj, (bool, int, float, Enum)):
        return terms
    if isinstance(obj, str):
        text = obj.strip()
        if _keep_term(text):
            terms.add(text)
        return terms
    if isinstance(obj, bytes):
        return collect_terms(obj.decode("utf-8", "replace").strip("\x00"), terms, seen)
    if isinstance(obj, (date, datetime)):
        terms |= date_terms(obj)
        return terms
    if id(obj) in seen:
        return terms
    seen.add(id(obj))
    if isinstance(obj, dict):
        for v in obj.values():
            collect_terms(v, terms, seen)
    elif isinstance(obj, (list, tuple, set, frozenset)):
        for v in obj:
            collect_terms(v, terms, seen)
    elif hasattr(type(obj), "model_fields"):  # pydantic (ome_types)
        for name in type(obj).model_fields:
            collect_terms(getattr(obj, name, None), terms, seen)
        extra = getattr(obj, "__pydantic_extra__", None)
        if extra:
            collect_terms(extra, terms, seen)
    elif hasattr(obj, "__dict__"):
        collect_terms(vars(obj), terms, seen)
    return terms


_ID_RE = re.compile(r"^[A-Za-z]+:\d+(:\d+)*$")  # structural LSIDs such as "Image:0", "Channel:0:1"


def _objective(ome: Any, image: Any) -> Any:
    instruments = list(getattr(ome, "instruments", []) or [])
    wanted = image.objective_settings.id if getattr(image, "objective_settings", None) else None
    ref = image.instrument_ref.id if getattr(image, "instrument_ref", None) else None
    candidates = [i for i in instruments if ref is None or i.id == ref] or instruments
    for inst in candidates:
        for obj in inst.objectives or []:
            if wanted is None or obj.id == wanted:
                return obj
    for inst in candidates:
        if inst.objectives:
            return inst.objectives[0]
    return None


def ome_allowlist(ome: Any, image: int = 0) -> tuple[dict[str, Any], set[str]]:
    """Rebuild the kept facts of one OME image from ``ome_types`` objects.

    Returns ``(fields, terms)``: ``fields`` are ImageInfo keyword arguments (pixel_size,
    pixel_unit, channels, objective_magnification, objective_na, immersion, acquired);
    ``terms`` is every string value in the whole OME document that was not kept.
    """
    terms = {t for t in collect_terms(ome) if not _ID_RE.match(t)}
    images = list(getattr(ome, "images", []) or [])
    if not images:
        return {}, terms
    img = images[image] if image < len(images) else images[0]
    px = img.pixels
    unit: PixelUnit = "um"
    pixel_size: dict[str, float] = {}
    for axis in ("x", "y", "z"):
        value = getattr(px, f"physical_size_{axis}", None)
        if value is not None:
            converted = convert_length(value, getattr(px, f"physical_size_{axis}_unit", "µm"), unit)
            if converted is not None and converted > 0:
                pixel_size[axis] = converted
    channels = []
    for i, ch in enumerate(px.channels or []):
        ex = wavelength_nm(ch.excitation_wavelength, ch.excitation_wavelength_unit)
        em = wavelength_nm(ch.emission_wavelength, ch.emission_wavelength_unit)
        channels.append(ChannelInfo(ex, em, channel_code(ex, i)))
    modes = [ch.acquisition_mode.value for ch in px.channels or [] if isinstance(ch.acquisition_mode, Enum)]
    obj = _objective(ome, img)
    immersion = obj.immersion.value if obj is not None and isinstance(obj.immersion, Enum) else None
    fields: dict[str, Any] = {
        "pixel_size": pixel_size,
        "pixel_unit": unit,
        "channels": channels,
        "objective_magnification": float(obj.nominal_magnification)
        if obj is not None and obj.nominal_magnification is not None else None,
        "objective_na": float(obj.lens_na) if obj is not None and obj.lens_na is not None else None,
        "immersion": immersion,
        "acquisition_mode": modes[0] if modes else None,
        "acquired": img.acquisition_date.date() if img.acquisition_date else None,
    }
    return fields, terms


# --- output metadata: NGFF group attributes and BIDS sidecars, from ImageInfo only ----------------

SPATIAL = ("z", "y", "x")
NGFF_UNITS: dict[str, str] = {"mm": "millimeter", "um": "micrometer", "nm": "nanometer"}
RETARDANCE_KINDS = frozenset({"retardance", "birefringence"})
_PALETTE = ("00FF00", "FF00FF", "00FFFF", "FF0000", "0000FF", "FFFF00")


PIXEL_UNIT_UNKNOWN = "pixel size unit unknown: set it in the plan"


class PixelSizeUnknown(ValueError):
    """A spatial axis has no pixel size: it is never invented (the reviewer sets it in the plan)."""


def pixel_sizes(info: ImageInfo) -> dict[str, float]:
    """The pixel size of every spatial axis of info (in ``info.pixel_unit``). The NGFF scale and the
    sidecar PixelSize both come from here. Raises PixelSizeUnknown when an axis has none, or the
    unit is unknown."""
    if info.pixel_unit not in _UNIT_M:
        raise PixelSizeUnknown(PIXEL_UNIT_UNKNOWN)
    out = {}
    for axis in SPATIAL:
        if axis in info.axes:
            value = info.pixel_size.get(axis)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) \
                    or value <= 0:
                raise PixelSizeUnknown("pixel size unknown: set it in the plan")
            out[axis] = float(value)
    return out


def with_plan_pixel_size(info: ImageInfo, entry: Any) -> ImageInfo:
    """info with the plan entry's pixel size and units (the source's, or the reviewer's), x, y[, z]
    for the image's spatial axes; PixelSizeUnknown when the entry has none or too few values."""
    from dataclasses import replace

    spatial = [a for a in "xyz" if a in info.axes]
    values = getattr(entry, "pixel_size", None)
    units = getattr(entry, "pixel_size_units", None)
    if values is None or units not in _UNIT_M or len(values) != len(spatial):
        raise PixelSizeUnknown("pixel size unknown: set it in the plan")
    out = replace(info, pixel_size={a: float(v) for a, v in zip(spatial, values)}, pixel_unit=units)
    pixel_sizes(out)
    return out


def channel_count(info: ImageInfo) -> int:
    return int(info.shape[info.axes.index("c")]) if "c" in info.axes else 1


def _color(ch: ChannelInfo | None, index: int, count: int) -> str:
    if count == 1:
        return "FFFFFF"
    nm = None
    if ch is not None:
        nm = ch.emission_nm or ((ch.excitation_nm + 30) if ch.excitation_nm else None)
    if nm:
        return "0000FF" if nm < 480 else "00FF00" if nm < 560 else "FF8000" if nm < 610 else "FF0000"
    return _PALETTE[index % len(_PALETTE)]


def _window(windows: Any, index: int) -> dict[str, float]:
    if windows and index < len(windows) and windows[index]:
        w = windows[index]
        return {k: float(w[k]) for k in ("min", "max", "start", "end")}
    return {"min": 0.0, "max": 1.0, "start": 0.0, "end": 1.0}


def omero(info: ImageInfo, windows: Any = None) -> dict:
    """One channel per channel of the image: label ``ch<nm>``/``ch<i>`` (never a source name)."""
    count = channel_count(info)
    channels = []
    for i in range(count):
        ch = info.channels[i] if i < len(info.channels) else None
        label = ch.name_code if ch is not None else f"ch{i}"
        channels.append({"label": label, "color": _color(ch, i, count), "active": True,
                         "coefficient": 1.0, "family": "linear", "inverted": False,
                         "window": _window(windows, i)})
    return {"channels": channels, "rdefs": {"model": "greyscale" if count == 1 else "color"}}


def _axis(name: str, unit: str) -> dict:
    if name in SPATIAL:
        return {"name": name, "type": "space", "unit": NGFF_UNITS[unit]}
    return {"name": name, "type": "channel" if name == "c" else "time"}


def ngff_attrs(info: ImageInfo, version: str, levels: Any = None, windows: Any = None) -> dict:
    """The whole group attributes of an OME-Zarr image, rebuilt from ``info``.

    ``levels``: per pyramid level, the absolute downsampling factor of each spatial axis
    (``[{}, {"x": 2, "y": 2}, ...]``; default one level), stored at paths ``"0"``, ``"1"``, ...
    ``windows``: per channel ``{min, max, start, end}`` (from the coarsest level). There is no
    ``name``, ``metadata`` or ``_creator`` and no OME-XML: nothing from a source or a library default.
    Version ``"0.5"`` nests everything under ``"ome"``; ``"0.4"`` puts it at the top.
    """
    if version not in ("0.5", "0.4"):
        raise ValueError(f"unsupported NGFF version: {version!r}")
    levels = list(levels) if levels else [{}]
    size = pixel_sizes(info)
    datasets = []
    for i, factors in enumerate(levels):
        scale = [size[a] * factors.get(a, 1) if a in size else 1.0 for a in info.axes]
        transforms: list[dict] = [{"type": "scale", "scale": scale}]
        if any(factors.get(a, 1) != 1 for a in size):
            transforms.append({"type": "translation", "translation": [
                (factors.get(a, 1) - 1) * size[a] / 2 if a in size else 0.0 for a in info.axes]})
        datasets.append({"path": str(i), "coordinateTransformations": transforms})
    multiscale: dict[str, Any] = {"axes": [_axis(a, info.pixel_unit) for a in info.axes], "datasets": datasets}
    if version == "0.4":
        return {"multiscales": [{"version": "0.4", **multiscale}], "omero": omero(info, windows)}
    return {"ome": {"version": "0.5", "multiscales": [multiscale], "omero": omero(info, windows)}}


def oct_retardance_kind(contrast: str | None) -> str:
    return contrast if contrast in RETARDANCE_KINDS else "n/a"


def sidecar(info: ImageInfo, entry: Any) -> dict:
    """The BIDS sidecar of a written microscopy image: PixelSize (x, y[, z]) and PixelSizeUnits, the
    objective when known and, for OCT, the custom OCT fields. Numbers and enum values only. The pixel
    size is the plan entry's when it has one, else info's; PixelSizeUnknown when an axis has none."""
    if getattr(entry, "pixel_size", None) is not None:
        info = with_plan_pixel_size(info, entry)
    size = pixel_sizes(info)
    out: dict[str, Any] = {
        "PixelSize": [size[a] for a in ("x", "y", "z") if a in size],
        "PixelSizeUnits": info.pixel_unit,
    }
    if info.objective_magnification:
        out["Magnification"] = float(info.objective_magnification)
    if info.objective_na:
        out["NumericalAperture"] = float(info.objective_na)
    if info.immersion:
        out["Immersion"] = info.immersion
    if getattr(entry, "suffix", None) == "OCT":
        contrast = (getattr(entry, "entities", None) or {}).get("acquisition")
        out["OCTContrast"] = contrast or "n/a"
        out["OCTRetardanceKind"] = oct_retardance_kind(contrast)
        out["OCTOpticAxisConvention"] = "n/a"
    return out
