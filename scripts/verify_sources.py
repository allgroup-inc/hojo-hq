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

- 結果の状態(2026-11-27): 鍵の失効(401)を「不一致」と報告し、国のAPIだけの日の成功で
  「解消」と閉じていた反省から、制度ごと・回ごと・AIごとに状態を分ける(下の「結果の状態」)。
  未解決の掲載とAIの障害は data/kpi/verify_open.json に持ち越し、原因ごとに復旧を確かめる。

レポートは verify_report.txt、Issue 用の要約は verify_status.json に書き出す。
その回が ok / ok_api_only 以外なら exit 1(処理そのものの異常は exit 2)。
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
try:  # 既定5件。再照合のときは環境変数で増やす。不正な値でも落ちない(落ちると履歴が残らない)
    SAMPLE_SIZE = max(1, int(os.getenv("VERIFY_SAMPLE_SIZE") or "5"))
except ValueError:
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


def redact(msg: str) -> str:
    """エラー文から鍵らしき部分を消す(Gemini はURLのクエリに鍵を載せるため。ログ・Issue・履歴に残さない)。"""
    msg = re.sub(r"(?i)(key=)[^&\s'\"]+", r"\1***", msg)
    return re.sub(r"\b(sk-ant-[A-Za-z0-9_-]{6})[A-Za-z0-9_-]+", r"\1***", msg)[:300]


def classify_error(e: Exception) -> str:
    """AIの呼び出しの失敗を、認証(auth)・利用上限(quota)・それ以外(error)に分ける。
    認証の失敗は「掲載データの誤り」ではないので、不一致としては扱わない(2026-11-27)。"""
    code = getattr(e, "status_code", None) or getattr(e, "code", None)
    name = type(e).__name__
    body = ""
    if isinstance(e, urllib.error.HTTPError):
        try:
            body = e.read().decode("utf-8", errors="replace")[:2000]
        except Exception:
            body = ""
    if code in (401, 403) or name in ("AuthenticationError", "PermissionDeniedError") \
            or "API_KEY_INVALID" in body or "API key not valid" in body:
        return "auth"
    if code == 429 or name == "RateLimitError" or "RESOURCE_EXHAUSTED" in body:
        return "quota"
    return "error"


def strip_html(html: str, limit: int = 12000) -> str:
    html = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", html)
    text = re.sub(r"(?s)<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text)
    return text[:limit]


JGRANTS_FETCH_FAILED = "jGrants APIの再取得に失敗"


def verify_jgrants(item: dict) -> list[str]:
    """jGrants APIの現在値と厳密照合。差異のリストを返す(空=OK)。
    取得そのものの失敗は JGRANTS_FETCH_FAILED で始まる1件を返す(内容の不一致とは別に扱う)。"""
    issues: list[str] = []
    try:
        data = json.loads(fetch(JGRANTS_DETAIL.format(sid=item["id"])).decode("utf-8"))
    except Exception as e:
        return [f"{JGRANTS_FETCH_FAILED}: {redact(str(e))}"]

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


GEMINI_LAST_ERROR = {"kind": None}  # 直近の Gemini 呼び出しの失敗の種類(auth/quota/error)


def gemini_generate(prompt: str, schema: dict, api_key: str) -> dict | None:
    """Gemini APIで構造化出力を得る汎用ヘルパー。API障害時はNone(種類は GEMINI_LAST_ERROR)。"""
    GEMINI_LAST_ERROR["kind"] = None
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
    GEMINI_LAST_ERROR["kind"] = classify_error(last_error) if last_error else "error"
    print(f"[info] Gemini呼び出しに失敗({GEMINI_LAST_ERROR['kind']}): {redact(str(last_error))}")
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
        print(f"[info] Claude再確認に失敗(指摘を維持): {redact(str(e))}")
        return None


def recheck_with_gemini(item: dict, page_text: str, issues: list[str], api_key: str) -> dict | None:
    """Geminiの指摘を本人に再確認させる。API障害時はNone(=指摘維持)。"""
    return gemini_generate(
        build_recheck_prompt(item, page_text, issues), GEMINI_RECHECK_SCHEMA, api_key
    )



# ── 結果の状態(2026-11-27)────────────────────────────────────────────
# 11/5〜11/26、Claude の鍵が無効(401)で照合が11回失敗した。失敗は
# 「掲載データと原文に不一致」という題の Issue になり、国のAPIだけの日に成功すると
# 「不一致が解消しました」と自動で閉じた。失敗した日は照合履歴にも残らなかった。
# そこで、結果を状態で分け、原因ごとに復旧の条件を持たせる。
#   制度ごと: ok / partial(片方のAIだけで確認) / mismatch(原文と食い違う)
#             / fetch_error(出典・APIを開けない) / ai_unavailable(AIで確かめられない)
#   その回:   ok / ok_api_only(国のAPIだけの回) / mismatch / degraded(AI照合が欠けている)
#             / fetch_error
#   AIごと:   ok / auth(認証) / quota(利用上限) / error / unconfigured(鍵なし)
#             / not_exercised(その回はAIの出番が無かった=前回の状態を引き継ぐ)
STATE_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "kpi", "verify_open.json")
STATUS_PATH = os.path.join(os.path.dirname(__file__), "..", "verify_status.json")
JUDGES = ("Claude", "Gemini")
PROCESS = "照合処理"  # 想定外のエラー(掲載の問題ではない)を、障害として持ち越すときの名前
RECHECK_MAX = 10  # 未解決の制度を、毎回いっしょに照合し直す上限
OK_RUN = ("ok", "ok_api_only")
JUDGE_LABEL = {"ok": "正常", "auth": "認証エラー(鍵の失効・誤り)", "quota": "利用上限",
               "error": "応答の異常", "unconfigured": "鍵が未登録", "not_exercised": "出番なし"}


