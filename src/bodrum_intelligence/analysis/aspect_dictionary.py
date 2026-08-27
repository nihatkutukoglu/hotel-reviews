"""Phase D9-D11: rule-based Turkish aspect taxonomy for the Google Travel
review corpus. Deliberately simple substring/phrase matching, not a
trained model - mention_rate is a recall-oriented signal, not sentiment.
"""
from __future__ import annotations

import re
import unicodedata

ASPECT_KEYWORDS: dict[str, list[str]] = {
    "STAFF": ["personel", "çalışan", "garson", "resepsiyon", "görevli", "müdür", "misafir ilişkileri"],
    "CLEANLINESS": ["temizlik", "temiz", "kirli", "pis", "lekeli", "çarşaf", "havlu", "toz", "oda temizliği"],
    "HYGIENE": ["hijyen", "hijyenik", "sinek", "böcek", "haşere", "kirli tabak", "kirli bardak"],
    "FOOD": ["yemek", "kahvaltı", "açık büfe", "restoran", "büfe", "lezzet", "tatlı", "ızgara", "meyve"],
    "ROOM": ["oda", "banyo", "duş", "minibar", "mobilya", "balkon"],
    "BED_COMFORT": ["yatak", "yastık", "uyku", "rahat", "rahatsız"],
    "BEACH_SEA": ["plaj", "deniz", "sahil", "koy", "iskele", "şezlong", "şemsiye"],
    "POOL": ["havuz", "aquapark", "kaydırak", "su parkı"],
    "SERVICE": ["hizmet", "servis", "sunum", "bekleme", "sipariş"],
    "PRICE_VALUE": ["fiyat", "ücret", "para", "pahalı", "uygun", "fiyat performans", "değer", "karşılığını"],
    "LOCATION": ["konum", "manzara", "merkez", "ulaşım", "koy", "doğa"],
    "FACILITIES": ["tesis", "alan", "lobi", "asansör", "koridor", "spa", "spor salonu"],
    "NOISE": ["gürültü", "ses", "müzik", "yüksek ses", "gece"],
    "FAMILY_KIDS": ["çocuk", "aile", "bebek", "mini club", "çocuk kulübü"],
    "ANIMATION_ENTERTAINMENT": ["animasyon", "aktivite", "etkinlik", "eğlence", "show", "şov"],
    "AIR_CONDITIONING": ["klima", "soğutma", "sıcak oda"],
    "CHECKIN_CHECKOUT": ["giriş", "çıkış", "check in", "check-in", "check out", "check-out", "oda hazır"],
    "RESERVATION": ["rezervasyon", "acente", "booking", "otelz", "ets", "iptal"],
    "REFUND_PAYMENT": ["iade", "ödeme", "kart", "provizyon", "ücret iadesi"],
    "TRANSPORT_TRANSFER": ["transfer", "servis aracı", "havaalanı", "taksi"],
    "MANAGEMENT": ["yönetim", "müdür", "yönetici", "işletme"],
    "COMMUNICATION": ["iletişim", "ulaşamadık", "geri dönüş", "cevap", "telefon"],
    "BAR_DRINKS": ["bar", "içecek", "alkol", "kokteyl", "bira", "soda"],
    "WIFI": ["wifi", "wi-fi", "internet"],
}

_NEGATION_MARKERS = ["değil", "yok", "olmadı", "yetersiz", "gelmedi", "vermedi", "yapmadı", "tavsiye etmem"]


def _fold(s: str) -> str:
    s = s.lower()
    s = s.translate(str.maketrans({"ı": "i", "İ": "i", "ş": "s", "ğ": "g", "ü": "u", "ö": "o", "ç": "c"}))
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")


_FOLDED_KEYWORDS = {
    aspect: [_fold(kw) for kw in kws] for aspect, kws in ASPECT_KEYWORDS.items()
}


def detect_aspects(text: str) -> set[str]:
    """Returns the set of aspects mentioned at least once in text."""
    if not text:
        return set()
    folded = _fold(text)
    found = set()
    for aspect, keywords in _FOLDED_KEYWORDS.items():
        if any(kw in folded for kw in keywords):
            found.add(aspect)
    return found


def has_negation_near(text: str, keyword: str, window: int = 40) -> bool:
    """Rough proxy: is a negation marker within `window` chars of an
    occurrence of keyword? Used only as a secondary signal, never presented
    as true sentiment (per the master prompt's explicit instruction)."""
    folded = _fold(text)
    kw = _fold(keyword)
    idx = folded.find(kw)
    if idx == -1:
        return False
    window_text = folded[max(0, idx - window): idx + len(kw) + window]
    return any(_fold(marker) in window_text for marker in _NEGATION_MARKERS)
