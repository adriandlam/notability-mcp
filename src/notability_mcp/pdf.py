"""Text and images of the PDF pages notes are built on, with macOS PDFKit (macOS only)."""

# pyobjc creates framework attributes at runtime, so pyright cannot see them.
# pyright: reportAttributeAccessIssue=false

import io

from PIL import Image


def _open(data: bytes):
    import Quartz
    from Foundation import NSData

    doc = Quartz.PDFDocument.alloc().initWithData_(NSData.dataWithBytes_length_(data, len(data)))
    if doc is None:
        raise ValueError("Not a readable PDF.")
    return doc


def page_texts(data: bytes) -> list[str]:
    """The text of every page, in order."""
    doc = _open(data)
    return [str(doc.pageAtIndex_(i).string() or "") for i in range(doc.pageCount())]


def render(data: bytes, index: int, size: tuple[int, int]) -> Image.Image | None:
    """Page `index` (0-based) drawn at `size` pixels; None if the PDF has no such page."""
    import Quartz

    doc = _open(data)
    if not 0 <= index < doc.pageCount():
        return None
    image = doc.pageAtIndex_(index).thumbnailOfSize_forBox_(size, Quartz.kPDFDisplayBoxCropBox)
    page = Image.open(io.BytesIO(bytes(image.TIFFRepresentation()))).convert("RGBA")
    out = Image.new("RGB", page.size, "white")
    out.paste(page, mask=page)
    return out.resize(size) if out.size != size else out
