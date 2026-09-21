#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""もらいわすれ堂 自己点検 — このリポジトリが実際に繰り返した失敗だけを機械で見張る。

CLAUDE.md「再発防止メモ」に載っている失敗は、どれも人の注意力ではなく検査で防ぐべきもの。
ここでは**過去に実害が出た型だけ**を対象にする(思いつきの検査を足すと偽陽性で信用を失う)。

判定は3段階に分ける。**「取得できなかった」と「間違っている」を混ぜない**という、
kensho で学んだ原則をそのまま適用する:

  [NG]   機械的に誤りと断定できる。終了コード1(CIを止める)
  [WARN] 誤りの疑いはあるが断定できない。終了コード0
  [TODO] 人の作業待ち。誤りではない。終了コード0(週次レポで可視化する用)

使い方:
    python scripts/selfcheck_moradou.py              # 点検
    python scripts/selfcheck_moradou.py --json       # 機械可読(週次レポ用)
    python scripts/selfcheck_moradou.py --self-test  # 検査そのものの自己テスト
"""
import argparse
import json
import os
import re
import sys
from datetime import date, datetime, timedelta, timezone

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

JST = timezone(timedelta(hours=9))
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SEIDO = os.path.join(BASE, "data", "fukugiiro", "seido.json")
NETA = os.path.join(BASE, "data", "fukugiiro", "ig_neta.json")
IG_FOLLOWERS = os.path.join(BASE, "data", "kpi", "moradou_ig_followers.json")
GO_GEN = os.path.join(BASE, "scripts", "generate_go_pages.py")
FETCH_WF = os.path.join(BASE, ".github", "workflows", "fukugiiro-fetch.yml")
DOCS = os.path.join(BASE, "docs")
# 既知の負債。ここに載っている NG は CI を止めない(新しく増えた分だけ止める)。
# 直したら --update-baseline で減らす。減らさずに放置すると件数がそのまま借金として見える。
BASELINE = os.path.join(BASE, "tests", "selfcheck_baseline.json")

# 転送先がこれらに向いているチャネルだけが line_redirect を名乗ってよい
LINE_HOSTS = ("lin.ee", "line.me")

# 締切3層ルール(CLAUDE.md)。SNS告知に使えるのは30日以上先か、締切なしの制度だけ
SNS_MIN_DAYS = 30

# 「締切7日前」系は憲法が명示的に誤りとしている表現
BANNED_DEADLINE_PHRASES = ["締切7日前", "締切の7日前", "7日前アラート", "締切1週間前"]

# 生成ステップと、その出力が fukugiiro-fetch.yml の git add に載っているべきパス。
# addリストから漏れた生成物は直後の git checkout/clean で消える(2026-08-17・09-20に実害)
GENERATOR_OUTPUTS = {
    "scripts/generate_area_pages.py": "site/fukugiiro/area",
    "scripts/generate_kit_pages.py": "site/fukugiiro/kit",
    "scripts/generate_life_pages.py": "site/fukugiiro/life",
    "scripts/generate_sitemap.py": "site/sitemap.xml",
    "scripts/yamanashi/build_yamanashi.py": "site/yamanashi",
    "scripts/kensho_fukugiiro.py": "data/fukugiiro/kensho_summary.json",
}


def fingerprint(item):
    """同じ問題を同じ文字列で指せるようにする。件数や語尾の揺れで別物にならないよう、
    check名と、メッセージ内の可変部分を除いた先頭だけを使う。"""
    msg = re.sub(r"\d+", "N", item["msg"])
    return f'{item["check"]}::{msg[:120]}'


def load_baseline():
    try:
        with open(BASELINE, encoding="utf-8") as f:
            return set(json.load(f).get("accepted", []))
    except OSError:
        return set()


class Report:
    def __init__(self):
        self.ng, self.warn, self.todo = [], [], []

    def add(self, level, check, msg):
        getattr(self, level).append({"check": check, "msg": msg})

    def as_dict(self):
        return {"ng": self.ng, "warn": self.warn, "todo": self.todo,
                "ng_count": len(self.ng), "warn_count": len(self.warn),
                "todo_count": len(self.todo)}


def _load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------- 検査1
def check_go_event_names(rep, src=None):
    """/go/ の転送先がLINEでないのに line_redirect を名乗っていないか。

    CLAUDE.md 再発防止メモの1件目。そのままだとLINE登録数が水増しされ、KGIの現在地を見誤る。
    """
    s = src if src is not None else open(GO_GEN, encoding="utf-8").read()
    # CHANNELS の { ... } ブロックを1チャネルずつ拾う
    block = re.search(r"CHANNELS\s*=\s*\{(.*?)\n\}", s, re.S)
    if not block:
        rep.add("warn", "go-event", "generate_go_pages.py の CHANNELS を読めませんでした(書式変更?)")
        return
    for m in re.finditer(r'"([a-z0-9-]+)"\s*:\s*\{(.*?)\}', block.group(1), re.S):
        ch, body = m.group(1), m.group(2)
        dest = re.search(r'"dest"\s*:\s*((?:"[^"]*"\s*)+)', body)
        if not dest:
            continue
        dest_url = "".join(re.findall(r'"([^"]*)"', dest.group(1)))
        ev = re.search(r'"event"\s*:\s*"([^"]+)"', body)
        event = ev.group(1) if ev else "line_redirect"   # 既定
        is_line = any(h in dest_url for h in LINE_HOSTS)
        if not is_line and event == "line_redirect":
            rep.add("ng", "go-event",
                    f"/go/{ch}/ の転送先はLINEではない({dest_url[:60]})のに event が line_redirect。"
                    "LINE登録数が水増しされます。event と dest_name を指定してください")
        if is_line and event != "line_redirect":
            rep.add("warn", "go-event",
                    f"/go/{ch}/ の転送先はLINEですが event が {event} です。意図的なら無視してください")


# ---------------------------------------------------------------- 検査2
def check_neta(rep, neta=None, seido=None, today=None):
    """IGネタが「検証済みの出典」かつ「締切3層ルール」に適合しているか。"""
    today = today or datetime.now(JST).date()
    neta = neta if neta is not None else _load(NETA)
    seido = seido if seido is not None else _load(SEIDO)
    by_url = {x["source_url"]: x for x in seido["items"]}

    for it in neta.get("items", []):
        no, url = it.get("no"), it.get("source_url", "")
        s = by_url.get(url)
        if s is None:
            rep.add("ng", "neta-source",
                    f"案{no}「{it.get('title','')[:24]}」の出典が seido.json にありません({url[:60]})。"
                    "未検証の情報をネタにしないでください(絶対ルール1)")
            continue
        if not s.get("verified"):
            rep.add("ng", "neta-source",
                    f"案{no}の出典「{s['name']}」は verified=false です。検証済みの制度から引いてください")
        dl = s.get("deadline")
        if s.get("deadline_type") == "期限あり" and dl:
            try:
                days = (date.fromisoformat(dl) - today).days
            except ValueError:
                rep.add("warn", "neta-deadline", f"案{no}の締切 {dl} を日付として読めませんでした")
                continue
            if days < SNS_MIN_DAYS:
                layer = "次回公募予告(7日未満)" if days < 7 else "LINE個別アラート(7〜29日)"
                rep.add("ng", "neta-deadline",
                        f"案{no}「{s['name']}」は締切まで残り{days}日。SNS投稿の帯(30日以上)ではなく"
                        f"{layer}の領域です。ネタから外すか、SNSでは出さないと明記してください")
        if not it.get("caution"):
            rep.add("ng", "neta-caution",
                    f"案{no}に caution がありません。金額・対象・期限を断定させない注意書きは必須です")

    # 鮮度は誤りではないので TODO
    upd = neta.get("updated_at")
    if upd:
        try:
            age = (today - date.fromisoformat(upd)).days
            if age >= 14:
                rep.add("todo", "neta-fresh",
                        f"IGネタが{age}日前({upd} / {neta.get('week')})のままです。"
                        "拡充ループが ig_neta.json を更新できているか確認してください")
        except ValueError:
            rep.add("warn", "neta-fresh", f"ig_neta.json の updated_at を読めません: {upd}")


# ---------------------------------------------------------------- 検査3
def check_workflow_add_list(rep, wf=None):
    """生成ステップの出力が git add のリストに載っているか。

    addリストから漏れた生成物は、直後の git checkout -- . と git clean -fd site で消える。
    2026-08-17(life)と 2026-09-20(山梨)で実際に踏んでいる。
    """
    s = wf if wf is not None else open(FETCH_WF, encoding="utf-8").read()
    add_lines = [ln for ln in s.splitlines() if re.search(r"^\s*git add ", ln)]
    add_blob = " ".join(add_lines)
    if not add_blob:
        rep.add("warn", "wf-add", "fukugiiro-fetch.yml に git add 行が見つかりませんでした")
        return
    for script, out in GENERATOR_OUTPUTS.items():
        if script not in s:
            continue   # そのステップが無いなら対象外
        if out not in add_blob:
            rep.add("ng", "wf-add",
                    f"{script} を実行しているのに、出力 {out} が git add のリストにありません。"
                    "直後の git checkout/clean で生成物が消えます")


# ---------------------------------------------------------------- 検査4
_DOC_PATH = re.compile(r"(?<![\w/./-])docs/[^\s`)（）、。,|\"'<>]*\.md")
# 「非公開repo」「kakei-crm」等が同じ行にあれば、本リポジトリ外を指しているとみなす
_EXTERNAL_HINTS = ("非公開repo", "非公開リポ", "kakei-crm", "glow-docs-private", "移設済み", "移設先")


def check_doc_refs(rep, files=None):
    """docs の中で案内している docs/*.md が実在するか。

    案内文書を他者へ送る前に検査する(CLAUDE.md 再発防止メモ)。
    テンプレート表記(* や < >)と、他リポジトリを指す記述は対象外。
    """
    files = files if files is not None else sorted(
        os.path.join(DOCS, f) for f in os.listdir(DOCS) if f.endswith(".md"))
    for path in files:
        try:
            lines = open(path, encoding="utf-8").read().splitlines()
        except OSError:
            continue
        for ln in lines:
            if any(h in ln for h in _EXTERNAL_HINTS):
                continue
            for m in _DOC_PATH.finditer(ln):
                ref = m.group(0)
                if "*" in ref or "<" in ref or ">" in ref:
                    continue   # テンプレート表記
                if not os.path.exists(os.path.join(BASE, ref)):
                    rep.add("ng", "doc-ref",
                            f"{os.path.relpath(path, BASE)} が存在しない {ref} を案内しています")


# ---------------------------------------------------------------- 検査5
def check_banned_phrases(rep, targets=None):
    """「締切7日前」系の禁止表現が対外文面に混ざっていないか。"""
    if targets is None:
        targets = []
        for root, _dirs, fs in os.walk(os.path.join(BASE, "site", "fukugiiro")):
            targets += [os.path.join(root, f) for f in fs if f.endswith(".html")]
        targets.append(NETA)
    for path in targets:
        try:
            txt = open(path, encoding="utf-8").read()
        except OSError:
            continue
        for ph in BANNED_DEADLINE_PHRASES:
            if ph in txt:
                rep.add("ng", "banned-phrase",
                        f"{os.path.relpath(path, BASE)} に禁止表現「{ph}」。"
                        "7日前では書類の準備が間に合いません。「締切の約1か月前から」に直してください")


# ---------------------------------------------------------------- 検査6
def check_human_todos(rep, followers=None, today=None):
    """人の作業待ちを可視化する。誤りではないので TODO。"""
    today = today or datetime.now(JST).date()
    try:
        f = followers if followers is not None else _load(IG_FOLLOWERS)
    except OSError:
        return
    st = f.get("last_status", "")
    if st.startswith("未接続"):
        rep.add("todo", "ig-token",
                "IGフォロワー数が自動取得できていません(MORADOU_IG_TOKEN 未登録)。"
                "プロアカウントならFacebookページ連携は不要です")
    hist = [h for h in f.get("history", []) if h.get("followers") is not None]
    if hist and hist[-1]["followers"] == 0:
        rep.add("todo", "ig-followers",
                f"IGフォロワーが0人のままです({hist[-1]['date']}時点)。"
                "まず関係者にフォローしてもらい、0を抜けてください")


# ---------------------------------------------------------------- 検査7
_REVIEW = re.compile(r"見直し期限[^\n]*?(\d{4}-\d{2}-\d{2})")


def check_review_deadlines(rep, files=None, today=None):
    """議事の見直し期限(CLAUDE.md 三名体制ルール7)が切れていないか。"""
    today = today or datetime.now(JST).date()
    files = files if files is not None else sorted(
        os.path.join(DOCS, f) for f in os.listdir(DOCS)
        if f.startswith("議事_") and f.endswith(".md"))
    for path in files:
        try:
            txt = open(path, encoding="utf-8").read()
        except OSError:
            continue
        m = _REVIEW.search(txt)
        if not m:
            continue
        try:
            d = date.fromisoformat(m.group(1))
        except ValueError:
            continue
        left = (d - today).days
        name = os.path.basename(path)
        if left < 0:
            rep.add("todo", "review-due",
                    f"{name} の見直し期限({m.group(1)})が{-left}日過ぎています。再議論してください")
        elif left <= 14:
            rep.add("todo", "review-due", f"{name} の見直し期限まであと{left}日({m.group(1)})")


# ---------------------------------------------------------------- 実行
CHECKS = [check_go_event_names, check_neta, check_workflow_add_list,
          check_doc_refs, check_banned_phrases, check_human_todos, check_review_deadlines]


def run():
    rep = Report()
    for fn in CHECKS:
        try:
            fn(rep)
        except Exception as e:   # noqa: BLE001
            # 検査自体が落ちても他の検査は続ける。落ちたことは隠さない
            rep.add("warn", fn.__name__, f"検査が実行できませんでした: {type(e).__name__}: {e}")
    return rep


def self_test():
    """検査そのものが正しく当たる/外れることを確かめる。"""
    ok = True

    def expect(cond, label):
        nonlocal ok
        print(("  ok   " if cond else "  NG   ") + label)
        ok = ok and cond

    # 1) /go/: LINE以外なのに line_redirect → NG
    r = Report()
    check_go_event_names(r, 'CHANNELS = {\n "x": {"dest": "https://example.com/a", "label": "l"},\n}\n')
    expect(len(r.ng) == 1, "LINE以外 + 既定イベント を検出する")
    r = Report()
    check_go_event_names(r, 'CHANNELS = {\n "x": {"dest": "https://example.com/a", "label": "l",\n "event": "shindan_redirect"},\n}\n')
    expect(len(r.ng) == 0, "イベントを分けてあれば通す")
    r = Report()
    check_go_event_names(r, 'CHANNELS = {\n "y": {"dest": "https://lin.ee/abc", "label": "l"},\n}\n')
    expect(len(r.ng) == 0, "LINE宛 + 既定イベント は正しいので通す")

    # 2) ネタ: 締切が近い制度を含む → NG / 常時なら通す
    today = date(2026, 9, 21)
    seido = {"items": [
        {"id": "a", "name": "近い制度", "source_url": "https://x.go.jp/a",
         "verified": True, "deadline_type": "期限あり", "deadline": "2026-09-30"},
        {"id": "b", "name": "常時制度", "source_url": "https://x.go.jp/b",
         "verified": True, "deadline_type": "常時", "deadline": None},
        {"id": "c", "name": "未検証", "source_url": "https://x.go.jp/c",
         "verified": False, "deadline_type": "常時", "deadline": None},
    ]}
    r = Report()
    check_neta(r, {"updated_at": "2026-09-21", "items": [
        {"no": 1, "source_url": "https://x.go.jp/a", "caution": "x"}]}, seido, today)
    expect(any(x["check"] == "neta-deadline" for x in r.ng), "締切まで9日の制度をSNSネタから弾く")
    r = Report()
    check_neta(r, {"updated_at": "2026-09-21", "items": [
        {"no": 1, "source_url": "https://x.go.jp/b", "caution": "x"}]}, seido, today)
    expect(len(r.ng) == 0, "常時の検証済み制度は通す")
    r = Report()
    check_neta(r, {"updated_at": "2026-09-21", "items": [
        {"no": 1, "source_url": "https://x.go.jp/c", "caution": "x"}]}, seido, today)
    expect(any(x["check"] == "neta-source" for x in r.ng), "未検証の制度を弾く")
    r = Report()
    check_neta(r, {"updated_at": "2026-09-21", "items": [
        {"no": 1, "source_url": "https://x.go.jp/b"}]}, seido, today)
    expect(any(x["check"] == "neta-caution" for x in r.ng), "caution 欠けを弾く")
    r = Report()
    check_neta(r, {"updated_at": "2026-09-01", "items": []}, seido, today)
    expect(any(x["check"] == "neta-fresh" for x in r.todo), "20日前のネタを TODO にする(NGにはしない)")

    # 3) ワークフロー: 生成しているのに add していない → NG
    r = Report()
    check_workflow_add_list(r, "run: python scripts/generate_life_pages.py\n  git add site/fukugiiro/area\n")
    expect(any(x["check"] == "wf-add" for x in r.ng), "addリスト漏れを検出する")
    r = Report()
    check_workflow_add_list(r, "run: python scripts/generate_life_pages.py\n  git add site/fukugiiro/life\n")
    expect(len(r.ng) == 0, "addされていれば通す")

    # 4) doc参照: 他リポジトリ表記とテンプレートは拾わない
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "t.md")
        open(p, "w", encoding="utf-8").write(
            "読み替え表は `kakei-crm/docs/appointment/README.md` にある\n"
            "非公開repo `docs/somewhere.md` を参照\n"
            "議事は `docs/議事_YYYYMMDD_<件名>.md` に置く\n")
        r = Report()
        check_doc_refs(r, [p])
        expect(len(r.ng) == 0, "他リポ・非公開repo・テンプレート表記を誤検出しない")
        open(p, "w", encoding="utf-8").write("詳細は docs/nonexistent-xyz.md を参照\n")
        r = Report()
        check_doc_refs(r, [p])
        expect(len(r.ng) == 1, "実在しない案内を検出する")

    # 5) 禁止表現
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "t.html")
        open(p, "w", encoding="utf-8").write("<p>締切7日前にお知らせします</p>")
        r = Report()
        check_banned_phrases(r, [p])
        expect(len(r.ng) == 1, "「締切7日前」を検出する")

    # 6) 人の作業待ちは TODO であって NG ではない
    r = Report()
    check_human_todos(r, {"last_status": "未接続(...)", "history": [{"date": "2026-09-21", "followers": 0}]},
                      date(2026, 9, 21))
    expect(len(r.ng) == 0 and len(r.todo) == 2, "未接続と0人を TODO として出す(CIは止めない)")

    # 7) 見直し期限
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "議事_x.md")
        open(p, "w", encoding="utf-8").write("- 見直し期限: **2026-09-01**(3ヶ月)\n")
        r = Report()
        check_review_deadlines(r, [p], date(2026, 9, 21))
        expect(any("過ぎ" in x["msg"] for x in r.todo), "期限切れの議事を検出する")

    print("self-test:", "OK" if ok else "NG")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description="もらいわすれ堂 自己点検")
    ap.add_argument("--json", action="store_true", help="機械可読で出力")
    ap.add_argument("--self-test", action="store_true", help="検査そのものをテスト")
    ap.add_argument("--update-baseline", action="store_true",
                    help="いまの NG を既知の負債として記録する(直したあとに実行して減らす)")
    a = ap.parse_args()
    if a.self_test:
        return self_test()

    rep = run()
    base = load_baseline()
    fresh = [x for x in rep.ng if fingerprint(x) not in base]
    known = [x for x in rep.ng if fingerprint(x) in base]

    if a.update_baseline:
        os.makedirs(os.path.dirname(BASELINE), exist_ok=True)
        with open(BASELINE, "w", encoding="utf-8") as f:
            json.dump({"note": "既知の負債。新しく増えた NG だけ CI を止める。"
                               "直したら --update-baseline で減らす",
                       "updated_at": datetime.now(JST).strftime("%Y-%m-%d"),
                       "accepted": sorted(fingerprint(x) for x in rep.ng)},
                      f, ensure_ascii=False, indent=1)
            f.write("\n")
        print(f"ベースラインを更新しました: 既知 {len(rep.ng)} 件")
        return 0

    if a.json:
        d = rep.as_dict()
        d["fresh_ng"] = fresh
        d["known_ng_count"] = len(known)
        print(json.dumps(d, ensure_ascii=False, indent=1))
        return 1 if fresh else 0

    for x in fresh:
        print(f"[NG]   {x['check']}: {x['msg']}")
    for x in rep.warn:
        print(f"[WARN] {x['check']}: {x['msg']}")
    for x in rep.todo:
        print(f"[TODO] {x['check']}: {x['msg']}")
    print(f"\n自己点検: 新規NG {len(fresh)} / 既知の負債 {len(known)} / "
          f"WARN {len(rep.warn)} / 人の作業待ち {len(rep.todo)}")
    if fresh:
        print("新しい NG があります。掲載や配信の前に直してください。")
    elif known:
        print(f"新規の NG はありません(既知の負債 {len(known)} 件は --json で確認できます)。")
    return 1 if fresh else 0


if __name__ == "__main__":
    sys.exit(main())
