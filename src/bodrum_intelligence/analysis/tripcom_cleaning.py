"""Phase C (Trip.com audit/cleaning) parsing helpers for the raw Trip.com
review CSVs (data/raw/reviews/trip/*.csv, columns: otel_adi, yorum, puan,
yorum_tarihi, konum, konaklama_tarihi, musteri_toplam_yorum_sayisi,
musteri_kademe, seyahat_tipi, oda_tipi - written by trip/trip_yorum.py).

Confirmed live from real scraped data (2026-08-26):
  - puan is already on a 0-10 scale (e.g. "8.0", "10.0").
  - yorum_tarihi looks like "Posted July 1, 2026" (an exact date, unlike
    Google Travel's relative-time strings).
  - konaklama_tarihi looks like "Stayed in June 2026" (month + year only).
  - seyahat_tipi is occasionally localized (Trip.com is a global site):
    "Traveling with friends"/"Travelling with friends" (both spellings
    appear), "Keluarga" (Indonesian: family), "Pelancong solo"
    (Indonesian: solo traveler), "Pasangan" (Indonesian: couple).
  - musteri_toplam_yorum_sayisi looks like "12 Reviews" / "1 Review".
  - A handful of rows show clear UI-leakage: konum == "Show More" (a
    button label, not a location) - flagged, never silently dropped.
"""
from __future__ import annotations

import re
import unicodedata

# --- rating ------------------------------------------------------------

def parse_trip_rating(puan_raw: str) -> tuple[float | None, float | None, bool]:
    """Returns (source_rating, source_rating_max, invalid_flag). Trip.com's
    scale is confirmed 0-10 from real sample data."""
    raw = (puan_raw or "").strip()
    if not raw:
        return None, None, True
    try:
        return float(raw.replace(",", ".")), 10.0, False
    except ValueError:
        return None, None, True


def rating_5_scale(source_rating: float | None, source_rating_max: float | None) -> float | None:
    if source_rating is None or not source_rating_max:
        return None
    return round(source_rating / source_rating_max * 5, 3)


# explicit thresholds per master prompt C7, applied on the NORMALIZED 5-scale
def rating_group_5(rating_5: float | None) -> str | None:
    if rating_5 is None:
        return None
    if rating_5 < 3.0:
        return "LOW"
    if rating_5 < 4.0:
        return "MID"
    return "HIGH"


# --- dates ---------------------------------------------------------------

_MONTHS = {m.lower(): i for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July",
     "August", "September", "October", "November", "December"], start=1)}

_POSTED_RE = re.compile(r"Posted\s+([A-Za-z]+)\s+(\d{1,2}),\s+(\d{4})", re.IGNORECASE)
_STAYED_RE = re.compile(r"Stayed\s+in\s+([A-Za-z]+)\s+(\d{4})", re.IGNORECASE)


def parse_review_date(raw: str) -> str | None:
    """Returns an ISO date string (YYYY-MM-DD) or None."""
    if not raw:
        return None
    m = _POSTED_RE.search(raw)
    if not m:
        return None
    month = _MONTHS.get(m.group(1).lower())
    if not month:
        return None
    return f"{m.group(3)}-{month:02d}-{int(m.group(2)):02d}"


def parse_stay_date(raw: str) -> tuple[int | None, int | None, str | None]:
    """Returns (stay_year, stay_month, stay_date_precision)."""
    if not raw:
        return None, None, None
    m = _STAYED_RE.search(raw)
    if not m:
        return None, None, None
    month = _MONTHS.get(m.group(1).lower())
    return int(m.group(2)), month, "MONTH"


# --- traveler type ---------------------------------------------------------

_TRAVELER_MAP = {
    "family": "FAMILY", "keluarga": "FAMILY",
    "couple": "COUPLE", "pasangan": "COUPLE",
    "solo traveler": "SOLO", "solo": "SOLO", "pelancong solo": "SOLO",
    "traveling with friends": "FRIENDS", "travelling with friends": "FRIENDS",
    "business": "BUSINESS", "business traveler": "BUSINESS",
}


def canonical_traveler_type(raw: str) -> str:
    if not raw:
        return "UNKNOWN"
    return _TRAVELER_MAP.get(raw.strip().lower(), "OTHER")


# --- room type (light-touch, never aggressive per C11) ---------------------

_ROOM_TYPE_RULES = [
    ("SUITE", ["suite"]),
    ("VILLA", ["villa"]),
    ("BUNGALOW", ["bungalow"]),
    ("FAMILY", ["family room"]),
    ("DELUXE", ["deluxe"]),
    ("STANDARD", ["standard"]),
]


def canonical_room_type(raw: str) -> str:
    if not raw or not raw.strip():
        return "UNKNOWN"
    folded = raw.lower()
    for canon, keywords in _ROOM_TYPE_RULES:
        if any(kw in folded for kw in keywords):
            return canon
    return "OTHER"


# --- customer tier ----------------------------------------------------------

_KNOWN_TIERS = ["diamond", "platinum", "gold", "silver"]


def canonical_customer_tier(raw: str) -> str:
    if not raw or not raw.strip():
        return "NONE"
    folded = raw.lower()
    if "verified by" in folded:
        return "OTHER"  # a trust badge, not a loyalty tier
    for tier in _KNOWN_TIERS:
        if tier in folded:
            return tier.upper()
    return "OTHER"


# --- reviewer review count ---------------------------------------------------

_REVIEW_COUNT_RE = re.compile(r"(\d+)\s*Review", re.IGNORECASE)


def parse_reviewer_review_count(raw: str) -> int | None:
    if not raw:
        return None
    m = _REVIEW_COUNT_RE.search(raw)
    return int(m.group(1)) if m else None


# --- reviewer location / country -------------------------------------------

_UI_ARTIFACT_LOCATIONS = {"show more", "show less"}
_LOCATION_PAREN_RE = re.compile(r"\(([^)]+)\)\s*$")


def parse_reviewer_location(raw: str) -> tuple[str | None, str | None, bool]:
    """Returns (reviewer_location_raw_or_none, reviewer_country, is_ui_leakage)."""
    if not raw or not raw.strip():
        return None, None, False
    folded = raw.strip().lower()
    if folded in _UI_ARTIFACT_LOCATIONS:
        return raw.strip(), None, True
    m = _LOCATION_PAREN_RE.search(raw.strip())
    country = m.group(1).strip() if m else raw.strip()
    return raw.strip(), country, False


# --- text-level UI leakage heuristic (review body) --------------------------

_TIER_ONLY_TEXTS = {"black diamond", "diamond", "platinum", "gold", "silver", "verified by"}


def is_review_text_ui_leakage(text: str) -> bool:
    """Heuristic: the 'review text' is actually a tier/badge label that
    leaked from a neighboring field, not real review content."""
    if not text:
        return False
    return text.strip().lower() in _TIER_ONLY_TEXTS


def clean_review_text(text: str) -> str:
    if not text:
        return ""
    s = unicodedata.normalize("NFKC", text)
    s = s.replace("​", "").replace("﻿", "")
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()
