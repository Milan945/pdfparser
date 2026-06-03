from pathlib import Path
import pytest
from netscan.pdf_backend import open_pdf
from netscan.geometry import extract_page_spans
from netscan.structure import strip_gutter
from netscan.profiles import PROFILES

_CA = Path("samples/there samples/2025_2026_5_2_2_000351_0_4_1_20250130_0.pdf")


def _ca_text() -> str:
    parts = []
    for geo in open_pdf(_CA):
        geo = strip_gutter(geo, PROFILES["CA"])
        for s in extract_page_spans(geo):
            parts.append(s.text)
    return "".join(parts)


@pytest.mark.skipif(not _CA.exists(), reason="CA sample bill not present")
def test_five_not_scrambled():
    text = _ca_text()
    assert "five hundred dollars" in text
    assert "vfie" not in text


@pytest.mark.skipif(not _CA.exists(), reason="CA sample bill not present")
def test_officer_not_scrambled():
    text = _ca_text()
    assert "officer" in text
    assert "ofcfier" not in text
