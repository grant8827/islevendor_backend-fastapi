from datetime import date, timedelta
from typing import Literal, Optional

from fastapi import APIRouter, File, Form, UploadFile
from pydantic import BaseModel

from app.config import settings
from app.lib.delivery_photo import check_delivery_photo
from app.lib.document_fields import (
    extract_document_date,
    extract_expiry_date,
    extract_name,
    extract_trns,
    name_match_score,
    plate_found,
    text_name_score,
    trn_matches,
)
from app.lib.ocr_engine import extract_text

router = APIRouter(prefix="/ocr", tags=["ocr"])

# license / insurance / registration: a driver's documents.
# photo_id: a reseller's or small vendor's own ID.
# trn_card / business_registration / proof_of_address: a warehouse's.
DocumentType = Literal["license", "insurance", "registration", "photo_id", "trn_card", "business_registration", "proof_of_address"]

# Documents that carry an expiry date and a holder's name on one line.
PERSONAL_DOCUMENTS = {"license", "insurance", "registration", "photo_id"}


class DocumentCheckResult(BaseModel):
    # "verified" | "name_mismatch" | "details_mismatch" | "expired" | "stale"
    # | "needs_review". expired and stale are objective date checks (the
    # caller blocks on them); name_mismatch and details_mismatch are
    # positive findings a human should look at; needs_review means Tesseract
    # couldn't confidently find what it needed — not that it's fine.
    status: str
    document_type: DocumentType
    extracted_name: Optional[str] = None
    name_match: Optional[bool] = None
    name_match_score: Optional[float] = None
    expiry_date: Optional[str] = None
    is_expired: Optional[bool] = None
    # TRN card: the TRN-shaped numbers read, and whether the expected one is among them.
    extracted_trns: Optional[list[str]] = None
    trn_match: Optional[bool] = None
    # Vehicle registration/insurance: whether the expected plate is on it.
    plate_match: Optional[bool] = None
    # Proof of address: its issue date, whether it's too old, and whether
    # the address appears on it.
    document_date: Optional[str] = None
    is_stale: Optional[bool] = None
    address_match: Optional[bool] = None
    # Plain-English list of what didn't check out, for the admin reviewing it.
    problems: list[str] = []
    # Truncated, for an admin reviewing a needs_review result — not meant to
    # be parsed by callers.
    raw_text_excerpt: Optional[str] = None


def _best_name_score(names: list[str], score) -> Optional[float]:
    scores = [score(n) for n in names if n and n.strip()]
    return max(scores) if scores else None


