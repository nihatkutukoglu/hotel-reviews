"""BOD192 (Yalıpark Beach Hotel, Yalıkavak) is the one master hotel that
had no record at all in any of the three link files (the 191-vs-192
discrepancy). apply_data_quality_fixes.py appended an explicit
MISSING_LINK_RECORD row to each file rather than fabricating a URL.
"""
import pytest

from bodrum_intelligence.reviews.common import PLATFORM_LINK_FILES, master_hotel_csv_path, read_csv_dicts
from bodrum_intelligence.reviews.validation import is_verified, url_present

pytestmark = pytest.mark.skipif(
    not master_hotel_csv_path().exists(),
    reason="master hotel dataset not found next to this repo; set BODRUM_MASTER_HOTEL_CSV to run this test",
)


def test_bod192_exists_in_master():
    master_by_id = {r["hotel_id"]: r for r in read_csv_dicts(master_hotel_csv_path())}
    assert "BOD192" in master_by_id
    assert master_by_id["BOD192"]["hotel_name"] == "Yalıpark Beach Hotel"
    assert master_by_id["BOD192"]["area"] == "Yalıkavak"


def test_bod192_present_in_every_link_file_as_missing_link_record():
    for platform, path in PLATFORM_LINK_FILES.items():
        rows = {r["hotel_id"]: r for r in read_csv_dicts(path)}
        assert "BOD192" in rows, f"{platform}: BOD192 still absent"
        row = rows["BOD192"]
        assert row["status"] == "MISSING_LINK_RECORD"
        assert not is_verified(row["status"])
        assert not url_present(row["direct_url"]), f"{platform}: BOD192 must never have a fabricated URL"


def test_bod192_enablement_never_rests_on_a_fabricated_or_missing_link():
    # BOD192 originally had MISSING_LINK_RECORD on every phase-1/2 platform
    # (asserted above) - it must never be *enabled* on the strength of one of
    # those placeholder rows. Task A's live full-coverage discovery later
    # searched Trip.com directly (independent of the phase-1/2 link files)
    # and found a genuine, verified_direct match for it there - that is
    # legitimate new data, not a fabricated URL, so BOD192 CAN be enabled
    # once a platform's own status is genuinely verified_direct.
    from bodrum_intelligence.reviews.runner import load_targets
    targets = {r["hotel_id"]: r for r in load_targets()}
    if "BOD192" not in targets:  # only present after build_platform_config.py has run
        return
    row = targets["BOD192"]
    if row["enabled"].strip().lower() == "true":
        assert row["trip_status"].strip() == "verified_direct" or row["google_travel_status"].strip() == "verified_direct"
        assert url_present(row.get("trip_url")) or url_present(row.get("google_travel_url"))
    assert row["tripadvisor_status"].strip() == "MISSING_LINK_RECORD"
    assert not url_present(row.get("tripadvisor_url"))
