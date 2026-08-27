"""Explicit, manually-verified per-hotel/per-platform name aliases
(config/multiplatform_hotel_aliases.csv). This is a narrow, auditable
override for cases where a specific site legitimately displays a hotel
under a different name than the master dataset (e.g. Trip.com showing
"Bellazure Hotel" for BOD013's canonical
"Sentido Bellazure - Akyarlar, Bodrum / Turkey").

This must never become a general fuzzy-matching rule: an alias only
applies to the exact (hotel_id, platform) pair it was verified for, and
only when it matches the detected name closely (normalized comparison).
Brand-family collisions (Selectum Colours vs Selectum Collection, La
Blanche Island vs Resort) are never affected since no alias row exists
for them.
"""
from __future__ import annotations

from .common import CONFIG_DIR, read_csv_dicts
from .validation import (
    NAME_REVIEW_REQUIRED, VALID_ENTITY, WRONG_ENTITY, entity_validation_status, name_match_status,
    normalize_name,
)

ALIASES_CSV = CONFIG_DIR / "multiplatform_hotel_aliases.csv"

_cache: dict[tuple[str, str], list[dict]] | None = None


def _truthy(v: str) -> bool:
    return str(v).strip().lower() in ("true", "1", "yes")


def load_aliases() -> dict[tuple[str, str], list[dict]]:
    global _cache
    if _cache is not None:
        return _cache
    out: dict[tuple[str, str], list[dict]] = {}
    if ALIASES_CSV.exists():
        for row in read_csv_dicts(ALIASES_CSV):
            if not _truthy(row.get("verified", "")):
                continue
            key = (row["hotel_id"], row["platform"])
            out.setdefault(key, []).append(row)
    _cache = out
    return out


def is_accepted_alias(hotel_id: str, platform: str, detected_name: str) -> bool:
    for row in load_aliases().get((hotel_id, platform), []):
        if normalize_name(row["accepted_alias"]) == normalize_name(detected_name):
            return True
    return False


def resolve_entity_status(hotel_id: str, platform: str, expected_name: str,
                           detected_name: str) -> tuple[str, str]:
    """Returns (name_match_status, entity_validation_status), applying a
    verified per-hotel/per-platform alias only as a last resort when the
    canonical name would otherwise be rejected as WRONG_ENTITY or held back
    as NAME_REVIEW_REQUIRED (e.g. a plain Otel/Hotel translation, a dropped
    "& Spa" suffix, or a punctuation-only difference - never a competing
    brand: those never get an alias row in the first place).
    """
    nm = name_match_status(expected_name, detected_name)
    vstatus = entity_validation_status(nm)
    if vstatus in (WRONG_ENTITY, NAME_REVIEW_REQUIRED) and is_accepted_alias(hotel_id, platform, detected_name):
        return "ALIAS_MATCH", VALID_ENTITY
    return nm, vstatus
