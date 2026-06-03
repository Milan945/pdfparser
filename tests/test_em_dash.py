from pathlib import Path

import pytest

from netscan.profiles import PROFILES

_KS = Path("samples/there samples/2025_2026_16_2_2_002206_0_4_1_20250203_0.pdf")
_CA = Path("samples/there samples/2025_2026_5_2_2_000351_0_4_1_20250130_0.pdf")


def test_profile_flags():
    assert PROFILES["KS"].em_dash_to_double_hyphen is True
    assert PROFILES["CA"].em_dash_to_double_hyphen is False


@pytest.mark.skipif(not _KS.exists(), reason="KS sample bill not present")
def test_ks_output_uses_double_hyphen_not_em_dash():
    from netscan.pipeline import convert
    out = convert(str(_KS), "KS")
    assert "—" not in out                 # no em-dashes remain
    assert "agriculture--division" in out  # Doctly's convention


@pytest.mark.skipif(not _CA.exists(), reason="CA sample bill not present")
def test_ca_output_keeps_em_dash():
    from netscan.pipeline import convert
    out = convert(str(_CA), "CA")
    assert "—" in out  # CA keeps the em-dash (matches CA Doctly)
