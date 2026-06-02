from netscan.profiles import PROFILES, StateProfile
from netscan.pdf_backend import Char
from netscan.structure import line_clusters


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
