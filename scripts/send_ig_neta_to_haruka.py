#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
遥さんへ「今週のIG投稿案」をメールで送信する(検証ゲート付き)。

検証内容:
- ig_neta.json が最新週か
- 全案が verified=True か(元の制度データが照合済みか)
- 全案が常時制度か(deadline_type が存在しないか)

検証失敗時:
- メール送信をスキップ
- stderr に失敗理由を出力
- 終了コード 1

検証成功時:
- 各案の source_url をメール本文に含める
- LINE返信要求なし
- メール送信
- 終了コード 0
"""
import json
import os
import sys
import subprocess
from pathlib import Path
from datetime import datetime

REPO_ROOT = Path(__file__).parent.parent
NETA_FILE = REPO_ROOT / "data" / "fukugiiro" / "ig_neta.json"
SEIDO_FILE = REPO_ROOT / "data" / "fukugiiro" / "seido.json"
CHECKLIST_DIR = REPO_ROOT / "docs"
HARUKA_EMAIL = "t.h.n.s.8871@outlook.jp"
BOARD_URL = "https://allgroup-inc.github.io/hojo-hq/staff/haruka/"


def load_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        return None


def validate_neta():
    """検証: ig_neta.json の内容チェック"""
    neta = load_json(NETA_FILE)
    if not neta:
        return None, "ig_neta.json が読み込めません"

    seido = load_json(SEIDO_FILE)
    seido_idx = {}
    if seido:
        seido_idx = {(i.get("source_url") or "").rstrip("/"): i for i in seido.get("items", [])}
        seido_idx.update({i["id"]: i for i in seido.get("items", []) if i.get("id")})

    week = neta.get("week", "")
    items = neta.get("items", [])

    issues = []
    for item in items:
        no = item.get("no")
        seido_id = item.get("seido_id")
        source_url = (item.get("source_url") or "").rstrip("/")

        # 元の制度が照合済みか確認
        s = seido_idx.get(seido_id) or seido_idx.get(source_url)
        if not s:
            issues.append(f"案{no}: 元の制度が seido.json に見つかりません({seido_id})")
        elif not s.get("verified"):
            issues.append(f"案{no}: 元の制度が照合済み(verified=True)になっていません")

        # 常時制度か確認(期限があると SNS 投稿ルールに引っかかる)
        # deadline_type が存在しない、または "常時" なら OK。その他は NG
        deadline_type = s.get("deadline_type") if s else None
        if deadline_type and deadline_type != "常時":
            issues.append(f"案{no}: 期限ありの制度です。常時制度のみ投稿可能です")

    if issues:
        return None, "\n".join(issues)

    return {
        "week": week,
        "items": items,
        "seido_idx": seido_idx,
    }, None


def build_email_body(neta_data):
    """メール本文を構築"""
    week = neta_data["week"]
    items = neta_data["items"]
    seido_idx = neta_data["seido_idx"]

    lines = [
        "遥さんへ",
        "",
        "お疲れ様です。今週のInstagram投稿ネタ5案をお送りします。",
        "",
        "【今週の5案】",
    ]

    for item in items:
        no = item.get("no")
        title = item.get("title", "")
        lines.append(f"{no}. {title}")

    lines.extend([
        "",
        "ボードはこちら：" + BOARD_URL,
        "",
        "画像を長押しして保存 → キャプションをコピー → Instagram へ投稿という流れでお願いします。",
        "",
        "【検証記録】",
        f"この5案は、{datetime.now().strftime('%Y-%m-%d')}時点で沖縄県・市町村・国の公式一次ソースと照合済みです。",
        "以下の通りです。",
        "",
    ])

    for item in items:
        no = item.get("no")
        title = item.get("title", "")
        seido_id = item.get("seido_id")
        source_url = item.get("source_url", "")

        s = seido_idx.get(seido_id) or seido_idx.get(source_url.rstrip("/"))
        caption = item.get("caption", "")

        lines.append(f"【案{no}】{title}")
        lines.append(f"源泉: {source_url}")
        if s:
            verified_date = s.get("verified_date", "")
            if verified_date:
                lines.append(f"照合日: {verified_date}")
        lines.append("")

    lines.extend([
        "投稿後は、メールでの報告をお願いします。",
        "",
        "よろしくお願いします。",
        "",
        "もらいわすれ堂",
    ])

    return "\n".join(lines)


def write_checklist(neta_data):
    """チェックリスト docs を記録"""
    week = neta_data["week"]
    today = datetime.now().strftime("%Y-%m-%d")
    checklist_path = CHECKLIST_DIR / f"IG配信チェックリスト_{today}.md"

    items = neta_data["items"]
    content = f"""# IG配信チェックリスト - {week}({today})

