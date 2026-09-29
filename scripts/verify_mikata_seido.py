#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
沖縄企業のミカタ IG自動化 Task 14: 制度データの原文照合(Claude + Gemini ダブルチェック)。

data/subsidies.json の各制度について出典(source_url)を取得し、Claude と Gemini に
それぞれ独立に「締切・上限額・対象地域・補助金かどうか」を抽出させ、
掲載データと突き合わせた結果を各制度の `verified` フィールドへ書き込む。

判定の意味(generate_ig_posts_mikata.py の _verified_ng が読む):
  claude_verified / gemini_verified
      True  … そのAIの抽出が掲載データと矛盾しない(比較できた項目がすべて一致)
      False … 掲載データと食い違う、または両AIの抽出が割れた(conflict)
      None  … 判定できない(取得失敗・API失敗・比較できる項目なし・ダブルチェック未完)
  conflict
      True  … Claude と Gemini の抽出が食い違った。自動修正はしない。人が原文を確認する
              (CLAUDE.md マルチAI連携: AI同士の一致は断定の必要条件であって十分条件ではない)

設計上の約束:
  - ダブルチェック必須なのは優先1(ig_priority<=5 かつ 上限額>=1億円 かつ 残り30日以上)。
    それ以外は Claude 単独。GEMINI_API_KEY 未設定なら全件 Claude 単独(エラーにしない)
  - 優先1で Gemini が失敗したら、Claude の「一致(True)」は None へ下げる(片方だけでは
    断定しない)。Claude の「不一致(False)」はそのまま残す(検知した誤りを隠さない)
  - 掲載値が None/「要確認」の項目は「未掲載」であって矛盾ではない(議事_20260817)
  - 取得できなかったことと内容が違うことは分ける。403(遮断)と404(消滅)は
    HTTPステータスまで記録する(CLAUDE.md 再発防止メモ 2026-09-20)
  - 403/404 は再試行しない(恒久的)。タイムアウト・5xx は最大2回再試行
  - 前回の照合から30日を超えた制度は監査ログに「要再確認」として出す

使い方:
  python scripts/verify_mikata_seido.py                 # 全件照合して subsidies.json を更新
  python scripts/verify_mikata_seido.py --only-ig       # IG候補(ig_priority あり)だけ
  python scripts/verify_mikata_seido.py --limit 5 --dry-run   # 書き込まずに試す
  python scripts/verify_mikata_seido.py --stale-report  # 通信せず、古い照合の一覧だけ出す

環境変数:
  ANTHROPIC_API_KEY(または CLAUDE_API_KEY)… 必須。未設定なら照合せず終了(データは書き換えない)
  GEMINI_API_KEY … 任意。あれば優先1をダブルチェック
  VERIFY_MIKATA_CLAUDE_MODEL … Claude のモデル(既定 claude-opus-5-5)
