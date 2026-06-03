"""Tests for emit whitespace-absorb / inter-tag spacing and reflow join spaces."""
from netscan.types import Span
from netscan.emit import render_markup
from netscan.reflow import paragraphs


def _s(text, struck=False, italic=False, top=0.0, x0=0.0):
    return Span(text=text, x0=x0, x1=x0 + max(1, len(text)), top=top, bottom=top + 10,
                bold=False, italic=italic, struck=struck, underlined=False,
                confidence=1.0, source="t")


def test_same_decoration_separated_by_space_merges_into_one_tag():
    # "(a) through" + " " + "(d)" all additions -> single [A>(a) through (d)<A]
    spans = [_s("(a) through", italic=True), _s(" "), _s("(d)", italic=True)]
    assert render_markup(spans) == "[A>(a) through (d)<A]"


def test_adjacent_delete_then_add_tags_get_a_space():
    spans = [_s("(c)", struck=True), _s("(d)", italic=True)]
    assert render_markup(spans) == "[D>(c)<D] [A>(d)<A]"


def test_continuous_deletion_across_two_spans_with_inner_space_stays_one_tag():
    # struck "standards and" + plain " " + struck "conduct" -> one deletion
    spans = [_s("standards and", struck=True), _s(" "), _s("conduct", struck=True)]
    assert render_markup(spans) == "[D>standards and conduct<D]"


def test_wrapped_lines_get_a_join_space():
    # two lines that are continuation (no block marker on the 2nd)
    spans = [_s("Requested by Representative Waggoner", top=100),
             _s("more text", top=112)]
    paras = paragraphs(spans)
    text = "".join(s.text for s in paras[0])
    assert "Waggoner more text" in text


def test_hyphenated_token_across_lines_does_not_get_a_space():
    # "25-" at line end must rejoin "4119a" with no space (de-hyphenation)
    spans = [_s("K.S.A. 25-", top=100), _s("4119a is amended", top=112)]
    paras = paragraphs(spans)
    text = "".join(s.text for s in paras[0])
    assert "25-4119a" in text
    assert "25- 4119a" not in text


def test_trailing_space_line_does_not_double_space():
    spans = [_s("ends with space ", top=100), _s("next", top=112)]
    paras = paragraphs(spans)
    text = "".join(s.text for s in paras[0])
    assert "ends with space next" in text
    assert "space  next" not in text
