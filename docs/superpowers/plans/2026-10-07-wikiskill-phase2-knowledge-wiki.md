# Phase 2 WikiSkill Knowledge Wiki 実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** commit 済みの Experience・Decision・失敗台帳から知識の **候補** を機械で作り、検証器と人の承認を通ったものだけを Official Wiki(`docs/wiki/`)にし、新しいセッションの Memory Bootstrap に「何を知っているか」と「なぜ信頼しているか」(Provenance・承認者・承認日)を付けて渡す。最優先は **誤った知識を正式知識にしないこと**。

**Architecture:** 既存の Phase 1 基盤(`experience_log.py` / `decision_memory.py` / `memory_bootstrap.py` / `check_experience_privacy.py`)に、①共通 schema(`wiki_schema.py`)②検証器(`wiki_validate.py`。repo-scope CI のステップ)③規則ベース抽出器(`knowledge_extract.py --no-llm`。書込先は `docs/wiki/_candidates/` だけ)④ロック(`wikiskill_lock.py`)⑤Bootstrap の `[Wiki]` 区分 ⑥dispatch → PR の workflow と CODEOWNERS を足す。昇格は人がマージする PR だけ。Skill には一切反映しない。hook・settings.json は変えない。

**Tech Stack:** Python 3.11 標準ライブラリのみ(後置の LLM 下書きだけ `anthropic` SDK。無ければ使わない)/ pytest(既存 `tests/scripts/`・`tests/integration/` の流儀・fixture `kb` `realcopy` `world` `world_private` と `hook()` を再利用)/ GitHub Actions

**Spec:** Phase 2 設計書(`docs/superpowers/specs/2026-10-07-wikiskill-phase2-knowledge-wiki-design.md`)/ 上位: `docs/superpowers/specs/2026-10-06-wikiskill-integration-design.md`(v1.1)

**作業ブランチ:** `claude/superpowers-per-chat-3mbx56`(harness の指定ブランチ。origin/main から再作成済み — Task 0 で最新の origin/main との一致を確認)

## Global Constraints

- **Skill の自己改善・自動更新を実装しない**。Wiki を Skill に反映する処理も作らない(Phase 3 以降・別承認)
- **変更禁止**: `.claude/skills/**`(110 Skills)/ `.claude/commands/**` / `scripts/update-skills.sh` / `.claude/agents/**` / `.claude/hooks/*`(既存 hook。`wikiskill-hook.sh` も含めて変えない)/ `.claude/settings.json`
- **Private → Public の自動経路を作らない**: 抽出器の入力は commit 済み・`visibility == public`・`repo == allgroup-inc/hojo-hq` の行だけ。クロスリポ読込なし。LLM には公開テキストのみ
- **Candidate は自動承認されない**。`docs/wiki/` 直下へ移すのは人がマージする PR だけ。AI は昇格 PR を用意してよいがマージしない
- **Decision > Wiki**: Wiki と矛盾する新しい Decision は CI を止めない。Wiki 側を needs_review にして注入しない
- **main へ直 push しない**(weekly-gakubi の直 push が FK-006 の一因)。抽出結果は必ずブランチ + PR
- **stdlib のみ**(`anthropic` は後置 Task 10 の任意機能だけ)
- **G2(小柳さん決裁 2026-10-07): 抽出 workflow は `workflow_dispatch` のみ**。`schedule`(cron)による定期自動実行は禁止。実運用実績の後に別 Decision で再検討する
- **各 Task 完了時のゲート(小柳さん指定)**: 各 Task 完了時に 実装内容 / 変更ファイル / 新規ファイル / テスト結果 / Privacy 確認 / Baseline Debt / Regression(Phase 1 テスト ID 固定) / 次 Task へ進んでよい状態か を確認し、異常なら STOP
- **Baseline Debt SAME**: 各 Task の終了時に `python3 scripts/baseline_debt.py --compare` が `verdict: SAME`(IMPROVED も可)
- **Phase 1 由来の既存テスト(2026-10-07 時点 347 件・ID は Task 0 で固定)に回帰なし + Phase 2 で追加した新規テストが全て PASS**(期待値を変える既存テストは本計画に名前を挙げたものだけ。理由を commit に書く。合計件数の固定値を合格条件にしない)
- **hook 500ms**: `[Wiki]` 追加後も段1・段2 とも 500ms 以内(realcopy でテスト固定。CI では `WIKISKILL_SKIP_TIMING=1`)
- **禁止語の実文字列を書かない**: ソース・テスト・文書とも `check_repo_scope.FORBIDDEN_CONTENT` を参照する
- **1つの PR で導入**し、マージ時にタグ `wikiskill-phase2-v1`(`git revert -m 1` で全戻し可能)
- **議事必須**: CI のルール追加・CODEOWNERS(本番設定)にあたるため、三名体制の導入議事を Task 7 で残す(ウタガイ反対理由つき)
- **コミット前に `git branch --show-current`** で `claude/superpowers-per-chat-3mbx56` にいることを確認する(CLAUDE.md 再発防止メモ)

### 各 Task 共通の終了条件(CE)

| # | 条件 | コマンド | 期待 |
|---|---|---|---|
| CE1 | Baseline 非悪化 | `python3 scripts/baseline_debt.py --compare \| tail -1` | `verdict: SAME`(または IMPROVED) |
| CE2 | 禁止語 0(このブランチで変えたファイル) | `git diff --name-only origin/main...HEAD \| python3 -c "import sys;sys.path.insert(0,'scripts');from check_repo_scope import scan_contents;print(len(scan_contents([l.strip() for l in sys.stdin if l.strip()])))"` | `0` |
| CE3 | 変更禁止リスト不変 | `git diff --stat origin/main...HEAD -- .claude/skills .claude/commands scripts/update-skills.sh .claude/agents .claude/hooks .claude/settings.json` | 空 |
| CE4 | 既存 + 新規テスト | `python3 -m pytest tests/scripts tests/integration -q \| tail -1` | `failed` が Baseline の scripts tests 2件のみ |
| CE5 | Bootstrap 500ms | `python3 -m pytest tests/scripts/test_memory_bootstrap.py -q -k runtime` | passed |
| CE6 | 現在のブランチ | `git branch --show-current` | `claude/superpowers-per-chat-3mbx56` |

## Review Focus

1. **`_candidates/` を Bootstrap が絶対に読まない**(glob が直下だけ + `docs/wiki/_` 始まりの明示除外の二重)→ Task 3 `test_candidates_dir_never_opened`
2. **Provenance の偽造**(手書き・LLM が「それらしい」引用を作る): evidence の quote が参照先本文に逐語で含まれなければ違反 → Task 1 `test_quote_must_be_verbatim`
3. **Decision が Wiki に負けない**: 新しい Decision と矛盾する approved Wiki は検証器が exit 0 + 警告(Decision の PR を止めない)、Bootstrap は注入しない → Task 4 `test_new_decision_marks_wiki_needs_review_exit0_warning` / `test_needs_review_wiki_not_injected`
4. **private / unknown の Experience 行は読まない・数えない** → Task 2 `test_private_and_unknown_rows_not_counted`
5. **公開リポのブランチは push 時点で公開**: 抽出 workflow は push の前に検証器を通す。また `GITHUB_TOKEN` で作った PR では他 workflow が起動しないので、検証は同じジョブ内で行い結果を PR 本文に貼る → Task 5 `test_knowledge_extract_runs_validator_before_pr`
6. **`[Wiki]` 追加で 500ms を超えない**(Decision の読み込みを `_decisions` と `_wiki` で共有)→ Task 3 `test_bootstrap_runtime_under_500ms_with_wiki`
7. **同義語が二重に数えられない**(「マージ」と「merge」が両方当たっても1語)→ Task 3 `test_synonym_group_counts_once`

---

## File Structure

| 種別 | パス | 責務 |
|---|---|---|
| Create | `scripts/wiki_schema.py` | 共通: 定数・frontmatter(1行 JSON 値)の読み書き・ID 生成・normalize・dedup_key・同義語の読込・visibility 判定・矛盾判定関数 |
| Create | `scripts/wiki_validate.py` | G: V01〜V15 の検査・`--selftest`・`--json`・needs_review の算出 |
| Create | `scripts/knowledge_extract.py` | B: 入力の絞り込み・規則 R1〜R4・重複排除・矛盾の事前判定・候補の書込・実行要約 |
| Create | `scripts/wikiskill_lock.py` | L: ロックの取得・heartbeat・stale 判定・解除(Decision 8) |
| Create | `.github/workflows/knowledge-extract.yml` | dispatch → 抽出 → 検証 → ブランチ → PR(main へ直 push しない) |
| Create | `.github/CODEOWNERS` | `docs/wiki/ @takeshikoyanagi9-lab` |
| Create | `docs/wiki/_candidates/.gitkeep` | 候補ディレクトリの維持 |
| Create | `docs/wiki/_synonyms.txt` | 同義語表(初期数行) |
| Create | `docs/wikiskill/Wiki昇格手順.md` | 昇格・却下・needs_review 解消・acknowledged の書き方 |
| Create | `docs/wikiskill/Phase2受け入れ記録.md` | 実セッション E2E の台帳 |
| Create | `docs/議事/議事_YYYYMMDD_WikiSkill_Phase2導入.md` | 三名体制議事(実施日で命名) |
| Create | `tests/scripts/test_wiki_schema.py` / `test_wiki_validate.py` / `test_knowledge_extract.py` / `test_wikiskill_lock.py` / `test_wikiskill_workflows.py` | 単体テスト |
| Create | `tests/integration/test_wikiskill_wiki_e2e.py` | 順方向・逆方向の自動 E2E |
| Modify | `scripts/experience_log.py` | 持ち越し (d)(e) |
| Modify | `scripts/memory_bootstrap.py` | `KINDS`・`COLLECTORS` に wiki、`_wiki`、`wiki.off`、同義語グループ、Skill 名一致の限定、検索語行、Decision 読込の共有 |
| Modify | `scripts/decision_memory.py` | 持ち越し (g)、任意キー `visibility` |
| Modify | `.github/workflows/wikiskill-tests.yml` | 持ち越し (f) + 新スクリプト・テスト |
| Modify | `.github/workflows/repo-scope.yml` | `wiki_validate.py` の自己点検と本検査のステップ |
| Modify | `.gitignore` | `.claude/wiki.off` |
| Modify | `docs/wikiskill/README.md` / `Rollback手順.md` / `議事frontmatterテンプレート.md` | Phase 2 の章・節 |
| Modify | `docs/議事/議事_20261006_Experience長期保存方式_候補.md` | 比較と推奨の追記(deferred のまま) |
| Modify | `docs/決裁キュー.md` / `docs/全体マップ.md` / `CLAUDE.md` | Gate 項目・置き場所・記憶の仕組み節に2行 |

共通の型は Task 1(`Wiki`)・Task 2(`Inputs` `Draft`)の Interfaces で定義し、以後の Task はそれを参照する。

---

### Task 0: ブランチ準備と基線確認

**目的:** 最新の origin/main から作業ブランチを作り、Phase 1 の基線(Phase 1 由来の既存テストの ID 一覧・Baseline SAME)を記録する(古いブランチでの判定は誤報告の元: CLAUDE.md 技術構成)。
**新規ファイル:** なし / **変更ファイル:** なし(Git 操作のみ)
**Interfaces:** Produces: origin/main と同一内容の `claude/superpowers-per-chat-3mbx56`
**Public/Private impact:** なし / **既存機能への影響:** なし

