#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ワークフローの鍵の扱いの検査(2026-11-03 GLOW Instagram 安全対策・鍵漏えい防止)。

公開リポジトリの Actions のログは誰でも読める。鍵を含む命令の書き出しや、承認ボタン
(environment)を通らずに Meta へ投稿できる経路を、機械で止める。

規則(一致した値は出力しない。出すのは規則・ファイル・ジョブ名・行番号だけ):
  W1 鍵を使うジョブの中で、実行の書き出し(set -x / set -o xtrace / bash -x)を使っている
  W2 run: の中に ${{ secrets.* }} を直接埋め込んでいる(env 経由で渡すこと)
  W3 run: の中で access_token= を命令の引数に載せている(鍵がコマンドラインに出る)
  W4 Meta の投稿用の鍵を、承認(environment:)の無いジョブに渡している
  W5 承認(environment:)の無いジョブが、Meta の投稿の窓口(graph.facebook.com)を直接呼んでいる
  W6 Meta の投稿用の鍵を、ワークフロー全体(workflow レベルの env)に置いている
  W7 Meta の投稿用の鍵を持つジョブが、リポジトリへの書き込み権限(contents: write)を持っている
  W8 ワークフローを読めない(壊れている)のに、Meta の投稿用の鍵の名前が書いてある

既知の例外(KNOWN_EXCEPTIONS)は、理由と対応予定つきで1件ずつ名指しする。
例外は「安全」という意味ではない。毎回、件数と理由を表示する。
例外にない違反が1件でもあれば exit 1。検査が成り立たないとき(0件・読めない)は exit 2。

使い方:
  python3 scripts/check_workflow_secret_hygiene.py            # .github/workflows を検査
  python3 scripts/check_workflow_secret_hygiene.py --selftest # 正例・負例の自己テスト
