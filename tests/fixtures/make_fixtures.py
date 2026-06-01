"""Generate synthetic legislative-style PDFs with known formatting.

Layout (single page, points; reportlab origin is bottom-left):
  y=720  "PLAIN" Helvetica            -> unformatted
  y=700  "BOLDWORD" Helvetica-Bold    -> bold
  y=680  "ITALICWORD" Helvetica-Oblique -> italic
  y=660  "STRUCK" + horizontal line through mid-glyph -> strikethrough
  y=640  "ADDED" + horizontal line at baseline        -> underline
"""
from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

FONT_SIZE = 12


def build_formatted_pdf(path: Path) -> None:
    c = canvas.Canvas(str(path), pagesize=letter)

    def draw(text: str, x: float, y: float, font: str = "Helvetica") -> float:
        c.setFont(font, FONT_SIZE)
        c.drawString(x, y, text)
        return c.stringWidth(text, font, FONT_SIZE)

    draw("PLAIN", 72, 720)
    draw("BOLDWORD", 72, 700, "Helvetica-Bold")
    draw("ITALICWORD", 72, 680, "Helvetica-Oblique")

    # STRUCK: line through vertical middle of glyphs (~0.35 * font size above baseline)
    w = draw("STRUCK", 72, 660)
    c.setLineWidth(0.6)
    c.line(72, 660 + FONT_SIZE * 0.35, 72 + w, 660 + FONT_SIZE * 0.35)

    # ADDED: line just below baseline (underline)
    w = draw("ADDED", 72, 640)
    c.line(72, 640 - 1.5, 72 + w, 640 - 1.5)

    c.showPage()
    c.save()
