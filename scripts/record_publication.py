#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hojo-hq — 公開記録+X告知の自動化(ワンタップ運用の後半)
(設計: docs/note収益化_運営計画v3_月30万.md / 2026-08-06 小柳さん指示「全自動で最終確認だけ」)

人間がnoteで記事を公開したあと、GitHub Actionsの publish-record ワークフローに
記事ID(お題ID/ファイル番号)と公開URLを入れて実行すると:
 1. 記事mdの先頭に公開記録(3役短評つき)を追記
 2. お題キューの該当お題を published に更新
 3. X告知文(記事ヘッダーのA/B/C案)を抽出して出力
    → Xシークレットがあれば post_x_announce.py が自動投稿+リプ欄にURL
    → なければLINE通知に文面を同梱(人間がコピペ投稿)

使い方:
  python scripts/record_publication.py --id 19 --url https://note.com/kekka_mag/n/xxxx [--hook a]
  出力(GITHub Actions用 key=value): article=<path> title=<...> announce=<...>
"""
import argparse
import glob
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

JST = timezone(timedelta(hours=9))
BASE = os.path.join(os.path.dirname(__file__), "..")
ARTICLE_DIR = os.path.join(BASE, "posts", "note", "tanpatsu")
TOPICS_PATH = os.path.join(BASE, "data", "tanpatsu_topics.json")


def find_article(article_id: str):
    hits = sorted(glob.glob(os.path.join(ARTICLE_DIR, f"{article_id}_*.md")))
    return hits[0] if hits else None


def extract_hooks(text: str):
    """記事ヘッダーのX告知文パック(A/B/C)を抽出する。

    2形式に対応(2026-08-08: 自動生成が【パターンA】形式のため抽出0件→X告知
    スキップになった不具合の修正):
      旧: `A(数字): 告知文`(1行)
      新: `【パターンA: 数字フック】` の次行から空行/次パターンまでが本文
    告知文は1行に正規化(GITHUB_OUTPUTのkey=value形式のため)。URLはリプ欄に
    貼る型なので、本文中の「(記事URL)」プレースホルダーは除去する。
    """
    hooks = {}
    for m in re.finditer(r"^([ABC])\([^)]*\):\s*(.+)$", text, flags=re.M):
        hooks[m.group(1).lower()] = m.group(2).strip()
    for m in re.finditer(r"^【パターン([ABC])[^】]*】\n((?:(?!【|\n\n).+\n?)+)", text, flags=re.M):
        body = " ".join(ln.strip() for ln in m.group(2).strip().splitlines())
        body = body.replace("→(記事URL)", "").replace("(記事URL)", "").strip(" →")
        hooks.setdefault(m.group(1).lower(), body)
    return hooks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", required=True, help="記事ID(例: 19)")
    ap.add_argument("--url", required=True, help="noteの公開URL")
    ap.add_argument("--hook", default="a", choices=["a", "b", "c"], help="X告知文の案(既定: a)")
    args = ap.parse_args()

    if not re.match(r"^https://note\.com/", args.url):
        print(f"エラー: noteのURLではありません: {args.url}", file=sys.stderr)
        return 1

    path = find_article(args.id)
    if not path:
        print(f"エラー: 記事ID {args.id} のファイルが見つかりません", file=sys.stderr)
        return 1

    text = open(path, encoding="utf-8").read()
    today = datetime.now(JST).date().isoformat()

    # べき等性ガード: 同じURLが記録済みなら、X告知を含む後続の副作用をすべて止める
    # (idempotency_key = 記事ID+公開URL。二重実行してもX二重投稿・二重課金にならない)
    already = f"published: {args.url}" in text
    if already:
        print("already=1")
    else:
        record = (
            f"<!-- published: {args.url} {today}(記録: publish-recordワークフロー)\n"
            "スイシン: 公開URL受領・記録済み。数字は公開前チェックリスト(規程3-1)を通過した前提\n"
            "ウタガイ: 出典抜き取り確認(2件)の実施は公開者の自己申告に依存。監査(タダス)の月次抜き取り照合の対象に含めること\n"
            "ベッカイ: 反応データ(ビュー・購入)が貯まったら、この記事の告知文パターン別の反応をKPI台帳で比較する -->\n\n"
        )
        open(path, "w", encoding="utf-8").write(record + text)

    # お題キューの更新(該当IDがあれば)
    topic_found = False
    x_already = False
    try:
        topics = json.load(open(TOPICS_PATH, encoding="utf-8"))
        for t in topics.get("queue", []):
            if t.get("id") == args.id:
                topic_found = True
                x_already = bool(t.get("x_post_url"))
                t["status"] = "published"
                t["published_url"] = args.url
                t["published_at"] = today
        json.dump(topics, open(TOPICS_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    except FileNotFoundError:
        pass

    # X告知のべき等性キーは x_post_url(X側の実行記録。2026-08-08改定)。
    # - お題に x_post_url あり → 投稿済みなので告知を出さない(二重投稿防止)
    # - キューに無い記事(手動執筆の旧記事)は published 記録の有無で代用
    # これにより「公開記録は済んだがX投稿だけ失敗/スキップ」の状態から、再実行で
    # X投稿だけをやり直せる(記録の二重追記は already ガードが引き続き防ぐ)
    suppress_x = x_already or (already and not topic_found)
    announce = ""
    if not suppress_x:
        hooks = extract_hooks(text)
        announce = hooks.get(args.hook) or hooks.get("a") or ""
        # プレースホルダー検知ガード(2026-08-23 お題13で指示文がそのままX実投稿された
        # 不具合の対策=ニドナシ台帳#16)。生成テンプレの指示文・未記入マーカーが
        # 告知文に混入していたら、成功扱いにせず失敗させて人間に知らせる
        placeholder_markers = (
            "(記事の", "(事例から", "(読者の",  # 旧build_xpackのデフォルト指示文
            "を1つ引用して", "を1行で紹介", "問いかけ形式で",
        )
        for marker in placeholder_markers:
            if marker in announce:
                print(
                    f"エラー: 告知文がプレースホルダーのままです(検知: {marker})。"
                    "お題に x_hook_a/b/c を登録するか、x-postワークフローで手動投稿してください",
                    file=sys.stderr,
                )
                return 1
        # 誇大表現の機械検査(規程3-3。告知文にも適用)
        for w in ("必ず", "絶対", "誰でも", "楽して", "確実に稼"):
            if w in announce:
                print(f"エラー: 告知文に禁止語({w})。手動で文面を直してください", file=sys.stderr)
                return 1

    title_m = re.search(r"^# (.+)$", text, flags=re.M)
    print(f"article={os.path.relpath(path, BASE)}")
    print(f"title={title_m.group(1) if title_m else ''}")
    print(f"announce={announce}")
    print(f"url={args.url}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
