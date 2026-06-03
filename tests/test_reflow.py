from netscan.types import Span
from netscan.reflow import lines_of
from netscan.reflow import paragraphs


def _s(text, top, x0=10.0):
    return Span(text=text, x0=x0, x1=x0 + 5, top=top, bottom=top + 10,
                bold=False, italic=False, struck=False, underlined=False,
                confidence=1.0, source="geometry")


def test_lines_of_groups_spans_by_top():
    spans = [_s("a", 100), _s("b", 100.5), _s("c", 130)]
    lines = lines_of(spans)
    assert ["".join(s.text for s in ln) for ln in lines] == ["ab", "c"]


def test_wrapped_lines_join_into_one_paragraph():
    spans = [_s("(a) first part ", 100), _s("continues here", 112)]
    paras = paragraphs(spans)
    assert len(paras) == 1


def test_new_subsection_marker_starts_new_paragraph():
    spans = [_s("(a) alpha ", 100), _s("(b) beta", 112)]
    paras = paragraphs(spans)
    assert len(paras) == 2


def test_section_header_starts_new_paragraph():
    spans = [_s("text of prior para ", 100), _s("Sec. 2. New section", 112)]
    paras = paragraphs(spans)
    assert len(paras) == 2
