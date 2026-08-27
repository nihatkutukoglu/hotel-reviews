from bodrum_intelligence.reviews.common import evaluate_raw_csv_quality, parse_source_rating, rating_5_scale


def test_google_travel_rating_is_x_of_5_format():
    # Confirmed from google/yorum.csv sample data: "puan" is literally "4/5".
    rating, scale = parse_source_rating("google_travel", "4/5")
    assert (rating, scale) == (4.0, 5.0)
    assert rating_5_scale(rating, scale) == 4.0


def test_trip_rating_is_zero_to_ten_scale():
    # Confirmed from trip/trip_yorum.csv sample data: "puan" is e.g. "9.5", "10.0".
    rating, scale = parse_source_rating("trip", "9.5")
    assert (rating, scale) == (9.5, 10.0)
    assert rating_5_scale(rating, scale) == 4.75


def test_tripadvisor_rating_is_one_to_five_scale():
    # Confirmed from tripadvisor/tripadvisor_yorum.csv sample data: "puan" is e.g. "4".
    rating, scale = parse_source_rating("tripadvisor", "4")
    assert (rating, scale) == (4.0, 5.0)
    assert rating_5_scale(rating, scale) == 4.0


def test_platforms_are_not_mixed_up_a_4_means_different_things():
    # The same raw "4" must NOT normalize to the same 5-scale value across
    # every platform if their max scales differ - here trip's scale is 10,
    # so a raw "4" is a much worse review than tripadvisor's raw "4"/5.
    trip_rating, trip_scale = parse_source_rating("trip", "4")
    ta_rating, ta_scale = parse_source_rating("tripadvisor", "4")
    assert rating_5_scale(trip_rating, trip_scale) == 2.0
    assert rating_5_scale(ta_rating, ta_scale) == 4.0


def test_empty_or_unparsable_rating_returns_none():
    assert parse_source_rating("google_travel", "") == (None, None)
    assert parse_source_rating("trip", "cok iyi") == (None, None)
    assert rating_5_scale(None, None) is None


def test_turkish_decimal_comma_is_handled():
    rating, scale = parse_source_rating("trip", "8,5")
    assert rating == 8.5


def test_quality_check_does_not_flag_valid_google_n_of_5_ratings_as_invalid(tmp_path):
    # Regression: evaluate_raw_csv_quality used to try float("2/5") directly
    # (ValueError) and flag every single real Google Travel rating as
    # invalid_rating, even though "2/5" is exactly the format
    # google/yorum.py has always written.
    csv_path = tmp_path / "reviews.csv"
    csv_path.write_text("otel_adi,yorum,hizmet,tarih,puan\nHotel X,Great stay,,today,2/5\n",
                         encoding="utf-8-sig")
    quality = evaluate_raw_csv_quality(csv_path, platform="google_travel")
    assert quality["invalid_rating"] == 0

    quality_no_platform = evaluate_raw_csv_quality(csv_path)
    assert quality_no_platform["invalid_rating"] == 1  # without platform hint, still the old naive behavior
