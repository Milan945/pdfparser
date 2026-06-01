from netscan.types import Span


def test_span_defaults_are_unformatted():
    s = Span(text="hello", x0=0.0, x1=10.0, top=0.0, bottom=8.0)
    assert s.bold is False
    assert s.italic is False
    assert s.struck is False
    assert s.underlined is False
    assert s.confidence == 1.0
    assert s.source == "geometry"


def test_span_records_formatting_and_source():
    s = Span(text="x", x0=0, x1=1, top=0, bottom=1,
             struck=True, confidence=0.4, source="vlm")
    assert s.struck is True
    assert s.confidence == 0.4
    assert s.source == "vlm"


def test_span_flag_reason_defaults_none_and_settable():
    s = Span(text="x", x0=0, x1=1, top=0, bottom=1)
    assert s.flag_reason is None
    s2 = Span(text="y", x0=0, x1=1, top=0, bottom=1, flag_reason="band_edge: foo")
    assert s2.flag_reason == "band_edge: foo"
