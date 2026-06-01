# Legislative Bill PDF → NetScan Markup Converter — Design Spec

**Date:** 2026-06-01
**Status:** Approved (brainstorm), pending spec review
**Working dir:** `D:\Projects\OCR Parser`

## 1. Purpose

Convert U.S. state legislative bill PDFs into clean, markup-tagged plain text for
the NetScan ingestion system. The hard requirement is **faithful detection of
amendment formatting** — strikethrough (deleted text), underline (added text),
bold, and italic — because in legislative drafting these markings carry legal
meaning.

## 2. Core principle

> **The PDF is the source of truth. The VLM only adjudicates the few genuinely
> ambiguous cases. A verifier catches what slips through.**

A native legislative PDF already *contains* its formatting as structured data:
characters with font flags (bold/italic) and strike/underline as vector rule
lines in the content stream. We read that ground truth deterministically and send
the VLM only the ambiguous residual. Every span the VLM never sees is a span that
cannot be hallucinated, dropped, or mis-tagged.

## 3. Locked decisions

| Topic | Decision |
|---|---|
| Codebase | Greenfield, fresh build |
| NetScan markup | Legislative bracket tags: `[[del]]…[[/del]]`, `[[ins]]…[[/ins]]`, `[[b]]…[[/b]]`, `[[i]]…[[/i]]` |
| Format mapping | strikethrough → `[[del]]`; underline → `[[ins]]`; bold → `[[b]]`; italic → `[[i]]` |
| PDF library | MIT stack (`pdfplumber` / `pdfminer.six`) behind a thin `pdf_backend` adapter (swappable for a licensed PyMuPDF later) |
| VLM provider | Azure / OpenAI **vision** model (gpt-4o / 4.1-class) behind a `vlm` adapter. *Deviation from the source prompt's Opus 4.8, driven by available API access. Architecture is provider-agnostic behind the adapter.* |
| Bulk OCR (Job B) | Pluggable interface; **stubbed in Phase 1** — scanned/image-only pages route to the QA queue until a real OCR backend is wired |
| Interface | Streamlit GUI (live progress, session management, downloads) + CLI batch script |
| Storage | In-memory page rendering / region cropping; no temp files on disk |

### Open confirmations (resolve during spec review)
1. **`[[u]]` is never emitted.** Under the chosen mapping, underline always means
   *insertion* (`[[ins]]`). There is no separate "underline-as-emphasis" tag.
   Confirm no distinct `[[u]]` is required. (The example originally shown contained
   `[[u]]new[[/u]]`; the chosen mapping supersedes it.)

## 4. Critical risk & gating milestone

**Unverified empirical premise:** the architecture assumes strike/underline reliably
appear as **vector rule lines** (`lines` / `rects`). Font flags give bold/italic for
free but carry **no** strike/underline bit — so rule-line ↔ glyph correlation does
*all* the work for the legally-meaningful signals. Some drafting tools instead emit
these as font rendering, overprint, or combining characters, which geometry would
silently miss.

**Mitigation — Milestone 1 is a geometry spike** on 2–3 real bills with an explicit
go/no-go gate:
- If rule-line correlation surfaces strike/underline cleanly → proceed to build
  stages 2–7 on it.
- If not → escalate more spans to the QA/VLM path and document the detection gap
  before building downstream stages on a false premise.

## 5. Pipeline (7 stages)

1. **Page triage** — native vs scanned per page (meaningful text layer vs
   empty/garbage). Native → geometry path. Scanned → Job B fallback. Never one path
   for all pages.
2. **Geometry extraction** (native, deterministic, no model) — per page: chars +
   bboxes + font flags (bold/italic taken directly); vector lines/rects;
   correlate line geometry vs glyph boxes (mid-glyph height = strikethrough;
   near baseline = underline) with deterministic overlap math.
3. **Conflict detection** — flag ONLY the ambiguous residual: strike/underline
   ambiguous by vertical position; drawings/text-box misalignment; color-only
   emphasis (no rule line); tables / multi-column with uncertain reading order.
   These flagged regions — not whole documents — are the VLM's input.
4. **VLM resolution** (targeted + batched) — **Job A**: adjudicate flagged spans
   (render only the flagged region/page, narrow question). **Job B**: extract
   scanned pages (full-page reading). Process in small batches (3–5) with a short
   running style/context summary for cross-page consistency. No single giant call.
   *Phase 1: Job A and Job B are stubbed — flagged/scanned spans go to the QA queue.*
