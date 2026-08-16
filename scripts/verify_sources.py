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
- マルチAIダブルチェック(2026-08-06 小柳さん決裁): GEMINI_API_KEY が設定されて
  いれば、同じ原文を Gemini でも独立に照合する。別系統モデルは誤り方が相関しない
  ため、どちらか一方でも矛盾を検知したら NG(要確認)扱い。Gemini側のAPI障害は
  NGにせず情報表示のみ(照合の可用性を外部ベンダーに依存させない)。
- 判定が割れたときのセカンドパス: 指摘した側のAIに根拠の引用を要求し、
  引用できない・見落としだった場合は撤回させる(誤検知Issueのノイズ対策)。
- NGの定義(議事_20260817): 掲載値が存在して原文と食い違う場合のみ。掲載値が
  None/「要確認」はサイト上の非断定表示(絶対ルール1)なので矛盾に数えない。
  かわりに原文に上限額の明記があれば「追加候補」として非失敗でレポート・履歴に
  記録し、人の原文確認後に追記する昇格運用に載せる。
- 照合履歴: 毎回の結果を data/kpi/verify_history.json に追記(同日再実行は上書き)。
  Gemini参加率も記録し、無料枠切れ等による「静かな脱落」を検知可能にする。
  NG項目の human_verdict は検証部が false_positive / true_mismatch を追記する運用。

