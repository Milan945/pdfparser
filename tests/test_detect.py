from pathlib import Path

import pytest

from netscan.detect import detect_state, detect_state_from_text

_CA = Path("samples/there samples/2025_2026_5_2_2_000351_0_4_1_20250130_0.pdf")
_KS = Path("samples/there samples/2025_2026_16_2_2_002206_0_4_1_20250203_0.pdf")


def test_detect_from_text_california():
    assert detect_state_from_text("CALIFORNIA LEGISLATURE 2025-26") == "CA"


def test_detect_from_text_kansas():
    assert detect_state_from_text("Be it enacted by the Legislature of the State of Kansas:") == "KS"


def test_detect_from_text_unknown_returns_none():
    assert detect_state_from_text("a generic document with no state") is None


@pytest.mark.skipif(not _CA.exists(), reason="CA sample bill not present")
def test_detect_real_ca_bill():
    assert detect_state(_CA) == "CA"


@pytest.mark.skipif(not _KS.exists(), reason="KS sample bill not present")
def test_detect_real_ks_bill():
    assert detect_state(_KS) == "KS"
