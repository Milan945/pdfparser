# Emit + Tag-Merge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Introduce the emit stage `render_markup(spans) -> str` that merges consecutive same-decoration spans into single `[D>..<D]`/`[A>..<A]` tags and keeps whitespace OUTSIDE the tags, collapsing the ~2x tag over-count toward Doctly (KS2206 tagged-similarity 0.83 -> ~0.976).

**Architecture:** A new `src/netscan/emit.py` owns turning a `list[Span]` into the markup string. It (1) applies `normalize_unicode` to each span's text, (2) merges runs of consecutive same-decoration spans (struck->D, italic->A, neither->plain) into one segment, (3) for a tagged segment, trims leading/trailing whitespace OUT of the tag (`" public "` italic -> `" [A>public<A] "`), and (4) drops tags around whitespace-only segments. `scripts/score_bill.py` replaces its inline normalize+tag loop with a single `render_markup(spans)` call. Reflow/paragraphs and the CLI come in a later slice; this slice emits one continuous string like today, just with correct tags.

**Tech Stack:** Python 3.14, pytest. No new dependencies.

**Decoration mapping (corrected ground truth):** struck -> `[D>..<D]`, italic -> `[A>..<A]`. Bold and underline produce NO tags in the Doctly bracket format and are treated as plain here.

---

## Prototype evidence (post reading-order fix)

| Bill | baseline tagged-sim | tags | merge+boundary tagged-sim | tags | gold tags |
|------|------|------|------|------|------|
| KS2206 | 0.8269 | 138D/234A | **0.9760** | 111D/114A | 97D/138A |
| CA351 | 0.9847 | 22D/21A | **0.9869** | 22D/12A | 10D/11A |