def label_of(j: str, st: str) -> str:
    if j == PROCESS:
        return "想定外のエラー(掲載の問題ではない)" if st == "error" else "正常"
    if j == "Gemini" and st == "unconfigured":
        return "鍵が未登録(Claude 単独で照合)"
    return JUDGE_LABEL.get(st, st)


def close_text(state: dict) -> str:
    """障害の Issue を閉じるときの文。いまの状態から作る(実態と違うことを書かない)。"""
    parts = [f"{j} {label_of(j, v['state'])}" for j, v in sorted(state.get("judges", {}).items())]
    return "✅ 照合の障害が解消しました(いまの状態: " + " / ".join(parts) + ")。自動で閉じます。"


def is_ai_item(item: dict) -> bool:
    return "jgrants-portal" not in (item.get("source_url") or "")


def pick_sample(items: list[dict], today: str, size: int) -> list[dict]:
    """日付で決まる無作為抽出。AIで照合する制度(国のAPI以外)があれば、必ず1件は含める。
    含めないと、国のAPIだけの日はAIの鍵が切れていても気づけない(11/5〜の実例)。"""
    rng = random.Random(today)
    sample = rng.sample(items, min(size, len(items)))
    others = [x for x in items if is_ai_item(x)]
    if sample and others and not any(is_ai_item(x) for x in sample):
        sample[-1] = rng.choice(others)
    return sample


def judge_one(name: str, call):
    """AIを1回呼ぶ。(issues, amount, 状態) を返す。状態は ok/auth/quota/error。"""
    try:
        if name == "Claude":
            issues, amount = call()
            return issues, amount, "ok"
        got = call()
        if got is None:
            return None, "", GEMINI_LAST_ERROR["kind"] or "error"
        issues, amount = got
        return issues, amount, "ok"
    except Exception as e:  # 認証・上限・応答の崩れ(JSONでない等)
        print(f"[info] {name}照合に失敗: {redact(str(e))}")
        return None, "", classify_error(e)


