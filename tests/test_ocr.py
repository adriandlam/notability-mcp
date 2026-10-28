import io

from PIL import Image, ImageDraw, ImageFont

from notability_mcp import ocr


def _png_with(lines: list[str]) -> bytes:
    img = Image.new("RGB", (900, 120 * len(lines) + 40), "white")
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default(size=64)
    for i, text in enumerate(lines):
        draw.text((30, 20 + 120 * i), text, fill="black", font=font)
    out = io.BytesIO()
    img.save(out, "PNG")
    return out.getvalue()


def test_reads_lines_top_to_bottom():
    lines = ocr.recognize(_png_with(["Complex numbers", "Harmonic conjugate"]))

    assert [line.text for line in lines] == ["Complex numbers", "Harmonic conjugate"]
    assert lines[0].box[1] < lines[1].box[1]


def test_blank_page_has_no_lines():
    assert ocr.recognize(_png_with([""])) == []
