"""Phase B (audit/cleaning) parsing helpers for the raw Google Travel review
CSVs (data/raw/reviews/google_travel/*.csv, columns: otel_adi, yorum,
hizmet, tarih, puan - all in Turkish, written by google/yorum.py).

Confirmed live from real scraped data (2026-08-26):
  - "tarih" is not a real date: it's a relative-time string that ALSO
    encodes which underlying source Google Travel aggregated the review
    from, e.g. "Google uzerinde 3 hafta once" or "Tripadvisor uzerinde bir
    ay once" or "Trip.com uzerinde ...". This confirms the master prompt's
    warning that a Google Travel review panel is not exclusively sourced
    from Google's own reviews.
  - "hizmet" usually starts with three mini sub-scores in a fixed order -
    "OdalarX,XHizmetX,XKonumX,X" (Rooms/Service/Location, Turkish-comma
    decimals) - sometimes followed by free-text elaboration sections
    (e.g. "Yiyecek ve icecekler..."), sometimes empty entirely.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

_SOURCE_MAP = {
    "google": "GOOGLE",
    "tripadvisor": "TRIPADVISOR",
    "trip.com": "TRIP_COM",
    "booking.com": "OTHER",
    "expedia": "OTHER",
}

_DATE_RE = re.compile(r"^(.*?)\s+üzerinde\s+(.+?)(?:\s+düzenlendi)?$", re.IGNORECASE)
_AGE_RE = re.compile(r"(bir|\d+)\s*(gün|hafta|ay|yıl)", re.IGNORECASE)
_AGE_UNIT_DAYS = {"gün": 1, "hafta": 7, "ay": 30, "yıl": 365}
_DETAIL_RE = re.compile(
    r"Odalar\s*([\d,.]+)\s*Hizmet\s*([\d,.]+)\s*Konum\s*([\d,.]+)(.*)$", re.IGNORECASE | re.DOTALL
)


def _fold(s: str) -> str:
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii").lower()


def parse_review_source(tarih_raw: str) -> tuple[str, str | None]:
    """Returns (canonical_source, raw_source_label|None). Canonical is one
    of GOOGLE/TRIPADVISOR/TRIP_COM/OTHER/UNKNOWN."""
    if not tarih_raw:
        return "UNKNOWN", None
    m = _DATE_RE.match(tarih_raw.strip())
    if not m:
        return "UNKNOWN", None
    label = m.group(1).strip()
    canonical = _SOURCE_MAP.get(_fold(label), "OTHER")
    return canonical, label


def parse_review_age_days(tarih_raw: str) -> tuple[int | None, str | None]:
    """Returns (approx_age_in_days, relative_phrase). Turkish "bir"="1"."""
    if not tarih_raw:
        return None, None
    m = _DATE_RE.match(tarih_raw.strip())
    phrase = m.group(2).strip() if m else tarih_raw.strip()
    am = _AGE_RE.search(phrase)
    if not am:
        return None, phrase
    qty_raw, unit = am.group(1).lower(), am.group(2).lower()
    qty = 1 if qty_raw == "bir" else int(qty_raw)
    return qty * _AGE_UNIT_DAYS.get(unit, 0), phrase


def is_edited(tarih_raw: str) -> bool:
    return "düzenlendi" in (tarih_raw or "").lower()


@dataclass
class ParsedDetail:
    rooms_score: float | None
    service_score: float | None
    location_score: float | None
    additional_detail_text: str


def parse_detail_scores(hizmet_raw: str) -> ParsedDetail:
    if not hizmet_raw:
        return ParsedDetail(None, None, None, "")
    m = _DETAIL_RE.match(hizmet_raw.strip())
    if not m:
        return ParsedDetail(None, None, None, hizmet_raw.strip())

    def to_float(s: str) -> float | None:
        try:
            return float(s.replace(",", "."))
        except ValueError:
            return None

    return ParsedDetail(to_float(m.group(1)), to_float(m.group(2)), to_float(m.group(3)),
                         m.group(4).strip())


def parse_rating(puan_raw: str) -> tuple[float | None, bool]:
    """Returns (rating_1_to_5, invalid_flag)."""
    raw = (puan_raw or "").strip()
    if not raw:
        return None, True
    if "/" in raw:
        num, _, denom = raw.partition("/")
        try:
            n, d = float(num.replace(",", ".")), float(denom.replace(",", "."))
            return round(n / d * 5, 3) if d else None, d == 0
        except ValueError:
            return None, True
    try:
        return float(raw.replace(",", ".")), False
    except ValueError:
        return None, True


def clean_review_text(text: str) -> str:
    if not text:
        return ""
    s = unicodedata.normalize("NFKC", text)
    s = s.replace("​", "").replace("﻿", "")
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


RATING_GROUPS = {1: "LOW", 2: "LOW", 3: "MID", 4: "HIGH", 5: "HIGH"}


def rating_group(rating_1_to_5: float | None) -> str | None:
    if rating_1_to_5 is None:
        return None
    return RATING_GROUPS.get(round(rating_1_to_5), None)
