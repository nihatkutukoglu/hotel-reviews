"""Regression tests over the real master dataset + platform link files.

These are integration tests, not unit tests with fixtures: the whole point
of the audit is what it finds in the *actual* files, so the real files are
the source of truth. They skip gracefully if the sibling master-hotel repo
isn't present (e.g. a checkout of this repo alone, without the master
project next to it).
"""
import pytest

from bodrum_intelligence.reviews.common import PLATFORM_LINK_FILES, master_hotel_csv_path, read_csv_dicts

pytestmark = pytest.mark.skipif(
    not master_hotel_csv_path().exists(),
    reason="master hotel dataset not found next to this repo; set BODRUM_MASTER_HOTEL_CSV to run this test",
)


def _master_ids() -> set[str]:
    return {r["hotel_id"] for r in read_csv_dicts(master_hotel_csv_path())}


def test_master_has_no_duplicate_hotel_ids():
    rows = read_csv_dicts(master_hotel_csv_path())
    ids = [r["hotel_id"] for r in rows]
    assert len(ids) == len(set(ids))


def test_master_has_no_duplicate_place_ids():
    rows = read_csv_dicts(master_hotel_csv_path())
    place_ids = [r["place_id"] for r in rows]
    assert len(place_ids) == len(set(place_ids))


def test_every_platform_link_file_has_no_extra_or_duplicate_hotel_ids():
    master_ids = _master_ids()
    for platform, path in PLATFORM_LINK_FILES.items():
        rows = read_csv_dicts(path)
        ids = [r["hotel_id"] for r in rows]
        assert len(ids) == len(set(ids)), f"{platform}: duplicate hotel_id found"
        assert set(ids) <= master_ids, f"{platform}: hotel_id(s) not present in master"


def test_bod192_is_present_in_every_link_file_after_the_phase2_fix():
    # Phase 1 found BOD192 (Yalıpark Beach Hotel, Yalıkavak) missing from
    # all three link files; phase 2's apply_data_quality_fixes.py appended
    # an explicit MISSING_LINK_RECORD row for it (no URL fabricated) to
    # each file. This is a regression guard against that row disappearing.
    master_ids = _master_ids()
    for platform, path in PLATFORM_LINK_FILES.items():
        rows = read_csv_dicts(path)
        link_ids = {r["hotel_id"] for r in rows}
        assert master_ids - link_ids == set(), f"{platform}: hotel_id(s) missing from link file"
        bod192_rows = [r for r in rows if r["hotel_id"] == "BOD192"]
        assert len(bod192_rows) == 1, f"{platform}: expected exactly one BOD192 row"
        assert bod192_rows[0]["status"] == "MISSING_LINK_RECORD"
        assert bod192_rows[0]["direct_url"] in ("null", ""), (
            f"{platform}: BOD192 must never have a fabricated direct_url"
        )
