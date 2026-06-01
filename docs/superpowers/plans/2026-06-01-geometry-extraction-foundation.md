# Geometry Extraction Foundation & Validation Gate — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and validate the deterministic geometry path that reads a native legislative-bill PDF page and emits formatted `Span`s (bold, italic, strikethrough, underline) — with a go/no-go gate confirming strike/underline really appear as vector rule lines in real bills.

**Architecture:** MIT PDF stack (`pdfplumber`) is isolated behind a `pdf_backend` adapter. `triage` classifies pages native vs scanned. `geometry` takes bold/italic directly from font names and detects strike/underline by correlating horizontal rule lines against glyph boxes. The risky premise (strike/underline = vector rule lines) is validated against real bills in a dedicated spike before downstream stages are built on it.

**Tech Stack:** Python 3.11+, `pdfplumber` (PDF geometry, MIT), `reportlab` (synthetic test-fixture PDFs, BSD), `pytest`. No model/API calls in this plan.

**Scope:** This is plan 1 of a multi-plan build. Out of scope here: conflict detection, reconcile, emit, verify, CLI, GUI, VLM/OCR (separate plans). This plan ends with a validated `geometry.extract_page_spans()` and a written gate decision.

---

## File Structure

```
pyproject.toml                          deps + pytest config
src/netscan/__init__.py
src/netscan/types.py                    Span dataclass (core spine type)
src/netscan/pdf_backend.py              ONLY module importing pdfplumber
src/netscan/triage.py                   native vs scanned classification
src/netscan/geometry.py                 font-flag + rule-line correlation → Spans
tests/fixtures/make_fixtures.py         reportlab synthetic-PDF generator
tests/test_pdf_backend.py
tests/test_triage.py
tests/test_geometry.py
docs/superpowers/spikes/2026-06-01-rule-line-gate.md   gate decision (Task 9)
```

Each module has one responsibility. `pdf_backend` is the only place `pdfplumber` is imported, so the library is swappable.

---

### Task 1: Project scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `src/netscan/__init__.py`
- Create: `tests/__init__.py`

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[project]
name = "netscan-converter"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "pdfplumber>=0.11",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "reportlab>=4.0",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]

[tool.setuptools.packages.find]
where = ["src"]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"
```

- [ ] **Step 2: Create empty package markers**

Create `src/netscan/__init__.py` containing a single line:
```python
"""NetScan legislative-bill PDF → markup converter."""
```
Create `tests/__init__.py` as an empty file.

- [ ] **Step 3: Install dependencies**

Run: `python -m pip install -e ".[dev]"`
Expected: installs pdfplumber, pytest, reportlab; ends with "Successfully installed".

- [ ] **Step 4: Verify pytest collects nothing yet without error**

Run: `python -m pytest -q`
Expected: "no tests ran" (exit code 5 is acceptable here).

- [ ] **Step 5: Commit**

```bash
git init
git add pyproject.toml src/netscan/__init__.py tests/__init__.py
git commit -m "chore: scaffold netscan converter project"
```
(If the user declined git, skip the git commands for every Commit step in this plan.)

---

### Task 2: Span core type

**Files:**
- Create: `src/netscan/types.py`
- Test: `tests/test_types.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_types.py
from netscan.types import Span


def test_span_defaults_are_unformatted():
    s = Span(text="hello", x0=0.0, x1=10.0, top=0.0, bottom=8.0)
    assert s.bold is False
    assert s.italic is False
    assert s.struck is False
    assert s.underlined is False
    assert s.confidence == 1.0
    assert s.source == "geometry"


def test_span_records_formatting_and_source():
    s = Span(text="x", x0=0, x1=1, top=0, bottom=1,
             struck=True, confidence=0.4, source="vlm")
    assert s.struck is True
    assert s.confidence == 0.4
    assert s.source == "vlm"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_types.py -v`
Expected: FAIL with "No module named 'netscan.types'" / ImportError.

- [ ] **Step 3: Write minimal implementation**

```python
# src/netscan/types.py
from dataclasses import dataclass
from typing import Literal

Source = Literal["geometry", "font_flag", "vlm", "ocr"]


@dataclass
class Span:
    """One run of text with its detected formatting and provenance."""
    text: str
    x0: float
    x1: float
    top: float
    bottom: float
    bold: bool = False
    italic: bool = False
    struck: bool = False
    underlined: bool = False
    confidence: float = 1.0
    source: Source = "geometry"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_types.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add src/netscan/types.py tests/test_types.py
