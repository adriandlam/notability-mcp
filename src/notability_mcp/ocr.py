"""Handwriting OCR with Apple's Vision framework (macOS only)."""

# pyobjc creates framework attributes at runtime, so pyright cannot see them.
# pyright: reportAttributeAccessIssue=false

import sys
from dataclasses import dataclass


@dataclass
class Line:
    text: str
    confidence: float  # 0..1; Vision reports coarse steps (0.3, 0.5, 1.0)
    box: tuple[float, float, float, float]  # x, y, width, height; normalized, top-left origin


def available() -> bool:
    return sys.platform == "darwin"


def recognize(png: bytes) -> list[Line]:
    """Text lines in an image, top to bottom."""
    import Vision
    from Foundation import NSData

    request = Vision.VNRecognizeTextRequest.alloc().init()
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
    lines.sort(key=lambda line: (round(line.box[1], 2), line.box[0]))
    return lines
