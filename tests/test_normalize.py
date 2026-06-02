# tests/test_normalize.py
from netscan.normalize import normalize_unicode


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
