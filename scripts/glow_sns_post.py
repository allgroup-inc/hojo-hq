#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GLOW「世界の懸け橋」の Facebook ページ / Instagram に、posts/glow/ の投稿を順番に1本ずつ出す。

  python scripts/glow_sns_post.py --status    # つながっているページ・IGアカウントを表示するだけ(投稿しない)
  python scripts/glow_sns_post.py --dry-run   # 次に出す投稿を選び、出荷ゲートを検査するだけ(投稿しない)
  python scripts/glow_sns_post.py             # 投稿する(ワークフロー glow-sns-post が月水金に実行)

必要な Secret は1つだけ: GLOW_FB_PAGE_TOKEN(GLOWのFacebookページの長期ページアクセストークン)。
ページIDとInstagramのIDはトークンから自動で調べる。ページ名に「GLOW」が無ければ投稿しない
(ミカタのページのトークンを誤って入れても、ミカタ側に投稿されないようにするため)。

順番は posts/glow/order.json、どこまで出したかは data/glow_sns_state.json に記録する。
最後まで出したら先頭に戻る。FBとIGの片方だけ成功した場合は、次の回にもう片方だけ出し直す(二重投稿しない)。
"""
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import shipping_gate  # noqa: E402

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
POSTS = os.path.join(BASE, "posts", "glow")
STATE = os.path.join(BASE, "data", "glow_sns_state.json")
RAW = "https://raw.githubusercontent.com/allgroup-inc/hojo-hq/main/posts/glow/"
GRAPH = "https://graph.facebook.com/v21.0"
JST = timezone(timedelta(hours=9))
PAGE_NAME_MUST_HAVE = "GLOW"


class GraphError(Exception):
    pass


def graph(method, path, params):
    q = urllib.parse.urlencode(params)
    if method == "GET":
        req = urllib.request.Request(f"{GRAPH}{path}?{q}")
    else:
        req = urllib.request.Request(GRAPH + path, data=q.encode("utf-8"), method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        # トークンがログに出ないよう、エラー本文だけを返す
        raise GraphError(f"HTTP {e.code} {path}: {body[:400]}") from None


def load_state():
    if os.path.exists(STATE):
        with open(STATE, encoding="utf-8") as f:
            return json.load(f)
    return {"next": 0, "pending": None, "history": []}


def save_state(st):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    with open(STATE, "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, indent=1)


def order():
    with open(os.path.join(POSTS, "order.json"), encoding="utf-8") as f:
        return json.load(f)


def pick(st):
    """出す投稿を決める。片方だけ出た投稿が残っていれば、それを名指しで続ける。"""
    if st.get("pending"):
        return st["pending"]["id"]
    ids = order()
    return ids[st.get("next", 0) % len(ids)]


def caption_of(pid):
    md = os.path.join(POSTS, pid + ".md")
    with open(md, encoding="utf-8") as f:
        text = f.read()
    m = re.search(r"## キャプション\n(.*?)(?:\n## |\Z)", text, re.S)
    if not m:
        raise SystemExit(f"[ng] キャプション欄が見つかりません: {md}")
    return md, m.group(1).strip()


def ig_caption(fb_caption):
    """IGのキャプション内URLは押せないため、URLの案内をプロフィールのリンクへ置き換える。"""
    out = re.sub(r"\n\n▶ くわしく.*?(?=\n\n#)", "\n\n▶ くわしくは、プロフィールのリンクから", fb_caption, flags=re.S)
    assert "http" not in out, "IGのキャプションにURLが残っています"
    return out


def connect(token):
    me = graph("GET", "/me", {"fields": "id,name", "access_token": token})
    page_id, name = me["id"], me.get("name", "")
    if PAGE_NAME_MUST_HAVE.lower() not in name.lower():
        raise SystemExit(f"[ng] トークンのページ名が「{name}」です。GLOWのページではないため投稿しません")
    ig = graph("GET", f"/{page_id}", {"fields": "instagram_business_account{id,username}", "access_token": token})
    iga = ig.get("instagram_business_account") or {}
    return page_id, name, iga.get("id"), iga.get("username")


def post_facebook(page_id, token, image_url, cap):
    r = graph("POST", f"/{page_id}/photos", {"url": image_url, "caption": cap, "access_token": token})
    return r.get("post_id") or r.get("id")


def post_instagram(ig_id, token, image_url, cap):
    c = graph("POST", f"/{ig_id}/media", {"image_url": image_url, "caption": cap, "access_token": token})
    cid = c["id"]
    for _ in range(12):  # 画像の取り込み完了を最大約1分待つ
        s = graph("GET", f"/{cid}", {"fields": "status_code", "access_token": token})
        if s.get("status_code") == "FINISHED":
            break
        if s.get("status_code") == "ERROR":
            raise GraphError(f"Instagramの画像取り込みに失敗: {s}")
        time.sleep(5)
    r = graph("POST", f"/{ig_id}/media_publish", {"creation_id": cid, "access_token": token})
    return r.get("id")


def gh_output(**kv):
    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with open(path, "a", encoding="utf-8") as f:
            for k, v in kv.items():
                f.write(f"{k}={v}\n")


def main():
    token = os.environ.get("GLOW_FB_PAGE_TOKEN", "").strip()
    if "--status" in sys.argv:
        if not token:
            print("[info] 未接続: Secret GLOW_FB_PAGE_TOKEN が未登録です")
            return
        page_id, name, ig_id, ig_user = connect(token)
        print(f"[ok] Facebookページ: {name}(ID {page_id})")
        print(f"[ok] Instagram: @{ig_user}(ID {ig_id})" if ig_id else
              "[warn] Instagramがページにつながっていません(Meta Business Suiteでリンクしてください)")
        return

    st = load_state()
    pid = pick(st)
    md, cap = caption_of(pid)
    image_url = RAW + pid + ".jpg"
    if not os.path.exists(os.path.join(POSTS, pid + ".jpg")):
        raise SystemExit(f"[ng] 画像がありません: posts/glow/{pid}.jpg")
    print(f"[info] 今回の投稿: {pid}")
    print(f"[info] 画像: {image_url}")
    print("[info] 文頭: " + cap.splitlines()[0])

    ok, problems, warnings = shipping_gate.verify_file(md)
    for w in warnings:
        print(f"[warn] 出荷ゲート: {w}")
    if not ok:
        print("[ng] 出荷ゲート未通過のため投稿しません")
        for p in problems:
            print("  - " + p)
        raise SystemExit(1)
    igcap = ig_caption(cap)
    gh_output(post_id=pid, head=cap.splitlines()[0][:60])

    if "--dry-run" in sys.argv:
        print("[ok] dry-run: 選定と出荷ゲート検査のみ(投稿なし)")
        return
    if not token:
        print("[info] 未接続のため投稿しません(Secret GLOW_FB_PAGE_TOKEN を登録すると動き出します)")
        gh_output(connected="no")
        return

    page_id, name, ig_id, ig_user = connect(token)
    pend = st.get("pending") or {"id": pid, "facebook": None, "instagram": None}
    errors = []
    if not pend.get("facebook"):
        try:
            pend["facebook"] = post_facebook(page_id, token, image_url, cap)
            print(f"[ok] Facebook({name})に投稿: {pend['facebook']}")
        except GraphError as e:
            errors.append(f"Facebook: {e}")
    if ig_id and not pend.get("instagram"):
        try:
            pend["instagram"] = post_instagram(ig_id, token, image_url, igcap)
            print(f"[ok] Instagram(@{ig_user})に投稿: {pend['instagram']}")
        except GraphError as e:
            errors.append(f"Instagram: {e}")
    elif not ig_id:
        print("[warn] Instagramがページにつながっていないため、Facebookのみ投稿")

    done = pend.get("facebook") and (pend.get("instagram") or not ig_id)
    if done:
        st["pending"] = None
        st["next"] = (order().index(pid) + 1) % len(order())
        st.setdefault("history", []).append({
            "date": datetime.now(JST).strftime("%Y-%m-%d %H:%M"), "id": pid,
            "facebook": pend.get("facebook"), "instagram": pend.get("instagram")})
        st["history"] = st["history"][-200:]
    else:
        st["pending"] = pend
    save_state(st)
    gh_output(connected="yes", ig=f"@{ig_user}" if ig_user else "未接続")
    if errors:
        for e in errors:
            print("[ng] " + e)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
