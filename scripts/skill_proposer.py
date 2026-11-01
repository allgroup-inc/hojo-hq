#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""WikiSkill M3 / Component F: Skill Proposer(人間が手動で実行する・提案だけを作る)。

使い方:
  python3 scripts/skill_proposer.py --skill <name>           # ドライラン(標準出力に表示。何も書かない)
  python3 scripts/skill_proposer.py --skill <name> --save    # docs/proposals/ へ提案書を1件保存(明示指示のときだけ)

原則:
  - 読むだけ。Skill 本体・失敗台帳・決定・Experience は変えない。書くのは --save の提案書1件だけ。
  - Skill を自動で変えない・自動で採用しない。提案は人間が判断する材料。
  - 根拠は公開できるものだけ: 公開リポの決定(visibility が public)・失敗台帳・公開 Experience の集計(E v2)。
  - 独立した根拠が2件以上かつ2種類以上あるときだけ「提案」。足りなければ「判定不能」(無理に提案を作らない)。
  - 失敗捕捉が観測されていない期間の failure_count / success_rate は根拠に使わない。
  - Failure Ledger の本文に Skill 名が出るだけでは、その Skill が原因とは断定しない。
  - 未承認(状態が adopted でない)の決定は確定事項として使わない。
  - 版の変更履歴は改善効果の証明に使わない。G(Skill Validator)は未実装のため、提案は常に「未検証」。
  - 提案本文には台帳・決定の本文を転記しない。出典は ID・記録日・関連性の理由だけで示す。
  - 保存前に、提案本文を機密の検査にかける。疑いがあれば保存しない(該当の文字列は表示しない)。
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import check_repo_scope  # noqa: E402  — 禁止語の一覧(FORBIDDEN_CONTENT)を再利用する
import decision_memory as dm  # noqa: E402
import memory_bootstrap as mb  # noqa: E402  — 失敗台帳の読み取り(_failures)を再利用する
import skill_metrics as sm  # noqa: E402  — Skill Metrics v2 の集計を再利用する
import wiki_schema as ws  # noqa: E402  — 決定の公開範囲(decision_visibility)を再利用する

PROPOSALS_DIR = "docs/proposals"
SKILLS_DIR = ".claude/skills"
SCHEMA = "skill-proposal/v1"
_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_BOUNDARY = r"(?<![A-Za-z0-9_.\-]){}(?![A-Za-z0-9_.\-])"
# 一般的な英単語と一致しやすい名前。本文に出ても関連の根拠には数えない
_COMMON_WORDS = {"plan", "review", "hook", "debug", "research", "summary", "translate", "ideas", "brief",
                 "pm", "email", "checklist", "compare", "critique", "pitch", "interview", "coach", "mentor",
                 "optimize", "teacher", "explain", "analysis", "design", "test", "write", "writing"}
# 提案本文に出してはいけないものの検査(ルール名 → 正規表現)。禁止語は check_repo_scope から取る
_SECRET_RULES = {
    "url": re.compile(r"https?://"),
    "email": re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    "session_id": re.compile(r"session[-_][0-9A-Za-z]{6,}"),
    "token_like": re.compile(r"[A-Za-z0-9_\-]{32,}"),
    "ipv4": re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b"),
    "bearer": re.compile(r"(?i)bearer\s"),
    "absolute_path": re.compile(r"/home/|/tmp/|/root/|/Users/"),
}
EXIT_OK, EXIT_USAGE, EXIT_SECRET, EXIT_SAVE_REFUSED = 0, 2, 3, 4


def _is_ambiguous(name: str) -> bool:
    return len(name) <= 6 or name.lower() in _COMMON_WORDS


def mentions(text: str, name: str) -> bool:
    """Skill 名が語として出るか(writing-plans は writing-plans-hojo に当たらない)。"""
    if not text or not name:
        return False
    return re.search(_BOUNDARY.format(re.escape(name)), text, re.IGNORECASE) is not None


