"""Emit stage: render extracted Spans into NetScan bracket markup.

Turns a list[Span] into the markup string Doctly produces:
  struck  -> [D>..<D]   (deletion)
  italic  -> [A>..<A]   (addition)
  neither -> plain text
Consecutive spans of the same decoration are merged into a single tag. Whitespace
handling matches Doctly's actual convention (confirmed against the KS2206/CA351
Doctly references and the 1-4 gold files):
  - DELETIONS keep their LEADING whitespace INSIDE the tag ("of[D> the<D]"),
    because the struck run in the PDF geometry includes the space before the
    deleted word; trailing whitespace stays outside.
  - ADDITIONS hug the word: leading AND trailing whitespace stay OUTSIDE
    (" [A>a<A] ").
  - Abutting tags are NOT separated by a synthetic space; any space between a
    deletion and the following addition comes from the addition's (stripped)
    leading space, so "machine[D>;<D][A>,<A]" stays abutting while
    "of[D> the<D] [A>a<A]" gets its space from " a".
Text is Unicode-normalized en route.

Reflow/paragraph structure is NOT applied here (it is applied by reflow.py,
which feeds one paragraph's spans at a time); this returns one continuous
string. See docs/superpowers/plans/2026-06-03-emit-tag-merge.md.
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
    """Render spans into bracket markup.

    - consecutive same-decoration spans merge into one tag;
    - two same-decoration runs separated only by whitespace also merge, pulling
      that whitespace INSIDE the tag (so a wrapped phrase like "(a) through (d)"
      is a single addition, not two);
    - DELETIONS keep leading whitespace inside the tag, trailing outside;
    - ADDITIONS keep both leading and trailing whitespace outside the tag;
    - abutting end/start tags are left abutting (no synthetic space).
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
    # 3. render each run with the per-decoration whitespace convention
    out: list[str] = []
    for deco, text in runs:
        if deco == "":
            out.append(text)
            continue
        if not text.strip():             # whitespace-only -> never an empty tag
            out.append(text)
            continue
        open_tag, close_tag = _TAGS[deco]
        trail = text[len(text.rstrip()):]
        if deco == "D":
            # deletions keep their leading whitespace inside the tag (the struck
            # run includes the space before the deleted word); trailing outside.
            body = text[: len(text.rstrip())] if trail else text
            out.append(f"{open_tag}{body}{close_tag}{trail}")
        else:
            # additions hug the word: both boundaries' whitespace stay outside.
            core = text.strip()
            lead = text[: len(text) - len(text.lstrip())]
            out.append(f"{lead}{open_tag}{core}{close_tag}{trail}")
    return "".join(out)
