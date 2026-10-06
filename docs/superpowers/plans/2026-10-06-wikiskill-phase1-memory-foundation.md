# Phase 1 WikiSkill Memory Foundation 実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Claude Code の新しいセッションになっても、過去の重要な Decision・前提・成功・失敗・再発防止事項を、必要な分だけ自動で復元できるようにする。

**Architecture:** hojo-hq の既存資産(議事・失敗台帳・決裁キュー・CLAUDE.md 再発防止メモ・SKILL.md)を「記憶の正本」とし、新設するのは ①機械記録(Experience Logger) ②議事の機械可読化(Decision Memory) ③関連情報だけを取り出す検索(Memory Bootstrap) ④公開リポに載せてよい記録かの検査(Privacy Boundary) ⑤緊急停止と正式Rollback(Rollback基盤) の5つ。すべて Claude Code の実在する hooks(SessionStart / UserPromptSubmit / PostToolUse / SessionEnd)+ Python 3.11 標準ライブラリだけで動かし、Skill の自動改善・自動更新は一切実装しない。

**Tech Stack:** Python 3.11(標準ライブラリのみ・pip 依存なし)/ Bash(hook の薄いラッパ1本)/ pytest(既存 `tests/scripts/`・`tests/integration/` の流儀)/ GitHub Actions(既存 `repo-scope.yml` に1ステップ追加)

**Spec:** `docs/superpowers/specs/2026-10-06-wikiskill-integration-design.md`(v1.1、2026-10-06 小柳さん基本承認)

**作業ブランチ:** `claude/superpowers-per-chat-3mbx56`(origin/main から作り直す。ローカル main は origin/main より81コミット遅れている — Task 0 参照)

## Global Constraints

- **変更禁止**: `.claude/skills/**`(110 Skills)/ `.claude/commands/**`(13リポへ丸ごと同期されるため)/ `scripts/update-skills.sh` / `.claude/hooks/superpowers-session-start.sh` / `.claude/agents/**`
- **Skill の自動改善・自動更新を実装しない**(Proposer / Validator / Evolution Gate は Phase 2 以降)
- **GitHub が正本**: Experience の原本 JSONL は Git にコミットする(Decision 4)。`.gitignore` に入れるのは `_local/`・`_audit.log`・`.claude/memory.off`・`.claude/locks/` のみ
- **silent fail 禁止**(修正1): 記録・検索の失敗は作業を止めないが、必ず `.claude/experience/_audit.log` に追記し、hook 出力の `systemMessage` で利用者に警告する
- **Experience に記録しないもの**: 利用者のプロンプト本文・Bash コマンド全文・ツール出力本文・プロジェクト外のパス。Bash は先頭トークン(プログラム名)だけ
- **Memory Bootstrap は現在のリポジトリ内しか読まない**(他リポ・private リポを横断しない。Decision 5「迷ったら Private」)
- **性能**: 各 hook の実行時間 500ms 以内(テストで上限を固定)
- **信頼階層**(修正3): Decision > 失敗台帳 > 再発防止メモ > Experience。Bootstrap 出力は必ずこの順で、各項目に出典ラベル `[D]` `[FK]` `[再発防止]` `[Skill]` `[Exp]` を付ける
- **hook 入力の契約**(Claude Code): stdin JSON に `session_id` / `cwd` / `hook_event_name` が来る。PostToolUse は `tool_name` / `tool_input`、UserPromptSubmit は `prompt`、SessionStart は `source`、SessionEnd は `reason`。出力は stdout JSON `{"hookSpecificOutput": {"hookEventName": "<event>", "additionalContext": "<text>"}, "systemMessage": "<warning>"}`。欠けていても落ちない(Review Focus 1)
- **Python は stdlib のみ**: hooks はどのコンテナでも pip なしで動く必要がある
- **1つの PR で導入**し、マージ時に `wikiskill-phase1-v1` タグを打つ(`git revert -m 1` で全戻し可能)
- **議事必須**: settings.json の hook 追加は「本番設定の変更(不可逆類型②)」にあたるため、三名体制の議事を Task 7 で残す(ウタガイ反対理由つき)

## Review Focus

1. **hook stdin が壊れている/`session_id` が無い**(古い Claude Code、手動実行): logger も bootstrap も例外で落ちず、`CLAUDE_SESSION_ID` 環境変数 → `unknown-<UTC時刻>` の順で補い、audit に1行残す → Task 2 `test_hook_tolerates_missing_session_id`
2. **commit されないまま終わったセッション**(クラウドのコンテナ破棄): SessionEnd は commits=[] でも記録を書き、Bootstrap 側は「commit されていない Experience は他セッションから見えない」と README で明記 → Task 2 `test_session_end_without_commits`
3. **見直し期限が過去の Decision**: 隠さず「期限切れ・再議論対象」ラベルで表示する(既存ルール「期限切れは自動で再議論」) → Task 4 `test_expired_decision_is_labeled_not_hidden`
4. **Edit/Write の対象がプロジェクト外**(`/home/user/glow-docs-private/...` など): パスは `<external>` に置換され、記録に残らない → Task 1 `test_sanitize_path_outside_project`
5. **UserPromptSubmit が毎回発火する**: 段2 はセッションごとに1回だけ。マーカーで2回目以降は何も出さない(毎回数千文字を注入してコンテキストを食い潰さない) → Task 4 `test_prompt_stage_runs_once_per_session`

---

## File Structure

| 種別 | パス | 責務 |
|---|---|---|
| Create | `scripts/wikiskill_common.py` | 共通: project_dir 解決・停止スイッチ判定・stdin JSON 読取・audit 追記・hook 出力 JSON 生成。他の4スクリプトはこれだけに依存 |
| Create | `scripts/experience_log.py` | A: イベント追記(サニタイズ込み)・hook モード・note モード・SessionEnd 集計 |
| Create | `scripts/decision_memory.py` | C: 議事ファイル走査(frontmatter + 旧形式ヒューリスティック)・`--check`・`--list --json` |
| Create | `scripts/memory_bootstrap.py` | D: 検索語生成・関連度スコア・6区分の取得・markdown 整形・hook モード(段1/段2) |
| Create | `scripts/check_experience_privacy.py` | K: hojo-hq 内の Experience が公開可能かの CI 検査・`--selftest` |
| Create | `scripts/experience_archive.py` | I/Decision 4: サイズ監視(`--check`)と 180 日超の月次 gzip 化(`--archive`) |
| Create | `.claude/hooks/wikiskill-hook.sh` | hook ラッパ1本。`wikiskill-hook.sh <event>` で停止スイッチを見てから Python を呼ぶ。常に exit 0 |
| Create | `docs/wikiskill/README.md` | 運用ガイド(何が記録され、何が復元され、どう止めるか) |
| Create | `docs/wikiskill/Rollback手順.md` | 守り部向け: 緊急停止 → 正式 revert → 議事化 の手順 |
| Create | `docs/wikiskill/議事frontmatterテンプレート.md` | 新規議事に付ける YAML frontmatter の雛形と各項目の意味 |
| Create | `docs/wikiskill/Phase1受け入れ記録.md` | 手動 E2E(実セッション A→B)の結果を記入する台帳 |
| Create | `docs/議事_20261006_WikiSkill_Phase1導入.md` | 本導入の三名体制議事(frontmatter 付き。Bootstrap の最初の実データでもある) |
| Create | `tests/scripts/test_experience_log.py` ほか5本 | 各スクリプトの単体テスト |
| Create | `tests/integration/test_wikiskill_memory_e2e.py` | Session A → Session B の自動 E2E |
| Modify | `.claude/settings.json` | hooks に SessionStart 2本目・UserPromptSubmit・PostToolUse・SessionEnd を追加(既存行は不変) |
| Modify | `.gitignore` | 末尾に4行追加 |
| Modify | `.github/workflows/repo-scope.yml` | `check_experience_privacy.py` のステップ追加 |
| Modify | `CLAUDE.md` | 「記憶の仕組み(WikiSkill Phase 1)」節(10行以内)+ 再発防止メモ1行 |
| Modify | `docs/全体マップ.md` | 置き場所を1行追加 |

共通の型(Python dict)は Task 1 と Task 3 の Interfaces で定義し、以後の Task はそれを参照する。

---

### Task 0: ブランチ準備と基線確認

**Files:**
- 変更なし(Git 操作のみ)

**Interfaces:**
- Produces: origin/main と同一内容の作業ブランチ `claude/superpowers-per-chat-3mbx56`。以後の全 Task はこの上で行う

**Public/Private への影響:** なし

- [ ] **Step 1: 現在地を確認する**

Run: `git branch --show-current && git status --short | wc -l && git fetch origin main && git rev-list --count main..origin/main`
Expected: `main` / `0` / 81前後(ローカル main が遅れていることの確認)

- [ ] **Step 2: 指定ブランチを origin/main から作り直す**

前回の同名ブランチは PR #… でマージ済み(Phase 2 Week 3)。マージ済み履歴を再利用せず、origin/main から再出発する(CLAUDE.md「生成物を再生成する前に最新を取り込む」と同根)。

Run: `git checkout -B claude/superpowers-per-chat-3mbx56 origin/main && git log --oneline -1`
Expected: `04dbc28f4`(または origin/main の最新)

- [ ] **Step 3: 既存の検査が通る基線を確認する**

