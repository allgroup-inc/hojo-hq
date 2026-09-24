#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
これまで遥さんに渡したIG投稿案を全部さかのぼって、照合の状況を調べる。

きっかけ(2026-09-24 遥さんの指摘):
  「今後送る案だけ最新情報を確認しても、すでに公開されている投稿に古い情報や
   未照合の情報が残っていたら意味がありません。これまで投稿済みの制度について、
   ①照合記録があるもの ②照合記録がないもの ③現在の公式情報と比べて修正が必要なもの
   を確認してほしい」

そのとおりなので、前向きの検査(check_ig_neta.py)だけでなく、**すでに渡した分**を
git履歴からすべて取り出して並べる。

大事な限界(はっきり書く):
  ここで分かるのは「**こちらが渡した案**」であって「**実際に投稿されたもの**」ではない。
  Instagramの投稿一覧を機械で読む手段が無い(アカウント連携が未了)。
  渡した案と実際の投稿の突き合わせは、遥さんに確認していただく必要がある。

使い方:
  python scripts/audit_ig_history.py                 # 照合記録の有無で仕分け
  python scripts/audit_ig_history.py --online        # 出典ページを開いて現状と比べる
  python scripts/audit_ig_history.py --md docs/点検_YYYYMMDD_IG投稿済みの照合状況.md
  python scripts/audit_ig_history.py --self-test