- [ ] **Step 1:** `git fetch origin main && git checkout -B claude/superpowers-per-chat-3mbx56 origin/main && git branch --show-current && git log --oneline -1` → `claude/superpowers-per-chat-3mbx56` / origin/main の最新
- [ ] **Step 2:** `pip install -q pytest && python3 scripts/baseline_debt.py --compare | tail -1` → `verdict: SAME`
- [ ] **Step 3:** `python3 -m pytest tests/scripts tests/integration -q | tail -1` → Phase 1 由来の既存テスト(2026-10-07 時点 347 件)の ID 一覧を `.superpowers/sdd/phase2-baseline/phase1-test-ids.txt` に保存して固定し、合格数と Baseline の2件 failed を記録する。以後の CE4 と Regression の基準は件数ではなく、この固定した ID
- [ ] **Step 4:** `python3 scripts/memory_bootstrap.py query "WikiSkill 記憶" > .superpowers/sdd/phase2-baseline/bootstrap-baseline.txt` → 既存6区分の出力を保存(Task 3 の回帰比較用)

**Acceptance Criteria:** ブランチが origin/main と一致 / Baseline SAME / 合格数を記録済み
**Rollback:** ブランチを削除するだけ

---

### Task 0b: Phase 1 持ち越し A 群((d)(e)(f))

**目的:** Phase 2 の前に、記録側の小さな穴を3つ塞ぐ。(d) git エラー時に commit 済みファイルへ追記しない (e) `~` 始まりのパスを `<external>` にし、検査側と一致させる (f) Bootstrap の入力が変わったら wikiskill-tests が走るようにする。
**新規ファイル:** `tests/scripts/test_wikiskill_workflows.py`
**変更ファイル:** `scripts/experience_log.py` / `.github/workflows/wikiskill-tests.yml` / `tests/scripts/test_experience_log.py`(追加のみ)

**Interfaces:**
- Produces(`experience_log.py`):
  - `_tracked_state(root: Path, path: Path) -> str` — `git ls-files --error-unmatch` の exit 0 → `"tracked"` / exit 1 → `"untracked"` / それ以外・例外 → `"error"`
  - `_is_tracked(root, path) -> bool` — 互換のため残す(`_tracked_state(...) == "tracked"`)
  - `session_file(root, session_id, ts) -> Path` — 本体の状態が `"error"` なら、ディスク上に存在しない最初の `session-<sid>.part<N>.jsonl` を返し、`audit(root, "experience_log", "git ls-files failed; writing to part file")` を1プロセス1回だけ残す
  - `sanitize_path(p, root)` — `str(p).startswith("~")` なら `"<external>"`
  - `_program_of(command, root)` — トークンが `~` で始まれば `"<external>"`
- Produces(`wikiskill-tests.yml` の `pull_request.paths` と `push.paths` に追加): `CLAUDE.md` / `docs/**` / `.claude/skills/**` / `.claude/settings.json` / `.gitignore` / `scripts/check_repo_scope.py`

**Tests:**
```python
# tests/scripts/test_experience_log.py(追加。fixture `repo` は既存)
def test_is_tracked_untracked_exit1_writes_base(repo): p = session_file(repo, "s1", NOW); assert p.name == "session-s1.jsonl"
def test_is_tracked_git_error_writes_part_file(repo, monkeypatch):  # subprocess.run を exit 128 に差し替え
    p = session_file(repo, "s1", NOW); assert ".part1." in p.name
def test_git_error_is_audited_once(repo, monkeypatch): ...; assert audit_text(repo).count("git ls-files failed") == 1
def test_sanitize_path_tilde_is_external(repo): assert sanitize_path("~/glow/x.md", repo) == "<external>"
def test_program_tilde_is_external(repo): assert _program_of("~/bin/tool --x", repo) == "<external>"
# tests/scripts/test_wikiskill_workflows.py(新規。YAML は文字列として読む: PyYAML に依存しない)
def test_wikiskill_tests_paths_cover_inputs():
    text = read(".github/workflows/wikiskill-tests.yml")
    for p in ["CLAUDE.md", "docs/**", ".claude/skills/**", ".claude/settings.json", ".gitignore", "scripts/check_repo_scope.py"]:
        assert text.count(f"'{p}'") == 2   # pull_request と push の両方
```

- [ ] **Step 1:** テストを書く → `python3 -m pytest tests/scripts/test_experience_log.py tests/scripts/test_wikiskill_workflows.py -q` → 新規6本 FAIL
- [ ] **Step 2:** 実装 → 同コマンドで既存 + 6 passed
- [ ] **Step 3:** `python3 scripts/check_experience_privacy.py --selftest` → `自己点検OK`(検査側は変えない)
- [ ] **Step 4:** CE1〜CE6 → commit `fix(wikiskill): 持ち越しA群 — git エラー時は part へ書く・~ パスを <external>・wikiskill-tests の paths 拡張`

**Acceptance Criteria:** 6テスト合格 / 既存の experience_log テスト不変で合格 / CE 全項目
**Rollback:** この commit を revert(記録先の選び方が Phase 1 に戻るだけ)
**Public/Private impact:** 強化のみ((e) で `~` パスが記録に残らない)
**既存機能への影響:** git が正常な環境では記録先は変わらない。git エラー時だけ part ファイルになり、読む側(`group_session_files`)は既に part に対応済み

---

### Task 1: Candidate・Wiki schema と `wiki_validate.py`(selftest・CI ステップ)

**目的:** 候補と正式 Wiki の形を固定し、schema / Provenance / privacy / 置き場所 / 重複 を機械で止める検証器を CI に入れる(矛盾検知 V11〜V13 は Task 4)。
**新規ファイル:** `scripts/wiki_schema.py` / `scripts/wiki_validate.py` / `docs/wiki/_candidates/.gitkeep` / `tests/scripts/test_wiki_schema.py` / `tests/scripts/test_wiki_validate.py`
**変更ファイル:** `.github/workflows/repo-scope.yml` / `.github/workflows/wikiskill-tests.yml`(新スクリプト・テストを paths とテスト一覧に追加)

**Interfaces:**
- Produces(`wiki_schema.py`):
  - 定数: `WIKI_DIR = "docs/wiki"` / `CANDIDATES_DIR = "docs/wiki/_candidates"` / `ARCHIVE_DIR = "docs/wiki/_archive"` / `SYNONYMS_PATH = "docs/wiki/_synonyms.txt"` / `WIKI_OFF = ".claude/wiki.off"`
  - `REQUIRED_KEYS = ("candidate_id","title","summary","evidence","confidence","confidence_basis","visibility","repo","created_at","proposed_by","contradictions","related_wiki","related_skills","review_status","dedup_key","extract_run")`
  - `APPROVED_KEYS = ("wiki_id","approved_by","approved_at","review_by","review")` / `SOURCE_KEYS = ("source_experience","source_decision","source_failure")`
  - `BODY_SECTIONS = ("## 知識", "## 根拠(Provenance)", "## 反証(ウタガイ)", "## 適用範囲と例外", "## 関連")`
  - `STATUS_BY_PLACE = {"candidates": {"candidate","conflict","rejected"}, "official": {"approved"}, "archive": {"superseded"}}`
  - 上限: `MAX_TITLE = 80` / `MAX_SUMMARY = 200` / `MAX_QUOTE = 200` / `MAX_EVIDENCE = 10` / `MAX_BODY = 4000` / `MAX_KNOWLEDGE = 1500` / `SHOWN_SUMMARY = 160` / `DEFAULT_REVIEW_DAYS = 180` / `DUPLICATE_RATIO = 0.6` / `CONFLICT_MIN_UNITS = 2`
  - `NEGATION_WORDS = ("禁止", "しない", "却下", "やめる", "不可")`
  - `BOT_APPROVERS = frozenset({"claude", "hojo-hq-bot", "github-actions", "github-actions[bot]", "knowledge_extract", "rule-based"})`(小文字で比較)
  - `EMPTY_WORDS = frozenset({"", "-", "なし", "無し", "tbd", "todo", "未記入"})`(ウタガイの空語)
  - 正規表現: `CANDIDATE_ID_RE = ^K\d{8}-[a-z0-9][a-z0-9-]{0,39}-[0-9a-f]{4,6}$` / `WIKI_ID_RE = ^W\d{8}-[a-z0-9][a-z0-9-]{0,39}$` / `EXP_SOURCE_RE = ^session-([A-Za-z0-9._-]+)@(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z)$` / `FK_RE = ^FK-\d{3}$`
  - `Wiki = dict` — frontmatter の全キー + `_path`(リポ相対)/ `_place` ∈ {`candidates`,`official`,`archive`} / `_body` / `_sections: dict[str, str]`
  - `class WikiFormatError(ValueError)`
  - `parse_wiki_frontmatter(text: str) -> tuple[dict, str]` — 1行1キー。値が `[` / `{` で始まれば `json.loads`、それ以外はスカラー(数値は float)。読めなければ `WikiFormatError`
  - `render_wiki(fm: dict, sections: dict[str, str]) -> str` — キー順は `REQUIRED_KEYS` → `SOURCE_KEYS` → 任意キー、JSON は `ensure_ascii=False`
  - `load_wiki_file(path: Path, root: Path) -> Wiki`
  - `iter_wiki(root: Path, place: str) -> list[Wiki]` — `official` は `docs/wiki/*.md`(直下・非再帰・`_` 始まりを除く)、`candidates` / `archive` は各ディレクトリ直下。読めないファイルは `{"_path":…, "_error": "<理由>"}`
  - `normalize(text: str) -> str` — NFKC → 小文字 → 空白・記号を除去
  - `slugify(text: str, fallback: str) -> str` — ASCII 英数とハイフンだけ、40字まで。空なら fallback(例 `fk-006` / `skill-writing-plans` / `note-<sid先頭6>`)
  - `dedup_key(title: str, source_ids: list[str]) -> str` — `sha1(normalize(title) + "|" + ",".join(sorted(source_ids))).hexdigest()`
  - `make_candidate_id(day: date, slug: str, key: str, taken: set[str]) -> str` — `K{day:%Y%m%d}-{slug}-{key[:4]}`、衝突したら `key[:5]`、`key[:6]`
  - `all_source_ids(w: Wiki) -> list[str]`
  - `repo_visibility(root: Path) -> str` — `experience_log.repo_slug(root) in experience_log.PUBLIC_REMOTES` なら `public`、それ以外(`unknown` を含む)は `private`
