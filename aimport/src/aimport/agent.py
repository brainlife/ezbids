"""The LLM agent: classifies series ezBIDS could not place and drafts dataset metadata.

Privacy: the only data a model sees is the JSON object ``{"series": [...]}`` built from
``ScrubbedSeries`` fields plus ezBIDS's own guess. The system prompts hold no data. Any text a
model returns that is kept goes back through ``redact`` with the run's terms.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any, Protocol

from .schema import EPHYS_DATATYPES, PHASE1_DATATYPES, Schema
from .scrub import ScrubbedSeries, redact

DEFAULT_MODEL = "claude-opus-5-5"
_LABEL = re.compile(r"[A-Za-z0-9]+")
# The schema names entities in full; models tend to answer with the filename abbreviations.
_ENTITY_ALIAS = {"acq": "acquisition", "dir": "direction", "rec": "reconstruction", "ce": "ceagent",
                 "sub": "subject", "ses": "session"}

CLASSIFY_SYSTEM = f"""You classify MRI/PET series for a BIDS (Brain Imaging Data Structure) dataset.

The user message is a JSON object {{"series": [...]}}. Each series has: series_idx, description,
protocol, ezbids_type, fields (acquisition parameters) and ezbids_guess (what the ezBIDS
heuristics decided: datatype, suffix, entities; null when it had no guess). Confirm or dispute
each guess from the description and parameters. Text shown as [x] was redacted; ignore it.

Answer every series with a BIDS datatype and suffix, and fill the entities that apply, such as
task, acquisition, direction, run, echo. Rules:
- Name entities as the BIDS schema does, in full (acquisition, direction, reconstruction), not the
  filename abbreviations (acq, dir, rec).
- datatype must be one of: {", ".join(PHASE1_DATATYPES)}.
- Use only suffixes and entities the BIDS specification allows for that datatype.
- Entity values are short alphanumeric labels only (letters and digits, no spaces or symbols).
- Give every entity BIDS requires for the suffix (for example func/bold requires task).
- If you cannot tell what a series is, answer datatype null and suffix null with low confidence.
- confidence is a number from 0 to 1.

Reply with ONLY a JSON array, no prose, one object per series:
[{{"series_idx": 0, "datatype": "anat", "suffix": "T1w", "entities": {{}}, "confidence": 0.9,
"reason": "one short sentence"}}]"""

MICR_SUFFIXES = ("TEM", "SEM", "uCT", "BF", "DF", "PC", "DIC", "FLUO", "CONF", "PLI", "CARS", "2PE", "MPE",
                 "SR", "NLO", "OCT", "SPIM", "XPCT")
MICR_ENTITIES = ("acquisition", "stain")
MICR_GENERATED = frozenset({"sample", "chunk", "run"})

MICR_CLASSIFY_SYSTEM = f"""You classify microscopy images for a BIDS (Brain Imaging Data Structure) dataset.

The user message is a JSON object {{"series": [...]}}. Each series has: series_idx, description,
protocol, ezbids_type, fields (image facts) and ezbids_guess (what the heuristics decided:
datatype, suffix, entities; null when there was no guess). The description and protocol are empty
on purpose. fields holds only Dimensions (axis sizes), PixelSize, PixelSizeUnits, ChannelCount,
ExcitationWavelengths, EmissionWavelengths, ObjectiveMagnification, ObjectiveNA, Immersion,
FormatFamily, Levels, DataType and Hints (generic words from the file layout). Confirm or dispute
each guess from those facts.

Answer every series with datatype micr and a suffix, and fill the entities that apply. Rules:
- datatype is always micr.
- suffix must be one of: {", ".join(MICR_SUFFIXES)}.
- entities may only be: {", ".join(MICR_ENTITIES)}. Do not answer sample, chunk or run: aimport assigns them.
- Entity values are short alphanumeric labels only (letters and digits, no spaces or symbols).
- If you cannot tell the technique, answer datatype null and suffix null with low confidence.
- confidence is a number from 0 to 1.

Reply with ONLY a JSON array, no prose, one object per series:
[{{"series_idx": 0, "datatype": "micr", "suffix": "CONF", "entities": {{}},
"confidence": 0.9, "reason": "one short sentence"}}]"""

EPHYS_ENTITIES = ("task", "acq", "run")
EPHYS_GENERATED = frozenset({"run"})

EPHYS_CLASSIFY_SYSTEM = f"""You classify electrophysiology and optical recordings for a BIDS (Brain Imaging Data Structure) dataset.

