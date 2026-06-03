"""End-to-end pipeline: bill PDF -> NetScan markup text.

convert() chains open_pdf -> strip_gutter -> extract_page_spans -> reflow into
paragraphs -> render_markup per paragraph, joining paragraphs with blank lines.
Also a CLI:  python -m netscan.pipeline <bill.pdf> <STATE> [out.txt]
"""
from __future__ import annotations
import os
import sys
import tempfile
from pathlib import Path

from netscan.pdf_backend import open_pdf
from netscan.structure import strip_gutter, strip_running_headers
from netscan.geometry import extract_page_spans
from netscan.profiles import PROFILES
from netscan.reflow import paragraphs
from netscan.emit import render_markup
from netscan.scope import suppress_preamble_additions


def convert(pdf_path: str, state: str) -> str:
    """Convert a bill PDF to paragraph-structured NetScan markup text."""
    profile = PROFILES[state]
    # Reflow per page: lines_of sorts spans by `top`, but `top` resets each page,
    # so pooling pages before reflow would interleave reading order (and float
    # each page's top-of-page header to the document front). Grouping per page
    # and concatenating in page order preserves reading order.
    paras: list = []
    operative = False  # True once the enacting clause is passed
    for page_index, geo in enumerate(open_pdf(Path(pdf_path))):
        geo = strip_gutter(geo, profile)
        geo = strip_running_headers(geo, profile)
        spans = extract_page_spans(geo)
        # Suppress italic-as-addition in the front matter / enacting clause.
        spans, operative = suppress_preamble_additions(spans, operative)
        # Fail-safe: the enacting clause always sits on the first page; if it was
        # not matched there, force operative from page 2 on so real additions on
        # later pages are never suppressed.
        if page_index == 0:
            operative = True
        paras.extend(paragraphs(spans, profile))
    rendered = [render_markup(p).strip() for p in paras]
    return "\n\n".join(r for r in rendered if r)


def convert_bytes(data: bytes, state: str) -> str:
    """Convert raw PDF bytes (e.g. an uploaded file) to markup text.

    Writes to a temporary file because the pdf backend opens by path.
    """
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as fh:
        fh.write(data)
        tmp = fh.name
    try:
        return convert(tmp, state)
    finally:
        os.unlink(tmp)


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: python -m netscan.pipeline <bill.pdf> <STATE> [out.txt]",
              file=sys.stderr)
        return 2
    pdf_path, state = argv[0], argv[1]
    out = convert(pdf_path, state)
    if len(argv) >= 3:
        Path(argv[2]).write_text(out, encoding="utf-8")
        print(f"wrote {argv[2]} ({len(out)} chars)")
    else:
        sys.stdout.buffer.write(out.encode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