Run: `python3 scripts/check_repo_scope.py --selftest && python3 scripts/check_repo_scope.py && python3 -m pytest tests/skill_validation -q 2>&1 | tail -2`
Expected: `自己点検OK(…件)` / `OK: …含まれていません` / pytest `passed`

- [ ] **Step 4: 既存 hook が今も動くことを確認する(回帰の基準)**

Run: `echo '{"session_id":"base","hook_event_name":"SessionStart","source":"startup","cwd":"'$PWD'"}' | CLAUDE_PROJECT_DIR=$PWD bash .claude/hooks/superpowers-session-start.sh | head -c 200`
Expected: `{ "hookSpecificOutput": { "hookEventName": "SessionStart", ...` で始まる JSON

---

### Task 1: Experience Logger コア(`experience_log.py` + `wikiskill_common.py`)

**Files:**
- Create: `scripts/wikiskill_common.py`
- Create: `scripts/experience_log.py`
- Test: `tests/scripts/test_wikiskill_common.py`
- Test: `tests/scripts/test_experience_log.py`

**Interfaces:**
- Produces(`wikiskill_common.py`):
  - `project_dir() -> Path` — `CLAUDE_PROJECT_DIR` → `git rev-parse --show-toplevel` → cwd の順
  - `disabled(root: Path) -> bool` — `HOJO_MEMORY_OFF` が truthy、または `root/.claude/memory.off` が存在
  - `read_hook_input() -> dict` — stdin の JSON。空・壊れていたら `{}`
  - `session_id_of(payload: dict) -> str` — `payload["session_id"]` → `CLAUDE_SESSION_ID` → `f"unknown-{UTC %Y%m%dT%H%M%SZ}"`
  - `audit(root: Path, component: str, message: str) -> None` — `root/.claude/experience/_audit.log` に `ISO8601\t<component>\t<message>` を追記。書けなければ stderr
  - `emit(event: str, additional_context: str | None = None, system_message: str | None = None) -> None` — 上記 Global Constraints の形の JSON を stdout に1回だけ出す。両方 None なら `{}`
  - `EXPERIENCE_DIR = ".claude/experience"`, `LOCAL_DIR = ".claude/experience/_local"`
- Produces(`experience_log.py`):
  - `Event = dict`(キー: `ts`(ISO8601 UTC) / `session_id` / `event` ∈ {`session_start`,`tool`,`skill`,`note`,`session_end`} / `repo`(例 `allgroup-inc/hojo-hq`)/ `visibility` ∈ {`public`,`private`} / `branch` / イベント固有キー)
  - `PUBLIC_REMOTES = {"allgroup-inc/hojo-hq"}` — ここに無い remote は `visibility="private"`
  - `repo_slug(root: Path) -> str` — `git remote get-url origin` から `owner/name`。取れなければ `"unknown"`(→ private 扱い)
  - `sanitize_path(p: str, root: Path) -> str` — root 配下なら相対パス、それ以外は `"<external>"`
  - `session_file(root: Path, session_id: str, ts: datetime) -> Path` — `root/.claude/experience/YYYY-MM/session-<session_id>.jsonl`
  - `append_event(root: Path, event: Event) -> Path` — 1行追記。失敗時は `audit()` し、例外を `ExperienceWriteError` として投げ直す(呼び元の hook モードが systemMessage に変える)
  - `build_tool_event(payload: dict, root: Path) -> Event | None` — `tool_name` が `Bash` なら `{"tool":"Bash","program": <先頭トークン>}`、`Edit|Write|MultiEdit` なら `{"tool":…, "path": sanitize_path(file_path)}`、`Skill` なら `event="skill", {"skill": tool_input["skill"]}`。それ以外は None
  - `summarize_session(root: Path, session_id: str) -> Event` — その session の JSONL を読み、`session_start` の `head` から `git log head..HEAD --format=%h%x09%s` で commits、ツール別件数、使用 skill、`duration_s` を集計した `session_end` イベントを返す
  - CLI: `python3 scripts/experience_log.py hook <SessionStart|PostToolUse|SessionEnd>`(stdin JSON)/ `python3 scripts/experience_log.py note "<text>"`(1,000文字で切る)

**Public/Private への影響:** `visibility` 判定をここで固定する。hojo-hq 以外の remote では必ず `private`

- [ ] **Step 1: 共通モジュールのテストを書く**

```python
# tests/scripts/test_wikiskill_common.py
def test_disabled_by_env(tmp_path, monkeypatch):
    monkeypatch.setenv("HOJO_MEMORY_OFF", "1"); assert disabled(tmp_path)
def test_disabled_by_file(tmp_path):
    (tmp_path / ".claude").mkdir(); (tmp_path / ".claude/memory.off").touch(); assert disabled(tmp_path)
def test_read_hook_input_tolerates_garbage(monkeypatch):
    monkeypatch.setattr("sys.stdin", io.StringIO("not json")); assert read_hook_input() == {}
def test_session_id_fallback_order(monkeypatch):
    monkeypatch.setenv("CLAUDE_SESSION_ID", "env-id"); assert session_id_of({}) == "env-id"
    monkeypatch.delenv("CLAUDE_SESSION_ID"); assert session_id_of({}).startswith("unknown-")
def test_audit_appends_tab_separated_line(tmp_path):
    audit(tmp_path, "logger", "disk full"); line = (tmp_path/".claude/experience/_audit.log").read_text().splitlines()[-1]
    assert line.split("\t")[1:] == ["logger", "disk full"]
def test_emit_shape(capsys):
    emit("SessionStart", additional_context="X", system_message="W")
    out = json.loads(capsys.readouterr().out)
    assert out["hookSpecificOutput"] == {"hookEventName": "SessionStart", "additionalContext": "X"} and out["systemMessage"] == "W"
```

- [ ] **Step 2: 失敗を確認する**

Run: `python3 -m pytest tests/scripts/test_wikiskill_common.py -q`
Expected: FAIL(`ModuleNotFoundError: wikiskill_common`)

- [ ] **Step 3: `scripts/wikiskill_common.py` を Interfaces の signature どおり実装する**

テストは `sys.path` に `scripts/` を足して import する(既存 `tests/scripts/test_verify_mikata_seido.py` の流儀に合わせる)。

- [ ] **Step 4: 合格を確認する**

Run: `python3 -m pytest tests/scripts/test_wikiskill_common.py -q`
Expected: 6 passed

- [ ] **Step 5: Logger のテストを書く**

```python
# tests/scripts/test_experience_log.py  (fixture `repo` = tmp_path に git init + origin を https://github.com/allgroup-inc/hojo-hq.git に設定 + 1 commit)
def test_sanitize_path_inside_project(repo):  assert sanitize_path(str(repo/"docs/a.md"), repo) == "docs/a.md"
def test_sanitize_path_outside_project(repo): assert sanitize_path("/home/user/glow-docs-private/x.md", repo) == "<external>"
def test_visibility_public_for_hojo_hq(repo): assert repo_slug(repo) == "allgroup-inc/hojo-hq"
def test_visibility_private_for_other_remote(repo_private):  # origin = allgroup-inc/glow-docs-private
    ev = start_event(repo_private, "s1"); assert ev["visibility"] == "private"
def test_append_event_writes_one_line_per_call(repo):
    p = append_event(repo, start_event(repo, "s1")); append_event(repo, {"ts":..., "session_id":"s1", "event":"note", "text":"ok"})
    assert len(p.read_text().splitlines()) == 2 and p.name == "session-s1.jsonl"
def test_bash_tool_event_keeps_only_program(repo):
    ev = build_tool_event({"tool_name":"Bash","tool_input":{"command":"git commit -m 'secret words'"}}, repo)
    assert ev["program"] == "git" and "secret" not in json.dumps(ev)
def test_skill_tool_event(repo):
    assert build_tool_event({"tool_name":"Skill","tool_input":{"skill":"writing-plans"}}, repo)["skill"] == "writing-plans"
def test_other_tools_ignored(repo): assert build_tool_event({"tool_name":"Read","tool_input":{}}, repo) is None
def test_note_truncated_to_1000(repo): assert len(note_event("s1", "x"*2000)["text"]) == 1000
def test_summarize_session_collects_commits(repo):
    append_event(repo, start_event(repo, "s1"))         # head を記録
    (repo/"f.txt").write_text("1"); git(repo, "add", "f.txt"); git(repo, "commit", "-m", "feat: f")
    s = summarize_session(repo, "s1"); assert s["commits"][0]["subject"] == "feat: f" and s["event"] == "session_end"
def test_append_event_failure_is_audited(repo, monkeypatch):
    monkeypatch.setattr("builtins.open", raising_open)  # 書込を失敗させる(実装者が fixture 化)
    with pytest.raises(ExperienceWriteError): append_event(repo, start_event(repo, "s1"))
    # audit も open を使うので stderr 側に出ることを capsys で確認
```

- [ ] **Step 6: 失敗を確認する**

Run: `python3 -m pytest tests/scripts/test_experience_log.py -q`
Expected: FAIL(import error)

- [ ] **Step 7: `scripts/experience_log.py` を実装する**

