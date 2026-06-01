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
