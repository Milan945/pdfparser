# NetScan Bill Converter

Converts U.S. state legislative bill PDFs into NetScan bracket markup — the tagged text format used by the NetScan ingestion system to represent amendments.

```
other health impairments[D>,<D] or specific learning disabilities

[A>(gg) "Other health impairment" means having limited strength, vitality or alertness...<A]
```

`[D>...<D]` = deleted text (strikethrough in the PDF)  
`[A>...<A]` = added text (italic in the PDF)  
Plain text = unchanged law

**No LLM, no OCR, no vision model.** All formatting is detected from the PDF's own vector geometry — font names and rule lines drawn by the typesetter.

---

## Supported States

| State | Gutter style | Em-dash |
|---|---|---|
| **CA** | `line N` prefix labels | preserved |
| **KS** | bare sequential integers | converted to `--` |

---

## Usage

**Web UI**
```bash
pip install -e ".[ui]"
streamlit run app.py
```
Upload a PDF, select the state, download the output `.txt`.

**Three-panel UI (React + FastAPI)**
```bash
# Terminal 1 — backend
pip install -e ".[api]"
uvicorn api.main:app --reload

# Terminal 2 — frontend
cd frontend
npm install
npm run dev
```
Open `http://localhost:5173`. Upload a PDF, review the three-panel output, download either version.

**CLI**
```bash
python -m netscan.pipeline bill.pdf CA          # stdout
python -m netscan.pipeline bill.pdf KS out.txt  # file
```

**Python**
```python
from netscan.pipeline import convert
markup = convert("bill.pdf", "CA")   # returns str
```

---

## Full Pipeline Walkthrough

Every PDF goes through the same seven stages in order. Each stage is a pure function — it takes data in and returns data out, with no shared state.

```
PDF file
   │
   ▼  pdf_backend.py
PageGeometry (chars + rule lines, per page)
   │
   ▼  structure.py  ×4 passes
PageGeometry (cleaned)
   │
   ▼  geometry.py
list[Span]  (text runs with formatting flags)
   │
   ▼  scope.py
list[Span]  (italic cleared before enacting clause)
   │
   ▼  reflow.py
list[list[Span]]  (paragraphs)
   │
   ▼  emit.py
str  (bracket markup for each paragraph)
   │
   ▼  "\n\n".join
final markup string
```

---

### Stage 1 — PDF Extraction (`pdf_backend.py`)

Reads the raw PDF using **pdfplumber** and produces a `PageGeometry` for every page. This is the only place in the codebase that touches a PDF library — everything else works on plain Python dataclasses.

**What it extracts per page:**

| Data | Description |
|---|---|
| `chars` | Every character glyph: text, position (`x0 x1 top bottom`), font name, point size |
| `rule_lines` | Horizontal vector lines and thin rectangles (used for strike/underline detection) |
| `width / height` | Page dimensions in points |
| `image_count` | Number of raster images (used by triage to detect scanned pages) |

Font names look like `ABCDEF+Helvetica-BoldOblique`. The six-character subset prefix is stripped internally; the rest encodes style.

---

### Stage 2 — Structure Cleaning (`structure.py`)

Runs four passes over `PageGeometry.chars` to remove noise **before** any formatting is detected. All passes return a new `PageGeometry` — the original is never mutated.

#### 2a. Fraction alignment (`align_fraction_digits`)

Fractions like `½` are typeset as three separate glyphs: a raised numerator, a fraction slash (U+2044 `⁄`), and a lowered denominator. Their `top` coordinates differ enough that line clustering would split them across lines. This pass snaps the digits flanking a `⁄` onto the slash's vertical extent so they stay together.

Runs **first**, on the raw content-stream order, because later passes re-cluster by line position and would separate the slash from its denominator before this fix could apply.

#### 2b. Gutter stripping (`strip_gutter`)

Legislative PDFs print a line-number gutter on every body line. Its format depends on the state.

**CA** — each line starts with a literal label such as `line 3 `. The pass matches the regex `^\s*line\s+\d+\s+` and drops every character belonging to that prefix.

**KS** — each line starts with a bare integer fused directly into the body text (`10some words`). The pass finds the line whose leading digit-run is exactly `"1"` (anchoring on line 1, not on `"10"` or `"1,000"`), then strips the expected counter (`1`, `2`, `3`, …) from the front of each subsequent line.

#### 2c. Header/footer removal (`strip_running_headers`)

Pages carry running headers and footers that are not part of the bill text.