5. **Reconcile** into a tagged token stream — precedence: (1) geometry + font flags
   win when confident; (2) VLM resolves flagged conflicts; (3) record per-span
   confidence. Output: ordered `Span(text, formatting, confidence, source)` in
   correct reading order.
6. **Emit NetScan markup** — map token stream to bracket tags. Pure deterministic
   formatting step. Mapping table is the single source of truth (swappable per state
   if ever needed).
7. **Verify** — round-trip diff (strip markup → compare to extracted plain text; any
   char mismatch flags dropped/hallucinated text) + QA queue of every low-confidence
   span. "99.99%" is achieved *post-QA* with a minimal flagged set.

**State detection (parallel):** filename-pattern match first (instant); AI
content-analysis fallback only on miss.

## 6. Architecture — modules

```
pdf_backend/   only module that touches pdfplumber; returns chars+bboxes, lines, rects
triage/        Stage 1
geometry/      Stage 2
conflict/      Stage 3
vlm/           Stage 4: Job A + Job B adapters (stubbed Phase 1)
reconcile/     Stage 5
emit/          Stage 6
verify/        Stage 7: round-trip diff + QA queue
state_detect/  filename pattern → AI fallback
pipeline.py    orchestration, small-batch processing, running style summary
cli.py         CLI batch script
app.py         Streamlit GUI
```

Each module: one job, typed dataclass interface between stages, independently testable.

### Core data type
```
Span(text, bold, italic, struck, underlined, confidence, source)
  source ∈ {geometry, font_flag, vlm, ocr}
  confidence ∈ [0, 1]
```

### Data flow
```
PDF → triage
   ├─ native  → geometry → conflict ─┐
   └─ scanned → Job B (stub→QA) ─────┤
                                     ↓
            (flagged spans → Job A or QA queue)
                                     ↓
              reconcile → emit → verify → {markup output, QA queue}
```

## 7. Error handling & confidence

- Every span carries confidence: geometry + font-flags = high; VLM-resolved =
  recorded value; unresolved/ambiguous = low → QA queue.
- Round-trip diff hard-fails on any character mismatch (dropped or hallucinated text).
- Scanned pages with no wired OCR backend → QA queue (Phase 1), never silent drop.
- No temp files; in-memory rendering/cropping.

## 8. Testing

- **Synthetic fixtures:** programmatically generated PDFs with known
  strike/underline/bold/italic → deterministic unit tests for geometry, emit, and
  round-trip. No real bills or API keys needed.
- **Real-bill spike:** Milestone 1 empirical gate (public state-legislature PDFs).
- **Metrics measured (not char-accuracy alone):** span-level formatting accuracy;
  fraction of spans routed to VLM (lower = better); round-trip mismatch rate;
  QA-queue size per document.

## 9. Model strategy

- Job A (adjudication): narrow, hard, low-volume → Azure/OpenAI vision model.
- Job B (bulk scanned extraction): high-volume, mostly straightforward → cheaper
  OCR backend behind the same interface (stubbed Phase 1).
- Most native bills hit neither path, so total VLM spend stays small.
- Before committing reasoning level, test 10–15 genuinely ambiguous spans and use
  the lowest setting that nails adjudication.

## 10. Milestones

1. **Geometry spike** on 2–3 real bills → go/no-go on the rule-line premise.
2. `pdf_backend` + `triage` + `geometry` + synthetic fixtures + tests.
3. `conflict` + `reconcile` + `emit` + round-trip `verify` → native PDFs work
   end-to-end, no API.
4. `state_detect` + CLI + Streamlit GUI.
5. Wire real Job A (Azure/OpenAI vision) + Job B OCR adapter.

## 11. Non-goals

- No blind, no-human pipeline claiming 99.99%. Aim for 99.99% *post-QA* with a
  minimal flagged set.
- Do not send whole documents to the VLM when geometry has resolved the spans.

## 12. What must not regress (from v1 concept)

- ❌ "Render all pages, VLM reads everything" → ✅ geometry-first, VLM only on residual.
- ❌ Single-pass / all-pages-in-one-call → ✅ small batches w/ running context;
  granular retry; no truncation cliff.
- ❌ No error detection → ✅ round-trip diff + per-span confidence + human QA queue.
- ❌ Vision as sole oracle for strike/underline → ✅ vector rule lines + font flags
  as ground truth.
