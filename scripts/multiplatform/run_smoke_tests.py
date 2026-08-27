"""Section 23-26: selects 5 hotels per the diversity criteria, scrapes a
capped number of reviews (default 10) on each verified platform plus one
policies row, and writes reports/multiplatform_smoke_test.csv.

Usage:
    python scripts/multiplatform/run_smoke_tests.py
    python scripts/multiplatform/run_smoke_tests.py --headless
"""
from __future__ import annotations

import _pathsetup  # noqa: F401

import argparse
import csv
from collections import Counter

from bodrum_intelligence.reviews.common import (
    REPORTS_DIR, evaluate_raw_csv_quality, master_hotel_csv_path,
    per_hotel_csv_path, read_csv_dicts, DATA_RAW_DIR,
)
from bodrum_intelligence.reviews.runner import ALL_PLATFORMS, load_targets, run_policies, run_review_platform

FIELDNAMES = ["hotel_id", "hotel_name", "platform", "url_valid", "entity_valid", "rows_scraped",
              "unique_rows", "empty_review_text", "invalid_rating", "duplicate_rows", "status", "error"]


def select_smoke_hotels(targets: list[dict], master_by_id: dict[str, dict]) -> list[dict]:
    """Section 23 selection: prefer 3-platform-verified, spread across
    areas, at least one likely brand-collision risk, one high-volume and
    one low/medium-volume hotel - drawn only from real coverage data.
    """
    def coverage(r: dict) -> int:
        return sum(bool(r.get(c)) for c in ("google_travel_url", "trip_url", "tripadvisor_url"))

    def review_count(r: dict) -> int:
        try:
            return int(master_by_id.get(r["hotel_id"], {}).get("google_review_count") or 0)
        except ValueError:
            return 0

    enabled = [r for r in targets if str(r.get("enabled")).strip().lower() == "true"]
    three_platform = [r for r in enabled if coverage(r) == 3]

    # Brand-collision risk: hotels whose normalized name shares a
    # non-generic first word with another enabled hotel's name (e.g. two
    # "Selectum ..." or two "La Blanche ..." sister properties) - a real,
    # data-driven signal rather than a guessed pair. Generic Turkish words
    # like "Bodrum"/"Otel"/"Hotel" are excluded since sharing them is not
    # a genuine brand-family collision.
    stopwords = {"bodrum", "hotel", "otel", "the", "grand", "club", "blue", "white"}
    first_word_counts = Counter(r["hotel_name"].split()[0].lower() for r in enabled if r["hotel_name"])
    collision_candidates = [
        r for r in three_platform
        if (w := r["hotel_name"].split()[0].lower()) not in stopwords and first_word_counts[w] > 1
    ]

    chosen: list[dict] = []
    used_areas: set[str] = set()

    def add(r: dict) -> None:
        if r and r["hotel_id"] not in {c["hotel_id"] for c in chosen}:
            chosen.append(r)
            used_areas.add(r["area"])

    if collision_candidates:
        add(collision_candidates[0])

    pool = sorted(three_platform, key=review_count, reverse=True)
    for r in pool:
        if len(chosen) >= 5:
            break
        if r["area"] not in used_areas:
            add(r)

    for r in pool:
        if len(chosen) >= 5:
            break
        add(r)

    if len(chosen) < 5:
        remaining = sorted((r for r in enabled if r not in chosen), key=review_count, reverse=True)
        for r in remaining:
            if len(chosen) >= 5:
                break
            add(r)

    return chosen[:5]


def evaluate_platform_result(row: dict, platform: str, result: dict) -> dict:
    hotel_id, hotel_name = row["hotel_id"], row["hotel_name"]
    url_valid = bool(result.get("source_url"))
    entity_valid = result.get("validation_status") == "VALID_ENTITY"
    out = {"hotel_id": hotel_id, "hotel_name": hotel_name, "platform": platform,
           "url_valid": url_valid, "entity_valid": entity_valid,
           "rows_scraped": 0, "unique_rows": 0, "empty_review_text": 0,
           "invalid_rating": 0, "duplicate_rows": 0,
           "status": result.get("status", ""), "error": result.get("error", "")}

    if platform == "policies_trip":
        out["rows_scraped"] = result.get("rows_added", 0)
        out["unique_rows"] = result.get("rows_added", 0)
        return out

    if not url_valid or not entity_valid:
        return out

    csv_path = per_hotel_csv_path(DATA_RAW_DIR / "reviews" / platform, hotel_id, hotel_name)
    quality = evaluate_raw_csv_quality(csv_path, platform=platform)
    out.update(quality)
    return out


def main() -> int:
    p = argparse.ArgumentParser(description="Run the 5-hotel multiplatform smoke test.")
    p.add_argument("--headless", action="store_true")
    p.add_argument("--max-reviews", type=int, default=10)
    args = p.parse_args()

    master_by_id = {r["hotel_id"]: r for r in read_csv_dicts(master_hotel_csv_path())}
    targets = load_targets()
    smoke_hotels = select_smoke_hotels(targets, master_by_id)

    if len(smoke_hotels) < 5:
        print(f"Uyari: yalnizca {len(smoke_hotels)} uygun (enabled=TRUE) otel bulundu; "
              "5 otel kriteri config/multiplatform_hotel_targets.csv icindeki gercek "
              "coverage ile sinirlidir.")

    print("Secilen smoke test otelleri:")
    for r in smoke_hotels:
        print(f"  {r['hotel_id']} | {r['hotel_name']} | {r['area']} | "
              f"coverage={r['platform_coverage_count']}")

    rows_out: list[dict] = []
    for row in smoke_hotels:
        for platform in ALL_PLATFORMS:
            if not row.get({"google_travel": "google_travel_url", "trip": "trip_url",
                             "tripadvisor": "tripadvisor_url"}[platform]):
                continue
            print(f"\n[smoke] {row['hotel_id']} {row['hotel_name']} / {platform}")
            result = run_review_platform(row, platform, max_reviews=args.max_reviews, headless=args.headless)
            print(f"  -> status={result['status']} rows_added={result.get('rows_added')} "
                  f"detected_name={result.get('detected_hotel_name')!r}")
            rows_out.append(evaluate_platform_result(row, platform, result))
        if row.get("policy_trip_url"):
            print(f"\n[smoke] {row['hotel_id']} {row['hotel_name']} / policies_trip")
            result = run_policies(row, headless=args.headless)
            print(f"  -> status={result['status']} rows_added={result.get('rows_added')}")
            rows_out.append(evaluate_platform_result(row, "policies_trip", result))

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = REPORTS_DIR / "multiplatform_smoke_test.csv"
    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=FIELDNAMES)
        w.writeheader()
        for r in rows_out:
            w.writerow(r)

    wrong_entity = sum(1 for r in rows_out if r["status"] == "WRONG_ENTITY")
    passed = sum(1 for r in rows_out if r["status"] in ("COMPLETED", "PARTIAL")
                 and r["duplicate_rows"] == 0 and r["entity_valid"])
    print(f"\n=== SMOKE TEST SUMMARY ===")
    print(f"Toplam kontrol: {len(rows_out)}, basarili (COMPLETED/PARTIAL, no dup, valid entity): {passed}")
    print(f"WRONG_ENTITY sayisi: {wrong_entity}")
    print(f"Rapor: {out_path}")
    full_batch_ready = wrong_entity == 0 and len(rows_out) > 0 and passed >= max(1, len(rows_out) // 2)
    print(f"FULL_BATCH_READY = {'YES' if full_batch_ready else 'NO'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
