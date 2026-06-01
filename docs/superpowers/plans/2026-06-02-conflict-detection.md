# Stage 3 — Conflict Detection — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Flag the ambiguous residual geometry can't resolve (band-edge rules, orphan rules, table/row-border "underlines"), recording it on spans + as region `Conflict`s for the QA queue — and fix the latent span-text-scramble bug in span assembly.

**Architecture:** New pure module `conflict.py` exposing `detect_conflicts(geo, spans) -> (spans, conflicts)`. It annotates ambiguous spans (`Span.flag_reason` + lowered `confidence`) and returns region-level `Conflict`s. It reuses geometry's bands and overlap helper (no pdfplumber import; isolation preserved). Conflict detection only flags — it never re-classifies. The span-scramble fix lands in `geometry.py` because conflict detection depends on correct span text.

**Tech Stack:** Python 3.11+, pytest. No model/API calls. Builds on Phase 1 (`pdf_backend`, `triage`, `geometry`, `types`).

**Spec:** `docs/superpowers/specs/2026-06-02-conflict-detection-design.md`.

---

## File Structure

```
src/netscan/types.py        MODIFY: add Span.flag_reason field
src/netscan/geometry.py     MODIFY: fix extract_page_spans line clustering; promote x_overlap_ratio to public
src/netscan/conflict.py     CREATE: Conflict dataclass + detect_conflicts + helpers
scripts/inspect_bill.py     MODIFY: print conflicts; used for real-bill verification
tests/test_geometry.py      MODIFY: add span-scramble regression test
tests/test_types.py         MODIFY: add flag_reason default test
tests/test_conflict.py      CREATE: per-category conflict tests
```

---

### Task 1: Fix span-text scramble in `extract_page_spans`

The current sort `(round(c.top / SAME_LINE_TOL), c.x0)` orders by `x0` only *within* a rounding bucket, so a single visual line whose glyph `top`s straddle a bucket boundary gets its characters scrambled when merged. Fix: cluster chars into lines by proximity first, then x-sort each line.

**Files:**
- Modify: `src/netscan/geometry.py` (the `extract_page_spans` function only)
- Test: `tests/test_geometry.py`

- [ ] **Step 1: Write the failing regression test (append to `tests/test_geometry.py`)**

```python
def test_line_straddling_bucket_boundary_keeps_text_order():
    # One visual line whose glyph tops jitter 4.4/4.6 across the round(top/3.0)
    # bucket boundary (bucket 1 vs 2). Must still read left-to-right "ABCD".
    def c(t, x0, top):
        return Char(text=t, x0=x0, x1=x0 + 6, top=top, bottom=top + 10,
                    fontname="Helvetica", size=10)
    chars = [c("A", 10, 4.4), c("B", 16, 4.6), c("C", 22, 4.4), c("D", 28, 4.6)]
    geo = PageGeometry(width=612, height=792, chars=chars, rule_lines=[], image_count=0)
    spans = extract_page_spans(geo)
    assert "".join(s.text for s in spans) == "ABCD"
```

