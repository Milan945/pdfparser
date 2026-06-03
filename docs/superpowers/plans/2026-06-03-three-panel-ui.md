# Three-Panel Bill Review UI — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Streamlit app with a React (Vite) + FastAPI three-panel UI: PDF viewer | rendered markup preview | editable text panel, with one-directional scroll sync from the middle panel to the left.

**Architecture:** FastAPI backend (api/) wraps the existing netscan pipeline and exposes three endpoints: POST /upload, GET /pdf/{session_id}, DELETE /session/{session_id}. React (Vite) frontend calls those endpoints and renders three equal-width panels. Markup is parsed client-side from the raw bracket syntax into colored spans. Scroll sync is one-directional: middle panel onScroll → PDF.js scroll position.

**Tech Stack:** Python 3.11+, FastAPI, uvicorn[standard], python-multipart; React 18, TypeScript, Vite, pdfjs-dist, Vitest

---

## File Map

**New files — backend**
- `api/__init__.py` — empty, makes api a package
- `api/session.py` — in-memory session store + temp file lifecycle
- `api/main.py` — FastAPI app, three endpoints
- `tests/test_api.py` — pytest tests for all three endpoints

**Modified files — backend**
- `pyproject.toml` — add `api` optional-dependency group (fastapi, uvicorn, python-multipart)

**New files — frontend**
- `frontend/package.json` — npm dependencies
- `frontend/vite.config.ts` — Vite config with /api proxy to localhost:8000
- `frontend/tsconfig.json` — TypeScript config
- `frontend/index.html` — HTML shell
- `frontend/src/main.tsx` — React root mount
- `frontend/src/App.tsx` — state machine (IDLE / UPLOADING / READY / ERROR)
- `frontend/src/App.css` — three-column layout, panel styles
- `frontend/src/lib/parseMarkup.ts` — bracket tag → Segment[] parser
- `frontend/src/lib/parseMarkup.test.ts` — Vitest unit tests for parser
- `frontend/src/components/UploadZone.tsx` — drag-and-drop / file picker
- `frontend/src/components/PdfPanel.tsx` — PDF.js viewer, receives scrollRatio prop
- `frontend/src/components/MarkupPanel.tsx` — renders colored spans, fires onScroll
- `frontend/src/components/EditorPanel.tsx` — textarea + download button

---

## Task 1: Add backend dependencies

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add api dependency group to pyproject.toml**

Replace the `[project.optional-dependencies]` section with:

```toml
[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "reportlab>=4.0",
    "httpx>=0.27",
]
ui = [
    "streamlit>=1.30",
]
api = [
    "fastapi>=0.111",
    "uvicorn[standard]>=0.29",
    "python-multipart>=0.0.9",
    "httpx>=0.27",
]
```

- [ ] **Step 2: Install api dependencies**

```bash
pip install -e ".[api]"
```

Expected: installs fastapi, uvicorn, python-multipart, httpx — no errors.

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "chore: add fastapi/uvicorn/httpx dependencies for api group"
```

---

## Task 2: Session store (`api/session.py`)

**Files:**
- Create: `api/__init__.py`
- Create: `api/session.py`
- Create: `tests/test_session.py`

- [ ] **Step 1: Create api package**

Create `api/__init__.py` as an empty file.

- [ ] **Step 2: Write failing tests**

Create `tests/test_session.py`:

```python
import time
from pathlib import Path
import tempfile
import pytest
from api.session import store_session, get_session, delete_session, cleanup_old_sessions


@pytest.fixture
def tmp_pdf(tmp_path):
    f = tmp_path / "bill.pdf"
    f.write_bytes(b"%PDF-1.4 fake")
    return f


def test_store_and_retrieve(tmp_pdf):
    store_session("abc", tmp_pdf)
    assert get_session("abc") == tmp_pdf


def test_get_missing_returns_none():
    assert get_session("does-not-exist") is None


def test_delete_removes_entry_and_file(tmp_pdf):
    store_session("del1", tmp_pdf)
    delete_session("del1")
    assert get_session("del1") is None
    assert not tmp_pdf.exists()


def test_delete_missing_session_is_noop():
    delete_session("no-such-session")  # must not raise