@router.post("/verify-document", response_model=DocumentCheckResult)
async def verify_document(
    document_type: DocumentType = Form(...),
    expected_name: str = Form(...),
    # Another name the document may be in — e.g. a business's TRN card or
    # utility bill can be in the company's name or the owner's.
    alternate_name: Optional[str] = Form(None),
    expected_trn: Optional[str] = Form(None),
    expected_plate: Optional[str] = Form(None),
    expected_address: Optional[str] = Form(None),
    image: UploadFile = File(...),
) -> DocumentCheckResult:
    """Reads an onboarding document via Tesseract and checks it against
    what the applicant told us:

    - license / insurance / registration / photo_id: holder name and expiry
      date; with `expected_plate`, the vehicle's licence plate too.
    - trn_card: the TRN number (`expected_trn`) and the name.
    - business_registration (COCJ): the business name.
    - proof_of_address: issued within PROOF_OF_ADDRESS_MAX_AGE_DAYS, shows
      `expected_address`, and the name.

    Tesseract's accuracy on real phone photos is genuinely limited — this
    returns "needs_review" rather than guessing when it can't find what it
    needs, and never fabricates a match. Callers should treat needs_review
    as "a human should look", not as a pass.
    """
    raw = await image.read()
    text = extract_text(raw, image.content_type or "")
    names = [expected_name, alternate_name or ""]
    problems: list[str] = []
    result = DocumentCheckResult(status="needs_review", document_type=document_type, raw_text_excerpt=text[:500] if text else None)

    if not text.strip():
        result.problems = ["No text could be read from the document"]
        return result

    found_everything = True

    if document_type in PERSONAL_DOCUMENTS:
        extracted_name = extract_name(text)
        expiry = extract_expiry_date(text)
        result.extracted_name = extracted_name
        if extracted_name:
            result.name_match_score = _best_name_score(names, lambda n: name_match_score(n, extracted_name))
            result.name_match = (result.name_match_score or 0) >= settings.NAME_MATCH_THRESHOLD
        if expiry:
            result.expiry_date = expiry.isoformat()
            result.is_expired = expiry < date.today()
        found_everything = extracted_name is not None and expiry is not None
        if expected_plate:
            result.plate_match = plate_found(expected_plate, text)
            if result.plate_match is False:
                problems.append(f"Licence plate {expected_plate} wasn't found on the document")

    elif document_type == "trn_card":
        result.extracted_trns = extract_trns(text)
        result.trn_match = trn_matches(expected_trn or "", text) if expected_trn else None
        if result.trn_match is False:
            problems.append(f"TRN {expected_trn} doesn't match the TRN on the card ({', '.join(result.extracted_trns)})")
        result.name_match_score = _best_name_score(names, lambda n: text_name_score(n, text))
        result.name_match = (result.name_match_score or 0) >= settings.NAME_MATCH_THRESHOLD
        found_everything = result.trn_match is not None

    elif document_type == "business_registration":
        result.name_match_score = _best_name_score(names, lambda n: text_name_score(n, text))
        result.name_match = (result.name_match_score or 0) >= settings.NAME_MATCH_THRESHOLD

    elif document_type == "proof_of_address":
        issued = extract_document_date(text)
        if issued:
            result.document_date = issued.isoformat()
            result.is_stale = issued < date.today() - timedelta(days=settings.PROOF_OF_ADDRESS_MAX_AGE_DAYS)
        if expected_address:
            score = text_name_score(expected_address, text)
            result.address_match = score >= settings.ADDRESS_MATCH_THRESHOLD
            if not result.address_match:
                problems.append("The address on the document doesn't match the one entered")
        result.name_match_score = _best_name_score(names, lambda n: text_name_score(n, text))
        result.name_match = (result.name_match_score or 0) >= settings.NAME_MATCH_THRESHOLD
        found_everything = issued is not None

    if result.name_match is False:
        problems.append("The name on the document doesn't match")

    # Objective date checks first: the caller blocks on these.
    if result.is_expired:
        result.status = "expired"
        problems.insert(0, f"Expired on {result.expiry_date}")
    elif result.is_stale:
        result.status = "stale"
        problems.insert(0, f"Issued {result.document_date}, more than {settings.PROOF_OF_ADDRESS_MAX_AGE_DAYS} days ago")
    elif result.trn_match is False or result.plate_match is False or result.address_match is False:
        result.status = "details_mismatch"
    elif result.name_match is False:
        result.status = "name_mismatch"
    elif not found_everything or result.name_match is None:
        result.status = "needs_review"
    else:
        result.status = "verified"

    result.problems = problems
    return result


class DeliveryPhotoCheck(BaseModel):
    # "passed" — what the driver said is in the photo was found;
    # "flagged" — it wasn't (the delivery still goes through; a person checks it).
    status: Literal["passed", "flagged"]
    proof_type: Literal["PACKAGE_WITH_ID", "PACKAGE_WITH_RECIPIENT"]
    faces_found: int
    id_text_found: bool
    reason: Optional[str] = None


@router.post("/delivery-photo", response_model=DeliveryPhotoCheck)
async def delivery_photo(
    proof_type: Literal["PACKAGE_WITH_ID", "PACKAGE_WITH_RECIPIENT"] = Form(...),
    image: UploadFile = File(...),
) -> DeliveryPhotoCheck:
    """Looks for what a proof-of-delivery photo is meant to show: a person
    (the recipient) or an ID card. It can't tell whether the package itself
    is in the frame, or whose face or ID it is — it catches photos that show
    neither, so a person can look at them."""
    raw = await image.read()
    return DeliveryPhotoCheck(proof_type=proof_type, **check_delivery_photo(raw, image.content_type or "", proof_type))
