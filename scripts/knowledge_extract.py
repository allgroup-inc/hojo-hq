#!/usr/bin/env python3
"""WikiSkill Phase 2: Knowledge Extractor(規則ベース・stdlib のみ・AI なし)。

commit 済み・public・hojo-hq の記録だけから、規則 R1〜R4 で Wiki の **候補** を決定的に作り、
`docs/wiki/_candidates/` にだけ書く(設計書 7.1)。正式化(承認)はしない。

入力(collect_inputs):
    共通        どの区分も「git 管理下・HEAD から変わっていない・symlink でない」ファイルだけを読む
    Experience  git 管理下で HEAD から変わっていない JSONL(wiki_validate と同じ読み方)の、
                visibility == "public" かつ repo == "allgroup-inc/hojo-hq" の行だけ。他の行は読み捨て・数えない
    Decision    load_decisions の status ∈ {adopted, deferred} かつ public のもの
    失敗台帳    docs/失敗台帳.md の `| FK-xxx |` 行。台帳が未 commit なら丸ごと読まない(input_errors に残す)
    学び        (--include-gakubi のときだけ)docs/学び/*.md の箇条書き。evidence 専用で、単独では根拠にしない
    リポジトリ自体が public(hojo-hq)でなければ、どの区分も読まない(private → public の経路を作らない)

規則:
    R1 反復成功   同じ Skill を使い commit まで到達したセッションが2件以上(session_end 行)
    R2 note 接頭辞 `学び:` `失敗:` `誤関連:` で始まる note(NFKC 後に判定。全角コロン可)
    R3 失敗台帳   FK 行
    R4 Decision   adopted の裁定 / deferred は「未決。判断根拠にしない」

書く前に各候補へ wiki_validate.validate_file を掛け、違反は書かずに要約へ(理由コードつき)。
タイトルが既存(正式・候補・この実行で先に作った候補)と V10 の基準で似ているときは、
`duplicate_of` に最も似た id を書いて人に判断を任せる(黙って捨てない・重複を隠さない)。
矛盾の事前判定(設計書 7.4): 採用済み Decision の否定語と語が2つ以上重なる候補、`学び:` と `失敗:` で
語を2つ以上共有する note の候補(互いの candidate_id を書く)は review_status: conflict + contradictions。
conflict の候補には duplicate_of を付けない(矛盾は重複に畳まず人が見る)。自動統合はしない。

使い方:
    python3 scripts/knowledge_extract.py [--no-llm] [--include-gakubi] [--dry-run] [--max N] [--run-id ID]
                                         [--root PATH] [--break-stale-lock]
    exit 0 / 1(書込・検証の失敗・実行中にロックを失った)/ 2(使い方。--llm は未実装)/ 3(ロック中)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import unicodedata
from collections import Counter
from datetime import date
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import experience_log  # noqa: E402
import wiki_schema as ws  # noqa: E402
import wiki_validate  # noqa: E402
import wikiskill_lock  # noqa: E402
from decision_memory import load_decisions, parse_frontmatter  # noqa: E402
from wikiskill_common import audit, group_session_files, iso, utc_now  # noqa: E402
from wikiskill_lock import LockHeld  # noqa: E402

VERSION = "1.0"
PROPOSED_BY_RULE = f"knowledge_extract.py@{VERSION} rule-based"
LOCK_NAME = "knowledge-extract"
NOTE_PREFIXES = {"学び": "lesson", "失敗": "failure", "誤関連": "misretrieval"}
R1_MIN_SESSIONS = 2
MAX_CANDIDATES = 10
CONFIDENCE = {"R1": (0.30, 0.05, 0.50), "R2": (0.40, 0.10, 0.60), "R3": (0.70, 0.0, 0.70),
              "R4_adopted": (0.80, 0.0, 0.80), "R4_deferred": (0.30, 0.0, 0.30)}

PUBLIC_REPO = "allgroup-inc/hojo-hq"
GAKUBI_DIR = "docs/学び"
LLM_UNAVAILABLE = "未実装(Task 10 は G3 不承認)"
_COMPONENT = "knowledge_extract"
_SKILL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,99}$")
_RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_BULLET_RE = re.compile(r"^\s*[-*+]\s+(.*\S)\s*$")
_LIST_MARK_RE = re.compile(r"^(?:[-*+]|\d+[.)])\s+")
_OUTCOME_WORDS = ("裁定", "結論", "決定")
_WHY_WORDS = ("なぜ", "背景", "目的")
_NOTE_LABEL = {"学び": "学び(手順・気づき)", "失敗": "失敗(避けるべき手順)", "誤関連": "誤関連(Bootstrap の取り違え)"}
_MAX_SOURCES = ws.MAX_EVIDENCE  # 1候補の source は evidence の上限まで(Provenance と evidence を1対1にする)

Inputs = dict
Draft = dict
Wiki = dict


# ---------------------------------------------------------------- 小さな部品

def _one_line(s) -> str:
    return " ".join(str(s).split())


def _clip(s, n: int) -> str:
    s = _one_line(s)
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


def _quote(text, source_text: str | None = None) -> str | None:
    """原文の先頭からの逐語の切り出し(MIN_QUOTE〜MAX_QUOTE 字)。言い換えはしない。足りなければ None。"""
    if not isinstance(text, str):
        return None
    q = text.strip()[: ws.MAX_QUOTE].strip()
    if len(q) < ws.MIN_QUOTE:
        return None
    if source_text is not None and q not in source_text:
        return None
    return q


def _exp_ref(sid: str, ev: dict) -> str | None:
    ref = f"session-{sid}@{ev.get('ts')}"
    return ref if ws.EXP_SOURCE_RE.match(ref) else None


def _sections(knowledge: str, provenance: list[str], utagai: str, scope: str, related: list[str]) -> dict[str, str]:
    return {
        "## 知識": knowledge.strip() or "なし",
        "## 根拠(Provenance)": "\n".join(provenance) or "- なし",
        "## 反証(ウタガイ)": utagai.strip() or "なし",
        "## 適用範囲と例外": scope.strip() or "なし",
        "## 関連": "\n".join(related) or "なし",
    }


def _confidence(key: str, extra: int = 0) -> float:
    base, step, cap = CONFIDENCE[key]
    return round(min(cap, base + step * max(0, extra)), 2)


# ---------------------------------------------------------------- 入力

def _read_experience(root: Path) -> tuple[dict[str, list[dict]], int]:
    """wiki_validate と同じ読み方(git 管理下・HEAD と同じ内容・symlink 除外)で、public・hojo-hq の行だけ。"""
    sessions: dict[str, list[dict]] = {}
    rows = 0
    for sid, files in group_session_files(wiki_validate._committed_experience(root)).items():
        kept: list[dict] = []
        for f in files:
            try:
                events = experience_log._read_events(Path(root) / f)
            except (OSError, UnicodeDecodeError) as e:
                audit(root, _COMPONENT, f"experience unreadable (skipped): {Path(f).as_posix()} {type(e).__name__}")
                continue
            kept.extend(e for e in events if e.get("visibility") == "public" and e.get("repo") == PUBLIC_REPO)
        if kept:
            sessions[sid] = kept
            rows += len(kept)
    return sessions, rows


class _Uncommitted(Exception):
    """入力のファイルが commit 済みのまま(git 管理下・HEAD と同じ内容・symlink でない)ではない。"""


# commit 済みのまま(git 管理下・HEAD と同じ内容・symlink でない)の判定は検証器と1つを共有する(食い違わない)
_committed_files = wiki_validate.committed_files


def _read_decisions(root: Path, repo_vis: str) -> list[dict]:
    committed = _committed_files(root, "docs")
    decisions = [d for d in load_decisions(root) if d.get("path") in committed]  # 未追跡・未 commit の議事は読まない
    ids = Counter(d.get("id") for d in decisions)
    out = []
    for d in decisions:
        if d.get("status") not in ("adopted", "deferred") or ids[d.get("id")] != 1:
            continue  # 同じ id が2件ある議事は検証器も解決しない
        if ws.decision_visibility(d, root, repo_vis) != "public":
            continue
        path = Path(root) / d["path"]
        if path.is_symlink():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            audit(root, _COMPONENT, f"decision unreadable (skipped): {d['path']} {type(e).__name__}")
            continue
        out.append({**d, "file_text": text})
    return out


def _read_failures(root: Path) -> list[dict]:
    ledger = Path(root) / wiki_validate.FAILURE_LEDGER
    if not ledger.exists() and not ledger.is_symlink():
        return []
    if wiki_validate.FAILURE_LEDGER not in _committed_files(root, wiki_validate.FAILURE_LEDGER):
        raise _Uncommitted(wiki_validate.FAILURE_LEDGER)  # 未追跡・未 commit の変更がある台帳は丸ごと読まない
    rows, dup = wiki_validate._read_ledger(root)
    out = []
    for fid, line in rows.items():
        if fid in dup:
            continue  # 同じ FK が2行ある台帳は検証器も解決しない
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 4 or not cells[3] or cells[3] == "-":
            continue
        out.append({"id": fid, "date": cells[1], "category": cells[2], "fact": cells[3],
                    "measure": cells[7] if len(cells) > 7 and cells[7] != "-" else "", "line": line})
    return sorted(out, key=lambda r: r["id"])


def _read_gakubi(root: Path) -> list[dict]:
    out = []
    for rel in sorted(p for p in _committed_files(root, GAKUBI_DIR) if p.endswith(".md")):
        path = Path(root) / rel
        if path.is_symlink() or Path(rel).parent.as_posix() != GAKUBI_DIR:
            continue
        try:
            lines = path.read_text(encoding="utf-8").split("\n")
        except (OSError, UnicodeDecodeError) as e:
            audit(root, _COMPONENT, f"gakubi unreadable (skipped): {rel} {type(e).__name__}")
            continue
        for n, line in enumerate(lines, start=1):
            m = _BULLET_RE.match(line)
            if m:
                out.append({"path": rel, "line": n, "text": m.group(1)})
    return out


def collect_inputs(root: Path, include_gakubi: bool = False) -> Inputs:
    """抽出の入力。読めない区分は audit して 0 件で続ける(errors に区分名を残す)。"""
    root = Path(root)
    inp: Inputs = {"sessions": {}, "decisions": [], "failures": [], "gakubi": [], "errors": [],
                   "counts": {"experience_rows": 0, "sessions": 0, "decisions": 0, "failures": 0, "gakubi": 0}}
    slug = experience_log.repo_slug(root)
    repo_vis = ws.repo_visibility(root)
    if slug != PUBLIC_REPO or repo_vis != "public":
        inp["errors"].append("repository-not-public")
        audit(root, _COMPONENT, "repository is not the public hojo-hq; no input is read")
        return inp
    steps = [("experience", lambda: _read_experience(root)), ("decisions", lambda: _read_decisions(root, repo_vis)),
             ("failures", lambda: _read_failures(root))]
    if include_gakubi:
        steps.append(("gakubi", lambda: _read_gakubi(root)))
    for name, fn in steps:
        try:
            got = fn()
        except _Uncommitted as e:
            inp["errors"].append(f"{name}-uncommitted")
            audit(root, _COMPONENT, f"input {name} skipped: {e} is untracked or has uncommitted changes")
            continue
        except Exception as e:  # noqa: BLE001 — 区分ごとに続ける(要約の errors に出す)
            inp["errors"].append(name)
            audit(root, _COMPONENT, f"input {name} unreadable: {type(e).__name__}: {e}")
            continue
        if name == "experience":
            inp["sessions"], inp["counts"]["experience_rows"] = got
            inp["counts"]["sessions"] = len(got[0])
        else:
            inp[name] = got
            inp["counts"][name] = len(got)
    return inp


# ---------------------------------------------------------------- 規則

def _event_text(ev: dict) -> str:
    return wiki_validate._event_text(ev)


def rule_skill_success(inp: Inputs) -> list[Draft]:
    """R1: 同じ Skill が skills に入り commit が1件以上ある session_end が、R1_MIN_SESSIONS セッション以上。"""
    by_skill: dict[str, list[tuple[str, dict, str]]] = {}
    for sid in sorted(inp.get("sessions", {})):
        best: dict[str, tuple[dict, str]] = {}
        for ev in inp["sessions"][sid]:
            if ev.get("event") != "session_end":
                continue
            skills, commits = ev.get("skills"), ev.get("commits")
            ref = _exp_ref(sid, ev)
            if not (isinstance(skills, list) and isinstance(commits, list) and commits and ref):
                continue
            for sk in skills:
                if isinstance(sk, str) and _SKILL_RE.match(sk):
                    if sk not in best or str(ev.get("ts")) > str(best[sk][0].get("ts")):
                        best[sk] = (ev, ref)
        for sk, (ev, ref) in best.items():
            by_skill.setdefault(sk, []).append((sid, ev, ref))
    drafts = []
    for sk in sorted(by_skill):
        rows = sorted(by_skill[sk], key=lambda t: (str(t[1].get("ts")), t[0]))
        n = len(rows)
        if n < R1_MIN_SESSIONS:
            continue
        rows = rows[-_MAX_SOURCES:]
        evidence, refs, prov = [], [], []
        for sid, ev, ref in rows:
            q = _quote('"skills": ' + json.dumps(ev["skills"], ensure_ascii=False), _event_text(ev))
            if q is None:
                continue
            refs.append(ref)
            evidence.append({"ref": ref, "quote": q})
            prov.append(f"- {ref}: session_end(commit {len(ev['commits'])}件・skills に {sk})")
        if len(refs) < R1_MIN_SESSIONS:
            continue
        branches = Counter(str(ev.get("branch") or "不明") for _s, ev, _r in rows)
        word = branches.most_common(1)[0][0] + (f" ほか{len(branches) - 1}ブランチ" if len(branches) > 1 else "")
        last = rows[-1][1]["commits"][0]
        subject = last.get("subject") if isinstance(last, dict) and isinstance(last.get("subject"), str) else ""
        knowledge = f"Skill {sk} は {word} の作業で commit まで到達した実績が {n} セッションある。"
        title = _clip(f"Skill {sk} で commit まで到達: {subject}", ws.MAX_TITLE) if _one_line(subject) else \
            _clip(f"Skill {sk} の commit 到達実績", ws.MAX_TITLE)
        drafts.append({
            "rule": "R1", "slug": f"skill-{sk}", "title": title, "summary": _clip(knowledge, ws.MAX_SUMMARY),
            "sections": _sections(
                knowledge, prov,
                "Skill を使ったことと commit に到達したことの因果は確かめていない(同じセッションで起きただけ)。"
                "Experience 単独の根拠で、信頼階層の最下位。",
                f"Skill {sk} を使うか迷う場面の参考まで。Experience のみが根拠なので、承認されるまで手順として使わない。",
                [f"- Skill: {sk}"]),
            "source_experience": refs, "source_decision": [], "source_failure": [], "evidence": evidence,
            "confidence": _confidence("R1", n - R1_MIN_SESSIONS),
            "confidence_basis": f"rule=R1 / Exp のみ / {n}セッションで commit まで到達",
            "related_skills": [sk],
        })
    return drafts


def _note_prefix(raw: str) -> tuple[str, str] | None:
    """`学び:` 等で始まる note を (接頭辞, 原文の本文) に分ける。判定は NFKC 後(全角コロン可)。"""
    for i in range(min(len(raw), 24)):
        head = unicodedata.normalize("NFKC", raw[: i + 1]).lstrip()
        for p in NOTE_PREFIXES:
            if head == f"{p}:":
                return p, raw[i + 1:]
    return None


def rule_note_prefix(inp: Inputs) -> list[Draft]:
    """R2: 接頭辞つきの note。同じ接頭辞・同じ正規化本文は1候補にまとめ、別セッションの数だけ confidence を足す。"""
    groups: dict[tuple[str, str], list[tuple[str, dict, str, str]]] = {}
    for sid in sorted(inp.get("sessions", {})):
        for ev in inp["sessions"][sid]:
            if ev.get("event") != "note" or not isinstance(ev.get("text"), str):
                continue
            parsed = _note_prefix(ev["text"])
            ref = _exp_ref(sid, ev)
            if not parsed or not ref:
                continue
            prefix, body = parsed
            key = ws.normalize(body)
            if not key:
                continue
            groups.setdefault((prefix, key), []).append((sid, ev, ref, body))
    drafts = []
    for (prefix, _key), rows in groups.items():
        rows = sorted({r[2]: r for r in rows}.values(), key=lambda t: (str(t[1].get("ts")), t[0]))
        sessions = len({r[0] for r in rows})
        rows = rows[:_MAX_SOURCES]
        evidence, refs, prov = [], [], []
        for _sid, ev, ref, body in rows:
            q = _quote(body, ev["text"]) or _quote(ev["text"])
            if q is None:
                continue
            refs.append(ref)
            evidence.append({"ref": ref, "quote": q})
            prov.append(f"- {ref}: note「{_clip(q, 80)}」")
        if not refs:
            continue
        body = _one_line(rows[0][3])
        label = _NOTE_LABEL[prefix]
        knowledge = f"{label}: {_clip(body, 1000)}"
        if prefix == "誤関連":
            knowledge += "\n同義語表(docs/wiki/_synonyms.txt)・検索語の見直し材料にする。"
        drafts.append({
            "rule": "R2", "slug": f"note-{NOTE_PREFIXES[prefix]}", "title": _clip(f"{prefix}: {body}", ws.MAX_TITLE),
            "summary": _clip(f"{label}: {body}", ws.MAX_SUMMARY),
            "sections": _sections(
                knowledge, prov,
                "本人の所感(note)だけが根拠。別の事例で再現したか、反対の結果が無いかは確かめていない。",
                "Experience のみが根拠の候補。人が承認するまで手順として使わない。",
                []),
            "source_experience": refs, "source_decision": [], "source_failure": [], "evidence": evidence,
            "confidence": _confidence("R2", sessions - 1),
            "confidence_basis": f"rule=R2 / Exp のみ / note {len(refs)}件・{sessions}セッション",
            "related_skills": [], "note_prefix": prefix, "note_body": body,
        })
    return sorted(drafts, key=lambda d: d["source_experience"][0].split("@", 1)[1] + d["source_experience"][0])


def rule_failure_ledger(inp: Inputs) -> list[Draft]:
    """R3: 失敗台帳の FK 行 →「<分類>: <事実経過の要旨> を避けるには <対策>」。"""
    drafts = []
    for r in inp.get("failures", []):
        fid, line = r["id"], r["line"]
        q_fact = _quote(r["fact"], line)
        if q_fact is None:
            continue
        evidence = [{"ref": fid, "quote": q_fact}]
        q_measure = _quote(r["measure"], line) if r["measure"] else None
        if q_measure:
            evidence.append({"ref": fid, "quote": q_measure})
        category = _one_line(r["category"]) or "失敗"
        head = _one_line(r["fact"]).split("。", 1)[0]
        fact_s, measure_s = _clip(r["fact"], 400), _clip(r["measure"], 400)
        knowledge = f"{category}: {fact_s} を避けるには {measure_s}" if measure_s else \
            f"{category}: {fact_s}(対策は失敗台帳の {fid} を参照)"
        summary = f"{category}: {_clip(r['fact'], 90)} を避けるには {_clip(r['measure'], 90)}" if measure_s else \
            f"{category}: {_clip(r['fact'], 150)}"
        drafts.append({
            "rule": "R3", "slug": fid.lower(), "title": _clip(f"{category}: {head}", ws.MAX_TITLE),
            "summary": _clip(summary, ws.MAX_SUMMARY),
            "sections": _sections(
                knowledge, [f"- {fid}: 失敗台帳({r['date']})「{_clip(q_fact, 80)}」"],
                "台帳の対策が今も有効かは、台帳のステータスと見直し予定日で確かめる。台帳の方が上位で、"
                "この候補が台帳と食い違えば台帳に従う。",
                f"{category} に当たる作業。台帳 {fid} が監視中・クローズのどちらでも、原文を確かめてから使う。",
                [f"- 失敗台帳: docs/失敗台帳.md の {fid}"]),
            "source_experience": [], "source_decision": [], "source_failure": [fid], "evidence": evidence,
            "confidence": _confidence("R3"), "confidence_basis": "rule=R3 / FK 1件 / Exp 0",
            "related_skills": [],
        })
    return drafts


def _section_first_line(text: str, words: tuple[str, ...]) -> str:
    """議事の本文で、見出しが words で始まる最初の節の、最初の空でない行(行頭の箇条書き記号を除く・原文のまま)。"""
    _fm, body = parse_frontmatter(text)
    lines = body.split("\n")
    for word in words:
        pat = re.compile(r"^(#{2,3})\s*" + re.escape(word))
        for i, line in enumerate(lines):
            m = pat.match(line)
            if not m:
                continue
            level = len(m.group(1))
            for nxt in lines[i + 1:]:
                h = re.match(r"^(#{1,6})\s", nxt)
                if h and len(h.group(1)) <= level:
                    break
                s = _LIST_MARK_RE.sub("", nxt.strip()).strip()
                if s:
                    return s
            return ""
    return ""


def rule_decision_ruling(inp: Inputs) -> list[Draft]:
    """R4: adopted の裁定 → 設計判断の知識 / deferred →「未決。判断根拠にしない」。"""
    drafts = []
    for d in inp.get("decisions", []):
        did, text, status = d["id"], d["file_text"], d["status"]
        outcome_line = _section_first_line(text, _OUTCOME_WORDS)
        outcome = _LIST_MARK_RE.sub("", _one_line(d.get("outcome") or "")).strip()
        if status == "adopted" and not outcome:
            continue
        q = _quote(outcome_line, text) or _quote(d.get("title"), text) or \
            _quote(_section_first_line(text, _WHY_WORDS), text)
        if q is None:
            continue
        title = _one_line(d.get("title") or did)
        review = f"見直し期限 {d['review_by']}" if d.get("review_by") else "見直し期限は議事に記載なし"
        utagai = f"議事のウタガイ: {_clip(d['utagai'], 300)}" if _one_line(d.get("utagai") or "") else \
            "議事にウタガイの記載が読み取れない。"
        prov = [f"- {did}: 議事 {d['path']}({d.get('date') or '日付不明'}・{status})「{_clip(q, 80)}」"]
        related = [f"- 議事: {d['path']}"]
        if status == "adopted":
            knowledge = f"{_clip(outcome, 1000)}\n(議事 {did} の裁定。{review})"
            drafts.append({
                "rule": "R4", "slug": did, "title": _clip(title, ws.MAX_TITLE),
                "summary": _clip(f"裁定: {outcome}", ws.MAX_SUMMARY),
                "sections": _sections(
                    knowledge, prov,
                    f"議事の前提が変われば裁定も変わる。{review}を過ぎていれば再確認する。{utagai}",
                    f"議事 {did} の対象範囲(scope: {_clip(d.get('scope') or '記載なし', 100)})。"
                    "議事の方が上位で、この候補と議事が食い違えば議事に従う。",
                    related),
                "source_experience": [], "source_decision": [did], "source_failure": [], "evidence": [{"ref": did, "quote": q}],
                "confidence": _confidence("R4_adopted"), "confidence_basis": "rule=R4 / Decision 1件(adopted)/ Exp 0",
                "related_skills": [],
            })
        else:
            knowledge = f"未決: {_clip(title, 200)}。" + (f"現時点の記載: {_clip(outcome, 600)}" if outcome else "")
            drafts.append({
                "rule": "R4", "slug": did, "title": _clip(f"未決: {title}", ws.MAX_TITLE),
                "summary": _clip(f"未決の議事(判断根拠にしない): {title}", ws.MAX_SUMMARY),
                "sections": _sections(
                    knowledge, prov,
                    f"未決なので、どちらの結論にもなり得る。{utagai}",
                    "未決(deferred)の議事。判断根拠にしない。決裁が出たら議事を更新し、再抽出する。",
                    related),
                "source_experience": [], "source_decision": [did], "source_failure": [], "evidence": [{"ref": did, "quote": q}],
                "confidence": _confidence("R4_deferred"), "confidence_basis": "rule=R4 / Decision 1件(deferred・未決)/ Exp 0",
                "related_skills": [],
            })
    return drafts


RULES = [("R1", rule_skill_success), ("R2", rule_note_prefix), ("R3", rule_failure_ledger), ("R4", rule_decision_ruling)]


def _attach_gakubi(drafts: list[Draft], gakubi: list[dict]) -> None:
    """学びノートに同旨の箇条書きがあれば、そのファイルの場所だけを ## 関連 に足す(本文は写さない・根拠にしない)。"""
    if not gakubi:
        return
    notes = [(g["path"], ws.normalize(g["text"])) for g in gakubi]
    for d in drafts:
        quotes = [ws.normalize(e["quote"]) for e in d["evidence"]]
        quotes = [q for q in quotes if len(q) >= ws.MIN_QUOTE]
        hits = sorted({p for p, nb in notes if len(nb) >= ws.MIN_QUOTE and any(q in nb or nb in q for q in quotes)})
        if not hits:
            continue
        rel = d["sections"]["## 関連"]
        lines = [] if rel == "なし" else rel.split("\n")
        lines += [f"- 学びノート: {p}(同旨の記述あり。根拠にはしない)" for p in hits]
        d["sections"]["## 関連"] = "\n".join(lines)
        d["confidence_basis"] += f" / 学び一致 {len(hits)}件(根拠にしない)"


