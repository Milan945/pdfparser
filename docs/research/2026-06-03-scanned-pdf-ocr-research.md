# Scanned PDF OCR Research — Which Engine and Approach?

**Date:** 2026-06-03  
**Branch:** feature/scanned-pdf-ocr  
**Question:** For detecting amendment markup (strikethrough = deletion, italic/underline = addition) in scanned legislative bill PDFs, which OCR engine and image-processing approach is best?

**Method:** 5-angle web search → 24 sources → 76 claims extracted → 25 adversarially verified. 11 confirmed, 14 killed.

---

## Key Finding: No Single Tool Does All Three

No OCR engine or cloud service handles all three markup signals (strikethrough, underline, italic) from scanned images. They must be handled by different tools combined.

| Signal | Detection Method | Best Tool |
|---|---|---|
| **Text extraction** | OCR | Tesseract 5 (local) or Azure/Textract (cloud) |
| **Strikethrough** | Pixel-space line detection | OpenCV (morphological ops or Hough transform) |
| **Underline** | Pixel-space line detection | OpenCV (same approach, different vertical band) |
| **Italic** | Font style API | Azure Document Intelligence (styleFont add-on) |

---

## Finding 1: Tesseract 5 Cannot Report Font Styles

**Confidence: High (3-0 vote)**

Tesseract 5's LSTM engine (the default since v4) cannot report italic, bold, or any font style attributes. This is a confirmed architectural limitation — font attribute reporting was a v3 legacy feature not carried into LSTM.

The legacy engine (`--oem 0`) can report italic in theory, but has a known bug: italic words are disproportionately "weak" (low-confidence) and weak words get assigned the modal (most common) font, stripping the italic flag. A working fix exists only in a fork (Scribe OCR) — stock Tesseract 5.5.x still has the bug.

**Implication:** Tesseract alone cannot detect italic text. It is useful only for text extraction + bounding boxes.

---

## Finding 2: Azure Document Intelligence Reports Italic — But Not Strikethrough

**Confidence: High (3-0 vote)**

Azure Document Intelligence's `styleFont` add-on (API versions 2023-07-31 GA and 2024-11-30 GA) reports per-span:
- `fontStyle`: italic / normal
- `fontWeight`: bold / normal
- `similarFontFamily`, `color`, `backgroundColor`

Strikethrough and underline are **explicitly absent** from the `DocumentStyle` class. Microsoft's own Q&A recommends geometric line-overlap analysis (PyMuPDF `get_drawings()`) as the workaround for strikethrough/underline detection.

**Implication:** Azure styleFont covers italic (additions in KS/VA convention) but not strikethrough (deletions). You still need pixel-space line detection for strikethrough regardless of which OCR engine you use.

---

## Finding 3: Strikethrough/Underline Must Be Detected in Pixel Space

**Confidence: High (3-0 vote)**

No cloud OCR service natively reports strikethrough or underline as style properties. The required technique is:

1. Convert PDF page to image (300+ DPI)
2. Detect horizontal line segments in pixel space using OpenCV:
   - **Morphological operations** (erode + dilate with horizontal kernel) — robust on printed documents
   - **Hough line transform** — works but produces more false positives near table borders
3. For each detected line segment, find OCR word bounding boxes that overlap it vertically
4. Classify as strikethrough or underline by the line's vertical position within the word's height (same band logic as the vector pipeline: 30–70% = strike, 72–135% = underline)

This is the **direct pixel-space analogue** of what `geometry.py` already does with vector rule lines. The same band thresholds can be reused.

---

## Finding 4: PDF-to-Image — Use PyMuPDF at 300 DPI

**Confidence: High**

| Library | Default DPI | Architecture | Verdict |
|---|---|---|---|
| **PyMuPDF** | configurable | native C library | ✅ Recommended |
| **pdf2image** | 200 DPI | subprocess wrapper (poppler) | ⚠️ Use with `dpi=300` |
| **pdfplumber** | N/A | text extraction only, no image rendering | ❌ Not suitable |

`pdf2image` defaults to 200 DPI, which is below the OCR quality threshold — always pass `dpi=300`.