(`Char`, `PageGeometry`, `extract_page_spans` are already imported in this test file from earlier tasks. If a needed name is missing, add the import.)

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_geometry.py::test_line_straddling_bucket_boundary_keeps_text_order -v`
Expected: FAIL — assembled text is `"ACBD"` (scrambled), not `"ABCD"`.

- [ ] **Step 3: Replace `extract_page_spans` in `src/netscan/geometry.py`**

Replace the entire existing `extract_page_spans` function (keep `SAME_LINE_TOL` and `_char_format` exactly as they are) with:

```python
def extract_page_spans(geo: PageGeometry) -> list[Span]:
    """Assemble chars into Spans in reading order (top-to-bottom, left-to-right).

    Chars are first clustered into lines by vertical proximity (within
    SAME_LINE_TOL of the line's first char), then each line is sorted by x0 and
    consecutive same-format chars are merged into one Span. Clustering before
    sorting prevents a line whose tops straddle a bucket boundary from scrambling.
    """
    ordered = sorted(geo.chars, key=lambda c: (c.top, c.x0))
    lines: list[tuple[float, list[Char]]] = []
    for ch in ordered:
        if lines and abs(ch.top - lines[-1][0]) <= SAME_LINE_TOL:
            lines[-1][1].append(ch)
        else:
            lines.append((ch.top, [ch]))

    spans: list[Span] = []
    for _, line_chars in lines:
        cur: Span | None = None
        cur_fmt: tuple | None = None
        for ch in sorted(line_chars, key=lambda c: c.x0):
            fmt = _char_format(ch, geo.rule_lines)
            if cur is not None and fmt == cur_fmt:
                cur.text += ch.text
                cur.x1 = ch.x1
                cur.bottom = max(cur.bottom, ch.bottom)
            else:
                bold, italic, struck, underlined = fmt
                cur = Span(text=ch.text, x0=ch.x0, x1=ch.x1, top=ch.top, bottom=ch.bottom,
                           bold=bold, italic=italic, struck=struck, underlined=underlined,
                           confidence=1.0, source="geometry")
                spans.append(cur)
                cur_fmt = fmt
    return spans
```

- [ ] **Step 4: Run the full suite**

Run: `python -m pytest -q`
Expected: PASS — the new test passes and all prior tests (fixture, mixed-format, line_decoration) stay green (17 total).

- [ ] **Step 5: Commit**

```bash
git add src/netscan/geometry.py tests/test_geometry.py
git commit -m "fix: cluster chars into lines before x-sort to prevent span-text scramble"
```

---

### Task 2: Add `flag_reason` to `Span`

**Files:**
- Modify: `src/netscan/types.py`
- Test: `tests/test_types.py`

- [ ] **Step 1: Write the failing test (append to `tests/test_types.py`)**

```python
def test_span_flag_reason_defaults_none_and_settable():
    s = Span(text="x", x0=0, x1=1, top=0, bottom=1)
    assert s.flag_reason is None
    s2 = Span(text="y", x0=0, x1=1, top=0, bottom=1, flag_reason="band_edge: foo")
    assert s2.flag_reason == "band_edge: foo"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_types.py::test_span_flag_reason_defaults_none_and_settable -v`
Expected: FAIL — `TypeError: __init__() got an unexpected keyword argument 'flag_reason'`.

- [ ] **Step 3: Add the field in `src/netscan/types.py`**

Add `flag_reason` as the LAST field of the `Span` dataclass (after `source`), so existing positional usage is unaffected:

```python
    source: Source = "geometry"
    flag_reason: Optional[str] = None
```

Add the import at the top of the file if not present:

```python
from typing import Literal, Optional
```

- [ ] **Step 4: Run the full suite**

Run: `python -m pytest -q`
Expected: PASS (18 total). Existing Span tests unaffected (new field defaults to None).

- [ ] **Step 5: Commit**

```bash
git add src/netscan/types.py tests/test_types.py
git commit -m "feat: add Span.flag_reason for conflict annotation"
```

---

### Task 3: Promote `x_overlap_ratio` to public in `geometry.py`

`conflict.py` needs the same glyph/rule x-overlap math `geometry.py` already has. Promote the private helper to a public name (DRY — one shared implementation) and update its single internal caller.

**Files:**
- Modify: `src/netscan/geometry.py`
- Test: `tests/test_geometry.py`

- [ ] **Step 1: Write the failing test (append to `tests/test_geometry.py`)**

```python
def test_x_overlap_ratio_is_public():
    from netscan.geometry import x_overlap_ratio
    ch = Char(text="x", x0=10, x1=20, top=0, bottom=10, fontname="Helvetica", size=10)
    full = RuleLine(x0=10, x1=20, top=5, bottom=5)
    half = RuleLine(x0=15, x1=25, top=5, bottom=5)
    assert x_overlap_ratio(ch, full) == 1.0
    assert x_overlap_ratio(ch, half) == 0.5
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_geometry.py::test_x_overlap_ratio_is_public -v`
Expected: FAIL — `cannot import name 'x_overlap_ratio'`.

- [ ] **Step 3: Rename in `src/netscan/geometry.py`**

Rename the function `_x_overlap_ratio` to `x_overlap_ratio` (drop the leading underscore) at its definition, and update its one caller inside `line_decoration`:

```python
def x_overlap_ratio(ch: Char, rule: RuleLine) -> float:
    overlap = min(ch.x1, rule.x1) - max(ch.x0, rule.x0)
    width = ch.x1 - ch.x0
    if width <= 0:
        return 0.0
    return max(0.0, overlap) / width
