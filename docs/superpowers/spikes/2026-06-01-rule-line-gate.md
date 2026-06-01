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
1. **Calibration is single-source (WA, one bill).** Other states may place rules at
   different fracs. Treat `STRIKE_BAND`/`UNDERLINE_BAND`/`MIN_X_OVERLAP_RATIO` as
   per-corpus tunables; validate against ≥1 bill per new state before trusting output.
2. **Band-edge ambiguity is exactly the Stage-3 conflict signal.** Rules whose frac
   lands near a band boundary (≈0.70–0.72) should be flagged for VLM/QA adjudication
   rather than silently classified. Build this into conflict detection.
3. **No scanned pages encountered** — Job B (OCR) path remains untested on real input;
   defer to its own plan as designed.
4. **Reading order on multi-column / tabular pages not yet stress-tested** — the
   current top-to-bottom, left-to-right sort is adequate for single-column bill text
   but must be revisited for tables (already a Stage-3 conflict category).

## Gate decision
**PASS.** The architecture's core empirical premise is validated on real bills.
Strikethrough and underline are reliably recoverable as vector rule lines, and the
deterministic geometry path tags them correctly after the band calibration above.
Proceed to build Stages 3–7 (conflict detection, reconcile, emit, verify) on this
foundation.