- Produces(`wiki_validate.py`):
  - `Violation = tuple[str, str, str]`(パス, コード, 理由)/ `Warning = tuple[str, str, str]`(パス, decision_id, 理由)
  - `Context = dict` — `root` / `repo_visibility` / `decisions`(`load_decisions`)/ `decisions_by_id` / `fk_rows: dict[str, str]`(FK id → 行の本文)/ `exp_events: dict[tuple[str, str], dict]`((sid, ts) → イベント。**git 管理下のファイルだけ**を `group_session_files` で束ね `experience_log._read_events` で読む)/ `official` / `ids`
  - `build_context(root: Path) -> Context`
  - `resolve_source(source: str, kind: str, ctx: Context) -> tuple[str, dict | None]` — (参照先の本文, 行/Decision/FK)。解決できなければ ("", None)
  - `validate_file(w: Wiki, ctx: Context) -> list[Violation]` — V01〜V10, V14, V15(本 Task)
  - `validate_tree(root: Path) -> tuple[list[Violation], list[Warning]]`
  - `selftest() -> int` — 正例・負例を内蔵。禁止語の負例は `FORBIDDEN_CONTENT[0]` で組み立てる
  - CLI: `python3 scripts/wiki_validate.py [--root PATH] [--json] [--selftest]` — exit 0 / 1(違反)/ 2(使い方・自己点検失敗)。違反なしで `OK: Wiki 0件・候補 N件・違反なし`
- Consumes: `check_repo_scope.find_content_violations` / `check_repo_scope.FORBIDDEN_CONTENT`(import。二重管理しない)、`decision_memory.load_decisions`、`wikiskill_common.group_session_files`、`experience_log._read_events` / `repo_slug` / `PUBLIC_REMOTES`
- repo-scope.yml 追加ステップ(既存の Experience 検査の後):
```yaml
      - name: Wiki(候補・正式)の自己点検
        if: ${{ !cancelled() }}
        run: python3 scripts/wiki_validate.py --selftest
      - name: Wiki(候補・正式)の検査
        if: ${{ !cancelled() }}
        run: python3 scripts/wiki_validate.py
```

**Tests:**
```python
# tests/scripts/test_wiki_schema.py
def test_parse_wiki_frontmatter_scalar_and_json(): fm, body = parse_wiki_frontmatter(GOOD); assert fm["evidence"][0]["ref"] and body.startswith("## 知識")
def test_parse_wiki_frontmatter_rejects_bad_json(): with pytest.raises(WikiFormatError): parse_wiki_frontmatter(GOOD.replace('"ref"', "ref"))
def test_candidate_id_format(): assert CANDIDATE_ID_RE.match(make_candidate_id(date(2026,10,20), "fk-006", "ab12"*10, set()))
def test_dedup_key_stable_under_whitespace_and_order(): assert dedup_key("A  b", ["x","y"]) == dedup_key("a b", ["y","x"])
def test_normalize_nfkc_lower_strip(): assert normalize("Ｍｅｒｇｅ！ ") == "merge"
def test_render_then_parse_roundtrip(): fm, _ = parse_wiki_frontmatter(render_wiki(FM, SECTIONS)); assert fm == FM
# tests/scripts/test_wiki_validate.py(fixture `wk` = tmp git repo(origin=hojo-hq)+ commit 済み Experience 1セッション(note 行)+ 議事1件(frontmatter)+ 失敗台帳(FK-002)+ 有効な候補1件)
def test_valid_candidate_passes(wk): assert validate_tree(wk) == ([], [])
def test_missing_required_key_fails(wk): assert codes(edit(wk, drop="summary")) == {"V01"}
def test_missing_body_section_fails(wk): assert "V01" in codes(edit_body(wk, drop="## 反証(ウタガイ)"))
def test_candidate_id_must_match_filename(wk): assert "V02" in codes(rename(wk, "K20261020-other-0000.md"))
def test_duplicate_candidate_id_fails(wk): copy_candidate(wk); assert "V02" in codes(wk)
def test_no_source_fails(wk): assert "V03" in codes(edit(wk, source_experience=[], source_decision=[], source_failure=[]))
def test_unresolved_experience_fails(wk): assert "V03" in codes(edit(wk, source_experience=["session-zzz@2026-10-01T00:00:00Z"]))
def test_untracked_experience_not_resolvable(wk): add_untracked_session(wk, "U"); assert "V03" in codes(edit(wk, source_experience=["session-U@…"]))
def test_unknown_decision_fails(wk): assert "V03" in codes(edit(wk, source_decision=["D20990101-none"]))
def test_fk_resolves(wk): assert codes(edit(wk, source_failure=["FK-002"], evidence=[fk_quote()])) == set()
def test_quote_must_be_verbatim(wk): assert "V04" in codes(edit(wk, evidence=[{"ref": REF, "quote": "要約した別の文"}]))
def test_private_experience_source_fails(wk): commit_private_row(wk, "P"); assert "V05" in codes(edit(wk, source_experience=["session-P@…"]))
def test_visibility_must_match_repo(wk): assert "V05" in codes(edit(wk, visibility="private"))
def test_forbidden_content_fails(wk): assert "V06" in codes(edit(wk, summary=f"x {FORBIDDEN_CONTENT[0]} y"))
def test_summary_over_200_fails(wk): assert "V07" in codes(edit(wk, summary="あ"*201))
def test_approved_in_candidates_fails(wk): assert "V08" in codes(edit(wk, review_status="approved", **APPROVED))
def test_candidate_in_wiki_root_fails(wk): move_to_root(wk); assert "V08" in codes(wk)
def test_approved_requires_approver_utagai_review_by(wk): promote(wk, review={"スイシン":"a","ウタガイ":"なし","ベッカイ":"c"}); assert "V09" in codes(wk)
def test_bot_approver_rejected(wk): promote(wk, approved_by="github-actions[bot]"); assert "V09" in codes(wk)
def test_duplicate_requires_duplicate_of(wk): promote(wk); add_candidate_same_words(wk); assert "V10" in codes(wk)
def test_synonyms_format(wk): write(wk, "docs/wiki/_synonyms.txt", "マージ, merge\nmerge, 統合\n"); assert "V14" in codes(wk)
def test_dangling_wiki_ref_fails(wk): assert "V15" in codes(edit(wk, related_wiki=["W20990101-none"]))
def test_selftest_passes(): assert run(["--selftest"]).returncode == 0
def test_cli_exit_codes(wk): assert run([], cwd=wk).returncode == 0; edit(wk, drop="title"); assert run([], cwd=wk).returncode == 1
```

- [ ] **Step 1:** テストを書く → `python3 -m pytest tests/scripts/test_wiki_schema.py tests/scripts/test_wiki_validate.py -q` → FAIL(import error)
- [ ] **Step 2:** `wiki_schema.py` を実装 → schema 6 passed
- [ ] **Step 3:** `wiki_validate.py` を実装(V11〜V13 は空関数で置き、Task 4 で中身を入れる)→ 30 passed
- [ ] **Step 4:** `mkdir -p docs/wiki/_candidates && touch docs/wiki/_candidates/.gitkeep && python3 scripts/wiki_validate.py --selftest && python3 scripts/wiki_validate.py` → `自己点検OK(…件)` / `OK: Wiki 0件・候補 0件・違反なし`
- [ ] **Step 5:** repo-scope.yml と wikiskill-tests.yml を更新 → `grep -c wiki_validate .github/workflows/repo-scope.yml` → `2`
- [ ] **Step 6:** CE1〜CE6 → commit `feat(wikiskill): Wiki 候補の schema と検証器 — 根拠の解決・逐語引用・公開可否・置き場所をCIで止める`

**Acceptance Criteria:** 30テスト合格 / `--selftest` に V01〜V10・V14・V15 の正例と負例 / repo-scope に2ステップ / 現状(候補0件)で CI 緑
**Rollback:** revert(検証器と CI ステップが消える。`docs/wiki/` はまだ空)
**Public/Private impact:** 公開境界の機械検査を Wiki に広げる(強化のみ)
**既存機能への影響:** repo-scope に2ステップ増える(`!cancelled()` なので既存ステップの赤に引きずられず、既存ステップにも影響しない)。Phase 1 のスクリプトは import するだけで変更しない

---

### Task 2: `knowledge_extract.py` 規則ベース + lock + 重複排除

**目的:** commit 済みの public 記録だけから、規則 R1〜R4 で候補を決定的に作り、`_candidates/` にだけ書く。二重実行はロックで防ぐ。
**新規ファイル:** `scripts/knowledge_extract.py` / `scripts/wikiskill_lock.py` / `tests/scripts/test_knowledge_extract.py` / `tests/scripts/test_wikiskill_lock.py`
**変更ファイル:** `.github/workflows/wikiskill-tests.yml`(paths とテスト一覧)

**Interfaces:**
- Produces(`wikiskill_lock.py`):
  - `LOCK_DIR = ".claude/locks"` / `TIMEOUT_S = 1800` / `HEARTBEAT_EVERY_S = 60`
  - `class LockHeld(Exception)` — 属性 `holder: dict` / `age_s: int`
  - `lock_path(root: Path, name: str) -> Path` — `root/.claude/locks/<name>.lock`
  - `lock_state(root: Path, name: str, now: datetime | None = None) -> str` — `free` / `held`(heartbeat から30分以内)/ `stale_safe`(30分超 **かつ** `_local/<session_id>.ended` がある、または同じ host で pid が生きていない)/ `stale_unsure`(30分超だが判断材料なし)
  - `acquire(root: Path, name: str, session_id: str, *, break_stale: bool = False, now: datetime | None = None) -> dict` — `free`・`stale_safe` は取得(stale 解除は audit)、`stale_unsure` は `break_stale=True` のときだけ取得、それ以外は `LockHeld`
  - `heartbeat(root: Path, name: str, lock: dict, now: datetime | None = None) -> None` / `release(root: Path, name: str, lock: dict) -> None`(自分のロックだけ消す)
- Produces(`knowledge_extract.py`):
  - `VERSION = "1.0"` / `PROPOSED_BY_RULE = f"knowledge_extract.py@{VERSION} rule-based"` / `LOCK_NAME = "knowledge-extract"`
  - `NOTE_PREFIXES = {"学び": "lesson", "失敗": "failure", "誤関連": "misretrieval"}`(NFKC 後に `学び:` 等で判定。全角コロン可)
  - `R1_MIN_SESSIONS = 2` / `MAX_CANDIDATES = 10`
  - `CONFIDENCE = {"R1": (0.30, 0.05, 0.50), "R2": (0.40, 0.10, 0.60), "R3": (0.70, 0.0, 0.70), "R4_adopted": (0.80, 0.0, 0.80), "R4_deferred": (0.30, 0.0, 0.30)}`(初期値, 加算, 上限)
  - `Inputs = dict` — `sessions: dict[str, list[dict]]`(sid → イベント。git 管理下・public・hojo-hq の行だけ)/ `decisions: list[dict]` / `failures: list[dict]`(`id` `date` `category` `fact` `measure` `line`)/ `gakubi: list[dict]` / `counts: dict[str, int]`(区分ごとの採用件数。読み捨てた行は数えない)
  - `collect_inputs(root: Path, include_gakubi: bool = False) -> Inputs` — Experience は `git ls-files -z -- .claude/experience` → `group_session_files` → `experience_log._read_events`。行ごとに `visibility == "public" and repo == "allgroup-inc/hojo-hq"` を満たすものだけ残す
  - `Draft = dict` — `rule` / `title` / `summary` / `sections` / `source_experience` / `source_decision` / `source_failure` / `evidence` / `confidence` / `confidence_basis` / `related_skills`
  - `rule_skill_success(inp: Inputs) -> list[Draft]` / `rule_note_prefix(inp) -> list[Draft]` / `rule_failure_ledger(inp) -> list[Draft]` / `rule_decision_ruling(inp) -> list[Draft]`
  - `RULES = [("R1", rule_skill_success), ("R2", rule_note_prefix), ("R3", rule_failure_ledger), ("R4", rule_decision_ruling)]`
  - `finalize(d: Draft, root: Path, run_id: str, today: date, existing_keys: set[str], taken_ids: set[str]) -> Wiki | None` — dedup_key が既存(candidate / conflict / rejected / approved / archive)にあれば None。`review_status: candidate`、`proposed_by = PROPOSED_BY_RULE`、`extract_run = run_id`
  - `write_candidate(root: Path, w: Wiki) -> Path` — 書込の唯一の入口。`root/docs/wiki/_candidates/` の外になるパスは `ValueError`
  - `run(root: Path, *, llm: bool = False, include_gakubi: bool = False, dry_run: bool = False, max_candidates: int = MAX_CANDIDATES, run_id: str | None = None, session_id: str | None = None, break_stale_lock: bool = False) -> dict` — 実行要約 `{"run_id", "written": [path], "skipped_duplicate", "conflict", "rejected_by_validator", "inputs": counts}`。書く前に各候補へ `wiki_validate.validate_file` を掛け、違反は書かずに要約へ
  - CLI: `python3 scripts/knowledge_extract.py [--no-llm] [--llm] [--include-gakubi] [--dry-run] [--max N] [--run-id ID] [--root PATH] [--break-stale-lock]` — 既定 `--no-llm`。exit 0 / 1(書込・検証の失敗)/ 2(使い方。`--llm` は Task 10 まで「未実装」で exit 2)/ 3(ロック中)
