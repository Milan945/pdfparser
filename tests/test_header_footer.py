from pathlib import Path

import pytest

from netscan.pdf_backend import Char, PageGeometry
from netscan.structure import strip_running_headers
from netscan.profiles import PROFILES, StateProfile


def _line(text, top, x0=48.0):
    chars, x = [], x0
    for ch in text:
        chars.append(Char(text=ch, x0=x, x1=x + 4, top=top, bottom=top + 10,
                          fontname="Times", size=10.0))
        x += 4
    return chars


def _geo(chars, height=792.0):
    return PageGeometry(width=612.0, height=height, chars=chars,
                        rule_lines=[], image_count=0)


def test_ca_running_header_in_top_band_is_dropped():
    chars = _line("AB 351 — 2 — ", top=43) + _line("real body text here", top=68)
    out = strip_running_headers(_geo(chars), PROFILES["CA"])
    text = "".join(c.text for c in out.chars)
    assert "AB 351" not in text
    assert "real body text here" in text


def test_ca_reversed_header_dropped():
    chars = _line("— 3 — AB 351 ", top=43) + _line("body", top=68)
    out = strip_running_headers(_geo(chars), PROFILES["CA"])
    assert "AB 351" not in "".join(c.text for c in out.chars)


def test_ca_footer_number_in_bottom_band_is_dropped():
    chars = _line("end of body.", top=600) + _line("99 ", top=612)
    out = strip_running_headers(_geo(chars), PROFILES["CA"])
    text = "".join(c.text for c in out.chars)
    assert "end of body." in text
    assert "99" not in text


def test_header_pattern_not_matched_in_body_band_is_kept():
    # a lone number in the BODY (not the footer band) must survive
    chars = _line("99", top=300)
    out = strip_running_headers(_geo(chars), PROFILES["CA"])
    assert "99" in "".join(c.text for c in out.chars)


def test_profile_without_patterns_is_noop():
    chars = _line("AB 351 — 2 —", top=43)
    geo = _geo(chars)
    bare = StateProfile(name="X", gutter="ks_line_numbers")  # no header/footer res
    out = strip_running_headers(geo, bare)
    assert out is geo  # no patterns: returned unchanged (same object)
    assert "AB 351" in "".join(c.text for c in out.chars)


_CA = Path("samples/there samples/2025_2026_5_2_2_000351_0_4_1_20250130_0.pdf")


@pytest.mark.skipif(not _CA.exists(), reason="CA sample bill not present")
def test_real_ca_pipeline_has_no_header_footer_artifacts():
    from netscan.pipeline import convert
    out = convert(str(_CA), "CA")
    assert "AB 351 —" not in out
    # the footer print-number 99 no longer bleeds into the digest sentence
    assert "in the    99" not in out and "in the 99" not in out


def test_ks_running_header_pattern_dropped():
    chars = _line("HB 2206 ", top=59, x0=78) + _line("body of the bill text", top=88)
    out = strip_running_headers(_geo(chars, height=648.0), PROFILES["KS"])
    text = "".join(c.text for c in out.chars)
    assert "HB 2206" not in text
    assert "body of the bill text" in text


_KS = Path("samples/there samples/2025_2026_16_2_2_002206_0_4_1_20250203_0.pdf")


@pytest.mark.skipif(not _KS.exists(), reason="KS sample bill not present")
def test_real_ks_pipeline_strips_running_header():
    from netscan.pipeline import convert
    out = convert(str(_KS), "KS")
    assert "HB 2206" not in out  # running head removed (title "HOUSE BILL No. 2206" differs)