```

In `line_decoration`, change the call site:

```python
        if x_overlap_ratio(ch, rule) < MIN_X_OVERLAP_RATIO:
```

- [ ] **Step 4: Run the full suite**

Run: `python -m pytest -q`
Expected: PASS (19 total). `line_decoration` tests still green (behavior unchanged, only the helper name changed).

- [ ] **Step 5: Commit**

```bash
git add src/netscan/geometry.py tests/test_geometry.py
git commit -m "refactor: make x_overlap_ratio public for reuse by conflict detection"
```

---

### Task 4: `conflict.py` — `Conflict` dataclass + `detect_conflicts` (all three categories)

The core of the stage. Build the module with shared helpers and all three categories, TDD with one focused test per behavior.

**Files:**
- Create: `src/netscan/conflict.py`
- Test: `tests/test_conflict.py`

- [ ] **Step 1: Write the failing tests (`tests/test_conflict.py`)**

```python
from netscan.pdf_backend import Char, PageGeometry, RuleLine
from netscan.types import Span
from netscan.conflict import detect_conflicts, Conflict


def _char(t, x0, top=100.0):
    return Char(text=t, x0=x0, x1=x0 + 6, top=top, bottom=top + 10,
                fontname="Helvetica", size=10)


def _span(text, x0, x1, top=100.0, **kw):
    return Span(text=text, x0=x0, x1=x1, top=top, bottom=top + 10, **kw)


def test_clean_strike_and_underline_are_not_flagged():
    # frac 0.5 (strike) and 0.82 (underline) are both well outside the edge zone.
    chars = [_char("S", 10), _char("U", 30)]
    strike = RuleLine(x0=10, x1=16, top=105.0, bottom=105.0)   # frac 0.5
    under = RuleLine(x0=30, x1=36, top=108.2, bottom=108.2)    # frac 0.82
    geo = PageGeometry(width=612, height=792, chars=chars,
                       rule_lines=[strike, under], image_count=0)
    spans = [_span("S", 10, 16, struck=True), _span("U", 30, 36, underlined=True)]
    out, conflicts = detect_conflicts(geo, spans)
    assert conflicts == []
    assert all(s.flag_reason is None for s in out)


def test_band_edge_rule_flags_span_and_emits_conflict():
    ch = _char("X", 10)                                        # top 100, h 10
    rule = RuleLine(x0=10, x1=16, top=107.1, bottom=107.1)     # frac 0.71 -> edge zone
    geo = PageGeometry(width=612, height=792, chars=[ch],
                       rule_lines=[rule], image_count=0)
    span = _span("X", 10, 16)
    out, conflicts = detect_conflicts(geo, [span])
    assert any(c.kind == "band_edge" for c in conflicts)
    assert out[0].flag_reason is not None and "band_edge" in out[0].flag_reason
    assert out[0].confidence == 0.5


def test_orphan_rule_over_text_emits_conflict():
    # A wide rule over text whose frac (0.0) matches no band and isn't an edge.
    ch = _char("Y", 10)
    rule = RuleLine(x0=10, x1=40, top=100.0, bottom=100.0)     # frac 0.0 -> no band
    geo = PageGeometry(width=612, height=792, chars=[ch],
                       rule_lines=[rule], image_count=0)
    out, conflicts = detect_conflicts(geo, [_span("Y", 10, 16)])
    assert any(c.kind == "orphan_rule" for c in conflicts)


