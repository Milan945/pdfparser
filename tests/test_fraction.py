from pathlib import Path

import pytest

from netscan.pdf_backend import Char, PageGeometry
from netscan.structure import align_fraction_digits
from netscan.geometry import extract_page_spans


def _c(text, x0, top):
    return Char(text=text, x0=x0, x1=x0 + 3, top=top, bottom=top + 12,
                fontname="Times", size=10)


def test_staggered_fraction_digits_snap_to_slash_line():
    # numerator raised, slash full-height, denominator dropped 6pt (out of the
    # 3pt line tolerance), then a space + word on the main line.
    chars = [_c("2", 86, 121), _c("⁄", 89, 120), _c("3", 91, 126),
             _c(" ", 95, 120), _c("v", 99, 120)]
    geo = PageGeometry(width=600, height=800, chars=chars, rule_lines=[], image_count=0)
    out = align_fraction_digits(geo)
    spans = extract_page_spans(out)
    text = "".join(s.text for s in spans)
    assert "2⁄3" in text          # fraction kept contiguous
    assert text.startswith("2⁄3")  # the 3 did not float away


def test_noop_without_fraction_slash():
    chars = [_c("a", 10, 100)]
    geo = PageGeometry(width=600, height=800, chars=chars, rule_lines=[], image_count=0)
    assert align_fraction_digits(geo) is geo


_CA = Path("samples/there samples/2025_2026_5_2_2_000351_0_4_1_20250130_0.pdf")


@pytest.mark.skipif(not _CA.exists(), reason="CA sample bill not present")
def test_real_ca_fraction_reassembled():
    from netscan.pipeline import convert
    out = convert(str(_CA), "CA")
    assert "2/3 vote" in out          # was "2/ vote" with a floating 3
    assert "with 3specified" not in out
    assert "with specified" in out or "compliance with" in out
