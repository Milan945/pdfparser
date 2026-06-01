"""Stage 3: flag the ambiguous residual that geometry can't resolve confidently.

Conflict detection NEVER resolves ambiguity — it only flags spans (via
Span.flag_reason + a lowered confidence) and emits region-level Conflicts for the
QA queue (Stage 7) / VLM adjudication (Stage 4, future). It reuses geometry's
bands and x-overlap helper; it does not import pdfplumber.
"""
from dataclasses import dataclass
from typing import Optional

from netscan.geometry import (
    MIN_X_OVERLAP_RATIO,
    STRIKE_BAND,
    UNDERLINE_BAND,
    x_overlap_ratio,
)
from netscan.pdf_backend import Char, PageGeometry, RuleLine
from netscan.types import Span

BAND_EDGE_RANGE = (0.66, 0.76)      # boundary neighborhood of strike-top/underline-floor
BAND_EDGE_CONFIDENCE = 0.5
WIDE_RULE_CONFIDENCE = 0.5
MIN_ORPHAN_RULE_WIDTH = 8.0         # pts; shorter uninterpreted rules are noise
WIDE_RULE_FACTOR = 1.5              # rule wider than this x its text run -> suspect border
WIDE_RULE_PAGE_FRAC = 0.8           # ...or wider than this x page width
CANDIDATE_FRAC_RANGE = (0.0, 1.4)   # fracs a rule could plausibly be decorating


@dataclass
class Conflict:
    kind: str
    reason: str
    x0: float
    x1: float
    top: float
    bottom: float
    confidence: float


def _frac(ch: Char, rule: RuleLine) -> Optional[float]:
    height = ch.bottom - ch.top
    if height <= 0:
        return None
    return (rule.y_mid - ch.top) / height


def _candidate_glyphs(geo: PageGeometry, rule: RuleLine) -> list[tuple[Char, float]]:
    """Glyphs this rule plausibly decorates: x-overlap >= min and frac in range."""
    lo, hi = CANDIDATE_FRAC_RANGE
    out: list[tuple[Char, float]] = []
    for ch in geo.chars:
        if x_overlap_ratio(ch, rule) < MIN_X_OVERLAP_RATIO:
            continue
        f = _frac(ch, rule)
        if f is None or not (lo <= f <= hi):
            continue
        out.append((ch, f))
    return out


def _flag_span_for_glyph(ch: Char, spans: list[Span], reason: str,
                         confidence: float) -> None:
    """Flag the span that covers this glyph (first reason wins; confidence lowered)."""
    for s in spans:
        if (s.top - 2 <= ch.top <= s.bottom + 2
                and s.x0 - 1 <= ch.x0 and ch.x1 <= s.x1 + 1):
            if s.flag_reason is None:
                s.flag_reason = reason
                s.confidence = min(s.confidence, confidence)
            return


def detect_conflicts(geo: PageGeometry,
                     spans: list[Span]) -> tuple[list[Span], list[Conflict]]:
    conflicts: list[Conflict] = []
    for rule in geo.rule_lines:
        cand = _candidate_glyphs(geo, rule)
        if not cand:
            continue  # page-border / decorative rule with no text under/through it
        glyphs = [ch for ch, _ in cand]
        fracs = [f for _, f in cand]
        rx0 = min(min(ch.x0 for ch in glyphs), rule.x0)
        rx1 = max(max(ch.x1 for ch in glyphs), rule.x1)
        rtop = min(ch.top for ch in glyphs)
        rbot = max(ch.bottom for ch in glyphs)

        has_strike = any(STRIKE_BAND[0] <= f <= STRIKE_BAND[1] for f in fracs)
        has_under = any(UNDERLINE_BAND[0] <= f <= UNDERLINE_BAND[1] for f in fracs)
        in_edge = any(BAND_EDGE_RANGE[0] <= f <= BAND_EDGE_RANGE[1] for f in fracs)

        # 4.1 band-edge: rule frac near the strike/underline boundary
        if in_edge:
            for ch, f in cand:
                if BAND_EDGE_RANGE[0] <= f <= BAND_EDGE_RANGE[1]:
                    _flag_span_for_glyph(
                        ch, spans,
                        f"band_edge: ambiguous strike vs underline (frac={f:.2f})",
                        BAND_EDGE_CONFIDENCE)
            conflicts.append(Conflict(
                "band_edge", "rule sits near the strike/underline boundary",
                rx0, rx1, rtop, rbot, BAND_EDGE_CONFIDENCE))

        # 4.2 orphan rule: over text but matched no band and isn't an edge case
        if not has_strike and not has_under and not in_edge:
            if (rule.x1 - rule.x0) >= MIN_ORPHAN_RULE_WIDTH:
                conflicts.append(Conflict(
                    "orphan_rule",
                    "horizontal rule over text matched no strike/underline band",
                    rx0, rx1, rtop, rbot, 0.5))

        # 4.3 wide underline: likely a table/row border, not a real underline
        if has_under:
            ug = [ch for ch, f in cand
                  if UNDERLINE_BAND[0] <= f <= UNDERLINE_BAND[1]]
            run = max(ch.x1 for ch in ug) - min(ch.x0 for ch in ug)
            rule_w = rule.x1 - rule.x0
            if run > 0 and (rule_w > WIDE_RULE_FACTOR * run
                            or rule_w > WIDE_RULE_PAGE_FRAC * geo.width):
                for ch in ug:
                    _flag_span_for_glyph(
                        ch, spans,
                        "wide_underline: rule may be a table/row border",
                        WIDE_RULE_CONFIDENCE)
                conflicts.append(Conflict(
                    "wide_underline",
                    "underline rule much wider than the text run it covers",
                    rx0, rx1, rtop, rbot, WIDE_RULE_CONFIDENCE))

    return spans, conflicts
