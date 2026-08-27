"""Phase 3, section 25/61-B: runs discovery for every master hotel that does
NOT already have a verified_direct URL on a given platform (already-verified
hotels are carried over as-is in build_verified_targets.py - re-discovering
a URL we already trust from live phase-1/2 scraping would just add risk for
no benefit).

Sequential, one browser per platform, no parallel browsers (section 26/38).
Writes/updates data/interim/discovery/<platform>_candidates.csv - resumable:
hotels already present in that file are skipped on a re-run.

Usage:
    python scripts/multiplatform/discovery/run_all_hotel_discovery.py --platform google_travel
    python scripts/multiplatform/discovery/run_all_hotel_discovery.py --platform trip
    python scripts/multiplatform/discovery/run_all_hotel_discovery.py --platform trip --limit 20
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import _pathsetup  # noqa: F401, E402

from bodrum_intelligence.reviews.common import REPO_ROOT, PLATFORM_LINK_FILES, master_hotel_csv_path, read_csv_dicts
from bodrum_intelligence.discovery.common import make_driver
from bodrum_intelligence.discovery import google_travel_discovery, trip_discovery

CANDIDATE_DIR = REPO_ROOT / "data" / "interim" / "discovery"
CANDIDATE_FIELDS = [
    "hotel_id", "hotel_name", "area", "platform", "candidate_rank", "candidate_url",
    "candidate_detected_name", "candidate_location", "name_similarity", "area_match",
    "address_match", "brand_collision_flag", "candidate_score", "validation_status",
    "validation_note", "discovered_at",
]
MODULES = {"google_travel": google_travel_discovery, "trip": trip_discovery}


def already_verified_ids(platform: str) -> set[str]:
    path = PLATFORM_LINK_FILES[platform]
    rows = read_csv_dicts(path)
    return {r["hotel_id"] for r in rows if r["status"] == "verified_direct"}


def already_discovered_ids(candidate_path: Path) -> set[str]:
    if not candidate_path.exists():
        return set()
    return {r["hotel_id"] for r in read_csv_dicts(candidate_path)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--platform", required=True, choices=list(MODULES))
    ap.add_argument("--limit", type=int, default=0, help="0 = no limit (all remaining)")
    ap.add_argument("--headless", action="store_true")
    args = ap.parse_args()

    module = MODULES[args.platform]
    master = read_csv_dicts(master_hotel_csv_path())
    verified = already_verified_ids(args.platform)
    candidate_path = CANDIDATE_DIR / f"{args.platform}_candidates.csv"
    done = already_discovered_ids(candidate_path)

    todo = [r for r in master if r["hotel_id"] not in verified and r["hotel_id"] not in done]
    if args.limit:
        todo = todo[: args.limit]

    print(f"platform={args.platform} total_master={len(master)} already_verified={len(verified)} "
          f"already_discovered_this_run={len(done)} to_discover_now={len(todo)}")
    if not todo:
        print("Nothing to do.")
        return 0

    CANDIDATE_DIR.mkdir(parents=True, exist_ok=True)
    file_exists = candidate_path.exists()
    driver = make_driver(headless=args.headless)
    written = 0
    try:
        with open(candidate_path, "a", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=CANDIDATE_FIELDS)
            if not file_exists:
                w.writeheader()
            for i, h in enumerate(todo, 1):
                print(f"[{args.platform}] {i}/{len(todo)} {h['hotel_id']} {h['hotel_name']}")
                r = module.discover(driver, h["hotel_id"], h["hotel_name"], h["area"])
                print(f"  -> {r['validation_status']} score={r['candidate_score']}")
                w.writerow({k: r.get(k, "") for k in CANDIDATE_FIELDS})
                f.flush()
                written += 1
    finally:
        driver.quit()
    print(f"Wrote {written} new rows to {candidate_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