def verify_item(item: dict, client, gemini_key: str) -> dict:
    """制度1件を照合し、状態つきの記録を返す。"""
    rec = {"name": item.get("name"), "url": item.get("source_url"), "id": item.get("id"),
           "method": "ai" if is_ai_item(item) else "jgrants", "judges": [],
           "judge_status": {}, "issues": [], "notes": []}
    if not is_ai_item(item):
        issues = verify_jgrants(item)
        if issues and issues[0].startswith(JGRANTS_FETCH_FAILED):
            rec.update(status="fetch_error", issues=issues)
        else:
            rec.update(status="mismatch" if issues else "ok", issues=issues, judges=["api"])
        return rec

    configured = {"Claude": client is not None, "Gemini": bool(gemini_key)}
    for j in JUDGES:
        if not configured[j]:
            rec["judge_status"][j] = "unconfigured"
    if not any(configured.values()):
        rec["status"] = "ai_unavailable"
        return rec
    try:
        html = fetch(item["source_url"]).decode("utf-8", errors="replace")
    except Exception as e:
        rec.update(status="fetch_error",
                   issues=[f"出典URLの取得に失敗: {redact(str(e))}(内容の誤りとは限らない)"])
        return rec
    page_text = strip_html(html)

    results: dict[str, list[str] | None] = {}
    amount_note = ""
    if configured["Claude"]:
        iss, a, st = judge_one("Claude", lambda: verify_local_with_claude(item, page_text, client))
        rec["judge_status"]["Claude"] = st
        results["Claude"] = iss
        amount_note = amount_note or a
    if configured["Gemini"]:
        iss, a, st = judge_one("Gemini", lambda: verify_local_with_gemini(item, page_text, gemini_key))
        rec["judge_status"]["Gemini"] = st
        results["Gemini"] = iss
        amount_note = amount_note or a

    # 判定が割れたときだけセカンドパス(指摘した側に根拠の引用を要求。撤回は履歴に残す)
    c, g = results.get("Claude"), results.get("Gemini")
    if c is not None and g is not None:
        if c and not g:
            r = recheck_with_claude(item, page_text, c, client)
            if r and not r["upheld"]:
                rec["notes"].append(f"Claudeが再確認で指摘を撤回: {r['reason']}")
                results["Claude"] = []
            elif r and r.get("evidence_quote"):
                c.append(f"根拠引用: {r['evidence_quote'][:200]}")
        elif g and not c:
            r = recheck_with_gemini(item, page_text, g, gemini_key)
            if r and not r["upheld"]:
                rec["notes"].append(f"Geminiが再確認で指摘を撤回: {r['reason']}")
                results["Gemini"] = []
            elif r and r.get("evidence_quote"):
                g.append(f"根拠引用: {r['evidence_quote'][:200]}")

    done = [j for j in JUDGES if results.get(j) is not None]
    rec["judges"] = done
    rec["issues"] = [f"{j}: {m}" for j in done for m in results[j]]
    if rec["issues"]:
        rec["status"] = "mismatch"
    elif not done:
        rec["status"] = "ai_unavailable"
    elif len(done) < sum(configured.values()):
        rec["status"] = "partial"  # 鍵のあるAIの一部だけで確認(二重照合になっていない)
    else:
        rec["status"] = "ok"
    if amount_note and item.get("max_amount") in (None, "", "要確認"):
        rec["amount_in_source"] = amount_note
    return rec


def safe_verify(item: dict, client, gemini_key: str) -> dict:
    """制度1件の想定外の失敗で、回全体を止めない(止まると履歴が残らない)。"""
    try:
        return verify_item(item, client, gemini_key)
    except Exception as e:
        return {"name": item.get("name"), "url": item.get("source_url"), "id": item.get("id"),
                "method": "ai" if is_ai_item(item) else "jgrants", "judges": [], "judge_status": {},
                "issues": [f"照合中に想定外のエラー: {type(e).__name__}: {redact(str(e))}"],
                "notes": [], "status": "error"}  # 掲載の問題ではなく、照合処理の不具合


def run_judge_state(records: list[dict], j: str, configured: bool) -> str:
    """その回の、AIごとの状態。成功が1件でもあれば ok、認証の失敗が1件でもあれば auth。"""
    if not configured:
        return "unconfigured"
    seen = [r["judge_status"].get(j) for r in records if j in r["judge_status"]]
    for k in ("auth", "quota", "error"):  # 一部でも失敗した回は、その原因を障害として残す
        if k in seen:
            return k
    return "ok" if "ok" in seen else "not_exercised"


