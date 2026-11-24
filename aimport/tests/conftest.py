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
# Identifiers planted into the microscopy fixtures (micr_fixtures: OME-XML, TIFF tags, slide
# labels) and the CMC-like folder names (donors H17, Moe, MN27; dates 250215, 20250422), lowercase.
MICR_PLANTED = {"jane doe", "jdoe@example.org", "scope-sn-4711", "2025-02-15", "250215", "20250422",
                "slide 42 smith", "annotation secret", "lab-workstation-7", "h17", "moe", "mn27"}


def tokens(text: str) -> set[str]:
    """The known identifying terms (PLANTED | NATIVE | MICR_PLANTED) found in text.

    Matching is by substring on lowercased text, so multi-word phrases ("hospital x") and
    values with punctuation ("12343@hucheng") are caught, which a word split would miss.
    Use as ``assert not PLANTED & tokens(text)`` or ``assert not NATIVE & tokens(text)``.
    """
    low = text.lower()
    return {t for t in PLANTED | NATIVE | MICR_PLANTED if t in low}
