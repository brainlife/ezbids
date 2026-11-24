"""Task 7: the agent sees allowlisted image facts for microscopy, and only micr answers are kept."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import numpy as np
import pytest
import tifffile

from aimport.agent import CLASSIFY_SYSTEM, MICR_CLASSIFY_SYSTEM, MICR_SUFFIXES
from aimport.micr import names
from aimport.micr.module import MICR_INDEX_BASE, micr_view
from aimport.pseudonyms import PseudonymKey
from conftest import MICR_PLANTED, tokens
from test_micr_plan import micr, scan
from aimport.ezbids_runner import CoreResult
from aimport.planner import build_plan
from fixtures.micr_fixtures import cmc_tree, planted_ome_tiff

MRI_PROMPT_SHA256 = "5fb7c028deadc1dfd608819d55c048c0ee0ed8b6d247cabffacf19d0d6c55a2f"
FIELDS = {"Dimensions", "PixelSize", "PixelSizeUnits", "ChannelCount", "ExcitationWavelengths",
          "EmissionWavelengths", "ObjectiveMagnification", "ObjectiveNA", "Immersion", "FormatFamily",
          "Levels", "DataType", "Hints"}


class Recorder:
    name = "recorder"

    def __init__(self, reply):
        self.reply, self.users, self.systems = reply, [], []

    def complete(self, system, user, step):
        self.users.append(user)
        self.systems.append(system)
        return self.reply(user) if callable(self.reply) else self.reply


@pytest.fixture
def key(tmp_path):
    k = PseudonymKey.load(tmp_path / "keys", "proj")
    yield k
    k.close()


def plan_with(root, tmp_path, key, schema, client):
    work = tmp_path / "work"
    m, claim = scan(root, work)
    plan = build_plan(CoreResult(), root, key, set(), client, schema, "bids", exclude=claim.roots,
                      extra_terms=frozenset(m.terms(work / "micr")),
                      planners=[lambda: m.plan(work / "micr", key, set(), client, schema, "bids")])
    return plan


def tiff_input(tmp_path, name="H17_250215/stack.ome.tif"):
    root = tmp_path / "in"
    planted_ome_tiff(root / name)
    return root


def reply_for(datatype, suffix, confidence=0.9, entities=None):
    def reply(user):
        series = json.loads(user)["series"]
        return json.dumps([{"series_idx": s["series_idx"], "datatype": datatype, "suffix": suffix,
                            "entities": {} if entities is None else entities, "confidence": confidence, "reason": "r"}
                           for s in series])
    return reply


def test_micr_payload_allowlisted(tmp_path, key, schema):
    root = tmp_path / "in"
    cmc_tree(root)
    planted_ome_tiff(root / "H17_250215" / "stack.ome.tif")
    rec = Recorder(reply_for("micr", "CONF"))
    plan_with(root, tmp_path, key, schema, rec)
    micr_calls = [u for sy, u in zip(rec.systems, rec.users) if sy == MICR_CLASSIFY_SYSTEM]
    assert micr_calls
    payload = micr_calls[0]
    series = json.loads(payload)["series"]
    assert series
    for s in series:
        assert s["description"] == "" and s["protocol"] == ""
        assert s["ezbids_type"].startswith("micr/")
        assert set(s["fields"]) == FIELDS
        assert all(names.is_vocab(t) for t in s["fields"]["Hints"])
    assert not tokens(payload) & MICR_PLANTED
    assert "/" not in payload.replace("micr/", "")
    assert not re.search(r"(?<!\d)(\d{6}|\d{8})(?!\d)", payload)
    stripped = json.dumps([{**s, "fields": {k: v for k, v in s["fields"].items() if k != "FormatFamily"}}
                           for s in series])
    assert not re.search(r"\.[A-Za-z]{2,5}\b", re.sub(r"\d+\.\d+", "", stripped))
    assert "acquired" not in payload and "2025" not in payload


def test_micr_view_unreadable_skipped_and_suffix():
    recs = [{"rel": "a", "family": "tiff", "facts": {}, "info": None},
            {"rel": "b/visor_488", "family": "visor", "facts": {},
             "info": {"axes": "zyx", "shape": [4, 8, 8], "dtype": "uint16", "pixel_size": {"x": 1.0, "y": 1.0},
                      "pixel_unit": "um", "channels": [{"excitation_nm": 488, "emission_nm": None}],
                      "levels": 1, "acquired": "2025-02-15"}}]
    (v,) = micr_view(recs)
    assert v.series_idx == MICR_INDEX_BASE + 1 and v.ezbids_type == "micr/SPIM"
    assert v.fields["Dimensions"] == {"z": 4, "y": 8, "x": 8}
    assert v.fields["ExcitationWavelengths"] == [488] and "acquired" not in json.dumps(v.fields)


def test_free_text_immersion_never_reaches_view():
    info = {"axes": "yx", "shape": [8, 8], "dtype": "uint8", "pixel_size": {"x": 1.0, "y": 1.0},
            "pixel_unit": "um", "channels": [], "levels": 1, "immersion": "Jane Doe oil"}
    (v,) = micr_view([{"rel": "a", "family": "tiff", "facts": {}, "info": info}])
    assert v.fields["Immersion"] is None
    info["immersion"] = "Oil"
    (v,) = micr_view([{"rel": "a", "family": "tiff", "facts": {}, "info": info}])
    assert v.fields["Immersion"] == "Oil"


def test_agent_fills_unknown_suffix(tmp_path, key, schema):
    root = tmp_path / "in"
    (root / "x").mkdir(parents=True)
    tifffile.imwrite(str(root / "x" / "plain.tiff"), np.zeros((16, 16), dtype=np.uint16))
    rec = Recorder(reply_for("micr", "CONF"))
    plan = plan_with(root, tmp_path, key, schema, rec)
    (e,) = micr(plan)
    assert (e.source, e.suffix, e.status) == ("agent", "CONF", "ok") and e.confidence == 0.9
    assert MICR_CLASSIFY_SYSTEM in rec.systems


def test_agent_agreement_and_disagreement(tmp_path, key, schema):
    root = tmp_path / "in"
    (root / "visor_488_Pos0").mkdir(parents=True)
    tifffile.imwrite(str(root / "visor_488_Pos0" / "a.tif"), np.zeros((16, 16), dtype=np.uint16))
    plan = plan_with(root, tmp_path, key, schema, Recorder(reply_for("micr", "SPIM", 0.95)))
    (e,) = micr(plan)
    assert e.source == "heuristic" and e.suffix == "SPIM" and e.confidence >= 0.95 and not e.agent_note
    plan = plan_with(root, tmp_path / "b", key, schema, Recorder(reply_for("micr", "CONF", 0.9)))
    (e,) = micr(plan)
    assert e.suffix == "SPIM" and e.agent_note and e.confidence == 0.5 and e.source == "heuristic"


def test_agent_non_micr_answer_rejected(tmp_path, key, schema):
    root = tmp_path / "in"
    (root / "x").mkdir(parents=True)
    tifffile.imwrite(str(root / "x" / "plain.tiff"), np.zeros((16, 16), dtype=np.uint16))
    plan = plan_with(root, tmp_path, key, schema, Recorder(reply_for("anat", "T1w")))
    (e,) = micr(plan)
    assert e.source == "none" and e.suffix is None and e.exclude


def test_micr_suffixes_match_schema(schema):
    assert len(MICR_SUFFIXES) == 18 and all(schema.is_valid("micr", s) for s in MICR_SUFFIXES)


def test_mri_prompt_unchanged():
    assert hashlib.sha256(CLASSIFY_SYSTEM.encode()).hexdigest() == MRI_PROMPT_SHA256
