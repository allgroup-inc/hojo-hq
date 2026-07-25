import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "insurance"))
import audit_reflection as a


def test_detect_negative_flags_negative_working_hours():
    records = [
        {"metric": "実稼働時間", "coord": "H46", "area": "ALL委託", "value": -283.0},
        {"metric": "実稼働時間", "coord": "C46", "area": "豊見城", "value": 627.5},
    ]
    out = a.detect_negative_anomalies(records)
    assert len(out) == 1
    assert out[0]["coord"] == "H46"
    assert out[0]["reason"] == "negative"


def test_detect_negative_ignores_diff_metric_that_may_be_negative():
    # 現差異は負値が正常にあり得るので NONNEG に含めない
    records = [{"metric": "現差異", "coord": "F10", "area": "嘉手納", "value": -90.7}]
    assert a.detect_negative_anomalies(records) == []


def test_detect_blanks_flags_none():
    records = [
        {"metric": "予算ANP", "coord": "C11", "area": "嘉手納", "value": None},
        {"metric": "予算ANP", "coord": "H11", "area": "特殊", "value": 790.0},
    ]
    out = a.detect_blanks(records)
    assert len(out) == 1 and out[0]["coord"] == "C11"


def test_check_rollup_matches_within_tolerance():
    r = a.check_rollup([100.0, 50.0, 25.0], 175.4, tol=1.0)
    assert r["ok"] is True
    assert abs(r["sum_parts"] - 175.0) < 1e-9


def test_check_rollup_flags_mismatch():
    r = a.check_rollup([100.0, 50.0], 200.0, tol=1.0)
    assert r["ok"] is False
    # diff = sum_parts - total = 150 - 200 = -50 (parts short of total)
    assert abs(r["diff"] - (-50.0)) < 1e-9