`start_event()` は `branch`(`git rev-parse --abbrev-ref HEAD`)と `head`(`git rev-parse HEAD`)と `source` を含める。hook モードの `SessionEnd` は `summarize_session()` の結果を追記し、`_local/<session_id>.ended` マーカーを置く(Phase 2 の stale lock 判定で使う)。hook モードは `ExperienceWriteError` を捕まえて `emit(event, system_message="⚠ Experience記録に失敗: <理由>。audit: .claude/experience/_audit.log")` を出し exit 0。

- [ ] **Step 8: 合格を確認する**

Run: `python3 -m pytest tests/scripts/test_experience_log.py tests/scripts/test_wikiskill_common.py -q`
Expected: 17 passed

- [ ] **Step 9: Commit**

```bash
git add scripts/wikiskill_common.py scripts/experience_log.py tests/scripts/test_wikiskill_common.py tests/scripts/test_experience_log.py
git commit -m "feat(wikiskill): Experience Logger コア — セッション記録を公開可能な範囲だけJSONLに残す(silent fail禁止)"
```

**Acceptance Criteria(Task 1):** 上記17テスト合格 / Bash コマンド全文・プロンプト本文が JSONL に一切現れない / hojo-hq 以外の remote で `visibility=private`
**失敗時の Rollback:** このコミットを revert するだけ(hooks 未登録のため本番影響なし)

---

### Task 2: hook ラッパと settings.json 登録(Experience 側)

**Files:**
- Create: `.claude/hooks/wikiskill-hook.sh`
- Modify: `.claude/settings.json`(hooks 配下のみ)
- Modify: `.gitignore`(末尾4行)
- Test: `tests/scripts/test_wikiskill_hook_sh.py`

**Interfaces:**
- Consumes: Task 1 の CLI(`experience_log.py hook <event>`)
- Produces: `bash .claude/hooks/wikiskill-hook.sh <SessionStart|UserPromptSubmit|PostToolUse|SessionEnd>`(stdin JSON をそのまま Python に渡す)。先頭で `disabled()` 相当(`HOJO_MEMORY_OFF` / `.claude/memory.off`)を bash で判定し、停止中は `{}` を出して exit 0。Python が無い/例外で落ちた場合も `{"systemMessage":"⚠ wikiskill hook 失敗: …"}` を出して exit 0(**exit 0 以外を返さない**: 既存作業を hook の都合で止めない)
- Produces(settings.json 追記。既存の SessionStart 1本目は不変):

```json
"SessionStart": [ {既存 superpowers…}, {"matcher": "startup|resume|clear|compact", "hooks": [{"type":"command","command":"$CLAUDE_PROJECT_DIR/.claude/hooks/wikiskill-hook.sh SessionStart"}]} ],
"UserPromptSubmit": [ {"hooks": [{"type":"command","command":"$CLAUDE_PROJECT_DIR/.claude/hooks/wikiskill-hook.sh UserPromptSubmit"}]} ],
"PostToolUse": [ {"matcher": "Bash|Skill|Edit|Write|MultiEdit", "hooks": [{"type":"command","command":"$CLAUDE_PROJECT_DIR/.claude/hooks/wikiskill-hook.sh PostToolUse"}]} ],
"SessionEnd": [ {"hooks": [{"type":"command","command":"$CLAUDE_PROJECT_DIR/.claude/hooks/wikiskill-hook.sh SessionEnd"}]} ]
```
  SessionStart と UserPromptSubmit は Task 4 で Bootstrap も同じラッパから呼ぶ(ラッパ内で `SessionStart` → logger と bootstrap の両方を順に実行し、JSON を1つに合成する)。この Task では logger 分だけ実装し、bootstrap 呼び出しの分岐は Task 4 で足す。

**Public/Private への影響:** `.gitignore` に `_local/`・`_audit.log`・`memory.off`・`locks/` を追加(原本 JSONL は除外しない)

- [ ] **Step 1: ラッパのテストを書く(subprocess で実行)**

```python
# tests/scripts/test_wikiskill_hook_sh.py  (fixture `repo` は Task 1 と同じ + scripts/ と .claude/hooks/ をコピー)
def run_hook(repo, event, payload, env=None): ...  # subprocess.run(["bash", ".claude/hooks/wikiskill-hook.sh", event], input=json.dumps(payload), ...)
def test_session_start_writes_record(repo):
    r = run_hook(repo, "SessionStart", {"session_id":"A","hook_event_name":"SessionStart","source":"startup","cwd":str(repo)})
    assert r.returncode == 0 and (repo/".claude/experience").glob("*/session-A.jsonl")
def test_hook_tolerates_missing_session_id(repo):
    r = run_hook(repo, "SessionStart", {"hook_event_name":"SessionStart"}); assert r.returncode == 0
    assert "unknown-" in next((repo/".claude/experience").glob("*/session-unknown-*.jsonl")).name
    assert "session_id" in (repo/".claude/experience/_audit.log").read_text()
def test_disabled_by_memory_off_file(repo):
    (repo/".claude/memory.off").touch(); r = run_hook(repo, "SessionStart", {...}); assert r.stdout.strip() == "{}" and not list((repo/".claude/experience").glob("*/*.jsonl"))
def test_post_tool_use_bash(repo):
    run_hook(repo, "PostToolUse", {"session_id":"A","tool_name":"Bash","tool_input":{"command":"python3 x.py --secret"}})
    text = read_session(repo, "A"); assert '"program": "python3"' in text and "--secret" not in text
def test_session_end_without_commits(repo):
    run_hook(repo, "SessionStart", {...A...}); r = run_hook(repo, "SessionEnd", {"session_id":"A","reason":"exit"})
    last = json.loads(read_session(repo,"A").splitlines()[-1]); assert last["event"]=="session_end" and last["commits"]==[]
    assert (repo/".claude/experience/_local/A.ended").exists()
def test_python_failure_is_reported_not_silent(repo, monkeypatch):
    (repo/"scripts/experience_log.py").write_text("raise SystemExit(3)")
    r = run_hook(repo, "SessionStart", {...}); assert r.returncode == 0 and "systemMessage" in r.stdout
def test_hook_runtime_under_500ms(repo):
    t=time.perf_counter(); run_hook(repo,"PostToolUse",{...Bash...}); assert time.perf_counter()-t < 0.5
```

- [ ] **Step 2: 失敗を確認する**

Run: `python3 -m pytest tests/scripts/test_wikiskill_hook_sh.py -q`
Expected: FAIL(`wikiskill-hook.sh: No such file`)

- [ ] **Step 3: `.claude/hooks/wikiskill-hook.sh` を実装する**

`set -uo pipefail`、`ROOT="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"`、停止判定 → `python3 "$ROOT/scripts/experience_log.py" hook "$1"`、失敗時の systemMessage 出力、`exit 0`。`chmod +x`。

- [ ] **Step 4: 合格を確認する**

Run: `python3 -m pytest tests/scripts/test_wikiskill_hook_sh.py -q`
Expected: 7 passed

- [ ] **Step 5: `.claude/settings.json` に hooks を追記し、JSON として妥当なことを確認する**

Run: `python3 -c "import json;d=json.load(open('.claude/settings.json'));print(sorted(d['hooks']))"`
Expected: `['PostToolUse', 'SessionEnd', 'SessionStart', 'UserPromptSubmit']`、かつ `git diff .claude/settings.json` で既存 superpowers 行の変更が無いこと

- [ ] **Step 6: `.gitignore` に追記する**

```
# WikiSkill Phase 1: 一時マーカー・監査ログ・停止スイッチ・ロック(原本 .claude/experience/*/*.jsonl はコミットする)
.claude/experience/_local/
.claude/experience/_audit.log
.claude/memory.off
.claude/locks/
```

Run: `touch .claude/memory.off && git check-ignore -q .claude/memory.off && echo ignored; rm .claude/memory.off`
Expected: `ignored`

- [ ] **Step 7: Commit**

```bash
git add .claude/hooks/wikiskill-hook.sh .claude/settings.json .gitignore tests/scripts/test_wikiskill_hook_sh.py
git commit -m "feat(wikiskill): hookラッパ1本でExperienceを記録。停止スイッチ .claude/memory.off と失敗時の警告を必須化"
```

**Acceptance Criteria(Task 2):** 7テスト合格 / 既存 superpowers hook の出力が Task 0 Step 4 と同一 / `.claude/memory.off` を置くと全記録が止まり、消すと再開する
**失敗時の Rollback:** 緊急: `.claude/memory.off` を置く(commit 不要)。正式: このコミットを revert(settings.json が元に戻る)

---

### Task 3: Decision Memory(議事の機械可読化)

**Files:**
- Create: `scripts/decision_memory.py`
- Create: `docs/wikiskill/議事frontmatterテンプレート.md`
- Test: `tests/scripts/test_decision_memory.py`

