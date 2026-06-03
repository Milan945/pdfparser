# Deep Research: How Doctly Works, and How We Reach 99.99% PDF-Faithful Extraction

**Date:** 2026-06-02
**Question researched:** How does Doctly.ai perform PDF-to-text/document parsing (architecture, VLM/OCR approach, accuracy claims, known limitations), and what are the established techniques for making programmatic PDF text extraction 99.99% faithful to the source PDF (geometry/vector-based extraction, font-flag and vector-rule-line detection for strikethrough/underline/italic, Unicode normalization, round-trip content verification, hallucination-prevention for any LLM/VLM-assisted correction pass)?
**Method:** Deep-research workflow. 103 agents, 5 search angles, 21 sources fetched, 96 claims extracted, 25 adversarially verified (3-vote, 2/3 to kill). Result: 23 confirmed, 2 killed.

---

## Executive summary

Doctly is not a single VLM or pure OCR engine. It is an agentic document parser that detects page features/layout and routes each page to the best-fit AI vision model, falling back to traditional OCR in some cases, with selectable accuracy tiers (lite/ultra). Its output target is structured Markdown/JSON, not a faithful raw-text dump. The co-founder has admitted on the record that the pipeline fabricates content (placeholder image URLs).

The research literature confirms VLM/MLLM OCR is intrinsically fragile and hallucination-prone: it degrades under blur/occlusion/low-contrast, overrelies on linguistic/parametric priors when the visual signal is ambiguous, and is systematically overconfident (so VLM self-reported confidence is an unreliable error signal). This is exactly why a deterministic geometry-first pipeline is preferable on native-text PDFs.

pdfplumber (built on pdfminer.six, no OCR) supplies the geometry-first primitives we need: per-character bounding boxes, font size, fontname, plus vector .lines/.rects/.curves. Faithful Unicode recovery is a hard, well-specified problem requiring a deterministic per-glyph cascade and ligature normalization. The core hallucination guard for any correction pass is round-trip verification: discard any extracted text not present in the source.

---

## Part 1: What Doctly actually is

Verified from the co-founder's own statements (Hacker News, founder Medium post) and the official docs/SDK.

- **Agentic router (high, 3-0).** Detects page features and layout, routes each page to the best-fit AI vision model, falls back to traditional OCR in some cases. Uses multiple vision models because different ones excel at different sub-tasks (language, tables, charts). No single model is faithful alone.
  - Source: Co-founder (kapitalx) on HN, verbatim: "we detect features/layout within the document and route them to different models and in some cases traditional OCR" and "AI vision models can do pretty well, but different ones excel at different things. From language support to table and chart conversion." Corroborated by founder Medium article + Doctly marketing. Caveat: founder self-description, no independent audit, dated ~Oct 2024.
- **Accuracy tiers (high, 2-1).** An `accuracy` API parameter: `lite` (fast, default) and `ultra` (highest accuracy, generates multiple versions per page and picks the best). Confirmed in the official Python SDK `Accuracy.LITE` / `Accuracy.ULTRA` enums.
  - Source: docs.doctly.ai API reference (`-F 'accuracy=ultra'`), github.com/doctly/doctly.
- **Output is structured Markdown/JSON, not raw text (high, 3-0).**
  - Source: Doctly docs ("turns unstructured documents into structured, machine-readable data... perfectly formatted Markdown or JSON").
- **Doctly hallucinates (high, 3-0).** The pipeline fabricates content not present in the source, specifically placeholder image URLs for images that were never actually extracted.
  - Source: Co-founder admission on HN: regarding fabricated image references, "that's something the LLMs are making up as they go along" and it is "something we need to fix." Strongest possible source quality (direct founder admission, not marketing).

**Implication for us:** Doctly is a VLM-per-page parser with a documented, founder-admitted hallucination defect. That is exactly the failure class our geometry-first design avoids. We are not copying Doctly's method; we match its output format while being structurally more faithful.

---

## Part 2: Why geometry-first is the right call (the literature)

- **Fragility (high, 3-0).** VLM/MLLM OCR degrades severely under blur, snow, occlusion, low contrast. Named SOTA models (Claude-3, Gemini-1.5, GPT-4o, GPT-4V, Qwen2.5-VL, InternVL3) all exhibit it as a persistent, unresolved failure mode.
  - Sources: arXiv 2506.20168 (KIE-HVQA benchmark), 2502.06445, 2511.19806v1, 2504.13690.
- **Prior-override (high, 3-0).** When the visual signal is ambiguous, models default to linguistic/parametric priors and "generate hallucinatory content, especially when a precise answer is not feasible." For statutory text this is disqualifying.
  - Source: arXiv 2506.20168 verbatim. Corroborated by MLLM hallucination survey (2404.18930).
- **Overconfidence (high, 3-0).** VLMs are systematically miscalibrated; their self-reported confidence / token probabilities are an unreliable signal for detecting OCR errors. "VLMs exhibit systematic miscalibration with prevalent overconfidence."
  - Source: arXiv 2511.19806v1 (Nov 2025). Qualifier: token-level entropy can still localize error hotspots (2505.00746) as a relative ranking signal, not calibrated self-confidence.

