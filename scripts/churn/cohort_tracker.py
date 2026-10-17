"""早期解約率コホート・トラッカー（合成データ）。

契約月ごとに「6ヶ月以内の早期解約率」を出し、目標ライン(3%)との距離を可視化する。
＋ 漏れ分析（どの要因で解約が出ているか）。3%は運用の成果目標＝まず現在地を測る器。

品質規律（churn-model-quality-gate / churn-retention-ops）:
- 早期解約率は「確定分（is_resolved: 6ヶ月経過 or 6ヶ月内解約が確定）」のみで算出。
  観測中（まだ6ヶ月経っていない継続中を含むコホート）は「観測中(未確定)」と明示し断定しない。
- 母数不足（確定数 < MIN_RELIABLE_N）は「参考」。営業担当別は教育・型改善が目的で人事評価に使わない。

PII（churn-pii-guard）: 入出力は private/ 限定。実データは統制環境で・審査後。本スクリプトは合成データ専用。

使い方:
  python -m scripts.churn.cohort_tracker
"""
from __future__ import annotations
import html
import os
from datetime import date

from scripts.churn.intake import load_records, load_column_map
from scripts.churn.report_agg import aggregate_by
from scripts.churn.cohort import cohort_rows, overall_rate
from scripts.churn.config import MIN_RELIABLE_N

D = "private/demo"
AS_OF = date(2026, 8, 1)
TARGET = 0.03  # 早期解約率の目標ライン 3%
FIELD_JP = {"channel": "集客チャネル", "apply_form": "申込形態", "product": "商品",
            "age_band": "年代", "agent_id": "営業担当"}


def _ym(d):
    return f"{d.year}-{d.month:02d}"


def build():
    cmap = load_column_map(f"{D}/column_map_real.json")
    records = load_records(f"{D}/apps.csv", cmap, AS_OF)

    # 本体モジュールに委譲（観測中判定は暦ベース＝解約アウトカムと交絡させない）
    rows = cohort_rows(records, AS_OF)
    ov = overall_rate(rows)
    overall = ov["rate"] if ov["rate"] is not None else 0.0
    tot_res, tot_churn = ov["resolved"], ov["churn"]

    # 漏れ分析は成熟コホートのレコードのみ（同じバイアスを避ける）
    mature_yms = {r["ym"] for r in rows if not r["observing"]}
    mature_recs = [r for r in records if r.get("apply_date") and _ym(r["apply_date"]) in mature_yms]
    leak = {f: aggregate_by(mature_recs, f) for f in ("channel", "apply_form", "product", "age_band", "agent_id")}
    return rows, overall, tot_res, tot_churn, leak


def _bar_rows(rows, max_rate):
    out = []
    for r in rows:
        if r["observing"]:
            # 観測中は率が免疫時間バイアスで跳ねる → %を出さず「観測中」。解約数(生の件数)は列で見せる
            cell = '<span class="tag obs">観測中(未確定)</span>'
            barw = 0
            cls = "na"
        elif r["rate"] is None:
            cell = '<span class="na">確定なし</span>'
            barw = 0
            cls = "na"
        else:
            pct = r["rate"] * 100
            barw = min(r["rate"] / max_rate, 1.0) * 100 if max_rate else 0
            over = r["rate"] > TARGET
            cls = "over" if over else "under"
            tags = []
            if r["reference"]:
                tags.append('<span class="tag ref">参考</span>')
            cell = f'{pct:.1f}% {"".join(tags)}'
        out.append(f"""
        <tr>
          <td class="ym">{html.escape(r["ym"])}</td>
          <td class="num">{r["total"]}</td>
          <td class="num">{r["resolved"]}</td>
          <td class="num">{r["churn"]}</td>
          <td class="bar"><div class="track"><div class="fill {cls}" style="width:{barw:.1f}%"></div></div></td>
          <td class="rate">{cell}</td>
        </tr>""")
    return "".join(out)


def _leak_block(title, field, rows):
    trs = []
    for r in rows[:8]:
        ref = ' <span class="tag ref">参考</span>' if r["reference"] else ""
        trs.append(f'<tr><td>{html.escape(str(r["value"]))}{ref}</td>'
                   f'<td class="num">{r["n"]}</td><td class="num">{r["churn"]}</td>'
                   f'<td class="rate">{r["churn_rate"]*100:.1f}%</td></tr>')
    return f"""
      <div class="leak">
        <div class="lt">{html.escape(title)}</div>
        <table><thead><tr><th>{html.escape(FIELD_JP.get(field, field))}</th><th>確定</th><th>解約</th><th>解約率</th></tr></thead>
        <tbody>{"".join(trs)}</tbody></table>
      </div>"""