- Consumes: Task 1 の `wiki_schema.*`・`wiki_validate.validate_file` / `build_context`、`decision_memory.load_decisions`

**Tests:**
```python
# tests/scripts/test_wikiskill_lock.py
def test_acquire_and_release(tmp_path): l = acquire(tmp_path, "x", "S"); release(tmp_path, "x", l); assert lock_state(tmp_path, "x") == "free"
def test_second_acquire_refused_with_holder_info(tmp_path): acquire(tmp_path,"x","S"); e = raises(LockHeld, acquire, tmp_path,"x","T"); assert e.holder["session_id"] == "S"
def test_heartbeat_extends_validity(tmp_path): l = acquire(..., now=T0); heartbeat(..., l, now=T0+25min); assert lock_state(..., now=T0+40min) == "held"
def test_stale_with_ended_marker_auto_released_and_audited(tmp_path): ...; ended_marker("S"); assert acquire(...,"T", now=T0+31min) and "stale" in audit_text(tmp_path)
def test_stale_without_marker_needs_break_flag(tmp_path): ...; raises(LockHeld, acquire, ..., now=T0+31min); assert acquire(..., break_stale=True, now=T0+31min)
def test_extract_cli_exit_3_when_locked(ex): acquire(ex, "knowledge-extract", "S"); assert run_cli(ex).returncode == 3
# tests/scripts/test_knowledge_extract.py(fixture `ex` = tmp git repo(origin=hojo-hq)+ commit 済み Experience: public 2セッション(同じ Skill・各 commit 1件)/ note 3行(学び: 失敗: 誤関連:)/ private 行1・repo 違い行1 + 議事2件(adopted / deferred)+ 失敗台帳(FK-002))
def test_reads_only_public_hojo_hq_rows(ex): inp = collect_inputs(ex); assert all(e["visibility"]=="public" and e["repo"]=="allgroup-inc/hojo-hq" for evs in inp["sessions"].values() for e in evs)
def test_private_and_unknown_rows_not_counted(ex): assert collect_inputs(ex)["counts"]["experience_rows"] == PUBLIC_ROWS
def test_untracked_experience_ignored(ex): add_untracked_session(ex, "U"); assert "U" not in collect_inputs(ex)["sessions"]
def test_r1_needs_two_sessions_with_commits(ex): assert len(rule_skill_success(collect_inputs(ex))) == 1; drop_commits(ex, "S2"); assert rule_skill_success(collect_inputs(ex)) == []
def test_r2_note_prefixes(ex): ds = rule_note_prefix(collect_inputs(ex)); assert len(ds) == 3 and {d["rule"] for d in ds} == {"R2"}
def test_r2_fullwidth_colon(ex): add_note(ex, "学び：全角でも拾う"); assert any("全角" in d["summary"] for d in rule_note_prefix(collect_inputs(ex)))
def test_r3_failure_row_candidate(ex): d = rule_failure_ledger(collect_inputs(ex))[0]; assert d["source_failure"] == ["FK-002"] and d["confidence"] == 0.70
def test_r4_adopted_decision_candidate(ex): assert any(d["source_decision"] == [ADOPTED_ID] for d in rule_decision_ruling(collect_inputs(ex)))
def test_r4_deferred_capped_confidence(ex): d = [d for d in rule_decision_ruling(collect_inputs(ex)) if d["source_decision"] == [DEFERRED_ID]][0]; assert d["confidence"] <= 0.30 and "判断根拠にしない" in d["sections"]["## 適用範囲と例外"]
def test_gakubi_is_evidence_only(ex): add_gakubi(ex); s = run(ex, include_gakubi=True); assert all(has_source(p) for p in s["written"])
def test_candidate_id_unique_in_run(ex): ids = [Path(p).stem for p in run(ex)["written"]]; assert len(ids) == len(set(ids))
def test_dedup_against_existing_including_rejected(ex): first = run(ex); mark_rejected(ex, first["written"][0]); assert run(ex)["written"] == [] and run(ex)["skipped_duplicate"] >= 1
def test_writes_only_under_candidates(ex): run(ex); assert all(p.startswith("docs/wiki/_candidates/") for p in git_untracked(ex))
def test_never_touches_approved_or_synonyms(ex): seed_approved_and_synonyms(ex); before = snapshot(ex, "docs/wiki"); run(ex); assert unchanged_except_candidates(before, ex)
def test_output_passes_validator(ex): run(ex); assert validate_tree(ex)[0] == []
def test_no_llm_default_makes_no_network_call(ex, monkeypatch): monkeypatch.setattr(socket, "create_connection", boom); assert run(ex)["written"]
def test_dry_run_writes_nothing(ex): s = run(ex, dry_run=True); assert s["written"] and not list((ex/"docs/wiki/_candidates").glob("K*.md"))
def test_max_limits_output(ex): assert len(run(ex, max_candidates=2)["written"]) == 2
```

- [ ] **Step 1:** lock のテストを書く → FAIL → `wikiskill_lock.py` 実装 → 6 passed
- [ ] **Step 2:** 抽出器のテストを書く → FAIL → `knowledge_extract.py` 実装 → 18 passed
- [ ] **Step 3:** 実データで確認(書かない): `python3 scripts/knowledge_extract.py --dry-run --max 10 | python3 -m json.tool | head -40` → `inputs` の件数・`written` の候補名が出る。`git status --short docs/wiki` → 空
- [ ] **Step 4:** CE1〜CE6 → commit `feat(wikiskill): 規則ベースの知識抽出器 — commit済みpublic記録だけから候補を作り _candidates にだけ書く(lock・重複排除)`

**Acceptance Criteria:** 24テスト合格 / 実データの `--dry-run` で例外なし・書込なし / 出力候補が検証器を通る
**Rollback:** revert(抽出器はまだ workflow から呼ばれていない)
**Public/Private impact:** 入力を public・hojo-hq・commit 済みに機械で限定。候補は公開リポに載る前提で Task 1 の検証を書込前に掛ける
**既存機能への影響:** なし(読み取り + `_candidates/` への書込のみ。Phase 1 スクリプトは import のみ)

---

### Task 3: Bootstrap `[Wiki]` + `wiki.off` + 同義語展開(持ち越し a, b, c)

**目的:** 承認済み Wiki を `[Wiki]` 区分として注入し、「なぜ信頼しているか」を同じ行に出す。あわせて同義語・Skill 名一致・検索語行の持ち越しを直す。
**新規ファイル:** `docs/wiki/_synonyms.txt`
**変更ファイル:** `scripts/memory_bootstrap.py` / `.gitignore`(`.claude/wiki.off` を1行)/ `tests/scripts/test_memory_bootstrap.py`(追加のみ)

**Interfaces:**
- Produces(`memory_bootstrap.py`):
  - `KINDS` に `("wiki", "[Wiki]", "## 承認済みの知識 [Wiki](Official Wiki・人が承認)")` を `prevention` の直後・`skill` の直前に挿入(`KIND_ORDER` は自動で追従)
  - `COLLECTORS` に `("wiki", _wiki)` を `prevention` の直後に挿入
  - `_decisions_cached(root: Path) -> list[dict]` — `load_decisions(root)` の1プロセス内 memo(`_decisions` と `_wiki` が共有)
  - `_wiki(root: Path) -> list[Source]` — `.claude/wiki.off` があれば `[]` + audit `wiki: disabled by wiki.off`。`wiki_schema.iter_wiki(root, "official")` のうち `review_status == "approved"`・`visibility == repo_visibility(root)`・needs_review でない(Task 4 で中身。本 Task は常に False)もの。相対パスが `docs/wiki/_` で始まるものは捨てる。`_src("wiki", "[Wiki]", wiki_id, path, title, summary, _wiki_line(w), approved_at, title + " " + summary + " " + 知識の先頭600字, title)`
  - `_wiki_line(w: Wiki) -> str` — `- [Wiki] {title} — {summary[:160]} / 根拠: Exp {n}・Decision {m}・FK {k} / 承認: {approved_by} {approved_at} → {path}`
  - `query_groups(terms: list[str], synonyms: list[frozenset[str]] | None = None) -> list[tuple[tuple[str, str, frozenset], ...]]` — `query_units(terms)` の各語に、同じ同義語グループの語(`query_units([語])` で単位化)を束ねた tuple。`query_units` の signature と挙動は変えない
  - `_group_matches(group, feats: set[str]) -> bool` — group のどれか1つが `_unit_matches` なら True(1語として数える)
  - `_select(sources, terms, per_kind=PER_KIND, min_score=MIN_SCORE, exclude=frozenset(), name_terms: list[str] | None = None, synonyms: list[frozenset[str]] | None = None)` — 照合単位を group に変更。**Skill の名前一致を1語に数えるのは、`name_terms` から作った group が名前に当たったときだけ**(`None` は全語=手動 `query` と `retrieve` の互換、`[]` は数えない)
  - 段1 `_stage1_render` は `name_terms=[]`、段2 `_stage2` は `name_terms=prompt_terms`、`retrieve` は `None`
  - `_units_line(groups) -> str` — 正規化後の語を `, ` で連結(同義語は `マージ(=merge)` の形)、`TERMS_SHOWN` で切る。段1・段2とも `検索語: ` 行に使う。段2は `検索語(指示から): … / (ブランチから): …` の2つに分ける。**指示の本文そのものは出さない**(語だけ)
  - `wiki_schema.load_synonyms(root: Path) -> list[frozenset[str]]` — `docs/wiki/_synonyms.txt` を読む(無ければ空)。`#` 以降はコメント、`,` 区切り、`_norm` で正規化、2語未満の行と V14 違反行は捨てて audit
- `docs/wiki/_synonyms.txt` 初期内容(例。最終は導入議事で確定): `マージ, merge` / `コミット, commit` / `締切, 期限, deadline` / `議事, decision`
- `.gitignore` 追記: `.claude/wiki.off`(Phase 1 のブロックの直後に1行)

