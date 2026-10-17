"""現ステータス遷移の追跡（救えた／失った）＝クローズドループ（連動アイデア2位）。

月次スナップショット2枚（前月・当月）を突合し、**前月に「未収で継続」だった契約**が
当月どうなったかを集計する。保全アクションの成果が毎月自動で積み上がり、学習が回る。

- 救えた: 未収が解消（当月＝継続・未収0）
- 失った: 早期解約に転落（未払消滅・失効・CAN 等）
- 継続(未収残): まだ未収が残る
- recovery_rate = 救えた /（救えた＋失った）。分母0は None（算出不能・断定しない）。

保全連携（contacted_keys）: その間に保全接触した契約の (顧客ID, apply_id) 集合を渡すと、
接触あり/なしで救えた・失ったを分ける。**ただし接触は無作為でない＝生存者バイアスが残り、
救えた率の差は因果ではない**（因果は experiment.py の段階導入で確認）。

resilient-agent-design: 入力はスナップショット＝外部保存の状態。月キーでべき等に集計できる。
突合キーは (顧客ID, apply_id)。実処理は統制環境・審査後（PIIは private 限定）。
"""
from __future__ import annotations


def _key(r):
    return (r.get("customer_id"), r.get("apply_id"))


def _at_risk(r):
    """前月に「未収で継続」だった＝リスク母集団。"""
    return r.get("status_category") == "継続" and (r.get("unpaid_count") or 0) > 0


def _blank_bucket():
    return {"救えた": 0, "失った": 0, "継続(未収残)": 0}


def status_transitions(prev_records, curr_records, contacted_keys=None):
    """前月リスク契約の当月遷移を集計。救えた/失った/継続(未収残)＋接触有無別。"""
    prev = {_key(r): r for r in prev_records}
    contacted_keys = set(contacted_keys or ())
    out = _blank_bucket()
    out["by_contact"] = {"接触あり": _blank_bucket(), "接触なし": _blank_bucket()}

    for c in curr_records:
        k = _key(c)
        p = prev.get(k)
        if p is None or not _at_risk(p):
            continue                      # 前月に存在＆リスクだった契約だけを追う
        if c.get("status_category") == "早期解約":
            bucket = "失った"
        elif c.get("status_category") == "継続" and (c.get("unpaid_count") or 0) == 0:
            bucket = "救えた"
        else:
            bucket = "継続(未収残)"
        out[bucket] += 1
        out["by_contact"]["接触あり" if k in contacted_keys else "接触なし"][bucket] += 1

    resolved = out["救えた"] + out["失った"]
    out["recovery_rate"] = (out["救えた"] / resolved) if resolved else None
    return out


def render_html(t, path):
    """遷移サマリをHTML出力（表示層・出力は private/ 限定）。"""
    def rate(b):
        r = b["救えた"] + b["失った"]
        return f'{b["救えた"] / r * 100:.1f}%' if r else "算出不能"
    rr = "算出不能" if t["recovery_rate"] is None else f'{t["recovery_rate"] * 100:.1f}%'
    ca, cn = t["by_contact"]["接触あり"], t["by_contact"]["接触なし"]
    doc = (
        '<!doctype html><meta charset="utf-8"><title>保全の成果（救えた/失った）</title>'
        '<style>body{font-family:Meiryo,"Noto Sans JP",sans-serif;padding:16px}'
        'table{border-collapse:collapse}th,td{border:1px solid #ccc;padding:6px;font-size:13px}'
        'th{background:#00335C;color:#fff}</style>'
        '<h1>保全の成果（前月に未収で継続だった契約の行方）</h1>'
        f'<p>救えた <b>{t["救えた"]}</b>件 / 失った <b>{t["失った"]}</b>件 / '
        f'未収残 {t["継続(未収残)"]}件 ／ 立て直し率 <b>{rr}</b></p>'
        '<table><thead><tr><th>保全接触</th><th>救えた</th><th>失った</th>'
        '<th>未収残</th><th>立て直し率</th></tr></thead><tbody>'
        f'<tr><td>接触あり</td><td>{ca["救えた"]}</td><td>{ca["失った"]}</td>'
        f'<td>{ca["継続(未収残)"]}</td><td>{rate(ca)}</td></tr>'
        f'<tr><td>接触なし</td><td>{cn["救えた"]}</td><td>{cn["失った"]}</td>'
        f'<td>{cn["継続(未収残)"]}</td><td>{rate(cn)}</td></tr></tbody></table>'
        '<p style="font-size:12px;color:#6B6B6B">接触あり/なしは無作為でないため、率の差は参考'
        '（生存者バイアス）。因果は段階導入(uplift)で確認。合成データ。</p>')
    with open(path, "w", encoding="utf-8") as f:
        f.write(doc)
