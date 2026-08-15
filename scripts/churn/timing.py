"""有効な架電時期（強化6）。

「いつ解約が起きるか」をデータから出し、その手前を架電の勝負どきにする。
まずは**解約ハザード曲線**＝成熟した早期解約者の「契約→解約の日数」分布。
モデル不要の純・記述統計（断定しない・母数不足は参考）。

- 継続中・非早期解約は混ぜない（分布が歪むため）。成熟した早期解約者のみ。
- バケツ幅は `HAZARD_BUCKET_DAYS`（小柳さん決裁事項）。
- `peak_window` は最も解約が集中するバケツ（＝ヤマ）。この手前が架電適期の基準になる（強化6-2で使用）。
"""
from __future__ import annotations

from .config import HAZARD_BUCKET_DAYS, MIN_RELIABLE_N, EARLY_CHURN_MONTHS


def _early_churn_tenures(records):
    """成熟した早期解約者の「契約→解約の日数」（0以上）の並び。"""
    out = []
    for r in records:
        if not (r.get("is_resolved") and (r.get("is_early_churn") or 0)):
            continue
        ad, cd = r.get("apply_date"), r.get("cancel_date")
        if ad and cd:
            days = (cd - ad).days
            if days >= 0:
                out.append(days)
    return out


def churn_hazard_by_tenure(records, bucket_days=HAZARD_BUCKET_DAYS,
                           horizon_days=EARLY_CHURN_MONTHS * 31, min_reliable=MIN_RELIABLE_N):
    """解約ハザード曲線：早期解約者の経過日数分布（バケツ別の件数・割合・累積割合）。"""
    tenures = _early_churn_tenures(records)
    total = len(tenures)
    n_buckets = max(1, -(-horizon_days // bucket_days))  # 天井除算
    counts = [0] * n_buckets
    over = 0
    for d in tenures:
        idx = d // bucket_days
        if idx < n_buckets:
            counts[idx] += 1
        else:
            over += 1  # 早期(6ヶ月)を超える解約はハザード対象外（ガード）
    rows, cum = [], 0
    for i, c in enumerate(counts):
        cum += c
        rows.append({
            "lo": i * bucket_days, "hi": (i + 1) * bucket_days, "count": c,
            "share": (c / total) if total else 0.0,
            "cum_share": (cum / total) if total else 0.0,
        })
    return {"total": total, "bucket_days": bucket_days, "over_horizon": over,
            "rows": rows, "reference": total < min_reliable}


def peak_window(hazard):
    """最も解約が集中するバケツの (lo, hi)。件数ゼロなら (None, None)。"""
    rows = hazard.get("rows", [])
    best = max(rows, key=lambda r: r["count"], default=None)
    if not best or best["count"] == 0:
        return (None, None)
    return (best["lo"], best["hi"])


def render_html(hazard, path):
    """解約ハザード曲線をHTML出力（表示層・出力は private/ 限定）。"""
    import html
    pk = peak_window(hazard)
    trs = []
    max_share = max((r["share"] for r in hazard["rows"]), default=0.0) or 1.0
    for r in hazard["rows"]:
        if r["count"] == 0 and r["cum_share"] in (0.0, 1.0) and r["lo"] > 0 and r["cum_share"] == 1.0:
            continue  # 末尾の空バケツは省略（見やすさ）
        bar_w = int(round(r["share"] / max_share * 200))
        mark = " ◀ヤマ" if (r["lo"], r["hi"]) == pk else ""
        trs.append(
            f'<tr><td>{r["lo"]}〜{r["hi"]}日{html.escape(mark)}</td><td>{r["count"]}</td>'
            f'<td>{r["share"]*100:.1f}%</td><td>{r["cum_share"]*100:.1f}%</td>'
            f'<td><div style="background:#F88800;height:12px;width:{bar_w}px"></div></td></tr>')
    ref = '（※母数不足＝参考）' if hazard["reference"] else ''
    pk_txt = (f'解約のヤマは契約後 <b>{pk[0]}〜{pk[1]}日</b> ＝ その手前が架電の勝負どき'
              if pk[0] is not None else '解約実績がまだありません')
    doc = (
        '<!doctype html><meta charset="utf-8"><title>解約ハザード曲線</title>'
        '<style>body{font-family:Meiryo,"Noto Sans JP",sans-serif;padding:16px}'
        'table{border-collapse:collapse}th,td{border:1px solid #ccc;padding:6px;font-size:13px}'
        'th{background:#00335C;color:#fff}</style>'
        f'<h1>いつ解約が起きるか（早期解約 {hazard["total"]}件{html.escape(ref)}）</h1>'
        f'<p>{pk_txt}。合成データ。</p>'
        '<table><thead><tr><th>契約からの経過</th><th>件数</th><th>割合</th>'
        '<th>累積</th><th>分布</th></tr></thead>'
        f'<tbody>{"".join(trs)}</tbody></table>')
    with open(path, "w", encoding="utf-8") as f:
        f.write(doc)
