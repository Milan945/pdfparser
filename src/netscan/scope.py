"""Scope italic-as-addition to the operative section of a bill.

By drafting convention the front matter and the enacting clause are set in
italic ("Session of 2025", "Be it enacted by the Legislature..."), but they are
NOT amendments. Only italic in the operative section (after the enacting clause)
marks an addition. This module suppresses the italic flag on preamble spans so
they are not wrongly tagged [A>..<A].

Fail-safe: the caller applies this only to the first page's preamble (where the
enacting clause always sits). If the enacting-clause marker is never matched,
suppression is bounded to that first page and never reaches real operative
additions on later pages.
"""
from __future__ import annotations
import re
import dataclasses

from netscan.types import Span

# The enacting clause marks the start of operative text. CA: "...do enact as
# follows:"; KS and most states: "Be it enacted by the Legislature...".
_ENACTING = re.compile(r"be it enacted|do enact as follows", re.IGNORECASE)


def suppress_preamble_additions(spans: list[Span], started: bool) -> tuple[list[Span], bool]:
    """Clear the italic flag on spans until the enacting clause is seen.

    `started` carries across pages: once True (operative section reached), spans
    pass through unchanged. Returns (spans, started). The span containing the
    enacting clause is itself treated as preamble (italic cleared), and `started`
    flips True for everything after it.
    """
    if started:
        return spans, True
    out: list[Span] = []
    for s in spans:
        if not started:
            if s.italic:
                s = dataclasses.replace(s, italic=False)
            if _ENACTING.search(s.text):
                started = True
        out.append(s)
    return out, started
