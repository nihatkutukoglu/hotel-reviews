"""Unit tests for the transparent 0-100 discovery candidate scorer
(section 12-13). Pure function, no browser needed.
"""
from bodrum_intelligence.discovery.candidate_scoring import (
    score_candidate, FOUND_EXACT, FOUND_HIGH_CONFIDENCE, REVIEW_REQUIRED, NOT_FOUND,
)


def test_identical_name_scores_found_exact():
    r = score_candidate("Armonia Holiday Village & Spa", "Armonia Holiday Village & Spa", area_match=True)
    assert r["validation_status"] == FOUND_EXACT
    assert r["candidate_score"] == 100


def test_minor_wording_difference_scores_high_confidence_or_exact():
    r = score_candidate("Armonia Holiday Village & Spa", "Armonia Holiday Village Spa Bodrum", area_match=True)
    assert r["validation_status"] in (FOUND_EXACT, FOUND_HIGH_CONFIDENCE)


def test_selectum_collision_is_never_silently_merged():
    # Same brand, different actual hotels - must stay below FOUND_EXACT/
    # FOUND_HIGH_CONFIDENCE even with a favorable area match, so it lands
    # on the human-review queue instead of being auto-accepted.
    r = score_candidate("Selectum Collection Bodrum", "Selectum Colours Bodrum", area_match=True)
    assert r["validation_status"] not in (FOUND_EXACT, FOUND_HIGH_CONFIDENCE)


def test_la_blanche_collision_is_never_silently_merged():
    r = score_candidate("La Blanche Island Bodrum", "La Blanche Resort Bodrum", area_match=True)
    assert r["validation_status"] not in (FOUND_EXACT, FOUND_HIGH_CONFIDENCE)


def test_no_detected_name_is_not_found():
    r = score_candidate("Any Hotel", "", area_match=None)
    assert r["validation_status"] == NOT_FOUND
    assert r["candidate_score"] == 0


def test_area_mismatch_alone_does_not_reject_a_strong_name_match():
    with_area = score_candidate("Some Hotel Name", "Some Hotel Name", area_match=True)
    without_area = score_candidate("Some Hotel Name", "Some Hotel Name", area_match=False)
    assert with_area["validation_status"] == FOUND_EXACT
    # area mismatch nudges the score down a little but never on its own
    # turns a perfect name match into a rejection (section 8).
    assert without_area["validation_status"] in (FOUND_EXACT, FOUND_HIGH_CONFIDENCE)


def test_score_components_are_explainable():
    r = score_candidate("Hotel X", "Hotel X", area_match=True)
    assert "name_component" in r["components"]
    assert "area_component" in r["components"]
    assert r["components"]["name_component"] + r["components"]["area_component"] >= r["candidate_score"]
