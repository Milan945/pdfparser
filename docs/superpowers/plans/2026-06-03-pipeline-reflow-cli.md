# Pipeline + Reflow + CLI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a usable end-to-end converter: `convert(pdf_path, state) -> str` that turns a bill PDF into paragraph-structured NetScan markup `.txt`, plus a CLI. Reflow groups wrapped lines into paragraphs (blank-line separated) and, by merging tags only WITHIN a paragraph, also fixes the cross-paragraph over-merge.

**Architecture:** New `src/netscan/reflow.py` groups a page's spans into lines (by `top`) and lines into paragraphs (a new paragraph starts at a block-marker line: section/subsection/front-matter). New `src/netscan/pipeline.py` chains `open_pdf -> strip_gutter -> extract_page_spans -> reflow.paragraphs -> emit.render_markup(per paragraph)`, joining paragraphs with blank lines, and exposes a CLI. `emit.render_markup` is reused per-paragraph, so tag-merge stays within a paragraph and never bridges two.

**Tech Stack:** Python 3.14, pytest. No new dependencies.

---

## File Structure

- Create: `src/netscan/reflow.py` - `lines_of(spans)`, `paragraphs(spans, profile)`.
- Create: `src/netscan/pipeline.py` - `convert(pdf_path, state) -> str` + `main()` CLI.
- Create: `tests/test_reflow.py` - paragraph grouping tests.
- Create: `tests/test_pipeline.py` - end-to-end real-bill tests.

---

## Task 1: Group spans into lines

**Files:** Create `src/netscan/reflow.py`; Test `tests/test_reflow.py`

- [ ] **Step 1: Failing test**

```python
# tests/test_reflow.py
from netscan.types import Span
from netscan.reflow import lines_of


def _s(text, top, x0=10.0):
    return Span(text=text, x0=x0, x1=x0 + 5, top=top, bottom=top + 10,
                bold=False, italic=False, struck=False, underlined=False,
                confidence=1.0, source="geometry")


def test_lines_of_groups_spans_by_top():
    spans = [_s("a", 100), _s("b", 100.5), _s("c", 130)]
    lines = lines_of(spans)
    assert ["".join(s.text for s in ln) for ln in lines] == ["ab", "c"]
```

- [ ] **Step 2: Run -> fail** (`python -m pytest tests/test_reflow.py -v` -> ModuleNotFound)

- [ ] **Step 3: Implement**

```python
# src/netscan/reflow.py
"""Reflow: group spans into lines and lines into paragraphs.

Legislative source PDFs have one physical line per numbered line with no blank
lines; Doctly output groups wrapped lines into blank-line-separated paragraphs.
We reconstruct paragraphs from block-marker lines (section/subsection/front
matter). Tag-merge then runs per paragraph, so a tag never bridges paragraphs.
See docs/superpowers/plans/2026-06-03-pipeline-reflow-cli.md.
"""
from __future__ import annotations
import re

from netscan.types import Span

_SAME_LINE_TOL = 3.0


def lines_of(spans: list[Span]) -> list[list[Span]]:
    """Group spans into physical lines by `top` (within tolerance), each line
    left-to-right, lines top-to-bottom."""
    out: list[list[Span]] = []
    for s in sorted(spans, key=lambda s: (s.top, s.x0)):
        if out and abs(s.top - out[-1][0].top) <= _SAME_LINE_TOL:
            out[-1].append(s)
        else:
            out.append([s])
    for ln in out:
        ln.sort(key=lambda s: s.x0)
    return out


# A line whose plain text starts with one of these begins a new paragraph.
_BLOCK_START = re.compile(
    r"""^\s*(
        Sec\.\s |               # Sec. 2.
        Section\s\d |           # Section 1.
        \([a-zA-Z]\)\s* |       # (a) (b) (A)
        \(\d+\)\s* |            # (1) (2)
        AN\ ACT\b |
        Be\ it\ enacted\b |
        HOUSE\ BILL\b | SENATE\ BILL\b |
        By\ Committee\b | By\ Representative\b | By\ Senator\b |
        Requested\ by\b |
        Session\ of\b
    )""",
    re.VERBOSE,
)


def _line_text(line: list[Span]) -> str:
    return "".join(s.text for s in line)


def paragraphs(spans: list[Span], profile=None) -> list[list[Span]]:
    """Group spans into paragraphs. A new paragraph starts at the first line and
    at every line whose text matches a block-start marker; other lines append to
    the current paragraph (wrapped-line continuation)."""
    paras: list[list[Span]] = []
    for line in lines_of(spans):
        text = _line_text(line)
        if not paras or _BLOCK_START.match(text):
            paras.append(list(line))
        else:
            paras[-1].extend(line)
    return paras
```

- [ ] **Step 4: Run -> pass**

- [ ] **Step 5: Commit** `feat: add reflow.lines_of for span line grouping`

---

## Task 2: Paragraph grouping

**Files:** Modify `tests/test_reflow.py`

- [ ] **Step 1: Tests**

```python
# tests/test_reflow.py  (add)
from netscan.reflow import paragraphs


def test_wrapped_lines_join_into_one_paragraph():
    spans = [_s("(a) first part ", 100), _s("continues here", 112)]
    paras = paragraphs(spans)
    assert len(paras) == 1


def test_new_subsection_marker_starts_new_paragraph():
    spans = [_s("(a) alpha ", 100), _s("(b) beta", 112)]
    paras = paragraphs(spans)
    assert len(paras) == 2


def test_section_header_starts_new_paragraph():
    spans = [_s("text of prior para ", 100), _s("Sec. 2. New section", 112)]
    paras = paragraphs(spans)
    assert len(paras) == 2
```

