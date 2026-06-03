"""Emit stage: render extracted Spans into NetScan bracket markup.

Turns a list[Span] into the markup string Doctly produces:
  struck  -> [D>..<D]   (deletion)
  italic  -> [A>..<A]   (addition)
  neither -> plain text
Consecutive spans of the same decoration are merged into a single tag, and
leading/trailing whitespace is kept OUTSIDE the tag so the markup hugs the
words (matching Doctly). Text is Unicode-normalized en route.

Reflow/paragraph structure is NOT applied here (later slice); this returns one
continuous string. See docs/superpowers/plans/2026-06-03-emit-tag-merge.md.
"""
from __future__ import annotations

from netscan.types import Span
from netscan.normalize import normalize_unicode

_TAGS = {"D": ("[D>", "<D]"), "A": ("[A>", "<A]")}


def _decoration(span: Span) -> str:
    """Return 'D' (struck), 'A' (italic), or '' (plain). Strike wins over italic."""
    if span.struck:
        return "D"
    if span.italic:
        return "A"
    return ""


def render_markup(spans: list[Span]) -> str:
    """Render spans into bracket markup, merging consecutive same-decoration
    runs and keeping whitespace outside tags."""
    # 1. merge consecutive same-decoration spans (normalized text)
    runs: list[list[str]] = []   # [decoration, text]
    for span in spans:
        deco = _decoration(span)
        text = normalize_unicode(span.text)
        if runs and runs[-1][0] == deco:
            runs[-1][1] += text
        else:
            runs.append([deco, text])
    # 2. render each run
    out: list[str] = []
    for deco, text in runs:
        if deco == "":
            out.append(text)
            continue
        core = text.strip()
        if not core:                     # whitespace-only -> never an empty tag
            out.append(text)
            continue
        lead = text[: len(text) - len(text.lstrip())]
        trail = text[len(text.rstrip()):]
        open_tag, close_tag = _TAGS[deco]
        out.append(f"{lead}{open_tag}{core}{close_tag}{trail}")
    return "".join(out)
