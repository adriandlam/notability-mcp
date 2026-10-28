"""Text and images of the PDF pages notes are built on, with PDFium."""

import threading

import pypdfium2 as pdfium
from PIL import Image

_lock = threading.Lock()  # PDFium is not thread-safe, and the server may run tools in threads


def page_texts(data: bytes) -> list[str]:
    """The text of every page, in order."""
    with _lock:
        doc = pdfium.PdfDocument(data)
        return [page.get_textpage().get_text_bounded() for page in doc]


def render(data: bytes, index: int, size: tuple[int, int]) -> Image.Image | None:
    """Page `index` (0-based) drawn at `size` pixels; None if the PDF has no such page."""
    with _lock:
        doc = pdfium.PdfDocument(data)
        if not 0 <= index < len(doc):
            return None
        page = doc[index]
        image = page.render(scale=size[0] / page.get_width()).to_pil()
    return image.resize(size) if image.size != size else image
