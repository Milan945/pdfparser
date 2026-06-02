# tests/test_normalize.py
from pathlib import Path
import pytest
from netscan.normalize import normalize_unicode
from netscan.pdf_backend import open_pdf
from netscan.geometry import extract_page_spans
from netscan.structure import strip_gutter
from netscan.profiles import PROFILES

_CA = Path("samples/there samples/2025_2026_5_2_2_000351_0_4_1_20250130_0.pdf")


def test_curly_single_quotes_become_ascii_apostrophe():
    assert normalize_unicode("party’s agent") == "party's agent"
    assert normalize_unicode("‘quoted’") == "'quoted'"


def test_curly_double_quotes_become_ascii_quote():
    assert normalize_unicode("“Party”") == '"Party"'


def test_fraction_slash_becomes_ascii_slash():
    assert normalize_unicode("a 2⁄3 vote") == "a 2/3 vote"


def test_nbsp_becomes_normal_space():
    assert normalize_unicode("(a)  The") == "(a)  The"


def test_zero_width_characters_are_removed():
    assert normalize_unicode("no.​The") == "no.The"
    assert normalize_unicode("a‌b‍﻿c") == "abc"


def test_dashes_and_plain_text_are_untouched():
    assert normalize_unicode("2025–26 — session") == "2025–26 — session"
    assert normalize_unicode("plain ascii text") == "plain ascii text"


@pytest.mark.skipif(not _CA.exists(), reason="CA sample bill not present")
def test_ca_real_bill_normalized_text_has_plain_forms():
    parts: list[str] = []
    for geo in open_pdf(_CA):
        geo = strip_gutter(geo, PROFILES["CA"])
        for s in extract_page_spans(geo):
            parts.append(normalize_unicode(s.text))
    text = "".join(parts)
    # plain forms present
    assert "party's agent" in text          # was party’s agent
    assert '"Party"' in text                 # was curly double quotes
    assert "/" in text and "⁄" not in text   # was 2⁄3 vote; numerator is a
    #                                          separate staggered span (reassembly
    #                                          is a later slice), so assert the
    #                                          fraction slash became ASCII '/'
    # quirks gone
    assert "’" not in text and "‘" not in text
    assert "“" not in text and "”" not in text
    assert "⁄" not in text
    assert "​" not in text
    assert " " not in text