# ---------------------------------------------------------------- 候補にする・書く

def _mark_decision_conflicts(w: Wiki, d: Draft, decisions: list[dict], synonyms) -> None:
    """矛盾②の事前判定: 採用済み Decision の否定と語が重なれば conflict + contradictions。判定の例外も conflict。"""
    try:
        found = ws.decision_conflicts(ws.conflict_text(d), decisions, synonyms,
                                      self_sources=d.get("source_decision") or [])
    except Exception as e:  # noqa: BLE001 — 判定できないものは「矛盾あり」(fail-closed。検証器の V12 も止める)
        w["review_status"] = "conflict"
        w["contradictions"].append({"source": "decision_conflicts", "note": f"矛盾判定に失敗(fail-closed): {type(e).__name__}"})
        return
    for c in found:
        w["contradictions"].append({"source": c["decision"], "note": f"Decision が否定({'・'.join(c['negations'])})"
                                    f" / 重なる語: {', '.join(c['units'][:6])}"})
    if found:
        w["review_status"] = "conflict"


def finalize(d: Draft, root: Path, run_id: str, today: date, existing_keys: set[str], taken_ids: set[str], *,
             created_at: str | None = None, repo: str | None = None, visibility: str | None = None,
             decisions: list[dict] | None = None, synonyms: list[frozenset[str]] | None = None) -> Wiki | None:
    """下書きを候補(Wiki)にする。dedup_key が既存(全状態・全置き場所)にあれば None。

    採用済み Decision の否定と語が重なる(wiki_schema.decision_conflicts)なら review_status = conflict にし、
    contradictions に Decision の id を書く。decisions を渡さなければ commit 済みの議事を読む(検証器と同じ)。
    candidate_id の衝突が6桁でも解けなければ ValueError(make_candidate_id)。
    """
    sources = {k: [s for s in d.get(k) or []] for k in ws.SOURCE_KEYS}
    ids = [s for k in ws.SOURCE_KEYS for s in sources[k]]
    key = ws.dedup_key(d["title"], ids)
    if key in existing_keys:
        return None
    cid = ws.make_candidate_id(today, d.get("slug") or d["rule"], key, taken_ids)
    fm = {
        "candidate_id": cid, "title": d["title"], "summary": d["summary"], "evidence": d["evidence"],
        "confidence": float(d["confidence"]), "confidence_basis": d["confidence_basis"],
        "visibility": visibility or ws.repo_visibility(root), "repo": repo or experience_log.repo_slug(root),
        "created_at": created_at or f"{today.isoformat()}T00:00:00Z", "proposed_by": PROPOSED_BY_RULE,
        "contradictions": [], "related_wiki": [], "related_skills": list(d.get("related_skills") or []),
        "review_status": "candidate", "dedup_key": key, "extract_run": run_id,
    }
    for k in ws.SOURCE_KEYS:
        if sources[k]:
            fm[k] = sources[k]
    w = {**fm, "_path": f"{ws.CANDIDATES_DIR}/{cid}.md", "_place": "candidates",
         "_sections": dict(d["sections"]), "_rule": d["rule"]}
    if decisions is None:
        decisions = wiki_validate._committed_decisions(root)
    if synonyms is None:
        synonyms = wiki_validate._read_synonyms(root)
    _mark_decision_conflicts(w, d, decisions, synonyms)
    return w


