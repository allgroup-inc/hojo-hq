#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自治体の一覧から取り込む項目の「人が承認したものだけ外す」仕組み(2026-11-11 段階A)。

県・市町村の一覧には、補助金ではないページ(業務委託・入札の公募、イベントやコンテストの参加募集)が
混ざる。ただし言葉だけで外すと、本物の補助金を消すおそれがある(例:「説明会」と書かれた補助金の告知)。
そこで次の3段にする。

  1. 候補: 名前に「入札・業務委託…」または「参加企業・登壇・コンテスト…」があり、
           かつ「補助・助成・支援金・給付・奨励・交付」が無い
  2. 除外: 候補のうち、承認済みの一覧(data/local_exclusions.json)と
           URL・名前・取得先(実施主体)が**すべて一致**したものだけ
  3. 要確認: 候補だが承認済みの一覧に無いもの。外さずに掲載し、項目に review_candidate を付けて記録する

承認済みの一覧に載せるのは、検証部が公式ページを確かめ、守り部が除外の妥当性を見て、
責任者(小柳さん)が承認したものだけ。載せた後に名前やURLが変わったら一致しなくなり、自動で掲載に戻る
(外れたままになることはない)。

一覧が読めない・形が違う・候補にならない名前が載っている(=本物の補助金を消すおそれ)ときは
ListingReviewError で止める(取り込み全体を止め、古いデータのまま公開を続ける=安全側)。
年度だけでは外さない(古い年度の扱いは fetch_local.py の既存の決まりのまま。ここでは見ない)。
"""
import json
import os
import re

DEFAULT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "local_exclusions.json")

# 補助金ではない公募・募集を示す語(語だけでは外さない。候補にするだけ)
PROCUREMENT_RE = re.compile(r"業務委託|委託業務|入札|企画提案|プロポーザル|公募型見積")
EVENT_RE = re.compile(r"参加企業|登壇|出展者?の?募集|ピッチ|コンテスト|セミナー|説明会|商談会|交流会|イベント")
# これがあれば、資金の支援が含まれる可能性があるので候補にしない
MONEY_RE = re.compile(r"補助|助成|支援金|給付|奨励|交付")

REQUIRED_KEYS = ("source_url", "name", "source", "reason", "verified_by", "reviewed_by", "approved_by", "approved_on")

DECISION_KEEP = "keep"
DECISION_REVIEW = "review"
DECISION_EXCLUDE = "exclude"


class ListingReviewError(Exception):
    """承認済みの一覧が使えない。取り込みを止める。"""


def _norm(s):
    return re.sub(r"\s+", " ", str(s or "")).strip()


def candidate_reason(name):
    """候補なら理由の文字列、候補でなければ None。"""
    n = _norm(name)
    if not n or MONEY_RE.search(n):
        return None
    if PROCUREMENT_RE.search(n):
        return "補助金ではない可能性(入札・業務委託・企画提案の公募)"
    if EVENT_RE.search(n):
        return "補助金ではない可能性(イベント・コンテスト・参加募集)"
    return None


def load_exclusions(path=DEFAULT_PATH):
    """承認済みの一覧を読む。ファイルが無ければ空。壊れている・形が違えば ListingReviewError。"""
    if not os.path.exists(path):
        return []
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        raise ListingReviewError(f"承認済みの一覧を読めません: {e}") from e
    items = data.get("items") if isinstance(data, dict) else None
    if not isinstance(items, list):
        raise ListingReviewError("承認済みの一覧に items(配列)がありません")
    seen = set()
    for i, e in enumerate(items):
        if not isinstance(e, dict):
            raise ListingReviewError(f"承認済みの一覧の {i + 1} 件目が形どおりではありません")
        missing = [k for k in REQUIRED_KEYS if not _norm(e.get(k))]
        if missing:
            raise ListingReviewError(f"承認済みの一覧の {i + 1} 件目に足りない項目: {', '.join(missing)}")
        if not re.match(r"^https?://", _norm(e["source_url"])):
            raise ListingReviewError(f"承認済みの一覧の {i + 1} 件目の URL が正しくありません")
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", _norm(e["approved_on"])):
            raise ListingReviewError(f"承認済みの一覧の {i + 1} 件目の承認日が YYYY-MM-DD ではありません")
        # 候補にならない名前(補助金の語を含む等)は、一覧に載っていても外させない
        if candidate_reason(e["name"]) is None:
            raise ListingReviewError(
                f"承認済みの一覧の {i + 1} 件目は候補の条件に当たらない名前です(本物の補助金を外すおそれ): {e['name'][:40]}")
        key = (_norm(e["source_url"]), _norm(e["name"]), _norm(e["source"]))
        if key in seen:
            raise ListingReviewError(f"承認済みの一覧に同じものが2回あります: {e['name'][:40]}")
        seen.add(key)
    return items


def decide(name, source_url, source, exclusions):
    """(判定, 理由)。判定は keep / review / exclude。"""
    reason = candidate_reason(name)
    if reason is None:
        return DECISION_KEEP, None
    key = (_norm(source_url), _norm(name), _norm(source))
    for e in exclusions:
        if (_norm(e["source_url"]), _norm(e["name"]), _norm(e["source"])) == key:
            return DECISION_EXCLUDE, f"承認済みの除外({e['approved_on']}・{_norm(e['reason'])})"
    return DECISION_REVIEW, reason
