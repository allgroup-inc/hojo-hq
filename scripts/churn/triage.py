"""今日の要接触（統合トリアージ）＝ ②予防トリガー＋守れる金額の高リスクを1本に束ねる。

複数のきっかけを重複排除→優先度＋守れる金額で並べ→キャパ内に絞る。上限超過は繰り越し
（落とした件数と最高“守れる金額”を明示＝no silent cap）。docs/churn/クローズドループ設計.md。
"""
from __future__ import annotations

from .score import score_record, display_pct
from .triggers import (prevention_trigger, initial_contact_trigger, unpaid_trigger,
                       _recent_streak)
from .effect_learning import _contacts_index
from .value import saveable as _saveable

# きっかけ → 営業向け「今日の一手」（提案。最終判断は人。営業別スコアは出さない）
_ACTION = {
    "未払消滅目前": "至急架電＋コンビニ用紙で入金依頼（消滅目前）",
    "未収2連続": "架電で入金確認",
    "不着": "初回引落の不着を架電確認",
    "遅延": "支払いの遅れを架電確認",
    "口座確認": "引落口座を確認",
    "初動": "初回のごあいさつ・状況確認",
    "高リスク": "様子伺いの連絡",
}


def recommend_action(trigger, account_issue=False, streak=0):
    """きっかけ（＋口座不備）から営業向けの“ひとこと”を返す。あくまで提案・最終判断は人。"""
    base = _ACTION.get(trigger, "状況確認")
    if account_issue and trigger in ("未払消滅目前", "未収2連続", "口座確認", "不着", "遅延"):
        base += "／口座不備の再設定"
    return base

# きっかけの優先度（小さいほど先）。小柳さん決裁 2026-08-17:
# 未払消滅目前(3ヶ月連続未収・4ヶ月目で消滅)＞不着＞遅延＞未収2連続＞口座確認＞初動＞高リスク。
PRIORITY = {"未払消滅目前": 0, "不着": 1, "遅延": 2, "未収2連続": 3,
            "口座確認": 4, "初動": 5, "高リスク": 6}


def classify(records, model, as_of, contacts=None):
    """継続中レコードを、きっかけつきの候補に分類する（1契約=1候補・重複排除済み）。

    contacts を渡すと、契約直後・未接触の継続契約を「初動」として拾う（保全は早いほど効く）。
    優先度（PRIORITY）: 未払消滅目前 ＞ 不着/遅延 ＞ 未収2連続 ＞ 口座確認 ＞ 初動 ＞ 高リスク。
    """
    idx = _contacts_index(contacts) if contacts is not None else None
    cands = []
    for r in records:
        up = unpaid_trigger(r, as_of)          # 未払消滅目前/未収2連続 or None（任意テニュア）
        if not r.get("is_scoreable"):
            # 早期枠(<6mo)外でも、未払消滅の恐れは拾う（消滅は任意テニュアで起きる）
            if up in ("未払消滅目前", "未収2連続"):
                trig = up
            else:
                continue
        else:
            prev = prevention_trigger(r, as_of)   # 不着/遅延/口座確認 or None
            # 優先度どおりに1つ選ぶ
            if up == "未払消滅目前":
                trig = up
            elif prev in ("不着", "遅延"):
                trig = prev
            elif up == "未収2連続":
                trig = up
            elif prev == "口座確認":
                trig = prev
            elif idx is not None and initial_contact_trigger(r, idx, as_of) is not None:
                trig = "初動"
            else:
                trig = None
        s = score_record(r, model)
        if trig is None:
            if s["band"] != "high":
                continue  # どのトリガーも高リスクもなければ候補でない
            trig = "高リスク"
        streak = _recent_streak(r.get("unpaid_months", []), as_of)
        account_issue = bool(r.get("unpaid_account_issue"))
        cands.append({
            "customer_id": r.get("customer_id"), "apply_id": r.get("apply_id"),
            "product": r.get("product"), "agent_id": r.get("agent_id"),
            "trigger": trig, "risk": s["risk"], "risk_pct": display_pct(s["risk"]),
            "band": s["band"], "hit_factors": s["hit_factors"],
            "saveable": _saveable(s["risk"], r.get("amount")),
            "unpaid_streak": streak, "account_issue": account_issue,
            "recommendation": recommend_action(trig, account_issue, streak),
        })
    return cands


def triage(candidates, capacity):
    """優先度→守れる金額順に並べ、キャパで today / carry に分ける。繰り越しは件数・最高額を明示。"""
    # 帯内は 未収連続が長い順 → 守れる金額順（消滅が近い人を先に）
    ordered = sorted(candidates, key=lambda c: (PRIORITY.get(c["trigger"], 99),
                                                -c.get("unpaid_streak", 0), -c["saveable"]))
    today = ordered[:capacity]
    carry = ordered[capacity:]
    stats = {
        "carry_count": len(carry),
        "carry_max_saveable": max((c["saveable"] for c in carry), default=0.0),
        "total": len(ordered),
    }
    return today, carry, stats


def render_html(today, carry, stats, path, capacity):
    """今日の要接触をHTML出力（表示層・出力は private/ 限定）。"""
    import html
    trs = []
    for i, c in enumerate(today, 1):
        stage = c.get("unpaid_streak", 0)
        stage_txt = f"未収{stage}ヶ月" if stage else "—"
        if c.get("account_issue"):
            stage_txt += "・口座不備"
        trs.append(
            f'<tr><td>{i}</td><td>{html.escape(str(c["trigger"]))}</td>'
            f'<td>{html.escape(str(c.get("customer_id") or "—"))}</td>'
            f'<td>{html.escape(str(c.get("product")))}</td>'
            f'<td>{html.escape(stage_txt)}</td>'
            f'<td>{c["risk_pct"]}%</td><td>{c["saveable"]:,.0f}円</td>'
            f'<td>{html.escape(str(c.get("recommendation", "")))}</td></tr>')
    carry_note = (
        f'キャパ{capacity}件/日 超過 {stats["carry_count"]}件は翌日へ繰り越し'
        f'（最高“守れる金額” {stats["carry_max_saveable"]:,.0f}円）'
        if stats["carry_count"] else 'キャパ内・取りこぼしなし')
    doc = (
        '<!doctype html><meta charset="utf-8"><title>今日の要接触</title>'
        '<style>body{font-family:Meiryo,"Noto Sans JP",sans-serif;padding:16px}'
        'table{border-collapse:collapse;width:100%}th,td{border:1px solid #ccc;padding:6px;font-size:13px}'
        'th{background:#00335C;color:#fff}</style>'
        f'<h1>今日の要接触（{len(today)}件 / 要接触合計 {stats["total"]}件）</h1>'
        f'<p>{carry_note}。優先度：未払消滅目前＞不着＞遅延＞未収2連続＞口座確認＞初動＞高リスク、各内で守れる金額順。'
        '顧客連絡は人が実行。合成データ。</p>'
        '<table><thead><tr><th>#</th><th>きっかけ</th><th>顧客ID</th><th>商品</th>'
        '<th>状態</th><th>リスク</th><th>守れる金額</th><th>今日の一手（提案）</th></tr></thead>'
        f'<tbody>{"".join(trs)}</tbody></table>')
    with open(path, "w", encoding="utf-8") as f:
        f.write(doc)
