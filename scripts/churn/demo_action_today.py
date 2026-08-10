"""「今日の要接触」統合トリアージ（合成データ・デモ）＝ ②予防トリガー＋③クローズドループ入口。

複数のきっかけ（②支払い挙動ウォッチ:不着/遅延・②初回引落"前"の口座確認・守れる金額の高リスク）を
1本に束ね、重複排除→優先度＋守れる金額で並べ→今日のN件(キャパ)に絞る。上限超過は繰り越し＋
落とした件数/最高"守れる金額"を明示（no silent cap）。各件に「最初の一手」を添える。

規律:
- 顧客連絡は人が実行（本画面は提示まで）。結果記録でループが閉じる（本デモは提示まで）。
- 数字は全て合成。断定しない。営業別は教育目的。実データは統制環境で審査後。

PII（churn-pii-guard）: 入出力は private/ 限定。実PIIは扱わない。

使い方: python -m scripts.churn.demo_action_today
"""
from __future__ import annotations
import html
import os
from datetime import date

from scripts.churn.intake import load_records, load_column_map
from scripts.churn.fit import load_model
from scripts.churn.score import score_record, display_pct
from scripts.churn.triggers import prevention_trigger
from scripts.churn.value import saveable
from scripts.churn.demo_dashboard import _first_move

D = "private/demo"
AS_OF = date(2026, 8, 1)
CAPACITY = 30  # 現場キャパ（件/日）。業務値=小柳さん決裁事項。

# きっかけ: (ラベル, 優先度, バッジ色クラス, その場の一手)
TRIGGERS = {
    "不着": (0, "nc", "初回の引落が不着です。すぐ一本、「口座やご残高、大丈夫ですか」と確認を"),
    "遅延": (1, "dl", "引落が遅れています。早めに一本、状況をやさしく確認"),
    "口座確認": (2, "ac", "引落の前に一本。「引落は普段お使いの口座ですか」を確認"),
    "高リスク": (3, "hi", None),  # 一手はヒット要因から
}


def build():
    cmap = load_column_map(f"{D}/column_map_real.json")
    records = load_records(f"{D}/apps.csv", cmap, AS_OF)
    model = load_model(f"{D}/risk_model.json")

    items = []
    for r in records:
        if not r.get("is_scoreable"):
            continue
        # きっかけ判定・守れる金額は本体モジュールに委譲（重複排除）
        trig = prevention_trigger(r, AS_OF)
        s = score_record(r, model)
        if trig is None:
            if s["band"] != "high":
                continue  # 候補でない
            trig = "高リスク"
        move = TRIGGERS[trig][2] or _first_move(s["hit_factors"])
        items.append({
            "trig": trig, "prio": TRIGGERS[trig][0],
            "cid": r.get("customer_id") or "—", "product": r.get("product"),
            "risk_pct": display_pct(s["risk"]), "band": s["band"],
            "saveable": saveable(s["risk"], r.get("amount")), "move": move,
            "detail": r.get("account_daily", "") if trig == "口座確認" else "",
        })
    items.sort(key=lambda x: (x["prio"], -x["saveable"]))
    today = items[:CAPACITY]
    carry = items[CAPACITY:]
    return today, carry, items


