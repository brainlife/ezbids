"""Microscopy (BIDS ``micr``) module: constants shared by discovery, reading and writing."""
from __future__ import annotations

import os
from typing import Literal, cast

NgffVersion = Literal["0.5", "0.4"]
NGFF_VERSIONS: tuple[NgffVersion, ...] = ("0.5", "0.4")

# Default OME-Zarr output version. "0.5" (Zarr v3, sharded) per the Task 1 validator ruling:
# @bids/validator 2.4.1 on schema 1.11.2 accepts NGFF 0.5, NGFF 0.4 and metadata-only stores.
DEFAULT_NGFF_VERSION: NgffVersion = "0.5"


def _ngff_version() -> NgffVersion:
    value = os.environ.get("AIMPORT_NGFF_VERSION", DEFAULT_NGFF_VERSION).strip()
    if value not in NGFF_VERSIONS:
        raise ValueError(f"AIMPORT_NGFF_VERSION must be one of {NGFF_VERSIONS}, got {value!r}")
    return cast(NgffVersion, value)


NGFF_VERSION: NgffVersion = _ngff_version()

# Conversion and reading touch at most this many bytes of pixels per block; a whole array is
# never materialised. Readers size their dask chunks to it (tests patch it smaller).
MAX_BLOCK_BYTES = 256 * 2**20

# BIDS micr suffixes (schema 1.11.2): vocabulary, never an identifying term of an input name
MICR_SUFFIXES = ("TEM", "SEM", "uCT", "BF", "DF", "PC", "DIC", "FLUO", "CONF", "PLI", "CARS", "2PE", "MPE",
                 "SR", "NLO", "OCT", "SPIM", "XPCT")
