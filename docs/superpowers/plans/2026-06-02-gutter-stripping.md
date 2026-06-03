# Gutter Stripping Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Strip per-state line-number gutters from extracted bill geometry so our output stops fusing line numbers into body text (e.g. `74-1050,297` -> `74-50,297`) and converges toward the Doctly gold output.

**Architecture:** A new `profiles.py` holds a `StateProfile` describing each state's gutter style. A new `structure.py` exposes `strip_gutter(geo, profile) -> PageGeometry` that removes gutter `Char`s before span extraction, leaving the rest of the pipeline (`extract_page_spans`, `detect_conflicts`) untouched. KS uses a sequential line-counter strip; CA uses a `line N` regex strip. `scripts/score_bill.py` is updated to apply the strip so the gain is measured against the gold files.

**Tech Stack:** Python 3.14, pdfplumber (via existing `pdf_backend`), pytest, dataclasses.

---

## File Structure

- Create: `src/netscan/profiles.py` - `StateProfile` dataclass + `PROFILES` registry (CA, KS).
- Create: `src/netscan/structure.py` - `strip_gutter` + per-state helpers, operating on `PageGeometry.chars`.
- Create: `tests/test_structure.py` - unit tests on synthetic `Char` fixtures + real-bill regression assertions.
- Modify: `scripts/score_bill.py` - apply `strip_gutter` in `our_markup` so scores reflect the strip.

Data types already in repo (do not redefine):
- `netscan.pdf_backend.Char(text, x0, x1, top, bottom, fontname, size)`
- `netscan.pdf_backend.PageGeometry(width, height, chars, rule_lines, image_count)`

---

## Task 1: StateProfile registry

**Files:**
- Create: `src/netscan/profiles.py`
- Test: `tests/test_structure.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_structure.py
from netscan.profiles import PROFILES, StateProfile


def test_profiles_registry_has_ca_and_ks():
    assert set(PROFILES) >= {"CA", "KS"}
    assert isinstance(PROFILES["CA"], StateProfile)
    assert PROFILES["CA"].gutter == "ca_line_label"
    assert PROFILES["KS"].gutter == "ks_line_numbers"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_structure.py::test_profiles_registry_has_ca_and_ks -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'netscan.profiles'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/netscan/profiles.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_structure.py::test_profiles_registry_has_ca_and_ks -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/netscan/profiles.py tests/test_structure.py
git commit -m "feat: add per-state StateProfile registry (CA, KS)"
```

---

## Task 2: Line clustering helper

**Files:**
- Create: `src/netscan/structure.py`
- Test: `tests/test_structure.py`

Group chars into physical lines by their `top` coordinate (same tolerance as `geometry.SAME_LINE_TOL = 3.0`), each line x-sorted. This is the unit both strip strategies operate on.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_structure.py  (add)
from netscan.pdf_backend import Char
from netscan.structure import line_clusters


def _char(text, x0, top):
    return Char(text=text, x0=x0, x1=x0 + 4, top=top, bottom=top + 10,
                fontname="Times", size=10.0)


