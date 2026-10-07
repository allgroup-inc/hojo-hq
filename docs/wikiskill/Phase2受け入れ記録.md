# WikiSkill Phase 2 受け入れ記録

Task 8(自動 E2E と、実セッション A → B → C の手動 E2E)の記入結果。**未記入(Task 8 で記入する空の台帳)。**
導入議事: `docs/議事/議事_20261007_WikiSkill_Phase2導入.md`
設計書の合格条件: `docs/superpowers/specs/2026-10-07-wikiskill-phase2-knowledge-wiki-design.md`(13章)

試験用の Wiki は題の先頭を「受け入れ試験:」にし、試験後に `docs/wiki/_archive/` へ superseded として移す(本物の知識として残さない)。試験の note に顧客情報・private の内容を書かない。

## 実セッション E2E(A → B → C)

| 項目 | 内容 |
|---|---|
| 実施日時 | 2026-10-07 05:03 UTC(Session B) |
| session_id(A) | |
| session_id(B) | a0fd1848-3e6b-5193-b939-d50edf9139b4 |
| session_id(C) | |

| # | 確認項目 | 結果(✅ / ❌) | 備考 |
|---|---|---|---|
| F1 | Session A: note `学び: …` を記録し、Experience と関連する議事を commit・push する | | |
| F2 | 抽出(knowledge-extract を dispatch、またはローカルで `--max 3`)が候補を `docs/wiki/_candidates/` に作る | | |
| F3 | 候補が検証(`python3 scripts/wiki_validate.py`)を通る | | |
| F4 | ウタガイが空のままの昇格は検証で止まる | | |
| F5 | 人の承認(昇格 PR 相当)後、検証が通り commit できる | | |
| F6 | Session B: 注入の並びが [再発防止] → [Wiki] → [Skill] | ✅ | 段1の見出し順: [D] → 未解決 → [FK] → [再発防止] → [Wiki] → [Skill] → [Exp] |
| F7 | Session B: `[Wiki]` 行に題・要約・`根拠:`・`承認:`・パスが出る | ✅ | 題「受け入れ試験: 生成物を作り直す前に origin/main を取り込むと、新しいデータを消さずに済む」・「根拠: Exp 1・Decision 0・FK 0」・「承認: 小柳(受け入れ試験) 2026-10-07」・「→ docs/wiki/W20261007-uketsuke-shiken-origin-main.md」の4点を grep -F で確認 |
| F8 | Session C: `.claude/wiki.off` で `[Wiki]` だけ止まり、他の区分と記録は動く。消すと戻る | | |
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
| | | |

## 自動 E2E と全体テスト

| 項目 | 結果 |
|---|---|
| `python3 -m pytest tests/integration/test_wikiskill_wiki_e2e.py -q` | |
| 全体テスト(Phase 1 の固定テスト ID が全て PASS / failed は Baseline の2件のみ)・Phase 2 の新規テスト数(実数) | |
| `python3 scripts/wiki_validate.py && python3 scripts/check_experience_privacy.py` | |

## Baseline 比較

```text
(`python3 scripts/baseline_debt.py --compare` の出力を貼る)
```

## 所見

(Task 8 で記入。❌ が出たら PR をマージせず、該当の Task に戻る)
