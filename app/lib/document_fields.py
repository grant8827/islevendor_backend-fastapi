"""Heuristic field extraction from OCR'd document text, plus fuzzy name
matching against the applicant's registered name.

There's no shared layout across a Jamaican driver's license, an insurer's
certificate of insurance, and the tax authority's certificate of
registration — so this looks for common labels (NAME/INSURED/OWNER,
EXPIRY/VALID UNTIL) rather than a per-document template, and falls back to
"take the most name-shaped line" / "take the latest date on the page" when
no label is found. It's a best-effort reading of the page, not a guarantee —
callers decide what to do when a field comes back None.
"""

import difflib
import re
from datetime import date
from typing import Optional

from dateutil import parser as date_parser

NAME_LABEL_RE = re.compile(
    r"\b(?:FULL\s*NAME|NAME\s*OF\s*INSURED|INSURED\s*NAME|POLICY\s*HOLDER|"
    r"REGISTERED\s*OWNER|OWNER(?:'?S)?\s*NAME|OWNER|NAME)\b\s*[:\-]?\s*(.+)",
    re.IGNORECASE,
)
# A plausible person/business name: letters/spaces/./'/- only, 2-6 "words".
NAME_SHAPE_RE = re.compile(r"^[A-Za-z][A-Za-z.'\-]*(?:\s+[A-Za-z][A-Za-z.'\-]*){1,5}$")

DATE_LABEL_RE = re.compile(r"\b(?:EXPIR\w*|VALID\s*(?:UNTIL|THRU|TO)|EXP(?:IRY)?\s*DATE)\b", re.IGNORECASE)
DATE_RE = re.compile(
    r"(\d{1,2}[\/\-.\s]\d{1,2}[\/\-.\s]\d{2,4}"  # 05/01/2027, 5-1-27, 05.01.2027
    r"|\d{1,2}\s+[A-Za-z]{3,9}\s+\d{2,4}"  # 05 January 2027
    r"|[A-Za-z]{3,9}\s+\d{1,2},?\s+\d{2,4})"  # January 5, 2027
)


def _parse_date(raw: str) -> Optional[date]:
    try:
        # Jamaica, like the UK, writes dates day-first.
        return date_parser.parse(raw, dayfirst=True, fuzzy=True).date()
    except (ValueError, OverflowError, TypeError):
        return None


def extract_name(text: str) -> Optional[str]:
    """Looks for a labeled name line first; falls back to the first
    name-shaped line in the document (many certs print the holder's name
    prominently near the top with no explicit "Name:" label).
    """
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    for line in lines:
        m = NAME_LABEL_RE.search(line)
        if m:
            candidate = m.group(1).strip(" .:-")
            if NAME_SHAPE_RE.match(candidate):
                return candidate.upper()

    for line in lines:
        if NAME_SHAPE_RE.match(line):
            return line.upper()

    return None


def extract_expiry_date(text: str) -> Optional[date]:
    """Looks for a date on the same line as an expiry-ish label first; falls
    back to the latest date found anywhere on the page (an expiry date is
    almost always the latest date printed on a KYC document — issue/DOB
    dates are earlier).
    """
    for line in text.splitlines():
        if DATE_LABEL_RE.search(line):
            m = DATE_RE.search(line)
            if m:
                parsed = _parse_date(m.group(1))
                if parsed:
                    return parsed

    candidates = [d for m in DATE_RE.finditer(text) if (d := _parse_date(m.group(1)))]
    return max(candidates) if candidates else None


def _normalize_tokens(name: str) -> set[str]:
    cleaned = re.sub(r"[^A-Za-z\s]", " ", name.upper())
    return {tok for tok in cleaned.split() if len(tok) > 1}


def name_match_score(expected_name: str, extracted_name: str) -> float:
    """Fraction of `expected_name`'s tokens found in `extracted_name`,
    allowing near-matches (edit-distance ratio >= 0.8) to absorb single
    OCR-misread characters. 1.0 = every token of the registered name showed
    up on the document; 0.0 = none did.
    """
    expected_tokens = _normalize_tokens(expected_name)
    extracted_tokens = _normalize_tokens(extracted_name)
    if not expected_tokens or not extracted_tokens:
        return 0.0

    matched = sum(
        1
        for token in expected_tokens
        if token in extracted_tokens
        or any(difflib.SequenceMatcher(None, token, other).ratio() >= 0.8 for other in extracted_tokens)
    )
    return matched / len(expected_tokens)
