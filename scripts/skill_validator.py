#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""WikiSkill M3 / Component G: Skill Validator(人間が指定した修正案だけを、読むだけで検査する)。

統合設計書の G(Skill Validator)に従う: 旧 Skill と新 Skill を同じ Evaluation Set で比べ、
回帰(性能低下)があれば不合格にする。測定できない改善は、改善とは扱わない。

使い方:
  python3 scripts/skill_validator.py --skill <name> --candidate <修正案のパス> \
      --evals <evals.jsonl> --results <results.jsonl> [--proposal <docs/proposals/...md>] [--save]

入力(すべて人間が明示的に指定する。探索や自動取得はしない):
  --candidate  修正案の SKILL.md(人間が用意したもの。G は内容を生成しない)
  --evals      Evaluation Set。1行1ケース: {"case_id": "...", ...}(本文は読まない)
  --results    測定結果。1行1件: {"case_id": "...", "variant": "old"|"new", "outcome": "pass"|"fail"|"error"}
  --proposal   根拠として参照する F の提案書(docs/proposals/ の中のもの。参照するだけ)

判定:
  - 不合格: 互換性の検査に落ちた / 回帰(旧で通り、新で落ちたケース)がある
  - 合格  : 互換性の検査を通り、回帰がなく、測定された成功率が改善した(十分な件数がある)
            ※ 合格は承認ではない。自動採用はしない。三名体制レビューと小柳さんの決裁を経る
  - 判定不能: 修正案がない / 測定結果がない・件数が足りない / 改善が測定されなかった

安全のための規則:
  - 読むだけ。Skill 本体・入力ファイルは変えない。書くのは --save の検証報告1件だけ(上書きしない)
  - 外部通信をしない(ネットワークのモジュールを使わない)
  - 外部コマンドは許可リスト方式: git の rev-parse / show のうち、決まった形の引数だけ(shell を使わない)
  - 報告には修正案の本文を出さない。機密の疑いがあれば保存しない(規則名だけを表示)
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import skill_proposer as sp  # noqa: E402  — 機密の検査(scan_text)と提案書の形式を再利用する

SKILLS_DIR = ".claude/skills"
EVAL_DIR = "docs/evaluations"
SCHEMA = "skill-validation/v1"
MIN_CASES = 10            # 比べられたケースがこれより少なければ、成功率の差を改善とは扱わない
MAX_BYTES = 200_000       # 修正案の大きさの上限
_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_CASE_ID = re.compile(r"^[A-Za-z0-9._:-]{1,64}$")
_DATASET_ID = re.compile(r"^[A-Za-z0-9._:-]{1,64}$")
_COMMITTED = re.compile(rf"^HEAD:{re.escape(SKILLS_DIR)}/[A-Za-z0-9][A-Za-z0-9._-]{{0,63}}/SKILL\.md$")
OUTCOMES = {"pass", "fail", "error"}
VARIANTS = {"old", "new"}


class CommandNotAllowed(PermissionError):
    """許可リストにない外部コマンドは実行しない。"""


def run_allowed(root: Path, args: list[str]) -> subprocess.CompletedProcess:
    """許可リストの git 呼び出しだけを実行する(shell を使わない・引数の形を固定)。

    許可: git show HEAD:.claude/skills/<name>/SKILL.md(比較の基準の読み取りだけ)
    """
    if not (len(args) == 2 and args[0] == "show" and _COMMITTED.match(args[1])):
        raise CommandNotAllowed(f"許可されていないコマンドです: {args[:1]}")
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=False,
                          timeout=30, shell=False, check=False)


def committed_skill_text(root: Path, name: str) -> str | None:
    """コミット済みの SKILL.md(比較の基準)。無ければ None。読むだけ。"""
    try:
        out = run_allowed(root, ["show", f"HEAD:{SKILLS_DIR}/{name}/SKILL.md"])
    except (CommandNotAllowed, OSError, subprocess.SubprocessError):
        return None
    return out.stdout.decode("utf-8", errors="replace") if out.returncode == 0 else None


