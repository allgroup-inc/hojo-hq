#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hojo-hq — 結果マガ週次メトリクス集約(売上自動化 Task 4)

Tasks 1-3 の出力(note_api.py / ga4_api.py / line_api.py)を組み合わせて、
週次集約データとして data/kekka_weekly_metrics.json に追記する。

出力形式(追記される要素):
{
  "week": "2026-W40",
  "collected_at": "2026-10-05T09:00:12+09:00",
  "note": {"week", "views_by_article", "total_likes", "total_sales_jpy", "buyer_count"},
  "ga4": { GA4Metrics.to_dict() },
  "line": { LINEMetrics.to_dict() },
  "line_source": "line_messaging_api" | "csv"
}

対象の週(C1 修正・2026-09-30):
- 既定は「前週」= JST の今日から7日前が属する ISO 週(月曜〜日曜)。
  定期実行は月曜 09:00 JST なので、直前に終わった週(日曜 23:59 JST まで)を集める。
  今日の ISO 週を使うと「始まったばかりの週」の数時間分を記録し、完了した週が永久に欠ける。
- 手動指定は 'YYYY-Www'。'2026-W1' のような1桁も受け付け、'2026-W01' に正規化する
  (表記ゆれで同じ週が別エントリになり、辞書順ソートが崩れるのを防ぐ)。

設計(捏造ゼロ):
- Tasks 1-3 から取得した値をそのまま組み合わせる。補完・推測はしない
- ファイルの weeks 配列に追記する。既出の week が再度来たら置き換える(手動再実行)
- 取得に1つでも失敗した週は書かない(CollectError)
- 既存ファイルの読み込み・形式検証は API 呼び出しより前に行う(壊れていれば API を叩く前に止める)
- 書き込みは一時ファイル → os.replace でアトミックに行う(途中で落ちてもファイルが切り詰められない)
- LINE の数字の取得元(API 実値か、手入力 CSV か)を line_source に残す

PII(C3 修正・2026-09-30。議事: docs/議事_20261001_結果マガ購入者データの保管先.md):
- 本リポジトリは PUBLIC。note の buyer_ids / buyer_profiles は公開ファイルにも標準出力にも出さない
- note セクションは _PUBLIC_NOTE_FIELDS のホワイトリストだけを書き、購入者はユニーク人数 buyer_count に集計する
  (NoteMetrics に将来フィールドが増えても、許可したもの以外は公開されない)
- 購入者単位のデータが必要になったら、守り部審査のうえ非公開リポジトリ(allgroup-inc/glow-docs-private)側で扱う

認証・接続:
- 環境変数: NOTE_API_TOKEN, GOOGLE_APPLICATION_CREDENTIALS, KEKKA_LINE_CHANNEL_ACCESS_TOKEN
- GA4 プロパティ ID: 引数 or 環境変数 GA4_PROPERTY_ID
- LINE チャネルID: 引数 or 環境変数 KEKKA_CHANNEL_ID、無ければ line_api.KEKKA_CHANNEL_ID

リトライ: Tasks 1-3 の関数が既にリトライを実装しているため、ここでは行わない。
  エラーは上位へ(ワークフロー側で失敗 Issue を起票する)