**Interfaces:**
- Produces:
  - `Decision = dict`(キー: `id` / `path`(リポ相対)/ `title` / `date`(`YYYY-MM-DD` or None)/ `review_by` / `review_status` ∈ {`active`,`expired`,`unknown`} / `status` ∈ {`adopted`,`rejected`,`deferred`,`superseded`,`unknown`} / `scope` / `tags: list[str]` / `why` / `premises` / `alternatives` / `utagai` / `bekkai` / `outcome` / `legacy: bool`(frontmatter 無し)/ `text_head`(検索用: title+tags+先頭600文字))
  - `DECISION_GLOBS = ["docs/議事_*.md", "docs/議事/*.md"]`(origin/main では 36 + 14 件)
  - `parse_frontmatter(text: str) -> tuple[dict, str]` — `---` で囲まれた YAML 風(key: value / tags: [a, b])のみ。PyYAML を使わない
  - `parse_decision(path: Path, root: Path) -> Decision` — frontmatter があれば優先、無ければ: ファイル名 `_YYYYMMDD_` または本文 `- 日付: YYYY-MM-DD` → date、`見直し期限[:：]?\s*\**(\d{4}-\d{2}-\d{2})` → review_by、`ウタガイ` を含む行 → utagai、`## 裁定|## 結論|## 決定` 節 → outcome、`## なぜ|## 背景|## 目的` 節 → why
  - `review_by` 未指定は `date + 180日`(Decision 2)。`review_status` は今日と比較
  - `load_decisions(root: Path) -> list[Decision]`
  - `check_decision(path: Path, root: Path) -> list[str]` — **frontmatter 付きファイルのみ**検査: `decision_id` `date` `title` `status` 必須 / `status` が許容値 / `review_by` が date より後 / 本文に `ウタガイ` 行があり「反対理由」が空でない(`ウタガイ.*[:：]\s*$` は違反)/ `## なぜ` か `## 背景` がある
  - CLI: `--check <path...>`(違反があれば exit 1)/ `--list [--json]`
- テンプレート(`docs/wikiskill/議事frontmatterテンプレート.md`)に固定する frontmatter:

```yaml
---
decision_id: D20261006-wikiskill-phase1   # D + 日付 + slug
date: 2026-10-06
title: WikiSkill Phase 1 導入
scope: hojo-hq/基盤                        # 事業/部門。自由記述
tags: [memory, hooks, skills]
status: adopted                            # adopted | rejected | deferred | superseded
review_by: 2027-04-04                      # 省略時は date+180日
supersedes:                                # 置き換える決定の decision_id(任意)
decided_by: 小柳
---
```
  本文の見出しは既存議事と同じ(`## なぜ(背景)` `## 前提` `## 代替案` `## 三名体制の議論`(スイシン/ウタガイ/ベッカイ)`## 裁定` `## 見直し条件`)。

**Public/Private への影響:** なし(hojo-hq の議事だけを読む)

- [ ] **Step 1: テストを書く**

```python
# tests/scripts/test_decision_memory.py
FM = "---\ndecision_id: D20261006-x\ndate: 2026-10-06\ntitle: テスト決定\nstatus: adopted\ntags: [a, b]\n---\n## なぜ\n理由A\n## 三名体制の議論\n- **ウタガイ**: コストが高い\n## 裁定\n採用\n"
def test_parse_frontmatter_tags_list(): fm, body = parse_frontmatter(FM); assert fm["tags"] == ["a","b"] and body.startswith("## なぜ")
def test_review_by_defaults_to_180_days(tmp_docs):  d = parse_decision(write(tmp_docs, "docs/議事_20261006_x.md", FM), tmp_docs); assert d["review_by"] == "2027-04-04"
def test_legacy_file_date_from_filename(tmp_docs):
    d = parse_decision(write(tmp_docs, "docs/議事_20260810_北極星.md", "# 議事: 北極星\n見直し期限: **2026-09-07**\n- **ウタガイ(反対理由)**: n=11では検証不能\n## 裁定\nSEO先行\n"), tmp_docs)
    assert d["legacy"] and d["date"]=="2026-08-10" and d["review_by"]=="2026-09-07" and d["review_status"]=="expired" and "n=11" in d["utagai"] and "SEO" in d["outcome"]
def test_legacy_date_from_body(tmp_docs):  # 議事_総額ポテンシャル表示.md 型
    d = parse_decision(write(tmp_docs, "docs/議事_総額.md", "# 議事: 総額\n- 日付: 2026-07-26 / 起案: x\n"), tmp_docs); assert d["date"]=="2026-07-26"
def test_load_scans_both_globs(tmp_docs): write(...,"docs/議事_20260101_a.md",...); write(...,"docs/議事/議事_20260102_b.md",...); assert len(load_decisions(tmp_docs))==2
def test_check_rejects_empty_utagai(tmp_docs):
    errs = check_decision(write(tmp_docs,"docs/議事_20261006_y.md", FM.replace("コストが高い","")), tmp_docs); assert any("ウタガイ" in e for e in errs)
def test_check_rejects_missing_status(tmp_docs): errs = check_decision(write(..., FM.replace("status: adopted\n","")), tmp_docs); assert any("status" in e for e in errs)
def test_check_ignores_legacy(tmp_docs): assert check_decision(write(...,"docs/議事_20260810_old.md","# old\n"), tmp_docs) == []
def test_cli_check_exit_code(tmp_docs): assert run(["--check", bad]).returncode == 1 and run(["--check", good]).returncode == 0
```

- [ ] **Step 2: 失敗を確認する**

Run: `python3 -m pytest tests/scripts/test_decision_memory.py -q`
Expected: FAIL(import error)

- [ ] **Step 3: `scripts/decision_memory.py` を実装する**

- [ ] **Step 4: 合格を確認し、実データ(origin/main の議事 50 件)で落ちないことを確認する**

Run: `python3 -m pytest tests/scripts/test_decision_memory.py -q && python3 scripts/decision_memory.py --list | wc -l && python3 scripts/decision_memory.py --list --json | python3 -c "import json,sys;d=json.load(sys.stdin);print(sum(1 for x in d if x['date']), 'dated /', len(d))"`
Expected: 9 passed / 50 前後 / `dated` が総数の 8 割以上(残りは `date: None` でも例外にならない)

- [ ] **Step 5: テンプレート文書を書く**

`docs/wikiskill/議事frontmatterテンプレート.md`: 上記 frontmatter と各項目の意味、「過去の議事には付け直さない(遡及しない)」「ウタガイ空欄は `--check` で止まる」を明記。

- [ ] **Step 6: Commit**

```bash
git add scripts/decision_memory.py tests/scripts/test_decision_memory.py docs/wikiskill/議事frontmatterテンプレート.md
git commit -m "feat(wikiskill): Decision Memory — 既存議事をfrontmatterで機械可読化(見直し期限は未指定なら180日)"
```

**Acceptance Criteria(Task 3):** 9テスト合格 / 実在する議事 50 件を例外なく読める / frontmatter 付き新規議事でウタガイ空欄なら `--check` が exit 1
**失敗時の Rollback:** revert のみ(読み取り専用スクリプト。本番影響なし)

---

### Task 4: Memory Bootstrap(関連情報だけを取り出す)

**Files:**
- Create: `scripts/memory_bootstrap.py`
- Modify: `.claude/hooks/wikiskill-hook.sh`(SessionStart / UserPromptSubmit で bootstrap も呼び、JSON を合成)
- Test: `tests/scripts/test_memory_bootstrap.py`

**Interfaces:**
- Consumes: `decision_memory.load_decisions()`(Task 3)、`wikiskill_common.*`(Task 1)
- Produces:
  - `build_query(root: Path, prompt: str | None = None) -> list[str]` — ブランチ名を `-_/` で分割した語 + 直近10 commit の件名 + `git diff --name-only origin/main...HEAD` の basename + prompt(あれば)。`claude`/`main`/`origin`/`feat`/`fix`/`docs` 等の定型語は除外
  - `bigrams(text: str) -> set[str]` — 空白・記号を除いた文字 bigram。ひらがな助詞だけの bigram(`の`,`は`,`を`,`に`,`が`,`と`,`で`,`て` を含む2文字)は除外
  - `score(query_terms: list[str], text: str) -> int` — query の bigram 集合と text の bigram 集合の共通数
  - `Source = dict`(`kind` ∈ {`decision`,`queue`,`failure`,`prevention`,`skill`,`experience`} / `label` / `title` / `body` / `path` / `score`)
  - `collect_sources(root: Path) -> list[Source]`:
    - `decision`: Task 3 の全 Decision(`text_head` を検索対象)
    - `queue`: `docs/決裁キュー.md` の未完了行(`~~` 取り消し線と `✅` を含まない番号付き行)
    - `failure`: `docs/失敗台帳.md` の表の行(`| FK-` で始まる)。title=`FK-xxx 発生日 分類`、body=事実経過の先頭200文字 + `対策:` 列
    - `prevention`: `CLAUDE.md` の `## 再発防止メモ` 節の箇条書き各行
    - `skill`: `.claude/skills/*/SKILL.md` の frontmatter `name` / `description`(`.gitignore` 対象のスキルも読んでよい: ローカルにあるものは現在有効)
    - `experience`: `.claude/experience/*/session-*.jsonl` の `session_end` 行のうち同じ `branch` のもの、新しい順に最大3件(スコア無関係・常に末尾・`[Exp]` ラベル)
  - `retrieve(root: Path, terms: list[str], budget_chars: int = 6000, per_kind: int = 5, min_score: int = 3) -> str` — 区分ごとにスコア降順で `per_kind` 件、`min_score` 未満は落とす。合計 `budget_chars` を超えたら各区分の末尾から削る。区分が空なら `- 該当なし`
  - 出力の固定形:

