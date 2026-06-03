from pathlib import Path
import pytest
from netscan.pipeline import convert

_KS = Path("samples/there samples/2025_2026_16_2_2_002206_0_4_1_20250203_0.pdf")


@pytest.mark.skipif(not _KS.exists(), reason="KS sample bill not present")
def test_convert_produces_paragraphed_markup():
    out = convert(str(_KS), "KS")
    assert "\n\n" in out                      # paragraphs are blank-line separated
    assert "[A>" in out and "[D>" in out       # tags present
    assert "[A> " not in out                    # whitespace stays outside tags
    # content is preserved (a known phrase survives)
    assert "public disclosure commission" in out
