from netscan.types import Span
from netscan.scope import suppress_preamble_additions


def _s(text, italic=False):
    return Span(text=text, x0=0, x1=1, top=0, bottom=1,
                bold=False, italic=italic, struck=False, underlined=False,
                confidence=1.0, source="geometry")


def test_italic_before_enacting_clause_is_suppressed():
    spans = [_s("Session of 2025", italic=True),
             _s("Be it enacted by the Legislature of the State of Kansas:", italic=True),
             _s(" public disclosure ", italic=True)]
    out, started = suppress_preamble_additions(spans, started=False)
    assert started is True
    # preamble + the enacting clause line itself: italic cleared
    assert out[0].italic is False
    assert out[1].italic is False
    # operative italic after the clause: preserved
    assert out[2].italic is True


def test_ca_enacting_clause_variant_triggers_start():
    spans = [_s("The people of the State of California do enact as follows:", italic=True),
             _s("added text", italic=True)]
    out, started = suppress_preamble_additions(spans, started=False)
    assert started is True
    assert out[0].italic is False
    assert out[1].italic is True


def test_already_started_passes_through_unchanged():
    spans = [_s("operative addition", italic=True)]
    out, started = suppress_preamble_additions(spans, started=True)
    assert started is True
    assert out[0].italic is True


def test_no_marker_suppresses_all_italic_on_this_call():
    # Fail-safe is the CALLER's job (bounding to page 1); within one call with no
    # marker, everything stays preamble. This documents that contract.
    spans = [_s("a", italic=True), _s("b", italic=True)]
    out, started = suppress_preamble_additions(spans, started=False)
    assert started is False
    assert all(s.italic is False for s in out)