"""
import argparse
import datetime as dt
import json
import os
import re
import socket
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SCRIPTS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPTS)

# Gemini呼び出し・HTML整形・jGrants日時変換は既存の原文照合と同じ実装を使う
# (モデル候補の自動追従などの改善を二重管理しないため)
from verify_sources import (  # noqa: E402
    JGRANTS_DETAIL,
    gemini_generate,
    jst_date,
    strip_html,
)

BASE = os.path.join(SCRIPTS, "..")
DATA_PATH = os.path.join(BASE, "data", "subsidies.json")
AUDIT_PATH = os.path.join(BASE, "data", "kpi", "verify_mikata_audit.jsonl")

CLAUDE_MODEL = os.environ.get("VERIFY_MIKATA_CLAUDE_MODEL", "claude-opus-5-5")
UA = "hojo-hq-verify-mikata/1.0 (+https://github.com/allgroup-inc/hojo-hq)"
PAGE_TEXT_LIMIT = 15000
MAX_RETRIES = 2            # タイムアウト・5xx のみ。403/404 は再試行しない
STALE_DAYS = 30            # 前回照合からこれ以上経ったら要再確認
PRIORITY1_MAX_RANK = 5     # ig_priority <= 5
PRIORITY1_MIN_AMOUNT = 100_000_000   # 1億円以上
PRIORITY1_MIN_DAYS = 30    # 残り30日以上(SNS投稿の対象層)
PREFS_RE = re.compile(r"(北海道|東京都|大阪府|京都府|.{2,3}県)")

EXTRACT_FIELDS = ("deadline_date", "days_to_deadline", "max_amount_yen", "target_area", "is_free")

# Claude 構造化出力(output_config.format)用
CLAUDE_SCHEMA = {
    "type": "object",
    "properties": {
        "deadline_date": {"anyOf": [{"type": "string"}, {"type": "null"}],
                          "description": "申請締切日 YYYY-MM-DD。原文に明記がなければ null"},
        "days_to_deadline": {"anyOf": [{"type": "integer"}, {"type": "null"}],
                             "description": "今日から締切までの日数。不明なら null"},
        "max_amount_yen": {"anyOf": [{"type": "integer"}, {"type": "null"}],
                           "description": "1件あたり上限額(円の整数)。明記がなければ null"},
        "target_area": {"type": "string",
                        "description": "対象地域(都道府県名 または 全国)。不明なら空文字"},
        "is_free": {"type": "boolean",
                    "description": "補助金・助成金・無料支援なら true、利用者負担の有償サービスなら false"},
    },
    "required": list(EXTRACT_FIELDS),
    "additionalProperties": False,
}

# Gemini responseSchema(OpenAPI サブセット)用
GEMINI_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "deadline_date": {"type": "STRING", "nullable": True},
        "days_to_deadline": {"type": "INTEGER", "nullable": True},
        "max_amount_yen": {"type": "INTEGER", "nullable": True},
        "target_area": {"type": "STRING"},
        "is_free": {"type": "BOOLEAN"},
    },
    "required": list(EXTRACT_FIELDS),
}


# ---------------------------------------------------------------- 時刻・分類

def now_utc():
    return dt.datetime.now(dt.timezone.utc)


def iso_utc(t):
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_date(s):
    try:
        return dt.date.fromisoformat(str(s)[:10])
    except (TypeError, ValueError):
        return None


def listed_amount(subsidy):
    """掲載上限額。実データは max_amount、計画書は max_amount_yen と呼ぶので両方読む。"""
    v = subsidy.get("max_amount_yen", subsidy.get("max_amount"))
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return int(v)
    if isinstance(v, str) and v.strip().isdigit():
        return int(v.strip())
    return None  # None・「要確認」など = 未掲載


def is_priority_1(subsidy, today=None):
    """ダブルチェック必須の優先1か(ig_priority<=5 かつ 1億円以上 かつ 残り30日以上)。"""
    today = today or now_utc().date()
    pri = subsidy.get("ig_priority")
    if not isinstance(pri, int) or isinstance(pri, bool) or not 1 <= pri <= PRIORITY1_MAX_RANK:
        return False
    amount = listed_amount(subsidy)
    if amount is None or amount < PRIORITY1_MIN_AMOUNT:
        return False
    days = subsidy.get("days_to_deadline")
    if not isinstance(days, int):
        d = parse_date(subsidy.get("deadline"))
        days = (d - today).days if d else None
    return days is not None and days >= PRIORITY1_MIN_DAYS


def stale_info(subsidy, now=None):
    """前回照合の経過日数。未照合なら None、古ければ (日数, True)。"""
    v = subsidy.get("verified")
    if not isinstance(v, dict) or not v.get("timestamp"):
        return None
    try:
        t = dt.datetime.strptime(v["timestamp"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)
    except ValueError:
        return None
    age = ((now or now_utc()) - t).days
    return age, age > STALE_DAYS


# ---------------------------------------------------------------- 取得

class FetchError(Exception):
    """取得失敗。error_msg は監査ログにそのまま出す('HTTPError 403' など)。"""

    def __init__(self, error_msg, status=None):
        super().__init__(error_msg)
        self.error_msg = error_msg
        self.status = status


def _http_get(url, timeout):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as res:
        return res.read()


def robots_allows(url, timeout=10, getter=_http_get):
    """robots.txt が明示的に禁止していなければ True。
    robots.txt が取れない(403含む)ときは許可扱い(brief の fallback)。
    ※ urllib.robotparser は 403 を『全面禁止』と解釈するため使わない。プロキシの403を
      robots禁止と誤記録すると、遮断(取得失敗)と規約上の不可を取り違える。"""
    from urllib.robotparser import RobotFileParser
    p = urllib.parse.urlsplit(url)
    robots_url = f"{p.scheme}://{p.netloc}/robots.txt"
    try:
        body = getter(robots_url, timeout).decode("utf-8", errors="replace")
    except Exception:
        return True
    rp = RobotFileParser()
    rp.parse(body.splitlines())
    return rp.can_fetch(UA, url)


def fetch_with_retry(url, timeout=30, getter=_http_get, sleep=time.sleep):
    """本文を取得。403/404 など 4xx は即失敗、タイムアウト・5xx は最大 MAX_RETRIES 回再試行。"""
    last = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            return getter(url, timeout)
        except urllib.error.HTTPError as e:
            last = FetchError(f"HTTPError {e.code}", e.code)
            if e.code < 500:
                raise last
        except (socket.timeout, TimeoutError):
            last = FetchError(f"Timeout after {timeout}s")
        except urllib.error.URLError as e:
            if isinstance(e.reason, (socket.timeout, TimeoutError)):
                last = FetchError(f"Timeout after {timeout}s")
            elif "Tunnel connection failed" in str(e.reason):
                # 実行環境のプロキシが拒否(サイト側の403とは別物。掲載の誤りの証拠ではない)
                raise FetchError(f"ProxyBlocked ({e.reason})")
            else:
                raise FetchError(f"URLError {e.reason}")
        if attempt < MAX_RETRIES:
            sleep(2 ** attempt)
    raise last


def jgrants_id(url):
    m = re.search(r"jgrants-portal\.go\.jp/subsidy/([A-Za-z0-9]+)", url or "")
    return m.group(1) if m else None


def source_text(subsidy, timeout=30, getter=_http_get):
    """AIに渡す原文テキスト。jGrants のポータルはJS描画で本文が取れないため、
    同じ制度の公開APIの詳細を原文として使う(verify_sources.py と同じ出典)。"""
    url = subsidy.get("source_url")
    sid = jgrants_id(url)
    if sid:
        raw = fetch_with_retry(JGRANTS_DETAIL.format(sid=sid), timeout, getter)
        results = (json.loads(raw.decode("utf-8")).get("result") or [])
        if not results:
            raise FetchError("jGrants APIに該当IDなし(公募終了・取り下げの可能性)", 404)
        cur = results[0]
        return (
            f"制度名: {cur.get('title') or cur.get('name')}\n"
            f"受付終了(JST): {jst_date(cur.get('acceptance_end_datetime'))}"
            f"(原値 {cur.get('acceptance_end_datetime')})\n"
            f"補助上限額: {cur.get('subsidy_max_limit')}\n"
            f"対象地域: {cur.get('target_area_search')}\n"
            f"本文: {strip_html(cur.get('detail') or '', PAGE_TEXT_LIMIT)}"
        )
    if not robots_allows(url, getter=getter):
        raise FetchError("robots.txt disallow(取得せず)")
    html = fetch_with_retry(url, timeout, getter).decode("utf-8", errors="replace")
    return strip_html(html, PAGE_TEXT_LIMIT)


# ---------------------------------------------------------------- 抽出

def build_prompt(page_text, today):
    return (
        "Given the following source page content, extract the key subsidy information:\n"
        "- Deadline (days until application closes, or date YYYY-MM-DD)\n"
        "- Maximum funding amount (integer Yen, e.g., 4500000 for ¥450万円)\n"
        "- Target area (都道府県 or 全国)\n"
        "- Is this program free/subsidy? (true for 補助金/助成金, false if cost-based)\n\n"
        "Only report values explicitly written in the source. If a value is not written, "
        "use null (do not guess). Today's date is " + today.isoformat() + ".\n\n"
        "Format answer as JSON: {\n"
        '  "deadline_date": "YYYY-MM-DD" or null,\n'
        '  "days_to_deadline": <int> or null,\n'
        '  "max_amount_yen": <int> or null,\n'
        '  "target_area": "string",\n'
        '  "is_free": true|false\n'
        "}\n\n"
        "Source page:\n" + page_text
    )


def extract_with_claude(client, prompt):
    """Claude で抽出。失敗時は例外(呼び出し側で None 扱い)。
    拒否に備えてサーバー側フォールバック(fallbacks: "default")を付ける。"""
    response = client.beta.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=16000,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        output_config={
            "effort": "low",
            "format": {"type": "json_schema", "schema": CLAUDE_SCHEMA},
        },
        messages=[{"role": "user", "content": prompt}],
    )
    if response.stop_reason == "refusal":
        raise RuntimeError("Claude refusal")
    text = next(b.text for b in response.content if b.type == "text")
    return json.loads(text)


class GeminiClient:
    """GEMINI_API_KEY がある場合だけ作る薄いラッパー(テストでは差し替える)。"""

    def __init__(self, api_key):
        self.api_key = api_key

    def extract(self, prompt):
        return gemini_generate(prompt, GEMINI_SCHEMA, self.api_key)  # 失敗時 None


def extract_with_gemini(gemini_client, prompt):
    out = gemini_client.extract(prompt)
    if out is None:
        raise RuntimeError("Gemini call failed")
    return out


def normalize_extraction(e, today):
    """AIの出力を比較用に正規化。締切は日付に揃える(日数しかなければ今日から計算)。"""
    if not isinstance(e, dict):
        return None
    d = parse_date(e.get("deadline_date"))
    if d is None and isinstance(e.get("days_to_deadline"), int):
        d = today + dt.timedelta(days=e["days_to_deadline"])
    amount = e.get("max_amount_yen")
    if isinstance(amount, bool) or not isinstance(amount, (int, float)) or amount <= 0:
        amount = None
    return {
        "deadline": d.isoformat() if d else None,
        "amount": int(amount) if amount is not None else None,
        "area": norm_area(e.get("target_area")),
        "is_free": e.get("is_free") if isinstance(e.get("is_free"), bool) else None,
    }


def norm_area(s):
    s = (s or "").strip()
    if not s or s in ("要確認", "不明"):
        return None
    if "全国" in s:
        return "全国"
    m = PREFS_RE.search(s)
    return m.group(1) if m else s


# ---------------------------------------------------------------- 比較

def _eq(field, a, b):
    if field == "area":
        return a == b or a in b or b in a
    return a == b


def field_agreement(field, values):
    """値の出そろった(None以外の)ものが全部一致なら True、割れたら False、比べる相手がなければ None。"""
    present = [v for v in values if v is not None]
    if len(present) < 2:
        return None
    return all(_eq(field, present[0], v) for v in present[1:])


def verdict_vs_listing(listing, ext):
    """1つのAIの抽出が掲載データと矛盾しないか。比較できる項目がなければ None。
    掲載が未掲載(None)の項目は比較しない(未掲載は矛盾ではない)。"""
    if ext is None:
        return None
    results = [field_agreement(f, [listing[f], ext[f]]) for f in ("deadline", "amount", "area")]
    results = [r for r in results if r is not None]
    if not results:
        return None
    return all(results)


def listing_view(subsidy):
    d = parse_date(subsidy.get("deadline"))
    return {
        "deadline": d.isoformat() if d else None,
        "amount": listed_amount(subsidy),
        "area": norm_area(subsidy.get("target_area")),
    }


# ---------------------------------------------------------------- 本体

def _result(ts, claude=None, gemini=None, conflict=False, amount_match=None,
            deadline_match=None, reachable=True, error=None, **extra):
    details = {
        "amount_match": amount_match,
        "deadline_match": deadline_match,
        "source_reachable": reachable,
        "error_msg": error,
    }
    details.update(extra)
    return {
        "claude_verified": claude,
        "gemini_verified": gemini,
        "timestamp": ts,
        "conflict": conflict,
        "details": details,
    }


def verify_subsidy_dual_check(subsidy, claude_client, gemini_client=None, timeout=30,
                              getter=_http_get, today=None, now=None):
    """
    Verify subsidy via Claude + Gemini dual-check (multi-AI連携).

    Returns:
    {
        "claude_verified": bool | None,
        "gemini_verified": bool | None,
        "timestamp": str (ISO8601),
        "conflict": bool,
        "details": {
            "amount_match": bool | None,
            "deadline_match": bool | None,
            "source_reachable": bool,
            "error_msg": str | None,
            ... (area_match, dual_check, claude/gemini の抽出値, needs_manual_review 等)
        }
    }
    """
    now = now or now_utc()
    today = today or now.date()
    ts = iso_utc(now)
    dual_required = is_priority_1(subsidy, today)
    dual_mode = "required" if dual_required else "claude_only"
    if gemini_client is None:
        dual_mode += "(gemini_unavailable)" if dual_required else ""

    url = subsidy.get("source_url")
    if not url:
        return _result(ts, reachable=False, error="source_url なし", dual_check=dual_mode)

    try:
        page_text = source_text(subsidy, timeout, getter)
    except FetchError as e:
        return _result(ts, reachable=False, error=e.error_msg, http_status=e.status,
                       dual_check=dual_mode)
    except Exception as e:  # 想定外の失敗でも1件で全体を止めない
        return _result(ts, reachable=False, error=f"{type(e).__name__}: {e}",
                       dual_check=dual_mode)

    prompt = build_prompt(page_text, today)
    listing = listing_view(subsidy)
    errors = []

    claude_ext = None
    if claude_client is not None:
        try:
            claude_ext = normalize_extraction(extract_with_claude(claude_client, prompt), today)
        except Exception as e:
            errors.append(f"Claude: {type(e).__name__}: {e}")
    else:
        errors.append("Claude: client なし")

    gemini_ext = None
    if dual_required and gemini_client is not None:
        try:
            gemini_ext = normalize_extraction(extract_with_gemini(gemini_client, prompt), today)
        except Exception as e:
            errors.append(f"Gemini: {type(e).__name__}: {e}")

    claude_v = verdict_vs_listing(listing, claude_ext)
    gemini_v = verdict_vs_listing(listing, gemini_ext)

    exts = [x for x in (claude_ext, gemini_ext) if x is not None]
    match = {f: field_agreement(f, [listing[f]] + [x[f] for x in exts])
             for f in ("deadline", "amount", "area")}

    conflict = False
    conflict_fields = []
    if claude_ext is not None and gemini_ext is not None:
        for f in ("deadline", "amount", "area"):
            if field_agreement(f, [claude_ext[f], gemini_ext[f]]) is False:
                conflict_fields.append(f)
        if claude_v is not None and gemini_v is not None and claude_v != gemini_v:
            conflict_fields.append("verdict")
        conflict = bool(conflict_fields)
        if conflict:
            # AIが割れたら断定しない: 両方 False にして人の確認へ回す(自動修正しない)
            claude_v, gemini_v = False, False
    elif dual_required and gemini_client is not None and claude_v is True:
        # ダブルチェック必須なのに片方しか結果がない → 一致を断定しない
        claude_v = None
        dual_mode = "incomplete"
    elif dual_required and gemini_client is not None and claude_ext is None and gemini_v is True:
        gemini_v = None
        dual_mode = "incomplete"

    return _result(
        ts, claude=claude_v, gemini=gemini_v, conflict=conflict,
        amount_match=match["amount"], deadline_match=match["deadline"],
        reachable=True, error="; ".join(errors) or None,
        area_match=match["area"], dual_check=dual_mode,
        conflict_fields=conflict_fields, needs_manual_review=conflict or claude_v is False
        or gemini_v is False,
        claude_extracted=claude_ext, gemini_extracted=gemini_ext,
        free_status_warning=any(x.get("is_free") is False for x in exts),
    )


def audit_record(subsidy, result):
    d = result["details"]
    return {
        "ts": result["timestamp"],
        "subsidy_id": subsidy.get("id"),
        "name": (subsidy.get("name") or "")[:60],
        "source_url": subsidy.get("source_url"),
        "dual_check": d.get("dual_check"),
        "claude_result": result["claude_verified"],
        "gemini_result": result["gemini_verified"],
        "conflict": result["conflict"],
        "conflict_fields": d.get("conflict_fields", []),
        "source_reachable": d["source_reachable"],
        "http_status": d.get("http_status"),
        "error_msg": d["error_msg"],
    }


def make_claude_client():
    key = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("CLAUDE_API_KEY")
    if not key:
        return None
    import anthropic
    return anthropic.Anthropic(api_key=key)


def run(items, claude_client, gemini_client, timeout=30, today=None, now=None,
        getter=_http_get, log=print):
    """items を順に照合し、各 item['verified'] を更新。監査レコードの一覧を返す。"""
    now = now or now_utc()
    records = []
    for s in items:
        st = stale_info(s, now)
        if st and st[1]:
            log(f"[stale] 前回照合から{st[0]}日: {s.get('id')} {s.get('name', '')[:30]}(要再確認)")
        result = verify_subsidy_dual_check(s, claude_client, gemini_client, timeout,
                                           getter=getter, today=today, now=now)
        s["verified"] = result
        rec = audit_record(s, result)
        records.append(rec)
        mark = ("CONFLICT" if rec["conflict"] else
                "NG" if False in (rec["claude_result"], rec["gemini_result"]) else
                "UNREACHABLE" if not rec["source_reachable"] else
                "OK" if rec["claude_result"] else "UNKNOWN")
        log(f"[{mark}] {rec['subsidy_id']} claude={rec['claude_result']} "
            f"gemini={rec['gemini_result']} {rec['error_msg'] or ''}".rstrip())
    return records


def summarize(records):
    c = {"total": len(records), "ok": 0, "ng": 0, "conflict": 0, "unreachable": 0, "unknown": 0,
         "dual_checked": 0}
    for r in records:
        if r["gemini_result"] is not None:
            c["dual_checked"] += 1
        if r["conflict"]:
            c["conflict"] += 1
        elif not r["source_reachable"]:
            c["unreachable"] += 1
        elif False in (r["claude_result"], r["gemini_result"]):
            c["ng"] += 1
        elif r["claude_result"] is True:
            c["ok"] += 1
        else:
            c["unknown"] += 1
    return c


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--data", default=DATA_PATH)
    ap.add_argument("--audit-log", default=AUDIT_PATH)
    ap.add_argument("--only-ig", action="store_true", help="ig_priority のある制度だけ照合")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--timeout", type=int, default=30)
    ap.add_argument("--dry-run", action="store_true", help="subsidies.json を書き換えない")
    ap.add_argument("--stale-report", action="store_true", help="通信せず古い照合だけ一覧")
    args = ap.parse_args(argv)

    with open(args.data, encoding="utf-8") as f:
        payload = json.load(f)
    items = payload["items"] if isinstance(payload, dict) else payload

    if args.stale_report:
        n = 0
        for s in items:
            st = stale_info(s)
            if st is None:
                print(f"[unverified] {s.get('id')} {s.get('name', '')[:30]}")
            elif st[1]:
                n += 1
                print(f"[stale] {st[0]}日前: {s.get('id')} {s.get('name', '')[:30]}")
        print(f"要再確認(>{STALE_DAYS}日): {n}件")
        return 0

    targets = [s for s in items if s.get("source_url")]
    if args.only_ig:
        targets = [s for s in targets if s.get("ig_priority") is not None]
    if args.limit:
        targets = targets[: args.limit]

    claude_client = make_claude_client()
    if claude_client is None:
        print("[error] ANTHROPIC_API_KEY(CLAUDE_API_KEY)未設定: 照合できないため中止"
              "(subsidies.json は書き換えていません)")
        return 2
    gemini_key = os.environ.get("GEMINI_API_KEY") or ""
    gemini_client = GeminiClient(gemini_key) if gemini_key else None
    if gemini_client is None:
        print("[info] Gemini verification skipped (GEMINI_API_KEY not set): 全件 Claude 単独照合")

    records = run(targets, claude_client, gemini_client, args.timeout)
    c = summarize(records)
    print(f"結果: 照合{c['total']}件 / OK {c['ok']} / NG {c['ng']} / 矛盾(要人確認) {c['conflict']}"
          f" / 取得不可 {c['unreachable']} / 判定不能 {c['unknown']} / ダブルチェック {c['dual_checked']}")

    if args.audit_log:
        os.makedirs(os.path.dirname(os.path.abspath(args.audit_log)), exist_ok=True)
        with open(args.audit_log, "a", encoding="utf-8") as f:
            for r in records:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
    if not args.dry_run:
        with open(args.data, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=1)
        print(f"[ok] verified を書き込みました → {args.data}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
