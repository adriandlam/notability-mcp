from pathlib import Path

from notability_mcp.bundle import decode_bundle
from notability_mcp.index import page_texts
from notability_mcp.store import PageText

BUNDLE = (Path(__file__).parent / "fixtures" / "synthetic_bundle.bin").read_bytes()


def test_typed_text_is_note_level_and_every_page_gets_a_row():
    texts = page_texts(decode_bundle(BUNDLE))

    assert texts == [
        PageText(0, "typed", "Hello world!\n\nbox"),
        PageText(1, "handwriting", "", None),  # no ink, so nothing to OCR
    ]