**Tests:**
```python
# tests/scripts/test_memory_bootstrap.py(追加。fixture `kb` に approved Wiki 1件 + candidate 1件 + _archive 1件を足す `kbw`)
def test_wiki_kind_order_between_prevention_and_skill(kbw): out = retrieve(kbw, WORDS); assert out.index("[再発防止]") < out.index("[Wiki]") < out.index("[Skill]")
def test_wiki_only_approved_shown(kbw): out = retrieve(kbw, WORDS); assert APPROVED_TITLE in out and CANDIDATE_TITLE not in out and ARCHIVED_TITLE not in out
def test_candidates_dir_never_opened(kbw, monkeypatch): opened = record_opens(monkeypatch); retrieve(kbw, WORDS); assert not any("/docs/wiki/_candidates/" in p for p in opened)
def test_archive_dir_never_opened(kbw, monkeypatch): ...; assert not any("/docs/wiki/_archive/" in p for p in opened)
def test_wiki_line_shows_provenance_and_approver(kbw): assert "根拠: Exp 1・Decision 1・FK 0 / 承認: 小柳(テスト) 2026-10-20 → docs/wiki/" in retrieve(kbw, WORDS)
def test_wiki_summary_truncated_160(kbw): set_summary(kbw, "あ"*200); line = wiki_line(retrieve(kbw, WORDS)); assert "あ"*160 in line and "あ"*161 not in line
def test_wiki_off_disables_only_wiki(kbw): touch(kbw/".claude/wiki.off"); out = retrieve(kbw, WORDS); assert section(out, "[Wiki]") == "- 該当なし" and "[D]" in out
def test_memory_off_disables_wiki_too(kbw): touch(kbw/".claude/memory.off"); r = run_hook(kbw, "SessionStart", PAYLOAD); assert r.stdout.strip() == "{}"
def test_wiki_per_kind_cap_and_budget(kbw): add_approved(kbw, 8); out = retrieve(kbw, WORDS, budget_chars=3000); assert count(out, "- [Wiki]") <= 5 and len(out) <= 3000
def test_synonym_group_matches_either_word(kbw): write_syn(kbw, "マージ, merge"); assert "[FK-002]" in retrieve(kbw, ["merge", "競合"])
def test_synonym_group_counts_once(kbw): s = _select(collect_sources(kbw), ["マージ merge"], synonyms=load_synonyms(kbw)); assert all(x["score"] <= 2 for x in s["failure"])
def test_skill_name_counts_only_for_prompt_terms(kbw):  # 段1(name_terms=[])では名前一致だけの Skill は出ない、段2(指示に名前)では出る
    assert "writing-plans-hojo" not in stage1_with_branch(kbw, "claude/writing-plans-x") and "writing-plans-hojo" in stage2(kbw, "writing-plans の手順")
def test_terms_line_shows_normalized_units(kbw): o = stage2(kbw, "マージ競合の手順を確認したい"); assert "検索語(指示から):" in o and "マージ" in o and "確認したい" not in o
def test_existing_kinds_unchanged_without_wiki(kb): assert strip_wiki_section(retrieve(kb, WORDS)) == PHASE1_EXPECTED  # 既存6区分の行は Phase 1 と同一
def test_bootstrap_runtime_under_500ms_with_wiki(realcopy): add_approved(realcopy, 20); t, r = _timed_hook(realcopy, "SessionStart", PAYLOAD); assert r.returncode == 0 and t < 0.5
```
既存テストで期待値を変えてよいのは、段1で Skill 名一致だけに頼っていたもの(あれば)と、`検索語:` 行の文字列を固定しているものだけ。変える場合は commit 本文にテスト名と理由を書く。

- [ ] **Step 1:** テストを書く → `python3 -m pytest tests/scripts/test_memory_bootstrap.py -q` → 新規15本 FAIL
- [ ] **Step 2:** 実装 → 既存 + 15 passed
- [ ] **Step 3:** 回帰比較: `python3 scripts/memory_bootstrap.py query "WikiSkill 記憶" | diff - .superpowers/sdd/phase2-baseline/bootstrap-baseline.txt` → 差分は `[Wiki]` 見出しと `- 該当なし` の2行だけ(Task 0 Step 4 の保存分と比較)
- [ ] **Step 4:** `touch .claude/wiki.off && git check-ignore -q .claude/wiki.off && echo ignored; rm .claude/wiki.off` → `ignored`
- [ ] **Step 5:** CE1〜CE6 → commit `feat(wikiskill): Bootstrap に [Wiki] 区分 — 承認済みだけを根拠件数・承認者つきで注入。wiki.off・同義語・Skill名一致の限定`

**Acceptance Criteria:** 15テスト合格 / Wiki が無い現状では既存6区分の出力が Phase 1 と同一 / 500ms 以内 / `wiki.off` で `[Wiki]` だけ止まる
**Rollback:** 緊急: `.claude/wiki.off`(この作業コピー)/ `.claude/memory.off`。正式: revert
**Public/Private impact:** 読むのは `docs/wiki/*.md` の approved で visibility がリポの公開性と一致するものだけ。`_candidates/` と `_archive/` は二重に除外
**既存機能への影響:** 出力に区分見出しが1つ増える(Wiki 0件の間は `- 該当なし`)。6,000字予算は共有なので、Wiki が増えると他区分の末尾が削られ得る(`_render` の既存規則: 件数の多い区分・信頼の低い区分から)。段1で Skill 名一致だけで出ていた Skill は出なくなる(持ち越し b の意図どおり)

---

### Task 4: 矛盾検知・Decision 優先・`needs_review`(J)

**目的:** 候補の矛盾(①contradictions ②Decision 否定語)を CONFLICT にし、承認後に新しい Decision と矛盾した Wiki(③)を needs_review にして注入しない。自動統合はしない。
**新規ファイル:** なし
**変更ファイル:** `scripts/wiki_schema.py` / `scripts/wiki_validate.py`(V11〜V13)/ `scripts/knowledge_extract.py`(conflict 付与)/ `scripts/memory_bootstrap.py`(`_wiki` の needs_review 除外)/ 各テスト(追加のみ)

**Interfaces:**
- Produces(`wiki_schema.py`):
  - `conflict_text(w_or_draft: dict) -> str` — `title + " " + summary + " " + sections["## 知識"]`
  - `decision_conflicts(text: str, decisions: list[dict], synonyms: list[frozenset[str]] | None = None, after: str | None = None) -> list[dict]` — `status == "adopted"`・`tags` に `test` を含まない・(`after` 指定時)`date > after` の Decision のうち、`title + outcome` に `NEGATION_WORDS` のどれかを含み、`text` の語(`memory_bootstrap.query_groups`)が Decision 側 `features` に `CONFLICT_MIN_UNITS`(2)以上当たるもの。返り値 `[{"decision": id, "units": [語…]}]`。`memory_bootstrap` は関数内で import(循環 import を避ける)
  - `needs_review(w: Wiki, decisions: list[dict], synonyms=None) -> list[str]` — approved の Wiki について `decision_conflicts(conflict_text(w), decisions, synonyms, after=w["approved_at"])` の id から `acknowledged_decisions` の id を除いたもの
  - 例外は呼び元で「矛盾あり」として扱う(fail-closed)
- Produces(`wiki_validate.py`):
  - V11: `contradictions` 非空 かつ `review_status != "conflict"`(候補)→ 違反
  - V12: `decision_conflicts(after=None)` が非空 → 候補は `review_status == "conflict"` でなければ違反、approved は該当 id がすべて `acknowledged_decisions` に無ければ違反(`acknowledged_decisions` の各要素は `reason` 非空)
  - V13: approved の `needs_review(...)` が非空 → **Warning**(exit は変えない)。CLI は `::warning file=<path>::needs_review <decision_id>` を出す
  - `needs_review_map(root: Path) -> dict[str, list[str]]`(path → decision ids)
- Produces(`knowledge_extract.py`): `finalize` が `decision_conflicts` を見て、該当すれば `review_status = "conflict"` と `contradictions += [{"source": <decision_id>, "note": "Decision が否定(<語>)"}]`。R2 で `学び:` と `失敗:` の note が2語以上共有するとき、両候補の `contradictions` に互いの `candidate_id` を入れ conflict にする
- Produces(`memory_bootstrap.py`): `_wiki` が `wiki_schema.needs_review(w, _decisions_cached(root), synonyms)` 非空の Wiki を出さず、audit に `wiki: needs_review <wiki_id> <decision_id>` を1行

**Tests:**
```python
# tests/scripts/test_wiki_validate.py(追加)
def test_contradictions_require_conflict_status(wk): assert "V11" in codes(edit(wk, contradictions=[{"source": "x", "note": "y"}]))
def test_negation_decision_two_unit_overlap_is_conflict(wk): add_decision(wk, outcome="自動生成物は main へ直接 push しない"); assert "V12" in codes(edit(wk, title="自動生成物の直接 push は速い"))
def test_one_unit_overlap_is_not_conflict(wk): add_decision(wk, outcome="直接 push しない"); assert "V12" not in codes(edit(wk, title="push の速さ"))
def test_non_adopted_or_test_tag_decisions_ignored(wk): add_decision(wk, status="deferred", ...); add_decision(wk, tags=["test"], ...); assert "V12" not in codes(...)
def test_conflict_candidate_cannot_be_approved(wk): make_conflicting(wk); promote(wk); assert "V12" in codes(wk)
def test_acknowledged_decision_allows_approval(wk): make_conflicting(wk); promote(wk, acknowledged_decisions=[{"decision": DID, "reason": "Decision と同じ向き"}]); assert "V12" not in codes(wk)
def test_new_decision_marks_wiki_needs_review_exit0_warning(wk): promote_clean(wk); add_decision(wk, date="2026-11-01", outcome=OPPOSITE); r = run([], cwd=wk); assert r.returncode == 0 and "needs_review" in r.stdout
def test_conflict_check_exception_fails_closed(wk, monkeypatch): monkeypatch.setattr(wiki_schema, "decision_conflicts", boom); assert "V12" in codes(wk)
# tests/scripts/test_memory_bootstrap.py(追加)
def test_needs_review_wiki_not_injected(kbw): add_decision(kbw, date="2026-11-01", outcome=OPPOSITE_TO_APPROVED); assert APPROVED_TITLE not in retrieve(kbw, WORDS) and "needs_review" in audit_text(kbw)
# tests/scripts/test_knowledge_extract.py(追加)
def test_extractor_marks_conflict_and_records_contradiction(ex): add_decision(ex, outcome=FORBID); w = load(run(ex)["written"]); assert any(x["review_status"] == "conflict" and x["contradictions"] for x in w)
def test_opposite_note_prefixes_cross_reference(ex): add_notes(ex, "学び: 直接 push で速く反映", "失敗: 直接 push で事故"); ws = conflicts(run(ex)); assert len(ws) == 2 and all(w["contradictions"] for w in ws)
def test_a_success_b_failure_c_forbidden_c_wins(ex):  # 設計書8章の A/B/C
    seed_abc(ex); s = run(ex); ka, kb_ = by_note(s, "A"), by_note(s, "B")
    assert ka["review_status"] == "conflict" and C_ID in [c["source"] for c in ka["contradictions"]]
    assert not list((ex/"docs/wiki").glob("*.md"))     # 何も正式にならない(自動統合しない)
```