def scan_text(text: str) -> list[str]:
    """提案本文の機密検査。引っかかった規則の名前だけを返す(該当の文字列は返さない)。"""
    hits = [rule for rule, pat in _SECRET_RULES.items() if pat.search(text)]
    hits += [f"forbidden_term_{i}" for i, term in enumerate(check_repo_scope.FORBIDDEN_CONTENT) if term in text]
    return hits


def _public_decision_text(d: dict) -> str:
    keys = ("title", "tags", "why", "outcome", "premises", "alternatives", "text_head")
    return " ".join(str(d.get(k) or "") for k in keys)


def gather(root: Path, skill: str) -> dict:
    """根拠を集める(読むだけ)。公開できない項目は含めず、その存在も示さない。"""
    root = Path(root)
    report = sm.collect(root)
    rows = [r for r in report["rows"] if r["skill"] == skill]
    observed = [r for r in rows if r.get("failure_observed")]
    versions = [v for v in report["versions"] if v["skill"] == skill]
    ambiguous = _is_ambiguous(skill)
    evidence: list[dict] = []

    try:
        ledger = mb._failures(root)  # 失敗台帳(公開)。台帳が無いときは根拠0件として扱う
    except OSError:
        ledger = []
    for s in ledger:
        fid = str(s.get("id", "")).split("#")[-1]
        if not mentions(s.get("text", ""), skill):
            continue
        evidence.append({
            "kind": "failure", "id": fid, "date": str(s.get("date") or ""), "source": "失敗台帳",
            "counts": not ambiguous,
            "reason": ("一般的な語と一致するため関連は弱い(根拠に数えない)" if ambiguous else
                       "台帳の本文に Skill 名が出る(原因とは断定しない。関連の候補)"),
        })

    repo_vis = ws.repo_visibility(root)
    for d in dm.load_decisions(root):  # 決定(公開範囲が public のものだけ)
        if d.get("status") == "superseded":
            continue
        if any(str(t).strip().lower() == "test" for t in d.get("tags") or []):
            continue
        if ws.decision_visibility(d, root, repo_vis) != "public":
            continue  # 非公開は、存在も含めて一切出さない
        if not mentions(_public_decision_text(d), skill):
            continue
        status = str(d.get("status") or "unknown")
        adopted = status == "adopted"
        evidence.append({
            "kind": "decision", "id": str(d.get("id") or ""), "date": str(d.get("date") or ""),
            "source": "決定(公開)", "status": status,
            "counts": adopted and not ambiguous,
            "reason": ("一般的な語と一致するため関連は弱い(根拠に数えない)" if ambiguous and adopted else
                       "採用済みの決定に Skill 名が出る" if adopted else
                       f"状態が『{status}』のため確定事項として使わない(根拠に数えない)"),
        })

    for r in observed:  # 観測済みの期間に記録された失敗だけ
        if r.get("failure_count"):
            evidence.append({
                "kind": "metric", "id": f"{r['period']}/{skill}/{r.get('version_key') or 'no-key'}",
                "date": str(r.get("last_seen") or ""), "source": "Skill Metrics(観測済み)",
                "counts": True, "reason": "失敗捕捉が観測された期間に失敗が記録された",
            })

    counted = [e for e in evidence if e["counts"]]
    return {
        "skill": skill,
        "usage_total": sum(r["total_invocations"] for r in rows),
        "observed_periods": len(observed),
        "failure_hook_registered_since": report["totals"].get("failure_hook_registered_since"),
        "failure_firing_confirmed": report["totals"].get("failure_firing_confirmed", False),
        "versions": versions,
        "evidence": evidence,
        "counted_ids": sorted({(e["kind"], e["id"]) for e in counted}),
        "counted_kinds": sorted({e["kind"] for e in counted}),
    }