def _shared_units(a: str, b: str, synonyms) -> list[str]:
    """2つの note の本文が共有する語(memory_bootstrap の語単位・同義語は1語)。多い方向の数を採る。"""
    import memory_bootstrap as mb  # 抽出器を Bootstrap に依存させるのはここだけ(語の数え方を揃える)

    fa, fb = mb.features(a), mb.features(b)
    ua = [g[0][1] for g in mb.query_groups([a], synonyms) if mb._group_matches(g, fb)]
    ub = [g[0][1] for g in mb.query_groups([b], synonyms) if mb._group_matches(g, fa)]
    return ua if len(ua) >= len(ub) else ub


_OPPOSITE_PREFIXES = frozenset({"学び", "失敗"})


def _cross_note_conflicts(items: list[tuple[Draft, Wiki | None, str | None]], synonyms) -> None:
    """矛盾①の事前判定: `学び:` と `失敗:` の note が CONFLICT_MIN_UNITS 語以上を共有すれば、この実行で作る候補に
    相手の id(この実行の candidate_id / 既にある候補・Wiki の id)を contradictions として書き、conflict にする。
    判定の例外は、関係しうる R2 の候補すべてを conflict にする(fail-closed)。"""
    notes = [(d, w, ident) for d, w, ident in items if d.get("note_prefix") in _OPPOSITE_PREFIXES and ident]
    try:
        pairs = []
        for i, (da, wa, ia) in enumerate(notes):
            for db, wb, ib in notes[i + 1:]:
                if da["note_prefix"] == db["note_prefix"] or (wa is None and wb is None):
                    continue
                units = _shared_units(da["note_body"], db["note_body"], synonyms)
                if len(units) >= ws.CONFLICT_MIN_UNITS:
                    pairs.append(((da, wa, ia), (db, wb, ib), units))
    except Exception as e:  # noqa: BLE001
        for _d, w, _i in notes:
            if w is not None:
                w["review_status"] = "conflict"
                w["contradictions"].append({"source": "note_conflicts",
                                            "note": f"矛盾判定に失敗(fail-closed): {type(e).__name__}"})
        return
    for (da, wa, ia), (db, wb, ib), units in pairs:
        for d_self, w_self, d_other, i_other in ((da, wa, db, ib), (db, wb, da, ia)):
            if w_self is None:
                continue  # 既にある候補・Wiki は書き換えない
            w_self["review_status"] = "conflict"
            w_self["contradictions"].append({
                "source": i_other,
                "note": f"`{d_other['note_prefix']}:` の note と逆向き / 共有する語: {', '.join(units[:6])}"})


