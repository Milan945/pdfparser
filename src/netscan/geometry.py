"""Stage 2: deterministic geometry extraction.

Bold/italic come from font names (pdfplumber exposes no clean style bit).
Strikethrough/underline come from correlating horizontal rule lines against
glyph boxes (added in Task 7). Thresholds here are CALIBRATED by the Task 9
real-bill spike; the defaults below are the starting point.
"""
_BOLD_TOKENS = ("bold", "black", "heavy", "semibold", "demibold")
_ITALIC_TOKENS = ("italic", "oblique")


def is_bold_font(fontname: str) -> bool:
    name = fontname.lower()
    return any(tok in name for tok in _BOLD_TOKENS)


def is_italic_font(fontname: str) -> bool:
    name = fontname.lower()
    return any(tok in name for tok in _ITALIC_TOKENS)


# Task 7: strike/underline detection via rule-line correlation
from typing import Optional

from netscan.pdf_backend import Char, RuleLine

# bands as fractions of glyph height, measured from `top`
STRIKE_BAND = (0.30, 0.70)     # mid-glyph
UNDERLINE_BAND = (0.85, 1.30)  # at/just below baseline
MIN_X_OVERLAP_RATIO = 0.5      # rule must cover >= half the glyph width


def _x_overlap_ratio(ch: Char, rule: RuleLine) -> float:
    overlap = min(ch.x1, rule.x1) - max(ch.x0, rule.x0)
    width = ch.x1 - ch.x0
    if width <= 0:
        return 0.0
    return max(0.0, overlap) / width


def line_decoration(ch: Char, rules: list[RuleLine]) -> Optional[str]:
    """Return 'strike', 'underline', or None for the glyph given nearby rules."""
    height = ch.bottom - ch.top
    if height <= 0:
        return None
    for rule in rules:
        if _x_overlap_ratio(ch, rule) < MIN_X_OVERLAP_RATIO:
            continue
        frac = (rule.y_mid - ch.top) / height
        if STRIKE_BAND[0] <= frac <= STRIKE_BAND[1]:
            return "strike"
        if UNDERLINE_BAND[0] <= frac <= UNDERLINE_BAND[1]:
            return "underline"
    return None
