from bodrum_intelligence.reviews.validation import url_format_status, url_present, is_verified


def test_url_present_treats_literal_null_string_as_absent():
    assert url_present("null") is False
    assert url_present("") is False
    assert url_present(None) is False
    assert url_present("https://example.com") is True


def test_google_travel_valid_url():
    assert url_format_status(
        "google_travel",
        "https://www.google.com/travel/hotels/entity/CgoIvomz-pTkabcd?g2lb=123") == "OK"


def test_google_travel_discovery_derived_query_url_is_also_valid():
    # Phase 3 discovery lands on .../entity?q=...&ts=... rather than the
    # canonical .../entity/<hash> form - confirmed live to be a stable,
    # cold-session-safe URL for the same hotel, so it must validate too.
    assert url_format_status(
        "google_travel",
        "https://www.google.com/travel/hotels/entity?q=Some+Hotel&ved=abc&ts=CAE") == "OK"


def test_trip_discovery_derived_hotelid_url_is_also_valid():
    # Phase 3 discovery constructs this canonical form from the resolved
    # numeric hotel id (optionId) - confirmed live to be stable.
    assert url_format_status("trip", "https://www.trip.com/hotels/detail/?hotelId=3448104") == "OK"


def test_google_travel_wrong_domain():
    assert url_format_status("google_travel", "https://www.bing.com/travel/hotels/entity/x") == "INVALID_DOMAIN"


def test_trip_valid_url():
    assert url_format_status(
        "trip", "https://www.trip.com/hotels/bodrum-hotel-detail-3448104/some-hotel/") == "OK"


def test_trip_wrong_domain():
    assert url_format_status("trip", "https://www.booking.com/hotels/detail-123/") == "INVALID_DOMAIN"


def test_tripadvisor_valid_url():
    assert url_format_status(
        "tripadvisor",
        "https://www.tripadvisor.com/Hotel_Review-g951437-d1097054-Reviews-Foo.html") == "OK"


def test_tripadvisor_malformed_path_on_correct_domain():
    assert url_format_status("tripadvisor", "https://www.tripadvisor.com/Some_Other_Page") == "INVALID_URL"


def test_no_url_status():
    assert url_format_status("google_travel", "null") == "NO_URL"
    assert url_format_status("trip", "") == "NO_URL"


def test_is_verified():
    assert is_verified("verified_direct") is True
    assert is_verified("VERIFIED_DIRECT") is True
    assert is_verified("null") is False
    assert is_verified("") is False
    assert is_verified(None) is False
