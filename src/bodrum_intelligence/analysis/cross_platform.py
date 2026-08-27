"""Phase E (Google Travel x Trip.com cross-platform) pure helper functions -
kept separate from the notebook so the core comparison rules are unit
testable without pandas/notebook execution.
"""
from __future__ import annotations


def hotel_coverage(google_ids: set[str], trip_ids: set[str]) -> dict[str, list[str]]:
    """No row-level merge (section E3) - just set membership per hotel_id."""
    return {
        "both": sorted(google_ids & trip_ids),
        "google_only": sorted(google_ids - trip_ids),
        "trip_only": sorted(trip_ids - google_ids),
    }


def rating_gap(google_mean: float | None, trip_mean_5: float | None) -> float | None:
    if google_mean is None or trip_mean_5 is None:
        return None
    return round(google_mean - trip_mean_5, 3)


# Explicit thresholds (section E7) - a divergence signal, never a "which
# platform is right" verdict.
def agreement_flag(gap: float | None) -> str:
    if gap is None:
        return "UNKNOWN"
    g = abs(gap)
    if g <= 0.3:
        return "HIGH_AGREEMENT"
    if g <= 0.7:
        return "MODERATE_AGREEMENT"
    return "DISAGREEMENT"


# Sample-size aware (section E8).
def support_flag(google_n: int, trip_n: int, min_n: int = 10) -> str:
    if google_n >= min_n and trip_n >= min_n:
        return "SUPPORTED_COMPARISON"
    return "LOW_SUPPORT"