A line is dropped only when **both** conditions hold:
1. Its `top` is within 60 pts of the page top (header) or 185 pts of the page bottom (footer).
2. Its text matches the state's pattern.

| State | Header pattern | Footer pattern |
|---|---|---|
| CA | `AB 351 — 2 —` / `— 3 — AB 351` | lone page number `99` |
| KS | `HB 2206` / `SB 123` | *(none)* |

The position+pattern double gate prevents body text near a margin from being dropped.

#### 2d. Small-caps uppercasing (`uppercase_small_caps`)

Some bills (CA) use small-caps fonts for section titles. pdfplumber extracts the lowercase code points, but the visual text — and Doctly's output — is uppercase. This pass detects small-caps fonts by their conventional `SC`/`PC` suffix (e.g. `MinionPC`) and uppercases those characters.

---

### Stage 3 — Geometry Extraction (`geometry.py`)

Converts the cleaned stream of individual characters into **Spans** — runs of consecutive characters that share the same formatting.

#### Step 1: Line clustering

Characters are sorted top-to-bottom, then grouped into lines: a character joins the current line if its `top` is within **3 pts** of the line's first character. This tolerance absorbs sub-pixel vertical jitter between glyphs on the same printed line.

#### Step 2: Reading-order sorting within each line

Within each line, characters are sorted left-to-right by `x0`, bucketed to a **1 pt** quantum. The quantum prevents zero-width ligature glyphs (e.g. the `fi` ligature) — whose `x0` collapses onto the following glyph's position — from reordering with that neighbour. Ties within a bucket break by content-stream order.

#### Step 3: Formatting detection

For each character, two sources are checked:

**Font name → bold / italic**

| Flag | Triggers when font name contains |
|---|---|
| `bold` | `bold`, `black`, `heavy` |
| `italic` | `italic`, `oblique` |

**Rule lines → strikethrough / underline**

Each horizontal rule line is correlated against the character's bounding box:

1. **X overlap:** the rule must cover at least 50% of the glyph's width.
2. **Vertical band:** the rule's vertical midpoint, expressed as a fraction of the glyph height, determines the decoration:
   - `0.30 – 0.70` of glyph height → **strikethrough** (mid-glyph)
   - `0.72 – 1.35` of glyph height → **underline** (at or just below baseline)

Strikethrough takes precedence over underline when both match.

**Zero-width glyph inheritance:** A zero-width glyph (ligature) has no horizontal extent and cannot overlap a rule line, so its decoration would always be `None`. The pass inherits strike/underline from the immediately following character (or preceding one if it is last), preventing a struck word like `"five"` from being split into struck `"fi"` + unstruck `"ve"`.

#### Step 4: Span merging

Consecutive characters with identical formatting are merged into a single `Span`. The `Span` records the combined text, the bounding box of the whole run, and the formatting flags.

---

### Stage 4 — Preamble Scoping (`scope.py`)

By drafting convention, the preamble and enacting clause of a bill are set in italic — but they are **not** amendments. Treating that italic as additions would produce false `[A>...<A]` tags around the bill title, the "Session of 2025" header, and "Be it enacted by the Legislature…".

This pass suppresses the `italic` flag on every span until the enacting clause is seen:

- **CA:** `"...do enact as follows:"`
- **KS and most states:** `"Be it enacted by the Legislature..."`

The `operative` flag carries across pages: once the enacting clause is found, all subsequent pages pass through unchanged. If the document has no enacting clause at all (unexpected for a real bill), the pass never suppresses anything — no genuine additions are hidden.

---

### Stage 5 — Reflow (`reflow.py`)

Groups the flat list of spans into **paragraphs** that match the block structure of the bill.

Spans are first re-clustered into physical lines (same 3 pt tolerance as geometry). A new paragraph starts at:

- The first line of the document
- Any line that opens with a block marker: `Sec.`, `Section`, `(a)`, `(1)`, `AN ACT`, `Be it enacted`, `HOUSE BILL`, and similar

Lines within a paragraph are joined with a single space, except:
- The line ends with a hyphen → the hyphen is removed and no space is inserted (de-hyphenation)
- The line already ends with a space, or the next line starts with a space → no extra space added

---

### Stage 6 — Emit (`emit.py`)

Renders each paragraph's spans into the final markup string.

#### Decoration mapping

| Span flag | Tag |
|---|---|
| `struck = True` | `[D>...<D]` |
| `italic = True` | `[A>...<A]` |
| neither | plain text |

Strike wins over italic when both are set.

#### Merging rules