def judge(g: dict) -> tuple[str, list[str]]:
    """判定。独立した根拠が2件以上かつ2種類以上なら「提案」。それ以外は「判定不能」と理由を返す。"""
    reasons = []
    n, k = len(g["counted_ids"]), len(g["counted_kinds"])
    if n >= 2 and k >= 2:
        return "提案", reasons
    if n == 0:
        reasons.append("根拠が0件")
    else:
        reasons.append(f"独立した根拠が{n}件(必要: 2件以上)")
        if k < 2:
            reasons.append(f"根拠の種類が{k}種類(必要: 2種類以上)")
    if g["observed_periods"] == 0:
        reasons.append("失敗捕捉の観測期間がない(失敗数・成功率は根拠にできない)")
    return "判定不能", reasons


def _evidence_table(evidence: list[dict]) -> list[str]:
    lines = ["| 出典ID | 種類 | 記録日 | 扱い | 関連性の理由 |", "|---|---|---|---|---|"]
    for e in evidence:
        mark = "根拠に数える" if e["counts"] else "参考(根拠に数えない)"
        lines.append(f"| {e['id']} | {e['source']} | {e['date'] or '日付なし'} | {mark} | {e['reason']} |")
    return lines


def render_report(g: dict, verdict: str, reasons: list[str], today: dt.date) -> str:
    """判定の結果(標準出力・判定不能のときの表示)。"""
    out = [f"# Skill Proposer 判定: {g['skill']}", f"- 判定: **{verdict}**(生成日 {today.isoformat()}・手動実行)"]
    out.append(f"- Skill Metrics の利用実績: {g['usage_total']} 件"
               + ("(利用実績が0件のため、成功・失敗の判断材料はありません)" if g["usage_total"] == 0 else ""))
    if g["observed_periods"] == 0:
        out.append("- 失敗捕捉: 観測期間なし(failure_count / success_rate は null のまま。0 とは扱わない)")
    out.append(f"- 版の変更履歴: {len(g['versions'])} 件(改善効果の証明にはならない)")
    if reasons:
        out.append("- 判定不能の理由: " + "; ".join(reasons))
    if g["evidence"]:
        out.append("")
        out.extend(_evidence_table(g["evidence"]))
    else:
        out.append("- 関連する記録は見つかりませんでした。")
    return "\n".join(out) + "\n"


def render_proposal(g: dict, today: dt.date) -> str:
    """提案書(判定が「提案」のときだけ作る)。根拠の出典は ID・日付・理由で示す。"""
    skill = g["skill"]
    lines = [
        f"# Skill改善提案(未検証): {skill}",
        "",
        "- 状態: **提案のみ**。G(Skill Validator)による検証は未実施です。自動では採用しません。",
        f"- 生成: {today.isoformat()} / 手動実行の CLI(scripts/skill_proposer.py)",
        f"- 対象 Skill: `{skill}`",
        "",
        "## 利用実績と版",
        f"- Skill Metrics の利用実績: {g['usage_total']} 件"
        + ("(0件のため、利用実績による裏づけはありません)" if g["usage_total"] == 0 else ""),
    ]
    if g["observed_periods"] == 0:
        lines.append("- 失敗捕捉: 未確認(観測期間なし)。failure_count と success_rate は根拠に使っていません。")
    else:
        lines.append(f"- 失敗捕捉: 観測済みの期間 {g['observed_periods']} 件(失敗の記録は根拠に数えたもののみ)")
    lines.append(f"- 版の変更履歴: {len(g['versions'])} 件。版の変更は改善効果を証明しません。")
    lines += ["", "## 根拠(出典ID・記録日・関連性の理由)"]
    lines += _evidence_table(g["evidence"])
    lines += [
        "",
        "## 制約と未確認事項",
        "- 失敗台帳の本文に Skill 名が出ていても、その Skill が原因だったとは断定していません。",
        "- 未承認(状態が採用でない)の決定は確定事項として使っていません。",
        "- 改善効果は確認していません。効果の評価には G と、改善前後の記録が必要です。",
        "- 失敗の捕捉が観測されていない期間の失敗数・成功率は、根拠にしていません。",
        "",
        "## 次の手順(人間が判断する)",
        "1. 上の出典を、ID から元の記録で読み直す。",
        "2. 改善の方向を決める(この提案は方向を決めていません)。",
        "3. G(Skill Validator)で検証する(未実施)。",
        "4. 三名体制レビューと、小柳さんの決裁を経て採否を決める。",
    ]
    return "\n".join(lines) + "\n"