```
# 🧠 Memory Bootstrap(段1: ブランチ・直近commitから)
検索語: superpowers, per, chat, Phase 2 Week 3, ...
## 関連する決定 [D]（高信頼・議事）
- [D] 2026-08-10 北極星4本の現在地と最初に潰すボトルネック — 裁定: SEOオンページ一括+… / なぜ: 律速段階は流入 / ウタガイ: n=11では効果検証不可 / 見直し: 2026-09-07 **(期限切れ・再議論対象)** → docs/議事_20260810_北極星ボトルネック裁定.md
## 未解決（決裁キュー）
## 過去の失敗 [FK]（失敗台帳）
- [FK-002] 2026-07-23 ヒヤリハット+プロセス — マージで競合一覧を確認せず… / 対策: 競合一覧→マーカー検査→全検査→コミット
## 再発防止メモ [再発防止]（CLAUDE.md）
## 現在有効な関連Skill [Skill]
- writing-plans-hojo — …description…
## 直近のExperience [Exp]（低信頼・参考。commitされたものだけ見える）
- 2026-10-05 session-abc: commits 3 / skills: writing-plans, systematic-debugging
```
  - CLI: `python3 scripts/memory_bootstrap.py hook SessionStart`(段1。`additionalContext` に出力)/ `hook UserPromptSubmit`(段2。`_local/<session_id>.bootstrapped` が無いときだけ `prompt` を加えた検索で差分を出し、マーカーを置く。あれば `{}`)/ `query "<語>"`(手動確認用)
  - 段2の出力見出しは `# 🧠 Memory Bootstrap(段2: 最初の指示から)` とし、段1で出した項目(path/id が同じ)は再掲しない

**Public/Private への影響:** `root` 配下しか読まない。`experience` 区分は `visibility == "public"` の行だけ表示(private 行が混入していれば表示せず audit に記録)

- [ ] **Step 1: テストを書く**

```python
# tests/scripts/test_memory_bootstrap.py  (fixture `kb` = tmp git repo + docs/議事_20260810_北極星ボトルネック裁定.md(本物をコピー) + docs/失敗台帳.md(FK-002 行) + docs/決裁キュー.md(未完了1行・完了1行) + CLAUDE.md(再発防止 2 行) + .claude/skills/writing-plans-hojo/SKILL.md)
def test_build_query_from_branch_and_commits(kb):  # branch=claude/lighthouse-css, commit "fix: word-break を見出し限定に"
    t = build_query(kb); assert "lighthouse" in t and any("word-break" in x for x in t) and "claude" not in t
def test_bigrams_drop_particle_only(): assert "のは" not in bigrams("のは") and "北極" in bigrams("北極星")
def test_decision_retrieved_with_why_and_utagai(kb):
    out = retrieve(kb, ["北極星", "ボトルネック", "SEO"]); assert "[D] 2026-08-10" in out and "なぜ:" in out and "ウタガイ:" in out
def test_expired_decision_is_labeled_not_hidden(kb):
    out = retrieve(kb, ["北極星"]); assert "期限切れ・再議論対象" in out
def test_failure_ledger_row_retrieved(kb): out = retrieve(kb, ["マージ", "競合"]); assert "[FK-002]" in out and "対策:" in out
def test_prevention_memo_retrieved(kb): out = retrieve(kb, ["議事", "docs"]); assert "[再発防止]" in out
def test_skill_retrieved_by_description(kb): out = retrieve(kb, ["実装計画"]); assert "writing-plans-hojo" in out
def test_queue_only_open_items(kb): out = retrieve(kb, ["Bing"]); assert "Bing Webmaster" in out and "moradou.jp採用" not in out
def test_empty_kind_says_none(kb): out = retrieve(kb, ["zzzz"]); assert out.count("該当なし") >= 4
def test_budget_respected(kb): assert len(retrieve(kb, ["北極星","マージ","議事","実装計画"], budget_chars=1500)) <= 1500
def test_experience_private_rows_not_shown(kb):  # session_end 行に visibility=private を1行仕込む
    out = retrieve(kb, []); assert "private-session" not in out and "private" in (kb/".claude/experience/_audit.log").read_text()
def test_prompt_stage_runs_once_per_session(kb):
    o1 = run_hook(kb, "UserPromptSubmit", {"session_id":"B","prompt":"失敗台帳のマージ競合を直したい"}); assert "[FK-002]" in o1.stdout
    o2 = run_hook(kb, "UserPromptSubmit", {"session_id":"B","prompt":"次は別の話"}); assert o2.stdout.strip() == "{}"
def test_stage2_does_not_repeat_stage1_items(kb): ...  # 段1で出た [D] の path が段2に無い
def test_session_start_hook_merges_logger_and_bootstrap(kb):
    r = run_hook(kb, "SessionStart", {"session_id":"B","source":"startup"}); out=json.loads(r.stdout)
    assert out["hookSpecificOutput"]["additionalContext"].startswith("# 🧠 Memory Bootstrap") and list((kb/".claude/experience").glob("*/session-B.jsonl"))
def test_bootstrap_never_reads_outside_root(kb):  # 境界: 隣のディレクトリ(別リポ想定)に議事を置いても拾わない
    sib = kb.parent/"glow-docs-private"; (sib/"docs").mkdir(parents=True); (sib/"docs/議事_20261001_極秘決定.md").write_text("# 議事: 極秘決定\n極秘キーワード\n")
    assert "極秘" not in retrieve(kb, ["極秘", "決定"])
def test_decision_loader_ignores_experience_dir(kb):  # 分離: Experience 配下に議事風ファイルがあっても Decision として読まない
    (kb/".claude/experience/2026-10").mkdir(parents=True); (kb/".claude/experience/2026-10/議事_20261001_偽.md").write_text("# 偽\n")
    assert all(".claude/experience" not in d["path"] for d in load_decisions(kb))
def test_bootstrap_runtime_under_500ms_on_real_repo():  # 本リポジトリ(docs 約300件)で計測
    t=time.perf_counter(); subprocess.run([... "query", "スキル改善"], cwd=REPO_ROOT, check=True); assert time.perf_counter()-t < 0.5
```

- [ ] **Step 2: 失敗を確認する**

Run: `python3 -m pytest tests/scripts/test_memory_bootstrap.py -q`
Expected: FAIL(import error)

- [ ] **Step 3: `scripts/memory_bootstrap.py` を実装する**

`collect_sources` は各区分を独立した関数にし、1区分の読み込み失敗(ファイル無し・壊れた表)は audit して空扱い(他区分は出す)。

- [ ] **Step 4: `wikiskill-hook.sh` を更新する**

`SessionStart`: logger → bootstrap の順に実行し、logger の `systemMessage` と bootstrap の `additionalContext` を1つの JSON に合成(`python3 -c` の小さな合成か、bootstrap 側に `--merge-system-message` を持たせる。どちらでも可、1箇所に決める)。`UserPromptSubmit`: bootstrap のみ(logger は何もしない)。

- [ ] **Step 5: 合格を確認する**

Run: `python3 -m pytest tests/scripts/test_memory_bootstrap.py tests/scripts/test_wikiskill_hook_sh.py -q`
Expected: 17 + 7 passed

- [ ] **Step 6: 本リポジトリで実際の出力を目視する**

Run: `python3 scripts/memory_bootstrap.py query "スキル改善 13リポ 配布" | head -40`
Expected: `[D]` に `スキル改善` 関連の議事、`[再発防止]` に「13リポへ広げるときは update-skills.sh に…」の行、`[Skill]` に `hojo-triangle-review` 等が出る。6,000 文字以内

- [ ] **Step 7: Commit**

```bash
git add scripts/memory_bootstrap.py .claude/hooks/wikiskill-hook.sh tests/scripts/test_memory_bootstrap.py
git commit -m "feat(wikiskill): Memory Bootstrap — 新セッションに関連するDecision・失敗・再発防止・Skillだけを2段で注入"
```

**Acceptance Criteria(Task 4):** 17テスト合格 / 本リポジトリで 500ms 以内 / 出力は信頼階層順・出典ラベル付き・6,000 文字以内 / 2回目以降の UserPromptSubmit で何も注入しない
**失敗時の Rollback:** 緊急: `.claude/memory.off`。正式: revert。Bootstrap だけ止めたい場合は settings.json の該当 matcher 行を削る(Experience は残る)

---

### Task 5: Privacy Boundary(CI 検査)

**Files:**
- Create: `scripts/check_experience_privacy.py`
- Modify: `.github/workflows/repo-scope.yml`(ステップ2つ追加)
- Test: `tests/scripts/test_check_experience_privacy.py`

**Interfaces:**
- Consumes: `check_repo_scope.FORBIDDEN_CONTENT` / `find_content_violations`(既存をそのまま import。禁止語リストを二重管理しない)
- Produces:
  - `PUBLIC_REPO = "allgroup-inc/hojo-hq"`、`MAX_FIELD = 500`、`MAX_NOTE = 1000`
  - `check_record(rec: dict, path: str) -> list[str]` — 違反メッセージ: `visibility != public` / `repo != PUBLIC_REPO` / `path` 系の値が `/` 始まり or `..` を含む / `note` 以外の文字列値が 500 文字超 / `note` が 1,000 文字超 / `find_content_violations(path, json.dumps(rec, ensure_ascii=False))` が非 None / 行が JSON でない
  - `scan(root: Path) -> list[tuple[str, str]]` — `git ls-files -z -- .claude/experience` の全行を検査
  - CLI: 引数なしで走査(違反があれば exit 1・HINT 表示)/ `--selftest`(正例・負例を内蔵。CLAUDE.md 再発防止メモ「検査を足したら正例で試す」に従う)
