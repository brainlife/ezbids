"""Phase 3 Task 8: the final gate (``ephys/gate.py``) re-reads every written header and sidecar."""
from __future__ import annotations

import json
import shutil
import tracemalloc
import warnings
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pytest

from aimport.ephys import gate
from conftest import EPHYS_PLANTED, ephys_tokens
from fixtures import ephys_fixtures as fx

BIRTHDAY = date(1970, 1, 1)
FORBIDDEN = gate.forbidden_date_forms([fx.MEAS_DATE, BIRTHDAY])
TERMS = set(EPHYS_PLANTED)

# planted builder, the BIDS names it is placed under (source suffix -> output name), the expected field kind
PLANTED = {
    "edf": (fx.planted_edf, {".edf": "sub-01/eeg/sub-01_task-rest_eeg.edf"}, "patient field"),
    "bdf": (fx.planted_bdf, {".bdf": "sub-01/eeg/sub-01_task-rest_eeg.bdf"}, "recording field"),
    "brainvision": (fx.planted_brainvision, {".vhdr": "sub-01/eeg/sub-01_task-rest_eeg.vhdr",
                                             ".vmrk": "sub-01/eeg/sub-01_task-rest_eeg.vmrk",
                                             ".eeg": "sub-01/eeg/sub-01_task-rest_eeg.eeg"}, "header line"),
    "fif": (fx.planted_fif, {".fif": "sub-01/meg/sub-01_task-rest_meg.fif"}, "experimenter"),
    "snirf": (fx.planted_snirf, {".snirf": "sub-01/nirs/sub-01_task-rest_nirs.snirf"}, "metaDataTags"),
    "nwb": (fx.planted_nwb, {".nwb": "sub-01/ieeg/sub-01_task-rest_ieeg.nwb"}, "string dataset"),
}


def _place(src_dir: Path, out: Path, names: dict[str, str]) -> list[Path]:
    files = []
    for p in sorted(src_dir.rglob("*")):
        rel = names.get(p.suffix.lower())
        if p.is_file() and rel:
            dest = out / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(p, dest)
            files.append(dest)
    return files


def _assert_generic(violations: list[str]) -> None:
    for v in violations:
        assert not ephys_tokens(v), v
        assert "Smith" not in v and "MRN" not in v


@pytest.mark.parametrize("fmt", [pytest.param(f, marks=pytest.mark.ephys_data) if f == "fif" else f
                                 for f in PLANTED])
def test_gate_flags_planted(tmp_path, fmt):
    builder, names, kind = PLANTED[fmt]
    builder(tmp_path / "in")
    out = tmp_path / "out"
    files = _place(tmp_path / "in", out, names)
    violations = gate.check(files, out, TERMS, FORBIDDEN, sources=[])
    assert violations
    assert any(v.endswith(f": {kind}") for v in violations), violations
    assert all(v.split(": ")[0] in names.values() for v in violations), violations
    _assert_generic(violations)
    msg = str(gate.GateError(violations))
    assert not ephys_tokens(msg)


def test_gate_flags_planted_detail(tmp_path):
    """The TAL annotation and the .vmrk comment are found on their own, and the .eeg samples are skipped."""
    fx.planted_edf(tmp_path / "in")
    fx.planted_brainvision(tmp_path / "in")
    out = tmp_path / "out"
    files = _place(tmp_path / "in", out, {".edf": "sub-01/eeg/sub-01_task-a_eeg.edf",
                                          ".vmrk": "sub-01/eeg/sub-01_task-b_eeg.vmrk",
                                          ".eeg": "sub-01/eeg/sub-01_task-b_eeg.eeg"})
    v = gate.check(files, out, {"said hello", "dr jane"}, set(), sources=[])
    # the EDF+ fields and the "New Segment" marker also hold full dates from 1925 on, refused as such
    assert v == ["sub-01/eeg/sub-01_task-a_eeg.edf: patient field", "sub-01/eeg/sub-01_task-a_eeg.edf: recording field",
                 "sub-01/eeg/sub-01_task-a_eeg.edf: annotation", "sub-01/eeg/sub-01_task-b_eeg.vmrk: marker date",
                 "sub-01/eeg/sub-01_task-b_eeg.vmrk: marker line"]


def test_gate_separator_variants_and_file_name(tmp_path):
    out = tmp_path / "out"
    (out / "sub-01" / "eeg").mkdir(parents=True)
    side = out / "sub-01" / "eeg" / "sub-01_task-rest_eeg.json"
    side.write_text(json.dumps({"TaskName": "rest", "Notes": ["JaneDoe"]}))
    named = out / "sub-01" / "eeg" / "sub-01_task-JaneDoe_events.tsv"
    named.write_text("onset\tduration\ttrial_type\n1.0\t0\tE001\n")
    v = gate.check([side, named], out, {"Jane Doe"}, set(), sources=[])
    assert v == ["(a file name): file name", "sub-01/eeg/sub-01_task-rest_eeg.json: sidecar value"]