- [ ] **Step 1:** テストを書く → 12本 FAIL
- [ ] **Step 2:** 実装 → 12 passed、Task 1〜3 のテストも再実行して合格
- [ ] **Step 3:** `python3 scripts/wiki_validate.py --selftest` → V11〜V13 の正例・負例が増えて `自己点検OK`
- [ ] **Step 4:** 実データの偽陽性を見る: `python3 scripts/knowledge_extract.py --dry-run --max 10 | python3 -c "import json,sys;print(json.load(sys.stdin)['conflict'])"` → 件数を記録(多すぎれば Task 7 の議事のウタガイに記載。しきい値は変えない)
- [ ] **Step 5:** CE1〜CE6 → commit `feat(wikiskill): 知識の矛盾検知 — Decisionの否定と重なる候補はCONFLICT、新しいDecisionと矛盾したWikiは注入しない`

**Acceptance Criteria:** 12テスト合格 / Decision 追加で CI が止まらない(exit 0 + warning)/ needs_review の Wiki が段1・段2に出ない / A/B/C の例で C が勝つ
**Rollback:** revert(Task 1〜3 の状態に戻る。needs_review が無くなるので、Wiki が承認されている状態で戻すなら同時に `wiki.off`)
**Public/Private impact:** なし(判定は同じリポ内の Decision だけ)
**既存機能への影響:** Decision の追加・変更 PR で `::warning::` が出ることがある(赤にはならない)

---

### Task 5: Gate — CODEOWNERS・昇格手順書・`knowledge-extract.yml`(dispatch → PR)・concurrency

**目的:** 候補 → 正式 の唯一の経路を「人がマージする PR」に固定し、抽出を main へ直 push しない workflow にする。
**新規ファイル:** `.github/CODEOWNERS` / `.github/workflows/knowledge-extract.yml` / `docs/wikiskill/Wiki昇格手順.md`
**変更ファイル:** `tests/scripts/test_wikiskill_workflows.py`(追加)

**Interfaces:**
- `.github/CODEOWNERS`: `docs/wiki/ @takeshikoyanagi9-lab`(1行 + コメント。branch protection の有効化は小柳さんの GitHub 設定 = Gate G1)
- `knowledge-extract.yml` の固定形:
```yaml
name: knowledge-extract
on:
  workflow_dispatch:
    inputs:
      max: { description: "最大候補数", default: "10" }
concurrency: { group: knowledge-extract, cancel-in-progress: false }
permissions: { contents: write, pull-requests: write, issues: write }
jobs:
  extract:
    runs-on: ubuntu-latest
    timeout-minutes: 15
    steps:
      # checkout(fetch-depth: 0)→ setup-python 3.11 → wiki_validate --selftest
      # → RUN_ID=$(date -u +%Y%m%dT%H%M%SZ)-${{ github.run_id }}
      # → python3 scripts/knowledge_extract.py --no-llm --max "${{ inputs.max }}" --run-id "$RUN_ID" > summary.json
      # → python3 scripts/wiki_validate.py(exit 1 なら終了。push しない)
      # → git add docs/wiki/_candidates
      # → ガード: git diff --cached --name-only の全行が docs/wiki/_candidates/ で始まること(違えば exit 1)
      # → 変更なしなら「候補なし」で exit 0
      # → git switch -c "wiki-candidates/$RUN_ID" && git commit && git push origin "HEAD:refs/heads/wiki-candidates/$RUN_ID"
      # → gh pr create --base main --head "wiki-candidates/$RUN_ID" --label wiki-candidate --title "Wiki候補 $RUN_ID(n件)" --body-file <summary + 検証結果 + 手順書へのリンク>
      # failure(): weekly-gakubi と同じ方式で Issue(label knowledge-extract)を起票・更新
```
  - **書かないもの**: `schedule`(Gate G2 まで)/ `push` トリガ / `git push origin main` / `--llm`(Task 10)/ 他リポの checkout
- `docs/wikiskill/Wiki昇格手順.md` の固定内容: ①昇格 PR の作り方(`git mv docs/wiki/_candidates/<id>.md docs/wiki/<slug>.md`、`wiki_id`・`approved_by`・`approved_at`・`review_by`・`review` の書き方、本文 `## 反証(ウタガイ)` は人が確定)②AI は PR を用意してよいがマージしない(branch protection 無効の間は運用上の約束であることを明記)③却下(`rejected` + `rejected_reason`、`_candidates/` に残す)④conflict の解消と `acknowledged_decisions`(**Decision と逆向きの知識は acknowledged にしない**)⑤needs_review の解消(再承認 or `_archive/` へ superseded)⑥抽出 PR のマージは「候補として受領」であり承認ではない ⑦`GITHUB_TOKEN` の PR では CI が自動で走らないので、PR 本文の検証結果を見る(必要なら PR を手で更新して CI を起動)

**Tests:**
```python
# tests/scripts/test_wikiskill_workflows.py(追加。YAML は文字列で検査)
def test_knowledge_extract_is_dispatch_only(): t = read(WF); assert "workflow_dispatch" in t and "schedule:" not in t and "\n  push:" not in t
def test_knowledge_extract_concurrency_group(): assert "group: knowledge-extract" in read(WF) and "cancel-in-progress: false" in read(WF)
def test_knowledge_extract_never_pushes_main(): t = read(WF); assert "push origin main" not in t and "refs/heads/main" not in t and "wiki-candidates/" in t
def test_knowledge_extract_stages_only_candidates(): t = read(WF); assert "git add docs/wiki/_candidates" in t and "git add -A" not in t and "docs/wiki/_candidates/" in guard_step(t)
def test_knowledge_extract_runs_validator_before_pr(): t = read(WF); assert t.index("wiki_validate.py") < t.index("git push") < t.index("gh pr create")
def test_codeowners_covers_docs_wiki(): assert "docs/wiki/ @takeshikoyanagi9-lab" in read(".github/CODEOWNERS")
def test_promotion_doc_paths_resolve(): assert unresolved_doc_paths("docs/wikiskill/Wiki昇格手順.md") == []   # CLAUDE.md 再発防止メモの \S+? 方式
```

- [ ] **Step 1:** テストを書く → 7本 FAIL → 3ファイルを書く → 7 passed
- [ ] **Step 2:** `python3 -c "import yaml" 2>/dev/null && python3 -c "import yaml;yaml.safe_load(open('.github/workflows/knowledge-extract.yml'))" || grep -c "wiki_validate" .github/workflows/knowledge-extract.yml` → 例外なし(yaml 無しの環境では `2` 以上)
- [ ] **Step 3:** CE1〜CE6 → commit `feat(wikiskill): Wiki昇格Gate — CODEOWNERS・昇格手順書・抽出はdispatchでPRのみ(mainへ直pushしない)`

**Acceptance Criteria:** 7テスト合格 / workflow にトリガは dispatch だけ / ステージ対象のガードがある / 手順書の参照パス NG 0
**Rollback:** revert。workflow は dispatch のみなので、実行しなければ何も起きない(GitHub の Disable workflow でも止まる)
**Public/Private impact:** push 前に検証(公開ブランチに違反を載せない)。`GITHUB_TOKEN` はこのリポジトリだけ
**既存機能への影響:** CODEOWNERS は `docs/wiki/` だけ。他のパスのレビュー要件は変わらない(branch protection 未設定なら要件自体が生じない)

---

### Task 6: 持ち越し B 群の残り (g) + 議事 `visibility` キー

**目的:** 旧議事のベッカイ抽出を本来の欄だけに絞る (g)。議事 frontmatter に任意キー `visibility` を足し、検証器が private の Decision を候補の source にさせないようにする。
**新規ファイル:** なし
**変更ファイル:** `scripts/decision_memory.py` / `scripts/wiki_schema.py`(`decision_visibility`)/ `scripts/wiki_validate.py`(V05 が使う)/ `docs/wikiskill/議事frontmatterテンプレート.md` / `tests/scripts/test_decision_memory.py`(追加)

**Interfaces:**
- Produces(`decision_memory.py`):
  - `_bekkai_text(lines: list[str]) -> str` — ①`##`/`###` 見出しが `ベッカイ` で始まればその節 ②無ければ `^\s*[-*・]\s*\**ベッカイ` で始まる最初の行と、それより深く字下げした継続行(`_utagai_continuation` と同じ規則)③どちらも無ければ `""`。`SECTION_MAX` で切る
  - Decision dict に `"visibility": str`(frontmatter の値。無ければ `""`)
  - `check_decision`: `visibility` があり `public` / `private` 以外なら違反
- Produces(`wiki_schema.py`): `decision_visibility(d: dict, root: Path) -> str` — `d["visibility"] or repo_visibility(root)`
- テンプレート: frontmatter 例に `visibility: public   # 任意。既定はリポジトリの公開性(private リポの議事は private)` を1行

**Tests:**
```python
# tests/scripts/test_decision_memory.py(追加)
def test_bekkai_from_heading_section(tmp_docs): d = parse(tmp_docs, "## ベッカイ\n前提を疑う案\n## 裁定\n採用\n"); assert d["bekkai"] == "前提を疑う案"
def test_bekkai_from_bullet_line_and_continuation(tmp_docs): d = parse(tmp_docs, "- **ベッカイ**: 別案\n  - 補足A\n- **裁定**: x\n"); assert "別案" in d["bekkai"] and "補足A" in d["bekkai"] and "裁定" not in d["bekkai"]
def test_bekkai_ignores_incidental_mentions(tmp_docs): d = parse(tmp_docs, "本文でベッカイ案に触れた。\n## 裁定\n採用\n"); assert d["bekkai"] == ""
def test_visibility_key_parsed(tmp_docs): assert parse(tmp_docs, FM.replace("status: adopted", "status: adopted\nvisibility: private"))["visibility"] == "private"
def test_check_rejects_bad_visibility(tmp_docs): assert any("visibility" in e for e in check(tmp_docs, FM.replace("status: adopted", "status: adopted\nvisibility: secret")))
def test_validator_treats_private_decision_as_private_source(wk): add_decision(wk, visibility="private", did="DP"); assert "V05" in codes(edit(wk, source_decision=["DP"]))
```

- [ ] **Step 1:** テストを書く → 6本 FAIL → 実装 → 6 passed
- [ ] **Step 2:** 実データで落ちないこと: `python3 scripts/decision_memory.py --list --json | python3 -c "import json,sys;d=json.load(sys.stdin);print(len(d), sum(1 for x in d if x['bekkai']))"` → 総数は Task 0 時点と同じ、bekkai の件数は減ってよい(本文中の言及を拾わなくなるため)
- [ ] **Step 3:** repo-scope の議事検査相当: `git -c core.quotePath=false ls-files -z 'docs/議事_*.md' 'docs/議事/*.md' | xargs -0 python3 scripts/decision_memory.py --check` → exit 0
- [ ] **Step 4:** CE1〜CE6 → commit `fix(wikiskill): 旧議事のベッカイ抽出を本来の欄に限定・議事に任意キー visibility`

