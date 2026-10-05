#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hojo-hq — 結果マガ GA4 クライアント(売上自動化 Task 2)

週単位で GA4 Data API(runReport)からセッション・PV・記事別CTR・新規/リピーター人数を取得し、
GA4Metrics にまとめる。出力は Task 4(collect_weekly_metrics.py)が
data/kekka_weekly_metrics.json の ga4 セクションへ追記する。

設計(捏造ゼロ):
- 数値はすべて GA4 応答の実値。値が整数でない・欠けている行は 0 で埋めず GA4APIError で止める
- CTR = 記事別 article_click 回数 / 同じ記事の page_view 回数(記事ID = イベントパラメータ article_id)
  - page_view があって click が無い記事 → CTR 0.0(実測のゼロ)
  - click があって page_view が 0 の記事 → 分母が無いので CTR を作らない(警告ログを出して除外。
    0 や 1.0 で埋めると事実でない数字になる。article_id が page_view に付いていないタグ設定漏れの兆候)
  - 1 を超える CTR(1PVで複数クリック)も丸めずそのまま返す
- 期間内にデータが1行も無い週は sessions=0 / pageviews=0(GA4 がゼロと答えた実値)。警告ログを出す
- 取得できなかった(ネットワーク/503)と内容が不正(スキーマ不一致)はエラー文で区別する
- 集計値のみ。個人識別子は扱わない。鍵・トークンはログに出さない

認証: 環境変数 GOOGLE_APPLICATION_CREDENTIALS(サービスアカウント鍵 JSON ファイルのパス)。
  ファイルが無い/読めない/JSONでない場合は API を叩く前に GA4APIError。
  トークン取得は google-auth(pip install google-auth。scripts/ga4_client.py と同じ依存)。
  既存 Secrets GA4_SA_JSON を使う場合は、ワークフロー側で一時ファイルへ書き出してこの変数に渡す。

接続先: https://analyticsdata.googleapis.com/v1beta/properties/{property_id}:runReport

プロパティ側の前提: カスタムディメンション(イベントスコープ・パラメータ名 article_id)が
  登録済みであること。未登録だと GA4 が HTTP 400 を返し、その旨の GA4APIError になる。
  登録日より前のイベントには article_id が付かない((not set) として除外される)。

リトライ: HTTP 500 / 503 / タイムアウトのみ、最大3回(待機 5s → 10s → 15s。Task 1 と同じ値)。
3回リトライしても失敗したら GA4APIError。400/401/403/404/429 等は即座に GA4APIError。

週の指定: ISO週 "YYYY-Www"(例 "2026-W40")。月曜〜日曜。日付の区切りは GA4 プロパティのタイムゾーン。

取得するレポート(3回の runReport):
1. 合計: metrics sessions, screenPageViews(ディメンションなし)
2. 記事別: dimensions eventName × customEvent:article_id / metric eventCount
   (eventName が page_view または article_click のものだけ)
3. ユーザー区分: dimension newVsReturning / metric activeUsers → {"new": n, "returning": m}
   ※ 購買確度の4セグメント(高エンゲージメント等)ではない。それは Task 8 が個人単位で判定する
