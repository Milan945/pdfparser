"""Report what the geometry path sees in a real bill, per page.

Usage: python scripts/inspect_bill.py samples/some_bill.pdf
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from netscan.pdf_backend import open_pdf          # noqa: E402
from netscan.triage import classify_page          # noqa: E402
from netscan.geometry import extract_page_spans    # noqa: E402


def main(pdf_path: str) -> None:
    pages = open_pdf(Path(pdf_path))
    for i, geo in enumerate(pages, 1):
        kind = classify_page(geo)
        spans = extract_page_spans(geo) if kind.value == "native" else []
        struck = [s.text for s in spans if s.struck]
        under = [s.text for s in spans if s.underlined]
        print(f"\n=== page {i}: {kind.value} | chars={len(geo.chars)} "
              f"rule_lines={len(geo.rule_lines)} images={geo.image_count} ===")
        print(f"  struck spans ({len(struck)}): {struck[:10]}")
        print(f"  underlined spans ({len(under)}): {under[:10]}")


if __name__ == "__main__":
    main(sys.argv[1])
