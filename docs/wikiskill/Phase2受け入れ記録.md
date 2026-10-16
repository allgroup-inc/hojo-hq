# WikiSkill Phase 2 受け入れ記録

Task 8(自動 E2E と、実セッション A → B → C の手動 E2E)の記入結果。**2026-10-07 記入済み(Task 8 完了)。2026-10-08 Release / Tag 作成完了(末尾の節)。**
導入議事: `docs/議事/議事_20261007_WikiSkill_Phase2導入.md`
設計書の合格条件: `docs/superpowers/specs/2026-10-07-wikiskill-phase2-knowledge-wiki-design.md`(13章)

試験用の Wiki は題の先頭を「受け入れ試験:」にし、試験後は本物の知識として残さない。計画では `docs/wiki/_archive/` へ superseded として移す予定だったが、検証器 V09 は `superseded` に後継 `superseded_by`(承認済み Wiki)を要求するため、後継の無い試験用 Wiki は `docs/wiki/_candidates/` に `review_status: rejected` + `rejected_reason` で退役させた(注入されず、再抽出でも重複として作られない)。後継の無い退役のための状態は Phase 3 持ち越し。試験の note に顧客情報・private の内容を書かない。

## 実セッション E2E(A → B → C)

| 項目 | 内容 |
|---|---|
| 実施日時 | 2026-10-07 04:47〜05:12 UTC(Session A 04:47 / 抽出・昇格 04:55〜04:57 / Session B 05:03 / Session C 相当 05:01 / 退役 05:10) |
| session_id(A) | 2e204a20-0518-5c71-9ca3-85007c32d8ea(クラウドセッション session_01Sbb1GdzyMc7H6wivatT9PL) |
| session_id(B) | a0fd1848-3e6b-5193-b939-d50edf9139b4(クラウドセッション session_011zwQi8VU2W1oy6yyTviUZM・3回目。1回目 session_01UEWSc2Ug4EJjWXQWTGhb6t と2回目 session_01HksZazM2fYCpdn5A2keNoD は最初の応答が API 側の安全装置エラーで停止し、hook の記録以外は残っていない。所見1) |
| session_id(C) | C-manual / C-manual-2(本セッションの作業コピーで hook を手動起動。新規クローンは SessionStart 前に `wiki.off` を置けないため、Phase 1 と同じ機械確認で代替。記録ファイルは commit しない) |

