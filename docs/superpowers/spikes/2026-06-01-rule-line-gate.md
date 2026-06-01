# Spike & Gate: Does strike/underline appear as vector rule lines in real bills?

**Date:** 2026-06-01 (validated 2026-06-02)
**Verdict:** ✅ **PASS** — proceed to the conflict/reconcile/emit/verify plan.
**Caveat:** required one calibration (underline band) that is now applied.

## What was tested

Two real Washington State Legislature bill PDFs, downloaded from
`lawfilesext.leg.wa.gov` (public, no auth), inspected with
`scripts/inspect_bill.py` against the geometry path (`pdf_backend` → `triage`
→ `geometry.extract_page_spans`):

- **HB 1100** — short bill, no amendatory redline content.
- **HB 1217** — 20+ pages, substantial amendatory content (strikes deletions of
  existing statute, underlines additions). This is the meaningful sample.

## Findings

### 1. Do strike/underline appear as `lines`/`rects`?
**Yes.** They appear in pdfplumber `page.lines` (reportlab/typesetter strokes),
not `page.rects`. The `pdf_backend` dual scan of `lines` + thin `rects` is correct;
`rects` was empty here but is defensive for other drafting tools.

On HB 1217, amendatory pages carry many rule lines (e.g. page 18: 22; page 16: 29;
page 9: 27). Non-amendatory pages carry 0–3 (page borders/header rules only).

### 2. Detection accuracy
- **Strikethrough: confirmed working from the start.** Page 18 correctly tagged
  deleted statutory sentences as struck (e.g. *"Except as provided in subsection (2)
  of this section, unless..."*, *"(2) All moneys paid, in excess of two months'
  rent..."*).
- **Underline: initially MISSED (0 across all pages), now fixed.** A frac histogram
  of same-line char↔rule pairs on page 18 showed two clean clusters:
  - frac ≈ **0.50** → mid-glyph → strikethrough (589 char-pairs)
  - frac ≈ **0.82** → underline on added text (16 char-pairs), e.g. `30.22.041`, `Unless`
  The original `UNDERLINE_BAND = (0.85, 1.30)` started just **above** 0.82, so real
  underlines fell in the dead gap between the strike and underline bands and returned
  `None`.

### 3. Root cause
pdfplumber's char bounding box includes descender padding, so the *visual* baseline
sits at ~0.8 of box height (not 1.0). WA underline rules are drawn right under the
text → frac ≈ 0.82.

## Calibration applied
`src/netscan/geometry.py`:
```
UNDERLINE_BAND = (0.85, 1.30)   # before
UNDERLINE_BAND = (0.72, 1.35)   # after — catches frac~0.82; gap above STRIKE_BAND (…,0.70) preserved
```

### Post-fix verification (HB 1217)
- Page 9: 10 underlined added spans + 3 struck.
- Page 16: underlined `NEW SECTION.` and added subsections + 3 struck.
- Page 18: old `30.22.041` struck (deleted) ↔ new `30A.22.041` underlined (added) —
  correct amendment semantics, aligning with strike→`[[del]]`, underline→`[[ins]]`.
- Full unit suite: 14/14 pass (synthetic fixtures unaffected by the band change).

## Failure modes / follow-ups for downstream plans
1. **Calibration is single-source (WA, one meaningful bill).** Only HB 1217 carried
   amendatory content (HB 1100 had none), so the constants are effectively WA-tuned on
   one document. Other states may place rules at different fracs. Treat
   `STRIKE_BAND`/`UNDERLINE_BAND`/`MIN_X_OVERLAP_RATIO` as per-corpus tunables;
   **validate against ≥1 amendatory bill per new state before trusting output.**
   Cross-state use is NOT yet supported.
2. **Band-edge ambiguity is exactly the Stage-3 conflict signal.** Rules whose frac
   lands near a band boundary (≈0.70–0.72) should be flagged for VLM/QA adjudication
   rather than silently classified. Build this into conflict detection.
3. **Widened `UNDERLINE_BAND` (…,1.35) risks false positives from rules BELOW text.**
   frac 1.35 reaches ~0.35×glyph-height below the char box (~4pt under a 12pt line). A
   full-width table-cell border or horizontal row separator sitting under a line of
   text has ≥50% x-overlap with every glyph above it and will now be tagged
   `underline`. HB 1217's sample showed none (no dense tables), so it is untested, not
   absent. **Stage-3 must treat horizontal rules below text in tabular regions as
   adjudication candidates, not silent underlines.**
4. **`geometry.py` `extract_page_spans` line-bucketing can scramble span TEXT (latent
   bug, deferred).** The sort key `round(c.top / SAME_LINE_TOL)` only orders by `x0`
   *within* a bucket, and the merge has no x-adjacency check. When one visual line's
   glyphs straddle a bucket boundary (e.g. tops 4.4 and 4.6 with tol=3.0 → buckets 1
   and 2), x-order is scrambled and baked into the merged span text (reproduced:
   `"ABCD"` → `"ACBD"`). Low-frequency in single-column bills (same-line glyphs usually
   share an identical `top`), so deferred — but it corrupts text, not just order. **Fix
   before the multi-column/tabular work: cluster chars into lines first, then sort each
   line by `x0`, using the same bucket value for both the sort and the same-line test.**
5. **No scanned pages encountered** — Job B (OCR) path remains untested on real input;
   defer to its own plan as designed.
6. **Reading order on multi-column / tabular pages not yet stress-tested** — the
   current top-to-bottom, left-to-right sort is adequate for single-column bill text
   but must be revisited for tables (pairs with #4; already a Stage-3 conflict category).

## Gate decision
**PASS.** The architecture's core empirical premise is validated on real bills.
Strikethrough and underline are reliably recoverable as vector rule lines, and the
deterministic geometry path tags them correctly after the band calibration above.
Proceed to build Stages 3–7 (conflict detection, reconcile, emit, verify) on this
foundation.
