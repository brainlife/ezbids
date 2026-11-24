import pytest

from aimport.schema import load_schema


@pytest.fixture(scope="session")
def schema():
    return load_schema()


# --- shared leak-test vocabulary (Tasks 5, 9, 10, 13, 14) ---
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "fixtures"))
from fetch_dcm_qa import NATIVE_IDENTIFIERS  # noqa: E402

# Identifiers planted into the DICOMs by fetch_dcm_qa(plant=True), lowercase.
PLANTED = {"smith", "john", "mrn0042", "19700101", "1970-01-01", "hospital x"}
# Identifiers dcm_qa_xa30 carries itself, lowercase.
NATIVE = {t.lower() for t in NATIVE_IDENTIFIERS}


def tokens(text: str) -> set[str]:
    """The known identifying terms (PLANTED | NATIVE) found in text.

    Matching is by substring on lowercased text, so multi-word phrases ("hospital x") and
    values with punctuation ("12343@hucheng") are caught, which a word split would miss.
    Use as ``assert not PLANTED & tokens(text)`` or ``assert not NATIVE & tokens(text)``.
    """
    low = text.lower()
    return {t for t in PLANTED | NATIVE | EPHYS_PLANTED if t in low}


# Identifiers planted into the ephys recordings (tests/fixtures/ephys_fixtures.py), lowercase: PLANTED plus
# the operator, the free-text annotations, the meas date in every form, and the renamed channel.
# "tapping" is planted only in free text (SNIRF stim name "Jane Doe tapping"); the bids-examples task label
# `tapping` is never used in a leak test.
EPHYS_PLANTED = PLANTED | {
    "jane doe",
    "jdoe",
    "eegtech_jane",
    "dr jane",
    "said hello",
    "2025-02-15",
    "20250215",
    "15.02.25",
    "15-feb-2025",
    "01-jan-1970",
    "smith pilot",
    "smith-fp1",
    "tapping",
}


def ephys_tokens(text: str) -> set[str]:
    """The ephys planted identifiers (EPHYS_PLANTED) found in text; substring match on lowercased text.

    Use ``assert not ephys_tokens(text)`` in ephys leak tests; it avoids clashes with the MRI vocabulary
    (NATIVE) that ``tokens`` also checks.
    """
    low = text.lower()
    return {t for t in EPHYS_PLANTED if t in low}
