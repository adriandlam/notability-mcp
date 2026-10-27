"""Rasterize a note page's ink to PNG."""

import io
import math
from collections.abc import Callable, Iterator

from PIL import Image, ImageDraw

from notability_mcp.bundle import HIGHLIGHTER, Ink, Page, decode_path

type Point = tuple[float, float]

MAX_EDGE = 1568  # Claude downscales images whose long edge is larger
_SUPERSAMPLE = 2  # draw at 2x, then downscale: cheap antialiasing


def render_page(page: Page, max_edge: int = MAX_EDGE) -> bytes:
    """PNG of the page's ink on white, long edge `max_edge` px.

    ponytail: PDF backgrounds, shapes and typed text are not drawn yet; add with pypdfium2.
    """
    k = max_edge / max(page.width, page.height)
    size = (round(page.width * k), round(page.height * k))
    s = k * _SUPERSAMPLE
    img = Image.new("RGB", (size[0] * _SUPERSAMPLE, size[1] * _SUPERSAMPLE), "white")
    draw = ImageDraw.Draw(img)
    # highlighters first so pen strokes stay on top
    for ink in sorted(page.inks, key=lambda i: i.tool != HIGHLIGHTER):
        color = _color(ink)
        for line, width in _polylines(ink):
            pts = [(x * s, y * s) for x, y in line]
            draw.line(pts, fill=color, width=max(1, round(width * s)), joint="curve")
    img = img.resize(size, Image.Resampling.LANCZOS)
    out = io.BytesIO()
    img.save(out, "PNG", optimize=True)
    return out.getvalue()


def _color(ink: Ink) -> tuple[int, int, int]:
    r, g, b, _ = ink.color
    if ink.tool == HIGHLIGHTER:  # ponytail: fake 40% translucency by blending with white
        return (round(r * 0.4 + 153), round(g * 0.4 + 153), round(b * 0.4 + 153))
    return (r, g, b)


def _transform(ink: Ink) -> Callable[[float, float], Point]:
    (ox, oy), (sx, sy) = ink.origin, ink.scale
    sx, sy = sx or 1.0, sy or 1.0
    cos, sin = math.cos(ink.rotation), math.sin(ink.rotation)
    return lambda x, y: (ox + x * sx * cos - y * sy * sin, oy + x * sx * sin + y * sy * cos)


def _polylines(ink: Ink) -> Iterator[tuple[list[Point], float]]:
    """Flatten the ink's Bézier path into polylines, each with one stroke width."""
    f = _transform(ink)
    scale = abs(ink.scale[0]) or 1.0
    line: list[Point] = []
    width = ink.width
    for raw in ink.paths:
        for kind, pts, w in decode_path(raw):
            pts = [f(x, y) for x, y in pts]
            width = w or width
            if kind in (3, 7) or not line:
                if len(line) > 1:
                    yield line, width * scale
                line = [pts[0]]
                if kind in (3, 7):
                    continue
            line.extend(_flatten(line[-1], kind, pts))
    if len(line) > 1:
        yield line, width * scale
    elif line:  # a dot
        yield [line[0], line[0]], width * scale


def _flatten(start: Point, kind: int, pts: list[Point]) -> list[Point]:
    if kind in (0, 4):  # cubic
        (x1, y1), (x2, y2), (x3, y3) = pts
        ts = (0.25, 0.5, 0.75, 1.0)
        return [
            (
                (1 - t) ** 3 * start[0]
                + 3 * (1 - t) ** 2 * t * x1
                + 3 * (1 - t) * t * t * x2
                + t**3 * x3,
                (1 - t) ** 3 * start[1]
                + 3 * (1 - t) ** 2 * t * y1
                + 3 * (1 - t) * t * t * y2
                + t**3 * y3,
            )
            for t in ts
        ]
    if kind in (1, 5):  # quadratic
        (x1, y1), (x2, y2) = pts
        ts = (1 / 3, 2 / 3, 1.0)
        return [
            (
                (1 - t) ** 2 * start[0] + 2 * (1 - t) * t * x1 + t * t * x2,
                (1 - t) ** 2 * start[1] + 2 * (1 - t) * t * y1 + t * t * y2,
            )
            for t in ts
        ]
    return [pts[-1]]  # line
