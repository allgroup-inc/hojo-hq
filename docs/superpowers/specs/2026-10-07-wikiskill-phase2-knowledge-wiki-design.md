# WikiSkill Phase 2 設計書: Knowledge Extraction → Wiki Candidate → Validation → Human Approval → Official Wiki

## v1.1 承認(2026-10-07 小柳さん Decision Gate)

小柳さんが 2026-10-07 に Gate G1〜G6 を次のとおり決裁した。本節が本設計書の最上位の決定であり、以降の本文・15章の「AI 推奨」より優先する。

| Gate | 決裁 |
|---|---|
| G1 | CODEOWNERS + branch protection **承認**。Official Wiki への昇格は小柳 Gate 必須。GitHub の branch protection を権限上自動設定できない場合は、他の手段で代替せず、必要な設定を報告して STOP |
| G2 | 抽出 workflow は `workflow_dispatch` のみ承認。**定期自動実行(cron・schedule)は禁止**。実運用実績ができた後に別 Decision で再検討 |
| G3 | LLM 下書きは Phase 2 MVP で**不承認**。Task 10 は実装しない。規則ベースのみ |
| G4 | Experience の保存方式は Phase 2 では現状維持。Phase 3 で「Raw 別ストレージ + Git には索引・Decision・Official Wiki」を中心案に再検討する。今回は Decision と比較資料まで |
| G5 | `docs/wiki/` の Obsidian 同期は許可。Official Wiki と Candidate を明確に区別し、`_candidates/` を Claude / Bootstrap が正式知識として利用してはならない。Bootstrap が使えるのは原則 `review_status: approved` の Official Wiki のみ |
| G6 | Phase 2 実装開始を承認。Task 0 → 0b → 1 → … → 9 の順で進める。Task 10 は禁止 |

### 最重要ルール

1. Experience から Candidate を自動生成してよい
2. Candidate から Official Wiki への**自動昇格は禁止**
3. Decision との矛盾は必ず CONFLICT とし、AI が勝手に解消しない
4. 信頼階層は Decision > 失敗台帳 > 再発防止 > Official Wiki > Candidate > Experience
5. Private から Public への自動経路を作らない
6. Provenance(出典)の無い Knowledge は昇格させない
7. 110 Skills・13リポ配布方式・`scripts/update-skills.sh`・`.claude/commands/` は変更しない
8. Skill の自己改善はしない

### STOP 条件

次のいずれかが起きたら、作業を止めて小柳さんへ報告する。

- Privacy Boundary の悪化
- Private から Public への経路の発生
- Decision との矛盾
- Baseline の悪化
- Phase 1 テストの回帰
- Provenance の欠落
- Candidate の自動昇格
- 110 Skills の変更
- 13リポ同期の変更
- `scripts/update-skills.sh` の変更
- `.claude/commands/` の変更
- Skill 自己改善の混入

**作成日**: 2026-10-06 / **版**: v1.0(起案)
**段階**: 設計(小柳さんレビュー待ち)。実装は未着手。実装計画は別紙 `docs/superpowers/plans/2026-10-07-wikiskill-phase2-knowledge-wiki.md`
**対象**: hojo-hq(公開リポジトリ)のみ。13配布リポジトリ・110 Skills・`.claude/commands/**`・`scripts/update-skills.sh` は対象外(不変)
**上位文書**: `docs/superpowers/specs/2026-10-06-wikiskill-integration-design.md`(v1.1)の B / G / H / J / K / L 節と Phase 2〜3
**決定者**: 小柳さん
**最優先の原則**: 誤った知識を正式知識にしないこと(正しい知識を取りこぼすより、誤った知識を通す方が重い)

---

## 0. この設計書の読み方

