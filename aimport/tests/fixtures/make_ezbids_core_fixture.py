"""Turn a raw ezBIDS_core.json (from unplanted dcm_qa_xa30) into the committed fixture.

    python make_ezbids_core_fixture.py <raw ezBIDS_core.json> <out ezbids_core_siemens.json>

Replaces every identifier with a neutral placeholder, moves acquisition dates to a fixed
fake date (times are kept) and strips the bulky NIfTI header dumps. Fails if any known
identifier is still present, so a changed upstream dataset cannot slip one in.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from fetch_dcm_qa import NATIVE_IDENTIFIERS, PLANTED, SUBJECT_DIR  # noqa: E402

FAKE_DATE = "20000101"
FAKE_DATE_DASHED = "2000-01-01"

PLACEHOLDER = {
    "PatientName": "anon",
    "PatientID": "anon",
    "PatientBirthDate": "00000000",
    "PatientSex": "n/a",
    "PatientAge": "n/a",
    "PatientWeight": "n/a",
    "StudyID": "anon",
    "StudyDescription": "anon",
    "ProcedureStepDescription": "anon",
    "StudyInstanceUID": "anon",
    "SeriesInstanceUID": "anon",
}
DROP = {
    "InstitutionName",
    "InstitutionAddress",
    "InstitutionalDepartmentName",
    "StationName",
    "DeviceSerialNumber",
    "WipMemBlock",  # sequence build stamp with a developer login
    "CMRRMeasurementUUID",
    "headers",  # NIfTI header dumps: bulky, not parsed
}
# phenotype values derived from the patient fields
PHENOTYPE = {"sex": "n/a", "age": "n/a"}


def _scrub_str(value: str) -> str:
    return (
        re.sub(r"2022-?07-?11", lambda m: FAKE_DATE_DASHED if "-" in m.group(0) else FAKE_DATE, value)
    )


def scrub(node, parent_key: str = ""):
    if isinstance(node, dict):
        out = {}
        for k, v in node.items():
            if k in DROP:
                continue
            if k in PLACEHOLDER:
                out[k] = PLACEHOLDER[k]
            elif parent_key == "phenotype" and k in PHENOTYPE:
                out[k] = PHENOTYPE[k]
            else:
                out[k] = scrub(v, k)
        return out
    if isinstance(node, list):
        return [scrub(v, parent_key) for v in node]
    if isinstance(node, str):
        return _scrub_str(node)
    return node


def leftovers(text: str) -> list[str]:
    terms = set(NATIVE_IDENTIFIERS) | set(PLANTED.values()) | {SUBJECT_DIR, "Smith", "MRN"}
    low = text.lower()
    return sorted(t for t in terms if t.lower() in low)


def main(src: Path, dest: Path) -> None:
    text = json.dumps(scrub(json.loads(src.read_text())), indent=1)
    found = leftovers(text)
    if found:
        raise SystemExit(f"identifiers still present: {found}")
    dest.write_text(text)


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
