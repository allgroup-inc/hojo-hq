#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hojo-hq — 結果マガ週次メトリクス集約(売上自動化 Task 4)

Tasks 1-3 の出力(note_api.py / ga4_api.py / line_api.py)を組み合わせて、
週次集約データとして data/kekka_weekly_metrics.json に追記する。

出力形式(追記される要素):
{
  "week": "2026-W40",
  "collected_at": "2026-09-30T17:30:00+09:00",
  "note": { NoteMetrics.to_dict() },
  "ga4": { GA4Metrics.to_dict() },
  "line": { LINEMetrics.to_dict() }
}

設計(捏造ゼロ):
- Tasks 1-3 から取得した値をそのまま組み合わせる。補完・推測はしない
- ファイルの weeks 配列に追記する(上書きしない)。既出の week が再度来たら上書きする
- 同一 week が複数回来た場合(例: 手動再実行)、古い方を新しい方で置き換える
- PII 対応: buyer_profiles は PUBLIC repo に保管しないため、取得後にハッシュ化する
  または削除する(実装時に判断が必要。当面は削除/リスト空化)
- タイムスタンプは実行時刻(collect_and_save_weekly_metrics が呼ばれた時刻)

認証・接続:
- 環境変数: NOTE_API_TOKEN, GOOGLE_APPLICATION_CREDENTIALS, KEKKA_LINE_CHANNEL_ACCESS_TOKEN
- GA4 プロパティ ID: 環境変数 GA4_PROPERTY_ID(既定値は設定ファイルまたは親スクリプトから)
- LINE チャネルID: line_api.py の KEKKA_CHANNEL_ID を利用

リトライ: Tasks 1-3 の関数が既にリトライを実装しているため、ここでは行わない。
  エラーは上位へ(ワークフロー側で LINE 通知等を行う)

