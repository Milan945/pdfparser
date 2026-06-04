"""Reflow: group spans into lines and lines into paragraphs.

Legislative source PDFs have one physical line per numbered line with no blank
lines; Doctly output groups wrapped lines into blank-line-separated paragraphs.
We reconstruct paragraphs from block-marker lines (section/subsection/front
matter). Tag-merge then runs per paragraph, so a tag never bridges paragraphs.
See docs/superpowers/plans/2026-06-03-pipeline-reflow-cli.md.
"""
from __future__ import annotations
import re

from netscan.types import Span

_SAME_LINE_TOL = 3.0


def lines_of(spans: list[Span]) -> list[list[Span]]:
    """Group spans into physical lines by `top` (within tolerance), each line
    left-to-right, lines top-to-bottom."""
    out: list[list[Span]] = []
    for s in sorted(spans, key=lambda s: (s.top, s.x0)):
        if out and abs(s.top - out[-1][0].top) <= _SAME_LINE_TOL:
            out[-1].append(s)
        else:
            out.append([s])
    for ln in out:
        ln.sort(key=lambda s: s.x0)
    return out


# STRONG markers always start a new paragraph regardless of indentation:
# front-matter lines, section headers, the amended-statute citation line, and the
# revisor/calendar tag.
_STRONG_START = re.compile(
    r"""^\s*(
        Sec\.\s |                       # Sec. 2.
        Section\s\d |                   # Section 1.
        SECTION\s\d |                   # SECTION 2--DEFINITIONS (compact-style header)
        ARTICLE\s |                     # ARTICLE headers
        \d+-[\d,]+[a-zA-Z]*\.\s |       # statute citation line: 65-4101.  8-1016.  25-4119a.
        \d+-\d+\s*$ |                   # revisor/calendar tag on its own line: 2-3
        AN\ ACT\b |
        Be\ it\ enacted\b |
        HOUSE\ BILL\b | SENATE\ BILL\b |
        By\ Committee\b | By\ Representative\b | By\ Senator\b |
        Requested\ by\b |
        Session\ of\b
    )""",
    re.VERBOSE,
)

# ENUMERATORS -- (a) (A) (1), double letters (aa) (pp), lowercase roman numerals
# (i) (ii) (viii). These begin a new paragraph ONLY when the line is indented
# (first-line-indent style): a bare "(5)" sitting at the wrap margin is a
# mid-sentence cross-reference (e.g. "subsection (a)(4) or (a)(5)") that wrapped,
# NOT a new list item. When the document has no measurable indentation (e.g.
# synthetic test spans all at one x0), fall back to treating any enumerator as a
# new paragraph.
_ENUM_START = re.compile(
    r"""^\s*(
        \([a-zA-Z]{1,4}\)\s* |          # (a) (A) (pp) (ii) (viii)
        \(\d+\)\s*                      # (1) (2)
    )""",
    re.VERBOSE,
)

# A line is "indented" (a paragraph start) when its left edge sits at least this
# many points right of the document's continuation margin.
_INDENT_TOL = 6.0


def _line_text(line: list[Span]) -> str:
    return "".join(s.text for s in line)


def _join_space(prev_line: list[Span], next_line: list[Span]) -> Span | None:
    """A synthetic space span to insert between two wrapped lines, or None when
    no space belongs there. No space is added when the previous line already
    ends in whitespace, the next starts with whitespace, or the previous line
    ends with a hyphen (a hyphenated token split across lines, e.g. statute
    number "25-\n4119a" must rejoin as "25-4119a", not "25- 4119a")."""
    if not prev_line or not next_line:
        return None
    prev = prev_line[-1]
    if prev.text.endswith((" ", "-")) or next_line[0].text.startswith(" "):
        return None
    # Adjacent parentheticals split across a wrap are a nested cross-reference,
    # e.g. "(a)(5)" or "21-5413(b)(3)" broken as "...(a)" / "(5)..." -- rejoin
    # with no space so it reads "(a)(5)", not "(a) (5)".
    if prev.text.rstrip().endswith(")") and next_line[0].text.lstrip().startswith("("):
        return None
    return Span(text=" ", x0=prev.x1, x1=prev.x1, top=prev.top, bottom=prev.bottom,
                bold=False, italic=False, struck=False, underlined=False,
                confidence=1.0, source="reflow-join")


def _continuation_margin(lines: list[list[Span]]) -> float | None:
    """The document's wrap margin: the most common left edge (rounded x0) across
    lines. Continuation/wrapped lines sit here; paragraph-start lines are indented
    to the right of it. Returns None when there is no measurable indentation
    (all lines share one x0, e.g. synthetic test spans)."""
    from collections import Counter
    counts: Counter[int] = Counter()
    for line in lines:
        if line:
            counts[round(line[0].x0)] += 1
    if not counts:
        return None
    margin = counts.most_common(1)[0][0]
    # No indentation signal if every line sits at (about) the same x0.
    if all(abs(x - margin) <= _INDENT_TOL for x in counts):
        return None
    return float(margin)


def paragraphs_from_lines(lines: list[list[Span]], profile=None) -> list[list[Span]]:
    """Group pre-computed physical lines into paragraphs.

    A new paragraph starts at the first line, at every STRONG marker line
    (headers, section, statute citation, revisor tag), and at every ENUMERATOR
    line that is indented relative to the wrap margin (first-line-indent style).
    A bare enumerator at the wrap margin is a wrapped mid-sentence cross-reference
    and continues the current paragraph. Other lines append to the current
    paragraph, joined by a single space where one belongs (see _join_space).

    Taking lines (not spans) lets the caller compute `lines_of` per page -- whose
    `top` coordinate resets each page -- then concatenate the lines in page order
    so a paragraph that wraps across a page boundary stays a single paragraph."""
    margin = _continuation_margin(lines)
    paras: list[list[Span]] = []
    for line in lines:
        text = _line_text(line)
        starts = not paras or bool(_STRONG_START.match(text))
        if not starts and _ENUM_START.match(text):
            if margin is None:
                starts = True                       # no indent signal: trust regex
            elif line and line[0].x0 >= margin + _INDENT_TOL:
                starts = True                       # indented enumerator = new item
        if starts:
            paras.append(list(line))
        else:
            gap = _join_space(paras[-1], line)
            if gap is not None:
                paras[-1].append(gap)
            paras[-1].extend(line)
    return paras


def paragraphs(spans: list[Span], profile=None) -> list[list[Span]]:
    """Group spans into paragraphs (single-page convenience: groups into lines
    then paragraphs). For multi-page documents, compute `lines_of` per page and
    feed the concatenated lines to `paragraphs_from_lines` so paragraphs join
    across page breaks."""
    return paragraphs_from_lines(lines_of(spans), profile)
