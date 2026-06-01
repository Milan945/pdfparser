"""Thin adapter over pdfplumber. The ONLY module that imports pdfplumber,
so the PDF library can be swapped without touching downstream stages.

All coordinates use pdfplumber's top-down system: `top` is distance from the
top of the page, `bottom = top + height`, y increases downward.
"""
from dataclasses import dataclass, field
from pathlib import Path

import pdfplumber

MAX_RULE_HEIGHT = 2.5  # pts; lines/rects thinner than this count as horizontal rules


@dataclass
class Char:
    text: str
    x0: float
    x1: float
    top: float
    bottom: float
    fontname: str
    size: float


@dataclass
class RuleLine:
    x0: float
    x1: float
    top: float
    bottom: float

    @property
    def y_mid(self) -> float:
        return (self.top + self.bottom) / 2.0


@dataclass
class PageGeometry:
    width: float
    height: float
    chars: list[Char] = field(default_factory=list)
    rule_lines: list[RuleLine] = field(default_factory=list)
    image_count: int = 0


def _horizontal_rules(page) -> list[RuleLine]:
    rules: list[RuleLine] = []
    # pdfplumber lines: explicit vector lines
    for ln in page.lines:
        if abs(ln["bottom"] - ln["top"]) <= MAX_RULE_HEIGHT and ln["x1"] > ln["x0"]:
            rules.append(RuleLine(ln["x0"], ln["x1"], ln["top"], ln["bottom"]))
    # pdfplumber rects: thin filled rectangles are often underlines/strikes
    for r in page.rects:
        if abs(r["bottom"] - r["top"]) <= MAX_RULE_HEIGHT and r["x1"] > r["x0"]:
            rules.append(RuleLine(r["x0"], r["x1"], r["top"], r["bottom"]))
    return rules


def open_pdf(path: Path) -> list[PageGeometry]:
    pages: list[PageGeometry] = []
    with pdfplumber.open(str(path)) as pdf:
        for page in pdf.pages:
            chars = [
                Char(
                    text=ch["text"],
                    x0=ch["x0"], x1=ch["x1"],
                    top=ch["top"], bottom=ch["bottom"],
                    fontname=ch.get("fontname", "") or "",
                    size=ch.get("size", 0.0) or 0.0,
                )
                for ch in page.chars
            ]
            pages.append(
                PageGeometry(
                    width=page.width,
                    height=page.height,
                    chars=chars,
                    rule_lines=_horizontal_rules(page),
                    image_count=len(page.images),
                )
            )
    return pages