def render(rows, overall, tot_res, tot_churn, leak):
    max_rate = max((r["rate"] for r in rows if r["rate"] is not None and not r["observing"]),
                   default=TARGET)
    gap = overall - TARGET
    doc = f"""<title>早期解約率 コホート・トラッカー（デモ）</title>
<style>
  :root{{--ground:#FBF8F3;--card:#FFF;--ink:#13222E;--soft:#4B5C6A;--line:#E4DBCB;
    --navy:#00335C;--accent:#F88800;--over:#C4443A;--overbg:#FBEAE8;--under:#2E7D5B;--underbg:#E8F2EC;
    --warn:#B5651D;--warnbg:#FBEEDD;--sh:0 1px 2px rgba(19,34,46,.05),0 9px 24px rgba(19,34,46,.06)}}
  @media(prefers-color-scheme:dark){{:root{{--ground:#0E1922;--card:#152430;--ink:#EAF1F6;--soft:#A6B7C4;
    --line:#26394A;--navy:#7FB0D8;--accent:#FFA22E;--over:#F0776D;--overbg:#3A1E1B;--under:#6FCB9F;--underbg:#123024;
    --warn:#E8A84E;--warnbg:#3A2A12;--sh:0 1px 2px rgba(0,0,0,.3),0 12px 30px rgba(0,0,0,.4)}}}}
  :root[data-theme=light]{{--ground:#FBF8F3;--card:#FFF;--ink:#13222E;--soft:#4B5C6A;--line:#E4DBCB;--navy:#00335C;--accent:#F88800;--over:#C4443A;--overbg:#FBEAE8;--under:#2E7D5B;--underbg:#E8F2EC;--warn:#B5651D;--warnbg:#FBEEDD}}
  :root[data-theme=dark]{{--ground:#0E1922;--card:#152430;--ink:#EAF1F6;--soft:#A6B7C4;--line:#26394A;--navy:#7FB0D8;--accent:#FFA22E;--over:#F0776D;--overbg:#3A1E1B;--under:#6FCB9F;--underbg:#123024;--warn:#E8A84E;--warnbg:#3A2A12}}
  *{{box-sizing:border-box}}
  body{{margin:0;background:var(--ground);color:var(--ink);line-height:1.7;font-feature-settings:"palt" 1;
    font-family:"Hiragino Kaku Gothic ProN","Yu Gothic",Meiryo,"Noto Sans JP",system-ui,sans-serif}}
  .wrap{{max-width:900px;margin:0 auto;padding:40px 20px 70px}}
  .eyebrow{{font-size:11.5px;letter-spacing:.16em;font-weight:700;color:var(--accent);text-transform:uppercase;margin:0 0 8px}}
  h1{{font-size:clamp(22px,4vw,29px);margin:0 0 6px;font-weight:800;text-wrap:balance}}
  .sub{{color:var(--soft);font-size:14.5px;margin:0 0 18px}}
  .banner{{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:22px}}
  .pill{{font-size:12.5px;font-weight:700;padding:5px 12px;border-radius:999px;border:1px solid var(--line);background:var(--card);color:var(--navy)}}
  .pill.warn{{background:var(--warnbg);color:var(--warn);border-color:transparent}}
  .score{{display:flex;flex-wrap:wrap;gap:16px;align-items:center;background:var(--card);border:1px solid var(--line);
    border-radius:14px;padding:20px 22px;box-shadow:var(--sh);margin-bottom:10px}}
  .score .big{{font-size:44px;font-weight:800;font-variant-numeric:tabular-nums;line-height:1;color:var(--over)}}
  .score .big.ok{{color:var(--under)}}
  .score .meta{{font-size:13px;color:var(--soft);line-height:1.6}}
  .score .meta b{{color:var(--ink)}}
  .target{{margin-left:auto;text-align:right;font-size:13px;color:var(--soft)}}
  .target .t{{font-size:22px;font-weight:800;color:var(--navy)}}
  h2{{font-size:17px;font-weight:800;margin:26px 0 6px;display:flex;align-items:center;gap:9px}}
  h2::before{{content:"";width:9px;height:9px;border-radius:2px;background:var(--accent)}}
  .cap{{font-size:12.5px;color:var(--soft);margin:0 0 12px}}
  .card{{background:var(--card);border:1px solid var(--line);border-radius:14px;box-shadow:var(--sh);overflow:hidden}}
  table{{border-collapse:collapse;width:100%;font-size:13.5px}}
  thead th{{background:transparent;color:var(--soft);font-size:11.5px;font-weight:700;text-align:left;
    padding:10px 12px;border-bottom:1.5px solid var(--line)}}
  td{{padding:9px 12px;border-bottom:1px solid var(--line);vertical-align:middle}}
  tr:last-child td{{border-bottom:none}}
  td.num,td.rate{{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}}
  td.ym{{font-weight:700;white-space:nowrap}}
  td.rate{{font-weight:800}}
  .bar{{width:34%}}
  .track{{background:color-mix(in srgb,var(--soft) 18%,transparent);border-radius:5px;height:14px;position:relative}}
  .fill{{height:100%;border-radius:5px}}
  .fill.over{{background:var(--over)}}
  .fill.under{{background:var(--under)}}
  .fill.na{{background:transparent}}
  .tag{{font-size:10px;font-weight:700;padding:1px 6px;border-radius:5px;margin-left:4px;white-space:nowrap}}
  .tag.obs{{background:var(--warnbg);color:var(--warn)}}
  .tag.ref{{background:color-mix(in srgb,var(--soft) 18%,transparent);color:var(--soft)}}
  .na{{color:var(--soft)}}
  .leaks{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}
  @media(max-width:620px){{.leaks{{grid-template-columns:1fr}}.bar{{width:22%}}}}
  .leak{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:6px 12px 10px;box-shadow:var(--sh)}}
  .leak .lt{{font-size:13px;font-weight:800;margin:8px 2px 4px}}
  .leak td,.leak th{{padding:6px 8px;font-size:12.5px}}
  .disc{{margin-top:24px;padding:13px 16px;border:1px solid var(--line);border-radius:11px;background:var(--card);font-size:12px;color:var(--soft);line-height:1.7}}
  .disc b{{color:var(--warn)}}
</style>
<div class="wrap">
  <p class="eyebrow">早期解約 &lt;3% ／ スコアボード</p>
  <h1>早期解約率 コホート・トラッカー</h1>
  <p class="sub">契約した月ごとに「6ヶ月以内にやめた割合」を追い、目標<b>3%</b>までの距離と“どこで漏れているか”を見る画面です。</p>
  <div class="banner">
    <span class="pill warn">数字はすべて合成（偽データ・解約率は現実より高く設定）</span>
    <span class="pill">確定分のみで算出</span>
  </div>

  <div class="score">
    <div>
      <div class="big {'ok' if overall<=TARGET else ''}">{overall*100:.1f}%</div>
      <div class="meta">全体の早期解約率（成熟コホートのみ）<br><b>{tot_churn}</b> / {tot_res} 件が6ヶ月以内に解約<br><span style="font-size:11.5px">観測中コホートは免疫時間バイアスのため全体から除外</span></div>
    </div>
    <div class="target">
      目標ライン<div class="t">3.0%</div>
      <div>目標まで <b>{'到達' if gap<=0 else f'▲{gap*100:.1f}pt'}</b></div>
    </div>
  </div>

  <h2>契約月コホート別</h2>
  <p class="cap">棒は解約率（<span style="color:var(--over)">赤=3%超</span> / <span style="color:var(--under)">緑=3%以下</span>）。<b>観測中</b>＝まだ6ヶ月経っていない契約が多く未確定。<b>参考</b>＝確定数が少ない（n&lt;{MIN_RELIABLE_N}）。</p>
  <div class="card">
    <table>
      <thead><tr><th>契約月</th><th>契約数</th><th>確定</th><th>解約</th><th>解約率</th><th></th></tr></thead>
      <tbody>{_bar_rows(rows, max_rate)}</tbody>
    </table>
  </div>

  <h2>漏れ分析（どこで解約が出ているか・確定分）</h2>
  <p class="cap">解約率の高い要因＝初期フォローの型を見直したい所。<b>教育・型改善が目的</b>で、営業担当別は人事評価に使いません。少件数は「参考」。</p>
  <div class="leaks">
    {_leak_block("集客チャネル別", "channel", leak["channel"])}
    {_leak_block("申込形態別", "apply_form", leak["apply_form"])}
    {_leak_block("商品別", "product", leak["product"])}
    {_leak_block("年代別", "age_band", leak["age_band"])}
    {_leak_block("営業担当別（教育目的）", "agent_id", leak["agent_id"])}
  </div>

  <div class="disc">
    ※ 数字はすべて<b>合成データ</b>（解約率はシグナル検証のため現実より高く設定）。早期解約率は<b>確定分のみ</b>で算出し、6ヶ月未満の継続中は含めない（免疫時間バイアス回避）。<b>3%はモデル精度でなく運用の成果目標</b>で、本トラッカーはその現在地を測る器。実データでの計測は統制環境で・守り部審査後に。
  </div>
</div>"""
    out = os.path.join(D, "cohort_tracker.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(doc)
    print(f"[cohort] 全体早期解約率(確定分)={overall*100:.1f}% "
          f"({tot_churn}/{tot_res}) 目標3% → {out}")
    return out


def main():
    rows, overall, tot_res, tot_churn, leak = build()
    render(rows, overall, tot_res, tot_churn, leak)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
