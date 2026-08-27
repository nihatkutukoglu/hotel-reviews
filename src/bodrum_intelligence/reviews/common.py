"""Shared paths, config loading, hashing and resume/dedupe helpers for the
multiplatform hotel review pipeline.

No absolute paths are hardcoded here: everything is resolved relative to the
repository root (this file's location) or overridable via environment
variables / config/pipeline_settings.json, since the master hotel dataset
lives in a sibling repository outside this one.
"""
from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import os
import sys
import types
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Mapping, Sequence

REPO_ROOT = Path(__file__).resolve().parents[3]
CONFIG_DIR = REPO_ROOT / "config"
REPORTS_DIR = REPO_ROOT / "reports"
DATA_RAW_DIR = REPO_ROOT / "data" / "raw"
DATA_PROCESSED_DIR = REPO_ROOT / "data" / "processed"
LINK_DIR = REPO_ROOT / "bodrum-otel-linkleri"

PLATFORM_LINK_FILES = {
    "google_travel": LINK_DIR / "bodrum_hotels_google_travel_direct_links_2026-08-26.csv",
    "trip": LINK_DIR / "bodrum_hotels_trip_com_direct_links_2026-08-26.csv",
    "tripadvisor": LINK_DIR / "bodrum_hotels_tripadvisor_direct_links_2026-08-26.csv",
}

_SETTINGS_FILE = CONFIG_DIR / "pipeline_settings.json"


