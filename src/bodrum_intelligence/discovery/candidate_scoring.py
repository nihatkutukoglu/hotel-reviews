"""Transparent, explainable candidate scoring (section 12-13).

Score 0-100, built from named components - never a black-box decision.
Thresholds (section 13, tuned against the same brand-collision regressions
already guarded in validation.py):
    95-100  FOUND_EXACT
    85-94   FOUND_HIGH_CONFIDENCE
    70-84   REVIEW_REQUIRED
    <70     REJECTED_CANDIDATE (or NOT_FOUND if there was no candidate at all)
"""
from __future__ import annotations

from difflib import SequenceMatcher

from bodrum_intelligence.reviews.validation import normalize_name

FOUND_EXACT = "FOUND_EXACT"
FOUND_HIGH_CONFIDENCE = "FOUND_HIGH_CONFIDENCE"
REVIEW_REQUIRED = "REVIEW_REQUIRED"
REJECTED_CANDIDATE = "REJECTED_CANDIDATE"
NOT_FOUND = "NOT_FOUND"
BLOCKED = "BLOCKED"
ERROR = "ERROR"


def name_similarity(expected_name: str, detected_name: str) -> float:
    if not detected_name:
        return 0.0
    ne, nd = normalize_name(expected_name), normalize_name(detected_name)
    if ne == nd:
        return 1.0
    return SequenceMatcher(None, ne, nd).ratio()


def score_candidate(expected_name: str, detected_name: str, area: str = "",
                     area_match: bool | None = None) -> dict:
    """Returns {"name_similarity", "area_match", "candidate_score",
    "validation_status", "components"}.

    Area/address are secondary signals (section 8): area mismatch alone
    never rejects a candidate, it only nudges the score down a little
    when the name match is already borderline.
    """
    sim = name_similarity(expected_name, detected_name)
    name_component = round(sim * 90)  # name carries the large majority of the score
    area_component = 0
    if detected_name:
        if area_match is True:
            area_component = 10
        elif area_match is None:
            area_component = 5  # unknown/not-checked: neutral, not penalized
        # area_match is False -> 0, a mild nudge down, never a hard reject on its own
    score = min(100, name_component + area_component)

    if not detected_name:
        status = NOT_FOUND
    elif score >= 95:
        status = FOUND_EXACT
    elif score >= 85:
        status = FOUND_HIGH_CONFIDENCE
    elif score >= 70:
        status = REVIEW_REQUIRED
    else:
        status = REJECTED_CANDIDATE

    return {
        "name_similarity": round(sim, 4),
        "area_match": area_match,
        "candidate_score": score,
        "validation_status": status,
        "components": {"name_component": name_component, "area_component": area_component},
    }
