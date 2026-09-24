#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
もらいわすれ堂 Instagram の投稿実績を記録する(2026-09-24 小柳さん決裁・案A)。

経緯:
  「投稿したらLINEで報告してください」と案内していたが、LINEは送信専用で受信を
  処理する仕組みが無く、報告はどこにも残っていなかった。遥さんから
  「今後は、実際に記録・反映できる連絡方法だけを案内してください」との指摘。
  連絡方法をメール返信に一本化し、受け取った内容をここへ残す。

台帳: data/kpi/ig_posts.json
  フォロワー数の台帳(moradou_ig_followers.json)とは別。混ぜない。
  **個人情報(氏名・メールアドレス・電話)は書かない**(本リポジトリはPUBLIC)。

使い方:
  python scripts/record_ig_post.py --date 2026-09-24 --no 3 --title "就学援助" 
  python scripts/record_ig_post.py --date 2026-09-24 --no 4 --skipped --why "旬を過ぎた"
  python scripts/record_ig_post.py --list
  python scripts/record_ig_post.py --self-test
"""
import argparse
import datetime as dt
import json
import os
import re
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
LEDGER = os.path.join(BASE, "data", "kpi", "ig_posts.json")

# 台帳に入ってはいけないもの(公開リポジトリのため)
PII = [
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"), "メールアドレス"),
    (re.compile(r"0\d{1,4}-?\d{1,4}-?\d{3,4}"), "電話番号らしい数字"),
]


def check_pii(text):
    return [label for pat, label in PII if pat.search(text or "")]


def add(ledger, date, no, title, posted, why="", seido_id="", source_url="",
        verified_at="", status=""):
    """1件足す。同じ日・同じ案番号は上書きせず弾く(二重計上を防ぐ)。

    2026-09-24 遥さんの要望で照合記録を紐づける:
      「『案として渡したもの』だけではなく、投稿実績台帳と照合記録が
        紐づいた状態で管理してもらえると助かります」
    seido_id / source_url / verified_at を一緒に残すので、あとから
    「この投稿はいつ時点の原文に基づくか」を1行でたどれる。
    """
    if check_pii(title) or check_pii(why):
        raise ValueError("個人情報らしき文字列が含まれています。台帳には書けません")
    try:
        dt.date.fromisoformat(date)
    except ValueError:
        raise ValueError(f"日付の形式が違います: {date}(YYYY-MM-DD)")
    for p in ledger["posts"]:
        if p["date"] == date and p["no"] == no:
            raise ValueError(f"{date} の案{no}は既に記録されています")
    if posted and not (seido_id or source_url):
        raise ValueError("投稿済みの記録には seido_id か source_url のどちらかが必要です"
                         "(照合記録と紐づかない投稿を台帳に残さない)")
    ledger["posts"].append({"date": date, "no": no, "title": title,
                            "posted": posted, "why": why,
                            "seido_id": seido_id, "source_url": source_url,
                            "verified_at": verified_at, "status": status,
                            "source": "遥さんからのメール返信"})
    ledger["posts"].sort(key=lambda p: (p["date"], p["no"]))
    ledger["updated_at"] = dt.date.today().isoformat()
    return ledger


def summary(ledger):
    posts = ledger.get("posts", [])
    done = [p for p in posts if p.get("posted")]
    linked = [p for p in done if p.get("verified_at")]
    return (f"投稿実績: 記録 {len(posts)}件(投稿 {len(done)}件 / 見送り "
            f"{len(posts) - len(done)}件)。うち照合日つき {len(linked)}件")


def load():
    with open(LEDGER, encoding="utf-8") as f:
        return json.load(f)


def save(d):
    with open(LEDGER, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
        f.write("\n")


def self_test():
    ok = bad = 0

    def check(label, cond):
        nonlocal ok, bad
        if cond:
            ok += 1
        else:
            bad += 1
            print(f"  NG {label}")

    def fresh():
        return {"posts": [], "updated_at": "2026-09-24"}

    d = add(fresh(), "2026-09-24", 3, "就学援助", True, seido_id="x",
            verified_at="2026-08-06")
    check("1件記録できる", len(d["posts"]) == 1 and d["posts"][0]["posted"])
    check("照合記録が紐づく",
          d["posts"][0]["seido_id"] == "x" and d["posts"][0]["verified_at"] == "2026-08-06")
    try:
        add(fresh(), "2026-09-24", 1, "裏づけなし", True)
        check("照合記録の無い投稿は台帳に入れない", False)
    except ValueError:
        check("照合記録の無い投稿は台帳に入れない", True)
    check("見送りなら裏づけ不要",
          len(add(fresh(), "2026-09-24", 1, "出さなかった", False)["posts"]) == 1)
    check("出どころを残す", d["posts"][0]["source"] == "遥さんからのメール返信")

    d = add(d, "2026-09-24", 4, "年金給付金", False, "旬を過ぎた")  # 見送りは裏づけ不要
    check("見送りも記録できる", len(d["posts"]) == 2 and not d["posts"][1]["posted"])
    check("集計が合う",
          summary(d) == "投稿実績: 記録 2件(投稿 1件 / 見送り 1件)。うち照合日つき 1件")

    try:
        add(d, "2026-09-24", 3, "就学援助", True, seido_id="x")
        check("同じ日の同じ案は弾く", False)
    except ValueError:
        check("同じ日の同じ案は弾く", True)

    try:
        add(fresh(), "9/24", 1, "x", True, seido_id="x")
        check("日付の形式を見る", False)
    except ValueError:
        check("日付の形式を見る", True)

    check("メールアドレスを見つける", check_pii("a@b.co.jp") == ["メールアドレス"])
    check("電話番号を見つける", check_pii("098-123-4567") == ["電話番号らしい数字"])
    check("ふつうの文は通す", check_pii("那覇市の就学援助について") == [])
    try:
        add(fresh(), "2026-09-24", 1, "連絡先 a@b.co.jp", True, seido_id="x")
        check("個人情報は台帳に入れない", False)
    except ValueError:
        check("個人情報は台帳に入れない", True)

    check("日付順に並ぶ",
          [p["no"] for p in add(add(fresh(), "2026-09-25", 1, "b", True, seido_id="x"),
                                "2026-09-24", 9, "a", True, seido_id="y")["posts"]]
          == [9, 1])

    # 実ファイルが読めて、形が期待どおりか
    real = load()
    check("台帳が読める", isinstance(real.get("posts"), list))
    # 台帳の役割が混ざっていないか(キーで見る。説明文に別台帳の名前が出るのは正しい)
    check("フォロワー台帳と混ざっていない", "followers" not in real)
    check("投稿実績の台帳である", set(real) >= {"posts", "note", "source"})

    print(f"自己テスト: OK {ok} / NG {bad}")
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date")
    ap.add_argument("--no", type=int)
    ap.add_argument("--title", default="")
    ap.add_argument("--skipped", action="store_true", help="投稿しなかった場合")
    ap.add_argument("--why", default="")
    ap.add_argument("--seido-id", default="")
    ap.add_argument("--source-url", default="")
    ap.add_argument("--verified-at", default="")
    ap.add_argument("--status", default="")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    d = load()
    if a.list:
        for p in d["posts"]:
            mark = "投稿" if p["posted"] else "見送り"
            print(f"  {p['date']} 案{p['no']} [{mark}] {p['title']} {p.get('why','')}")
        print(summary(d))
        return 0
    if not (a.date and a.no):
        ap.error("--date と --no を指定してください(または --list / --self-test)")
    save(add(d, a.date, a.no, a.title, not a.skipped, a.why,
             a.seido_id, a.source_url, a.verified_at, a.status))
    print(f"記録しました: {a.date} 案{a.no}")
    print(summary(load()))
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