def frontmatter_keys(text: str) -> tuple[bool, dict[str, str]]:
    """先頭の frontmatter の、一番上の階層の項目。(あるか, {項目: 値})。"""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return False, {}
    out: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            return True, out
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*):\s*(.*)$", line)
        if m:
            out[m.group(1)] = m.group(2).strip()
    return False, {}  # 閉じの --- が無い


def diff_summary(old: str, new: str) -> dict:
    """変更の大きさだけを数える(本文は出さない)。"""
    old_lines, new_lines = old.splitlines(), new.splitlines()
    old_h = [line for line in old_lines if line.startswith("#")]
    new_h = [line for line in new_lines if line.startswith("#")]
    return {
        "lines_old": len(old_lines), "lines_new": len(new_lines),
        "bytes_old": len(old.encode("utf-8")), "bytes_new": len(new.encode("utf-8")),
        "headings_added": len([h for h in new_h if h not in old_h]),
        "headings_removed": len([h for h in old_h if h not in new_h]),
    }


def compatibility(skill: str, old: str | None, candidate: str) -> list[str]:
    """互換性の検査。問題の一覧(空なら問題なし)。本文は出さない。"""
    problems = []
    size = len(candidate.encode("utf-8"))
    if size > MAX_BYTES:
        problems.append(f"サイズが上限({MAX_BYTES} バイト)を超えています")
    has_fm, new_fm = frontmatter_keys(candidate)
    if not has_fm:
        problems.append("frontmatter(先頭の --- ... ---)がありません")
        return problems
    if new_fm.get("name", "").strip().strip("\"'") != skill:
        problems.append("frontmatter の name が Skill 名と一致しません(名前の変更は不可)")
    if not new_fm.get("description", "").strip():
        problems.append("frontmatter の description が空です(起動の条件が失われます)")
    if old is not None:
        _, old_fm = frontmatter_keys(old)
        removed = sorted(set(old_fm) - set(new_fm))
        if removed:
            problems.append(f"frontmatter の項目が削除されています: {', '.join(removed)}")
    hits = sp.scan_text(candidate)
    if hits:
        problems.append(f"機密の疑いのある内容(規則: {', '.join(sorted(set(hits)))})")
    return problems


def load_evals(path: Path) -> set[str]:
    cases: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except ValueError:
            continue
        cid = obj.get("case_id") if isinstance(obj, dict) else None
        if isinstance(cid, str) and _CASE_ID.match(cid):
            cases.add(cid)
    return cases


def load_results(path: Path) -> tuple[dict[str, dict[str, str]], int]:
    """測定結果 {variant: {case_id: outcome}} と、使えなかった行の数。同じケースで結果が食い違うものは使わない。"""
    seen: dict[tuple[str, str], set[str]] = {}
    errored: set[tuple[str, str]] = set()
    bad = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except ValueError:
            bad += 1
            continue
        if not isinstance(obj, dict):
            bad += 1
            continue
        cid, var, out = obj.get("case_id"), obj.get("variant"), obj.get("outcome")
        if not (isinstance(cid, str) and _CASE_ID.match(cid) and var in VARIANTS and out in OUTCOMES):
            bad += 1
            continue
        if out == "error":
            bad += 1  # 測定に失敗したケースは、その変種の結果を採らない(前の成功も無効にする)
            errored.add((var, cid))
            continue
        seen.setdefault((var, cid), set()).add(out)
    result: dict[str, dict[str, str]] = {v: {} for v in VARIANTS}
    for (var, cid), outs in seen.items():
        if (var, cid) in errored:
            continue
        if len(outs) == 1:
            result[var][cid] = outs.pop()
        else:
            bad += 1  # 同じケースで食い違う結果は採らない
    return result, bad


