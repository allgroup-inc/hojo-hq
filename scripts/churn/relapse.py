"""再発監視（A3）＝「一度救えた契約」がまた未収に戻ったのを早期に拾う。

一度未収が解消（＝救えた）した契約は再発しやすい。Ⅳ列の未収履歴を**エピソード**
（連続する未収の塊）に分け、**解消のギャップをはさんで再び未収**が出たものを「再発」として
監視リストに載せる。次の未収サイクルの早い段階で一声かけ、長期継続につなげる（docs/churn/連動アイデア）。

- 未収連鎖トリガー(triggers.unpaid_trigger)は「直近の連続」だけを見る。再発は**過去に解消をはさむ**
  点が違う＝直近streakが1でも拾える、追加の早期シグナル。
- 対象は継続中(is_scoreable or 現ステータス＝継続)。年欠損の未収月は timeline に載せない（監査は unpaid 側）。
- 直近 recency_months 以内に最新の未収があるものだけ（＝いままさに再発中）。値は 決裁候補。
- **優先度順(triage)への組み込みは小柳さん決裁事項**。ここは検知と監視リストの提示まで。
"""
from __future__ import annotations

RELAPSE_RECENT_MONTHS = 3   # 最新未収が直近何ヶ月以内なら「再発中」とみなすか（決裁候補）


def _ordinal(y, m):
    return y * 12 + (m - 1)


def unpaid_episodes(unpaid_months):
    """未収月 (年, 月) を連続エピソード（塊）に分割。古い順・年欠損は除外・重複排除。"""
    idx = sorted({_ordinal(y, m) for (y, m) in unpaid_months if y})
    episodes = []
    for o in idx:
        if episodes and o == episodes[-1][-1] + 1:
            episodes[-1].append(o)
        else:
            episodes.append([o])
    return [[(o // 12, o % 12 + 1) for o in ep] for ep in episodes]


def is_relapse(record, as_of, recency_months=RELAPSE_RECENT_MONTHS):
    """一度解消（エピソード間にギャップ）した後、直近で再び未収＝再発中か。"""
    active = record.get("is_scoreable") or record.get("status_category") == "継続"
    if not active:
        return False
    eps = unpaid_episodes(record.get("unpaid_months") or [])
    if len(eps) < 2:
        return False
    ly, lm = eps[-1][-1]                       # 最新エピソードの最後の未収月
    return (_ordinal(as_of.year, as_of.month) - _ordinal(ly, lm)) <= recency_months


def relapse_candidates(records, as_of, recency_months=RELAPSE_RECENT_MONTHS):
    """再発中の契約を、エピソード数の多い順・守れる金額(=保険料)の大きい順に並べて返す。"""
    out = []
    for r in records:
        if not is_relapse(r, as_of, recency_months):
            continue
        eps = unpaid_episodes(r.get("unpaid_months") or [])
        out.append({
            "customer_id": r.get("customer_id"), "apply_id": r.get("apply_id"),
            "product": r.get("product"), "agent_id": r.get("agent_id"),
            "amount": r.get("amount") or 0,
            "episodes": len(eps), "last_unpaid": eps[-1][-1]})
    out.sort(key=lambda c: (-c["episodes"], -c["amount"]))
    return out


def render_html(rows, path):
    """再発監視リスト（営業向け）をHTML出力（表示層・出力は private/ 限定）。"""
    import html
    trs = []
    for c in rows:
        ly, lm = c["last_unpaid"]
        trs.append(
            f'<tr><td>{html.escape(str(c.get("customer_id") or "—"))}</td>'
            f'<td>{html.escape(str(c.get("product")))}</td>'
            f'<td>{html.escape(str(c.get("agent_id")))}</td>'
            f'<td>{c["episodes"]}回</td><td>{ly}年{lm}月</td>'
            f'<td>{int(c["amount"]):,}円</td></tr>')
    doc = (
        '<!doctype html><meta charset="utf-8"><title>再発監視リスト</title>'
        '<style>body{font-family:Meiryo,"Noto Sans JP",sans-serif;padding:16px}'
        'table{border-collapse:collapse;width:100%}th,td{border:1px solid #ccc;padding:6px;font-size:13px}'
        'th{background:#00335C;color:#fff}</style>'
        f'<h1>再発監視リスト（{len(rows)}件・未収の再発回数が多い順）</h1>'
        '<p style="font-size:12px;color:#6B6B6B">一度未収が解消した後、また未収に戻った契約。'
        '再発は解約に近い前兆。早めの一声で長期継続へ。連絡は人が実行。合成データ。</p>'
        '<table><thead><tr><th>顧客ID</th><th>商品</th><th>営業</th>'
        '<th>未収エピソード</th><th>直近の未収</th><th>保険料</th></tr></thead>'
        f'<tbody>{"".join(trs)}</tbody></table>')
    with open(path, "w", encoding="utf-8") as f:
        f.write(doc)