| 節 | 内容 |
|---|---|
| 1〜4 | 現状・目的・信頼階層・全体フロー |
| 5〜6 | 置き場所と Candidate / Wiki の schema |
| 7 | コンポーネント別設計(B / G / H / J / L / Bootstrap[Wiki] / Privacy / Rollback) |
| 8〜9 | Knowledge Conflict の具体例、Private→Public 自動経路が無いことの証明 |
| 10〜11 | Experience 長期保存の比較(#24)、Phase 1 持ち越しの分類 |
| 12〜13 | MVP と E2E 受け入れ基準 |
| 14〜16 | Top 5 Risks、小柳 Decision Gate 項目、ファイル一覧 |

上位文書 v1.1 の Phase 2 は「Knowledge Extractor + Skill Validator + Evolution Gate + Lock」だった。本設計では小柳さん指示に従い、**Phase 2 の G と H は「知識」に対する Validator と Gate** と読み替える。Skill を対象にした Validator(Regression 比較)と Evolution Gate は Phase 3 以降に送る(2章 非目的)。

---

## 1. 現状(Phase 1 の到達点と制約)

### 1.1 到達点(2026-10-06 小柳さん正式承認)

| 項目 | 状態 | 根拠 |
|---|---|---|
| Experience Logger | 稼働。`.claude/experience/YYYY-MM/session-<sid>.jsonl`(commit 後は `.part<N>.jsonl`) | `scripts/experience_log.py` |
| Decision Memory | 稼働。議事 frontmatter + 旧形式ヒューリスティック。`--check` が CI | `scripts/decision_memory.py`(`load_decisions`) |
| Memory Bootstrap | 稼働。段1(SessionStart)/ 段2(最初の指示)。6区分 `KINDS`・`COLLECTORS` | `scripts/memory_bootstrap.py` |
| Privacy Boundary | 稼働。`check_experience_privacy.py`(`PUBLIC_REPO`・`find_content_violations` を import) | repo-scope CI |
| Rollback | `.claude/memory.off` / `HOJO_MEMORY_OFF=1` / `git revert -m 1`(タグ `wikiskill-phase1-v1`) | `docs/wikiskill/Rollback手順.md` |
| 受け入れ | Session B で Decision・なぜ・前提・ウタガイ・見直し期限・FK・再発防止の復元成功。SessionStart 0.371秒。自動テスト 347件 Green。Baseline SAME(9/5/2) | `docs/wikiskill/Phase1受け入れ記録.md` |

### 1.2 制約(Phase 2 がそのまま引き継ぐもの)

| # | 制約 | Phase 2 への含意 |
|---|---|---|
| C1 | 本リポジトリは **PUBLIC**。commit した内容は履歴から消せない | 候補(Candidate)も commit した時点で公開される。候補の段階から公開可能性を検査する |
| C2 | Bootstrap は **root 内しか読まない**(`_inside`・`_git_ready`) | Wiki もこのリポジトリ内のファイルだけ。クロスリポ読込なし |
| C3 | Bootstrap の性能目標 500ms(実測 0.25〜0.4秒) | `[Wiki]` 追加後も 500ms 以内。Decision の読み込みは1回に共有する |
| C4 | Experience は「低信頼」。commit されたものしか他セッションから見えない | 抽出器は **commit 済み**の Experience だけを入力にする(作業ツリーの未追跡ファイルは読まない) |
| C5 | Baseline Debt(privacy 9 / skill_validation 5 / scripts tests 2)は別タスクで是正(#22) | Phase 2 は `baseline_debt.py --compare` が SAME であることを各 Task の終了条件にする |
| C6 | weekly-gakubi が生成物を **main へ直 push** し、禁止語を含む `学び_2026-W41` が公開された(FK-006 の一因) | 抽出器は main へ直 push しない。必ず PR を作り、CI 検証器と人が見る |
| C7 | 同期: `docs/**/*.md` は毎朝 Obsidian へ写る(`docs/Obsidian連携ガイド.md`) | `docs/wiki/` と `docs/wiki/_candidates/` も自動で Obsidian に写る(Gate 項目) |
| C8 | `.claude/commands/**` と `scripts/update-skills.sh` は13リポへ同期される | Phase 2 はどちらも触らない。Skill への反映も一切しない |

### 1.3 Phase 1 の受け入れで見つかった課題(持ち越し)

11章の分類表で扱う。要点: 同義語が無いので「マージ」と「merge」が別語になる (a)、Skill 名一致が段1でも1語に数えられる (b)、段2の検索語行が読めない (c)、`_is_tracked` が git エラーと未追跡を区別しない (d)、`~` 始まりパスの扱い (e)、wikiskill-tests の paths 不足 (f)、旧議事のベッカイ抽出が広すぎる (g)。

---

## 2. 目的と非目的

### 2.1 目的

```
Raw Experience ─▶ Knowledge Extraction ─▶ Wiki Candidate ─▶ Validation ─▶ Human Approval ─▶ Official Wiki
                                                                                              │
                                                                         新セッションの Bootstrap に [Wiki] として注入
```

| # | 目的 | 測り方 |
|---|---|---|
| P1 | Experience・Decision・失敗台帳から「再利用価値のある知識」の候補を機械で作る | 抽出器が候補を出し、検証器を通る |
| P2 | 候補を正式知識にするのは **人の承認だけ** にする | `docs/wiki/` 直下の approved はすべて人の `approved_by` と非空ウタガイを持つ |
| P3 | 正式知識には「なぜ信頼しているか」(Provenance・承認者・承認日)を必ず付ける | Bootstrap の `[Wiki]` 行に 根拠件数と承認者・承認日が出る |
| P4 | Decision と矛盾する知識は正式にしない。正式化後に矛盾した知識は注入しない | 検証器の CONFLICT / needs_review、E2E 逆方向テスト |
| P5 | Private 由来のテキストが Public の知識になる自動経路を構造的に持たない | 9章の証明と CI |

### 2.2 非目的(Phase 2 では作らない・やらない)

| 非目的 | 理由 |
|---|---|
| **Skill の自己改善・自動更新** | 小柳さん指示で禁止。Skill Proposer / Skill Validator(Regression 比較)/ Skill Evolution Gate は Phase 3 以降・別承認 |
| Wiki から Skill への反映(SKILL.md の書き換え、`related_skills` を根拠にした変更) | 同上。`related_skills` は参照の記録のみ |
| 候補の自動承認・自動マージ | P2。AI は昇格 PR を **用意してよいがマージできない** |
| 矛盾の自動統合(新しい方を自動採用する Conflict Resolver) | Phase 3。Phase 2 は「検知して人に回す」だけ |
| 全 Wiki の注入 | Phase 1 修正2「関連するものだけ」を継承 |
| クロスリポの知識統合 | C2・Decision 5「迷ったら Private」 |
| Experience 保存方式の変更 | #24 で決裁。Phase 2 では比較と推奨のみ(10章) |
| LLM 下書きを MVP に含めること | 幻覚リスク。MVP は規則ベース(`--no-llm`)のみ。LLM は後置 Task・Gate 項目 |

---

## 3. 信頼階層

```
高 ┃ Decision(議事・小柳決裁)              … 人が書き、ウタガイ反対理由つき。常に最上位
   ┃ 失敗台帳(docs/失敗台帳.md)             … ニドナシ機構が真因まで確認した失敗
   ┃ 再発防止メモ(CLAUDE.md 末尾)           … 2度起きたミスの1行ルール
   ┃ Official Wiki(docs/wiki/*.md, approved) … 抽出 → 検証 → 人が承認した知識   ← Phase 2 で新設
   ┃ Wiki Candidate(docs/wiki/_candidates/)  … AI/規則が作った未承認の候補。Bootstrap は読まない
低 ┃ Experience(.claude/experience/)        … 機械記録。単独では判断根拠にしない
```

| 規則 | 内容 |
|---|---|
| T1 | 上位と矛盾する下位は、下位が負ける。Wiki が Decision と矛盾したら Wiki を注入しない(needs_review) |
| T2 | Candidate は「知識」ではない。Bootstrap・Skill・他の自動処理の入力にしない |
| T3 | Official Wiki は失敗台帳・再発防止メモより下。Wiki が失敗台帳を「上書き」することは無い(重複はあり得る。重複検知で抑える) |
| T4 | AI 同士・規則同士の一致は断定の必要条件であって十分条件ではない(CLAUDE.md マルチAI連携の原則を知識にも適用) |
| T5 | Bootstrap の出力順はこの順。`[Wiki]` は `[再発防止]` の後・`[Skill]` の前 |

---

## 4. 全体フロー図(テキスト)

```
 [Session 群]                          [GitHub Actions: knowledge-extract.yml(workflow_dispatch)]
   │ hook(Phase 1)                         │ concurrency: knowledge-extract
   ▼                                        ▼
 .claude/experience/**.jsonl ─commit─▶ (1) 入力の絞り込み(機械的)
 docs/議事_*.md, docs/議事/*.md ──────▶     visibility==public かつ repo==allgroup-inc/hojo-hq の行のみ
 docs/失敗台帳.md(FK 行)───────────▶     Decision は status adopted/deferred、visibility!=private
 (任意)docs/学び/*.md ────────────────▶     学びは evidence 専用(単独の根拠にしない)
                                            │
                                            ▼
                                       (2) 規則ベース抽出(決定的・AI なし)R1〜R4
                                            │   (後置・任意)(2') LLM 下書き --llm
                                            ▼
                                       (3) 重複排除(dedup_key)・矛盾の事前判定(conflict 付与)
                                            │
                                            ▼
                                       (4) docs/wiki/_candidates/<candidate_id>.md を書く(ここ以外に書かない)
                                            │
                                            ▼
                                       (5) wiki_validate.py(同じジョブ内で実行。exit 1 なら PR を作らない)
                                            │
                                            ▼
                                       (6) ブランチ wiki-candidates/<run_id> に commit → PR(1 PR = 1 抽出実行)
                                            │        ※ main へ直 push しない
                                            ▼
 [人: 統括・検証部・守り部]            (7) PR レビュー → マージ = 「候補として受領」(承認ではない)
                                            │
                                            ▼
 [人 or AI が用意 / 人だけがマージ]    (8) 昇格 PR: git mv _candidates/<id>.md docs/wiki/<slug>.md
                                            │   review_status: approved / approved_by / approved_at / review_by / review(ウタガイ必須)
                                            ▼
                                       (9) CI: repo-scope の wiki_validate ステップ + CODEOWNERS(docs/wiki/ → 小柳さん)
                                            │
                                            ▼
                                     (10) main の docs/wiki/<slug>.md(Official Wiki)── docs 同期 ──▶ Obsidian
                                            │
                                            ▼
 [次の Session]                      (11) Memory Bootstrap: KINDS の wiki 区分(approved のみ・needs_review を除く)
                                            "- [Wiki] <title> — <summary> / 根拠: Exp n・Decision m・FK k / 承認: <誰> <日付> → <path>"

 [逆流の監視] 新しい Decision が main に入る ─▶ wiki_validate が approved Wiki との矛盾を検知
                                            ─▶ needs_review(派生状態)→ Bootstrap は注入しない → 人が再承認 or superseded
```

---

## 5. 置き場所

| 対象 | パス | Git | Bootstrap | 書く主体 | 備考 |
|---|---|---|---|---|---|
| Official Wiki | `docs/wiki/<slug>.md` | 管理 | **読む**(approved のみ・直下のみ・非再帰) | 人(昇格 PR) | 直下に置けるのは `review_status: approved` だけ |
| Wiki Candidate | `docs/wiki/_candidates/<candidate_id>.md` | 管理 | **絶対に読まない** | 抽出器(PR 経由) | `review_status: candidate / conflict / rejected` |
| 置き換え済み Wiki | `docs/wiki/_archive/<slug>.md` | 管理 | 読まない | 人(PR) | `review_status: superseded`。Provenance のため残す |
| 同義語表 | `docs/wiki/_synonyms.txt` | 管理 | 読む(`query_units` の展開) | 人(Official Wiki と同じ承認経路) | 1行1グループ `マージ, merge`。持ち越し (a) の解 |
| 部分停止スイッチ | `.claude/wiki.off` | **git-ignored** | 存在すれば `[Wiki]` だけ止める | 守り部・利用者 | `.claude/memory.off` は全停止(既存) |
| 抽出ロック | `.claude/locks/knowledge-extract.lock` | git-ignored(既存の `.claude/locks/`) | — | 抽出器(ローカル実行時) | Decision 8 |
| 昇格手順書 | `docs/wikiskill/Wiki昇格手順.md` | 管理 | 読まない(議事ではない) | 人 | `docs/wiki/` 直下に README を置かない(直下は approved のみ) |
| ディレクトリ維持 | `docs/wiki/_candidates/.gitkeep` | 管理 | — | Phase 2 PR | `.md` ではないので検証器・Bootstrap の対象外 |

**命名規則**: `_` で始まるファイル・ディレクトリは Bootstrap も検証器の「Official 判定」も対象外。Bootstrap の glob は `docs/wiki/*.md` だけ(`docs/wiki/**` を使わない)なので、`_candidates/` と `_archive/` は glob の構造上入らない。加えて `_wiki` 収集関数は相対パスが `docs/wiki/_` で始まるものを捨てる(二重の歯止め)。

---

## 6. Candidate・Wiki schema

### 6.1 frontmatter の書式

- 1行1キー。値は **スカラー** か **1行の JSON**(配列・オブジェクト)。JSON の flow 形式は YAML としても正しいので Obsidian の Properties でも読める
- 標準ライブラリだけで読む(`json.loads`)。入れ子の YAML ブロックは使わない(`decision_memory.parse_frontmatter` は入れ子に対応しないため、Wiki 用に `wiki_schema.parse_wiki_frontmatter` を別に持つ)
- 読めない frontmatter は「schema 違反」(検証器 exit 1)。黙って空扱いにしない

### 6.2 キー一覧

| キー | 型 | 必須 | 候補 | 承認後 | 規則 |
|---|---|---|---|---|---|
| `candidate_id` | str | ○ | ○ | ○(残す) | `K<YYYYMMDD>-<slug>-<4hex>`。4hex = `dedup_key` の先頭4桁。ファイル名(候補)と一致 |
| `wiki_id` | str | 承認時 | — | ○ | `W<YYYYMMDD>-<slug>`(昇格日)。ファイル名は `<slug>.md` |
| `title` | str | ○ | ○ | ○ | 80字以内 |
| `summary` | str | ○ | ○ | ○ | **200字以内**。Bootstrap は先頭160字を出す |
| `source_experience` | list[str] | △ | | | `session-<sid>@<ts>`(行の ts)。commit 済み・public 行に解決できること |
| `source_decision` | list[str] | △ | | | `decision_id`(旧議事は `legacy:<stem>`)。`load_decisions` で解決 |
| `source_failure` | list[str] | △ | | | `FK-xxx`。`docs/失敗台帳.md` の行に解決 |
| `evidence` | list[{ref, quote}] | ○ | ○ | ○ | 1〜10件。`quote` 200字以内・**参照先の本文に逐語で含まれる**こと |
| `confidence` | float | ○ | ○ | ○ | 0.0〜1.0。昇格の可否には使わない(表示と並び順のみ) |
| `confidence_basis` | str | ○ | ○ | ○ | 例 `rule=R3 / FK 1件(真因確認済み)/ Exp 0` |
| `visibility` | `public`/`private` | ○ | ○ | ○ | **リポジトリの公開性と一致**。全 source も同じ visibility |
| `repo` | str | ○ | ○ | ○ | `allgroup-inc/hojo-hq`(`repo_slug(root)` と一致) |
| `created_at` | ISO8601 | ○ | ○ | ○ | 抽出時刻(UTC) |
| `proposed_by` | str | ○ | ○ | ○ | `knowledge_extract.py@<ver> rule-based` または `knowledge_extract.py@<ver> <model名>` |
| `contradictions` | list[{source, note}] | ○(空可) | ○ | ○ | 非空なら `review_status: conflict` 必須 |
| `related_wiki` | list[str] | ○(空可) | | | `wiki_id` |
| `related_skills` | list[str] | ○(空可) | | | Skill 名(参照のみ。Skill を変更する根拠にしない) |
| `review_status` | enum | ○ | candidate / conflict / rejected | approved / superseded | `needs_review` は**書かない**(派生状態。7.4) |
| `dedup_key` | str | ○(抽出器が付与) | ○ | ○ | sha1(normalize(title) + "|" + sorted(全 source id))の16進 |
| `duplicate_of` | str | 条件付き | ○ | — | approved との語一致 ≥60% のとき必須。非空の候補は昇格できない |
| `extract_run` | str | ○ | ○ | ○ | 抽出実行の run_id(1 PR = 1 run の追跡用) |
| `approved_by` | str | 承認時 | — | ○ | 人の名前または GitHub ハンドル。bot 名・空は不可 |
| `approved_at` | date | 承認時 | — | ○ | YYYY-MM-DD |
| `review_by` | date | 承認時 | — | ○ | 未指定なら `approved_at + 180日`(Decision 2 と同じ) |
| `review` | {スイシン, ウタガイ, ベッカイ} | 承認時 | — | ○ | **ウタガイ非空必須**(空語 `なし` `-` `TBD` も不可) |
| `acknowledged_decisions` | list[{decision, reason}] | 任意 | | ○ | 検証器の矛盾判定が偽陽性だと人が判断した Decision(7.4) |
| `rejected_reason` | str | rejected 時 | ○ | — | 却下理由(重複排除の記憶として候補を残す) |
| `supersedes` / `superseded_by` | str | 任意 | | ○ | `wiki_id` |

△ = `source_experience` / `source_decision` / `source_failure` のうち **最低1件**(Provenance 必須)。

### 6.3 本文の構成(見出し固定・この順)

| 見出し | 内容 | 検査 |
|---|---|---|
| `## 知識` | 1〜5行。再利用できる形の主張 | 必須・1,500字以内 |
| `## 根拠(Provenance)` | source ごとに1行: id・何が起きたか・evidence の quote | 必須。frontmatter の source と同じ id が全部出ること |
| `## 反証(ウタガイ)` | この知識が誤っている可能性・適用すべきでない場面 | 必須。承認時は frontmatter `review.ウタガイ` と別に本文にも書く |
| `## 適用範囲と例外` | どの作業・部門・条件で使うか | 必須 |
| `## 関連` | 関連 Wiki・Decision・FK・Skill | 必須(空なら「なし」) |

本文全体 4,000字以内。

### 6.4 状態遷移

```
            抽出器                                  人(PR)
  (なし) ───────▶ candidate ───────────────────────────────▶ approved ──(人: 置換)──▶ superseded(_archive/)
                    │  ▲                                        │
     矛盾検知 ①②     │  │ 人: 矛盾を解消(acknowledged)            │ 新しい Decision と矛盾(派生)
                    ▼  │                                        ▼
                  conflict ──(人)──▶ rejected               needs_review ──(人: 再承認 / superseded)
                    candidate ──(人)──▶ rejected               (Bootstrap は注入しない)
```

| 遷移 | 誰が | どこで | 検証器が要求すること |
|---|---|---|---|
| → candidate / conflict | 抽出器 | 抽出 PR | schema・Provenance・privacy・禁止語・長さ・矛盾①②の整合 |
| candidate → approved | 人 | 昇格 PR(`git mv`) | approved の必須キー・ウタガイ非空・矛盾なし(または acknowledged)・`duplicate_of` 空 |
| → rejected | 人 | PR | `rejected_reason` 非空。`_candidates/` に残す |
| approved → needs_review | (派生) | 毎回の検証・Bootstrap | 新しい adopted Decision と矛盾(③) |
| approved → superseded | 人 | PR(`git mv` to `_archive/`) | `superseded_by` が実在する approved を指す |

---

## 7. コンポーネント別設計

### 7.1 B. Knowledge Extractor — `scripts/knowledge_extract.py`

| 項目 | 内容 |
|---|---|
| 目的 | commit 済みの記録から、再利用価値のある知識の **候補** を決定的に作る。正式化はしない |
| 入力 | ①Experience: `git ls-files -z -- .claude/experience` の JSONL(本体 + part を `group_session_files` で1セッションに束ねる)。**`visibility == "public"` かつ `repo == "allgroup-inc/hojo-hq"` の行だけ**。他の行は読み捨て・数えない ②Decision: `load_decisions(root)` の `status ∈ {adopted, deferred}` かつ visibility が private でないもの ③失敗台帳: `docs/失敗台帳.md` の `| FK-` 行 ④(任意 `--include-gakubi`)`docs/学び/*.md` の箇条書き(**evidence 専用**。単独では Provenance にならない) |
| 処理 | ①規則ベース(既定・AI なし。下表 R1〜R4)→ ②(後置)`--llm` 下書き → ③`dedup_key` で重複排除(既存の approved / candidate / conflict / rejected と一致なら生成しない)→ ④矛盾の事前判定(7.4 の①②。該当すれば `review_status: conflict` と `contradictions` を付ける)→ ⑤`_candidates/` へ書く → ⑥`wiki_validate` を自分の出力に掛け、違反した候補は書かずに理由を表示 |
| 出力 | `docs/wiki/_candidates/<candidate_id>.md`(0件以上)と、標準出力の実行要約 JSON(`run_id` / `written` / `skipped_duplicate` / `conflict` / `rejected_by_validator` / `inputs`(区分別の件数)) |
| 保存場所 | `docs/wiki/_candidates/` **のみ**。`docs/wiki/` 直下・既存 approved・`_archive/`・`_synonyms.txt` は触らない(書込先を関数1つに集約し、パスが `docs/wiki/_candidates/` 配下であることを書込直前に検査) |
| 実行タイミング | GitHub Actions `workflow_dispatch`(MVP)。実行頻度(後に月次 cron)は Gate 項目。ローカル手動実行も可 |
| 担当 | 実行: 統括(akari)の指示 / レビュー: 検証部(kensho)・守り部(mamori)/ 承認: 小柳さん |
| 失敗時 | 入力1区分の読み込み失敗は `audit()` して続行(その区分は 0 件と要約に明記)。書込失敗・検証失敗は exit 1(Actions は PR を作らない)。ロック取得失敗は exit 3 で「<session_id> が実行中(最終 heartbeat N分前)」を表示 |
| Security | INTERNAL→PUBLIC(候補は公開リポに載る)。入力を機械的に public に絞る。LLM には公開テキストのみ |
| Git管理 | 候補は Git 管理(PR 経由)。ロックは git-ignored |
| 優先度 | 必須(MVP は規則ベースのみ) |

**規則ベース抽出(R1〜R4)**

| 規則 | 入力 | 条件 | 生成する知識 | source | confidence(初期値) |
|---|---|---|---|---|---|
| R1 反復成功 | Experience `session_end` | 同じ Skill が `skills` に入ったセッションが **2件以上**、各セッションで `commits` が1件以上(合計2件以上) | 「Skill <名> は <ブランチ語> の作業で commit まで到達した実績が n セッションある」 | `source_experience`(各セッションの session_end 行) | 0.30 + 0.05×(セッション数−2)、上限 0.50 |
| R2 note 接頭辞 | Experience `note` | `text` が `学び:` `失敗:` `誤関連:` で始まる | 学び → 手順・気づき / 失敗 → 避けるべき手順 / 誤関連 → Bootstrap の取り違え(同義語表の見直し材料) | `source_experience`(note 行) | 0.40(同じ正規化本文が別セッションにもあれば +0.10、上限 0.60) |
| R3 失敗台帳 | FK 行 | 全 FK 行(重複排除で既存と同じものは出ない) | 「<分類>: <事実経過の要旨> を避けるには <対策>」 | `source_failure` | 0.70 |
| R4 Decision の裁定 | Decision | adopted で `outcome`(裁定)が空でない / deferred は「未決」として | adopted → 設計判断の知識 / deferred → 「未決。判断根拠にしない」と `## 適用範囲と例外` に明記 | `source_decision` | adopted 0.80 / deferred 0.30 上限 |

- confidence は **並び順と表示にだけ使う**。どれだけ高くても自動承認しない
- R1・R2 は Experience 単独を根拠にした候補であり、信頼階層上は最下位の根拠しか持たない。`confidence_basis` に `Exp のみ` と必ず書く
- note の接頭辞は全角コロン `：` も同じに扱う(NFKC 後に判定)

**重複排除**: `normalize(text)` = NFKC → 小文字 → 空白・記号を除去。`dedup_key = sha1(normalize(title) + "|" + ",".join(sorted(source ids)))`。既存の全候補・全 approved・`_archive/` の `dedup_key` と一致したら生成しない。`candidate_id` の 4hex 衝突は 6hex まで延ばす(一意性は検証器でも確認)。

**LLM 下書き(後置・MVP 外)**: `--llm` 指定時だけ。Secret `ANTHROPIC_API_KEY`、モデルは weekly-gakubi と同じ環境変数方式(`KNOWLEDGE_MODEL`、既定は weekly-gakubi と同じ候補列・`NotFoundError` で次候補・`stop_reason == "max_tokens"` は失敗扱い)。LLM に渡すのは規則ベースで作った候補の `title` / `summary` / evidence の quote(すべて公開テキスト)だけ。LLM が書けるのは `## 知識` と `## 適用範囲と例外` の文面だけで、**source・evidence・visibility は書き換えられない**(厳密な JSON schema で受け、余計なキーがあれば捨てる)。出力は検証器を通ったものだけ書く。`anthropic` が import できなければ `--no-llm` に落ちず exit 2(明示指定の失敗を黙って別動作にしない)。

### 7.2 G. Knowledge Validator — `scripts/wiki_validate.py` + CI ステップ

| 項目 | 内容 |
|---|---|
| 目的 | 誤った知識・公開できない知識・根拠の無い知識が、候補として main に入ること、正式知識になることを機械で止める |
| 入力 | `docs/wiki/*.md`・`docs/wiki/_candidates/*.md`・`docs/wiki/_archive/*.md`・`docs/wiki/_synonyms.txt`、解決用に Experience(git 管理下のみ)・`load_decisions`・失敗台帳 |
| 処理 | 下表 V01〜V15。違反は (パス, コード, 理由) の一覧。`--json` で機械可読 |
| 出力 | exit 0(違反なし)/ exit 1(違反あり。PR を止める)/ exit 2(使い方・自己点検失敗)。needs_review は exit 0 + `::warning::` |
| 保存場所 | なし(読み取り専用) |
| 実行タイミング | ①repo-scope.yml の新ステップ(全 push / PR、`if: ${{ !cancelled() }}`)②knowledge-extract.yml の PR 作成前 ③抽出器の書込前(自分の出力) |
| 担当 | 検証部(kensho)が検査の追加・偽陽性の是正。緩めるときは議事(不可逆類型②: 閾値・ルールの変更) |
| 失敗時 | 検査自体が実行できない(git が無い等)は exit 1(fail-closed。「検査できなかった」を「違反なし」にしない) |
| Security | CRITICAL(公開境界の機械検査) |
| Git管理 | スクリプト・selftest は管理 |
| 優先度 | 必須(MVP) |

| コード | 検査 | 失敗の例 |
|---|---|---|
| V01 | schema 完全性(必須キー・型・enum・本文の5見出し) | `summary` が無い |
| V02 | ID 形式と一意性(`candidate_id`・`wiki_id`・ファイル名との一致) | 同じ `candidate_id` が2ファイル |
| V03 | Provenance: source が最低1件、すべて解決できる | `session-X@ts` に該当行が無い / 未知の `decision_id` / 無い FK |
| V04 | evidence の quote が参照先本文に逐語で含まれる(空白正規化のみ許す) | 要約した文を quote に入れた |
| V05 | visibility: 候補の値 == リポジトリの公開性、全 source が public(Experience 行の `visibility`・Decision の `visibility`) | private 行を source にした |
| V06 | 禁止語: `check_repo_scope.find_content_violations(path, text)` が None | 禁止語を含む(禁止語リストは import し二重管理しない) |
| V07 | 長さ上限(title 80 / summary 200 / quote 200 / evidence 10件 / 本文 4,000 / `## 知識` 1,500) | summary 201字 |
| V08 | 置き場所: `_candidates/` に approved が無い / `docs/wiki/` 直下は approved のみ / `_archive/` は superseded のみ | 直下に candidate |
| V09 | approved の必須: `wiki_id`・`approved_by`(bot 名は不可)・`approved_at`・`review_by`(> approved_at)・`review.ウタガイ` 非空 | ウタガイ空欄 |
| V10 | 重複: approved との語一致 ≥60% なら `duplicate_of` 必須。`duplicate_of` 非空は approved 不可 | 既存 Wiki とほぼ同文 |
| V11 | 矛盾①: `contradictions` 非空なら `review_status: conflict` | 矛盾を書いたまま candidate |
| V12 | 矛盾②: 採用済み Decision の裁定に否定語があり、候補と語が2つ以上重なる → CONFLICT(status が conflict でなければ違反。approved は acknowledged が無ければ違反) | 「直 push は速い」候補 vs「直 push しない」Decision |
| V13 | 矛盾③: approved Wiki と、Wiki の `approved_at` より新しい adopted Decision の間で②と同じ判定 → **needs_review**(違反ではなく警告。Decision の PR を止めない) | 承認後に逆向きの Decision が採用された |
| V14 | 同義語表: 1行1グループ・各語 2〜30字・1グループ 8語以内・全体 200行以内・禁止語なし・同じ語が2グループに出ない | `merge` が2行に出る |
| V15 | `superseded_by` / `related_wiki` / `duplicate_of` が実在の `wiki_id` を指す | 消えた Wiki を指す |

**V13 を違反にしない理由**: 新しい Decision の PR が既存 Wiki のせいで止まると、信頼階層が逆転する(Wiki が Decision を拒否できてしまう)。Decision は常に通し、Wiki 側を注入停止にする。

**`--selftest`**: V01〜V15 それぞれに正例(通るべきもの)と負例(止まるべきもの)を内蔵する(CLAUDE.md 再発防止メモ「検査を足したら正例で試す」)。禁止語の負例は `FORBIDDEN_CONTENT[0]` を参照して組み立て、実文字列をソースに書かない。

### 7.3 H. Promotion Gate(Phase 2 は Gate 設計のみ)

| 項目 | 内容 |
|---|---|
| 目的 | 候補 → 正式知識 の唯一の経路を「人がマージする PR」に固定する |
| 入力 | `_candidates/` の candidate(conflict は解消後のみ) |
| 処理 | 昇格 PR で ①`git mv docs/wiki/_candidates/<id>.md docs/wiki/<slug>.md` ②`review_status: approved`・`wiki_id`・`approved_by`・`approved_at`・`review_by`・`review`(スイシン/ウタガイ/ベッカイ)を記入 ③本文 `## 反証(ウタガイ)` を人が確定 → CI(repo-scope の wiki_validate)合格 → CODEOWNERS の承認 → マージ |
| 出力 | `docs/wiki/<slug>.md`(approved) |
| 保存場所 | `.github/CODEOWNERS`(新規)に `docs/wiki/ @takeshikoyanagi9-lab`。手順書 `docs/wikiskill/Wiki昇格手順.md` |
| 実行タイミング | 人が必要と判断したとき(候補 PR のマージ後) |
| 担当 | 用意: 誰でも(AI 可。Decision 3「半自動」: 三役の論点案は AI が出してよい)/ ウタガイの確定: 人(担当者)/ マージ: 小柳さん(CODEOWNERS) |
| 失敗時 | CI 不合格 → マージ不可。却下は `rejected` にして `_candidates/` に残す |
| Security | CRITICAL。**AI は昇格 PR を用意してよいがマージできない**。この保証は CODEOWNERS + branch protection(GitHub 設定。Gate 項目)で行う。branch protection が無効な間は「運用上の約束」でしかないことを README に明記 |
| Git管理 | PR 履歴そのもの |
| 優先度 | 必須(MVP: CODEOWNERS と手順書。branch protection の有効化は小柳さんの GitHub 設定) |

- **Skill への反映は一切しない**。昇格した Wiki を読んで SKILL.md を直す作業は、Phase 3 以降の Skill Evolution Gate(別承認)を通す
- GitHub の仕様上、`GITHUB_TOKEN` で作った PR では他のワークフローが起動しない。抽出 PR の検証は knowledge-extract.yml 自身の中で行い、結果を PR 本文に貼る。昇格 PR は人が作るので通常どおり repo-scope が走る

### 7.4 J. Knowledge Conflict(最小)

| 項目 | 内容 |
|---|---|
| 目的 | 矛盾を「検知して人に回す」。自動統合はしない。Decision が常に勝つ |
| 入力 | 候補・approved Wiki・adopted Decision(`load_decisions`)・Experience の note 接頭辞 |
| 処理 | ①候補の `contradictions` 非空 → conflict ②Decision 否定語判定 → CONFLICT ③approved Wiki と新しい Decision → needs_review(派生) |
| 出力 | 候補: `review_status: conflict` + `contradictions`(抽出器が付与)/ approved: 検証器の警告と Bootstrap の非注入 |
| 保存場所 | 候補 frontmatter のみ。needs_review は保存しない(毎回計算) |
| 実行タイミング | 抽出時・毎回の CI・毎回の Bootstrap |
| 担当 | 解消: 統括 + 検証部。迷ったら小柳さんへ上申(三名体制ルール4) |
| 失敗時 | 判定関数の例外は「矛盾あり」として扱う(fail-closed:注入しない側へ倒す) |
| Security | INTERNAL |
| Git管理 | 候補 frontmatter として管理 |
| 優先度 | 必須(MVP) |

**判定②の固定値**

| 項目 | 値 |
|---|---|
| 否定語 `NEGATION_WORDS` | `禁止` `しない` `却下` `やめる` `不可` |
| 対象 Decision | `status == adopted` のみ(deferred / rejected / superseded は対象外。`tags` に `test` を含むものも対象外) |
| 照合範囲 | Decision 側: `title` + `outcome`。候補側: `title` + `summary` + `## 知識` |
| 一致の数え方 | `memory_bootstrap.query_units` で候補側を語に分け、Decision 側の `features` に `_unit_matches` で当たる語の数(同義語グループは1語) |
| しきい値 | 2語以上で CONFLICT |
| 偽陽性の解消 | approved にする人が `acknowledged_decisions: [{"decision": "<id>", "reason": "<Decision と同じ向きである理由>"}]` を書く。**Decision と逆向きの知識を acknowledged で通すことは手順書で禁止**(逆向きなら rejected) |

判定①の抽出器側: 同じ語を2語以上共有する `学び:` と `失敗:` の note が両方あるとき、両方の候補に互いを `contradictions` として書き、conflict にする。

**needs_review の解消**: ①人が Wiki を見直し、Decision と同じ向きなら `acknowledged_decisions` に追記して再承認(`approved_at` 更新)②逆向きなら `superseded` にして `_archive/` へ。どちらも PR。

### 7.5 L. Concurrency(最小)

| 項目 | 内容 |
|---|---|
| 目的 | 抽出の二重実行で候補が二重に出る・同じファイルを2つの PR が書く、を防ぐ |
| 入力 | — |
| 処理 | ①Actions: `concurrency: {group: knowledge-extract, cancel-in-progress: false}` ②ローカル: `.claude/locks/knowledge-extract.lock`(JSON: `session_id` / `pid` / `host` / `acquired_at` / `heartbeat_at`)③`candidate_id` 一意(検証器 V02)④1 PR = 1 抽出実行(ブランチ `wiki-candidates/<run_id>`、PR 本文に run_id) |
| 出力 | ロックファイル(終了時に削除) |
| 保存場所 | `.claude/locks/`(git-ignored・既存) |
| 実行タイミング | 抽出の開始〜終了。heartbeat は候補1件ごと、かつ60秒ごと |
| 担当 | 抽出器(自動)。stale の解除判断は利用者 |
| 失敗時 | 取得できない → exit 3 で保持者と最終 heartbeat を表示。**stale 判定**(Decision 8): heartbeat から30分超 **かつ**(`_local/<session_id>.ended` がある、または同じ host で pid が生きていない)→ 自動解除して audit。マーカーも pid 情報も無い → 自動解除せず `--break-stale-lock` の明示指定を求める |
| Security | INTERNAL |
| Git管理 | なし |
| 優先度 | 必須(MVP) |

### 7.6 Bootstrap `[Wiki]` — `scripts/memory_bootstrap.py` の変更

| 項目 | 内容 |
|---|---|
| 目的 | 承認済みの知識を、関連するものだけ、「なぜ信頼しているか」と一緒に新セッションへ渡す |
| 入力 | `docs/wiki/*.md`(直下・非再帰)。`review_status == approved` かつ needs_review でないもの。`visibility` がリポジトリの公開性と一致するもの |
| 処理 | `KINDS` の `prevention` の直後・`skill` の直前に `("wiki", "[Wiki]", "## 承認済みの知識 [Wiki](Official Wiki・人が承認)")`。`COLLECTORS` に `("wiki", _wiki)`。`_wiki` は `_src(kind="wiki", label="[Wiki]", sid=wiki_id, path, title, body, line, date=approved_at, text=title+summary+知識の先頭600字, match_title=title)` を返す。採点・`_select`・`_render` は既存のまま(区分ごと最大5件・全体 6,000字に含める) |
| 出力 | `- [Wiki] <title> — <summary[:160]> / 根拠: Exp n・Decision m・FK k / 承認: <approved_by> <approved_at> → <path>`(n, m, k は source 各リストの件数) |
| 保存場所 | 出力は `additionalContext`(保存しない) |
| 実行タイミング | 段1・段2(既存の hook のまま。hook・settings.json は変えない) |
| 担当 | 自動 |
| 失敗時 | `_wiki` の例外は既存の `collect_sources` が audit して空扱い(他区分は出る)。壊れた Wiki 1件は audit してその1件だけ飛ばす |
| Security | `docs/wiki/_` 始まりは読まない(glob と明示チェックの二重)。`.claude/wiki.off` があれば `_wiki` は `[]` を返し audit に `wiki: disabled by wiki.off` を1行 |
| Git管理 | スクリプトのみ |
| 優先度 | 必須(MVP) |

**性能**: Decision の読み込みを `_decisions` と `_wiki`(needs_review 判定)で共有する(`_decisions_cached(root)`。1プロセス内の memo)。Wiki 20件・Decision 50件で 500ms 以内をテストで固定する(realcopy fixture)。

**持ち越し (a)(b)(c) を同じ Task で直す**(11章): 同義語グループでの照合、Skill 名一致の min_score 算入を指示由来の語に限定、検索語行に正規化後の語を表示。

### 7.7 Privacy(Phase 1 より弱くしない)

| 項目 | 内容 |
|---|---|
| 目的 | Private 由来のテキストが Public の候補・Wiki・注入に現れる経路を作らない |
| 入力 | 抽出器・検証器・Bootstrap のすべての入力 |
| 処理 | ①抽出器は Experience を `visibility`/`repo` で機械的に絞る(private・unknown は入力にしない・数えない)②議事 frontmatter に任意キー `visibility`(public / private。既定はリポジトリの公開性)を追加し、検証器が読む ③候補の `visibility` はリポジトリの公開性と一致必須 ④LLM には公開テキストのみ ⑤クロスリポ読込なし ⑥候補は自動承認されない ⑦禁止語 CI(V06・既存 repo-scope) |
| 出力 | 違反時は CI 赤(マージ不可) |
| 保存場所 | — |
| 実行タイミング | 抽出時・CI・Bootstrap |
| 担当 | 守り部(mamori)。違反が main に入ったら緊急停止 → 失敗台帳 |
| 失敗時 | fail-closed(判定できない visibility は private 扱い。`repo_slug` が `unknown` なら private) |
| Security | CRITICAL |
| Git管理 | 検査スクリプトは管理 |
| 優先度 | 必須(MVP) |

詳細な証明は9章。

### 7.8 Rollback

| 項目 | 内容 |
|---|---|
| 目的 | 誤った知識・漏えい・性能劣化が起きたとき、数秒で止め、Git で正式に戻す |
| 入力 | — |
| 処理 | ①部分停止: `touch .claude/wiki.off`(`[Wiki]` だけ止まる。他の区分・Experience は動く)②全停止: `.claude/memory.off` / `HOJO_MEMORY_OFF=1`(既存)③Wiki 1件: その Wiki を追加した PR を revert(または `superseded` へ)④抽出: workflow_dispatch なので実行しなければ動かない。workflow を無効化(GitHub の Disable workflow)でも止まる ⑤Phase 2 全体: 1つの PR + タグ `wikiskill-phase2-v1` で `git revert -m 1 <merge commit>` |
| 出力 | 議事 `docs/議事/議事_YYYYMMDD_WikiSkill_Phase2緊急停止.md`(48時間以内・Decision 7) |
| 保存場所 | `docs/wikiskill/Rollback手順.md` に Phase 2 の節を追記 |
| 実行タイミング | Rollback 条件(下表)に1つでも該当したとき |
| 担当 | 緊急停止は守り部が単独で可(Decision 7)。正式判断は小柳 Decision Gate |
| 失敗時 | revert 競合は守り部が手で解決し、解決内容を議事に残す |
| Security | INTERNAL |
| Git管理 | `.claude/wiki.off` は git-ignored(`.gitignore` に1行追加) |
| 優先度 | 必須(MVP) |

**Rollback 条件(1つでも該当 → 守り部が緊急停止 → 小柳 Gate)**

| # | 条件 | 最初の止め方 |
|---|---|---|
| RB1 | 検証器の偽陰性で、誤った知識が approved に入った | `wiki.off` → 該当 Wiki の revert → 検証器に負例を追加 |
| RB2 | Private 由来のテキストが候補(PR を含む)に出た | `wiki.off` + 抽出 workflow 無効化 → 失敗台帳 → 履歴の扱いは議事 |
| RB3 | Bootstrap の `slow`(500ms 超)が週3回 | `wiki.off` → 原因調査 |
| RB4 | `baseline_debt.py --compare` が REGRESSION | 該当 PR を revert |
| RB5 | Decision と矛盾する Wiki が注入された(needs_review の取りこぼし) | `wiki.off` → V13 の負例を追加 |

---

## 8. Knowledge Conflict の設計例(A 成功 / B 失敗 / C 禁止)

**素材**(テスト fixture でも同じ形を使う):

| 記号 | 種類 | 内容(要旨) | 信頼 |
|---|---|---|---|
| A | Experience note(session-A) | `学び: 自動生成した学びノートを main へ直接 push したら、PR 待ちが無く当日中に反映できた` | 低 |
| B | Experience note(session-B) | `失敗: 自動生成物を main へ直接 push したため、禁止語を含むノートがレビュー前に公開された` | 低 |
| C | Decision(adopted) | 裁定「自動生成物は main へ直接 push しない。必ず PR を通し CI と人が見る」 | 高 |

**処理と結果**

| 段 | 何が起きるか | 結果 |
|---|---|---|
| 抽出 R2 | A から候補 KA(「直接 push は当日反映できる」)、B から候補 KB(「直接 push は公開事故を招く」)を作る | 2候補 |
| 矛盾① | KA と KB は「自動生成」「main」「直接」「push」を共有し、接頭辞が `学び:` と `失敗:` で逆 → 互いを `contradictions` に記入 | KA・KB とも conflict |
| 矛盾② | C の裁定に否定語「しない」があり、KA と語が2つ以上重なる → CONFLICT(`contradictions` に `{"source": "<C の decision_id>", "note": "Decision が禁止"}`) | KA は conflict のまま |
| 矛盾② | KB も C と語が重なる → 同じく CONFLICT(**偽陽性**: KB は C と同じ向き) | KB も conflict |
| 人のレビュー | KA: C と逆向き → `rejected`(理由「Decision C が禁止。A を根拠に Wiki を書かない」)。KB: C と同じ向き → `acknowledged_decisions` に C を記入し、`source_decision` にも C を足して承認 | KA rejected / KB approved |
| Bootstrap | KA は `_candidates/` にあるので読まれない。KB は `[Wiki]` に出る(根拠: Exp 1・Decision 1・FK 0) | C が勝つ |

**守ること**

1. **C が勝ち、A を根拠に Wiki を書かない**。A の「成功」は Experience(低信頼)であり、Decision(高信頼)の禁止を覆さない
2. 自動統合しない。KA と KB を1つの Wiki に混ぜる処理は無い
3. 否定語判定は粗い。KB のような偽陽性が出るのは設計どおり(止めすぎる側に倒す)。解消は人だけが行う
4. E2E 逆方向テストは「誤った Experience A → 候補 → C と矛盾 → CONFLICT → `docs/wiki/` に無い → Bootstrap に出ない」を固定する

**Decision が後から来る場合**: KB 承認後に「直接 push を一部許可する」新 Decision D が採用されたら、V13 が KB を needs_review にし、Bootstrap は KB を注入しない。人が KB を D に合わせて書き直すか superseded にする。

---

## 9. 「Private → Public の自動経路」が存在しないことの証明

**主張**: hojo-hq の `docs/wiki/`(候補を含む)と `[Wiki]` 注入に、private 由来のテキストが **人の手を介さず** 到達する経路は無い。

**証明(経路の全列挙)**: `docs/wiki/` にテキストが入る経路は次の4つしか無い。

| # | 経路 | 入力の出どころ | 遮断点(機械) | 遮断点(人) |
|---|---|---|---|---|
| E1 | 抽出器(規則ベース) | hojo-hq の作業ツリーにある **commit 済み** ファイルのみ(`git ls-files`)。Experience は `visibility == public` かつ `repo == allgroup-inc/hojo-hq` の行だけ。Decision は visibility が private でないもの。FK は本リポの台帳 | ①入力フィルタ ②書込先は `_candidates/` のみ ③V03/V04/V05/V06 ④Actions の commit 前に「ステージされたパスがすべて `docs/wiki/_candidates/` 配下」を検査 | 抽出 PR のレビュー |
| E2 | 抽出器(LLM・後置) | E1 で作った候補の公開テキストだけ | ①LLM は source・evidence を書けない ②quote 逐語検査 V04 ③E1 と同じ全検査 | Gate 項目「LLM 下書きの許可」 |
| E3 | 昇格 PR | `_candidates/` の既存ファイル(E1/E2 の出力)の `git mv` + 人の記入 | V01〜V15、CODEOWNERS | 小柳さんのマージ |
| E4 | 人が直接書く PR | 人の手入力 | V05/V06(既存 repo-scope の禁止語と同じ) | 人そのもの(= 自動経路ではない) |

**private の内容が hojo-hq の入力に来ない理由**

1. Experience Logger は `$CLAUDE_PROJECT_DIR` 配下にしか書かない(Phase 1 K)。private リポで作業したセッションの記録は private リポに残り、hojo-hq の作業ツリーに現れない
2. hojo-hq の作業ツリーに private 行が混ざっても(手編集・誤 commit)、`check_experience_privacy.py` が CI で止め、抽出器は `visibility`/`repo` で読み捨てる(二重)
3. 抽出器・検証器・Bootstrap は root 外を読まない(`_inside` と同じ確認を共通化)。他リポを clone・fetch する処理を持たない
4. knowledge-extract.yml の `GITHUB_TOKEN` はこのリポジトリにしか権限が無く、他リポの Secrets も使わない。checkout するのは hojo-hq だけ
5. LLM に送る本文は E1 の候補テキスト(= 公開済みの commit 内容からの逐語引用)だけ。送信前に `find_content_violations` を掛ける

**逆方向(Public → Private)**: private リポで同じ仕組みを動かす場合、候補の `visibility` は private になり(リポの公開性と一致必須)、private リポの中で完結する。Public 側へ書く経路は無い(E1〜E3 はすべて「同じリポジトリ内」の操作)。

**残る経路(自動ではないもの)と対策**

| 残余 | なぜ自動経路ではないか | 対策 |
|---|---|---|
| 人が note に非公開情報を書いて commit | 人の操作 | README の注意・`check_experience_privacy` の禁止語・R2 は接頭辞付き note しか拾わない・抽出 PR のレビュー(Top Risk 2) |
| 人が昇格 PR で private の内容を書き足す | 人の操作 | V06・CODEOWNERS |

**push の時点で公開されることへの手当て**: 公開リポジトリでは、PR 用のブランチも push した時点で誰でも読める。したがって「PR でレビューするから大丈夫」は公開前の保証にならない。knowledge-extract.yml は **push の前に** 同じジョブ内で検証器(V03〜V06)を通し、1件でも違反があれば push せずに終了する(ローカル実行でも抽出器は書込前に自分の出力を検証する)。

よって、自動経路(E1・E2)は入力の段階で public に限定され、出力の段階で同一リポジトリの `_candidates/` に限定され、昇格は人のマージに限定される。**Private → Public の自動経路は構造上存在しない**。

---

## 10. Experience 長期保存の比較(#24・Phase 2 では変更しない)

**前提**: 1行およそ 220 バイト。gzip や archive をしても **Git 履歴のサイズは減らない**(過去に commit した原本 blob が残る)。履歴を縮めるには履歴の書き換え(公開リポでは全 clone・PR 参照が壊れる)か新規リポジトリへの移行しかない → **方式を変えるなら早いほど安い**。

| 候補 | 容量 | プライバシー | 監査可能性 | Bootstrap の読みやすさ | 運用コスト | Obsidian との役割分担 |
|---|---|---|---|---|---|---|
| ①Git 全保持(現行) | ×(単調増加。履歴は縮まない) | △(公開履歴に永久に残る) | ◎(Decision・FK と同じ履歴) | ○(現行のまま) | ◎(追加の仕組み無し) | `.claude/` は同期対象外。Obsidian には写らない |
| ②一定期間後に別ストレージ(Private repo `allgroup-inc/hojo-experience-private` または GitHub Release asset)+ Git には索引 `.claude/experience/_index.jsonl`(session_id, date, branch, commits, skills, note digest)のみ | ○(以後の増加は索引のみ。既存履歴は残る) | ○(Raw は private 側) | ○(索引から元の場所へ辿れる。digest で改ざん検知) | ○(索引だけ読めば速い) | △(別 repo の権限・移動ジョブ・CI) | Obsidian には Wiki(知識)が写り、Raw は写らない。役割が分かれる |
| ③要約/索引のみ Git(Raw は保存しない) | ◎ | ○ | ×(Raw が無く Provenance を解決できない) | ○ | ○ | 同上 |
| ④Private Experience は別管理(private リポ内で完結=現状) | —(境界の原則) | ◎ | ○ | ○ | ◎ | 変わらない |
| ⑤SQLite ローカル索引(コミットしない) | —(Git に入らない) | ◎ | ×(共有されない・再現できない) | ◎(速い。ただしクラウドセッションは毎回作り直し) | △ | 関係なし |
| ⑥Knowledge 昇格後の Raw 扱い(昇格に使った Raw は Provenance のため保持、未使用 Raw は期限で移動) | ○(②と組み合わせて効く) | ○ | ◎(承認済み知識の根拠は消えない) | ○ | △(「使われた Raw」の印付けが要る) | Wiki の根拠が Git に残る |

**推奨(小柳さん決裁用)**

| 時期 | 推奨 | 理由 |
|---|---|---|
| Phase 2(本 PR) | **①継続**。方式・閾値は変えない | #24 決裁前に方式を変えない(小柳さん判断 2026-10-06) |
| Phase 2(#24 で推奨が採られた場合のみ・別の小 PR) | **索引 `_index.jsonl` の生成だけ**を足す(Raw は動かさない) | Raw を後から動かせる準備。索引は公開してよい項目だけ(`check_experience_privacy` と同じ検査) |
| Phase 3(本命) | **② + ⑥**。昇格に使った Raw は Git に残し(`source_experience` が解決できる)、未使用 Raw は期限後に private 側へ移す | 履歴の増加を止めつつ Provenance を壊さない |
| 常に | ④ を維持(private の Experience は private リポで完結) | Decision 5 |
| 任意 | ⑤ は補助(性能が足りなくなったときのローカル cache)に限る | 正本にしない |

**Phase 3 で必要になる設計上の手当て**: ②を採ると、検証器 V03 は「Git 内の Raw」だけでなく「索引上で `pinned: true`(昇格に使われた)の行」を解決できる必要がある。Phase 2 の V03 は Git 内の Raw だけを解決し、②の採用時に索引解決を足す(本設計の範囲外。#24 の議事に追記する)。

---

## 11. Phase 1 持ち越しの分類

| 記号 | 内容 | 分類 | 扱う Task | 理由 |
|---|---|---|---|---|
| (d) | `_is_tracked` が git エラー(exit 128 等)と未追跡(exit 1)を区別しない。エラー時に commit 済みの本体へ追記し得る | **A(Phase 2 前に直す)** | Task 0b | 作業ツリーを汚す(checkout/rebase を止める)。エラー時は part ファイルへ書く安全側に倒す |
| (e) | `~` 始まりのパスが `<external>` にならない(`root/~/x` と解釈され相対パスとして残り、CI 検査で赤になる) | **A** | Task 0b | 記録側と検査側の不一致(CLAUDE.md「同じ対象を扱うスクリプトは特例を共有する」) |
| (f) | wikiskill-tests.yml の paths に `CLAUDE.md`・`docs/**`・`.claude/skills/**`・`.claude/settings.json`・`.gitignore`・`scripts/check_repo_scope.py` が無い(Bootstrap の入力が変わってもテストが走らない) | **A** | Task 0b | Phase 2 の `docs/wiki/**` 変更でも走る必要がある |
| (a) | 同義語が無い(「マージ」と「merge」が別語) | **B(Phase 2 と同時)** | Task 3 | `docs/wiki/_synonyms.txt` で解く。Wiki と同じ承認経路 |
| (b) | Skill 名一致の min_score 算入が段1(ブランチ・commit 由来の語)でも効く | **B** | Task 3 | 「指示由来の語」に限る(段2の指示・手動 query) |
| (c) | 段2の検索語行が読めない(「最初の指示 + …」で語が分からず、受け入れ時に「マージ」が語に入ったか確認できなかった) | **B** | Task 3 | 正規化後の単位語を表示(指示の本文は出さない) |
| (g) | 旧議事のベッカイ抽出が「ベッカイ」を含む全行を連結する(本文中の言及まで拾う) | **B** | Task 6 | `_bekkai_text` を節見出し、または `- **ベッカイ**:` 行とその継続行に限定 |
| #24 | Experience 長期保存方式 | **B(Decision 起票のみ)** | Task 7 | 比較表は本設計書10章。議事に追記し `status: deferred` のまま |
| #22 | Baseline Debt 是正(8 SKILL.md・学び W41・11リポ再配布・skill_validation) | **C(触らない)** | — | 守り部の別タスク。Phase 2 は「増やさない」だけ |
| #23 | Skill 配布前ゲートの実装 | **C** | — | `scripts/update-skills.sh` を触るため Phase 2 では禁止 |

---

## 12. MVP(最小構成)

| 含める | 内容 |
|---|---|
| M1 | Candidate / Wiki schema(6章)と共通モジュール `scripts/wiki_schema.py` |
| M2 | Validator `scripts/wiki_validate.py`(schema / provenance / privacy / conflict / placement / duplicate。`--selftest`)+ repo-scope CI ステップ |
| M3 | 規則ベース抽出器 `scripts/knowledge_extract.py --no-llm`(R1〜R4・重複排除・lock) |
| M4 | Bootstrap `[Wiki]`(`KINDS`・`COLLECTORS`・`.claude/wiki.off`)+ 同義語展開 |
| M5 | 昇格手順(PR + CODEOWNERS + 手順書)と抽出 workflow(dispatch → PR) |
| M6 | E2E 順方向・逆方向(自動 + 実セッション) |

| 含めない(後置) | 理由 |
|---|---|
| `--llm` 下書き | 幻覚リスク。Gate 項目「LLM 下書きの許可」の承認後に別 PR |
| 月次 cron | Gate 項目「実行頻度」。MVP は dispatch のみ |
| Experience 索引 `_index.jsonl` | #24 決裁後 |
| Skill への反映・Skill Validator・Evolution Gate | Phase 3 以降・別承認 |

---

## 13. E2E Acceptance Criteria

**順方向(正しい知識が正式になり、次のセッションに届く)**

| # | 手順 | 合格条件 |
|---|---|---|
| F1 | Session A: note `学び: …` を記録し、Experience と関連する議事を commit(クラウドは push まで) | JSONL に note 行(public)・議事が `--check` 合格 |
| F2 | 抽出器 `--no-llm` を実行 | `_candidates/K<日付>-<slug>-<4hex>.md` が1件、`source_experience` に `session-A@<ts>`、`proposed_by` に `rule-based` |
| F3 | 検証器 | exit 0。V03(Provenance 解決)・V04(quote 逐語)・V05(public)合格 |
| F4 | ウタガイを記入せずに approved にする | 検証器 exit 1(V09) |
| F5 | ウタガイを記入し、`git mv` で `docs/wiki/<slug>.md` へ昇格(テストでは人の承認を frontmatter 編集で模擬) | 検証器 exit 0 |
| F6 | 新しい Session B(別 session_id)の段1 | `[Wiki] <title>` が `[再発防止]` の後・`[Skill]` の前に出る |
| F7 | 同じ行に「なぜ信頼しているか」 | `根拠: Exp 1・Decision n・FK k` と `承認: <approved_by> <approved_at>` と `→ docs/wiki/<slug>.md` が出る |
| F8 | `.claude/wiki.off` を置いて Session C | `[Wiki]` 区分だけ「該当なし」、他区分と Experience 記録は動く |

**逆方向(誤った知識は正式にならず、注入されない)**

| # | 手順 | 合格条件 |
|---|---|---|
| R1 | 誤った Experience(8章 A)を commit。禁止する Decision C(adopted)が存在 | — |
| R2 | 抽出器 | 候補は作られるが `review_status: conflict`、`contradictions` に C |
| R3 | 検証器 | conflict 候補は exit 0(候補としては正しい形)。approved に書き換えると exit 1(V12) |
| R4 | Bootstrap(段1・段2) | 候補の title・本文の語が出力に一切現れない。`docs/wiki/` 直下に該当ファイルが無い |
| R5 | approved Wiki の後に逆向きの Decision を追加 | 検証器 exit 0 + needs_review 警告、Bootstrap はその Wiki を注入しない |
| R6 | private 行(`visibility: private`)だけの Experience | 抽出器は候補を作らず、要約の入力件数にも数えない |

**自動 + 実セッション**: 上記は pytest(`world` fixture・`hook()`)で自動化し、加えて実際の Claude Code 2セッション(A→B)で F1〜F8 と R4 を手で確認し `docs/wikiskill/Phase2受け入れ記録.md` に記入する。**Session B は「何を知っているか」(Wiki の title・summary)と「なぜ信頼しているか」(Provenance の件数・承認者・承認日・パス)を注入テキストで示すこと**が合格条件。

---

## 14. Top 5 Risks

| # | リスク | 確度 | 影響 | 対策 | 検知 |
|---|---|---|---|---|---|
| 1 | **検証器の偽陰性で誤った知識が approved に入る** | 中 | 重大(全セッションに誤前提が注入される) | 承認は人のみ(CODEOWNERS)/ quote 逐語検査 / 否定語判定は止めすぎる側 / `--selftest` に負例 / approved に review_by(180日)| RB1・利用者申告・needs_review |
| 2 | **note 経由の private 情報が候補に乗る** | 低〜中 | 重大(公開履歴に残る) | R2 は接頭辞付き note のみ / 禁止語 V06 / 抽出 PR のレビュー / note の注意を README に再掲 | `check_experience_privacy`・V06・RB2 |
| 3 | **候補が溜まって誰も見ない(レビュー負債)** | 高 | 中(仕組みが形骸化。CODEOWNERS で小柳さんに集中) | dispatch のみ(勝手に増えない)/ 1回の上限 `--max 10` / 却下も `_candidates/` に残し再生成しない / 週次レポに未処理件数 | `_candidates/` の candidate 件数 |
| 4 | **同義語表が暗黙の知識になる**(誰も意識しない語の結びつきが検索結果を左右する) | 中 | 中(誤関連) | `_synonyms.txt` は Official Wiki と同じ承認経路(CODEOWNERS)/ V14 で形式検査 / 検索語行に展開後の語を表示 (c) | 段2の検索語行・`誤関連:` note |
| 5 | **LLM 下書きの幻覚** | 高(有効時) | 重大 | MVP では無効 / source・evidence を LLM に書かせない / quote 逐語 V04 / Gate 承認後のみ | V04 の失敗件数 |

---

## 15. 小柳 Decision Gate 項目

| # | 項目 | 選択肢 | AI 推奨 |
|---|---|---|---|
| G1 | CODEOWNERS(`docs/wiki/ @takeshikoyanagi9-lab`)と branch protection(main に「Code Owners の承認必須」)の有効化 | 有効化 / CODEOWNERS のみ(運用上の約束) | 有効化。無効の間は「AI がマージできない」が機械で保証されない |
| G2 | 抽出 workflow の実行頻度 | dispatch のみ / 月次 cron / 週次 | 当面 dispatch のみ。候補の処理実績(レビュー負債が溜まらないこと)を見てから月次 |
| G3 | LLM 下書き(`--llm`)の許可 | 不許可 / 許可(条件付き) | MVP では不許可。規則ベースの候補が3回以上回ってから再上申 |
| G4 | #24 Experience 保存方式 | ①継続 / ②+⑥ / ③ / その他 | Phase 2 は①継続、Phase 3 で ②+⑥(10章) |
| G5 | `docs/wiki/` の Obsidian 公開可否(docs 同期で自動的に写る。`_candidates/` も写る) | 全部写す / approved だけ写す(同期側で `_` 始まりを除外)/ 写さない | approved だけ写す。同期は整理担当セッションの仕組みなので、除外は連携メモで依頼 |
| G6 | Phase 2 PR の承認(マージ・タグ `wikiskill-phase2-v1`) | 承認 / 差し戻し | E2E 順方向・逆方向の合格と Baseline SAME を確認のうえ承認 |

---

## 16. ファイル一覧

### 16.1 変更予定ファイル

| ファイル | 変更内容 | Task |
|---|---|---|
| `scripts/experience_log.py` | (d) `_is_tracked` の3値化と git エラー時の part ファイル / (e) `~` 始まり → `<external>` | 0b |
| `.github/workflows/wikiskill-tests.yml` | (f) paths 追加 + Phase 2 の新スクリプト・テスト | 0b, 1〜4 |
| `.github/workflows/repo-scope.yml` | `wiki_validate.py --selftest` と本検査のステップ(`if: ${{ !cancelled() }}`) | 1 |
| `scripts/memory_bootstrap.py` | `KINDS`・`COLLECTORS` に wiki、`_wiki`、`wiki.off`、同義語グループ照合、Skill 名一致の限定、検索語行、Decision 読み込みの共有 | 3, 4 |
| `scripts/decision_memory.py` | (g) `_bekkai_text` の限定 / 任意キー `visibility` を Decision dict に追加・`check_decision` で値を検査 | 6 |
| `.gitignore` | `.claude/wiki.off` を1行追加 | 3 |
| `docs/wikiskill/README.md` | Phase 2 の章(Wiki・候補・昇格・止め方・`[Wiki]` の読み方) | 7 |
| `docs/wikiskill/Rollback手順.md` | Phase 2 の節(wiki.off・Wiki 単体 revert・workflow 無効化・全体 revert) | 7 |
| `docs/wikiskill/議事frontmatterテンプレート.md` | 任意キー `visibility` の説明 | 6 |
| `docs/議事/議事_20261006_Experience長期保存方式_候補.md` | 10章の比較と推奨を追記(`status: deferred` のまま) | 7 |
| `docs/決裁キュー.md` | Gate 項目 G1〜G6 を追加、#24 に比較の追記を反映 | 7 |
| `docs/全体マップ.md` | `docs/wiki/` と Phase 2 文書の置き場所を1行ずつ | 7 |
| `CLAUDE.md` | 「記憶の仕組み」節に2行(`[Wiki]` と `wiki.off`、Skill 自動更新は Phase 3 以降も別承認) | 7 |

### 16.2 新規予定ファイル

| ファイル | 目的 | Task |
|---|---|---|
| `scripts/wiki_schema.py` | 共通: frontmatter 読み書き・ID 生成・normalize・dedup_key・同義語の読込・矛盾判定関数 | 1 |
| `scripts/wiki_validate.py` | Knowledge Validator(V01〜V15・`--selftest`・`--json`) | 1, 4 |
| `scripts/knowledge_extract.py` | Knowledge Extractor(R1〜R4・重複排除・lock・`--no-llm` 既定) | 2 |
| `scripts/wikiskill_lock.py` | ロック(取得・heartbeat・stale 判定・解除。Decision 8) | 2 |
| `.github/workflows/knowledge-extract.yml` | dispatch → 抽出 → 検証 → ブランチ → PR | 5 |
| `.github/CODEOWNERS` | `docs/wiki/ @takeshikoyanagi9-lab` | 5 |
| `docs/wiki/_candidates/.gitkeep` | 候補ディレクトリの維持 | 1 |
| `docs/wiki/_synonyms.txt` | 同義語表(初期数行) | 3 |
| `docs/wikiskill/Wiki昇格手順.md` | 昇格・却下・needs_review 解消・acknowledged の書き方 | 5 |
| `docs/wikiskill/Phase2受け入れ記録.md` | 実セッション E2E の台帳 | 7, 8 |
| `docs/議事/議事_YYYYMMDD_WikiSkill_Phase2導入.md` | 三名体制議事(frontmatter・ウタガイ必須) | 7 |
| `tests/scripts/test_wiki_schema.py` ほか4本 | 各スクリプトの単体テスト | 1〜6 |
| `tests/integration/test_wikiskill_wiki_e2e.py` | 順方向・逆方向の自動 E2E | 8 |

### 16.3 作らないもの・変えないもの

| 対象 | 理由 |
|---|---|
| Skill Proposer / Skill Validator(Regression)/ Skill Evolution Gate | Phase 3 以降・別承認 |
| SKILL.md の自動更新・Wiki からの反映 | 非目的(小柳さん指示) |
| `.claude/skills/**`(110 Skills)・`.claude/commands/**`・`scripts/update-skills.sh`・`.claude/agents/**` | 13リポ配布方式を変えない |
| `.claude/settings.json`・`.claude/hooks/*`(既存 hook) | `[Wiki]` は既存の Bootstrap 経路に乗るだけ。hook を足さない |
| `docs/wiki/README.md` などの直下の非 Wiki 文書 | 直下は approved のみ |
| Conflict Resolver(自動統合)・`docs/conflicts/` | Phase 3 |
| Skill Metrics・Dashboard | Phase 3 |
| Experience の移動・索引・SQLite | #24 決裁後 |
| 抽出結果の main 直 push | FK-006 の再発防止 |
| クロスリポの読込・他リポへの書込 | Privacy |
