"""BOD135/BOD155/BOD175 have a literal "|" in their master hotel_name
(e.g. "Yılmaz Hotel | Bodrum Ortakent Otelleri"). Standard CSV parsing
(csv.DictReader, comma-delimited, quoted fields) was never actually the
problem - "|" is just a character inside a properly-quoted field. The
original link-file generator apparently mis-split on it anyway, shifting
text into the area column. apply_data_quality_fixes.py corrected the 3
link-file rows to copy hotel_name/area straight from master. These tests
guard both facts: standard CSV parsing handles "|" fine, and the link
files now match master exactly for these 3 hotels.
"""
import csv
import io

import pytest

from bodrum_intelligence.reviews.common import PLATFORM_LINK_FILES, master_hotel_csv_path, read_csv_dicts

PIPE_BUG_IDS = ["BOD135", "BOD155", "BOD175"]

pytestmark = pytest.mark.skipif(
    not master_hotel_csv_path().exists(),
    reason="master hotel dataset not found next to this repo; set BODRUM_MASTER_HOTEL_CSV to run this test",
)


def test_standard_csv_parser_never_splits_on_a_pipe_character():
    raw = 'hotel_id,hotel_name,area\nBOD135,"Yılmaz Hotel | Bodrum Ortakent Otelleri",Ortakent-Yahşi\n'
    rows = list(csv.DictReader(io.StringIO(raw)))
    assert rows[0]["hotel_name"] == "Yılmaz Hotel | Bodrum Ortakent Otelleri"
    assert rows[0]["area"] == "Ortakent-Yahşi"
    assert "|" not in rows[0]["area"]


def test_link_files_now_match_master_hotel_name_and_area_for_the_pipe_bug_hotels():
    master_by_id = {r["hotel_id"]: r for r in read_csv_dicts(master_hotel_csv_path())}
    for platform, path in PLATFORM_LINK_FILES.items():
        link_by_id = {r["hotel_id"]: r for r in read_csv_dicts(path)}
        for hid in PIPE_BUG_IDS:
            master_row = master_by_id[hid]
            link_row = link_by_id[hid]
            assert link_row["hotel_name"] == master_row["hotel_name"], f"{platform}/{hid}: hotel_name mismatch"
            assert link_row["area"] == master_row["area"], f"{platform}/{hid}: area mismatch"
            assert "|" not in link_row["area"], f"{platform}/{hid}: area still contains a shifted '|' fragment"