def test_line_clusters_groups_by_top_and_sorts_by_x0():
    chars = [_char("b", 50, 100), _char("a", 40, 100.5), _char("c", 30, 130)]
    lines = line_clusters(chars)
    assert [ "".join(ch.text for ch in line) for line in lines ] == ["ab", "c"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_structure.py::test_line_clusters_groups_by_top_and_sorts_by_x0 -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'netscan.structure'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/netscan/structure.py
"""Structural processing: strip per-state line-number gutters from geometry.

Operates on PageGeometry.chars BEFORE span extraction, so the rest of the
pipeline (extract_page_spans, detect_conflicts) is unaffected. See
docs/superpowers/plans/2026-06-02-gutter-stripping.md.
"""
from __future__ import annotations
import re
from dataclasses import replace

from netscan.pdf_backend import Char, PageGeometry
from netscan.profiles import StateProfile

SAME_LINE_TOL = 3.0


def line_clusters(chars: list[Char]) -> list[list[Char]]:
    """Group chars into physical lines by `top` (within SAME_LINE_TOL),
    each line sorted left-to-right by x0, lines ordered top-to-bottom."""
    out: list[list[Char]] = []
    for ch in sorted(chars, key=lambda c: c.top):
        if out and abs(ch.top - out[-1][0].top) <= SAME_LINE_TOL:
            out[-1].append(ch)
        else:
            out.append([ch])
    for line in out:
        line.sort(key=lambda c: c.x0)
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_structure.py::test_line_clusters_groups_by_top_and_sorts_by_x0 -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/netscan/structure.py tests/test_structure.py
git commit -m "feat: add line_clusters helper for structural processing"
```

---

## Task 3: CA gutter strip (`line N` labels)

**Files:**
- Modify: `src/netscan/structure.py`
- Test: `tests/test_structure.py`

CA operative lines begin with chars spelling ` line <n> ` (leading space, "line", space, digits, space). Drop the leading run of chars whose accumulated text matches `^\s*line\s+\d+\s+`. Lines that do not match (digest/front matter) are left intact.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_structure.py  (add)
from netscan.structure import strip_gutter
from netscan.profiles import PROFILES


def _line(text, top, x0=20.0):
    chars, x = [], x0
    for chx in text:
        chars.append(Char(text=chx, x0=x, x1=x + 4, top=top, bottom=top + 10,
                          fontname="Times", size=10.0))
        x += 4
    return chars


def test_ca_strip_removes_line_label_prefix():
    chars = _line(" line 1 SECTION 1. Section 84308", 100)
    chars += _line(" line 2 amended to read:", 112)
    geo = PageGeometry(width=600, height=800, chars=chars,
                       rule_lines=[], image_count=0)
    out = strip_gutter(geo, PROFILES["CA"])
    text_by_line = ["".join(c.text for c in line)
                    for line in line_clusters(out.chars)]
    assert text_by_line == ["SECTION 1. Section 84308", "amended to read:"]


def test_ca_strip_leaves_unlabeled_frontmatter_intact():
    chars = _line("The Political Reform Act of 1974", 100, x0=48.0)
    geo = PageGeometry(width=600, height=800, chars=chars,
                       rule_lines=[], image_count=0)
    out = strip_gutter(geo, PROFILES["CA"])
    assert "".join(c.text for c in out.chars) == "The Political Reform Act of 1974"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_structure.py -k ca_strip -v`
Expected: FAIL with `AttributeError` / `ImportError` (strip_gutter not defined)

- [ ] **Step 3: Write minimal implementation**

```python
# src/netscan/structure.py  (add)

_CA_LABEL = re.compile(r"^\s*line\s+\d+\s+", re.IGNORECASE)


def _strip_ca(chars: list[Char]) -> list[Char]:
    keep: list[Char] = []
    for line in line_clusters(chars):
        text = "".join(c.text for c in line)
        m = _CA_LABEL.match(text)
        keep.extend(line[m.end():] if m else line)
    return keep


def strip_gutter(geo: PageGeometry, profile: StateProfile) -> PageGeometry:
    """Return a copy of geo with the line-number gutter chars removed."""
    if profile.gutter == "ca_line_label":
        kept = _strip_ca(geo.chars)
    elif profile.gutter == "ks_line_numbers":
        kept = _strip_ks(geo.chars)
    else:
        kept = list(geo.chars)
    return replace(geo, chars=kept)
```

Note: `m.end()` is a character offset into the joined line text, and the line is one `Char` per character, so `line[m.end():]` drops exactly the matched prefix chars. `_strip_ks` is added in Task 4; define a temporary stub now so the module imports:

```python
# src/netscan/structure.py  (add, temporary - replaced in Task 4)
def _strip_ks(chars: list[Char]) -> list[Char]:
    return list(chars)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_structure.py -k ca_strip -v`
Expected: PASS (both CA tests)

- [ ] **Step 5: Commit**

```bash
git add src/netscan/structure.py tests/test_structure.py
git commit -m "feat: strip CA 'line N' gutter labels"
```

---

## Task 4: KS gutter strip (sequential line counter)

**Files:**
- Modify: `src/netscan/structure.py`
- Test: `tests/test_structure.py`

KS line numbers are bare integers fused at the start of each operative line, incrementing 1, 2, 3 ... down the page at the body left margin. Strategy: find where numbering starts (first line whose leading digit-run starts with "1" at the left margin), then for each subsequent line strip the leading prefix equal to `str(counter)` if present, incrementing `counter`. Stripping the exact counter prefix (not the whole digit run) preserves legitimate leading digits: line 7 `725-4119a` -> strip `7` -> `25-4119a`; line 10 `1050,297` -> strip `10` -> `50,297`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_structure.py  (add)

def test_ks_strip_removes_sequential_counter_prefix():
    # line numbers 1,2,3 fused at start; body left margin x0=55
    chars = _line("1AN ACT concerning", 186, x0=55.0)
    chars += _line("2governmental ethics", 198, x0=55.0)
    chars += _line("3Kansas public", 209, x0=55.0)
    geo = PageGeometry(width=600, height=800, chars=chars,
                       rule_lines=[], image_count=0)
    out = strip_gutter(geo, PROFILES["KS"])
    text_by_line = ["".join(c.text for c in line)
                    for line in line_clusters(out.chars)]
    assert text_by_line == ["AN ACT concerning",
                            "governmental ethics",
                            "Kansas public"]


def test_ks_strip_strips_only_counter_not_following_digits():
    # line 7 begins with statute number 25-4119a -> "725-4119a"
    chars = _line("1first", 100, x0=55.0)
    chars += _line("2second", 112, x0=55.0)
    chars += _line("3third", 124, x0=55.0)
    chars += _line("4fourth", 136, x0=55.0)
    chars += _line("5fifth", 148, x0=55.0)
    chars += _line("6sixth", 160, x0=55.0)
    chars += _line("725-4119a", 172, x0=55.0)
    geo = PageGeometry(width=600, height=800, chars=chars,
                       rule_lines=[], image_count=0)
    out = strip_gutter(geo, PROFILES["KS"])
    last = "".join(c.text for c in line_clusters(out.chars)[-1])
    assert last == "25-4119a"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_structure.py -k ks_strip -v`
Expected: FAIL (stub `_strip_ks` returns chars unchanged, so prefixes remain)

- [ ] **Step 3: Write minimal implementation**

Replace the temporary `_strip_ks` stub with:

```python
# src/netscan/structure.py  (replace the Task 3 stub)
def _strip_ks(chars: list[Char]) -> list[Char]:
    lines = line_clusters(chars)
    texts = ["".join(c.text for c in line) for line in lines]
    # numbering starts at the first line whose leading digit-run begins with "1"
    start = None
    for i, t in enumerate(texts):
        lead = re.match(r"\d+", t)
        if lead and lead.group().startswith("1"):
            start = i
            break
    if start is None:
        return list(chars)
    keep: list[Char] = []
    counter = 1
    for i, line in enumerate(lines):
        if i < start:
            keep.extend(line)
            continue
        prefix = str(counter)
        if texts[i].startswith(prefix):
            keep.extend(line[len(prefix):])
            counter += 1
        else:
            keep.extend(line)
    return keep
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_structure.py -k ks_strip -v`
Expected: PASS (both KS tests)

- [ ] **Step 5: Commit**

```bash
git add src/netscan/structure.py tests/test_structure.py
git commit -m "feat: strip KS sequential line-number gutter"
```

---

## Task 5: Real-bill regression (the 74-50,297 fix)

**Files:**
- Test: `tests/test_structure.py`

Lock the concrete bug fix against the real KS bill so it cannot regress.

- [ ] **Step 1: Write the failing-then-passing test**

```python
# tests/test_structure.py  (add)
from pathlib import Path
import pytest
from netscan.pdf_backend import open_pdf
from netscan.geometry import extract_page_spans

_KS = Path("samples/there samples/2025_2026_16_2_2_002206_0_4_1_20250203_0.pdf")


@pytest.mark.skipif(not _KS.exists(), reason="KS sample bill not present")
def test_ks_gutter_strip_fixes_fused_statute_number():
    page = open_pdf(_KS)[0]
    stripped = strip_gutter(page, PROFILES["KS"])
    text = "".join(s.text for s in extract_page_spans(stripped))
    assert "74-50,297" in text
    assert "74-1050,297" not in text
```

- [ ] **Step 2: Run test**

Run: `python -m pytest tests/test_structure.py::test_ks_gutter_strip_fixes_fused_statute_number -v`
Expected: PASS (implementation from Task 4 already makes this true). If it fails, the counter logic needs review before proceeding.

- [ ] **Step 3: Commit**

```bash
git add tests/test_structure.py
git commit -m "test: lock the 74-50,297 KS gutter-strip regression"
```

---

## Task 6: Wire strip into the scorer and re-measure

**Files:**
- Modify: `scripts/score_bill.py`

Apply `strip_gutter` in the scorer so the gain is measured against gold. State is inferred from the filename (`*_5_*` and `351` -> CA; KS otherwise) — these three sample bills only.

- [ ] **Step 1: Update `our_markup` to strip per state**

Replace the body of `our_markup` in `scripts/score_bill.py` with:

```python
def _state_for(pdf_path: str) -> str:
    name = Path(pdf_path).name
    return "CA" if "_5_2_2_000351_" in name else "KS"


def our_markup(pdf_path: str) -> str:
    from netscan.structure import strip_gutter
    from netscan.profiles import PROFILES
    profile = PROFILES[_state_for(pdf_path)]
    out: list[str] = []
    for geo in open_pdf(Path(pdf_path)):
        geo = strip_gutter(geo, profile)
        for s in extract_page_spans(geo):
            t = s.text
            if s.struck:
                t = f"[D>{t}<D]"
            elif s.italic:
                t = f"[A>{t}<A]"
            out.append(t)
    return "".join(out)
```

- [ ] **Step 2: Re-run the scorer**

Run: `PYTHONIOENCODING=utf-8 python scripts/score_bill.py`
Expected: char_similarity rises on all three bills vs the recorded baseline (KS2203 0.9237, KS2206 0.8393, CA351 0.7661). KS gains should be clear; CA should gain the most (its `line N` labels are many characters).

- [ ] **Step 3: Commit**

```bash
git add scripts/score_bill.py
git commit -m "feat: apply per-state gutter strip in score_bill; re-measure"
```

---

## Self-Review

**Spec coverage:** This plan covers only the gutter-strip slice (slice 1 of the structural layer in `docs/research/2026-06-02-doctly-and-faithful-extraction.md` and the memory status note). Boilerplate scoping, tag-boundary/merge, reflow, and normalization are explicitly out of scope and will get their own plans.

**Placeholder scan:** The only temporary placeholder is the `_strip_ks` stub in Task 3, which is required so the module imports before Task 4 implements it; Task 4 replaces it. No "TBD"/"handle edge cases" steps remain.

**Type consistency:** `Char`/`PageGeometry` fields match `pdf_backend`. `StateProfile.gutter` values `"ca_line_label"`/`"ks_line_numbers"` are used identically in `profiles.py` and `structure.py`. `line_clusters`, `strip_gutter`, `_strip_ca`, `_strip_ks` signatures are consistent across tasks.

**Known limitation (deferred, not a gap):** KS counter strip assumes per-page numbering restart is handled by the "starts with 1" detector firing once per page (open_pdf yields one PageGeometry per page, and the scorer/strip run per page, so the counter naturally resets each page). If a page's body genuinely starts mid-document without a line "1", the detector will not fire and that page is left unstripped rather than mis-stripped — the safe failure direction. A later slice can refine start-detection using the left-margin x band if any sample bill needs it.
