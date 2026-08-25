from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import facial, ocr, routing

app = FastAPI(
    title="IsleVendor AI Service",
    description="OCR, facial liveness/match, and route-distance helpers for the IsleVendor platform.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.CORS_ORIGIN],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ocr.router)
app.include_router(facial.router)
app.include_router(routing.router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "backend-fastapi"}
