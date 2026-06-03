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


PROFILES: dict[str, StateProfile] = {
    "CA": StateProfile(
        name="CA",
        gutter="ca_line_label",
        # "AB 351 — 2 —" or "— 3 — AB 351" (bill id + em-dash + page number,
        # either order). The em-dash is the distinctive, body-safe anchor.
        header_re=r"^\s*(?:AB|SB)?\s*\d*\s*—\s*\d+\s*—\s*(?:AB|SB)?\s*\d*\s*$",
        footer_re=r"^\s*\d{1,4}\s*$",   # lone print/page number, e.g. "99"
    ),
    "KS": StateProfile(name="KS", gutter="ks_line_numbers"),
}
