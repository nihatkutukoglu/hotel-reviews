"""Phase B6-B8 (Policies feature engineering + reports): builds the
authoritative data/processed/hotel_policies_features.csv (primary key
hotel_id) plus:
    reports/tripcom_policies_coverage.csv
    reports/tripcom_policies_quality.csv
    reports/tripcom_amenity_frequency.csv
    reports/tripcom_policies_summary.txt

Amenity flags are derived ONLY from real evidence in the raw `hizmetler`
text (B6) - never guessed. A missing policy field is not a hotel
failure (B3/section "Policies missing field = hotel failure değildir").

Usage:
    python scripts/analysis/build_policies_features_and_reports.py
"""
from __future__ import annotations

import _pathsetup  # noqa: F401

import csv
import glob
from pathlib import Path

from bodrum_intelligence.reviews.common import CONFIG_DIR, DATA_PROCESSED_DIR, DATA_RAW_DIR, REPORTS_DIR, read_csv_dicts
from bodrum_intelligence.analysis.policies_cleaning import AMENITY_KEYWORDS, detect_amenities

POLICIES_DIR = DATA_RAW_DIR / "hotel_policies" / "trip"

FAMILY_FLAGS = ["has_children_policy", "has_kids_club", "has_kids_pool", "has_playground", "has_childcare"]
WELLNESS_FLAGS = ["has_spa", "has_sauna", "has_gym"]
WATER_FLAGS = ["has_private_beach", "has_diving", "has_snorkeling", "has_outdoor_pool", "has_indoor_pool"]

COVERAGE_FLAGS = ["has_checkin", "has_checkout", "has_children_policy", "has_extra_bed_policy",
                  "has_breakfast_policy", "has_pet_policy", "has_service_animal_policy",
                  "has_age_rule", "has_license", "has_facilities"]

FEATURE_FIELDS = (
    ["hotel_id", "hotel_name", "area", "policy_status"] + COVERAGE_FLAGS +
    list(AMENITY_KEYWORDS.keys()) +
    ["amenity_count", "family_feature_count", "wellness_feature_count", "water_feature_count"]
)


def _truthy(v) -> bool:
    return str(v).strip().lower() in ("true", "1", "yes")


def main() -> int:
    hotel_meta = {r["hotel_id"]: r for r in read_csv_dicts(CONFIG_DIR / "multiplatform_hotel_targets.csv")}
    raw_files = sorted(glob.glob(str(POLICIES_DIR / "*.csv")))

    feature_rows = []
    quality_rows = []
    amenity_hits = {k: 0 for k in AMENITY_KEYWORDS}
    status_counts: dict[str, int] = {}

    for path in raw_files:
        rows = read_csv_dicts(Path(path))
        if not rows:
            continue
        p = rows[0]
        hotel_id = p.get("hotel_id", "")
        meta = hotel_meta.get(hotel_id, {})
        hotel_name = meta.get("hotel_name", p.get("hotel_name_expected", ""))
        area = meta.get("area", p.get("area", ""))
        policy_status = p.get("policy_status", "")
        status_counts[policy_status] = status_counts.get(policy_status, 0) + 1

        hizmetler = p.get("hizmetler", "") or ""
        out_row = {"hotel_id": hotel_id, "hotel_name": hotel_name, "area": area, "policy_status": policy_status}
        for flag in COVERAGE_FLAGS:
            out_row[flag] = _truthy(p.get(flag, "False"))

        amenities = detect_amenities(hizmetler)
        out_row.update(amenities)
        amenity_count = sum(1 for hit in amenities.values() if hit)
        for flag, hit in amenities.items():
            if hit:
                amenity_hits[flag] += 1
        out_row["amenity_count"] = amenity_count
        out_row["family_feature_count"] = sum(1 for f in FAMILY_FLAGS if out_row.get(f))
        out_row["wellness_feature_count"] = sum(1 for f in WELLNESS_FLAGS if out_row.get(f))
        out_row["water_feature_count"] = sum(1 for f in WATER_FLAGS if out_row.get(f))
        feature_rows.append(out_row)

        quality_rows.append({
            "hotel_id": hotel_id, "policy_status": policy_status,
            "fields_present": sum(1 for f in COVERAGE_FLAGS if out_row.get(f)),
            "fields_total": len(COVERAGE_FLAGS),
        })

    DATA_PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    out_path = DATA_PROCESSED_DIR / "hotel_policies_features.csv"
    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=FEATURE_FIELDS)
        w.writeheader()
        for r in feature_rows:
            w.writerow(r)
    print(f"Wrote {out_path} ({len(feature_rows)} hotels)")

    # primary key uniqueness assertion (global validation requirement)
    ids = [r["hotel_id"] for r in feature_rows]
    assert len(ids) == len(set(ids)), "hotel_policies_features.csv primary key (hotel_id) is not unique!"

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    cov_path = REPORTS_DIR / "tripcom_policies_coverage.csv"
    with open(cov_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["policy_status", "hotel_count"])
        for status, cnt in status_counts.items():
            w.writerow([status, cnt])
        w.writerow(["TOTAL_HOTELS_WITH_POLICY_DATA", len(feature_rows)])
    print(f"Wrote {cov_path}")

    qual_path = REPORTS_DIR / "tripcom_policies_quality.csv"
    with open(qual_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["hotel_id", "policy_status", "fields_present", "fields_total"])
        w.writeheader()
        for r in quality_rows:
            w.writerow(r)
    print(f"Wrote {qual_path}")

    amenity_path = REPORTS_DIR / "tripcom_amenity_frequency.csv"
    with open(amenity_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["amenity", "hotel_count", "share_pct"])
        n = len(feature_rows) or 1
        for amenity, cnt in sorted(amenity_hits.items(), key=lambda x: -x[1]):
            w.writerow([amenity, cnt, round(cnt / n * 100, 1)])
    print(f"Wrote {amenity_path}")

    summary = [
        "TRIP.COM POLICIES SUMMARY", "=" * 30,
        f"hotels_with_policy_data: {len(feature_rows)}",
        f"policy_status_distribution: {status_counts}",
        f"top_amenities: {sorted(amenity_hits.items(), key=lambda x: -x[1])[:10]}",
        "NOTE: a missing policy field reflects the source page, not a scraper failure "
        "(checkout time in particular is not rendered by Trip.com for many hotels).",
    ]
    with open(REPORTS_DIR / "tripcom_policies_summary.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(summary) + "\n")
    print(f"Wrote {REPORTS_DIR / 'tripcom_policies_summary.txt'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
