"""Turn a note bundle into searchable page text."""

import sqlite3
from statistics import fmean

from notability_mcp import ocr, store
from notability_mcp.bundle import Note, decode_bundle
from notability_mcp.render import render_page
from notability_mcp.store import PageText

OCR_MAX_EDGE = 2048  # a bit above page-image size: small handwriting reads better


def page_texts(note: Note) -> list[PageText]:
    """Typed text (page 0) plus one handwriting row per page, empty when there is no ink."""
    texts = [PageText(0, "typed", note.text)] if note.text else []
    can_ocr = ocr.available()
    for page in note.pages:
        lines = ocr.recognize(render_page(page, OCR_MAX_EDGE)) if page.inks and can_ocr else []
        confidence = fmean(line.confidence for line in lines) if lines else None
        texts.append(
            PageText(page.number, "handwriting", "\n".join(line.text for line in lines), confidence)
        )
    return texts


def index_note(con: sqlite3.Connection, note_id: str, bundle: bytes) -> int:
    """Decode, OCR and store one note; returns its page count."""
    note = decode_bundle(bundle)
    store.save_note(con, note_id, bundle, len(note.pages), page_texts(note))
    return len(note.pages)