def test_page_border_rule_not_overlapping_text_is_ignored():
    ch = _char("Z", 10)
    border = RuleLine(x0=400, x1=590, top=50.0, bottom=50.0)   # no x-overlap with text
    geo = PageGeometry(width=612, height=792, chars=[ch],
                       rule_lines=[border], image_count=0)
    out, conflicts = detect_conflicts(geo, [_span("Z", 10, 16)])
    assert conflicts == []


def test_wide_underline_rule_flags_as_possible_border():
    ch = _char("W", 10)                                        # 6pt wide glyph
    wide = RuleLine(x0=10, x1=560, top=108.2, bottom=108.2)    # frac 0.82, ~full width
    geo = PageGeometry(width=612, height=792, chars=[ch],
                       rule_lines=[wide], image_count=0)
    span = _span("W", 10, 16, underlined=True)
    out, conflicts = detect_conflicts(geo, [span])
    assert any(c.kind == "wide_underline" for c in conflicts)
    assert out[0].flag_reason is not None and "wide_underline" in out[0].flag_reason
    assert out[0].underlined is True  # tag retained — Stage 3 flags, does not resolve
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_conflict.py -v`
Expected: FAIL — `No module named 'netscan.conflict'`.

- [ ] **Step 3: Create `src/netscan/conflict.py`**

```python
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
CANDIDATE_FRAC_RANGE = (0.2, 1.4)   # fracs a rule could plausibly be decorating


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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_conflict.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Run the full suite**

Run: `python -m pytest -q`
Expected: PASS (24 total).

- [ ] **Step 6: Commit**

```bash
git add src/netscan/conflict.py tests/test_conflict.py
git commit -m "feat: add Stage 3 conflict detection (band-edge, orphan, wide-underline)"
```

---

### Task 5: Wire conflicts into `inspect_bill.py` + real-bill verification

Extend the spike tool to report conflicts, then verify on HB 1217 that the flagged fraction is small and genuine (success metric).

**Files:**
- Modify: `scripts/inspect_bill.py`

- [ ] **Step 1: Update `scripts/inspect_bill.py`**

Replace the body of `main` to also run conflict detection and print a per-page conflict summary plus a document-level flagged-span fraction. Full file:

```python
"""Report what the geometry path sees in a real bill, per page.

Usage: python scripts/inspect_bill.py samples/some_bill.pdf
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from netscan.pdf_backend import open_pdf          # noqa: E402
from netscan.triage import classify_page          # noqa: E402
from netscan.geometry import extract_page_spans    # noqa: E402
from netscan.conflict import detect_conflicts      # noqa: E402


def main(pdf_path: str) -> None:
    pages = open_pdf(Path(pdf_path))
    total_spans = 0
    total_flagged = 0
    total_conflicts = 0
    for i, geo in enumerate(pages, 1):
        kind = classify_page(geo)
        spans = extract_page_spans(geo) if kind.value == "native" else []
        spans, conflicts = detect_conflicts(geo, spans)
        flagged = [s for s in spans if s.flag_reason]
        total_spans += len(spans)
        total_flagged += len(flagged)
        total_conflicts += len(conflicts)
        struck = [s.text for s in spans if s.struck]
        under = [s.text for s in spans if s.underlined]
        print(f"\n=== page {i}: {kind.value} | chars={len(geo.chars)} "
              f"rule_lines={len(geo.rule_lines)} images={geo.image_count} ===")
        print(f"  struck spans ({len(struck)}): {struck[:8]}")
        print(f"  underlined spans ({len(under)}): {under[:8]}")
        print(f"  conflicts ({len(conflicts)}): "
              f"{[c.kind for c in conflicts]}")
        if flagged:
            print(f"  flagged spans ({len(flagged)}): "
                  f"{[(s.text, s.flag_reason) for s in flagged][:5]}")
    pct = (100.0 * total_flagged / total_spans) if total_spans else 0.0
    print(f"\n--- TOTAL: spans={total_spans} flagged={total_flagged} "
          f"({pct:.1f}%) conflicts={total_conflicts} ---")


if __name__ == "__main__":
    main(sys.argv[1])
```