Merge is a large win on KS2206 and modest on CA (CA's deletions are interleaved with additions, so consecutive-merge cannot combine them; that residual is a later concern). Over-merging some additions (KS A 114 < gold 138) is acceptable: net tagged-similarity rises sharply.

---

## File Structure

- Create: `src/netscan/emit.py` - `render_markup(spans) -> str` + a `_decoration(span)` helper.
- Create: `tests/test_emit.py` - unit tests for merge, boundary, whitespace-only, interleaving, plus a real-bill KS assertion.
- Modify: `scripts/score_bill.py` - `our_markup` calls `render_markup`.

---

## Task 1: render_markup core (merge + boundary)

**Files:**
- Create: `src/netscan/emit.py`
- Test: `tests/test_emit.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_emit.py
from netscan.types import Span
from netscan.emit import render_markup


def _span(text, struck=False, italic=False):
    return Span(text=text, x0=0, x1=1, top=0, bottom=1,
                bold=False, italic=italic, struck=struck, underlined=False,
                confidence=1.0, source="geometry")


def test_plain_spans_concatenate_untagged():
    spans = [_span("Hello "), _span("world")]
    assert render_markup(spans) == "Hello world"


def test_consecutive_same_decoration_merge_into_one_tag():
    spans = [_span("one ", italic=True), _span("thousand", italic=True)]
    assert render_markup(spans) == "[A>one thousand<A]"


def test_consecutive_struck_merge_into_delete_tag():
    spans = [_span("five ", struck=True), _span("hundred", struck=True)]
    assert render_markup(spans) == "[D>five hundred<D]"


def test_leading_and_trailing_whitespace_sits_outside_tag():
    spans = [_span(" public disclosure ", italic=True)]
    assert render_markup(spans) == " [A>public disclosure<A] "


def test_whitespace_only_decorated_span_is_not_tagged():
    spans = [_span("a", italic=True), _span(" ", italic=True), _span("b")]
    # the lone whitespace italic span must not become an empty [A><A]
    assert render_markup(spans) == "[A>a<A] b"


def test_interleaved_delete_add_do_not_merge():
    spans = [_span("old", struck=True), _span("new", italic=True)]
    assert render_markup(spans) == "[D>old<D][A>new<A]"


def test_normalization_is_applied_to_tag_text():
    spans = [_span("party’s", italic=True)]   # curly apostrophe
    assert render_markup(spans) == "[A>party's<A]"
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/test_emit.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'netscan.emit'`

- [ ] **Step 3: Implement**

```python
# src/netscan/emit.py
"""Emit stage: render extracted Spans into NetScan bracket markup.

Turns a list[Span] into the markup string Doctly produces:
  struck  -> [D>..<D]   (deletion)
  italic  -> [A>..<A]   (addition)
  neither -> plain text
Consecutive spans of the same decoration are merged into a single tag, and
leading/trailing whitespace is kept OUTSIDE the tag so the markup hugs the
words (matching Doctly). Text is Unicode-normalized en route.

Reflow/paragraph structure is NOT applied here (later slice); this returns one
continuous string. See docs/superpowers/plans/2026-06-03-emit-tag-merge.md.
"""
from __future__ import annotations

from netscan.types import Span
from netscan.normalize import normalize_unicode

_TAGS = {"D": ("[D>", "<D]"), "A": ("[A>", "<A]")}


def _decoration(span: Span) -> str:
    """Return 'D' (struck), 'A' (italic), or '' (plain). Strike wins over italic."""
    if span.struck:
        return "D"
    if span.italic:
        return "A"
    return ""


def render_markup(spans: list[Span]) -> str:
    """Render spans into bracket markup, merging consecutive same-decoration
    runs and keeping whitespace outside tags."""
    # 1. merge consecutive same-decoration spans (normalized text)
    runs: list[list[str]] = []   # [decoration, text]
    for span in spans:
        deco = _decoration(span)
        text = normalize_unicode(span.text)
        if runs and runs[-1][0] == deco:
            runs[-1][1] += text
        else:
            runs.append([deco, text])
    # 2. render each run
    out: list[str] = []
    for deco, text in runs:
        if deco == "":
            out.append(text)
            continue
        core = text.strip()
        if not core:                     # whitespace-only -> never an empty tag
            out.append(text)
            continue
        lead = text[: len(text) - len(text.lstrip())]
        trail = text[len(text.rstrip()):]
        open_tag, close_tag = _TAGS[deco]
        out.append(f"{lead}{open_tag}{core}{close_tag}{trail}")
    return "".join(out)
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_emit.py -v`
Expected: all 7 PASS

- [ ] **Step 5: Commit**

```bash
git add src/netscan/emit.py tests/test_emit.py
git commit -m "feat: add emit.render_markup (merge same-decoration runs, whitespace outside tags)"
```

---

## Task 2: Wire into the scorer

**Files:**
- Modify: `scripts/score_bill.py`

- [ ] **Step 1: Replace the inline tagging in `our_markup`**

`our_markup` currently builds spans, normalizes per span, and wraps each in tags inline. Replace its per-span tagging loop with a single `render_markup` call. The function becomes:

```python
def our_markup(pdf_path: str) -> str:
    from netscan.structure import strip_gutter
    from netscan.profiles import PROFILES
    from netscan.emit import render_markup
    profile = PROFILES[_state_for(pdf_path)]
    spans = []
    for geo in open_pdf(Path(pdf_path)):
        geo = strip_gutter(geo, profile)
        spans.extend(extract_page_spans(geo))
    return render_markup(spans)
```

(The `normalize_unicode` import is no longer needed in `score_bill.py`; `render_markup` applies it. Remove the now-unused import if present.)

- [ ] **Step 2: Re-measure**

Run: `PYTHONIOENCODING=utf-8 python scripts/score_bill.py`
Expected, vs current master:
- KS2206 `tagged` similarity rises from 0.8269 to ~0.976; its A tag count drops from 234 toward ~114.
- CA351 `tagged` rises from 0.9847 to ~0.987.
- `content` similarity is unchanged (same words, same normalization): KS2203 0.9984, KS2206 0.9977, CA351 0.9922.
Record all three bills' content + tagged similarity and tag counts.

- [ ] **Step 3: Commit**

```bash
git add scripts/score_bill.py
git commit -m "feat: render scorer output via emit.render_markup; re-measure"
```

---

## Task 3: Real-bill regression

**Files:**
- Modify: `tests/test_emit.py`

- [ ] **Step 1: Add a real-bill assertion**

```python
# tests/test_emit.py  (add)
from pathlib import Path
import pytest
from netscan.pdf_backend import open_pdf
from netscan.geometry import extract_page_spans
from netscan.structure import strip_gutter
from netscan.profiles import PROFILES

_KS = Path("samples/there samples/2025_2026_16_2_2_002206_0_4_1_20250203_0.pdf")


@pytest.mark.skipif(not _KS.exists(), reason="KS sample bill not present")
def test_ks_merge_collapses_tag_count():
    spans = []
    for geo in open_pdf(_KS):
        geo = strip_gutter(geo, PROFILES["KS"])
        spans.extend(extract_page_spans(geo))
    out = render_markup(spans)
    # merged output has far fewer addition tags than the unmerged 234
    assert out.count("[A>") < 150
    # tags must not wrap leading spaces (whitespace stays outside)
    assert "[A> " not in out and "[D> " not in out
    assert " <A]" not in out and " <D]" not in out
```

- [ ] **Step 2: Run**

Run: `python -m pytest tests/test_emit.py -v`
Expected: all PASS (8 tests).

- [ ] **Step 3: Commit**

```bash
git add tests/test_emit.py
git commit -m "test: lock KS tag-merge count + whitespace-outside-tags on real bill"
```

---

## Self-Review

**Spec coverage:** Creates the emit stage with merge + boundary; wires it into the scorer; locks behavior with unit + real-bill tests. Reflow and CLI are explicitly deferred.

**Placeholder scan:** None.

**Type consistency:** `render_markup(list[Span]) -> str`, `_decoration(Span) -> str` returning `"D"|"A"|""`. Uses `Span` fields `struck`/`italic`/`text` (confirmed in `src/netscan/types.py`).

**Known follow-ups (not gaps):** CA deletions remain fragmented because they interleave with additions (consecutive-merge cannot join them) - a later refinement. Over-merging additions that Doctly splits is accepted (net tagged-similarity rises). Strike-precedence in `_decoration` matches `geometry.line_decoration`.
