#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IG投稿案(ig_neta.json)が「断定してよいことだけを断定しているか」を検査する。

きっかけ(2026-09-24 遥さんの指摘):
  9月8日に作った案2「私立高校生の奨学給付金、申請は9月30日までです」を9月21日に送った。
  しかし沖縄県の公式ページでは9月17日に期限が9月30日→10月30日へ延長されていた。
  遥さんが学校からの案内でたまたま気づいて教えてくれた。

調べて分かったこと(指摘より悪い):
  ① その「9月30日」は照合済みDB(seido.json)由来ですらない。ネタを書いたときに
     直接書き込まれ、一度も照合を通っていない
  ② ig_neta.json を生成するスクリプトは存在せず、手で置かれた静的ファイル。
     照合パイプラインとつながっていないので、原文が変わっても永久に気づけない
  ③ その誤った日付で締切3層ルールを適用したため、本当は残り39日(=SNS可)の案を
     「残り9日」と判定してインスタから外していた。誤りが配信の判断まで曲げていた

この検査がやること:
  - 断定された日付・金額が、照合済みの制度(verified=True)に裏づけられているか
  - ネタ自体・照合そのものが古くなっていないか
  - --online: 出典ページを実際に取得し、断定した日付がいまもそのページに書いてあるか
    (取得失敗と不一致は必ず分けて報告する。通信失敗は掲載が誤っている証拠ではない)

使い方:
  python scripts/check_ig_neta.py             # 構造の検査(通信なし)
  python scripts/check_ig_neta.py --online    # 出典ページと突き合わせる
  python scripts/check_ig_neta.py --self-test