PROVENANCE_REASON = {
    "missing": "評価データの出どころの申告(--provenance)がない",
    "unreadable": "評価データの出どころの申告を読めない・形が正しくない",
    "not_independent": "評価データが修正案と独立していると申告されていない",
    "mismatch": "申告されたハッシュと評価データ・結果ファイルが一致しない(作成後に変わった可能性)",
    "no_inputs": "出どころの申告を照合する評価データ・結果がない",
}
PROVENANCE_LABEL = {"ok": "照合済み(ファイルは申告と一致)", **PROVENANCE_REASON}


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_provenance(path: Path | None, evals_path: Path | None,
                     results_path: Path | None) -> tuple[str, str | None]:
    """評価データの出どころの申告を、ファイルと照らす。(状態, dataset_id)。

    申告の形: {"dataset_id": "...", "independent_of_candidate": true,
              "evals_sha256": "...", "results_sha256": "..."}
    ハッシュの一致は「申告の後で評価データが変わっていない」ことだけを示す。
    誰がどう測ったか(真正性)は、この検査では確認できない。
    """
    if path is None:
        return "missing", None
    try:
        m = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "unreadable", None
    if not isinstance(m, dict):
        return "unreadable", None
    ds = m.get("dataset_id")
    if not (isinstance(ds, str) and _DATASET_ID.match(ds)):
        return "unreadable", None
    if m.get("independent_of_candidate") is not True:
        return "not_independent", ds
    if evals_path is None or results_path is None:
        return "no_inputs", ds
    try:
        ok = (m.get("evals_sha256") == sha256_of(evals_path)
              and m.get("results_sha256") == sha256_of(results_path))
    except OSError:
        ok = False
    return ("ok", ds) if ok else ("mismatch", ds)


def evaluate(evals: set[str] | None, results: dict[str, dict[str, str]] | None) -> dict:
    """成功率の比較。測定できた共通のケースだけで数える。"""
    if evals is None or results is None:
        return {"measured": False, "reason": "測定結果がない(成功率を測定できない)"}
    common = sorted(c for c in evals if c in results["old"] and c in results["new"])
    n = len(common)
    if n < MIN_CASES:
        return {"measured": False, "n": n,
                "reason": f"両方の結果がそろったケースが {n} 件(必要: {MIN_CASES} 件以上)"}
    old_pass = [c for c in common if results["old"][c] == "pass"]
    new_pass = [c for c in common if results["new"][c] == "pass"]
    regressions = sorted(c for c in common if results["old"][c] == "pass" and results["new"][c] == "fail")
    improved = sorted(c for c in common if results["old"][c] == "fail" and results["new"][c] == "pass")
    return {
        "measured": True, "n": n,
        "old_rate": round(len(old_pass) / n, 3), "new_rate": round(len(new_pass) / n, 3),
        "regressions": regressions, "improved": improved,
    }


def judge(skill: str, candidate_text: str | None, old: str | None, problems: list[str],
          measurement: dict, same_as_live: bool, provenance: str = "missing") -> tuple[str, list[str]]:
    if candidate_text is None:
        return "判定不能", ["検証対象の修正案がない(修正案を明示的に指定してください)"]
    if same_as_live:
        return "判定不能", ["修正案が現在の Skill と同一(比べる差分がない)"]
    if old is None:
        return "判定不能", ["コミット済みの現行 Skill が読めない(比較の基準がない)"]
    if problems:
        return "不合格", problems
    if measurement.get("regressions"):
        return "不合格", [f"回帰(旧で通り、新で落ちた)ケース: {len(measurement['regressions'])} 件"]
    if not measurement.get("measured"):
        return "判定不能", [measurement["reason"], "互換性の検査は通過(改善効果は未測定)"]
    if measurement["new_rate"] > measurement["old_rate"]:
        if provenance != "ok":  # 出どころを確認できない評価は、合格とは扱わない
            return "判定不能", [f"指定データ上で成功率は上がったが、{PROVENANCE_REASON[provenance]}"]
        return "合格", ["指定された評価データ上で、回帰なしに成功率が上がった"
                        "(実運用の改善とは別。承認ではない。三名体制レビューと決裁が必要)"]
    return "判定不能", ["指定データ上で改善が測定されなかった(成功率が旧と同等以下)"]


