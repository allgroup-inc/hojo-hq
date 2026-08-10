"""結果記録 → 効果測定 → 学習（合成データ・デモ）＝ ③クローズドループの後半。

保全アクションログ(actions.csv)と成熟実績を突き合わせ、
(1) 効果測定: 保全接触あり/なしで早期解約率を比較（免疫時間除外・母数不足は参考・断定しない）
(2) 学習: 対応内容ごとの早期解約率＝「効いた一手」を並べ、"最初の一手"へ還元する材料にする。

正直さ（churn-retention-ops）:
- 早期解約率は成熟実績（is_resolved）のみ。接触は解約前のものだけ（免疫時間バイアス回避・データ生成側で担保）。
- 母数不足（n<MIN_RELIABLE_N）は「参考」。0/100%を断定しない。営業担当別は扱わない（教育目的の別軸）。
- 観察データの単純比較は選択バイアスを含む → 本番は段階導入（先行/後発）で因果を測る、を明記。

PII（churn-pii-guard）: 入出力は private/ 限定。合成データ専用。

使い方: python -m scripts.churn.demo_effect_learning
"""
from __future__ import annotations
import html
import os
from datetime import date

from scripts.churn.intake import load_records, load_column_map
from scripts.churn.contact_log import load_contacts
from scripts.churn.effect_learning import effect, learning

D = "private/demo"
AS_OF = date(2026, 8, 1)


# 6ヶ月窓が完全に経過した成熟契約のみで測る（打ち切り回避）。AS_OFの6ヶ月前より前。
MATURE_BEFORE = date(2026, 2, 1)
_CONTACT_MAP = {"customer_id": "顧客ID", "apply_date": "契約日", "contact_date": "接触日",
                "action": "対応内容", "result": "結果区分", "reaction": "顧客反応"}


def build():
    cmap = load_column_map(f"{D}/column_map_real.json")
    records = load_records(f"{D}/apps.csv", cmap, AS_OF)
    contacts = load_contacts(f"{D}/actions.csv", _CONTACT_MAP)
    # 本体モジュールに委譲（成熟のみ・解約前接触のみ=免疫時間除外・空アクション除外・母数不足参考）
    return effect(records, contacts, MATURE_BEFORE), learning(records, contacts, MATURE_BEFORE)


