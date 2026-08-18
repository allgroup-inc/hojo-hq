#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hojo-hq — SNS自動投稿(Facebookページ+Instagram)
議事_20260730(議題2「構築を進める」)の実装。

- 投稿素材は generate_sns.py / generate_images.py が生成済みの
  posts/launch/<nn>_<slug>.md(キャプション) + posts/images/<nn>_<slug>.png(画像)
  をそのまま使う(締切3層ルール・原文照合はスクリプト側で担保済み)
- 選定: 日付ローテーション(同じ日は同じ投稿=再実行しても二重投稿しにくい)
- Secrets未設定時は「未接続」と明記してスキップ(静かに欠損させない)

必要なSecrets(Meta Business Suite連携後に登録):
  FB_PAGE_ID / FB_PAGE_ACCESS_TOKEN / IG_USER_ID
使い方:
  python scripts/post_social.py                  # 本番投稿(Secrets必須・その場で選定)
  python scripts/post_social.py --stem 09_cta    # 承認済みの素材を名指しで投稿(推奨)
  python scripts/post_social.py --dry-run        # 選定とキャプションの確認のみ
  python scripts/post_social.py --preview        # GitHub Actions用: key=value形式で本日の素材を出力

承認(sns-approval)から投稿までに日付が変わると、再選定では別の素材が選ばれる。
実際に 2026-08-14(金)にカルーセルを承認 → 08-15(土)に通常投稿が出ていた
(監査 2026-W34 §4)。ワークフローは必ず --stem でプレビューの選定結果を渡すこと。
"""
import glob
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone

import shipping_gate

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

BASE = os.path.join(os.path.dirname(__file__), "..")
RAW_BASE = "https://raw.githubusercontent.com/allgroup-inc/hojo-hq/main/posts/images/"
GRAPH = "https://graph.facebook.com/v21.0"
JST = timezone(timedelta(hours=9))
STATE_PATH = os.path.join(BASE, "data", "social_post_state.json")


def load_state(today, stem):
    """本日・本日の投稿素材と一致する状態のみ有効(resilient-agent-design: べき等性)。
    Facebook投稿後にInstagramが失敗し、job再実行された場合にFacebookへ二重投稿しない。"""
    try:
        with open(STATE_PATH, encoding="utf-8") as f:
            state = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"date": today, "stem": stem, "facebook": False, "instagram": False}
    if state.get("date") != today or state.get("stem") != stem:
        return {"date": today, "stem": stem, "facebook": False, "instagram": False}
    return state


def save_state(state):
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


CAROUSEL_DIR = os.path.join(BASE, "posts", "carousel")
RAW_CAROUSEL = "https://raw.githubusercontent.com/allgroup-inc/hojo-hq/main/posts/carousel/"


def carousel_today():
    """金曜はカルーセル投稿(carousel-writerスキル準拠・保存狙いの週1枠)。
    素材(caption.md+slide_*.png)が揃っている場合のみ。無ければ通常投稿へフォールバック。

    注意: これは**選定(プレビュー)専用**。投稿側は --stem で承認済みの素材を名指しする
    (日付が変わると判定が変わり、承認したものと違う投稿が出るため)。"""
    if datetime.now(JST).weekday() != 4:  # 金曜のみ
        return None
    return carousel_materials()


def pick_post():
    """日付でローテーション選定。md と png が揃っている素材のみ対象。"""
    mds = sorted(glob.glob(os.path.join(BASE, "posts", "launch", "*.md")))
    pairs = []
    for md in mds:
        stem = os.path.splitext(os.path.basename(md))[0]
        png = os.path.join(BASE, "posts", "images", stem + ".png")
        if os.path.exists(png):
            pairs.append((md, stem))
    if not pairs:
        raise SystemExit("[ng] 投稿素材が見つかりません(posts/launch + posts/images)")
    idx = date.today().toordinal() % len(pairs)
    return pairs[idx]


def extract_caption(md_path):
    text = open(md_path, encoding="utf-8").read()
    m = re.search(r"## キャプション\n(.*?)(?:\n## |\Z)", text, re.S)
    if not m:
        raise SystemExit(f"[ng] キャプション欄が見つかりません: {md_path}")
    return m.group(1).strip()


def gate_or_die(md_path):
    """出荷ゲート(運用規程1-3)の通過記録を確認する。無ければ**投稿しない**。

    resilient-agent-design: 確認できないときは進めずに止まる(フェイルクローズ)。
    黙ってスキップせず異常終了させ、GitHub Actionsを赤くして気づけるようにする。
    """
    ok, problems, warnings = shipping_gate.verify_file(md_path)
    for w in warnings:
        print(f"[warn] 出荷ゲート: {w}")
    if ok:
        return
    print("[ng] 出荷ゲート未通過のため投稿を中止します(運用規程1-3)")
    for p in problems:
        print(f"  - {p}")
    print("  対応: 文面を hojo-accuracy-check → hojo-deadline-alert → humanizer で見直し、")
    print("        生成器の GATE_CHECKED を更新してから再実行してください")
    raise SystemExit(1)


def api(path, params):
    data = urllib.parse.urlencode(params).encode("utf-8")
    req = urllib.request.Request(GRAPH + path, data=data, method="POST")
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def carousel_materials():
    """カルーセル素材(caption.md + slide_*.png)。揃っていなければ None。"""
    cap = os.path.join(CAROUSEL_DIR, "caption.md")
    slides = sorted(glob.glob(os.path.join(CAROUSEL_DIR, "slide_*.png")))
    if os.path.exists(cap) and len(slides) >= 3:
        return cap, [RAW_CAROUSEL + os.path.basename(s) for s in slides]
    return None


def resolve_stem(stem):
    """プレビューで承認された素材を名指しで解決する(--stem)。

    承認から投稿までに日付が変わると、再選定では別の素材になってしまう
    (pick_post は日付ローテーション / carousel_today は金曜判定)。
    実際に 2026-08-14(金)承認 → 08-15(土)投稿 で、承認したカルーセルではなく
    通常投稿が出ていた(監査 2026-W34 §4)。承認したものと違うものを出さないため、
    素材が見つからないときは**投稿しない**(フェイルクローズ)。
    """
    if stem == "carousel":
        car = carousel_materials()
        if not car:
            raise SystemExit("[ng] 承認された素材(carousel)が見つかりません。投稿を中止します")
        return car[0], "carousel", car[1]
    md = os.path.join(BASE, "posts", "launch", stem + ".md")
    png = os.path.join(BASE, "posts", "images", stem + ".png")
    if not (os.path.exists(md) and os.path.exists(png)):
        raise SystemExit(f"[ng] 承認された素材({stem})が見つかりません。投稿を中止します")
    return md, stem, None


def main():
    dry = "--dry-run" in sys.argv
    approved = None
    if "--stem" in sys.argv:
        i = sys.argv.index("--stem")
        approved = sys.argv[i + 1] if i + 1 < len(sys.argv) else ""

    if approved:
        # 承認済みの素材を名指しで使う(再選定しない)
        md, stem, slide_urls = resolve_stem(approved)
        caption = extract_caption(md)
        image_url = slide_urls[0] if slide_urls else RAW_BASE + stem + ".png"
    else:
        car = carousel_today()
        if car:
            md, slide_urls = car
            stem = "carousel"
            caption = extract_caption(md)
            image_url = slide_urls[0]  # プレビューは表紙
        else:
            slide_urls = None
            md, stem = pick_post()
            caption = extract_caption(md)
            image_url = RAW_BASE + stem + ".png"
    now = datetime.now(JST).strftime("%Y-%m-%d %H:%M")

    if "--preview" in sys.argv:
        # GitHub Actionsのstep outputs用(小柳さんへのデザイン確認LINEに使う)
        print(f"stem={stem}")
        print(f"image={image_url}")
        print(f"caption_head={caption.splitlines()[0]}")
        if slide_urls:
            print(f"slides={len(slide_urls)}")
        # 出荷ゲートの見込みも先に出す(投稿段階で落ちる前に気づけるように)
        gate_ok, _, _ = shipping_gate.verify_file(md)
        print(f"gate={'ok' if gate_ok else 'ng'}")
        return

    print(f"[info] {now} JST / 本日の投稿素材: {stem}")
    print(f"[info] 画像: {image_url}")
    print("[info] キャプション先頭: " + caption.splitlines()[0])

    # 出荷ゲート: 通過記録が無い/古い/禁止表現がある文面は外に出さない
    gate_or_die(md)

    if dry:
        print("[ok] dry-run: 出荷ゲート通過・選定とキャプション抽出のみ実施(投稿なし)")
        return

    page_id = os.environ.get("FB_PAGE_ID", "")
    token = os.environ.get("FB_PAGE_ACCESS_TOKEN", "")
    ig_user = os.environ.get("IG_USER_ID", "")

    today = date.today().isoformat()
    state = load_state(today, stem)
    posted = []

    if state.get("facebook"):
        print("[skip] Facebook: 本日分は投稿済み(state記録済み・二重投稿防止)")
    elif page_id and token:
        if slide_urls:
            # カルーセル→FBは複数写真の1投稿(unpublishedでアップ→feedにattach)
            media_ids = []
            for u in slide_urls:
                r = api(f"/{page_id}/photos",
                        {"url": u, "published": "false", "access_token": token})
                media_ids.append(r["id"])
            params = {"message": caption, "access_token": token}
            for i, mid in enumerate(media_ids):
                params[f"attached_media[{i}]"] = json.dumps({"media_fbid": mid})
            res = api(f"/{page_id}/feed", params)
            print(f"[ok] Facebook複数写真投稿 完了({len(media_ids)}枚): id={res.get('id')}")
        else:
            res = api(f"/{page_id}/photos",
                      {"url": image_url, "caption": caption, "access_token": token})
            print(f"[ok] Facebook投稿 完了: id={res.get('id') or res.get('post_id')}")
        posted.append("facebook")
        state["facebook"] = True
        save_state(state)
    else:
        print("[skip] Facebook: 未接続(FB_PAGE_ID / FB_PAGE_ACCESS_TOKEN 未設定)")

    if state.get("instagram"):
        print("[skip] Instagram: 本日分は投稿済み(state記録済み・二重投稿防止)")
    elif ig_user and token:
        if slide_urls:
            # IGカルーセル: 子コンテナ(is_carousel_item)→CAROUSEL親→publish
            children = []
            for u in slide_urls:
                c = api(f"/{ig_user}/media",
                        {"image_url": u, "is_carousel_item": "true", "access_token": token})
                children.append(c["id"])
            c = api(f"/{ig_user}/media",
                    {"media_type": "CAROUSEL", "children": ",".join(children),
                     "caption": caption, "access_token": token})
        else:
            c = api(f"/{ig_user}/media",
                    {"image_url": image_url, "caption": caption, "access_token": token})
        creation_id = c["id"]
        last_err = None
        for _ in range(3):  # コンテナ処理待ちを考慮して公開を最大3回試行
            try:
                pub = api(f"/{ig_user}/media_publish",
                          {"creation_id": creation_id, "access_token": token})
                print(f"[ok] Instagram投稿 完了: id={pub.get('id')}")
                posted.append("instagram")
                state["instagram"] = True
                save_state(state)
                last_err = None
                break
            except Exception as e:  # noqa: BLE001
                last_err = e
                time.sleep(10)
        if last_err:
            raise SystemExit(f"[ng] Instagram公開に失敗: {last_err}")
    else:
        print("[skip] Instagram: 未接続(IG_USER_ID 未設定)")

    if not posted and not (state.get("facebook") or state.get("instagram")):
        print("[warn] どのSNSにも未接続のため投稿は行われていません(Meta連携後にSecretsを登録してください)")


if __name__ == "__main__":
    main()
