"""Tests the wrapper logic in trip_adapter.py without launching a real
browser (see test_google_adapter.py for the shared rationale)."""
import types

import pytest

from bodrum_intelligence.reviews import trip_adapter as ta


class FakeDriver:
    def get(self, url):
        pass

    def quit(self):
        pass


def make_fake_module(detected_name: str, yorumlari_cek_calls: list, takvimi_kapat_calls: list):
    def tarayici_olustur(headless):
        return FakeDriver()

    def takvimi_kapat(driver):
        takvimi_kapat_calls.append(driver)

    def otel_adini_al(driver):
        return detected_name

    def yorumlari_cek(driver, url, csv_dosyasi, max_reviews):
        yorumlari_cek_calls.append((url, csv_dosyasi, max_reviews))
        return 7

    return types.SimpleNamespace(
        tarayici_olustur=tarayici_olustur, takvimi_kapat=takvimi_kapat,
        otel_adini_al=otel_adini_al, yorumlari_cek=yorumlari_cek,
    )


@pytest.fixture(autouse=True)
def reset_module_cache(monkeypatch):
    monkeypatch.setattr(ta, "_MODULE", None)


def test_takvimi_kapat_runs_before_name_check(monkeypatch, tmp_path):
    scrape_calls, calendar_calls = [], []
    fake = make_fake_module("Kefaluka Resort", scrape_calls, calendar_calls)
    monkeypatch.setattr(ta, "_module", lambda: fake)
    monkeypatch.setattr(ta, "DATA_RAW_DIR", tmp_path)

    ta.scrape_hotel("BOD007", "Kefaluka Resort", "Akyarlar", "https://www.trip.com/hotels/x")

    assert len(calendar_calls) == 1


def test_wrong_entity_never_scrapes(monkeypatch, tmp_path):
    scrape_calls, calendar_calls = [], []
    fake = make_fake_module("Baska Bir Otel", scrape_calls, calendar_calls)
    monkeypatch.setattr(ta, "_module", lambda: fake)
    monkeypatch.setattr(ta, "DATA_RAW_DIR", tmp_path)

    result = ta.scrape_hotel("BOD007", "Kefaluka Resort", "Akyarlar", "https://www.trip.com/hotels/x")

    assert result["status"] == "WRONG_ENTITY"
    assert scrape_calls == []


def test_valid_entity_threads_max_reviews_through(monkeypatch, tmp_path):
    scrape_calls, calendar_calls = [], []
    fake = make_fake_module("Kefaluka Resort", scrape_calls, calendar_calls)
    monkeypatch.setattr(ta, "_module", lambda: fake)
    monkeypatch.setattr(ta, "DATA_RAW_DIR", tmp_path)

    result = ta.scrape_hotel("BOD007", "Kefaluka Resort", "Akyarlar", "https://www.trip.com/hotels/x",
                              max_reviews=10)

    assert result["status"] == "COMPLETED"
    assert result["rows_added"] == 7
    assert scrape_calls[0][2] == 10
