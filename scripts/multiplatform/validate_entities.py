"""Section 21/22: opens each verified_direct URL and checks the on-page
hotel name against the expected hotel BEFORE any scraping happens.
Never scrapes - this only validates entity identity.

Usage:
    python scripts/multiplatform/validate_entities.py --max-hotels 10
    python scripts/multiplatform/validate_entities.py --hotel-id BOD012 --hotel-id BOD053
"""
from __future__ import annotations

import _pathsetup  # noqa: F401

import argparse
import csv

from bodrum_intelligence.reviews.common import REPORTS_DIR
from bodrum_intelligence.reviews.runner import ALL_PLATFORMS, filter_targets, load_targets, run_policies, run_review_platform

FIELDNAMES = ["hotel_id", "hotel_name_expected", "area", "platform", "source_url",
              "detected_hotel_name", "name_match_status", "page_accessible",
              "review_section_found", "validation_status", "validation_note", "checked_at"]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Validate hotel entity identity on each verified platform URL.")
    p.add_argument("--max-hotels", type=int, default=None)
    p.add_argument("--hotel-id", action="append", default=None)
    p.add_argument("--area", action="append", default=None)
    p.add_argument("--platform", choices=list(ALL_PLATFORMS) + ["policies"], default=None)
    p.add_argument("--headless", action="store_true")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    rows = filter_targets(load_targets(), hotel_ids=args.hotel_id, areas=args.area,
                           only_enabled=True, max_hotels=args.max_hotels)
    if not rows:
        print("Uyari: filtreye uyan enabled=TRUE hotel bulunamadi.")
        return 1

    platforms = [args.platform] if args.platform and args.platform != "policies" else list(ALL_PLATFORMS)
    include_policies = args.platform in (None, "policies")

    results = []
    for row in rows:
        for platform in platforms:
            if not row.get({"google_travel": "google_travel_url", "trip": "trip_url",
                             "tripadvisor": "tripadvisor_url"}[platform]):
                continue
            print(f"[validate] {row['hotel_id']} {row['hotel_name']} / {platform}")
            r = run_review_platform(row, platform, headless=args.headless, validate_only=True)
            results.append(r)
        if include_policies and row.get("policy_trip_url"):
            print(f"[validate] {row['hotel_id']} {row['hotel_name']} / policies_trip")
            results.append(run_policies(row, headless=args.headless, validate_only=True))

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = REPORTS_DIR / "multiplatform_entity_validation.csv"
    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=FIELDNAMES)
        w.writeheader()
        for r in results:
            w.writerow({
                "hotel_id": r["hotel_id"], "hotel_name_expected": r["hotel_name_expected"],
                "area": r["area"], "platform": r["platform"], "source_url": r["source_url"],
                "detected_hotel_name": r["detected_hotel_name"], "name_match_status": r["name_match_status"],
                "page_accessible": r["page_accessible"], "review_section_found": r["review_section_found"],
                "validation_status": r["validation_status"], "validation_note": r.get("error", ""),
                "checked_at": r["checked_at"],
            })

    wrong = sum(1 for r in results if r["status"] == "WRONG_ENTITY")
    valid = sum(1 for r in results if r["validation_status"] == "VALID_ENTITY")
    print(f"\n{len(results)} kontrol tamamlandi: VALID_ENTITY={valid}, WRONG_ENTITY={wrong}")
    print(f"Rapor: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
