"""google/yorum.py:otel_adini_al used to fall back to the literal string
"Bilinmeyen otel" ("Unknown hotel") when none of its selectors matched -
live testing found ALL 3 old selectors had gone stale against Google's
current DOM, so every real hotel silently got this fake placeholder name,
which the entity validator then (correctly, if accidentally) rejected as
a CONFLICT/WRONG_ENTITY.

Phase 2 repaired otel_adini_al to return "" instead (see google/yorum.py),
and google_travel_adapter.py must treat "" as a distinct
NAME_DETECTION_FAILED technical failure - never as a valid identity, and
never scrape past it.
"""
import types

import pytest

from bodrum_intelligence.reviews import google_travel_adapter as gta
from bodrum_intelligence.reviews.validation import NAME_DETECTION_FAILED


class FakeDriver:
    def get(self, url):
        pass

    def quit(self):
        pass


def make_fake_module(detected_name: str, yorumlari_cek_calls: list):
    def tarayici_olustur(headless):
        return FakeDriver()

    def otel_adini_al(driver):
        return detected_name

    def yorumlari_cek(driver, url, csv_dosyasi, max_reviews):
        yorumlari_cek_calls.append((url, csv_dosyasi, max_reviews))
        return 3

    return types.SimpleNamespace(
        tarayici_olustur=tarayici_olustur, otel_adini_al=otel_adini_al,
        yorumlari_cek=yorumlari_cek, SAYFA_ACILIS_BEKLEMESI=0,
    )


@pytest.fixture(autouse=True)
def reset_module_cache(monkeypatch):
    monkeypatch.setattr(gta, "_MODULE", None)


def test_empty_detected_name_is_name_detection_failed_not_wrong_entity(monkeypatch, tmp_path):
    calls = []
    fake = make_fake_module("", calls)
    monkeypatch.setattr(gta, "_module", lambda: fake)
    monkeypatch.setattr(gta, "DATA_RAW_DIR", tmp_path)

    result = gta.scrape_hotel("BOD001", "Aksoy Tas Ev", "Akyarlar", "https://www.google.com/travel/x")

    assert result["status"] == NAME_DETECTION_FAILED
    assert result["validation_status"] == NAME_DETECTION_FAILED
    assert calls == []  # never scraped


def test_the_old_fake_placeholder_string_would_still_be_rejected_if_it_ever_reappeared(monkeypatch, tmp_path):
    # Defense in depth: even if otel_adini_al ever regresses back to
    # returning a literal placeholder instead of "", it must never be
    # accepted as a valid identity for any real expected hotel name.
    calls = []
    fake = make_fake_module("Bilinmeyen otel", calls)
    monkeypatch.setattr(gta, "_module", lambda: fake)
    monkeypatch.setattr(gta, "DATA_RAW_DIR", tmp_path)

    result = gta.scrape_hotel("BOD001", "Aksoy Tas Ev", "Akyarlar", "https://www.google.com/travel/x")

    assert result["status"] != "COMPLETED"
    assert calls == []
