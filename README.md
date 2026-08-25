# IsleVendor AI Service (FastAPI)

Domain A/D helpers: driver's-license OCR, facial liveness/match, and route-distance
ranking. **The OCR and facial endpoints are stubs** — they return `status:
"not_implemented"` and null fields on purpose, so no driver KYC decision can
accidentally be made from fabricated data. See the docstrings in
`app/routers/ocr.py` and `app/routers/facial.py` for what needs to be wired in.

Note: port 8000 is used by another local service on this machine, so this API
runs on **8001** by default (see `app/config.py` / `.env`).

## Setup and run

1. Create and activate a virtual environment:

```bash
python3 -m venv venv
source venv/bin/activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Copy `.env.example` to `.env` and adjust if needed.

4. Run the server:

```bash
uvicorn main:app --reload --port 8001
```

Interactive API docs: http://localhost:8001/docs
