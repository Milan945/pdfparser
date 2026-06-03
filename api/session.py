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
