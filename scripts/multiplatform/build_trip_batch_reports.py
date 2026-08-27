"""Phase 2, section 7: builds the Trip.com 20-review controlled-batch
reports from whatever has actually been scraped into
data/raw/reviews/trip/ - never invents numbers.

Usage:
    python scripts/multiplatform/build_trip_batch_reports.py
"""
from __future__ import annotations

import _pathsetup  # noqa: F401

import csv

from bodrum_intelligence.reviews.common import DATA_RAW_DIR, REPORTS_DIR, per_hotel_csv_path, read_csv_dicts
from bodrum_intelligence.reviews.runner import filter_targets, load_targets


def pct(numerator: int, denominator: int) -> float:
    return round(100 * numerator / denominator, 1) if denominator else 0.0


def main() -> int:
    targets = filter_targets(load_targets(), only_enabled=True, platform="trip")
    trip_dir = DATA_RAW_DIR / "reviews" / "trip"

    status_rows, coverage_rows, quality_rows = [], [], []

    for row in targets:
        hid, hname, area = row["hotel_id"], row["hotel_name"], row["area"]
        csv_path = per_hotel_csv_path(trip_dir, hid, hname)
        exists = csv_path.exists()
        data = read_csv_dicts(csv_path) if exists else []

        status = "COMPLETED" if data else ("NO_REVIEWS_FOUND" if exists else "NOT_RUN")
        status_rows.append({"hotel_id": hid, "hotel_name": hname, "area": area, "status": status,
                             "rows_saved": len(data), "csv_path": str(csv_path) if exists else ""})

        coverage_rows.append({"hotel_id": hid, "hotel_name": hname, "area": area,
                               "verified_link": True, "scraped": exists, "unique_review_count": len(data)})

        if not data:
            quality_rows.append({
                "hotel_id": hid, "hotel_name": hname, "rows": 0, "unique_rows": 0, "empty_text": 0,
                "invalid_rating": 0, "duplicate_hash": 0, "date_coverage": 0, "stay_date_coverage": 0,
                "traveler_type_coverage": 0, "room_type_coverage": 0,
            })
            continue

        seen = set()
        duplicate_hash = 0
        for r in data:
            key = tuple(sorted(r.items()))
            if key in seen:
                duplicate_hash += 1
            else:
                seen.add(key)

        empty_text = sum(1 for r in data if not (r.get("yorum") or "").strip())
        invalid_rating = 0
        from bodrum_intelligence.reviews.common import parse_source_rating
        for r in data:
            raw = (r.get("puan") or "").strip()
            if raw:
                rating, _ = parse_source_rating("trip", raw)
                if rating is None:
                    invalid_rating += 1
        date_cov = sum(1 for r in data if (r.get("yorum_tarihi") or "").strip())
        stay_cov = sum(1 for r in data if (r.get("konaklama_tarihi") or "").strip())
        travel_cov = sum(1 for r in data if (r.get("seyahat_tipi") or "").strip())
        room_cov = sum(1 for r in data if (r.get("oda_tipi") or "").strip())

        quality_rows.append({
            "hotel_id": hid, "hotel_name": hname, "rows": len(data), "unique_rows": len(seen),
            "empty_text": empty_text, "invalid_rating": invalid_rating, "duplicate_hash": duplicate_hash,
            "date_coverage": pct(date_cov, len(data)), "stay_date_coverage": pct(stay_cov, len(data)),
            "traveler_type_coverage": pct(travel_cov, len(data)), "room_type_coverage": pct(room_cov, len(data)),
        })

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(REPORTS_DIR / "trip_batch_20_status.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["hotel_id", "hotel_name", "area", "status", "rows_saved", "csv_path"])
        w.writeheader()
        w.writerows(status_rows)

    with open(REPORTS_DIR / "trip_batch_20_coverage.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["hotel_id", "hotel_name", "area", "verified_link", "scraped",
                                           "unique_review_count"])
        w.writeheader()
        w.writerows(coverage_rows)

    with open(REPORTS_DIR / "trip_batch_20_quality.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["hotel_id", "hotel_name", "rows", "unique_rows", "empty_text",
                                           "invalid_rating", "duplicate_hash", "date_coverage",
                                           "stay_date_coverage", "traveler_type_coverage", "room_type_coverage"])
        w.writeheader()
        w.writerows(quality_rows)

    total_rows = sum(r["rows_saved"] for r in status_rows)
    completed = sum(1 for r in status_rows if r["status"] == "COMPLETED")
    total_dupes = sum(r["duplicate_hash"] for r in quality_rows)
    total_invalid = sum(r["invalid_rating"] for r in quality_rows)
    print(f"Trip batch: {completed}/{len(targets)} hotels completed, {total_rows} total unique reviews saved")
    print(f"duplicate_hash total: {total_dupes}, invalid_rating total: {total_invalid}")
    trip_full_ready = completed == len(targets) and total_dupes == 0
    print(f"TRIP_FULL_READY = {'YES' if trip_full_ready else 'NO'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
