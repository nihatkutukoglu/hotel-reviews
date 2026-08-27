"""Phase B6 (Policies feature engineering): amenity detection purely from
raw `hizmetler` text evidence - never guessed, never inferred from hotel
name/category."""
from __future__ import annotations

AMENITY_KEYWORDS: dict[str, list[str]] = {
    "has_private_beach": ["private beach", "özel plaj"],
    "has_indoor_pool": ["indoor pool", "kapalı havuz"],
    "has_outdoor_pool": ["outdoor pool", "açık havuz"],
    "has_kids_pool": ["kids' pool", "kids pool", "çocuk havuzu"],
    "has_kids_club": ["kids' club", "kids club", "çocuk kulübü"],
    "has_playground": ["playground", "oyun alanı", "oyun parkı"],
    "has_spa": ["spa"],
    "has_sauna": ["sauna"],
    "has_gym": ["fitness", "gym"],
    "has_restaurant": ["restaurant", "restoran"],
    "has_bar": ["bar"],
    "has_wifi": ["wifi", "wi-fi", "internet"],
    "has_airport_pickup": ["airport pick", "havalimanı transfer", "airport shuttle"],
    "has_airport_dropoff": ["airport drop", "havalimanına transfer"],
    "has_parking": ["parking", "otopark"],
    "has_tennis": ["tennis", "tenis"],
    "has_diving": ["diving", "dalış"],
    "has_snorkeling": ["snorkel"],
    "has_childcare": ["childcare", "babysitting", "çocuk bakımı"],
    "has_conference_room": ["conference room", "meeting room", "toplantı salonu", "konferans"],
}


def detect_amenities(hizmetler_text: str) -> dict[str, bool]:
    """Returns {amenity_flag: bool}, true only when a keyword literally
    appears in hizmetler_text (case-insensitive)."""
    folded = (hizmetler_text or "").lower()
    return {flag: any(kw in folded for kw in keywords) for flag, keywords in AMENITY_KEYWORDS.items()}
