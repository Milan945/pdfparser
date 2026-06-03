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


# A line whose plain text starts with one of these begins a new paragraph.
_BLOCK_START = re.compile(
    r"""^\s*(
        Sec\.\s |               # Sec. 2.
        Section\s\d |           # Section 1.
        \([a-zA-Z]\)\s* |       # (a) (b) (A)
        \(\d+\)\s* |            # (1) (2)
        AN\ ACT\b |
        Be\ it\ enacted\b |
        HOUSE\ BILL\b | SENATE\ BILL\b |
        By\ Committee\b | By\ Representative\b | By\ Senator\b |
        Requested\ by\b |
        Session\ of\b
    )""",
    re.VERBOSE,
)


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
    return Span(text=" ", x0=prev.x1, x1=prev.x1, top=prev.top, bottom=prev.bottom,
                bold=False, italic=False, struck=False, underlined=False,
                confidence=1.0, source="reflow-join")


def paragraphs(spans: list[Span], profile=None) -> list[list[Span]]:
    """Group spans into paragraphs. A new paragraph starts at the first line and
    at every line whose text matches a block-start marker; other lines append to
    the current paragraph (wrapped-line continuation), joined by a single space
    where one belongs (see _join_space)."""
    paras: list[list[Span]] = []
    for line in lines_of(spans):
        text = _line_text(line)
        if not paras or _BLOCK_START.match(text):
            paras.append(list(line))
        else:
            gap = _join_space(paras[-1], line)
            if gap is not None:
                paras[-1].append(gap)
            paras[-1].extend(line)
    return paras
