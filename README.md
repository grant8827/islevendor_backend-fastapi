# IsleVendor AI Service (FastAPI)

Domain A/D helpers: driver KYC document OCR/verification, facial liveness/match,
and route-distance ranking.

**The facial endpoint is still a stub** — it returns `status: "not_implemented"`
and null fields on purpose, so no driver KYC decision can accidentally be made
from fabricated data. See the docstring in `app/routers/facial.py` for what
needs to be wired in.

**The OCR endpoint (`POST /ocr/verify-document`) is real**, backed by
Tesseract (`app/lib/ocr_engine.py`, `app/lib/document_fields.py`). It reads a
driver's license / certificate of insurance / certificate of registration,
extracts the holder name and expiry date, and checks the name against the
applicant's registered name — see the docstring in `app/routers/ocr.py` for
what it does when it can't confidently read a field (it says so, rather than
guessing). backend-node calls this during driver onboarding to gate document
uploads — see `backend-node/src/lib/ocrClient.ts`.

Note: port 8000 is used by another local service on this machine, so this API
runs on **8001** by default (see `app/config.py` / `.env`).

## Setup and run

1. Install the Tesseract OCR engine itself (a system binary, not a pip
   package) — `pytesseract` just shells out to it:

```bash
brew install tesseract   # macOS
```

   If it's not on PATH, set `TESSERACT_CMD` in `.env` to its full path.

2. Create and activate a virtual environment:

```bash
python3 -m venv venv
source venv/bin/activate
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Copy `.env.example` to `.env` and adjust if needed.

5. Run the server:

```bash
uvicorn main:app --reload --port 8001
```

Interactive API docs: http://localhost:8001/docs