"""
import argparse
import datetime as dt
import json
import os
import re
import sys
import urllib.error
import urllib.request

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
NETA = os.path.join(BASE, "data", "fukugiiro", "ig_neta.json")
SEIDO = os.path.join(BASE, "data", "fukugiiro", "seido.json")

NETA_STALE_DAYS = 14      # ネタ自体がこれ以上古ければ使う前に見直す
VERIFY_STALE_DAYS = 30    # 照合からこれ以上経った日付は断定させない
TIMEOUT = 20
UA = "moradou-neta-check/1.0 (+https://github.com/allgroup-inc/hojo-hq)"

DATE_RE = re.compile(r"(?:\d{4}年)?\d{1,2}月\d{1,2}日")
MONEY_RE = re.compile(r"\d[\d,]*\s*円")


def norm_url(u):
    return (u or "").strip().rstrip("/")


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def seido_index(seido):
    idx = {}
    for i in seido.get("items", []):
        idx.setdefault(norm_url(i.get("source_url")), i)
    return idx


def asserted(it):
    """案の本文で断定されている日付と金額。"""
    text = (it.get("title") or "") + " " + (it.get("caption") or "")
    return sorted(set(DATE_RE.findall(text))), sorted(set(MONEY_RE.findall(text)))


def days_since(date_str, today):
    try:
        d = dt.date.fromisoformat(date_str)
    except (TypeError, ValueError):
        return None
    return (today - d).days


def audit(neta, seido, today):
    """(NGの一覧, WARNの一覧) を返す。"""
    idx = seido_index(seido)
    ng, warn = [], []

    age = days_since(neta.get("updated_at"), today)
    if age is not None and age > NETA_STALE_DAYS:
        warn.append(f"ネタ全体が{age}日前({neta.get('updated_at')})のままです。"
                    f"使う前に作り直してください")

    for it in neta.get("items", []):
        no = it.get("no")
        dates, moneys = asserted(it)
        s = idx.get(norm_url(it.get("source_url")))

        if not (dates or moneys):
            continue  # 断定していないので裏づけは要らない

        what = "・".join(dates + moneys)
        if s is None:
            ng.append(f"案{no}: 「{what}」を断定していますが、この出典は制度DBにありません。"
                      f"照合を通していない数字は本文に書かないでください")
            continue
        if not s.get("verified"):
            ng.append(f"案{no}: 「{what}」を断定していますが、制度 {s.get('id')} は未照合"
                      f"(status={s.get('status')})です")
            continue

        v_age = days_since(s.get("verified_at"), today)
        if v_age is None:
            ng.append(f"案{no}: 制度 {s.get('id')} は照合済みですが照合日がありません")
        elif v_age > VERIFY_STALE_DAYS:
            ng.append(f"案{no}: 「{what}」の裏づけが{v_age}日前の照合"
                      f"({s.get('verified_at')})です。再照合してから使ってください")

        # 締切を断定しているなら、制度DBの締切と一致しているか
        if dates and s.get("deadline"):
            try:
                d = dt.date.fromisoformat(s["deadline"])
                want = f"{d.month}月{d.day}日"
                if not any(want in x for x in dates):
                    ng.append(f"案{no}: 本文の日付({'・'.join(dates)})が制度DBの締切"
                              f"({s['deadline']})と違います")
            except ValueError:
                pass
    return ng, warn


# ── 出典ページとの突き合わせ(通信あり) ──────────────────────
def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            raw = r.read()
    except urllib.error.HTTPError as e:
        return None, f"HTTP {e.code}"
    except urllib.error.URLError as e:
        return None, f"つながらない({e.reason})"
    except Exception as e:
        return None, f"{type(e).__name__}"
    for enc in ("utf-8", "euc_jp", "shift_jis"):
        try:
            return raw.decode(enc), None
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace"), None


def strip_tags(html):
    html = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", html)
    return re.sub(r"<[^>]+>", " ", html)


def online_check(neta, fetcher=fetch):
    """断定した日付が、いまも出典ページに書いてあるか。
    「取得できない」と「書いていない」は必ず分ける(通信失敗は誤りの証拠ではない)。"""
    ng, unknown = [], []
    for it in neta.get("items", []):
        dates, _m = asserted(it)
        if not dates:
            continue
        url = it.get("source_url")
        body, err = fetcher(url)
        if body is None:
            unknown.append(f"案{it.get('no')}: 出典を取得できませんでした({err})。"
                           f"誤りとは判定していません")
            continue
        text = strip_tags(body)
        missing = [d for d in dates if d.replace("　", "") not in text.replace("　", "")]
        if missing:
            ng.append(f"案{it.get('no')}: 本文の「{'・'.join(missing)}」が"
                      f"出典ページに見当たりません。変更されている可能性があります")
    return ng, unknown


def report(ng, warn, unknown=()):
    for m in ng:
        print(f"[NG]   {m}")
    for m in warn:
        print(f"[WARN] {m}")
    for m in unknown:
        print(f"[不明] {m}")
    print(f"\nIG投稿案の検査: NG {len(ng)} / WARN {len(warn)} / 取得できず {len(unknown)}")
    return 1 if ng else 0


# ── 自己テスト ────────────────────────────────────────────────
def self_test():
    ok = bad = 0

    def check(label, cond):
        nonlocal ok, bad
        if cond:
            ok += 1
        else:
            bad += 1
            print(f"  NG {label}")

    today = dt.date(2026, 9, 24)
    URL = "https://example.org/a"

    def neta_of(caption, updated="2026-09-20", url=URL):
        return {"updated_at": updated,
                "items": [{"no": 1, "title": "T", "caption": caption, "source_url": url}]}

    def seido_of(**kw):
        base = {"id": "x", "source_url": URL, "verified": True,
                "verified_at": "2026-09-20", "status": "検証済み"}
        base.update(kw)
        return {"items": [base]}

    check("日付を拾う", asserted({"title": "", "caption": "9月30日まで"})[0] == ["9月30日"])
    check("年つきも拾う",
          asserted({"title": "2026年10月30日", "caption": ""})[0] == ["2026年10月30日"])
    check("金額を拾う", asserted({"title": "", "caption": "4,400円分"})[1] == ["4,400円"])
    check("日付が無ければ空", asserted({"title": "就学援助とは", "caption": "締切なし"})[0] == [])

    ng, _w = audit(neta_of("9月30日まで"), {"items": []}, today)
    check("制度DBに無い出典で日付を断定→NG", len(ng) == 1 and "制度DBにありません" in ng[0])

    ng, _w = audit(neta_of("9月30日まで"), seido_of(verified=False, status="要確認"), today)
    check("未照合の制度で日付を断定→NG", len(ng) == 1 and "未照合" in ng[0])

    ng, _w = audit(neta_of("9月30日まで"), seido_of(deadline="2026-09-30"), today)
    check("照合済み・締切一致→NG無し", ng == [])

    ng, _w = audit(neta_of("9月30日まで"), seido_of(deadline="2026-10-30"), today)
    check("制度DBの締切と食い違う→NG", len(ng) == 1 and "違います" in ng[0])

    ng, _w = audit(neta_of("9月30日まで"), seido_of(verified_at="2026-07-01"), today)
    check("照合が古すぎる→NG", len(ng) == 1 and "再照合" in ng[0])

    ng, _w = audit(neta_of("締切のない制度です"), {"items": []}, today)
    check("断定していなければ裏づけ不要", ng == [])

    _n, warn = audit(neta_of("締切なし", updated="2026-09-01"), {"items": []}, today)
    check("ネタが古ければWARN", len(warn) == 1 and "23日前" in warn[0])

    _n, warn = audit(neta_of("締切なし", updated="2026-09-20"), {"items": []}, today)
    check("新しければWARN無し", warn == [])

    # online: 取得失敗と不一致を分ける
    ng, unk = online_check(neta_of("9月30日まで"),
                           fetcher=lambda u: ("<p>申請は9月30日まで</p>", None))
    check("出典に日付があればOK", ng == [] and unk == [])

    ng, unk = online_check(neta_of("9月30日まで"),
                           fetcher=lambda u: ("<p>申請は10月30日まで</p>", None))
    check("出典の日付が変わっていたらNG", len(ng) == 1 and unk == [])

    ng, unk = online_check(neta_of("9月30日まで"),
                           fetcher=lambda u: (None, "HTTP 403"))
    check("取得できないのはNGにしない", ng == [] and len(unk) == 1)
    check("取得できない理由を残す", "403" in unk[0])

    ng, _u = online_check(neta_of("9月30日まで"),
                          fetcher=lambda u: ("<script>9月30日</script><p>本文</p>", None))
    check("scriptの中は本文として数えない", len(ng) == 1)

    check("NGがあれば終了コード1", report(["x"], []) == 1)
    check("NGが無ければ終了コード0", report([], ["y"]) == 0)

    print(f"自己テスト: OK {ok} / NG {bad}")
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--online", action="store_true", help="出典ページと突き合わせる")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    neta, seido = load(NETA), load(SEIDO)
    today = dt.date.today()
    ng, warn = audit(neta, seido, today)
    unknown = []
    if a.online:
        ong, unknown = online_check(neta)
        ng += ong
    return report(ng, warn, unknown)


if __name__ == "__main__":
    sys.exit(main() or 0)
