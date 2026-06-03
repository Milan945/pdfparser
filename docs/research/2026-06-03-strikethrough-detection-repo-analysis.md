# Strikethrough Detection Repo Analysis

**Date:** 2026-06-03  
**Repo:** https://github.com/iamrishi-x/Strick-through-word-detection  
**Purpose:** Assess what this repo does, what's reusable, and what gaps remain for our scanned PDF OCR pipeline.

---

## TL;DR

This is a proof-of-concept repo (0 stars, 6 commits, one person) but it contains the exact algorithm we need for strikethrough detection in pixel space. The OpenCV approach is directly portable to our pipeline. It does **not** handle italic or underline detection — those remain unsolved gaps.

---

## What the Repo Does

Two methods for detecting struck-through words in document images:

1. **OpenCV + Tesseract (Method 1)** — fast, rule-based, directly reusable
2. **U-Net CNN (Method 2)** — trained on synthetic data, slower, more robust on complex cases

---

## Method 1: OpenCV + Tesseract (The One We Want)

### Algorithm Step-by-Step

```
1. Load image (BGR)
2. Convert to grayscale
3. Adaptive threshold (Gaussian, THRESH_BINARY_INV, kernel=11)
4. Create horizontal kernel: np.ones((1, 50), np.uint8)
5. Morphological OPEN with kernel (2 iterations) → isolates horizontal lines
6. Find contours of detected horizontal lines
7. Run Tesseract on original image → word bounding boxes + text
8. For each word bbox (x, y, w, h):
     For each detected line contour (x_line, y_line, w_line, h_line):
       if (y < y_line < y + h) AND (x_line < x+w AND x_line+w_line > x):
           → word is struck through
```

### Core Intersection Code

```python
# Line isolation
kernel = np.ones((1, 50), np.uint8)
horizontal_lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel, iterations=2)
contours, _ = cv2.findContours(horizontal_lines, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

# Word bboxes from Tesseract
ocr_data = pytesseract.image_to_data(image, output_type=Output.DICT)

# Intersection check
for i in range(len(ocr_data["text"])):
    if ocr_data["text"][i].strip():
        x, y, w, h = ocr_data["left"][i], ocr_data["top"][i], ocr_data["width"][i], ocr_data["height"][i]
        for contour in contours:
            x_line, y_line, w_line, h_line = cv2.boundingRect(contour)
            if (y < y_line < y + h) and (x_line < x + w and x_line + w_line > x):
                # word at index i is struck through
```

### Key Parameters (Needs Tuning for Our Bills)

| Parameter | Value Used | What It Controls |
|---|---|---|
| Adaptive threshold kernel | 11×11 | Binarization window size |
| Horizontal kernel | `(1, 50)` | Min horizontal run length to count as a line |
| Morphology iterations | 2 | How aggressively small gaps are bridged |

**Important:** The `(1, 50)` kernel width (50 pixels) is calibrated to their test images. For 300 DPI legislative bills, this will need tuning — a 50-pixel run at 300 DPI corresponds to ~4mm, which may be too short or too long depending on bill formatting.

### PDF Input

Uses `pdf2image.convert_from_path()` — straightforward. We'd swap this for PyMuPDF at 300 DPI.

### Outputs

- Word text (from Tesseract)
- Word bounding box (x, y, w, h) in pixel coordinates
- Boolean: is this word struck through?
- No confidence score on the strikethrough classification

---

## Method 2: U-Net CNN

Trained on 1,000 **synthetically generated** images (not real legislative bills). Synthetic data uses random text + programmatically drawn strikethrough lines in 8 styles (single, double, zigzag, dotted, dashed, wavy, cross, scribble).

- **Architecture:** Standard U-Net (encoder 64→128→256→512, bottleneck, decoder with skip connections)
- **Output:** Pixel-level binary segmentation mask (strikethrough region = 1)
- **Training:** 4 epochs, batch=16, binary cross-entropy, Adam
- **Inference:** Sliding 128×128 patches with 50% overlap

**Assessment for us:** Not immediately usable. Trained on synthetic data, not on printed legislative bill scans. Would need retraining on real bill images. Also adds TensorFlow as a dependency. Skip for now — use as a fallback if the OpenCV approach has too many false positives.

---

## What This Repo Does NOT Handle

| Signal | Handled? | Notes |
|---|---|---|
| Strikethrough | ✅ | The whole point of the repo |
| Underline | ❌ | Explicitly excluded in README |
| Italic | ❌ | Not mentioned — fundamentally different problem |
| Bold | ❌ | Not mentioned |
| Colored strikethroughs | ❌ | Assumes black on white only |
| Diagonal/wavy strokes (handwritten) | ❌ | Horizontal kernel only |
| Document deskewing | ❌ | Assumes straight pages |
| Scanned noise/degradation | ❌ | No preprocessing for scanner artifacts |