git commit -m "feat: add Span core type"
```

---

### Task 3: Synthetic fixture generator

Generates real PDFs with known formatting so geometry logic can be unit-tested deterministically. Strike/underline are drawn as real vector lines — this validates the *correlation math*, not the real-world premise (that is Task 9).

**Files:**
- Create: `tests/fixtures/__init__.py` (empty)
- Create: `tests/fixtures/make_fixtures.py`
- Test: `tests/test_fixtures.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_fixtures.py
from pathlib import Path
from tests.fixtures.make_fixtures import build_formatted_pdf


def test_build_formatted_pdf_creates_file(tmp_path):
    out = tmp_path / "sample.pdf"
    build_formatted_pdf(out)
    assert out.exists()
    assert out.stat().st_size > 0
    # PDF magic bytes
    assert out.read_bytes()[:5] == b"%PDF-"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_fixtures.py -v`
Expected: FAIL with ImportError (module not found).

- [ ] **Step 3: Write minimal implementation**

```python
# tests/fixtures/make_fixtures.py
"""Generate synthetic legislative-style PDFs with known formatting.

Layout (single page, points; reportlab origin is bottom-left):
  y=720  "PLAIN" Helvetica            -> unformatted
  y=700  "BOLDWORD" Helvetica-Bold    -> bold
  y=680  "ITALICWORD" Helvetica-Oblique -> italic
  y=660  "STRUCK" + horizontal line through mid-glyph -> strikethrough
  y=640  "ADDED" + horizontal line at baseline        -> underline
"""
from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

FONT_SIZE = 12


def build_formatted_pdf(path: Path) -> None:
    c = canvas.Canvas(str(path), pagesize=letter)

    def draw(text: str, x: float, y: float, font: str = "Helvetica") -> float:
        c.setFont(font, FONT_SIZE)
        c.drawString(x, y, text)
        return c.stringWidth(text, font, FONT_SIZE)

    draw("PLAIN", 72, 720)
    draw("BOLDWORD", 72, 700, "Helvetica-Bold")
    draw("ITALICWORD", 72, 680, "Helvetica-Oblique")

    # STRUCK: line through vertical middle of glyphs (~0.35 * font size above baseline)
    w = draw("STRUCK", 72, 660)
    c.setLineWidth(0.6)
    c.line(72, 660 + FONT_SIZE * 0.35, 72 + w, 660 + FONT_SIZE * 0.35)

    # ADDED: line just below baseline (underline)
    w = draw("ADDED", 72, 640)
    c.line(72, 640 - 1.5, 72 + w, 640 - 1.5)

    c.showPage()
    c.save()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_fixtures.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/fixtures/__init__.py tests/fixtures/make_fixtures.py tests/test_fixtures.py
git commit -m "test: add synthetic formatted-PDF fixture generator"
```

---

### Task 4: pdf_backend adapter

The only module importing pdfplumber. Exposes normalized geometry: chars with bboxes + font names, and horizontal rule lines. Normalizes pdfplumber `lines` AND thin `rects` into one `RuleLine` list (drafting tools emit underlines as either).

**Files:**
- Create: `src/netscan/pdf_backend.py`
- Test: `tests/test_pdf_backend.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_pdf_backend.py
from netscan.pdf_backend import open_pdf, PageGeometry, Char, RuleLine
from tests.fixtures.make_fixtures import build_formatted_pdf


def test_extract_chars_and_lines(tmp_path):
    pdf = tmp_path / "s.pdf"
    build_formatted_pdf(pdf)
    pages = open_pdf(pdf)
    assert len(pages) == 1
    geo = pages[0]
    assert isinstance(geo, PageGeometry)

    text = "".join(ch.text for ch in geo.chars)
    assert "STRUCK" in text
    assert "ADDED" in text

    # every char has a positive-width bbox and a font name
    for ch in geo.chars:
        assert ch.x1 > ch.x0
        assert ch.bottom > ch.top
        assert isinstance(ch.fontname, str) and ch.fontname

    # at least the two rule lines we drew are present and horizontal
    assert len(geo.rule_lines) >= 2
    for ln in geo.rule_lines:
        assert ln.x1 > ln.x0
        assert abs(ln.bottom - ln.top) < 2.0  # horizontal
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_pdf_backend.py -v`
Expected: FAIL with ImportError.

- [ ] **Step 3: Write minimal implementation**

```python
# src/netscan/pdf_backend.py
"""Thin adapter over pdfplumber. The ONLY module that imports pdfplumber,
so the PDF library can be swapped without touching downstream stages.

All coordinates use pdfplumber's top-down system: `top` is distance from the
top of the page, `bottom = top + height`, y increases downward.
"""
from dataclasses import dataclass, field
from pathlib import Path