**Implication for us:** We cannot trust a VLM's own confidence in any correction pass. Cross-model disagreement (the revamp's judge design) is a valid signal; a single model's confidence score is not.

---

## Part 3: The concrete techniques for 99.99% faithful extraction

### Technique 1: Geometry primitives (we already have this)

- **pdfplumber per-char geometry (high, 3-0).** Built on pdfminer.six, no OCR, works best on machine-generated PDFs. Exposes exact `x0/x1/y0/y1`, `size`, `fontname` for every content-stream glyph.
  - Source: github.com/jsvine/pdfplumber README + local reproduction on 0.11.9. Scope: applies to content-stream glyphs, not image-baked text (consistent with non-OCR scope).
- **pdfplumber vector shapes (high, 3-0).** `.lines`, `.rects`, `.curves` each carry position/linewidth data. Thin horizontal line/rect objects are how rule-line-rendered underline/strikethrough appear in vector PDF content.
  - Source: same README. Caveat: strike/underline are sometimes encoded as font glyph decorations rather than vector lines (see Technique 4).

**Status:** Confirms our backend choice. No action needed.

### Technique 2: Unicode recovery (a likely fidelity gap for us)

Verified against a granted USPTO patent (PDFlib GmbH, US 7,636,885 B2, 2009).

- **Glyph IDs are not Unicode (high, 3-0).** Correct text depends on the ToUnicode CMap, which is frequently incorrect, incomplete, or absent. Complex-layout scripts (e.g. Indic) cannot be copied correctly unless annotated with /ActualText (glyph order is visual, Unicode is phonetic).
  - Sources: shreevatsa/pdf-glyph-mapping, W3C WAI list. Structural property of ISO 32000, not time-sensitive.
- **Deterministic per-glyph cascade (high, 3-0).** Unicode is determined per-glyph (not per-font) in fixed priority: (1) predefined CMaps for CID fonts, (2) external ToUnicode, (3) internal/embedded ToUnicode, (4) inverting the embedded TrueType/OpenType cmap, (5) glyph-name method for simple fonts (code -> glyph name -> decompose -> external list -> algorithmic heuristic -> Adobe Glyph List -> internal non-standard names).
  - Source: US Patent 7,636,885 B2 Claim 1 + flowchart. Matches how pdfminer/pdfplumber and MuPDF operate. Note: general established technique (PDFlib), not Doctly-proprietary.
