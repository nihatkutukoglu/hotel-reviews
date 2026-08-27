"""Section 3 / global validation: Google Travel and Trip.com use different
sampling mechanisms and rating scales - raw scores must never be
overwritten, and source_platform must always be identifiable. Checked both
as a unit-level rule and, when the real processed files exist, against the
actual generated data.
"""
import csv
from pathlib import Path

from bodrum_intelligence.analysis.tripcom_cleaning import parse_trip_rating, rating_5_scale
from bodrum_intelligence.reviews.common import DATA_PROCESSED_DIR


def test_trip_raw_rating_and_normalized_rating_are_independent_columns():
    raw, raw_max, _ = parse_trip_rating("9.0")
    normalized = rating_5_scale(raw, raw_max)
    assert raw == 9.0  # the 0-10 raw score, untouched
    assert normalized == 4.5  # a SEPARATE, derived 5-scale value
    assert raw != normalized


def test_google_clean_dataset_preserves_raw_rating_and_platform_label():
    path = DATA_PROCESSED_DIR / "google_travel_all_hotels_reviews_clean.csv"
    if not path.exists():
        return  # pipeline hasn't been run in this environment yet
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        return
    assert all(r["review_rating_raw"] for r in rows if r["review_rating_numeric"])
    # source_platform-equivalent column for google is review_source - must
    # never be blank when a review row exists.
    assert all(r.get("review_source") for r in rows)


def test_trip_clean_dataset_preserves_raw_rating_and_platform_label():
    path = DATA_PROCESSED_DIR / "tripcom_reviews_clean.csv"
    if not path.exists():
        return
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        return
    for r in rows:
        assert r["source_platform"] == "trip"
        if r["source_rating"]:
            # raw is 0-10 scale, rating_5_scale is the separate normalized column
            assert float(r["source_rating_max"]) == 10.0
            if r["rating_5_scale"]:
                assert 0.0 <= float(r["rating_5_scale"]) <= 5.0