import pdfplumber

MAX_RULE_HEIGHT = 2.5  # pts; lines/rects thinner than this count as horizontal rules


@dataclass
class Char:
    text: str
    x0: float
    x1: float
    top: float
    bottom: float
    fontname: str
    size: float


@dataclass
class RuleLine:
    x0: float
    x1: float
    top: float
    bottom: float

    @property
    def y_mid(self) -> float:
        return (self.top + self.bottom) / 2.0


@dataclass
class PageGeometry:
    width: float
    height: float
    chars: list[Char] = field(default_factory=list)
    rule_lines: list[RuleLine] = field(default_factory=list)
    image_count: int = 0


def _horizontal_rules(page) -> list[RuleLine]:
    rules: list[RuleLine] = []
    # pdfplumber lines: explicit vector lines
    for ln in page.lines:
        if abs(ln["bottom"] - ln["top"]) <= MAX_RULE_HEIGHT and ln["x1"] > ln["x0"]:
            rules.append(RuleLine(ln["x0"], ln["x1"], ln["top"], ln["bottom"]))
    # pdfplumber rects: thin filled rectangles are often underlines/strikes
    for r in page.rects:
        if abs(r["bottom"] - r["top"]) <= MAX_RULE_HEIGHT and r["x1"] > r["x0"]:
            rules.append(RuleLine(r["x0"], r["x1"], r["top"], r["bottom"]))
    return rules


def open_pdf(path: Path) -> list[PageGeometry]:
    pages: list[PageGeometry] = []
    with pdfplumber.open(str(path)) as pdf:
        for page in pdf.pages:
            chars = [
                Char(
                    text=ch["text"],
                    x0=ch["x0"], x1=ch["x1"],
                    top=ch["top"], bottom=ch["bottom"],
                    fontname=ch.get("fontname", "") or "",
                    size=ch.get("size", 0.0) or 0.0,
                )
                for ch in page.chars
            ]
            pages.append(
                PageGeometry(
                    width=page.width,
                    height=page.height,
                    chars=chars,
                    rule_lines=_horizontal_rules(page),
                    image_count=len(page.images),
                )
            )
    return pages
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_pdf_backend.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/netscan/pdf_backend.py tests/test_pdf_backend.py
git commit -m "feat: add pdfplumber-backed pdf_backend adapter"
```

---

### Task 5: Triage — native vs scanned

A page is **native** when it carries a meaningful text layer; **scanned** when it is image-only / empty.

**Files:**
- Create: `src/netscan/triage.py`
- Test: `tests/test_triage.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_triage.py
from netscan.pdf_backend import PageGeometry, Char
from netscan.triage import classify_page, PageKind


def _char(t):
    return Char(text=t, x0=0, x1=5, top=0, bottom=10, fontname="Helvetica", size=10)


def test_page_with_text_is_native():
    geo = PageGeometry(width=612, height=792,
                       chars=[_char(c) for c in "The agency shall review applications"],
                       image_count=0)
    assert classify_page(geo) == PageKind.NATIVE


def test_empty_page_is_scanned():
    geo = PageGeometry(width=612, height=792, chars=[], image_count=1)
    assert classify_page(geo) == PageKind.SCANNED


def test_few_garbage_chars_is_scanned():
    geo = PageGeometry(width=612, height=792, chars=[_char("\x00"), _char(" ")],
                       image_count=1)
    assert classify_page(geo) == PageKind.SCANNED
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_triage.py -v`
Expected: FAIL with ImportError.

- [ ] **Step 3: Write minimal implementation**

```python
# src/netscan/triage.py
"""Stage 1: classify each page as NATIVE (real text layer) or SCANNED."""
from enum import Enum

from netscan.pdf_backend import PageGeometry

MIN_MEANINGFUL_CHARS = 20  # below this, treat as scanned/empty


class PageKind(str, Enum):
    NATIVE = "native"
    SCANNED = "scanned"