The user message is a JSON object {{"series": [...]}}. Each series has: series_idx, description,
protocol, ezbids_type, fields (recording facts) and ezbids_guess (what the heuristics decided:
datatype, suffix, entities; null when there was no guess). The description and protocol are empty
on purpose. fields holds only FormatFamily, SystemFamily, SamplingFrequency, ChannelCount,
ChannelTypes (a histogram), DurationSeconds, EventCounts (coded event labels such as E001 and how
often each occurs), LineFrequency, HasDigitization, Wavelengths and Hints (generic words from the
file layout). Confirm or dispute each guess from those facts.

Answer every series with a BIDS datatype and a suffix, and fill the entities that apply. Rules:
- datatype must be one of: {", ".join(EPHYS_DATATYPES)}.
- suffix equals the datatype (eeg for eeg, meg for meg, ieeg for ieeg, nirs for nirs, emg for emg).
- entities may only be: {", ".join(EPHYS_ENTITIES)}. Do not answer run: aimport assigns it.
- task must be a lowercase alphanumeric word chosen from Hints, or unknown.
- acq is a short alphanumeric label only when Hints support it.
- If you cannot tell what a recording is, answer datatype null and suffix null with low confidence.
- confidence is a number from 0 to 1.

Reply with ONLY a JSON array, no prose, one object per series:
[{{"series_idx": 0, "datatype": "eeg", "suffix": "eeg", "entities": {{"task": "rest"}},
"confidence": 0.9, "reason": "one short sentence"}}]"""

METADATA_SYSTEM = """You write dataset-level metadata for a BIDS dataset from a list of its acquisitions.

The user message is a JSON object {"series": [...]}. Each series has: series_idx, description,
protocol, ezbids_type, fields (acquisition parameters) and ezbids_guess. Text shown as [x] was
redacted; ignore it.

Write a short descriptive dataset name and a README (plain text or Markdown) describing the
acquisitions: modalities, sequences and counts. Do not invent facts that are not in the data, and
do not mention people, institutions, places or dates.

Reply with ONLY a JSON object: {"name": "...", "readme": "..."}"""


class LLMClient(Protocol):
    name: str

    def complete(self, system: str, user: str, step: str) -> str: ...


class ClaudeClient:
    """Anthropic Messages API (``ANTHROPIC_API_KEY``). The SDK client is built on first use."""

    def __init__(self, model: str = DEFAULT_MODEL, max_tokens: int = 16000, timeout: float = 120.0) -> None:
        self.model, self.name = model, model
        self.max_tokens, self.timeout = max_tokens, timeout
        self._client: Any = None

    def complete(self, system: str, user: str, step: str) -> str:
        if self._client is None:
            import anthropic

            self._client = anthropic.Anthropic(timeout=self.timeout)
        response = self._client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return "".join(b.text for b in response.content if b.type == "text")


class AutobidsifyClient:
    """OpenAI and Qwen backends through autobidsify's own routing (private API, pinned 0.9.9.1)."""

    def __init__(self, model: str) -> None:
        self.model, self.name = model, model

    def complete(self, system: str, user: str, step: str) -> str:
        from autobidsify.llm import _call_llm

        return _call_llm(self.model, system, user, step=step)


def client_from_env() -> LLMClient | None:
    """The client for ``AIMPORT_MODEL`` (default claude-opus-5-5), or None if its key is absent."""
    model = os.environ.get("AIMPORT_MODEL", DEFAULT_MODEL)
    low = model.lower()
    if low.startswith("claude"):
        return ClaudeClient(model) if os.environ.get("ANTHROPIC_API_KEY") else None
    if low.startswith(("gpt", "o1", "o3")):
        return AutobidsifyClient(model) if os.environ.get("OPENAI_API_KEY") else None
    if low.startswith("qwen"):
        if os.environ.get("OLLAMA_BASE_URL") or os.environ.get("DASHSCOPE_API_KEY"):
            return AutobidsifyClient(model)
    return None


@dataclass
class Guess:
    series_idx: int
    datatype: str | None
    suffix: str | None
    entities: dict[str, str]
    confidence: float
    reason: str


@dataclass
class DatasetDraft:
    name: str
    readme: str


def _payload(series: list[ScrubbedSeries], heuristic: dict[int, tuple[str, str, dict]] | None) -> str:
    items = []
    for s in series:
        item: dict[str, Any] = {
            "series_idx": s.series_idx,
            "description": s.description,
            "protocol": s.protocol,
            "ezbids_type": s.ezbids_type,
            "fields": s.fields,
        }
        if heuristic is not None:
            g = heuristic.get(s.series_idx)
            item["ezbids_guess"] = (
                {"datatype": g[0], "suffix": g[1], "entities": g[2]} if g else None
            )
        items.append(item)
    return json.dumps({"series": items}, default=str)


