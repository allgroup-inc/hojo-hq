"""U3 fetch guard(scripts/guard_subsidies.py / fetch_jgrants.py / fetch_local.py / update.yml)の検査。

設計 v1.2(判断事項 A〜I 決裁 2026-10-11)と最終レビュー I-1〜I-8 に従う。
- ネットワークは使わない(urlopen / http_get / robots_ok を差し替える)。
- data/subsidies.json には触れない(OUT_PATH を一時ディレクトリに差し替える)。
- 10 月 5 日の事故は git 履歴から取った実データ fixture で再現する。
- C2(push 対象の HEAD blob)/ C3(公開物)の同一性は一時 git リポジトリで実演する。
禁止語の実文字列はこのファイルに書かない。
"""
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
FIX = Path(__file__).resolve().parent / "fixtures"
sys.path.insert(0, str(SCRIPTS))

import guard_subsidies as g  # noqa: E402
import fetch_jgrants as fj  # noqa: E402
import fetch_local as fl  # noqa: E402

PREV = json.loads((FIX / "subsidies_20261005_prev.json").read_text(encoding="utf-8"))   # c9b15ff63: 145 件
BAD = json.loads((FIX / "subsidies_20261005_bad.json").read_text(encoding="utf-8"))     # 0a002ff96: 17 件
STATUS_1005 = json.loads((FIX / "fetch_status_20261005.json").read_text(encoding="utf-8"))
STATUS_OK = json.loads(json.dumps(STATUS_1005))
STATUS_OK["jgrants"].update({"failed": 0, "kinds": {}, "failed_keywords": [], "items": 128})


def codes(errors):
    return sorted({e.split()[0] for e in errors})


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


# ── 定数(判断事項 D)─────────────────────────────────────────────────────
def test_constants_match_decision_d():
    assert (g.MIN_TOTAL, g.MIN_JGRANTS, g.MAX_DROP_PCT, g.SOURCE_MIN, g.SOURCE_DROP_PCT) == (100, 80, 15, 5, 50)
    assert g.REQUIRED_FIELDS == ("id", "name", "deadline", "source_url", "status", "tag")


def test_const_cli(capsys):
    assert g.main(["g", "const", "MIN_TOTAL"]) == 0
    assert capsys.readouterr().out.strip() == "100"
    assert g.main(["g", "const", "NOPE"]) == 2


# ── selftest(正例・負例を内蔵。本番 step の冒頭でも毎回走る)────────────────
def test_selftest_passes(capsys):
    assert g.selftest() == 0
    out = capsys.readouterr().out
    assert "RESULT: PASS" in out and "NG " not in out


def test_selftest_detects_broken_case(monkeypatch, capsys):
    """負例の負例: ケースの期待値を壊すと selftest が FAIL する(検査が効いている証跡)。"""
    broken = list(g.SELFTEST_CASES)
    name, prev, new, st, _ = broken[0]
    broken[0] = (name, prev, new, st, ["G4"])
    monkeypatch.setattr(g, "SELFTEST_CASES", broken)
    assert g.selftest() == 1
    assert "RESULT: FAIL" in capsys.readouterr().out


# ── 10 月 5 日の事故(実データ)────────────────────────────────────────────
def test_incident_20261005_is_blocked():
    errors, _, info = g.check_data(PREV, BAD, STATUS_1005)
    assert codes(errors) == ["G1", "G2", "G3", "G4"]
    assert info["prev_total"] == 145 and info["new_total"] == 17 and info["new_jgrants"] == 0
    assert any("66/66" in e for e in errors)


def test_incident_cli_exit_1(tmp_path, capsys):
    args = ["g", "check", "--prev", str(FIX / "subsidies_20261005_prev.json"),
            "--new", str(FIX / "subsidies_20261005_bad.json"), "--status", str(FIX / "fetch_status_20261005.json")]
    assert g.main(args) == 1
    assert "RESULT: FAIL" in capsys.readouterr().out


def test_one_directional_recovery_from_incident_baseline():
    """prev が事故データ(17 件)でも、新データが健全(145 件)なら PASS して自然に回復する(判断事項 I)。"""
    errors, _, _ = g.check_data(BAD, PREV, STATUS_OK)
    assert errors == []


def test_normal_same_data_passes(capsys):
    errors, warnings, _ = g.check_data(PREV, PREV, STATUS_OK)
    assert errors == []


# ── 境界値(§7)──────────────────────────────────────────────────────────
@pytest.mark.parametrize("prev,new,expected", [
    (100, 85, False), (100, 84, True), (145, 124, False), (145, 123, True),
    (143, 122, False), (143, 121, True), (145, 17, True), (143, 150, False), (1, 1, False),
])
def test_drop_rule_boundaries(prev, new, expected):
    assert g.drop_exceeds(prev, new, g.MAX_DROP_PCT) is expected


def _mk(n_jg, pref=8, ric=9):
    return g._mk(n_jg, pref=pref, ric=ric)


@pytest.mark.parametrize("prev_jg,new_jg,expected", [
    (183, 153, []),        # 200→170 = 15.00% → PASS(等号)
    (183, 152, ["G4"]),    # 200→169 = 15.50% → FAIL
    (128, 107, []),        # 145→124
    (128, 106, ["G4"]),    # 145→123
])
def test_g4_total_boundaries(prev_jg, new_jg, expected):
    errors, _, _ = g.check_data(_mk(prev_jg), _mk(new_jg), g._st())
    assert codes(errors) == expected


@pytest.mark.parametrize("pref,ric,expected", [
    (4, 9, []), (3, 9, ["G5"]), (8, 5, []), (8, 4, ["G5"]), (0, 9, ["G5"]),
])
def test_g5_source_boundaries(pref, ric, expected):
    errors, _, _ = g.check_data(_mk(128), _mk(128, pref=pref, ric=ric), g._st())
    assert codes(errors) == expected


def test_g5_not_applied_below_source_min():
    errors, _, _ = g.check_data(_mk(128, pref=4), _mk(128, pref=0), g._st())
    assert errors == []