def key_of(x: dict) -> str:
    """未解決の制度を見分ける鍵。出典URLを直しても同じ制度として扱うため、id を優先する。"""
    return str(x.get("id") or x.get("source_url") or x.get("url"))


def update_state(prev: dict, records: list[dict], judge_now: dict, items_by_key: dict,
                 today: str) -> tuple[dict, dict]:
    """未解決の状態を更新する。(新しい状態, 変化) を返す。
    - 内容(不一致・出典を開けない): 同じ制度を照合し直して ok になるか、掲載が終わったら解決
    - AIの障害: そのAIが実際に照合できたら解決。出番が無かった回は前の状態のまま"""
    open_items = {o.get("key") or o["url"]: o for o in prev.get("open_items", [])}
    new_items, resolved = [], []
    for r in records:
        k = key_of(r)
        if r["status"] in ("mismatch", "fetch_error"):
            if k not in open_items:
                new_items.append(k)
            o = open_items.get(k, {"key": k, "name": r["name"], "since": today})
            o.update(url=r["url"], status=r["status"], last=today, issues=r["issues"][:5])
            open_items[k] = o
        elif k in open_items and r["status"] == "ok":
            resolved.append(k)
            open_items.pop(k)
    for k in list(open_items):
        if k not in items_by_key:  # 掲載が終わった制度
            resolved.append(k)
            open_items.pop(k)

    judges = dict(prev.get("judges", {}))
    judge_changed = []
    for j, st in judge_now.items():
        if st == "not_exercised":
            continue
        before = (judges.get(j) or {}).get("state")
        if before != st:
            judge_changed.append(j)
            judges[j] = {"state": st, "since": today}
    state = {"open_items": sorted(open_items.values(), key=lambda o: o["since"]),
             "judges": judges, "updated": today}
    return state, {"new_items": new_items, "resolved": resolved, "judge_changed": judge_changed}


def outage_of(state: dict) -> dict:
    """障害として知らせるもの。Claude が主で、Gemini は鍵がある間だけ二重照合に加わる設計
    (議事 2026-08-06)なので、鍵の未登録を障害にしないのは Gemini だけ。Claude の未登録は障害。"""
    judges = state.get("judges", {})
    return {j: v for j, v in judges.items()
            if v.get("state") != "ok" and not (j == "Gemini" and v.get("state") == "unconfigured")}


def run_status(records: list[dict], state: dict) -> str:
    st = {r["status"] for r in records}
    if "mismatch" in st or any(o["status"] == "mismatch" for o in state.get("open_items", [])):
        return "mismatch"
    if st & {"ai_unavailable", "partial", "error"} or outage_of(state):
        return "degraded"
    if "fetch_error" in st or state.get("open_items"):
        return "fetch_error"
    return "ok" if any(r["method"] == "ai" for r in records) else "ok_api_only"


def render_report(today: str, records: list[dict], state: dict, status: str) -> str:
    mark = {"ok": "✅ OK", "partial": "🟡 片方のAIだけで確認", "mismatch": "❌ 不一致",
            "error": "🛠 照合処理の不具合",
            "fetch_error": "⚠ 開けない", "ai_unavailable": "⏸ AIで確認できず"}
    lines = [f"原文照合レポート {today}(照合 {len(records)}件・結果: {status})", ""]
    for r in records:
        lines.append(f"{mark[r['status']]}: {(r['name'] or '')[:40]} [{r['url']}]")
        lines.extend(f"   - {m}" for m in r["issues"])
        lines.extend(f"   ℹ {m}" for m in r["notes"])
        if r.get("amount_in_source"):
            lines.append(f"   ℹ 追加候補: 原文に上限額の記載あり「{r['amount_in_source'][:80]}」"
                         "(掲載は要確認のまま。人の原文確認後に追記)")
    lines.append("")
    for j, v in sorted(state.get("judges", {}).items()):
        lines.append(f"{j}: {label_of(j, v['state'])}({v['since']}から)")
    if state.get("open_items"):
        lines.append(f"未解決の掲載: {len(state['open_items'])}件(照合し直して解消を確かめるまで残す)")
    return "\n".join(lines)


