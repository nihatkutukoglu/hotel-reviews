"""Section 27-30: the full/sequential batch runner. Always processes one
hotel x platform at a time (never more than one Selenium driver open at
once - section 28). Defaults are conservative: resume=True, force=False,
headless=False, no review-count limit removed (still capped by
--max-reviews, default 10) unless explicitly raised.

Usage:
    python scripts/multiplatform/run_batch.py --dry-run
    python scripts/multiplatform/run_batch.py --platform tripadvisor --area Akyarlar --max-hotels 5 --max-reviews 20
    python scripts/multiplatform/run_batch.py --validate-only --max-hotels 10
"""
from __future__ import annotations

import _pathsetup  # noqa: F401

import argparse
import csv

from bodrum_intelligence.reviews.common import REPORTS_DIR
from bodrum_intelligence.reviews.runner import ALL_PLATFORMS, filter_targets, load_targets, run_policies, run_review_platform

STATUS_FIELDNAMES = ["hotel_id", "hotel_name", "area", "platform", "source_url", "detected_name",
                      "status", "rows_added", "started_at", "finished_at", "last_error"]


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Sequential multiplatform batch scraper.")
    p.add_argument("--platform", choices=list(ALL_PLATFORMS) + ["policies", "all"], default="all")
    p.add_argument("--hotel-id", action="append", default=None)
    p.add_argument("--area", action="append", default=None)
    p.add_argument("--max-hotels", type=int, default=None)
    p.add_argument("--max-reviews", type=int, default=10)
    p.add_argument("--headless", action="store_true")
    p.add_argument("--resume", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--force", action="store_true", help="Only affects policies (single-row files); "
                   "review platforms always append-only via their own dedupe, so --force is a no-op there.")
    p.add_argument("--validate-only", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    rows = filter_targets(load_targets(), hotel_ids=args.hotel_id, areas=args.area,
                           only_enabled=True, max_hotels=args.max_hotels)
    if not rows:
        print("Uyari: filtreye uyan enabled=TRUE hotel bulunamadi.")
        return 1

    platforms = list(ALL_PLATFORMS) if args.platform == "all" else \
        ([] if args.platform == "policies" else [args.platform])
    include_policies = args.platform in ("all", "policies")

    plan = []
    for row in rows:
        for platform in platforms:
            url_col = {"google_travel": "google_travel_url", "trip": "trip_url",
                       "tripadvisor": "tripadvisor_url"}[platform]
            if row.get(url_col):
                plan.append((row, platform))
        if include_policies and row.get("policy_trip_url"):
            plan.append((row, "policies_trip"))

    print(f"Plan: {len(rows)} otel, {len(plan)} hotel x platform is birimi "
          f"({'validate-only' if args.validate_only else 'scrape'}, sequential).")

    if args.dry_run:
        for row, platform in plan:
            url = row.get({"google_travel": "google_travel_url", "trip": "trip_url",
                            "tripadvisor": "tripadvisor_url", "policies_trip": "policy_trip_url"}[platform], "")
            print(f"  [dry-run] {row['hotel_id']} | {row['hotel_name']} | {platform} | {url}")
        print("\nDry-run: hicbir tarayici acilmadi, hicbir istek yapilmadi.")
        return 0

    results = []
    for row, platform in plan:
        print(f"\n[batch] {row['hotel_id']} {row['hotel_name']} / {platform}")
        if platform == "policies_trip":
            r = run_policies(row, headless=args.headless, resume=args.resume, force=args.force,
                              validate_only=args.validate_only)
        else:
            r = run_review_platform(row, platform, max_reviews=args.max_reviews,
                                     headless=args.headless, validate_only=args.validate_only)
        print(f"  -> status={r['status']} rows_added={r.get('rows_added')} "
              f"detected_name={r.get('detected_hotel_name')!r}")
        results.append(r)

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = REPORTS_DIR / "multiplatform_scrape_status.csv"
    file_exists = out_path.exists()
    with open(out_path, "a", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=STATUS_FIELDNAMES)
        if not file_exists:
            w.writeheader()
        for r in results:
            w.writerow({
                "hotel_id": r["hotel_id"], "hotel_name": r["hotel_name_expected"], "area": r["area"],
                "platform": r["platform"], "source_url": r["source_url"],
                "detected_name": r["detected_hotel_name"], "status": r["status"],
                "rows_added": r.get("rows_added", 0), "started_at": r.get("checked_at", ""),
                "finished_at": r.get("checked_at", ""), "last_error": r.get("error", ""),
            })

    wrong_entity = sum(1 for r in results if r["status"] == "WRONG_ENTITY")
    print(f"\n=== BATCH SUMMARY ===")
    print(f"Tamamlanan birim: {len(results)}, WRONG_ENTITY: {wrong_entity}")
    print(f"Durum raporu (append): {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(None))