@pytest.mark.parametrize("total_jg,expected", [(83, []), (82, ["G2"])])
def test_g2_boundary(total_jg, expected):
    errors, _, _ = g.check_data(_mk(total_jg), _mk(total_jg), g._st())
    assert codes(errors) == expected


@pytest.mark.parametrize("jg,expected", [(80, []), (79, ["G3"])])
def test_g3_boundary(jg, expected):
    errors, _, _ = g.check_data(_mk(100, pref=30, ric=30), _mk(jg, pref=30, ric=30), g._st())
    assert codes(errors) == expected


# ── G1: status ───────────────────────────────────────────────────────────
@pytest.mark.parametrize("status,expected_substr", [
    (None, "status ファイルが無い"),
    ({"schema_version": 1}, "jgrants が無い"),
    (g._st(no_local=True), "local が無い"),
    (g._st(failed=1), "1/66"),
    (g._st(incomplete=True), "incomplete"),
    (g._st(local_incomplete=True), "local_incomplete"),
    (g._st(schema=2), "schema_version"),
    (g._st(done=60), "クエリ数が不正"),
    (g._st(queries=0), "クエリ数が不正"),
    ({**g._st(), "jgrants": {**g._st()["jgrants"], "failed": "0"}}, "failed が数値でない"),
    (g._st(drop_label="沖縄県(産業・公募補助金)"), "取得記録が status に無い"),
])
def test_g1_status_cases(status, expected_substr):
    errors, _, _ = g.check_data(_mk(128), _mk(128), status)
    assert "G1" in codes(errors)
    assert any(expected_substr in e for e in errors)


def test_g1_robots_skip_of_source_with_previous_items_fails():
    errors, _, _ = g.check_data(_mk(128), _mk(128, pref=0), g._st(pref_skip=True))
    assert codes(errors) == ["G1", "G5"]
    assert any("robots 不許可" in e for e in errors)


def test_g1_failure_of_source_with_zero_previous_items_is_only_warning():
    st = g._st()
    st["local"]["naha_city"]["ok"] = False
    errors, warnings, _ = g.check_data(_mk(128), _mk(128), st)
    assert errors == []
    assert any("那覇市" in w for w in warnings)


# ── G0 / snapshot ────────────────────────────────────────────────────────
def test_snapshot_ok_copies_file(tmp_path, capsys):
    src = tmp_path / "subsidies.json"
    src.write_text(json.dumps(PREV, ensure_ascii=False), encoding="utf-8")
    dst = tmp_path / "prev.json"
    assert g.main(["g", "snapshot", "--src", str(src), "--dst", str(dst)]) == 0
    assert sha(src) == sha(dst)


@pytest.mark.parametrize("content", [None, "{not json", '{"items": []}', '{"count": 3}', "[]"])
def test_snapshot_g0_fails_closed(tmp_path, content, capsys):
    src = tmp_path / "subsidies.json"
    if content is not None:
        src.write_text(content, encoding="utf-8")
    dst = tmp_path / "prev.json"
    assert g.main(["g", "snapshot", "--src", str(src), "--dst", str(dst)]) == 1
    assert not dst.exists()
    assert "G0" in capsys.readouterr().out


def test_check_with_unreadable_prev_fails(tmp_path, capsys):
    new = tmp_path / "new.json"
    new.write_text(json.dumps(PREV, ensure_ascii=False), encoding="utf-8")
    st = tmp_path / "status.json"
    st.write_text(json.dumps(STATUS_OK), encoding="utf-8")
    assert g.main(["g", "check", "--prev", str(tmp_path / "missing.json"), "--new", str(new), "--status", str(st)]) == 1
    assert "G0" in capsys.readouterr().out


# ── G6 ──────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("kw", [dict(dup=True), dict(drop_field="source_url"), dict(bad_count=True), dict(bad_by_source=True)])
def test_g6_cases(kw):
    errors, _, _ = g.check_data(_mk(128), g._mk(128, **kw), g._st())
    assert codes(errors) == ["G6"]


@pytest.mark.parametrize("mutate", [
    lambda d: d["items"].append("not-a-dict"),
    lambda d: d.__setitem__("by_source", {"jGrants": "128"}),
    lambda d: d.__setitem__("by_source", [1, 2]),
    lambda d: d.__setitem__("items", [1, 2, 3]),
])
def test_g6_type_errors_are_reported_not_raised(mutate):
    """M1: 型が違っても例外で落ちず、G6 として理由が残る(fail-closed のまま)。"""
    new = g._mk(128)
    mutate(new)
    errors, _, _ = g.check_data(_mk(128), new, g._st())
    assert "G6" in codes(errors)


def test_g6_broken_new_json_file(tmp_path, capsys):
    prev = tmp_path / "prev.json"
    prev.write_text(json.dumps(PREV, ensure_ascii=False), encoding="utf-8")
    new = tmp_path / "new.json"
    new.write_text("<<<<<<< HEAD\n{", encoding="utf-8")
    st = tmp_path / "status.json"
    st.write_text(json.dumps(STATUS_OK), encoding="utf-8")
    assert g.main(["g", "check", "--prev", str(prev), "--new", str(new), "--status", str(st)]) == 1
    assert "G6" in capsys.readouterr().out


def test_step_summary_written(tmp_path, monkeypatch):
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    g.write_step_summary("Guard (C1)", ["G2 絶対下限: x"], ["w"], {"prev_total": 1, "new_total": 2})
    text = summary.read_text(encoding="utf-8")
    assert "Guard (C1): FAIL" in text and "G2" in text


