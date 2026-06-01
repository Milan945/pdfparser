"""Stage 2: deterministic geometry extraction.

Bold/italic come from font names (pdfplumber exposes no clean style bit).
Strikethrough/underline come from correlating horizontal rule lines against
glyph boxes (added in Task 7). Thresholds here are CALIBRATED by the Task 9
real-bill spike; the defaults below are the starting point.
"""
from typing import Optional

from netscan.pdf_backend import Char, PageGeometry, RuleLine
from netscan.types import Span

_BOLD_TOKENS = ("bold", "black", "heavy", "semibold", "demibold")
_ITALIC_TOKENS = ("italic", "oblique")


def is_bold_font(fontname: str) -> bool:
    name = fontname.lower()
    return any(tok in name for tok in _BOLD_TOKENS)


def is_italic_font(fontname: str) -> bool:
    name = fontname.lower()
    return any(tok in name for tok in _ITALIC_TOKENS)


# bands as fractions of glyph height, measured from `top`.
# Calibrated against real WA bills (HB 1217): strikethrough rules sit ~0.5 of
# glyph height; underline rules sit ~0.82 (pdfplumber's char box includes
# descender padding, so the visual baseline is ~0.8, not 1.0).
STRIKE_BAND = (0.30, 0.70)     # mid-glyph
UNDERLINE_BAND = (0.72, 1.35)  # at/just below baseline
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


SAME_LINE_TOL = 3.0  # pts; chars whose tops differ by less are on one line


def _char_format(ch: Char, rules: list[RuleLine]) -> tuple[bool, bool, bool, bool]:
    deco = line_decoration(ch, rules)
    return (
        is_bold_font(ch.fontname),
        is_italic_font(ch.fontname),
        deco == "strike",
        deco == "underline",
    )


def extract_page_spans(geo: PageGeometry) -> list[Span]:
    """Assemble chars into Spans in reading order (top-to-bottom, left-to-right).

    Consecutive chars on the same line with identical formatting are merged
    into a single Span.
    """
    # reading order: top-to-bottom, then left-to-right
    chars = sorted(geo.chars, key=lambda c: (round(c.top / SAME_LINE_TOL), c.x0))
    spans: list[Span] = []
    cur: Span | None = None
    cur_fmt: tuple | None = None
    cur_top: float | None = None

    for ch in chars:
        fmt = _char_format(ch, geo.rule_lines)
        same_line = cur_top is not None and abs(ch.top - cur_top) <= SAME_LINE_TOL
        if cur is not None and fmt == cur_fmt and same_line:
            cur.text += ch.text
            cur.x1 = ch.x1
            cur.bottom = max(cur.bottom, ch.bottom)
        else:
            bold, italic, struck, underlined = fmt
            cur = Span(text=ch.text, x0=ch.x0, x1=ch.x1, top=ch.top, bottom=ch.bottom,
                       bold=bold, italic=italic, struck=struck, underlined=underlined,
                       confidence=1.0, source="geometry")
            spans.append(cur)
            cur_fmt = fmt
            cur_top = ch.top
    return spans