- [ ] **Step 2-3: Run, confirm pass** (implementation from Task 1 already satisfies these)

- [ ] **Step 4: Commit** `test: lock reflow paragraph grouping`

---

## Task 3: Pipeline + CLI

**Files:** Create `src/netscan/pipeline.py`; Test `tests/test_pipeline.py`

- [ ] **Step 1: Failing test**

```python
# tests/test_pipeline.py
from pathlib import Path
import pytest
from netscan.pipeline import convert

_KS = Path("samples/there samples/2025_2026_16_2_2_002206_0_4_1_20250203_0.pdf")


@pytest.mark.skipif(not _KS.exists(), reason="KS sample bill not present")
def test_convert_produces_paragraphed_markup():
    out = convert(str(_KS), "KS")
    assert "\n\n" in out                      # paragraphs are blank-line separated
    assert "[A>" in out and "[D>" in out       # tags present
    assert "[A> " not in out                    # whitespace stays outside tags
    # content is preserved (a known phrase survives)
    assert "public disclosure commission" in out
```

- [ ] **Step 2: Run -> fail**

- [ ] **Step 3: Implement**

```python
# src/netscan/pipeline.py
"""End-to-end pipeline: bill PDF -> NetScan markup text.

convert() chains open_pdf -> strip_gutter -> extract_page_spans -> reflow into
paragraphs -> render_markup per paragraph, joining paragraphs with blank lines.
Also a CLI:  python -m netscan.pipeline <bill.pdf> <STATE> [out.txt]
"""
from __future__ import annotations
import sys
from pathlib import Path

from netscan.pdf_backend import open_pdf
from netscan.structure import strip_gutter
from netscan.geometry import extract_page_spans
from netscan.profiles import PROFILES
from netscan.reflow import paragraphs
from netscan.emit import render_markup


def convert(pdf_path: str, state: str) -> str:
    """Convert a bill PDF to paragraph-structured NetScan markup text."""
    profile = PROFILES[state]
    spans = []
    for geo in open_pdf(Path(pdf_path)):
        geo = strip_gutter(geo, profile)
        spans.extend(extract_page_spans(geo))
    paras = paragraphs(spans, profile)
    rendered = [render_markup(p).strip() for p in paras]
    return "\n\n".join(r for r in rendered if r)


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: python -m netscan.pipeline <bill.pdf> <STATE> [out.txt]",
              file=sys.stderr)
        return 2
    pdf_path, state = argv[0], argv[1]
    out = convert(pdf_path, state)
    if len(argv) >= 3:
        Path(argv[2]).write_text(out, encoding="utf-8")
        print(f"wrote {argv[2]} ({len(out)} chars)")
    else:
        sys.stdout.buffer.write(out.encode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
```

- [ ] **Step 4: Run -> pass** (`python -m pytest tests/test_pipeline.py -v`)

- [ ] **Step 5: Manual smoke test**

Run: `PYTHONIOENCODING=utf-8 python -m netscan.pipeline "samples/there samples/2025_2026_16_2_2_002206_0_4_1_20250203_0.pdf" KS out_ks.txt` from repo root with `src` on path (the test uses the installed package; for the CLI run set `PYTHONPATH=src`). Confirm `out_ks.txt` looks like paragraphed markup. Then delete `out_ks.txt` (do not commit it).

- [ ] **Step 6: Commit** `feat: add pipeline.convert + CLI (PDF -> markup .txt)`

---

## Task 4: Measure full-output similarity

**Files:** Modify `scripts/score_bill.py`

Add a `convert`-based full-output similarity so reflow quality is measured (paragraphs + tags vs gold, whitespace-collapsed). This replaces the span-concatenation path with the real pipeline for the tagged metric.

- [ ] **Step 1: Add a fulltext metric to `score_pair`**

In `scripts/score_bill.py`, add after the tagged metric:

```python
    # full pipeline output (with reflow) vs gold, whitespace-collapsed
    from netscan.pipeline import convert
    state = _state_for(pdf_path)
    full = convert(pdf_path, state)
    fk_o = re.sub(r"\s+", " ", full).strip()
    full_ratio = difflib.SequenceMatcher(None, fk_o, tk_g).ratio()
    print(f"  fulltext similarity={full_ratio:.4f} (pipeline reflow output vs gold)")
```

- [ ] **Step 2: Re-measure**

Run: `PYTHONIOENCODING=utf-8 python scripts/score_bill.py`
Record content / tagged / fulltext for all three. The `fulltext` number is the new headline (reflow + tags). It may differ from `tagged` because reflow changes paragraph boundaries and limits cross-paragraph merge. If `fulltext` is much LOWER than `tagged`, reflow is over-splitting; report the worst paragraph diffs.

- [ ] **Step 3: Commit** `feat(scorer): add fulltext similarity via pipeline.convert`

---

## Self-Review

**Spec coverage:** Produces the deliverable pipeline + CLI with paragraph reflow, and a metric to measure it. Reflow markers are heuristic and CA/KS-tuned; refinement (and per-state marker sets via `profile`) is a follow-up. The `profile` param is threaded through `paragraphs` for that future use but unused now (documented, not dead-by-accident).

**Placeholder scan:** None.

**Type consistency:** `lines_of(list[Span]) -> list[list[Span]]`, `paragraphs(list[Span], profile=None) -> list[list[Span]]`, `convert(str, str) -> str`. Reuses `render_markup` and `Span` unchanged.

**Risk:** reflow can over-split (false block-start) or under-split (missed marker). The fulltext metric in Task 4 is the empirical guard; if it regresses vs the `tagged` baseline (KS2206 0.976, CA351 0.989), report rather than merge.
