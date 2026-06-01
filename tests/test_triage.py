from netscan.pdf_backend import PageGeometry, Char
from netscan.triage import classify_page, PageKind


def _char(t):
    return Char(text=t, x0=0, x1=5, top=0, bottom=10, fontname="Helvetica", size=10)


def test_page_with_text_is_native():
    geo = PageGeometry(width=612, height=792,
                       chars=[_char(c) for c in "The agency shall review applications"],
                       image_count=0)
    assert classify_page(geo) == PageKind.NATIVE


def test_empty_page_is_scanned():
    geo = PageGeometry(width=612, height=792, chars=[], image_count=1)
    assert classify_page(geo) == PageKind.SCANNED


def test_few_garbage_chars_is_scanned():
    geo = PageGeometry(width=612, height=792, chars=[_char("\x00"), _char(" ")],
                       image_count=1)
    assert classify_page(geo) == PageKind.SCANNED