"""
import argparse
import json
import os
import re
import subprocess
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
NETA_PATH = "data/fukugiiro/ig_neta.json"
SEIDO = os.path.join(BASE, "data", "fukugiiro", "seido.json")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from check_ig_neta import asserted, fetch, strip_tags, norm_url  # noqa: E402

# 沖縄県向けのサービスなのに、他都道府県の自治体ドメインが出典になっていないか。
# (2026-09-24 実際に大阪市阿倍野区のページを出典にした案が見つかった)
OKINAWA_HINTS = ("okinawa", "naha", "urasoe", "ginowan", "nanjo", "uruma", "itoman",
                 "tomigusuku", "miyakojima", "ishigaki", "nago", "yaese", "haebaru",
                 "nishihara", "chatan", "kadena", "yomitan", "kin", "onna", "motobu")
MUNI_DOMAIN = re.compile(r"(?:city|town|vill)\.([a-z0-9-]+)\.(?:lg\.jp|jp)")


def is_shallow():
    """浅いクローンかどうか。CIの checkout は既定で depth=1 なので履歴が無い。"""
    r = subprocess.run(["git", "rev-parse", "--is-shallow-repository"],
                       cwd=BASE, capture_output=True, text=True)
    return r.stdout.strip() == "true"


def git_versions(path=NETA_PATH):
    """そのファイルの全バージョンを古い順に返す。[(commit, 日付, データ)]

    浅いクローンでは履歴が見えず、**最新1件だけを全履歴として報告してしまう**。
    それでも成功として通ってしまうので、ここで止める。
    (2026-09-24 実際に起きた。CIが「渡した案15件」を「5件」と報告し、
     正しい記録を上書きした。checkout の fetch-depth: 0 が必要)
    """
    out = subprocess.run(
        ["git", "log", "--follow", "--format=%H\t%ad", "--date=short", "--", path],
        cwd=BASE, capture_output=True, text=True, check=True).stdout
    rows = [l.split("\t") for l in out.strip().split("\n") if l.strip()]
    versions = []
    for sha, day in reversed(rows):
        blob = subprocess.run(["git", "show", f"{sha}:{path}"],
                              cwd=BASE, capture_output=True, text=True)
        if blob.returncode != 0:
            continue
        try:
            versions.append((sha[:9], day, json.loads(blob.stdout)))
        except ValueError:
            continue
    # 浅いクローン + 見つかったのが1件だけ = 履歴が切れているのか、
    # 本当に1件しか無いのかを**区別できない**。区別できないまま
    # 「これが全部です」と報告するのがいちばん危ないので、ここで止める。
    # (浅くても複数件見つかっていれば、履歴は追えているので進める)
    if len(versions) <= 1 and is_shallow():
        raise SystemExit(
            "::error::浅いクローンで履歴が1件しか見えません。全履歴なのか"
            "切れているのか区別できないため中止します。"
            "actions/checkout に fetch-depth: 0 を指定してください")
    return versions


def seido_index():
    with open(SEIDO, encoding="utf-8") as f:
        items = json.load(f).get("items", [])
    idx = {}
    for i in items:
        idx.setdefault(norm_url(i.get("source_url")), i)
    return idx


def foreign_muni(url):
    """沖縄以外の自治体ドメインなら、その自治体名を返す。"""
    m = MUNI_DOMAIN.search((url or "").lower())
    if not m:
        return None
    name = m.group(1)
    return None if name in OKINAWA_HINTS else name


def collect(versions, idx):
    """渡した案を重複なく集め、照合の状況で仕分けする。"""
    seen, rows = {}, []
    for sha, day, d in versions:
        for it in d.get("items", []):
            key = (it.get("title", ""), norm_url(it.get("source_url")))
            if key in seen:
                seen[key]["handed"].append(day)
                continue
            dates, moneys = asserted(it)
            s = idx.get(norm_url(it.get("source_url")))
            if s is None:
                state = "照合記録なし"
            elif s.get("verified"):
                state = "照合記録あり"
            else:
                state = "制度DBにあるが未照合"
            rec = {
                "title": it.get("title", ""),
                "url": it.get("source_url", ""),
                "dates": dates,
                "moneys": moneys,
                "state": state,
                "verified_at": (s or {}).get("verified_at"),
                "seido_id": (s or {}).get("id"),
                "foreign": foreign_muni(it.get("source_url")),
                "handed": [day],
                "first_commit": sha,
            }
            seen[key] = rec
            rows.append(rec)
    return rows


def priority(r):
    """期限・金額が本文に入っていて、かつ照合記録が無いものを最優先で見る。"""
    has_claim = bool(r["dates"] or r["moneys"])
    if has_claim and r["state"] != "照合記録あり":
        return 0
    if r["foreign"]:
        return 0
    if has_claim:
        return 1
    if r["state"] != "照合記録あり":
        return 2
    return 3


LABEL = {0: "最優先", 1: "要確認", 2: "確認", 3: "問題なし"}


def online_status(rows, fetcher=fetch):
    """出典ページを開いて、本文で断定した値がいまもあるかを見る。
    取得失敗と不一致は必ず分ける。"""
    for r in rows:
        claims = r["dates"] + r["moneys"]
        if not claims:
            r["online"] = "断定なし(確認不要)"
            continue
        body, err = fetcher(r["url"])
        if body is None:
            r["online"] = f"取得できず({err}) ※誤りとは判定していない"
            continue
        text = strip_tags(body)
        missing = [c for c in claims if c not in text]
        r["online"] = ("出典に残っている" if not missing
                       else f"出典に見当たらない: {'・'.join(missing)} → 修正が必要")
    return rows


def to_markdown(rows, online, shallow=False):
    lines = ["# 点検: これまで渡したIG投稿案の照合状況(2026-09-24)", "",
             "遥さんの指摘「すでに公開されている投稿に古い情報や未照合の情報が残っていないか」"
             "を受けて、git履歴から**渡した案を全部**取り出して並べた。", "",
             "**限界**: ここに出るのは「こちらが渡した案」であって「実際に投稿されたもの」ではない。"
             "Instagramの投稿一覧を機械で読む手段が無いため(アカウント連携が未了)、"
             "実際の投稿との突き合わせは遥さんの確認が必要。", ""]
    n = {}
    for r in rows:
        n[r["state"]] = n.get(r["state"], 0) + 1
    lines += [f"渡した案 {len(rows)}件 — "
              + " / ".join(f"{k} {v}件" for k, v in sorted(n.items())), ""]
    days = sorted({d for r in rows for d in r["handed"]})
    if len(days) < 2:
        lines += ["> ⚠️ 渡した日が1日しかありません。履歴が取れていない可能性があります"
                  "(浅いクローン)。件数を鵜呑みにしないでください。", ""]
    if shallow:
        lines += ["> ⚠️ 浅いクローンで作成しました。古い履歴が欠けている可能性があります"
                  "(完全な履歴は fetch-depth: 0 で取れます)。", ""]
    lines += ["| 優先 | 案 | 断定している値 | 照合 | 出典 |", "|---|---|---|---|---|"]
    for r in sorted(rows, key=priority):
        claims = "・".join(r["dates"] + r["moneys"]) or "—"
        state = r["state"] + (f"({r['verified_at']})" if r["verified_at"] else "")
        if r["foreign"]:
            state += f" ⚠️出典が県外の自治体({r['foreign']})"
        if online and r.get("online"):
            state += f" / {r['online']}"
        lines.append(f"| {LABEL[priority(r)]} | {r['title'][:40]} | {claims} | {state} "
                     f"| {r['url'][:70]} |")
    lines += ["", "渡した日: " + ", ".join(
        sorted({d for r in rows for d in r["handed"]})), ""]
    return "\n".join(lines) + "\n"


def self_test():
    ok = bad = 0

    def check(label, cond):
        nonlocal ok, bad
        if cond:
            ok += 1
        else:
            bad += 1
            print(f"  NG {label}")

    check("県外の自治体ドメインを見つける",
          foreign_muni("https://www.city.osaka.lg.jp/abeno/page/1.html") == "osaka")
    check("沖縄の自治体は県外扱いしない",
          foreign_muni("https://www.city.naha.okinawa.jp/a.html") is None)
    check("自治体でないドメインは対象外",
          foreign_muni("https://www.mext.go.jp/a.html") is None)

    base = {"title": "t", "url": "u", "dates": [], "moneys": [],
            "state": "照合記録あり", "verified_at": "2026-08-06", "seido_id": "x",
            "foreign": None, "handed": ["2026-09-08"], "first_commit": "abc"}

    def r(**kw):
        d = dict(base)
        d.update(kw)
        return d

    check("断定あり×照合なし → 最優先",
          priority(r(dates=["9月30日"], state="照合記録なし")) == 0)
    check("県外出典 → 最優先", priority(r(foreign="osaka")) == 0)
    check("断定あり×照合あり → 要確認", priority(r(dates=["9月30日"])) == 1)
    check("断定なし×照合なし → 確認", priority(r(state="照合記録なし")) == 2)
    check("断定なし×照合あり → 問題なし", priority(r()) == 3)

    rows = online_status([r(dates=["9月30日"])],
                         fetcher=lambda u: ("<p>9月30日まで</p>", None))
    check("出典に残っていればそう書く", "残っている" in rows[0]["online"])
    rows = online_status([r(dates=["9月30日"])],
                         fetcher=lambda u: ("<p>10月30日まで</p>", None))
    check("出典から消えていれば修正が必要", "修正が必要" in rows[0]["online"])
    rows = online_status([r(dates=["9月30日"])], fetcher=lambda u: (None, "HTTP 403"))
    check("取得失敗は誤りと判定しない", "取得できず" in rows[0]["online"]
          and "修正が必要" not in rows[0]["online"])
    rows = online_status([r()], fetcher=lambda u: (None, "boom"))
    check("断定が無ければ取りに行かない", rows[0]["online"] == "断定なし(確認不要)")

    md = to_markdown([r(dates=["9月30日"], state="照合記録なし")], online=False)
    check("表に出る", "9月30日" in md and "最優先" in md)
    check("渡した日が1日だけなら履歴不足を警告する", "履歴が取れていない可能性" in md)
    two = to_markdown([r(handed=["2026-08-11"]), r(title="b", handed=["2026-09-08"])],
                      online=False)
    check("複数日あれば警告しない", "履歴が取れていない可能性" not in two)
    check("浅いクローンなら報告に明記する",
          "古い履歴が欠けている可能性" in to_markdown([r()], online=False, shallow=True))
    check("浅くなければ書かない",
          "古い履歴が欠けている可能性" not in to_markdown([r()], online=False, shallow=False))
    check("限界を明記する", "実際に投稿されたものではない" in md.replace("」", "").replace("「", "")
          or "実際に投稿されたもの" in md)

    print(f"自己テスト: OK {ok} / NG {bad}")
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--online", action="store_true")
    ap.add_argument("--md")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    rows = collect(git_versions(), seido_index())
    if a.online:
        online_status(rows)
    md = to_markdown(rows, a.online, shallow=is_shallow())
    if a.md:
        path = a.md if os.path.isabs(a.md) else os.path.join(BASE, a.md)
        with open(path, "w", encoding="utf-8") as f:
            f.write(md)
        print(f"書き出しました: {a.md}")
    print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
