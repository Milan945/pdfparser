# Stage 3 — Conflict Detection — Design Spec

**Date:** 2026-06-02
**Status:** Approved (brainstorm), pending spec review
**Depends on:** Phase 1 geometry foundation (`pdf_backend`, `triage`, `geometry`, `Span`).
**Parent spec:** `docs/superpowers/specs/2026-06-01-netscan-markup-converter-design.md` (Stage 3).
**Gate inputs:** `docs/superpowers/spikes/2026-06-01-rule-line-gate.md` (follow-ups #2, #3, #4).

## 1. Purpose

Geometry (Stage 2) tags most spans deterministically and confidently. Stage 3
identifies the **ambiguous residual** — spans/regions geometry cannot resolve with
confidence — and records that ambiguity on the data so it can later be routed to the
VLM (Job A) or, in the current phase, to the human QA queue (Stage 7). Conflict
detection never *resolves* ambiguity; it only *flags* it. This keeps the
"every span the VLM never sees can't be hallucinated" principle intact: only the
flagged minority needs a second look.

## 2. Data model

- **`Span.flag_reason: Optional[str] = None`** — new field on the existing core type.
  `None` = unflagged. When set, the span is ambiguous; its `confidence` is also lowered
  (the numeric channel Stage 5/7 already consume). No other `Span` change.
- **`Conflict`** — new dataclass for region-level issues not tied to a single span:
  - `kind: str` — one of `"orphan_rule"`, `"wide_underline"`, `"band_edge"` (band_edge
    conflicts annotate a span AND emit a Conflict for traceability).
  - `reason: str` — human-readable explanation for the QA queue.
  - `x0, x1, top, bottom: float` — bounding box of the region (in pdfplumber coords).
  - `confidence: float` — detector's confidence the region IS a real conflict (0–1).

## 3. Module & interface

New module `src/netscan/conflict.py`:

```
detect_conflicts(geo: PageGeometry, spans: list[Span]) -> tuple[list[Span], list[Conflict]]
```

- Mutates/returns the same `spans` (annotating `flag_reason` + lowering `confidence`
  on ambiguous ones), and returns a list of region-level `Conflict`s.
- Pure function of its inputs; no I/O, no model calls. One responsibility: flag ambiguity.

`conflict.py` imports `PageGeometry`/`RuleLine`/`Char` from `pdf_backend` and `Span`
from `types`. It does NOT import pdfplumber (isolation preserved).

## 4. Conflict categories (this phase)

Three categories, all detectable from data already extracted (`chars`, `rule_lines`,
fracs). Tunable constants live at module top, mirroring `geometry.py`'s band constants.

### 4.1 Band-edge ambiguity
A rule overlaps a glyph (x-overlap ≥ `MIN_X_OVERLAP_RATIO`) with a frac in the tight
boundary neighborhood `BAND_EDGE_RANGE = (0.66, 0.76)` — i.e. the dead gap between
strike-top (0.70) and underline-floor (0.72) plus a ~0.05 fringe each side. This fires
**regardless of whether geometry classified the glyph**: a frac in this zone is "near the
strike/underline boundary — verify," whether it landed as strike, underline, or `None`.
Clean strikes (frac ≈ 0.5) and clean underlines (frac ≈ 0.82) fall well outside the zone
and are never flagged. The span covering the glyph gets `flag_reason="band_edge:
ambiguous strike vs underline (frac=X.XX)"`, `confidence` lowered to
`BAND_EDGE_CONFIDENCE = 0.5`, and a `Conflict(kind="band_edge")` is emitted. (On HB 1217,
where strikes cluster at 0.5 and underlines at 0.82, this flags nothing — the real-bill
check in §8 confirms the low false-flag rate.)

### 4.2 Orphan rule lines
A horizontal rule with length ≥ `MIN_ORPHAN_RULE_WIDTH` (pts) that has x-overlap ≥
`MIN_X_OVERLAP_RATIO` with at least one glyph but matches NO band for ANY overlapping
glyph (i.e. produced no strike/underline). Emits `Conflict(kind="orphan_rule")` —
a rule the geometry saw but couldn't interpret must never vanish silently. Page-border
rules (no glyph x-overlap at all) are NOT orphans and are ignored.

### 4.3 Wide "underline" rules (table/row-border false positives)
The gate widened `UNDERLINE_BAND` to `(0.72, 1.35)`, which makes a full-width row/cell
border under text classifiable as underline. Detection: for any rule that produced an
underline classification, if the rule's width exceeds `WIDE_RULE_FACTOR = 1.5 ×` the
total x-extent of the underlined glyph run it covers (or exceeds `WIDE_RULE_PAGE_FRAC =
0.8 ×` page width), flag every span it underlined with `flag_reason="wide_underline:
rule may be a table/row border"`, lower `confidence` to `WIDE_RULE_CONFIDENCE = 0.5`,
and emit `Conflict(kind="wide_underline")`. The underline tag is RETAINED (not removed)
— Stage 3 flags, it does not resolve.

## 5. Bundled fix — span-text scramble (gate follow-up #4)

`geometry.extract_page_spans` currently sorts by `(round(c.top / SAME_LINE_TOL), c.x0)`,
ordering by `x0` only *within* a bucket; a visual line whose glyphs straddle a bucket
boundary scrambles span text. Fix: **cluster chars into lines first** (group by a single
line-key derived from `top`), **then sort each line's chars by `x0`**, and use that same
line-key for the same-line merge test. Behavior for normal single-bucket lines is
unchanged; the straddle case is corrected. This lives in `geometry.py` (not `conflict.py`)
because it is a geometry-assembly correctness fix; conflict detection depends on correct
span text, so it ships in the same plan.

## 6. Out of scope (deferred, with reason)

- **Color-only emphasis** — `Char` carries no color; adding `non_stroking_color`
  extraction is a separate change. Deferred.
- **Multi-column / table reading order** — needs real layout analysis (column
  detection, table cell ordering). Deferred; pairs with future table support. The
  span-scramble fix (§5) handles only the single-column straddle case, NOT multi-column.

## 7. Error handling

- Empty `spans` or empty `rule_lines` → returns `(spans, [])`, no error.
- A rule matching multiple categories emits one `Conflict` per applicable category but
  flags a given span at most once (first reason wins; lowest confidence applied).
- `flag_reason` is additive context for QA — it never changes a span's bold/italic/
  struck/underlined flags. Stage 3 flags; it does not re-classify.

## 8. Testing

Hand-built `PageGeometry` fixtures (no real PDF needed) — one focused test per behavior:
- near-boundary frac (e.g. 0.71) → span flagged `band_edge`, confidence 0.5, one Conflict.
- a clean strike (frac 0.5) and clean underline (frac 0.82) → NOT flagged (no false flags).
- orphan rule over text matching no band → one `orphan_rule` Conflict; page-border rule
  (no glyph overlap) → no Conflict.
- full-page-width rule under a short word → span flagged `wide_underline`, underline flag
  retained, one Conflict.
- §5: a single line whose glyph `top`s straddle a bucket boundary → span text in correct
  left-to-right order.

Plus a real-bill check: re-run `scripts/inspect_bill.py` (extended to print conflicts) on
HB 1217 and confirm the flagged fraction is small and genuine — geometry should still
resolve the vast majority of spans cleanly.

## 9. Success metrics

- Fraction of spans flagged is small (geometry resolves most) — measured on HB 1217.
- Zero rule lines silently dropped (every uninterpreted over-text rule becomes a Conflict).
- Span-scramble regression test passes.
- No false flags on clean strike/underline spans (the synthetic clean-case test).
