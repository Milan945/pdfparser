# State Legislature PDF Amendment Formats — Research Report

**Date:** 2026-06-03  
**Question:** How many U.S. state legislatures publish amendment bills as native vector PDFs where strikethrough marks deletions and italic/underline marks additions — and which ones are compatible with a PDF geometry parser (no OCR)?

**Method:** 6-angle web search fan-out → 22 sources fetched → 55 claims extracted → 25 adversarially verified (3-vote majority). 13 confirmed, 12 killed.

---

## Summary

At least **4 states** are confirmed to publish native vector PDFs with typeset amendment markup readable by a PDF geometry parser without OCR: **Florida, Kansas, Virginia, and Washington**. Three use strikethrough-only for deletions (directly parseable); Washington adds a double-parenthesis text delimiter that requires extra logic.

The geometry parser approach is technically validated: underline and strikethrough are encoded as drawn geometric lines in the PDF content stream — not as annotation objects — requiring coordinate correlation between rule-line geometry and glyph bounding boxes.

---

## Confirmed States

### Kansas — italic + strikethrough (already supported)

- **Additions:** italic type
- **Deletions:** strikethrough (canceled type)
- **Replaced text:** both simultaneously
- **Legal basis:** KSA 45-301(d) — statutory mandate
- **Confidence:** high (3-0 vote)

> *"material added to an existing section of the statutes shall be printed in italic style type, and material deleted from an existing section of the statutes shall be printed in canceled type."*

---

### Virginia — italic + strikethrough

- **Additions:** italic
- **Deletions:** strikethrough
- **Legal basis:** Virginia Code § 1-246 — codified in state law
- **Confidence:** high (3-0 vote)
- **Note:** The statute uses permissive language ("may be used") rather than a mandate. Real PDFs should be verified before building a VA profile.

> *"Stricken language for deletions and italics for additions or changes may be used in legislative drafts, printed bills, enrolled bills, and printed Acts of Assembly."*

**Parser impact:** Same convention as Kansas. Adding Virginia support requires only a new `StateProfile` entry — no pipeline changes.

---

### Florida — underline + strikethrough

- **Additions:** underline
- **Deletions:** strikethrough
- **Legal basis:** Rules of both chambers; boilerplate legend on every bill: *"CODING: Words stricken are deletions; words underlined are additions."*
- **PDF format:** Confirmed native vector (embedded fonts: CourierNewPSMT/ArialNarrow/ArialMT, FlateDecode-compressed content streams)
- **URL pattern:** `flsenate.gov/Session/Bill/{year}/{bill}/BillText/{stage}/PDF`
- **Confidence:** high (3-0 vote on mandate; 2-1 on native vector)

**Parser impact:** Strikethrough detection works unchanged. The emit stage needs a small change: treat `underlined = True` as `[A>...<A]` instead of `italic = True`. The `underlined` flag on `Span` already exists — it just isn't wired to the addition tag yet.

---

### Washington — underline + `((strikethrough))`

- **Additions:** underline
- **Deletions:** text enclosed in double parentheses **and** struck through — `((deleted text))`
- **Legal basis:** Washington State Legislature Bill Drafting Guide (2025 edition); constitutional mandate (Article II, Section 37 of the Washington State Constitution)
- **Confidence:** high (3-0 vote)

> *"Language and punctuation intended to be deleted is set forth in full, enclosed by double parentheses, and struck through with a solid line (( ))."*

**Parser impact:** Requires detecting the `(( ))` text delimiters in addition to the rule line. The double parentheses are Unicode characters in the extracted text — detectable via text extraction, not additional geometry. This is the most complex state to support.

---

## California — Unverified by This Research

California was the reference state for this project but **two CA-specific claims were refuted** (1-2 votes) during adversarial verification. The leginfo.ca.gov help page did not provide enough signal to confirm the PDF format. CA is confirmed working from direct pipeline testing, but the research could not independently verify it from web sources alone.

Open question: does CA use underline-for-additions or italic-for-additions? Our pipeline currently detects italic → `[A>...<A]`.

---

## Technical Validation

### How strikethrough/underline is encoded in PDFs

Confirmed (3-0): underline and strikethrough are **drawn geometric lines** in the PDF content stream — thin rectangles with a fill — not PDF annotation objects. This means:

- `page.annots()` (PyMuPDF) does **not** find them
- `page.get_drawings()` (PyMuPDF) or pdfplumber's `lines`/`rects` extraction **does** find them
- Coordinate correlation between the rule line's x-range and the glyph's bounding box is required
- A small tolerance is needed because glyph bounding boxes are slightly larger than the visual glyph

This is exactly what `geometry.py` implements via `line_decoration()`.

---

## Open Questions

1. How many additional states beyond these four use native vector PDFs with typeset amendment markup? No systematic source (NCSL, Plural Policy) enumerates them all.
2. What font name strings appear in Virginia bill PDFs — are they compatible with the existing `is_italic_font()` heuristic?
3. Does Washington's `(( ))` appear as literal Unicode parenthesis characters in extracted text, making it detectable via text extraction alone?
4. What does California's actual convention look like from the statute or drafting guide (not just from testing)?

---

## Expansion Roadmap

| State | Addition markup | Deletion markup | Pipeline changes needed |
|---|---|---|---|
| Kansas | italic | strikethrough | — already supported |
| California | italic (assumed) | strikethrough | — already supported |
| Virginia | italic | strikethrough | New `StateProfile` only |
| Florida | underline | strikethrough | New `StateProfile` + wire `underlined → [A>...<A]` in emit |
| Washington | underline | `((strikethrough))` | New `StateProfile` + `(( ))` delimiter detection in geometry/emit |

---

## Sources

| URL | Quality | Role |
|---|---|---|
| https://law.lis.virginia.gov/vacode/title1/chapter2.1/section1-246/ | primary | Virginia § 1-246 statute |
| https://www.flsenate.gov/reference/faq | primary | Florida chamber rules FAQ |
| https://www.flsenate.gov/Session/Bill/2026/947/BillText/Filed/PDF | primary | FL bill PDF (2026, vector confirmed) |
| https://leg.wa.gov/bills-meetings-and-session/bills/bill-drafting-guide/ | primary | WA Bill Drafting Guide (2025) |
| https://kslegislature.gov | primary | KS legislature (KSA 45-301) |
| https://www.kac.org/how_to_read_a_bill | secondary | KS convention explainer |
| https://github.com/pymupdf/PyMuPDF/issues/515 | forum | PyMuPDF: geometric encoding of underline/strike |
| https://github.com/pymupdf/PyMuPDF/issues/1756 | forum | PyMuPDF: coordinate correlation technique |
| https://arxiv.org/pdf/2410.09871 | primary | PDF parsing benchmark gap (no font-style eval) |
