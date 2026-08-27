from bodrum_intelligence.analysis.tripcom_cleaning import canonical_traveler_type


def test_english_variants():
    assert canonical_traveler_type("Family") == "FAMILY"
    assert canonical_traveler_type("Couple") == "COUPLE"
    assert canonical_traveler_type("Solo traveler") == "SOLO"


def test_friends_spelling_variants_both_map_to_friends():
    # Trip.com shows both spellings in real scraped data.
    assert canonical_traveler_type("Traveling with friends") == "FRIENDS"
    assert canonical_traveler_type("Travelling with friends") == "FRIENDS"


def test_localized_indonesian_variants():
    # Confirmed present in real scraped data (Trip.com is a global site).
    assert canonical_traveler_type("Keluarga") == "FAMILY"
    assert canonical_traveler_type("Pelancong solo") == "SOLO"
    assert canonical_traveler_type("Pasangan") == "COUPLE"


def test_empty_is_unknown_not_other():
    assert canonical_traveler_type("") == "UNKNOWN"
    assert canonical_traveler_type(None) == "UNKNOWN"


def test_unrecognized_value_is_other_not_dropped():
    assert canonical_traveler_type("Something Unmapped") == "OTHER"