- repo-scope.yml 追加ステップ:

```yaml
      - name: Experience記録の公開可否 自己点検
        run: python3 scripts/check_experience_privacy.py --selftest
      - name: Experience記録の公開可否
        run: python3 scripts/check_experience_privacy.py
```

**Public/Private への影響:** これが境界の機械検査そのもの。違反1件でマージ不可

- [ ] **Step 1: テストを書く**

```python
# tests/scripts/test_check_experience_privacy.py
OK = {"ts":"2026-10-06T00:00:00Z","session_id":"A","event":"tool","repo":"allgroup-inc/hojo-hq","visibility":"public","branch":"main","tool":"Edit","path":"docs/a.md"}
def test_ok_record(): assert check_record(OK, "x.jsonl") == []
def test_private_visibility_rejected(): assert check_record({**OK,"visibility":"private"}, "x") 
def test_other_repo_rejected(): assert check_record({**OK,"repo":"allgroup-inc/glow-docs-private"}, "x")
def test_absolute_path_rejected(): assert check_record({**OK,"path":"/home/user/x"}, "x")
def test_external_placeholder_ok(): assert check_record({**OK,"path":"<external>"}, "x") == []
def test_long_field_rejected(): assert check_record({**OK,"path":"a"*501}, "x")
def test_note_up_to_1000_ok(): assert check_record({**OK,"event":"note","text":"あ"*1000}, "x") == []
def test_forbidden_content_rejected():  # 禁止語の実文字列を本計画に書かない(本計画自体が check_repo_scope の検査対象)
    word = check_repo_scope.FORBIDDEN_CONTENT[0]; assert check_record({**OK,"event":"note","text":f"環境変数 {word} を"}, "x")
def test_selftest_passes(): assert run(["--selftest"]).returncode == 0
def test_scan_reports_file_and_reason(repo_with_bad_jsonl): hits = scan(repo_with_bad_jsonl); assert hits and hits[0][0].endswith(".jsonl")
```

- [ ] **Step 2: 失敗を確認する**

Run: `python3 -m pytest tests/scripts/test_check_experience_privacy.py -q`
Expected: FAIL(import error)

- [ ] **Step 3: `scripts/check_experience_privacy.py` を実装する**

- [ ] **Step 4: 合格と、現時点(Experience 0件)で CI 相当が通ることを確認する**

Run: `python3 -m pytest tests/scripts/test_check_experience_privacy.py -q && python3 scripts/check_experience_privacy.py --selftest && python3 scripts/check_experience_privacy.py`
Expected: 10 passed / `自己点検OK` / `OK: Experience記録 0件・違反なし`

- [ ] **Step 5: `repo-scope.yml` にステップを追加し、YAML が壊れていないことを確認する**

Run: `python3 -c "import yaml" 2>/dev/null && python3 -c "import yaml,sys;yaml.safe_load(open('.github/workflows/repo-scope.yml'))" || grep -c "check_experience_privacy" .github/workflows/repo-scope.yml`
Expected: 例外なし(yaml 無しの環境では `2`)

- [ ] **Step 6: Commit**

```bash
git add scripts/check_experience_privacy.py tests/scripts/test_check_experience_privacy.py .github/workflows/repo-scope.yml
git commit -m "feat(wikiskill): Experience記録の公開可否をCIで検査(private・他リポ・絶対パス・禁止語を止める)"
```

**Acceptance Criteria(Task 5):** 10テスト合格 / `--selftest` に正例・負例の両方が含まれる / CI の repo-scope ジョブに2ステップが見える
**失敗時の Rollback:** revert。検査が偽陽性を出す場合は `check_record` を直す(緩めるときは議事)

---

### Task 6: Rollback 基盤(緊急停止・サイズ監視・Archive・手順書)

**Files:**
- Create: `scripts/experience_archive.py`
- Create: `docs/wikiskill/Rollback手順.md`
- Test: `tests/scripts/test_experience_archive.py`

**Interfaces:**
- Produces:
  - `total_size(root: Path) -> int` — `.claude/experience/**/*.jsonl` と `archive/*.jsonl.gz` の合計バイト
  - `check_size(root: Path, warn_mb: float = 3.0, fail_mb: float = 10.0) -> int` — exit code: 0 / 1(warn)/ 2(fail)。Phase 1 の CI では warn までで止めない(fail は表示のみ)
  - `archivable_months(root: Path, today: date, older_than_days: int = 180) -> list[Path]` — 月フォルダ `YYYY-MM` の翌月1日から 180 日以上経過したもの
  - `archive(root: Path, today: date, older_than_days: int = 180) -> list[Path]` — 各月を `archive/YYYY-MM.jsonl.gz`(全セッション連結・gzip)に固め、元フォルダを削除。**原本は gzip 内に全文保持**(Decision 4「原本を保持」)。実行は Git 管理下で行い、結果は commit する(手動 or 月次 Routine。Phase 1 は手動)
  - CLI: `--check` / `--archive [--dry-run]`
- `docs/wikiskill/Rollback手順.md` の内容(固定):
  1. **緊急停止(守り部・単独可・数秒)**: `touch .claude/memory.off`(クラウドセッションなら各セッションで。恒久化するなら `HOJO_MEMORY_OFF=1` を環境に)→ 全 hook が無効。既存 superpowers hook は影響なし
  2. **正式 Rollback(Git)**: `git revert -m 1 <wikiskill-phase1-v1 のマージコミット>` → settings.json / hooks / scripts / docs / CI ステップが一括で戻る。Experience の JSONL は履歴に残る(消す判断は別途議事)
  3. **記録**: 48時間以内に `docs/議事_YYYYMMDD_WikiSkill緊急停止.md`(frontmatter 付き)を作り、小柳 Decision Gate で正式判断(Decision 7)。失敗台帳にも1行
  4. **部分停止**: Bootstrap だけ止める = settings.json の UserPromptSubmit と SessionStart 2本目を削除。Experience だけ止める = PostToolUse / SessionEnd を削除

**Public/Private への影響:** なし

- [ ] **Step 1: テストを書く**

```python
# tests/scripts/test_experience_archive.py
def test_check_size_levels(repo): write_jsonl(repo, "2026-10", 4*MB); assert check_size(repo)==1; write_jsonl(repo,"2026-11",7*MB); assert check_size(repo)==2
def test_archivable_months_boundary(repo):
    mk(repo,"2026-03"); mk(repo,"2026-05"); assert [p.name for p in archivable_months(repo, date(2026,10,6))] == ["2026-03"]  # 2026-04-01+180日=2026-09-28 < 10-06, 2026-06-01+180=11-28 > 10-06
def test_archive_roundtrip_keeps_every_line(repo):
    lines = write_many(repo, "2026-03"); archive(repo, date(2026,10,6)); gz = repo/".claude/experience/archive/2026-03.jsonl.gz"
    assert gz.exists() and gzip.open(gz,"rt").read().splitlines() == lines and not (repo/".claude/experience/2026-03").exists()
def test_archive_dry_run_changes_nothing(repo): ...
def test_archived_size_counts_toward_total(repo): ...
```

- [ ] **Step 2: 失敗を確認する**

Run: `python3 -m pytest tests/scripts/test_experience_archive.py -q`
Expected: FAIL(import error)

- [ ] **Step 3: `scripts/experience_archive.py` を実装する**

- [ ] **Step 4: 合格を確認する**

Run: `python3 -m pytest tests/scripts/test_experience_archive.py -q && python3 scripts/experience_archive.py --check`
Expected: 5 passed / `Experience合計 0.0MB(警告 3MB / 上限 10MB)`

- [ ] **Step 5: `docs/wikiskill/Rollback手順.md` を書く(上記 1〜4 を手順化。コマンドは実行可能な形で)**

- [ ] **Step 6: Commit**

```bash
git add scripts/experience_archive.py tests/scripts/test_experience_archive.py docs/wikiskill/Rollback手順.md
git commit -m "feat(wikiskill): Rollback基盤 — 緊急停止手順・Experienceサイズ監視・180日超の月次gzip化"
```

**Acceptance Criteria(Task 6):** 5テスト合格 / 手順書のコマンドを順に実行すると Task 2〜5 の変更が消え、Task 0 Step 4 の出力に戻る(Task 9 で実演)
**失敗時の Rollback:** revert

---

### Task 7: 文書・CLAUDE.md・導入議事

**Files:**
- Create: `docs/wikiskill/README.md`
- Create: `docs/議事_20261006_WikiSkill_Phase1導入.md`
- Create: `docs/wikiskill/Phase1受け入れ記録.md`(空の台帳。Task 8 で記入)
- Modify: `CLAUDE.md`(「技術構成」の下に節を1つ、「再発防止メモ」に1行)
- Modify: `docs/全体マップ.md`(1行)

**Interfaces:**
- Consumes: Task 3 のテンプレート(議事は frontmatter 付きで書き、`decision_memory.py --check` に通す)
- Produces: Bootstrap の最初の実データとしての議事(`decision_id: D20261006-wikiskill-phase1`、`tags: [memory, hooks, wikiskill, skills]`、`review_by: 2027-04-04`)

