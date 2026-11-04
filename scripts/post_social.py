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
  python scripts/post_social.py --stem 09_cta --approved-digest <指紋> --approved-created <作成日時>
                                                 # 本番投稿(承認済みの素材と承認対象の指紋が必須)
  python scripts/post_social.py --dry-run        # 選定・検査・承認対象の作成のみ(投稿なし)
  python scripts/post_social.py --preview [--preview-file PATH]
                                                 # GitHub Actions用: key=value形式で本日の素材を出力

安全対策(2026-11-03 GLOW Instagram 安全対策 M1・M2):
- 承認対象(本文・画像の指紋・コミットに固定した画像URL・投稿先の種別・期限)をひとまとめにし、
  プレビューで指紋を出す。投稿側は同じコミットで作り直して指紋を照らし合わせ、
  固定URLから画像を取り直して指紋を確かめる。1つでも違えば投稿しない。
- 出典の制度が、原文照合から72時間以内で、公募要領・募集状況・締切の3点が原文と一致して
  いなければ投稿しない(scripts/sns_safety.py の check_seido)。
- 投稿先の番号は、照合用の指紋(環境変数 SNS_DEST_FP_MIKATA)と一致しなければ投稿しない。
- Meta の返事やエラーはそのまま出さない(HTTPステータスとエラー番号だけ)。
- その場での選定による本番投稿はできない(--stem と --approved-digest が必須)。

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
import sns_safety
from sns_safety import SafetyError

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

BASE = os.path.join(os.path.dirname(__file__), "..")
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
SUBSIDIES_PATH = os.path.join(BASE, "data", "subsidies.json")
ACCOUNT = "ミカタ(Facebookページ+Instagram)"


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
    """Meta への投稿。失敗しても返事の本文は出さない(sns_safety.meta_post)。"""
    return sns_safety.meta_post(path, params, graph=GRAPH)


def current_sha():
    """画像を固定するコミット。GitHub Actions では GITHUB_SHA、手元では HEAD。"""
    sha = os.environ.get("GITHUB_SHA", "").strip()
    if sha:
        return sha
    import subprocess
    r = subprocess.run(["git", "-C", BASE, "rev-parse", "HEAD"], capture_output=True, text=True)
    return r.stdout.strip()


def load_subsidies():
    try:
        with open(SUBSIDIES_PATH, encoding="utf-8") as f:
            d = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None
    return d.get("items") if isinstance(d, dict) else d


def seido_problems(md):
    subs = load_subsidies()
    if subs is None:
        return ["掲載データ(data/subsidies.json)を読めません"]
    return sns_safety.check_seido(open(md, encoding="utf-8").read(), subs)


def build_package(md, stem, image_rels, caption, sha, created_at=None):
    return sns_safety.build_package(
        account=ACCOUNT, kind="carousel" if stem == "carousel" else "single",
        caption=caption, images=image_rels, sha=sha, base_dir=BASE, stem=stem,
        created_at=created_at)


def carousel_materials():
    """カルーセル素材(caption.md + slide_*.png)。揃っていなければ None。"""
    cap = os.path.join(CAROUSEL_DIR, "caption.md")
    slides = sorted(glob.glob(os.path.join(CAROUSEL_DIR, "slide_*.png")))
    if os.path.exists(cap) and len(slides) >= 3:
        return cap, ["posts/carousel/" + os.path.basename(s) for s in slides]
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


def _arg(name):
    if name in sys.argv:
        i = sys.argv.index(name)
        return sys.argv[i + 1] if i + 1 < len(sys.argv) else ""
    return None


def select(approved):
    """(md, stem, 画像の相対パスの並び)。approved があれば名指し、無ければ本日の選定。"""
    if approved:
        md, stem, slides = resolve_stem(approved)
    else:
        car = carousel_today()
        if car:
            md, slides = car
            stem = "carousel"
        else:
            md, stem = pick_post()
            slides = None
    rels = slides if slides else [f"posts/images/{stem}.png"]
    return md, stem, rels


