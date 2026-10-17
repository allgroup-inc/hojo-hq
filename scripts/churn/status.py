"""現ステータス分類（徳元さん回答 2026-08-17・詳細は docs/churn/現ステータス分類ルール.md）。

現ステータス18種を「継続／早期解約／対象外／母集団外」に分ける。早期解約率の分母は
「継続＋早期解約」＝**保全で防げる離脱**に限定し、対象外（死亡・クーリングオフ・告知解除）は
除外して**件数を併記**する（小柳さん決裁 2026-08-17「除外＋件数併記」）。

- 解約日 = 初回保険料着金日（※成立済のときは使わない＝着金日であって解約ではない）。
- 契約開始 = 契約日（保険料発生の起点）。
- 「不成立【引受後未入金】」＝初回引落前に落ちた＝早期解約。解約日が欠損しても早期解約とし監査フラグを立てる。
"""
from __future__ import annotations

from .config import EARLY_CHURN_MONTHS
from .dates import has_reached_months, is_within_months

CONTINUING_STATUSES = {"成立済"}

EARLY_CHURN_STATUSES = {
    "解約予定【成立後】", "成立後CAN【解約】", "失効中", "未払消滅",
    "不成立【引受後CAN】", "不成立【引受後未入金】",
}

# 対象外（保全で防げない離脱）→ 除外し件数を併記
EXCLUDED_STATUSES = {
    "死亡解約": "死亡",
    "取消・解除【成立後】": "告知解除",
    "契約取り消し": "クーリングオフ",
    "契約取り消し【引受後】": "クーリングオフ",
    "契約取り消し【成立後】": "クーリングオフ",
}

# 母集団外（そもそも契約成立せず）
OUT_OF_SCOPE_STATUSES = {
    "謝絶", "PL申込【申込取消】", "PL申込【送信前】",
    "受注後CAN【受渡未】", "不成立【引受前】",
}


def _norm(status):
    return (status or "").strip()


def classify_status(status):
    """現ステータス → 継続 / 早期解約 / 対象外 / 母集団外 / 不明。"""
    s = _norm(status)
    if s in CONTINUING_STATUSES:
        return "継続"
    if s in EARLY_CHURN_STATUSES:
        return "早期解約"
    if s in EXCLUDED_STATUSES:
        return "対象外"
    if s in OUT_OF_SCOPE_STATUSES:
        return "母集団外"
    return "不明"


def excluded_reason(status):
    """対象外の理由（死亡／告知解除／クーリングオフ）。対象外でなければ None。"""
    return EXCLUDED_STATUSES.get(_norm(status))


def status_scope(status, apply_date, cancel_date, as_of, months=EARLY_CHURN_MONTHS):
    """現ステータス＋日付から、分析スコープと早期解約/成熟フラグを返す。"""
    cat = classify_status(status)
    out = {"category": cat, "in_scope": cat in ("継続", "早期解約"),
           "is_early_churn": False, "is_resolved": False, "is_continuing": False,
           "excluded_reason": excluded_reason(status) if cat == "対象外" else None,
           "date_missing": False}

    if cat == "早期解約":
        if cancel_date is None:
            # 解約日欠損でも現ステータスが解約を示す＝churn。生存者に混ぜない（KPIを過小にしない）。
            # 6ヶ月内かは日付が無く確定できないが、これらは初回引落前後の離脱が大半＝早期扱い＋監査フラグ。
            out["is_resolved"] = True
            out["date_missing"] = True
            out["is_early_churn"] = True
        elif apply_date is not None:
            out["is_resolved"] = True
            out["is_early_churn"] = is_within_months(apply_date, cancel_date, months)
    elif cat == "継続":
        if apply_date is not None and has_reached_months(apply_date, as_of, months):
            out["is_resolved"] = True          # 6ヶ月生存＝成熟・非早期
        elif apply_date is not None:
            out["is_continuing"] = True        # 6ヶ月未満・継続中＝これから手を打てる
    return out


def scope_summary(statuses):
    """現ステータスの並びを、カテゴリ別件数＋対象外の理由別件数に集計（除外の件数併記用）。"""
    summ = {"継続": 0, "早期解約": 0, "対象外": 0, "母集団外": 0, "不明": 0,
            "excluded_by_reason": {}}
    for s in statuses:
        cat = classify_status(s)
        summ[cat] += 1
        if cat == "対象外":
            r = excluded_reason(s) or "その他"
            summ["excluded_by_reason"][r] = summ["excluded_by_reason"].get(r, 0) + 1
    return summ
