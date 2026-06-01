from netscan.pdf_backend import Char, PageGeometry, RuleLine
from netscan.types import Span
from netscan.conflict import detect_conflicts


def _char(t, x0, top=100.0):
    return Char(text=t, x0=x0, x1=x0 + 6, top=top, bottom=top + 10,
                fontname="Helvetica", size=10)


def _span(text, x0, x1, top=100.0, **kw):
    return Span(text=text, x0=x0, x1=x1, top=top, bottom=top + 10, **kw)


def test_clean_strike_and_underline_are_not_flagged():
    chars = [_char("S", 10), _char("U", 30)]
    strike = RuleLine(x0=10, x1=16, top=105.0, bottom=105.0)   # frac 0.5
    under = RuleLine(x0=30, x1=36, top=108.2, bottom=108.2)    # frac 0.82
    geo = PageGeometry(width=612, height=792, chars=chars,
                       rule_lines=[strike, under], image_count=0)
    spans = [_span("S", 10, 16, struck=True), _span("U", 30, 36, underlined=True)]
    out, conflicts = detect_conflicts(geo, spans)
    assert conflicts == []
    assert all(s.flag_reason is None for s in out)


def test_band_edge_rule_flags_span_and_emits_conflict():
    ch = _char("X", 10)
    rule = RuleLine(x0=10, x1=16, top=107.1, bottom=107.1)     # frac 0.71 -> edge
    geo = PageGeometry(width=612, height=792, chars=[ch],
                       rule_lines=[rule], image_count=0)
    span = _span("X", 10, 16)
    out, conflicts = detect_conflicts(geo, [span])
    assert any(c.kind == "band_edge" for c in conflicts)
    assert out[0].flag_reason is not None and "band_edge" in out[0].flag_reason
    assert out[0].confidence == 0.5


def test_orphan_rule_over_text_emits_conflict():
    ch = _char("Y", 10)
    rule = RuleLine(x0=10, x1=40, top=100.0, bottom=100.0)     # frac 0.0 -> no band
    geo = PageGeometry(width=612, height=792, chars=[ch],
                       rule_lines=[rule], image_count=0)
    out, conflicts = detect_conflicts(geo, [_span("Y", 10, 16)])
    assert any(c.kind == "orphan_rule" for c in conflicts)


def test_page_border_rule_not_overlapping_text_is_ignored():
    ch = _char("Z", 10)
    border = RuleLine(x0=400, x1=590, top=50.0, bottom=50.0)   # no x-overlap with text
    geo = PageGeometry(width=612, height=792, chars=[ch],
                       rule_lines=[border], image_count=0)
    out, conflicts = detect_conflicts(geo, [_span("Z", 10, 16)])
    assert conflicts == []


def test_wide_underline_rule_flags_as_possible_border():
    ch = _char("W", 10)
    wide = RuleLine(x0=10, x1=560, top=108.2, bottom=108.2)    # frac 0.82, ~full width
    geo = PageGeometry(width=612, height=792, chars=[ch],
                       rule_lines=[wide], image_count=0)
    span = _span("W", 10, 16, underlined=True)
    out, conflicts = detect_conflicts(geo, [span])
    assert any(c.kind == "wide_underline" for c in conflicts)
    assert out[0].flag_reason is not None and "wide_underline" in out[0].flag_reason
    assert out[0].underlined is True


def test_full_line_underline_near_page_width_is_not_flagged():
    # Legitimate full-line underlined addition: rule width ~= text run width and
    # near page width. Must NOT be flagged (regression: a page-fraction trigger
    # falsely flagged real full-line insertions on WA HB 1217).
    left = _char("L", 60)                                      # x 60..66
    right = _char("R", 550)                                    # x 550..556
    rule = RuleLine(x0=60, x1=556, top=108.2, bottom=108.2)    # frac 0.82; rw 496 ~= run 496
    geo = PageGeometry(width=612, height=792, chars=[left, right],
                       rule_lines=[rule], image_count=0)
    span = _span("LR", 60, 556, underlined=True)
    out, conflicts = detect_conflicts(geo, [span])
    assert not any(c.kind == "wide_underline" for c in conflicts)
    assert out[0].flag_reason is None


def test_band_edge_fires_even_when_glyph_is_cleanly_classified():
    ch = _char("X", 10)                                    # top 100, h 10
    rule = RuleLine(x0=10, x1=16, top=106.8, bottom=106.8) # frac 0.68: strike-band AND edge
    geo = PageGeometry(width=612, height=792, chars=[ch],
                       rule_lines=[rule], image_count=0)
    out, conflicts = detect_conflicts(geo, [_span("X", 10, 16)])
    assert any(c.kind == "band_edge" for c in conflicts)
    assert out[0].flag_reason is not None and "band_edge" in out[0].flag_reason


def test_narrow_rule_below_min_width_is_not_orphan():
    ch = _char("Y", 10)
    rule = RuleLine(x0=10, x1=15, top=100.0, bottom=100.0)  # frac 0.0 no band; width 5 < 8
    geo = PageGeometry(width=612, height=792, chars=[ch],
                       rule_lines=[rule], image_count=0)
    out, conflicts = detect_conflicts(geo, [_span("Y", 10, 16)])
    assert not any(c.kind == "orphan_rule" for c in conflicts)
