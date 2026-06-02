from pathlib import Path
import pytest
from netscan.profiles import PROFILES, StateProfile
from netscan.pdf_backend import Char, PageGeometry, open_pdf
from netscan.geometry import extract_page_spans
from netscan.structure import line_clusters, strip_gutter

_KS = Path("samples/there samples/2025_2026_16_2_2_002206_0_4_1_20250203_0.pdf")


@pytest.mark.skipif(not _KS.exists(), reason="KS sample bill not present")
def test_ks_gutter_strip_fixes_fused_statute_number():
    page = open_pdf(_KS)[0]
    stripped = strip_gutter(page, PROFILES["KS"])
    text = "".join(s.text for s in extract_page_spans(stripped))
    assert "74-50,297" in text
    assert "74-1050,297" not in text


def _line(text, top, x0=20.0):
    chars, x = [], x0
    for chx in text:
        chars.append(Char(text=chx, x0=x, x1=x + 4, top=top, bottom=top + 10,
                          fontname="Times", size=10.0))
        x += 4
    return chars


def test_ks_strip_removes_sequential_counter_prefix():
    # line numbers 1,2,3 fused at start; body left margin x0=55
    chars = _line("1AN ACT concerning", 186, x0=55.0)
    chars += _line("2governmental ethics", 198, x0=55.0)
    chars += _line("3Kansas public", 209, x0=55.0)
    geo = PageGeometry(width=600, height=800, chars=chars,
                       rule_lines=[], image_count=0)
    out = strip_gutter(geo, PROFILES["KS"])
    text_by_line = ["".join(c.text for c in line)
                    for line in line_clusters(out.chars)]
    assert text_by_line == ["AN ACT concerning",
                            "governmental ethics",
                            "Kansas public"]


def test_ks_strip_strips_only_counter_not_following_digits():
    # line 7 begins with statute number 25-4119a -> "725-4119a"
    chars = _line("1first", 100, x0=55.0)
    chars += _line("2second", 112, x0=55.0)
    chars += _line("3third", 124, x0=55.0)
    chars += _line("4fourth", 136, x0=55.0)
    chars += _line("5fifth", 148, x0=55.0)
    chars += _line("6sixth", 160, x0=55.0)
    chars += _line("725-4119a", 172, x0=55.0)
    geo = PageGeometry(width=600, height=800, chars=chars,
                       rule_lines=[], image_count=0)
    out = strip_gutter(geo, PROFILES["KS"])
    last = "".join(c.text for c in line_clusters(out.chars)[-1])
    assert last == "25-4119a"


def test_ca_strip_removes_line_label_prefix():
    chars = _line(" line 1 SECTION 1. Section 84308", 100)
    chars += _line(" line 2 amended to read:", 112)
    geo = PageGeometry(width=600, height=800, chars=chars,
                       rule_lines=[], image_count=0)
    out = strip_gutter(geo, PROFILES["CA"])
    text_by_line = ["".join(c.text for c in line)
                    for line in line_clusters(out.chars)]
    assert text_by_line == ["SECTION 1. Section 84308", "amended to read:"]


def test_ca_strip_leaves_unlabeled_frontmatter_intact():
    chars = _line("The Political Reform Act of 1974", 100, x0=48.0)
    geo = PageGeometry(width=600, height=800, chars=chars,
                       rule_lines=[], image_count=0)
    out = strip_gutter(geo, PROFILES["CA"])
    assert "".join(c.text for c in out.chars) == "The Political Reform Act of 1974"


def _char(text, x0, top):
    return Char(text=text, x0=x0, x1=x0 + 4, top=top, bottom=top + 10,
                fontname="Times", size=10.0)


def test_line_clusters_groups_by_top_and_sorts_by_x0():
    chars = [_char("b", 50, 100), _char("a", 40, 100.5), _char("c", 30, 130)]
    lines = line_clusters(chars)
    assert [ "".join(ch.text for ch in line) for line in lines ] == ["ab", "c"]


def test_profiles_registry_has_ca_and_ks():
    assert set(PROFILES) >= {"CA", "KS"}
    assert isinstance(PROFILES["CA"], StateProfile)
    assert PROFILES["CA"].gutter == "ca_line_label"
    assert PROFILES["KS"].gutter == "ks_line_numbers"
