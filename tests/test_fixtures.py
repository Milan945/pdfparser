from pathlib import Path
from tests.fixtures.make_fixtures import build_formatted_pdf


def test_build_formatted_pdf_creates_file(tmp_path):
    out = tmp_path / "sample.pdf"
    build_formatted_pdf(out)
    assert out.exists()
    assert out.stat().st_size > 0
    # PDF magic bytes
    assert out.read_bytes()[:5] == b"%PDF-"
