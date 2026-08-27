"""Builds config/multiplatform_hotel_targets.csv by merging the master
hotel dataset with the three platform direct-link CSVs (section 15).

`enabled=TRUE` only for hotels with at least one verified_direct platform
link AND no unresolved name/area conflict AND a link record on all three
platforms (i.e. never for a MISSING_LINK_RECORD hotel like BOD192, and
never for a name/area conflict like BOD135/BOD155/BOD175 until reviewed).

Usage:
    python scripts/multiplatform/build_platform_config.py
"""
from __future__ import annotations

import _pathsetup  # noqa: F401

import csv

from bodrum_intelligence.reviews.common import (
    CONFIG_DIR,
    PLATFORM_LINK_FILES,
    master_hotel_csv_path,
    read_csv_dicts,
)
from bodrum_intelligence.reviews.validation import is_verified, name_match_status, normalize_name


def main() -> int:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    master_rows = read_csv_dicts(master_hotel_csv_path())
    master_by_id = {r["hotel_id"]: r for r in master_rows}
    link_data = {p: {r["hotel_id"]: r for r in read_csv_dicts(path)}
                 for p, path in PLATFORM_LINK_FILES.items()}

    out_path = CONFIG_DIR / "multiplatform_hotel_targets.csv"
    fieldnames = ["hotel_id", "hotel_name", "area", "google_travel_url", "google_travel_status",
                  "trip_url", "trip_status", "tripadvisor_url", "tripadvisor_status",
                  "policy_trip_url", "platform_coverage_count", "manual_review_required", "enabled"]

    enabled_count = 0
    review_count = 0
    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for hid, m in sorted(master_by_id.items()):
            rows = {p: link_data[p].get(hid) for p in PLATFORM_LINK_FILES}
            verified = {p: bool(r and is_verified(r.get("status"))) for p, r in rows.items()}
            cov = sum(verified.values())
            missing_link_record = any(r is None for r in rows.values())

            conflict = False
            for p, r in rows.items():
                if r is None:
                    continue
                nm = name_match_status(m["hotel_name"], r.get("hotel_name", ""))
                area_mismatch = normalize_name(m["area"]) != normalize_name(r.get("area", ""))
                if nm in ("CONFLICT", "REVIEW_REQUIRED") or area_mismatch:
                    conflict = True

            manual_review = (cov == 0) or conflict or missing_link_record
            enabled = (cov >= 1) and not manual_review
            enabled_count += int(enabled)
            review_count += int(manual_review)

            def url_or_blank(p: str) -> str:
                r = rows[p]
                return r.get("direct_url", "") if (r and verified[p]) else ""

            w.writerow({
                "hotel_id": hid, "hotel_name": m["hotel_name"], "area": m["area"],
                "google_travel_url": url_or_blank("google_travel"),
                "google_travel_status": (rows["google_travel"].get("status", "") if rows["google_travel"] else "MISSING"),
                "trip_url": url_or_blank("trip"),
                "trip_status": (rows["trip"].get("status", "") if rows["trip"] else "MISSING"),
                "tripadvisor_url": url_or_blank("tripadvisor"),
                "tripadvisor_status": (rows["tripadvisor"].get("status", "") if rows["tripadvisor"] else "MISSING"),
                "policy_trip_url": url_or_blank("trip"),
                "platform_coverage_count": cov,
                "manual_review_required": manual_review,
                "enabled": enabled,
            })

    print(f"Wrote {out_path} ({len(master_by_id)} hotels): "
          f"enabled={enabled_count}, manual_review_required={review_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
