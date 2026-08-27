"""Phase C (Trip.com audit + cleaning) - builds:
    data/processed/tripcom_reviews_clean.csv
    reports/tripcom_input_inventory.csv
    reports/tripcom_duplicate_audit.csv
    reports/tripcom_audit_summary.txt

Source of truth: data/raw/reviews/trip/*.csv (never modified).
Removal policy: only exact duplicates and empty review text are dropped
from the CLEAN file - everything else (short reviews, missing traveler
type/room type/location, suspected UI-leakage rows) is KEPT but flagged
in quality_flags, per the same "missing field != row removal" principle
used for the Google Travel and Policies cleaning.

Usage:
    python scripts/analysis/build_tripcom_clean_dataset.py
"""
from __future__ import annotations

import _pathsetup  # noqa: F401

import csv
import hashlib
import glob
from collections import Counter, defaultdict
from pathlib import Path

from bodrum_intelligence.reviews.common import CONFIG_DIR, DATA_PROCESSED_DIR, DATA_RAW_DIR, REPORTS_DIR, read_csv_dicts
from bodrum_intelligence.analysis.tripcom_cleaning import (
    canonical_customer_tier, canonical_room_type, canonical_traveler_type, clean_review_text,
    is_review_text_ui_leakage, parse_review_date, parse_reviewer_location, parse_reviewer_review_count,
    parse_stay_date, parse_trip_rating, rating_5_scale, rating_group_5,
)

RAW_DIR = DATA_RAW_DIR / "reviews" / "trip"
CLEAN_FIELDS = [
    "review_id", "hotel_id", "hotel_name", "area", "source_platform", "review_text", "review_text_clean",
    "source_rating", "source_rating_max", "rating_5_scale", "rating_group", "review_date", "review_date_raw",
    "stay_year", "stay_month", "stay_date_raw", "traveler_type", "traveler_type_raw", "room_type",
    "room_type_raw", "reviewer_location", "reviewer_country", "customer_tier", "customer_tier_raw",
    "reviewer_review_count", "review_hash", "source_url", "collected_at", "quality_flags",
]


def load_hotel_meta() -> dict:
    return {r["hotel_id"]: r for r in read_csv_dicts(CONFIG_DIR / "multiplatform_hotel_targets.csv")}


def load_collected_at() -> dict:
    status_path = REPORTS_DIR / "multiplatform_scrape_status.csv"
    out = {}
    if status_path.exists():
        for r in read_csv_dicts(status_path):
            if r["platform"] != "trip":
                continue
            out[r["hotel_id"]] = max(out.get(r["hotel_id"], ""), r.get("finished_at", ""))
    return out