def _fix_unwritten_refs(accepted: list[Wiki], provisional: dict[str, Draft]) -> None:
    """この実行で作られなかった候補(上限・検証で落ちた)を指す contradictions は、相手の根拠(Experience)を指し直す。"""
    written = {w["candidate_id"] for w in accepted}
    for w in accepted:
        for c in w.get("contradictions") or []:
            d = provisional.get(c.get("source"))
            if d is None or c["source"] in written:
                continue
            refs = d.get("source_experience") or []
            c["source"] = refs[0] if refs else "unwritten-candidate"
            c["note"] += "(相手の候補はこの実行では作られていない)"


def write_candidate(root: Path, w: Wiki) -> Path:
    """候補を書く唯一の入口。`root/docs/wiki/_candidates/<candidate_id>.md` 以外になるなら ValueError。既存は上書きしない。"""
    cid = w.get("candidate_id")
    if not isinstance(cid, str) or not ws.CANDIDATE_ID_RE.match(cid):
        raise ValueError(f"candidate_id が不正: {str(cid)[:60]!r}")
    root_r = Path(root).resolve()
    base = root_r / ws.CANDIDATES_DIR

    def check_dirs() -> None:
        parts = Path(ws.CANDIDATES_DIR).parts
        for i in range(1, len(parts) + 1):
            rel = Path(*parts[:i])
            p = Path(root) / rel
            if p.is_symlink() or (p.exists() and (not p.is_dir() or p.resolve() != root_r / rel)):
                raise ValueError(f"書込先が {ws.CANDIDATES_DIR}/ の外を指す: {rel.as_posix()}")

    check_dirs()
    target = base / f"{cid}.md"
    if target.parent != base or not target.resolve().is_relative_to(base) or target.resolve().parent != base:
        raise ValueError(f"書込先が {ws.CANDIDATES_DIR}/ の外: {cid}")
    base.mkdir(parents=True, exist_ok=True)
    check_dirs()
    fm = {k: v for k, v in w.items() if not str(k).startswith("_")}
    text = ws.render_wiki(fm, w.get("_sections") or {})
    with open(target, "x", encoding="utf-8") as f:
        f.write(text)
    return target