def main():
    dry = "--dry-run" in sys.argv
    preview = "--preview" in sys.argv
    approved = _arg("--stem")
    approved_digest = _arg("--approved-digest")
    approved_created = _arg("--approved-created")

    if not (dry or preview) and not (approved and approved_digest and approved_created):
        # その場で選び直して投稿すると、承認したものと違うものが出る(監査 2026-W34 §4)
        raise SystemExit("[ng] 本番投稿には --stem・--approved-digest・--approved-created が必要です(承認対象を確定できないため投稿しません)")

    md, stem, rels = select(approved)
    caption = extract_caption(md)
    sha = current_sha()
    created = None
    if approved_created:
        try:
            created = datetime.fromisoformat(approved_created)
        except ValueError:
            raise SystemExit("[ng] 承認対象の作成日時を読めません") from None
    try:
        pkg = build_package(md, stem, rels, caption, sha, created_at=created)
    except SafetyError as e:
        if preview:
            print("stem=" + stem)
            print("pkg=ng")
            print("pkg_digest=")
            print("seido=ng")
            print("gate=ng")
            print(f"[ng] 承認対象を作れません: {e}", file=sys.stderr)
            return
        raise SystemExit(f"[ng] 承認対象を作れません: {e}")
    digest = sns_safety.package_digest(pkg)
    image_urls = [img["url"] for img in pkg["images"]]
    slide_urls = image_urls if stem == "carousel" else None
    image_url = image_urls[0]
    now = datetime.now(JST).strftime("%Y-%m-%d %H:%M")
    problems = seido_problems(md)

    if preview:
        # GitHub Actionsのstep outputs用(小柳さんへのデザイン確認LINEに使う)
        print(f"stem={stem}")
        print(f"image={image_url}")
        print(f"caption_head={caption.splitlines()[0]}")
        if slide_urls:
            print(f"slides={len(slide_urls)}")
        gate_ok, _, _ = shipping_gate.verify_file(md)
        print(f"gate={'ok' if gate_ok else 'ng'}")
        print("pkg=ok")
        print(f"pkg_digest={digest}")
        print(f"pkg_created={pkg['created_at']}")
        print(f"pkg_expires={pkg['expires_at']}")
        print(f"seido={'ok' if not problems else 'ng'}")
        out = _arg("--preview-file")
        if out:
            lines = sns_safety.preview_lines(pkg, digest, caption)
            if problems:
                lines.insert(0, "⛔ 制度情報の確認が済んでいないため、承認しても投稿されません:")
                for p in problems[:8]:
                    lines.insert(1, "・" + p)
            with open(out, "w", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")
        return

    print(f"[info] {now} JST / 投稿素材: {stem}")
    print(f"[info] 画像(コミット固定): {image_url}")
    print(f"[info] 承認対象の指紋: {digest[:12]}")
    print("[info] キャプション先頭: " + caption.splitlines()[0])

    # 出荷ゲート: 通過記録が無い/古い/禁止表現がある文面は外に出さない
    gate_or_die(md)

    # 制度情報の確認(M2): 確認できないものは「要確認」で出すのではなく、投稿しない
    if problems:
        print("[ng] 制度情報の確認が済んでいないため投稿しません(原文の公募要領・募集状況・締切)")
        for p in problems:
            print(f"  - {p}")
        raise SystemExit(1)

    if dry:
        print("[ok] dry-run: 出荷ゲート・制度確認を通過、承認対象を作成(投稿なし)")
        return

    # 承認対象の照合(M1): 承認された中身と同じか・期限内か・固定URLの画像が同じか
    try:
        sns_safety.verify_before_publish(pkg, approved_digest)
    except SafetyError as e:
        raise SystemExit(f"[ng] 投稿の直前の照合で止めました: {e}")

    page_id = os.environ.get("FB_PAGE_ID", "")
    token = os.environ.get("FB_PAGE_ACCESS_TOKEN", "")
    ig_user = os.environ.get("IG_USER_ID", "")
    if not (page_id and token and ig_user):
        raise SystemExit("[ng] 投稿用の設定(FB_PAGE_ID / FB_PAGE_ACCESS_TOKEN / IG_USER_ID)が揃っていません")
    try:
        sns_safety.check_destination(os.environ.get("SNS_DEST_FP_MIKATA", ""), page_id, ig_user)
    except SafetyError as e:
        raise SystemExit(f"[ng] 投稿先の照合で止めました: {e}")

    today = date.today().isoformat()
    state = load_state(today, stem)
    try:
        _publish(state, page_id, token, ig_user, caption, image_url, slide_urls)
    except SafetyError as e:
        raise SystemExit(f"[ng] {e}")


def _publish(state, page_id, token, ig_user, caption, image_url, slide_urls):
    if state.get("facebook"):
        print("[skip] Facebook: 本日分は投稿済み(state記録済み・二重投稿防止)")
    else:
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
            api(f"/{page_id}/feed", params)
            print(f"[ok] Facebook複数写真投稿 完了({len(media_ids)}枚)")
        else:
            api(f"/{page_id}/photos",
                {"url": image_url, "caption": caption, "access_token": token})
            print("[ok] Facebook投稿 完了")
        state["facebook"] = True
        save_state(state)

    # IGのキャプション内URLはタップできない(リンク化されるのはプロフィール欄と
    # ストーリーズのスタンプのみ)。サイトURLの行を「プロフィールのリンクから」に
    # 置き換える(2026-09-01 小柳さん指摘)。制度の原文URLは情報として残す。
    ig_caption = re.sub(
        r"^https://allgroup-inc\.github\.io/hojo-hq/\S*$",
        "プロフィールのリンクからどうぞ",
        caption, flags=re.M)

    if state.get("instagram"):
        print("[skip] Instagram: 本日分は投稿済み(state記録済み・二重投稿防止)")
        return
    if slide_urls:
        # IGカルーセル: 子コンテナ(is_carousel_item)→CAROUSEL親→publish
        children = []
        for u in slide_urls:
            c = api(f"/{ig_user}/media",
                    {"image_url": u, "is_carousel_item": "true", "access_token": token})
            children.append(c["id"])
        c = api(f"/{ig_user}/media",
                {"media_type": "CAROUSEL", "children": ",".join(children),
                 "caption": ig_caption, "access_token": token})
    else:
        c = api(f"/{ig_user}/media",
                {"image_url": image_url, "caption": ig_caption, "access_token": token})
    creation_id = c["id"]
    last_err = None
    for _ in range(3):  # コンテナ処理待ちを考慮して公開を最大3回試行
        try:
            api(f"/{ig_user}/media_publish",
                {"creation_id": creation_id, "access_token": token})
            print("[ok] Instagram投稿 完了")
            state["instagram"] = True
            save_state(state)
            return
        except SafetyError as e:
            last_err = e
            time.sleep(10)
    raise SafetyError(f"Instagram公開に失敗: {last_err}")


if __name__ == "__main__":
    main()
