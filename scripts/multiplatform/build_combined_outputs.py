"""Section 38-42: optional convenience outputs built ONLY from what has
actually been scraped so far (never fabricates rows). Reads the raw
per-hotel-per-platform CSVs, and produces:

  - data/processed/multiplatform_reviews_raw_normalized.csv  (section 38-40:
    one row per source review, metadata + rating_5_scale added; raw files
    themselves are untouched, sources are never merged into one row)
  - reports/multiplatform_cross_source_duplicate_candidates.csv (section 41:
    same-hotel candidate duplicates across platforms, flagged only, never
    auto-deleted)
  - data/processed/hotel_policies_features.csv (section 42: policy fields +
    binary amenity flags, kept separate from the review dataset)

Usage:
    python scripts/multiplatform/build_combined_outputs.py
"""
from __future__ import annotations

import _pathsetup  # noqa: F401

import csv
from difflib import SequenceMatcher
from pathlib import Path

from bodrum_intelligence.reviews.common import (
    DATA_PROCESSED_DIR, DATA_RAW_DIR, parse_source_rating, rating_5_scale,
)
from bodrum_intelligence.reviews.runner import load_targets

PROCESSED_FIELDNAMES = [
    "review_id", "hotel_id", "hotel_name", "area", "source_platform", "source_rating",
    "source_rating_max", "rating_5_scale", "review_title", "review_text", "review_date_raw",
    "stay_date_raw", "traveler_type", "room_type", "reviewer_location", "value_rating",
    "rooms_rating", "location_rating", "cleanliness_rating", "service_rating",
    "source_url", "collected_at",
]

AMENITY_KEYWORDS = {
    "has_private_beach": ["private beach", "özel plaj"],
    "has_indoor_pool": ["indoor pool", "kapalı havuz"],
    "has_outdoor_pool": ["outdoor pool", "açık havuz"],
    "has_kids_pool": ["kids' pool", "kids pool", "çocuk havuzu"],
    "has_kids_club": ["kids' club", "kids club", "çocuk kulübü"],
    "has_playground": ["playground", "oyun alanı", "oyun parkı"],
    "has_spa": ["spa"],
    "has_sauna": ["sauna"],
    "has_gym": ["fitness", "gym"],
    "has_restaurant": ["restaurant", "restoran"],
    "has_bar": ["bar"],
    "has_wifi": ["wifi", "wi-fi", "internet"],
    "has_airport_pickup": ["airport pick", "havalimanı transfer", "airport shuttle"],
    "has_airport_dropoff": ["airport drop", "havalimanına transfer"],
    "has_parking": ["parking", "otopark"],
}


def find_raw_csv(platform_dir: Path, hotel_id: str) -> Path | None:
    matches = list(platform_dir.glob(f"{hotel_id}_*.csv"))
    return matches[0] if matches else None


def build_reviews(targets: list[dict]) -> tuple[int, dict]:
    out_path = DATA_PROCESSED_DIR / "multiplatform_reviews_raw_normalized.csv"
    DATA_PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    review_id = 0
    per_hotel_texts: dict[str, list[tuple[str, str, str]]] = {}  # hotel_id -> [(platform, text, date)]

    with open(out_path, "w", newline="", encoding="utf-8-sig") as out_f:
        w = csv.DictWriter(out_f, fieldnames=PROCESSED_FIELDNAMES)
        w.writeheader()
        for row in targets:
            hid, hname, area = row["hotel_id"], row["hotel_name"], row["area"]
            for platform, url_col in (("google_travel", "google_travel_url"), ("trip", "trip_url"),
                                       ("tripadvisor", "tripadvisor_url")):
                platform_dir = DATA_RAW_DIR / "reviews" / platform
                raw_csv = find_raw_csv(platform_dir, hid)
                if raw_csv is None:
                    continue
                with open(raw_csv, encoding="utf-8-sig", newline="") as rf:
                    for r in csv.DictReader(rf):
                        review_id += 1
                        rating, rating_max = parse_source_rating(platform, r.get("puan", ""))
                        text = r.get("yorum", "")
                        w.writerow({
                            "review_id": review_id, "hotel_id": hid, "hotel_name": hname, "area": area,
                            "source_platform": platform, "source_rating": rating,
                            "source_rating_max": rating_max, "rating_5_scale": rating_5_scale(rating, rating_max),
                            "review_title": r.get("yorum_basligi", ""), "review_text": text,
                            "review_date_raw": r.get("tarih") or r.get("yorum_tarihi", ""),
                            "stay_date_raw": r.get("konaklama_tarihi", ""),
                            "traveler_type": r.get("seyahat_tipi") or r.get("seyahat_turu", ""),
                            "room_type": r.get("oda_tipi", ""),
                            "reviewer_location": r.get("konum", ""),
                            "value_rating": r.get("value_rating", ""), "rooms_rating": r.get("rooms_rating", ""),
                            "location_rating": r.get("location_rating", ""),
                            "cleanliness_rating": r.get("cleanliness_rating", ""),
                            "service_rating": r.get("service_rating", ""),
                            "source_url": row.get(url_col, ""), "collected_at": "",
                        })
                        if text.strip():
                            per_hotel_texts.setdefault(hid, []).append(
                                (platform, text, r.get("tarih") or r.get("yorum_tarihi", "")))
    print(f"Wrote {out_path} ({review_id} rows)")
    return review_id, per_hotel_texts


