"""Phase 3, section 24: 20-hotel discovery smoke test.

Mix (per section 24): existing verified (regression re-find check), a known
brand-collision pair on each side (Selectum, La Blanche), BOD192, the three
former pipe-character hotels, and never-before-attempted hotels across
different areas.

Runs Google Travel discovery for all 20, THEN Trip.com discovery for all 20
(sequential, one browser per platform - no parallel browsers, section 26/38).

Usage:
    python scripts/multiplatform/discovery/run_discovery_smoke_test.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import _pathsetup  # noqa: F401, E402

import csv

from bodrum_intelligence.reviews.common import REPORTS_DIR, master_hotel_csv_path, read_csv_dicts
from bodrum_intelligence.discovery.common import make_driver
from bodrum_intelligence.discovery import google_travel_discovery, trip_discovery

SMOKE_HOTEL_IDS = [
    "BOD007", "BOD008", "BOD013", "BOD036",  # google-verified regression check
    "BOD002", "BOD004", "BOD010", "BOD011",  # trip-verified regression check
    "BOD012", "BOD068", "BOD106", "BOD160",  # brand-collision pairs (Selectum, La Blanche)
    "BOD192",                                 # missing-link-record hotel
    "BOD135", "BOD155", "BOD175",             # former pipe-character bug hotels
    "BOD001", "BOD017", "BOD020", "BOD006",   # never-attempted, different areas
]

CANDIDATE_FIELDS = [
    "hotel_id", "hotel_name", "area", "platform", "candidate_rank", "candidate_url",
    "candidate_detected_name", "candidate_location", "name_similarity", "area_match",
    "address_match", "brand_collision_flag", "candidate_score", "validation_status",
    "validation_note", "discovered_at",
]


def run_platform(module, platform_name, hotels, headless=False):
    driver = make_driver(headless=headless)
    rows = []
    try:
        for i, h in enumerate(hotels, 1):
            print(f"[{platform_name}] {i}/{len(hotels)} {h['hotel_id']} {h['hotel_name']}")
            r = module.discover(driver, h["hotel_id"], h["hotel_name"], h["area"])
            print(f"  -> {r['validation_status']} score={r['candidate_score']} url={r['candidate_url'][:80]}")
            rows.append(r)
    finally:
        driver.quit()
    return rows


def main() -> int:
    master = read_csv_dicts(master_hotel_csv_path())
    by_id = {r["hotel_id"]: r for r in master}
    hotels = [by_id[hid] for hid in SMOKE_HOTEL_IDS if hid in by_id]
    missing = [hid for hid in SMOKE_HOTEL_IDS if hid not in by_id]
    if missing:
        print("WARNING: not in master:", missing)

    google_rows = run_platform(google_travel_discovery, "google_travel", hotels)
    trip_rows = run_platform(trip_discovery, "trip", hotels)

    out_dir = REPORTS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "discovery_smoke_test_20.csv"
    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=CANDIDATE_FIELDS)
        w.writeheader()
        for r in google_rows + trip_rows:
            w.writerow({k: r.get(k, "") for k in CANDIDATE_FIELDS})
    print(f"\nWrote {out_path}")

    for platform_name, rows in [("google_travel", google_rows), ("trip", trip_rows)]:
        found = sum(1 for r in rows if r["validation_status"] in ("FOUND_EXACT", "FOUND_HIGH_CONFIDENCE"))
        review = sum(1 for r in rows if r["validation_status"] == "REVIEW_REQUIRED")
        not_found = sum(1 for r in rows if r["validation_status"] in ("NOT_FOUND", "REJECTED_CANDIDATE"))
        errors = sum(1 for r in rows if r["validation_status"] == "ERROR")
        print(f"{platform_name}: found={found} review_required={review} not_found={not_found} error={errors} / {len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