def test_cleanup_old_sessions_removes_expired(tmp_path):
    old_file = tmp_path / "old.pdf"
    old_file.write_bytes(b"%PDF")
    store_session("old1", old_file)
    # Force the stored timestamp to be old
    from api import session as sess_module
    sess_module._sessions["old1"] = (old_file, time.time() - 7200)
    cleanup_old_sessions(max_age_seconds=3600)
    assert get_session("old1") is None
    assert not old_file.exists()


def test_cleanup_keeps_fresh_sessions(tmp_path):
    fresh_file = tmp_path / "fresh.pdf"
    fresh_file.write_bytes(b"%PDF")
    store_session("fresh1", fresh_file)
    cleanup_old_sessions(max_age_seconds=3600)
    assert get_session("fresh1") == fresh_file
```

- [ ] **Step 3: Run tests — verify they fail**

```bash
pytest tests/test_session.py -v
```

Expected: `ModuleNotFoundError: No module named 'api'`

- [ ] **Step 4: Implement `api/session.py`**

```python
from __future__ import annotations
import time
from pathlib import Path

# Maps session_id -> (Path, created_timestamp)
_sessions: dict[str, tuple[Path, float]] = {}


def store_session(session_id: str, path: Path) -> None:
    _sessions[session_id] = (path, time.time())


def get_session(session_id: str) -> Path | None:
    entry = _sessions.get(session_id)
    return entry[0] if entry else None


def delete_session(session_id: str) -> None:
    entry = _sessions.pop(session_id, None)
    if entry:
        path, _ = entry
        if path.exists():
            path.unlink()


def cleanup_old_sessions(max_age_seconds: int = 3600) -> None:
    now = time.time()
    expired = [sid for sid, (_, ts) in _sessions.items()
               if now - ts > max_age_seconds]
    for sid in expired:
        delete_session(sid)
```

- [ ] **Step 5: Run tests — verify they pass**

```bash
pytest tests/test_session.py -v
```

Expected: 6 passed.

- [ ] **Step 6: Commit**

```bash
git add api/__init__.py api/session.py tests/test_session.py
git commit -m "feat(api): session store with temp file lifecycle"
```

---

## Task 3: FastAPI endpoints (`api/main.py`)

**Files:**
- Create: `api/main.py`
- Create: `tests/test_api.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_api.py`:

```python
import io
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)

SAMPLE_PDF = Path("samples/there samples/2025_2026_16_2_2_002203_0_4_1_20250203_0.pdf")


@pytest.fixture(autouse=True)
def clear_sessions():
    from api import session as sess
    sess._sessions.clear()
    yield
    sess._sessions.clear()


def test_upload_valid_pdf_returns_markup():
    with open(SAMPLE_PDF, "rb") as f:
        response = client.post(
            "/upload",
            files={"file": ("ks2203.pdf", f, "application/pdf")},
            data={"state": "KS"},
        )
    assert response.status_code == 200
    body = response.json()
    assert "session_id" in body
    assert "markup" in body
    assert "filename" in body
    assert body["state"] == "KS"
    assert len(body["markup"]) > 100