def issue_texts(state: dict) -> tuple[str, str]:
    """(内容のIssue本文, AI障害のIssue本文)。空なら開いているものを閉じる合図。"""
    content = ""
    if state.get("open_items"):
        rows = ["原文照合で、確かめが必要な掲載があります(締切・金額は原文どおりが絶対ルール)。",
                "照合し直して問題が無くなるか、掲載が終わった制度から自動で外れます。", "",
                "| 状態 | 制度 | いつから | 内容 |", "|---|---|---|---|"]
        for o in state["open_items"]:
            kind = "原文と食い違う" if o["status"] == "mismatch" else "出典を開けない(誤りとは限らない)"
            detail = " / ".join(o.get("issues", []))[:200].replace("|", "/")
            rows.append(f"| {kind} | [{(o['name'] or '')[:30]}]({o['url']}) | {o['since']} | {detail} |")
        content = "\n".join(rows)
    out = outage_of(state)
    outage = ""
    if out:
        rows = ["**AIによる照合が実施できていません。掲載データの誤りではありません。**",
                "国のAPIでの照合と情報の収集は続いています。AIで照合する制度は、確かめられないまま残ります"
                "(照合済みには上げません)。", "", "| AI | 状態 | いつから |", "|---|---|---|"]
        rows += [f"| {j} | {label_of(j, v['state'])} | {v['since']} |" for j, v in sorted(out.items())]
        rows += ["", "直し方: 鍵の失効・未登録なら、代表が鍵を発行し直して Secrets に登録する"
                 "(値はチャット・Issue・ログに書かない)。そのAIが次に照合できた回に自動で閉じます。"]
        outage = "\n".join(rows)
    return content, outage


