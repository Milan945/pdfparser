"""Report what the geometry path sees in a real bill, per page.

Usage: python scripts/inspect_bill.py samples/some_bill.pdf
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from netscan.pdf_backend import open_pdf          # noqa: E402
from netscan.triage import classify_page          # noqa: E402
from netscan.geometry import extract_page_spans    # noqa: E402
from netscan.conflict import detect_conflicts      # noqa: E402


def main(pdf_path: str) -> None:
    pages = open_pdf(Path(pdf_path))
    total_spans = 0
    total_flagged = 0
    kind_counts: dict[str, int] = {}
    for i, geo in enumerate(pages, 1):
        kind = classify_page(geo)
        spans = extract_page_spans(geo) if kind.value == "native" else []
        spans, conflicts = detect_conflicts(geo, spans)
        flagged = [s for s in spans if s.flag_reason]
        total_spans += len(spans)
        total_flagged += len(flagged)
        for c in conflicts:
            kind_counts[c.kind] = kind_counts.get(c.kind, 0) + 1
        struck = [s.text for s in spans if s.struck]
        under = [s.text for s in spans if s.underlined]
        print(f"\n=== page {i}: {kind.value} | chars={len(geo.chars)} "
              f"rule_lines={len(geo.rule_lines)} images={geo.image_count} ===")
        print(f"  struck spans ({len(struck)}): {struck[:8]}")
        print(f"  underlined spans ({len(under)}): {under[:8]}")
        print(f"  conflicts ({len(conflicts)}): {[c.kind for c in conflicts]}")
        if flagged:
            print(f"  flagged spans ({len(flagged)}): "
                  f"{[(s.text, s.flag_reason) for s in flagged][:5]}")
    pct = (100.0 * total_flagged / total_spans) if total_spans else 0.0
    print(f"\n--- TOTAL: spans={total_spans} flagged={total_flagged} "
          f"({pct:.1f}%) conflicts_by_kind={kind_counts} ---")


if __name__ == "__main__":
    main(sys.argv[1])