def test_error_annotations_emitted(capsys, tmp_path):
    """I-A: FAIL 時は規則ごとに ::error:: 注釈を 1 行ずつ出す(snapshot・check とも)。"""
    args = ["g", "check", "--prev", str(FIX / "subsidies_20261005_prev.json"),
            "--new", str(FIX / "subsidies_20261005_bad.json"), "--status", str(FIX / "fetch_status_20261005.json")]
    assert g.main(args) == 1
    out = capsys.readouterr().out
    ann = [l for l in out.splitlines() if l.startswith("::error title=U3 fetch guard::")]
    assert len(ann) == 4 and all("\n" not in a for a in ann)
    assert g.main(["g", "snapshot", "--src", str(tmp_path / "none.json"), "--dst", str(tmp_path / "p.json")]) == 1
    assert "::error title=U3 fetch guard::G0" in capsys.readouterr().out
    assert g._annotation("a%b\nc") == "::error title=U3 fetch guard::a%25b c"


def test_sha_out_written_only_on_pass(tmp_path, capsys):
    """M4: --sha-out は guard が検査したバイト列の sha256 を、PASS のときだけ書く。"""
    prev = tmp_path / "prev.json"
    prev.write_bytes((FIX / "subsidies_20261005_prev.json").read_bytes())
    st = tmp_path / "status.json"
    st.write_text(json.dumps(STATUS_OK), encoding="utf-8")
    out = tmp_path / "guard.sha"
    assert g.main(["g", "check", "--prev", str(prev), "--new", str(prev), "--status", str(st), "--sha-out", str(out)]) == 0
    assert out.read_text().strip() == sha(prev)
    out.unlink()
    bad = tmp_path / "bad.json"
    bad.write_bytes((FIX / "subsidies_20261005_bad.json").read_bytes())
    st.write_text(json.dumps(STATUS_1005), encoding="utf-8")
    assert g.main(["g", "check", "--prev", str(prev), "--new", str(bad), "--status", str(st), "--sha-out", str(out)]) == 1
    assert not out.exists()
    # N4: 古い sha が残っていても FAIL なら消える / N5: 値なしの --sha-out は用途エラー
    out.write_text("stale\n", encoding="utf-8")
    assert g.main(["g", "check", "--prev", str(prev), "--new", str(bad), "--status", str(st), "--sha-out", str(out)]) == 1
    assert not out.exists()
    assert g.main(["g", "check", "--prev", str(prev), "--new", str(prev), "--status", str(st), "--sha-out"]) == 2
    assert g.main(["g", "check", "--prev", str(prev), "--new", str(prev), "--status", str(st), "--sha-out", "--explain"]) == 2


def test_internal_errors_become_g6_not_crash(capsys):
    """N3: 想定外の型でも例外で落ちず、G6 内部エラーとして注釈とサマリーに残る。"""
    new = g._mk(128)
    new["items"][0]["source"] = {"unhashable": 1}
    errors, _, _ = g.safe_check_data(g._mk(128), new, g._st())
    assert codes(errors) == ["G6"] and "内部エラー" in errors[0]
    errors, _, _ = g.safe_check_data({"items": [1, 2, 3]}, g._mk(128), g._st())
    assert codes(errors) == ["G0"]
    new = g._mk(128)
    new["items"][0]["id"] = ["list-id"]
    errors, _, _ = g.check_data(g._mk(128), new, g._st())
    assert any("id が文字列でない" in e for e in errors)


def test_log_lines_are_single_line(capsys):
    """N2: ラベル等に改行が混ざっても NG/WARN 行とサマリーが 1 行に潰される(ワークフローコマンド注入の防止)。"""
    st = g._st()
    st["local"]["naha_city"]["label"] = "那覇市\n::warning::injected"
    st["local"]["naha_city"]["ok"] = False
    errors, warnings, info = g.check_data(g._mk(128), g._mk(128), st)
    text = g.render(errors, warnings, info)
    assert "\n::warning::" not in text and "::warning::injected" in text.replace("\n", "|")


# ── fetch_jgrants: status の記録(T1〜T10)───────────────────────────────
class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _item(kw):
    return {"id": f"id-{kw}", "title": f"制度 {kw}", "target_area_search": "全国",
            "acceptance_end_datetime": "2026-12-31T00:00:00Z"}


def _run_jgrants(monkeypatch, tmp_path, behavior):
    """behavior(keyword, attempt) -> bytes を返すか例外を投げる。status と出力 JSON を返す。"""
    import urllib.parse
    import urllib.request
    attempts = {}

    def fake_urlopen(req, timeout=30):
        url = req.full_url
        kw = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)["keyword"][0]
        attempts[kw] = attempts.get(kw, 0) + 1
        body = behavior(kw, attempts[kw])
        return _Resp(body)

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(fj.time, "sleep", lambda s: None)
    monkeypatch.setattr(fj, "OUT_PATH", str(tmp_path / "subsidies.json"))
    monkeypatch.setattr(fj, "STATUS_PATH", str(tmp_path / "status.json"))
    fj.main()
    status = json.loads((tmp_path / "status.json").read_text(encoding="utf-8"))
    out = json.loads((tmp_path / "subsidies.json").read_text(encoding="utf-8"))
    return status, out


def _ok_body(kw):
    return json.dumps({"result": [_item(kw)]}).encode()


def _http503(url="u"):
    return urllib.error.HTTPError(url, 503, "Service Unavailable", {}, io.BytesIO(b""))


def test_t1_all_ok(monkeypatch, tmp_path):
    status, out = _run_jgrants(monkeypatch, tmp_path, lambda kw, n: _ok_body(kw))
    jg = status["jgrants"]
    assert status["schema_version"] == 1
    assert jg["queries"] == 66 and jg["done"] == 66 and jg["failed"] == 0 and jg["incomplete"] is False
    assert jg["items"] == out["count"] == 66


def test_t2_one_keyword_503_three_times(monkeypatch, tmp_path):
    bad = fj.KEYWORDS[10]

    def behavior(kw, n):
        if kw == bad:
            raise _http503()
        return _ok_body(kw)

    status, out = _run_jgrants(monkeypatch, tmp_path, behavior)
    jg = status["jgrants"]
    assert jg["failed"] == 1 and jg["kinds"] == {"HTTPError 503": 1} and jg["failed_keywords"] == [bad]
    assert out["count"] == 65  # 現行と同じ出力(形式不変)。違いは status に失敗が残ること
    errors, _, _ = g.check_data(_mk(128), _mk(128), {**status, "local": g._st()["local"], "local_incomplete": False})
    assert "G1" in codes(errors)


