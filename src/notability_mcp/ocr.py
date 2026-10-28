"""Handwriting OCR: Apple's Vision framework on macOS, RapidOCR everywhere else."""

# pyobjc creates framework attributes at runtime, so pyright cannot see them.
# pyright: reportAttributeAccessIssue=false

import io
import sys
from dataclasses import dataclass
from functools import cache

from PIL import Image


@dataclass
class Line:
    text: str
    confidence: float  # 0..1; Vision reports coarse steps (0.3, 0.5, 1.0)
    box: tuple[float, float, float, float]  # x, y, width, height; normalized, top-left origin


def recognize(png: bytes) -> list[Line]:
    """Text lines in an image, top to bottom."""
    lines = _vision(png) if sys.platform == "darwin" else _rapidocr(png)
    lines.sort(key=lambda line: (round(line.box[1], 2), line.box[0]))
    return lines


def _vision(png: bytes) -> list[Line]:
    import Vision  # pyright: ignore[reportMissingImports]
    from Foundation import NSData  # pyright: ignore[reportMissingImports]

    request = Vision.VNRecognizeTextRequest.alloc().init()
    # Revision 3 runs on the Neural Engine, which can fail (e5rtError) or hang forever; revision
    # 2 read handwritten math as well in a benchmark on 20 pages, and 10x faster.
    request.setRevision_(Vision.VNRecognizeTextRequestRevision2)
    request.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
    request.setUsesLanguageCorrection_(True)
    data = NSData.dataWithBytes_length_(png, len(png))
    handler = Vision.VNImageRequestHandler.alloc().initWithData_options_(data, None)
    ok, error = handler.performRequests_error_([request], None)
    if not ok:
        raise RuntimeError(f"Vision text recognition failed: {error}")

    lines = []
    for obs in request.results() or []:
        candidates = obs.topCandidates_(1)
        if not candidates:
            continue
        bb = obs.boundingBox()  # Vision's origin is bottom-left
        top = 1 - bb.origin.y - bb.size.height
        box = (bb.origin.x, top, bb.size.width, bb.size.height)
        lines.append(Line(str(candidates[0].string()), float(candidates[0].confidence()), box))
    return lines


@cache
def _rapidocr_engine():
    from rapidocr import RapidOCR  # pyright: ignore[reportMissingImports]

    return RapidOCR(params={"Global.log_level": "error"})  # it warns on every textless page


def _rapidocr(png: bytes) -> list[Line]:
    # The models bundled with the wheel (PP-OCRv6 small) found as many key words as Vision and
    # twice the formulas in the same 20-page benchmark, at about 1 s per page.
    width, height = Image.open(io.BytesIO(png)).size
    out = _rapidocr_engine()(png)
    boxes, texts, scores = out.boxes, out.txts, out.scores
    if boxes is None or texts is None or scores is None:  # no text found
        return []
    lines = []
    for quad, text, score in zip(boxes, texts, scores, strict=True):
        xs, ys = [float(x) / width for x, _ in quad], [float(y) / height for _, y in quad]
        box = (min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys))
        lines.append(Line(str(text), float(score), box))
    return lines