def test_upload_auto_detects_state():
    with open(SAMPLE_PDF, "rb") as f:
        response = client.post(
            "/upload",
            files={"file": ("ks2203.pdf", f, "application/pdf")},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["state"] in ("KS", None)


def test_upload_unsupported_state_returns_400():
    with open(SAMPLE_PDF, "rb") as f:
        response = client.post(
            "/upload",
            files={"file": ("bill.pdf", f, "application/pdf")},
            data={"state": "TX"},
        )
    assert response.status_code == 400
    assert "not yet supported" in response.json()["detail"].lower()


def test_upload_non_pdf_returns_422():
    fake = io.BytesIO(b"this is not a pdf")
    response = client.post(
        "/upload",
        files={"file": ("bill.txt", fake, "text/plain")},
        data={"state": "KS"},
    )
    assert response.status_code == 422


def test_get_pdf_returns_bytes():
    with open(SAMPLE_PDF, "rb") as f:
        upload = client.post(
            "/upload",
            files={"file": ("ks2203.pdf", f, "application/pdf")},
            data={"state": "KS"},
        )
    session_id = upload.json()["session_id"]
    response = client.get(f"/pdf/{session_id}")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content[:4] == b"%PDF"


def test_get_pdf_unknown_session_returns_404():
    response = client.get("/pdf/no-such-id")
    assert response.status_code == 404


def test_delete_session_removes_it():
    with open(SAMPLE_PDF, "rb") as f:
        upload = client.post(
            "/upload",
            files={"file": ("ks2203.pdf", f, "application/pdf")},
            data={"state": "KS"},
        )
    session_id = upload.json()["session_id"]
    response = client.delete(f"/session/{session_id}")
    assert response.status_code == 200
    assert client.get(f"/pdf/{session_id}").status_code == 404
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
pytest tests/test_api.py -v
```

Expected: `ModuleNotFoundError: No module named 'api.main'`

- [ ] **Step 3: Implement `api/main.py`**

```python
from __future__ import annotations
import os
import tempfile
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from netscan.detect import detect_state
from netscan.pipeline import convert
from netscan.profiles import PROFILES
from api.session import cleanup_old_sessions, delete_session, get_session, store_session

app = FastAPI(title="NetScan Bill Converter API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    cleanup_old_sessions(max_age_seconds=3600)


@app.post("/upload")
async def upload(
    file: UploadFile = File(...),
    state: str | None = Form(default=None),
) -> JSONResponse:
    if file.content_type not in ("application/pdf", "application/octet-stream"):
        if not (file.filename or "").lower().endswith(".pdf"):
            raise HTTPException(status_code=422, detail="Please upload a valid PDF file.")

    data = await file.read()
    if not data.startswith(b"%PDF"):
        raise HTTPException(status_code=422, detail="Please upload a valid PDF file.")

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as fh:
        fh.write(data)
        tmp_path = fh.name

    try:
        resolved_state = state or detect_state(tmp_path)
        if resolved_state and resolved_state not in PROFILES:
            os.unlink(tmp_path)
            supported = ", ".join(sorted(PROFILES))
            raise HTTPException(
                status_code=400,
                detail=f"State {resolved_state!r} is not yet supported. Supported: {supported}.",
            )

        if resolved_state:
            markup = convert(tmp_path, resolved_state)
        else:
            markup = ""

        session_id = str(uuid.uuid4())
        store_session(session_id, Path(tmp_path))
        stem = Path(file.filename or "bill").stem
        return JSONResponse({
            "session_id": session_id,
            "state": resolved_state,
            "markup": markup,
            "filename": f"{stem}.txt",
        })
    except HTTPException:
        raise
    except Exception as exc:
        os.unlink(tmp_path)
        raise HTTPException(status_code=500, detail=f"Conversion failed: {exc}") from exc


@app.get("/pdf/{session_id}")
def get_pdf(session_id: str) -> FileResponse:
    path = get_session(session_id)
    if path is None or not path.exists():
        raise HTTPException(status_code=404, detail="Session not found.")
    return FileResponse(path, media_type="application/pdf")


@app.delete("/session/{session_id}")
def remove_session(session_id: str) -> JSONResponse:
    delete_session(session_id)
    return JSONResponse({"ok": True})
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
pytest tests/test_api.py -v
```

Expected: 8 passed.

- [ ] **Step 5: Verify server starts**

```bash
uvicorn api.main:app --reload
```

Expected: `Uvicorn running on http://127.0.0.1:8000`. Ctrl+C to stop.

- [ ] **Step 6: Commit**

```bash
git add api/main.py tests/test_api.py
git commit -m "feat(api): FastAPI endpoints for upload, pdf streaming, session delete"
```

---

## Task 4: Scaffold React + Vite frontend

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/tsconfig.json`
- Create: `frontend/index.html`
- Create: `frontend/src/main.tsx`

- [ ] **Step 1: Scaffold the Vite app**

```bash
cd frontend
npm create vite@latest . -- --template react-ts
```

When prompted "Current directory is not empty. Remove existing files and continue?" — choose **Yes** only if the directory is empty. Otherwise run in the `frontend/` directory directly.

- [ ] **Step 2: Install dependencies**

```bash
cd frontend
npm install
npm install pdfjs-dist
```

Expected: `node_modules/` created, `pdfjs-dist` listed in `package.json` dependencies.

- [ ] **Step 3: Configure Vite proxy**

Replace the contents of `frontend/vite.config.ts` with:

```ts
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/upload': 'http://localhost:8000',
      '/pdf': 'http://localhost:8000',
      '/session': 'http://localhost:8000',
    },
  },
  test: {
    environment: 'node',
  },
})
```

- [ ] **Step 4: Install Vitest**

```bash
cd frontend
npm install -D vitest
```

- [ ] **Step 5: Verify dev server starts**

```bash
cd frontend
npm run dev
```

Expected: `Local: http://localhost:5173/` — default Vite React page. Ctrl+C to stop.

