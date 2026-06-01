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