---

## How It Maps to Our Pipeline

Our existing `geometry.py` already does the conceptual equivalent for **native PDFs**:
- Detects horizontal rule lines from vector data
- Correlates them with glyph bounding boxes
- Uses vertical band fractions (30–70% = strike, 72–135% = underline)

For **scanned pages**, this repo's OpenCV approach gives us the same thing in pixel space:

```
Native PDF path (geometry.py):          Scanned path (new ocr_geometry.py):
─────────────────────────────────       ─────────────────────────────────────
pdfplumber → RuleLine objects           PyMuPDF → 300 DPI PIL image
↓                                       ↓
line_decoration(char, rules)            OpenCV morphological → pixel line segments
↓                                       ↓
x_overlap_ratio + vertical band         Tesseract → word bboxes
↓                                       ↓
struck=True / underlined=True           Intersection check + vertical band fraction
↓                                       ↓
Span(struck=True, source="geometry")    Span(struck=True, source="ocr", confidence=0.85)
```

The band-fraction logic (30–70% for strike, 72–135% for underline) can be ported directly — just expressed in pixels instead of PDF points.

---

## Directly Reusable Code

### 1. Horizontal line isolation (adapt kernel width)
```python
import cv2
import numpy as np

def isolate_horizontal_lines(binary_img, min_line_width_px: int = 50) -> np.ndarray:
    kernel = np.ones((1, min_line_width_px), np.uint8)
    return cv2.morphologyEx(binary_img, cv2.MORPH_OPEN, kernel, iterations=2)
```

### 2. Intersection logic (port directly)
```python
def line_intersects_word(word_bbox, line_bbox) -> bool:
    x, y, w, h = word_bbox
    x_line, y_line, w_line, h_line = line_bbox
    vertically_inside = y < y_line < y + h
    horizontally_overlaps = x_line < x + w and x_line + w_line > x
    return vertically_inside and horizontally_overlaps
```

### 3. Band fraction (same logic as geometry.py)
```python
def classify_line(word_bbox, line_bbox) -> str | None:
    """Returns 'strike', 'underline', or None."""
    _, y, _, h = word_bbox
    _, y_line, _, h_line = line_bbox
    y_mid_line = y_line + h_line / 2
    frac = (y_mid_line - y) / h if h > 0 else 0
    if 0.30 <= frac <= 0.70:
        return "strike"
    if 0.72 <= frac <= 1.35:
        return "underline"
    return None
```

---

## Gaps This Repo Does Not Solve

### 1. Italic detection from scanned images
The repo has zero coverage of this. For KS/VA bills where italic = addition, this is a critical gap. Known options:
- **Azure Document Intelligence styleFont** — only cloud service that reports italic per span, ~$0.001/page, requires API key
- **Slant angle estimation** — measure character lean on word image crops; works for strongly italic fonts but no off-the-shelf library does this reliably
- **Fine-tuned classifier** — train a CNN on word image crops labeled italic/not-italic; needs annotated data

### 2. Underline detection (independent of strikethrough)
The same OpenCV morphological approach works for underlines — just use the lower vertical band (72–135% of word height). Not covered by this repo but the algorithm is the same.

### 3. Real bill benchmarking
The repo was tested on synthetic and generic documents. We don't know how the `(1, 50)` kernel and 2-iteration settings hold up on real KS or CA legislative bill scans. The kernel width will need calibration once we have a real scanned bill.

---

## Recommended Next Steps (When We Come Back)

1. Get a real scanned legislative bill PDF (KS or CA preferred — we have the ground truth markup from Doctly)
2. Convert to images with PyMuPDF at 300 DPI
3. Run the OpenCV approach with kernel `(1, 50)` → measure precision/recall against known strikethroughs
4. Tune kernel width until F1 is acceptable (target >0.90)
5. Port the intersection + band-fraction logic into a new `src/netscan/ocr_geometry.py` module
6. Wire into `triage.py` SCANNED path: `PageKind.SCANNED → ocr_geometry.extract_page_spans_from_image()`
7. Decide italic detection strategy separately (Azure API vs slant estimation)

---

## Dependencies Needed

```
# New for scanned path
opencv-python>=4.9
pytesseract>=0.3.10   # or doctr for better bboxes
pymupdf>=1.24         # for PDF→image at 300 DPI
pillow>=10.0

# System
tesseract-ocr         # must be installed on OS
poppler-utils         # only if using pdf2image instead of pymupdf
```