**Public/Private への影響:** なし(文書のみ。顧客情報・private リポの内容を書かない)

- [ ] **Step 1: 導入議事を書く(三名体制・ウタガイ反対理由必須)**

含める内容: `## なぜ`(セッション終了で知識が散逸・Skill 実績未測定)/ `## 前提`(GitHub 正本・public/private 分離・110 Skills 不変・13リポ配布不変)/ `## 代替案`(Obsidian 側に書く案 → 鏡に書いても元に映らないので却下。全 Wiki 投入案 → トークン浪費で却下)/ `## 三名体制の議論` — スイシン: 既存資産の再利用で新設最小 / **ウタガイ(反対理由)**: ①hook 4本追加は全セッションの固定費。500ms 上限を守れる保証が無い ②Experience を公開リポに置くこと自体が情報漏えいの面を増やす(記録範囲を縛っても note は自由記述) ③「関連度」の bigram 一致は粗く、誤った Decision を関連として出すと前提を誤らせる → 受け入れ条件: 時間上限をテストで固定・note は CI 検査対象・出力に出典と見直し期限を必ず付ける / ベッカイ: そもそも Decision は議事に既にある。足りないのは「取り出し」であり記録ではないのでは → Bootstrap を Phase 1 の中心に置く(MVP 比較で候補3を採る根拠) / `## 裁定`: 2026-10-06 小柳さん承認(修正4点・Decision 8件は設計書 v1.1 冒頭)/ `## 見直し条件`: hook 時間 500ms 超が週3回・privacy 検査の違反1件・Bootstrap の誤関連が利用者申告で3件 → 再議論 / `## Rollback`: `docs/wikiskill/Rollback手順.md`

Run: `python3 scripts/decision_memory.py --check docs/議事_20261006_WikiSkill_Phase1導入.md`
Expected: exit 0

- [ ] **Step 2: README を書く**

`docs/wikiskill/README.md`: 何が記録されるか(と記録されないもの)/ どう復元されるか(段1・段2・信頼階層・6,000 文字上限)/ 止め方(`.claude/memory.off`)/ 新しい議事の書き方(テンプレート参照)/ `note` の残し方(`python3 scripts/experience_log.py note "..."`。利用者が「記録して」と言ったら Claude が実行)/ **commit されない Experience は他セッションから見えない**(Review Focus 2)/ Phase 2 以降の予定(Wiki・Validator・Lock)は未実装であること

- [ ] **Step 3: CLAUDE.md に節を足す(10行以内)**

「## 記憶の仕組み(WikiSkill Phase 1・2026-10-06 導入)」: 正本は GitHub / Decision=議事(frontmatter 付き、見直し期限は未指定なら180日)/ Experience=`.claude/experience/`(機械記録・低信頼・公開可能な範囲のみ)/ 新セッションは Bootstrap が関連する Decision・失敗台帳・再発防止・Skill だけを注入 / 止め方 / Skill の自動更新はしない(Proposal→Evaluation→三名体制→小柳 Gate→Merge は Phase 2 以降)/ 詳細 `docs/wikiskill/README.md`

再発防止メモに1行: 「**`.claude/commands/` に repo 固有のコマンドを足さない**(13リポへ丸ごと同期される。WikiSkill の note 追記をコマンド化しかけて 2026-10-06 の設計で検知)」

- [ ] **Step 4: 全体マップに1行、受け入れ記録の空台帳を作る**

- [ ] **Step 5: 文書内の `docs/*.md` 参照が実在することを機械検査する(CLAUDE.md 再発防止メモの手順)**

Run: `for f in docs/wikiskill/README.md docs/議事_20261006_WikiSkill_Phase1導入.md; do python3 -c "import re,sys,os;[print(('OK ' if os.path.exists(p) else 'NG ')+p) for p in sorted(set(re.findall(r'docs/\S+?\.md',open(sys.argv[1],encoding='utf-8').read())))]" "$f"; done | grep -c NG`
Expected: `0`

- [ ] **Step 6: Commit**

```bash
git add docs/wikiskill/README.md docs/議事_20261006_WikiSkill_Phase1導入.md docs/wikiskill/Phase1受け入れ記録.md CLAUDE.md docs/全体マップ.md
git commit -m "docs(wikiskill): Phase 1 導入議事(三名体制)・運用ガイド・CLAUDE.md 記憶の仕組み節"
```

**Acceptance Criteria(Task 7):** 導入議事が `--check` 合格 / 参照パス NG 0 / `python3 scripts/memory_bootstrap.py query "WikiSkill 記憶"` の `[D]` 先頭にこの議事が出る
**失敗時の Rollback:** revert

---

### Task 8: E2E テスト(自動 + 実セッション手動)

**Files:**
- Create: `tests/integration/test_wikiskill_memory_e2e.py`
- Modify: `docs/wikiskill/Phase1受け入れ記録.md`(手動結果を記入)

**Interfaces:**
- Consumes: Task 1〜7 の全部。hook は `wikiskill-hook.sh` 経由(subprocess)で呼び、Claude Code と同じ stdin JSON を渡す

**Public/Private への影響:** 手動 E2E は hojo-hq のみで行う(private リポでは行わない)

- [ ] **Step 1: 自動 E2E を書く**

```python
# tests/integration/test_wikiskill_memory_e2e.py
# fixture `world`: tmp git repo(origin=hojo-hq)+ scripts/ + .claude/hooks/ + .claude/settings.json + CLAUDE.md(再発防止2行)+ docs/失敗台帳.md(FK-002)+ docs/決裁キュー.md + .claude/skills/writing-plans-hojo/SKILL.md、ブランチ claude/e2e-memory
def test_session_a_then_fresh_session_b_restores_decision_and_why(world):
    # ---- Session A ----
    hook(world, "SessionStart", sid="A", source="startup")
    write(world, "docs/議事_20261006_E2Eテスト決定.md", FM_DECISION)   # なぜ: 「締切7日前では準備が間に合わない」/ ウタガイ: 「30日前は早すぎて忘れられる」/ 裁定: 「約1か月前で統一」
    hook(world, "PostToolUse", sid="A", tool_name="Write", tool_input={"file_path": str(world/"docs/議事_20261006_E2Eテスト決定.md")})
    git(world, "add", "-A"); git(world, "commit", "-m", "docs: 締切アラート時期の決定")
    hook(world, "PostToolUse", sid="A", tool_name="Bash", tool_input={"command": "git commit -m x"})
    hook(world, "PostToolUse", sid="A", tool_name="Skill", tool_input={"skill": "writing-plans-hojo"})
    hook(world, "SessionEnd", sid="A", reason="exit")
    git(world, "add", ".claude/experience"); git(world, "commit", "-m", "chore: experience")   # クラウドでは push まで必要
    a = read_session(world, "A"); assert '"event": "session_end"' in a and "締切アラート時期の決定" in a
    # ---- Session B(完全に別の session_id・マーカー無し)----
    r1 = hook(world, "SessionStart", sid="B", source="startup"); ctx = json.loads(r1.stdout)["hookSpecificOutput"]["additionalContext"]
    assert "[D] 2026-10-06 E2Eテスト決定" in ctx                      # Decision が復元される
    assert "なぜ: 締切7日前では準備が間に合わない" in ctx                # 「なぜ」が復元される
    assert "ウタガイ: 30日前は早すぎて忘れられる" in ctx                # 反対理由が復元される
    assert "見直し: 2027-04-04" in ctx                                   # 180日既定
    assert "[Exp]" in ctx and "session-A" in ctx and "writing-plans-hojo" in ctx   # 低信頼ラベル付きで A の Experience
    r2 = hook(world, "UserPromptSubmit", sid="B", prompt="マージで競合したときの手順を確認したい")
    ctx2 = json.loads(r2.stdout)["hookSpecificOutput"]["additionalContext"]
    assert "[FK-002]" in ctx2 and "[再発防止]" in ctx2                 # 失敗・再発防止が必要に応じて復元される
    assert "E2Eテスト決定" not in ctx2                                   # 段1の項目を再掲しない
    r3 = hook(world, "UserPromptSubmit", sid="B", prompt="次"); assert r3.stdout.strip() == "{}"
def test_memory_off_disables_everything_without_breaking_session(world):
    (world/".claude/memory.off").touch(); r = hook(world, "SessionStart", sid="C", source="startup")
    assert r.returncode == 0 and r.stdout.strip() == "{}" and not list((world/".claude/experience").glob("*/session-C.jsonl"))
def test_private_repo_session_never_marks_public(world_private):   # origin=glow-docs-private
    hook(world_private, "SessionStart", sid="P", source="startup"); assert '"visibility": "private"' in read_session(world_private, "P")
def test_privacy_check_passes_on_e2e_output(world):  # Session A の記録が CI 検査を通る
    assert subprocess.run(["python3","scripts/check_experience_privacy.py"], cwd=world).returncode == 0
```

- [ ] **Step 2: 失敗(または未実装部分)を確認して、合格させる**

Run: `python3 -m pytest tests/integration/test_wikiskill_memory_e2e.py -q`
Expected: 4 passed(落ちた場合は該当 Task のスクリプトを直し、その Task のテストも再実行)

- [ ] **Step 3: 全テストと既存検査をまとめて実行する**

