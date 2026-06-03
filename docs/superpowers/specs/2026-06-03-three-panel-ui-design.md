# Three-Panel Bill Review UI — Design Spec

**Date:** 2026-06-03  
**Status:** Approved

---

## Overview

Replace the current Streamlit app with a React (Vite) + FastAPI three-panel UI that mirrors the Doctly review workflow: PDF viewer on the left, rendered markup preview in the middle, and an editable text panel on the right. Both the middle and right panels are downloadable as `.txt`.

---

## Architecture

```
Browser (React/Vite)
│
│  1. User uploads PDF
│  2. POST /upload  ──────────────►  FastAPI (api/)
│                                       │
│                                       ├─ saves PDF to temp file
│                                       ├─ runs netscan pipeline
│                                       └─ returns { session_id, state, markup, filename }
│
│  3. GET /pdf/{session_id}  ──────►  FastAPI
│                                       └─ streams temp PDF back
│
│  Left panel:  PDF.js renders /pdf/{session_id}
│  Mid panel:   parses markup → colored spans (read-only)
│  Right panel: textarea pre-filled with raw markup (editable)
│
│  Sync scrolling: scroll % on mid panel → same % applied to left panel (one-directional)
│
│  Download mid:   raw markup string → .txt blob
│  Download right: current textarea value → .txt blob
```

---

## Backend

### File structure

```
api/
├── main.py      # FastAPI app and endpoints
└── session.py   # temp file lifecycle (store, retrieve, cleanup)
```

### Endpoints

**`POST /upload`**  
Accepts multipart PDF upload plus an optional `state` form field.

- Saves PDF to a temp file, generates a UUID `session_id`
- Runs `detect_state()` — uses result unless `state` field was explicitly provided
- Runs `convert(tmp_path, state)`
- Returns:
  ```json
  {
    "session_id": "abc-123",
    "state": "KS",
    "markup": "Session of 2025\n\nHOUSE BILL...",
    "filename": "ks2203.txt"
  }
  ```
- If `detect_state()` returns `None` and no `state` was provided, returns `"state": null` — frontend handles the dropdown fallback

**`GET /pdf/{session_id}`**  
Streams the stored temp PDF. Returns 404 if session not found.

**`DELETE /session/{session_id}`**  
Deletes the temp file and removes the session entry. Called by the frontend on tab close via `navigator.sendBeacon`.

### Session management (`session.py`)

- In-memory `dict[str, Path]` mapping session IDs to temp file paths
- On server startup: sweep and delete temp files older than 1 hour (handles hard-crash leftovers)
- On new upload: delete the previous temp file for the same browser session if one exists (frontend passes prior `session_id` as a header)

---

## Frontend

### File structure

```
frontend/
├── index.html
├── vite.config.ts
├── src/
│   ├── main.tsx
│   ├── App.tsx               # upload flow + state machine
│   ├── components/
│   │   ├── UploadZone.tsx    # drag-and-drop / file picker
│   │   ├── PdfPanel.tsx      # PDF.js viewer (left)
│   │   ├── MarkupPanel.tsx   # rendered preview (middle)
│   │   └── EditorPanel.tsx   # textarea editor (right)
│   └── lib/
│       └── parseMarkup.ts    # [D>...<D] / [A>...<A] → React spans
```

### UI States

```
IDLE
│  UploadZone visible, no panels
▼
UPLOADING / CONVERTING
│  Spinner overlay, "Analyzing bill..."
▼
READY
│  Three panels visible
│  State badge: "KS — auto-detected"
│  "Upload new bill" button above panels
▼
ERROR
│  Error message
│  UploadZone reappears
```

If `state` is `null` in the response, READY shows a state dropdown (CA / KS) and a "Convert" button instead of the panels. Selecting a state re-calls `POST /upload` with the explicit `state` field.

### Panel layout

Three equal-width columns, full viewport height (`100vh`), each independently scrollable, sticky header row for download buttons.

```
┌─────────────────┬─────────────────┬─────────────────┐
│   PDF Viewer    │  Markup Preview │     Editor      │
│                 │                 │                 │
│  [PDF.js]       │  plain text     │  plain text     │
│                 │                 │                 │
│                 │  ~~deleted~~    │  [D>deleted<D]  │
│                 │  (red)          │  [A>added<A]    │
│                 │  added          │                 │
│                 │  (green)        │                 │
│─────────────────│─────────────────│─────────────────│
│                 │  [Download]     │  [Download]     │
└─────────────────┴─────────────────┴─────────────────┘
```

### Left panel — PDF viewer (`PdfPanel.tsx`)

- Renders the PDF via PDF.js (`pdfjs-dist`)
- Scrolls passively — position driven by middle panel's scroll ratio
- Default PDF.js toolbar (zoom, page number)
- Loads pages lazily for large documents

### Middle panel — Markup preview (`MarkupPanel.tsx`)

- `parseMarkup.ts` splits the markup string on `[D>...<D]` and `[A>...<A]` tokens
- `[D>text<D]` → `<span className="deletion">text</span>` (red, line-through)
- `[A>text<A]` → `<span className="addition">text</span>` (green)
- Plain text → bare text node
- Read-only (`pointer-events: none` on spans, no selection manipulation)
- `onScroll` fires → computes `scrollTop / (scrollHeight - clientHeight)` → applies ratio to PDF.js scroll position
- Download button: exports the original raw markup string (with tags) as `.txt`

### Right panel — Editor (`EditorPanel.tsx`)

- Plain `<textarea>` pre-filled with the raw markup string (tags visible)
- User edits freely — no validation, no sync back to middle panel
- Middle panel always shows the original extraction
- Download button: exports current `textarea.value` as `.txt`

### Sync scrolling

- One-directional: mid → left only (avoids feedback loops)
- Formula: `pdfScrollRatio = midPanel.scrollTop / (midPanel.scrollHeight - midPanel.clientHeight)`
- Applied to PDF.js viewer by setting its internal scroll position
- Clamped to `[0, 1]` — handles cases where PDF is shorter or taller than the markup panel

### Markup parser (`parseMarkup.ts`)

```ts
type Segment = { type: 'plain' | 'deletion' | 'addition'; text: string }

export function parseMarkup(markup: string): Segment[]
```

Splits on the bracket tag pattern with a single regex, classifies each segment, returns an array rendered as React elements by `MarkupPanel`.

---

## Error Handling

| Situation | Response |
|---|---|
| Unsupported state | 400: "State X is not yet supported. Supported: CA, KS." |
| Scanned/image-only PDF | 422: "This PDF appears to be scanned — no selectable text found." |
| Corrupt or non-PDF file | 422: "Could not read the file. Please upload a valid PDF." |
| Conversion exception | 500: "Conversion failed: {message}" |
| Empty markup output | Middle panel shows: "No amendment markup detected." |
| Session not found (GET /pdf) | 404 — frontend shows error state |

---

## Dependencies

**Backend**
- `fastapi`, `uvicorn[standard]` — API server
- `python-multipart` — file upload parsing
- `netscan` package (existing pipeline, installed as editable)

**Frontend**
- `react`, `react-dom`
- `vite` + `@vitejs/plugin-react`
- `pdfjs-dist` — PDF rendering
- `typescript`

No UI component library — plain CSS for the three-column layout to keep the dependency surface small.

---

## Out of Scope

- Authentication / multi-user sessions
- Persistent storage of conversions
- Saving edits back to the server
- Support for states beyond CA and KS (handled by the pipeline separately)
- Bidirectional sync scrolling