def test_t3_retry_recovery_is_not_failure(monkeypatch, tmp_path):
    flaky = fj.KEYWORDS[3]

    def behavior(kw, n):
        if kw == flaky and n == 1:
            raise _http503()
        return _ok_body(kw)

    status, _ = _run_jgrants(monkeypatch, tmp_path, behavior)
    jg = status["jgrants"]
    assert jg["failed"] == 0 and jg["retried"] == 1


def test_t5_all_503_like_20261005(monkeypatch, tmp_path):
    def behavior(kw, n):
        raise _http503()

    status, out = _run_jgrants(monkeypatch, tmp_path, behavior)
    jg = status["jgrants"]
    assert jg["failed"] == 66 and jg["kinds"] == {"HTTPError 503": 66} and out["count"] == 0
    assert jg["incomplete"] is False


def test_t6_timeout_kind(monkeypatch, tmp_path):
    import socket
    bad = fj.KEYWORDS[0]

    def behavior(kw, n):
        if kw == bad:
            raise socket.timeout("timed out")
        return _ok_body(kw)

    status, _ = _run_jgrants(monkeypatch, tmp_path, behavior)
    assert status["jgrants"]["kinds"] == {"timeout": 1}


def test_t7_non_json_body(monkeypatch, tmp_path):
    bad = fj.KEYWORDS[1]
    status, _ = _run_jgrants(monkeypatch, tmp_path, lambda kw, n: b"<html>maintenance</html>" if kw == bad else _ok_body(kw))
    assert status["jgrants"]["failed"] == 1 and status["jgrants"]["kinds"] == {"json": 1}


def test_t8_result_key_missing_is_schema_failure(monkeypatch, tmp_path):
    bad = fj.KEYWORDS[2]
    status, _ = _run_jgrants(monkeypatch, tmp_path,
                             lambda kw, n: json.dumps({"message": "ok"}).encode() if kw == bad else _ok_body(kw))
    assert status["jgrants"]["failed"] == 1 and status["jgrants"]["kinds"] == {"schema": 1}


def test_t9_empty_result_is_normal_zero(monkeypatch, tmp_path):
    status, out = _run_jgrants(monkeypatch, tmp_path, lambda kw, n: json.dumps({"result": []}).encode())
    assert status["jgrants"]["failed"] == 0 and out["count"] == 0


def test_stale_status_file_is_replaced_at_start(monkeypatch, tmp_path):
    """M2: 古い status が残っていても、開始時に今回のものへ置き換わる。"""
    (tmp_path / "status.json").write_text(json.dumps({"schema_version": 1, "jgrants": {"failed": 66}, "local": {}}), encoding="utf-8")
    status, _ = _run_jgrants(monkeypatch, tmp_path, lambda kw, n: _ok_body(kw))
    assert status["jgrants"]["failed"] == 0 and status["jgrants"]["done"] == 66 and "local" not in status


def test_status_written_even_on_unexpected_exception(monkeypatch, tmp_path):
    """I-1: 想定外の例外で落ちても finally で status(incomplete=true)が残る。"""
    bad = fj.KEYWORDS[4]

    def behavior(kw, n):
        if kw == bad:
            raise RuntimeError("boom")  # fetch_json は Exception を捕まえるので 3 回とも失敗扱いになる
        return _ok_body(kw)

    status, _ = _run_jgrants(monkeypatch, tmp_path, behavior)
    assert status["jgrants"]["failed"] == 1 and status["jgrants"]["kinds"] == {"RuntimeError": 1}

    # normalize を壊して本当に途中終了させる
    monkeypatch.setattr(fj, "normalize", lambda item, tag: (_ for _ in ()).throw(RuntimeError("boom")))
    with pytest.raises(RuntimeError):
        _run_jgrants(monkeypatch, tmp_path, lambda kw, n: _ok_body(kw))
    status = json.loads((tmp_path / "status.json").read_text(encoding="utf-8"))
    assert status["jgrants"]["incomplete"] is True
    errors, _, _ = g.check_data(_mk(128), _mk(128), {**status, "local": g._st()["local"], "local_incomplete": False})
    assert "G1" in codes(errors)


def test_t10_status_file_missing_fails_guard(tmp_path, capsys):
    prev = tmp_path / "prev.json"
    prev.write_text(json.dumps(PREV, ensure_ascii=False), encoding="utf-8")
    assert g.main(["g", "check", "--prev", str(prev), "--new", str(prev), "--status", str(tmp_path / "none.json")]) == 1
    assert "status ファイルが無い" in capsys.readouterr().out


# ── fetch_local: ソースごとの status(TL1〜TL6)──────────────────────────
PREF = fl.SOURCES[0]
LISTING = PREF["listing"]
BASE = LISTING.rsplit("/", 1)[0]


def _listing_html(n):
    links = "".join(f'<li><a href="{BASE}/{1000 + i}.html">沖縄県テスト補助金 第{i}号</a></li>' for i in range(n))
    return f"<html><body><main><ul>{links}</ul></main></body></html>"


DETAIL_HTML = "<html><body><main><p>募集期間:令和8年12月31日まで</p></main></body></html>"


