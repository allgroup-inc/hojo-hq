"""有効な架電時期（強化6）。

「いつ解約が起きるか」をデータから出し、その手前を架電の勝負どきにする。
まずは**解約ハザード曲線**＝成熟した早期解約者の「契約→解約の日数」分布。
モデル不要の純・記述統計（断定しない・母数不足は参考）。

- 継続中・非早期解約は混ぜない（分布が歪むため）。成熟した早期解約者のみ。
- バケツ幅は `HAZARD_BUCKET_DAYS`（小柳さん決裁事項）。
- `peak_window` は最も解約が集中するバケツ（＝ヤマ）。この手前が架電適期の基準になる（強化6-2で使用）。
"""
from __future__ import annotations

from .config import (HAZARD_BUCKET_DAYS, HAZARD_CALL_LEAD_DAYS,
                     MIN_RELIABLE_N, EARLY_CHURN_MONTHS)
from .effect_learning import _contacts_index, _mature_resolved


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


# 状態の並び順（架電適期＝最優先）
_TIMING_ORDER = {"架電適期": 0, "適期前": 1, "適期後": 2}


def call_timing(record, as_of, hazard, lead_days=HAZARD_CALL_LEAD_DAYS):
    """継続顧客について「今が架電の効く時期か」を、解約のヤマ（ハザードピーク）から判定。

    架電窓 = [ヤマ開始 - lead_days, ヤマ終了]。窓内＝架電適期／窓前＝適期前／窓後＝適期後。
    継続中でない・ハザードにヤマが無いときは None。
    """
    if not record.get("is_scoreable"):
        return None
    ad = record.get("apply_date")
    lo, hi = peak_window(hazard)
    if ad is None or lo is None:
        return None
    tenure = (as_of - ad).days
    window_start = lo - lead_days
    if tenure < window_start:
        status, days_to_window = "適期前", window_start - tenure
    elif tenure <= hi:
        status, days_to_window = "架電適期", 0
    else:
        status, days_to_window = "適期後", 0
    return {"customer_id": record.get("customer_id"), "apply_id": record.get("apply_id"),
            "product": record.get("product"), "agent_id": record.get("agent_id"),
            "tenure": tenure, "peak": (lo, hi), "status": status,
            "days_to_window": days_to_window}


def call_timing_list(records, as_of, hazard, lead_days=HAZARD_CALL_LEAD_DAYS):
    """継続顧客の架電適期を、架電適期→適期前（近い順）→適期後 に並べて返す。"""
    out = [t for t in (call_timing(r, as_of, hazard, lead_days) for r in records) if t]
    out.sort(key=lambda t: (_TIMING_ORDER.get(t["status"], 9), t["days_to_window"]))
    return out


def _first_qualifying_tenure(record, idx):
    """解約前・対応内容ありの接触のうち、最も早い接触の経過日数。無ければ None。"""
    by_id, by_date = idx
    cs = by_id.get((record.get("customer_id"), record.get("apply_id")))
    if cs is None:
        cs = by_date.get((record.get("customer_id"), record.get("apply_date")), [])
    ad, cancel = record.get("apply_date"), record.get("cancel_date")
    tenures = []
    for c in cs:
        cd, action = c.get("contact_date"), (c.get("action") or "").strip()
        if cd is None or not action or ad is None:
            continue
        if cancel is None or cd < cancel:          # 解約後は数えない（免疫時間）
            tenures.append((cd - ad).days)
    return min(tenures) if tenures else None


def contact_timing_effect(records, contacts, mature_before, bucket_days=HAZARD_BUCKET_DAYS,
                          min_reliable=MIN_RELIABLE_N):
    """架電時期別の早期解約率＝「どの時期の架電が効いたか」。

    成熟実績のみ。各契約の“最初の効いた接触”の経過日数でバケツ分けし、早期解約率を出す。
    未接触は別枠（ベースライン）。**接触は無作為でないため生存者バイアスが残る＝参考**。
    因果は段階導入（experiment.py）で確認する。母数不足は reference。
    """
    idx = _contacts_index(contacts)
    buckets, none_b = {}, {"n": 0, "churn": 0}
    for r in _mature_resolved(records, mature_before):
        churn = r.get("is_early_churn") or 0
        t = _first_qualifying_tenure(r, idx)
        b = none_b if (t is None or t < 0) else buckets.setdefault(t // bucket_days,
                                                                   {"n": 0, "churn": 0})
        b["n"] += 1
        b["churn"] += churn
    rows = [{"lo": k * bucket_days, "hi": (k + 1) * bucket_days, "n": v["n"], "churn": v["churn"],
             "rate": v["churn"] / v["n"] if v["n"] else 0.0,
             "reference": v["n"] < min_reliable} for k, v in sorted(buckets.items())]
    none_row = {"label": "未接触", "n": none_b["n"], "churn": none_b["churn"],
                "rate": none_b["churn"] / none_b["n"] if none_b["n"] else 0.0,
                "reference": none_b["n"] < min_reliable}
    return {"rows": rows, "not_contacted": none_row}


def render_call_timing_html(rows, path, peak=(None, None)):
    """架電時期リスト（営業マン向け・架電適期が先頭）をHTML出力（private/ 限定）。"""
    import html
    color = {"架電適期": "#F88800", "適期前": "#FFD27F", "適期後": "#EAF2F8"}
    trs = []
    for r in rows:
        if r["status"] == "架電適期":
            msg = "今が架電適期"
        elif r["status"] == "適期前":
            msg = f"あと{r['days_to_window']}日で適期"
        else:
            msg = "適期を過ぎています"
        bg = color.get(r["status"], "#fff")
        trs.append(
            f'<tr style="background:{bg}"><td>{html.escape(str(r.get("customer_id") or "—"))}</td>'
            f'<td>{html.escape(str(r.get("product")))}</td>'
            f'<td>{html.escape(str(r.get("agent_id")))}</td>'
            f'<td>契約後{r["tenure"]}日</td><td>{html.escape(r["status"])}</td>'
            f'<td>{html.escape(msg)}</td></tr>')
    pk = (f'解約のヤマは契約後 {peak[0]}〜{peak[1]}日'
          if peak[0] is not None else 'ハザード未確定（解約実績待ち）')
    doc = (
        '<!doctype html><meta charset="utf-8"><title>架電時期リスト</title>'
        '<style>body{font-family:Meiryo,"Noto Sans JP",sans-serif;padding:16px}'
        'table{border-collapse:collapse;width:100%}th,td{border:1px solid #ccc;padding:6px;font-size:13px}'
        'th{background:#00335C;color:#fff}</style>'
        f'<h1>架電時期リスト（{len(rows)}件・架電適期が上）</h1>'
        f'<p>{pk} ＝ その手前が架電の勝負どき。顧客連絡は人が実行。合成データ。</p>'
        '<table><thead><tr><th>顧客ID</th><th>商品</th><th>営業</th>'
        '<th>経過</th><th>時期</th><th>ひとこと</th></tr></thead>'
        f'<tbody>{"".join(trs)}</tbody></table>')
    with open(path, "w", encoding="utf-8") as f:
        f.write(doc)


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