不一致があれば verify_report.txt に書き出して exit 1
(→ ワークフローがIssueを自動起票する)。
"""
import json
import os
import random
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone, timedelta

JST = timezone(timedelta(hours=9))
DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "subsidies.json")
REPORT_PATH = os.path.join(os.path.dirname(__file__), "..", "verify_report.txt")
# 照合履歴(壊れにくい設計・原則③: 状態はコンテキストでなく外部へ)。
# 2026-11-06 の効果測定で「NGのうち誤検知/真の不一致」を集計するための台帳。
# NG項目の human_verdict は人が後から "false_positive" / "true_mismatch" を記入する。
HISTORY_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "kpi", "verify_history.json"
)
JGRANTS_DETAIL = "https://api.jgrants-portal.go.jp/exp/v1/public/subsidies/id/{sid}"
SAMPLE_SIZE = 5
CLAUDE_MODEL = "claude-haiku-4-5"
# モデルは廃止・改名され得るため候補を順に試す。"-latest" エイリアスを最優先に
# しておくと Google 側の世代交代に自動追従する(2026-08-06: gemini-2.5-flash 404 対応)。
GEMINI_MODELS = ["gemini-flash-latest", "gemini-3-flash-preview", "gemini-2.5-flash"]
GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "{model}:generateContent?key={key}"
)

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
        "amount_in_source": {
            "type": "string",
            "description": "掲載データの上限額がNone/「要確認」で、原文に上限額が明記されている場合のみ、その金額を原文ママで記入(追加候補として人が確認する)。それ以外は空文字",
        },
    },
    "required": ["consistent", "issues", "page_mentions_subsidy", "amount_in_source"],
    "additionalProperties": False,
}

# 判定が割れたときの再確認(セカンドパス)。指摘した側に根拠の引用を要求し、
# 引用できない・見落としだった場合は撤回させる(誤検知によるIssueノイズ対策)。
RECHECK_SCHEMA = {
    "type": "object",
    "properties": {
        "upheld": {
            "type": "boolean",
            "description": "再確認の結果、指摘を維持するか。根拠を示せない・表記ゆれや略称の見落としだった場合は false(撤回)",
        },
        "evidence_quote": {
            "type": "string",
            "description": "指摘を維持する場合、根拠となる本文箇所の引用(原文ママ)。『言及が見つからない』の維持や撤回時は空文字",
        },
        "reason": {"type": "string", "description": "判断理由(日本語・簡潔に)"},
    },
    "required": ["upheld", "evidence_quote", "reason"],
    "additionalProperties": False,
}

GEMINI_VERDICT_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "consistent": {"type": "BOOLEAN"},
        "issues": {"type": "ARRAY", "items": {"type": "STRING"}},
        "page_mentions_subsidy": {"type": "BOOLEAN"},
        "amount_in_source": {"type": "STRING"},
    },
    "required": ["consistent", "issues", "page_mentions_subsidy", "amount_in_source"],
}

GEMINI_RECHECK_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "upheld": {"type": "BOOLEAN"},
        "evidence_quote": {"type": "STRING"},
        "reason": {"type": "STRING"},
    },
    "required": ["upheld", "evidence_quote", "reason"],
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


def build_verify_prompt(item: dict, page_text: str) -> str:
    """Claude/Gemini 共通の照合プロンプト。両者に同一条件で判定させる。"""
    return (
        "あなたは補助金情報サイトの検証担当です。掲載データが出典ページの原文と"
        "矛盾しないか判定してください。表記ゆれ(全角半角・日付形式・万円/円表記の違い)は"
        "矛盾とみなさず、金額や日付の実質的な食い違い、制度の言及自体がない場合のみ"
        "問題として報告してください。\n"
        "掲載データの値が None・空・「要確認」の項目は、サイト上では「要確認」と"
        "表示され断定していないことを意味します(議事_20260817)。原文に値が明記されて"
        "いても、それは「未掲載」であって矛盾ではないため issues には含めないでください。"
        "そのかわり、上限額が未掲載で原文に上限額の明記がある場合は amount_in_source に"
        "その金額を原文ママで記入してください。\n\n"
        f"【掲載データ】\n名称: {item.get('name')}\n締切: {item.get('deadline')}\n"
        f"上限額: {item.get('max_amount')}\n発行元: {item.get('issuer')}\n\n"
        f"【出典ページ本文(抜粋)】\n{page_text}"
    )


def verdict_to_issues(verdict: dict) -> list[str]:
    """構造化判定(consistent/issues/page_mentions_subsidy)を差異リストへ。"""
    issues: list[str] = []
    if not verdict["page_mentions_subsidy"]:
        issues.append("出典ページに制度の言及が見つからない(移設・削除の可能性)")
    if not verdict["consistent"]:
        issues.extend(verdict["issues"] or ["原文と掲載データに矛盾(詳細不明)"])
    return issues


def verify_local_with_claude(item: dict, page_text: str, client) -> tuple[list[str], str]:
    """県・公社ページをClaude(Haiku)で照合。(差異リスト, 原文で見つけた未掲載の上限額)を返す。"""
    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=1024,
        output_config={"format": {"type": "json_schema", "schema": VERDICT_SCHEMA}},
        messages=[{"role": "user", "content": build_verify_prompt(item, page_text)}],
    )
    text = next(b.text for b in response.content if b.type == "text")
    verdict = json.loads(text)
    return verdict_to_issues(verdict), (verdict.get("amount_in_source") or "").strip()


def gemini_generate(prompt: str, schema: dict, api_key: str) -> dict | None:
    """Gemini APIで構造化出力を得る汎用ヘルパー。API障害時はNone。"""
    body = json.dumps(
        {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0,
                "responseMimeType": "application/json",
                "responseSchema": schema,
            },
        }
    ).encode("utf-8")
    last_error: Exception | None = None
    for model in GEMINI_MODELS:
        req = urllib.request.Request(
            GEMINI_URL.format(model=model, key=api_key),
            data=body,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as res:
                data = json.loads(res.read().decode("utf-8"))
            verdict = json.loads(data["candidates"][0]["content"]["parts"][0]["text"])
            # 使えたモデルを先頭へ寄せ、以降の照合で404の試行を繰り返さない
            if GEMINI_MODELS[0] != model:
                GEMINI_MODELS.remove(model)
                GEMINI_MODELS.insert(0, model)
            return verdict
        except urllib.error.HTTPError as e:
            last_error = e
            if e.code == 404:  # モデル提供終了・改名 → 次の候補へ
                continue
            break
        except Exception as e:
            last_error = e
            break
    print(f"[info] Gemini呼び出しに失敗: {last_error}")
    return None


def verify_local_with_gemini(item: dict, page_text: str, api_key: str) -> tuple[list[str], str] | None:
    """同じ原文をGeminiで独立照合。(差異リスト, 原文で見つけた未掲載の上限額)。API障害時はNone。"""
    verdict = gemini_generate(
        build_verify_prompt(item, page_text), GEMINI_VERDICT_SCHEMA, api_key
    )
    if verdict is None:
        return None
    return verdict_to_issues(verdict), (verdict.get("amount_in_source") or "").strip()


def build_recheck_prompt(item: dict, page_text: str, issues: list[str]) -> str:
    """判定が割れたときのセカンドパス。指摘側に根拠の引用を要求する。"""
    listed = "\n".join(f"- {m}" for m in issues)
    return (
        "あなたは補助金情報サイトの検証担当です。この掲載データについて、"
        "以下の指摘が出ましたが、別の独立した照合では問題なしと判定され、結論が割れています。\n\n"
        f"【指摘】\n{listed}\n\n"
        "出典ページ本文(抜粋)だけを根拠に、指摘が本当に正しいか再確認してください。\n"
        "- 金額・日付の食い違いを維持する場合: 根拠となる本文箇所をそのまま引用してください(evidence_quote)\n"
        "- 「制度の言及が見つからない」を維持する場合: 名称の表記ゆれ・略称・部分一致・関連事業名を"
        "本文から再走査し、それでも見つからない場合のみ維持してください(evidence_quoteは空でよい)\n"
        "- 根拠を示せない場合、または表記ゆれ・見落としだった場合: upheld=false で撤回してください\n\n"
        f"【掲載データ】\n名称: {item.get('name')}\n締切: {item.get('deadline')}\n"
        f"上限額: {item.get('max_amount')}\n発行元: {item.get('issuer')}\n\n"
        f"【出典ページ本文(抜粋)】\n{page_text}"
    )


def recheck_with_claude(item: dict, page_text: str, issues: list[str], client) -> dict | None:
    """Claudeの指摘を本人に再確認させる。API障害時はNone(=指摘維持)。"""
    try:
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=1024,
            output_config={"format": {"type": "json_schema", "schema": RECHECK_SCHEMA}},
            messages=[
                {"role": "user", "content": build_recheck_prompt(item, page_text, issues)}
            ],
        )
        text = next(b.text for b in response.content if b.type == "text")
        return json.loads(text)
    except Exception as e:
        print(f"[info] Claude再確認に失敗(指摘を維持): {e}")
        return None


def recheck_with_gemini(item: dict, page_text: str, issues: list[str], api_key: str) -> dict | None:
    """Geminiの指摘を本人に再確認させる。API障害時はNone(=指摘維持)。"""
    return gemini_generate(
        build_recheck_prompt(item, page_text, issues), GEMINI_RECHECK_SCHEMA, api_key
    )


def append_history(entry: dict) -> None:
    """日次の照合結果を data/kpi/verify_history.json へ追記。同日再実行は上書き(べき等)。"""
    try:
        with open(HISTORY_PATH, encoding="utf-8") as f:
            history = json.load(f)
    except Exception:
        history = []
    history = [h for h in history if h.get("date") != entry["date"]]
    history.append(entry)
    os.makedirs(os.path.dirname(HISTORY_PATH), exist_ok=True)
    with open(HISTORY_PATH, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=1)
        f.write("\n")


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

    gemini_key = os.environ.get("GEMINI_API_KEY") or ""
    if not gemini_key:
        print("[info] GEMINI_API_KEY未設定: Geminiダブルチェックはスキップ(従来のClaude単独照合)")

    lines: list[str] = [f"原文照合レポート {today}(サンプル{len(sample)}件)", ""]
    failed = 0
    gemini_eligible = 0  # Geminiが照合に参加すべきだった件数(AI照合対象×キー設定済み)
    gemini_joined = 0    # 実際に参加できた件数(A-2: 静かな脱落の検知用)
    history_items: list[dict] = []
    for item in sample:
        is_jgrants = "jgrants-portal" in (item.get("source_url") or "")
        label = f"{item.get('name', '')[:40]} [{item.get('source_url')}]"
        judged_by = ""
        judges: list[str] = []
        method = "jgrants" if is_jgrants else "ai"
        recheck_note = None
        amount_note = ""  # 未掲載×原文に金額あり → 追加候補(非失敗・議事_20260817)
        if is_jgrants:
            issues = verify_jgrants(item)
        elif client or gemini_key:
            try:
                html = fetch(item["source_url"]).decode("utf-8", errors="replace")
            except Exception as e:
                issues = [f"出典URLの取得に失敗: {e}(リンク切れの可能性)"]
            else:
                page_text = strip_html(html)
                claude_issues: list[str] | None = None
                gemini_issues: list[str] | None = None
                if client:
                    claude_issues, a = verify_local_with_claude(item, page_text, client)
                    amount_note = amount_note or a
                    judges.append("Claude")
                if gemini_key:
                    gemini_eligible += 1
                    g = verify_local_with_gemini(item, page_text, gemini_key)
                    if g is not None:
                        gemini_issues, a = g
                        amount_note = amount_note or a
                        gemini_joined += 1
                        judges.append("Gemini")

                # 判定が割れたときだけセカンドパス: 指摘した側に根拠の引用を要求し、
                # 撤回されたら誤検知としてOKに戻す(Issueノイズ対策。撤回も履歴に残す)
                if claude_issues is not None and gemini_issues is not None:
                    if claude_issues and not gemini_issues:
                        r = recheck_with_claude(item, page_text, claude_issues, client)
                        if r and not r["upheld"]:
                            recheck_note = f"Claudeが再確認で指摘を撤回: {r['reason']}"
                            claude_issues = []
                        elif r and r.get("evidence_quote"):
                            claude_issues.append(f"根拠引用: {r['evidence_quote'][:200]}")
                    elif gemini_issues and not claude_issues:
                        r = recheck_with_gemini(item, page_text, gemini_issues, gemini_key)
                        if r and not r["upheld"]:
                            recheck_note = f"Geminiが再確認で指摘を撤回: {r['reason']}"
                            gemini_issues = []
                        elif r and r.get("evidence_quote"):
                            gemini_issues.append(f"根拠引用: {r['evidence_quote'][:200]}")

                issues = [f"Claude: {m}" for m in (claude_issues or [])]
                issues += [f"Gemini: {m}" for m in (gemini_issues or [])]
                if len(judges) > 1 and not issues:
                    judged_by = f"({'+'.join(judges)}一致)"
        else:
            lines.append(f"⏭ SKIP(APIキー未設定): {label}")
            history_items.append(
                {"name": item.get("name"), "url": item.get("source_url"),
                 "method": "skip", "judges": [], "ok": None, "issues": []}
            )
            continue

        if issues:
            failed += 1
            lines.append(f"❌ NG: {label}")
            lines.extend(f"   - {msg}" for msg in issues)
        else:
            lines.append(f"✅ OK{judged_by}: {label}")
        if recheck_note:
            lines.append(f"   ℹ {recheck_note}")
        if amount_note and item.get("max_amount") in (None, "", "要確認"):
            lines.append(
                f"   ℹ 追加候補: 原文に上限額の記載あり「{amount_note[:80]}」"
                "(掲載は要確認のまま。人の原文確認後に追記)"
            )

        record = {
            "name": item.get("name"), "url": item.get("source_url"),
            "method": method, "judges": judges or (["api"] if is_jgrants else []),
            "ok": not issues, "issues": issues,
        }
        if recheck_note:
            record["recheck"] = recheck_note
        if amount_note and item.get("max_amount") in (None, "", "要確認"):
            record["amount_in_source"] = amount_note
        if issues:
            record["human_verdict"] = None  # 人が後から false_positive / true_mismatch を記入
        history_items.append(record)

    lines.append("")
    lines.append(f"結果: NG {failed}件 / 照合 {len(sample)}件")
    if gemini_key:
        lines.append(f"Gemini参加: {gemini_joined}/{gemini_eligible}件(AI照合対象)")
        if gemini_eligible > 0 and gemini_joined == 0:
            lines.append("⚠ GeminiがAI照合に1件も参加できていません(APIキー・無料枠・障害を確認)")
    report = "\n".join(lines)
    print(report)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(report)

    append_history(
        {
            "date": today,
            "sample": len(sample),
            "ng": failed,
            "gemini": {"enabled": bool(gemini_key), "eligible": gemini_eligible, "joined": gemini_joined},
            "items": history_items,
        }
    )

    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
