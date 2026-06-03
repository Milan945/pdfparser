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
    from netscan.structure import strip_gutter, strip_running_headers, uppercase_small_caps
    from netscan.profiles import PROFILES
    from netscan.emit import render_markup
    profile = PROFILES[_state_for(pdf_path)]
    spans = []
    for geo in open_pdf(Path(pdf_path)):
        geo = strip_gutter(geo, profile)
        geo = strip_running_headers(geo, profile)
        geo = uppercase_small_caps(geo)
        spans.extend(extract_page_spans(geo))
    return render_markup(spans)


def content_key(s: str) -> str:
    """Tag-stripped, whitespace-free content key (the round-trip invariant).

    Measures CONTENT fidelity only: are the same words present, ignoring tags
    and all whitespace/reflow.
    """
    return re.sub(r"\s+", "", _TAG_RE.sub("", s))


def tagged_key(s: str) -> str:
    """Whitespace collapsed to single spaces, tags KEPT.

    Measures content + tag placement + tag-boundary spacing, normalizing away
    reflow (newlines/paragraphs). This is the metric closest to byte-parity with
    Doctly once reflow is excluded; it is lowered by tag fragmentation and by
    spaces sitting inside vs outside tags, which the tag-merge slice targets.
    """
    return re.sub(r"\s+", " ", s).strip()


def tag_inventory(s: str) -> tuple[list[str], list[str]]:
    """Return (deletions, additions) inner texts, each whitespace-normalized."""
    dels = [re.sub(r"\s+", " ", t).strip() for t in re.findall(r"\[D>(.*?)<D\]", s, re.S)]
    adds = [re.sub(r"\s+", " ", t).strip() for t in re.findall(r"\[A>(.*?)<A\]", s, re.S)]
    return dels, adds


def _multiset_overlap(a: list[str], b: list[str]) -> int:
    """Count of exact-match items shared between two lists (as multisets)."""
    from collections import Counter
    ca, cb = Counter(a), Counter(b)
    return sum((ca & cb).values())


def score_pair(name: str, pdf_path: str, gold_path: str) -> None:
    ours = our_markup(pdf_path)
    gold = Path(gold_path).read_text(encoding="utf-8")
    ck_o, ck_g = content_key(ours), content_key(gold)
    content_ratio = difflib.SequenceMatcher(None, ck_o, ck_g).ratio()
    tk_o, tk_g = tagged_key(ours), tagged_key(gold)
    tagged_ratio = difflib.SequenceMatcher(None, tk_o, tk_g).ratio()
    # full pipeline output (with reflow) vs gold, whitespace-collapsed
    from netscan.pipeline import convert
    state = _state_for(pdf_path)
    full = convert(pdf_path, state)
    fk_o = re.sub(r"\s+", " ", full).strip()
    full_ratio = difflib.SequenceMatcher(None, fk_o, tk_g).ratio()
    od, oa = tag_inventory(ours)
    gd, ga = tag_inventory(gold)
    d_match, a_match = _multiset_overlap(od, gd), _multiset_overlap(oa, ga)
    print(f"{name}:")
    print(f"  content  chars ours={len(ck_o)} gold={len(ck_g)} "
          f"identical={ck_o == ck_g} similarity={content_ratio:.4f}")
    print(f"  tagged   similarity={tagged_ratio:.4f} (content+tags, reflow-normalized)")
    print(f"  fulltext similarity={full_ratio:.4f} (pipeline reflow output vs gold)")
    print(f"  tags     ours D={len(od)} A={len(oa)} | gold D={len(gd)} A={len(ga)} | "
          f"exact-match D={d_match}/{len(gd)} A={a_match}/{len(ga)}")


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
