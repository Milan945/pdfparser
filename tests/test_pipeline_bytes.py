from pathlib import Path

import pytest

from netscan.pipeline import convert, convert_bytes

_KS = Path("samples/there samples/2025_2026_16_2_2_002206_0_4_1_20250203_0.pdf")


@pytest.mark.skipif(not _KS.exists(), reason="KS sample bill not present")
def test_convert_bytes_matches_convert_path():
    data = _KS.read_bytes()
    assert convert_bytes(data, "KS") == convert(str(_KS), "KS")
