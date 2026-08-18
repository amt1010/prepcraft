from pathlib import Path

import pytest
from reportlab.pdfgen import canvas

from app.backend.ingestion.image_loader import load_pages

FIXTURE_JPG = Path("tests/fixtures/existing_paper/main/page_1.jpg")


def test_loads_a_single_page_from_a_jpg():
    pages = load_pages(FIXTURE_JPG)

    assert len(pages) == 1
    assert pages[0].ndim == 3  # H, W, channels


def test_loads_one_page_per_pdf_page(tmp_path):
    pdf_path = tmp_path / "two_pages.pdf"
    c = canvas.Canvas(str(pdf_path), pagesize=(200, 300))
    c.drawString(10, 150, "page one")
    c.showPage()
    c.drawString(10, 150, "page two")
    c.showPage()
    c.save()

    pages = load_pages(pdf_path)

    assert len(pages) == 2
    assert all(page.ndim == 3 for page in pages)


def test_raises_on_an_unsupported_extension(tmp_path):
    bad_file = tmp_path / "notes.txt"
    bad_file.write_text("not an image")

    with pytest.raises(ValueError, match="unsupported"):
        load_pages(bad_file)