この script は単体実行可能(例: python scripts/collect_weekly_metrics.py -w 2026-W40)
"""
import argparse
import datetime as dt
import json
import logging
import os
import sys
from pathlib import Path
from typing import Optional

# 親ディレクトリの scripts をインポートパスに追加
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from note_api import fetch_note_metrics, NoteAPIError
from ga4_api import fetch_ga4_metrics, GA4APIError
from line_api import fetch_line_metrics, LINEAPIError

logger = logging.getLogger("collect_weekly_metrics")

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
WEEKLY_METRICS_FILE = DATA_DIR / "kekka_weekly_metrics.json"


class CollectError(Exception):
    """集約処理の失敗(API側のエラー、ファイルI/O)をまとめる。"""


def _now_jst() -> str:
    """現在時刻を ISO 8601 形式(+09:00)で返す。"""
    now = dt.datetime.now(dt.timezone(dt.timedelta(hours=9)))
    return now.isoformat()


def _sanitize_buyer_profiles(profiles: list[dict]) -> list[dict]:
    """
    PII対応: buyer_profiles をハッシュ化または削除する。
    当面は、個人を特定し得る属性(名前・メール等)を削除し、
    buyer_id のみを保持する。

    (決定: CLAUDE.md §機密区分 に従い、PUBLIC repo の buyer_profiles は、
    個人を特定し得る属性を含むそのまま保管はしない。
    ハッシュ化か削除かは守り部確認が必要だが、当面は削除)
    """
    # 実装案A: buyer_id のみを保持
    sanitized = []
    for p in profiles:
        if isinstance(p, dict) and "buyer_id" in p:
            sanitized.append({"buyer_id": p["buyer_id"]})
    return sanitized


def collect_and_save_weekly_metrics(
    week: str,
    *,
    api_token: Optional[str] = None,
    property_id: Optional[str] = None,
    channel_id: Optional[str] = None,
) -> dict:
    """
    週次データを集約して data/kekka_weekly_metrics.json に追記する。

    Args:
        week: ISO週 'YYYY-Www'(例 '2026-W40')
        api_token: note API トークン(None = 環境変数から)
        property_id: GA4 プロパティID(None = 環境変数から)
        channel_id: LINE チャネルID(None = 環境変数または定数から)

    Returns:
        集約した週次データ dict

    Raises:
        CollectError: API取得失敗、ファイルI/O失敗
    """
    logger.info(f"週次メトリクス集約開始: week={week}")

    # --- Tasks 1-3 からデータを取得 ---
    try:
        logger.debug("note メトリクスを取得中...")
        note_metrics = fetch_note_metrics(api_token or "", week)
        logger.info(f"note: {note_metrics.views_by_article} articles, {note_metrics.total_sales_jpy} JPY")
    except NoteAPIError as e:
        raise CollectError(f"note API 失敗: {e}") from e

    try:
        logger.debug("GA4 メトリクスを取得中...")
        pid = property_id or os.environ.get("GA4_PROPERTY_ID", "").strip()
        if not pid:
            raise CollectError(
                "GA4 プロパティID がありません(引数 property_id または環境変数 GA4_PROPERTY_ID)"
            )
        ga4_metrics = fetch_ga4_metrics(pid, week)
        logger.info(f"GA4: {ga4_metrics.sessions} sessions, {ga4_metrics.pageviews} pageviews")
    except GA4APIError as e:
        raise CollectError(f"GA4 API 失敗: {e}") from e

    try:
        logger.debug("LINE メトリクスを取得中...")
        ch_id = channel_id or os.environ.get("KEKKA_CHANNEL_ID", "").strip()
        if not ch_id:
            # line_api.py の定数をフォールバック
            from line_api import KEKKA_CHANNEL_ID
            ch_id = KEKKA_CHANNEL_ID
        line_metrics = fetch_line_metrics(ch_id, week)
        logger.info(f"LINE: {line_metrics.registered_count} 登録者, {len(line_metrics.open_rate_by_segment)} セグメント")
    except LINEAPIError as e:
        raise CollectError(f"LINE API 失敗: {e}") from e

    # --- 集約データを構築 ---
    note_dict = note_metrics.to_dict()
    # PII対応: buyer_profiles をサニタイズ
    if note_dict.get("buyer_profiles"):
        note_dict["buyer_profiles"] = _sanitize_buyer_profiles(note_dict["buyer_profiles"])

    aggregated = {
        "week": week,
        "collected_at": _now_jst(),
        "note": note_dict,
        "ga4": ga4_metrics.to_dict(),
        "line": line_metrics.to_dict(),
    }

    # --- kekka_weekly_metrics.json に追記 ---
    try:
        logger.debug(f"メトリクスファイルを読み込み: {WEEKLY_METRICS_FILE}")
        if WEEKLY_METRICS_FILE.exists():
            with open(WEEKLY_METRICS_FILE, "r", encoding="utf-8") as f:
                content = json.load(f)
        else:
            logger.warning(f"ファイルが無いため初期化: {WEEKLY_METRICS_FILE}")
            content = {"weeks": []}

        # weeks 配列が無ければ初期化
        if "weeks" not in content:
            content["weeks"] = []

        # 既存の同一 week があれば置き換え、無ければ追加
        weeks = content["weeks"]
        existing_idx = None
        for i, entry in enumerate(weeks):
            if entry.get("week") == week:
                existing_idx = i
                break

        if existing_idx is not None:
            logger.info(f"既存のエントリを置き換え: week={week} (index {existing_idx})")
            weeks[existing_idx] = aggregated
        else:
            logger.info(f"新規エントリを追加: week={week}")
            weeks.append(aggregated)

        # 時系列順(week の昇順)にソート
        weeks.sort(key=lambda x: x.get("week", ""))

        logger.debug(f"メトリクスファイルを書き込み: {WEEKLY_METRICS_FILE}")
        with open(WEEKLY_METRICS_FILE, "w", encoding="utf-8") as f:
            json.dump(content, f, ensure_ascii=False, indent=2)

        logger.info(f"✓ 集約完了: {WEEKLY_METRICS_FILE} に week={week} を記録")
    except (OSError, json.JSONDecodeError, KeyError) as e:
        raise CollectError(f"メトリクスファイル操作失敗: {e}") from e

    return aggregated


def main():
    parser = argparse.ArgumentParser(
        description="結果マガの週次メトリクスを集約して data/kekka_weekly_metrics.json に追記"
    )
    parser.add_argument(
        "-w", "--week",
        help="ISO週 'YYYY-Www'(例 '2026-W40')。指定なしは今週",
        type=str,
    )
    parser.add_argument(
        "--api-token",
        help="note API トークン(指定なしは環境変数 NOTE_API_TOKEN から)",
        type=str,
    )
    parser.add_argument(
        "--property-id",
        help="GA4 プロパティID(指定なしは環境変数 GA4_PROPERTY_ID から)",
        type=str,
    )
    parser.add_argument(
        "--channel-id",
        help="LINE チャネルID(指定なしは環境変数から、または定数から)",
        type=str,
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="詳細ログを出力",
    )
    args = parser.parse_args()

    # ログレベル設定
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # 週の決定
    if args.week:
        week = args.week
    else:
        # 今週(ISO週で現在日時から)
        today = dt.date.today()
        iso = today.isocalendar()
        week = f"{iso.year}-W{iso.week:02d}"

    try:
        result = collect_and_save_weekly_metrics(
            week,
            api_token=args.api_token,
            property_id=args.property_id,
            channel_id=args.channel_id,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(0)
    except CollectError as e:
        logger.error(f"✗ 集約失敗: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
