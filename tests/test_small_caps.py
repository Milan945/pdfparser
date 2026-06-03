from pathlib import Path

import pytest

from netscan.geometry import is_small_caps_font
from netscan.pdf_backend import Char, PageGeometry
from netscan.structure import uppercase_small_caps


def test_is_small_caps_font_detects_pc_and_sc_suffix():
    assert is_small_caps_font("GFEDCB+MinionPC") is True
    assert is_small_caps_font("ABCDEF+FooSC") is True
    assert is_small_caps_font("MinionPro-SmallCaps") is True


def test_is_small_caps_font_rejects_regular_fonts():
    assert is_small_caps_font("Times-Roman") is False
    assert is_small_caps_font("Times-Bold") is False
    assert is_small_caps_font("GFEDCB+Minion") is False


def _char(text, font):
    return Char(text=text, x0=0, x1=4, top=0, bottom=10, fontname=font, size=10)


def test_uppercase_small_caps_uppercases_only_small_caps_chars():
    chars = [_char("a", "X+MinionPC"), _char("b", "Times-Roman")]
    out = uppercase_small_caps(PageGeometry(width=600, height=800, chars=chars,
                                            rule_lines=[], image_count=0))
    assert [c.text for c in out.chars] == ["A", "b"]


def test_uppercase_small_caps_noop_without_small_caps():
    chars = [_char("a", "Times-Roman")]
    geo = PageGeometry(width=600, height=800, chars=chars, rule_lines=[], image_count=0)
    out = uppercase_small_caps(geo)
    assert out is geo


_CA = Path("samples/there samples/2025_2026_5_2_2_000351_0_4_1_20250130_0.pdf")


@pytest.mark.skipif(not _CA.exists(), reason="CA sample bill not present")
def test_real_ca_header_is_uppercased():
    from netscan.pipeline import convert
    out = convert(str(_CA), "CA")
    assert "CALIFORNIA LEGISLATURE" in out
    assert "california legislature" not in out