def _similar(w: Wiki, ctx: dict) -> str | None:
    """V10 と同じ基準(双方向の最大 ≥ DUPLICATE_RATIO)で最も似た既存の id。無ければ None。"""
    best, best_r = None, 0.0
    others = [o for o in ctx["official"] if "_error" not in o]
    others += [o for o in ctx["candidates"] if "_error" not in o and o.get("_path") != w["_path"]]
    for o in others:
        if not isinstance(o.get("title"), str):
            continue
        oid = o.get("wiki_id") if o["_place"] == "official" else o.get("candidate_id")
        if not isinstance(oid, str) or not oid or oid == w["candidate_id"]:
            continue
        r = max(ws.title_similarity(w["title"], o["title"]), ws.title_similarity(o["title"], w["title"]))
        if r >= ws.DUPLICATE_RATIO and r > best_r:
            best, best_r = oid, r
    return best


def _remember(ctx: dict, w: Wiki) -> None:
    """この実行で採った候補を検証の文脈に足す(V02 の一意性・V10 の類似・V15 の参照先がこの実行の分も見る)。"""
    m = wiki_validate._materialize(w)
    ctx["candidates"].append(m)
    ctx["ids"]["candidate"].setdefault(w["candidate_id"], []).append(w["_path"])


# ---------------------------------------------------------------- 実行

