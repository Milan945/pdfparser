# Reading-Order / Ligature Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop the span-builder from scrambling words that contain zero-width ligature glyphs (`five` -> `vfie`, `officer` -> `ofcfier`), restoring faithful statutory text and making struck/italic runs contiguous.

**Architecture:** The bug is in `extract_page_spans` (`src/netscan/geometry.py`). Within a visual line it sorts chars purely by `x0`. A `fi`/`ffi` ligature glyph is reported by pdfplumber with a collapsed, zero-width box (`x1 <= x0`) whose reported `x0` is the pen ADVANCE position, landing ~0.1pt onto the neighbor instead of the ligature's true visual origin (~1 glyph-width to the LEFT). Fix: sort within a line by `x0` quantized to ~1pt buckets, tie-broken by content-stream order, AND left-bias zero-width glyphs by one quantum so they bucket to the left of the neighbor they collapsed onto. Normal characters are ~6pt apart so their order is unchanged; only zero-width ligature glyphs move.

**CORRECTED (verified against the real bill):** an earlier draft of this plan assumed content-stream order would place the ligature before its neighbor; it does NOT. For `five` the stream order is `space, v, fi, e` (ligature AFTER `v`), so a stream-order tiebreak alone leaves "vfie". The left-bias on zero-width glyphs is the actual fix. Verified: CA `vfie` 5->0, `ofcfier` 6->0, both gate tests still green.

**Tech Stack:** Python 3.14, pytest. No new dependencies.

**Hard gate (must stay green):** `tests/test_geometry.py::test_mixed_format_single_line_splits_into_ordered_spans` and `::test_line_straddling_bucket_boundary_keeps_text_order`. These protect the earlier span-scramble fix. The change is valid only if BOTH stay green while `five`/`officer` are fixed.

---

## Root-cause evidence (from real CA bill, page 3, the word "five")

```
streamidx  text   x0       x1
640        ' '    92.294   95.294
641        'v'    94.556   100.556
642        'fi'   94.630   94.630    <- zero-width ligature, drawn AFTER v, x0 collapsed onto v
643        'e'    106.974  112.302
```
Pure-x0 sort yields `space, v, fi, e` = " vfie". Stream order is `v` THEN `fi`, so a stream-order tiebreak does NOT help. Left-biasing the zero-width `fi` by one quantum: its sort-x becomes 93.63 -> bucket 94, while `v`->95 and space->92, giving `space(92), fi(94), v(95), e(107)` = " five". The same left-bias fixes `officer`->`ofcfier` (an `fi`/`ffi` glyph drawn after `c`).

---

## File Structure

- Modify: `src/netscan/geometry.py` - `extract_page_spans` within-line sort only.
- Modify: `tests/test_geometry.py` - add a synthetic ligature-ordering unit test.
- Create: `tests/test_reading_order.py` - real-bill regressions (`five`, `officer`).

---

## Task 1: Stream-order-preserving within-line sort

**Files:**
- Modify: `src/netscan/geometry.py`
- Test: `tests/test_geometry.py`

- [ ] **Step 1: Write the failing unit test**

```python
# tests/test_geometry.py  (add near the other extract_page_spans tests)
def test_zero_width_ligature_keeps_stream_order():
    # Reproduces the real "five" case: a zero-width 'fi' ligature whose x0 lands
    # just RIGHT of the following 'v'. Pure-x0 sort gives "vfie"; the builder must
    # emit "five" by falling back to content-stream order for the sub-1pt overlap.
    def c(t, x0, x1):
        return Char(text=t, x0=x0, x1=x1, top=100.0, bottom=110.0,
                    fontname="Times-Roman", size=10)
    # Real stream order: 'v' is drawn BEFORE the zero-width 'fi' ligature (whose
    # x0 collapses onto v). A stream-order tiebreak alone gives "vfie"; only the
    # left-bias on the zero-width glyph produces "five".
    chars = [c("v", 94.56, 100.56), c("fi", 94.63, 94.63), c("e", 106.97, 112.30)]
    geo = PageGeometry(width=612, height=792, chars=chars, rule_lines=[], image_count=0)
    spans = _eps(geo)
    assert "".join(s.text for s in spans) == "five"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_geometry.py::test_zero_width_ligature_keeps_stream_order -v`
Expected: FAIL — actual is "vfie" (pure-x0 sort puts `v` before `fi`).

- [ ] **Step 3: Change the within-line sort**

In `src/netscan/geometry.py`, add a quantum constant next to `SAME_LINE_TOL`:

```python
SAME_LINE_TOL = 3.0  # pts; chars whose tops differ by less are on one line
X_ORDER_QUANTUM = 1.0  # pts; within a line, x0 is bucketed to this granularity
#                        so sub-quantum overlaps (zero-width ligature glyphs whose
#                        x0 collapses onto a neighbor) fall back to content-stream
#                        order instead of scrambling. Normal glyphs are ~6pt apart.
```

In `extract_page_spans`, build a content-stream index map once, and change ONLY the within-line sort key (line that currently reads `for ch in sorted(line_chars, key=lambda c: c.x0):`). Replace the function body's ordering so it reads:

