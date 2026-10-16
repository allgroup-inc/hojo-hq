#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hojo-hq — 結果マガ LINE クライアント(売上自動化 Task 3)

週単位で結果マガの LINE 公式アカウント(@473btavk・プロバイダー kekka_mag・チャネルID 2011004310)の
登録者数と、購買確度セグメント別の開封率・クリック率を取り、LINEMetrics にまとめる。
ミカタ(沖縄企業のミカタ)やもらいわすれ堂の LINE 公式アカウントは対象外(数字を混ぜない)。出力は Task 4(collect_weekly_metrics.py)が
data/kekka_weekly_metrics.json の line セクションへ追記する。

取得経路(この順に試す):
1. LINE Messaging API(リアルタイム)
   - 登録者数: GET /v2/bot/insight/followers?date=<週の日曜>
     → followers(結果マガ LINE の友だち追加の累計。ブロックしても減らない。
       LINE 公式アカウント管理画面の「友だち追加数」と同じ定義。有効友だち数 = followers - blocks ではない)
   - セグメント別の開封・クリック: GET /v2/bot/insight/message/event/aggregation
     ?customAggregationUnit=<ユニット名>&from=<月曜>&to=<日曜>
     → overview.uniqueImpression(開封した人数)/ overview.uniqueClick(クリックした人数)
     ユニット名は aggregation_unit(segment) = "kekka_<segment>"。送信側(Task 9)は
     push/multicast の customAggregationUnits にこの名前を付けて送ること
     from/to は「イベント(開封・クリック)が起きた日」で絞る(送信日ではない)。前週に送った
     メッセージを今週開いた分は今週に数えられ、今週送った分の開封が翌週にずれ込むこともある。
     分母の delivered_by_segment は送信日ベースなので、週またぎの配信では率がわずかにずれ得る
   - 分母(配信人数)は LINE が返さないため、呼び出し側が delivered_by_segment で渡す
     (送信ログ由来のセグメント別ユニーク配信人数)。渡されなければ API 経路は「利用不可」
2. フォールバック: data/line_segment_stats_<week>.csv(Power Automate の配信ログ等から事前集計したもの)

CSV の形式(UTF-8。Excel の BOM 付きも可。1行 = 1セグメント):
    week,registered_count,segment,delivered,unique_opens,unique_clicks
    2026-W40,152,high_engagement,40,31,12
    2026-W40,152,line_only,80,,
  - week は要求した週と一致すること。registered_count は全行で同じ値(週末時点の登録者数)
  - segment は SEGMENTS のいずれか。重複不可
  - delivered は必須。unique_opens / unique_clicks は空欄 = 不明(その率は作らない。0 とはみなさない)

率の定義(両経路共通・compute_rates):
  open_rate  = unique_opens  / delivered
  click_rate = unique_clicks / delivered   (分母は開封数ではなく配信人数)

設計(捏造ゼロ):
- 数値はすべて LINE 応答または CSV の実値から計算する。欠けた値を 0 で埋めない
  - delivered = 0 のセグメントは率を作らない(分母が無い。警告ログ)
  - 開封/クリック人数が null(LINE は少人数の統計を null で返すことがある)・空欄なら、その率を作らない
  - 開封/クリック人数 > 配信人数(率 > 1)は定義不整合として LINEAPIError(丸めない)
  - 配信したのにユニットにメッセージが1通も無い → 送信時のユニット付け忘れ。0% と誤報しないよう LINEAPIError
- 「取得できなかった」(未設定・503・タイムアウト・集計待ち)は LINEAPIUnavailable → CSV へフォールバック
  「内容が違う/設定が誤り」(401/403・応答不正・チャネル不一致・CSV 不正)は LINEAPIError で止める
- どちらの経路で取ったかはログと fetch_line_metrics_with_source() の戻り値で分かる
- 集計値のみ。個人識別子(userId 等)は扱わない。チャネルアクセストークンはログにもエラー文にも出さない

認証: 環境変数 KEKKA_LINE_CHANNEL_ACCESS_TOKEN(結果マガ専用。.github/workflows/line-test.yml と同じ Secret。
  未設定なら API を叩かず CSV へ)。ミカタ用の LINE_CHANNEL_ACCESS_TOKEN は読まない。
  呼び出し側は channel_id=2011004310 を渡す。取得前に POST /v2/oauth/verify でトークンの発行元チャネルが
  channel_id と一致するか確かめる(リポジトリにはミカタ・もらいわすれ堂など複数の LINE 公式アカウントがあり、
  取り違えると別アカウントの数字になる)。

