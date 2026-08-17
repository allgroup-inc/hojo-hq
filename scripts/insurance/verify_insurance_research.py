#!/usr/bin/env python3
"""勝てるくん: 3社公開情報リサーチの原文照合(マルチAIダブルチェック)

docs/insurance/照合対象_早見表_claims.json の各主張について、出典URLの原文を1回だけ取得し、
Claude と Gemini に同一入力で独立判定させる(multi-ai-crosscheckスキル準拠)。

- 保守的マージ: 両方「支持」のときだけ verified。どちらかが不支持/不明なら「要確認」
- Gemini障害はスキップして続行(参加率を毎回記録。記録なしのスキップ禁止)
- 出力: docs/insurance/照合結果_早見表_latest.json(同日再実行は上書き・べき等)
        docs/insurance/照合レポート_早見表.md(人間レビュー用)
- AI一致は断定の十分条件ではない。verified でも最終根拠は原文(絶対ルール1)

決裁: 2026-08-17 小柳さん(決裁キュー⑥第一段階: 公開情報のみ・顧客情報は扱わない)
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone, timedelta
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
CLAIMS = ROOT / "docs/insurance/照合対象_早見表_claims.json"
OUT_JSON = ROOT / "docs/insurance/照合結果_早見表_latest.json"
OUT_MD = ROOT / "docs/insurance/照合レポート_早見表.md"

CLAUDE_MODEL = "claude-sonnet-5"
GEMINI_MODELS = ["gemini-flash-latest", "gemini-3-flash-preview", "gemini-2.5-flash"]
GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "{model}:generateContent?key={key}"
)
JST = timezone(timedelta(hours=9))

VERDICT_SCHEMA = {
    "type": "object",
    "properties": {
        "supported": {"type": "string", "enum": ["yes", "partial", "no", "not_found"]},
        "quote": {"type": "string"},
        "note": {"type": "string"},
    },
    "required": ["supported", "quote", "note"],
}


class _Text(HTMLParser):
    SKIP = {"script", "style", "noscript"}

    def __init__(self) -> None:
        super().__init__()
        self.buf: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self._skip += 1

    def handle_endtag(self, tag):
        if tag in self.SKIP and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if not self._skip and data.strip():
            self.buf.append(data.strip())


def fetch_text(url: str, limit: int = 14000) -> str | None:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (verify-bot)"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                html = r.read().decode("utf-8", errors="replace")
            p = _Text()
            p.feed(html)
            return " ".join(p.buf)[:limit]
        except (urllib.error.URLError, TimeoutError, OSError):
            time.sleep(2 * (attempt + 1))
    return None


def build_prompt(claim: str, page: str) -> str:
    return (
        "あなたは保険商品情報の照合担当です。以下の「主張」が「ページ本文」で裏付けられるか判定してください。\n"
        "ルール: ページに書かれていることだけで判定する。推測で補わない。\n"
        "- yes: 主張の要点がすべて本文で確認できる\n"
        "- partial: 一部のみ確認できる(確認できなかった要素をnoteに)\n"
        "- no: 本文と矛盾する(矛盾箇所をnoteに)\n"
        "- not_found: 本文に該当の記載が見当たらない\n"
        "quote には根拠となる本文の該当箇所をそのまま引用する(not_foundなら空文字)。\n\n"
        f"【主張】\n{claim}\n\n【ページ本文】\n{page}"
    )


def ask_claude(prompt: str, client):
    msg = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=1000,
        tools=[{"name": "verdict", "description": "照合判定", "input_schema": VERDICT_SCHEMA}],
        tool_choice={"type": "tool", "name": "verdict"},
        messages=[{"role": "user", "content": prompt}],
    )
    for block in msg.content:
        if block.type == "tool_use":
            return dict(block.input)
    return None


def ask_gemini(prompt: str, key: str):
    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseJsonSchema": VERDICT_SCHEMA,
        },
    }).encode()
    for model in list(GEMINI_MODELS):
        req = urllib.request.Request(
            GEMINI_URL.format(model=model, key=key), data=body,
            headers={"Content-Type": "application/json"}, method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                data = json.loads(r.read().decode())
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            if GEMINI_MODELS[0] != model:
                GEMINI_MODELS.remove(model)
                GEMINI_MODELS.insert(0, model)
            return json.loads(text)
        except Exception:
            continue
    return None


def merge(cl: dict | None, ge: dict | None) -> str:
    """保守的マージ: 両判定が揃って yes のときだけ verified。"""
    if cl is None:
        return "判定不能(Claude障害)"
    if ge is None:
        return "verified(単独)" if cl.get("supported") == "yes" else "要確認"
    a, b = cl.get("supported"), ge.get("supported")
    if a == "yes" and b == "yes":
        return "verified"
    return "要確認"


def main() -> None:
    data = json.loads(CLAIMS.read_text())
    try:
        import anthropic
        client = anthropic.Anthropic()
    except Exception as e:
        print(f"anthropic 初期化失敗: {e}", file=sys.stderr)
        sys.exit(1)
    gem_key = os.environ.get("GEMINI_API_KEY", "")

    today = datetime.now(JST).strftime("%Y-%m-%d")
    results, pages = [], {}
    gem_ok = 0
    for c in data["claims"]:
        url = c["url"]
        if url not in pages:
            pages[url] = fetch_text(url)  # 1URL1回取得。両AIに同一テキストを渡す
        page = pages[url]
        if page is None:
            results.append({**c, "status": "取得失敗(URL要確認)", "claude": None, "gemini": None})
            continue
        prompt = build_prompt(c["claim"], page)
        try:
            cl = ask_claude(prompt, client)
        except Exception as e:
            cl = None
            print(f"[{c['id']}] Claude error: {e}", file=sys.stderr)
        ge = ask_gemini(prompt, gem_key) if gem_key else None
        if ge is not None:
            gem_ok += 1
        results.append({**c, "status": merge(cl, ge), "claude": cl, "gemini": ge})
        print(f"[{c['id']}] {results[-1]['status']}")

    n = len(data["claims"])
    summary = {
        "run_date": today,
        "total": n,
        "verified": sum(1 for r in results if r["status"].startswith("verified")),
        "needs_review": sum(1 for r in results if r["status"] == "要確認"),
        "fetch_failed": sum(1 for r in results if "取得失敗" in r["status"]),
        "gemini_participation": f"{gem_ok}/{n}",
        "gemini_enabled": bool(gem_key),
    }
    OUT_JSON.write_text(json.dumps({"summary": summary, "results": results}, ensure_ascii=False, indent=1))

    lines = [
        "# 勝てるくん 原文照合レポート(早見表の根拠・自動生成)",
        "",
        f"実行日: {today} / 判定: Claude+Gemini独立ダブルチェック(Gemini参加率 {summary['gemini_participation']})",
        f"結果: verified {summary['verified']} / 要確認 {summary['needs_review']} / URL取得失敗 {summary['fetch_failed']} (全{n}件)",
        "",
        "**verifiedでも最終根拠は原文(絶対ルール1)。「要確認」は人間が出典URLを開いて判断し、リサーチファイルを修正すること。**",
        "",
        "| ID | 会社 | 主張(要約) | 判定 | メモ |",
        "|---|---|---|---|---|",
    ]
    for r in results:
        note = ""
        for v in (r.get("claude"), r.get("gemini")):
            if v and v.get("supported") != "yes" and v.get("note"):
                note = v["note"][:80]
                break
        lines.append(f"| {r['id']} | {r['company']} | {r['claim'][:45]}… | {r['status']} | {note} |")
    lines.append("")
    lines.append(f"要確認の詳細(両AIの判定・引用全文): docs/insurance/照合結果_早見表_latest.json")
    OUT_MD.write_text("\n".join(lines) + "\n")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