**Acceptance Criteria:** 6テスト合格 / 既存議事が全件読める / 既存の議事検査が緑のまま
**Rollback:** revert
**Public/Private impact:** private と明示した議事を Public の候補の根拠にできなくなる(強化)
**既存機能への影響:** 旧議事の `[D]` 行でベッカイ欄が短くなる・消えることがある(誤った抜き出しが減る方向)。frontmatter の無い議事は従来どおり検査対象外

---

### Task 7: 文書(README・導入議事・決裁キュー・全体マップ・#24 追記・Rollback 手順)

**目的:** 運用者が仕組みを理解して止められるようにし、Phase 2 導入の判断を三名体制の議事として残す。
**新規ファイル:** `docs/議事/議事_YYYYMMDD_WikiSkill_Phase2導入.md`(実施日)/ `docs/wikiskill/Phase2受け入れ記録.md`(空の台帳)/ 設計書と本計画を `docs/superpowers/specs/` `docs/superpowers/plans/` へ(承認時の指示に従う)
**変更ファイル:** `docs/wikiskill/README.md` / `docs/wikiskill/Rollback手順.md` / `docs/議事/議事_20261006_Experience長期保存方式_候補.md` / `docs/決裁キュー.md` / `docs/全体マップ.md` / `CLAUDE.md`(記憶の仕組み節に2行のみ)

**Interfaces:**
- Consumes: `docs/wikiskill/議事frontmatterテンプレート.md`(Task 6 版)
- Produces(導入議事の frontmatter): `decision_id: D<YYYYMMDD>-wikiskill-phase2` / `title: WikiSkill Phase 2 導入(Knowledge Wiki)` / `scope: hojo-hq/基盤` / `tags: [wiki, knowledge, wikiskill, phase2]` / `status: adopted` / `review_by`: 実施日 + 180日 / `visibility: public` / `decided_by: 小柳`
- 導入議事の本文: `## なぜ(背景)`(Experience が知識にならない・同じ失敗の再発)/ `## 前提`(承認は人のみ・Decision > Wiki・Skill に反映しない・public のみ)/ `## 代替案`(LLM 抽出を MVP に入れる案 → 幻覚で却下 / 候補を Bootstrap に低信頼で出す案 → 未承認が判断に混ざるので却下 / Obsidian 側に Wiki を書く案 → 正本は GitHub なので却下)/ `## 三名体制の議論` — スイシン: 既存資産と同じ PR・CI・CODEOWNERS で完結 / **ウタガイ(反対理由)**: ①否定語判定は粗く、偽陽性の conflict がレビュー負債になる ②公開リポではブランチの push 時点で公開されるので、検証器の偽陰性はレビュー前に公開を招く ③承認が小柳さんに集中し、形骸化して「通すだけ」になる → 受け入れ条件: 実行は dispatch のみ・1回10件まで・偽陽性件数を週次で見る・push 前検証 / ベッカイ: そもそも Wiki は要るのか。失敗台帳と再発防止メモで足りるなら、Phase 2 は同義語表と検索語行の改善だけで十分では → MVP の後に [Wiki] の採用件数で再評価 / `## 裁定` / `## 見直し条件`(Rollback 条件 RB1〜RB5 のどれか・3か月で approved 0件・conflict の8割以上が偽陽性)/ `## Rollback`(`docs/wikiskill/Rollback手順.md`)
- README の Phase 2 章: Wiki と候補の違い / `[Wiki]` 行の読み方(根拠件数・承認者)/ 止め方(`.claude/wiki.off` と `.claude/memory.off`)/ 昇格手順書へのリンク / 候補は commit・push 時点で公開されること / 「まだ無いもの」を Phase 3 以降(Skill Validator・Evolution Gate・Conflict Resolver・LLM 下書き)に更新
- Rollback 手順の Phase 2 節: 部分停止(`wiki.off`)/ Wiki 1件の revert / workflow の無効化 / `git revert -m 1 <wikiskill-phase2-v1 のマージコミット>` / 48時間以内の議事(Decision 7)
- #24 議事への追記: 節 `## Phase 2 時点の比較(追記 YYYY-MM-DD)` に設計書10章の比較表と推奨。`status: deferred` は変えない
- 決裁キュー: Gate G1〜G6 を1項目にまとめて追加(議事へのリンク)、#24 の行に「比較表追記済み」
- 全体マップ: `docs/wiki/`・`docs/wikiskill/Wiki昇格手順.md`・Phase 2 設計書と計画の置き場所を1行ずつ
- CLAUDE.md「記憶の仕組み」節に2行: 「承認済みの知識(`docs/wiki/*.md`)は `[Wiki]` として注入。候補(`docs/wiki/_candidates/`)は読まない。部分停止は `.claude/wiki.off`」「Skill の自動更新はしない(Skill の検証・Gate は Phase 3 以降・別承認)」

**Tests:** 文書のため単体テストなし。機械検査のみ:
- `python3 scripts/decision_memory.py --check docs/議事/議事_*_WikiSkill_Phase2導入.md` → exit 0
- 参照パス検査(CLAUDE.md 再発防止メモの `\S+?` 方式)を README・導入議事・昇格手順書・受け入れ記録に掛ける → NG 0
- `python3 scripts/memory_bootstrap.py query "Wiki 候補 昇格"` → `[D]` の上位に導入議事

- [ ] **Step 1:** 導入議事を書く → `--check` exit 0
- [ ] **Step 2:** README・Rollback 手順・#24 追記・決裁キュー・全体マップ・CLAUDE.md を更新
- [ ] **Step 3:** 参照パス検査 → `0`
- [ ] **Step 4:** CE1〜CE6 → commit `docs(wikiskill): Phase 2 導入議事(三名体制)・運用ガイド・Rollback手順・#24に保存方式の比較を追記`

**Acceptance Criteria:** 導入議事が `--check` 合格 / 参照パス NG 0 / Bootstrap の `[D]` に導入議事が出る / #24 は deferred のまま
**Rollback:** revert
**Public/Private impact:** 文書に private リポの内容・顧客情報・禁止語を書かない(CE2)
**既存機能への影響:** 導入議事が Bootstrap の `[D]` 候補に加わる(本物の決定なので意図どおり)

---

### Task 8: E2E(自動 順方向 + 逆方向、実セッション A→B 手動、受け入れ記録)

**目的:** 「Session A の経験 → 候補 → 検証 → 人の承認 → Session B が知識と信頼の理由を受け取る」と、「誤った経験 → 候補 → Decision と矛盾 → 正式にならず注入されない」を、自動と実セッションの両方で確認する。
**新規ファイル:** `tests/integration/test_wikiskill_wiki_e2e.py`
**変更ファイル:** `docs/wikiskill/Phase2受け入れ記録.md`(記入)/ `.github/workflows/wikiskill-tests.yml`(E2E を一覧に追加)

**Interfaces:**
- Consumes: Task 0b〜7 のすべて。hook は Phase 1 の `world` / `world_private` fixture と `hook()`(`wikiskill-hook.sh` を Claude Code と同じ stdin JSON で呼ぶ)を再利用。`_build_world` の複製対象に `scripts/wiki_schema.py` `wiki_validate.py` `knowledge_extract.py` `wikiskill_lock.py` と `docs/wiki/_synonyms.txt` を足す(fixture 側の `SCRIPT_NAMES` に追加)
- 人の承認はテスト内で frontmatter の編集と `git mv` で模擬する(`approved_by: 小柳(テスト)`)

**Tests:**
```python
# tests/integration/test_wikiskill_wiki_e2e.py
def test_forward_session_a_to_wiki_to_session_b(world):
    hook(world, "SessionStart", sid="A", source="startup")
    note(world, "A", "学び: 生成物を作り直す前に origin/main を取り込むと、新しいデータを消さずに済む")
    hook(world, "SessionEnd", sid="A", reason="exit"); git(world, "add", "-A"); git(world, "commit", "-m", "chore: experience A")
    s = extract(world); cid = Path(s["written"][0]).stem; assert validate(world).returncode == 0          # F2, F3
    promote(world, cid, utagai=""); assert validate(world).returncode == 1                                  # F4(ウタガイ空は通らない)
    promote(world, cid, utagai="データが少ないうちは例外が多い", approved_by="小柳(テスト)", approved_at="2026-10-20")
    assert validate(world).returncode == 0; git(world, "add", "-A"); git(world, "commit", "-m", "docs: wiki 昇格")  # F5
    ctx = context(hook(world, "SessionStart", sid="B", source="startup"))
    assert ctx.index("[再発防止]") < ctx.index("[Wiki]") < ctx.index("[Skill]")                              # F6
    assert "根拠: Exp 1・Decision 0・FK 0" in ctx and "承認: 小柳(テスト) 2026-10-20" in ctx and "→ docs/wiki/" in ctx  # F7
def test_reverse_wrong_experience_conflict_never_injected(world):
    commit_decision(world, outcome="自動生成物は main へ直接 push しない。必ず PR を通す")                   # C
    session_with_note(world, "A", "学び: 自動生成物を main へ直接 push したら当日中に反映できた")           # A(誤り)
    w = load(extract(world)["written"][0]); assert w["review_status"] == "conflict"                          # R2
    promote(world, w["candidate_id"], utagai="x"); assert validate(world).returncode == 1; undo_promote(world)  # R3
    ctx = context(hook(world, "SessionStart", sid="B", source="startup")) + stage2(world, "B", "直接 push の手順")
    assert "当日中に反映" not in ctx and not list((world/"docs/wiki").glob("*.md"))                           # R4
def test_candidate_never_injected_before_approval(world): session_with_note(world, "A", "学び: 固有語ZQX の手順"); extract(world); commit_all(world); assert "ZQX" not in context(hook(world, "SessionStart", sid="B", source="startup"))
def test_wiki_off_partial_stop_keeps_other_kinds(world): seed_approved(world); (world/".claude/wiki.off").touch(); ctx = context(hook(world, "SessionStart", sid="C", source="startup")); assert section(ctx, "[Wiki]") == "- 該当なし" and session_recorded(world, "C")   # F8
def test_needs_review_after_new_decision_stops_injection(world): seed_approved(world); commit_decision(world, date="2026-11-01", outcome=OPPOSITE); assert validate(world).returncode == 0 and APPROVED_TITLE not in context(hook(world, "SessionStart", sid="D", source="startup"))  # R5
def test_private_world_extracts_nothing_public(world_private): session_with_note(world_private, "P", "学び: 非公開側の気づき"); s = extract(world_private); assert all(load(p)["visibility"] == "private" for p in s["written"])  # 公開側へ書く経路が無い
```
R6(private 行だけの Experience は数えない)は Task 2 `test_private_and_unknown_rows_not_counted` が担う。

