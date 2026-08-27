from bodrum_intelligence.analysis.cross_platform import hotel_coverage


def test_intersection_and_differences():
    google_ids = {"BOD001", "BOD002", "BOD003"}
    trip_ids = {"BOD002", "BOD003", "BOD004"}
    cov = hotel_coverage(google_ids, trip_ids)
    assert cov["both"] == ["BOD002", "BOD003"]
    assert cov["google_only"] == ["BOD001"]
    assert cov["trip_only"] == ["BOD004"]


def test_no_row_level_merge_only_hotel_ids():
    # This function only ever operates on hotel_id SETS - it has no way to
    # accidentally merge individual review rows across platforms
    # (section E3's "no row-level merge" rule holds by construction).
    cov = hotel_coverage(set(), set())
    assert cov == {"both": [], "google_only": [], "trip_only": []}


def test_disjoint_sets():
    cov = hotel_coverage({"A"}, {"B"})
    assert cov["both"] == []
    assert cov["google_only"] == ["A"]
    assert cov["trip_only"] == ["B"]
