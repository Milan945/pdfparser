"""Stage 1: classify each page as NATIVE (real text layer) or SCANNED."""
from enum import Enum

from netscan.pdf_backend import PageGeometry

MIN_MEANINGFUL_CHARS = 20  # below this, treat as scanned/empty


class PageKind(str, Enum):
    NATIVE = "native"
    SCANNED = "scanned"


def classify_page(geo: PageGeometry) -> PageKind:
    meaningful = sum(1 for ch in geo.chars if ch.text and ch.text.strip()
                     and ch.text.isprintable())
    if meaningful >= MIN_MEANINGFUL_CHARS:
        return PageKind.NATIVE
    return PageKind.SCANNED
