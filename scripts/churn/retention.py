"""保持期限の確実削除（守り部審査 #142 項目3）。

月次スナップショット（`snapshot.py`）を、保持年数を過ぎたら確実に削除する。
「消さずに残す」の裏返しの規律＝**期限が来たら確実に消す**（個人情報の保持最小化）。

設計（resilient-agent-design）:
- 安全側の既定: **ドライラン（apply=False）**。何を消すかを出すだけで、実削除しない。
  実削除は `apply=True` を明示したときだけ（破壊的操作は明示的オプトイン）。
- べき等: 既に無い月は対象にならない。二度実行しても増えない。
- 完了条件・監査ログ: 削除した事実を `deletion_log.json` に追記（月・行数・sha256・削除基準日）。
  監査（テキホウさん）が後から「いつ何を消したか」を独立点検できる。**顧客の値は残さない**（PII非出力）。
- 満期判定はカレンダー基準: 取得月 + 保持年数 に達したら満期（例: 2020-08取得・6年→2026-08で満期）。

PII（churn-pii-guard）: 実データの削除は統制環境（hojo-churn）で・審査後に運用する。
`deletion_log.json` は集計（件数・ハッシュ）のみ。個人の値を書かない。

使い方:
  # まず何が消えるか確認（ドライラン）
  python -m scripts.churn.retention --dir private/snapshots --as-of 2026-08-01
  # 実削除（明示）
  python -m scripts.churn.retention --dir private/snapshots --as-of 2026-08-01 --apply
"""
from __future__ import annotations
import argparse
import json
import os
import re
import shutil

from .config import SNAPSHOT_RETENTION_YEARS

_MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def _month_index(y, m):
    return y * 12 + (m - 1)


def _is_expired(month, as_of, retention_years):
    y, m = (int(p) for p in month.split("-"))
    matured_idx = _month_index(y, m) + retention_years * 12
    return _month_index(as_of.year, as_of.month) >= matured_idx


def _manifest_files(month_dir):
    path = os.path.join(month_dir, "manifest.json")
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f).get("files", [])


def _append_log(snapshots_dir, entry):
    path = os.path.join(snapshots_dir, "deletion_log.json")
    log = []
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            log = json.load(f)
    log.append(entry)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)


def purge_snapshots(snapshots_dir, as_of, retention_years=SNAPSHOT_RETENTION_YEARS, apply=False):
    """満期を過ぎた月次スナップショットを列挙（apply=Trueで実削除＋監査ログ追記）。"""
    if not os.path.isdir(snapshots_dir):
        return {"expired": [], "deleted": [], "kept": 0, "apply": apply,
                "retention_years": retention_years}

    months = sorted(m for m in os.listdir(snapshots_dir)
                    if _MONTH_RE.match(m) and os.path.isdir(os.path.join(snapshots_dir, m)))
    expired = [m for m in months if _is_expired(m, as_of, retention_years)]
    kept = len(months) - len(expired)

    deleted = []
    if apply:
        for month in expired:
            month_dir = os.path.join(snapshots_dir, month)
            files = _manifest_files(month_dir)
            shutil.rmtree(month_dir)
            _append_log(snapshots_dir, {
                "month": month,
                "purged_as_of": as_of.isoformat(),
                "retention_years": retention_years,
                "files": files,   # 件数・sha256のみ（manifest由来・PII非出力）
            })
            deleted.append(month)

    return {"expired": expired, "deleted": deleted, "kept": kept,
            "apply": apply, "retention_years": retention_years}


def _as_of(value):
    if not value:
        raise SystemExit("--as-of は YYYY-MM-DD で指定してください")
    from datetime import date
    y, m, d = (int(p) for p in value.split("-"))
    return date(y, m, d)


def main(argv=None):
    p = argparse.ArgumentParser(prog="churn-retention",
                                description="月次スナップショットの保持期限削除（既定ドライラン）")
    p.add_argument("--dir", required=True, help="スナップショット保存先（private/配下）")
    p.add_argument("--as-of", required=True, help="削除基準日 YYYY-MM-DD")
    p.add_argument("--years", type=int, default=SNAPSHOT_RETENTION_YEARS, help="保持年数")
    p.add_argument("--apply", action="store_true", help="実削除する（未指定はドライラン）")
    a = p.parse_args(argv)
    rep = purge_snapshots(a.dir, _as_of(a.as_of), a.years, a.apply)
    mode = "実削除" if a.apply else "ドライラン（消しません）"
    print(f"[retention] {mode} 保持{rep['retention_years']}年 "
          f"満期{len(rep['expired'])}件 保持継続{rep['kept']}件")
    if rep["expired"]:
        print(f"  ・満期: {rep['expired']}")
    if a.apply:
        print(f"  ・削除済: {rep['deleted']} → deletion_log.json に記録")
    elif rep["expired"]:
        print("  ※実削除は --apply を付けて実行してください")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
