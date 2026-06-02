from netscan.profiles import PROFILES, StateProfile
from netscan.pdf_backend import Char, PageGeometry
from netscan.structure import line_clusters, strip_gutter


def _line(text, top, x0=20.0):
    chars, x = [], x0
    for chx in text:
        chars.append(Char(text=chx, x0=x, x1=x + 4, top=top, bottom=top + 10,
                          fontname="Times", size=10.0))
        x += 4
    return chars


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
