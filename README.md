# IsleVendor AI Service (FastAPI)

Domain A/D helpers: driver KYC document OCR/verification, facial liveness/match,
and route-distance ranking.

**The facial endpoint is still a stub** — it returns `status: "not_implemented"`
and null fields on purpose, so no driver KYC decision can accidentally be made
from fabricated data. See the docstring in `app/routers/facial.py` for what
needs to be wired in.

**The OCR endpoint (`POST /ocr/verify-document`) is real**, backed by
Tesseract (`app/lib/ocr_engine.py`, `app/lib/document_fields.py`). It reads
every document uploaded at sign-up and checks it against what the applicant
entered:

| `document_type` | Who uploads it | What's checked |
| --- | --- | --- |
| `license`, `insurance`, `registration` | drivers | holder name, expiry date; with `expected_plate`, the licence plate |
| `photo_id` | resellers, small vendors | holder name, expiry date |
| `trn_card` | warehouses | the TRN (`expected_trn`), the name |
| `business_registration` (COCJ) | warehouses | the business name |
| `proof_of_address` | warehouses | issued within 90 days, the address (`expected_address`), the name |

`alternate_name` lets a business document be in the owner's name instead.
It answers `verified`, `name_mismatch`, `details_mismatch` (TRN, plate or
address), `expired`, `stale` (proof of address too old) or `needs_review`
(couldn't read it confidently — never a guessed pass), plus a plain-English
`problems` list. backend-node blocks sign-up only on `expired` and `stale`
and records the rest for an admin — see `backend-node/src/lib/ocrClient.ts`
and `onboarding.routes.ts`.

**`POST /ocr/delivery-photo`** looks at a proof-of-delivery photo for what
the driver says it shows — the recipient (OpenCV face detection) or their ID
(ID-card wording via Tesseract, or the portrait on the card). It can't tell
whether the package is in the frame or whose face it is; it answers
`passed` or `flagged`, and backend-node never blocks a delivery on it.

Tests: `venv/bin/python -m pytest tests` (generates document images and
runs them through Tesseract — needs Tesseract installed).

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
