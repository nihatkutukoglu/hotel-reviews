"""Confirms the 5 previously-WRONG_ENTITY Trip.com hotels (BOD051/055/059/
072/073) resolve via their explicit aliases, and that this never leaks
into a different platform or a different hotel_id - see also
test_manual_alias_matching.py for the original phase-3 regression suite
this extends.
"""
import pytest

from bodrum_intelligence.reviews.aliases import is_accepted_alias, resolve_entity_status
from bodrum_intelligence.reviews.validation import VALID_ENTITY, WRONG_ENTITY

CASES = [
    ("BOD051", "Faros Bodrum Hotel Göltürkbükü", "Faros Hotel Bodrum - Special Category"),
    ("BOD055", "Lavinya Otel Göltürkbükü", "Lavinya Otel"),
    ("BOD059", "Bodrum Hotel Baba", "Hotel Baba"),
    ("BOD072", "VERY CHIC BODRUM", "Very Chic Bodrum Adult Only"),
    ("BOD073", "Arriba Apartment & Restaurant & Bungalows", "Arriba Apart Bungalow Restaurant"),
]


@pytest.mark.parametrize("hotel_id,expected,detected", CASES)
def test_alias_resolves_on_trip(hotel_id, expected, detected):
    nm, status = resolve_entity_status(hotel_id, "trip", expected, detected)
    assert nm == "ALIAS_MATCH"
    assert status == VALID_ENTITY


@pytest.mark.parametrize("hotel_id,expected,detected", CASES)
def test_alias_isolated_to_trip_platform(hotel_id, expected, detected):
    _nm, status = resolve_entity_status(hotel_id, "google_travel", expected, detected)
    assert status == WRONG_ENTITY


@pytest.mark.parametrize("hotel_id,_expected,detected", CASES)
def test_alias_isolated_to_its_own_hotel_id(hotel_id, _expected, detected):
    assert is_accepted_alias("BOD999", "trip", detected) is False
