"""Trip.com URL discovery (section 10).

Live-verified flow (2026-08-26, real Chrome session):
    1. https://www.trip.com/hotels/ -> click the "Where to?" destination
       input, type the hotel name.
    2. An autocomplete dropdown appears; click_best_text_match() (structural
       DOM walk, no hardcoded hashed class names - same lesson as the
       Google selector repair in phase 2) clicks the closest-matching
       suggestion.
    3. Click the visible "Search" button (button.tripui-online-btn, a
       stable design-system class, not a rotating hash).
    4. The resulting search-results URL carries the resolved hotel id as
       ?optionId=<digits> - this is the SAME id trip.com uses in its own
       canonical "bodrum-hotel-detail-<id>-..." URLs (confirmed against
       Armonia Holiday Village & Spa: optionId=3448104 matches the existing
       verified link for BOD002 exactly).
    5. https://www.trip.com/hotels/detail/?hotelId=<id> is a stable,
       cold-session-safe canonical URL (confirmed) - trip_adapter.py's
       otel_adini_al() reads the hotel name straight off it.

BUG FOUND IN THE FIRST VERSION, FIXED HERE (per explicit instruction after
the first 20-hotel smoke test): two problems, both now fixed.
  1. The DOM-matching heuristic used a crude JS `includes()` check, which
     false-matches short generic leaves (e.g. a bare "Hotel" nav label is
     a substring of nearly every hotel name) - it could click on unrelated
     UI text when the real autocomplete dropdown hadn't rendered yet.
     Fixed: candidates are now scored with the same real name-similarity
     function (SequenceMatcher on normalized text) used everywhere else in
     this codebase, with a minimum-confidence floor, and only THEN clicked
     by exact text - no fuzziness at the DOM layer.
  2. A previous hotel's confirmed selection could leak into the next
     hotel's search on the same reused browser session (observed: several
     consecutive unrelated hotels all resolving to the SAME stale
     optionId). Fixed: cookies + local/session storage are cleared and the
     page is hard-reloaded before every single hotel's search
     (reset_browser_state), and a duplicate-optionId safety net rejects a
     result that repeats an id already seen earlier in the same run.
"""
from __future__ import annotations

import re
import time

from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.common.by import By

from bodrum_intelligence.reviews.common import REPO_ROOT, load_legacy_module
from .candidate_scoring import score_candidate, name_similarity, NOT_FOUND, ERROR, REJECTED_CANDIDATE
from .common import click_exact_text_leaf, list_clickable_text_leaves, reset_browser_state, utcnow_iso

_MODULE = None
_OPTION_ID_RE = re.compile(r"[?&]optionId=(\d{4,})")  # real ids are 5-8 digits; guards against a stray "optionId=0" when no destination actually got selected
_MIN_SUGGESTION_SIMILARITY = 0.5
_seen_option_ids: set[str] = set()  # process-wide safety net against stale-id reuse


def _module():
    global _MODULE
    if _MODULE is None:
        _MODULE = load_legacy_module("legacy_trip_yorum_discovery", REPO_ROOT / "trip" / "trip_yorum.py")
    return _MODULE


def _best_suggestion(driver, hotel_name: str) -> tuple[str | None, float]:
    """Polls the page for clickable text leaves and returns the one with
    the highest real name-similarity to hotel_name, if any clears the
    minimum-confidence floor."""
    best_text, best_sim = None, 0.0
    for leaf in list_clickable_text_leaves(driver, min_len=4, cap=120):
        sim = name_similarity(hotel_name, leaf)
        if sim > best_sim:
            best_text, best_sim = leaf, sim
    return (best_text, best_sim) if best_sim >= _MIN_SUGGESTION_SIMILARITY else (None, best_sim)


def discover(driver, hotel_id: str, hotel_name: str, area: str) -> dict:
    m = _module()
    result = {
        "hotel_id": hotel_id, "hotel_name": hotel_name, "area": area, "platform": "trip",
        "candidate_rank": 1, "candidate_url": "", "candidate_detected_name": "",
        "candidate_location": "", "candidate_source": "trip_com_search_box",
        "name_similarity": 0.0, "area_match": None, "address_match": None,
        "brand_collision_flag": False, "candidate_score": 0,
        "validation_status": NOT_FOUND, "validation_note": "", "discovered_at": utcnow_iso(),
    }
    try:
        reset_browser_state(driver, "https://www.trip.com/hotels/")
        time.sleep(3)
        try:
            box = driver.find_element(By.CSS_SELECTOR, "input[placeholder='Where to?']")
        except NoSuchElementException:
            result["validation_note"] = "Search box not found (site layout may have changed)."
            return result
        box.click()
        time.sleep(0.5)
        box.clear()
        box.send_keys(hotel_name)

        best_text, best_sim = None, 0.0
        for _ in range(5):  # poll for the dropdown to actually refresh instead of a fixed sleep
            time.sleep(1)
            best_text, best_sim = _best_suggestion(driver, hotel_name)
            if best_text:
                break
        if not best_text:
            result["validation_note"] = (
                f"No autocomplete suggestion cleared the {_MIN_SUGGESTION_SIMILARITY} "
                f"similarity floor (best_similarity={best_sim:.2f})."
            )
            return result
        result["candidate_location"] = best_text
        if not click_exact_text_leaf(driver, best_text):
            result["validation_note"] = f"Matched suggestion {best_text!r} but it was not clickable."
            return result
        time.sleep(1.5)
        try:
            search_btn = driver.find_element(By.CSS_SELECTOR, "button.tripui-online-btn")
            search_btn.click()
        except NoSuchElementException:
            result["validation_note"] = "Search button not found after selecting a suggestion."
            return result
        time.sleep(5)
        match = _OPTION_ID_RE.search(driver.current_url)
        if not match:
            result["validation_note"] = f"No optionId in results URL: {driver.current_url}"
            return result
        hotel_numeric_id = match.group(1)
        if hotel_numeric_id in _seen_option_ids:
            result["validation_status"] = REJECTED_CANDIDATE
            result["validation_note"] = (
                f"Safety net: optionId={hotel_numeric_id} was already used for an earlier hotel "
                f"in this run - rejecting rather than risk stale-session reuse."
            )
            return result
        candidate_url = f"https://www.trip.com/hotels/detail/?hotelId={hotel_numeric_id}"
        result["candidate_url"] = candidate_url
        driver.get(candidate_url)
        time.sleep(4)
        m.takvimi_kapat(driver)
        detected = m.otel_adini_al(driver)
        result["candidate_detected_name"] = detected
        scored = score_candidate(hotel_name, detected, area)
        result["name_similarity"] = scored["name_similarity"]
        result["candidate_score"] = scored["candidate_score"]
        result["validation_status"] = scored["validation_status"]
        result["validation_note"] = (
            f"suggestion='{best_text}' (sim={best_sim:.2f}) detected='{detected}' "
            f"vs expected='{hotel_name}' -> score={scored['candidate_score']}"
        )
        if scored["validation_status"] not in ("NOT_FOUND",):
            _seen_option_ids.add(hotel_numeric_id)
    except TimeoutException as exc:
        result["validation_status"] = ERROR
        result["validation_note"] = f"timeout: {str(exc).split('Stacktrace:', 1)[0].strip()}"
    except Exception as exc:  # noqa: BLE001 - report, never crash the batch
        result["validation_status"] = ERROR
        result["validation_note"] = str(exc)
    return result