- [ ] **Step 1:** 自動 E2E を書く → `python3 -m pytest tests/integration/test_wikiskill_wiki_e2e.py -q` → 6 passed(落ちたら該当 Task に戻り、その Task のテストも再実行)
- [ ] **Step 2:** 全体: `python3 -m pytest tests/scripts tests/integration -q | tail -1` → Task 0 で固定した Phase 1 テスト ID が全て PASS + Phase 2 で追加した新規テストが全て PASS(新規テスト数は受け入れ記録に実数を記す。合計件数の固定値は合格条件にしない)/ failed は Baseline の2件のみ。`python3 scripts/wiki_validate.py && python3 scripts/check_experience_privacy.py` → OK / OK
- [ ] **Step 3:** CE1〜CE6 → commit `test(wikiskill): Phase 2 E2E — 経験が承認を経てWikiになり別セッションへ届く/誤った経験は矛盾で止まり注入されない` → `git push -u origin claude/superpowers-per-chat-3mbx56`
- [ ] **Step 4:** 実セッション E2E(必須)。`docs/wikiskill/Phase2受け入れ記録.md` に記入:
  1. **Session A**(このブランチ): `python3 scripts/experience_log.py note "学び: <試験用の短い文>"` → `.claude/experience` を commit・**push** → 終了
  2. 抽出: Actions で knowledge-extract を dispatch(またはローカルで `--max 3`)→ 候補 PR(または差分)を確認 → 検証結果が緑
  3. 昇格: 候補の1件を手順書どおり昇格(試験用であることを `tags` ではなく `title` 先頭の「受け入れ試験:」で示し、試験後に `_archive/` へ superseded)→ commit・push
  4. **Session B**(完全に新しいセッション): 段1に `[Wiki] 受け入れ試験: …` と `根拠:` `承認:` が出ること。conflict の候補(逆方向)が出ないこと
  5. `.claude/wiki.off` を置いて Session C: `[Wiki]` だけ止まり、他区分と記録は動くこと。消して戻す
  6. 記入項目: 実施日時 / session_id(A, B, C)/ F1〜F8・R4 の ✅❌ / Session B の注入テキスト(`[Wiki]` 行の前後20行)/ SessionStart の所要時間(`_audit.log` の `slow` の有無)/ Baseline 比較の出力 / 所見
- [ ] **Step 5:** 試験用の Wiki を `_archive/` へ移し、受け入れ記録と一緒に commit・push(試験用の知識を本物として残さない。Phase 1 所見7と同じ扱い)

**Acceptance Criteria:** 自動 E2E 6本合格 / 実セッションで F1〜F8・R4 がすべて ✅ / Session B の注入テキストに「何を知っているか」(title・summary)と「なぜ信頼しているか」(根拠件数・承認者・承認日・パス)が出ている / 既存テスト・既存 CI に回帰なし
**Rollback:** ❌ が出たら PR をマージせず該当 Task に戻る(main は未変更)
**Public/Private impact:** 実セッション試験は hojo-hq のみ。試験の note に顧客情報・private の内容を書かない
**既存機能への影響:** なし(試験用 Wiki は `_archive/` へ移して注入されない状態で終える)

---

### Task 9: PR・小柳 Gate・マージ・タグ(STOP 前提)

**目的:** Phase 2 を1つの PR で小柳さんの Decision Gate に上げる。**承認が出るまでマージしない**。
**Release/Tag は小柳さん最終承認後のみ。報告項目 A〜O(実装結果/全テスト/Phase 1 Regression/Phase 2 E2E/逆方向 CONFLICT E2E/Privacy/Provenance/Baseline/変更ファイル/新規ファイル/Rollback/残課題/Phase 3 持ち越し/PR 番号/Release 候補タグ)を報告して STOP。**
**新規ファイル:** なし / **変更ファイル:** なし(Git / GitHub 操作。マージ後に `docs/wikiskill/Rollback手順.md` へマージコミットを追記)

**Interfaces:** Produces: PR(タイトル `WikiSkill Phase 2: Knowledge Wiki(Candidate → Validation → Human Approval → Official Wiki)`)、マージ後のタグ `wikiskill-phase2-v1`

- [ ] **Step 1:** Rollback 実演(作業ブランチ上): `touch .claude/wiki.off && python3 scripts/memory_bootstrap.py query "Wiki" | grep -A1 "\[Wiki\]"; rm .claude/wiki.off` → `- 該当なし`。使い捨てブランチで `git revert --no-commit origin/main..HEAD` → `git diff origin/main --stat` が空 → 使い捨てブランチを削除
- [ ] **Step 2:** PR を作る(PR テンプレートがあれば従う)。本文: 設計書の要点 / File Structure / **変えていないもの**(Skills・commands・update-skills.sh・agents・hooks・settings.json)/ E2E 結果(受け入れ記録へのリンク)/ Baseline 比較 / Rollback 手順と条件 / Gate 項目 G1〜G6 / 導入議事へのリンク。CI: repo-scope(Wiki 検査ステップを含む)と wikiskill-tests が緑(置き場所の検査は Baseline の9件のみ赤)
- [ ] **Step 3: STOP** — 小柳さんの判断を待つ。G1(CODEOWNERS + branch protection)・G5(Obsidian)は GitHub 設定・連携メモで小柳さん側が行う
- [ ] **Step 4:** 承認・マージ後: `git fetch origin main && git tag -a wikiskill-phase2-v1 -m "WikiSkill Phase 2 Knowledge Wiki" origin/main && git push origin wikiskill-phase2-v1` → Rollback 手順書にマージコミットの hash を追記して commit(別 PR)

**Acceptance Criteria:** 小柳さんの承認でマージ / タグが存在 / revert 実演の結果が PR に残っている
**Rollback:** マージ前なら PR をクローズ。マージ後は `docs/wikiskill/Rollback手順.md` の Phase 2 節
**Public/Private impact:** PR 本文に private リポの内容・顧客情報を書かない
**既存機能への影響:** マージ時点では `docs/wiki/` は空(試験用は `_archive/`)。`[Wiki]` は「該当なし」から始まる

---

### Task 10(実施禁止・G3 不承認)

小柳さん Decision G3(2026-10-07)により Phase 2 では実装しない。将来の別 Decision 後に別計画とする。

---

## Phase 2 全体の Acceptance Criteria / Rollback 条件

**Acceptance Criteria(すべて満たすこと)**
1. Phase 1 由来の既存テスト(2026-10-07 時点 347 件・ID は Task 0 で固定)に回帰なし + Phase 2 で追加した新規テストが全て PASS(Task 0b〜8 で追加したもの。failed は Baseline の scripts tests 2件のみ)
2. E2E 順方向(F1〜F8)・逆方向(R1〜R6)が自動で合格し、実セッション A→B で F1〜F8・R4 が ✅
3. Session B の注入テキストが「何を知っているか」と「なぜ信頼しているか(Provenance の件数・承認者・承認日・パス)」を示す
4. `docs/wiki/_candidates/` を Bootstrap が開かない(テストで固定)。候補は人の PR 以外で approved にならない
5. Decision と矛盾する Wiki は注入されない(needs_review)。新しい Decision の PR は Wiki のせいで赤にならない
6. 抽出器の入力に private・unknown・未 commit の Experience が入らない。Private → Public の自動経路が無い(設計書9章 + テスト)
7. Bootstrap 段1・段2 とも 500ms 以内
8. `baseline_debt.py --compare` が SAME / 禁止語 0 / 変更禁止リストの差分 0
9. 導入議事が三名体制(ウタガイ反対理由つき)で `decision_memory.py --check` 合格
10. `.claude/wiki.off` で `[Wiki]` だけ止まり、`git revert -m 1` で全戻しが実演済み

**Rollback 条件(1つでも該当 → 守り部が緊急停止 → 小柳 Gate で正式判断)**
- RB1 検証器の偽陰性で、誤った知識が approved に入った
- RB2 Private 由来のテキストが候補(PR・ブランチを含む)に出た
- RB3 Bootstrap 500ms 超(`_audit.log` の `slow`)が週3回
- RB4 `baseline_debt.py --compare` が REGRESSION
- RB5 Decision と矛盾する Wiki が注入された

**Phase 2 で作らないもの(再掲)**: Skill Proposer / Skill Validator(Regression)/ Skill Evolution Gate / Skill への反映 / Conflict Resolver(自動統合)/ Skill Metrics / Experience の移動・索引(#24 決裁後)/ 月次 cron(G2)/ LLM 下書き(Task 10・G3)/ main 直 push / クロスリポ読込。110 Skills・13リポ配布方式・`.claude/commands/`・hooks・settings.json は不変。

---

## Self-Review(計画作成時に実施)

1. **Spec coverage**: 設計書の B → Task 2(R1〜R4・重複・書込先)/ G → Task 1(V01〜V10・V14・V15)+ Task 4(V11〜V13)/ H → Task 5(CODEOWNERS・手順書・dispatch→PR)/ J → Task 4(CONFLICT・needs_review・A/B/C)/ L → Task 2(lock)+ Task 5(concurrency・1 PR = 1 run)+ Task 1(`candidate_id` 一意 V02)/ Bootstrap[Wiki] → Task 3 / Privacy → Task 1(V05・V06)・Task 2(入力フィルタ)・Task 5(push 前検証)・Task 6(議事 visibility)/ Rollback → Task 3(wiki.off)・Task 7(手順)・Task 9(実演)。持ち越し A(d,e,f)→ Task 0b、B(a,b,c)→ Task 3、(g)→ Task 6、#24 → Task 7、C(#22・#23)→ 対象外。MVP(設計書12章)= Task 0〜9、LLM は Task 10 に後置。E2E 順方向・逆方向 → Task 8。
2. **Step scan**: 各 Task は 目的 / 新規ファイル / 変更ファイル / Interfaces / Tests / Acceptance Criteria / Rollback / Public-Private impact / 既存機能への影響 を持ち、Step は「テスト → 失敗確認 → 実装 → 合格 → CE → commit」。実装本体のコードは書いていない(signature・固定値・テストの assert から一意に決まる)。
3. **Type consistency**: `Wiki`(Task 1)・`Inputs` / `Draft`(Task 2)・`Source`(Phase 1)のキー名を全 Task で同一に使用(`review_status`・`source_experience`・`approved_by`・`approved_at`・`acknowledged_decisions`・`visibility`)。Experience の参照形式 `session-<sid>@<ts>` は Task 1 の `EXP_SOURCE_RE` と Task 2・8 で同一。
4. **Review Focus**: 7項目すべてに担当 Task とテスト名を割り当て済み。
5. **Reuse**: Phase 1 の `load_decisions` / `group_session_files` / `_read_events` / `repo_slug` / `PUBLIC_REMOTES` / `query_units` / `_unit_matches` / `features` / `KINDS` / `COLLECTORS` / `_src` / `_select` / `_render` / `find_content_violations` / fixture `kb` `realcopy` `world` `world_private` `hook()` を再利用し、二重実装しない。`_read_session_events` は作業ツリーの全ファイル(未追跡を含む)を読むため、抽出器・検証器では使わず、git 管理下のファイルだけを `_read_events` で読む。
6. **Proportion**: 設計書(約700行)に対し本計画は約700行。コードブロックはテストの assert・workflow の固定形のみ。

---

## 実装への遷移(停止点)

本計画は **小柳さんのレビュー待ち** で停止する。実装は開始しない。承認後の実行方法:

- **Subagent-driven**(推奨): Task ごとに新しい subagent が実装し、別の reviewer が検査してから次へ。検証器の偽陰性が最大のリスクなので、Task 1・4 は reviewer に負例の追加を必ず依頼する
- **Native**: 本セッションが全 Task を順に実装し、最後に1回レビュー

承認時に併せて決めること: 設計書と本計画を `docs/superpowers/specs/` / `docs/superpowers/plans/` へ置くか(Task 7 の commit に含める)、Gate G1〜G6 のうち PR 前に決めるもの(少なくとも G1)。
