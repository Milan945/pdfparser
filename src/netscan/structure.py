"""Structural processing: strip per-state line-number gutters from geometry.

Operates on PageGeometry.chars BEFORE span extraction, so the rest of the
pipeline (extract_page_spans, detect_conflicts) is unaffected. See
docs/superpowers/plans/2026-06-02-gutter-stripping.md.
"""
from __future__ import annotations
import re
from dataclasses import replace

from netscan.geometry import SAME_LINE_TOL, is_small_caps_font
from netscan.pdf_backend import Char, PageGeometry
from netscan.profiles import StateProfile


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
    lines = line_clusters(chars)
    texts = ["".join(c.text for c in line) for line in lines]
    # numbering starts at the first line whose leading digit-run is exactly "1"
    # (the literal line number 1); a run like "10" or "1,000" must NOT anchor.
    start = None
    for i, t in enumerate(texts):
        lead = re.match(r"\d+", t)
        if lead and lead.group() == "1":
            start = i
            break
    if start is None:
        return list(chars)
    keep: list[Char] = []
    counter = 1
    for i, line in enumerate(lines):
        if i < start:
            keep.extend(line)
            continue
        prefix = str(counter)
        if texts[i].startswith(prefix):
            keep.extend(line[len(prefix):])
            counter += 1
        else:
            keep.extend(line)
    return keep


def strip_gutter(geo: PageGeometry, profile: StateProfile) -> PageGeometry:
    """Return a copy of geo with the line-number gutter chars removed."""
    if profile.gutter == "ca_line_label":
        kept = _strip_ca(geo.chars)
    elif profile.gutter == "ks_line_numbers":
        kept = _strip_ks(geo.chars)
    else:
        kept = list(geo.chars)
    return replace(geo, chars=kept)


# Running header/footer margin bands (pts). A line is a header candidate only if
# it sits within HEADER_BAND of the page top, a footer candidate only if within
# FOOTER_BAND of the page bottom. Bands are tight enough to exclude body text
# (CA body starts ~68pt from top and ends well above the ~612pt footer line).
HEADER_BAND = 60.0
FOOTER_BAND = 185.0


def strip_running_headers(geo: PageGeometry, profile: StateProfile) -> PageGeometry:
    """Return a copy of geo with running header/footer lines removed.

    A line is dropped only if it BOTH sits in the top/bottom margin band AND its
    text matches the profile's header_re/footer_re. The pattern gate keeps body
    text that happens to be near a margin. No-op when the profile has no patterns.
    """
    if not profile.header_re and not profile.footer_re:
        return geo
    header = re.compile(profile.header_re) if profile.header_re else None
    footer = re.compile(profile.footer_re) if profile.footer_re else None
    bottom_edge = geo.height - FOOTER_BAND
    kept: list[Char] = []
    for line in line_clusters(geo.chars):
        top = line[0].top
        text = "".join(c.text for c in line)
        if header and top < HEADER_BAND and header.match(text):
            continue
        if footer and top > bottom_edge and footer.match(text):
            continue
        kept.extend(line)
    return replace(geo, chars=kept)


_FRACTION_SLASH = "⁄"


def align_fraction_digits(geo: PageGeometry) -> PageGeometry:
    """Snap the numerator/denominator digits of a staggered fraction onto the
    fraction slash's line.

    A fraction like "2/3" is typeset as a raised numerator, a full-height
    fraction slash (U+2044), and a lowered denominator. The denominator's `top`
    can fall outside SAME_LINE_TOL, so line clustering would banish it to another
    line (producing "2/" here and a stray "3" elsewhere). Re-stamping the digits
    immediately adjacent to a slash with the slash's vertical extent keeps the
    fraction intact. Only chars flanking a U+2044 are touched."""
    chars = list(geo.chars)
    if not any(c.text == _FRACTION_SLASH for c in chars):
        return geo
    for i, c in enumerate(chars):
        if c.text != _FRACTION_SLASH:
            continue
        if i > 0 and chars[i - 1].text.isdigit():
            chars[i - 1] = replace(chars[i - 1], top=c.top, bottom=c.bottom)
        if i + 1 < len(chars) and chars[i + 1].text.isdigit():
            chars[i + 1] = replace(chars[i + 1], top=c.top, bottom=c.bottom)
    return replace(geo, chars=chars)


def uppercase_small_caps(geo: PageGeometry) -> PageGeometry:
    """Uppercase the text of chars set in a small-caps font.

    Small-caps fonts render lowercase letters as small capitals; the source's
    visual form (and Doctly's output) is uppercase, but extraction yields the
    lowercase code points. Uppercasing those chars restores the visual form.
    No-op for documents without small-caps fonts (e.g. KS bills use Times)."""
    if not any(is_small_caps_font(c.fontname) for c in geo.chars):
        return geo
    chars = [replace(c, text=c.text.upper()) if is_small_caps_font(c.fontname) else c
             for c in geo.chars]
    return replace(geo, chars=chars)