def _run_local(monkeypatch, tmp_path, listing_html, robots=lambda url: True, detail_html=DETAIL_HTML,
               existing=None, existing_status=None):
    def fake_get(url, retries=3):
        if url == LISTING:
            return listing_html
        return detail_html

    monkeypatch.setattr(fl, "http_get", fake_get)
    monkeypatch.setattr(fl, "robots_ok", lambda url, cache: robots(url))
    monkeypatch.setattr(fl.time, "sleep", lambda s: None)
    monkeypatch.setattr(fl, "SOURCES", [PREF])
    out = tmp_path / "subsidies.json"
    out.write_text(json.dumps(existing or {"items": [], "count": 0}, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(fl, "OUT_PATH", str(out))
    st_path = tmp_path / "status.json"
    if existing_status is not None:
        st_path.write_text(json.dumps(existing_status), encoding="utf-8")
    monkeypatch.setattr(fl, "STATUS_PATH", str(st_path))
    fl.main()
    return json.loads(st_path.read_text(encoding="utf-8")), json.loads(out.read_text(encoding="utf-8"))


def test_tl1_listing_ok_adopts_items(monkeypatch, tmp_path):
    status, out = _run_local(monkeypatch, tmp_path, _listing_html(8),
                             existing_status={"schema_version": 1, "jgrants": {"failed": 0}})
    st = status["local"]["okinawa_pref_sangyo"]
    assert st["ok"] is True and st["listing_skipped"] is False and st["listing_entries"] == 8 and st["items"] == 8
    assert status["local_incomplete"] is False
    assert status["jgrants"] == {"failed": 0}  # fetch_jgrants の記録を壊さずに追記
    assert out["by_source"] == {PREF["label"]: 8}


def test_tl2_listing_robots_disallow_is_recorded(monkeypatch, tmp_path):
    status, out = _run_local(monkeypatch, tmp_path, _listing_html(8), robots=lambda url: url != LISTING)
    st = status["local"]["okinawa_pref_sangyo"]
    assert st["ok"] is False and st["listing_skipped"] is True and st["items"] == 0
    assert out["count"] == 0  # 前回掲載分は fetch_jgrants の上書きで既に無い → guard が G1 で止める
    errors, _, _ = g.check_data(_mk(128), _mk(128, pref=0), {**g._st(), "local": status["local"]})
    assert "G1" in codes(errors)


def test_tl3_listing_fetch_failure_is_recorded(monkeypatch, tmp_path):
    status, _ = _run_local(monkeypatch, tmp_path, None)
    st = status["local"]["okinawa_pref_sangyo"]
    assert st["ok"] is False and st["listing_skipped"] is False and st["items"] == 0


def test_tl4_listing_ok_zero_entries_is_normal_zero(monkeypatch, tmp_path):
    status, _ = _run_local(monkeypatch, tmp_path, "<html><main><p>該当なし</p></main></html>")
    st = status["local"]["okinawa_pref_sangyo"]
    assert st["ok"] is True and st["listing_entries"] == 0 and st["items"] == 0


def test_tl5_detail_robots_disallow_counted(monkeypatch, tmp_path):
    blocked = {f"{BASE}/1000.html", f"{BASE}/1001.html"}
    status, _ = _run_local(monkeypatch, tmp_path, _listing_html(8), robots=lambda url: url not in blocked)
    st = status["local"]["okinawa_pref_sangyo"]
    assert st["ok"] is True and st["detail_skipped"] == 2 and st["items"] == 6


def test_tl6_status_written_without_jgrants_record_makes_guard_fail(monkeypatch, tmp_path):
    status, _ = _run_local(monkeypatch, tmp_path, _listing_html(8))
    assert "jgrants" not in status and status["schema_version"] == 1
    errors, _, _ = g.check_data(_mk(128), _mk(128), status)
    assert any("jgrants が無い" in e for e in errors)


def test_fetch_local_output_format_unchanged(monkeypatch, tmp_path):
    existing = {"updated_at": "x", "count": 1, "by_tag": {"okinawa": 1},
                "items": [{"id": "j1", "name": "n", "deadline": "2026-12-31", "source_url": "https://www.jgrants-portal.go.jp/subsidy/j1",
                           "status": "募集中", "tag": "okinawa"}]}
    _, out = _run_local(monkeypatch, tmp_path, _listing_html(2), existing=existing)
    assert list(out) == ["updated_at", "count", "by_tag", "items", "by_source"]
    assert out["count"] == 3 and out["by_source"] == {"jGrants": 1, PREF["label"]: 2}


# ── update.yml の静的確認(順序・権限・トリガー不変)────────────────────
WF = (ROOT / ".github" / "workflows" / "update.yml").read_text(encoding="utf-8")


def _wf():
    import yaml  # PyYAML が無い環境では skip せず失敗させる(静的検査と run ブロック実行を黙って飛ばさない)
    return yaml.safe_load(WF)


def _steps():
    return _wf()["jobs"]["fetch-and-deploy"]["steps"]


def _step(prefix):
    return next(s for s in _steps() if (s.get("name") or "").startswith(prefix))


def test_pyyaml_available_for_workflow_tests():
    import yaml  # noqa: F401
    assert yaml.safe_load("a: 1") == {"a": 1}


def test_workflow_yaml_and_step_order():
    doc = _wf()
    assert doc["permissions"] == {"contents": "write", "pages": "write", "id-token": "write"}
    assert set(doc[True] if True in doc else doc["on"]) == {"schedule", "workflow_dispatch"}
    assert doc["concurrency"] == {"group": "update-subsidies", "cancel-in-progress": False}
    job = doc["jobs"]["fetch-and-deploy"]
    # C-1(独立レビュー): runner コンテキストは job レベルの env では使えない。step の env に置く
    assert "env" not in job
    for prefix in ("Fetch jGrants data", "Fetch local", "Guard (C1"):
        assert _step(prefix)["env"]["FETCH_STATUS_PATH"] == "${{ runner.temp }}/fetch_status.json"
    names = [s.get("name") or s.get("uses") for s in job["steps"]]

    def idx(prefix):
        return next(i for i, n in enumerate(names) if n and n.startswith(prefix))

    assert idx("Snapshot previous data") < idx("Fetch jGrants data") < idx("Fetch local") \
        < idx("Preserve verified") < idx("Guard (C1") < idx("Generate LINE deadline alerts") \
        < idx("Commit updated data") < idx("Copy data into site") < idx("Validate data before deploy") \
        < idx("Prepare Pages artifact") < idx("Verify artifact (C3") < idx("Upload site") < idx("Deploy to GitHub Pages")
    assert "shipping-gate" in doc["jobs"]
    assert not any("if" in s for s in job["steps"])   # 失敗したらそこで止まる(failure() で走る step は無い)


def test_workflow_runner_context_not_in_job_level_keys():
    """C-1 の再発防止: runner.* は steps 配下(env/run/with)でのみ使う。"""
    doc = _wf()
    for job in doc["jobs"].values():
        for key, val in job.items():
            if key != "steps":
                assert "runner." not in json.dumps(val, ensure_ascii=False), f"job-level {key} に runner コンテキスト"


def test_workflow_text_invariants():
    assert "allow_drop" not in WF                       # 判断事項 F: 迂回入力なし
    assert "issues: write" not in WF                    # 判断事項 A(α): 権限追加なし
    assert "if n < 10" not in WF and "MIN_TOTAL" in WF  # 判断事項 B/I-4
    assert "git show HEAD:data/subsidies.json" in WF    # C2 は HEAD blob
    assert "/tmp/pages-deploy/data/subsidies.json" in WF  # C3 は公開物
    assert 'if [ "$pushed" != 1 ]' in WF                # 判断事項 G
    assert "guard_subsidies.py --selftest" in WF
    assert "--sha-out" in WF                            # M4: guard が検査したバイト列の sha


# ── update.yml の run ブロックそのものを実行する(I-B)─────────────────────
def _bash(script, cwd, env=None, pipefail=True):
    """GitHub Actions の `shell: bash` 相当(bash --noprofile --norc -eo pipefail)で run ブロックを実行。"""
    e = dict(os.environ)
    e.update(env or {})
    opts = ["-eo", "pipefail"] if pipefail else ["-e"]
    return subprocess.run(["bash", "--noprofile", "--norc", *opts, "-c", script], cwd=cwd, env=e,
                          capture_output=True, text=True)


def _prepare_tree(root):
    """update.yml の Commit step が git add するパスを最低限そろえる。"""
    for d in ("data/kpi", "posts/launch", "posts/images", "posts/line", "posts/carousel", "site/themes", "site/ig"):
        (root / d).mkdir(parents=True, exist_ok=True)
        (root / d / ".keep").write_text("", encoding="utf-8")
    (root / "data" / "line_alerts.json").write_text("{}", encoding="utf-8")


@pytest.fixture
def wf_repos(tmp_path):
    origin = tmp_path / "origin.git"
    _git(tmp_path, "init", "-q", "--bare", "-b", "main", str(origin))
    a, b = tmp_path / "runner", tmp_path / "other"
    for d in (a, b):
        _git(tmp_path, "clone", "-q", str(origin), str(d))
        _git(d, "config", "user.email", "t@example.com")
        _git(d, "config", "user.name", "t")
    _prepare_tree(a)
    (a / "data" / "subsidies.json").write_text(_multi_line_json(), encoding="utf-8")
    (a / "other.txt").write_text("x\n", encoding="utf-8")
    _git(a, "add", "-A")
    _git(a, "commit", "-q", "-m", "base")
    _git(a, "push", "-q", "origin", "main")
    _git(b, "pull", "-q", "origin", "main")
    rt = tmp_path / "runner_temp"
    rt.mkdir()
    return a, b, origin, rt


def _origin_blob_sha(origin):
    data = subprocess.run(["git", "--git-dir", str(origin), "show", "main:data/subsidies.json"], check=True, capture_output=True).stdout
    return hashlib.sha256(data).hexdigest()


def _commit_step(a, rt):
    """runner 側で新データを書き、guard.sha を置き、Commit step の run ブロックをそのまま実行する。"""
    (a / "data" / "subsidies.json").write_text(_multi_line_json(tag=" 更新"), encoding="utf-8")
    expected = sha(a / "data" / "subsidies.json")
    (rt / "guard.sha").write_text(expected + "\n", encoding="utf-8")
    r = _bash(_step("Commit updated data")["run"], a, {"RUNNER_TEMP": str(rt)})
    return r, expected


def test_run_commit_step_s1_no_concurrent_push(wf_repos):
    a, _, origin, rt = wf_repos
    r, expected = _commit_step(a, rt)
    assert r.returncode == 0, r.stdout + r.stderr
    assert _origin_blob_sha(origin) == expected and "C2 OK" in r.stdout


@pytest.mark.parametrize("trailing", [b"", b"\n", b"\n\n"])
def test_run_commit_step_s1b_real_fixture_bytes_any_trailing_newline(wf_repos, trailing):
    """C2 は末尾改行の有無・個数に関わらず「guard が検査したバイト列 == push される blob」で一致する
    (第 3 ラウンド C-1 の再発防止: 本番 fixture のバイト列 + 末尾改行 0/1/2 個)。"""
    a, _, origin, rt = wf_repos
    data = (FIX / "subsidies_20261005_prev.json").read_bytes() + trailing
    (a / "data" / "subsidies.json").write_bytes(data)
    expected = hashlib.sha256(data).hexdigest()
    (rt / "guard.sha").write_text(expected + "\n", encoding="utf-8")
    r = _bash(_step("Commit updated data")["run"], a, {"RUNNER_TEMP": str(rt)})
    assert r.returncode == 0, r.stdout + r.stderr
    assert _origin_blob_sha(origin) == expected


def test_run_commit_step_s2_concurrent_change_to_same_file_blocks_push(wf_repos):
    a, b, origin, rt = wf_repos
    before = _origin_blob_sha(origin)
    text = (b / "data" / "subsidies.json").read_text(encoding="utf-8").replace('"name": "制度0"', '"name": "制度0 (他)"')
    (b / "data" / "subsidies.json").write_text(text, encoding="utf-8")
    _git(b, "commit", "-qam", "other")
    _git(b, "push", "-q", "origin", "main")
    other = _origin_blob_sha(origin)
    r, _ = _commit_step(a, rt)
    assert r.returncode == 1 and "::error::C2" in r.stdout
    assert _origin_blob_sha(origin) == other != before   # runner からは何も push されていない


def test_run_commit_step_s3_push_rejected_three_times(wf_repos):
    a, _, origin, rt = wf_repos
    hook = origin / "hooks" / "pre-receive"
    hook.write_text("#!/bin/sh\necho rejected >&2\nexit 1\n", encoding="utf-8")
    hook.chmod(0o755)
    before = _origin_blob_sha(origin)
    r, _ = _commit_step(a, rt)
    assert r.returncode == 1 and r.stdout.count("push retry") == 3 and "push に3回失敗" in r.stdout
    assert _origin_blob_sha(origin) == before


def test_run_commit_step_s4_concurrent_change_to_other_file(wf_repos):
    a, b, origin, rt = wf_repos
    (b / "other.txt").write_text("y\n", encoding="utf-8")
    _git(b, "commit", "-qam", "other file")
    _git(b, "push", "-q", "origin", "main")
    r, expected = _commit_step(a, rt)
    assert r.returncode == 0 and _origin_blob_sha(origin) == expected


def test_run_commit_step_s6_unreadable_head_blob_reports_c2(wf_repos, tmp_path):
    """N1: `git show HEAD:data/subsidies.json` が失敗しても(pipefail 下で黙って 128 で落ちず)
    ::error::C2 を出して止まり、push されない。git show だけ失敗させる shim を PATH の先頭に置いて実行。"""
    a, _, origin, rt = wf_repos
    shim = tmp_path / "shim"
    shim.mkdir()
    real_git = shutil.which("git")
    (shim / "git").write_text(f'#!/bin/sh\nif [ "$1" = "show" ]; then echo "fatal: simulated" >&2; exit 128; fi\nexec "{real_git}" "$@"\n', encoding="utf-8")
    (shim / "git").chmod(0o755)
    (a / "data" / "subsidies.json").write_text(_multi_line_json(tag=" 更新"), encoding="utf-8")
    (rt / "guard.sha").write_text(sha(a / "data" / "subsidies.json") + "\n", encoding="utf-8")
    before = _origin_blob_sha(origin)
    r = _bash(_step("Commit updated data")["run"], a, {"RUNNER_TEMP": str(rt), "PATH": f"{shim}:{os.environ['PATH']}"})
    assert r.returncode == 1 and "::error::C2" in r.stdout and "読めない" in r.stdout
    assert _origin_blob_sha(origin) == before


def test_run_commit_step_s5_missing_guard_sha_fails(wf_repos):
    a, _, origin, rt = wf_repos
    (a / "data" / "subsidies.json").write_text(_multi_line_json(tag=" 更新"), encoding="utf-8")
    before = _origin_blob_sha(origin)
    r = _bash(_step("Commit updated data")["run"], a, {"RUNNER_TEMP": str(rt)})
    assert r.returncode != 0 and _origin_blob_sha(origin) == before


def _c3_script(deploy_dir):
    return _step("Verify artifact (C3")["run"].replace("/tmp/pages-deploy", str(deploy_dir))


def test_run_c3_step(tmp_path):
    rt = tmp_path / "rt"
    rt.mkdir()
    deploy = tmp_path / "pages-deploy" / "data"
    deploy.mkdir(parents=True)
    f = deploy / "subsidies.json"
    f.write_text(_multi_line_json(), encoding="utf-8")
    (rt / "guard.sha").write_text(sha(f) + "\n", encoding="utf-8")
    assert _bash(_c3_script(tmp_path / "pages-deploy"), tmp_path, {"RUNNER_TEMP": str(rt)}).returncode == 0
    f.write_bytes(f.read_bytes() + b" ")
    r = _bash(_c3_script(tmp_path / "pages-deploy"), tmp_path, {"RUNNER_TEMP": str(rt)})
    assert r.returncode == 1 and "::error::C3" in r.stdout
    f.unlink()
    assert _bash(_c3_script(tmp_path / "pages-deploy"), tmp_path, {"RUNNER_TEMP": str(rt)}).returncode != 0


def _stage_scripts(root):
    (root / "scripts").mkdir(exist_ok=True)
    shutil.copy(SCRIPTS / "guard_subsidies.py", root / "scripts" / "guard_subsidies.py")


@pytest.mark.parametrize("n_items,expected_rc", [(100, 0), (99, 1)])
def test_run_validate_step(tmp_path, n_items, expected_rc):
    _stage_scripts(tmp_path)
    (tmp_path / "site" / "data").mkdir(parents=True)
    (tmp_path / "site" / "data" / "subsidies.json").write_text(json.dumps({"items": [{"id": i} for i in range(n_items)]}), encoding="utf-8")
    (tmp_path / "site" / "data" / "line_alerts.json").write_text("{}", encoding="utf-8")
    r = _bash(_step("Validate data before deploy")["run"], tmp_path, pipefail=False)
    assert r.returncode == expected_rc, r.stdout + r.stderr


def test_run_validate_step_fails_when_const_unavailable(tmp_path):
    (tmp_path / "site" / "data").mkdir(parents=True)
    (tmp_path / "site" / "data" / "subsidies.json").write_text(json.dumps({"items": [{"id": i} for i in range(150)]}), encoding="utf-8")
    (tmp_path / "site" / "data" / "line_alerts.json").write_text("{}", encoding="utf-8")
    r = _bash(_step("Validate data before deploy")["run"], tmp_path, pipefail=False)   # scripts/ が無い
    assert r.returncode != 0


def test_run_snapshot_and_guard_steps_pass_and_fail(tmp_path):
    """Snapshot → Guard の run ブロックを実データ fixture で実行。PASS で guard.sha が残り、FAIL では残らない。"""
    _stage_scripts(tmp_path)
    rt = tmp_path / "rt"
    rt.mkdir()
    (tmp_path / "data").mkdir()
    data = tmp_path / "data" / "subsidies.json"
    data.write_bytes((FIX / "subsidies_20261005_prev.json").read_bytes())
    env = {"RUNNER_TEMP": str(rt), "FETCH_STATUS_PATH": str(rt / "fetch_status.json")}
    assert _bash(_step("Snapshot previous data")["run"], tmp_path, env, pipefail=False).returncode == 0
    (rt / "fetch_status.json").write_text(json.dumps(STATUS_OK), encoding="utf-8")
    r = _bash(_step("Guard (C1")["run"], tmp_path, env)
    assert r.returncode == 0, r.stdout + r.stderr
    assert (rt / "guard.sha").read_text().strip() == sha(data)
    # FAIL: 10-05 のデータと status に差し替え
    (rt / "guard.sha").unlink()
    data.write_bytes((FIX / "subsidies_20261005_bad.json").read_bytes())
    (rt / "fetch_status.json").write_text(json.dumps(STATUS_1005), encoding="utf-8")
    r = _bash(_step("Guard (C1")["run"], tmp_path, env)
    assert r.returncode == 1 and "::error title=U3 fetch guard::G1" in r.stdout
    assert not (rt / "guard.sha").exists()


# ── C2 / C3 の実演(一時 git リポジトリ)──────────────────────────────────
def _git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout


def _head_blob_sha(repo):
    data = subprocess.run(["git", "show", "HEAD:data/subsidies.json"], cwd=repo, check=True, capture_output=True).stdout
    return hashlib.sha256(data).hexdigest()


def _multi_line_json(n=20, tag=""):
    """本番と同じ書式(json.dump(indent=1) = 末尾改行なし)。末尾改行の有無で sha が変わるため、ここを本番に合わせる。"""
    items = [{"id": f"j{i}", "name": f"制度{i}{tag if i == n - 1 else ''}"} for i in range(n)]
    return json.dumps({"count": n, "items": items}, ensure_ascii=False, indent=1)


def test_fixture_and_test_data_match_production_format():
    """C2 の照合は blob のバイト列そのものに対して行う(末尾改行の有無に依存しない。s1b で 0/1/2 個を検証)。
    ここでは fixture とテスト用データが本番の書き出し(json.dump(indent=1) = 末尾改行なし)と同じ形であることだけを固定する。
    本番の data/subsidies.json 自体は bot が書き換えるため検査しない。"""
    assert not (FIX / "subsidies_20261005_prev.json").read_bytes().endswith(b"\n")
    assert not _multi_line_json().endswith("\n")


@pytest.fixture
def repos(tmp_path):
    origin = tmp_path / "origin.git"
    _git(tmp_path, "init", "-q", "--bare", "-b", "main", str(origin))
    a = tmp_path / "runner"
    b = tmp_path / "other"
    for d in (a, b):
        _git(tmp_path, "clone", "-q", str(origin), str(d))
        _git(d, "config", "user.email", "t@example.com")
        _git(d, "config", "user.name", "t")
    (a / "data").mkdir()
    (a / "data" / "subsidies.json").write_text(_multi_line_json(), encoding="utf-8")
    (a / "other.txt").write_text("x\n", encoding="utf-8")
    _git(a, "add", "-A")
    _git(a, "commit", "-q", "-m", "base")
    _git(a, "push", "-q", "origin", "main")
    _git(b, "pull", "-q", "origin", "main")
    return a, b


def test_c2_detects_rebase_changing_the_pushed_blob(repos):
    a, b = repos
    # other: 先頭付近の別 hunk を変えて先に push(ig-posts-mikata が ig_* を付ける状況の模擬)
    text = (b / "data" / "subsidies.json").read_text(encoding="utf-8").replace('"name": "制度0"', '"name": "制度0 (他 workflow の変更)"')
    (b / "data" / "subsidies.json").write_text(text, encoding="utf-8")
    _git(b, "commit", "-qam", "other")
    _git(b, "push", "-q", "origin", "main")
    # runner: 末尾の別 hunk を変えて commit(= Guard 合格データ)
    (a / "data" / "subsidies.json").write_text(_multi_line_json(tag=" 更新"), encoding="utf-8")
    expected = sha(a / "data" / "subsidies.json")
    _git(a, "commit", "-qam", "auto: update")
    assert _head_blob_sha(a) == expected
    _git(a, "pull", "-q", "--rebase", "-X", "theirs", "origin", "main")
    assert _head_blob_sha(a) != expected, "rebase で両方の hunk が混ざり、push 対象の blob が検査済みと変わる"


def test_c2_passes_when_other_push_touches_other_files(repos):
    a, b = repos
    (b / "other.txt").write_text("y\n", encoding="utf-8")
    _git(b, "commit", "-qam", "other file")
    _git(b, "push", "-q", "origin", "main")
    (a / "data" / "subsidies.json").write_text(_multi_line_json(tag=" 更新"), encoding="utf-8")
    expected = sha(a / "data" / "subsidies.json")
    _git(a, "commit", "-qam", "auto: update")
    _git(a, "pull", "-q", "--rebase", "-X", "theirs", "origin", "main")
    assert _head_blob_sha(a) == expected


def test_c2_head_blob_check_is_independent_of_working_tree(repos):
    """作業ツリーだけ改変されても HEAD blob(push される物)は検査済みのまま → HEAD 側を見る根拠。"""
    a, _ = repos
    (a / "data" / "subsidies.json").write_text(_multi_line_json(tag=" 更新"), encoding="utf-8")
    expected = sha(a / "data" / "subsidies.json")
    _git(a, "commit", "-qam", "auto: update")
    (a / "data" / "subsidies.json").write_text("tampered", encoding="utf-8")
    assert sha(a / "data" / "subsidies.json") != expected
    assert _head_blob_sha(a) == expected


def test_c3_artifact_copy_identity(tmp_path):
    site = tmp_path / "site"
    (site / "data").mkdir(parents=True)
    (site / "data" / "subsidies.json").write_text(_multi_line_json(), encoding="utf-8")
    expected = sha(site / "data" / "subsidies.json")
    deploy = tmp_path / "pages-deploy"
    shutil.copytree(site, deploy)
    assert sha(deploy / "data" / "subsidies.json") == expected
    (deploy / "data" / "subsidies.json").write_bytes((deploy / "data" / "subsidies.json").read_bytes() + b" ")
    assert sha(deploy / "data" / "subsidies.json") != expected