def classify_page(geo: PageGeometry) -> PageKind:
    meaningful = sum(1 for ch in geo.chars if ch.text and ch.text.strip()
                     and ch.text.isprintable())
    if meaningful >= MIN_MEANINGFUL_CHARS:
        return PageKind.NATIVE
    return PageKind.SCANNED
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_triage.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add src/netscan/triage.py tests/test_triage.py
git commit -m "feat: add page triage (native vs scanned)"
```

---

### Task 6: Geometry — bold/italic from font names

pdfplumber/pdfminer expose `fontname` (e.g. `ABCDEF+Helvetica-BoldOblique`), not a clean bold/italic bit. Detect by substring heuristic; document the limitation.

**Files:**
- Create: `src/netscan/geometry.py`
- Test: `tests/test_geometry.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_geometry.py
from netscan.geometry import is_bold_font, is_italic_font


def test_bold_detection():
    assert is_bold_font("ABCDEF+Helvetica-BoldMT") is True
    assert is_bold_font("Arial-Black") is True
    assert is_bold_font("Helvetica") is False


def test_italic_detection():
    assert is_italic_font("Helvetica-Oblique") is True
    assert is_italic_font("Times-Italic") is True
    assert is_italic_font("Helvetica") is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_geometry.py -v`
Expected: FAIL with ImportError.

- [ ] **Step 3: Write minimal implementation**

```python
# src/netscan/geometry.py
"""Stage 2: deterministic geometry extraction.

Bold/italic come from font names (pdfplumber exposes no clean style bit).
Strikethrough/underline come from correlating horizontal rule lines against
glyph boxes (added in Task 7). Thresholds here are CALIBRATED by the Task 9
real-bill spike; the defaults below are the starting point.
"""
_BOLD_TOKENS = ("bold", "black", "heavy", "semibold", "demibold")
_ITALIC_TOKENS = ("italic", "oblique")


def is_bold_font(fontname: str) -> bool:
    name = fontname.lower()
    return any(tok in name for tok in _BOLD_TOKENS)


def is_italic_font(fontname: str) -> bool:
    name = fontname.lower()
    return any(tok in name for tok in _ITALIC_TOKENS)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_geometry.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add src/netscan/geometry.py tests/test_geometry.py
git commit -m "feat: detect bold/italic from font names"
```

---

### Task 7: Geometry — strike/underline by rule-line correlation

For each char, find a horizontal rule line whose x-range overlaps the char and whose y sits in the strike band (mid-glyph) or underline band (near baseline). pdfplumber is top-down: `top` < `bottom`, baseline ≈ `bottom`.

**Files:**
- Modify: `src/netscan/geometry.py`
- Test: `tests/test_geometry.py`

- [ ] **Step 1: Write the failing test (append to existing file)**

```python
# append to tests/test_geometry.py
from netscan.pdf_backend import Char, RuleLine
from netscan.geometry import line_decoration


def _char():
    # glyph box: top=0, bottom=10 -> height 10, mid at 5, baseline near 10
    return Char(text="x", x0=10, x1=20, top=0, bottom=10, fontname="Helvetica", size=10)


def test_midline_is_strikethrough():
    ch = _char()
    rule = RuleLine(x0=10, x1=20, top=5, bottom=5)  # mid-glyph
    assert line_decoration(ch, [rule]) == "strike"


def test_baseline_is_underline():
    ch = _char()
    rule = RuleLine(x0=10, x1=20, top=10.5, bottom=10.5)  # just below baseline
    assert line_decoration(ch, [rule]) == "underline"


def test_non_overlapping_line_is_ignored():
    ch = _char()
    rule = RuleLine(x0=100, x1=120, top=5, bottom=5)  # different x range
    assert line_decoration(ch, [rule]) is None


def test_no_lines_returns_none():
    assert line_decoration(_char(), []) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_geometry.py -v`
Expected: FAIL — `cannot import name 'line_decoration'`.

- [ ] **Step 3: Add the implementation to `geometry.py`**

```python
# append to src/netscan/geometry.py
from typing import Optional

from netscan.pdf_backend import Char, RuleLine

# bands as fractions of glyph height, measured from `top`
STRIKE_BAND = (0.30, 0.70)     # mid-glyph
UNDERLINE_BAND = (0.85, 1.30)  # at/just below baseline
MIN_X_OVERLAP_RATIO = 0.5      # rule must cover >= half the glyph width


