from bodrum_intelligence.analysis.tripcom_cleaning import parse_trip_rating, rating_5_scale, rating_group_5


def test_trip_rating_scale_is_0_to_10():
    rating, max_, invalid = parse_trip_rating("8.5")
    assert rating == 8.5
    assert max_ == 10.0
    assert invalid is False


def test_empty_rating_is_invalid_not_zero():
    rating, max_, invalid = parse_trip_rating("")
    assert rating is None
    assert invalid is True


def test_rating_5_scale_conversion():
    assert rating_5_scale(10.0, 10.0) == 5.0
    assert rating_5_scale(8.0, 10.0) == 4.0
    assert rating_5_scale(None, 10.0) is None


def test_rating_group_explicit_thresholds():
    # LOW < 3.0, MID 3.0-3.99, HIGH >= 4.0 (on the normalized 5-scale)
    assert rating_group_5(2.99) == "LOW"
    assert rating_group_5(3.0) == "MID"
    assert rating_group_5(3.99) == "MID"
    assert rating_group_5(4.0) == "HIGH"
    assert rating_group_5(None) is None


def test_raw_rating_is_never_overwritten_by_normalization():
    # rating_5_scale is a derived, separate value - the raw source_rating
    # (0-10) must remain untouched by this helper.
    raw, raw_max, _ = parse_trip_rating("7.0")
    normalized = rating_5_scale(raw, raw_max)
    assert raw == 7.0  # untouched
    assert normalized == 3.5
