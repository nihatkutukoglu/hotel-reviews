"""Thin wrapper around the existing, untouched google/yorum.py scraper.

Loads the legacy script as a module (by file path, so the "google" module
name never collides with any installed google.* package), verifies the
on-page hotel name against the expected hotel BEFORE scraping, and writes
to a per-hotel-per-platform CSV in the raw platform-native schema (section
17: raw schema is preserved as-is; cross-platform metadata is added later,
at the processed layer, not injected into this file).
"""
from __future__ import annotations

import time

from selenium.common.exceptions import TimeoutException

from .aliases import resolve_entity_status
from .common import REPO_ROOT, per_hotel_csv_path, load_legacy_module, utcnow_iso, DATA_RAW_DIR
from .validation import WRONG_ENTITY, NAME_DETECTION_FAILED

_MODULE = None


def _module():
    global _MODULE
    if _MODULE is None:
        _MODULE = load_legacy_module("legacy_google_yorum", REPO_ROOT / "google" / "yorum.py")
    return _MODULE


def scrape_hotel(hotel_id: str, expected_hotel_name: str, area: str, direct_url: str,
                  max_reviews: int = 10, headless: bool = False, validate_only: bool = False) -> dict:
    m = _module()
    result = {
        "hotel_id": hotel_id, "hotel_name_expected": expected_hotel_name, "area": area,
        "platform": "google_travel", "source_url": direct_url,
        "detected_hotel_name": "", "name_match_status": "", "page_accessible": False,
        "review_section_found": False, "validation_status": "", "rows_added": 0,
        "status": "", "error": "", "checked_at": utcnow_iso(),
    }
    driver = None
    try:
        driver = m.tarayici_olustur(headless)
        driver.get(direct_url)
        time.sleep(m.SAYFA_ACILIS_BEKLEMESI)
        result["page_accessible"] = True
        detected = m.otel_adini_al(driver)
        result["detected_hotel_name"] = detected
        if not detected:
            # google/yorum.py:otel_adini_al returns "" (never a fake
            # placeholder name) when no heading/title text is found -
            # that's a technical detection failure, not a name conflict.
            result["validation_status"] = NAME_DETECTION_FAILED
            result["status"] = NAME_DETECTION_FAILED
            return result
        nm, vstatus = resolve_entity_status(hotel_id, "google_travel", expected_hotel_name, detected)
        result["name_match_status"] = nm
        result["validation_status"] = vstatus
        if vstatus == WRONG_ENTITY:
            result["status"] = "WRONG_ENTITY"
            return result
        if validate_only:
            result["status"] = vstatus
            return result

        out_path = per_hotel_csv_path(DATA_RAW_DIR / "reviews" / "google_travel", hotel_id, expected_hotel_name)
        added = m.yorumlari_cek(driver, direct_url, out_path, max_reviews)
        result["review_section_found"] = True
        result["rows_added"] = added
        result["status"] = "COMPLETED" if added > 0 else "VALID_ENTITY_NO_REVIEWS"
    except TimeoutException as exc:
        result["status"] = "PAGE_ERROR"
        result["error"] = str(exc).split("Stacktrace:", 1)[0].strip()
    except Exception as exc:  # noqa: BLE001 - report, never crash the batch
        result["status"] = "ERROR"
        result["error"] = str(exc)
    finally:
        if driver is not None:
            driver.quit()
    return result
