"""Emit stage: render extracted Spans into NetScan bracket markup.

Turns a list[Span] into the markup string Doctly produces:
  struck  -> [D>..<D]   (deletion)
  italic  -> [A>..<A]   (addition)
  neither -> plain text
Consecutive spans of the same decoration are merged into a single tag, and
leading/trailing whitespace is kept OUTSIDE the tag so the markup hugs the
words (matching Doctly). Text is Unicode-normalized en route.

Reflow/paragraph structure is NOT applied here (it is applied by reflow.py,
which feeds one paragraph's spans at a time); this returns one continuous
string. See docs/superpowers/plans/2026-06-03-emit-tag-merge.md.
"""
from __future__ import annotations
import re

from netscan.types import Span
from netscan.normalize import normalize_unicode

_TAGS = {"D": ("[D>", "<D]"), "A": ("[A>", "<A]")}
# An end tag immediately followed by a start tag (e.g. a struck enumerator
# directly followed by its italic replacement, "(c)(d)"): Doctly puts a space
# between them.
_ADJACENT_TAGS = re.compile(r"(<[DA]\])(\[[DA]>)")


def _decoration(span: Span) -> str:
    """Return 'D' (struck), 'A' (italic), or '' (plain). Strike wins over italic."""
    if span.struck:
        return "D"
    if span.italic:
        return "A"
    return ""


def render_markup(spans: list[Span]) -> str:
    """Render spans into bracket markup.

    - consecutive same-decoration spans merge into one tag;
    - two same-decoration runs separated only by whitespace also merge, pulling
      that whitespace INSIDE the tag (so a wrapped phrase like "(a) through (d)"
      is a single addition, not two);
    - leading/trailing whitespace of a tagged run stays OUTSIDE the tag;
    - an end tag directly abutting a start tag gets a separating space.
    """
    # 1. merge consecutive same-decoration spans (normalized text)
    runs: list[list[str]] = []   # [decoration, text]
    for span in spans:
        deco = _decoration(span)
        text = normalize_unicode(span.text)
        if runs and runs[-1][0] == deco:
            runs[-1][1] += text
        else:
            runs.append([deco, text])
    # 2. absorb a whitespace-only plain run flanked by the same decoration into
    #    a single tagged run (keeps a wrapped decorated phrase as one tag).
    i = 1
    while i < len(runs) - 1:
        deco, text = runs[i]
        if (deco == "" and text != "" and text.strip() == ""
                and runs[i - 1][0] == runs[i + 1][0] and runs[i - 1][0] != ""):
            runs[i - 1][1] += text + runs[i + 1][1]
            del runs[i:i + 2]
        else:
            i += 1
    # 3. render each run, keeping boundary whitespace outside the tag
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
    # 4. separate directly-abutting end/start tags with a space
    return _ADJACENT_TAGS.sub(r"\1 \2", "".join(out))
