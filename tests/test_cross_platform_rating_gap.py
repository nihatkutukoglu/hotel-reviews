from bodrum_intelligence.analysis.cross_platform import agreement_flag, rating_gap, support_flag


def test_rating_gap_computation():
    assert rating_gap(4.5, 4.0) == 0.5
    assert rating_gap(3.0, 4.0) == -1.0


def test_rating_gap_none_when_either_side_missing():
    assert rating_gap(None, 4.0) is None
    assert rating_gap(4.0, None) is None


def test_agreement_thresholds_are_explicit_and_symmetric():
    assert agreement_flag(0.0) == "HIGH_AGREEMENT"
    assert agreement_flag(0.3) == "HIGH_AGREEMENT"
    assert agreement_flag(-0.3) == "HIGH_AGREEMENT"
    assert agreement_flag(0.31) == "MODERATE_AGREEMENT"
    assert agreement_flag(0.7) == "MODERATE_AGREEMENT"
    assert agreement_flag(0.71) == "DISAGREEMENT"
    assert agreement_flag(-1.5) == "DISAGREEMENT"


def test_agreement_flag_is_not_a_quality_verdict():
    # A large gap is a DIVERGENCE signal - the function must never return
    # anything implying one platform is "correct".
    result = agreement_flag(2.0)
    assert result in ("HIGH_AGREEMENT", "MODERATE_AGREEMENT", "DISAGREEMENT", "UNKNOWN")


def test_sample_size_aware_support_flag():
    assert support_flag(10, 10) == "SUPPORTED_COMPARISON"
    assert support_flag(9, 10) == "LOW_SUPPORT"
    assert support_flag(50, 3) == "LOW_SUPPORT"
