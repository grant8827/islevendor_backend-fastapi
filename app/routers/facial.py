from typing import Optional

from fastapi import APIRouter, UploadFile, File
from pydantic import BaseModel

from app.config import settings

router = APIRouter(prefix="/facial", tags=["facial"])


class FacialMatchResult(BaseModel):
    status: str  # "not_implemented" until a real model is wired in
    is_live: Optional[bool] = None
    match_score: Optional[float] = None
    passes_threshold: Optional[bool] = None


@router.post("/liveness-match", response_model=FacialMatchResult)
async def liveness_match(
    license_photo: UploadFile = File(...),
    selfie: UploadFile = File(...),
) -> FacialMatchResult:
    """Compare a live selfie against the license photo and score liveness.

    STUB: returns nulls, not a fabricated score — driver_profiles.facial_match_score
    and is_kyc_approved must only ever be set from a real model's output.
    Wire in DeepFace/InsightFace (or a hosted liveness API) before Domain A /
    Phase 5. Threshold for auto-approval is settings.FACIAL_MATCH_THRESHOLD.
    """
    await license_photo.read()
    await selfie.read()
    return FacialMatchResult(status="not_implemented")


@router.get("/threshold")
async def get_threshold() -> dict:
    return {"facial_match_threshold": settings.FACIAL_MATCH_THRESHOLD}
