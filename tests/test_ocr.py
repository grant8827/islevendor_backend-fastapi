"""End-to-end checks of /ocr/verify-document and /ocr/delivery-photo with
generated document images, so Tesseract really reads them (no mocks).
Run: venv/bin/python -m pytest tests"""

import io
from datetime import date, timedelta

from fastapi.testclient import TestClient
from PIL import Image, ImageDraw, ImageFont

from main import app

client = TestClient(app)


def _font(size: int):
    for path in ("/System/Library/Fonts/Supplemental/Arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def document(lines: list[str]) -> bytes:
    """A clean, high-contrast 'scan' with one line of text per entry."""
    img = Image.new("RGB", (1600, 140 + 90 * len(lines)), "white")
    draw = ImageDraw.Draw(img)
    for i, line in enumerate(lines):
        draw.text((60, 60 + 90 * i), line, fill="black", font=_font(48))
    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


def verify(document_type: str, image: bytes, **fields) -> dict:
    data = {"document_type": document_type, "expected_name": fields.pop("expected_name", "Island Gadgets Limited"), **fields}
    res = client.post("/ocr/verify-document", data=data, files={"image": ("doc.png", image, "image/png")})
    assert res.status_code == 200, res.text
    return res.json()


def fmt(d: date) -> str:
    return d.strftime("%d/%m/%Y")


# ── TRN card ──────────────────────────────────────────────────────────────

TRN_CARD = document(["TAX ADMINISTRATION JAMAICA", "TAXPAYER REGISTRATION NUMBER", "TRN 123-456-789", "ISLAND GADGETS LIMITED"])


def test_trn_card_matching_number_and_name_is_verified():
    r = verify("trn_card", TRN_CARD, expected_trn="123456789")
    assert r["trn_match"] is True
    assert r["status"] == "verified", r


def test_trn_card_with_a_different_number_is_a_details_mismatch():
    r = verify("trn_card", TRN_CARD, expected_trn="987654321")
    assert r["trn_match"] is False
    assert r["status"] == "details_mismatch"
    assert any("TRN" in p for p in r["problems"])


def test_trn_card_in_the_owners_name_matches_the_alternate_name():
    card = document(["TAX ADMINISTRATION JAMAICA", "TRN 123 456 789", "NAME: MARCIA BROWN"])
    r = verify("trn_card", card, expected_trn="123456789", alternate_name="Marcia Brown")
    assert r["name_match"] is True
    assert r["status"] == "verified", r


# ── COCJ business registration ────────────────────────────────────────────


def test_business_registration_with_the_business_name_is_verified():
    cert = document(["COMPANIES OFFICE OF JAMAICA", "CERTIFICATE OF INCORPORATION", "ISLAND GADGETS LIMITED", "COMPANY NO. 123456"])
    assert verify("business_registration", cert)["status"] == "verified"


def test_business_registration_for_another_business_is_a_name_mismatch():
    cert = document(["COMPANIES OFFICE OF JAMAICA", "CERTIFICATE OF INCORPORATION", "BLUE MOUNTAIN TRADERS LIMITED"])
    assert verify("business_registration", cert)["status"] == "name_mismatch"


# ── Proof of address ──────────────────────────────────────────────────────

ADDRESS = "12 Hope Road Liguanea"


def bill(issued: date, address_line: str = "12 HOPE ROAD, LIGUANEA") -> bytes:
    return document(["JAMAICA PUBLIC SERVICE", "ISLAND GADGETS LIMITED", address_line, f"BILL DATE {fmt(issued)}"])


def test_recent_bill_at_the_address_is_verified():
    r = verify("proof_of_address", bill(date.today() - timedelta(days=20)), expected_address=ADDRESS)
    assert r["is_stale"] is False
    assert r["address_match"] is True
    assert r["status"] == "verified", r


def test_bill_older_than_three_months_is_stale():
    r = verify("proof_of_address", bill(date.today() - timedelta(days=200)), expected_address=ADDRESS)
    assert r["status"] == "stale"
    assert r["is_stale"] is True


def test_bill_for_another_address_is_a_details_mismatch():
    r = verify("proof_of_address", bill(date.today() - timedelta(days=10), "45 BARBICAN ROAD, KINGSTON 8"), expected_address=ADDRESS)
    assert r["address_match"] is False
    assert r["status"] == "details_mismatch"


# ── Vehicle documents ─────────────────────────────────────────────────────

REGISTRATION = document(
    ["CERTIFICATE OF REGISTRATION", "OWNER: MARCIA BROWN", "PLATE NO: PG 1234", f"EXPIRY DATE {fmt(date.today() + timedelta(days=300))}"]
)


def test_registration_with_the_drivers_plate_is_verified():
    r = verify("registration", REGISTRATION, expected_name="Marcia Brown", expected_plate="PG1234")
    assert r["plate_match"] is True
    assert r["status"] == "verified", r


def test_registration_for_another_plate_is_a_details_mismatch():
    r = verify("registration", REGISTRATION, expected_name="Marcia Brown", expected_plate="AB 9999")
    assert r["plate_match"] is False
    assert r["status"] == "details_mismatch"


def test_expired_document_still_wins_over_everything_else():
    expired = document(["CERTIFICATE OF REGISTRATION", "OWNER: MARCIA BROWN", "PLATE NO: PG 1234", "EXPIRY DATE 01/01/2020"])
    assert verify("registration", expired, expected_name="Marcia Brown", expected_plate="AB9999")["status"] == "expired"


def test_existing_callers_without_the_new_fields_behave_as_before():
    r = verify("license", REGISTRATION, expected_name="Marcia Brown")
    assert r["status"] == "verified"
    assert r["plate_match"] is None


def test_unreadable_document_needs_review():
    blank = document([])
    r = verify("trn_card", blank, expected_trn="123456789")
    assert r["status"] == "needs_review"


# ── Delivery photo ────────────────────────────────────────────────────────


def photo_check(proof_type: str, image: bytes) -> dict:
    res = client.post("/ocr/delivery-photo", data={"proof_type": proof_type}, files={"image": ("p.png", image, "image/png")})
    assert res.status_code == 200, res.text
    return res.json()


def test_photo_showing_an_id_card_passes_as_package_with_id():
    card = document(["JAMAICA", "DRIVER'S LICENCE", "SURNAME BROWN", "DATE OF BIRTH 01/02/1990"])
    r = photo_check("PACKAGE_WITH_ID", card)
    assert r["id_text_found"] is True
    assert r["status"] == "passed"


def test_photo_showing_neither_an_id_nor_a_person_is_flagged():
    box = document(["FRAGILE", "THIS SIDE UP"])
    for proof_type in ("PACKAGE_WITH_ID", "PACKAGE_WITH_RECIPIENT"):
        r = photo_check(proof_type, box)
        assert r["status"] == "flagged"
        assert r["reason"]
