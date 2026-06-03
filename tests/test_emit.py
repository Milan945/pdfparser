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
