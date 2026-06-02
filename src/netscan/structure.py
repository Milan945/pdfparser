"""Structural processing: strip per-state line-number gutters from geometry.

Operates on PageGeometry.chars BEFORE span extraction, so the rest of the
pipeline (extract_page_spans, detect_conflicts) is unaffected. See
docs/superpowers/plans/2026-06-02-gutter-stripping.md.
"""
from __future__ import annotations
import re
from dataclasses import replace

from netscan.pdf_backend import Char, PageGeometry
from netscan.profiles import StateProfile

SAME_LINE_TOL = 3.0


def line_clusters(chars: list[Char]) -> list[list[Char]]:
    """Group chars into physical lines by `top` (within SAME_LINE_TOL),
    each line sorted left-to-right by x0, lines ordered top-to-bottom."""
    out: list[list[Char]] = []
    for ch in sorted(chars, key=lambda c: c.top):
        if out and abs(ch.top - out[-1][0].top) <= SAME_LINE_TOL:
            out[-1].append(ch)
        else:
            out.append([ch])
    for line in out:
        line.sort(key=lambda c: c.x0)
    return out


_CA_LABEL = re.compile(r"^\s*line\s+\d+\s+", re.IGNORECASE)


def _strip_ca(chars: list[Char]) -> list[Char]:
    keep: list[Char] = []
    for line in line_clusters(chars):
        text = "".join(c.text for c in line)
        m = _CA_LABEL.match(text)
        keep.extend(line[m.end():] if m else line)
    return keep


def _strip_ks(chars: list[Char]) -> list[Char]:
    return list(chars)


def strip_gutter(geo: PageGeometry, profile: StateProfile) -> PageGeometry:
    """Return a copy of geo with the line-number gutter chars removed."""
    if profile.gutter == "ca_line_label":
        kept = _strip_ca(geo.chars)
    elif profile.gutter == "ks_line_numbers":
        kept = _strip_ks(geo.chars)
    else:
        kept = list(geo.chars)
    return replace(geo, chars=kept)
