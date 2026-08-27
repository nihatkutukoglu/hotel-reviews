"""Phase B (audit + cleaning) - builds:
    data/processed/google_travel_all_hotels_reviews_clean.csv
    reports/google_travel_all_hotels_input_inventory.csv
    reports/google_travel_all_hotels_duplicate_audit.csv
    reports/google_travel_all_hotels_audit_summary.txt

Source of truth: data/raw/reviews/google_travel/*.csv (never modified).
Removal policy (section B18): only exact duplicates and empty review text
are dropped from the CLEAN file - short reviews / unknown source / missing
details are kept.

Usage:
    python scripts/analysis/build_google_travel_clean_dataset.py
"""
from __future__ import annotations

import _pathsetup  # noqa: F401

import csv
import hashlib
import glob
import re
from collections import Counter, defaultdict
from pathlib import Path

from bodrum_intelligence.reviews.common import CONFIG_DIR, DATA_PROCESSED_DIR, DATA_RAW_DIR, REPORTS_DIR, read_csv_dicts
from bodrum_intelligence.analysis.google_travel_cleaning import (
    clean_review_text, is_edited, parse_detail_scores, parse_rating, parse_review_age_days,
    parse_review_source, rating_group,
)

RAW_DIR = DATA_RAW_DIR / "reviews" / "google_travel"
CLEAN_FIELDS = [
    "hotel_id", "hotel_name", "area", "review_text", "review_text_clean", "review_details_raw",
    "review_date_raw", "review_date_is_approximate", "review_age_days_approx", "is_edited",
    "review_rating_raw", "review_rating_numeric", "rating_group", "review_source",
    "rooms_score", "service_score", "location_score", "review_word_count", "review_char_count",
    "language_detected", "review_hash", "source_url", "collected_at", "quality_flags",
]

_TR_CHARS = set("ığşöçüİĞŞÖÇÜ")
_EN_STOPWORDS = {"the", "and", "was", "very", "with", "our", "for", "room", "staff", "great", "good"}


def detect_language(text: str) -> str:
    if not text:
        return "UNKNOWN"
    if any(ch in _TR_CHARS for ch in text):
        return "tr"
    words = set(re.findall(r"[a-zA-Z']+", text.lower()))
    if len(words & _EN_STOPWORDS) >= 2:
        return "en"
    return "UNKNOWN"


def load_hotel_meta() -> dict:
    targets = read_csv_dicts(CONFIG_DIR / "multiplatform_hotel_targets.csv")
    return {r["hotel_id"]: r for r in targets}


