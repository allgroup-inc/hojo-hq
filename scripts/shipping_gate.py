#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hojo-hq — 出荷ゲートの通過記録と検査(運用規程1-3の実装)

運用規程1-3: 対外文面は hojo-accuracy-check → hojo-deadline-alert → humanizer の
3スキル通過が出荷条件。しかし通過したかどうかが成果物に残っていなかったため、
「通したつもり」を後から検証できなかった(点検: docs/点検_20260817_スキル適用と完成度.md ⑤)。

二層構造(議事: docs/議事_20260817_出荷ゲート通過記録.md):
  [機械が検査する層] 禁止語・lin.ee直貼り・記録の鮮度 → 申告があっても違反ならNG
  [申告する層]       humanizerの自然さなど人の判断が要る部分 → 生成器が checked 日付を申告
申告だけでは嘘をつけてしまうため、機械で検査できるものは必ず機械で落とす。
申告部分は週次レポ§4の無作為点検(独立監査)で拾う。

記録の形式(生成物のmarkdown末尾に生成器が出力する):

    ## 出荷ゲート
    - gates: accuracy-check, deadline-alert, humanizer
    - checked: 2026-08-17
    - by: scripts/generate_sns.py

使い方:
  python scripts/shipping_gate.py --check posts/launch/01_launch.md
  python scripts/shipping_gate.py --check-group sns  # 配信経路ごとに検査(CI用・sns/line)
  python scripts/shipping_gate.py --check-all        # 対外文面をまとめて検査
  python scripts/shipping_gate.py --self-test
