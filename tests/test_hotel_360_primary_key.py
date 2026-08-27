"""Global validation: data/processed/hotel_360_intelligence.csv must have
a unique hotel_id primary key and cover every master hotel (one row per
hotel, whether or not it has review/policy data yet).
"""
import csv

import pytest

from bodrum_intelligence.reviews.common import DATA_PROCESSED_DIR, master_hotel_csv_path


def _load(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def test_hotel_360_primary_key_is_unique():
    path = DATA_PROCESSED_DIR / "hotel_360_intelligence.csv"
    if not path.exists():
        pytest.skip("hotel_360_intelligence.csv not generated in this environment yet")
    rows = _load(path)
    ids = [r["hotel_id"] for r in rows]
    assert len(ids) == len(set(ids)), "duplicate hotel_id in hotel_360_intelligence.csv"


def test_hotel_360_covers_every_master_hotel():
    path = DATA_PROCESSED_DIR / "hotel_360_intelligence.csv"
    master_path = master_hotel_csv_path()
    if not path.exists() or not master_path.exists():
        pytest.skip("hotel_360_intelligence.csv or master dataset not available in this environment")
    rows = _load(path)
    master_rows = _load(master_path)
    assert {r["hotel_id"] for r in rows} == {r["hotel_id"] for r in master_rows}


def test_hotel_360_confidence_values_are_from_the_documented_set():
    path = DATA_PROCESSED_DIR / "hotel_360_intelligence.csv"
    if not path.exists():
        pytest.skip("hotel_360_intelligence.csv not generated in this environment yet")
    rows = _load(path)
    allowed = {"HIGH", "MEDIUM", "LOW", "VERY_LOW"}
    for r in rows:
        assert r.get("customer_voice_support", "") in allowed
