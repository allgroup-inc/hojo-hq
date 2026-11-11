"""自治体の取り込みの「人が承認したものだけ外す」仕組み(2026-11-11 段階A)。合成データのみ・通信なし。"""
import json
import os
import sys

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import fetch_local as FL  # noqa: E402
import listing_review as LR  # noqa: E402

PREF = next(s for s in FL.SOURCES if s["key"] == "okinawa_pref_sangyo")
BASE = "https://www.pref.okinawa.lg.jp/shigoto/keizai/1009879/1010143/"

# 2026-11-11 時点のデータで候補になった3件(名前はデータのまま)
CONTRACT = "令和5年沖縄建設産業グローバル化支援業務委託に係る企画提案書等の募集"
BOOST = "「Boost Up OKINAWA 2026」参加企業の募集"
PITCH = "九州・山口ベンチャーマーケット2026 ピッチコンテスト登壇企業の募集について"


def entry(name, url, source=PREF["label"], **kw):
    e = {"source_url": url, "name": name, "source": source, "reason": "補助金ではない(公式ページで確認)",
         "verified_by": "検証部", "reviewed_by": "守り部", "approved_by": "小柳", "approved_on": "2026-11-11"}
    e.update(kw)
    return e


# ---- 候補の判定 ----
@pytest.mark.parametrize("name", [CONTRACT, BOOST, PITCH, "〇〇事業に係る入札公告", "販路開拓セミナー参加者募集"])
def test_candidates(name):
    assert LR.candidate_reason(name)


@pytest.mark.parametrize("name", [
    "小規模事業者持続化補助金",
    "電気料金高騰に対する支援",                       # 案内ページかもしれないが外さない(人の確認へ)
    "補助金説明会のお知らせ",                          # 補助金の語があるので候補にしない
    "商談会出展支援助成金",                            # 助成の語がある
    "展示会出展費補助事業(参加企業の募集)",           # 補助の語がある
    "令和6年度補正予算 商用車等の電動化促進事業",     # 年度だけでは見ない
    "",
])
def test_not_candidates(name):
    assert LR.candidate_reason(name) is None


# ---- 承認済みの一覧との照合 ----
def test_exclude_only_when_url_name_source_all_match():
    ex = [entry(BOOST, BASE + "1001.html")]
    assert LR.decide(BOOST, BASE + "1001.html", PREF["label"], ex)[0] == LR.DECISION_EXCLUDE
    assert LR.decide(BOOST, BASE + "9999.html", PREF["label"], ex)[0] == LR.DECISION_REVIEW   # URLが違う
    assert LR.decide(BOOST + "(第2回)", BASE + "1001.html", PREF["label"], ex)[0] == LR.DECISION_REVIEW  # 名前が違う
    assert LR.decide(BOOST, BASE + "1001.html", "那覇市(企業支援)", ex)[0] == LR.DECISION_REVIEW     # 取得先が違う
    assert LR.decide("小規模事業者持続化補助金", BASE + "1001.html", PREF["label"], ex)[0] == LR.DECISION_KEEP


def test_unapproved_candidate_is_review_not_exclude():
    assert LR.decide(PITCH, BASE + "1002.html", PREF["label"], [])[0] == LR.DECISION_REVIEW


# ---- 一覧の検査(壊れていたら止める) ----
def _write(tmp_path, obj):
    p = tmp_path / "ex.json"
    p.write_text(obj if isinstance(obj, str) else json.dumps(obj, ensure_ascii=False), encoding="utf-8")
    return str(p)


def test_load_missing_file_is_empty(tmp_path):
    assert LR.load_exclusions(str(tmp_path / "none.json")) == []


def test_repo_ledger_is_empty_until_official_check():
    # 公式ページの確認が終わるまで、承認済みの一覧には何も載せない(2026-11-11 決裁の条件1)
    assert LR.load_exclusions() == []


@pytest.mark.parametrize("bad,msg", [
    ("{壊れている", "読めません"),
    ({"items": "x"}, "配列"),
    ({"items": [{"name": BOOST}]}, "足りない項目"),
    ({"items": [entry(BOOST, "not-a-url")]}, "URL"),
    ({"items": [entry(BOOST, BASE + "1.html", approved_on="11/11")]}, "承認日"),
    ({"items": [entry("小規模事業者持続化補助金", BASE + "1.html")]}, "本物の補助金"),
    ({"items": [entry(BOOST, BASE + "1.html"), entry(BOOST, BASE + "1.html")]}, "2回"),
])
def test_load_rejects_broken_ledger(tmp_path, bad, msg):
    with pytest.raises(LR.ListingReviewError, match=msg):
        LR.load_exclusions(_write(tmp_path, bad))