"""
import glob
import os
import re
import sys
from datetime import date, datetime, timedelta, timezone

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

JST = timezone(timedelta(hours=9))
BASE = os.path.join(os.path.dirname(__file__), "..")

REQUIRED_GATES = ("accuracy-check", "deadline-alert", "humanizer")

# 記録の鮮度。制度の件数・締切は動くため、古い記録のまま出し続けさせない。
MAX_AGE_DAYS = 90    # これを超えたら出荷停止(再点検が必要)
WARN_AGE_DAYS = 76   # 残り14日で警告(黙って止まるのを防ぐ)

# 機械で検査する禁止パターン。スタンプがあっても、ここに引っかかれば出荷しない。
FORBIDDEN = (
    (r"締切\s*[の]?\s*7\s*日前",
     "「締切7日前」はCLAUDE.mdで誤りと明記(7日前では書類・gBizIDの準備が間に合わない)。"
     "利用者向けは「締切の約1か月前から」に統一する"),
    (r"7\s*日前\s*(?:に|から)?\s*(?:お知らせ|通知|アラート|配信)",
     "同上(締切3層ルール違反)"),
    (r"必ず\s*(?:もらえ|受け取れ|通り|採択)",
     "断定表現。絶対ルール1(不明時は「要確認」・断定しない)違反"),
    (r"確実に\s*(?:もらえ|受給|採択|通)",
     "断定表現。絶対ルール1違反"),
    (r"誰でも\s*(?:もらえ|受け取れ|申請できま)",
     "断定表現。要件を満たさない事業者に誤解を与える"),
    (r"https?://lin\.ee/",
     "lin.ee の直貼り。go-link-discipline により /go/<チャネル>/ を経由すること"),
)

GATE_HEAD_RE = re.compile(r"^##\s*出荷ゲート\s*$", re.M)
DATE_RE = re.compile(r"(20\d{2}-\d{2}-\d{2})")


# ---------------------------------------------------------------- 記録の読み書き

def render_stamp(by, checked, gates=REQUIRED_GATES):
    """生成器が出力する出荷ゲート記録(markdown節)を組み立てる。"""
    return (
        "## 出荷ゲート\n"
        f"- gates: {', '.join(gates)}\n"
        f"- checked: {checked}\n"
        f"- by: {by}\n"
    )


def parse_stamp(text):
    """出荷ゲート記録を読み取る。無ければ None。"""
    m = GATE_HEAD_RE.search(text or "")
    if not m:
        return None
    body = text[m.end():]
    nxt = re.search(r"^##\s", body, re.M)
    if nxt:
        body = body[: nxt.start()]
    gates = []
    gm = re.search(r"^-\s*gates:\s*(.+)$", body, re.M)
    if gm:
        gates = [g.strip() for g in gm.group(1).split(",") if g.strip()]
    checked = None
    cm = re.search(r"^-\s*checked:\s*(.+)$", body, re.M)
    if cm:
        dm = DATE_RE.search(cm.group(1))
        if dm:
            try:
                checked = datetime.strptime(dm.group(1), "%Y-%m-%d").date()
            except ValueError:
                checked = None
    bm = re.search(r"^-\s*by:\s*(.+)$", body, re.M)
    return {"gates": gates, "checked": checked, "by": bm.group(1).strip() if bm else None}


# ---------------------------------------------------------------- 検査

def check_forbidden(text):
    """機械で検査できる違反(申告より優先。申告があってもここで落とす)。"""
    out = []
    for pat, why in FORBIDDEN:
        m = re.search(pat, text or "")
        if m:
            out.append(f"禁止表現「{m.group(0)}」— {why}")
    return out


def verify(text, today=None, label=""):
    """対外文面を検査する。

    返り値: (ok, problems, warnings)
      ok=False なら出荷しない(フェイルクローズ)。warnings は出荷は止めないが要対応。
    """
    today = today or datetime.now(JST).date()
    problems = check_forbidden(text)
    warnings = []

    def result():
        p = [f"{label}: {x}" for x in problems] if label else problems
        w = [f"{label}: {x}" for x in warnings] if label else warnings
        return (not problems, p, w)

    stamp = parse_stamp(text)
    if stamp is None:
        problems.append(
            "出荷ゲートの通過記録がない。生成器に shipping_gate.render_stamp() の出力を"
            "追加し、3スキル(accuracy-check/deadline-alert/humanizer)を通してから出荷する"
        )
        return result()

    missing = [g for g in REQUIRED_GATES if g not in stamp["gates"]]
    if missing:
        problems.append(f"未通過のゲート: {', '.join(missing)}")

    if stamp["checked"] is None:
        problems.append("checked の日付が読めない(YYYY-MM-DD で記録する)")
    else:
        age = (today - stamp["checked"]).days
        if age < 0:
            problems.append(f"checked が未来日({stamp['checked']})。記録として無効")
        elif age > MAX_AGE_DAYS:
            problems.append(
                f"記録が古い({stamp['checked']} / {age}日経過 > {MAX_AGE_DAYS}日)。"
                "件数・締切が動いている可能性があるため再点検が必要"
            )
        elif age > WARN_AGE_DAYS:
            warnings.append(
                f"記録の期限が近い({age}日経過 / {MAX_AGE_DAYS}日で出荷停止)。"
                "文面を3スキルで見直して checked を更新すること"
            )

    if not stamp.get("by"):
        warnings.append("by(誰が通したか)が未記入")

    return result()


def verify_file(path, today=None):
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except OSError as e:
        return (False, [f"{path}: 読み込めない({e})"], [])
    return verify(text, today=today, label=os.path.relpath(path, BASE))


# ---------------------------------------------------------------- 一括検査(CI用)

# 対外に出る文面。ここに載っていないものは検査されないので、新しい出力先を作ったら足す。
# グループを分けているのは、配信経路ごとに独立して止めるため
# (LINE下書きの違反でInstagram投稿まで巻き添えで止めない)。
TARGET_GROUPS = {
    "sns":  ("posts/launch/*.md", "posts/carousel/caption.md"),
    "line": ("posts/line/alerts_latest.md",),
}


def collect_targets(base=BASE, group=None):
    globs = TARGET_GROUPS[group] if group else tuple(
        g for gs in TARGET_GROUPS.values() for g in gs)
    out = []
    for g in globs:
        out.extend(sorted(glob.glob(os.path.join(base, g))))
    return out


def check_all(base=BASE, today=None, group=None):
    targets = collect_targets(base, group)
    if not targets:
        print("[warn] 検査対象が1件も見つかりません(生成器を先に実行してください)")
        return 0
    ng = 0
    for p in targets:
        ok, problems, warnings = verify_file(p, today=today)
        for w in warnings:
            print(f"[warn] {w}")
        if not ok:
            ng += 1
            for pr in problems:
                print(f"[ng] {pr}")
    if ng:
        print(f"\n出荷ゲート: {len(targets)}件中 {ng}件が不合格。**この文面は出荷しない**")
        return 1
    print(f"出荷ゲート OK: {len(targets)}件すべて通過記録あり・禁止表現なし")
    return 0


# ---------------------------------------------------------------- 自己テスト

_OK_DOC = """# 投稿1

## キャプション
沖縄で今使える補助金・助成金。締切の約1か月前からLINEでお知らせします。

