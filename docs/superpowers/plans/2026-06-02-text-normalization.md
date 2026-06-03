# Text Normalization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Normalize the Unicode quirks in extracted bill text (curly quotes, fraction slash, zero-width characters, non-breaking spaces) to the plain forms Doctly emits, raising CA351 char-similarity from ~0.951 toward ~0.979 without harming KS.

**Architecture:** A new `src/netscan/normalize.py` exposes a single pure function `normalize_unicode(text: str) -> str`. It is applied to each span's text at emit time (in `scripts/score_bill.py` now, and the real emitter later), after gutter stripping, before markup tags are added. Pure string transform, no geometry. Deliberately excludes ligature recovery and small-caps uppercasing (see Out of Scope).

**Tech Stack:** Python 3.14, pytest. No new dependencies.

---

## Out of Scope (deliberate, measured decisions)

- **Ligature recovery** (`officer` -> `ofcfier`): verified there are NO U+FB00-FB04 codepoints in the extraction; the glyph is already decomposed and reordered to raw ASCII during extraction. A presentation-form char map would be dead code. This belongs to a later Unicode-cascade / reading-order slice.
- **Small-caps uppercasing** (`california legislature` -> `CALIFORNIA LEGISLATURE`): font-aware, needs `Char.fontname`, not a pure string transform. Separate slice.
- **Running header/footer strip** and **staggered-fraction reassembly**: geometry-level. Separate slices.
- **Dashes** (en/em U+2013/U+2014): Doctly KEEPS these; do NOT normalize them.

---

## File Structure

- Create: `src/netscan/normalize.py` - `normalize_unicode(text)` + the character maps.
- Create: `tests/test_normalize.py` - unit tests per character class + a real-bill CA assertion.
- Modify: `scripts/score_bill.py` - apply `normalize_unicode` to `s.text` inside `our_markup`.

---

## Task 1: normalize_unicode core

**Files:**
- Create: `src/netscan/normalize.py`
- Test: `tests/test_normalize.py`

Map curly single/double quotes to ASCII `'`/`"`, fraction slash U+2044 to `/`, non-breaking space U+00A0 to a normal space, and delete zero-width characters (U+200B ZERO WIDTH SPACE, U+200C ZWNJ, U+200D ZWJ, U+FEFF BOM/ZWNBSP). Leave all other characters (including dashes) untouched.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_normalize.py
from netscan.normalize import normalize_unicode


def test_curly_single_quotes_become_ascii_apostrophe():
    assert normalize_unicode("party’s agent") == "party's agent"
    assert normalize_unicode("‘quoted’") == "'quoted'"


def test_curly_double_quotes_become_ascii_quote():
    assert normalize_unicode("“Party”") == '"Party"'


def test_fraction_slash_becomes_ascii_slash():
    assert normalize_unicode("a 2⁄3 vote") == "a 2/3 vote"


def test_nbsp_becomes_normal_space():
    assert normalize_unicode("(a)  The") == "(a)  The"


def test_zero_width_characters_are_removed():
    assert normalize_unicode("no.​The") == "no.The"
    assert normalize_unicode("a‌b‍﻿c") == "abc"


def test_dashes_and_plain_text_are_untouched():
    assert normalize_unicode("2025–26 — session") == "2025–26 — session"
    assert normalize_unicode("plain ascii text") == "plain ascii text"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_normalize.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'netscan.normalize'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/netscan/normalize.py
"""Unicode normalization of extracted bill text to Doctly's plain forms.

Pure string transform applied per span at emit time, after gutter stripping
and before markup tags are added. Covers the safe, high-frequency quirks
measured on real bills (curly quotes, fraction slash, zero-width chars, NBSP).

Deliberately excludes ligature recovery (the extraction yields no U+FB00-FB04
codepoints to map), small-caps uppercasing (font-aware), and dash changes
(Doctly keeps en/em dashes). See docs/superpowers/plans/2026-06-02-text-normalization.md.
"""
from __future__ import annotations

# Curly quotes -> ASCII. Single (incl. low-9 and high-reversed) -> ' ; double -> "
_QUOTES = {
    0x2018: "'", 0x2019: "'", 0x201A: "'", 0x201B: "'",
    0x201C: '"', 0x201D: '"', 0x201E: '"', 0x201F: '"',
}
# Zero-width characters to delete entirely.
_ZERO_WIDTH = {0x200B, 0x200C, 0x200D, 0xFEFF}

_FRACTION_SLASH = 0x2044
_NBSP = 0x00A0


