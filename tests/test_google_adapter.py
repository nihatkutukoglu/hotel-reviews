"""Tests the wrapper logic in google_travel_adapter.py without launching a
real browser: the legacy module's driver/scrape functions are replaced
with fakes, so what's actually under test is "does the adapter refuse to
scrape a WRONG_ENTITY page, and does it call through correctly otherwise".
"""
import types

import pytest

from bodrum_intelligence.reviews import google_travel_adapter as gta


class FakeDriver:
    def __init__(self):
        self.quit_called = False

    def get(self, url):
        pass

    def quit(self):
        self.quit_called = True


def make_fake_module(detected_name: str, yorumlari_cek_calls: list):
    def tarayici_olustur(headless):
        return FakeDriver()

    def otel_adini_al(driver):
        return detected_name

    def yorumlari_cek(driver, url, csv_dosyasi, max_reviews):
        yorumlari_cek_calls.append((url, csv_dosyasi, max_reviews))
        return 3

    m = types.SimpleNamespace(
        tarayici_olustur=tarayici_olustur,
        otel_adini_al=otel_adini_al,
        yorumlari_cek=yorumlari_cek,
        SAYFA_ACILIS_BEKLEMESI=0,
    )
    return m


@pytest.fixture(autouse=True)
def reset_module_cache(monkeypatch):
    monkeypatch.setattr(gta, "_MODULE", None)


def test_wrong_entity_never_calls_yorumlari_cek(monkeypatch, tmp_path):
    calls = []
    fake = make_fake_module("Tamamen Farkli Bir Otel", calls)
    monkeypatch.setattr(gta, "_module", lambda: fake)
    monkeypatch.setattr(gta, "DATA_RAW_DIR", tmp_path)

    result = gta.scrape_hotel("BOD001", "Aksoy Tas Ev", "Akyarlar", "https://www.google.com/travel/x")

    assert result["status"] == "WRONG_ENTITY"
    assert calls == []  # scraping must never have started


def test_validate_only_never_calls_yorumlari_cek(monkeypatch, tmp_path):
    calls = []
    fake = make_fake_module("Aksoy Tas Ev", calls)
    monkeypatch.setattr(gta, "_module", lambda: fake)
    monkeypatch.setattr(gta, "DATA_RAW_DIR", tmp_path)

    result = gta.scrape_hotel("BOD001", "Aksoy Tas Ev", "Akyarlar", "https://www.google.com/travel/x",
                               validate_only=True)

    assert result["validation_status"] == "VALID_ENTITY"
    assert calls == []


def test_valid_entity_scrapes_and_reports_rows_added(monkeypatch, tmp_path):
    calls = []
    fake = make_fake_module("Aksoy Tas Ev", calls)
    monkeypatch.setattr(gta, "_module", lambda: fake)
    monkeypatch.setattr(gta, "DATA_RAW_DIR", tmp_path)

    result = gta.scrape_hotel("BOD001", "Aksoy Tas Ev", "Akyarlar", "https://www.google.com/travel/x",
                               max_reviews=5)

    assert result["status"] == "COMPLETED"
    assert result["rows_added"] == 3
    assert len(calls) == 1
    assert calls[0][2] == 5  # max_reviews threaded through correctly
