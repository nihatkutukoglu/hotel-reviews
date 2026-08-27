from bodrum_intelligence.reviews.policies_adapter import compute_policy_status_and_coverage

ALL_FIELDS = ["giris_saati", "cıkıs_saati", "cocuk_politikası", "bebek_ve_ek_yatak",
              "kahvalti", "evcil_hayvan", "hizmet_hayvanları", "yas_sarti", "sertifika_numarasi"]


def test_complete_when_nothing_missing():
    status, coverage = compute_policy_status_and_coverage([], has_facilities=True)
    assert status == "COMPLETE"
    assert all(coverage.values())


def test_partial_when_some_fields_missing():
    status, coverage = compute_policy_status_and_coverage(["cıkıs_saati", "yas_sarti"], has_facilities=True)
    assert status == "PARTIAL"
    assert coverage["has_checkout"] is False
    assert coverage["has_age_rule"] is False
    assert coverage["has_checkin"] is True  # unaffected fields stay True


def test_valid_entity_no_policy_data_when_everything_missing():
    status, coverage = compute_policy_status_and_coverage(ALL_FIELDS, has_facilities=False)
    assert status == "VALID_ENTITY_NO_POLICY_DATA"
    assert not any(v for k, v in coverage.items() if k != "has_facilities")


def test_partial_not_no_policy_data_when_facilities_found_even_if_all_fields_missing():
    # A hotel with a populated amenities list but zero readable policy
    # text fields still has *some* data - it should not be misreported as
    # having no policy data at all.
    status, coverage = compute_policy_status_and_coverage(ALL_FIELDS, has_facilities=True)
    assert status == "PARTIAL"
    assert coverage["has_facilities"] is True