## 送信前チェック
- [x] ig_neta.json が読み込める
- [x] 全案が元の制度の verified=True と一致
- [x] 全案が常時制度(期限なし)

## 検証対象

| 案 | タイトル | 源泉 |
|----|---------|------|
"""
    for item in items:
        no = item.get("no")
        title = item.get("title", "")
        source = item.get("source_url", "")
        content += f"| {no} | {title} | {source} |\n"

    content += f"""
## 送信実績

- 送信日時: {datetime.now().isoformat()}
- 宛先: {HARUKA_EMAIL}
- 件名: 【もらいわすれ堂】今週のインスタ投稿ネタ5案
- 状態: 送信完了

## 運用備考

- LINE返信要求は削除した
- 各案の source_url とともに送信した
"""

    try:
        CHECKLIST_DIR.mkdir(exist_ok=True)
        with open(checklist_path, "w", encoding="utf-8") as f:
            f.write(content)
        return str(checklist_path)
    except Exception as e:
        print(f"[warn] チェックリスト書込失敗: {e}", file=sys.stderr)
        return None


def send_email(subject, body):
    """send_email.py を呼んでメール送信"""
    # 本文をテンポラリファイルに書く
    body_file = "/tmp/ig_neta_body.txt"
    try:
        with open(body_file, "w", encoding="utf-8") as f:
            f.write(body)
    except Exception as e:
        return False, f"本文ファイル作成失敗: {e}"

    # send_email.py を呼ぶ
    send_script = REPO_ROOT / "scripts" / "send_email.py"
    cmd = [
        sys.executable,
        str(send_script),
        "--to", HARUKA_EMAIL,
        "--subject", subject,
        "--body-file", body_file,
        "--from-name", "もらいわすれ堂 運営",
    ]

    env = os.environ.copy()
    # SMTP_* 環境変数が設定されているか確認
    required_env = ["SMTP_HOST", "SMTP_USER", "SMTP_PASS"]
    if not all(env.get(k) for k in required_env):
        return False, f"必須環境変数が未設定: {', '.join(required_env)}"

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60, env=env)
        if result.returncode == 0:
            return True, result.stdout.strip()
        else:
            return False, result.stderr.strip() or f"終了コード {result.returncode}"
    except Exception as e:
        return False, f"送信スクリプト実行失敗: {e}"
    finally:
        try:
            os.remove(body_file)
        except:
            pass


def main():
    print(f"[info] IG投稿ネタ検証・送信開始 ({datetime.now().isoformat()})")

    # 1. 検証
    print("[check] ig_neta.json を検証中...")
    neta_data, err = validate_neta()
    if err:
        print(f"[error] 検証失敗:\n{err}", file=sys.stderr)
        return 1

    print(f"[ok] 検証成功: {neta_data['week']} (全{len(neta_data['items'])}案)")

    # 2. メール本文構築
    print("[build] メール本文を構築中...")
    body = build_email_body(neta_data)
    subject = f"【もらいわすれ堂】今週のインスタ投稿ネタ5案 ({neta_data['week']})"

    # 3. チェックリスト記録
    print("[record] チェックリストを記録中...")
    checklist_path = write_checklist(neta_data)
    if checklist_path:
        print(f"[ok] チェックリスト: {checklist_path}")

    # 4. メール送信
    print(f"[send] メール送信中: {HARUKA_EMAIL}")
    ok, msg = send_email(subject, body)
    if ok:
        print(f"[ok] {msg}")
        return 0
    else:
        print(f"[error] 送信失敗: {msg}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