SCOPE_LINE = ("- 適用範囲: 指定された評価結果ファイルの集計のみ。実際のタスクの自動実行・測定はしていない。"
              "実運用での改善は確認していない。")


def render(skill: str, verdict: str, reasons: list[str], diff: dict | None, measurement: dict,
           proposal_ref: str | None, today: dt.date, provenance: str = "missing",
           dataset_id: str | None = None) -> str:
    qualifier = "(指定された評価データ上のみ。実運用の改善ではない)" if verdict == "合格" else ""
    out = [f"# Skill 検証報告(G): {skill}", "",
           f"- 判定: **{verdict}**{qualifier}(生成日 {today.isoformat()}・手動実行)",
           "- 状態: 検証のみ。自動採用・自動反映はしていません。",
           SCOPE_LINE,
           f"- 評価データの出どころ: {PROVENANCE_LABEL.get(provenance, provenance)}"
           + (f"(dataset_id: `{dataset_id}`)" if dataset_id and provenance == 'ok' else ""),
           "- 出どころの限界: 申告との一致は、申告の後に評価データが変わっていないことだけを示す。"
           "誰がどう測ったか(真正性)は確認していない。",
           f"- 参照した提案: {proposal_ref or 'なし'}"]
    if diff:
        out.append(f"- 変更の大きさ: 行数 {diff['lines_old']}→{diff['lines_new']}、"
                   f"バイト {diff['bytes_old']}→{diff['bytes_new']}、見出しの追加 {diff['headings_added']}・削除 {diff['headings_removed']}")
    if measurement.get("measured"):
        out.append(f"- 評価結果の集計(共通ケース {measurement['n']} 件・実行はしていない): "
                   f"成功率 {measurement['old_rate']} → {measurement['new_rate']}、"
                   f"回帰 {len(measurement['regressions'])} 件、旧で不合格・新で合格 {len(measurement['improved'])} 件")
    else:
        out.append(f"- 評価結果の集計: 未実施または不足 — {measurement.get('reason', '')}")
    out.append("- 利用実績の注意: Skill Metrics の利用実績が少ない・0件の場合、実運用での効果は確認できません。")
    if reasons:
        out.append("")
        out.append("## 理由")
        out.extend(f"- {r}" for r in reasons)
    return "\n".join(out) + "\n"


def save_report(root: Path, skill: str, today: dt.date, text: str) -> Path:
    target_dir = (Path(root) / EVAL_DIR).resolve()
    target = (target_dir / f"skill-{skill}-eval-{today.strftime('%Y%m%d')}.md").resolve()
    if target.parent != target_dir:
        raise ValueError("保存先が docs/evaluations の外です")
    if target.exists():
        raise FileExistsError("同じ名前の検証報告が既にあります(上書きしません)")
    target_dir.mkdir(parents=True, exist_ok=True)
    with open(target, "x", encoding="utf-8") as f:
        f.write(text)
    return target


