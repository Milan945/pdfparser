"""Stage 2: deterministic geometry extraction.

Bold/italic come from font names (pdfplumber exposes no clean style bit).
Strikethrough/underline come from correlating horizontal rule lines against
glyph boxes (added in Task 7). Thresholds here are CALIBRATED by the Task 9
real-bill spike; the defaults below are the starting point.
"""
from typing import Optional

from netscan.pdf_backend import Char, PageGeometry, RuleLine
from netscan.types import Span

_BOLD_TOKENS = ("bold", "black", "heavy")
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


def x_overlap_ratio(ch: Char, rule: RuleLine) -> float:
    overlap = min(ch.x1, rule.x1) - max(ch.x0, rule.x0)
    width = ch.x1 - ch.x0
    if width <= 0:
        return 0.0
    return max(0.0, overlap) / width


def line_decoration(ch: Char, rules: list[RuleLine]) -> Optional[str]:
    """Return 'strike', 'underline', or None for the glyph given nearby rules.

    Strike takes precedence over underline regardless of rule order.
    """
    height = ch.bottom - ch.top
    if height <= 0:
        return None
    has_strike = False
    has_underline = False
    for rule in rules:
        if x_overlap_ratio(ch, rule) < MIN_X_OVERLAP_RATIO:
            continue
        frac = (rule.y_mid - ch.top) / height
        if STRIKE_BAND[0] <= frac <= STRIKE_BAND[1]:
            has_strike = True
        elif UNDERLINE_BAND[0] <= frac <= UNDERLINE_BAND[1]:
            has_underline = True
    if has_strike:
        return "strike"
    if has_underline:
        return "underline"
    return None


SAME_LINE_TOL = 3.0  # pts; chars whose tops differ by less are on one line
X_ORDER_QUANTUM = 1.0  # pts; within a line, x0 is bucketed to this granularity
#                        so sub-quantum overlaps (zero-width ligature glyphs whose
#                        x0 collapses onto a neighbor) fall back to content-stream
#                        order instead of scrambling. Normal glyphs are ~6pt apart.


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

    Chars are first clustered into lines by vertical proximity (within
    SAME_LINE_TOL of the line's first char), then each line is ordered by x0
    bucketed to X_ORDER_QUANTUM (ties broken by content-stream order) and
    consecutive same-format chars are merged into one Span. Clustering before
    ordering prevents a line whose tops straddle a bucket boundary from
    scrambling; bucketing x0 prevents a zero-width ligature glyph (whose x0
    collapses onto its neighbor) from reordering with that neighbor.
    """
    stream_index = {id(c): i for i, c in enumerate(geo.chars)}
    ordered = sorted(geo.chars, key=lambda c: (c.top, c.x0))
    lines: list[tuple[float, list[Char]]] = []
    for ch in ordered:
        if lines and abs(ch.top - lines[-1][0]) <= SAME_LINE_TOL:
            lines[-1][1].append(ch)
        else:
            lines.append((ch.top, [ch]))

    def line_order_key(c: Char):
        # Zero-width glyphs (x1 <= x0) -- chiefly ligatures, but also NBSP/zero-
        # width spaces -- report their pen-advance x, which collapses onto the
        # following glyph; bias them one quantum left so they order at their true
        # visual origin. Ties break by content-stream order. The 1pt bias is far
        # smaller than real glyph spacing (~6pt), so only the collapsed neighbour
        # is ever reordered, never a legitimate preceding glyph.
        x = c.x0 - X_ORDER_QUANTUM if c.x1 <= c.x0 else c.x0
        return (round(x / X_ORDER_QUANTUM), stream_index[id(c)])

    spans: list[Span] = []
    for _, line_chars in lines:
        cur: Span | None = None
        cur_fmt: tuple | None = None
        for ch in sorted(line_chars, key=line_order_key):
            fmt = _char_format(ch, geo.rule_lines)
            if cur is not None and fmt == cur_fmt:
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
    return spans
