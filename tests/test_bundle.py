from pathlib import Path

from notability_mcp.bundle import Note, decode_bundle, linearize

FIXTURES = Path(__file__).parent / "fixtures"


def test_typed_text_from_bundle():
    note = decode_bundle((FIXTURES / "synthetic_bundle.bin").read_bytes())

    # body text (with an edit and a removed char), then a separate text box
    assert note.text == "Hello world!\n\nbox"


def test_streamed_ink_lands_on_the_implicit_first_page(ink_note: Note):
    [page] = ink_note.pages
    [ink] = page.inks
    assert (page.number, page.width, page.height) == (1, 612.0, 792.0)
    assert ink.origin == (80.0, 300.0)
    assert ink.width == 2.0
    assert ink.paths[1].hex() == "0001000060540045005500c5a0550000333d003cff00"


def test_rga_orders_newest_sibling_first():
    a, b, c = (1, 1, 0), (1, 1, 1), (2, 5, 0)
    # "ab" typed, then "c" inserted after "a" by a later op: a c b
    assert linearize([(a, None), (b, a), (c, a)]) == [a, c, b]


def test_rga_survives_an_anchor_cycle():
    a, b = (1, 1, 0), (1, 2, 0)
    assert linearize([(a, None), (b, a), (a, b)]) == [a, b]
