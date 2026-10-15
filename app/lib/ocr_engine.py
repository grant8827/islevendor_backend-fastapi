"""Tesseract-based text extraction for driver KYC documents.

Real OCR, not a stub — but Tesseract's accuracy on phone photos of varied
document layouts (license/insurance/registration all look different, and
none of them is a controlled scan) is genuinely limited. Callers
(app/routers/ocr.py) treat a failed/ambiguous field extraction as
"needs_review" rather than guessing, on purpose.
"""

import io

import fitz  # PyMuPDF — used only to rasterize a PDF's first page
import pytesseract
from PIL import Image, ImageOps

from app.config import settings

if settings.TESSERACT_CMD:
    pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_CMD

# Phone photos of documents are routinely low-contrast/skewed; a modest DPI
# bump when rasterizing PDFs helps Tesseract find small print (expiry dates,
# policy numbers) it would otherwise miss.
PDF_RASTER_DPI = 300


def _load_image(file_bytes: bytes, content_type: str) -> Image.Image:
    if content_type == "application/pdf":
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        try:
            page = doc[0]
            pix = page.get_pixmap(dpi=PDF_RASTER_DPI)
            return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        finally:
            doc.close()

    image = Image.open(io.BytesIO(file_bytes))
    # Phone cameras routinely tag rotation via EXIF instead of rotating pixels;
    # PIL doesn't honor that automatically, so text can end up sideways for
    # Tesseract unless this runs first.
    return ImageOps.exif_transpose(image)


def extract_text(file_bytes: bytes, content_type: str) -> str:
    """Returns whatever text Tesseract can read from an uploaded document
    image or single-page PDF. May return an empty string — callers must
    handle that rather than assume extraction always finds something.
    """
    image = _load_image(file_bytes, content_type).convert("L")  # grayscale aids OCR
    return pytesseract.image_to_string(image)