## 出荷ゲート
- gates: accuracy-check, deadline-alert, humanizer
- checked: 2026-08-17
- by: scripts/generate_sns.py
"""


def self_test():
    failed = 0
    total = 0
    today = date(2026, 8, 17)

    def check(name, cond, detail=""):
        nonlocal failed, total
        total += 1
        if not cond:
            failed += 1
            print(f"[SELFTEST FAIL] {name} {detail}")

    # 1) 正例
    ok, pr, wn = verify(_OK_DOC, today=today)
    check("ok.pass", ok, f"problems={pr}")
    check("ok.no_warn", not wn, f"warnings={wn}")

    # 2) 記録なし → 不合格(フェイルクローズ)
    ok, pr, _ = verify("## キャプション\nこんにちは\n", today=today)
    check("no_stamp.ng", not ok)
    check("no_stamp.reason", any("通過記録がない" in p for p in pr), f"got {pr}")

    # 3) ゲート欠け
    doc = _OK_DOC.replace("accuracy-check, deadline-alert, humanizer", "accuracy-check")
    ok, pr, _ = verify(doc, today=today)
    check("missing_gate.ng", not ok)
    check("missing_gate.names",
          any("deadline-alert" in p and "humanizer" in p for p in pr), f"got {pr}")

    # 4) 鮮度(期限内 / 警告 / 超過 / 未来日)
    def with_date(d):
        return _OK_DOC.replace("2026-08-17", d)
    ok, _, wn = verify(with_date("2026-08-01"), today=today)
    check("age.fresh", ok and not wn)
    ok, _, wn = verify(with_date("2026-05-25"), today=today)   # 84日経過
    check("age.warn", ok and any("期限が近い" in w for w in wn), f"warnings={wn}")
    ok, pr, _ = verify(with_date("2026-01-01"), today=today)   # 228日経過
    check("age.expired", not ok and any("記録が古い" in p for p in pr), f"got {pr}")
    ok, pr, _ = verify(with_date("2026-12-31"), today=today)
    check("age.future", not ok and any("未来日" in p for p in pr), f"got {pr}")
    ok, pr, _ = verify(_OK_DOC.replace("- checked: 2026-08-17", "- checked: いつか"), today=today)
    check("age.unparsable", not ok and any("読めない" in p for p in pr), f"got {pr}")

    # 5) 機械検査は申告より優先(スタンプがあっても禁止表現は落とす)
    bad = _OK_DOC.replace("締切の約1か月前から", "締切7日前に")
    ok, pr, _ = verify(bad, today=today)
    check("forbidden.deadline7", not ok and any("7日前" in p for p in pr), f"got {pr}")
    bad = _OK_DOC.replace("お知らせします", "必ずもらえます")
    ok, pr, _ = verify(bad, today=today)
    check("forbidden.assert", not ok and any("断定" in p for p in pr), f"got {pr}")
    bad = _OK_DOC.replace("お知らせします", "登録は https://lin.ee/xxxx から")
    ok, pr, _ = verify(bad, today=today)
    check("forbidden.linee", not ok and any("lin.ee" in p for p in pr), f"got {pr}")
    # 正当な「必ず」(原文確認の注意書き)は落とさない
    good = _OK_DOC.replace("お知らせします", "要件は必ず原文の公募要領でご確認ください")
    ok, _, _ = verify(good, today=today)
    check("forbidden.no_false_positive", ok)

    # 6) 記録の組み立て → 読み取りの往復
    st = parse_stamp(render_stamp("scripts/x.py", "2026-08-17"))
    check("roundtrip.gates", st and list(st["gates"]) == list(REQUIRED_GATES), f"got {st}")
    check("roundtrip.checked", st and st["checked"] == date(2026, 8, 17))
    check("roundtrip.by", st and st["by"] == "scripts/x.py")
    check("parse.none", parse_stamp("## キャプション\n本文\n") is None)

    # 7) ラベル付与(どのファイルが落ちたか分かること)
    ok, pr, _ = verify("本文のみ", today=today, label="posts/launch/01.md")
    check("label", not ok and pr[0].startswith("posts/launch/01.md: "), f"got {pr}")

    # 8) 配信経路グループ(LINEの違反でSNS投稿を巻き添えにしない分離)
    check("group.names", set(TARGET_GROUPS) == {"sns", "line"}, f"got {set(TARGET_GROUPS)}")
    sns_t = collect_targets(group="sns")
    line_t = collect_targets(group="line")
    check("group.disjoint", not (set(sns_t) & set(line_t)))
    check("group.all_is_union", set(collect_targets()) == set(sns_t) | set(line_t))
    check("group.sns_found", len(sns_t) >= 1, f"got {len(sns_t)}")

    if failed:
        print(f"自己テスト失敗: {failed} 件")
        return 1
    print(f"自己テスト OK: {total}チェック(記録なし/ゲート欠け/鮮度4種/禁止表現3種+誤検知なし/往復)")
    return 0


def main():
    if "--self-test" in sys.argv:
        return self_test()
    if "--check-all" in sys.argv:
        return check_all()
    if "--check-group" in sys.argv:
        i = sys.argv.index("--check-group")
        name = sys.argv[i + 1] if i + 1 < len(sys.argv) else ""
        if name not in TARGET_GROUPS:
            print(f"[ng] 不明なグループ「{name}」。使えるのは: {', '.join(TARGET_GROUPS)}")
            return 2
        return check_all(group=name)
    args = [a for a in sys.argv[1:] if a != "--check"]
    if not args:
        print(__doc__)
        return 2
    rc = 0
    for p in args:
        ok, problems, warnings = verify_file(p)
        for w in warnings:
            print(f"[warn] {w}")
        for pr in problems:
            print(f"[ng] {pr}")
        if ok:
            print(f"[ok] {p}")
        else:
            rc = 1
    return rc


if __name__ == "__main__":
    sys.exit(main())