- [ ] **Step 2: Run on the real bill (if `samples/wa_hb1217.pdf` is present)**

Run: `python scripts/inspect_bill.py samples/wa_hb1217.pdf`
Expected: per-page output ending with a TOTAL line. Verify:
- The flagged fraction is **small** (geometry should resolve the vast majority; a high % means a band/threshold is mis-tuned, not that the code is wrong).
- Struck/underlined detection from Phase 1 is unchanged on the amendatory pages (9, 16, 18).
- Conflicts that appear are plausible (e.g. `wide_underline` only where a genuinely wide rule exists).

If `samples/wa_hb1217.pdf` is absent (it is gitignored), re-download per the gate doc:
`curl -sL -A "Mozilla/5.0" -o samples/wa_hb1217.pdf "https://lawfilesext.leg.wa.gov/biennium/2025-26/Pdf/Bills/House%20Bills/1217.pdf"`

- [ ] **Step 3: Record the result as a concern if the flagged fraction is high**

If the flagged fraction exceeds ~5%, do NOT silently accept it. Report it back (DONE_WITH_CONCERNS) with the per-page breakdown so the controller can decide whether a constant needs tuning. Otherwise note the actual percentage in the report.

- [ ] **Step 4: Commit**

```bash
git add scripts/inspect_bill.py
git commit -m "feat: report conflicts and flagged-span fraction in inspect_bill"
```

---

## Self-Review

**Spec coverage:**
- §2 `Span.flag_reason` → Task 2 ✓; `Conflict` dataclass → Task 4 ✓
- §3 `detect_conflicts(geo, spans) -> (spans, conflicts)`, pure, no pdfplumber → Task 4 ✓
- §4.1 band-edge (range 0.66–0.76, conf 0.5, flags regardless of classification) → Task 4 test `test_band_edge...` ✓
- §4.2 orphan rule (over text, no band, min width, page-border ignored) → Task 4 tests `test_orphan...`, `test_page_border...` ✓
- §4.3 wide underline (factor 1.5 / page-frac 0.8, tag retained) → Task 4 test `test_wide_underline...` ✓
- §4 no-false-flag on clean strike/underline → Task 4 test `test_clean_strike_and_underline...` ✓
- §5 span-scramble fix (cluster lines then x-sort) → Task 1 ✓
- §6 color + multi-column deferred → not implemented (correct) ✓
- §8 real-bill check → Task 5 ✓
- §9 success metrics (flagged fraction small, no dropped rules, scramble test, no false flags) → Tasks 1, 4, 5 ✓

**Placeholder scan:** No TBD/TODO/"handle edge cases"; every code step shows complete code. Task 5 Steps 2–3 are spike verification with explicit numeric gates, not vague instructions. ✓

**Type consistency:**
- `Span` gains `flag_reason: Optional[str] = None` (Task 2), used identically in `conflict.py` and tests (Task 4). ✓
- `x_overlap_ratio` (public, Task 3) imported and called in `conflict.py` (Task 4) with matching `(Char, RuleLine) -> float` signature. ✓
- `STRIKE_BAND`/`UNDERLINE_BAND`/`MIN_X_OVERLAP_RATIO` imported from `geometry` match their definitions there. ✓
- `Conflict` fields (`kind, reason, x0, x1, top, bottom, confidence`) constructed consistently in `detect_conflicts` and asserted by `.kind` in tests. ✓
- `detect_conflicts` return shape `(spans, conflicts)` consumed correctly in `inspect_bill.py` (Task 5). ✓
