from typing import Optional

from fastapi import APIRouter, UploadFile, File
from pydantic import BaseModel

router = APIRouter(prefix="/ocr", tags=["ocr"])


class LicenseOcrResult(BaseModel):
    status: str  # "not_implemented" until a real OCR engine is wired in
    license_number: Optional[str] = None
    full_name: Optional[str] = None
    license_expiry: Optional[str] = None
    confidence: Optional[float] = None


@router.post("/jamaican-license", response_model=LicenseOcrResult)
async def parse_jamaican_license(image: UploadFile = File(...)) -> LicenseOcrResult:
    """Parse a photo of a Jamaican driver's license into structured fields.

    STUB: returns nulls, not fabricated data — a driver-onboarding decision
    must never be made on invented OCR output. Wire this up to a real engine
    (Tesseract + a JM-license field template, or a hosted OCR API) before
    Domain A / Phase 5 goes live, and only then let driver_profiles.is_kyc_approved
    be set from this response.
    """
    await image.read()  # consumes the upload; real parsing happens here later
    return LicenseOcrResult(status="not_implemented")