"""
import glob
import os
import re
import sys

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

BASE = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
META_PUBLISH_SECRETS = ("FB_PAGE_ACCESS_TOKEN", "GLOW_FB_PAGE_TOKEN")

# (ファイル名, ジョブ名, 規則) → 理由。ジョブ名 "*" はファイル全体
KNOWN_EXCEPTIONS = {
    ("glow-sns-post.yml", "post", "W4"): "世界の架け橋。承認の仕組みは M3 で入れる(鍵は未登録・定期実行の一時停止は決裁待ち)",
    ("weekly-report.yml", "report", "W4"): "投稿用の鍵で数字を読んでいる。読み取り専用の鍵へ分ける(M4)",
    ("weekly-report.yml", "report", "W7"): "同上。鍵を分ければ解消",
    ("funnel-deep-dive.yml", "report", "W4"): "投稿用の鍵で数字を読んでいる。読み取り専用の鍵へ分ける(M4)",
    ("funnel-deep-dive.yml", "report", "W7"): "同上。鍵を分ければ解消",
    ("social-post.yml", "post", "W7"): "二重投稿防止の記録をコミットするため。承認後のジョブに限る。記録用ジョブの分離は別途",
    ("post-resort-kingdom.yml", "post", "W4"): "2026-10-16 に手動で無効化済み。ファイルの削除は別承認",
    ("fukuda-data-import.yml", "validate-and-import", "W2"): "Instagram とは別件(2026-11-03 検出)。env 経由で渡す形へ直す(別承認)",
    ("resort-kingdom-post.yml", "*", "W8"): "2026-10-16 に手動で無効化済み・設定ファイルが壊れている。削除は別承認",
}

XTRACE = re.compile(r"(^|[;&|\s])(set\s+-[A-Za-z]*x[A-Za-z]*\b|set\s+-o\s+xtrace\b|bash\s+-[A-Za-z]*x\b)", re.M)
SECRET_IN_RUN = re.compile(r"\$\{\{\s*secrets\.")
TOKEN_ARG = re.compile(r"access_token=", re.I)
GRAPH = re.compile(r"graph\.facebook\.com")
SECRET_REF = re.compile(r"secrets\.([A-Za-z0-9_]+)")


def _walk_strings(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for k, v in obj.items():
            yield from _walk_strings(k)
            yield from _walk_strings(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk_strings(v)


def _line_of(text, needle_re, start_hint=None):
    lines = text.splitlines()
    for i, line in enumerate(lines, 1):
        if needle_re.search(line):
            return i
    return 0


def _job_secrets(job):
    names = set()
    for s in _walk_strings(job):
        names.update(SECRET_REF.findall(s))
    return names


def _job_write(job, wf_perm):
    perm = job.get("permissions", wf_perm)
    if perm in ("write-all",):
        return True
    if isinstance(perm, dict):
        return perm.get("contents") == "write"
    return perm is None  # 指定なし=既定の権限(書き込みになり得る)を危険側に数える


def check_text(fname, text):
    """1ファイルを検査し、(規則, ジョブ, 行, 説明) の一覧を返す。"""
    found = []
    try:
        wf = yaml.safe_load(text) if yaml else None
    except Exception:  # noqa: BLE001
        wf = None
    if not isinstance(wf, dict) or not isinstance(wf.get("jobs"), dict):
        if any(k in text for k in META_PUBLISH_SECRETS):
            found.append(("W8", "*", 0, "ワークフローを読めないが、Meta の投稿用の鍵の名前がある"))
        return found
    wf_env = wf.get("env") or {}
    for s in _walk_strings(wf_env):
        if any(k in s for k in META_PUBLISH_SECRETS):
            found.append(("W6", "*", _line_of(text, re.compile(r"^env:")), "Meta の投稿用の鍵をワークフロー全体に置いている"))
            break
    wf_perm = wf.get("permissions")
    wf_secrets = _job_secrets(wf_env)
    for jname, job in wf["jobs"].items():
        if not isinstance(job, dict):
            continue
        secrets_used = _job_secrets(job) | wf_secrets
        has_meta = any(k in secrets_used for k in META_PUBLISH_SECRETS)
        gated = bool(job.get("environment"))
        steps = job.get("steps") or []
        for st in steps:
            if not isinstance(st, dict):
                continue
            run = st.get("run")
            if not isinstance(run, str):
                continue
            if secrets_used and XTRACE.search(run):
                found.append(("W1", jname, _line_of(text, XTRACE), "鍵を使うジョブで実行の書き出し(set -x 等)を使っている"))
            if SECRET_IN_RUN.search(run):
                found.append(("W2", jname, _line_of(text, SECRET_IN_RUN), "run の中に secrets を直接埋め込んでいる"))
            if TOKEN_ARG.search(run):
                found.append(("W3", jname, _line_of(text, TOKEN_ARG), "access_token= を命令の引数に載せている"))
            if not gated and GRAPH.search(run):
                found.append(("W5", jname, _line_of(text, GRAPH), "承認の無いジョブが Meta の投稿の窓口を直接呼んでいる"))
        if has_meta and not gated:
            found.append(("W4", jname, 0, "Meta の投稿用の鍵を、承認(environment)の無いジョブに渡している"))
        if has_meta and _job_write(job, wf_perm):
            found.append(("W7", jname, 0, "Meta の投稿用の鍵を持つジョブに書き込み権限がある"))
    # 同じ (規則, ジョブ) は1件にまとめる
    uniq, seen = [], set()
    for f in found:
        key = (f[0], f[1])
        if key not in seen:
            seen.add(key)
            uniq.append(f)
    return uniq


def classify(fname, found):
    new, known = [], []
    for rule, job, line, msg in found:
        reason = KNOWN_EXCEPTIONS.get((fname, job, rule)) or KNOWN_EXCEPTIONS.get((fname, "*", rule))
        (known if reason else new).append((rule, job, line, msg, reason))
    return new, known


def run(paths):
    if yaml is None:
        print("[ng] 検査に必要な部品(PyYAML)がありません。検査できないため失敗にします")
        return 2
    if not paths:
        print("[ng] 検査するワークフローが0件です。検査できないため失敗にします")
        return 2
    total_new, total_known, used_exc = 0, 0, set()
    for p in sorted(paths):
        fname = os.path.basename(p)
        with open(p, encoding="utf-8") as f:
            text = f.read()
        new, known = classify(fname, check_text(fname, text))
        for rule, job, line, msg, _ in new:
            total_new += 1
            loc = f"{fname}:{line}" if line else fname
            print(f"::error file=.github/workflows/{fname}::[{rule}] {loc} ジョブ {job}: {msg}")
        for rule, job, line, msg, reason in known:
            total_known += 1
            used_exc.add((fname, job, rule))
            print(f"[既知の例外] [{rule}] {fname} ジョブ {job}: {msg} — {reason}")
    stale = [k for k in KNOWN_EXCEPTIONS if k not in used_exc and any(os.path.basename(p) == k[0] for p in paths)]
    for k in stale:
        print(f"[情報] 例外 {k} は該当がなくなりました。例外の一覧から外せます")
    print(f"[結果] 検査 {len(paths)} 件 / 新しい違反 {total_new} 件 / 既知の例外 {total_known} 件"
          "(既知の例外は安全という意味ではありません)")
    return 1 if total_new else 0


def selftest():
    bad_xtrace = """
