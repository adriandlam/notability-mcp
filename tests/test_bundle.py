import json
from pathlib import Path

from notability_mcp.bundle import build_note, decode_bundle, linearize, read_ops

FIXTURES = Path(__file__).parent / "fixtures"


def event_ops(name: str):
    """Ops from a server-acknowledged AppendOpsEvent captured by notability-cli."""
    fixture = json.loads((FIXTURES / f"{name}.json").read_text())
    return read_ops(bytes.fromhex(fixture["append_ops_event_hex"]), ops_field=0)


def test_typed_text_and_assets_from_bundle():
    note = decode_bundle((FIXTURES / "synthetic_bundle.bin").read_bytes())

    # body text (with an edit and a removed char), then a separate text box
    assert note.text == "Hello world!\n\nbox"
    assert len(note.assets) == 1


def test_streamed_ink_lands_on_the_implicit_first_page():
    note = build_note("n", event_ops("25_ink_pen") + event_ops("26_ink_add_path"))

    [page] = note.pages
    [ink] = page.inks
    assert (page.number, page.width, page.height) == (1, 612.0, 792.0)
    assert ink.origin == (80.0, 300.0)
    assert ink.width == 2.0
    assert ink.paths[1].hex() == "0001000060540045005500c5a0550000333d003cff00"


def test_rga_orders_newest_sibling_first():
    a, b, c = (1, 1, 0), (1, 1, 1), (2, 5, 0)
    # "ab" typed, then "c" inserted after "a" by a later op: a c b
    assert linearize([(a, None), (b, a), (c, a)]) == [a, c, b]
