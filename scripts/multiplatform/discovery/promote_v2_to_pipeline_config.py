"""Turns config/multiplatform_hotel_targets_v2.csv (built by
build_verified_targets.py from v1-verified + phase-3 discovery) into the
schema scripts/multiplatform/run_batch.py's runner.py actually reads
(config/multiplatform_hotel_targets.csv).

Why a separate promotion step instead of writing runner.py's file directly
from build_verified_targets.py: section 19 requires the raw discovery
outputs (v2 link files, v1/v2 diff) to be inspectable on their own before
anything is wired into the live scraping pipeline. This script is the
explicit "I've looked at v2, wire it in" step.

TripAdvisor is out of scope for phase 3 (section 64) - its columns are
carried over unchanged from whatever is already in the existing
multiplatform_hotel_targets.csv (so previously-enabled TripAdvisor targets
are not silently disabled), never touched by discovery.

Usage:
    python scripts/multiplatform/discovery/promote_v2_to_pipeline_config.py
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import _pathsetup  # noqa: F401, E402

from bodrum_intelligence.reviews.common import CONFIG_DIR, read_csv_dicts

V2_PATH = CONFIG_DIR / "multiplatform_hotel_targets_v2.csv"
OUT_PATH = CONFIG_DIR / "multiplatform_hotel_targets.csv"
FIELDNAMES = ["hotel_id", "hotel_name", "area", "google_travel_url", "google_travel_status",
              "trip_url", "trip_status", "tripadvisor_url", "tripadvisor_status",
              "policy_trip_url", "platform_coverage_count", "manual_review_required", "enabled"]


def main() -> int:
    if not V2_PATH.exists():
        print(f"{V2_PATH} not found - run build_verified_targets.py first.")
        return 1
    v2_rows = {r["hotel_id"]: r for r in read_csv_dicts(V2_PATH)}
    existing_ta = {}
    if OUT_PATH.exists():
        for r in read_csv_dicts(OUT_PATH):
            existing_ta[r["hotel_id"]] = (r.get("tripadvisor_url", ""), r.get("tripadvisor_status", "MISSING"))

    enabled_count = 0
    with open(OUT_PATH, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=FIELDNAMES)
        w.writeheader()
        for hid, r in sorted(v2_rows.items()):
            ta_url, ta_status = existing_ta.get(hid, ("", "MISSING"))
            g_ok = r["google_travel_status"] == "verified_direct"
            t_ok = r["trip_status"] == "verified_direct"
            ta_ok = ta_status == "verified_direct"
            # manual_review_required is informational only (surfaces that at
            # least one platform needs a human look) - it must NEVER disable
            # a DIFFERENT platform that is already independently verified.
            # (Bug found here: BOD072/BOD078 had trip_status=verified_direct
            # but were fully disabled because their unrelated google_travel
            # status happened to be review_required.)
            manual_review = r["manual_review_required"] in ("True", "true", True) or (not g_ok and not t_ok and not ta_ok)
            enabled = g_ok or t_ok or ta_ok
            enabled_count += int(enabled)
            w.writerow({
                "hotel_id": hid, "hotel_name": r["hotel_name"], "area": r["area"],
                "google_travel_url": r["google_travel_url"] if g_ok else "",
                "google_travel_status": r["google_travel_status"],
                "trip_url": r["trip_url"] if t_ok else "", "trip_status": r["trip_status"],
                "tripadvisor_url": ta_url, "tripadvisor_status": ta_status,
                "policy_trip_url": r["policy_trip_url"],
                "platform_coverage_count": r["platform_coverage_count"],
                "manual_review_required": manual_review, "enabled": enabled,
            })
    print(f"Wrote {OUT_PATH} ({len(v2_rows)} hotels): enabled={enabled_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