def load_collected_at() -> dict:
    status_path = REPORTS_DIR / "multiplatform_scrape_status.csv"
    out = {}
    if status_path.exists():
        for r in read_csv_dicts(status_path):
            if r["platform"] != "google_travel":
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
    empty_text_count = 0
    total_raw_rows = 0

    for path in raw_files:
        fname = Path(path).name
        hotel_id = fname.split("_", 1)[0]
        meta = hotel_meta.get(hotel_id, {})
        hotel_name = meta.get("hotel_name", fname.split("_", 1)[1].rsplit(".csv", 1)[0] if "_" in fname else hotel_id)
        area = meta.get("area", "")
        source_url = meta.get("google_travel_url", "")
        collected_at = collected_at_by_hotel.get(hotel_id, "")

        rows = read_csv_dicts(Path(path))
        total_raw_rows += len(rows)
        inventory_rows.append({
            "file_name": fname, "hotel_id": hotel_id, "hotel_name": hotel_name,
            "row_count": len(rows), "column_count": len(rows[0]) if rows else 0,
            "file_size_bytes": Path(path).stat().st_size,
            "schema_signature": ",".join(rows[0].keys()) if rows else "",
        })

        for r in rows:
            raw_text = r.get("yorum", "") or ""
            text_clean = clean_review_text(raw_text)
            if not text_clean.strip():
                empty_text_count += 1
            details = parse_detail_scores(r.get("hizmet", ""))
            source_canonical, _label = parse_review_source(r.get("tarih", ""))
            age_days, _phrase = parse_review_age_days(r.get("tarih", ""))
            rating_numeric, invalid_rating = parse_rating(r.get("puan", ""))
            rg = rating_group(rating_numeric)

            h = hashlib.sha256(
                "\x1f".join([hotel_id, text_clean, r.get("tarih", ""), r.get("puan", "")]).encode("utf-8")
            ).hexdigest()
            seen_hashes[h].append(hotel_id)

            flags = []
            if not text_clean.strip():
                flags.append("EMPTY_TEXT")
            if invalid_rating:
                flags.append("INVALID_RATING")
            if text_clean and len(text_clean.split()) < 4:
                flags.append("VERY_SHORT")
            if is_edited(r.get("tarih", "")):
                flags.append("EDITED")

            clean_rows.append({
                "hotel_id": hotel_id, "hotel_name": hotel_name, "area": area,
                "review_text": raw_text, "review_text_clean": text_clean,
                "review_details_raw": r.get("hizmet", ""), "review_date_raw": r.get("tarih", ""),
                "review_date_is_approximate": True, "review_age_days_approx": age_days,
                "is_edited": is_edited(r.get("tarih", "")),
                "review_rating_raw": r.get("puan", ""), "review_rating_numeric": rating_numeric,
                "rating_group": rg, "review_source": source_canonical,
                "rooms_score": details.rooms_score, "service_score": details.service_score,
                "location_score": details.location_score,
                "review_word_count": len(text_clean.split()) if text_clean else 0,
                "review_char_count": len(text_clean),
                "language_detected": detect_language(text_clean),
                "review_hash": h, "source_url": source_url, "collected_at": collected_at,
                "quality_flags": ";".join(flags),
            })

    # section B18: drop exact duplicates (keep first) and fully-empty-text rows
    dedup_seen = set()
    final_rows = []
    duplicates_dropped = 0
    for row in clean_rows:
        h = row["review_hash"]
        if h in dedup_seen:
            duplicates_dropped += 1
            continue
        dedup_seen.add(h)
        if not row["review_text_clean"].strip():
            continue
        final_rows.append(row)

    DATA_PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    clean_path = DATA_PROCESSED_DIR / "google_travel_all_hotels_reviews_clean.csv"
    with open(clean_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=CLEAN_FIELDS)
        w.writeheader()
        for row in final_rows:
            w.writerow(row)
    print(f"Wrote {clean_path} ({len(final_rows)} clean rows from {total_raw_rows} raw rows)")

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    inv_path = REPORTS_DIR / "google_travel_all_hotels_input_inventory.csv"
    with open(inv_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(inventory_rows[0].keys()) if inventory_rows else [])
        w.writeheader()
        for r in inventory_rows:
            w.writerow(r)
    print(f"Wrote {inv_path}")

    dup_path = REPORTS_DIR / "google_travel_all_hotels_duplicate_audit.csv"
    cross_hotel_dups = [(h, ids) for h, ids in seen_hashes.items() if len(ids) > 1]
    with open(dup_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["review_hash", "occurrence_count", "hotel_ids"])
        for h, ids in cross_hotel_dups:
            w.writerow([h, len(ids), ";".join(sorted(set(ids)))])
    print(f"Wrote {dup_path} ({len(cross_hotel_dups)} hash groups with >1 occurrence)")

    source_dist = Counter(r["review_source"] for r in final_rows)
    rating_dist = Counter(r["rating_group"] for r in final_rows)
    unique_hotels = len({r["hotel_id"] for r in final_rows})
    summary = [
        "GOOGLE TRAVEL ALL-HOTELS AUDIT SUMMARY", "=" * 45,
        f"raw_total_rows: {total_raw_rows}",
        f"clean_total_rows: {len(final_rows)}",
        f"hotel_count: {unique_hotels}",
        f"duplicates_dropped: {duplicates_dropped}",
        f"empty_text_dropped: {empty_text_count}",
        f"source_distribution: {dict(source_dist)}",
        f"rating_group_distribution: {dict(rating_dist)}",
        "",
        "NOTE: 'tarih' is a relative-time string, not an exact date (e.g. "
        "'Google uzerinde 3 hafta once') - it ALSO reveals that Google "
        "Travel's review panel aggregates reviews originally posted on "
        "Google, TripAdvisor, and even Trip.com. review_source reflects "
        "this; review_age_days_approx is a rough estimate, not a real date.",
    ]
    summary_path = REPORTS_DIR / "google_travel_all_hotels_audit_summary.txt"
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write("\n".join(summary) + "\n")
    print(f"Wrote {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