def test_gate_flags_copied_source(tmp_path):
    src = tmp_path / "in" / "Smith_John_rest.eeg"
    src.parent.mkdir()
    data = np.random.default_rng(0).bytes(4096)
    src.write_bytes(data)
    other = tmp_path / "in" / "other.eeg"
    other.write_bytes(data[:-1] + bytes([data[-1] ^ 1]))  # same size, different bytes
    out = tmp_path / "out"
    (out / "sub-01" / "eeg").mkdir(parents=True)
    copied = out / "sub-01" / "eeg" / "sub-01_task-rest_eeg.eeg"
    copied.write_bytes(data)
    fresh = out / "sub-01" / "eeg" / "sub-01_task-b_eeg.eeg"
    fresh.write_bytes(np.random.default_rng(1).bytes(4096))
    v = gate.check([copied, fresh], out, TERMS, FORBIDDEN, sources=[other, src, tmp_path / "missing"])
    assert v == ["sub-01/eeg/sub-01_task-rest_eeg.eeg: copied source bytes"]
    assert gate.check([fresh], out, TERMS, FORBIDDEN, sources=[other]) == []


def _clean_raw(kind: str):
    import mne

    if kind == "meg":
        info = mne.create_info(["MEG0111", "MEG0112", "MEG0113"], fx.SFREQ, "mag")
        scale = 1e-13
    else:
        info = mne.create_info(["Fp1", "Fp2", "Cz"], fx.SFREQ, "eeg")
        scale = 1e-5
    info["line_freq"] = 60.0
    raw = mne.io.RawArray(np.random.default_rng(0).standard_normal((3, fx.N_SAMPLES)) * scale, info, verbose=False)
    raw.set_meas_date(fx.MEAS_DATE)
    raw.set_annotations(mne.Annotations([1.0, 2.0], [0.0, 0.0], ["E001", "eyes closed"]))
    return raw


@pytest.mark.parametrize("fmt", ["BrainVision", "EDF", "BDF", "FIF"])
def test_gate_clean_passes(tmp_path, fmt):
    import mne_bids

    datatype = "meg" if fmt == "FIF" else "eeg"
    root = tmp_path / "bids"
    bp = mne_bids.BIDSPath(subject="01", task="rest", datatype=datatype, root=root)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        mne_bids.write_raw_bids(_clean_raw(datatype), bp, format=fmt, allow_preload=True, overwrite=True,
                                anonymize={"daysback": 40000, "keep_his": False, "keep_source": False},
                                verbose=False)
    files = [p for p in root.rglob("*") if p.is_file()]
    assert len(files) >= 5
    extra: dict[str, int] = {}
    assert gate.check(files, root, TERMS, FORBIDDEN, sources=[], extra_points=extra) == []
    if fmt == "FIF":
        assert extra == {"sub-01/meg/sub-01_task-rest_meg.fif": 0}


def test_gate_shifted_date_only_in_scans(tmp_path):
    out = tmp_path / "out"
    (out / "sub-01" / "eeg").mkdir(parents=True)
    shifted = (fx.MEAS_DATE + timedelta(days=-400)).strftime("%Y-%m-%dT%H:%M:%S")
    scans = out / "sub-01" / "sub-01_scans.tsv"
    scans.write_text(f"filename\tacq_time\neeg/sub-01_task-rest_eeg.edf\t{shifted}\n")
    assert gate.check([scans], out, TERMS, FORBIDDEN, sources=[]) == []

    side = out / "sub-01" / "eeg" / "sub-01_task-rest_eeg.json"
    side.write_text(json.dumps({"TaskName": "rest", "RecordingDate": shifted}))
    assert gate.check([scans, side], out, TERMS, FORBIDDEN, sources=[]) == [
        "sub-01/eeg/sub-01_task-rest_eeg.json: sidecar value"]

    events = out / "sub-01" / "eeg" / "sub-01_task-rest_events.tsv"
    events.write_text(f"onset\tduration\tnote\n1.0\t0\t{shifted}\n")
    assert gate.check([events], out, TERMS, FORBIDDEN, sources=[]) == [
        "sub-01/eeg/sub-01_task-rest_events.tsv: table cell"]

    original = fx.MEAS_DATE.strftime("%Y-%m-%dT%H:%M:%S")
    scans.write_text(f"filename\tacq_time\neeg/sub-01_task-rest_eeg.edf\t{original}\n")
    assert gate.check([scans], out, TERMS, FORBIDDEN, sources=[]) == ["sub-01/sub-01_scans.tsv: table cell"]

    # an anonymized date (before 1925) is allowed anywhere
    side.write_text(json.dumps({"TaskName": "rest", "Note": "1915-08-12"}))
    assert gate.check([side], out, TERMS, FORBIDDEN, sources=[]) == []