def _x_overlap_ratio(ch: Char, rule: RuleLine) -> float:
    overlap = min(ch.x1, rule.x1) - max(ch.x0, rule.x0)
    width = ch.x1 - ch.x0
    if width <= 0:
        return 0.0
    return max(0.0, overlap) / width


def line_decoration(ch: Char, rules: list[RuleLine]) -> Optional[str]:
    """Return 'strike', 'underline', or None for the glyph given nearby rules."""
    height = ch.bottom - ch.top
    if height <= 0:
        return None
    for rule in rules:
        if _x_overlap_ratio(ch, rule) < MIN_X_OVERLAP_RATIO:
            continue
        frac = (rule.y_mid - ch.top) / height
        if STRIKE_BAND[0] <= frac <= STRIKE_BAND[1]:
            return "strike"
        if UNDERLINE_BAND[0] <= frac <= UNDERLINE_BAND[1]:
            return "underline"
    return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_geometry.py -v`
Expected: PASS (all geometry tests pass).

- [ ] **Step 5: Commit**

```bash
git add src/netscan/geometry.py tests/test_geometry.py
git commit -m "feat: detect strike/underline via rule-line correlation"
```

---

### Task 8: Geometry — assemble page into Spans

Tag each char (bold/italic/strike/underline), then group consecutive same-line, same-formatting chars into `Span`s in reading order (top-to-bottom, then left-to-right).

**Files:**
- Modify: `src/netscan/geometry.py`
- Test: `tests/test_geometry.py`

- [ ] **Step 1: Write the failing integration test (append)**

```python
# append to tests/test_geometry.py
from netscan.pdf_backend import open_pdf
from netscan.geometry import extract_page_spans
from tests.fixtures.make_fixtures import build_formatted_pdf


def _find(spans, word):
    for s in spans:
        if word in s.text:
            return s
    raise AssertionError(f"{word!r} not found in {[s.text for s in spans]}")


def test_extract_page_spans_tags_fixture(tmp_path):
    pdf = tmp_path / "s.pdf"
    build_formatted_pdf(pdf)
    geo = open_pdf(pdf)[0]
    spans = extract_page_spans(geo)

    assert _find(spans, "PLAIN").bold is False
    assert _find(spans, "PLAIN").struck is False
    assert _find(spans, "BOLDWORD").bold is True
    assert _find(spans, "ITALICWORD").italic is True
    assert _find(spans, "STRUCK").struck is True
    assert _find(spans, "ADDED").underlined is True

    # round-trip: concatenated span text contains every source word
    joined = " ".join(s.text for s in spans)
    for w in ("PLAIN", "BOLDWORD", "ITALICWORD", "STRUCK", "ADDED"):
        assert w in joined
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_geometry.py::test_extract_page_spans_tags_fixture -v`
Expected: FAIL — `cannot import name 'extract_page_spans'`.

- [ ] **Step 3: Add the implementation to `geometry.py`**

```python
# append to src/netscan/geometry.py
from netscan.pdf_backend import PageGeometry
from netscan.types import Span

SAME_LINE_TOL = 3.0  # pts; chars whose tops differ by less are on one line


def _char_format(ch: Char, rules: list[RuleLine]) -> tuple[bool, bool, bool, bool]:
    deco = line_decoration(ch, rules)
    return (
        is_bold_font(ch.fontname),
        is_italic_font(ch.fontname),
        deco == "strike",
        deco == "underline",
    )


def extract_page_spans(geo: PageGeometry) -> list[Span]:
    # reading order: top-to-bottom, then left-to-right
    chars = sorted(geo.chars, key=lambda c: (round(c.top / SAME_LINE_TOL), c.x0))
    spans: list[Span] = []
    cur: Span | None = None
    cur_fmt: tuple | None = None
    cur_top: float | None = None

    for ch in chars:
        fmt = _char_format(ch, geo.rule_lines)
        same_line = cur_top is not None and abs(ch.top - cur_top) <= SAME_LINE_TOL
        if cur is not None and fmt == cur_fmt and same_line:
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
            cur_top = ch.top
    return spans
