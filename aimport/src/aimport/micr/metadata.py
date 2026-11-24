"""Microscopy metadata rebuilt from an allowlist.

Nothing in a source's metadata is cleaned field by field: the facts aimport keeps (pixel size,
wavelengths, objective, acquisition date) are read out into a fresh ``ImageInfo``, and every
other string value is dropped and returned as a *term* so later steps can redact it.
"""
from __future__ import annotations

import re
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
    pixel_unit: PixelUnit = "um"
    channels: list[ChannelInfo] = field(default_factory=list)
    objective_magnification: float | None = None
    objective_na: float | None = None
    immersion: str | None = None  # OME Objective Immersion enum value only
    levels: int = 1
    zarr_format: Literal[2, 3] | None = None
    ngff_version: str | None = None
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


def _keep_term(text: str) -> bool:
    return len(text) >= 2 and any(ch.isalnum() for ch in text)


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
        "acquired": img.acquisition_date.date() if img.acquisition_date else None,
    }
    return fields, terms
