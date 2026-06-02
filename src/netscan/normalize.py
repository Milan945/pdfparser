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
_NBSP = 0x00A0


def normalize_unicode(text: str) -> str:
    """Return text with curly quotes, fraction slash, NBSP, and zero-width
    characters normalized to their plain ASCII forms. All other characters
    (including en/em dashes) are left unchanged."""
    out: list[str] = []
    for ch in text:
        code = ord(ch)
        if code in _ZERO_WIDTH:
            continue
        if code in _QUOTES:
            out.append(_QUOTES[code])
        elif code == _FRACTION_SLASH:
            out.append("/")
        elif code == _NBSP:
            out.append(" ")
        else:
            out.append(ch)
    return "".join(out)
