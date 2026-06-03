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


def paragraphs(spans: list[Span], profile=None) -> list[list[Span]]:
    """Group spans into paragraphs. A new paragraph starts at the first line and
    at every line whose text matches a block-start marker; other lines append to
    the current paragraph (wrapped-line continuation)."""
    paras: list[list[Span]] = []
    for line in lines_of(spans):
        text = _line_text(line)
        if not paras or _BLOCK_START.match(text):
            paras.append(list(line))
        else:
            paras[-1].extend(line)
    return paras