def normalize_unicode(text: str) -> str:
    """Return text with curly quotes, fraction slash, NBSP, and zero-width
    characters normalized to their plain ASCII forms. All other characters
    (including en/em dashes) are left unchanged."""
    out: list[str] = []
    for ch in text:
        code = ord(ch)
        if code in _ZERO_WIDTH:
            continue
        if code in _QUOTES:
            out.append(_QUOTES[code])
        elif code == _FRACTION_SLASH:
            out.append("/")
        elif code == _NBSP:
            out.append(" ")
        else:
            out.append(ch)
    return "".join(out)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_normalize.py -v`
Expected: PASS (all 6 tests)

- [ ] **Step 5: Commit**

```bash
git add src/netscan/normalize.py tests/test_normalize.py
git commit -m "feat: add normalize_unicode (quotes, fraction slash, NBSP, zero-width)"
```

---

## Task 2: Real-bill CA regression

**Files:**
- Test: `tests/test_normalize.py`

Lock the real-bill effect: after gutter strip + normalization, the CA text contains the plain forms and none of the curly/zero-width/fraction-slash quirks.

- [ ] **Step 1: Write the test**

```python
# tests/test_normalize.py  (add)
from pathlib import Path
import pytest
from netscan.pdf_backend import open_pdf
from netscan.geometry import extract_page_spans
from netscan.structure import strip_gutter
from netscan.profiles import PROFILES

_CA = Path("samples/there samples/2025_2026_5_2_2_000351_0_4_1_20250130_0.pdf")


@pytest.mark.skipif(not _CA.exists(), reason="CA sample bill not present")
def test_ca_real_bill_normalized_text_has_plain_forms():
    parts: list[str] = []
    for geo in open_pdf(_CA):
        geo = strip_gutter(geo, PROFILES["CA"])
        for s in extract_page_spans(geo):
            parts.append(normalize_unicode(s.text))
    text = "".join(parts)
    # plain forms present
    assert "party's agent" in text          # was party’s agent
    assert '"Party"' in text                 # was curly double quotes
    assert "2/3 vote" in text                # was 2⁄3 vote (numerator may
    #                                          still be staggered; the slash itself
    #                                          must be ASCII '/')
    # quirks gone
    assert "’" not in text and "‘" not in text
    assert "“" not in text and "”" not in text
    assert "⁄" not in text
    assert "​" not in text
    assert " " not in text
```

Note on the `2/3 vote` assertion: the fraction numerator may still be a separate staggered span (reassembly is a later slice), so do NOT assert the full literal if it proves brittle — if `"2/3 vote"` is not contiguous, fall back to asserting `"/" ` replaced the fraction slash by checking `"⁄" not in text` (already covered) and that the digit `2` and a `/` appear. Run it first; keep the strongest assertion that passes.

- [ ] **Step 2: Run test**

Run: `python -m pytest tests/test_normalize.py::test_ca_real_bill_normalized_text_has_plain_forms -v`
Expected: PASS. If `"2/3 vote"` is not contiguous because of the staggered numerator, weaken just that line to `assert "/" in text and "⁄" not in text` and re-run.

- [ ] **Step 3: Commit**

```bash
git add tests/test_normalize.py
git commit -m "test: lock CA real-bill Unicode normalization"
```

---

## Task 3: Wire into the scorer and re-measure

**Files:**
- Modify: `scripts/score_bill.py`

Apply `normalize_unicode` to each span's text inside `our_markup`, after gutter strip, before tagging.

- [ ] **Step 1: Update `our_markup`**

In `scripts/score_bill.py`, inside `our_markup`, add the import and apply normalization to `s.text`. The loop body becomes:

```python
def our_markup(pdf_path: str) -> str:
    from netscan.structure import strip_gutter
    from netscan.profiles import PROFILES
    from netscan.normalize import normalize_unicode
    profile = PROFILES[_state_for(pdf_path)]
    out: list[str] = []
    for geo in open_pdf(Path(pdf_path)):
        geo = strip_gutter(geo, profile)
        for s in extract_page_spans(geo):
            t = normalize_unicode(s.text)
            if s.struck:
                t = f"[D>{t}<D]"
            elif s.italic:
                t = f"[A>{t}<A]"
            out.append(t)
    return "".join(out)
```

- [ ] **Step 2: Re-run the scorer**

Run: `PYTHONIOENCODING=utf-8 python scripts/score_bill.py`
Expected: CA351 char_similarity rises from 0.9600 toward ~0.979. KS2203 and KS2206 stay at ~0.9984 / ~0.9977 (they have none of these characters, so unchanged within rounding). Record the three numbers.

- [ ] **Step 3: Commit**

```bash
git add scripts/score_bill.py
git commit -m "feat: apply Unicode normalization in score_bill; re-measure"
```

---

## Self-Review

**Spec coverage:** Covers buckets 1 (quotes), 2 (fraction slash), 6 (zero-width) and NBSP from the CA divergence analysis. Small-caps, header strip, ligature, and staggered-fraction reassembly are explicitly Out of Scope above with reasons.

**Placeholder scan:** No TBD/placeholder steps. Task 2 gives an explicit, bounded fallback for one assertion (verify-then-weaken) rather than a vague "handle edge cases".

**Type consistency:** `normalize_unicode(text: str) -> str` is used identically in tests and in `score_bill.py`. Character-map names (`_QUOTES`, `_ZERO_WIDTH`, `_FRACTION_SLASH`, `_NBSP`) are internal and consistent.

**Contract note for a later slice:** Normalization changes content characters, so the future round-trip-vs-source verifier must apply `normalize_unicode` to BOTH sides before comparing, otherwise every quote would be flagged as a content change. Recorded here so the verifier slice honors it.
