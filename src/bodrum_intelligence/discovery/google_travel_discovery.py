"""Google Travel URL discovery (section 9).

Live-verified flow (2026-08-26, real Chrome session):
    1. https://www.google.com/travel/search?q=<hotel name>+<area>+Bodrum
       renders result CARDS, each an <a href=".../travel/hotels/entity/...">
       whose accessible name (walking up from the anchor to the first
       ancestor with >10 chars of text) is the real hotel name, e.g.
       "Kefaluka Resort otelini yeni sekmede aç" ("open Kefaluka Resort in
       a new tab"). Confirmed across 8 live queries: Google always ranks
       the best-matching property FIRST regardless of whether the page
       renders as an auto-navigated single-hotel view or a broader
       area-results view.
    2. CRITICAL BUG FOUND IN THE FIRST VERSION OF THIS MODULE: reading the
       hotel name off the *search results page itself* (via a generic
       [role=heading]/document.title fallback) is unsafe - that page can
       carry an unrelated breadcrumb heading ("Bodrum · 2.925 sonuç") or,
       worse, one that echoes the query text back verbatim as a location
       label even when no real hotel was matched, producing a false-positive
       "exact match" score against nothing. Fixed per explicit instruction:
       the candidate URL is only ever a CANDIDATE from this page. The name
       is verified by opening that candidate URL as its OWN page load and
       reading otel_adini_al() there - the same function already proven
       reliable on real single-hotel detail pages.
"""
from __future__ import annotations

import time
from urllib.parse import quote

from selenium.common.exceptions import TimeoutException

from bodrum_intelligence.reviews.common import REPO_ROOT, load_legacy_module
from .candidate_scoring import score_candidate, NOT_FOUND, BLOCKED, ERROR
from .common import utcnow_iso

_MODULE = None

_TOP_CANDIDATE_JS = """
const anchors = Array.from(document.querySelectorAll('a[href*="travel/hotels/entity"]'));
if (!anchors.length) return null;
const a = anchors[0];
let el = a, text = '';
for (let i = 0; i < 6 && el; i++) {
    text = (el.textContent || '').trim();
    if (text.length > 10) break;
    el = el.parentElement;
}
return {href: a.href, nearText: text.slice(0, 200), totalCandidates: anchors.length};
"""


def _module():
    global _MODULE
    if _MODULE is None:
        _MODULE = load_legacy_module("legacy_google_yorum_discovery", REPO_ROOT / "google" / "yorum.py")
    return _MODULE


def discover(driver, hotel_id: str, hotel_name: str, area: str) -> dict:
    m = _module()
    query = f"{hotel_name} {area} Bodrum".strip()
    result = {
        "hotel_id": hotel_id, "hotel_name": hotel_name, "area": area, "platform": "google_travel",
        "candidate_rank": 1, "candidate_url": "", "candidate_detected_name": "",
        "candidate_location": "", "candidate_source": "google_travel_search",
        "name_similarity": 0.0, "area_match": None, "address_match": None,
        "brand_collision_flag": False, "candidate_score": 0,
        "validation_status": NOT_FOUND, "validation_note": "", "discovered_at": utcnow_iso(),
    }
    try:
        driver.get("https://www.google.com/travel/search?q=" + quote(query))
        time.sleep(5)
        top = driver.execute_script(_TOP_CANDIDATE_JS)
        if not top or not top.get("href"):
            result["validation_note"] = "No hotel-entity result card found on search results page."
            return result
        candidate_url = top["href"]
        result["candidate_url"] = candidate_url
        result["candidate_location"] = top.get("nearText", "")[:200]

        # Verify on the candidate's OWN page, never on the search-results
        # page's ambiguous heading (see module docstring).
        driver.get(candidate_url)
        time.sleep(4)
        detected = m.otel_adini_al(driver)
        result["candidate_detected_name"] = detected
        scored = score_candidate(hotel_name, detected, area)
        result["name_similarity"] = scored["name_similarity"]
        result["candidate_score"] = scored["candidate_score"]
        result["validation_status"] = scored["validation_status"]
        result["validation_note"] = (
            f"detected='{detected}' vs expected='{hotel_name}' "
            f"(card near-text was '{top.get('nearText', '')[:60]}', {top.get('totalCandidates')} candidates on page) "
            f"-> score={scored['candidate_score']}"
        )
    except TimeoutException as exc:
        result["validation_status"] = ERROR
        result["validation_note"] = f"timeout: {str(exc).split('Stacktrace:', 1)[0].strip()}"
    except Exception as exc:  # noqa: BLE001 - report, never crash the batch
        result["validation_status"] = ERROR
        result["validation_note"] = str(exc)
    return result