- [ ] **Step 6: Commit**

```bash
git add frontend/
git commit -m "chore(frontend): scaffold Vite + React + TypeScript + pdfjs-dist"
```

---

## Task 5: Markup parser (`parseMarkup.ts`)

**Files:**
- Create: `frontend/src/lib/parseMarkup.ts`
- Create: `frontend/src/lib/parseMarkup.test.ts`

- [ ] **Step 1: Write failing tests**

Create `frontend/src/lib/parseMarkup.test.ts`:

```ts
import { describe, it, expect } from 'vitest'
import { parseMarkup } from './parseMarkup'

describe('parseMarkup', () => {
  it('returns plain segment for plain text', () => {
    expect(parseMarkup('hello world')).toEqual([
      { type: 'plain', text: 'hello world' },
    ])
  })

  it('parses a single deletion', () => {
    expect(parseMarkup('[D>old<D]')).toEqual([
      { type: 'deletion', text: 'old' },
    ])
  })

  it('parses a single addition', () => {
    expect(parseMarkup('[A>new<A]')).toEqual([
      { type: 'addition', text: 'new' },
    ])
  })

  it('parses mixed content', () => {
    expect(parseMarkup('keep [D>del<D] and [A>add<A] end')).toEqual([
      { type: 'plain', text: 'keep ' },
      { type: 'deletion', text: 'del' },
      { type: 'plain', text: ' and ' },
      { type: 'addition', text: 'add' },
      { type: 'plain', text: ' end' },
    ])
  })

  it('handles adjacent tags', () => {
    expect(parseMarkup('[D>a<D][A>b<A]')).toEqual([
      { type: 'deletion', text: 'a' },
      { type: 'addition', text: 'b' },
    ])
  })

  it('handles multiline text inside tags', () => {
    const result = parseMarkup('[A>line one\nline two<A]')
    expect(result).toEqual([{ type: 'addition', text: 'line one\nline two' }])
  })

  it('returns empty array for empty string', () => {
    expect(parseMarkup('')).toEqual([])
  })
})
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
cd frontend
npx vitest run src/lib/parseMarkup.test.ts
```

Expected: `Cannot find module './parseMarkup'`

- [ ] **Step 3: Implement `parseMarkup.ts`**

Create `frontend/src/lib/parseMarkup.ts`:

```ts
export type Segment = {
  type: 'plain' | 'deletion' | 'addition'
  text: string
}

const TAG_RE = /\[D>([\s\S]*?)<D\]|\[A>([\s\S]*?)<A\]/g

export function parseMarkup(markup: string): Segment[] {
  if (!markup) return []
  const segments: Segment[] = []
  let last = 0
  let match: RegExpExecArray | null

  TAG_RE.lastIndex = 0
  while ((match = TAG_RE.exec(markup)) !== null) {
    if (match.index > last) {
      segments.push({ type: 'plain', text: markup.slice(last, match.index) })
    }
    if (match[1] !== undefined) {
      segments.push({ type: 'deletion', text: match[1] })
    } else {
      segments.push({ type: 'addition', text: match[2] })
    }
    last = TAG_RE.lastIndex
  }

  if (last < markup.length) {
    segments.push({ type: 'plain', text: markup.slice(last) })
  }

  return segments
}
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
cd frontend
npx vitest run src/lib/parseMarkup.test.ts
```

Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/parseMarkup.ts frontend/src/lib/parseMarkup.test.ts
git commit -m "feat(frontend): markup parser with Vitest tests"
```

---

## Task 6: UploadZone component

**Files:**
- Create: `frontend/src/components/UploadZone.tsx`

- [ ] **Step 1: Create `UploadZone.tsx`**

```tsx
import React, { useRef, useState } from 'react'

