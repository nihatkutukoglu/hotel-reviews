"""Shared logic for reading config/multiplatform_hotel_targets.csv and
dispatching to the right platform adapter. Used by validate_entities.py,
run_smoke_tests.py, run_batch.py and the per-platform run_*.py scripts.
"""
from __future__ import annotations

from typing import Callable

from . import google_travel_adapter, trip_adapter, tripadvisor_adapter, policies_adapter
from .common import CONFIG_DIR, read_csv_dicts

TARGETS_CSV = CONFIG_DIR / "multiplatform_hotel_targets.csv"

URL_COLUMN = {
    "google_travel": "google_travel_url",
    "trip": "trip_url",
    "tripadvisor": "tripadvisor_url",
}
STATUS_COLUMN = {
    "google_travel": "google_travel_status",
    "trip": "trip_status",
    "tripadvisor": "tripadvisor_status",
}
REVIEW_ADAPTERS = {
    "google_travel": google_travel_adapter,
    "trip": trip_adapter,
    "tripadvisor": tripadvisor_adapter,
}
ALL_PLATFORMS = ("google_travel", "trip", "tripadvisor")


def load_targets() -> list[dict]:
    if not TARGETS_CSV.exists():
        raise FileNotFoundError(
            f"{TARGETS_CSV} bulunamadi. Once: python scripts/multiplatform/build_platform_config.py")
    return read_csv_dicts(TARGETS_CSV)


def _truthy(v: str) -> bool:
    return str(v).strip().lower() in ("true", "1", "yes")


def filter_targets(rows: list[dict], hotel_ids: list[str] | None = None,
                    areas: list[str] | None = None, platform: str | None = None,
                    only_enabled: bool = True, max_hotels: int | None = None) -> list[dict]:
    out = rows
    if only_enabled:
        out = [r for r in out if _truthy(r.get("enabled", ""))]
    if hotel_ids:
        wanted = set(hotel_ids)
        out = [r for r in out if r["hotel_id"] in wanted]
    if areas:
        wanted_areas = {a.lower() for a in areas}
        out = [r for r in out if r["area"].lower() in wanted_areas]
    if platform:
        col = URL_COLUMN[platform]
        out = [r for r in out if r.get(col)]
    if max_hotels is not None:
        out = out[:max_hotels]
    return out


def run_review_platform(row: dict, platform: str, max_reviews: int = 10,
                         headless: bool = False, validate_only: bool = False) -> dict:
    adapter = REVIEW_ADAPTERS[platform]
    url = row.get(URL_COLUMN[platform], "")
    if not url:
        return {
            "hotel_id": row["hotel_id"], "hotel_name_expected": row["hotel_name"], "area": row["area"],
            "platform": platform, "source_url": "", "detected_hotel_name": "", "name_match_status": "",
            "page_accessible": False, "review_section_found": False, "validation_status": "NO_URL",
            "rows_added": 0, "status": "NO_VERIFIED_URL", "error": "", "checked_at": "",
        }
    return adapter.scrape_hotel(row["hotel_id"], row["hotel_name"], row["area"], url,
                                 max_reviews=max_reviews, headless=headless, validate_only=validate_only)


def run_policies(row: dict, headless: bool = False, resume: bool = True, force: bool = False,
                  validate_only: bool = False) -> dict:
    url = row.get("policy_trip_url", "")
    if not url:
        return {
            "hotel_id": row["hotel_id"], "hotel_name_expected": row["hotel_name"], "area": row["area"],
            "platform": "policies_trip", "source_url": "", "detected_hotel_name": "", "name_match_status": "",
            "page_accessible": False, "review_section_found": False, "validation_status": "NO_URL",
            "rows_added": 0, "status": "NO_VERIFIED_URL", "error": "", "checked_at": "",
        }
    return policies_adapter.scrape_hotel(row["hotel_id"], row["hotel_name"], row["area"], url,
                                          headless=headless, resume=resume, force=force,
                                          validate_only=validate_only)
