"""Regression lock on the 1-4 gold samples (Doctly NetScan markup).

Guards the converter's output quality against future regressions: the three
prose bills must stay byte-identical to their references, and every bill's
amendment spans ([A>..<A]/[D>..<D]) must match the reference set exactly. 1.pdf
contains a Schedule-IV drug table whose dot-leader layout Doctly renders in a
tool-specific way we do not reproduce byte-for-byte, so it is held to a high
word-similarity bar plus exact amendment spans rather than an exact match.
"""
from __future__ import annotations
import difflib
import re
from pathlib import Path

import pytest

from netscan.pipeline import convert

SAMPLES = Path("samples/there samples")


def _read(p: Path) -> str:
    raw = p.read_bytes()
    for enc in ("utf-8", "cp1252", "latin-1"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        text = raw.decode("latin-1", "replace")
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _spans(s: str) -> tuple[list[str], list[str]]:
    norm = lambda x: re.sub(r"\s+", " ", x).strip()
    a = [norm(x) for x in re.findall(r"\[A>(.*?)<A\]", s, re.S)]
    d = [norm(x) for x in re.findall(r"\[D>(.*?)<D\]", s, re.S)]
    return a, d


def _has(n: str) -> bool:
    return (SAMPLES / f"{n}.pdf").exists() and (SAMPLES / f"{n}.txt").exists()


@pytest.mark.parametrize("name", ["2", "3", "4"])
@pytest.mark.skipif(not SAMPLES.exists(), reason="gold samples not present")
def test_prose_bills_match_reference_exactly(name: str):
    if not _has(name):
        pytest.skip(f"{name}.pdf/.txt missing")
    out = convert(str(SAMPLES / f"{name}.pdf"), "KS")
    ref = _read(SAMPLES / f"{name}.txt")
    assert out.strip() == ref.strip()


@pytest.mark.parametrize("name", ["1", "2", "3", "4"])
@pytest.mark.skipif(not SAMPLES.exists(), reason="gold samples not present")
def test_amendment_spans_match_reference(name: str):
    if not _has(name):
        pytest.skip(f"{name}.pdf/.txt missing")
    out = convert(str(SAMPLES / f"{name}.pdf"), "KS")
    ref = _read(SAMPLES / f"{name}.txt")
    out_a, out_d = _spans(out)
    ref_a, ref_d = _spans(ref)
    assert sorted(out_a) == sorted(ref_a), f"{name}: additions differ"
    assert sorted(out_d) == sorted(ref_d), f"{name}: deletions differ"


@pytest.mark.skipif(not SAMPLES.exists(), reason="gold samples not present")
def test_drug_table_bill_stays_high():
    if not _has("1"):
        pytest.skip("1.pdf/.txt missing")
    out = convert(str(SAMPLES / "1.pdf"), "KS")
    ref = _read(SAMPLES / "1.txt")
    w = lambda s: re.sub(r"\s+", " ", s).strip().split()
    sim = difflib.SequenceMatcher(None, w(ref), w(out)).ratio()
    assert sim >= 0.96, f"1.pdf word similarity regressed to {sim:.4f}"
