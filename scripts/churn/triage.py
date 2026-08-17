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
from .config import VISIT_SAVEABLE_MIN

# きっかけ → 「今日やること（手段抜きの論点）」。手段(架電/訪問)は contact_channel が決める
_TOPIC = {
    "未払消滅目前": "入金のご相談＋コンビニ用紙（消滅目前）",
    "未収2連続": "入金確認",
    "不着": "初回引落の不着を確認",
    "遅延": "支払いの遅れを確認",
    "口座確認": "引落口座を確認",
    "初動": "初回のごあいさつ・状況確認",
    "高リスク": "様子伺い",
}


def contact_channel(band, saveable, trigger, saveable_min=VISIT_SAVEABLE_MIN):
    """接触手段を決める。高リスク×守れる金額大（または未払消滅目前×大）は「訪問」、他は「架電」。

    訪問は重コストなので「守れる金額×リスク」が高い人に絞る（しきい値=小柳さん決裁事項）。
    """
    high_value = (saveable or 0) >= saveable_min
    high_stakes = band == "high" or trigger == "未払消滅目前"
    return "訪問" if (high_value and high_stakes) else "架電"


def recommend_action(trigger, account_issue=False, channel="架電"):
    """きっかけ（＋口座不備・接触手段）から営業向けの“ひとこと”を返す。提案・最終判断は人。"""
    topic = _TOPIC.get(trigger, "状況確認")
    if account_issue and trigger in ("未払消滅目前", "未収2連続", "口座確認", "不着", "遅延"):
        topic += "／口座不備の再設定"
    verb = "訪問して挨拶＋" if channel == "訪問" else "架電で"
    return verb + topic

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
        sv = _saveable(s["risk"], r.get("amount"))
        channel = contact_channel(s["band"], sv, trig)
        cands.append({
            "customer_id": r.get("customer_id"), "apply_id": r.get("apply_id"),
            "product": r.get("product"), "agent_id": r.get("agent_id"),
            "trigger": trig, "risk": s["risk"], "risk_pct": display_pct(s["risk"]),
            "band": s["band"], "hit_factors": s["hit_factors"], "saveable": sv,
            "unpaid_streak": streak, "account_issue": account_issue, "channel": channel,
            "recommendation": recommend_action(trig, account_issue, channel),
        })
    return cands


def triage(candidates, capacity):
    """優先度→守れる金額順に並べ、キャパで today / carry に分ける。繰り越しは件数・最高額を明示。"""
    # 帯内は「守れる金額」順（未収連続数はきっかけ自体が表すので二次キーにしない：帯内で
    # streakを優先すると不着等が金額順から外れ、消滅済み(streak≥4)を救える目前より上げてしまう）
    ordered = sorted(candidates, key=lambda c: (PRIORITY.get(c["trigger"], 99), -c["saveable"]))
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
        parts = []
        if c.get("trigger") in ("未払消滅目前", "未収2連続") and c.get("unpaid_streak"):
            parts.append(f"未収{c['unpaid_streak']}ヶ月")   # 未収連鎖トリガーのときだけ「未収」表記
        if c.get("account_issue"):
            parts.append("口座不備")
        stage_txt = "・".join(parts) if parts else "—"
        trs.append(
            f'<tr><td>{i}</td><td>{html.escape(str(c["trigger"]))}</td>'
            f'<td>{html.escape(str(c.get("customer_id") or "—"))}</td>'
            f'<td>{html.escape(str(c.get("product")))}</td>'
            f'<td>{html.escape(stage_txt)}</td>'
            f'<td>{c["risk_pct"]}%</td><td>{c["saveable"]:,.0f}円</td>'
            f'<td>{html.escape(str(c.get("channel", "架電")))}</td>'
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
        '<th>状態</th><th>リスク</th><th>守れる金額</th><th>手段</th>'
        '<th>今日の一手（提案）</th></tr></thead>'
        f'<tbody>{"".join(trs)}</tbody></table>')
    with open(path, "w", encoding="utf-8") as f:
        f.write(doc)