def build_cross_source_duplicates(per_hotel_texts: dict, hotel_names: dict[str, str],
                                   reports_dir: Path) -> None:
    reports_dir.mkdir(parents=True, exist_ok=True)
    out_path = reports_dir / "multiplatform_cross_source_duplicate_candidates.csv"
    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["hotel_id", "hotel_name", "source_a", "source_b", "text_similarity",
                    "review_date_similarity", "candidate_duplicate"])
        for hid, entries in per_hotel_texts.items():
            for i in range(len(entries)):
                for j in range(i + 1, len(entries)):
                    pa, ta, da = entries[i]
                    pb, tb, db = entries[j]
                    if pa == pb:
                        continue
                    sim = SequenceMatcher(None, ta.strip().lower(), tb.strip().lower()).ratio()
                    if sim < 0.5:
                        continue
                    date_sim = 1 if da and da == db else 0
                    w.writerow([hid, hotel_names.get(hid, ""), pa, pb, round(sim, 3), date_sim,
                                sim >= 0.75])
    print(f"Wrote {out_path}")


def build_policy_features(targets: list[dict]) -> None:
    out_path = DATA_PROCESSED_DIR / "hotel_policies_features.csv"
    DATA_PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    fieldnames = ["hotel_id", "hotel_name", "area", "checkin_time", "checkout_time",
                  "children_allowed", "pets_allowed", "service_animals_allowed", "minimum_age",
                  "license_number", "facility_count"] + list(AMENITY_KEYWORDS.keys())
    policies_dir = DATA_RAW_DIR / "hotel_policies" / "trip"
    written = 0
    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for row in targets:
            hid, hname, area = row["hotel_id"], row["hotel_name"], row["area"]
            raw_csv = find_raw_csv(policies_dir, hid)
            if raw_csv is None:
                continue
            with open(raw_csv, encoding="utf-8-sig", newline="") as rf:
                policy_rows = list(csv.DictReader(rf))
            if not policy_rows:
                continue
            p = policy_rows[0]
            hizmetler = (p.get("hizmetler", "") or "").lower()
            evcil = (p.get("evcil_hayvan", "") or "").lower()
            cocuk = (p.get("cocuk_politikası", "") or "")
            out_row = {
                "hotel_id": hid, "hotel_name": hname, "area": area,
                "checkin_time": p.get("giris_saati", ""), "checkout_time": p.get("cıkıs_saati", ""),
                "children_allowed": "children" in cocuk.lower() or bool(cocuk),
                "pets_allowed": "not allowed" not in evcil and "pets are" in evcil,
                "service_animals_allowed": "allowed" in (p.get("hizmet_hayvanları", "") or "").lower(),
                "minimum_age": p.get("yas_sarti", ""), "license_number": p.get("sertifika_numarasi", ""),
                "facility_count": len([h for h in hizmetler.split(";") if h.strip()]),
            }
            for flag, keywords in AMENITY_KEYWORDS.items():
                out_row[flag] = any(kw in hizmetler for kw in keywords)
            w.writerow(out_row)
            written += 1
    print(f"Wrote {out_path} ({written} hotels)")


def main() -> int:
    targets = load_targets()
    hotel_names = {r["hotel_id"]: r["hotel_name"] for r in targets}
    from bodrum_intelligence.reviews.common import REPORTS_DIR

    _review_count, per_hotel_texts = build_reviews(targets)
    build_cross_source_duplicates(per_hotel_texts, hotel_names, REPORTS_DIR)
    build_policy_features(targets)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
