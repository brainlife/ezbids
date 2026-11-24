"""Event labels: the safe-label patterns (kept verbatim); everything else is coded (Task 5).

``code`` gives two maps. The first (normalised original -> label) is identifying and lives only in
``work/ephys/events.json``. The second (code -> code) seeds ``Plan.event_names``, the plan's coded
label list, which the reviewer may rename. Raw annotation text never leaves this module's callers'
local files: not to the LLM, the plan, the API or the output.
"""
from __future__ import annotations

import re
from collections.abc import Iterable
from functools import lru_cache

from aimport.scrub import redact

SAFE_WORDS: tuple[str, ...] = (
    "rest", "eyes open", "eyes closed", "eo", "ec", "start", "stop", "begin", "end", "onset", "offset",
    "stimulus", "response", "target", "standard", "deviant", "novel", "cue", "feedback", "button", "left",
    "right", "correct", "incorrect", "blink", "artifact", "movement", "seizure", "spike", "sleep", "wake",
    "photic", "hyperventilation", "baseline", "trigger", "marker", "task",
)

SAFE_PATTERNS: tuple[re.Pattern, ...] = tuple(
    re.compile(p, re.I | re.A)  # ASCII only: no non-ASCII digits, no case folds such as "ſ" or the Kelvin sign
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


SEPARATORS = re.compile(r"[_.\-/+]+")
_NON_ALNUM = re.compile(r"[\W_]+")


@lru_cache(maxsize=8)
def _squashed_terms(terms: frozenset[str]) -> frozenset[str]:
    return frozenset(q for q in (_NON_ALNUM.sub("", t).casefold() for t in terms) if len(q) >= 3)


def holds_term(text: str, terms: set[str]) -> bool:
    """True when the text holds a run term, also with separators in either written differently.

    Checked: the text itself; the text with ``_ . - / +`` runs as spaces (``Jane_Doe``, ``Jane-Doe-Fp1``);
    and the whole text without separators against each term without separators (``150225`` for
    ``15.02.25``, ``JaneDoe`` for ``Jane Doe``).
    """
    s = str(text)
    if redact(s, terms) != s:
        return True
    spaced = SEPARATORS.sub(" ", s)
    if redact(spaced, terms) != spaced:
        return True
    return _NON_ALNUM.sub("", s).casefold() in _squashed_terms(frozenset(terms))


def _keep(text: str, terms: set[str]) -> bool:
    s = str(text).strip()
    return is_safe(s) and not holds_term(s, terms)


def code(descriptions_by_recording: list[list[str]], terms: set[str]) -> tuple[dict[str, str], dict[str, str]]:
    """Map every description to a safe label (kept as written) or a code ``E001``, ``E002``, ...

    Recordings are taken in the order given (sorted record order), descriptions in onset order; codes
    are numbered by first occurrence across the dataset. Matching is on ``normalise(text)``, so one
    text gets one label everywhere. A key is kept only when every variant of it (texts that normalise
    to it) is a safe label holding no run term; its label is then the stripped variant that is least
    by (casefold, text), so the label never depends on recording order. Anything else is coded.
    Returns (normalised original -> label, code -> code); the first map is identifying (local only),
    the second seeds ``Plan.event_names``.
    """
    variants: dict[str, set[str]] = {}  # insertion order = first occurrence
    for descriptions in descriptions_by_recording:
        for text in descriptions:
            variants.setdefault(normalise(text), set()).add(str(text).strip())
    mapping: dict[str, str] = {}
    codes: dict[str, str] = {}
    for key, texts in variants.items():
        if all(_keep(t, terms) for t in texts):
            mapping[key] = min(texts, key=lambda t: (t.casefold(), t))
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