def render(today, carry, items):
    from collections import Counter
    by_trig = Counter(i["trig"] for i in items)
    carry_max = max((c["saveable"] for c in carry), default=0)

    def trbadge(t):
        cls = TRIGGERS[t][1]
        return f'<span class="tb {cls}">{html.escape(t)}</span>'

    rows = []
    for i, it in enumerate(today, 1):
        detail_html = f'<span class="dt">{html.escape(it["detail"])}</span>' if it["detail"] else ""
        rows.append(f"""
        <tr>
          <td class="rk">{i}</td>
          <td>{trbadge(it['trig'])}{detail_html}</td>
          <td class="cid">{html.escape(str(it['cid']))}</td>
          <td>{html.escape(str(it['product']))}</td>
          <td class="pct"><span class="riskpct band-{it['band']}">{it['risk_pct']}%</span></td>
          <td class="save">{it['saveable']:,.0f}<span class="u">円</span></td>
          <td class="mv">{html.escape(it['move'])}</td>
        </tr>""")

    seg = "".join(
        f'<span class="seg"><b>{by_trig.get(t,0)}</b> {t}</span>'
        for t in ("不着", "遅延", "口座確認", "高リスク"))
    carry_note = (
        f'<div class="carry">⚠️ キャパ({CAPACITY}件/日)超過ぶん <b>{len(carry)}件</b> は翌日へ繰り越し。'
        f'うち最高“守れる金額” <b>{carry_max:,.0f}円</b>。<b>黙って落とさず</b>、翌日の先頭で拾う。</div>'
        if carry else '<div class="carry ok">✅ 本日の要接触はキャパ内。取りこぼしなし。</div>')

    doc = f"""<title>今日の要接触（デモ）</title>
<style>
  :root{{--ground:#FBF8F3;--card:#FFF;--ink:#13222E;--soft:#4B5C6A;--line:#E4DBCB;--navy:#00335C;
    --accent:#F88800;--nc:#C4443A;--dl:#B5651D;--ac:#0A6E8C;--hi:#8A5A00;--hot:#C4443A;--hibg:#FEEFD8;
    --warn:#B5651D;--warnbg:#FBEEDD;--ok:#2E7D5B;--okbg:#E8F2EC;--sh:0 1px 2px rgba(19,34,46,.05),0 9px 24px rgba(19,34,46,.06)}}
  @media(prefers-color-scheme:dark){{:root{{--ground:#0E1922;--card:#152430;--ink:#EAF1F6;--soft:#A6B7C4;--line:#26394A;--navy:#7FB0D8;
    --accent:#FFA22E;--nc:#F0776D;--dl:#E8A84E;--ac:#5FB6D4;--hi:#E8A84E;--hot:#F0776D;--hibg:#2A2416;--warn:#E8A84E;--warnbg:#3A2A12;--ok:#6FCB9F;--okbg:#123024;--sh:0 1px 2px rgba(0,0,0,.3),0 12px 30px rgba(0,0,0,.4)}}}}
  :root[data-theme=light]{{--ground:#FBF8F3;--card:#FFF;--ink:#13222E;--soft:#4B5C6A;--line:#E4DBCB;--navy:#00335C;--accent:#F88800;--nc:#C4443A;--dl:#B5651D;--ac:#0A6E8C;--hi:#8A5A00;--hot:#C4443A;--hibg:#FEEFD8;--warn:#B5651D;--warnbg:#FBEEDD;--ok:#2E7D5B;--okbg:#E8F2EC}}
  :root[data-theme=dark]{{--ground:#0E1922;--card:#152430;--ink:#EAF1F6;--soft:#A6B7C4;--line:#26394A;--navy:#7FB0D8;--accent:#FFA22E;--nc:#F0776D;--dl:#E8A84E;--ac:#5FB6D4;--hi:#E8A84E;--hot:#F0776D;--hibg:#2A2416;--warn:#E8A84E;--warnbg:#3A2A12;--ok:#6FCB9F;--okbg:#123024}}
  *{{box-sizing:border-box}}
  body{{margin:0;background:var(--ground);color:var(--ink);line-height:1.7;font-feature-settings:"palt" 1;
    font-family:"Hiragino Kaku Gothic ProN","Yu Gothic",Meiryo,"Noto Sans JP",system-ui,sans-serif}}
  .wrap{{max-width:940px;margin:0 auto;padding:38px 20px 66px}}
  .eyebrow{{font-size:11.5px;letter-spacing:.16em;font-weight:700;color:var(--accent);text-transform:uppercase;margin:0 0 8px}}
  h1{{font-size:clamp(22px,4vw,29px);margin:0 0 6px;font-weight:800}}
  .sub{{color:var(--soft);font-size:14px;margin:0 0 16px}}
  .banner{{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:16px}}
  .pill{{font-size:12px;font-weight:700;padding:5px 11px;border-radius:999px;border:1px solid var(--line);background:var(--card);color:var(--navy)}}
  .pill.warn{{background:var(--warnbg);color:var(--warn);border-color:transparent}}
  .tiles{{display:flex;flex-wrap:wrap;gap:10px;margin-bottom:14px}}
  .tile{{flex:1 1 150px;background:var(--card);border:1px solid var(--line);border-radius:12px;padding:13px 15px;box-shadow:var(--sh)}}
  .tile .v{{font-size:26px;font-weight:800;font-variant-numeric:tabular-nums;line-height:1}}
  .tile .l{{font-size:12px;color:var(--soft);margin-top:4px}}
  .segs{{display:flex;flex-wrap:wrap;gap:8px;align-items:center}}
  .seg{{font-size:12.5px;color:var(--soft);background:var(--card);border:1px solid var(--line);border-radius:8px;padding:5px 10px}}
  .seg b{{color:var(--ink);font-variant-numeric:tabular-nums}}
  .carry{{margin:12px 0;padding:11px 15px;border-radius:11px;background:var(--warnbg);border:1px solid var(--warn);font-size:13px;line-height:1.6}}
  .carry.ok{{background:var(--okbg);border-color:var(--ok);color:var(--ink)}}
  .carry b{{color:var(--ink)}}
  .card{{background:var(--card);border:1px solid var(--line);border-radius:14px;box-shadow:var(--sh);overflow:hidden}}
  .scroll{{overflow-x:auto}}
  table{{border-collapse:collapse;width:100%;font-size:13.5px;min-width:680px}}
  thead th{{background:transparent;color:var(--soft);font-size:11.5px;font-weight:700;text-align:left;padding:10px 12px;border-bottom:1.5px solid var(--line)}}
  td{{padding:10px 12px;border-bottom:1px solid var(--line);vertical-align:middle}}
  tr:last-child td{{border-bottom:none}}
  td.rk{{color:var(--soft);font-weight:800;font-variant-numeric:tabular-nums;width:28px}}
  td.cid{{font-weight:800;color:var(--navy);white-space:nowrap}}
  td.save{{text-align:right;font-weight:800;color:var(--navy);font-variant-numeric:tabular-nums;white-space:nowrap}}
  td.save .u{{font-size:10px;color:var(--soft);font-weight:600;margin-left:2px}}
  td.pct{{white-space:nowrap}}
  .riskpct{{font-weight:800;font-variant-numeric:tabular-nums;padding:3px 8px;border-radius:7px;font-size:13px}}
  .band-high{{background:var(--hibg);color:var(--hot)}} .band-med{{color:var(--warn)}} .band-low{{color:var(--soft)}}
  .tb{{font-size:11px;font-weight:800;color:#fff;padding:3px 8px;border-radius:6px;white-space:nowrap}}
  .tb.nc{{background:var(--nc)}} .tb.dl{{background:var(--dl)}} .tb.ac{{background:var(--ac)}} .tb.hi{{background:var(--hi)}}
  .dt{{font-size:10px;color:var(--soft);margin-left:5px}}
  td.mv{{font-size:12.5px;color:var(--ink);line-height:1.5;min-width:230px}}
  .disc{{margin-top:22px;padding:13px 16px;border:1px solid var(--line);border-radius:11px;background:var(--card);font-size:12px;color:var(--soft);line-height:1.7}}
  .disc b{{color:var(--warn)}}
</style>
<div class="wrap">
  <p class="eyebrow">早期解約 &lt;3% ／ 現場の1画面</p>
  <h1>今日の要接触</h1>
  <p class="sub">複数の“きっかけ”を1本に束ね、守れる金額の大きい順に、キャパ内で。上から順に電話・保全を。</p>
  <div class="banner">
    <span class="pill warn">数字はすべて合成（偽データ）</span>
    <span class="pill">キャパ {CAPACITY}件/日</span>
    <span class="pill">顧客連絡は人が実行</span>
  </div>

  <div class="tiles">
    <div class="tile"><div class="v">{len(today)}<span style="font-size:14px">件</span></div><div class="l">今日やる（優先順）</div></div>
    <div class="tile"><div class="v">{len(carry)}<span style="font-size:14px">件</span></div><div class="l">翌日へ繰り越し</div></div>
    <div class="tile"><div class="v">{len(items)}<span style="font-size:14px">件</span></div><div class="l">要接触 合計</div></div>
  </div>
  <div class="segs">内訳：{seg}</div>
  {carry_note}

  <div class="card"><div class="scroll">
    <table>
      <thead><tr><th>#</th><th>きっかけ</th><th>顧客ID</th><th>商品</th><th>リスク</th><th>守れる金額<span style="font-weight:400;font-size:9px;display:block">目安/年</span></th><th>最初の一手</th></tr></thead>
      <tbody>{''.join(rows)}</tbody>
    </table>
  </div></div>

  <div class="disc">
    ※ きっかけの優先度: <b>不着 &gt; 遅延 &gt; 口座確認(引落前) &gt; 高リスク</b>、各内で守れる金額順。1契約が複数のきっかけで挙がっても1件に束ねる。
    キャパ超過は<b>翌日へ繰り越し</b>し落とした件数を明示（黙って消さない）。数字は全て<b>合成データ</b>で、断定に使わない。
    本画面は「提示」まで＝<b>顧客連絡は保全担当が判断して実行</b>し、結果を記録するとクローズドループ（測る・学ぶ）が閉じる。実データは統制環境で審査後。
  </div>
</div>"""
    out = os.path.join(D, "action_today.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(doc)
    print(f"[today] 要接触{len(items)}件 → 今日{len(today)} / 繰り越し{len(carry)} → {out}")
    return out


def main():
    today, carry, items = build()
    render(today, carry, items)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