1. **Consecutive same-decoration spans** are merged into a single tag — no redundant open/close pairs.
2. **Whitespace-only plain spans flanked by the same decoration** are absorbed into the surrounding tag. This keeps a wrapped decorated phrase — e.g. an addition that breaks across a line — as one `[A>...<A]` rather than two.
3. **Leading and trailing whitespace** of a tagged run stays **outside** the tag, so `[A>word<A]` not `[A> word <A]`.
4. **Adjacent end/start tags** (`<D][A>`, `<A][D>`, etc.) get a separating space inserted between them, matching Doctly's convention.

#### Unicode normalization

Applied at emit time to every span's text:

| Input | Output |
|---|---|
| Curly quotes `"` `"` `'` `'` | Straight `"` `'` |
| Fraction slash U+2044 `⁄` | `/` |
| Non-breaking space U+00A0 | regular space |
| Zero-width chars (U+200B, U+200C, U+200D, U+FEFF) | deleted |
| En-dash, em-dash | preserved (em-dash converted to `--` for KS in post-processing) |

---

### Post-processing

After all paragraphs are joined with `"\n\n"`:

- **KS only:** every em-dash (`—`) is replaced with `--`, matching Doctly's KS convention.

---

## Key Data Structures

### `Span` — the universal currency

```python
@dataclass
class Span:
    text: str             # the characters in this run
    x0: float             # left edge (pts)
    x1: float             # right edge
    top: float            # top edge
    bottom: float         # bottom edge
    bold: bool            # from font name
    italic: bool          # from font name  →  [A>...<A] if operative
    struck: bool          # from rule line  →  [D>...<D]
    underlined: bool      # from rule line  (reserved, not emitted)
    confidence: float     # 1.0 = geometry-certain; lower = flagged
    source: Source        # "geometry" | "font_flag" | "vlm" | "ocr"
    flag_reason: str|None # set by conflict detection when ambiguous
```

### `PageGeometry` — one page from the PDF

```python
@dataclass
class PageGeometry:
    width: float
    height: float
    chars: list[Char]          # individual glyphs
    rule_lines: list[RuleLine] # horizontal vector lines
    image_count: int

@dataclass
class Char:
    text: str
    x0: float; x1: float; top: float; bottom: float
    fontname: str   # e.g. "ABCDEF+Helvetica-BoldOblique"
    size: float     # point size

@dataclass
class RuleLine:
    x0: float; x1: float
    top: float; bottom: float
    y_mid: float  # (top + bottom) / 2
```

---

## Project Structure

```
src/netscan/
├── pipeline.py       # orchestration + CLI entry point
├── types.py          # Span dataclass
├── pdf_backend.py    # pdfplumber adapter (only PDF library touchpoint)
├── structure.py      # gutter strip, header/footer removal, fractions, small-caps
├── geometry.py       # font-name + rule-line formatting detection → Spans
├── scope.py          # preamble italic suppression
├── reflow.py         # paragraph reconstruction
├── emit.py           # bracket markup rendering + unicode normalization
├── normalize.py      # unicode normalization helpers
├── profiles.py       # per-state configuration (CA, KS)
├── detect.py         # auto-detect state from first-page text
└── conflict.py       # ambiguity flagging (infrastructure for future QA routing)

app.py                # Streamlit web UI
samples/              # sample PDFs + Doctly reference outputs
tests/                # pytest unit tests (one file per module)
scripts/
├── inspect_bill.py   # inspect what the geometry stage sees in a PDF
└── score_bill.py     # score pipeline output against a Doctly reference
```

---

## Running Tests

```bash
pip install -e ".[dev]"
pytest
```

Tests use programmatically generated PDFs (via reportlab) as fixtures — no dependency on the sample bills.

---

## Design Principles

**Geometry first.** Font names and rule lines encode formatting deterministically. The pipeline reads what the typesetter drew; it does not guess.

**Single responsibility.** Each module does exactly one job. `pdf_backend.py` is the only file that imports pdfplumber — swapping the PDF library means touching one file.

**Fail-safe suppression.** If the enacting clause is never found, `scope.py` suppresses nothing. Missing a deletion is worse than a false addition in that context.

**Confidence tracking.** Every `Span` carries a `confidence` score and a `source` tag (`"geometry"`, `"font_flag"`, `"vlm"`, `"ocr"`). The `conflict.py` module flags ambiguous rule-line positions and lowers confidence, routing those spans to a QA queue. The VLM and OCR paths are stubbed — infrastructure for future work.
