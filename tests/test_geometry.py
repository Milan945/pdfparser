from netscan.geometry import is_bold_font, is_italic_font


def test_bold_detection():
    assert is_bold_font("ABCDEF+Helvetica-BoldMT") is True
    assert is_bold_font("Arial-Black") is True
    assert is_bold_font("Helvetica") is False


def test_italic_detection():
    assert is_italic_font("Helvetica-Oblique") is True
    assert is_italic_font("Times-Italic") is True
    assert is_italic_font("Helvetica") is False


# Task 7: strike/underline detection via rule-line correlation
from netscan.pdf_backend import Char, RuleLine
from netscan.geometry import line_decoration


def _char():
    # glyph box: top=0, bottom=10 -> height 10, mid at 5, baseline near 10
    return Char(text="x", x0=10, x1=20, top=0, bottom=10, fontname="Helvetica", size=10)


def test_midline_is_strikethrough():
    ch = _char()
    rule = RuleLine(x0=10, x1=20, top=5, bottom=5)  # mid-glyph
    assert line_decoration(ch, [rule]) == "strike"


def test_baseline_is_underline():
    ch = _char()
    rule = RuleLine(x0=10, x1=20, top=10.5, bottom=10.5)  # just below baseline
    assert line_decoration(ch, [rule]) == "underline"


def test_non_overlapping_line_is_ignored():
    ch = _char()
    rule = RuleLine(x0=100, x1=120, top=5, bottom=5)  # different x range
    assert line_decoration(ch, [rule]) is None


def test_no_lines_returns_none():
    assert line_decoration(_char(), []) is None


# Task 8: assemble page into tagged Spans
from netscan.pdf_backend import open_pdf
from netscan.geometry import extract_page_spans
from tests.fixtures.make_fixtures import build_formatted_pdf


def _find(spans, word):
    for s in spans:
        if word in s.text:
            return s
    raise AssertionError(f"{word!r} not found in {[s.text for s in spans]}")


def test_extract_page_spans_tags_fixture(tmp_path):
    pdf = tmp_path / "s.pdf"
    build_formatted_pdf(pdf)
    geo = open_pdf(pdf)[0]
    spans = extract_page_spans(geo)

    assert _find(spans, "PLAIN").bold is False
    assert _find(spans, "PLAIN").struck is False
    assert _find(spans, "BOLDWORD").bold is True
    assert _find(spans, "ITALICWORD").italic is True
    assert _find(spans, "STRUCK").struck is True
    assert _find(spans, "ADDED").underlined is True

    # round-trip: concatenated span text contains every source word
    joined = " ".join(s.text for s in spans)
    for w in ("PLAIN", "BOLDWORD", "ITALICWORD", "STRUCK", "ADDED"):
        assert w in joined


def test_strike_takes_precedence_over_underline_regardless_of_order():
    ch = _char()  # top=0, bottom=10, height 10
    strike = RuleLine(x0=10, x1=20, top=5, bottom=5)      # frac 0.5 -> strike band
    under = RuleLine(x0=10, x1=20, top=10.5, bottom=10.5)  # frac 1.05 -> underline band
    assert line_decoration(ch, [strike, under]) == "strike"
    assert line_decoration(ch, [under, strike]) == "strike"


# Finding #3: mixed-format single line splits into ordered spans
from netscan.pdf_backend import PageGeometry
from netscan.geometry import extract_page_spans as _eps


def _line_char(t, x0, bold=False):
    fn = "Helvetica-Bold" if bold else "Helvetica"
    return Char(text=t, x0=x0, x1=x0 + 6, top=100.0, bottom=110.0, fontname=fn, size=10)


def test_mixed_format_single_line_splits_into_ordered_spans():
    # "AB" plain, "CD" bold, "EF" plain — all on one line
    chars = [
        _line_char("A", 10), _line_char("B", 16),
        _line_char("C", 22, bold=True), _line_char("D", 28, bold=True),
        _line_char("E", 34), _line_char("F", 40),
    ]
    geo = PageGeometry(width=612, height=792, chars=chars, rule_lines=[], image_count=0)
    spans = _eps(geo)
    assert [s.text for s in spans] == ["AB", "CD", "EF"]
    assert [s.bold for s in spans] == [False, True, False]


def test_line_straddling_bucket_boundary_keeps_text_order():
    # One visual line whose glyph tops jitter 4.4/4.6 across the round(top/3.0)
    # bucket boundary (bucket 1 vs 2). Must still read left-to-right "ABCD".
    def c(t, x0, top):
        return Char(text=t, x0=x0, x1=x0 + 6, top=top, bottom=top + 10,
                    fontname="Helvetica", size=10)
    chars = [c("A", 10, 4.4), c("B", 16, 4.6), c("C", 22, 4.4), c("D", 28, 4.6)]
    geo = PageGeometry(width=612, height=792, chars=chars, rule_lines=[], image_count=0)
    spans = extract_page_spans(geo)
    assert "".join(s.text for s in spans) == "ABCD"


def test_zero_width_ligature_keeps_stream_order():
    # Reproduces the real "five" case: a zero-width 'fi' ligature whose x0 lands
    # just RIGHT of the following 'v'. Pure-x0 sort gives "vfie"; the builder must
    # emit "five" by falling back to content-stream order for the sub-1pt overlap.
    def c(t, x0, x1):
        return Char(text=t, x0=x0, x1=x1, top=100.0, bottom=110.0,
                    fontname="Times-Roman", size=10)
    # stream order is correct: f-i(ligature), v, e
    chars = [c("fi", 94.63, 94.63), c("v", 94.56, 100.56), c("e", 106.97, 112.30)]
    geo = PageGeometry(width=612, height=792, chars=chars, rule_lines=[], image_count=0)
    spans = _eps(geo)
    assert "".join(s.text for s in spans) == "five"


def test_x_overlap_ratio_is_public():
    from netscan.geometry import x_overlap_ratio
    ch = Char(text="x", x0=10, x1=20, top=0, bottom=10, fontname="Helvetica", size=10)
    full = RuleLine(x0=10, x1=20, top=5, bottom=5)
    half = RuleLine(x0=15, x1=25, top=5, bottom=5)
    assert x_overlap_ratio(ch, full) == 1.0
    assert x_overlap_ratio(ch, half) == 0.5