def _session_id(session_id: str | None) -> str:
    return (session_id or os.environ.get("CLAUDE_SESSION_ID", "").strip()
            or os.environ.get("GITHUB_RUN_ID", "").strip() and f"gha-{os.environ['GITHUB_RUN_ID'].strip()}"
            or f"pid-{os.getpid()}")


def run(root: Path, *, llm: bool = False, include_gakubi: bool = False, dry_run: bool = False,
        max_candidates: int = MAX_CANDIDATES, run_id: str | None = None, session_id: str | None = None,
        break_stale_lock: bool = False) -> dict:
    """抽出を1回実行して要約を返す。ロックは実行の間ずっと持つ(取れなければ LockHeld)。"""
    if llm:
        raise NotImplementedError(LLM_UNAVAILABLE)
    if isinstance(max_candidates, bool) or not isinstance(max_candidates, int) or max_candidates < 0:
        raise ValueError("max_candidates は 0 以上の整数")
    now = utc_now()
    run_id = run_id or f"local-{now:%Y%m%dT%H%M%SZ}"
    if not _RUN_ID_RE.match(run_id):
        raise ValueError("run_id は英数字と . _ - の64字まで")
    root = Path(root)
    lock = wikiskill_lock.acquire(root, LOCK_NAME, _session_id(session_id), break_stale=break_stale_lock)
    try:
        return _run_locked(root, lock, now, run_id, include_gakubi, dry_run, max_candidates)
    finally:
        wikiskill_lock.release(root, LOCK_NAME, lock)


