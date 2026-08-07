"""保全アクション・ダッシュボードを合成データから生成する（デモ）。

① 守れる金額順ランキング（リスク% × 年間保険料）＋「最初の一手」
② 掛け合わせ別の解約傾向（商品×年代・地域×チャネル、参考マスは非表示）
③ だからどこから手を打つか（①と②の橋渡し）
＋ 初回引落アラート（不着/遅延の継続中契約を最優先。モデルと別のルール旗）

規律:
- 営業担当別・掛け合わせは教育・型改善の目的。母数不足(n<MIN_RELIABLE_N)は「参考」明示・断定しない。
- 予測はモデル（合成AUCは弱い）→本番はAUC確認後、と明記。数字は全て合成。
- 「最初の一手」は保全責任者の実践に沿ったたたき台（humanizerで自然な口調に）。現場が確定する。

PII（churn-pii-guard）:
- 入出力は private/ 配下（gitignore）限定。生成HTMLは顧客個人情報を含みうるため絶対にコミットしない。
- 本スクリプトは合成データ（private/demo）専用のデモ。実データに流用する場合は統制環境で・審査後に。
"""
from __future__ import annotations
import csv
import html
import os

from scripts.churn.intake import load_records, load_column_map
from scripts.churn.fit import load_model
from scripts.churn.score import score_record, display_pct
from scripts.churn.config import MIN_RELIABLE_N
from datetime import date

D = "private/demo"
AS_OF = date(2026, 8, 1)
FIELD_JP = {"agent_id": "営業担当", "apply_form": "申込形態", "channel": "チャネル",
            "product": "商品", "amount_band": "保険料帯", "age_band": "年代",
            "gender": "性別", "area": "地域"}


def crosstab(resolved, row_f, col_f):
    cells, rows, cols = {}, {}, {}
    for r in resolved:
        rk, ck = r.get(row_f, "不明"), r.get(col_f, "不明")
        c = cells.setdefault((rk, ck), {"n": 0, "churn": 0})
        c["n"] += 1
        c["churn"] += r["is_early_churn"]
        rows[rk] = rows.get(rk, 0) + 1
        cols[ck] = cols.get(ck, 0) + 1
    return cells, rows, cols


