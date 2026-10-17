"""教育ナレッジ（トークスクリプト化）— 訪問保全設計 スライス3。

対話ログの「懸念 × 返し方」を早期解約率と突き合わせ、**この懸念にはこの返し方が効いた**を
教育カードにする。新人・全体の対応レベルを積み上げる仕組み（docs/churn/訪問保全と教育ループ設計）。

規律:
- 成熟実績・解約前接触のみ（免疫時間）。懸念と返し方の**両方が非空**の接触だけ数える。
- 少数事例を「効いた型」と断定しない：母数不足は reference で明示。
- 測るのは**返し方（型）の効き**であって個人の成績ではない（人事評価転用禁止・churn-retention-ops）。
- 接触は無作為でない＝生存者バイアスが残る。因果は experiment の段階導入で確認（＝参考）。
"""
from __future__ import annotations

from .config import MIN_RELIABLE_N
from .effect_learning import _contacts_index, _mature_resolved, _qualifying_contacts
from .experiment import wilson_interval


def _qualifying_pairs(record, idx, f1, f2):
    """解約前・f1とf2の両方が非空の接触から (f1値, f2値) の並び（免疫時間・空タグ除外）。"""
    out = []
    for c in _qualifying_contacts(record, idx):
        v1 = (c.get(f1) or "").strip()
        v2 = (c.get(f2) or "").strip()
        if v1 and v2:
            out.append((v1, v2))
    return out


def concern_playbook(records, contacts, mature_before,
                     concern_field="concern", approach_field="approach",
                     min_reliable=MIN_RELIABLE_N):
    """懸念ごとに「効いた返し方（低い解約率）」を出す教育カードの並び。"""
    idx = _contacts_index(contacts)
    per = {}   # (concern, approach) -> {n, churn}
    for r in _mature_resolved(records, mature_before):
        churn = r.get("is_early_churn") or 0
        for con, app in set(_qualifying_pairs(r, idx, concern_field, approach_field)):
            b = per.setdefault((con, app), {"n": 0, "churn": 0})
            b["n"] += 1
            b["churn"] += churn

    concerns = {}
    for (con, app), b in per.items():
        concerns.setdefault(con, []).append({
            "approach": app, "n": b["n"], "churn": b["churn"],
            "rate": b["churn"] / b["n"] if b["n"] else 0.0,
            # 早期解約率のWilson上限（不確実性ペナルティ）。少数の偶然0%を「効いた型」に祭り上げない。
            "rate_ub": wilson_interval(b["churn"], b["n"])[1],
            "reference": b["n"] < min_reliable})

    rows = []
    for con, apps in sorted(concerns.items()):
        # 「確信をもって低い」順＝Wilson上限が低い順・母数多い順（生率ではない）。
        apps.sort(key=lambda a: (a["rate_ub"], -a["n"]))
        best = apps[0]
        rows.append({
            "concern": con, "best_approach": best["approach"], "rate": best["rate"],
            "n": best["n"], "reference": best["reference"], "alternatives": apps[1:]})
    return rows


def render_html(rows, path):
    """教育カード（懸念→効いた返し方）をHTML出力（表示層・出力は private/ 限定）。"""
    import html
    cards = []
    for r in rows:
        ref = "（参考・母数少）" if r["reference"] else ""
        alts = "".join(
            f'<li>{html.escape(a["approach"])} … 解約{a["rate"]*100:.0f}%（n={a["n"]}）</li>'
            for a in r["alternatives"])
        cards.append(
            '<div style="border-bottom:1px solid #E4E4E4;padding:12px 0">'
            f'<div style="color:#6B6B6B;font-size:12px">この懸念には</div>'
            f'<div style="font-size:16px;font-weight:600">{html.escape(r["concern"])}</div>'
            f'<div style="margin-top:6px">効いた返し方: <b>{html.escape(r["best_approach"])}</b>'
            f'（早期解約 {r["rate"]*100:.0f}%・n={r["n"]}）{ref}</div>'
            + (f'<ul style="color:#6B6B6B;font-size:12px;margin:6px 0">{alts}</ul>' if alts else "")
            + '</div>')
    doc = (
        '<!doctype html><meta charset="utf-8"><title>保全トークスクリプト</title>'
        '<style>body{font-family:Meiryo,"Noto Sans JP",sans-serif;padding:16px;max-width:760px}'
        'h1{font-size:20px}</style>'
        '<h1>この懸念には、この返し方（教育カード）</h1>'
        '<p style="font-size:12px;color:#6B6B6B">対応（型）の共有であって個人の成績ではありません。'
        '接触は無作為でないため参考（因果は段階導入で確認）。母数不足は参考。合成データ。</p>'
        + "".join(cards))
    with open(path, "w", encoding="utf-8") as f:
        f.write(doc)
