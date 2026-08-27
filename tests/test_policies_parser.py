"""Tests the tolerant, label-based policy-field reader in
policies_adapter.py.

Phase 1: the underlying politikalar.py aborts the ENTIRE hotel if even one
field is missing (see politikalar.py:csvye_yaz) - this adapter must
instead produce a partial row when only some fields fail.

Phase 2: live DOM inspection found Trip.com's *value wording* for several
fields (child policy, crib/extra-bed, breakfast, pets, service animals,
age requirement) varies per hotel / changed over time, so those 6 fields
are now matched by their stable left-hand LABEL via driver.execute_script,
not by a value-text prefix. Check-in/check-out/license still use the
original m.ilk_metin prefix-matching (still valid, unchanged).
"""
import types

from selenium.common.exceptions import TimeoutException

from bodrum_intelligence.reviews.policies_adapter import _read_policy_fields_tolerant


def make_fake_module(ilk_metin_fn, label_values: dict):
    def temizle(s):
        return (s or "").strip()

    return types.SimpleNamespace(ilk_metin=ilk_metin_fn, temizle=temizle), label_values


class FakeDriver:
    def __init__(self, label_values: dict):
        self.label_values = label_values

    def execute_script(self, script, label):
        return self.label_values.get(label)


def test_all_fields_present():
    def ilk_metin(driver, xpath):
        return "some-value"

    m, _ = make_fake_module(ilk_metin, {})
    driver = FakeDriver({
        "Child policies": "Children of all ages are welcome",
        "Cribs and Extra Beds": "Extra bed and crib policies may vary",
        "Breakfast": "Option: Buffet",
        "Pets": "Pets are not allowed",
        "Service animals": "Service animals are not allowed",
        "Age Requirements": "The main guest must be at least 18",
    })
    row, missing = _read_policy_fields_tolerant(m, driver, "Test Hotel", "Wifi; Pool")

    assert missing == []
    assert row["otel_adi"] == "Test Hotel"
    assert row["hizmetler"] == "Wifi; Pool"
    assert row["giris_saati"] == "some-value"
    assert row["cocuk_politikası"] == "Children of all ages are welcome"
    assert row["bebek_ve_ek_yatak"] == "Extra bed and crib policies may vary"


def test_missing_license_number_does_not_lose_the_other_fields():
    def ilk_metin(driver, xpath):
        if "License number" in xpath:
            raise TimeoutException("not found")
        return "some-value"

    m, _ = make_fake_module(ilk_metin, {})
    driver = FakeDriver({
        "Child policies": "Children of all ages are welcome",
        "Cribs and Extra Beds": "Extra bed policy text",
        "Breakfast": "Option: Buffet",
        "Pets": "Pets are not allowed",
        "Service animals": "Service animals are not allowed",
        "Age Requirements": "Must be at least 18",
    })
    row, missing = _read_policy_fields_tolerant(m, driver, "Test Hotel", "Wifi")

    assert missing == ["sertifika_numarasi"]
    assert row["sertifika_numarasi"] == ""
    assert row["giris_saati"] == "some-value"  # unaffected


def test_label_based_field_missing_from_dom_is_reported_but_others_survive():
    # Simulates the real bug found live: Trip.com's crib/extra-bed wording
    # changed and the label itself wasn't present for this hotel either.
    def ilk_metin(driver, xpath):
        return "some-value"

    m, _ = make_fake_module(ilk_metin, {})
    driver = FakeDriver({
        "Child policies": "Children of all ages are welcome",
        # "Cribs and Extra Beds" deliberately absent
        "Breakfast": "Option: Buffet",
        "Pets": "Pets are not allowed",
        "Service animals": "Service animals are not allowed",
        "Age Requirements": "Must be at least 18",
    })
    row, missing = _read_policy_fields_tolerant(m, driver, "Test Hotel", "Wifi")

    assert "bebek_ve_ek_yatak" in missing
    assert row["bebek_ve_ek_yatak"] == ""
    assert row["cocuk_politikası"] == "Children of all ages are welcome"  # unaffected


def test_all_fields_missing_still_returns_a_row_not_an_exception():
    def ilk_metin(driver, xpath):
        raise TimeoutException("not found")

    m, _ = make_fake_module(ilk_metin, {})
    driver = FakeDriver({})
    row, missing = _read_policy_fields_tolerant(m, driver, "Test Hotel", "")

    assert len(missing) == 9  # 3 via ilk_metin + 6 label-based fields
    assert row["otel_adi"] == "Test Hotel"
