"""Checks a proof-of-delivery photo for what the driver says it shows: the
recipient (a face) or the recipient's ID (ID-card wording, or the portrait
printed on the card).

Deliberately modest: OpenCV's stock Haar face detector and Tesseract, both
local and free. It can't tell whether the package is in the frame, or whose
face or ID it is. What it catches is a photo showing neither a person nor an
ID — and callers only flag those for a person to look at, never block a
delivery on them (a dark doorstep or a blurry phone photo would otherwise
leave a driver stuck with the package).
"""

import logging
import re
from typing import Optional

import numpy as np
import pytesseract

from app.lib.ocr_engine import load_image

# Words printed on Jamaican IDs: driver's licence, passport, national ID,
# electoral (voter) ID — plus the field labels they share.
ID_WORDS = re.compile(
    r"\b(JAMAICA|LICEN[CS]E|DRIVER|PASSPORT|NATIONAL|ELECTORAL|IDENTIFICATION|"
    r"TRN|DATE\s*OF\s*BIRTH|D\.?O\.?B|EXPIR\w*|SURNAME|GIVEN\s*NAMES?)\b",
    re.IGNORECASE,
)
# Two or more distinct ID words before calling it an ID — one stray "TRN"
# on a shipping label isn't an ID card.
MIN_ID_WORDS = 2

# The photo is scaled to this width before face detection: phone photos
# are 3000–4000px wide, which is slow and no more accurate.
DETECT_WIDTH = 1000

log = logging.getLogger(__name__)

# Loaded on first use, not at import: if OpenCV can't load on a server, the
# rest of the service (document OCR) must still start. Face detection then
# reports None and photos are judged on ID text alone.
_face_detector = None
_face_detector_failed = False


def _detector():
    global _face_detector, _face_detector_failed
    if _face_detector is None and not _face_detector_failed:
        try:
            import cv2

            _face_detector = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        except Exception:  # noqa: BLE001 — any OpenCV failure means "can't look for faces"
            log.exception("OpenCV face detection unavailable")
            _face_detector_failed = True
    return _face_detector


def _count_faces(gray: np.ndarray) -> Optional[int]:
    """Faces found, or None if face detection isn't available."""
    detector = _detector()
    if detector is None:
        return None
    import cv2

    scale = DETECT_WIDTH / gray.shape[1] if gray.shape[1] > DETECT_WIDTH else 1.0
    if scale != 1.0:
        gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    gray = cv2.equalizeHist(gray)
    # minSize keeps tiny false positives (patterns on the box) out; an ID
    # card's portrait held up to the camera is still well above it.
    faces = detector.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=6, minSize=(36, 36))
    return len(faces)


def _id_text_found(image) -> bool:
    text = pytesseract.image_to_string(image)
    words = {m.group(1).upper().replace(" ", "") for m in ID_WORDS.finditer(text)}
    return len(words) >= MIN_ID_WORDS


def check_delivery_photo(file_bytes: bytes, content_type: str, proof_type: str) -> dict:
    image = load_image(file_bytes, content_type).convert("L")
    faces = _count_faces(np.array(image))
    id_text = _id_text_found(image)
    face_seen = bool(faces)

    if proof_type == "PACKAGE_WITH_RECIPIENT":
        passed = face_seen
        reason = None if passed else ("Face detection isn't available to check the photo" if faces is None else "No person could be seen in the photo")
    else:
        # An ID card shows its wording, or at least the holder's portrait.
        passed = id_text or face_seen
        reason = None if passed else "No ID card could be made out in the photo"

    return {"status": "passed" if passed else "flagged", "faces_found": faces or 0, "id_text_found": id_text, "reason": reason}