jobs:
  post:
    runs-on: ubuntu-latest
    environment: sns-approval
    steps:
      - env:
          TOKEN: ${{ secrets.FB_PAGE_ACCESS_TOKEN }}
        run: |
          set -e
          set -x
          echo hi
"""
    good = """
permissions:
  contents: read
jobs:
  preview:
    runs-on: ubuntu-latest
    steps:
      - env:
          TOKEN: ${{ secrets.LINE_CHANNEL_ACCESS_TOKEN }}
        run: echo "offset -x is text" && python x.py --max-x 3
  post:
    runs-on: ubuntu-latest
    environment: sns-approval
    permissions:
      contents: read
    steps:
      - env:
          FB_PAGE_ACCESS_TOKEN: ${{ secrets.FB_PAGE_ACCESS_TOKEN }}
        run: python scripts/post_social.py --stem a
"""
    ungated = """
permissions:
  contents: read
jobs:
  post:
    runs-on: ubuntu-latest
    steps:
      - env:
          TOKEN: ${{ secrets.FB_PAGE_ACCESS_TOKEN }}
        run: curl -X POST https://graph.facebook.com/v21.0/x/media -d "access_token=${TOKEN}"
"""
    inline = """
jobs:
  a:
    runs-on: ubuntu-latest
    permissions:
      contents: read
    steps:
      - run: echo ${{ secrets.LINE_CHANNEL_ACCESS_TOKEN }}
"""
    wf_env = """
env:
  T: ${{ secrets.GLOW_FB_PAGE_TOKEN }}
jobs:
  a:
    runs-on: ubuntu-latest
    environment: x
    permissions:
      contents: write
    steps:
      - run: set -ex; python y.py
"""
    broken = "jobs:\n  a:\n    steps: [\nFB_PAGE_ACCESS_TOKEN\n"
    rules = lambda t: sorted({f[0] for f in check_text("t.yml", t)})  # noqa: E731
    assert rules(bad_xtrace) == ["W1", "W7"], rules(bad_xtrace)   # 権限指定なし=危険側
    assert rules(good) == [], rules(good)
    assert rules(ungated) == ["W3", "W4", "W5"], rules(ungated)
    assert rules(inline) == ["W2"], rules(inline)
    assert rules(wf_env) == ["W1", "W6", "W7"], rules(wf_env)
    assert rules(broken) == ["W8"], rules(broken)
    # 出力に値が出ないこと: 説明文に secrets の名前の値(${{ }})を含めない
    for t in (bad_xtrace, ungated, inline, wf_env):
        for f in check_text("t.yml", t):
            assert "${{" not in f[3]
    # 例外の名指し: ファイル・ジョブ・規則が一致したときだけ例外になる
    n, k = classify("glow-sns-post.yml", [("W4", "post", 0, "m")])
    assert not n and k
    n, k = classify("glow-sns-post.yml", [("W1", "post", 0, "m")])
    assert n and not k
    print("[ok] check_workflow_secret_hygiene selftest")
    return 0


def main(argv):
    if "--selftest" in argv:
        return selftest()
    paths = glob.glob(os.path.join(BASE, ".github", "workflows", "*.yml")) + \
        glob.glob(os.path.join(BASE, ".github", "workflows", "*.yaml"))
    return run(paths)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
