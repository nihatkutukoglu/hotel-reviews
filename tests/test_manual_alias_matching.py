"""config/multiplatform_hotel_aliases.csv holds explicit, manually-verified
per-(hotel_id, platform) name overrides - currently just BOD013/trip. This
must never generalize into a fuzzy-matching rule: it should only ever
rescue the exact hotel_id + platform + alias text it was verified for.
"""
import pytest

from bodrum_intelligence.reviews.aliases import is_accepted_alias, load_aliases, resolve_entity_status
from bodrum_intelligence.reviews.validation import NAME_REVIEW_REQUIRED, VALID_ENTITY, WRONG_ENTITY

PHASE3_TRIP_ALIASES = [
    ("BOD051", "Faros Bodrum Hotel Göltürkbükü", "Faros Hotel Bodrum - Special Category"),
    ("BOD055", "Lavinya Otel Göltürkbükü", "Lavinya Otel"),
    ("BOD059", "Bodrum Hotel Baba", "Hotel Baba"),
    ("BOD072", "VERY CHIC BODRUM", "Very Chic Bodrum Adult Only"),
    ("BOD073", "Arriba Apartment & Restaurant & Bungalows", "Arriba Apart Bungalow Restaurant"),
]

# Task B (overnight controller): fresh full-coverage Trip.com entity validation
# turned up 10 NAME_REVIEW_REQUIRED hotels (a softer bucket than WRONG_ENTITY) -
# each is a plain translation/punctuation/suffix variant of the same property.
TASK_B_TRIP_REVIEW_REQUIRED_ALIASES = [
    ("BOD017", "Ambrosia Otel Beach & Spa", "Ambrosia Hotel Beach & Spa"),
    ("BOD066", "Royal Asarlik Beach Hotel & Spa", "Royal Asarlik Beach Hotel"),
    ("BOD071", "Tropicana Beach Hotel", "Tropicana Beach"),
    ("BOD082", "Otel Gümüşlük", "Hotel Gumusluk"),
    ("BOD122", "Florida Otel", "Florida Hotel"),
    ("BOD136", "Zest Exclusive Hotel and Spa", "Zest Exclusive Hotel & Spa"),
    ("BOD140", "DoubleTree by Hilton Bodrum Işıl Club All-Inclusive Resort",
     "DoubleTree by Hilton Bodrum Isil Club Ultra All Inclusive Resort"),
    ("BOD151", "Sarpedor Boutique Hotel & SPA", "Sarpedor Boutique Hotel"),
    ("BOD170", "No:81 Hotel", "No81 Hotel"),
    ("BOD175", "Avantgarde Refined Hotel | Yalıkavak", "Avantgarde Refined Yalıkavak"),
]


def test_bod013_alias_is_loaded_and_verified():
    aliases = load_aliases()
    assert ("BOD013", "trip") in aliases
    row = aliases[("BOD013", "trip")][0]
    assert row["accepted_alias"] == "Bellazure Hotel"
    assert row["alias_type"] == "MANUAL_VERIFIED_ALIAS"


def test_bod013_trip_alias_rescues_the_conflict():
    nm, vstatus = resolve_entity_status(
        "BOD013", "trip", "Sentido Bellazure - Akyarlar, Bodrum / Turkey", "Bellazure Hotel")
    assert nm == "ALIAS_MATCH"
    assert vstatus == VALID_ENTITY


def test_alias_does_not_apply_on_a_different_platform():
    # The alias was verified for Trip.com only - it must NOT rescue the
    # same mismatch on google_travel or tripadvisor.
    nm, vstatus = resolve_entity_status(
        "BOD013", "google_travel", "Sentido Bellazure - Akyarlar, Bodrum / Turkey", "Bellazure Hotel")
    assert vstatus == WRONG_ENTITY


def test_alias_does_not_apply_to_a_different_hotel_id():
    # Some other hotel that happens to also detect as "Bellazure Hotel"
    # on Trip.com must NOT be silently accepted by BOD013's alias.
    assert is_accepted_alias("BOD999", "trip", "Bellazure Hotel") is False


def test_alias_requires_close_normalized_match_to_the_detected_name():
    # A near-miss of the accepted alias text should not match - this is a
    # lookup table, not a second round of fuzzy matching.
    assert is_accepted_alias("BOD013", "trip", "Completely Unrelated Hotel Name") is False


def test_selectum_and_la_blanche_regressions_are_unaffected_by_aliases():
    # No alias row exists for either pair - the brand-collision safety net
    # from phase 1 must still hold with the alias system layered on top.
    nm, vstatus = resolve_entity_status("BOD_X", "trip", "Selectum Colours", "Selectum Collection")
    assert vstatus == WRONG_ENTITY
    nm2, vstatus2 = resolve_entity_status("BOD_Y", "trip", "La Blanche Island", "La Blanche Resort")
    assert vstatus2 == WRONG_ENTITY


@pytest.mark.parametrize("hotel_id,expected_name,detected_name", PHASE3_TRIP_ALIASES)
def test_phase3_trip_wrong_entity_set_now_resolves_via_alias(hotel_id, expected_name, detected_name):
    # Section 18: the 5 previously-WRONG_ENTITY Trip.com hotels are the same
    # real property under a shorter/reordered Trip.com display name - each
    # got an explicit, hotel_id+platform-scoped alias rather than a looser
    # fuzzy-matching rule.
    nm, vstatus = resolve_entity_status(hotel_id, "trip", expected_name, detected_name)
    assert nm == "ALIAS_MATCH"
    assert vstatus == VALID_ENTITY


@pytest.mark.parametrize("hotel_id,expected_name,detected_name", PHASE3_TRIP_ALIASES)
def test_phase3_trip_aliases_do_not_leak_to_other_platforms(hotel_id, expected_name, detected_name):
    nm, vstatus = resolve_entity_status(hotel_id, "google_travel", expected_name, detected_name)
    assert vstatus != VALID_ENTITY or nm != "ALIAS_MATCH"


@pytest.mark.parametrize("hotel_id,expected_name,detected_name", TASK_B_TRIP_REVIEW_REQUIRED_ALIASES)
def test_task_b_review_required_set_resolves_via_alias(hotel_id, expected_name, detected_name):
    # Without the alias, these are NAME_REVIEW_REQUIRED (a name_match_status of
    # REVIEW_REQUIRED), not WRONG_ENTITY - confirms the alias override now also
    # covers that softer bucket, not just hard WRONG_ENTITY conflicts.
    from bodrum_intelligence.reviews.validation import entity_validation_status, name_match_status
    nm_without_alias = name_match_status(expected_name, detected_name)
    assert entity_validation_status(nm_without_alias) == NAME_REVIEW_REQUIRED

    nm, vstatus = resolve_entity_status(hotel_id, "trip", expected_name, detected_name)
    assert nm == "ALIAS_MATCH"
    assert vstatus == VALID_ENTITY


@pytest.mark.parametrize("hotel_id,expected_name,detected_name", TASK_B_TRIP_REVIEW_REQUIRED_ALIASES)
def test_task_b_review_required_aliases_do_not_leak_to_other_platforms(hotel_id, expected_name, detected_name):
    nm, vstatus = resolve_entity_status(hotel_id, "google_travel", expected_name, detected_name)
    assert vstatus != VALID_ENTITY or nm != "ALIAS_MATCH"