def _run_locked(root: Path, lock: dict, now, run_id: str, include_gakubi: bool, dry_run: bool,
                max_candidates: int) -> dict:
    """ロックを途中で失ったら(heartbeat が LockHeld)、そこで止めて途中までの要約に lock_lost を付けて返す(exit 1)。"""
    summary = {"run_id": run_id, "dry_run": dry_run, "written": [], "skipped_duplicate": 0, "conflict": 0,
               "duplicate_of_marked": 0, "over_max": 0, "rejected_by_validator": [], "post_write_violations": [],
               "errors": [], "input_errors": [], "lock_lost": False, "inputs": {}}
    try:
        _run_body(root, lock, now, run_id, include_gakubi, dry_run, max_candidates, summary)
    except LockHeld as e:  # ここで出る LockHeld は heartbeat からだけ(取得失敗は run() の外で exit 3)
        summary["lock_lost"] = True
        summary["errors"].append(f"lock lost mid-run: {e}")
        audit(root, _COMPONENT, f"lock lost mid-run; stopped after {len(summary['written'])} write(s): {e}")
    return summary


def _run_body(root: Path, lock: dict, now, run_id: str, include_gakubi: bool, dry_run: bool,
              max_candidates: int, summary: dict) -> None:
    last_beat = time.monotonic()

    def beat(force: bool = False) -> None:
        nonlocal last_beat
        if force or time.monotonic() - last_beat >= wikiskill_lock.HEARTBEAT_EVERY_S:
            wikiskill_lock.heartbeat(root, LOCK_NAME, lock)
            last_beat = time.monotonic()

    inp = collect_inputs(root, include_gakubi=include_gakubi)
    summary["inputs"], summary["input_errors"] = dict(inp["counts"]), list(inp["errors"])
    beat(force=True)

    drafts: list[Draft] = []
    order = {name: i for i, (name, _fn) in enumerate(RULES)}
    for name, fn in RULES:
        try:
            drafts.extend(fn(inp))
        except Exception as e:  # noqa: BLE001 — 規則の不具合は失敗として要約に出す(exit 1)
            summary["errors"].append(f"rule {name}: {type(e).__name__}: {e}")
            audit(root, _COMPONENT, f"rule {name} failed: {type(e).__name__}: {e}")
    _attach_gakubi(drafts, inp["gakubi"])
    drafts = [d for _i, d in sorted(enumerate(drafts), key=lambda t: (-t[1]["confidence"], order[t[1]["rule"]], t[0]))]

    ctx = wiki_validate.build_context(root)
    existing_ids: dict[str, str] = {}
    for w in ctx["official"] + ctx["candidates"] + ctx["archive"]:
        if isinstance(w.get("dedup_key"), str):
            oid = w.get("wiki_id") if w.get("_place") != "candidates" and w.get("wiki_id") else w.get("candidate_id")
            existing_ids.setdefault(w["dedup_key"], oid if isinstance(oid, str) else "")
    existing = set(existing_ids)
    taken = set(ctx["ids"]["candidate"]) | set(ctx["ids"]["wiki"])
    repo, visibility, created_at = ctx["repo_slug"], ctx["repo_visibility"], iso(now)
    synonyms = ctx.get("synonyms") or []

    # 1) 先に全下書きを候補にする(candidate_id を決めてから、note 同士の矛盾を互いの id で書くため)
    items: list[tuple[Draft, Wiki | None, str | None]] = []
    errors: dict[int, str] = {}
    provisional: dict[str, Draft] = {}
    for i, d in enumerate(drafts):
        beat()
        ids = [s for k in ws.SOURCE_KEYS for s in d.get(k) or []]
        try:
            w = finalize(d, root, run_id, now.date(), existing, taken, created_at=created_at, repo=repo,
                         visibility=visibility, decisions=ctx["decisions"], synonyms=synonyms)
        except ValueError as e:
            errors[i] = str(e)[:200]
            items.append((d, None, None))
            continue
        if w is None:
            items.append((d, None, existing_ids.get(ws.dedup_key(d["title"], ids)) or None))
            continue
        existing.add(w["dedup_key"])
        taken.add(w["candidate_id"])
        provisional[w["candidate_id"]] = d
        items.append((d, w, w["candidate_id"]))
    _cross_note_conflicts(items, synonyms)

    # 2) 上限・重複・検証(従来の順と同じ数え方)
    accepted: list[Wiki] = []
    for i, (d, w, _ident) in enumerate(items):
        beat()
        ids = [s for k in ws.SOURCE_KEYS for s in d.get(k) or []]
        if len(accepted) >= max_candidates:
            summary["over_max"] += 1
            continue
        if i in errors:
            summary["rejected_by_validator"].append({"rule": d["rule"], "candidate_id": None, "sources": ids,
                                                     "codes": ["V02"], "reasons": [errors[i]]})
            continue
        if w is None:
            summary["skipped_duplicate"] += 1
            continue
        # 矛盾は人が個別に見る: conflict の候補は重複(duplicate_of)に畳まない
        dup = _similar(w, ctx) if w["review_status"] != "conflict" else None
        if dup:
            w["duplicate_of"] = dup
        violations = wiki_validate.validate_file(w, ctx)
        if violations:
            summary["rejected_by_validator"].append({
                "rule": d["rule"], "candidate_id": w["candidate_id"], "sources": ids,
                "codes": sorted({c for _p, c, _r in violations}), "reasons": [r for _p, _c, r in violations][:10]})
            continue
        summary["duplicate_of_marked"] += 1 if dup else 0
        accepted.append(w)
        _remember(ctx, w)
    _fix_unwritten_refs(accepted, provisional)
    summary["conflict"] = sum(1 for w in accepted if w["review_status"] == "conflict")

    if dry_run:
        summary["written"] = [w["_path"] for w in accepted]
        return
    for w in accepted:
        beat()
        try:
            write_candidate(root, w)
        except (OSError, ValueError) as e:
            summary["errors"].append(f"write {w['candidate_id']}: {type(e).__name__}: {e}")
            audit(root, _COMPONENT, f"write failed {w['candidate_id']}: {type(e).__name__}: {e}")
            continue
        summary["written"].append(w["_path"])
    if summary["written"]:
        ctx2 = wiki_validate.build_context(root)  # 書いた後のディスクの状態で、自分の出力をもう一度検査する
        for rel in summary["written"]:
            try:
                w2 = ws.load_wiki_file(root / rel, root)
            except (OSError, UnicodeDecodeError, ValueError) as e:
                summary["post_write_violations"].append([rel, "V01", f"読めない: {type(e).__name__}"])
                continue
            summary["post_write_violations"].extend(list(v) for v in wiki_validate.validate_file(w2, ctx2))


