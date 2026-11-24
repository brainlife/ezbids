"""Channel names: identifier-free names kept, everything else renamed ``<type>_<NNN>`` (Task 5).

The rename map (new -> old in ``work/ephys/channels.json``) is local only; standard 10-20 and sensor
names stay as they are.
"""
from __future__ import annotations

import re

from aimport.ephys.events import holds_term

CHANNEL_NAME_RE = re.compile(r"^[A-Za-z0-9 _.\-+/'()]{1,32}$")


def is_kept(name: str, terms: set[str]) -> bool:
    """True when the name is short, plain and holds no run term."""
    return bool(CHANNEL_NAME_RE.fullmatch(name)) and not holds_term(name, terms)


def _type_label(ch_type: str) -> str:
    t = re.sub(r"[^a-z0-9]+", "_", str(ch_type).lower()).strip("_")
    return t[:20] or "misc"


def rename(ch_names: list[str], ch_types: list[str], terms: set[str]) -> dict[str, str]:
    """old -> new for the channels that must be renamed (only those).

    A new name is ``<type>_<NNN>`` where NNN starts at the channel's 1-based position among the
    channels of its type and moves to the next free number when that name is taken. Deterministic,
    and it never collides (case-insensitively) with any existing name or another new name.
    """
    if len(ch_names) != len(ch_types):
        raise ValueError("ch_names and ch_types differ in length")
    taken = {n.casefold() for n in ch_names}
    position: dict[str, int] = {}
    out: dict[str, str] = {}
    for name, ch_type in zip(ch_names, ch_types):
        t = _type_label(ch_type)
        position[t] = position.get(t, 0) + 1
        if is_kept(name, terms):
            continue
        n = position[t]
        while f"{t}_{n:03d}".casefold() in taken:
            n += 1
        new = f"{t}_{n:03d}"
        taken.add(new.casefold())
        out[name] = new
    return out
