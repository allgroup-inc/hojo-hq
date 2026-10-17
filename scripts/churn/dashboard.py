"""保全ダッシュボード＝「保全トリガーを常に見つける装置」を1画面に束ねる集約ビュー。

3%スコアボード（成熟コホートの早期解約率）／今日の要接触（triage）／解約の山（A2）／
未払消滅目前（A1）／再発監視（A3）の**見出し数字**を1枚に集める。分析は既存モジュールを呼ぶだけ
（新しい統計はしない）。**triageの決裁済み優先度は変えない**——ここは表示の集約層。

churn-model-quality-gate: 率は成熟分のみ・母数不足は参考・断定しない。
churn-pii-guard: 出力は private/ 限定。実処理は統制環境・審査後。
"""
from __future__ import annotations

from .cohort import cohort_rows, overall_rate, excluded_summary
from .triage import classify, triage
from .timing import churn_hazard_by_tenure, peak_windows
from .relapse import relapse_candidates
from .triggers import unpaid_trigger
from .config import MIN_RELIABLE_N, CAPACITY_PER_DAY


def retained_premium(records, as_of):
    """守れた累積保険料（決定3・LTV補助KPI）＝継続中契約の これまでの継続月数 × 月額保険料 の総和。

    「引き止めの口実にしない」ため、主KPIは継続率・これは従（決定ブリーフ 決定3）。観測値のみ・射影しない。
    対象は 母集団内かつ継続中（現ステータス＝継続 or is_scoreable）で、契約日・保険料があるもの。
    """
    total = 0
    for r in records:
        if r.get("in_scope", True) is False:
            continue
        if not (r.get("status_category") == "継続" or r.get("is_scoreable")):
            continue
        ad, amt = r.get("apply_date"), r.get("amount")
        if ad is None or not amt:
            continue
        months = max(0, (as_of - ad).days // 30)
        total += months * amt
    return int(total)


def dashboard_summary(records, as_of, model, capacity=CAPACITY_PER_DAY):
    """ダッシュボードの見出し数字をまとめて返す（既存の集計関数を呼ぶだけ）。"""
    rows = cohort_rows(records, as_of, model=model)
    _, _, stats = triage(classify(records, model, as_of), capacity)
    hazard = churn_hazard_by_tenure(records)
    peaks = peak_windows(hazard, min_count=max(1, MIN_RELIABLE_N // 4))
    return {
        "overall": overall_rate(rows),
        "excluded": excluded_summary(records),
        "cohort_rows": rows,
        "today_total": stats["total"],
        "today_capacity": capacity,
        "hazard": hazard,
        "peaks": peaks,
        "relapse_count": len(relapse_candidates(records, as_of)),
        "imminent_count": sum(1 for r in records
                              if unpaid_trigger(r, as_of) == "未払消滅目前"),
        "retained_premium": retained_premium(records, as_of),
    }


def _card(title, value, note, accent="#00335C"):
    import html
    return (
        f'<div style="border:1px solid #E4E4E4;border-top:4px solid {accent};border-radius:6px;'
        'padding:14px 16px;min-width:150px;flex:1">'
        f'<div style="font-size:12px;color:#6B6B6B">{html.escape(title)}</div>'
        f'<div style="font-size:26px;font-weight:700;color:{accent};margin:4px 0">{value}</div>'
        f'<div style="font-size:12px;color:#6B6B6B">{note}</div></div>')


def render_index(summary, links, path, target=0.03):
    """見出しカード＋各詳細ページへのリンクをindex.htmlに出力（private/ 限定）。"""
    import html
    ov = summary["overall"]
    if ov["rate"] is None:
        rate_txt, accent, note = "－", "#6B6B6B", "成熟データ待ち（0%と断定しない）"
    else:
        over = ov["rate"] > target
        rate_txt = f'{ov["rate"]*100:.1f}%'
        accent = "#C0392B" if over else "#1E8449"
        note = f'目標{target*100:.0f}%を{"上回る" if over else "下回る"}（成熟{ov["resolved"]}件）'
    peaks = summary["peaks"]
    peak_txt = "／".join(f'{p["lo"]}〜{p["hi"]}日' for p in peaks) or "実績待ち"
    exc = summary["excluded"]

    cards = "".join([
        _card("3%スコアボード（早期解約率）", rate_txt, note, accent),
        _card("今日の要接触", f'{summary["today_total"]}件',
              f'キャパ {summary["today_capacity"]}件/日', "#F88800"),
        _card("未払消滅目前（A1）", f'{summary["imminent_count"]}件',
              "3ヶ月連続未収＝消滅前に手続き支援", "#C0392B"),
        _card("再発監視（A3）", f'{summary["relapse_count"]}件',
              "一度解消→また未収", "#F88800"),
        _card("解約の山（A2）", f'{len(peaks)}つ',
              f'契約後 {peak_txt}', "#00335C"),
        _card("守れた累積保険料（LTV補助）", f'{summary["retained_premium"]:,}円',
              "継続月数×月額の総和・主KPIは継続率", "#1E8449"),
        _card("除外（母集団外/対象外）", f'{exc["total_excluded"]}件',
              "率の分母から除外・件数併記", "#6B6B6B"),
    ])
    link_items = "".join(
        f'<li><a href="{html.escape(href)}">{html.escape(label)}</a></li>'
        for label, href in links)
    doc = (
        '<!doctype html><meta charset="utf-8"><title>保全ダッシュボード</title>'
        '<style>body{font-family:Meiryo,"Noto Sans JP",sans-serif;padding:20px;max-width:1000px;'
        'margin:auto;color:#1a1a1a}a{color:#00335C}h1{font-size:22px}'
        '.cards{display:flex;flex-wrap:wrap;gap:12px;margin:16px 0}</style>'
        '<h1>保全ダッシュボード（早期解約を止める“当たり所”）</h1>'
        '<p style="font-size:13px;color:#6B6B6B">契約から6ヶ月以内の解約を3%未満に。'
        '検知→今日の要接触→各山の手前→再発、を1画面で。連絡は人が実行。合成データ。</p>'
        f'<div class="cards">{cards}</div>'
        '<h2 style="font-size:16px">詳細ページ</h2>'
        f'<ul style="font-size:14px;line-height:1.9">{link_items}</ul>'
        '<p style="font-size:12px;color:#6B6B6B">率は成熟分のみ・母数不足は参考・単純比較で断定しない'
        '（因果は段階導入で確認）。優先度順は小柳さん決裁。出力は private 限定。</p>')
    with open(path, "w", encoding="utf-8") as f:
        f.write(doc)