Run: `python3 -m pytest tests/scripts/test_wikiskill_common.py tests/scripts/test_experience_log.py tests/scripts/test_wikiskill_hook_sh.py tests/scripts/test_decision_memory.py tests/scripts/test_memory_bootstrap.py tests/scripts/test_check_experience_privacy.py tests/scripts/test_experience_archive.py tests/integration/test_wikiskill_memory_e2e.py -q && python3 scripts/check_repo_scope.py && python3 scripts/check_experience_privacy.py && python3 -m pytest tests/skill_validation -q | tail -1`
Expected: 69 passed / OK / OK / skill_validation passed(既存テストに回帰なし)

- [ ] **Step 4: Commit し、push する**

```bash
git add tests/integration/test_wikiskill_memory_e2e.py
git commit -m "test(wikiskill): E2E — Session A の Decision・なぜ・反対理由・失敗台帳を別セッション B が復元する"
git push -u origin claude/superpowers-per-chat-3mbx56
```

- [ ] **Step 5: 実セッションでの手動 E2E(必須・小柳さん指示)**

手順(`docs/wikiskill/Phase1受け入れ記録.md` に結果を記入):
1. **Session A**(このブランチで新規セッション): 開始直後に `# 🧠 Memory Bootstrap` が注入されていることを確認(段1)。frontmatter 付きの小さな議事(例: `docs/議事_20261007_受け入れ試験.md`、なぜ・ウタガイ・裁定を各1行)を作り commit → `python3 scripts/experience_log.py note "受け入れ試験 A 完了"` → commit → **push** → セッション終了
2. **Session B**(完全に新しいセッション・同じブランチ): 開始直後の Bootstrap に `[D] 2026-10-07 受け入れ試験` と「なぜ:」「ウタガイ:」が出ること。最初の指示で「マージ競合の手順」と書き、段2に `[FK-002]` と `[再発防止]` が出ること。2回目の指示で何も注入されないこと
3. `time` 相当: Session B の開始が体感で遅くならないこと(`.claude/experience/_audit.log` に `slow` 警告が無い)
4. `.claude/memory.off` を置いて Session C を開始し、Bootstrap も記録も止まること。消して再開すること
5. 記入項目: 実施日時 / session_id(A, B, C)/ 各確認の ✅❌ / Bootstrap の実出力(先頭20行を貼る)/ 所見

- [ ] **Step 6: 受け入れ記録を commit する**

```bash
git add docs/wikiskill/Phase1受け入れ記録.md docs/議事_20261007_受け入れ試験.md .claude/experience
git commit -m "docs(wikiskill): Phase 1 受け入れ記録 — 実セッション A→B で Decision と理由の復元を確認"
git push
```

**Acceptance Criteria(Task 8):** 自動 E2E 4本合格 / 手動 E2E 5項目すべて ✅ / 既存テスト・既存 CI に回帰なし
**失敗時の Rollback:** 手動 E2E で ❌ が出たら PR をマージせず、該当 Task に戻る。本番(main)は未変更のまま

---

### Task 9: PR・Rollback 実演・タグ

**Files:** 変更なし(Git / GitHub 操作)

**Public/Private への影響:** PR 本文に private リポの内容・顧客情報を書かない

- [ ] **Step 1: Rollback 手順書どおりに戻せることを、作業ブランチ上で実演する**

Run: `git stash -u -q 2>/dev/null; touch .claude/memory.off && echo '{"session_id":"rb","hook_event_name":"SessionStart","source":"startup"}' | bash .claude/hooks/wikiskill-hook.sh SessionStart; rm .claude/memory.off`
Expected: `{}`(緊急停止が効く)。続けて `git revert --no-commit <Task2のコミット>..HEAD` を**別の使い捨てブランチ**で行い、`.claude/settings.json` が origin/main と一致することを `git diff origin/main -- .claude/settings.json` で確認(空)。確認後その使い捨てブランチは削除

- [ ] **Step 2: PR を作る(小柳さんの Decision Gate)**

タイトル: `WikiSkill Phase 1: Memory Foundation(Experience / Decision / Bootstrap / Privacy / Rollback)`
本文: 設計書 v1.1 の要点 / 変更ファイル一覧(本計画の File Structure)/ **変更していないもの**(Skills・commands・update-skills.sh・既存 hook)/ 手動 E2E の結果(受け入れ記録へのリンク)/ Rollback 手順 / 見直し条件 / 添付: `docs/議事_20261006_WikiSkill_Phase1導入.md`
CI: `repo-scope`(新ステップ含む)が緑であること

- [ ] **Step 3: マージ後(小柳さん承認後)にタグを打つ**

Run: `git fetch origin main && git tag -a wikiskill-phase1-v1 -m "WikiSkill Phase 1 Memory Foundation" origin/main && git push origin wikiskill-phase1-v1`
Expected: タグが GitHub に見える。`docs/wikiskill/Rollback手順.md` のマージコミット欄に hash を追記して commit

**Acceptance Criteria(Task 9):** PR が小柳さん承認でマージ / タグ存在 / revert 実演で settings.json が origin/main と一致した記録が PR に残る
**失敗時の Rollback:** マージ前なら PR をクローズするだけ。マージ後は `docs/wikiskill/Rollback手順.md`

---

## Phase 1 全体の Acceptance Criteria / Rollback 条件

**Acceptance Criteria(すべて満たすこと)**
1. 自動テスト 69 本合格、既存テスト(`tests/skill_validation` 等)に回帰なし
2. 手動 E2E(Session A → B)で、Decision の「件名・なぜ・ウタガイ反対理由・見直し期限」と、関連する失敗台帳 FK・再発防止メモが復元される
3. 各 hook 500ms 以内(テストで固定・実セッションで体感確認)
4. Experience に プロンプト本文・Bash 全文・プロジェクト外パス が一切無い(CI 検査 + E2E assert)
5. `.claude/memory.off` で全停止 / `git revert -m 1` で全戻しが実演済み
6. 変更禁止リスト(Skills 110・commands・update-skills.sh・既存 hook・agents)に `git diff origin/main --stat` で差分が無い
7. 導入議事が三名体制(ウタガイ反対理由つき)で存在し `decision_memory.py --check` 合格

**Rollback 条件(1つでも該当したら守り部が緊急停止 → 小柳 Gate で正式判断)**
- hook 時間 500ms 超の警告が1週間に3回以上
- `check_experience_privacy.py` の違反が1件でも main に入った
- Bootstrap が無関係/誤った Decision を「関連」として出した、との利用者申告が3件
- 既存 superpowers hook・既存 CI に回帰が出た
- Experience 合計が 10MB を超えた(archive で解消しない場合)

**Phase 1 で作らないもの(再掲)**: Skill Proposer / Skill Validator / Evolution Gate / Knowledge Extractor(`docs/wiki/`)/ Concurrency Lock / Conflict Resolver / Skill Metrics。既存 110 Skills・13リポ配布方式・`.claude/commands/` は不変。

---

## Self-Review(計画作成時に実施)

1. **Spec coverage**: 設計書 v1.1 の Phase 1 対象 A/C/D/K/I → Task 1-2 / 3 / 4 / 5 / 6。修正1(silent fail 禁止)→ Task 1 `audit`+`emit(system_message)`・Task 2 `test_python_failure_is_reported_not_silent`。修正2(関連情報のみ・毎セッション)→ Task 4 の budget/min_score/2段構え。修正3(信頼階層)→ Task 4 出力順とラベル。修正4(Skill 自動更新なし)→ Global Constraints。Decision 1〜8 のうち Phase 1 に関わる 1・2・4・5・7 → Task 4 / 3 / 6 / 1&5 / 6。3・6・8 は Phase 2〜3(本計画の対象外、設計書に反映済み)。E2E(Session A→B)→ Task 8。
2. **Step scan**: 各 Step は「テストを書く(assert 付き)/ 失敗確認(コマンド+期待)/ 実装(signature と固定値)/ 合格確認 / commit」。実装本体のコードは書いていない(関数本体は signature・テスト・固定値から一意に決まる)。
3. **Type consistency**: `Event`・`Decision`・`Source` の dict キーは Task 1/3/4 の Interfaces で定義し、Task 5/8 はそのキー名を使用(`visibility`・`repo`・`path`・`note.text`・`review_by`・`utagai`)。hook ラッパ名 `wikiskill-hook.sh <event>` と CLI `hook <event>` は全 Task で同一。
4. **Review Focus**: 5項目すべてに担当 Task とテスト名を割り当て済み。
5. **Proportion**: 設計書(約1,500行)に対し本計画は約600行。コードブロックはテストの assert と固定フォーマットのみ。

---

## 実装への遷移(停止点)

本計画は **小柳さんのレビュー待ち** で停止する。実装は開始しない。承認後の実行方法:

- **Subagent-driven**(推奨): Task ごとに新しい subagent が実装し、別の reviewer が検査してから次へ。Task 間のインターフェース(dict キー・CLI 名)が多く、hook は全セッションに効くため、出荷ミスの費用が高い
- **Native**: 本セッションが全 Task を順に実装し、最後に1回レビュー

承認時に併せて決めること: 計画・設計書を `docs/superpowers/plans/2026-10-06-wikiskill-phase1-memory-foundation.md` / `docs/superpowers/specs/2026-10-06-wikiskill-integration-design.md` へ置く(Task 7 の commit に含める)か否か。