# ---- 取り込み(fetch_local.crawl_source)に組み込んだ動き ----
LISTING = """<html><main>
<a href="/shigoto/keizai/1009879/1010143/1001.html">{boost}</a>
<a href="/shigoto/keizai/1009879/1010143/1002.html">{pitch}</a>
<a href="/shigoto/keizai/1009879/1010143/1003.html">{contract}</a>
<a href="/shigoto/keizai/1009879/1010143/1004.html">小規模事業者向け設備導入支援補助金</a>
<a href="/shigoto/keizai/1009879/1010143/1005.html">販路開拓セミナー参加者募集のご案内</a>
</main></html>""".format(boost=BOOST, pitch=PITCH, contract=CONTRACT)
DETAIL = "<html><main>募集期間 令和8年12月25日まで</main></html>"


@pytest.fixture
def offline(monkeypatch):
    calls = []

    def fake_get(url, retries=3):
        calls.append(url)
        return LISTING if url == PREF["listing"] else DETAIL
    monkeypatch.setattr(FL, "http_get", fake_get)
    monkeypatch.setattr(FL, "robots_ok", lambda url, cache: True)
    monkeypatch.setattr(FL, "REQUEST_DELAY", 0)
    return calls


def _names(items):
    return {it["name"] for it in items}


def test_crawl_without_approvals_keeps_everything_and_flags(offline):
    st = {}
    items = FL.crawl_source(PREF, {}, st, [])
    names = _names(items)
    assert {BOOST, PITCH, CONTRACT, "小規模事業者向け設備導入支援補助金"} <= names   # 何も外さない
    assert st["excluded"] == []
    flagged = {it["name"] for it in items if it.get("review_candidate")}
    assert {BOOST, PITCH, CONTRACT} <= flagged
    assert "小規模事業者向け設備導入支援補助金" not in flagged
    assert len(st["review_candidates"]) >= 3


def test_crawl_excludes_only_approved(offline):
    ex = [entry(BOOST, BASE + "1001.html"), entry(PITCH, BASE + "1002.html"), entry(CONTRACT, BASE + "1003.html")]
    st = {}
    items = FL.crawl_source(PREF, {}, st, ex)
    names = _names(items)
    assert not ({BOOST, PITCH, CONTRACT} & names)
    assert "小規模事業者向け設備導入支援補助金" in names                     # 補助金は残る
    assert "販路開拓セミナー参加者募集のご案内" in names                     # 候補だが未承認なので残る
    assert sorted(e["name"] for e in st["excluded"]) == sorted([BOOST, PITCH, CONTRACT])
    assert all(BASE + n not in offline for n in ("1001.html", "1002.html", "1003.html"))  # 外すページは開かない


def test_main_stops_when_more_excluded_than_approved(offline, monkeypatch, tmp_path):
    # 想定外の除外(承認済みより多く外す)が起きたら、データを書き換えずに止める
    out = tmp_path / "subsidies.json"
    out.write_text(json.dumps({"items": []}), encoding="utf-8")
    monkeypatch.setattr(FL, "OUT_PATH", str(out))
    monkeypatch.setattr(FL, "STATUS_PATH", str(tmp_path / "status.json"))
    monkeypatch.setattr(FL, "SOURCES", [PREF])
    monkeypatch.setattr(LR, "load_exclusions", lambda path=None: [entry(BOOST, BASE + "1001.html")])
    real = LR.decide
    monkeypatch.setattr(LR, "decide", lambda n, u, s, e: (LR.DECISION_EXCLUDE, "壊れた判定") if n in (BOOST, PITCH)
                        else real(n, u, s, e))
    with pytest.raises(LR.ListingReviewError, match="より多い"):
        FL.main()
    assert json.loads(out.read_text(encoding="utf-8")) == {"items": []}             # 書き換えていない
    status = json.loads((tmp_path / "status.json").read_text(encoding="utf-8"))
    assert status["local_incomplete"] is True                                         # guard が公開を止める印


def test_main_stops_on_broken_ledger(offline, monkeypatch, tmp_path):
    out = tmp_path / "subsidies.json"
    out.write_text(json.dumps({"items": []}), encoding="utf-8")
    monkeypatch.setattr(FL, "OUT_PATH", str(out))
    monkeypatch.setattr(FL, "STATUS_PATH", str(tmp_path / "status.json"))

    def broken(path=None):
        raise LR.ListingReviewError("壊れている")
    monkeypatch.setattr(LR, "load_exclusions", broken)
    with pytest.raises(LR.ListingReviewError):
        FL.main()
    assert json.loads((tmp_path / "status.json").read_text(encoding="utf-8"))["local_incomplete"] is True
