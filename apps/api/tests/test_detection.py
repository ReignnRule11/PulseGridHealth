from app.services.detection import robust_anomaly

def test_insufficient_history_is_not_flagged():
    result = robust_anomaly([1, 1, 2], 10, min_history=6)
    assert result.is_candidate is False
    assert result.reason == "insufficient_history"

def test_known_large_increase_is_flagged():
    result = robust_anomaly([10, 11, 9, 10, 11, 10, 9], 25, min_history=6, threshold=3.5)
    assert result.is_candidate is True
    assert result.reason == "unusual_increase"

def test_zero_mad_does_not_fabricate_score():
    result = robust_anomaly([10, 10, 10, 10, 10, 10], 20, min_history=6)
    assert result.is_candidate is False
    assert result.anomaly_score is None
    assert result.reason == "zero_mad_requires_review"