def proposal_path(root: Path, skill: str, today: dt.date) -> Path:
    return Path(root) / PROPOSALS_DIR / f"proposal-{today.strftime('%Y%m%d')}-{skill}.md"


def save_proposal(root: Path, skill: str, today: dt.date, text: str) -> Path:
    """docs/proposals/ の中に、新しい1件だけを書く。既存は上書きしない。"""
    target_dir = (Path(root) / PROPOSALS_DIR).resolve()
    target = proposal_path(root, skill, today).resolve()
    if target.parent != target_dir or not target.name.startswith("proposal-"):
        raise ValueError("保存先が docs/proposals の外です")
    if target.exists():
        raise FileExistsError("同じ名前の提案書が既にあります(上書きしません)")
    target_dir.mkdir(parents=True, exist_ok=True)
    with open(target, "x", encoding="utf-8") as f:
        f.write(text)
    return target


def run(root: Path, skill: str, save: bool, today: dt.date) -> int:
    root = Path(root)
    if not _NAME.match(skill) or not (root / SKILLS_DIR / skill / "SKILL.md").is_file():
        print(f"エラー: Skill `{skill}` がリポジトリに見つかりません(名前と場所を確認してください)", file=sys.stderr)
        return EXIT_USAGE
    g = gather(root, skill)
    verdict, reasons = judge(g)
    if verdict != "提案":
        print(render_report(g, verdict, reasons, today), end="")
        if save:
            print("保存しません(提案が成立していないため)。", file=sys.stderr)
        else:
            print("ドライラン: 何も保存していません。", file=sys.stderr)
        return EXIT_OK
    text = render_proposal(g, today)
    hits = scan_text(text)
    if hits:
        print(f"機密の検査で止めました(規則: {', '.join(sorted(set(hits)))})。提案本文は表示・保存しません。",
              file=sys.stderr)
        return EXIT_SECRET
    if not save:
        print(text, end="")
        print("ドライラン: 何も保存していません。保存するには --save を付けてください。", file=sys.stderr)
        return EXIT_OK
    try:
        path = save_proposal(root, skill, today, text)
    except (ValueError, FileExistsError) as e:
        print(f"保存しません: {e}", file=sys.stderr)
        return EXIT_SAVE_REFUSED
    print(f"保存しました: {path.relative_to(Path(root).resolve())}", file=sys.stderr)
    return EXIT_OK


def default_root() -> Path:
    """このスクリプトのあるリポジトリ。CLAUDE_PROJECT_DIR(別の作業ツリーを指すことがある)は使わない。"""
    return Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Skill 改善提案を、根拠つきで手動生成する(WikiSkill F)")
    ap.add_argument("--skill", required=True, help="対象 Skill の名前(.claude/skills のフォルダ名)")
    ap.add_argument("--root", default=None, help="対象リポジトリ(既定はこのスクリプトのリポジトリ)")
    ap.add_argument("--save", action="store_true", help="docs/proposals/ へ提案書を保存する(明示指示のとき)")
    ap.add_argument("--date", default=None, help="生成日(YYYY-MM-DD)。既定は今日")
    a = ap.parse_args(argv)
    try:
        today = dt.date.fromisoformat(a.date) if a.date else dt.date.today()
    except ValueError:
        ap.error("--date は YYYY-MM-DD の形で指定してください")
    root = Path(a.root) if a.root else default_root()  # 明示の --root があればそれを使う
    return run(root, a.skill, a.save, today)


if __name__ == "__main__":
    sys.exit(main())
