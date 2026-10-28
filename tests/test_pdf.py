import io
from pathlib import Path

import pytest
from PIL import Image, ImageOps

from notability_mcp import pdf
from notability_mcp.bundle import Note, Page, PdfPage
from notability_mcp.index import page_texts
from notability_mcp.render import render_page
from notability_mcp.store import PageText

pytestmark = pytest.mark.skipif(not pdf.available(), reason="PDFKit is macOS-only")

HELLO = (Path(__file__).parent / "fixtures" / "hello.pdf").read_bytes()  # "Hello PDF", 612x792
SHA = "ab" * 64


def pdf_note() -> Note:
    page = Page(1, (0, 0, 0), 612, 792, pdf=PdfPage(SHA, 0))
    return Note("n1", "Slides", [page], "", {SHA})


def test_pdf_text_is_indexed_separately_from_handwriting():
    assert page_texts(pdf_note(), {SHA: HELLO}) == [
        PageText(1, "handwriting", "", None),  # no ink on the slide
        PageText(1, "pdf", "Hello PDF"),
    ]


def test_page_image_draws_the_pdf_under_the_ink():
    page = pdf_note().pages[0]

    with_pdf = Image.open(io.BytesIO(render_page(page, 792, HELLO))).convert("L")
    without = Image.open(io.BytesIO(render_page(page, 792))).convert("L")

    left, top, _, _ = ImageOps.invert(with_pdf).getbbox() or (0, 0, 0, 0)
    assert 60 <= left <= 85 and 40 <= top <= 70  # text sits at (72, 700) from the bottom
    assert ImageOps.invert(without).getbbox() is None  # blank without its PDF


def test_missing_pdf_page_is_skipped():
    assert pdf.render(HELLO, 5, (100, 100)) is None
