from bodrum_intelligence.analysis.policies_cleaning import AMENITY_KEYWORDS, detect_amenities


def test_amenity_detected_only_from_real_text_evidence():
    hits = detect_amenities("Spa and Wellness Center, Outdoor Pool, Free Wifi")
    assert hits["has_spa"] is True
    assert hits["has_outdoor_pool"] is True
    assert hits["has_wifi"] is True
    assert hits["has_diving"] is False


def test_amenity_never_inferred_from_absence():
    hits = detect_amenities("")
    assert not any(hits.values())


def test_amenity_flags_cover_the_documented_set():
    hits = detect_amenities("anything")
    assert set(hits.keys()) == set(AMENITY_KEYWORDS.keys())


def test_turkish_keyword_variant_matches_too():
    hits = detect_amenities("Özel Plaj, Kapalı Havuz")
    assert hits["has_private_beach"] is True
    assert hits["has_indoor_pool"] is True


def test_case_insensitive_matching():
    hits = detect_amenities("SPA AND SAUNA AVAILABLE")
    assert hits["has_spa"] is True
    assert hits["has_sauna"] is True