PyMuPDF uses a zoom factor: `zoom = dpi / 72`, so `zoom = 300/72 ≈ 4.17` gives 300 DPI. Prefer PyMuPDF because:
- It's already in the Python ecosystem (no poppler subprocess dependency)
- Faster than subprocess-based pdf2image
- The same library can also extract drawings/lines from native PDFs (already used conceptually in the pipeline)

**Recommended call:**
```python
import fitz  # PyMuPDF
doc = fitz.open(pdf_path)
page = doc[page_num]
mat = fitz.Matrix(300/72, 300/72)  # 300 DPI
pix = page.get_pixmap(matrix=mat)
img = pix.tobytes("png")  # or pil_image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
```

---

## Finding 5: EasyOCR Is Not Suitable

**Confidence: High (3-0 vote)**

EasyOCR has no layout analysis — it uses CRAFT for text region detection but performs no column detection or reading-order analysis. It fragments text into separate bounding boxes that should be on the same line. Not suitable for multi-line legislative bill pages.

---

## What the Research Could Not Confirm

The adversarial verification **killed** all quantitative accuracy claims comparing cloud OCR engines:
- Google Document AI vs Azure vs Textract rankings: **refuted**
- Per-page cost figures ($1.50/1000 pages): **refuted**
- Tesseract noise sensitivity vs cloud: **refuted**

**Implication:** No verified accuracy ranking between cloud OCR engines exists from this research. An empirical benchmark on real scanned legislative bills is needed before choosing between Azure, Google, and Textract for text extraction.

---

## Recommended Architecture for Scanned Pages

```
Scanned page (PageKind.SCANNED)
         │
         ▼
PyMuPDF → PIL image (300 DPI)
         │
         ├──────────────────────────────┐
         ▼                              ▼
  Tesseract 5 (LSTM)           OpenCV line detection
  text + word bboxes           horizontal segments in pixel space
         │                              │
         └──────────┬───────────────────┘
                    ▼
         Correlate line segments
         with word bboxes
         (same band logic as geometry.py:
          30-70% height = strike,
          72-135% height = underline)
                    │
                    ▼
              list[Span]
         (struck / underlined flags set,
          source="ocr", confidence=0.85)
                    │
                    ▼
         [Optional: Azure styleFont add-on
          for italic detection on ambiguous pages]
                    │
                    ▼
         Feeds into existing scope.py →
         reflow.py → emit.py pipeline
```

---

## Open Questions (Unresolved by Research)

1. **OCR accuracy ranking** — no verified benchmark survived. Need empirical test: run Tesseract, Azure, and Textract on 5–10 real scanned legislative bill pages and measure word error rate.
2. **OpenCV line detection precision** — can morphological ops reliably distinguish strikethrough lines from table borders and section dividers in bill layouts?
3. **Italic detection without Azure** — is there an open-source model (Surya, DocTR, fine-tuned layout model) that detects italic from scanned images via slant-angle estimation?
4. **Azure styleFont latency/cost** — what does the add-on actually cost and add in latency for a 100-200 page bill?

---

## Decision Points Before Implementation

1. **Text extraction:** Start with Tesseract 5 (free, local, no API key needed). Benchmark against Azure/Textract on real scanned bills before committing.
2. **Strikethrough/underline:** OpenCV pixel-space line detection — no cloud service helps here regardless of budget.
3. **Italic:** If bills use italic for additions (KS, VA convention) and scanned quality is good, try slant-angle estimation first. If unreliable, use Azure styleFont as fallback.
4. **PDF-to-image:** PyMuPDF at 300 DPI. Already a near-dependency (conceptually similar to pdfplumber).

---

## Sources

| URL | Quality | Finding |
|---|---|---|
| https://learn.microsoft.com/en-us/azure/ai-services/document-intelligence/concept/add-on-capabilities | primary | Azure styleFont reports italic, not strikethrough |
| https://github.com/tesseract-ocr/tesseract/issues/2781 | forum | LSTM has no font style reporting |
| https://github.com/tesseract-ocr/tesseract/issues/1371 | forum | Legacy engine italic unreliable |
| https://pypi.org/project/pdf2image/ | primary | pdf2image defaults to 200 DPI |
| https://artifex.com/blog/converting-pdfs-to-images-with-pymupdf-a-complete-guide | blog | PyMuPDF zoom=dpi/72 |
| https://intuitionlabs.ai/articles/non-llm-ocr-technologies | blog | EasyOCR has no layout analysis |
