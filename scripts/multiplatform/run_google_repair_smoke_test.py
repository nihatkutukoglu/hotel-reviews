"""Phase 2, section 12: retests the same 5 smoke hotels against the
repaired google/yorum.py, using real config eligibility (only hotels with
a verified_direct google_travel_url are attempted). Max 10 reviews/hotel.

Usage:
    python scripts/multiplatform/run_google_repair_smoke_test.py
"""
from __future__ import annotations

import _pathsetup  # noqa: F401

import csv

from bodrum_intelligence.reviews.common import DATA_RAW_DIR, REPORTS_DIR, evaluate_raw_csv_quality, per_hotel_csv_path
from bodrum_intelligence.reviews.runner import load_targets, run_review_platform

SMOKE_HOTEL_IDS = ["BOD012", "BOD056", "BOD058", "BOD007", "BOD013"]

FIELDNAMES = ["hotel_id", "hotel_name_expected", "detected_name", "entity_status", "reviews_saved",
              "empty_text", "invalid_rating", "duplicate_rows", "details_coverage", "status", "error"]


def main() -> int:
    targets = {r["hotel_id"]: r for r in load_targets()}
    rows_out = []

    for hid in SMOKE_HOTEL_IDS:
        row = targets.get(hid)
        if row is None or not row.get("google_travel_url"):
            rows_out.append({"hotel_id": hid, "hotel_name_expected": "", "detected_name": "",
                              "entity_status": "NO_VERIFIED_URL", "reviews_saved": 0, "empty_text": 0,
                              "invalid_rating": 0, "duplicate_rows": 0, "details_coverage": 0,
                              "status": "NO_VERIFIED_URL", "error": ""})
            continue

        print(f"\n[google-repair-smoke] {hid} {row['hotel_name']}")
        result = run_review_platform(row, "google_travel", max_reviews=10, headless=False)
        print(f"  -> status={result['status']} detected={result['detected_hotel_name']!r} "
              f"rows_added={result.get('rows_added')}")

        quality = {"rows_scraped": 0, "unique_rows": 0, "empty_review_text": 0,
                   "invalid_rating": 0, "duplicate_rows": 0}
        details_coverage = 0.0
        if result["status"] in ("COMPLETED", "VALID_ENTITY_NO_REVIEWS"):
            csv_path = per_hotel_csv_path(DATA_RAW_DIR / "reviews" / "google_travel", hid, row["hotel_name"])
            quality = evaluate_raw_csv_quality(csv_path, platform="google_travel")
            if csv_path.exists():
                from bodrum_intelligence.reviews.common import read_csv_dicts
                raw_rows = read_csv_dicts(csv_path)
                if raw_rows:
                    with_details = sum(1 for r in raw_rows if (r.get("tarih") or "").strip())
                    details_coverage = round(100 * with_details / len(raw_rows), 1)

        rows_out.append({
            "hotel_id": hid, "hotel_name_expected": row["hotel_name"],
            "detected_name": result["detected_hotel_name"], "entity_status": result["validation_status"],
            "reviews_saved": result.get("rows_added", 0), "empty_text": quality["empty_review_text"],
            "invalid_rating": quality["invalid_rating"], "duplicate_rows": quality["duplicate_rows"],
            "details_coverage": details_coverage, "status": result["status"], "error": result.get("error", ""),
        })

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = REPORTS_DIR / "google_repair_smoke_test.csv"
    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=FIELDNAMES)
        w.writeheader()
        for r in rows_out:
            w.writerow(r)

    passed = sum(1 for r in rows_out if r["status"] == "COMPLETED" and r["reviews_saved"] >= 1
                 and r["duplicate_rows"] == 0)
    wrong_entity = sum(1 for r in rows_out if r["status"] == "WRONG_ENTITY")
    print(f"\n=== GOOGLE REPAIR SMOKE SUMMARY ===")
    print(f"{len(rows_out)} hotels checked, {passed} fully passed, wrong_entity={wrong_entity}")
    google_full_ready = wrong_entity == 0 and passed >= 1
    print(f"GOOGLE_FULL_READY = {'YES' if google_full_ready else 'NO'}")
    print(f"Rapor: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
