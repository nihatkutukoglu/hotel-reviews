"""Tests the wrapper logic in tripadvisor_adapter.py without launching a
real browser (see test_google_adapter.py for the shared rationale)."""
import types

import pytest

from bodrum_intelligence.reviews import tripadvisor_adapter as taa


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
        return (9, 4)  # (toplam_cekilen, toplam_kaydedilen) - tuple return, unlike the other two scripts

    return types.SimpleNamespace(
        tarayici_olustur=tarayici_olustur, otel_adini_al=otel_adini_al,
        yorumlari_cek=yorumlari_cek, SAYFA_ACILIS_BEKLEMESI=0,
    )


@pytest.fixture(autouse=True)
def reset_module_cache(monkeypatch):
    monkeypatch.setattr(taa, "_MODULE", None)


def test_wrong_entity_never_scrapes(monkeypatch, tmp_path):
    calls = []
    fake = make_fake_module("Yanlis Otel", calls)
    monkeypatch.setattr(taa, "_module", lambda: fake)
    monkeypatch.setattr(taa, "DATA_RAW_DIR", tmp_path)

    result = taa.scrape_hotel("BOD007", "Kefaluka Resort", "Akyarlar",
                               "https://www.tripadvisor.com/Hotel_Review-x.html")

    assert result["status"] == "WRONG_ENTITY"
    assert calls == []


def test_valid_entity_uses_the_second_tuple_element_as_rows_added(monkeypatch, tmp_path):
    calls = []
    fake = make_fake_module("Kefaluka Resort", calls)
    monkeypatch.setattr(taa, "_module", lambda: fake)
    monkeypatch.setattr(taa, "DATA_RAW_DIR", tmp_path)

    result = taa.scrape_hotel("BOD007", "Kefaluka Resort", "Akyarlar",
                               "https://www.tripadvisor.com/Hotel_Review-x.html")

    assert result["status"] == "COMPLETED"
    assert result["rows_added"] == 4  # not 9 - must be the *newly saved* count, not the fetched count
