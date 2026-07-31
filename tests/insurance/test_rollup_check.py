import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "insurance"))
import rollup_check as rc


def test_cumulative_sums_through_day():
    daily = [10.0, 5.0, 0.0, 8.0]
    assert rc.cumulative(daily, 1) == 10.0
    assert rc.cumulative(daily, 3) == 15.0
    assert rc.cumulative(daily, 4) == 23.0


def test_match_day_finds_cutoff():
    daily = [10.0, 5.0, 0.0, 8.0]  # cum: 10,15,15,23
    assert rc.match_day(daily, 15.0) == 2  # first day reaching 15
    assert rc.match_day(daily, 23.0) == 4


def test_match_day_none_when_no_match():
    daily = [10.0, 5.0]  # cum: 10,15
    assert rc.match_day(daily, 999.0) is None


def test_reconcile_flags_ok_and_mismatch():
    team = {"①": [10.0, 5.0, 8.0], "②": [3.0, 3.0, 3.0]}
    board = {"①": 15.0, "②": 100.0}  # ① matches day2; ② no match
    out = rc.reconcile(team, board, tol=0.5)
    assert out["①"]["ok"] is True and out["①"]["matched_day"] == 2
    assert out["②"]["ok"] is False and out["②"]["matched_day"] is None
    assert out["②"]["full_total"] == 9.0