def main():
    cmap = load_column_map(f"{D}/column_map_real.json")
    records = load_records(f"{D}/apps.csv", cmap, AS_OF)
    model = load_model(f"{D}/risk_model.json")
    base = model["base_rate"]
    resolved = [r for r in records if r.get("is_resolved")]

    # 初回引落結果を生CSVから読む（モデルは使わない列。ルール旗として別扱い）。
    # キー=(顧客ID, 契約日)。直近半年の継続中だけ値が入る（古い契約は上書きで消える想定）。
    debit_by_key = {}
    with open(f"{D}/apps.csv", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            debit_by_key[(row.get("顧客ID"), row.get("契約日"))] = row.get("初回引落結果", "")

    # ① 予測ランキング（継続中）＝「守れる金額」順（リスク% × 年間保険料の目安）
    scoreable = [r for r in records if r.get("is_scoreable")]
    scored, urgent = [], []
    for r in scoreable:
        s = score_record(r, model)
        annual = (r.get("amount") or 0) * 12  # 月額 × 12 の目安
        saveable = s["risk"] * annual         # 期待“守れる”保険料
        ad = r.get("apply_date")
        debit = debit_by_key.get((r.get("customer_id"), ad.isoformat() if ad else ""), "")
        row = (r, s, annual, saveable, debit)
        if debit in ("不着", "遅延"):
            urgent.append(row)          # ルールで最優先（モデルと別系統）
        else:
            scored.append(row)
    # 不着→遅延→守れる金額の順
    urgent.sort(key=lambda x: (0 if x[4] == "不着" else 1, -x[3]))
    scored.sort(key=lambda x: x[3], reverse=True)
    top = scored[:12]

    # ② クロス集計（複数の掛け合わせ）
    PAIRS = [("product", "age_band", "商品 × 年代"),
             ("area", "channel", "地域 × チャネル")]
    tabs = []
    worst = None  # 全掛け合わせを通して最も解約率が高い“信頼できる”セル
    for row_f, col_f, title in PAIRS:
        cells, rowtot, coltot = crosstab(resolved, row_f, col_f)
        # 行＝解約率の高い順（その行全体の早期解約率）
        rowchurn = {}
        for (rk, ck), c in cells.items():
            b = rowchurn.setdefault(rk, {"n": 0, "churn": 0})
            b["n"] += c["n"]; b["churn"] += c["churn"]
        rows_o = sorted(rowtot, key=lambda k: -(rowchurn[k]["churn"] / rowchurn[k]["n"]))
        cols_o = sorted(coltot, key=lambda k: -coltot[k])
        reliable = [c["churn"] / c["n"] for c in cells.values()
                    if c["n"] >= MIN_RELIABLE_N]
        max_rate = max(reliable) if reliable else base
        tabs.append({"row_f": row_f, "col_f": col_f, "title": title,
                     "cells": cells, "rows": rows_o, "rowtot": rowtot,
                     "rowchurn": rowchurn, "cols": cols_o, "max_rate": max_rate})
        for (rk, ck), c in cells.items():
            if c["n"] >= MIN_RELIABLE_N:
                rate = c["churn"] / c["n"]
                if worst is None or rate > worst["rate"]:
                    worst = {"row_f": row_f, "col_f": col_f, "rk": rk, "ck": ck,
                             "rate": rate, "n": c["n"]}

    render(top, urgent, base, tabs, worst, len(scoreable))


# 効いている要因 → 「最初の一手」のたたき台。徳元さん(保全責任者)の実践に沿って更新。
# 実際に効いた対応：保険料負担→減額提案／通販乗換懸念→対面サポート価値／初回引落は口座確認。
ACTION_MAP = {
    ("amount_band", "〜3千"): "「保険料、負担になっていませんか」から。厳しければ減額でも続けられます（減額で継続の方も）",
    ("channel", "名簿"): "初回の引落が始まる前に一本。「引落は普段お使いの口座ですか」を確認",
    ("channel", "WEB"): "初回の引落が始まる前に一本。「引落は普段お使いの口座ですか」を確認",
    ("apply_form", "電話"): "「請求のときもそばでお手伝いします」と、対面で支える安心をひとこと",
    ("apply_form", "WEB"): "「請求のときもそばでお手伝いします」と、対面で支える安心をひとこと",
    ("age_band", "20代"): "いま必要な理由を、その方の年齢に合わせて自分ごとになるように",
    ("product", "医療女性"): "「こんな時に使えます」と、給付の場面を具体的に",
    ("product", "がん"): "「こんな時に使えます」と、給付の場面を具体的に",
    ("product", "医療"): "「こんな時に使えます」と、給付の場面を具体的に",
}


def _first_move(hit_factors):
    for f in hit_factors:
        if f.get("direction") != "up":
            continue
        act = ACTION_MAP.get((f["field"], f["value"]))
        if act:
            return act
    return "まずは一本、安心の声かけを。引落の口座もあわせて確認"


def _hit_friendly(hit_factors):
    parts = []
    for f in hit_factors:
        arrow = "▲" if f["direction"] == "up" else "▽"
        jp = FIELD_JP.get(f["field"], f["field"])
        ref = "※参考" if f["reference"] else ""
        parts.append(f'<span class="hf {"up" if f["direction"]=="up" else "dn"}">'
                     f'{arrow} {html.escape(jp)}：{html.escape(str(f["value"]))}{ref}</span>')
    return "".join(parts)


def _heatmap(tab):
    """1つの掛け合わせのヒートマップHTMLを返す。参考(n<20)マスは非表示。"""
    cells, rows, cols, rowtot, rowchurn, max_rate = (
        tab["cells"], tab["rows"], tab["cols"], tab["rowtot"],
        tab["rowchurn"], tab["max_rate"])
    row_jp = FIELD_JP.get(tab["row_f"], tab["row_f"])
    head = "".join(f"<th>{html.escape(str(c))}</th>" for c in cols)
    head += '<th class="rowrate-h">行の解約率</th>'
    body = []
    hidden = 0
    visible = 0
    for rk in rows:
        rn = rowchurn[rk]["n"]
        rr = rowchurn[rk]["churn"] / rn
        row_ref = rn < MIN_RELIABLE_N
        tds = [f'<th class="rowh">{html.escape(str(rk))}'
               f'<span class="rn">n={rowtot[rk]}</span></th>']
        for ck in cols:
            c = cells.get((rk, ck))
            if not c or c["n"] == 0:
                tds.append('<td class="empty">–</td>')
                continue
            if c["n"] < MIN_RELIABLE_N:  # 参考は非表示
                hidden += 1
                tds.append('<td class="hide" title="参考(母数不足)のため非表示"></td>')
                continue
            visible += 1
            rate = c["churn"] / c["n"]
            inten = min(rate / max_rate, 1.0) if max_rate else 0
            tds.append(f'<td class="cell" style="--i:{inten:.3f}">'
                       f'<span class="r">{rate*100:.0f}%</span>'
                       f'<span class="n">n={c["n"]}</span></td>')
        rr_cls = "rowrate ref" if row_ref else "rowrate"
        rr_note = '<span class="rref">参考</span>' if row_ref else ''
        tds.append(f'<td class="{rr_cls}">{rr*100:.0f}%{rr_note}</td>')
        body.append(f"<tr>{''.join(tds)}</tr>")
    hidenote = (f'　｜　非表示 {hidden} マス（参考・母数不足）' if hidden else '')
    empty_warn = ''
    if visible == 0:
        empty_warn = ('<div class="emptywarn">⚠️ この掛け合わせは<b>全マスが母数不足（n&lt;'
                      f'{MIN_RELIABLE_N}）</b>でした。{html.escape(row_jp)}で細かく割ると'
                      '1マスの件数が減りすぎ、信頼できる傾向が出ません。'
                      'より粗い軸（例：地域をまとめる／チャネル単独）での確認を推奨します。</div>')
    return f"""
      <div class="tabtitle">{html.escape(tab["title"])}
        <span class="axis">縦：{html.escape(row_jp)}（解約率の高い順）</span></div>
      <div class="card">
        {empty_warn}
        <div class="heat-scroll">
        <table class="heat"><thead><tr><th></th>{head}</tr></thead>
          <tbody>{''.join(body)}</tbody></table>
        </div>
        <div class="legend"><span>低</span><span class="grad"></span><span>高（解約率）</span>
          <span style="margin-left:10px">□ 空白＝参考（n&lt;{MIN_RELIABLE_N}）で非表示{hidenote}</span></div>
      </div>"""


def render(top, urgent, base, tabs, worst, n_score):
    # ⓪ 最優先アラート（初回引落が不着/遅延）＝モデルと別のルール
    alert_rows = []
    for r, s, annual, saveable, debit in urgent:
        tag = "不着" if debit == "不着" else "遅延"
        alert_rows.append(f"""
        <tr>
          <td><span class="dbadge {'nc' if debit=='不着' else 'dl'}">{tag}</span></td>
          <td class="cid">{html.escape(str(r.get("customer_id") or "—"))}</td>
          <td>{html.escape(str(r.get("product")))}</td>
          <td>{html.escape(str(r.get("agent_id")))}</td>
          <td class="save">{saveable:,.0f}<span class="u">円</span></td>
          <td class="hits">初回の引落が{tag}です。<b>すぐ一本</b>、「口座やご残高、大丈夫ですか」と確認を</td>
        </tr>""")
    alert_html = ""
    if alert_rows:
        alert_html = f"""
  <section>
    <div class="h"><span class="n alert">!</span><h2>今すぐ：初回引落アラート</h2></div>
    <p class="cap"><b>モデルの点数とは別のルール</b>です。初回引落が<b>不着・遅延</b>の継続中契約は、失効に直結するので<b>最優先</b>。（直近半年の契約で出るデータ。徳元さんが記録している情報を活用）</p>
    <div class="card alertcard">
      <div class="heat-scroll">
      <table class="rank-tbl">
        <thead><tr><th>状態</th><th>顧客ID</th><th>商品</th><th>営業担当</th><th>守れる金額<span class="th-note">目安</span></th><th>最初の一手</th></tr></thead>
        <tbody>{''.join(alert_rows)}</tbody>
      </table>
      </div>
    </div>
  </section>"""

    # ① ランキング行（守れる金額順）
    rank_rows = []
    for i, (r, s, annual, saveable, debit) in enumerate(top, 1):
        pct = display_pct(s["risk"])
        band = s["band"]
        rank_rows.append(f"""
        <tr>
          <td class="rank">{i}</td>
          <td class="cid">{html.escape(str(r.get("customer_id") or "—"))}</td>
          <td>{html.escape(str(r.get("product")))}</td>
          <td class="pct"><span class="riskpct band-{band}">{pct}%</span></td>
          <td class="yen">{annual:,.0f}<span class="u">円/年</span></td>
          <td class="save">{saveable:,.0f}<span class="u">円</span></td>
          <td class="hits">{_hit_friendly(s["hit_factors"])}
            <div class="move">→ 最初の一手（たたき台）：{html.escape(_first_move(s["hit_factors"]))}</div>
          </td>
        </tr>""")

    # ② 複数ヒートマップ
    heatmaps = "".join(_heatmap(t) for t in tabs)

    # ③ 橋渡し文（全掛け合わせで最も高い“信頼できる”セル）
    if worst:
        r_jp = FIELD_JP.get(worst["row_f"], worst["row_f"])
        c_jp = FIELD_JP.get(worst["col_f"], worst["col_f"])
        bridge = (f'過去の実績では、<b>{html.escape(r_jp)}「{html.escape(str(worst["rk"]))}」'
                  f'× {html.escape(c_jp)}「{html.escape(str(worst["ck"]))}」</b>の'
                  f'早期解約率が <b>{worst["rate"]*100:.0f}%</b>（n={worst["n"]}・'
                  f'ベース{base*100:.0f}%の約{worst["rate"]/base:.1f}倍）と、'
                  f'信頼できる母数の中で最も高い組み合わせです。'
                  f'まずこの組み合わせに当てはまる継続中の案件から保全に入るのが効率的です。')
        matches = [str(r.get("customer_id")) for r, s, _a, _sv, _d in top
                   if r.get(worst["row_f"]) == worst["rk"]
                   and r.get(worst["col_f"]) == worst["ck"]]
        if matches:
            bridge += f'<br>上のランキングでは <b>{("・".join(matches))}</b> が該当します。'
    else:
        bridge = "信頼できる母数（n≥20）の組み合わせがまだ十分にありません（母数不足）。実データで再評価します。"

    doc = f"""<title>保全アクション・ダッシュボード（デモ）</title>
<style>
  :root{{--ground:#FBF8F3;--card:#FFF;--ink:#12212E;--soft:#4A5B69;--line:#E6DECF;
    --navy:#00335C;--accent:#F88800;--hot:#D6453B;--warn:#B5651D;--warnbg:#FBEEDD;
    --hi:#F88800;--hibg:#FEEFD8;--sh:0 1px 2px rgba(18,33,46,.05),0 8px 22px rgba(18,33,46,.06)}}
  @media(prefers-color-scheme:dark){{:root{{--ground:#0E1922;--card:#152430;--ink:#EAF1F6;
    --soft:#A6B7C4;--line:#263945;--navy:#7FB0D8;--accent:#FFA22E;--hot:#F0776D;
    --warn:#E8A84E;--warnbg:#3A2A12;--hibg:#2A2416;--sh:0 1px 2px rgba(0,0,0,.3),0 10px 26px rgba(0,0,0,.35)}}}}
  :root[data-theme=light]{{--ground:#FBF8F3;--card:#FFF;--ink:#12212E;--soft:#4A5B69;--line:#E6DECF;--navy:#00335C;--accent:#F88800;--hot:#D6453B;--warn:#B5651D;--warnbg:#FBEEDD;--hibg:#FEEFD8}}
  :root[data-theme=dark]{{--ground:#0E1922;--card:#152430;--ink:#EAF1F6;--soft:#A6B7C4;--line:#263945;--navy:#7FB0D8;--accent:#FFA22E;--hot:#F0776D;--warn:#E8A84E;--warnbg:#3A2A12;--hibg:#2A2416}}
  *{{box-sizing:border-box}}
  body{{margin:0;background:var(--ground);color:var(--ink);font-feature-settings:"palt" 1;
    font-family:"Hiragino Kaku Gothic ProN","Yu Gothic",Meiryo,"Noto Sans JP",system-ui,sans-serif;line-height:1.7}}
  .wrap{{max-width:960px;margin:0 auto;padding:40px 20px 72px}}
  .eyebrow{{font-size:12px;letter-spacing:.16em;font-weight:700;color:var(--accent);text-transform:uppercase;margin:0 0 8px}}
  h1{{font-size:clamp(23px,4.5vw,30px);margin:0 0 8px;font-weight:800;text-wrap:balance}}
  .sub{{color:var(--soft);margin:0 0 18px;font-size:15px}}
  .banner{{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:26px}}
  .pill{{font-size:12.5px;font-weight:700;padding:5px 12px;border-radius:999px;border:1px solid var(--line);background:var(--card);color:var(--navy)}}
  .pill.warn{{background:var(--warnbg);color:var(--warn);border-color:transparent}}
  section{{margin-top:30px}}
  .h{{display:flex;align-items:baseline;gap:10px;margin:0 0 6px}}
  .h .n{{font-size:12px;font-weight:800;color:var(--accent);padding-top:2px}}
  .h .n.alert{{background:var(--hot);color:#fff;width:20px;height:20px;border-radius:50%;
    display:inline-grid;place-items:center;font-size:13px}}
  .alertcard{{border-color:var(--hot);box-shadow:0 0 0 1px var(--hot) inset,var(--sh)}}
  .dbadge{{font-weight:800;font-size:11.5px;padding:3px 9px;border-radius:7px;white-space:nowrap;color:#fff}}
  .dbadge.nc{{background:var(--hot)}}
  .dbadge.dl{{background:var(--warn)}}
  .h h2{{font-size:19px;margin:0;font-weight:800}}
  .cap{{font-size:13px;color:var(--soft);margin:0 0 14px}}
  .fieldmemo{{background:color-mix(in srgb,var(--navy) 7%,var(--card));
    border:1px solid var(--line);border-left:4px solid var(--navy);border-radius:11px;
    padding:12px 15px;font-size:13px;line-height:1.7;margin:0 0 14px}}
  .fieldmemo b{{color:var(--ink)}}
  .card{{background:var(--card);border:1px solid var(--line);border-radius:14px;box-shadow:var(--sh);overflow:hidden}}
  table{{border-collapse:collapse;width:100%;font-size:13.5px}}
  .rank-tbl thead th{{background:transparent;color:var(--soft);font-size:11.5px;font-weight:700;
    text-align:left;padding:10px 12px;border-bottom:1.5px solid var(--line);letter-spacing:.03em}}
  .rank-tbl td{{padding:11px 12px;border-bottom:1px solid var(--line);vertical-align:middle}}
  .rank-tbl tr:last-child td{{border-bottom:none}}
  td.rank{{font-weight:800;color:var(--soft);font-variant-numeric:tabular-nums;width:30px}}
  td.cid{{font-weight:800;color:var(--navy);white-space:nowrap}}
  td.pct{{white-space:nowrap}}
  .riskpct{{font-weight:800;font-variant-numeric:tabular-nums;padding:3px 9px;border-radius:7px;font-size:13.5px}}
  .band-high{{background:var(--hibg);color:var(--hot)}}
  .band-med{{background:transparent;color:var(--warn)}}
  .band-low{{color:var(--soft)}}
  td.yen,td.save{{font-variant-numeric:tabular-nums;white-space:nowrap;font-weight:700;text-align:right}}
  td.yen{{color:var(--soft)}}
  td.save{{color:var(--navy);font-weight:800}}
  td.yen .u,td.save .u{{font-size:10px;font-weight:600;color:var(--soft);margin-left:2px}}
  .th-note{{display:block;font-size:9px;font-weight:600;color:var(--soft)}}
  td.hits{{line-height:1.5;min-width:260px}}
  .move{{margin-top:6px;font-size:12px;font-weight:700;color:var(--navy);
    background:color-mix(in srgb,var(--navy) 8%,var(--card));border-radius:7px;
    padding:4px 9px;display:inline-block;line-height:1.4}}
  .hf{{display:inline-block;font-size:11.5px;font-weight:700;padding:2px 7px;border-radius:6px;margin:1px 3px 1px 0;white-space:nowrap}}
  .hf.up{{background:rgba(214,69,59,.10);color:var(--hot)}}
  .hf.dn{{background:rgba(46,125,91,.12);color:#2E7D5B}}
  @media(prefers-color-scheme:dark){{.hf.dn{{color:#6FCB9F}}}}
  /* heatmap */
  .tabtitle{{display:flex;align-items:baseline;gap:10px;font-weight:800;font-size:15px;
    margin:20px 0 9px}}
  .tabtitle:first-of-type{{margin-top:0}}
  .tabtitle .axis{{font-size:11.5px;font-weight:600;color:var(--soft)}}
  .card + .tabtitle{{margin-top:22px}}
  .heat-scroll{{overflow-x:auto}}
  .heat{{border-collapse:separate;border-spacing:4px;padding:12px}}
  .heat th{{font-size:12px;font-weight:700;color:var(--soft);padding:4px 8px;text-align:center}}
  .heat th.rowh{{text-align:right;color:var(--ink);font-weight:800;white-space:nowrap}}
  .heat th.rowh .rn{{display:block;font-size:10.5px;color:var(--soft);font-weight:600}}
  .heat td{{width:78px;height:52px;text-align:center;border-radius:9px;vertical-align:middle}}
  .heat td.cell{{background:color-mix(in srgb, var(--accent) calc(var(--i)*82% + 8%), var(--card))}}
  .heat td.cell .r{{font-weight:800;font-size:15px;display:block;color:#3a2600}}
  .heat td.cell .n{{font-size:10px;color:#5a4a2a}}
  .heat td.hide{{background:transparent;border:1px dashed var(--line);opacity:.5}}
  .heat td.empty{{color:var(--line)}}
  .heat th.rowrate-h{{color:var(--navy);font-weight:800;padding-left:10px}}
  .heat td.rowrate{{font-weight:800;font-size:14px;color:var(--navy);
    font-variant-numeric:tabular-nums;background:transparent;width:64px;
    border-left:2px solid var(--line)}}
  .heat td.rowrate.ref{{color:var(--soft);font-weight:700}}
  .heat td.rowrate .rref{{display:block;font-size:9px;font-weight:700;color:var(--warn)}}
  .emptywarn{{margin:12px 12px 0;padding:11px 14px;border-radius:10px;
    background:var(--warnbg);color:var(--ink);font-size:13px;line-height:1.65}}
  .emptywarn b{{color:var(--warn)}}
  .legend{{display:flex;align-items:center;gap:10px;padding:0 12px 12px;font-size:11.5px;color:var(--soft);flex-wrap:wrap}}
  .grad{{width:120px;height:10px;border-radius:5px;background:linear-gradient(90deg,color-mix(in srgb,var(--accent) 8%,var(--card)),var(--accent))}}
  .bridge{{background:var(--hibg);border:1px solid var(--accent);border-left-width:4px;border-radius:12px;padding:16px 18px;font-size:14.5px;line-height:1.75}}
  .bridge b{{color:var(--ink)}}
  .disclaimer{{margin-top:28px;padding:14px 16px;border:1px solid var(--line);border-radius:11px;background:var(--card);font-size:12.5px;color:var(--soft);line-height:1.7}}
  .disclaimer b{{color:var(--warn)}}
</style>
<div class="wrap">
  <p class="eyebrow">早期解約リスク保全 ／ 運用ダッシュボード</p>
  <h1>どの案件から保全に入るか</h1>
  <p class="sub">過去の傾向から「半年以内にやめそうな案件」を見つけ、手を打つ順番を決めるための画面です。</p>
  <div class="banner">
    <span class="pill warn">数字はすべて合成（偽データ）</span>
    <span class="pill warn">品質チェック AUC 0.558 ＝本番はAUC確認後に使用</span>
    <span class="pill">継続中 {n_score}件を採点</span>
  </div>
{alert_html}
  <section>
    <div class="h"><span class="n">01</span><h2>「守れる金額」順ランキング</h2></div>
    <p class="cap">継続中の案件を <b>解約リスク% × 年間保険料（目安）＝守れる金額</b> の大きい順に。リスクが同じでも高額契約を優先＝<b>守れる保険料が大きい順</b>に手を打つ、という考え方です。保険料は月額×12の概算。<b>「最初の一手」は保全責任者の実践に沿ったたたき台</b>で、現場に合わせて確定します。</p>
    <div class="fieldmemo">🗣️ <b>現場メモ（徳元さん）</b>：契約後<b>3営業日</b>に申込内容の確認 → 次は<b>約30日後</b>の初回引落案内。この<b>“約30日の空白”が危険窓</b>で、高リスクはこの間に追加の一手を。対応キャパは<b>約30件／日</b>＝この表の上位から回すのが効率的。</div>
    <div class="card">
      <div class="heat-scroll">
      <table class="rank-tbl">
        <thead><tr><th>#</th><th>顧客ID</th><th>商品</th><th>リスク</th><th>年間保険料<span class="th-note">目安</span></th><th>守れる金額<span class="th-note">目安</span></th><th>効いている理由（上位3つ）</th></tr></thead>
        <tbody>{''.join(rank_rows)}</tbody>
      </table>
      </div>
    </div>
  </section>

  <section>
    <div class="h"><span class="n">02</span><h2>掛け合わせ別の解約傾向</h2></div>
    <p class="cap">過去の“決着済み”実績での早期解約率。色が濃いほど高い＝初期フォローの型を見直したい組み合わせ。<b>信頼できるマス（n≥{MIN_RELIABLE_N}）だけ表示</b>し、件数不足のマスは空白にしています（隠した数は各表の下に明記）。行は<b>解約率の高い順</b>。教育・型改善が目的で、人事評価には使いません。</p>
    {heatmaps}
  </section>

  <section>
    <div class="h"><span class="n">03</span><h2>だから、どこから手を打つ</h2></div>
    <div class="bridge">{bridge}</div>
  </section>

  <div class="disclaimer">
    ※ このダッシュボードの数字はすべて<b>合成データ（偽データ）</b>です。①のランキングはモデルの予測で、今回の合成では品質チェック（AUC 0.558）が弱いため<b>本番ではAUC合格を確認してから</b>使います。②は過去実績の傾向で、営業担当別は<b>教育・初期フォローの型改善が目的</b>。人事評価・叱責には使いません。実データの本番実行は、統制された社内環境で審査後に行います。
  </div>
</div>"""
    # 出力は private/(gitignore)限定。顧客個人情報を含みうるためリポジトリ直下には書かない。
    out = os.path.join(D, "action_board.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(doc)
    print(f"[board] → {out}")
    if worst:
        print(f"[worst reliable combo] {worst['rk']} × {worst['ck']}: "
              f"{worst['rate']*100:.0f}% (n={worst['n']})")


if __name__ == "__main__":
    main()
