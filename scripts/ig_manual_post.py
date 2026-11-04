#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ミカタ公式Instagramへの手動投稿(フィード単枚 / ストーリーズ)。
ig-feed.yml / ig-story.yml から使う(2026-11-03 GLOW Instagram 安全対策 M8・M1)。

この部品では:
  - 見本(--preview)で承認対象(本文・画像の指紋・コミットに固定した画像URL・期限)を作り、
    指紋を出す。見本には Meta の鍵を渡さない(LINE 通知の鍵だけ)
  - 承認後(--post)に同じコミットで作り直して照らし合わせ、固定URLの画像の指紋を確かめる
  - 投稿先の番号は照合用の指紋(SNS_DEST_FP_MIKATA)と一致しなければ投稿しない
  - Meta の返事はそのまま出さない

使い方:
  python scripts/ig_manual_post.py --kind feed  --image posts/x.jpg --caption-file c.txt --preview --preview-file p.txt
  python scripts/ig_manual_post.py --kind story --image posts/x.png --preview
  python scripts/ig_manual_post.py --kind feed  --image posts/x.jpg --caption-file c.txt --post \
      --approved-digest <指紋> --approved-created <作成日時>
"""
import argparse
import os
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sns_safety  # noqa: E402
from sns_safety import SafetyError  # noqa: E402

BASE = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
ACCOUNT = "ミカタ(Instagram)"
STORY_CAPTION = "(ストーリーズは本文なし)"


def current_sha():
    sha = os.environ.get("GITHUB_SHA", "").strip()
    if sha:
        return sha
    import subprocess
    r = subprocess.run(["git", "-C", BASE, "rev-parse", "HEAD"], capture_output=True, text=True)
    return r.stdout.strip()


def read_caption(args):
    if args.kind == "story":
        return STORY_CAPTION
    if not args.caption_file:
        raise SafetyError("フィード投稿には本文(--caption-file)が必要です")
    with open(args.caption_file, encoding="utf-8") as f:
        return f.read().strip()


def make_package(args, caption, created=None):
    return sns_safety.build_package(
        account=ACCOUNT, kind=args.kind, caption=caption, images=[args.image],
        sha=current_sha(), base_dir=BASE, created_at=created, stem=None)


def publish(args, pkg, caption, opener=None, sleep=time.sleep):
    token = os.environ.get("FB_PAGE_ACCESS_TOKEN", "")
    ig_user = os.environ.get("IG_USER_ID", "")
    if not (token and ig_user):
        raise SafetyError("投稿用の設定(FB_PAGE_ACCESS_TOKEN / IG_USER_ID)が揃っていません")
    sns_safety.check_destination(os.environ.get("SNS_DEST_FP_MIKATA", ""), ig_user)
    url = pkg["images"][0]["url"]
    params = {"image_url": url, "access_token": token}
    if args.kind == "story":
        params["media_type"] = "STORIES"
    else:
        params["caption"] = caption
    c = sns_safety.meta_post(f"/{ig_user}/media", params, opener=opener)
    cid = c.get("id")
    if not cid:
        raise SafetyError("投稿の準備(コンテナ作成)の返事に番号がありません")
    last = None
    for _ in range(3):
        sleep(5)
        try:
            sns_safety.meta_post(f"/{ig_user}/media_publish",
                                 {"creation_id": cid, "access_token": token}, opener=opener)
            return
        except SafetyError as e:
            last = e
    raise SafetyError(f"公開に失敗しました: {last}")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", choices=["feed", "story"], required=True)
    ap.add_argument("--image", required=True)
    ap.add_argument("--caption-file")
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preview", action="store_true")
    mode.add_argument("--post", action="store_true")
    ap.add_argument("--preview-file")
    ap.add_argument("--approved-digest")
    ap.add_argument("--approved-created")
    args = ap.parse_args(argv)

    try:
        caption = read_caption(args)
        if args.preview:
            pkg = make_package(args, caption)
            digest = sns_safety.package_digest(pkg)
            print(f"pkg_digest={digest}")
            print(f"pkg_created={pkg['created_at']}")
            print(f"image={pkg['images'][0]['url']}")
            if args.preview_file:
                with open(args.preview_file, "w", encoding="utf-8") as f:
                    f.write("\n".join(sns_safety.preview_lines(pkg, digest, caption)) + "\n")
            return 0
        if not (args.approved_digest and args.approved_created):
            raise SafetyError("承認された指紋と作成日時が渡されていません")
        try:
            created = datetime.fromisoformat(args.approved_created)
        except ValueError:
            raise SafetyError("承認対象の作成日時を読めません") from None
        pkg = make_package(args, caption, created)
        sns_safety.verify_before_publish(pkg, args.approved_digest)
        publish(args, pkg, caption)
        print(f"[ok] {'ストーリーズ' if args.kind == 'story' else 'フィード'}投稿 完了")
        return 0
    except SafetyError as e:
        print(f"[ng] 投稿しません: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