def main() -> int:
    hotel_meta = load_hotel_meta()
    collected_at_by_hotel = load_collected_at()
    raw_files = sorted(glob.glob(str(RAW_DIR / "*.csv")))

    inventory_rows = []
    clean_rows = []
    seen_hashes: dict[str, list[str]] = defaultdict(list)
    total_raw_rows = 0
    review_id = 0

    for path in raw_files:
        fname = Path(path).name
        hotel_id = fname.split("_", 1)[0]
        meta = hotel_meta.get(hotel_id, {})
        hotel_name = meta.get("hotel_name", fname)
        area = meta.get("area", "")
        source_url = meta.get("trip_url", "")
        collected_at = collected_at_by_hotel.get(hotel_id, "")

        rows = read_csv_dicts(Path(path))
        total_raw_rows += len(rows)
        inventory_rows.append({
            "file_name": fname, "hotel_id": hotel_id, "hotel_name": hotel_name,
            "row_count": len(rows), "column_count": len(rows[0]) if rows else 0,
            "schema_signature": ",".join(rows[0].keys()) if rows else "",
        })

        for r in rows:
            review_id += 1
            raw_text = r.get("yorum", "") or ""
            text_clean = clean_review_text(raw_text)
            rating, rating_max, invalid_rating = parse_trip_rating(r.get("puan", ""))
            r5 = rating_5_scale(rating, rating_max)
            rg = rating_group_5(r5)
            review_date = parse_review_date(r.get("yorum_tarihi", ""))
            stay_year, stay_month, _prec = parse_stay_date(r.get("konaklama_tarihi", ""))
            traveler_raw = r.get("seyahat_tipi", "")
            room_raw = r.get("oda_tipi", "")
            tier_raw = r.get("musteri_kademe", "")
            loc_raw, country, loc_leak = parse_reviewer_location(r.get("konum", ""))
            reviewer_count = parse_reviewer_review_count(r.get("musteri_toplam_yorum_sayisi", ""))

            h = hashlib.sha256(
                "\x1f".join([hotel_id, text_clean, r.get("yorum_tarihi", ""), r.get("puan", "")]).encode("utf-8")
            ).hexdigest()
            seen_hashes[h].append(hotel_id)

            flags = []
            if not text_clean.strip():
                flags.append("EMPTY_TEXT")
            if invalid_rating:
                flags.append("INVALID_RATING")
            if text_clean and len(text_clean.split()) < 4:
                flags.append("VERY_SHORT")
            if loc_leak:
                flags.append("UI_LEAKAGE_LOCATION")
            if is_review_text_ui_leakage(text_clean):
                flags.append("UI_LEAKAGE_REVIEW_TEXT")

            clean_rows.append({
                "review_id": review_id, "hotel_id": hotel_id, "hotel_name": hotel_name, "area": area,
                "source_platform": "trip", "review_text": raw_text, "review_text_clean": text_clean,
                "source_rating": rating, "source_rating_max": rating_max, "rating_5_scale": r5,
                "rating_group": rg, "review_date": review_date, "review_date_raw": r.get("yorum_tarihi", ""),
                "stay_year": stay_year, "stay_month": stay_month, "stay_date_raw": r.get("konaklama_tarihi", ""),
                "traveler_type": canonical_traveler_type(traveler_raw), "traveler_type_raw": traveler_raw,
                "room_type": canonical_room_type(room_raw), "room_type_raw": room_raw,
                "reviewer_location": loc_raw, "reviewer_country": country,
                "customer_tier": canonical_customer_tier(tier_raw), "customer_tier_raw": tier_raw,
                "reviewer_review_count": reviewer_count,
                "review_hash": h, "source_url": source_url, "collected_at": collected_at,
                "quality_flags": ";".join(flags),
            })

    dedup_seen = set()
    final_rows = []
    duplicates_dropped = 0
    empty_text_dropped = 0
    for row in clean_rows:
        h = row["review_hash"]
        if h in dedup_seen:
            duplicates_dropped += 1
            continue
        dedup_seen.add(h)
        if not row["review_text_clean"].strip():
            empty_text_dropped += 1
            continue
        final_rows.append(row)

    DATA_PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    clean_path = DATA_PROCESSED_DIR / "tripcom_reviews_clean.csv"
    with open(clean_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=CLEAN_FIELDS)
        w.writeheader()
        for row in final_rows:
            w.writerow(row)
    print(f"Wrote {clean_path} ({len(final_rows)} clean rows from {total_raw_rows} raw rows)")

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    inv_path = REPORTS_DIR / "tripcom_input_inventory.csv"
    with open(inv_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(inventory_rows[0].keys()) if inventory_rows else [])
        w.writeheader()
        for r in inventory_rows:
            w.writerow(r)
    print(f"Wrote {inv_path}")

    dup_path = REPORTS_DIR / "tripcom_duplicate_audit.csv"
    cross_hotel_dups = [(h, ids) for h, ids in seen_hashes.items() if len(ids) > 1]
    with open(dup_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["review_hash", "occurrence_count", "hotel_ids"])
        for h, ids in cross_hotel_dups:
            w.writerow([h, len(ids), ";".join(sorted(set(ids)))])
    print(f"Wrote {dup_path} ({len(cross_hotel_dups)} hash groups with >1 occurrence)")

    traveler_dist = Counter(r["traveler_type"] for r in final_rows)
    room_dist = Counter(r["room_type"] for r in final_rows)
    rating_dist = Counter(r["rating_group"] for r in final_rows)
    ui_leak = sum(1 for r in final_rows if "UI_LEAKAGE" in r["quality_flags"])
    summary = [
        "TRIP.COM AUDIT SUMMARY", "=" * 30,
        f"raw_total_rows: {total_raw_rows}",
        f"clean_total_rows: {len(final_rows)}",
        f"hotel_count: {len({r['hotel_id'] for r in final_rows})}",
        f"duplicates_dropped: {duplicates_dropped}",
        f"empty_text_dropped: {empty_text_dropped}",
        f"suspected_ui_leakage_rows_flagged_not_dropped: {ui_leak}",
        f"traveler_type_distribution: {dict(traveler_dist)}",
        f"room_type_distribution: {dict(room_dist)}",
        f"rating_group_distribution (5-scale, LOW<3.0 MID 3.0-3.99 HIGH>=4.0): {dict(rating_dist)}",
    ]
    with open(REPORTS_DIR / "tripcom_audit_summary.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(summary) + "\n")
    print(f"Wrote {REPORTS_DIR / 'tripcom_audit_summary.txt'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
