from datetime import date
from typing import Literal, Optional

from fastapi import APIRouter, File, Form, UploadFile
from pydantic import BaseModel

from app.config import settings
from app.lib.document_fields import extract_expiry_date, extract_name, name_match_score
from app.lib.ocr_engine import extract_text

router = APIRouter(prefix="/ocr", tags=["ocr"])

DocumentType = Literal["license", "insurance", "registration", "photo_id"]


class DocumentCheckResult(BaseModel):
    # "verified" | "name_mismatch" | "expired" | "needs_review". Only
    # name_mismatch and expired are positive findings against real extracted
    # text/dates — needs_review means Tesseract couldn't confidently find a
    # name and/or expiry date, not that one was found and is fine.
    status: str
    document_type: DocumentType
    extracted_name: Optional[str] = None
    name_match: Optional[bool] = None
    name_match_score: Optional[float] = None
    expiry_date: Optional[str] = None
    is_expired: Optional[bool] = None
    # Truncated, for an admin reviewing a needs_review result — not meant to
    # be parsed by callers.
    raw_text_excerpt: Optional[str] = None


@router.post("/verify-document", response_model=DocumentCheckResult)
async def verify_document(
    document_type: DocumentType = Form(...),
    expected_name: str = Form(...),
    image: UploadFile = File(...),
) -> DocumentCheckResult:
    """Extracts the holder name and expiry date from an onboarding KYC
    document (driver's license / insurance / registration / a reseller or
    vendor's personal photo ID) via Tesseract, and checks the name against
    `expected_name` (the applicant's registered legal name).

    Tesseract's accuracy on real phone photos of differently-laid-out
    document types is genuinely limited — this deliberately returns
    "needs_review" rather than guessing when a field can't be confidently
    located, instead of ever fabricating a name or date match. Callers
    should treat needs_review as "a human should look", not as a pass.
    """
    raw = await image.read()
    text = extract_text(raw, image.content_type or "")

    extracted_name = extract_name(text)
    expiry = extract_expiry_date(text)

    name_match: Optional[bool] = None
    match_score: Optional[float] = None
    if extracted_name:
        match_score = name_match_score(expected_name, extracted_name)
        name_match = match_score >= settings.NAME_MATCH_THRESHOLD

    is_expired = expiry is not None and expiry < date.today()

    if is_expired:
        status_value = "expired"
    elif name_match is False:
        status_value = "name_mismatch"
    elif extracted_name is None or expiry is None:
        status_value = "needs_review"
    else:
        status_value = "verified"

    return DocumentCheckResult(
        status=status_value,
        document_type=document_type,
        extracted_name=extracted_name,
        name_match=name_match,
        name_match_score=match_score,
        expiry_date=expiry.isoformat() if expiry else None,
        is_expired=is_expired if expiry else None,
        raw_text_excerpt=text[:500] if text else None,
    )