# ---------------------------------------------------------------- CLI

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="規則ベースの知識抽出(候補を docs/wiki/_candidates/ にだけ書く)")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--no-llm", action="store_true", help="規則ベースだけ(既定)")
    mode.add_argument("--llm", action="store_true", help="LLM 下書き(未実装)")
    ap.add_argument("--include-gakubi", action="store_true", help="docs/学び/ を evidence 専用の参考に読む")
    ap.add_argument("--dry-run", action="store_true", help="書かずに要約だけ出す")
    ap.add_argument("--max", type=int, default=MAX_CANDIDATES, help=f"書く候補の上限(既定 {MAX_CANDIDATES})")
    ap.add_argument("--run-id", default=None, help="抽出実行の id(既定: local-<UTC時刻>)")
    ap.add_argument("--root", default=None, help="リポジトリルート(既定: 今いる git リポジトリの最上位)")
    ap.add_argument("--break-stale-lock", action="store_true", help="終了を確認できない古いロックを明示的に外す")
    args = ap.parse_args(argv)
    if args.llm:
        print(LLM_UNAVAILABLE, file=sys.stderr)
        return 2
    if args.max < 0:
        print("--max は 0 以上", file=sys.stderr)
        return 2
    if args.run_id is not None and not _RUN_ID_RE.match(args.run_id):
        print("--run-id は英数字と . _ - の64字まで", file=sys.stderr)
        return 2
    root = Path(args.root) if args.root else wiki_validate._repo_root()
    if root is None:
        print("抽出できませんでした: git リポジトリの中で実行してください", file=sys.stderr)
        return 1
    try:
        summary = run(root, include_gakubi=args.include_gakubi, dry_run=args.dry_run, max_candidates=args.max,
                      run_id=args.run_id, break_stale_lock=args.break_stale_lock)
    except LockHeld as e:
        print(f"抽出を開始できません: {e}", file=sys.stderr)
        return 3
    except Exception as e:  # noqa: BLE001 — 入力・検証の準備ができないなら止める(fail-closed)
        audit(root, _COMPONENT, f"run failed: {type(e).__name__}: {e}")
        print(f"抽出に失敗しました: {type(e).__name__}: {e}", file=sys.stderr)
        return 1
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 1 if summary["errors"] or summary["post_write_violations"] else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
