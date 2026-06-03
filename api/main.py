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