def _load_settings() -> dict:
    if _SETTINGS_FILE.exists():
        with open(_SETTINGS_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def master_hotel_csv_path() -> Path:
    """Resolve the master hotel dataset path.

    Priority: BODRUM_MASTER_HOTEL_CSV env var > config/pipeline_settings.json
    "master_hotel_csv" (relative to this repo's parent directory) > default
    sibling-repo location.
    """
    env_override = os.environ.get("BODRUM_MASTER_HOTEL_CSV")
    if env_override:
        return Path(env_override)
    settings = _load_settings()
    if "master_hotel_csv" in settings:
        return (REPO_ROOT.parent.parent / settings["master_hotel_csv"]).resolve()
    return (REPO_ROOT.parent.parent / "bodrum otel" / "bodrum-otel" / "bodrum_hotels_master_2026-08-24.csv").resolve()


def load_legacy_module(unique_name: str, file_path: Path) -> types.ModuleType:
    """Loads one of the existing google/trip/tripadvisor/politikalar scripts
    as a Python module by explicit file path (not via sys.path + normal
    import), so directory names like "google" or "trip" never shadow or
    collide with real installed packages of the same name.
    """
    if unique_name in sys.modules:
        return sys.modules[unique_name]
    spec = importlib.util.spec_from_file_location(unique_name, file_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load legacy module from {file_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[unique_name] = module
    spec.loader.exec_module(module)
    return module


def read_csv_dicts(path: Path) -> list[dict]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def safe_hotel_slug(hotel_name: str) -> str:
    keep = "".join(c if c.isalnum() else "_" for c in hotel_name.lower())
    while "__" in keep:
        keep = keep.replace("__", "_")
    return keep.strip("_")


def per_hotel_csv_path(base_dir: Path, hotel_id: str, hotel_name: str) -> Path:
    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir / f"{hotel_id}_{safe_hotel_slug(hotel_name)}.csv"


REVIEW_HASH_FIELDS_BY_PLATFORM: Mapping[str, Sequence[str]] = {
    "google_travel": ("hotel_id", "reviewer_name", "review_text", "review_date_raw", "rating"),
    "trip": ("hotel_id", "yorum", "yorum_tarihi", "puan"),
    "tripadvisor": ("hotel_id", "yorum_basligi", "yorum", "yorum_tarihi", "puan"),
}


def review_hash(fields: Mapping[str, object]) -> str:
    """Stable SHA-256 hash over a fixed, ordered set of fields.

    Used for dedupe: same (hotel, reviewer/text/date/rating) tuple always
    hashes the same way regardless of dict key ordering or extra columns.
    """
    parts = [str(fields.get(k, "")).strip() for k in sorted(fields.keys())]
    joined = "\x1f".join(parts)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def read_existing_hashes(csv_path: Path, hash_field: str = "review_hash") -> set[str]:
    if not csv_path.exists():
        return set()
    with open(csv_path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return {row[hash_field] for row in reader if row.get(hash_field)}


def parse_source_rating(platform: str, raw_puan: str) -> tuple[float | None, float | None]:
    """Returns (source_rating, source_rating_max) for a raw "puan" value.
    Confirmed empirically from the existing sample CSVs (do not assume a
    uniform scale across platforms):
      - google_travel: "4/5" style strings -> scale is 5
      - trip:          plain "9.5" style strings -> scale is 10
      - tripadvisor:   plain "4" style strings -> scale is 5
    Only used at the processed layer (section 39) - raw values are never
    rewritten.
    """
    raw = (raw_puan or "").strip()
    if not raw:
        return None, None
    if platform == "google_travel":
        if "/" in raw:
            num, _, denom = raw.partition("/")
            try:
                return float(num.replace(",", ".")), float(denom.replace(",", "."))
            except ValueError:
                return None, None
        try:
            return float(raw.replace(",", ".")), 5.0
        except ValueError:
            return None, None
    if platform == "trip":
        try:
            return float(raw.replace(",", ".")), 10.0
        except ValueError:
            return None, None
    if platform == "tripadvisor":
        try:
            return float(raw.replace(",", ".")), 5.0
        except ValueError:
            return None, None
    return None, None


def rating_5_scale(source_rating: float | None, source_rating_max: float | None) -> float | None:
    if source_rating is None or not source_rating_max:
        return None
    return round(source_rating / source_rating_max * 5, 3)


def evaluate_raw_csv_quality(csv_path: Path, text_field: str = "yorum",
                              rating_field: str = "puan", platform: str | None = None) -> dict:
    """Smoke-test quality checks (section 25/26) over a raw per-hotel
    review CSV: row counts, empty review text, unparsable ratings, and
    duplicate rows (by full-row content, independent of the writer's own
    dedupe logic - this is an external re-check, not a re-implementation
    of it).
    """
    if not csv_path.exists():
        return {"rows_scraped": 0, "unique_rows": 0, "empty_review_text": 0,
                "invalid_rating": 0, "duplicate_rows": 0}
    rows = read_csv_dicts(csv_path)
    seen = set()
    duplicate_rows = 0
    empty_text = 0
    invalid_rating = 0
    for row in rows:
        key = tuple(sorted(row.items()))
        if key in seen:
            duplicate_rows += 1
        else:
            seen.add(key)
        if not (row.get(text_field) or "").strip():
            empty_text += 1
        raw_rating = (row.get(rating_field) or "").strip()
        if raw_rating:
            if platform:
                rating, _max = parse_source_rating(platform, raw_rating)
                if rating is None:
                    invalid_rating += 1
            else:
                try:
                    float(raw_rating.replace(",", "."))
                except ValueError:
                    invalid_rating += 1
    return {
        "rows_scraped": len(rows),
        "unique_rows": len(seen),
        "empty_review_text": empty_text,
        "invalid_rating": invalid_rating,
        "duplicate_rows": duplicate_rows,
    }


def append_rows_dedup(
    csv_path: Path,
    rows: Iterable[dict],
    fieldnames: Sequence[str],
    hash_field: str = "review_hash",
) -> tuple[int, int]:
    """Append new rows to csv_path, skipping any whose hash_field value is
    already present. Never overwrites existing rows (resume-safe).

    Returns (rows_added, duplicates_skipped).
    """
    existing = read_existing_hashes(csv_path, hash_field)
    file_exists = csv_path.exists()
    added = 0
    skipped = 0
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with open(csv_path, "a", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        for row in rows:
            h = row.get(hash_field)
            if h in existing:
                skipped += 1
                continue
            writer.writerow(row)
            existing.add(h)
            added += 1
    return added, skipped
