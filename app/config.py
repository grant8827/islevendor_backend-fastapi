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


settings = Settings()
