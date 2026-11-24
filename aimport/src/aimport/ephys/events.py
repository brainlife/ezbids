"""Event labels: the safe-label patterns (kept verbatim); everything else is coded (Task 5)."""
from __future__ import annotations

import re

SAFE_WORDS: tuple[str, ...] = (
    "rest", "eyes open", "eyes closed", "eo", "ec", "start", "stop", "begin", "end", "onset", "offset",
    "stimulus", "response", "target", "standard", "deviant", "novel", "cue", "feedback", "button", "left",
    "right", "correct", "incorrect", "blink", "artifact", "movement", "seizure", "spike", "sleep", "wake",
    "photic", "hyperventilation", "baseline", "trigger", "marker", "task",
)

SAFE_PATTERNS: tuple[re.Pattern, ...] = tuple(
    re.compile(p, re.I)
    for p in (
        r"^\d{1,6}$",
        r"^(Stimulus|Response)/\s*[SR]\s*\d{1,4}$",
        r"^BAD(_[A-Z_]{1,20})?$",
        r"^EDGE$",
        r"^boundary$",
        r"^Sleep stage (W|N1|N2|N3|N4|R|\?)$",
        r"^(DIN|TRSP|STI|STIM|TRIG|TR)\d{0,3}$",
        r"^(" + "|".join(re.escape(w) for w in SAFE_WORDS) + r")([ _-]?\d{1,4})?$",
    )
)


def is_safe(text: str) -> bool:
    """True when the stripped text fully matches one of ``SAFE_PATTERNS`` (case-insensitive)."""
    s = str(text).strip()
    return bool(s) and any(p.fullmatch(s) for p in SAFE_PATTERNS)
