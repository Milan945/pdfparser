from netscan.types import Span
from netscan.reflow import lines_of


def _s(text, top, x0=10.0):
    return Span(text=text, x0=x0, x1=x0 + 5, top=top, bottom=top + 10,
                bold=False, italic=False, struck=False, underlined=False,
                confidence=1.0, source="geometry")


def test_lines_of_groups_spans_by_top():
    spans = [_s("a", 100), _s("b", 100.5), _s("c", 130)]
    lines = lines_of(spans)
    assert ["".join(s.text for s in ln) for ln in lines] == ["ab", "c"]
