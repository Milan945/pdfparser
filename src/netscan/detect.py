"""Best-effort state detection from a bill PDF's first page.

Used to pre-select the per-state profile in the UI/CLI; the user can override.
Detection is intentionally simple (first-page text scan) and returns None when
unsure rather than guessing.
"""
from __future__ import annotations
from pathlib import Path
from typing import Optional

from netscan.pdf_backend import open_pdf

# Ordered by specificity; first match wins.
_SIGNATURES: list[tuple[str, str]] = [
    ("california", "CA"),
    ("kansas", "KS"),
]


def detect_state_from_text(text: str) -> Optional[str]:
    """Return 'CA'/'KS' if a known signature appears in the text, else None."""
    low = text.lower()
    for needle, state in _SIGNATURES:
        if needle in low:
            return state
    return None


def detect_state(pdf_path: str | Path) -> Optional[str]:
    """Open the PDF and detect the state from its first page's text."""
    pages = open_pdf(Path(pdf_path))
    if not pages:
        return None
    first = "".join(c.text for c in pages[0].chars)
    return detect_state_from_text(first)
