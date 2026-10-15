#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""WikiSkill M1: 読み取り専用の検索(決定・正式Wiki・失敗台帳)。

照合と信頼の規則は scripts/memory_bootstrap.py をそのまま使う(作り直さない)。
- 出すもの: Decision(公開リポでは visibility が public のものだけ)、承認済みの正式 Wiki
  (commit 済み・出典あり・矛盾なし。Bootstrap と同じ条件)、失敗台帳(FK)の行。
- 出さないもの: 候補 Wiki(docs/wiki/_candidates)、矛盾の疑いのある Wiki、アーカイブ、
  Experience(機械記録)、private の Decision、superseded の Decision、試験用の Decision。
- 書き込みはしない。検索は hook ではないので監査ログへの追記も止める(_read_only)。

使い方:
  python3 scripts/wiki_search.py "締切 アラート"
  python3 scripts/wiki_search.py "マージ 競合" --kind decision,failure --limit 5
  python3 scripts/wiki_search.py "競合" --json
"""
from __future__ import annotations

import argparse
import contextlib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import memory_bootstrap as mb  # noqa: E402
import wiki_schema as ws  # noqa: E402

DEFAULT_KINDS = ("decision", "wiki", "failure")
DEFAULT_LIMIT = 5
LINE_SHOWN = 300
OFFICIAL_WIKI_PATH = re.compile(r"^docs/wiki/[^/_][^/]*\.md$")  # 直下のみ。_candidates・_archive は含まない


def terms_of(query: str) -> list[str]:
    """検索語。空白・読点で割り、2字未満・定型語・重複を除く(Bootstrap と同じ規則)。"""
    return mb._filter_terms(re.split(r"[\s,、。・/]+", query.strip()))


@contextlib.contextmanager
def _read_only():
    """検索中は監査ログへ書かない。読み取り以外の副作用を作らない。"""
    saved = (mb.audit, mb._audit_once)
    mb.audit = lambda *a, **k: None
    mb._audit_once = lambda *a, **k: None
    try:
        yield
    finally:
        mb.audit, mb._audit_once = saved


def _public_decisions(root: Path) -> list[dict]:
    """Decision のうち、公開してよいもの(リポの公開性と visibility の両方で public)。"""
    by_path = {d["path"]: d for d in mb._decisions_cached(root)}
    repo_vis = ws.repo_visibility(root)
    out = []
    for s in mb._decisions(root):
        d = by_path.get(s.get("path"))
        if d is None:  # 元の記録が引けないものは出さない(fail closed)
            continue
        if ws.decision_visibility(d, root, repo_vis) != "public":
            continue
        out.append({**s, "ref": d.get("id") or s.get("path", "")})
    return out


def _failures_safe(root: Path) -> list[dict]:
    """失敗台帳。台帳が無い・読めないときは空(検索は止めない)。"""
    try:
        rows = mb._failures(root)
    except OSError:
        return []
    out = []
    for s in rows:
        if s.get("kind") != "failure":
            continue
        out.append({**s, "ref": (s.get("id") or "").split("#")[-1]})
    return out


def _official_wiki(root: Path) -> list[dict]:
    """承認済みの正式 Wiki。Bootstrap の判定(_wiki)を通ったものだけを、さらに直下のパスに絞る。"""
    if mb._ws is None:
        return []
    out = []
    for s in mb._wiki(root):
        path = s.get("path", "")
        if s.get("kind") != "wiki" or not OFFICIAL_WIKI_PATH.match(path):
            continue
        if "_candidates" in path or "_archive" in path:
            continue
        out.append(s)
    return out


def search(root: Path, query: str, kinds=DEFAULT_KINDS, limit: int = DEFAULT_LIMIT,
           min_score: int = 1) -> dict:
    """query に当たる項目を区分ごとに返す。結果は読み取りだけで作る。"""
    root = Path(root)
    kinds = tuple(kinds)
    terms = terms_of(query)
    report = {"query": query, "terms": terms, "wiki_available": mb._ws is not None, "results": []}
    if not terms:
        return report
    with _read_only():
        pool: list[dict] = []
        if "decision" in kinds:
            pool += _public_decisions(root)
        if "failure" in kinds:
            pool += _failures_safe(root)
        if "wiki" in kinds:
            pool += _official_wiki(root)
        picked = mb._select(pool, terms, per_kind=limit, min_score=min_score,
                            synonyms=mb._synonyms(root))
    for kind in kinds:
        for s in picked.get(kind, [])[:limit]:
            ref = s.get("ref") or (Path(s.get("path", "")).stem if kind == "wiki" else s.get("id", ""))
            report["results"].append({
                "kind": kind, "label": s.get("label", ""), "id": ref,
                "title": s.get("title", ""), "date": s.get("date") or "",
                "path": s.get("path", ""), "line": (s.get("line") or "")[:LINE_SHOWN],
                "score": s.get("score", 0),
            })
    return report


def render(report: dict) -> str:
    lines = [f"検索語: {' / '.join(report['terms']) or '(なし)'}"]
    if not report["results"]:
        lines.append("該当なし(正式な決定・正式Wiki・失敗台帳に一致する項目はありません)")
    for r in report["results"]:
        lines.append(f"- {r['label']} {r['id']} {r['title']} ({r['date'] or '日付なし'}) — {r['path']}")
        lines.append(f"  {r['line']}")
    if not report["wiki_available"]:
        lines.append("注: 正式Wikiは使えません(wiki_schema が読めないか、.claude/wiki.off があります)")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="決定・正式Wiki・失敗台帳を読み取り専用で検索する")
    ap.add_argument("query", help="検索語(空白で複数指定できます)")
    ap.add_argument("--kind", default=",".join(DEFAULT_KINDS),
                    help="対象の区分(decision,wiki,failure のカンマ区切り)")
    ap.add_argument("--limit", type=int, default=DEFAULT_LIMIT, help="区分ごとの件数(既定 5)")
    ap.add_argument("--json", action="store_true", help="JSON で出す")
    ap.add_argument("--root", default=None, help="対象リポジトリ(既定はこのスクリプトのリポジトリ)")
    a = ap.parse_args(argv)
    kinds = [k.strip() for k in a.kind.split(",") if k.strip()]
    bad = [k for k in kinds if k not in DEFAULT_KINDS]
    if bad:
        ap.error(f"未知の区分: {', '.join(bad)}(使えるもの: {', '.join(DEFAULT_KINDS)})")
    if a.limit < 1:
        ap.error("--limit は1以上")
    root = Path(a.root) if a.root else Path(__file__).resolve().parents[1]
    report = search(root, a.query, kinds=kinds, limit=a.limit)
    print(json.dumps(report, ensure_ascii=False, indent=2) if a.json else render(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
