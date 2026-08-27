from bodrum_intelligence.analysis.tripcom_cleaning import parse_review_date, parse_stay_date


def test_parse_review_date_exact_format():
    # Trip.com's yorum_tarihi is an exact date, unlike Google Travel's
    # relative-time strings.
    assert parse_review_date("Posted July 1, 2026") == "2026-07-01"
    assert parse_review_date("Posted December 25, 2025") == "2025-12-25"


def test_parse_review_date_missing_is_none():
    assert parse_review_date("") is None
    assert parse_review_date("garbage text") is None


def test_parse_stay_date_month_precision_only():
    year, month, precision = parse_stay_date("Stayed in June 2026")
    assert year == 2026
    assert month == 6
    assert precision == "MONTH"


def test_parse_stay_date_missing():
    year, month, precision = parse_stay_date("")
    assert (year, month, precision) == (None, None, None)
