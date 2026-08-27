"""Name/area/URL consistency checks and hotel-entity validation statuses
shared by the audit scripts and the live scraping adapters.
"""
from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher

# --- name normalization / matching -----------------------------------------

_TR_MAP = str.maketrans({"ı": "i", "İ": "i", "ş": "s", "ğ": "g", "ü": "u", "ö": "o", "ç": "c"})


def normalize_name(name: str | None) -> str:
    if not name:
        return ""
    s = name.strip().lower().translate(_TR_MAP)
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def name_match_status(expected_name: str | None, observed_name: str | None) -> str:
    """Compare two hotel names. Returns one of:
    EXACT, NORMALIZED_MATCH, REVIEW_REQUIRED, CONFLICT, NO_DATA.

    Only compares the two given names directly (never fuzzy-matches against
    a *different* hotel's name), so distinct sister properties such as
    "Selectum Colours" and "Selectum Collection" are correctly reported as
    CONFLICT rather than silently merged.
    """
    if not observed_name:
        return "NO_DATA"
    if expected_name == observed_name:
        return "EXACT"
    ne, no = normalize_name(expected_name), normalize_name(observed_name)
    if ne == no:
        return "NORMALIZED_MATCH"
    ratio = SequenceMatcher(None, ne, no).ratio()
    # Threshold picked empirically: a trailing city/area tag ("Hotel X" vs
    # "Hotel X Bodrum") scores ~0.84 and should be REVIEW_REQUIRED, while
    # genuinely different sister properties ("Selectum Colours" vs
    # "Selectum Collection" ~0.74, "La Blanche Island" vs "La Blanche
    # Resort" ~0.71) must stay CONFLICT - see test_name_matching.py.
    if ratio >= 0.80:
        return "REVIEW_REQUIRED"
    return "CONFLICT"


# --- URL format validation ---------------------------------------------------

URL_PATTERNS = {
    # Accepts both the canonical hash-path form (.../entity/<hash>) and the
    # discovery-derived form (.../entity?q=...&ts=...), which was confirmed
    # live to be a stable, cold-session-safe URL for the same hotel entity.
    "google_travel": re.compile(r"google\.[a-z.]+/travel/hotels/entity(/|\?)", re.I),
    "trip": re.compile(r"trip\.com/.*hotel-detail-|trip\.com/hotels/.*detail", re.I),
    "tripadvisor": re.compile(r"tripadvisor\.[a-z.]+/Hotel_Review-", re.I),
}
DOMAIN_HINT = {
    "google_travel": "google.",
    "trip": "trip.com",
    "tripadvisor": "tripadvisor.",
}


def url_present(url: str | None) -> bool:
    u = (url or "").strip()
    return u != "" and u.lower() != "null"


def url_format_status(platform: str, url: str | None) -> str:
    """OK, NO_URL, INVALID_DOMAIN, or INVALID_URL."""
    if not url_present(url):
        return "NO_URL"
    u = (url or "").strip()
    if DOMAIN_HINT[platform] not in u.lower():
        return "INVALID_DOMAIN"
    if not URL_PATTERNS[platform].search(u):
        return "INVALID_URL"
    return "OK"


def is_verified(status: str | None) -> bool:
    return (status or "").strip().lower() == "verified_direct"


# --- entity validation status enum ------------------------------------------

VALID_ENTITY = "VALID_ENTITY"
NAME_REVIEW_REQUIRED = "NAME_REVIEW_REQUIRED"
WRONG_ENTITY = "WRONG_ENTITY"
PAGE_ERROR = "PAGE_ERROR"
NAME_DETECTION_FAILED = "NAME_DETECTION_FAILED"


def entity_validation_status(name_match: str) -> str:
    """Map a name_match_status result to the entity-validation status used
    to gate scraping (section 21): only EXACT/NORMALIZED_MATCH may proceed.
    """
    if name_match in ("EXACT", "NORMALIZED_MATCH"):
        return VALID_ENTITY
    if name_match == "REVIEW_REQUIRED":
        return NAME_REVIEW_REQUIRED
    if name_match == "CONFLICT":
        return WRONG_ENTITY
    return PAGE_ERROR