```

- [ ] **Step 4: Run the full suite**

Run: `python -m pytest -v`
Expected: PASS (all tasks' tests green).

- [ ] **Step 5: Commit**

```bash
git add src/netscan/geometry.py tests/test_geometry.py
git commit -m "feat: assemble tagged Spans in reading order"
```

---

### Task 9: Real-bill validation spike & GATE

This is a **spike**, not TDD: the goal is to learn whether real bills behave as assumed, then write a go/no-go decision. **No downstream plan starts until this gate is recorded.**

**Files:**
- Create: `scripts/inspect_bill.py`
- Create: `docs/superpowers/spikes/2026-06-01-rule-line-gate.md`

- [ ] **Step 1: Obtain 2–3 real native bill PDFs**

Download public bills that visibly contain struck and underlined amendment text from any state legislature site (e.g. a state legislature's "amended bill" / "engrossed" PDF). Save under `samples/` (gitignored). If the user provided sample bills, use those instead.

- [ ] **Step 2: Write the inspection script**

```python
# scripts/inspect_bill.py
"""Report what the geometry path sees in a real bill, per page.

Usage: python scripts/inspect_bill.py samples/some_bill.pdf
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from netscan.pdf_backend import open_pdf          # noqa: E402
from netscan.triage import classify_page          # noqa: E402
from netscan.geometry import extract_page_spans    # noqa: E402


def main(pdf_path: str) -> None:
    pages = open_pdf(Path(pdf_path))
    for i, geo in enumerate(pages, 1):
        kind = classify_page(geo)
        spans = extract_page_spans(geo) if kind.value == "native" else []
        struck = [s.text for s in spans if s.struck]
        under = [s.text for s in spans if s.underlined]
        print(f"\n=== page {i}: {kind.value} | chars={len(geo.chars)} "
              f"rule_lines={len(geo.rule_lines)} images={geo.image_count} ===")
        print(f"  struck spans ({len(struck)}): {struck[:10]}")
        print(f"  underlined spans ({len(under)}): {under[:10]}")


if __name__ == "__main__":
    main(sys.argv[1])
```

- [ ] **Step 3: Run the inspection on each sample**

Run: `python scripts/inspect_bill.py samples/<bill>.pdf`
Expected: per-page report. Manually compare struck/underlined spans against what you SEE in the PDF viewer for those pages.

- [ ] **Step 4: Record the gate decision**

Create `docs/superpowers/spikes/2026-06-01-rule-line-gate.md` answering, with evidence from Step 3:
1. Do strike/underline appear as `lines`/`rects` in `rule_lines`? (counts per page)
2. Detection accuracy: of the struck/underlined runs you see by eye, what fraction did `extract_page_spans` tag correctly? (estimate per sample)
3. Failure modes observed (e.g. underline absent from rule_lines, bands mis-calibrated, multi-column reading order wrong).
4. **GATE:** PASS → proceed to the conflict/reconcile/emit/verify plan, recording any threshold recalibration (`STRIKE_BAND`, `UNDERLINE_BAND`, `MIN_X_OVERLAP_RATIO`). FAIL → document where geometry misses and note that more spans must escalate to the VLM/QA path before building downstream stages.

- [ ] **Step 5: Commit**

```bash
git add scripts/inspect_bill.py docs/superpowers/spikes/2026-06-01-rule-line-gate.md
git commit -m "spike: validate rule-line premise on real bills + gate decision"
```

---

## Self-Review

**Spec coverage (this plan = spec Milestones 1–2):**
- Stage 1 triage → Task 5 ✓
- Stage 2 geometry (font flags bold/italic) → Task 6 ✓
- Stage 2 geometry (rule-line strike/underline correlation) → Tasks 7–8 ✓
- MIT stack behind adapter → Task 4 ✓
- `Span(text, formatting, confidence, source)` core type → Task 2 ✓
- Synthetic test fixtures → Task 3 ✓
- Milestone-1 real-bill gate → Task 9 ✓
- Deferred to later plans (correctly out of scope): conflict (Stage 3), VLM (Stage 4), reconcile (Stage 5), emit (Stage 6), verify/QA queue (Stage 7), state detection, CLI, GUI.

**Placeholder scan:** No "TBD/TODO/handle edge cases" in code steps; every code step shows complete code. Task 9 is intentionally a spike with judgment steps (download/inspect/decide), not code-by-TDD — its outputs (script + gate doc) are fully specified. ✓

**Type consistency:** `Span` fields (`text,x0,x1,top,bottom,bold,italic,struck,underlined,confidence,source`) are used identically in Tasks 2 and 8. `Char`/`RuleLine`/`PageGeometry` defined in Task 4 are used unchanged in Tasks 5,7,8. `line_decoration` returns `'strike'|'underline'|None`, consumed consistently in Task 8. `PageKind` enum `.value` used in Task 9 matches Task 5. ✓