def render(overall, actions):
    max_rate = max((a["rate"] for a in actions), default=0.01) or 0.01
    best = actions[0] if actions else None
    diff = overall["diff"]
    ref = ' <span class="tag">参考(母数不足)</span>' if overall["reference"] else ""

    arows = []
    for a in actions:
        w = min(a["rate"] / max_rate, 1.0) * 100
        rtag = ' <span class="tag">参考</span>' if a["reference"] else ""
        arows.append(f"""
        <tr>
          <td class="an">{html.escape(a['action'])}{rtag}</td>
          <td class="num">{a['n']}</td>
          <td class="num">{a['churn']}</td>
          <td class="bar"><div class="track"><div class="fill" style="width:{w:.0f}%"></div></div></td>
          <td class="rate">{a['rate']*100:.1f}%</td>
        </tr>""")

    doc = f"""<title>保全の効果測定と学習（デモ）</title>
<style>
  :root{{--ground:#FBF8F3;--card:#FFF;--ink:#13222E;--soft:#4B5C6A;--line:#E4DBCB;--navy:#00335C;
    --accent:#F88800;--good:#2E7D5B;--goodbg:#E8F2EC;--bad:#C4443A;--warn:#B5651D;--warnbg:#FBEEDD;
    --sh:0 1px 2px rgba(19,34,46,.05),0 9px 24px rgba(19,34,46,.06)}}
  @media(prefers-color-scheme:dark){{:root{{--ground:#0E1922;--card:#152430;--ink:#EAF1F6;--soft:#A6B7C4;--line:#26394A;
    --navy:#7FB0D8;--accent:#FFA22E;--good:#6FCB9F;--goodbg:#123024;--bad:#F0776D;--warn:#E8A84E;--warnbg:#3A2A12;
    --sh:0 1px 2px rgba(0,0,0,.3),0 12px 30px rgba(0,0,0,.4)}}}}
  :root[data-theme=light]{{--ground:#FBF8F3;--card:#FFF;--ink:#13222E;--soft:#4B5C6A;--line:#E4DBCB;--navy:#00335C;--accent:#F88800;--good:#2E7D5B;--goodbg:#E8F2EC;--bad:#C4443A;--warn:#B5651D;--warnbg:#FBEEDD}}
  :root[data-theme=dark]{{--ground:#0E1922;--card:#152430;--ink:#EAF1F6;--soft:#A6B7C4;--line:#26394A;--navy:#7FB0D8;--accent:#FFA22E;--good:#6FCB9F;--goodbg:#123024;--bad:#F0776D;--warn:#E8A84E;--warnbg:#3A2A12}}
  *{{box-sizing:border-box}}
  body{{margin:0;background:var(--ground);color:var(--ink);line-height:1.7;font-feature-settings:"palt" 1;
    font-family:"Hiragino Kaku Gothic ProN","Yu Gothic",Meiryo,"Noto Sans JP",system-ui,sans-serif}}
  .wrap{{max-width:840px;margin:0 auto;padding:38px 20px 66px}}
  .eyebrow{{font-size:11.5px;letter-spacing:.16em;font-weight:700;color:var(--accent);text-transform:uppercase;margin:0 0 8px}}
  h1{{font-size:clamp(22px,4vw,29px);margin:0 0 6px;font-weight:800}}
  .sub{{color:var(--soft);font-size:14px;margin:0 0 16px}}
  .banner{{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:20px}}
  .pill{{font-size:12px;font-weight:700;padding:5px 11px;border-radius:999px;border:1px solid var(--line);background:var(--card);color:var(--navy)}}
  .pill.warn{{background:var(--warnbg);color:var(--warn);border-color:transparent}}
  h2{{font-size:17px;font-weight:800;margin:26px 0 6px;display:flex;align-items:center;gap:9px}}
  h2::before{{content:"";width:9px;height:9px;border-radius:2px;background:var(--accent)}}
  .cap{{font-size:12.5px;color:var(--soft);margin:0 0 12px}}
  .cmp{{display:flex;flex-wrap:wrap;gap:12px;align-items:stretch}}
  .box{{flex:1 1 170px;background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px 18px;box-shadow:var(--sh)}}
  .box .v{{font-size:30px;font-weight:800;font-variant-numeric:tabular-nums;line-height:1}}
  .box .l{{font-size:12.5px;color:var(--soft);margin-top:5px}}
  .box.c .v{{color:var(--good)}} .box.n .v{{color:var(--bad)}}
  .box.d{{background:var(--goodbg);border-color:var(--good)}}
  .box.d .v{{color:var(--good)}}
  .tag{{font-size:10px;font-weight:700;color:var(--warn);background:var(--warnbg);border-radius:5px;padding:1px 6px}}
  .card{{background:var(--card);border:1px solid var(--line);border-radius:14px;box-shadow:var(--sh);overflow:hidden}}
  table{{border-collapse:collapse;width:100%;font-size:13.5px}}
  thead th{{background:transparent;color:var(--soft);font-size:11.5px;font-weight:700;text-align:left;padding:10px 12px;border-bottom:1.5px solid var(--line)}}
  td{{padding:10px 12px;border-bottom:1px solid var(--line);vertical-align:middle}}
  tr:last-child td{{border-bottom:none}}
  td.an{{font-weight:700}} td.num,td.rate{{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}}
  td.rate{{font-weight:800}}
  .bar{{width:32%}}
  .track{{background:color-mix(in srgb,var(--soft) 18%,transparent);border-radius:5px;height:13px}}
  .fill{{height:100%;border-radius:5px;background:var(--accent)}}
  .warnnote{{margin-top:12px;padding:12px 15px;border-radius:11px;background:var(--warnbg);border:1px solid var(--warn);font-size:13px;line-height:1.65}}
  .warnnote b{{color:var(--ink)}}
  .learn{{margin-top:14px;padding:14px 16px;border-radius:12px;background:var(--goodbg);border:1px solid var(--good);font-size:14px;line-height:1.7}}
  .learn b{{color:var(--ink)}}
  .disc{{margin-top:22px;padding:13px 16px;border:1px solid var(--line);border-radius:11px;background:var(--card);font-size:12px;color:var(--soft);line-height:1.7}}
  .disc b{{color:var(--warn)}}
</style>
<div class="wrap">
  <p class="eyebrow">早期解約 &lt;3% ／ クローズドループ 後半</p>
  <h1>保全の効果測定と学習</h1>
  <p class="sub">記録した保全結果から「効いたか」を測り、「どの一手が効くか」を学ぶ画面です。</p>
  <div class="banner">
    <span class="pill warn">数字はすべて合成（偽データ）</span>
    <span class="pill">成熟実績のみ・免疫時間除外</span>
  </div>

  <h2>① 効果測定（保全接触あり / なし）</h2>
  <p class="cap">6ヶ月窓が完全に経過した成熟契約のみ・解約前の接触のみを「あり」に数える（打ち切り／免疫時間バイアス回避）。{ref}</p>
  <div class="cmp">
    <div class="box c"><div class="v">{overall['rate_c']*100:.1f}%</div><div class="l">保全接触<b>あり</b>の早期解約率<br>（{overall['n_c']}件中）</div></div>
    <div class="box n"><div class="v">{overall['rate_n']*100:.1f}%</div><div class="l">保全接触<b>なし</b>の早期解約率<br>（{overall['n_n']}件中）</div></div>
    <div class="box d"><div class="v">{'−' if diff<0 else '+'}{abs(diff)*100:.1f}pt</div><div class="l">差（単純比較）<br><b>⚠️ これだけで判断しない</b></div></div>
  </div>
  <div class="warnnote">⚠️ <b>単純な あり/なし 比較は当てにならない</b>。母数と交絡で差が小さく、符号すら安定しない（この合成でも{'ありの方が僅かに高く出た' if diff>=0 else 'ぶれている'}）。正しく読むには <b>②一手ごと</b> ＋ <b>段階導入（先行/後発）で因果</b>を測る。</div>

  <h2>② 学習（どの一手が効くか）</h2>
  <p class="cap">対応内容ごとの早期解約率。<b>低いほど継続に効いた一手</b>＝「最初の一手」へ還元する材料。少件数は「参考」。</p>
  <div class="card">
    <table>
      <thead><tr><th>対応内容</th><th>件数</th><th>解約</th><th></th><th>早期解約率</th></tr></thead>
      <tbody>{''.join(arows)}</tbody>
    </table>
  </div>
  {(f'<div class="learn">💡 <b>学習の示唆</b>：単純な あり/なし では判断しない。<b>一手ごと</b>に見ると <b>{html.escape(best["action"])}</b> の早期解約率が最も低く（{best["rate"]*100:.1f}%）、継続に効いた候補。→ 該当する駆動要因の契約で「最初の一手」に優先還元する。ただし母数は中程度なので、<b>本番は段階導入で因果を確定</b>してから広げる。' + ('（※母数不足のため参考）' if best['reference'] else '') + '</div>') if best else ''}

  <div class="disc">
    ※ 数字はすべて<b>合成データ</b>（効きは検証用に仕込み）。<b>観察データの単純比較は選択バイアスを含む</b>ため、本番は<b>段階導入（先行/後発）で因果</b>を測る。早期解約率は成熟実績のみ・<b>解約後の接触は数えない（免疫時間除外）</b>・母数不足は「参考」・0/100%を断定しない。営業担当別は教育目的の別軸。実データは統制環境で審査後。
  </div>
</div>"""
    out = os.path.join(D, "effect_learning.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(doc)
    print(f"[effect] あり{overall['rate_c']*100:.1f}%({overall['n_c']}) / "
          f"なし{overall['rate_n']*100:.1f}%({overall['n_n']}) 差{overall['diff']*100:+.1f}pt → {out}")
    if best:
        print(f"[learn] 効いた一手: {best['action']} {best['rate']*100:.1f}% (n={best['n']})")
    return out


def main():
    overall, actions = build()
    render(overall, actions)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
