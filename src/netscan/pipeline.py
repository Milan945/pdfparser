"""End-to-end pipeline: bill PDF -> NetScan markup text.

convert() chains open_pdf -> strip_gutter -> extract_page_spans -> reflow into
paragraphs -> render_markup per paragraph, joining paragraphs with blank lines.
Also a CLI:  python -m netscan.pipeline <bill.pdf> <STATE> [out.txt]
"""
from __future__ import annotations
import sys
from pathlib import Path

from netscan.pdf_backend import open_pdf
from netscan.structure import strip_gutter
from netscan.geometry import extract_page_spans
from netscan.profiles import PROFILES
from netscan.reflow import paragraphs
from netscan.emit import render_markup


def convert(pdf_path: str, state: str) -> str:
    """Convert a bill PDF to paragraph-structured NetScan markup text."""
    profile = PROFILES[state]
    spans = []
    for geo in open_pdf(Path(pdf_path)):
        geo = strip_gutter(geo, profile)
        spans.extend(extract_page_spans(geo))
    paras = paragraphs(spans, profile)
    rendered = [render_markup(p).strip() for p in paras]
    return "\n\n".join(r for r in rendered if r)


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