リトライ: HTTP 500/502/503/504・タイムアウトのみ最大3回(待機 5s → 10s → 15s。Task 1/2 と同じ値)。
  それでも失敗、または 429 は LINEAPIUnavailable(CSV へ)。

週の指定: ISO週 "YYYY-Www"(例 "2026-W40")。月曜〜日曜。LINE の統計は日本時間(UTC+9)で区切られる。
"""
import csv
import datetime as dt
import http.client
import json
import logging
import os
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path

logger = logging.getLogger("line_api")

API_BASE = "https://api.line.me"
TOKEN_ENV = "KEKKA_LINE_CHANNEL_ACCESS_TOKEN"  # 結果マガ専用(ミカタの LINE_CHANNEL_ACCESS_TOKEN ではない)
KEKKA_CHANNEL_ID = "2011004310"  # 結果マガ LINE(@473btavk)。Task 4 はこれを channel_id に渡す
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
REQUEST_TIMEOUT_SEC = 30
RETRY_DELAYS_SEC = (5, 10, 15)
RETRYABLE_STATUS = (500, 502, 503, 504)

# 購買確度の4セグメント(設計書 1.3 / Task 8)。CSV とユニット名のキー
SEGMENTS = ("high_engagement", "active_reader", "discovery_seeker", "line_only")
UNIT_PREFIX = "kekka_"
CSV_COLUMNS = ("week", "registered_count", "segment", "delivered", "unique_opens", "unique_clicks")

SOURCE_API = "line_messaging_api"
SOURCE_CSV = "csv"


class LINEAPIError(Exception):
    """LINE の数字を正しく作れないときの例外(黙って成功扱いにしない)。"""


class LINEAPIUnavailable(LINEAPIError):
    """API から取得できなかった(未設定・一時障害・集計待ち)。CSV フォールバックの対象。"""


@dataclass
class LINEMetrics:
    week: str
    registered_count: int
    open_rate_by_segment: dict[str, float]
    click_rate_by_segment: dict[str, float]

    def to_dict(self) -> dict:
        return asdict(self)


def aggregation_unit(segment: str) -> str:
    """セグメント → LINE のカスタム集計ユニット名(英数字と _ のみ・30文字以内)。"""
    return f"{UNIT_PREFIX}{segment}"


def week_range(week: str) -> tuple[dt.date, dt.date]:
    """ISO週 "YYYY-Www" → (月曜, 日曜)。"""
    try:
        year_s, w_s = week.split("-W")
        start = dt.date.fromisocalendar(int(year_s), int(w_s), 1)
    except (ValueError, AttributeError) as e:
        raise LINEAPIError(f"week は ISO週 'YYYY-Www' 形式で指定してください(受け取った値: {week!r})") from e
    return start, start + dt.timedelta(days=6)


# --- 率の計算(両経路共通)--------------------------------------------------

def compute_rates(
    delivered: dict[str, int],
    opens: dict[str, int | None],
    clicks: dict[str, int | None],
) -> tuple[dict[str, float], dict[str, float]]:
    """セグメント別の開封率・クリック率。分母が無い・分子が不明なら、その率は作らない。"""
    open_rates: dict[str, float] = {}
    click_rates: dict[str, float] = {}
    for seg in sorted(delivered):
        n = delivered[seg]
        if n == 0:
            logger.warning("LINE rates: segment=%s は配信0人のため率を算出しません", seg)
            continue
        for label, counts, out in (("開封", opens, open_rates), ("クリック", clicks, click_rates)):
            value = counts.get(seg)
            if value is None:
                logger.warning("LINE rates: segment=%s の%s人数が不明のため%s率を算出しません", seg, label, label)
                continue
            if value > n:
                raise LINEAPIError(
                    f"segment={seg} の{label}人数 {value} が配信人数 {n} を超えています"
                    "(配信人数がユニーク人数でない、または集計対象がずれている)"
                )
            out[seg] = value / n
    return open_rates, click_rates


def _check_count(value, what: str, *, allow_none: bool = False) -> int | None:
    if value is None and allow_none:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise LINEAPIError(f"{what} が0以上の整数ではありません(値: {value!r})")
    return value


# --- API 経路 ---------------------------------------------------------------

def _is_timeout(err: BaseException) -> bool:
    if isinstance(err, (socket.timeout, TimeoutError)):
        return True
    if isinstance(err, urllib.error.URLError) and isinstance(err.reason, (socket.timeout, TimeoutError)):
        return True
    return False


def _http_error_detail(e: urllib.error.HTTPError) -> str:
    """LINE のエラー本文から message だけ取り出す(本文にトークンは含まれない)。"""
    try:
        body = json.loads(e.read().decode("utf-8"))
        return str(body.get("message", ""))[:300]
    except Exception:  # noqa: BLE001
        return ""


def _request(url: str, label: str, *, token: str | None = None, form: dict | None = None,
             sleep=time.sleep) -> dict:
    """GET(form なし)/ POST(form あり)して JSON を返す。ログに出すのは URL・ステータス・要約だけ。"""
    data = urllib.parse.urlencode(form).encode("utf-8") if form is not None else None
    method = "POST" if data is not None else "GET"
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if data is not None:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    attempts = len(RETRY_DELAYS_SEC) + 1
    last_reason = ""
    for attempt in range(1, attempts + 1):
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        logger.info("LINE request %s attempt=%d/%d %s %s", label, attempt, attempts, method, url)
        try:
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_SEC) as resp:
                status = getattr(resp, "status", 200)
                raw = resp.read()
            try:
                payload = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as e:
                raise LINEAPIError(f"LINE の応答が JSON ではありません({label}, HTTP {status})") from e
            if not isinstance(payload, dict):
                raise LINEAPIError(f"LINE の応答がオブジェクトではありません({label})")
            logger.info("LINE response %s status=%s keys=%s", label, status, sorted(payload))
            return payload
        except urllib.error.HTTPError as e:
            detail = _http_error_detail(e)
            logger.warning("LINE response %s status=%s attempt=%d detail=%s", label, e.code, attempt, detail)
            if e.code in (401, 403):
                raise LINEAPIError(
                    f"LINE 認証/権限エラー(HTTP {e.code}, {label})。"
                    f"{TOKEN_ENV} がこのチャネルの有効なチャネルアクセストークンか確認してください"
                ) from e
            if e.code == 429:
                raise LINEAPIUnavailable(f"LINE のレート制限(HTTP 429, {label})") from e
            if e.code not in RETRYABLE_STATUS:
                raise LINEAPIError(f"LINE がエラーを返しました(HTTP {e.code}, {label}): {detail}") from e
            last_reason = f"HTTP {e.code}"
        except (urllib.error.URLError, OSError, http.client.HTTPException) as e:
            # 通信系の失敗だけ受ける(TypeError 等のコードの誤りは握りつぶさず、そのまま落とす)
            if _is_timeout(e):
                logger.warning("LINE timeout %s attempt=%d", label, attempt)
                last_reason = "timeout"
            else:
                raise LINEAPIUnavailable(f"LINE に接続できません({label}, {type(e).__name__})") from e
        if attempt < attempts:
            delay = RETRY_DELAYS_SEC[attempt - 1]
            logger.info("LINE retry %s in %ss (reason=%s)", label, delay, last_reason)
            sleep(delay)
    raise LINEAPIUnavailable(
        f"LINE 取得失敗({label}): {len(RETRY_DELAYS_SEC)}回リトライしても応答なし(最後の理由: {last_reason})"
    )


def _verify_channel(channel_id: str, token: str, sleep) -> None:
    """トークンの発行元チャネル(client_id)が channel_id と一致するか確かめる。"""
    payload = _request(f"{API_BASE}/v2/oauth/verify", "verify", form={"access_token": token}, sleep=sleep)
    client_id = str(payload.get("client_id", ""))
    if client_id != channel_id:
        raise LINEAPIError(
            f"{TOKEN_ENV} は channel_id={channel_id} のトークンではありません(発行元: {client_id or '不明'})。"
            "別の LINE 公式アカウントの数字を取らないよう中止します"
        )


def _fetch_followers(token: str, day: dt.date, sleep) -> int:
    url = f"{API_BASE}/v2/bot/insight/followers?date={day:%Y%m%d}"
    payload = _request(url, "followers", token=token, sleep=sleep)
    status = payload.get("status")
    if status != "ready":
        raise LINEAPIUnavailable(f"LINE 友だち数が未確定です(date={day:%Y%m%d}, status={status})")
    followers = _check_count(payload.get("followers"), "LINE 応答の followers")
    logger.info("LINE followers date=%s followers=%d blocks=%s", day, followers, payload.get("blocks"))
    return followers


def _fetch_unit(token: str, segment: str, start: dt.date, end: dt.date, sleep) -> tuple[int | None, int | None, int | None]:
    """ユニットの (開封人数, クリック人数, メッセージ数)。LINE が null を返した値は None のまま。"""
    query = urllib.parse.urlencode({
        "customAggregationUnit": aggregation_unit(segment),
        "from": f"{start:%Y%m%d}",
        "to": f"{end:%Y%m%d}",
    })
    payload = _request(f"{API_BASE}/v2/bot/insight/message/event/aggregation?{query}",
                       f"unit={aggregation_unit(segment)}", token=token, sleep=sleep)
    overview = payload.get("overview")
    if not isinstance(overview, dict):
        raise LINEAPIError(f"LINE 応答に overview がありません(segment={segment})")
    opens = _check_count(overview.get("uniqueImpression"), f"segment={segment} の uniqueImpression", allow_none=True)
    clicks = _check_count(overview.get("uniqueClick"), f"segment={segment} の uniqueClick", allow_none=True)
    messages = payload.get("messages")
    n_messages = len(messages) if isinstance(messages, list) else None
    logger.info("LINE unit segment=%s messages=%s uniqueImpression=%s uniqueClick=%s",
                segment, n_messages, opens, clicks)
    return opens, clicks, n_messages


def fetch_line_metrics_from_api(
    channel_id: str,
    week: str,
    *,
    delivered_by_segment: dict[str, int] | None,
    token: str | None = None,
    verify_channel: bool = True,
    sleep=time.sleep,
) -> LINEMetrics:
    """Messaging API から取る。取れなければ LINEAPIUnavailable、数字がおかしければ LINEAPIError。"""
    start, end = week_range(week)
    token = token if token is not None else (os.environ.get(TOKEN_ENV) or "").strip()
    if not token:
        raise LINEAPIUnavailable(f"{TOKEN_ENV} が未設定です")
    if delivered_by_segment is None:
        raise LINEAPIUnavailable(
            "セグメント別の配信人数(delivered_by_segment)が渡されていません。LINE は分母を返さないため API では率を作れません"
        )
    delivered: dict[str, int] = {}
    for seg, n in delivered_by_segment.items():
        if seg not in SEGMENTS:
            raise LINEAPIError(f"未知のセグメント {seg!r}(使えるのは {', '.join(SEGMENTS)})")
        delivered[seg] = _check_count(n, f"segment={seg} の配信人数")

    if verify_channel:
        _verify_channel(channel_id, token, sleep)
    registered = _fetch_followers(token, end, sleep)

    opens: dict[str, int | None] = {}
    clicks: dict[str, int | None] = {}
    for seg in sorted(delivered):
        if delivered[seg] == 0:
            continue
        o, c, n_messages = _fetch_unit(token, seg, start, end, sleep)
        if n_messages == 0:
            raise LINEAPIError(
                f"segment={seg} は {delivered[seg]}人に配信したはずですが、ユニット {aggregation_unit(seg)} に"
                "メッセージがありません(送信時の customAggregationUnits 付け忘れ)。0% と誤報しないよう中止します"
            )
        opens[seg], clicks[seg] = o, c

    open_rates, click_rates = compute_rates(delivered, opens, clicks)
    return LINEMetrics(week=week, registered_count=registered,
                       open_rate_by_segment=open_rates, click_rate_by_segment=click_rates)


# --- CSV フォールバック -----------------------------------------------------

def csv_path(week: str, data_dir: Path | str = DATA_DIR) -> Path:
    return Path(data_dir) / f"line_segment_stats_{week}.csv"


def _csv_int(row: dict, key: str, line_no: int, *, allow_blank: bool = False) -> int | None:
    raw = (row.get(key) or "").strip()
    if raw == "" and allow_blank:
        return None
    if not (raw.isascii() and raw.isdigit()):
        raise LINEAPIError(f"CSV {line_no}行目の {key} が0以上の整数ではありません(値: {raw!r})")
    return int(raw)


def load_line_metrics_csv(week: str, *, data_dir: Path | str = DATA_DIR) -> LINEMetrics:
    """data/line_segment_stats_<week>.csv を読む。無ければ LINEAPIUnavailable、不正なら LINEAPIError。"""
    week_range(week)
    path = csv_path(week, data_dir)
    if not path.is_file():
        raise LINEAPIUnavailable(f"フォールバック CSV がありません: {path.name}")
    logger.info("LINE csv read %s", path)
    try:
        with open(path, encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            header = [h.strip() for h in (reader.fieldnames or [])]
            missing = [c for c in CSV_COLUMNS if c not in header]
            if missing:
                raise LINEAPIError(f"CSV {path.name} に列がありません: {', '.join(missing)}")
            reader.fieldnames = header
            rows = list(reader)
    except (OSError, UnicodeDecodeError, csv.Error) as e:
        raise LINEAPIError(f"CSV {path.name} を読めません({type(e).__name__})") from e
    if not rows:
        raise LINEAPIError(f"CSV {path.name} にデータ行がありません")

    registered: int | None = None
    delivered: dict[str, int] = {}
    opens: dict[str, int | None] = {}
    clicks: dict[str, int | None] = {}
    for i, row in enumerate(rows, start=2):  # 1行目はヘッダー
        row_week = (row.get("week") or "").strip()
        if row_week != week:
            raise LINEAPIError(f"CSV {i}行目の week={row_week!r} が要求した週 {week} と違います")
        seg = (row.get("segment") or "").strip()
        if seg not in SEGMENTS:
            raise LINEAPIError(f"CSV {i}行目の segment={seg!r} は未知です(使えるのは {', '.join(SEGMENTS)})")
        if seg in delivered:
            raise LINEAPIError(f"CSV {i}行目: segment={seg} が重複しています")
        reg = _csv_int(row, "registered_count", i)
        if registered is None:
            registered = reg
        elif reg != registered:
            raise LINEAPIError(f"CSV {i}行目の registered_count={reg} が他の行({registered})と違います")
        delivered[seg] = _csv_int(row, "delivered", i)
        opens[seg] = _csv_int(row, "unique_opens", i, allow_blank=True)
        clicks[seg] = _csv_int(row, "unique_clicks", i, allow_blank=True)

    logger.info("LINE csv rows=%d registered_count=%d segments=%s", len(rows), registered, sorted(delivered))
    open_rates, click_rates = compute_rates(delivered, opens, clicks)
    return LINEMetrics(week=week, registered_count=registered,
                       open_rate_by_segment=open_rates, click_rate_by_segment=click_rates)


# --- 入口 ---------------------------------------------------------------------

def fetch_line_metrics_with_source(
    channel_id: str,
    week: str,
    *,
    delivered_by_segment: dict[str, int] | None = None,
    token: str | None = None,
    data_dir: Path | str = DATA_DIR,
    verify_channel: bool = True,
    sleep=time.sleep,
) -> tuple[LINEMetrics, str]:
    """(LINEMetrics, 取得元)を返す。取得元は SOURCE_API か SOURCE_CSV。"""
    channel_id = (channel_id or "").strip()
    if not channel_id.isdigit():
        raise LINEAPIError(f"channel_id は LINE のチャネルID(数字)で指定してください(受け取った値: {channel_id!r})")
    week_range(week)
    try:
        m = fetch_line_metrics_from_api(channel_id, week, delivered_by_segment=delivered_by_segment,
                                        token=token, verify_channel=verify_channel, sleep=sleep)
        source = SOURCE_API
    except LINEAPIUnavailable as api_reason:
        logger.warning("LINE API 利用不可 → CSV にフォールバック(理由: %s)", api_reason)
        try:
            m = load_line_metrics_csv(week, data_dir=data_dir)
        except LINEAPIUnavailable as csv_reason:
            raise LINEAPIError(f"LINE の数字を取得できません。API: {api_reason} / CSV: {csv_reason}") from csv_reason
        source = SOURCE_CSV
    logger.info(
        "LINE metrics week=%s source=%s registered_count=%d open=%s click=%s",
        week, source, m.registered_count, sorted(m.open_rate_by_segment), sorted(m.click_rate_by_segment),
    )
    return m, source


def fetch_line_metrics(channel_id: str, week: str, **kwargs) -> LINEMetrics:
    """指定週(ISO週 "YYYY-Www")の LINE 実績。API → CSV の順に試す。どちらも駄目なら LINEAPIError。"""
    return fetch_line_metrics_with_source(channel_id, week, **kwargs)[0]


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    if len(sys.argv) != 3:
        print("usage: line_api.py CHANNEL_ID YYYY-Www", file=sys.stderr)
        sys.exit(2)
    try:
        metrics, src = fetch_line_metrics_with_source(sys.argv[1], sys.argv[2])
    except LINEAPIError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
    print(json.dumps({"source": src, **metrics.to_dict()}, ensure_ascii=False, indent=2))