単体実行: python scripts/collect_weekly_metrics.py [-w 2026-W40]
"""
import argparse
import datetime as dt
import json
import logging
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Optional

# 親ディレクトリの scripts をインポートパスに追加
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from note_api import fetch_note_metrics, NoteAPIError  # noqa: E402
from ga4_api import fetch_ga4_metrics, GA4APIError  # noqa: E402
from line_api import fetch_line_metrics_with_source, LINEAPIError, KEKKA_CHANNEL_ID  # noqa: E402

logger = logging.getLogger("collect_weekly_metrics")

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
WEEKLY_METRICS_FILE = DATA_DIR / "kekka_weekly_metrics.json"

JST = dt.timezone(dt.timedelta(hours=9))

# 入力は 1〜2 桁の週番号を許し、出力は常に2桁(YYYY-Www)
_WEEK_INPUT_RE = re.compile(r"^([0-9]{4})-W([0-9]{1,2})$")

# 公開ファイルへ書く note のフィールド(ホワイトリスト)。buyer_ids / buyer_profiles は含めない
_PUBLIC_NOTE_FIELDS = ("week", "views_by_article", "total_likes", "total_sales_jpy")


class CollectError(Exception):
    """集約処理の失敗(API側のエラー、入力不正、ファイルI/O)をまとめる。"""


def _now_jst() -> dt.datetime:
    """現在時刻(JST)。テストで差し替える。"""
    return dt.datetime.now(JST)


def normalize_week(week: str) -> str:
    """'YYYY-Www'(週番号1〜2桁)を検証し、'YYYY-Www'(2桁ゼロ埋め)に正規化する。"""
    m = _WEEK_INPUT_RE.match((week or "").strip().upper())
    if not m:
        raise CollectError(f"week は ISO週 'YYYY-Www' 形式で指定してください(受け取った値: {week!r})")
    year, wk = int(m.group(1)), int(m.group(2))
    try:
        dt.date.fromisocalendar(year, wk, 1)
    except ValueError as e:
        raise CollectError(f"存在しない ISO 週です(受け取った値: {week!r})") from e
    return f"{year}-W{wk:02d}"


def default_week(now: Optional[dt.datetime] = None) -> str:
    """既定の対象週 = 前週(JST の今日から7日前が属する ISO 週)。"""
    now = now or _now_jst()
    if now.tzinfo is None:
        raise ValueError("now はタイムゾーン付きで渡してください")
    target = now.astimezone(JST).date() - dt.timedelta(days=7)
    iso = target.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


def _load_metrics_file(path: Path) -> dict:
    """既存ファイルを読み込み、形式を検証する(API 呼び出しより前に呼ぶ)。"""
    if not path.exists():
        logger.warning("ファイルが無いため初期化します: %s", path)
        return {"weeks": []}
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        raise CollectError(f"メトリクスファイルを読めません({path}): {e}") from e
    if not isinstance(content, dict):
        raise CollectError(f"メトリクスファイルの最上位が object ではありません({path})")
    weeks = content.setdefault("weeks", [])
    if not isinstance(weeks, list):
        raise CollectError(f"メトリクスファイルの weeks が配列ではありません({path})")
    for i, entry in enumerate(weeks):
        if not isinstance(entry, dict) or not isinstance(entry.get("week"), str):
            raise CollectError(f"メトリクスファイルの weeks[{i}] に week(文字列)がありません({path})")
    return content


def _write_atomic(path: Path, content: dict) -> None:
    """一時ファイルに書いてから os.replace で置き換える。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(content, f, ensure_ascii=False, indent=2)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def _public_note(note_dict: dict) -> dict:
    """note の公開用 dict。ホワイトリストのフィールドと購入者のユニーク人数だけにする。"""
    public = {k: note_dict[k] for k in _PUBLIC_NOTE_FIELDS if k in note_dict}
    public["buyer_count"] = len(set(note_dict.get("buyer_ids") or []))
    return public


def summarize(aggregated: dict) -> dict:
    """標準出力用の集計サマリ(公開の Actions ログに出るため、集計値だけにする)。"""
    note = aggregated.get("note", {})
    ga4 = aggregated.get("ga4", {})
    line = aggregated.get("line", {})
    return {
        "week": aggregated.get("week"),
        "collected_at": aggregated.get("collected_at"),
        "note": {
            "articles": len(note.get("views_by_article") or {}),
            "total_views": sum((note.get("views_by_article") or {}).values()),
            "total_likes": note.get("total_likes"),
            "total_sales_jpy": note.get("total_sales_jpy"),
            "buyer_count": note.get("buyer_count"),
        },
        "ga4": {"sessions": ga4.get("sessions"), "pageviews": ga4.get("pageviews")},
        "line": {
            "registered_count": line.get("registered_count"),
            "segments": len(line.get("open_rate_by_segment") or {}),
            "source": aggregated.get("line_source"),
        },
    }


