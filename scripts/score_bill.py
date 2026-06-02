"""Score our extraction against Doctly gold-standard outputs.

Two independent contracts (see docs/research/2026-06-02-doctly-and-faithful-extraction.md):
  1. CONTENT FIDELITY  - our text (tags stripped, whitespace removed) vs the
     gold text similarly normalized. This is the hallucination guard. Where the
     SOURCE has a quirk (e.g. the 'disclsoure' typo in ks2206), both should keep
     it, so high similarity here is expected once gutters/headers are stripped.
  2. STRUCTURE         - tag counts and a char-level similarity ratio against the
     gold output. This measures gutter strip, reflow, boilerplate scoping, and
     tag-boundary convention. This is where the current gap lives.

This is a measurement tool, not a test. It prints a baseline so each structural
fix can be scored. Pairs are discovered from samples/ by the '<stem>_doctly.txt'
convention.

Usage:
    python scripts/score_bill.py                 # score every discovered pair
    python scripts/score_bill.py <bill.pdf> <gold.txt>   # score one pair
"""
import sys
import re
import difflib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from netscan.pdf_backend import open_pdf          # noqa: E402
from netscan.geometry import extract_page_spans    # noqa: E402

_TAG_RE = re.compile(r"\[D>|<D\]|\[A>|<A\]")


def _state_for(pdf_path: str) -> str:
    name = Path(pdf_path).name
    return "CA" if "_5_2_2_000351_" in name else "KS"


def our_markup(pdf_path: str) -> str:
    from netscan.structure import strip_gutter
    from netscan.profiles import PROFILES
    from netscan.normalize import normalize_unicode
    profile = PROFILES[_state_for(pdf_path)]
    out: list[str] = []
    for geo in open_pdf(Path(pdf_path)):
        geo = strip_gutter(geo, profile)
        for s in extract_page_spans(geo):
            t = normalize_unicode(s.text)
            if s.struck:
                t = f"[D>{t}<D]"
            elif s.italic:
                t = f"[A>{t}<A]"
            out.append(t)
    return "".join(out)


def content_key(s: str) -> str:
    """Tag-stripped, whitespace-free content key (the round-trip invariant)."""
    return re.sub(r"\s+", "", _TAG_RE.sub("", s))


def score_pair(name: str, pdf_path: str, gold_path: str) -> None:
    ours = our_markup(pdf_path)
    gold = Path(gold_path).read_text(encoding="utf-8")
    ck_o, ck_g = content_key(ours), content_key(gold)
    ratio = difflib.SequenceMatcher(None, ck_o, ck_g).ratio()
    print(f"{name}:")
    print(f"  content chars  ours={len(ck_o)} gold={len(ck_g)} "
          f"identical={ck_o == ck_g} char_similarity={ratio:.4f}")
    print(f"  tags  ours D={ours.count('[D>')} A={ours.count('[A>')} | "
          f"gold D={gold.count('[D>')} A={gold.count('[A>')}")


def discover_pairs() -> list[tuple[str, str, str]]:
    root = Path(__file__).resolve().parents[1]
    pairs: list[tuple[str, str, str]] = []
    for gold in sorted(root.glob("samples/**/*_doctly.txt")):
        pdf = gold.with_name(gold.name.replace("_doctly.txt", ".pdf"))
        if pdf.exists():
            pairs.append((pdf.stem, str(pdf), str(gold)))
    return pairs


def main(argv: list[str]) -> None:
    if len(argv) == 2:
        score_pair(Path(argv[0]).stem, argv[0], argv[1])
        return
    pairs = discover_pairs()
    if not pairs:
        print("No <stem>.pdf / <stem>_doctly.txt pairs found under samples/.")
        return
    for name, pdf, gold in pairs:
        score_pair(name, pdf, gold)


if __name__ == "__main__":
    main(sys.argv[1:])
