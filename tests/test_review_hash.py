import csv

from bodrum_intelligence.reviews.common import append_rows_dedup, read_existing_hashes, review_hash


def test_review_hash_is_deterministic_regardless_of_key_order():
    a = {"hotel_id": "BOD012", "yorum": "Harika bir tatildi", "puan": "5/5"}
    b = {"puan": "5/5", "hotel_id": "BOD012", "yorum": "Harika bir tatildi"}
    assert review_hash(a) == review_hash(b)


def test_review_hash_differs_for_different_content():
    a = review_hash({"hotel_id": "BOD012", "yorum": "Harika"})
    b = review_hash({"hotel_id": "BOD012", "yorum": "Kotu"})
    assert a != b


def test_read_existing_hashes_missing_file_returns_empty_set(tmp_path):
    assert read_existing_hashes(tmp_path / "does_not_exist.csv") == set()


def test_append_rows_dedup_skips_duplicates_and_never_overwrites(tmp_path):
    out = tmp_path / "reviews.csv"
    fieldnames = ["review_hash", "yorum"]

    row1 = {"review_hash": review_hash({"yorum": "birinci"}), "yorum": "birinci"}
    row2 = {"review_hash": review_hash({"yorum": "ikinci"}), "yorum": "ikinci"}

    added, skipped = append_rows_dedup(out, [row1, row2], fieldnames)
    assert (added, skipped) == (2, 0)

    # Re-appending the same rows plus one new one on a "second run" (resume)
    # must not duplicate the first two and must not rewrite the file.
    row3 = {"review_hash": review_hash({"yorum": "ucuncu"}), "yorum": "ucuncu"}
    added2, skipped2 = append_rows_dedup(out, [row1, row2, row3], fieldnames)
    assert (added2, skipped2) == (1, 2)

    with open(out, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 3
    assert rows[0]["yorum"] == "birinci"  # original row untouched/not overwritten
