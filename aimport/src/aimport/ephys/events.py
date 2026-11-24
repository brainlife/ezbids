"""Event labels: the safe-label patterns (kept verbatim); everything else is coded (Task 5).

``code`` gives two maps. The first (normalised original -> label) is identifying and lives only in
``work/ephys/events.json``. The second (code -> code) seeds ``Plan.event_names``, the plan's coded
label list, which the reviewer may rename. Raw annotation text never leaves this module's callers'
local files: not to the LLM, the plan, the API or the output.
"""
from __future__ import annotations

import re
from collections.abc import Iterable

from aimport.scrub import redact

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


CODE_PREFIX = "E"


def normalise(text: str) -> str:
    """The matching key of a description: casefolded, whitespace collapsed and stripped."""
    return " ".join(str(text).split()).casefold()


def _keep(text: str, terms: set[str]) -> bool:
    s = str(text).strip()
    return is_safe(s) and redact(s, terms) == s


def code(descriptions_by_recording: list[list[str]], terms: set[str]) -> tuple[dict[str, str], dict[str, str]]:
    """Map every description to a safe label (kept, stripped) or a code ``E001``, ``E002``, ...

    Recordings are taken in the order given (sorted record order), descriptions in onset order; codes
    are numbered by first occurrence across the dataset. Matching is on ``normalise(text)``, so one
    text gets one label everywhere. A safe label that holds a run term is coded too.
    Returns (normalised original -> label, code -> code); the first map is identifying (local only),
    the second seeds ``Plan.event_names``.
    """
    mapping: dict[str, str] = {}
    codes: dict[str, str] = {}
    for descriptions in descriptions_by_recording:
        for text in descriptions:
            key = normalise(text)
            if key in mapping:
                continue
            if _keep(text, terms):
                mapping[key] = str(text).strip()
            else:
                c = f"{CODE_PREFIX}{len(codes) + 1:03d}"
                mapping[key] = codes[c] = c
    return mapping, codes


def label(text: str, mapping: dict[str, str]) -> str:
    """The label of one description; ValueError (without the text) when it was never coded."""
    try:
        return mapping[normalise(text)]
    except KeyError:
        raise ValueError("an annotation description is not in the event map") from None


def counts(annotations, mapping: dict[str, str]) -> dict[str, int]:
    """label -> number of annotations; ``annotations`` is an mne.Annotations or an iterable of descriptions."""
    descriptions: Iterable = getattr(annotations, "description", annotations)
    out: dict[str, int] = {}
    for text in descriptions:
        lab = label(text, mapping)
        out[lab] = out.get(lab, 0) + 1
    return out
