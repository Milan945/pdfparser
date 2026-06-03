"""Per-state configuration for structural processing.

Each state's bills differ in how the line-number gutter is rendered:
  - CA: every operative line is prefixed with a literal " line N " label.
  - KS: every operative line is prefixed with a bare, sequential integer fused
        into the body text at the left margin (e.g. "10" before "50,297").
The gutter field selects the strip strategy in structure.py.

header_re/footer_re are optional regexes: a line in the top/bottom margin band
whose text matches is treated as a running header/footer and dropped. CA pages
carry an alternating running head ("AB 351 — 2 —" / "— 3 — AB 351") and a footer
print number ("99"). States without running heads leave these None (no-op).

em_dash_to_double_hyphen matches Doctly's per-state convention: KS Doctly output
renders the source em-dash (U+2014) as "--" (its gold has zero em-dashes), while
CA Doctly keeps the em-dash. This is a benchmark-parity choice; note the KS
source glyph IS a true em-dash, so "--" follows Doctly rather than the raw glyph.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class StateProfile:
    name: str
    gutter: str  # "ca_line_label" | "ks_line_numbers"
    header_re: Optional[str] = None
    footer_re: Optional[str] = None
    em_dash_to_double_hyphen: bool = False


PROFILES: dict[str, StateProfile] = {
    "CA": StateProfile(
        name="CA",
        gutter="ca_line_label",
        # "AB 351 — 2 —" or "— 3 — AB 351" (bill id + em-dash + page number,
        # either order). The em-dash is the distinctive, body-safe anchor.
        header_re=r"^\s*(?:AB|SB)?\s*\d*\s*—\s*\d+\s*—\s*(?:AB|SB)?\s*\d*\s*$",
        footer_re=r"^\s*\d{1,4}\s*$",   # lone print/page number, e.g. "99"
    ),
    "KS": StateProfile(
        name="KS",
        gutter="ks_line_numbers",
        # Running head on pages 2+: "HB 2206" / "SB 123" + page number, top band.
        header_re=r"^(?:HB|SB)\s+\d+\s*$",
        em_dash_to_double_hyphen=True,
    ),
}