interface Props {
  onFile: (file: File) => void
  disabled?: boolean
}

export function UploadZone({ onFile, disabled }: Props) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)

  function handleDrop(e: React.DragEvent) {
    e.preventDefault()
    setDragging(false)
    const file = e.dataTransfer.files[0]
    if (file && file.name.endsWith('.pdf')) onFile(file)
  }

  function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (file) onFile(file)
  }

  return (
    <div
      className={`upload-zone ${dragging ? 'dragging' : ''}`}
      onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
      onDragLeave={() => setDragging(false)}
      onDrop={handleDrop}
      onClick={() => !disabled && inputRef.current?.click()}
    >
      <input
        ref={inputRef}
        type="file"
        accept=".pdf"
        style={{ display: 'none' }}
        onChange={handleChange}
        disabled={disabled}
      />
      <p>Drop a bill PDF here or <span className="link">click to browse</span></p>
    </div>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/UploadZone.tsx
git commit -m "feat(frontend): UploadZone drag-and-drop component"
```

---

## Task 7: MarkupPanel component

**Files:**
- Create: `frontend/src/components/MarkupPanel.tsx`

- [ ] **Step 1: Create `MarkupPanel.tsx`**

```tsx
import React, { useRef } from 'react'
import { parseMarkup } from '../lib/parseMarkup'

interface Props {
  markup: string
  filename: string
  onScrollRatio: (ratio: number) => void
}

export function MarkupPanel({ markup, filename, onScrollRatio }: Props) {
  const ref = useRef<HTMLDivElement>(null)

  function handleScroll() {
    const el = ref.current
    if (!el) return
    const max = el.scrollHeight - el.clientHeight
    onScrollRatio(max > 0 ? el.scrollTop / max : 0)
  }

  const segments = parseMarkup(markup)

  return (
    <div className="panel">
      <div className="panel-header">
        <span className="panel-title">Markup Preview</span>
        <a
          className="download-btn"
          href={URL.createObjectURL(new Blob([markup], { type: 'text/plain' }))}
          download={filename}
        >
          Download
        </a>
      </div>
      <div className="panel-body" ref={ref} onScroll={handleScroll}>
        {segments.length === 0 && (
          <p className="empty-notice">No amendment markup detected.</p>
        )}
        {segments.map((seg, i) => {
          if (seg.type === 'deletion') {
            return (
              <span key={i} className="deletion">{seg.text}</span>
            )
          }
          if (seg.type === 'addition') {
            return (
              <span key={i} className="addition">{seg.text}</span>
            )
          }
          return <span key={i}>{seg.text}</span>
        })}
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/MarkupPanel.tsx
git commit -m "feat(frontend): MarkupPanel renders colored spans, fires scroll ratio"
```

---

## Task 8: PdfPanel component

**Files:**
- Create: `frontend/src/components/PdfPanel.tsx`

- [ ] **Step 1: Create `PdfPanel.tsx`**

```tsx
import React, { useEffect, useRef } from 'react'
import * as pdfjsLib from 'pdfjs-dist'

// Point the worker at the bundled worker file shipped with pdfjs-dist
pdfjsLib.GlobalWorkerOptions.workerSrc = new URL(
  'pdfjs-dist/build/pdf.worker.min.mjs',
  import.meta.url,
).toString()

interface Props {
  sessionId: string
  scrollRatio: number
}

export function PdfPanel({ sessionId, scrollRatio }: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const bodyRef = useRef<HTMLDivElement>(null)

  // Render all pages once when sessionId changes
  useEffect(() => {
    const container = bodyRef.current
    if (!container) return
    container.innerHTML = ''

    let cancelled = false
    pdfjsLib.getDocument(`/pdf/${sessionId}`).promise.then(async (pdf) => {
      for (let i = 1; i <= pdf.numPages; i++) {
        if (cancelled) break
        const page = await pdf.getPage(i)
        const viewport = page.getViewport({ scale: 1.2 })
        const canvas = document.createElement('canvas')
        canvas.width = viewport.width
        canvas.height = viewport.height
        canvas.style.display = 'block'
        canvas.style.marginBottom = '8px'
        container.appendChild(canvas)
        await page.render({ canvasContext: canvas.getContext('2d')!, viewport }).promise
      }
    })

    return () => { cancelled = true }
  }, [sessionId])

  // Apply scroll ratio from middle panel
  useEffect(() => {
    const el = bodyRef.current
    if (!el) return
    const max = el.scrollHeight - el.clientHeight
    el.scrollTop = scrollRatio * max
  }, [scrollRatio])

  return (
    <div className="panel" ref={containerRef}>
      <div className="panel-header">
        <span className="panel-title">PDF Viewer</span>
      </div>
      <div className="panel-body" ref={bodyRef} />
    </div>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/PdfPanel.tsx
git commit -m "feat(frontend): PdfPanel with PDF.js, responds to scrollRatio prop"
```

---

## Task 9: EditorPanel component

**Files:**
- Create: `frontend/src/components/EditorPanel.tsx`

- [ ] **Step 1: Create `EditorPanel.tsx`**

```tsx
import React, { useRef } from 'react'

interface Props {
  initialMarkup: string
  filename: string
}

export function EditorPanel({ initialMarkup, filename }: Props) {
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  function handleDownload() {
    const text = textareaRef.current?.value ?? initialMarkup
    const blob = new Blob([text], { type: 'text/plain' })
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = `edited_${filename}`
    a.click()
  }

  return (
    <div className="panel">
      <div className="panel-header">
        <span className="panel-title">Editor</span>
        <button className="download-btn" onClick={handleDownload}>
          Download
        </button>
      </div>
      <div className="panel-body editor-body">
        <textarea
          ref={textareaRef}
          className="editor-textarea"
          defaultValue={initialMarkup}
          spellCheck={false}
        />
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/EditorPanel.tsx
git commit -m "feat(frontend): EditorPanel textarea with download"
```

---

## Task 10: App state machine and layout (`App.tsx` + `App.css`)

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/App.css`

- [ ] **Step 1: Replace `frontend/src/App.tsx`**

```tsx
import React, { useState } from 'react'
import './App.css'
import { UploadZone } from './components/UploadZone'
import { PdfPanel } from './components/PdfPanel'
import { MarkupPanel } from './components/MarkupPanel'
import { EditorPanel } from './components/EditorPanel'
import { PROFILES } from './lib/profiles'

type AppState = 'idle' | 'uploading' | 'ready' | 'needs-state' | 'error'

interface ConversionResult {
  sessionId: string
  state: string
  markup: string
  filename: string
}

// Available states — must match backend PROFILES
const SUPPORTED_STATES = ['CA', 'KS']

export default function App() {
  const [appState, setAppState] = useState<AppState>('idle')
  const [result, setResult] = useState<ConversionResult | null>(null)
  const [pendingFile, setPendingFile] = useState<File | null>(null)
  const [selectedState, setSelectedState] = useState('CA')
  const [errorMsg, setErrorMsg] = useState('')
  const [scrollRatio, setScrollRatio] = useState(0)

  async function runUpload(file: File, state?: string) {
    setAppState('uploading')
    const form = new FormData()
    form.append('file', file)
    if (state) form.append('state', state)

    try {
      const res = await fetch('/upload', { method: 'POST', body: form })
      const body = await res.json()

      if (!res.ok) {
        setErrorMsg(body.detail ?? 'Upload failed.')
        setAppState('error')
        return
      }

      if (body.state === null) {
        setPendingFile(file)
        setAppState('needs-state')
        return
      }

      setResult({
        sessionId: body.session_id,
        state: body.state,
        markup: body.markup,
        filename: body.filename,
      })
      setAppState('ready')
    } catch {
      setErrorMsg('Network error — is the API server running?')
      setAppState('error')
    }
  }

  function handleFile(file: File) {
    runUpload(file)
  }

  function handleConvertWithState() {
    if (pendingFile) runUpload(pendingFile, selectedState)
  }

  function handleReset() {
    if (result) {
      fetch(`/session/${result.sessionId}`, { method: 'DELETE' })
    }
    setResult(null)
    setPendingFile(null)
    setAppState('idle')
    setErrorMsg('')
    setScrollRatio(0)
  }

  if (appState === 'idle') {
    return (
      <div className="center-page">
        <h1>NetScan Bill Converter</h1>
        <UploadZone onFile={handleFile} />
      </div>
    )
  }

  if (appState === 'uploading') {
    return (
      <div className="center-page">
        <p className="spinner-text">Analyzing bill…</p>
      </div>
    )
  }

  if (appState === 'needs-state') {
    return (
      <div className="center-page">
        <p>Could not auto-detect state. Please select one:</p>
        <select value={selectedState} onChange={e => setSelectedState(e.target.value)}>
          {SUPPORTED_STATES.map(s => <option key={s}>{s}</option>)}
        </select>
        <button className="primary-btn" onClick={handleConvertWithState}>
          Convert
        </button>
      </div>
    )
  }

  if (appState === 'error') {
    return (
      <div className="center-page">
        <p className="error-msg">{errorMsg}</p>
        <UploadZone onFile={handleFile} />
      </div>
    )
  }

  // READY
  return (
    <div className="app-ready">
      <div className="top-bar">
        <span className="state-badge">{result!.state} — auto-detected</span>
        <button className="reset-btn" onClick={handleReset}>Upload new bill</button>
      </div>
      <div className="panels">
        <PdfPanel sessionId={result!.sessionId} scrollRatio={scrollRatio} />
        <MarkupPanel
          markup={result!.markup}
          filename={result!.filename}
          onScrollRatio={setScrollRatio}
        />
        <EditorPanel initialMarkup={result!.markup} filename={result!.filename} />
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Replace `frontend/src/App.css`**

```css
/* ---- Reset ---- */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: system-ui, sans-serif; font-size: 14px; background: #f5f5f5; }

/* ---- Centered page (idle / error / uploading) ---- */
.center-page {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  gap: 16px;
}

/* ---- Upload zone ---- */
.upload-zone {
  border: 2px dashed #aaa;
  border-radius: 8px;
  padding: 48px 64px;
  cursor: pointer;
  text-align: center;
  color: #555;
  transition: border-color 0.15s, background 0.15s;
}
.upload-zone:hover, .upload-zone.dragging {
  border-color: #0070f3;
  background: #f0f7ff;
}
.upload-zone .link { color: #0070f3; text-decoration: underline; }

/* ---- Ready layout ---- */
.app-ready { display: flex; flex-direction: column; height: 100vh; overflow: hidden; }

.top-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 16px;
  background: #fff;
  border-bottom: 1px solid #ddd;
  flex-shrink: 0;
}
.state-badge {
  font-weight: 600;
  color: #333;
}

/* ---- Three panels ---- */
.panels {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  flex: 1;
  overflow: hidden;
  gap: 0;
}

.panel {
  display: flex;
  flex-direction: column;
  border-right: 1px solid #ddd;
  background: #fff;
  overflow: hidden;
}
.panel:last-child { border-right: none; }

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  border-bottom: 1px solid #eee;
  flex-shrink: 0;
  background: #fafafa;
}
.panel-title { font-weight: 600; font-size: 13px; color: #444; }

.panel-body {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  white-space: pre-wrap;
  line-height: 1.6;
  font-family: 'Georgia', serif;
  font-size: 13px;
}

/* ---- Markup colors ---- */
.deletion {
  color: #c00;
  text-decoration: line-through;
}
.addition {
  color: #007a00;
}

/* ---- Editor ---- */
.editor-body { padding: 0; }
.editor-textarea {
  width: 100%;
  height: 100%;
  border: none;
  outline: none;
  resize: none;
  padding: 16px;
  font-family: 'Courier New', monospace;
  font-size: 13px;
  line-height: 1.6;
  background: #fff;
}

/* ---- Buttons ---- */
.download-btn {
  padding: 4px 10px;
  border: 1px solid #0070f3;
  border-radius: 4px;
  color: #0070f3;
  background: #fff;
  cursor: pointer;
  font-size: 12px;
  text-decoration: none;
}
.download-btn:hover { background: #f0f7ff; }

.primary-btn {
  padding: 8px 20px;
  background: #0070f3;
  color: #fff;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
}
.primary-btn:hover { background: #005fd1; }

.reset-btn {
  padding: 4px 12px;
  background: none;
  border: 1px solid #aaa;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
  color: #555;
}
.reset-btn:hover { border-color: #555; }

/* ---- Misc ---- */
.error-msg { color: #c00; font-weight: 600; }
.spinner-text { color: #555; font-size: 18px; }
.empty-notice { color: #888; font-style: italic; }
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/App.tsx frontend/src/App.css
git commit -m "feat(frontend): App state machine and three-panel layout with CSS"
```

---

## Task 11: Wire up and smoke test

**Files:**
- Modify: `frontend/src/main.tsx` (verify it mounts App correctly)

- [ ] **Step 1: Verify main.tsx**

Open `frontend/src/main.tsx`. It should contain:

```tsx
import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
```

If Vite generated something different, replace it with the above.

- [ ] **Step 2: Start the backend**

In terminal 1:
```bash
uvicorn api.main:app --reload
```

Expected: `Uvicorn running on http://127.0.0.1:8000`

- [ ] **Step 3: Start the frontend**

In terminal 2:
```bash
cd frontend
npm run dev
```

Expected: `Local: http://localhost:5173/`

- [ ] **Step 4: Smoke test — upload flow**

Open `http://localhost:5173` in a browser.

1. Drop `samples/there samples/2025_2026_16_2_2_002203_0_4_1_20250203_0.pdf` onto the upload zone
2. Verify spinner appears briefly
3. Verify three panels appear:
   - Left: PDF renders with bill text visible
   - Middle: bill text visible, deleted comma shown in red strikethrough, added subsections in green
   - Right: textarea with raw markup including `[D>...<D]` and `[A>...<A]` tags
4. Scroll the middle panel — verify left panel scrolls in sync
5. Click Download in the middle panel — verify a `.txt` file downloads with the raw markup
6. Edit text in the right panel — verify middle panel is unchanged
7. Click Download in the right panel — verify the edited version downloads
8. Click "Upload new bill" — verify panels disappear and upload zone reappears

- [ ] **Step 5: Run all backend tests**

```bash
pytest tests/ -v
```

Expected: all tests pass.

- [ ] **Step 6: Run frontend parser tests**

```bash
cd frontend
npx vitest run
```

Expected: 7 passed.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/main.tsx
git commit -m "feat: three-panel UI complete — PDF viewer, markup preview, editor"
```

---

## Task 12: Update pyproject.toml scripts and README

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add API/frontend usage to README**

In `README.md`, find the **Usage** section and add after the existing Streamlit block:

```markdown
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
```

- [ ] **Step 2: Commit and push**

```bash
git add README.md
git commit -m "docs: add three-panel UI usage instructions to README"
git push
```

---

## Self-Review

**Spec coverage check:**

| Spec requirement | Covered by |
|---|---|
| Three equal-width panels | Task 10 — `grid-template-columns: 1fr 1fr 1fr` |
| PDF viewer (left) | Task 8 — PdfPanel + PDF.js |
| Markup preview with colored spans (middle) | Task 7 — MarkupPanel + parseMarkup |
| Tags hidden, text colored | Task 5 + Task 7 — parseMarkup renders spans not raw tags |
| Editor textarea (right) | Task 9 — EditorPanel |
| Both panels downloadable | Task 7 (MarkupPanel), Task 9 (EditorPanel) |
| Sync scroll mid → left | Task 7 `onScrollRatio`, Task 8 `scrollRatio` prop |
| Upload flow with spinner | Task 10 — App state machine |
| Auto-detect state, dropdown fallback | Task 10 — `needs-state` branch |
| Re-upload button | Task 10 — `handleReset` |
| Error states with messages | Task 3 (backend 400/422/500), Task 10 (error state) |
| Temp file cleanup on tab close | Task 3 — DELETE /session endpoint |
| Startup cleanup of old files | Task 3 — `@app.on_event("startup")` |
| Empty markup warning | Task 7 — `empty-notice` |

All spec requirements are covered.
