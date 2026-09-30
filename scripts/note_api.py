#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hojo-hq — 結果マガ note API クライアント(売上自動化 Task 1)

週単位で note API から記事別ビュー・スキ・売上・購入者を取得し、NoteMetrics にまとめる。
出力は Task 4(collect_weekly_metrics.py)が data/kekka_weekly_metrics.json へ追記する。

設計(捏造ゼロ):
- 数値はすべて API 応答の実値。views / likes が欠けている・整数でない記事は 0 で埋めず
  NoteAPIError で止める(欠損を 0 と書くと「実績ゼロ」という誤った事実になるため)
- sales キーが無い記事は「売上なし」として扱う(API がその記事の売上を持たない、の意)
- 取得できなかった(ネットワーク/503)と内容が不正(スキーマ不一致)はエラー文で区別する

認証: Bearer トークン。引数 api_token が空なら環境変数 NOTE_API_TOKEN を使う。
接続先: 環境変数 NOTE_API_BASE_URL(既定 https://note.com/api)+ /v1/articles

リトライ: HTTP 503 / タイムアウトのみ、最大3回(待機 5s → 10s → 15s)。
3回リトライしても失敗したら NoteAPIError。401/403 等は即座に NoteAPIError(再試行しない)。

週の指定: ISO週 "YYYY-Www"(例 "2026-W40")。月曜〜日曜を対象にする。

想定する応答(1ページ・ページングなし):
{
  "articles": [
    {"id": "n43d414a32946", "views": 1200, "likes": 34,
     "sales": [{"buyer_id": "u_1", "amount_jpy": 1280, "buyer_profile": {...}}]}
  ]
}
"""
import datetime as dt
import json
import logging
import os
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field

logger = logging.getLogger("note_api")

DEFAULT_BASE_URL = "https://note.com/api"
ARTICLES_PATH = "/v1/articles"
REQUEST_TIMEOUT_SEC = 30
# 3回リトライ・待機は 5s → 10s → 15s(計画書の指定値をそのまま使う)
RETRY_DELAYS_SEC = (5, 10, 15)


class NoteAPIError(Exception):
    """note API の取得失敗・認証失敗・応答不正をすべてこの例外で上げる(黙って成功扱いにしない)。"""


@dataclass
class NoteMetrics:
    week: str
    views_by_article: dict[str, int]
    total_likes: int
    total_sales_jpy: int
    buyer_ids: list[str]
    buyer_profiles: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def week_range(week: str) -> tuple[dt.date, dt.date]:
    """ISO週 "YYYY-Www" → (月曜, 日曜)。"""
    try:
        year_s, w_s = week.split("-W")
        year, wk = int(year_s), int(w_s)
        start = dt.date.fromisocalendar(year, wk, 1)
    except (ValueError, AttributeError) as e:
        raise NoteAPIError(f"week は ISO週 'YYYY-Www' 形式で指定してください(受け取った値: {week!r})") from e
    return start, start + dt.timedelta(days=6)


def _resolve_token(api_token: str | None) -> str:
    token = (api_token or os.environ.get("NOTE_API_TOKEN") or "").strip()
    if not token:
        raise NoteAPIError("note API トークンがありません。環境変数 NOTE_API_TOKEN を設定してください")
    return token


def _is_timeout(err: BaseException) -> bool:
    if isinstance(err, (socket.timeout, TimeoutError)):
        return True
    if isinstance(err, urllib.error.URLError) and isinstance(err.reason, (socket.timeout, TimeoutError)):
        return True
    return False


def _get_json(url: str, token: str, sleep=time.sleep) -> dict:
    """GET して JSON を返す。503/タイムアウトは RETRY_DELAYS_SEC に従って再試行。"""
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        method="GET",
    )
    attempts = len(RETRY_DELAYS_SEC) + 1
    last_reason = ""
    for attempt in range(1, attempts + 1):
        logger.info("note API request attempt=%d/%d GET %s", attempt, attempts, url)
        try:
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_SEC) as resp:
                status = getattr(resp, "status", 200)
                body = resp.read()
            logger.info("note API response status=%s bytes=%d", status, len(body))
            try:
                return json.loads(body.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as e:
                raise NoteAPIError(f"note API の応答が JSON ではありません(HTTP {status})") from e
        except urllib.error.HTTPError as e:
            logger.warning("note API response status=%s attempt=%d", e.code, attempt)
            if e.code in (401, 403):
                raise NoteAPIError(
                    f"note API 認証失敗(HTTP {e.code})。NOTE_API_TOKEN が無効か期限切れです"
                ) from e
            if e.code != 503:
                raise NoteAPIError(f"note API がエラーを返しました(HTTP {e.code})") from e
            last_reason = "HTTP 503"
        except NoteAPIError:
            raise
        except Exception as e:  # noqa: BLE001 — タイムアウト判定のため一旦受ける
            if not _is_timeout(e):
                raise NoteAPIError(f"note API に接続できません({type(e).__name__}: {e})") from e
            logger.warning("note API timeout attempt=%d", attempt)
            last_reason = "timeout"
        if attempt < attempts:
            delay = RETRY_DELAYS_SEC[attempt - 1]
            logger.info("note API retry in %ss (reason=%s)", delay, last_reason)
            sleep(delay)
    raise NoteAPIError(
        f"note API 取得失敗: {len(RETRY_DELAYS_SEC)}回リトライしても応答なし(最後の理由: {last_reason})"
    )


def _require_int(value, what: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise NoteAPIError(f"note API 応答の {what} が0以上の整数ではありません(値: {value!r})")
    return value


def _parse_metrics(week: str, payload: dict) -> NoteMetrics:
    if not isinstance(payload, dict) or not isinstance(payload.get("articles"), list):
        raise NoteAPIError("note API 応答に articles 配列がありません")

    views_by_article: dict[str, int] = {}
    total_likes = 0
    total_sales = 0
    buyer_ids: list[str] = []
    buyer_profiles: list[dict] = []
    seen_buyers: set[str] = set()

    for i, art in enumerate(payload["articles"]):
        if not isinstance(art, dict):
            raise NoteAPIError(f"articles[{i}] がオブジェクトではありません")
        art_id = art.get("id")
        if not isinstance(art_id, str) or not art_id:
            raise NoteAPIError(f"articles[{i}] に id がありません")
        if art_id in views_by_article:
            raise NoteAPIError(f"記事 {art_id} が応答に重複しています")
        views_by_article[art_id] = _require_int(art.get("views"), f"記事 {art_id} の views")
        total_likes += _require_int(art.get("likes"), f"記事 {art_id} の likes")

        sales = art.get("sales", [])
        if not isinstance(sales, list):
            raise NoteAPIError(f"記事 {art_id} の sales が配列ではありません")
        for j, sale in enumerate(sales):
            if not isinstance(sale, dict):
                raise NoteAPIError(f"記事 {art_id} の sales[{j}] がオブジェクトではありません")
            total_sales += _require_int(sale.get("amount_jpy"), f"記事 {art_id} の sales[{j}].amount_jpy")
            buyer_id = sale.get("buyer_id")
            if not isinstance(buyer_id, str) or not buyer_id:
                raise NoteAPIError(f"記事 {art_id} の sales[{j}] に buyer_id がありません")
            if buyer_id in seen_buyers:
                continue
            seen_buyers.add(buyer_id)
            buyer_ids.append(buyer_id)
            profile = sale.get("buyer_profile")
            if isinstance(profile, dict):
                buyer_profiles.append({"buyer_id": buyer_id, **profile})

    return NoteMetrics(
        week=week,
        views_by_article=views_by_article,
        total_likes=total_likes,
        total_sales_jpy=total_sales,
        buyer_ids=buyer_ids,
        buyer_profiles=buyer_profiles,
    )


def fetch_note_metrics(api_token: str, week: str, *, sleep=time.sleep) -> NoteMetrics:
    """指定週(ISO週 "YYYY-Www")に公開された記事の実績を note API から取得する。

    失敗時は NoteAPIError(トークン無し/無効・3回リトライ後の503/タイムアウト・応答不正)。
    """
    token = _resolve_token(api_token)
    start, end = week_range(week)
    base = os.environ.get("NOTE_API_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
    query = urllib.parse.urlencode({"published_after": start.isoformat(), "published_before": end.isoformat()})
    url = f"{base}{ARTICLES_PATH}?{query}"
    payload = _get_json(url, token, sleep=sleep)
    return _parse_metrics(week, payload)


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    if len(sys.argv) != 2:
        print("usage: note_api.py YYYY-Www", file=sys.stderr)
        sys.exit(2)
    try:
        m = fetch_note_metrics(os.environ.get("NOTE_API_TOKEN", ""), sys.argv[1])
    except NoteAPIError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
    print(json.dumps(m.to_dict(), ensure_ascii=False, indent=2))
