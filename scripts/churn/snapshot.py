"""顧客データの月次スナップショット（消さずに残す仕組み）。

顧客管理画面からのエクスポートを、上書きせず月ごとに保存して履歴を積む。
これにより「初回引落結果」「接触ログ」「現ステータス」など、CRM上書きで消える
予兆データが蓄積され、半年後にはモデルが学習できるようになる（docs/churn/データ保存設計.md）。

設計原則（resilient-agent-design）:
- べき等: 同月のスナップショットが既にあれば上書きしない（履歴を壊さない）。--force で明示的に取り直し。
- 状態の外部保存: スナップショット自体が履歴＝監査ログ。manifest に取得の事実を残す。
- 完了条件: 行数・ハッシュを manifest に記録し、後から取得を検証できる。

PII（churn-pii-guard）:
- 実エクスポートは顧客個人情報。出力は private/（gitignore）配下・統制環境限定。絶対にコミットしない。
- 本番実行は守り部審査とご決裁の後。合成データ（private/demo）での検証は審査前でも可。

使い方:
  python -m scripts.churn.snapshot --csv private/demo/apps.csv \
    --interactions private/demo/inter.csv --month 2026-08 --out-dir private/snapshots
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import os
import shutil


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _rows(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return sum(1 for _ in csv.reader(f)) - 1  # ヘッダ除く


def _valid_month(m):
    parts = m.split("-")
    if len(parts) != 2 or len(parts[0]) != 4 or not (1 <= int(parts[1]) <= 12):
        raise SystemExit("--month は YYYY-MM で指定してください（PII保護のため既定値は使いません）")
    return m


def snapshot(csv_path, inter_path, month, out_dir, force=False):
    month = _valid_month(month)
    dest = os.path.join(out_dir, month)
    if os.path.exists(dest) and not force:
        # べき等: 履歴を壊さないため上書きしない
        print(f"[snapshot] {month} は既に存在します（履歴保護のためスキップ）。取り直すなら --force。→ {dest}")
        return {"status": "skipped", "dir": dest}

    os.makedirs(dest, exist_ok=True)
    files = []
    for label, src in (("apps", csv_path), ("interactions", inter_path)):
        if not src:
            continue
        if not os.path.exists(src):
            raise SystemExit(f"入力が見つかりません: {src}")
        fname = f"{label}.csv"
        shutil.copy2(src, os.path.join(dest, fname))
        files.append({"file": fname, "rows": _rows(src), "sha256": _sha256(src)})

    manifest = {
        "snapshot_id": f"snapshot:{month}",
        "as_of_month": month,
        "files": files,
        "note": "顧客個人情報を含む。private/限定・コミット禁止。",
    }
    with open(os.path.join(dest, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    total = sum(x["rows"] for x in files)
    print(f"[snapshot] {month} を保存: {len(files)}ファイル・計{total}行 → {dest}")
    return {"status": "created", "dir": dest, "manifest": manifest}


def main(argv=None):
    p = argparse.ArgumentParser(prog="churn-snapshot", description="顧客データ月次スナップショット")
    p.add_argument("--csv", required=True, help="申込台帳のCSV（顧客管理画面エクスポート）")
    p.add_argument("--interactions", help="接触ログのCSV（任意）")
    p.add_argument("--month", required=True, help="スナップショット対象月 YYYY-MM")
    p.add_argument("--out-dir", default="private/snapshots", help="保存先（private/配下）")
    p.add_argument("--force", action="store_true", help="同月が存在しても取り直す")
    a = p.parse_args(argv)
    snapshot(a.csv, a.interactions, a.month, a.out_dir, a.force)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