def load_json(path: str, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def write_json(path: str, data) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
        f.write("\n")


def history_item(r: dict) -> dict:
    h = {"name": r["name"], "url": r["url"], "method": r["method"], "status": r["status"],
         "judges": r["judges"], "ok": r["status"] in ("ok", "partial"), "issues": r["issues"]}
    if r["judge_status"]:
        h["judge_status"] = r["judge_status"]
    if r.get("recheck"):
        h["rechecked"] = True  # 未解決の制度を照合し直した分(抽出した5件とは別に数える)
    if r["notes"]:
        h["recheck"] = " / ".join(r["notes"])  # 従来どおり: AIが再確認で指摘を撤回したメモ
    if r.get("amount_in_source"):
        h["amount_in_source"] = r["amount_in_source"]
    if r["status"] == "mismatch" and (not r.get("recheck") or r.get("first_mismatch")):
        h["human_verdict"] = None  # 人が後から false_positive / true_mismatch を記入
    return h


def run(items: list[dict], today: str, client, gemini_key: str, prev_state: dict,
        size: int = SAMPLE_SIZE) -> dict:
    """照合の本体(外部との出入りは引数の client / fetch に限る。テストから呼べる)。"""
    items_by_key = {key_of(x): x for x in items}
    sample = pick_sample(items, today, size)
    keys = {key_of(x) for x in sample}
    open_keys = [o.get("key") or o["url"] for o in prev_state.get("open_items", [])]
    recheck = [items_by_key[k] for k in open_keys if k in items_by_key and k not in keys][:RECHECK_MAX]
    records = [safe_verify(x, client, gemini_key) for x in sample + recheck]
    prev_status = {o.get("key") or o["url"]: o.get("status") for o in prev_state.get("open_items", [])}
    for r, x in zip(records, sample + recheck):
        r["recheck"] = x in recheck
        # その制度で初めての不一致(前は「開けない」等)なら、照合し直した回でも人の判定の対象にする
        r["first_mismatch"] = r["status"] == "mismatch" and prev_status.get(key_of(r)) != "mismatch"
    judge_now = {j: run_judge_state(records, j, c) for j, c in
                 (("Claude", client is not None), ("Gemini", bool(gemini_key)))}
    # 照合処理そのものの不具合も、障害として同じ仕組みで持ち越す(掲載の問題にしない)
    judge_now[PROCESS] = "error" if any(r["status"] == "error" for r in records) else "ok"
    state, changes = update_state(prev_state, records, judge_now, items_by_key, today)
    status = run_status(records, state)
    content, outage = issue_texts(state)
    entry = {
        "date": today, "status": status, "sample": len(sample), "recheck": len(recheck),
        "ng": sum(r["status"] == "mismatch" and not r["recheck"] for r in records),
        "ng_recheck": sum(r["status"] == "mismatch" and r["recheck"] for r in records),
        "judge_state": judge_now,
        "gemini": {"enabled": bool(gemini_key),
                   "eligible": sum("Gemini" in r["judge_status"] and r["judge_status"]["Gemini"] != "unconfigured"
                                   for r in records),
                   "joined": sum(r["judge_status"].get("Gemini") == "ok" for r in records)},
        "items": [history_item(r) for r in records],
    }
    return {"status": status, "records": records, "state": state, "changes": changes,
            "close_text": close_text(state),
            "history": entry, "report": render_report(today, records, state, status),
            "content_issue": content, "outage_issue": outage}


def append_history(entry: dict) -> None:
    """日次の照合結果を data/kpi/verify_history.json へ追記。同日再実行は上書き(べき等)。
    失敗・未実施の回も必ず残す(11/5〜11/26 は失敗した日が残らず、止まっている状態が見えなかった)。"""
    history = load_json(HISTORY_PATH, [])
    history = [h for h in history if h.get("date") != entry["date"]]
    history.append(entry)
    write_json(HISTORY_PATH, history)


def main() -> int:
    today = datetime.now(JST).strftime("%Y-%m-%d")
    try:
        with open(DATA_PATH, encoding="utf-8") as f:
            items = json.load(f)["items"]
        client = None
        if os.environ.get("ANTHROPIC_API_KEY"):
            import anthropic

            client = anthropic.Anthropic()
        gemini_key = os.environ.get("GEMINI_API_KEY") or ""
        prev = {}
        if os.path.exists(STATE_PATH):  # あるのに読めないなら止める(空として読むと未解決が消える)
            try:
                with open(STATE_PATH, encoding="utf-8") as f:
                    prev = json.load(f)
            except ValueError as e:
                raise RuntimeError(
                    f"未解決の状態ファイル(data/kpi/verify_open.json)が読めない: {e}。"
                    "直し方: そのファイルを前のコミットの版に戻す(git log -- data/kpi/verify_open.json)。"
                    "消すと未解決の掲載の記録も消えるので、消すのは中身を確かめてから") from None
        res = run(items, today, client, gemini_key, prev)
    except Exception as e:  # 処理そのものの異常終了。履歴と状態に残し、障害として知らせる
        msg = f"照合処理が異常終了: {type(e).__name__}: {redact(str(e))}"
        print(msg)
        append_history({"date": today, "status": "crash", "error": msg, "sample": 0, "recheck": 0,
                        "ng": 0, "ng_recheck": 0, "gemini": {}, "items": []})
        # 内容の Issue は触らない(content_issue なし)。障害の Issue には必ず載せる
        write_json(STATUS_PATH, {"status": "crash", "error": msg,
                                 "changes": {"judge_changed": ["crash"]},
                                 "outage_issue": "**照合処理が異常終了しました。掲載データの誤りではありません。**"
                                                 f"\n\n{msg}\n\n次の回で正常に終われば自動で閉じます。"})
        with open(REPORT_PATH, "w", encoding="utf-8") as f:
            f.write(msg)
        return 2
    print(res["report"])
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(res["report"])
    append_history(res["history"])
    write_json(STATE_PATH, res["state"])
    write_json(STATUS_PATH, {
        "status": res["status"], "changes": res["changes"],
        "content_issue": res["content_issue"], "outage_issue": res["outage_issue"],
        "outage_close_text": res["close_text"],
    })
    return 0 if res["status"] in OK_RUN else 1


if __name__ == "__main__":
    sys.exit(main())