| # | 確認項目 | 結果(✅ / ❌) | 備考 |
|---|---|---|---|
| F1 | Session A: note `学び: …` を記録し、Experience と関連する議事を commit・push する | ✅ | note「学び: 受け入れ試験: 生成物を作り直す前に origin/main を取り込むと、新しいデータを消さずに済む」を `.claude/experience/2026-10/session-2e204a20-….jsonl` に記録(`visibility: public`・`repo: allgroup-inc/hojo-hq`)。commit ec88e58b5・dc4efe262(part1)を push。関連する議事は導入議事(D20261007-wikiskill-phase2)が既に commit 済み |
| F2 | 抽出(knowledge-extract を dispatch、またはローカルで `--max 3`)が候補を `docs/wiki/_candidates/` に作る | ✅ | ローカルで `--max 10 --run-id acceptance-20261007`(`--max 3` では信頼度順で議事・失敗台帳の候補が先に選ばれ note が入らないため)。written 10(議事3・FK6・note1)/ conflict 8 / rejected_by_validator 0 / errors 0。Session A の note は `K20261007-note-lesson-d50e.md`(R2・confidence 0.4・`source_experience` 1件・引用は逐語)。試験で使う note の候補1件だけを残し、他9件は削除(マージ後の最初の dispatch で再生成される)。dispatch は main にまだ workflow が無いため未実施(残課題) |
| F3 | 候補が検証(`python3 scripts/wiki_validate.py`)を通る | ✅ | `OK: Wiki 0件・候補 10件・違反なし`(10件時点)/ 受領 commit 0b1307aa9 |
| F4 | ウタガイが空のままの昇格は検証で止まる | ✅ | `review: {"ウタガイ": "なし"}` で昇格 → `docs/wiki/W20261007-uketsuke-shiken-origin-main.md: V09 review.ウタガイ(反対理由)が空・空語`・exit 1 |
| F5 | 人の承認(昇格 PR 相当)後、検証が通り commit できる | ✅ | ウタガイ「note 1件が根拠で再現例が無い…」を記入、`approved_by: 小柳(受け入れ試験)`・`approved_at: 2026-10-07`・`review_by: 2027-04-05` → `OK: Wiki 1件・候補 0件・違反なし` → commit 3905bb517 を push(件名に Wiki の語を含めて段1の検索語に当たるようにした。Phase 1 E2E と同じ方式) |
| F6 | Session B: 注入の並びが [再発防止] → [Wiki] → [Skill] | ✅ | 段1の見出し順: [D] → 未解決 → [FK] → [再発防止] → [Wiki] → [Skill] → [Exp] |
| F7 | Session B: `[Wiki]` 行に題・要約・`根拠:`・`承認:`・パスが出る | ✅ | 題「受け入れ試験: 生成物を作り直す前に origin/main を取り込むと、新しいデータを消さずに済む」・「根拠: Exp 1・Decision 0・FK 0」・「承認: 小柳(受け入れ試験) 2026-10-07」・「→ docs/wiki/W20261007-uketsuke-shiken-origin-main.md」の4点を grep -F で確認 |
| F8 | Session C: `.claude/wiki.off` で `[Wiki]` だけ止まり、他の区分と記録は動く。消すと戻る | ✅ | `touch .claude/wiki.off` → hook SessionStart(sid C-manual): `[Wiki]` の節は `- 該当なし`、[D]・未解決・[FK]・[再発防止]・[Skill]・[Exp] は出る、`session-C-manual.jsonl` が作られる、`_audit.log` に `wiki: disabled by wiki.off` 1行。`rm .claude/wiki.off` → sid C-manual-2 で `[Wiki]` 行が戻る |
| R4 | 逆方向: 矛盾した候補(conflict)が Session B の注入(段1・段2)に一切出ない。`docs/wiki/` 直下に該当ファイルが無い | ✅ | 段1・段2とも conflict 候補の注入なし(段1に「conflict」の語が1回あるが、Phase 2 導入議事 [D] のウタガイ本文の引用で候補ではない)。`ls docs/wiki/*.md` は W20261007-uketsuke-shiken-origin-main.md の1件のみ。備考: Session B 開始時の自分自身のコンテキスト(SessionStart hook の注入)にも `[Wiki]` の行: あり |

## Session B の注入テキスト(`[Wiki]` 行の前後20行)

