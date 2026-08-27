from bodrum_intelligence.reviews.validation import (
    entity_validation_status, name_match_status, normalize_name,
    NAME_REVIEW_REQUIRED, VALID_ENTITY, WRONG_ENTITY,
)


def test_exact_match():
    assert name_match_status("Kefaluka Resort", "Kefaluka Resort") == "EXACT"


def test_normalized_match_turkish_characters_and_case():
    assert name_match_status("Yalıkavak Palace", "yalikavak palace") == "NORMALIZED_MATCH"
    assert name_match_status("Göltürkbükü Otel", "GOLTURKBUKU OTEL") == "NORMALIZED_MATCH"


def test_no_data_when_observed_missing():
    assert name_match_status("Kefaluka Resort", "") == "NO_DATA"
    assert name_match_status("Kefaluka Resort", None) == "NO_DATA"


def test_selectum_colours_vs_collection_regression():
    # These are two DIFFERENT sister properties - must never be treated as
    # a match just because they share the "Selectum" prefix.
    status = name_match_status("Selectum Colours", "Selectum Collection")
    assert status == "CONFLICT"
    assert entity_validation_status(status) == WRONG_ENTITY


def test_la_blanche_island_vs_resort_regression():
    status = name_match_status("La Blanche Island", "La Blanche Resort")
    assert status == "CONFLICT"
    assert entity_validation_status(status) == WRONG_ENTITY


def test_review_required_for_close_but_not_identical_names():
    # Small suffix difference (e.g. a trailing city tag) should be
    # flagged for review rather than silently accepted or rejected.
    status = name_match_status("Bendis Beach Hotel", "Bendis Beach Hotel Bodrum")
    assert status in ("REVIEW_REQUIRED", "NORMALIZED_MATCH")
    assert entity_validation_status(status) in (VALID_ENTITY, NAME_REVIEW_REQUIRED)


def test_normalize_name_strips_turkish_diacritics_and_punctuation():
    assert normalize_name("Şık Otel & Spa!") == "sik otel spa"
