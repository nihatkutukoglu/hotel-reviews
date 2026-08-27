"""Thin wrapper around the existing, untouched tripadvisor/tripadvisor_yorum.py
scraper. See google_travel_adapter.py for the shared design rationale.
"""
from __future__ import annotations

import time

from selenium.common.exceptions import TimeoutException

from .aliases import resolve_entity_status
from .common import REPO_ROOT, per_hotel_csv_path, load_legacy_module, utcnow_iso, DATA_RAW_DIR
from .validation import WRONG_ENTITY

_MODULE = None

_BLOCK_MARKERS = (
    "erişim geçici olarak kısıtlanmıştır",
    "access to this page has been denied",
    "access denied",
    "unusual traffic",
    "verify you are a human",
    "pardon our interruption",
)


def _blocked_by_platform(driver) -> bool:
    try:
        haystack = (driver.title or "") + " " + driver.page_source[:5000]
    except Exception:  # noqa: BLE001 - best-effort probe only
        return False
    haystack = haystack.lower()
    return any(marker in haystack for marker in _BLOCK_MARKERS)


def _module():
    global _MODULE
    if _MODULE is None:
        _MODULE = load_legacy_module(
            "legacy_tripadvisor_yorum", REPO_ROOT / "tripadvisor" / "tripadvisor_yorum.py"
        )
    return _MODULE


def scrape_hotel(hotel_id: str, expected_hotel_name: str, area: str, direct_url: str,
                  max_reviews: int = 10, headless: bool = False, validate_only: bool = False) -> dict:
    m = _module()
    result = {
        "hotel_id": hotel_id, "hotel_name_expected": expected_hotel_name, "area": area,
        "platform": "tripadvisor", "source_url": direct_url,
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
        if _blocked_by_platform(driver):
            result["status"] = "BLOCKED_SAFE_STOP"
            result["error"] = "TripAdvisor bot-protection / temporary-restricted-access page detected."
            return result
        detected = m.otel_adini_al(driver)
        result["detected_hotel_name"] = detected
        nm, vstatus = resolve_entity_status(hotel_id, "tripadvisor", expected_hotel_name, detected)
        result["name_match_status"] = nm
        result["validation_status"] = vstatus
        if vstatus == WRONG_ENTITY:
            result["status"] = "WRONG_ENTITY"
            return result
        if validate_only:
            result["status"] = vstatus
            return result

        out_path = per_hotel_csv_path(DATA_RAW_DIR / "reviews" / "tripadvisor", hotel_id, expected_hotel_name)
        _fetched, added = m.yorumlari_cek(driver, direct_url, out_path, max_reviews)
        result["review_section_found"] = True
        result["rows_added"] = added
        result["status"] = "COMPLETED" if added > 0 else "VALID_ENTITY_NO_REVIEWS"
    except TimeoutException as exc:
        result["status"] = "PAGE_ERROR"
        result["error"] = str(exc).split("Stacktrace:", 1)[0].strip()
    except RuntimeError as exc:
        msg = str(exc)
        result["status"] = "MANUAL_ACTION_REQUIRED" if "dogrulama" in msg.lower() or "cerez" in msg.lower() else "ERROR"
        result["error"] = msg
    except Exception as exc:  # noqa: BLE001 - report, never crash the batch
        result["status"] = "ERROR"
        result["error"] = str(exc)
    finally:
        if driver is not None:
            driver.quit()
    return result