def run(root: Path, skill: str, candidate: Path | None, evals: Path | None, results: Path | None,
        proposal: Path | None, save: bool, today: dt.date, provenance_path: Path | None = None) -> int:
    root = Path(root)
    if not _NAME.match(skill) or not (root / SKILLS_DIR / skill / "SKILL.md").is_file():
        print(f"エラー: Skill `{skill}` がリポジトリに見つかりません", file=sys.stderr)
        return sp.EXIT_USAGE
    proposal_ref = None
    if proposal is not None:
        pdir = (root / sp.PROPOSALS_DIR).resolve()
        ppath = proposal.resolve()
        if ppath.parent != pdir or not ppath.is_file():
            print("エラー: --proposal は docs/proposals/ の中の提案書だけを指定できます", file=sys.stderr)
            return sp.EXIT_USAGE
        if f"# Skill改善提案(未検証): {skill}" not in ppath.read_text(encoding="utf-8").splitlines()[0]:
            print("エラー: 提案書の対象 Skill が一致しません", file=sys.stderr)
            return sp.EXIT_USAGE
        proposal_ref = ppath.name
    live = (root / SKILLS_DIR / skill / "SKILL.md").resolve()
    candidate_text = None
    if candidate is not None:
        cpath = candidate.resolve()
        if not cpath.is_file():
            print("エラー: --candidate が読めるファイルではありません", file=sys.stderr)
            return sp.EXIT_USAGE
        with open(cpath, "rb") as f:  # 先頭だけ読む(上限を超えたものは、互換性の検査で止まる)
            data = f.read(MAX_BYTES * 4)
        candidate_text = data.decode("utf-8", errors="replace")
    old = committed_skill_text(root, skill)
    same = candidate_text is not None and old is not None and candidate_text == old
    problems = compatibility(skill, old, candidate_text) if candidate_text is not None else []
    diff = diff_summary(old, candidate_text) if (candidate_text is not None and old is not None) else None
    eval_cases = load_evals(evals) if evals is not None else None
    result_map, bad = (load_results(results) if results is not None else (None, 0))
    measurement = evaluate(eval_cases, result_map)
    if results is not None:
        measurement["unusable_result_lines"] = bad
    prov, dataset_id = check_provenance(provenance_path, evals, results)
    verdict, reasons = judge(skill, candidate_text, old, problems, measurement, same, prov)
    text = render(skill, verdict, reasons, diff, measurement, proposal_ref, today, prov, dataset_id)
    hits = sp.scan_text(text)
    if hits:
        print(f"機密の検査で止めました(規則: {', '.join(sorted(set(hits)))})。報告は表示・保存しません。",
              file=sys.stderr)
        return sp.EXIT_SECRET
    print(text, end="")
    if not save:
        print("ドライラン: 何も保存していません。保存するには --save を付けてください。", file=sys.stderr)
        return sp.EXIT_OK
    try:
        path = save_report(root, skill, today, text)
    except (ValueError, FileExistsError) as e:
        print(f"保存しません: {e}", file=sys.stderr)
        return sp.EXIT_SAVE_REFUSED
    print(f"保存しました: {path.relative_to(root.resolve())}", file=sys.stderr)
    return sp.EXIT_OK


def default_root() -> Path:
    """このスクリプトのあるリポジトリ。CLAUDE_PROJECT_DIR(別の作業ツリーを指すことがある)は使わない。"""
    return Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="修正案の Skill を、旧版と比べて検証する(WikiSkill G・読むだけ)")
    ap.add_argument("--skill", required=True)
    ap.add_argument("--candidate", default=None, help="修正案の SKILL.md(人間が用意したもの)")
    ap.add_argument("--evals", default=None, help="Evaluation Set(JSONL)")
    ap.add_argument("--results", default=None, help="測定結果(JSONL)")
    ap.add_argument("--proposal", default=None, help="参照する F の提案書(docs/proposals/ の中)")
    ap.add_argument("--provenance", default=None,
                    help="評価データの出どころの申告(JSON)。合格には必須。ハッシュの一致は改変がないことだけを示す")
    ap.add_argument("--root", default=None)
    ap.add_argument("--date", default=None)
    ap.add_argument("--save", action="store_true")
    a = ap.parse_args(argv)
    try:
        today = dt.date.fromisoformat(a.date) if a.date else dt.date.today()
    except ValueError:
        ap.error("--date は YYYY-MM-DD の形で指定してください")
    root = Path(a.root) if a.root else default_root()  # 修正案と基準を同じリポジトリから読む
    return run(root, a.skill,
               Path(a.candidate) if a.candidate else None,
               Path(a.evals) if a.evals else None,
               Path(a.results) if a.results else None,
               Path(a.proposal) if a.proposal else None,
               a.save, today, Path(a.provenance) if a.provenance else None)


if __name__ == "__main__":
    sys.exit(main())
