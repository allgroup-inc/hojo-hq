"""保全コンソール（記録一体）＝架電リストの表示から対応記録までを1画面で。

「架電から対応記録まで全部このシステムで・外で管理しない」（小柳さん 2026-08-18）ための、
**ローカルで動く**操作画面。Python標準ライブラリだけ・外部サービス不使用・データはこのPC内。
- 画面: 今日の要接触（優先度順）＋各行に「対応を記録」フォーム（選択式）。
- 保存: フォーム送信 → 保全ログCSV（private/）に追記（`contact_log.append_contact`）→ 画面に戻る。
churn-pii-guard: 実データは統制されたPCでのみ・出力は private/・公開リポには置かない。
"""
from __future__ import annotations
import html
import urllib.parse

from .contact_log import append_contact

# 記録の選択肢（保全記録_かんたん入力様式 と同じ）。手打ちを減らす。
PICKLISTS = {
    "medium": ["架電", "訪問"],
    "concern": ["保険料負担", "必要性の疑問", "家計不安", "商品理解", "手続き不明", "その他"],
    "approach": ["入金のご相談・コンビニ用紙", "口座の再設定案内", "減額のご相談",
                 "家計の見直し提案", "給付事例のご案内", "再説明・ご納得", "ごあいさつ・様子伺い", "その他"],
    "result": ["つながった", "入金いただけた", "検討中", "解約意向", "つながらない"],
    "next_action": ["完了", "再架電", "訪問", "書類送付", "様子見"],
}
_LABELS = {"medium": "手段", "concern": "懸念", "approach": "返し方",
           "result": "結果", "next_action": "次アクション"}


def _select(name, options):
    opts = "".join(f'<option value="{html.escape(o)}">{html.escape(o)}</option>' for o in options)
    return (f'<label style="font-size:12px">{_LABELS[name]}'
            f'<select name="{name}" style="margin:0 6px 0 2px">{opts}</select></label>')


def render_console(today, as_of, saved_cid=None):
    """今日の要接触＋各行に対応記録フォーム（選択式）を出す。today は triage の候補並び。"""
    rows = []
    for c in today:
        cid = str(c.get("customer_id") or "—")
        trig = html.escape(str(c.get("trigger", "")))
        ch = html.escape(str(c.get("channel", "架電")))
        save = c.get("saveable")
        save_txt = f"{int(save):,}円" if save else "—"
        rec = html.escape(str(c.get("recommendation", "")))
        selects = "".join(_select(k, PICKLISTS[k]) for k in
                          ("medium", "concern", "approach", "result", "next_action"))
        just_saved = ' ✅記録しました' if cid == str(saved_cid) else ""
        rows.append(
            '<tr><td style="white-space:nowrap">' + html.escape(cid) + '</td>'
            f'<td>{trig}</td><td>{ch}</td><td style="text-align:right">{save_txt}</td>'
            f'<td style="font-size:12px">{rec}</td>'
            '<td><form method="post" action="/record" style="margin:0">'
            f'<input type="hidden" name="customer_id" value="{html.escape(cid)}">'
            + selects +
            '<button type="submit" style="margin-left:6px">保存</button>'
            f'<span style="color:#1E8449">{just_saved}</span></form></td></tr>')
    doc = (
        '<!doctype html><meta charset="utf-8"><title>保全コンソール</title>'
        '<style>body{font-family:Meiryo,"Noto Sans JP",sans-serif;padding:16px}'
        'table{border-collapse:collapse;width:100%}th,td{border:1px solid #ccc;padding:6px;font-size:13px}'
        'th{background:#00335C;color:#fff}select,button{font-size:12px}</style>'
        f'<h1>保全コンソール（{as_of}）— 今日の要接触 {len(today)}件</h1>'
        '<p style="font-size:12px;color:#6B6B6B">上から順に架電し、その場で対応を記録（選ぶだけ）→保存。'
        '記録はこのPC内に貯まります。連絡は人が実行・督促にしない・成績評価に使わない。</p>'
        '<table><thead><tr><th>顧客ID</th><th>きっかけ</th><th>手段</th><th>守れる金額</th>'
        '<th>おすすめの一手</th><th>対応の記録</th></tr></thead>'
        f'<tbody>{"".join(rows)}</tbody></table>')
    return doc


def _today_list(csv_path, column_map, as_of, capacity):
    from .intake import load_records
    from .fit import fit_model
    from .triage import classify, triage
    records = load_records(csv_path, column_map, as_of)
    model = fit_model(records)
    today, _carry, _stats = triage(classify(records, model, as_of), capacity)
    return today


def make_handler(csv_path, column_map, contacts_out, contact_map, as_of, capacity):
    from http.server import BaseHTTPRequestHandler

    class Handler(BaseHTTPRequestHandler):
        def _page(self, saved_cid=None):
            today = _today_list(csv_path, column_map, as_of, capacity)
            body = render_console(today, as_of, saved_cid).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            self._page()

        def do_POST(self):
            n = int(self.headers.get("Content-Length", 0))
            form = urllib.parse.parse_qs(self.rfile.read(n).decode("utf-8"))
            vals = {k: (form.get(k, [""])[0]) for k in
                    ("customer_id", "medium", "concern", "approach", "result", "next_action")}
            vals["contact_date"] = str(as_of)
            append_contact(contacts_out, contact_map, vals)   # private/ に追記
            self._page(saved_cid=vals["customer_id"])

        def log_message(self, *a):   # 標準の逐次ログは出さない（PII混入を避ける）
            pass

    return Handler
