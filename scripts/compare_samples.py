"""Score netscan convert() output against reference .txt ground truth.

Usage:  python scripts/compare_samples.py [--verbose]

Reads every <name>.pdf that has a sibling <name>.txt in the sample dirs below,
runs convert(), and reports per-file similarity plus aggregate scores. The
reference .txt files are the Doctly-produced NetScan markup we want to match.
"""
from __future__ import annotations
import difflib
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from netscan.pipeline import convert  # noqa: E402
from netscan.detect import detect_state  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SAMPLE_DIRS = [ROOT / "samples" / "there samples"]


def read_text(p: Path) -> str:
    raw = p.read_bytes()
    for enc in ("utf-8", "cp1252", "latin-1"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        text = raw.decode("latin-1", "replace")
    # Normalize CRLF/CR -> LF: line-ending style is an encoding artifact, not a
    # content difference, and convert() emits LF only.
    return text.replace("\r\n", "\n").replace("\r", "\n")


def words(s: str) -> list[str]:
    return re.sub(r"\s+", " ", s).strip().split()


def spans(s: str) -> tuple[list[str], list[str]]:
    norm = lambda x: re.sub(r"\s+", " ", x).strip()
    a = [norm(x) for x in re.findall(r"\[A>(.*?)<A\]", s, re.S)]
    d = [norm(x) for x in re.findall(r"\[D>(.*?)<D\]", s, re.S)]
    return a, d


def pairs(name: str) -> list[tuple[Path, Path]]:
    """Every PDF with a reference .txt. Matches both the `N.txt` gold files and
    the older `<stem>_doctly.txt` references (KS2203/KS2206/CA351) so a single run
    covers every profile -- CA included -- and global changes can't silently
    regress a state that the KS-only gold batch never exercises."""
    out = []
    for d in SAMPLE_DIRS:
        if not d.is_dir():
            continue
        for pdf in sorted(d.glob("*.pdf")):
            for txt in (pdf.with_suffix(".txt"),
                        pdf.with_name(pdf.stem + "_doctly.txt")):
                if txt.exists():
                    out.append((pdf, txt))
                    break
    return out


def main(argv: list[str]) -> int:
    verbose = "--verbose" in argv or "-v" in argv
    rows = []
    for pdf, txt in pairs(""):
        state = detect_state(str(pdf)) or "KS"
        try:
            out = convert(str(pdf), state)
        except Exception as e:  # noqa: BLE001
            print(f"{pdf.name:>10}  ERROR {type(e).__name__}: {e}")
            rows.append((pdf.name, 0.0, 0.0))
            continue
        ref = read_text(txt)
        wr = difflib.SequenceMatcher(None, words(ref), words(out)).ratio()
        cr = difflib.SequenceMatcher(None, ref, out).ratio()
        ra, rd = spans(ref)
        oa, od = spans(out)
        a_ok = sorted(ra) == sorted(oa)
        d_ok = sorted(rd) == sorted(od)
        rows.append((pdf.name, wr, cr))
        flag = "" if (a_ok and d_ok) else "  <-- span mismatch"
        print(f"{pdf.name:>10}  word={wr:.4f}  char={cr:.4f}  "
              f"A:{len(oa)}/{len(ra)} D:{len(od)}/{len(rd)}{flag}")
        if verbose and not (a_ok and d_ok):
            for lbl, rs, os_ in (("ADD", ra, oa), ("DEL", rd, od)):
                for x in rs:
                    if x not in os_:
                        print(f"      {lbl} ref-only: {x[:140]!r}")
                for x in os_:
                    if x not in rs:
                        print(f"      {lbl} our-only: {x[:140]!r}")
    if rows:
        n = len(rows)
        print("-" * 60)
        print(f"  mean word similarity: {sum(r[1] for r in rows)/n:.4f}")
        print(f"  mean char similarity: {sum(r[2] for r in rows)/n:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
