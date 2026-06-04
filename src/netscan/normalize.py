"""Unicode normalization of extracted bill text to Doctly's plain forms.

Pure string transform applied per span at emit time, after gutter stripping
and before markup tags are added. Covers the safe, high-frequency quirks
measured on real bills (curly quotes, fraction slash, zero-width chars, NBSP).

Deliberately excludes ligature recovery (the extraction yields no U+FB00-FB04
codepoints to map), small-caps uppercasing (font-aware), and dash changes
(Doctly keeps en/em dashes). See docs/superpowers/plans/2026-06-02-text-normalization.md.
"""
from __future__ import annotations

# Curly quotes -> ASCII. Single (incl. low-9 and high-reversed) -> ' ; double -> "
_QUOTES = {
    0x2018: "'", 0x2019: "'", 0x201A: "'", 0x201B: "'",
    0x201C: '"', 0x201D: '"', 0x201E: '"', 0x201F: '"',
}
# Zero-width characters to delete entirely.
_ZERO_WIDTH = {0x200B, 0x200C, 0x200D, 0xFEFF}

_FRACTION_SLASH = 0x2044

# Unicode space separators (category Zs) that Doctly flattens to a plain ASCII
# space. Legislative PDFs use U+2003 (EM SPACE) heavily for the indent after an
# enumerator, e.g. "(a) text"; left as-is it differs from Doctly's "(a) text"
# on every enumerated line. NBSP (U+00A0) is included here too.
_SPACES = frozenset({
    0x00A0,                                  # no-break space
    0x1680,                                  # ogham space mark
    0x2000, 0x2001, 0x2002, 0x2003, 0x2004,  # en/em quad, en/em/three-per-em space
    0x2005, 0x2006, 0x2007, 0x2008, 0x2009,  # four/six-per-em, figure, punct, thin
    0x200A,                                  # hair space
    0x202F,                                  # narrow no-break space
    0x205F,                                  # medium mathematical space
    0x3000,                                  # ideographic space
})


def normalize_unicode(text: str) -> str:
    """Return text with curly quotes, fraction slash, Unicode space separators,
    and zero-width characters normalized to their plain ASCII forms. All other
    characters (including en/em dashes) are left unchanged."""
    out: list[str] = []
    for ch in text:
        code = ord(ch)
        if code in _ZERO_WIDTH:
            continue
        if code in _QUOTES:
            out.append(_QUOTES[code])
        elif code == _FRACTION_SLASH:
            out.append("/")
        elif code in _SPACES:
            out.append(" ")
        else:
            out.append(ch)
    return "".join(out)
