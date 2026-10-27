import io

from PIL import Image, ImageOps

from notability_mcp.bundle import Note
from notability_mcp.render import render_page


def test_ink_is_drawn_where_it_sits_on_the_page(ink_note: Note):
    png = render_page(ink_note.pages[0], max_edge=792)  # 1 px per point on a 612x792 page

    img = Image.open(io.BytesIO(png))
    left, top, right, _ = ImageOps.invert(img.convert("L")).getbbox() or (0, 0, 0, 0)
    assert img.size == (612, 792)
    assert 70 <= left <= 85 and 290 <= top <= 300  # stroke origin is (80, 300)
    assert 165 <= right <= 180


def test_long_edge_is_capped(ink_note: Note):
    img = Image.open(io.BytesIO(render_page(ink_note.pages[0], max_edge=400)))
    assert max(img.size) == 400
