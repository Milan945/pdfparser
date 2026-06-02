"""Per-state configuration for structural processing.

Each state's bills differ in how the line-number gutter is rendered:
  - CA: every operative line is prefixed with a literal " line N " label.
  - KS: every operative line is prefixed with a bare, sequential integer fused
        into the body text at the left margin (e.g. "10" before "50,297").
The gutter field selects the strip strategy in structure.py.
"""
from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class StateProfile:
    name: str
    gutter: str  # "ca_line_label" | "ks_line_numbers"


PROFILES: dict[str, StateProfile] = {
    "CA": StateProfile(name="CA", gutter="ca_line_label"),
    "KS": StateProfile(name="KS", gutter="ks_line_numbers"),
}