- **Ligatures corrupt extraction (high, 3-0).** Glyphs ff/fi/fl/ffi/ffl mapped to presentation-form codepoints U+FB00-U+FB04 in a ToUnicode CMap corrupt copy/paste and extraction. Root cause: ambiguous glyph-to-Unicode mapping in font subsetting. Fix: map the ligature glyph to its constituent characters (e.g. <00660066> for "ff"), omit ligatures from the CMap, or emit /ActualText (Chrome's approach).
  - Source: Mozilla bug 1810914 (Jonathan Kew, Mozilla gfx). Corroborated by Adobe Acrobat community, Unicode standard, PrinceXML, pdf2htmlEX. Caveat: "should not be used in ToUnicode" is interoperability convention, not a hard ISO 32000 prohibition.

**Status:** Extends our existing normalization (U+2044->/, NBSP, zero-width, curly quotes). **Action: add U+FB00-FB04 ligature normalization; implement per-glyph cascade fallback for broken/absent ToUnicode maps.**

### Technique 3: Round-trip verification (the hallucination guard)

- **Discard text not in the source (high, 3-0 / 2-1).** "A simple way to avoid hallucinations is to remove any extracted text that does not appear in the original source." Contiguous spans = exact string match; discontiguous spans = ordered token alignment. A token-alignment verifier (taln) doing this is fast and deterministic, unlike LLM-based verification which is slow, expensive, and non-deterministic.
  - Sources: bioRxiv 704502 v2 (Booeshaghi & Streets, Feb 2026), github.com/sbooeshaghi/taln (n-gram indexing + DFS order-preserving alignments via tiktoken, no LLM).

**Status:** Our content-invariant gate in `llm_correction.py` is exactly this principle. **Action: upgrade to handle discontiguous spans via ordered token alignment, not just whole-string equality.**

### Technique 4: Strike/underline as glyph decoration (an open gap)

From the research caveats: our `.lines`/`.rects` detection is **necessary but not sufficient**. Some PDFs encode strikethrough/underline as styled glyphs or combining marks rather than vector lines. Vector-rule detection alone misses that encoding.

**Status: Action: add a test for strike/underline encoded as glyph decoration (not just vector lines) on CA and KS bills.**

---

## Bottom line on "99.99% same as the PDF"

The research confirms and sharpens our architecture. Honest picture:

- **Text fidelity to ~100% is achievable deterministically** on native-text bills, because we read glyphs not pixels. The gating risk is not detection; it is Unicode recovery (ligatures, missing ToUnicode maps) and structure (reflow, gutters), exactly as we assessed.
- **The "99.99%" claim is defensible only with the round-trip verifier in place** plus a small QA queue. It is not a blind/automated guarantee on every document. Any VLM correction pass must be text-locked (ours is), because VLM self-confidence is provably unreliable.

### Four concrete next actions this research surfaces

1. Add ligature normalization (U+FB00-FB04) to our Unicode pass and test against Doctly output.
2. Implement the per-glyph Unicode cascade fallback for PDFs with broken/absent ToUnicode maps.
3. Upgrade round-trip verification to handle discontiguous spans via ordered token alignment.
4. Add a test for strike/underline encoded as glyph decoration (not just vector lines) on CA and KS bills.

---

## Open questions (not resolved by available sources)

1. What is Doctly's actual measured byte-level faithfulness on native-text legislative bill PDFs (not scanned/degraded inputs), and does it normalize ligature presentation-forms and apply the per-glyph Unicode cascade, or inherit those defects? No independent benchmark of Doctly output fidelity was found.
2. How should the geometry-first pipeline disambiguate strikethrough/underline encoded as font glyph decoration rather than vector lines?
3. For amendment markup, what reading-order / column-segmentation algorithm reconstructs correct logical order from per-character geometry on multi-column/two-column bill layouts, and how is that verified against the source?
4. On native-text bills, does an LLM correction pass add net value at all once round-trip token-alignment verification is in place, given the demonstrated hallucination and overconfidence risks?

---

## Claims that were refuted (excluded from findings)

- "Subword tokenization with LLM-specific tokenizers improves alignment accuracy ~50% vs word-level." Vote 1-2. Source: bioRxiv 704502 v2. (Qualitative deterministic-verification claim survived; this quantitative claim did not.)
- "The benchmark evaluates faithfulness via eight specific error metrics (NL+/NL-, P+/P-/P-arrow, W+/W-/W~)." Vote 0-3. Source: ckorzen/pdf-text-extraction-benchmark.

---

## Caveats on source quality

Source quality is strong overall (primary HN founder statements, official Doctly docs/SDK, the pdfplumber repo + local reproduction, a granted USPTO patent, an upstream Mozilla engineering bug, recent arXiv/bioRxiv preprints), with these caveats:

1. Doctly architecture claims rest entirely on founder self-description (HN ~Oct 2024 + marketing) with no independent technical audit; architecture may have evolved.
2. VLM-fragility literature is fast-moving; arXiv 2502.06445 is video-OCR specific. The "therefore geometry-first is preferable on native-text PDFs" conclusion is contextual inference, not an empirical finding in any cited paper. VLM fragility is established for degraded/scanned inputs, a different regime from clean native-text PDFs.
3. The Unicode-cascade patent belongs to PDFlib GmbH and describes a general technique, not Doctly's proprietary method.
4. The ligature/ToUnicode guidance is an interoperability convention, not a hard ISO 32000 prohibition; root cause scoped to cmap-driven subsetting producers.
5. The token-alignment paper is a Feb 2026 preprint; its quantitative ~50% claim was refuted and excluded. Only the qualitative deterministic-verification and contiguous/discontiguous-matching claims survived.
6. Strikethrough/underline can be encoded as font glyph decorations rather than vector lines, so vector-line detection alone is necessary but not sufficient.

---

## Sources (by angle)

**Doctly product (primary):**
- https://news.ycombinator.com/item?id=41948448 (co-founder statements)
- https://doctly.ai/ , https://docs.doctly.ai/ , https://github.com/doctly/doctly

**VLM failure modes:**
- https://arxiv.org/pdf/2506.20168 (KIE-HVQA)
- https://arxiv.org/abs/2502.06445
- https://arxiv.org/html/2511.19806v1 (overconfidence)
- https://arxiv.org/abs/2504.13690 / https://arxiv.org/pdf/2504.18639
- https://reducto.ai/blog/lvm-ocr-accuracy-mistral-gemini
- https://www.dataunboxed.io/blog/ocr-vs-vlm-ocr-naive-benchmarking-accuracy-for-scanned-documents

**Geometry-first extraction:**
- https://github.com/jsvine/pdfplumber
- https://woteq.com/how-to-get-bounding-boxes-of-text-using-pdfplumber
- https://www.biorxiv.org/content/10.64898/2026.02.06.704502v2.full.pdf (taln)

**Unicode faithfulness:**
- https://github.com/shreevatsa/pdf-glyph-mapping
- https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/7636885 (US Patent 7,636,885 B2, PDFlib)
- https://bugzilla.mozilla.org/show_bug.cgi?id=1810914 (ligatures)
- https://lists.w3.org/Archives/Public/w3c-wai-ig/2016JanMar/0000.html

**Hallucination prevention:**
- https://github.com/sbooeshaghi/taln
- https://arxiv.org/abs/2505.24347 , https://arxiv.org/html/2410.13305v1 , https://arxiv.org/pdf/2403.06988 , https://arxiv.org/pdf/2411.07870
- https://airbyte.com/agentic-data/prevent-llm-hallucinations
