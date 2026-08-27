"""Integration-level test: politikalar.py's own writer would raise and
save NOTHING if even one field were missing. policies_adapter.scrape_hotel
must instead always write a CSV row for a VALID_ENTITY hotel, with
whatever fields were actually found - this is the section 15 fix.
"""
import csv
import types

import pytest
from selenium.common.exceptions import TimeoutException

from bodrum_intelligence.reviews import policies_adapter as pa


class FakeDriver:
    def __init__(self, label_values):
        self.label_values = label_values

    def get(self, url):
        pass

    def execute_script(self, script, label=None):
        if label is None:
            return None
        return self.label_values.get(label)

    def quit(self):
        pass


def make_fake_module(detected_name, ilk_metin_ok_fields, label_values, hizmetler="Wifi; Pool"):
    def tarayici_olustur(headless):
        return FakeDriver(label_values)

    def arama_butonuna_bas(driver):
        pass

    def otel_adini_al(driver):
        return detected_name

    def bes_kademe_asagi_in(driver):
        pass

    def hizmetleri_al(driver):
        return hizmetler

    def politikalar_sekmesini_ac(driver):
        pass

    def ilk_metin(driver, xpath):
        if "After" in xpath and "giris_saati" in ilk_metin_ok_fields:
            return "After 15:00"
        if "Before" in xpath and "cıkıs_saati" in ilk_metin_ok_fields:
            return "Before 12:00"
        if "License number" in xpath and "sertifika_numarasi" in ilk_metin_ok_fields:
            return "License number: 123"
        raise TimeoutException("not found")

    def temizle(s):
        return (s or "").strip()

    return types.SimpleNamespace(
        tarayici_olustur=tarayici_olustur, arama_butonuna_bas=arama_butonuna_bas,
        otel_adini_al=otel_adini_al, bes_kademe_asagi_in=bes_kademe_asagi_in,
        hizmetleri_al=hizmetleri_al, politikalar_sekmesini_ac=politikalar_sekmesini_ac,
        ilk_metin=ilk_metin, temizle=temizle,
        CSV_ALANLARI=("otel_adi", "giris_saati", "cıkıs_saati", "cocuk_politikası",
                      "bebek_ve_ek_yatak", "kahvalti", "evcil_hayvan", "hizmet_hayvanları",
                      "yas_sarti", "sertifika_numarasi", "hizmetler"),
    )


@pytest.fixture(autouse=True)
def reset_module_cache(monkeypatch):
    monkeypatch.setattr(pa, "_MODULE", None)


def test_missing_fields_still_produce_a_saved_row(monkeypatch, tmp_path):
    # Only check-in and license resolve; everything else (checkout, child
    # policy, crib, breakfast, pets, service animals, age) is missing -
    # the legacy csvye_yaz would have raised and saved nothing at all.
    fake = make_fake_module(
        detected_name="Test Hotel",
        ilk_metin_ok_fields={"giris_saati", "sertifika_numarasi"},
        label_values={},
    )
    monkeypatch.setattr(pa, "_module", lambda: fake)
    monkeypatch.setattr(pa, "DATA_RAW_DIR", tmp_path)

    result = pa.scrape_hotel("BOD999", "Test Hotel", "Akyarlar", "https://www.trip.com/hotels/x")

    assert result["status"] == "PARTIAL"
    assert result["rows_added"] == 1

    out_files = list((tmp_path / "hotel_policies" / "trip").glob("BOD999_*.csv"))
    assert len(out_files) == 1
    with open(out_files[0], encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1
    assert rows[0]["giris_saati"] == "After 15:00"
    assert rows[0]["cıkıs_saati"] == ""  # missing field saved as empty, not a crash
    assert rows[0]["policy_status"] == "PARTIAL"
    assert rows[0]["has_checkin"] == "True"
    assert rows[0]["has_checkout"] == "False"


def test_wrong_entity_writes_nothing(monkeypatch, tmp_path):
    fake = make_fake_module(detected_name="Completely Different Hotel",
                             ilk_metin_ok_fields=set(), label_values={})
    monkeypatch.setattr(pa, "_module", lambda: fake)
    monkeypatch.setattr(pa, "DATA_RAW_DIR", tmp_path)

    result = pa.scrape_hotel("BOD999", "Test Hotel", "Akyarlar", "https://www.trip.com/hotels/x")

    assert result["status"] == "WRONG_ENTITY"
    assert not list(tmp_path.rglob("*.csv"))
