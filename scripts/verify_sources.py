#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hojo-hq 検証部(ケンショウ)× 100点基準❹
掲載データの「原文照合」を毎日5件自動サンプリングする。

方式:
- jGrants由来の制度: jGrants APIから同じidの詳細を再取得し、
  名称・締切・上限額を機械的に厳密照合(APIキー不要)。
- 県・公社由来の制度: 出典URLのHTML本文を取得し、Claude API(Haiku)で
  掲載内容(名称/締切/金額)と原文の整合を判定(ANTHROPIC_API_KEY必要。
  未設定時はスキップして通知のみ)。

不一致があれば verify_report.txt に書き出して exit 1
(→ ワークフローがIssueを自動起票する)。
"""
import json
import os
import random
import re
import sys
import urllib.request
from datetime import datetime, timezone, timedelta

JST = timezone(timedelta(hours=9))
DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "subsidies.json")
REPORT_PATH = os.path.join(os.path.dirname(__file__), "..", "verify_report.txt")
JGRANTS_DETAIL = "https://api.jgrants-portal.go.jp/exp/v1/public/subsidies/id/{sid}"
SAMPLE_SIZE = 5
CLAUDE_MODEL = "claude-haiku-4-5"

VERDICT_SCHEMA = {
    "type": "object",
    "properties": {
        "consistent": {
            "type": "boolean",
            "description": "掲載データ(名称・締切・金額)が原文ページと矛盾しないか",
        },
        "issues": {
            "type": "array",
            "items": {"type": "string"},
            "description": "矛盾・疑義がある点の説明(日本語)。なければ空配列",
        },
        "page_mentions_subsidy": {
            "type": "boolean",
            "description": "ページ本文がこの制度に言及しているか(リンク切れ・別ページ検知用)",
        },
    },
    "required": ["consistent", "issues", "page_mentions_subsidy"],
    "additionalProperties": False,
}


def jst_date(s: str | None) -> str | None:
    """jGrants APIの日時をJST日付(YYYY-MM-DD)へ。fetch_jgrants.py と同じ変換。"""
    if not s:
        return None
    try:
        return (
            datetime.fromisoformat(s.replace("Z", "+00:00"))
            .astimezone(JST)
            .strftime("%Y-%m-%d")
        )
    except Exception:
        return None


def fetch(url: str, timeout: int = 30) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "hojo-hq-verify/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as res:
        return res.read()


def strip_html(html: str, limit: int = 12000) -> str:
    html = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", html)
    text = re.sub(r"(?s)<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text)
    return text[:limit]


def verify_jgrants(item: dict) -> list[str]:
    """jGrants APIの現在値と厳密照合。差異のリストを返す(空=OK)。"""
    issues: list[str] = []
    try:
        data = json.loads(fetch(JGRANTS_DETAIL.format(sid=item["id"])).decode("utf-8"))
    except Exception as e:
        return [f"jGrants APIの再取得に失敗: {e}"]

    results = data.get("result") or []
    if not results:
        return ["jGrants APIに該当IDが存在しない(公募終了・取り下げの可能性。掲載継続は不適切)"]
    cur = results[0]

    api_name = cur.get("title") or cur.get("name") or ""
    if api_name and api_name != item.get("name"):
        issues.append(f"名称不一致: 掲載「{item.get('name')}」/ 原文「{api_name}」")

    api_deadline = jst_date(cur.get("acceptance_end_datetime"))
    if api_deadline and item.get("deadline") not in (api_deadline, "要確認"):
        issues.append(f"締切不一致: 掲載「{item.get('deadline')}」/ 原文「{api_deadline}」")

    api_amount = cur.get("subsidy_max_limit")
    if api_amount is not None and str(item.get("max_amount")) != str(api_amount):
        issues.append(f"上限額不一致: 掲載「{item.get('max_amount')}」/ 原文「{api_amount}」")

    return issues


def verify_local_with_claude(item: dict, client) -> list[str]:
    """県・公社ページをClaude(Haiku)で照合。差異のリストを返す(空=OK)。"""
    try:
        html = fetch(item["source_url"]).decode("utf-8", errors="replace")
    except Exception as e:
        return [f"出典URLの取得に失敗: {e}(リンク切れの可能性)"]

    page_text = strip_html(html)
    prompt = (
        "あなたは補助金情報サイトの検証担当です。掲載データが出典ページの原文と"
        "矛盾しないか判定してください。表記ゆれ(全角半角・日付形式・万円/円表記の違い)は"
        "矛盾とみなさず、金額や日付の実質的な食い違い、制度の言及自体がない場合のみ"
        "問題として報告してください。\n\n"
        f"【掲載データ】\n名称: {item.get('name')}\n締切: {item.get('deadline')}\n"
        f"上限額: {item.get('max_amount')}\n発行元: {item.get('issuer')}\n\n"
        f"【出典ページ本文(抜粋)】\n{page_text}"
    )
    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=1024,
        output_config={"format": {"type": "json_schema", "schema": VERDICT_SCHEMA}},
        messages=[{"role": "user", "content": prompt}],
    )
    text = next(b.text for b in response.content if b.type == "text")
    verdict = json.loads(text)

    issues: list[str] = []
    if not verdict["page_mentions_subsidy"]:
        issues.append("出典ページに制度の言及が見つからない(移設・削除の可能性)")
    if not verdict["consistent"]:
        issues.extend(verdict["issues"] or ["原文と掲載データに矛盾(詳細不明)"])
    return issues


def main() -> None:
    with open(DATA_PATH, encoding="utf-8") as f:
        items = json.load(f)["items"]

    today = datetime.now(JST).strftime("%Y-%m-%d")
    sample = random.Random(today).sample(items, min(SAMPLE_SIZE, len(items)))

    client = None
    if os.environ.get("ANTHROPIC_API_KEY"):
        import anthropic

        client = anthropic.Anthropic()
    else:
        print("[info] ANTHROPIC_API_KEY未設定: 県・公社ページのClaude照合はスキップ(jGrants照合のみ実施)")

    lines: list[str] = [f"原文照合レポート {today}(サンプル{len(sample)}件)", ""]
    failed = 0
    for item in sample:
        is_jgrants = "jgrants-portal" in (item.get("source_url") or "")
        label = f"{item.get('name', '')[:40]} [{item.get('source_url')}]"
        if is_jgrants:
            issues = verify_jgrants(item)
        elif client:
            issues = verify_local_with_claude(item, client)
        else:
            lines.append(f"⏭ SKIP(APIキー未設定): {label}")
            continue

        if issues:
            failed += 1
            lines.append(f"❌ NG: {label}")
            lines.extend(f"   - {msg}" for msg in issues)
        else:
            lines.append(f"✅ OK: {label}")

    lines.append("")
    lines.append(f"結果: NG {failed}件 / 照合 {len(sample)}件")
    report = "\n".join(lines)
    print(report)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(report)

    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