def test_gate_edf_anonymized_header_passes(tmp_path):
    """aimport's own EDF values (X X X X, Startdate X X X X, 01.01.85) are never flagged, even when the
    original birthday is 1985-01-01."""
    fx.planted_edf(tmp_path / "in")
    out = tmp_path / "out"
    (edf,) = _place(tmp_path / "in", out, {".edf": "sub-01/eeg/sub-01_task-rest_eeg.edf"})
    raw = bytearray(edf.read_bytes())
    raw[8:88] = b"X X X X".ljust(80)
    raw[88:168] = b"Startdate X X X X".ljust(80)
    raw[168:184] = b"01.01.8500.00.00"
    # rename the planted channel and drop the planted annotation text, keeping the layout
    data = bytes(raw).replace(b"Smith-Fp1", b"eeg_002  ").replace(b"Smith John said hello", b"E001".ljust(21))
    edf.write_bytes(data)
    forbidden = FORBIDDEN | gate.forbidden_date_forms([date(1985, 1, 1)])
    assert gate.check([edf], out, TERMS, forbidden, sources=[]) == []


def test_gate_unknown_file_utf16_and_unreadable(tmp_path):
    out = tmp_path / "out"
    (out / "sub-01").mkdir(parents=True)
    blob = out / "sub-01" / "sub-01_notes.bin"
    blob.write_bytes(b"\x00\x01" * 10 + "Jane Doe".encode("utf-16-le") + b"\x00" * 10)
    broken = out / "sub-01" / "sub-01_task-rest_eeg.json"
    broken.write_text("{not json")
    outside = tmp_path / "elsewhere.json"
    outside.write_text("{}")
    v = gate.check([blob, broken, outside], out, TERMS, FORBIDDEN, sources=[])
    assert v == ["(a file outside the output): location", "sub-01/sub-01_notes.bin: file bytes",
                 "sub-01/sub-01_task-rest_eeg.json: unreadable"]


def test_gate_error_message():
    err = gate.GateError([f"sub-01/eeg/f{i}.json: sidecar value" for i in range(25)])
    assert len(err.violations) == 25
    assert "f19.json" in str(err) and "f20.json" not in str(err) and "5 more" in str(err)


def _sparse_bdf(path: Path, size: int, tweak: bool = False) -> None:
    """A BDF of about ``size`` bytes (2048 Hz EEG + a BDF Annotations signal), sparse on disk."""
    ns, n_eeg, n_ann = 2, 2048, 60
    rec = (n_eeg + n_ann) * 3
    n_rec = (size - 256 * (ns + 1)) // rec
    f = lambda v, w: str(v).ljust(w).encode("latin-1")  # noqa: E731
    head = (b"\xffBIOSEMI" + f("X X X X", 80) + f("Startdate X X X X", 80) + f("01.01.85", 8) + f("00.00.00", 8)
            + f(256 * (ns + 1), 8) + f("BDF+C", 44) + f(n_rec, 8) + f(1, 8) + f(ns, 4))
    sig = b"".join([f("EEG Fp1", 16) + f("BDF Annotations", 16), f("", 80) * 2, f("uV", 8) + f("", 8),
                    f(-8000, 8) + f(-1, 8), f(8000, 8) + f(1, 8), f(-8388608, 8) + f(-8388608, 8),
                    f(8388607, 8) + f(8388607, 8), f("", 80) * 2, f(n_eeg, 8) + f(n_ann, 8), f("", 32) * 2])
    with open(path, "wb") as fh:
        fh.write(head + sig)
        tal = b"+0\x14\x14\x00+0.5\x14\x14eyes closed\x14\x00"
        fh.seek(256 * (ns + 1) + n_eeg * 3)
        fh.write(tal)
        fh.truncate(256 * (ns + 1) + n_rec * rec)
        if tweak:
            fh.seek(256 * (ns + 1) + 10)
            fh.write(b"\x01")


def test_gate_bounded(tmp_path):
    out = tmp_path / "out"
    (out / "sub-01" / "eeg").mkdir(parents=True)
    bdf = out / "sub-01" / "eeg" / "sub-01_task-rest_eeg.bdf"
    _sparse_bdf(bdf, 256 * 2**20)
    src = tmp_path / "source.bdf"
    _sparse_bdf(src, 256 * 2**20, tweak=True)  # same size: hashed, not equal
    assert bdf.stat().st_size == src.stat().st_size > 250 * 2**20
    tracemalloc.start()
    try:
        v = gate.check([bdf], out, TERMS | {"eyes closed"}, FORBIDDEN, sources=[src])
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert v == ["sub-01/eeg/sub-01_task-rest_eeg.bdf: annotation"]
    assert peak < 32 * 2**20, peak
