from netscan.pdf_backend import open_pdf, PageGeometry, Char, RuleLine
from tests.fixtures.make_fixtures import build_formatted_pdf


def test_extract_chars_and_lines(tmp_path):
    pdf = tmp_path / "s.pdf"
    build_formatted_pdf(pdf)
    pages = open_pdf(pdf)
    assert len(pages) == 1
    geo = pages[0]
    assert isinstance(geo, PageGeometry)

    text = "".join(ch.text for ch in geo.chars)
    assert "STRUCK" in text
    assert "ADDED" in text

    # every char has a positive-width bbox and a font name
    for ch in geo.chars:
        assert ch.x1 > ch.x0
        assert ch.bottom > ch.top
        assert isinstance(ch.fontname, str) and ch.fontname

    # at least the two rule lines we drew are present and horizontal
    assert len(geo.rule_lines) >= 2
    for ln in geo.rule_lines:
        assert ln.x1 > ln.x0
        assert abs(ln.bottom - ln.top) < 2.0  # horizontal
