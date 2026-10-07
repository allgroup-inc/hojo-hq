#!/usr/bin/env python3
"""WikiSkill Phase 2: Knowledge Validator(stdlib のみ・読み取り専用)。

誤った知識・公開できない知識・根拠の無い知識が、候補として main に入ること、正式知識になることを機械で止める。
検査(設計書 7.2): V01 schema / V02 ID / V03 Provenance の解決 / V04 逐語引用 / V05 公開性 / V06 禁止語 /
V07 長さ / V08 置き場所 / V09 承認の必須 / V10 重複 / V11〜V13 矛盾(Task 4)/ V14 同義語表 / V15 参照先。
検査中の例外はその規則の違反として数える(fail-closed。「検査できなかった」を「違反なし」にしない)。

使い方:
    python3 scripts/wiki_validate.py [--root PATH] [--json]   # exit 0 違反なし / 1 違反あり・検査不能
    python3 scripts/wiki_validate.py --selftest               # exit 0 / 2(自己点検失敗)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import experience_log  # noqa: E402
import wiki_schema as ws  # noqa: E402  (規則は ws.<関数> で呼ぶ: テストで差し替えて fail-closed を確かめられる)
from check_repo_scope import FORBIDDEN_CONTENT, find_content_violations, find_violations  # noqa: E402
from decision_memory import load_decisions  # noqa: E402
from wikiskill_common import group_session_files  # noqa: E402

Violation = tuple[str, str, str]  # (パス, コード, 理由)
Warning = tuple[str, str, str]  # noqa: A001 — (パス, decision_id, 理由)。needs_review(V13)用
Context = dict

FAILURE_LEDGER = "docs/失敗台帳.md"
EXP_DIR = ".claude/experience"
EXP_TEXT_FIELDS = ("text", "note")  # Experience 行の自由記述欄。無ければ行の JSON 全体が「本文」
_KIND = {"experience": "source_experience", "decision": "source_decision", "failure": "source_failure",
         **{k: k for k in ws.SOURCE_KEYS}}
_FK_ROW_RE = re.compile(r"^\|\s*(FK-\d{3})\s*\|")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_HEX40_RE = re.compile(r"^[0-9a-f]{40}$")
_STR_KEYS = ("candidate_id", "title", "summary", "confidence_basis", "repo", "created_at", "proposed_by",
             "dedup_key", "extract_run")
_LIST_STR_KEYS = ("related_wiki", "related_skills")
_GIT_ENV_DROP = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE")


class ContextError(RuntimeError):
    """検査に必要な入力(git 等)を読めない。検査全体を違反として止める。"""


# ---------------------------------------------------------------- 入力(Context)

def _git(root: Path, *args: str) -> str:
    try:
        r = subprocess.run(["git", "-c", "core.quotePath=false", *args], cwd=str(root), capture_output=True,
                           text=True, encoding="utf-8", errors="strict", timeout=60)
    except (OSError, subprocess.SubprocessError, ValueError) as e:
        raise ContextError(f"git {args[0]} を実行できない: {type(e).__name__}") from e
    if r.returncode != 0:
        raise ContextError(f"git {args[0]} が失敗(exit {r.returncode})")
    return r.stdout


def committed_files(root: Path, pathspec: str) -> set[str]:
    """git 管理下の通常ファイル(mode 100644/100755・symlink でない)で、`git diff --name-only HEAD` に出ない
    (作業ツリー・index とも HEAD と同じ = commit 済みのまま)もの。検証器と抽出器が共有する唯一の判定。

    シンボリックリンク(mode 120000)・submodule(160000)は除く: リンク先は commit されたものとは限らない。
    git が失敗すれば ContextError(呼び元で fail-closed)。
    """
    tracked: set[str] = set()
    for entry in _git(root, "ls-files", "-s", "-z", "--", pathspec).split("\0"):
        if not entry:
            continue
        meta, _tab, path = entry.partition("\t")
        if meta.split(" ", 1)[0] not in ("100644", "100755") or (Path(root) / path).is_symlink():
            continue
        tracked.add(path)
    changed = set(_git(root, "diff", "--name-only", "-z", "HEAD", "--", pathspec).split("\0"))
    return tracked - changed


def _committed_experience(root: Path) -> list[str]:
    """commit 済みのまま(committed_files)の Experience の JSONL(パス順)。"""
    return sorted(p for p in committed_files(root, EXP_DIR) if p.endswith(".jsonl"))


def _committed_decisions(root: Path) -> list[dict]:
    """load_decisions のうち、議事ファイルが commit 済みのまま(committed_files)のものだけ。"""
    committed = committed_files(root, "docs")
    return [d for d in load_decisions(root) if d.get("path") in committed]


def _read_synonyms(root: Path) -> list[frozenset[str]]:
    """矛盾判定(V12・V13)用の同義語表。検証器は audit も書かない(形式違反の行は V14 が別に報告する)。"""
    path = Path(root) / ws.SYNONYMS_PATH
    if path.is_symlink() or not path.is_file():
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []  # 同義語なし = 語を束ねない = 矛盾判定は止めすぎる側
    return ws.parse_synonyms(text)[0]


def _read_ledger(root: Path, committed_only: bool = False) -> tuple[dict[str, str], set[str]]:
    """失敗台帳の FK 行。committed_only なら、台帳が commit 済みのまま(committed_files)でなければ丸ごと空。"""
    path = Path(root) / FAILURE_LEDGER
    if not path.is_file():
        return {}, set()
    if committed_only and FAILURE_LEDGER not in committed_files(root, FAILURE_LEDGER):
        return {}, set()
    rows: dict[str, str] = {}
    dup: set[str] = set()
    for line in path.read_text(encoding="utf-8").split("\n"):
        m = _FK_ROW_RE.match(line)
        if m:
            if m.group(1) in rows:
                dup.add(m.group(1))
            rows[m.group(1)] = line.rstrip("\r")
    return rows, dup


def build_context(root: Path) -> Context:
    root = Path(root)
    decisions = _committed_decisions(root)  # 未追跡・未 commit の議事は根拠にも矛盾判定にも使わない(抽出器と同じ)
    by_id: dict[str, dict] = {}
    dup_dec: set[str] = set()
    for d in decisions:
        did = d.get("id")
        if did in by_id:
            dup_dec.add(did)
        by_id.setdefault(did, d)
    fk_rows, dup_fk = _read_ledger(root, committed_only=True)
    exp_events: dict[tuple[str, str], dict] = {}
    exp_groups: dict[tuple[str, str], list[dict]] = {}
    exp_errors: list[tuple[str, str]] = []  # (読めない Experience のパス, 理由)
    for sid, files in group_session_files(_committed_experience(root)).items():
        for f in files:
            try:
                events = experience_log._read_events(root / f)
            except (OSError, UnicodeDecodeError) as e:
                exp_errors.append((Path(f).as_posix(), f"{type(e).__name__}: {e}"))
                continue
            for ev in events:
                if isinstance(ev.get("ts"), str):
                    exp_events.setdefault((sid, ev["ts"]), ev)
                    exp_groups.setdefault((sid, ev["ts"]), []).append(ev)
    official, candidates, archive = (ws.iter_wiki(root, p) for p in ("official", "candidates", "archive"))
    ids: dict[str, dict[str, list[str]]] = {"wiki": {}, "candidate": {}}
    for w in official + archive:
        if isinstance(w.get("wiki_id"), str) and w["wiki_id"]:
            ids["wiki"].setdefault(w["wiki_id"], []).append(w["_path"])
    for w in official + candidates + archive:
        if isinstance(w.get("candidate_id"), str) and w["candidate_id"]:
            ids["candidate"].setdefault(w["candidate_id"], []).append(w["_path"])
    return {
        "root": root, "repo_slug": experience_log.repo_slug(root), "repo_visibility": ws.repo_visibility(root),
        "decisions": decisions, "decisions_by_id": by_id, "ambiguous_decisions": dup_dec,
        "fk_rows": fk_rows, "ambiguous_fk": dup_fk, "exp_events": exp_events, "exp_groups": exp_groups,
        "exp_errors": exp_errors, "official": official, "candidates": candidates, "archive": archive, "ids": ids,
        "synonyms": _read_synonyms(root),
    }


def _event_text(ev: dict) -> str:
    texts = [ev[f] for f in EXP_TEXT_FIELDS if isinstance(ev.get(f), str) and ev[f]]
    return "\n".join(texts) if texts else json.dumps(ev, ensure_ascii=False)


def resolve_source(source: str, kind: str, ctx: Context) -> tuple[str, dict | None]:
    """(参照先の本文, 行 / Decision / FK)。解決できなければ ("", None)。例外も解決不能として扱う。"""
    try:
        k = _KIND.get(kind)
        if not isinstance(source, str) or k is None:
            return "", None
        if k == "source_experience":
            m = ws.EXP_SOURCE_RE.match(source)
            evs = ctx["exp_groups"].get((m.group(1), m.group(2))) if m else None
            if not evs:
                return "", None
            return "\n".join(_event_text(e) for e in evs), evs[0]
        if k == "source_decision":
            d = ctx["decisions_by_id"].get(source)
            if d is None or source in ctx["ambiguous_decisions"]:
                return "", None
            return (Path(ctx["root"]) / d["path"]).read_text(encoding="utf-8"), d
        if not ws.FK_RE.match(source) or source in ctx["ambiguous_fk"] or source not in ctx["fk_rows"]:
            return "", None
        row = ctx["fk_rows"][source]
        return row, {"id": source, "text": row}
    except Exception:  # noqa: BLE001 — 解決できないものは「解決できない」(呼び元で V03/V04)
        return "", None


# ---------------------------------------------------------------- 小さな判定

def _s(v) -> bool:
    return isinstance(v, str) and bool(v.strip())


def _date(v) -> date | None:
    if not isinstance(v, str) or not _DATE_RE.match(v):
        return None
    try:
        return date.fromisoformat(v)
    except ValueError:
        return None


def _is_bot(name: str) -> bool:
    n = unicodedata.normalize("NFKC", name).strip().lower()
    return (n in ws.BOT_APPROVERS or n.endswith("[bot]") or n.startswith("github-actions") or "claude" in n
            or "knowledge_extract" in n)


def _empty_word(v) -> bool:
    if not isinstance(v, str):
        return True
    return unicodedata.normalize("NFKC", v).strip().lower() in ws.EMPTY_WORDS or ws.normalize(v) in ws.EMPTY_WORDS


def _forbidden_index(path: str, texts: list[str]) -> int | None:
    """禁止語(check_repo_scope.FORBIDDEN_CONTENT)の位置。原文・JSON を解いた文・NFKC・大小無視の順に見る。"""
    for t in texts:
        for variant in (t, unicodedata.normalize("NFKC", t)):
            hit = find_content_violations(path, variant)
            if hit:
                return FORBIDDEN_CONTENT.index(hit)
            folded = variant.casefold()
            for i, word in enumerate(FORBIDDEN_CONTENT):
                if word.casefold() in folded:
                    return i
        # ゼロ幅文字・ソフトハイフン・空白を挟んだ書き方も止める(記号は残す: 許された語を誤検知しない)
        squashed = ws.strip_invisible(t)
        for i, word in enumerate(FORBIDDEN_CONTENT):
            if ws.strip_invisible(word) and ws.strip_invisible(word) in squashed:
                return i
    return None


def _materialize(w: dict) -> dict:
    """ファイルから読んでいない Wiki(抽出器の下書き)は、書いたときと同じ形に描いて読み直す。"""
    if "_text" in w:
        return w
    fm = {k: v for k, v in w.items() if not str(k).startswith("_")}
    text = ws.render_wiki(fm, w.get("_sections") or {})
    _fm, body = ws.parse_wiki_frontmatter(text)
    pre, sections, order = ws.split_sections(body)
    return {**w, "_text": text, "_body": body, "_sections": sections, "_section_order": order, "_preamble": pre}


# ---------------------------------------------------------------- 規則 V01〜V15

def check_v01(w: dict, ctx: Context) -> list[Violation]:
    """schema: 必須キー・未知のキー・型・enum・本文の5見出し(この順・空でない)。"""
    p, out = w["_path"], []
    bad = lambda r: out.append((p, "V01", r))  # noqa: E731
    for k in ws.REQUIRED_KEYS:
        if k not in w:
            bad(f"必須キー {k} がありません")
    for k in w:
        if not str(k).startswith("_") and k not in ws.KNOWN_KEYS:
            bad(f"未知のキー {k}(書けるキーは設計書 6.2。needs_review は書かない)")
    for k in _STR_KEYS:
        if k in w and not _s(w[k]):
            bad(f"{k} は空でない文字列")
    ev = w.get("evidence")
    if "evidence" in w:
        if not isinstance(ev, list) or not ev:
            bad("evidence は1件以上の配列")
        else:
            for i, e in enumerate(ev):
                if not (isinstance(e, dict) and _s(e.get("ref")) and _s(e.get("quote"))):
                    bad(f"evidence[{i}] は {{ref, quote}}(どちらも空でない文字列)")
    c = w.get("confidence")
    if "confidence" in w and (isinstance(c, bool) or not isinstance(c, (int, float)) or not 0.0 <= c <= 1.0):
        bad("confidence は 0.0〜1.0 の数")
    if "visibility" in w and w["visibility"] not in ws.VISIBILITIES:
        bad("visibility は public / private")
    if "created_at" in w:
        ca = w["created_at"]
        try:
            ok = isinstance(ca, str) and bool(_ISO_RE.match(ca)) and bool(datetime.strptime(ca, "%Y-%m-%dT%H:%M:%SZ"))
        except ValueError:
            ok = False
        if not ok:
            bad("created_at は YYYY-MM-DDTHH:MM:SSZ")
    if "contradictions" in w:
        cs = w["contradictions"]
        if not isinstance(cs, list) or not all(isinstance(x, dict) and _s(x.get("source"))
                                               and isinstance(x.get("note"), str) for x in cs):
            bad("contradictions は [{source, note}] の配列")
    for k in _LIST_STR_KEYS + ws.SOURCE_KEYS:
        if k in w and not (isinstance(w[k], list) and all(_s(x) for x in w[k])):
            bad(f"{k} は文字列の配列")
    if "review_status" in w and w["review_status"] not in ws.ALL_STATUSES:
        bad(f"review_status は {' / '.join(sorted(ws.ALL_STATUSES))}")
    if "dedup_key" in w and not (isinstance(w["dedup_key"], str) and _HEX40_RE.match(w["dedup_key"])):
        bad("dedup_key は sha1 の16進40桁")
    for k in ("duplicate_of", "rejected_reason", "supersedes", "superseded_by"):
        if k in w and not isinstance(w[k], str):
            bad(f"{k} は文字列")
    if "acknowledged_decisions" in w:
        ad = w["acknowledged_decisions"]
        if not isinstance(ad, list) or not all(isinstance(x, dict) and _s(x.get("decision")) and _s(x.get("reason"))
                                               for x in ad):
            bad("acknowledged_decisions は [{decision, reason}](どちらも空でない)")
    if w.get("review_status") == "rejected" and not _s(w.get("rejected_reason")):
        bad("rejected には rejected_reason(却下理由)が必要")
    if (w.get("_preamble") or "").strip():
        bad("最初の見出しより前に本文がある")
    order = w.get("_section_order") or []
    if order != list(ws.BODY_SECTIONS):
        missing = [h for h in ws.BODY_SECTIONS if h not in order]
        bad(f"本文の見出しは {' → '.join(ws.BODY_SECTIONS)} の順に1回ずつ"
            + (f"(無い: {', '.join(missing)})" if missing else "(余分・重複・順序違い)"))
    for h in ws.BODY_SECTIONS:
        if h in (w.get("_sections") or {}) and not w["_sections"][h].strip():
            bad(f"{h} が空(書くことが無ければ「なし」)")
    return out


def check_v02(w: dict, ctx: Context) -> list[Violation]:
    """ID の形式・ファイル名との一致・一意性。"""
    p, out = w["_path"], []
    cid = w.get("candidate_id")
    if not (isinstance(cid, str) and ws.CANDIDATE_ID_RE.match(cid)):
        out.append((p, "V02", "candidate_id が K<YYYYMMDD>-<slug>-<4〜6hex> ではない"))
    else:
        dk = w.get("dedup_key")
        if not (isinstance(dk, str) and dk.startswith(cid.rsplit("-", 1)[1])):
            out.append((p, "V02", "candidate_id の末尾が dedup_key の先頭と一致しない"))
        if w["_place"] == "candidates" and Path(p).stem != cid:
            out.append((p, "V02", "ファイル名が candidate_id と一致しない"))
        if [x for x in ctx["ids"]["candidate"].get(cid, []) if x != p]:
            out.append((p, "V02", "同じ candidate_id が別のファイルにもある"))
    if "wiki_id" in w:
        wid = w["wiki_id"]
        if not (isinstance(wid, str) and ws.WIKI_ID_RE.match(wid)):
            out.append((p, "V02", "wiki_id が W<YYYYMMDD>-<slug> ではない"))
        else:
            if [x for x in ctx["ids"]["wiki"].get(wid, []) if x != p]:
                out.append((p, "V02", "同じ wiki_id が別のファイルにもある"))
            if w["_place"] == "archive" and Path(p).stem != wid:
                out.append((p, "V02", "ファイル名が wiki_id と一致しない"))
    return out


def check_v03(w: dict, ctx: Context) -> list[Violation]:
    """Provenance: source が1件以上・すべて解決できる・本文の根拠節に全 id が出る。"""
    p, out = w["_path"], []
    ids = ws.all_source_ids(w)
    if not ids:
        out.append((p, "V03", "source_experience / source_decision / source_failure が1件もない"))
    for k in ws.SOURCE_KEYS:
        for s in (w.get(k) if isinstance(w.get(k), list) else []):
            if not isinstance(s, str):
                continue
            if k == "source_experience" and not ws.EXP_SOURCE_RE.match(s):
                out.append((p, "V03", f"{k} の形式が session-<sid>@<ts> ではない: {s[:60]}"))
            elif k == "source_failure" and not ws.FK_RE.match(s):
                out.append((p, "V03", f"{k} の形式が FK-xxx ではない: {s[:60]}"))
            elif resolve_source(s, k, ctx)[1] is None:
                out.append((p, "V03", f"{k} を解決できない(commit 済みの行・議事・台帳に無い): {s[:60]}"))
    prov = (w.get("_sections") or {}).get("## 根拠(Provenance)", "")
    for s in ids:
        if s not in prov:
            out.append((p, "V03", f"本文の ## 根拠(Provenance) に {s[:60]} が無い"))
    return out


def check_v04(w: dict, ctx: Context) -> list[Violation]:
    """evidence の quote が、ref が指す source の本文に逐語で含まれる(前後の空白を除くだけ)。"""
    p, out = w["_path"], []
    ev = w.get("evidence")
    if not isinstance(ev, list):
        return out
    by_kind = {k: set(w[k]) if isinstance(w.get(k), list) else set() for k in ws.SOURCE_KEYS}
    for i, e in enumerate(ev):
        if not isinstance(e, dict) or not isinstance(e.get("ref"), str) or not isinstance(e.get("quote"), str):
            continue
        kinds = [k for k in ws.SOURCE_KEYS if e["ref"] in by_kind[k]]
        if not kinds:
            out.append((p, "V04", f"evidence[{i}] の ref が source_* のどれにも無い"))
            continue
        q = e["quote"].strip()
        if len(q) < ws.MIN_QUOTE or len(q) > ws.MAX_QUOTE:
            out.append((p, "V04", f"evidence[{i}] の quote は {ws.MIN_QUOTE}〜{ws.MAX_QUOTE} 字"))
            continue
        text, row = resolve_source(e["ref"], kinds[0], ctx)
        if row is None:
            out.append((p, "V04", f"evidence[{i}] の参照先を解決できない"))
        elif q not in text:
            out.append((p, "V04", f"evidence[{i}] の quote が参照先の本文に逐語で含まれない(要約・言い換えは不可)"))
    return out


def check_v05(w: dict, ctx: Context) -> list[Violation]:
    """visibility == リポジトリの公開性・repo == このリポジトリ・全 source が public。"""
    p, out = w["_path"], []
    rv = ctx["repo_visibility"]
    if w.get("visibility") != rv:
        out.append((p, "V05", f"visibility がリポジトリの公開性({rv})と一致しない"))
    if w.get("repo") != ctx["repo_slug"]:
        out.append((p, "V05", "repo がこのリポジトリと一致しない(クロスリポの知識は置けない)"))
    for s in (w.get("source_experience") if isinstance(w.get("source_experience"), list) else []):
        m = ws.EXP_SOURCE_RE.match(s) if isinstance(s, str) else None
        for e in (ctx["exp_groups"].get((m.group(1), m.group(2)), []) if m else []):
            if e.get("visibility") != "public" or e.get("repo") != ctx["repo_slug"]:
                out.append((p, "V05", f"source_experience が public・このリポジトリの行ではない: {s[:60]}"))
                break
    for s in (w.get("source_decision") if isinstance(w.get("source_decision"), list) else []):
        d = ctx["decisions_by_id"].get(s) if isinstance(s, str) else None
        if d is not None and ws.decision_visibility(d, ctx["root"], rv) != "public":
            out.append((p, "V05", f"source_decision が public ではない: {s[:60]}"))
    for s in (w.get("source_failure") if isinstance(w.get("source_failure"), list) else []):
        if isinstance(s, str) and s in ctx["fk_rows"] and rv != "public":
            out.append((p, "V05", f"source_failure が public ではない: {s[:60]}"))
    return out


def check_v06(w: dict, ctx: Context) -> list[Violation]:
    """禁止語(check_repo_scope を import。二重管理しない)。理由に禁止語そのものは書かない。"""
    p = w["_path"]
    fm = {k: v for k, v in w.items() if not str(k).startswith("_")}
    decoded = json.dumps(fm, ensure_ascii=False) + "\n" + (w.get("_body") or "")
    out = []
    i = _forbidden_index(p, [w["_text"], decoded])
    if i is not None:
        out.append((p, "V06", f"禁止語(check_repo_scope.FORBIDDEN_CONTENT[{i}])を含む"))
    if find_violations([p]):
        out.append((p, "V06", "パスが check_repo_scope の禁止パターンに触れる"))
    return out


def check_v07(w: dict, ctx: Context) -> list[Violation]:
    p, out = w["_path"], []
    limits = (("title", ws.MAX_TITLE), ("summary", ws.MAX_SUMMARY))
    for k, n in limits:
        if isinstance(w.get(k), str) and len(w[k]) > n:
            out.append((p, "V07", f"{k} は {n} 字まで({len(w[k])}字)"))
    ev = w.get("evidence")
    if isinstance(ev, list):
        if len(ev) > ws.MAX_EVIDENCE:
            out.append((p, "V07", f"evidence は {ws.MAX_EVIDENCE} 件まで"))
        for i, e in enumerate(ev):
            if isinstance(e, dict) and isinstance(e.get("quote"), str) and len(e["quote"].strip()) > ws.MAX_QUOTE:
                out.append((p, "V07", f"evidence[{i}] の quote は {ws.MAX_QUOTE} 字まで"))
    if len(w.get("_body") or "") > ws.MAX_BODY:
        out.append((p, "V07", f"本文は {ws.MAX_BODY} 字まで"))
    if len((w.get("_sections") or {}).get("## 知識", "")) > ws.MAX_KNOWLEDGE:
        out.append((p, "V07", f"## 知識 は {ws.MAX_KNOWLEDGE} 字まで"))
    return out


def check_v08(w: dict, ctx: Context) -> list[Violation]:
    """置き場所と review_status の組(_candidates/ に approved は置けない等)。approved は承認キー必須。"""
    p, place, st = w["_path"], w["_place"], w.get("review_status")
    out = []
    allowed = ws.STATUS_BY_PLACE[place]
    if st not in allowed:
        out.append((p, "V08", f"{place} に置けるのは {' / '.join(sorted(allowed))} だけ"))
    if st == "approved":
        missing = [k for k in ws.APPROVED_KEYS if k not in w]
        if missing:
            out.append((p, "V08", f"approved に必要なキーが無い: {', '.join(missing)}"))
    return out


def check_v09(w: dict, ctx: Context) -> list[Violation]:
    """approved の中身: 人の承認者・日付・見直し期限・ウタガイ非空・wiki_id とファイル名。"""
    p, out = w["_path"], []
    st = w.get("review_status")
    if st == "superseded" and not _s(w.get("superseded_by")):
        out.append((p, "V09", "superseded には superseded_by が必要"))
    if st != "approved":
        return out
    ab = w.get("approved_by")
    if not _s(ab) or _is_bot(ab):
        out.append((p, "V09", "approved_by は人の名前か GitHub ハンドル(bot・空は不可)"))
    aa, rb = _date(w.get("approved_at")), _date(w.get("review_by"))
    if aa is None:
        out.append((p, "V09", "approved_at は YYYY-MM-DD"))
    if rb is None:
        out.append((p, "V09", "review_by は YYYY-MM-DD"))
    elif aa is not None and not aa < rb <= aa + timedelta(days=ws.MAX_REVIEW_DAYS):
        out.append((p, "V09", f"review_by は approved_at より後、{ws.MAX_REVIEW_DAYS} 日以内(6か月以内に見直す)"))
    ca = _date(w["created_at"][:10]) if isinstance(w.get("created_at"), str) else None
    if aa is not None and (ca is None or aa < ca):
        out.append((p, "V09", "approved_at は created_at(候補の作成日)以降(承認日を遡らせない)"))
    rv = w.get("review")
    if not isinstance(rv, dict) or any(not isinstance(rv.get(r), str) for r in ws.REVIEW_ROLES):
        out.append((p, "V09", "review は {スイシン, ウタガイ, ベッカイ}(すべて文字列)"))
    elif _empty_word(rv.get("ウタガイ")):
        out.append((p, "V09", "review.ウタガイ(反対理由)が空・空語"))
    wid = w.get("wiki_id")
    if not (isinstance(wid, str) and ws.WIKI_ID_RE.match(wid)):
        out.append((p, "V09", "wiki_id が W<YYYYMMDD>-<slug> ではない"))
    elif Path(p).stem != wid:
        out.append((p, "V09", "ファイル名が wiki_id と一致しない"))
    return out


def check_v10(w: dict, ctx: Context) -> list[Violation]:
    """重複: 正式 Wiki・他の候補とタイトルの語が DUPLICATE_RATIO 以上一致なら duplicate_of 必須。

    contradictions のある conflict 候補は除く(矛盾は重複として畳まず、人が個別に判断する)。
    """
    p, out = w["_path"], []
    dup = w.get("duplicate_of")
    if w["_place"] == "official" and _s(dup):
        out.append((p, "V10", "duplicate_of がある知識は承認できない"))
    title, cid = w.get("title"), w.get("candidate_id")
    if w["_place"] != "candidates" or w.get("review_status") not in ("candidate", "conflict") or _s(dup) \
            or not isinstance(title, str):
        return out
    cs = w.get("contradictions")
    if w.get("review_status") == "conflict" and isinstance(cs, list) and cs:
        return out  # 矛盾は人が個別に見る(Task 4)。重複(duplicate_of)に畳ませない
    others = [o for o in ctx["official"] if "_error" not in o]
    others += [o for o in ctx["candidates"] if "_error" not in o and o["_path"] != p]
    for o in others:
        if o["_place"] == "candidates" and _s(cid) and o.get("duplicate_of") == cid:
            continue  # 相手が自分を duplicate_of に書いている(自分が元)
        if not isinstance(o.get("title"), str):
            continue
        # 双方向: 既存のタイトル全体を含み語を足しただけの候補も重複として止める
        r = max(ws.title_similarity(title, o["title"]), ws.title_similarity(o["title"], title))
        if r >= ws.DUPLICATE_RATIO:
            oid = o.get("wiki_id") if o["_place"] == "official" else o.get("candidate_id")
            out.append((p, "V10", f"{oid or o['_path']} とタイトルの語が {r:.0%} 一致(duplicate_of: <id> を書く)"))
    return out


_NO_CONFLICT_CHECK = ("rejected",)  # 却下済みの候補は矛盾を書いたまま残してよい(人が解消した記録)


def check_v11(w: dict, ctx: Context) -> list[Violation]:
    """矛盾①: 候補の contradictions が非空なら review_status は conflict(却下済みは除く)。"""
    if w["_place"] != "candidates" or w.get("review_status") in ("conflict",) + _NO_CONFLICT_CHECK:
        return []
    cs = w.get("contradictions")
    if isinstance(cs, list) and cs:
        return [(w["_path"], "V11", "contradictions があるのに review_status が conflict ではない")]
    return []


def _conflict_reason(c: dict) -> str:
    neg = "・".join(c.get("negations") or []) or "否定語"
    return f"Decision {c['decision']} の否定({neg})と語が {len(c['units'])} 個重なる({', '.join(c['units'][:6])})"


def check_v12(w: dict, ctx: Context) -> list[Violation]:
    """矛盾②: 採用済み Decision の否定と語が CONFLICT_MIN_UNITS 以上重なる。

    候補(candidate)は conflict でなければ違反。approved は approved_at 以前の Decision について、該当 id が
    すべて acknowledged_decisions(reason 非空)に無ければ違反(approved_at より新しい Decision は V13 の警告)。
    判定関数の例外は validate_file が V12 の違反にする(fail-closed)。
    """
    p, place, st = w["_path"], w["_place"], w.get("review_status")
    if place == "archive" or st in _NO_CONFLICT_CHECK:
        return []
    until = None
    if place == "official":
        aa = w.get("approved_at")
        until = aa if _date(aa) is not None else None  # 読めない approved_at は全 Decision と比べる(止めすぎる側)
    found = ws.decision_conflicts(ws.conflict_text(w), ctx["decisions"], ctx.get("synonyms"), until=until,
                                  self_sources=ws.source_decisions(w))
    if place == "candidates":
        if found and st != "conflict":
            return [(p, "V12", f"{_conflict_reason(found[0])}: review_status を conflict にする")]
        return []
    acked = ws.acknowledged_ids(w)
    return [(p, "V12", f"{_conflict_reason(c)}: 承認するなら acknowledged_decisions に同じ向きである理由を書く"
                       "(逆向きなら承認しない)") for c in found if c["decision"] not in acked]


def check_v13(w: dict, ctx: Context) -> list[Warning]:
    """矛盾③: approved の Wiki と、approved_at より新しい adopted Decision → needs_review の警告(違反ではない)。"""
    if w["_place"] != "official" or w.get("review_status") != "approved":
        return []
    return [(w["_path"], did, "承認後の Decision と矛盾(Bootstrap は注入しない。再承認するか superseded にする)")
            for did in ws.needs_review(w, ctx["decisions"], ctx.get("synonyms"))]


def check_v15(w: dict, ctx: Context) -> list[Violation]:
    """related_wiki / supersedes / superseded_by / duplicate_of が実在の id を指す。"""
    p, out = w["_path"], []
    wiki_ids = ctx["ids"]["wiki"]
    approved = {o.get("wiki_id") for o in ctx["official"] if o.get("review_status") == "approved"}
    for r in (w.get("related_wiki") if isinstance(w.get("related_wiki"), list) else []):
        if r not in wiki_ids:
            out.append((p, "V15", f"related_wiki が実在しない wiki_id を指す: {str(r)[:60]}"))
    if _s(w.get("superseded_by")) and w["superseded_by"] not in approved:
        out.append((p, "V15", "superseded_by が実在する approved の wiki_id を指していない"))
    if _s(w.get("supersedes")) and w["supersedes"] not in wiki_ids:
        out.append((p, "V15", "supersedes が実在しない wiki_id を指す"))
    dup = w.get("duplicate_of")
    if _s(dup):
        own = {w.get("wiki_id"), w.get("candidate_id")}
        if dup in own or not (dup in wiki_ids or dup in ctx["ids"]["candidate"]):
            out.append((p, "V15", "duplicate_of が実在する別の wiki_id / candidate_id を指していない"))
    return out


RULES = (("V01", check_v01), ("V02", check_v02), ("V03", check_v03), ("V04", check_v04), ("V05", check_v05),
         ("V06", check_v06), ("V07", check_v07), ("V08", check_v08), ("V09", check_v09), ("V10", check_v10),
         ("V11", check_v11), ("V12", check_v12), ("V15", check_v15))


def validate_file(w: dict, ctx: Context) -> list[Violation]:
    """1ファイル(または抽出器の下書き)に V01〜V12・V15 を掛ける。"""
    p = str(w.get("_path", "?"))
    if "_error" in w:
        return [(p, "V01", f"読めない: {w['_error']}")]
    try:
        w = _materialize(w)
    except Exception as e:  # noqa: BLE001
        return [(p, "V01", f"読めない: {type(e).__name__}: {e}")]
    out: list[Violation] = []
    for code, fn in RULES:
        try:
            out.extend(fn(w, ctx))
        except Exception as e:  # noqa: BLE001 — 検査できなかった規則は違反(fail-closed)
            out.append((p, code, f"検査中に例外(fail-closed): {type(e).__name__}: {e}"))
    return out


def validate_synonyms(root: Path) -> list[Violation]:
    """V14: 同義語表の形式・禁止語。"""
    path, rel = Path(root) / ws.SYNONYMS_PATH, ws.SYNONYMS_PATH
    if not path.exists() and not path.is_symlink():
        return []
    if path.is_symlink() or not path.is_file():
        return [(rel, "V14", "同義語表は通常のファイルにする")]
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        return [(rel, "V14", f"読めない: {type(e).__name__}")]
    out = [(rel, "V14", r) for r in ws.parse_synonyms(text)[1]]
    i = _forbidden_index(rel, [text])
    if i is not None:
        out.append((rel, "V14", f"禁止語(check_repo_scope.FORBIDDEN_CONTENT[{i}])を含む"))
    return out


def stray_files(root: Path) -> list[Violation]:
    """V08: docs/wiki/ の中で、決まった置き場所の外にあるファイル(検証も Bootstrap も素通りするもの)。"""
    base = Path(root) / ws.WIKI_DIR
    out: list[Violation] = []
    if not base.exists():
        return out
    for dirpath, dirnames, filenames in os.walk(base):
        d = Path(dirpath)
        for name in filenames + [n for n in dirnames if (d / n).is_symlink()]:
            rel = (d / name).relative_to(Path(root)).as_posix()
            parent = (d / name).parent.relative_to(Path(root)).as_posix()
            ok = ((parent == ws.WIKI_DIR and name.endswith(".md") and not name.startswith("_"))
                  or rel == ws.SYNONYMS_PATH
                  or (parent in (ws.CANDIDATES_DIR, ws.ARCHIVE_DIR) and (name.endswith(".md") or name == ".gitkeep")))
            if not ok:
                out.append((rel, "V08", "Wiki の置き場所の外(docs/wiki/*.md・_candidates/・_archive/・_synonyms.txt だけ)"))
    return out


def validate_tree(root: Path) -> tuple[list[Violation], list[Warning]]:
    root = Path(root)
    try:
        ctx = build_context(root)
    except Exception as e:  # noqa: BLE001 — 入力を読めないなら全体を止める
        return [(".", "V03", f"検査を実行できない(fail-closed): {type(e).__name__}: {e}")], []
    violations: list[Violation] = []
    warnings: list[Warning] = []
    for w in ctx["official"] + ctx["candidates"] + ctx["archive"]:
        violations.extend(validate_file(w, ctx))
        if "_error" not in w:
            try:
                warnings.extend(check_v13(w, ctx))
            except Exception as e:  # noqa: BLE001 — 矛盾判定の失敗は needs_review 扱い
                warnings.append((w["_path"], "error", f"矛盾判定に失敗(needs_review 扱い): {type(e).__name__}"))
    for rel, reason in ctx["exp_errors"]:
        violations.append((rel, "V03", f"commit 済みの Experience を読めない(根拠として解決できない): {reason}"))
    for code, fn in (("V08", stray_files), ("V14", validate_synonyms)):
        try:
            violations.extend(fn(root))
        except Exception as e:  # noqa: BLE001
            violations.append((".", code, f"検査中に例外(fail-closed): {type(e).__name__}: {e}"))
    return violations, warnings


def needs_review_map(root: Path) -> dict[str, list[str]]:
    """approved の Wiki のうち needs_review のもの: {パス: [decision_id…]}。判定の例外は ["error"](注入しない側)。

    入力を読めなければ(build_context の例外)そのまま例外を上げる(呼び元が「全部 needs_review」として扱う)。
    """
    ctx = build_context(Path(root))
    out: dict[str, list[str]] = {}
    for w in ctx["official"]:
        if "_error" in w or w.get("review_status") != "approved":
            continue
        try:
            ids = ws.needs_review(w, ctx["decisions"], ctx.get("synonyms"))
        except Exception:  # noqa: BLE001 — 判定できない Wiki は needs_review(fail-closed)
            ids = ["error"]
        if ids:
            out[w["_path"]] = ids
    return out


# ---------------------------------------------------------------- 自己点検

_ST_TS = "2026-10-01T00:00:00Z"
_ST_REF = f"session-s1@{_ST_TS}"
_ST_NOTE = "学び: マージ前に競合ファイル一覧を確認すると事故が減る"
_ST_QUOTE = "競合ファイル一覧を確認すると事故が減る"
_ST_DID = "D20261001-selftest"
_ST_DECISION = ("---\ndecision_id: D20261001-selftest\ndate: 2026-10-01\ntitle: マージ手順\nstatus: adopted\n---\n"
                "# マージ手順\n\n## なぜ\n見落とし防止\n\n- **ウタガイ**: 遅くなる\n\n## 裁定\nマージ前に競合一覧を必ず確認する\n")
_ST_FK = ("| FK-002 | 2026-07-23 | ヒヤリハット | マージで競合ファイル一覧を確認せずコミットした | 実害なし | 自己申告 |"
          " 手順が無い | ルール化 | - | 監視中 | 2027-01-23 |")
_ST_WID = "W20261020-merge-conflict"
_ST_APPROVED = {"wiki_id": _ST_WID, "approved_by": "selftest-human", "approved_at": "2026-10-20",
                "review_by": "2027-04-18", "review": {"スイシン": "a", "ウタガイ": "急ぎでは重い", "ベッカイ": "c"}}


def _st_fm(**over) -> dict:
    fm = {"candidate_id": "", "title": "マージ前に競合ファイル一覧を確認する", "summary": "競合一覧を確認して事故を防ぐ。",
          "evidence": [{"ref": _ST_REF, "quote": _ST_QUOTE}], "confidence": 0.4, "confidence_basis": "rule=R2 / Exp のみ",
          "visibility": "public", "repo": "allgroup-inc/hojo-hq", "created_at": "2026-10-07T00:00:00Z",
          "proposed_by": "knowledge_extract.py@1 rule-based", "contradictions": [], "related_wiki": [],
          "related_skills": [], "review_status": "candidate", "dedup_key": "", "extract_run": "selftest",
          "source_experience": [_ST_REF]}
    fm.update(over)
    fm["dedup_key"] = fm["dedup_key"] or ws.dedup_key(fm["title"], ws.all_source_ids(fm))
    fm["candidate_id"] = fm["candidate_id"] or ws.make_candidate_id(date(2026, 10, 7), "st", fm["dedup_key"], set())
    return fm


def _st_sections(fm: dict, **over) -> dict:
    secs = {"## 知識": "マージ前に競合一覧を確認する。",
            "## 根拠(Provenance)": "\n".join(f"- {s}: 根拠" for s in ws.all_source_ids(fm)) or "- なし",
            "## 反証(ウタガイ)": "急ぎの修正では重い。", "## 適用範囲と例外": "main へのマージ。", "## 関連": "なし"}
    secs.update(over)
    return secs


def _st_write(root: Path, fm: dict, place: str = "candidates", name: str | None = None, sections=None) -> Path:
    d = root / ws.PLACES[place]
    d.mkdir(parents=True, exist_ok=True)
    stem = fm.get("wiki_id") if place != "candidates" else fm.get("candidate_id")
    path = d / (name or f"{stem}.md")
    path.write_text(ws.render_wiki(fm, sections if sections is not None else _st_sections(fm)), encoding="utf-8")
    return path


def _st_git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=str(root), check=True, capture_output=True)


def _st_setup(root: Path) -> None:
    _st_git(root, "init", "-q")
    for k, v in (("user.email", "selftest@example.com"), ("user.name", "selftest"), ("commit.gpgsign", "false")):
        _st_git(root, "config", k, v)
    _st_git(root, "remote", "add", "origin", "https://github.com/allgroup-inc/hojo-hq.git")
    rows = {"s1": ("public", "allgroup-inc/hojo-hq"), "P": ("private", "allgroup-inc/hojo-hq"),
            "O": ("private", "allgroup-inc/glow-docs-private")}
    for sid, (vis, repo) in rows.items():
        ev = {"ts": _ST_TS, "session_id": sid, "event": "note", "repo": repo, "visibility": vis, "text": _ST_NOTE}
        f = root / EXP_DIR / "2026-10" / f"session-{sid}.jsonl"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(ev, ensure_ascii=False) + "\n", encoding="utf-8")
    (root / "docs/議事").mkdir(parents=True)
    (root / "docs/議事/議事_20261001_selftest.md").write_text(_ST_DECISION, encoding="utf-8")
    (root / FAILURE_LEDGER).write_text("# 失敗台帳\n\n" + _ST_FK + "\n", encoding="utf-8")
    _st_git(root, "add", "-A")
    _st_git(root, "commit", "-q", "-m", "selftest")
    u = root / EXP_DIR / "2026-10" / "session-U.jsonl"  # 未追跡(commit しない)
    u.write_text((root / EXP_DIR / "2026-10" / "session-s1.jsonl").read_text(encoding="utf-8").replace('"s1"', '"U"'),
                 encoding="utf-8")


def _st_reset(root: Path) -> Path:
    shutil.rmtree(root / ws.WIKI_DIR, ignore_errors=True)
    return _st_write(root, _st_fm())


def _st_promote(root: Path, **over) -> dict:
    (root / ws.CANDIDATES_DIR / f"{_st_fm()['candidate_id']}.md").unlink()
    fm = _st_fm(review_status="approved", **{**_ST_APPROVED, **over})
    _st_write(root, fm, place="official", name=f"{_ST_WID}.md")
    return fm


def _st_replace(root: Path, old: str, new: str) -> None:
    p = root / ws.CANDIDATES_DIR / f"{_st_fm()['candidate_id']}.md"
    p.write_text(p.read_text(encoding="utf-8").replace(old, new, 1), encoding="utf-8")


def _st_cand(root: Path, **over) -> None:
    """基本の候補を書き換える(本文の Provenance は source に合わせる)。"""
    (root / ws.CANDIDATES_DIR / f"{_st_fm()['candidate_id']}.md").unlink()
    _st_write(root, _st_fm(**over))


_ST_NEG_DID = "D20261005-selftest-neg"
_ST_OPPOSITE = "マージ前の競合一覧の確認はしない"  # 基本の候補と「マージ・競合・一覧・確認」が重なる


def _st_decision(root: Path, day: str = "2026-10-05", outcome: str = _ST_OPPOSITE, did: str = _ST_NEG_DID) -> None:
    """否定語を含む adopted の議事を足して commit する(次の case の前に selftest がリセットする)。"""
    text = (f"---\ndecision_id: {did}\ndate: {day}\ntitle: 作業順\nstatus: adopted\n---\n# 作業順\n\n"
            f"## なぜ\n手戻り\n\n- **ウタガイ**: 事故\n\n## 裁定\n{outcome}\n")
    (root / "docs/議事" / f"議事_{day.replace('-', '')}_neg.md").write_text(text, encoding="utf-8")
    _st_git(root, "add", "-A", "docs/議事")
    _st_git(root, "commit", "-q", "-m", "selftest decision")


def _st_cases() -> list[tuple[str, object, str | None]]:
    word = FORBIDDEN_CONTENT[0]  # 禁止語の実文字列はソースに書かない
    fk_ev = [{"ref": "FK-002", "quote": "競合ファイル一覧を確認せず"}]
    other = dict(title="締切アラートの配信時期", source_failure=["FK-002"])
    arch = _st_fm(title="古い手順", source_failure=["FK-002"], review_status="superseded",
                  wiki_id="W20261001-old", superseded_by=_ST_WID)
    pid = f"session-P@{_ST_TS}"
    q = lambda s: [{"ref": _ST_REF, "quote": s}]  # noqa: E731
    long_title = "マージ前に競合ファイル一覧を確認するのは、急ぎの修正でも夜間の自動生成でも休日のリリース作業でも同じ"
    return [
        # 通すべきもの
        ("有効な候補", lambda r: None, None),
        ("FK を根拠にした候補", lambda r: _st_cand(r, source_failure=["FK-002"], evidence=fk_ev), None),
        ("Decision を根拠にした候補", lambda r: _st_cand(r, source_decision=[_ST_DID],
                                                       evidence=[{"ref": _ST_DID, "quote": "競合一覧を必ず確認する"}]), None),
        ("承認済み Wiki", lambda r: _st_promote(r), None),
        ("duplicate_of を書いた類似候補", lambda r: (_st_promote(r), _st_write(r, _st_fm(
            source_failure=["FK-002"], duplicate_of=_ST_WID))), None),
        ("正しい同義語表", lambda r: (r / ws.SYNONYMS_PATH).write_text("# x\nマージ, merge\n締切, 期限\n", encoding="utf-8"), None),
        ("実在の Wiki を指す related_wiki", lambda r: (_st_promote(r), _st_write(r, _st_fm(
            **other, related_wiki=[_ST_WID]))), None),
        ("approved を指す superseded", lambda r: (_st_promote(r), _st_write(r, arch, place="archive")), None),
        ("summary 200字ちょうど", lambda r: _st_cand(r, summary="あ" * ws.MAX_SUMMARY), None),
        ("quote 8字ちょうど", lambda r: _st_cand(r, evidence=q(_ST_QUOTE[:ws.MIN_QUOTE])), None),
        # V01
        ("JSON が壊れた frontmatter", lambda r: _st_replace(r, '"ref"', "ref"), "V01"),
        ("summary が無い", lambda r: _st_replace(r, "\nsummary: ", "\nxsummary: "), "V01"),
        ("本文の見出しが欠ける", lambda r: _st_replace(r, "## 反証(ウタガイ)", "## 反証"), "V01"),
        ("内部キーの偽装", lambda r: _st_replace(r, "---\n", "---\n_place: official\n"), "V01"),
        ("confidence が範囲外", lambda r: _st_cand(r, confidence=1.5), "V01"),
        ("needs_review を書いた", lambda r: _st_cand(r, review_status="needs_review"), "V01"),
        # V02
        ("ファイル名と candidate_id が違う", lambda r: (r / ws.CANDIDATES_DIR / f"{_st_fm()['candidate_id']}.md").rename(
            r / ws.CANDIDATES_DIR / "K20261020-other-0000.md"), "V02"),
        ("candidate_id の重複", lambda r: _st_write(r, _st_fm(), place="archive", name="W20261001-dup.md"), "V02"),
        ("candidate_id の形式違反", lambda r: _st_replace(r, "candidate_id: K", "candidate_id: X"), "V02"),
        # V03
        ("source が無い", lambda r: _st_cand(r, source_experience=[]), "V03"),
        ("解決できない Experience", lambda r: _st_cand(r, source_experience=[f"session-zzz@{_ST_TS}"]), "V03"),
        ("未追跡の Experience", lambda r: _st_cand(r, source_experience=[f"session-U@{_ST_TS}"]), "V03"),
        ("未知の Decision", lambda r: _st_cand(r, source_decision=["D20990101-none"]), "V03"),
        ("無い FK", lambda r: _st_cand(r, source_failure=["FK-999"]), "V03"),
        ("根拠節に id が無い", lambda r: _st_replace(r, f"- {_ST_REF}: 根拠", "- 根拠"), "V03"),
        # V04
        ("逐語でない quote", lambda r: _st_cand(r, evidence=q("要約して言い換えた別の文章")), "V04"),
        ("source に無い ref", lambda r: _st_cand(r, evidence=fk_ev), "V04"),
        ("quote 1字", lambda r: _st_cand(r, evidence=q(_ST_QUOTE[:1])), "V04"),
        ("quote 7字", lambda r: _st_cand(r, evidence=q(_ST_QUOTE[:ws.MIN_QUOTE - 1])), "V04"),
        # V05
        ("visibility が private", lambda r: _st_cand(r, visibility="private"), "V05"),
        ("private 行を source", lambda r: _st_cand(r, source_experience=[pid], evidence=[{"ref": pid, "quote": _ST_QUOTE}]),
         "V05"),
        ("他リポの行を source", lambda r: _st_cand(r, source_experience=[f"session-O@{_ST_TS}"]), "V05"),
        # V06
        ("summary に禁止語", lambda r: _st_cand(r, summary=f"x {word} y"), "V06"),
        ("本文に禁止語(小文字)", lambda r: _st_replace(r, "## 関連\nなし", f"## 関連\n{word.lower()}"), "V06"),
        ("非公開リポ名の言及(禁止語ではない)", lambda r: _st_cand(
            r, summary="移設先は " + FORBIDDEN_CONTENT[6].lower().replace("_", "-").strip("-") + " です"), None),
        ("ゼロ幅文字を挟んだ禁止語", lambda r: _st_cand(r, summary=f"x {word[:2]}\u200b{word[2:]} y"), "V06"),
        ("JSON エスケープした禁止語", lambda r: _st_replace(
            r, "related_skills: []", 'related_skills: ["' + "".join(f"\\u{ord(c):04x}" for c in word) + '"]'), "V06"),
        # V07
        ("summary 201字", lambda r: _st_cand(r, summary="あ" * (ws.MAX_SUMMARY + 1)), "V07"),
        ("title 81字", lambda r: _st_cand(r, title="あ" * (ws.MAX_TITLE + 1)), "V07"),
        ("evidence 11件", lambda r: _st_cand(r, evidence=[{"ref": _ST_REF, "quote": _ST_QUOTE}] * 11), "V07"),
        # V08
        ("_candidates に approved", lambda r: _st_cand(r, review_status="approved", **_ST_APPROVED), "V08"),
        ("直下に candidate", lambda r: shutil.move(str(r / ws.CANDIDATES_DIR / f"{_st_fm()['candidate_id']}.md"),
                                                  str(r / ws.WIKI_DIR / "x.md")), "V08"),
        ("置き場所の外のファイル", lambda r: (r / ws.WIKI_DIR / "_draft.md").write_text("x", encoding="utf-8"), "V08"),
        # V09
        ("ウタガイが空語", lambda r: _st_promote(r, review={"スイシン": "a", "ウタガイ": "なし", "ベッカイ": "c"}), "V09"),
        ("bot が承認", lambda r: _st_promote(r, approved_by="github-actions[bot]"), "V09"),
        ("review_by が approved_at 以前", lambda r: _st_promote(r, review_by="2026-10-20"), "V09"),
        ("review_by が6か月より先", lambda r: _st_promote(r, review_by="2099-12-31"), "V09"),
        ("wiki_id とファイル名が違う", lambda r: _st_promote(r, wiki_id="W20261020-other"), "V09"),
        # V10
        ("類似候補に duplicate_of なし", lambda r: (_st_promote(r), _st_write(r, _st_fm(source_failure=["FK-002"]))), "V10"),
        ("approved のタイトル全体+語を足した候補", lambda r: (_st_promote(r), _st_write(r, _st_fm(
            title=long_title, source_failure=["FK-002"]))), "V10"),
        ("approved に duplicate_of", lambda r: _st_promote(r, duplicate_of=_ST_WID), "V10"),
        # V11〜V13(矛盾)
        ("contradictions のある conflict 候補", lambda r: _st_cand(
            r, review_status="conflict", contradictions=[{"source": "K20261007-x-0000", "note": "逆向き"}]), None),
        ("却下済みの候補に contradictions", lambda r: _st_cand(
            r, review_status="rejected", rejected_reason="Decision が禁止",
            contradictions=[{"source": _ST_NEG_DID, "note": "Decision が否定"}]), None),
        ("contradictions があるのに candidate", lambda r: _st_cand(
            r, contradictions=[{"source": "K20261007-x-0000", "note": "逆向き"}]), "V11"),
        ("否定語の Decision と2語重なる candidate", lambda r: _st_decision(r), "V12"),
        ("否定語の Decision と2語重なる conflict 候補", lambda r: (_st_decision(r), _st_cand(
            r, review_status="conflict", contradictions=[{"source": _ST_NEG_DID, "note": "Decision が否定"}])), None),
        ("否定語の Decision と1語だけ重なる", lambda r: _st_decision(r, outcome="競合の解消はしない"), None),
        ("否定語の無い Decision と重なる", lambda r: _st_decision(r, outcome="マージ前の競合一覧の確認を急ぐ"), None),
        ("承認前の Decision と矛盾する approved", lambda r: (_st_decision(r), _st_promote(r)), "V12"),
        ("承認前の Decision を acknowledged した approved", lambda r: (_st_decision(r), _st_promote(
            r, acknowledged_decisions=[{"decision": _ST_NEG_DID, "reason": "同じ向き"}])), None),
        ("出典の Decision を否定ごと言い直した候補", lambda r: (_st_decision(r), _st_cand(
            r, source_decision=[_ST_NEG_DID], summary=_ST_OPPOSITE + "。",
            evidence=[{"ref": _ST_NEG_DID, "quote": _ST_OPPOSITE}])), None),
        ("出典の Decision の否定語を落とした候補", lambda r: (_st_decision(r), _st_cand(
            r, source_decision=[_ST_NEG_DID], evidence=[{"ref": _ST_NEG_DID, "quote": _ST_OPPOSITE}])), "V12"),
        ("定型語(main・docs)だけ重なる", lambda r: (_st_decision(r, outcome="main と docs の書き込みはしない"),
                                             _st_cand(r, title="main と docs の整理")), None),
        ("created_at より前の approved_at", lambda r: _st_promote(r, approved_at="2026-10-06", review_by="2027-03-01"),
         "V09"),
        ("承認後の Decision と矛盾する approved(警告)", lambda r: (_st_promote(r), _st_decision(r, day="2026-11-01")),
         "V13"),
        # V14
        ("同義語の同じ語が2行", lambda r: (r / ws.SYNONYMS_PATH).write_text("マージ, merge\nmerge, 統合\n", encoding="utf-8"),
         "V14"),
        ("同義語が1語だけ", lambda r: (r / ws.SYNONYMS_PATH).write_text("孤立\n", encoding="utf-8"), "V14"),
        # V15
        ("消えた Wiki を指す related_wiki", lambda r: _st_cand(r, related_wiki=["W20990101-none"]), "V15"),
        ("消えた Wiki を指す superseded_by", lambda r: (_st_promote(r), _st_write(
            r, {**arch, "superseded_by": "W20990101-none"}, place="archive")), "V15"),
    ]


def selftest() -> int:
    """V01〜V15 の正例(通るべきもの)と負例(止まるべきもの)を一時 git リポジトリで確かめる。

    期待 "V13" は「違反なし・needs_review の警告あり」。各 case の前に commit と docs/ を準備直後に戻す。
    """
    saved = {k: os.environ.pop(k) for k in _GIT_ENV_DROP if k in os.environ}
    failed: list[str] = []
    cases = _st_cases()
    try:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _st_setup(root)
            base = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(root), check=True, capture_output=True,
                                  text=True).stdout.strip()
            for name, mutate, expect in cases:
                _st_git(root, "reset", "-q", "--hard", base)
                _st_git(root, "clean", "-fdq", "--", "docs")
                _st_reset(root)
                (root / ws.SYNONYMS_PATH).unlink(missing_ok=True)
                try:
                    mutate(root)
                    vs, warns = validate_tree(root)
                except Exception as e:  # noqa: BLE001
                    failed.append(f"  {name}: 例外 {type(e).__name__}: {e}")
                    continue
                got = sorted({c for _p, c, _r in vs})
                if expect == "V13":
                    if vs or not warns:
                        failed.append(f"  {name}: 期待=警告のみ 実際={got or '違反なし'} 警告={warns[:2]}")
                elif (expect is None and (vs or warns)) or (expect is not None and expect not in got):
                    failed.append(f"  {name}: 期待={expect or '違反なし'} 実際={got or '違反なし'} {vs[:3]}")
    except Exception as e:  # noqa: BLE001
        failed.append(f"  準備に失敗: {type(e).__name__}: {e}")
    finally:
        os.environ.update(saved)
    if failed:
        print("自己点検に失敗しました:", file=sys.stderr)
        print("\n".join(failed), file=sys.stderr)
        return 2
    print(f"自己点検OK({len(cases)}件)")
    return 0


# ---------------------------------------------------------------- CLI

def _repo_root() -> Path | None:
    try:
        top = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    return Path(top.stdout.strip()) if top.returncode == 0 and top.stdout.strip() else None


def _gh_escape(s: str, prop: bool = False) -> str:
    s = str(s).replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
    return s.replace(":", "%3A").replace(",", "%2C") if prop else s


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Knowledge Wiki(候補・正式)の検査")
    ap.add_argument("--root", default=None, help="リポジトリルート(既定: 今いる git リポジトリの最上位)")
    ap.add_argument("--json", action="store_true", help='{"violations": [...], "warnings": [...]} を出す')
    ap.add_argument("--selftest", action="store_true", help="検査ロジックの自己点検")
    args = ap.parse_args(argv)
    if args.selftest:
        return selftest()
    root = Path(args.root) if args.root else _repo_root()
    if root is None:
        print("Wiki を検査できませんでした: git リポジトリの中で実行してください(fail-closed)", file=sys.stderr)
        return 1
    violations, warnings = validate_tree(root)
    if args.json:
        print(json.dumps({"violations": [list(v) for v in violations], "warnings": [list(x) for x in warnings]},
                         ensure_ascii=False))
        return 1 if violations else 0
    gha = bool(os.environ.get("GITHUB_ACTIONS"))
    for path, code, reason in violations:
        print(f"{path}: {code} {reason}")
        if gha:
            print(f"::error file={_gh_escape(path, True)}::{_gh_escape(f'{code} {reason}')}")
    for path, did, reason in warnings:
        print(f"{path}: 警告 needs_review {did} {reason}")
        if gha:
            print(f"::warning file={_gh_escape(path, True)}::{_gh_escape(f'needs_review {did} {reason}')}")
    if violations:
        return 1
    n = len(ws.iter_wiki(root, "official"))
    m = len(ws.iter_wiki(root, "candidates"))
    print(f"OK: Wiki {n}件・候補 {m}件・違反なし")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