def collect_and_save_weekly_metrics(
    week: Optional[str] = None,
    *,
    api_token: Optional[str] = None,
    property_id: Optional[str] = None,
    channel_id: Optional[str] = None,
) -> dict:
    """
    週次データを集約して data/kekka_weekly_metrics.json に追記する。

    Args:
        week: ISO週 'YYYY-Www'(例 '2026-W40')。None なら前週(default_week)
        api_token: note API トークン(None = 環境変数から)
        property_id: GA4 プロパティID(None = 環境変数から)
        channel_id: LINE チャネルID(None = 環境変数 KEKKA_CHANNEL_ID → 定数)

    Returns:
        集約した週次データ dict(公開ファイルに書いたものと同じ。購入者IDは含まない)

    Raises:
        CollectError: 入力不正、API取得失敗、ファイルI/O失敗
    """
    week = normalize_week(week) if week is not None else default_week()
    logger.info("週次メトリクス集約開始: week=%s", week)

    # --- API を叩く前に、設定と既存ファイルを検証する(早く失敗させる) ---
    pid = (property_id or os.environ.get("GA4_PROPERTY_ID", "")).strip()
    if not pid:
        raise CollectError("GA4 プロパティID がありません(引数 property_id または環境変数 GA4_PROPERTY_ID)")
    ch_id = (channel_id or os.environ.get("KEKKA_CHANNEL_ID", "")).strip() or KEKKA_CHANNEL_ID
    content = _load_metrics_file(WEEKLY_METRICS_FILE)

    # --- Tasks 1-3 からデータを取得 ---
    try:
        note_metrics = fetch_note_metrics(api_token or "", week)
    except NoteAPIError as e:
        raise CollectError(f"note API 失敗: {e}") from e
    logger.info("note: articles=%d sales_jpy=%s", len(note_metrics.views_by_article), note_metrics.total_sales_jpy)

    try:
        ga4_metrics = fetch_ga4_metrics(pid, week)
    except GA4APIError as e:
        raise CollectError(f"GA4 API 失敗: {e}") from e
    logger.info("GA4: sessions=%s pageviews=%s", ga4_metrics.sessions, ga4_metrics.pageviews)

    try:
        line_metrics, line_source = fetch_line_metrics_with_source(ch_id, week)
    except LINEAPIError as e:
        raise CollectError(f"LINE API 失敗: {e}") from e
    logger.info(
        "LINE: registered=%s segments=%d source=%s",
        line_metrics.registered_count, len(line_metrics.open_rate_by_segment), line_source,
    )

    # --- 集約データを構築(購入者IDは公開しない) ---
    aggregated = {
        "week": week,
        "collected_at": _now_jst().isoformat(timespec="seconds"),
        "note": _public_note(note_metrics.to_dict()),
        "ga4": ga4_metrics.to_dict(),
        "line": line_metrics.to_dict(),
        "line_source": line_source,
    }

    # --- 追記(同じ週は置き換え)して昇順に並べ、アトミックに書く ---
    weeks = [e for e in content["weeks"] if e.get("week") != week]
    if len(weeks) != len(content["weeks"]):
        logger.info("既存のエントリを置き換え: week=%s", week)
    else:
        logger.info("新規エントリを追加: week=%s", week)
    weeks.append(aggregated)
    weeks.sort(key=lambda x: x["week"])
    content["weeks"] = weeks

    try:
        _write_atomic(WEEKLY_METRICS_FILE, content)
    except OSError as e:
        raise CollectError(f"メトリクスファイル書き込み失敗: {e}") from e

    logger.info("集約完了: %s に week=%s を記録", WEEKLY_METRICS_FILE, week)
    return aggregated


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="結果マガの週次メトリクスを集約して記録")
    parser.add_argument(
        "-w", "--week",
        help="ISO週 'YYYY-Www'(例 '2026-W40')。指定なしは前週(JST の7日前が属する週)",
        type=str,
    )
    parser.add_argument("--api-token", help="note API トークン(指定なしは環境変数 NOTE_API_TOKEN)", type=str)
    parser.add_argument("--property-id", help="GA4 プロパティID(指定なしは環境変数 GA4_PROPERTY_ID)", type=str)
    parser.add_argument("--channel-id", help="LINE チャネルID(指定なしは環境変数 KEKKA_CHANNEL_ID → 定数)", type=str)
    parser.add_argument("-v", "--verbose", action="store_true", help="詳細ログを出力")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    try:
        result = collect_and_save_weekly_metrics(
            args.week,
            api_token=args.api_token,
            property_id=args.property_id,
            channel_id=args.channel_id,
        )
    except CollectError as e:
        logger.error("集約失敗: %s", e)
        return 1
    # 公開の Actions ログに出るため、集計サマリだけを出す
    print(json.dumps(summarize(result), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