"""
import datetime as dt
import json
import logging
import os
import socket
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass

logger = logging.getLogger("ga4_api")

API_BASE = "https://analyticsdata.googleapis.com/v1beta"
SCOPES = ("https://www.googleapis.com/auth/analytics.readonly",)
CREDENTIALS_ENV = "GOOGLE_APPLICATION_CREDENTIALS"
REQUEST_TIMEOUT_SEC = 30
RETRY_DELAYS_SEC = (5, 10, 15)
RETRYABLE_STATUS = (500, 503)
PAGE_LIMIT = 10000

PAGE_VIEW_EVENT = "page_view"
CLICK_EVENT = "article_click"
ARTICLE_DIMENSION = "customEvent:article_id"
# GA4 がパラメータ無しのイベントに返す値。記事IDとして扱わない
UNSET_VALUES = ("", "(not set)")


class GA4APIError(Exception):
    """GA4 の取得失敗・認証失敗・応答不正をすべてこの例外で上げる(黙って成功扱いにしない)。"""


@dataclass
class GA4Metrics:
    week: str
    sessions: int
    pageviews: int
    ctr_by_article: dict[str, float]
    user_segment_counts: dict[str, int]

    def to_dict(self) -> dict:
        return asdict(self)


def week_range(week: str) -> tuple[dt.date, dt.date]:
    """ISO週 "YYYY-Www" → (月曜, 日曜)。"""
    try:
        year_s, w_s = week.split("-W")
        start = dt.date.fromisocalendar(int(year_s), int(w_s), 1)
    except (ValueError, AttributeError) as e:
        raise GA4APIError(f"week は ISO週 'YYYY-Www' 形式で指定してください(受け取った値: {week!r})") from e
    return start, start + dt.timedelta(days=6)


def _normalize_property_id(property_id: str) -> str:
    pid = (property_id or "").strip()
    if pid.startswith("properties/"):
        pid = pid[len("properties/"):]
    if not pid.isdigit():
        raise GA4APIError(
            f"property_id は GA4 のプロパティID(数字)で指定してください(受け取った値: {property_id!r})。"
            "測定ID(G-…)ではありません"
        )
    return pid


def _credentials_path() -> str:
    path = (os.environ.get(CREDENTIALS_ENV) or "").strip()
    if not path:
        raise GA4APIError(f"GA4 の認証情報がありません。環境変数 {CREDENTIALS_ENV} に鍵JSONのパスを設定してください")
    if not os.path.isfile(path):
        raise GA4APIError(f"{CREDENTIALS_ENV} が指すファイルがありません")
    if not os.access(path, os.R_OK):
        raise GA4APIError(f"{CREDENTIALS_ENV} が指すファイルを読めません(権限)")
    try:
        with open(path, encoding="utf-8") as f:
            info = json.load(f)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as e:
        # 鍵の中身をメッセージに含めない
        raise GA4APIError(f"{CREDENTIALS_ENV} のファイルが JSON として読めません({type(e).__name__})") from e
    if not isinstance(info, dict) or info.get("type") != "service_account":
        raise GA4APIError(f"{CREDENTIALS_ENV} のファイルがサービスアカウント鍵ではありません")
    return path


def _default_token() -> str:
    """GOOGLE_APPLICATION_CREDENTIALS の鍵でアクセストークンを取る。"""
    path = _credentials_path()
    try:
        from google.oauth2 import service_account  # noqa: PLC0415
        import google.auth.transport.requests  # noqa: PLC0415
    except ImportError as e:
        raise GA4APIError("google-auth が入っていません(pip install google-auth)") from e
    try:
        creds = service_account.Credentials.from_service_account_file(path, scopes=list(SCOPES))
        creds.refresh(google.auth.transport.requests.Request())
    except Exception as e:  # noqa: BLE001 — google-auth の例外型は多いので種類名だけ残す
        raise GA4APIError(f"GA4 のアクセストークン取得に失敗しました({type(e).__name__})") from e
    if not creds.token:
        raise GA4APIError("GA4 のアクセストークンが空です")
    return creds.token


def _is_timeout(err: BaseException) -> bool:
    if isinstance(err, (socket.timeout, TimeoutError)):
        return True
    if isinstance(err, urllib.error.URLError) and isinstance(err.reason, (socket.timeout, TimeoutError)):
        return True
    return False


def _http_error_detail(e: urllib.error.HTTPError) -> str:
    """GA4 のエラー本文から message だけ取り出す(本文に鍵は含まれない)。"""
    try:
        body = json.loads(e.read().decode("utf-8"))
        return str(body.get("error", {}).get("message", ""))[:300]
    except Exception:  # noqa: BLE001
        return ""


def _run_report(property_id: str, token: str, body: dict, label: str, sleep=time.sleep) -> dict:
    """runReport を POST して JSON を返す。500/503/タイムアウトは RETRY_DELAYS_SEC に従って再試行。"""
    url = f"{API_BASE}/properties/{property_id}:runReport"
    data = json.dumps(body).encode("utf-8")
    attempts = len(RETRY_DELAYS_SEC) + 1
    last_reason = ""
    for attempt in range(1, attempts + 1):
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            method="POST",
        )
        logger.info("GA4 request report=%s attempt=%d/%d POST %s", label, attempt, attempts, url)
        try:
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_SEC) as resp:
                status = getattr(resp, "status", 200)
                raw = resp.read()
            try:
                payload = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as e:
                raise GA4APIError(f"GA4 の応答が JSON ではありません(report={label}, HTTP {status})") from e
            if not isinstance(payload, dict):
                raise GA4APIError(f"GA4 の応答がオブジェクトではありません(report={label})")
            logger.info(
                "GA4 response report=%s status=%s rows=%d rowCount=%s",
                label, status, len(payload.get("rows") or []), payload.get("rowCount", 0),
            )
            return payload
        except urllib.error.HTTPError as e:
            detail = _http_error_detail(e)
            logger.warning("GA4 response report=%s status=%s attempt=%d detail=%s", label, e.code, attempt, detail)
            if e.code in (401, 403):
                raise GA4APIError(
                    f"GA4 認証/権限エラー(HTTP {e.code}, report={label})。"
                    "サービスアカウントがプロパティの「閲覧者」に追加されているか確認してください"
                ) from e
            if e.code == 400 and ARTICLE_DIMENSION in json.dumps(body) and "article_id" in detail:
                raise GA4APIError(
                    f"GA4 が {ARTICLE_DIMENSION} を受け付けません(HTTP 400)。プロパティにカスタムディメンション"
                    "(イベントスコープ・パラメータ名 article_id)を登録してください"
                ) from e
            if e.code not in RETRYABLE_STATUS:
                raise GA4APIError(f"GA4 がエラーを返しました(HTTP {e.code}, report={label}): {detail}") from e
            last_reason = f"HTTP {e.code}"
        except GA4APIError:
            raise
        except Exception as e:  # noqa: BLE001 — タイムアウト判定のため一旦受ける
            if not _is_timeout(e):
                raise GA4APIError(f"GA4 に接続できません(report={label}, {type(e).__name__}: {e})") from e
            logger.warning("GA4 timeout report=%s attempt=%d", label, attempt)
            last_reason = "timeout"
        if attempt < attempts:
            delay = RETRY_DELAYS_SEC[attempt - 1]
            logger.info("GA4 retry report=%s in %ss (reason=%s)", label, delay, last_reason)
            sleep(delay)
    raise GA4APIError(
        f"GA4 取得失敗(report={label}): {len(RETRY_DELAYS_SEC)}回リトライしても応答なし(最後の理由: {last_reason})"
    )


def _run_report_all_rows(property_id: str, token: str, body: dict, label: str, sleep=time.sleep) -> list[dict]:
    """rowCount に達するまで offset でページングして全行を返す。"""
    rows: list[dict] = []
    offset = 0
    while True:
        page_body = dict(body, limit=str(PAGE_LIMIT), offset=str(offset))
        payload = _run_report(property_id, token, page_body, f"{label}@{offset}", sleep=sleep)
        page = payload.get("rows") or []
        if not isinstance(page, list):
            raise GA4APIError(f"GA4 応答の rows が配列ではありません(report={label})")
        rows.extend(page)
        total = _to_int(payload.get("rowCount", len(rows)), f"{label} の rowCount")
        if not page or len(rows) >= total:
            return rows
        offset = len(rows)


def _to_int(value, what: str) -> int:
    """GA4 は数値を文字列で返す("123")。整数として読めない値は 0 にせずエラー。"""
    if isinstance(value, bool):
        raise GA4APIError(f"GA4 応答の {what} が整数ではありません(値: {value!r})")
    try:
        n = int(value)
    except (TypeError, ValueError) as e:
        raise GA4APIError(f"GA4 応答の {what} が整数ではありません(値: {value!r})") from e
    if n < 0 or (isinstance(value, float) and value != n):
        raise GA4APIError(f"GA4 応答の {what} が0以上の整数ではありません(値: {value!r})")
    return n


def _cell(row: dict, key: str, index: int, what: str) -> str:
    try:
        return row[key][index]["value"]
    except (KeyError, IndexError, TypeError) as e:
        raise GA4APIError(f"GA4 応答の行に {what} がありません") from e


def _date_ranges(week: str) -> list[dict]:
    start, end = week_range(week)
    return [{"startDate": start.isoformat(), "endDate": end.isoformat()}]


def _fetch_totals(pid, token, week, sleep) -> tuple[int, int]:
    payload = _run_report(pid, token, {
        "dateRanges": _date_ranges(week),
        "metrics": [{"name": "sessions"}, {"name": "screenPageViews"}],
    }, "totals", sleep=sleep)
    rows = payload.get("rows") or []
    if not rows:
        logger.warning("GA4 totals: week=%s にデータ行がありません → sessions=0, pageviews=0(GA4の実値)", week)
        return 0, 0
    row = rows[0]
    sessions = _to_int(_cell(row, "metricValues", 0, "sessions"), "sessions")
    pageviews = _to_int(_cell(row, "metricValues", 1, "screenPageViews"), "screenPageViews")
    return sessions, pageviews


def compute_ctr(pageviews_by_article: dict[str, int], clicks_by_article: dict[str, int]) -> dict[str, float]:
    """記事別 CTR = clicks / pageviews。page_view が 0 の記事は CTR を作らない(警告して除外)。"""
    ctr: dict[str, float] = {}
    for aid in sorted(set(pageviews_by_article) | set(clicks_by_article)):
        pv = pageviews_by_article.get(aid, 0)
        clicks = clicks_by_article.get(aid, 0)
        if pv == 0:
            logger.warning(
                "GA4 CTR: 記事 %s は article_click=%d だが page_view=0 のため CTR を算出しません"
                "(page_view に article_id が付いているか確認)", aid, clicks,
            )
            continue
        ctr[aid] = clicks / pv
    return ctr


def _fetch_article_counts(pid, token, week, sleep) -> tuple[dict[str, int], dict[str, int]]:
    rows = _run_report_all_rows(pid, token, {
        "dateRanges": _date_ranges(week),
        "dimensions": [{"name": "eventName"}, {"name": ARTICLE_DIMENSION}],
        "metrics": [{"name": "eventCount"}],
        "dimensionFilter": {"filter": {"fieldName": "eventName", "inListFilter": {
            "values": [PAGE_VIEW_EVENT, CLICK_EVENT]}}},
    }, "article_events", sleep=sleep)
    pageviews: dict[str, int] = {}
    clicks: dict[str, int] = {}
    unset = {PAGE_VIEW_EVENT: 0, CLICK_EVENT: 0}
    for row in rows:
        event = _cell(row, "dimensionValues", 0, "eventName")
        aid = _cell(row, "dimensionValues", 1, "article_id")
        count = _to_int(_cell(row, "metricValues", 0, "eventCount"), f"{event}/{aid} の eventCount")
        if event not in unset:
            raise GA4APIError(f"GA4 応答に想定外のイベント {event!r} が含まれています(フィルタ不一致)")
        if aid in UNSET_VALUES:
            unset[event] += count
            continue
        target = pageviews if event == PAGE_VIEW_EVENT else clicks
        target[aid] = target.get(aid, 0) + count
    if unset[PAGE_VIEW_EVENT] or unset[CLICK_EVENT]:
        logger.info(
            "GA4 article_events: article_id 無しのイベントを除外 page_view=%d article_click=%d",
            unset[PAGE_VIEW_EVENT], unset[CLICK_EVENT],
        )
    return pageviews, clicks


def _fetch_user_segments(pid, token, week, sleep) -> dict[str, int]:
    rows = _run_report_all_rows(pid, token, {
        "dateRanges": _date_ranges(week),
        "dimensions": [{"name": "newVsReturning"}],
        "metrics": [{"name": "activeUsers"}],
    }, "user_segments", sleep=sleep)
    counts: dict[str, int] = {}
    for row in rows:
        seg = _cell(row, "dimensionValues", 0, "newVsReturning") or "(not set)"
        counts[seg] = counts.get(seg, 0) + _to_int(_cell(row, "metricValues", 0, "activeUsers"), f"{seg} の activeUsers")
    return counts


def fetch_ga4_metrics(property_id: str, week: str, *, token_provider=None, sleep=time.sleep) -> GA4Metrics:
    """指定週(ISO週 "YYYY-Www")の GA4 実績を取得する。

    token_provider: アクセストークンを返す関数(テスト用)。省略時は GOOGLE_APPLICATION_CREDENTIALS の鍵を使う。
    失敗時は GA4APIError(認証情報なし/不正・権限なし・3回リトライ後の500/503/タイムアウト・応答不正)。
    """
    pid = _normalize_property_id(property_id)
    week_range(week)  # 形式不正はトークン取得前に止める
    token = (token_provider or _default_token)()
    if not token:
        raise GA4APIError("GA4 のアクセストークンが空です")

    sessions, pageviews = _fetch_totals(pid, token, week, sleep)
    pv_by_article, clicks_by_article = _fetch_article_counts(pid, token, week, sleep)
    ctr_by_article = compute_ctr(pv_by_article, clicks_by_article)
    user_segment_counts = _fetch_user_segments(pid, token, week, sleep)

    logger.info(
        "GA4 metrics week=%s sessions=%d pageviews=%d articles=%d segments=%s",
        week, sessions, pageviews, len(ctr_by_article), sorted(user_segment_counts),
    )
    return GA4Metrics(
        week=week,
        sessions=sessions,
        pageviews=pageviews,
        ctr_by_article=ctr_by_article,
        user_segment_counts=user_segment_counts,
    )


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    if len(sys.argv) != 3:
        print("usage: ga4_api.py PROPERTY_ID YYYY-Www", file=sys.stderr)
        sys.exit(2)
    try:
        m = fetch_ga4_metrics(sys.argv[1], sys.argv[2])
    except GA4APIError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
    print(json.dumps(m.to_dict(), ensure_ascii=False, indent=2))
