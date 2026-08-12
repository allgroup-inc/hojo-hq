"""早期解約率のコホート集計（契約月別）＝ 3%目標のスコアボード。

品質規律（churn-model-quality-gate）:
- 早期解約率は確定分（is_resolved）のみで算出。
- 観測中コホート（6ヶ月窓が未確定で生存者が定まらず率が跳ねる）は observing フラグを立て、
  全体率からも除外する（免疫時間／打ち切りバイアス回避）。
- 確定数が少ないコホート（< MIN_RELIABLE_N）は reference（参考）。
"""
from __future__ import annotations
from datetime import date

from .config import MIN_RELIABLE_N, EARLY_CHURN_MONTHS
from .score import score_record


def _ym(d):
    return f"{d.year}-{d.month:02d}"


def _cohort_matured(ym, as_of, months=EARLY_CHURN_MONTHS):
    """暦ベースの成熟判定：その月末の契約が6ヶ月経過済みか（＝月初から months+1 ヶ月後 <= as_of）。
    resolved/total 比では解約アウトカムと交絡するため、暦で判定する。"""
    y, m = int(ym[:4]), int(ym[5:7])
    idx = y * 12 + (m - 1) + months + 1
    return date(idx // 12, idx % 12 + 1, 1) <= as_of


def cohort_rows(records, as_of, min_reliable=MIN_RELIABLE_N, model=None):
    """契約月別の早期解約率。model を渡すと観測中コホートの「着地見込み率」も推計する（確定値とは別）。

    着地見込み = そのコホート**全メンバーの予測リスク（原契約時点）の平均**。
    較正が取れていれば、これが早期解約率の期待値になる（＝前向きの推計）。
    確定分の実解約を実数1で数え、継続中を予測で足す「ブレンド」は、早期解約が前倒しで起きるため
    生存者を過大評価する（打ち切りバイアス）。それを避けるため実現値と混ぜない。**確定値ではない**。
    """
    groups = {}
    for r in records:
        ad = r.get("apply_date")
        if not ad:
            continue
        g = groups.setdefault(_ym(ad), {"total": 0, "resolved": 0, "churn": 0, "members": []})
        g["total"] += 1
        g["members"].append(r)
        if r.get("is_resolved"):
            g["resolved"] += 1
            g["churn"] += r.get("is_early_churn") or 0
    rows = []
    for ym in sorted(groups):
        g = groups[ym]
        observing = not _cohort_matured(ym, as_of)  # 暦ベース（解約と交絡させない）
        # 着地見込みは観測中のみ・モデルありのとき。全メンバーの予測リスク平均（較正前提の前向き推計）
        projected = None
        if observing and model is not None and g["total"]:
            projected = sum(score_record(m, model)["risk"] for m in g["members"]) / g["total"]
        rows.append({
            "ym": ym, "total": g["total"], "resolved": g["resolved"], "churn": g["churn"],
            "rate": (g["churn"] / g["resolved"]) if g["resolved"] else None,
            "projected_rate": projected,
            "maturity": g["resolved"] / g["total"] if g["total"] else 0.0,
            "observing": observing,
            "reference": g["resolved"] < min_reliable,
        })
    return rows


def overall_rate(rows):
    """全体の早期解約率（観測中コホートを除いた成熟分のみ）。成熟データ皆無なら rate=None（0%と断定しない）。"""
    res = sum(r["resolved"] for r in rows if not r["observing"])
    churn = sum(r["churn"] for r in rows if not r["observing"])
    return {"resolved": res, "churn": churn, "rate": (churn / res) if res else None}


def render_html(rows, overall, path, target=0.03):
    """コホート表＋全体率と目標ラインをHTML出力（表示層・出力は private/ 限定）。"""
    import html
    trs = []
    for r in rows:
        if r["observing"]:
            cell = "観測中(未確定)"
        elif r["rate"] is None:
            cell = "確定なし"
        else:
            cell = f'{r["rate"]*100:.1f}%' + (" 参考" if r["reference"] else "")
        # 着地見込み（推計・確定値とは別）。観測中で推計がある時だけ表示
        if r.get("projected_rate") is not None and r["observing"]:
            proj = f'{r["projected_rate"]*100:.1f}%<span style="color:#888">(見込)</span>'
        else:
            proj = "—"
        trs.append(f'<tr><td>{html.escape(r["ym"])}</td><td>{r["total"]}</td>'
                   f'<td>{r["resolved"]}</td><td>{r["churn"]}</td><td>{cell}</td>'
                   f'<td>{proj}</td></tr>')
    if overall["rate"] is None:
        head = f'全体 <b>算出不能</b>（成熟したコホートがまだありません）／ 目標 {target*100:.0f}%'
    else:
        o = overall["rate"] * 100
        head = (f'全体 <b>{o:.1f}%</b> ／ 目標 {target*100:.0f}%（差 {o-target*100:+.1f}pt）'
                f' ／ 成熟 {overall["churn"]}/{overall["resolved"]}件')
    doc = (
        '<!doctype html><meta charset="utf-8"><title>早期解約率コホート</title>'
        '<style>body{font-family:Meiryo,"Noto Sans JP",sans-serif;padding:16px}'
        'table{border-collapse:collapse}th,td{border:1px solid #ccc;padding:6px}'
        'th{background:#00335C;color:#fff}</style>'
        f'<h1>早期解約率 コホート（成熟分のみ）</h1>'
        f'<p>{head}</p>'
        '<p style="font-size:12px;color:#888">観測中(6ヶ月未確定)は確定率を出さず全体からも除外。'
        '「着地見込」はコホート全員の予測リスク平均＝較正前提の前向き推計・参考（確定値ではない）。'
        '少件数は参考。合成データ。</p>'
        '<table><thead><tr><th>契約月</th><th>契約数</th><th>確定</th><th>解約</th>'
        '<th>早期解約率(確定)</th><th>着地見込(推計)</th></tr></thead>'
        f'<tbody>{"".join(trs)}</tbody></table>')
    with open(path, "w", encoding="utf-8") as f:
        f.write(doc)
