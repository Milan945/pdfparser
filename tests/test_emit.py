from netscan.types import Span
from netscan.emit import render_markup


def _span(text, struck=False, italic=False):
    return Span(text=text, x0=0, x1=1, top=0, bottom=1,
                bold=False, italic=italic, struck=struck, underlined=False,
                confidence=1.0, source="geometry")


def test_plain_spans_concatenate_untagged():
    spans = [_span("Hello "), _span("world")]
    assert render_markup(spans) == "Hello world"


def test_consecutive_same_decoration_merge_into_one_tag():
    spans = [_span("one ", italic=True), _span("thousand", italic=True)]
    assert render_markup(spans) == "[A>one thousand<A]"


def test_consecutive_struck_merge_into_delete_tag():
    spans = [_span("five ", struck=True), _span("hundred", struck=True)]
    assert render_markup(spans) == "[D>five hundred<D]"


def test_leading_and_trailing_whitespace_sits_outside_tag():
    spans = [_span(" public disclosure ", italic=True)]
    assert render_markup(spans) == " [A>public disclosure<A] "


def test_whitespace_only_decorated_span_is_not_tagged():
    spans = [_span("a", italic=True), _span(" ", italic=True), _span("b")]
    # the lone whitespace italic span must not become an empty [A><A]
    assert render_markup(spans) == "[A>a<A] b"


def test_interleaved_delete_add_do_not_merge():
    spans = [_span("old", struck=True), _span("new", italic=True)]
    assert render_markup(spans) == "[D>old<D][A>new<A]"


def test_normalization_is_applied_to_tag_text():
    spans = [_span("party’s", italic=True)]   # curly apostrophe
    assert render_markup(spans) == "[A>party's<A]"


from pathlib import Path
import pytest
from netscan.pdf_backend import open_pdf
from netscan.geometry import extract_page_spans
from netscan.structure import strip_gutter
from netscan.profiles import PROFILES

_KS = Path("samples/there samples/2025_2026_16_2_2_002206_0_4_1_20250203_0.pdf")


@pytest.mark.skipif(not _KS.exists(), reason="KS sample bill not present")
def test_ks_merge_collapses_tag_count():
    spans = []
    for geo in open_pdf(_KS):
        geo = strip_gutter(geo, PROFILES["KS"])
        spans.extend(extract_page_spans(geo))
    out = render_markup(spans)
    # merged output has far fewer addition tags than the unmerged 234
    assert out.count("[A>") < 150
    # tags must not wrap leading spaces (whitespace stays outside)
    assert "[A> " not in out and "[D> " not in out
    assert " <A]" not in out and " <D]" not in out
