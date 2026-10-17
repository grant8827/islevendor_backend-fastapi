from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """AI service config. Values are placeholders until real OCR/facial
    models are chosen (Domain A, Phase 5) — see README for the decision
    that's still open (Tesseract vs. a hosted OCR API, DeepFace vs. InsightFace).
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    PORT: int = 8001  # 8000 is occupied by another local service on this machine
    NODE_API_URL: str = "http://localhost:5000"
    FACIAL_MATCH_THRESHOLD: float = 0.75  # min confidence to auto-approve a driver
    CORS_ORIGIN: str = "http://localhost:5173"

    # Document OCR/verification (driver KYC: license, insurance, registration).
    # Fraction of the applicant's name tokens that must be found (allowing for
    # OCR noise) on the document before it's considered a name match.
    NAME_MATCH_THRESHOLD: float = 0.6
    # Path to the tesseract binary, only needed if it's not on PATH (e.g. a
    # non-default Homebrew prefix). Leave unset to use pytesseract's default.
    TESSERACT_CMD: Optional[str] = None

    # A proof of address (utility bill, bank statement) must be issued within
    # this many days of the application.
    PROOF_OF_ADDRESS_MAX_AGE_DAYS: int = 90
    # Fraction of the address's words that must appear on a proof of address.
    ADDRESS_MATCH_THRESHOLD: float = 0.5


settings = Settings()