```text
### 段1(SessionStart・hook の実出力)
# 🧠 Memory Bootstrap(段1: ブランチ・直近commitから)
検索語: superpowers, chat, knowledge, extract, yml, wikiskill, tests, claude, md, w20261007, uketsuke, shiken, origin, main, phase2, 記録, readme, rollback, 手順, wiki, 昇格手順, 議事(=decision), frontmatter, テンプレート, …
## 関連する決定 [D]（高信頼・議事）
- [D:保留] 2026-10-06 Raw Experience を Git へ長期保存し続ける設計の適否(候補・Phase 2〜3) — 裁定: 未決。Phase 2〜3 の正式な Decision の対象とする。採否が決まるまでは Phase 1 の方式を継続し、`python3 scripts/experience_archive.py --check` で合計サイズを監視する… / なぜ: Phase 1 は、Experience の原本(JSONL)を Git にコミットして保存している(`.claude/experience/YYYY-MM/session-*.jsonl`)。1行はおよそ220バイト。全セッションがコミ… / 前提: - gzip や archive をしても、Git 履歴のサイズは減らない。圧縮したファイルを追加しても、過去にコミッ… / ウタガイ: 1. 公開リポの履歴は削除できないため、誤って入った情報は永久に残る(公開可否の検査は通過後の保証であり、検査をすり抜けた分は戻せない) 2. 履歴肥大で clone / CI が遅くなり、全セッションの固定費になる 3. Archive… / ベッカイ: 記録すべきは Raw ではなく「学び」ではないか。Raw は外部保存・要約のみ Git にする案が、Wiki(Phase 2)の設計と整合する。Raw を残す目的(再現・監査)が本当に長期で要るのかも先に確かめたい / 見直し: 2027-01-06 → docs/議事/議事_20261006_Experience長期保存方式_候補.md
- [D] 2026-10-07 WikiSkill Phase 2 導入(Knowledge Wiki) — 裁定: 承認(2026-10-07 小柳さん)。承認済みの知識だけを `[Wiki]` で注入し、昇格は人だけ・抽出は dispatch のみ・LLM 下書きと Skill 反映は無し。Task 9(PR・マージ・タグ)は別承認。 - ウタガイの… / なぜ: - Phase 1 で Experience(機械記録)は残るが、それ自体は「知識」にならない。同じ失敗(FK-001〜FK-006 など)が、記録があるのに繰り返される。新しいセッションは記録を自分から読み解かない。 - 失敗台帳と再発… / 前提: - 承認は人のみ。承認済み(`review_status: approved`)の Wiki だけが Bootstra… / ウタガイ: 1. 否定語による矛盾判定は粗く、偽陽性の conflict がレビュー負債になる。実データの実測で候補9件のうち5件(5/9)が conflict になり、うち4件は組織全体の語だけで当たった。見落とすより騒ぎすぎる方向に倒れており、人… / ベッカイ: そもそも Wiki は要るのか。失敗台帳と再発防止メモで足りるなら、Phase 2 は同義語表と検索語行の改善だけで十分ではないか。MVP の後に、`[Wiki]` が実際に採用された件数で再評価する。 / 見直し: 2027-04-05 → docs/議事/議事_20261007_WikiSkill_Phase2導入.md
- [D] 2026-10-06 WikiSkill Phase 1(記憶基盤)の導入 — 裁定: 2026-10-06 小柳さん承認。Task 9(PR・マージ・タグ)は別承認。 - 内容は上記と設計書 v1.1 冒頭のとおり。ウタガイの3点は受け入れ条件として実装に取り込む。 - 実装は Subagent-driven で進める。 / なぜ: - セッションが終わると理由・前提・反対意見が散逸し、同じ議論と同じミスが繰り返される。議事や失敗台帳に書いてあっても、新しいセッションは自分から探さない。 - Skill(110本)がどれだけ役に立っているかの実績がまだ測れていない。使… / 前提: - 正本は GitHub。本リポジトリは PUBLIC で、Bootstrap は現在のリポ内しか読まない(他リポ・p… / ウタガイ: 1. hook を4本追加するのは全セッションの固定費になる。500ms の上限を守れる保証が無い。 2. Experience を公開リポジトリに置くこと自体が、情報漏えいの面を増やす。記録範囲を縛っても、note は自由記述になる。 … / ベッカイ: Decision は議事に既にある。足りないのは「取り出し」であり、記録ではない。だから Bootstrap を Phase 1 の中心に置く(MVP 比較で Bootstrap 案を採る根拠)。 / 見直し: 2027-04-04 → docs/議事_20261006_WikiSkill_Phase1導入.md
## 未解決（決裁キュー）
- [未解決] 25. 【Phase 2 Gate・小柳さん】WikiSkill Phase 2(Knowledge Wiki)の Gate G1〜G6(2026-10-07 設計書 v1.1・計画を承認済み。議事: docs/議事/議事_20261007_WikiSkill_Phase2導入.md)。決裁済み: G2 抽出は dispatch のみ(cron 禁止)/ G3 LLM 下書きは不承認(Task …
- [未解決] 21. 【実装済み・情報共有】週次学びダイジェスト・月次AIアップデートウォッチを新設 — L1(内部実装・定型データ生成)のため決裁不要で実装。①`weekly-gakubi.yml`: 直近7日のdocs/reportsの変更をClaudeが要約し`docs/学び/`へmain直接追加(毎週月曜21時)。②`ai-update-watch.yml`: Claude Code/Anthropi…
- [未解決] 24. 【Phase 2〜3 Decision】Raw Experience を Git へ長期保存し続けるかの判断(候補: Git継続 / Private repo / DB / Object Storage / Raw外部+要約のみGit / 保存期間短縮。前提: gzip/archive しても Git 履歴は減らない)。議事: docs/議事/議事_20261006_Experience…
## 過去の失敗 [FK]（失敗台帳）
- [FK-006] 2026-10-02 事故+プロセス — 2026-10-02に追加された8つのSKILL.md(commit 6044bb918 / f065ef5a7)と、2026-10-06にweekly-gakubiが自動生成した`docs/学び/学び_2026-W41.md`(commit 68343664b)の本文が、`scripts/check_repo_scope.py`の`FORBIDDEN_CONTENT`の1語目(kakei-cr… / 対策: 部分実装(固定のみ・是正は別タスク): Baseline Debtとして`docs/wikiskill/baseline-debt.json`に固定し(`scripts/baseline_debt.py --compare`で増加を機械検出)、WikiSkill Phase 1は新たな違反を足さない(小柳さん2026…
- [FK-002] 2026-07-23 ヒヤリハット+プロセス — mainへのマージで競合ファイル一覧を確認せず、既知の2ファイルのみ--theirs解決して`git add -A`でコミット。競合が他ファイルに及んでいればマーカー入りHTMLを本番公開する構造だった(事後grepで無事を確認) / 対策: ルール化: マージコミット前に①`git diff --name-only --diff-filter=U`で競合一覧確認 ②マーカーgrep ③check_lp+validate+node test合格、を必須手順として本台帳に記載(スクリプト化はメインブランチ運用が安定したら実施)
- [FK-003] 2026-07-26 事故+プロセス — Lighthouse CIがperformanceスコア基準(0.95)未達で連続失敗し、GitHub Issue #10が21日間(〜2026-08-17)開いたまま自動botコメントが積まれ続けたが、対応着手されなかった。CLAUDE.md記載によれば2026-08-05・08-12にレイアウト系CSS(`word-break:auto-phrase`等)を見出し以外の繰り返し要素にも適用す… / 対策: 部分実装+要継続対応: 適用範囲をh1〜h3見出し限定に修正済みだが本番スコアは未回復。CLAUDE.mdに「レイアウト系CSSは見出し限定。適用範囲を広げる変更はLighthouseローカル実測(hojo-lighthouse-triageスキル)とセットで行う」を明記(2度目の再発のため)。議事: `docs/議…
## 再発防止メモ [再発防止]（CLAUDE.md）
- [再発防止] 「未実装」「停止中」と書く前に、稼働記録を当たる(運用ドキュメントの日付・設定ファイルの実値・PR番号)。2026-09-19: もらいわすれ堂の受給報告フローを「A1未実装・44日停止」として12点の促進パッケージを作り決裁者へ送る直前だったが、実際は2026-08-10稼働済み(`FG_LINE_OA_ID`設定済み・PR#163)だった。完了済みの作業を決裁者に再依頼すると信用を失う(20…
- [再発防止] 議事は `docs/議事_YYYYMMDD_<件名>.md` に置く。他の文書の一節に埋め込まない(2026-08-17: 面談予約表の議事を企画書内に書いて議事一覧・週次の無作為点検から漏れた)
- [再発防止] スキルやドキュメントを参照する記述を書いたら、その参照先が実在するか確認する(2026-08-17: `generate_go_pages.py` 等3ファイルが未作成の go-link-discipline を「準拠」と参照していた / 2026-09-19: A1実装促進パッケージのREADMEと完了記録が、`もらいわすれ堂_` 接頭辞を落とした存在しないパスで3ファイルを案内していた)。案…
## 承認済みの知識 [Wiki](Official Wiki・人が承認)
- [Wiki] 受け入れ試験: 生成物を作り直す前に origin/main を取り込むと、新しいデータを消さずに済む — 学び(手順・気づき): 受け入れ試験: 生成物を作り直す前に origin/main を取り込むと、新しいデータを消さずに済む / 根拠: Exp 1・Decision 0・FK 0 / 承認: 小柳(受け入れ試験) 2026-10-07 → docs/wiki/W20261007-uketsuke-shiken-origin-main.md
## 現在有効な関連Skill [Skill]
- [Skill] ai-seo — When the user wants to optimize content for AI search engines, get cited by LLMs, or appear in AI-generated answers. Also use when the user mentions 'AI SEO,' …
- [Skill] feature-factory — 1人開発でも複数エージェントに役割分担させて機能追加を進めるとき、Vibe Coding(1つの会話に全部詰め込んで思い込みが連鎖する)から抜け出したいときに使う。調査→ストーリー→仕様→実装(分業)→検証の役割分担チェーンと、CLAUDE.mdを土台にした再現性の作り方を提供する。
- [Skill] glow-ma-triangle-review — GLOW M&A・不動産の企業リレーション管理システム(glow-ma)でスコアリング設計・紹介料率・提案順序・提携パートナー条件など意思決定を伴う検討をまとめるときに必ず使う。Step 1(対象明確化)→Step 2(スコアリング)→Step 3(料率)→Step 4(提案順序)→Step 5(提携条件)→Step…
## 直近のExperience [Exp]（低信頼・参考。commitされたものだけ見える）
- [Exp] 2026-10-07 session-a0fd1848-3e6b-5193-b939-d50edf9139b4: events 3
- [Exp] 2026-10-07 session-2e204a20-0518-5c71-9ca3-85007c32d8ea: events 12 / note: 学び: 受け入れ試験: 生成物を作り直す前に origin/main を取り込むと、新しいデータを消さずに済む
- [Exp] 2026-10-06 session-2fa162fe-4733-5601-955c-492a60d37529: events 15

### 段2(UserPromptSubmit・hook の実出力)
# 🧠 Memory Bootstrap(段2: 最初の指示から)
検索語(指示から): マージ(=merge), 競合, 手順, 直接, push, 確認
検索語(ブランチから): superpowers, chat
## 関連する決定 [D]（高信頼・議事）
- 該当なし
## 未解決（決裁キュー）
- 該当なし
## 過去の失敗 [FK]（失敗台帳）
- [FK-001] 2026-07-22 ヒヤリハット+プロセス — LP検査がCSSの`max-width:100%`を禁止語『100%』と誤検知。さらに検査失敗を確認せずコミット・pushした(コマンドを`;`で連結し失敗が止まらなかった) / 対策: テスト化: 検査を可視文言のみに修正(スクリプトに台帳ID明記)。ルール化: 検査系→コミットは`&&`連結を厳守し、失敗時はpushしない
## 再発防止メモ [再発防止]（CLAUDE.md）
- 該当なし
## 承認済みの知識 [Wiki](Official Wiki・人が承認)
- 該当なし
## 現在有効な関連Skill [Skill]
- [Skill] hojo-lighthouse-triage — GitHub ActionsのLighthouseワークフローの失敗通知・自動起票Issueに対応するとき、またはPerformance/Accessibility/Best Practices/SEOのスコア改善を頼まれたときに必ず使う。Claude Code環境からは本番URLやGitHub Actionsのアー…
- [Skill] lean-app-validation — 新しいアプリ・ツール・デジタル商品のアイデアを発掘・検証するとき、または『新規事業/新機能を思いつきで作り始めそうになっている』ときに必ず使う。ゼロから発明せず、伸びている巨大市場の1%を狙う・既存の不満(レビュー等)から改善点を見つける・作る前にマーケで需要を確認する、という一連の検証手順を提供する。「新しいアプリ…
- [Skill] multi-ai-crosscheck — 複数のAI(Claude+Gemini等)による独立クロスチェックを新規設計・実装・レビューするときに使う。正確性が最優先のデータ検証で、別系統モデルの独立照合・保守的マージ・割れたときの根拠引用つき再確認・参加率と履歴の台帳化という4点セットのパターンを提供する。
## 直近のExperience [Exp]（低信頼・参考。commitされたものだけ見える）
- 該当なし
```

## SessionStart の所要時間

| 測定値(real) | `_audit.log` の `slow` 行の数 | 判定(0.5秒未満 かつ 0件で ✅) |
|---|---|---|
| 0.387 s / 0.385 s / 0.429 s(本セッションの作業コピーで実 hook を3回。Session B の hook 実出力は上の節) | 0 | ✅ |

## 自動 E2E と全体テスト

| 項目 | 結果 |
|---|---|
| `python3 -m pytest tests/integration/test_wikiskill_wiki_e2e.py -q` | `6 passed`(順方向 F2〜F7・逆方向 R2〜R4・候補の非注入・wiki.off・needs_review・private 側) |
| 全体テスト(Phase 1 の固定テスト ID が全て PASS / failed は Baseline の2件のみ)・Phase 2 の新規テスト数(実数) | `tests/scripts tests/integration`: `3 failed, 647 passed`(failed は Baseline の scripts tests 2件 + 制度データ件数に依存する `test_ig_automation_e2e`(origin/main でも失敗する既知の赤)。Phase 1 固定 ID 347件: `347 passed`(1回目は負荷依存の SessionStart 計時テスト1件だけが落ち、単独では3回とも合格)。新規テスト: 収集ノード 303件のうち WikiSkill Phase 2 由来 274件(test_wiki_validate 144 / test_knowledge_extract 38 / test_memory_bootstrap 28 / test_wiki_schema 17 / test_wikiskill_lock 10 / test_experience_archive 9 / test_wikiskill_workflows 8 / test_experience_log 7 / test_decision_memory 7 / test_wikiskill_wiki_e2e 6)、残り29件は Phase 1 の固定リストに無かった IG・ミカタ系の既存テスト |
| `python3 scripts/wiki_validate.py && python3 scripts/check_experience_privacy.py` | `OK: Wiki 0件・候補 1件・違反なし` / `OK: Experience記録 5件・違反なし`(退役後) |

## Baseline 比較

```text
skill_validation                   5        5     +0
scripts_tests_preexisting          2        2     +0
verdict: SAME
```
(check_repo_scope の置き場所の検査は Baseline の 9 件のまま)

## 所見

F1〜F8・R4 はすべて ✅。❌ は無い。

1. **Session B は3回目で成功した。** 1回目・2回目は、最初の応答が API 側の安全装置(reasoning_extraction)で止まり、出力 0 トークンで終了した(hook は動いて SessionStart の記録はできている)。両回とも「開始時に注入されたブロックを一字も変えずに貼れ」という指示を含んでおり、3回目はその指示をやめて **hook をツールとして再実行した実出力**(同じリポ状態なら決定的に同じ)を記録させたところ成功した。モデルに「自分のコンテキストの逐語引用」を求める指示が安全装置に当たる可能性がある。次回以降の受け入れ試験はこの方式(hook の再実行)を標準にする。
2. **段2の `[FK-002]`(マージ競合)は出ない。** 段1で既に `[FK-002]` が出ているため、段2は段1に出たものを除外する規則(Phase 1 どおり)で `[FK-001]` が選ばれた。設計どおりで、自動 E2E の逆方向テストもこの性質を踏まえて陽性対照を置いている。
3. **実データの矛盾検知は 10 件中 8 件が conflict**(Task 4 時点の 9 件中 5 件から増加。Phase 2 導入議事が否定語「しない」を多く含むため)。試験用の note 候補は conflict にならなかった。導入議事のウタガイ①(偽陽性がレビュー負債になる)のとおりで、しきい値・照合範囲は変えていない。文単位の照合は別 Decision で検討(議事に試算を記載)。
4. **試験用 Wiki の退役先。** `_archive/` の `superseded` は後継 Wiki を要求する(V09)ため、`_candidates/` に `rejected` で退役させた。後継の無い退役(試験用・陳腐化)のための状態は Phase 3 持ち越し。
5. **Session C は手動 hook 起動で代替**(新規クローンは SessionStart 前に `wiki.off` を置けない)。Phase 1 の所見と同じ扱い。
6. **SessionStart は 0.39〜0.43 秒**(Wiki 1 件・候補 1 件)。Phase 1(0.371 秒)から +0.02〜0.06 秒。`slow` は 0 件。全体テストの同時実行中だけ Phase 1 の単発計時テストが 0.5 秒を跨ぐことがある(負荷依存。残課題として報告)。
7. **knowledge-extract workflow の dispatch は未実施**(main にまだ無い)。マージ後の最初の dispatch を Task 9 の残課題にする。

## 矛盾判定の再測定(2026-10-07・照合範囲の修正後)

議事: `docs/議事/議事_20261007_WikiSkill_Phase2_矛盾判定の照合範囲.md`。Decision 側の照合を、否定語を含む文(+ その文が この/その/これ/それ/上記/前記 で始まる場合は直前の1文)だけにし、コード断片を除いた。しきい値(2語)・否定語の一覧・fail-closed・V12/V13 は変えていない。

正解の扱い: 同じ10件の候補は、どれも採用済みの Decision と本当には矛盾しない。conflict になったものは FP、ならなかったものは TN と数える。

| | conflict | TP | FP | TN | FN | FP率(conflict のうち) |
|---|---|---|---|---|---|---|
| Before(全文照合・e60c3f609) | 9/10 | 0 | 9 | 1 | 0 | 100% |
| After(修正 + この議事を commit した後) | 0/10 | 0 | 0 | 10 | 0 | —(conflict なし) |

| 候補 id | Before | After |
|---|---|---|
| K20261007-d20261006-experience-storage-e39e | conflict(FP) | candidate(TN)※ |
| K20261007-d20261006-skill-dist-privacy-gate-208e | conflict(FP) | candidate(TN) |
| K20261007-d20261006-wikiskill-phase1-2486 | conflict(FP) | candidate(TN) |
| K20261007-d20261007-wikiskill-phase2-6505 | conflict(FP) | candidate(TN) |
| K20261007-fk-001-4a33 | conflict(FP) | candidate(TN) |
| K20261007-fk-002-2041 | conflict(FP) | candidate(TN) |
| K20261007-fk-003-6e0f | conflict(FP) | candidate(TN) |
| K20261007-fk-004-6e31 | conflict(FP) | candidate(TN) |
| K20261007-fk-005-def2 | candidate(TN) | candidate(TN) |
| K20261007-fk-006-6196 | conflict(FP) | candidate(TN) |

※ この議事を commit すると、議事の裁定から11件目の候補(`K20261007-d20261007-wikiskill-conflict-scope-226b`。R4・candidate・矛盾なし)ができる。そのため `--max 10` では experience-storage が上限からあふれて書かれない(`over_max`)。判定(review_status)はあふれる前に計算されており、candidate だった。

真の矛盾を拾うテストは、fixture を変えずにすべて通る。

- A/B/C(`test_a_success_b_failure_c_forbidden_c_wins`・`test_abc_forbidden_still_conflicts`)
- E2E の逆方向(`test_reverse_wrong_experience_conflict_never_injected`)
- E2E の R5(`test_needs_review_after_new_decision_stops_injection`。fixture「…手順は使わない。この手順は採用しない」は指示語の規則で拾う)
- V12 の各テスト(`test_negation_decision_two_unit_overlap_is_conflict`・`test_conflict_candidate_cannot_be_approved`・`test_self_source_dropping_negation_is_v12`・`test_approved_older_decision_is_v12_not_warning` ほか)と `wiki_validate --selftest`(69件)
- 締切アラートの真の矛盾(`test_genuinely_incompatible_alert_candidate_conflicts`)
- 指示語(`test_anaphoric_negation_conflicts_via_previous_sentence`)

既知の偽陰性の類型(否定語の一覧に無い動詞「送らない」など)は `test_known_false_negative_verb_not_in_negation_words`(`xfail` strict)に残した。否定語リストの拡張は別議事で扱う。

## 既知の Performance Debt(2026-10-07)

SessionStart hook の単発計時テスト `test_hook_session_start_under_500ms_on_real_copy` は、この実行環境では単独実行でも 0.5 秒を跨ぐことがある(実測 0.512 秒。origin/main の Phase 1 単体で 0.36〜0.42 秒、Phase 2 の追加分は約 0.04 秒 = `[Wiki]` の commit 確認 git 3 回と承認要件の検査)。ロジックの回帰ではなく性能余裕の不足。受け入れ基準 0.5 秒は変更しない。CI は `WIKISKILL_SKIP_TIMING=1` で計時を飛ばすため赤にならない。Phase 3 の最適化候補: `_git_ready` の toplevel 結果を `committed_files` で再利用(git 1 回減)、`docs/wiki` に承認ページが無いときは git を呼ばない、Decision の特徴語を 1 プロセス 1 回に限定。見直し: Phase 3 着手時。

## Release / Tag 作成完了(2026-10-08)

| 項目 | 値 |
|---|---|
| PR | #441(WikiSkill Phase 2: Knowledge Wiki)。小柳さん最終承認 2026-10-07 → merge 方式でマージ |
| マージコミット(Rollback 対象) | `1e19530df1608f970d3732c27c9cb397e8660f54`(parents: `9955c7a0e` main / `3b4fa5076` PR head) |
| タグ | `wikiskill-phase2-v1` → 同じ SHA(小柳さんが GitHub の Release 画面で作成。lightweight) |
| Release | https://github.com/allgroup-inc/hojo-hq/releases/tag/wikiskill-phase2-v1(公開 2026-10-08 00:04 UTC・タイトル「WikiSkill Phase 2 Knowledge Wiki」) |
| 作成経路 | このセッションからの `git push` のタグ送信と API はどちらも proxy で拒否(Phase 1 と同じ)。迂回せず STOP し、小柳さんが画面で作成 |

マージ後検証(main のマージコミットを clean worktree で実施): `wiki_validate --selftest` 69件 OK / `wiki_validate` OK(Wiki 0件・候補 1件)/ Experience Privacy 自己点検 23件 + 記録 10件 OK / 全議事 `--check` OK / Baseline `SAME` / Bootstrap 実 hook 段1 OK(`[Wiki]` は該当なし)/ 抽出 dry-run conflict 0/10 / Phase 2 E2E 6本 + Phase 1 E2E 4本 PASS / 全体 700 passed(failed は Baseline の 2件 + 制度データ件数依存の既知 1件)。Release 後の確認: リモートタグと Release の対象 SHA が一致・Release 公開状態・main にマージコミット存在・Phase 3 未着手。

これをもって **WikiSkill Phase 2 は正式完了**。Phase 3(Conflict の文脈/極性理解・否定語リスト拡張・「却下。」型・文中指示語・SessionStart 最適化・Experience 長期保存・Skill Metrics/Proposer/Validator/Evolution Gate・LLM Draft・Conflict Resolver)は小柳さんの別承認まで開始しない。Branch Protection と `knowledge-extract` の初回 dispatch も未実施(決裁キュー #26)。