```python
def extract_page_spans(geo: PageGeometry) -> list[Span]:
    """Assemble chars into Spans in reading order (top-to-bottom, left-to-right).

    Chars are first clustered into lines by vertical proximity (within
    SAME_LINE_TOL of the line's first char), then each line is ordered by x0
    bucketed to X_ORDER_QUANTUM (ties broken by content-stream order) and
    consecutive same-format chars are merged into one Span. Clustering before
    ordering prevents a line whose tops straddle a bucket boundary from
    scrambling; bucketing x0 prevents a zero-width ligature glyph (whose x0
    collapses onto its neighbor) from reordering with that neighbor.
    """
    stream_index = {id(c): i for i, c in enumerate(geo.chars)}
    ordered = sorted(geo.chars, key=lambda c: (c.top, c.x0))
    lines: list[tuple[float, list[Char]]] = []
    for ch in ordered:
        if lines and abs(ch.top - lines[-1][0]) <= SAME_LINE_TOL:
            lines[-1][1].append(ch)
        else:
            lines.append((ch.top, [ch]))

    def line_order_key(c: Char):
        # Zero-width ligature glyphs (x1 <= x0) report their pen-advance x, which
        # collapses onto the following glyph; bias them one quantum left so they
        # order at their true visual origin. Ties break by content-stream order.
        x = c.x0 - X_ORDER_QUANTUM if c.x1 <= c.x0 else c.x0
        return (round(x / X_ORDER_QUANTUM), stream_index[id(c)])

    spans: list[Span] = []
    for _, line_chars in lines:
        cur: Span | None = None
        cur_fmt: tuple | None = None
        for ch in sorted(line_chars, key=line_order_key):
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

- [ ] **Step 4: Run the new test AND the hard-gate tests**

Run: `python -m pytest tests/test_geometry.py -v`
Expected: ALL pass, including `test_zero_width_ligature_keeps_stream_order`, `test_mixed_format_single_line_splits_into_ordered_spans`, and `test_line_straddling_bucket_boundary_keeps_text_order`.

If either gate test fails, STOP and report — do not weaken the gate tests.

- [ ] **Step 5: Commit**

```bash
git add src/netscan/geometry.py tests/test_geometry.py
git commit -m "fix: preserve stream order for zero-width ligature glyphs in span-builder"
```

---

## Task 2: Real-bill regressions (five, officer)

**Files:**
- Create: `tests/test_reading_order.py`

- [ ] **Step 1: Write the tests**

```python
# tests/test_reading_order.py
from pathlib import Path
import pytest
from netscan.pdf_backend import open_pdf
from netscan.geometry import extract_page_spans
from netscan.structure import strip_gutter
from netscan.profiles import PROFILES

_CA = Path("samples/there samples/2025_2026_5_2_2_000351_0_4_1_20250130_0.pdf")


def _ca_text() -> str:
    parts = []
    for geo in open_pdf(_CA):
        geo = strip_gutter(geo, PROFILES["CA"])
        for s in extract_page_spans(geo):
            parts.append(s.text)
    return "".join(parts)


@pytest.mark.skipif(not _CA.exists(), reason="CA sample bill not present")
def test_five_not_scrambled():
    text = _ca_text()
    assert "five hundred dollars" in text
    assert "vfie" not in text


@pytest.mark.skipif(not _CA.exists(), reason="CA sample bill not present")
def test_officer_not_scrambled():
    text = _ca_text()
    assert "officer" in text
    assert "ofcfier" not in text
```

- [ ] **Step 2: Run the tests**

Run: `python -m pytest tests/test_reading_order.py -v`
Expected: both PASS. If `test_officer_not_scrambled` fails, the `officer` ligature (likely `ffi`) may have a different geometry than `fi`; report the failing char dump (do NOT loosen the assertion) so the controller can decide whether it needs a follow-up.

- [ ] **Step 3: Commit**

```bash
git add tests/test_reading_order.py
git commit -m "test: lock real-bill reading-order fix (five, officer)"
```

---

## Task 3: Full-suite + score regression check

**Files:** none (verification only)

- [ ] **Step 1: Run the full suite**

Run: `python -m pytest -q`
Expected: all tests pass (43 prior + 3 new = 46), with NO previously-passing test now failing.

- [ ] **Step 2: Re-measure scores**

Run: `PYTHONIOENCODING=utf-8 python scripts/score_bill.py`
Expected: all three char_similarity scores HOLD or RISE vs current master (KS2203 0.9984, KS2206 0.9977, CA351 0.9868). The CA score should rise (the `vfie`/`ofcfier` content errors are corrected). Record the three numbers. If ANY score drops, STOP and report — the quantization regressed something.

- [ ] **Step 3: No commit** (verification only; nothing changed).

---

## Self-Review

**Spec coverage:** Single root-cause fix (within-line ordering) plus its synthetic and real-bill regressions and a full-suite/score gate. Nothing else changed.

**Placeholder scan:** No placeholders. Failure branches in Tasks 2/3 say "STOP and report", not "handle later".

**Type consistency:** `X_ORDER_QUANTUM: float`, `stream_index: dict[int, int]` keyed by `id(char)`, `line_order_key(Char) -> tuple[int, int]`. `extract_page_spans` signature unchanged.

**Risk note:** This is core geometry. The quantization is global but only affects ordering of chars whose x0 falls within 1pt of each other; real adjacent glyphs are ~6pt apart, so only degenerate overlaps (ligatures) change behavior. The two hard-gate tests plus the three real-bill scores are the empirical proof that normal text is unaffected. If a future bill exhibits a sub-1pt boundary inversion, refine by scoping the stream-order fallback to zero-width glyphs (`x1 <= x0`) specifically rather than all chars.