def _extract(text: str, opener: str, kind: type) -> Any:
    """The first JSON value of ``kind`` in ``text``, tolerating prose and code fences around it."""
    decoder = json.JSONDecoder()
    pos = text.find(opener)
    while pos != -1:
        try:
            value, _ = decoder.raw_decode(text, pos)
        except json.JSONDecodeError:
            value = None
        else:
            if isinstance(value, kind):
                return value
        pos = text.find(opener, pos + 1)
    raise json.JSONDecodeError("no JSON found in model reply", text, 0)


def _entity_value(v: Any) -> str | None:
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        v = str(v)
    return v if isinstance(v, str) and _LABEL.fullmatch(v) else None


def _checked(answer: dict, schema: Schema,
             datatypes: tuple[str, ...] = PHASE1_DATATYPES,
             generated: frozenset[str] = frozenset()) -> tuple[str, str, dict[str, str]] | None:
    datatype, suffix, raw = answer.get("datatype"), answer.get("suffix"), answer.get("entities") or {}
    if datatype not in datatypes or not isinstance(suffix, str) or not isinstance(raw, dict):
        return None
    if not schema.is_valid(datatype, suffix):
        return None
    entities = {}
    for k, v in raw.items():
        value = _entity_value(v)
        if value is None:
            return None
        entities[_ENTITY_ALIAS.get(str(k), str(k))] = value
    if not set(entities) <= set(schema.allowed_entities(datatype, suffix)):
        return None
    if not set(schema.required_entities(datatype, suffix)) - generated <= set(entities):
        return None
    return datatype, suffix, entities


def _confidence(v: Any) -> float:
    try:
        return min(1.0, max(0.0, float(v)))
    except (TypeError, ValueError):
        return 0.0


def classify(series: list[ScrubbedSeries], heuristic: dict[int, tuple[str, str, dict]],
             client: LLMClient | None, schema: Schema, system: str = CLASSIFY_SYSTEM,
             datatypes: tuple[str, ...] = PHASE1_DATATYPES,
             generated: frozenset[str] = frozenset()) -> list[Guess]:
    def all_with(reason: str) -> list[Guess]:
        return [Guess(s.series_idx, None, None, {}, 0.0, reason) for s in series]

    if client is None:
        return all_with("no model configured")
    try:
        reply = client.complete(system, _payload(series, heuristic), "classify")
        answers = _extract(reply, "[", list)
    except Exception as exc:  # any backend or parse failure degrades to "no guess"
        return all_with(f"model error: {type(exc).__name__}")

    by_idx: dict[int, dict] = {}
    for a in answers:
        if isinstance(a, dict) and isinstance(a.get("series_idx"), int):
            by_idx.setdefault(a["series_idx"], a)
    out = []
    for s in series:
        a = by_idx.get(s.series_idx)
        if a is None:
            out.append(Guess(s.series_idx, None, None, {}, 0.0, "no answer"))
            continue
        if a.get("datatype") is None and a.get("suffix") is None:
            reason = a.get("reason")
            out.append(Guess(s.series_idx, None, None, {}, _confidence(a.get("confidence")),
                             reason if isinstance(reason, str) else "agent could not tell"))
            continue
        ok = _checked(a, schema, datatypes, generated)
        if ok is None:
            out.append(Guess(s.series_idx, None, None, {}, 0.0, "agent answer not valid BIDS"))
        else:
            reason = a.get("reason")
            out.append(Guess(s.series_idx, ok[0], ok[1], ok[2], _confidence(a.get("confidence")),
                             reason if isinstance(reason, str) else ""))
    return out


def draft_metadata(series: list[ScrubbedSeries], client: LLMClient | None,
                   terms: set[str]) -> DatasetDraft | None:
    """A dataset name and README from the acquisitions, redacted with the run's terms."""
    if client is None:
        return None
    try:
        reply = client.complete(METADATA_SYSTEM, _payload(series, None), "metadata")
        data = _extract(reply, "{", dict)
        name, readme = data.get("name"), data.get("readme")
        if not isinstance(name, str) or not isinstance(readme, str) or not name.strip():
            return None
    except Exception:
        return None
    return DatasetDraft(redact(name.strip(), terms), redact(readme, terms))
