# WikiSkill 運用ガイド(Phase 1 記憶の仕組み + Phase 2 Knowledge Wiki)

小柳さん・守り部向け。Claude Code のセッションが終わっても、決めた理由・前提・反対意見・失敗の記録が次のセッションに引き継がれるようにする仕組みの説明書です。導入の経緯と決裁は `docs/議事_20261006_WikiSkill_Phase1導入.md`。

この仕組みは **記録と取り出し(Phase 2 では承認済みの知識の取り出しも)だけ** をします。Skill を自動で書き換えることはしません。Phase 2(Knowledge Wiki)は9章。

## 1. 何が記録されるか

2種類の記録があり、信頼の重さが違います。

| 種類 | 置き場所 | 中身 | 信頼 |
|---|---|---|---|
| Decision(決定) | `docs/議事/`(新規はここ。`docs` 直下の `議事_*.md` も引き続き読まれます)の議事(frontmatter 付き) | 決定内容・なぜ・前提・ウタガイ(反対理由)・見直し期限 | 高(人が書いて決裁したもの) |
| Experience(経験) | `.claude/experience/YYYY-MM/session-<ID>.jsonl`(commit した後の続きは `session-<ID>.part<N>.jsonl`。7章) | どのツールを使ったか、どのファイルを触ったか、commit、所要時間などの機械記録と、任意の note | 低(参考。誤りうる) |

Experience に残るのは次のものだけです。

- ツール名(Bash / Skill / Edit / Write など)
- Bash はプログラム名(先頭の1語の basename)だけ。英数字と `._+-` の32字以内でなければ `<unknown>`、プロジェクトの外の絶対パスは `<external>` にします(鍵の断片や他リポのスクリプト名を残さない。CI の検査も同じ形だけを通します)
- 使った Skill の名前
- プロジェクト内の相対パス
- commit
- 所要時間
- 任意の note(1,000字まで)

## 2. 記録されないもの

- あなたの指示(プロンプト)の本文
- Bash コマンドの全文
- ツールの出力の本文
- プロジェクトの外のパス
- 他のリポジトリ(private リポを含む)の内容

本リポジトリは公開です。Experience も commit すると公開されるため、上のように範囲を絞っています。note だけは自由記述なので、**顧客名・個人情報・非公開の数字・認証情報は書かない**でください。CI の検査(`scripts/check_experience_privacy.py`)が、公開リポでの範囲外のパスや長さ超過、禁止語を止めます。

## 3. どう復元されるか(Memory Bootstrap)

新しいセッションでは、記憶の中から **今の作業に関係するものだけ** が自動で最初に届きます。毎回全部が出るわけではありません。

- **段1(セッション開始時)**: 今のブランチ名、このブランチだけの commit(`origin/main..HEAD`。無ければ直近5件)、`origin/main` からの変更ファイル名から関連を探します。クラウドのセッションは detached HEAD で始まるので、HEAD を指す `origin/<ブランチ>` がちょうど1つならその名前を使います(決められなければブランチ名は使わず、`[Exp]` もブランチで絞りません)。
- **段2(最初の指示を出したとき、セッションにつき1回)**: 最初の指示の言葉とブランチ名の語だけで、あらためて関連を探します(commit 件名や変更ファイル名は使いません。指示から語が2つ取れないときだけ段1の語も使います)。2回目以降の指示では何も足されません。
- **雑音を減らす決まり**: 区分ごとに、その区分の25%を超える項目(3件以上)に当たる語(例: 「確認」)はその区分では照合に使いません。題・名前での一致は並び順にだけ使い、2語一致の条件には数えません(Skill の名前だけは例外で1語に数えます)。commit の SHA・セッション ID・ブランチ名の乱数部分(`3mbx56` など)と `.claude/experience/` のファイル名は検索語にしません。
- **上限**: 区分ごとに最大5件(ただし `[Exp]` は最大3件)、全体で6,000字まで。セッション開始の hook は実測でおよそ0.25〜0.4秒です(500ms を超えると `_audit.log` に `slow` が残ります)。
- **信頼の順**: Decision > 失敗台帳 > 再発防止メモ > Experience。出力にはこの順で並び、出典のラベルが付きます。

| ラベル | 意味 |
|---|---|
| `[D]` | 決定(議事)。裁定・なぜ・前提・ウタガイ・ベッカイ・見直し期限と、元の文書のパスを付けます。期限切れは「期限切れ・再議論対象」と表示。保留(`status: deferred`)は `[D:保留]`、却下(`rejected`)は `[D:却下]`。置き換えられた決定(`superseded`)と `tags` に `test` を含む議事は出しません |
| `[未解決]` | 決裁キューの未決事項 |
| `[FK]` | 失敗台帳(過去の失敗) |
| `[再発防止]` | `CLAUDE.md` の再発防止メモ |
| `[Skill]` | 関連する Skill |
| `[Exp]` | Experience(低信頼・参考)。セッションの最新の `session_end` から commit 数と Skill を出します。`session_end` が commit されていない(commit・push の後に終了した)セッションは、最新の行から `events <件数> / note: <最新の note の先頭60字>` を出します。並びは各セッションの先頭行の時刻順。今のセッション自身は出しません |

Bootstrap はこのリポジトリの中しか読みません。

手元で何が出るかは、次のコマンドで確認できます(語は好きに変えられます)。

```bash
python3 scripts/memory_bootstrap.py query "WikiSkill 記憶"
```

## 4. 止め方

守り部は、小柳さんの事前承認なしで止めてかまいません。

```bash
touch .claude/memory.off     # 止める(git に入らない。この作業コピーだけ)
rm .claude/memory.off        # 再開する
```

環境変数 `HOJO_MEMORY_OFF=1` でも同じです。クラウドのセッションは作業コピーが毎回新しいので、全セッションに効かせたいときは環境側にこの変数を設定します。止まると、記録も Bootstrap も両方止まります。段階別の戻し方(設定の取り外し、PR 全体の revert)は `docs/wikiskill/Rollback手順.md`。

失敗したときは、作業を止めずに `.claude/experience/_audit.log` に書き、セッション内に警告が出ます(黙って失敗はしません)。

## 5. 新しい議事の書き方

新しい議事は `docs/議事/` に `議事_YYYYMMDD_<件名>.md` として置き(`docs` 直下の議事も引き続き読まれます)、先頭に frontmatter を付けます。書式は `docs/wikiskill/議事frontmatterテンプレート.md`。

- 見直し期限(`review_by`)は決定ごとに決めます。書かなければ日付の180日後になります。
- `## なぜ`(または `## 背景`)の見出しと、ウタガイの反対理由は必須です。書き終えたら次で確認します。

```bash
python3 scripts/decision_memory.py --check <議事ファイルのパス>
```

**注意(注入される `[D]` の長さ)**: セッションに注入される `[D]` の1行は上限があり、全体で700字、欄(裁定・なぜ・前提・ウタガイ…)ごとに120字までです。収まらないときは 前提 → なぜ → 裁定 の順に60字へ縮め、それでも収まらなければ 前提 → なぜ → ベッカイ の順に欄ごと落とします。**ウタガイ(反対理由・最低80字)と見直し期限と元の文書のパスは、必ず表示されることを保証しています**(テストで固定)。ただし裁定・なぜ・前提が縮められると、新しいセッションに届く情報は減ります。**裁定・なぜ・前提は、それぞれ冒頭を短い1行にまとめてください。**

反対理由が空だと、ここで止まります。過去の議事に frontmatter を付け直す必要はありません(見出しと行の形から推定して読みます)。

## 6. note(所感)の残し方

その場の気づきを Experience に残せます。Claude に「記録して」と言えば Claude が実行します。自分で打つなら次のとおりです。

```bash
python3 scripts/experience_log.py note "受け入れ試験 A 完了"
```

1,000字まで。2章のとおり、顧客名・個人情報・認証情報は書かないでください。

## 7. 注意: commit されない Experience は、他のセッションから見えない

Experience は Git にコミットして初めて、別のセッションや別の作業コピーに引き継がれます。クラウドのセッションでは **push まで** しないと、次のセッションには届きません。Decision(議事)も同じで、commit・push された文書だけが `[D]` として出ます。

**セッションの途中で commit しても大丈夫です。** `session-<ID>.jsonl` が一度 commit されると、その後の記録は同じフォルダの `session-<ID>.part1.jsonl`(それも commit されたら `.part2`…)に書かれます。commit 済みのファイルに追記しないので、作業ツリーが汚れて `git checkout` や `git rebase` が止まることはありません。読む側(Bootstrap・検査・Archive)は本体と part を1つのセッションとして扱います。

おすすめの流れは、**セッションを終える前の最後の手順として `.claude/experience` を commit(・push)する**ことです。それより後の記録(`session_end` など)は次の part に入り、次に commit したときに引き継がれます。

Experience の原本は消さずに残します。180日より古い月は `python3 scripts/experience_archive.py --archive` で gzip にまとめます。容量は `--check` で見られます(3MB で警告、10MB で失敗)。

## 8. Baseline Debt の見方

導入時点で既に赤かった検査(privacy 9件 / skill_validation 5件 / scripts tests 2件。2026-10-06 に固定)は、この仕組みとは別に是正します(`docs/失敗台帳.md` の FK-006)。Phase 1 の約束は「新しい赤を増やさない」ことです。

```bash
python3 scripts/baseline_debt.py --compare
```

- `SAME`: 固定時と同じ(問題なし)
- `IMPROVED`: 減った(是正が進んだ)
- `REGRESSION`: 増えた。作業を止めて原因を調べる

固定値は `docs/wikiskill/baseline-debt.json`。置き場所の検査の項目は、禁止語そのものではなく `<パス>::FORBIDDEN_CONTENT[<番号>]`(本文の語)/ `<パス>::FORBIDDEN[<番号>]`(パスの語)と、`scripts/check_repo_scope.py` のリストの番号で記録します(記録ファイル自体が検査に引っかからないように。検査の例外 `ALLOWED` は広げていません)。

クラウドセッションでは先に `pip install pytest`(入っていないと「pytest が見つかりません」で止まります)。

## 9. Phase 2: Knowledge Wiki(承認済みの知識)

導入の経緯と決裁は `docs/議事/議事_20261007_WikiSkill_Phase2導入.md`。Phase 1 の記録(Experience)から「学びの候補」を機械が拾い、**人が承認したものだけ**を正式な知識(Wiki)として新しいセッションに届けます。Skill を書き換えることはしません。

### Wiki と候補の違い

| | 置き場所 | 誰が作る | Bootstrap に出るか |
|---|---|---|---|
| 候補 | `docs/wiki/_candidates/` の `K….md` | 抽出(`knowledge-extract` ワークフロー。**手動実行のみ**。1回10件まで) | **出ない**(読まない。`review_status` が `approved` でないものは注入しない) |
| 正式な Wiki | `docs/wiki/` 直下の `<wiki_id>.md` | 人が昇格 PR で承認し、小柳さんがマージ | `[Wiki]` として出る |
| 置き換え済み | `docs/wiki/_archive/` | 人 | 出ない |

信頼の順は Decision > 失敗台帳 > 再発防止 > Wiki > 候補 > Experience です。Decision と矛盾する知識は正式になれません(候補は `conflict`、承認済みでも後から新しい Decision と矛盾すれば `needs_review` になり、注入が止まります)。

### `[Wiki]` 行の読み方

セッション開始時(段1・段2)の注入に、次の形で出ます。

- 題と要約(160字まで)
- **根拠: Exp 〇・Decision 〇・FK 〇** — 何を元にした知識か(Experience の行数、議事の件数、失敗台帳の件数)
- **承認: 〇〇 YYYY-MM-DD** — 誰がいつ承認したか(人の名前。bot は承認者になれません)
- `→ docs/wiki/…` — 元のファイルのパス

根拠の件数が少ない、承認が古い、題と中身が合わない、と感じたら信用せず、`docs/wiki/` の原本と原文を確認してください。Wiki は Decision や失敗台帳より下の信頼です。

手元で何が出るかは次で確認できます。

```bash
python3 scripts/memory_bootstrap.py query "締切 マージ"
python3 scripts/wiki_validate.py        # Wiki と候補の検査(違反があると exit 1)
```

### 止め方

| やりたいこと | 方法 |
|---|---|
| `[Wiki]` だけ止める(他の区分と記録は動く) | `touch .claude/wiki.off`(再開は `rm .claude/wiki.off`。git に入らない) |
| 全部止める(記録も注入も) | `touch .claude/memory.off` または `HOJO_MEMORY_OFF=1`(4章) |
| 抽出ワークフローを止める | GitHub の Actions で `knowledge-extract` を無効化(`docs/wikiskill/Rollback手順.md` の Phase 2 節) |

段階別の戻し方は `docs/wikiskill/Rollback手順.md`。

### 候補の昇格(人の仕事)

昇格 PR の作り方・却下・conflict と needs_review の解消は `docs/wikiskill/Wiki昇格手順.md`。承認は昇格 PR のマージだけで、抽出 PR のマージは「候補として受け取った」だけです(承認ではありません)。

### 注意: 候補は commit・push した時点で公開される

本リポジトリは PUBLIC です。抽出が作る候補は `wiki-candidates/<RUN_ID>` ブランチへの push で、**マージ前でも公開されます**。そのため、抽出は commit 済みで HEAD から変わっていない public の記録だけを読み、書く前に検証器に掛けます。それでも note は自由記述なので、2章のとおり顧客名・個人情報・非公開の数字・認証情報は書かないでください。

- GitHub Actions の `GITHUB_TOKEN` で作った PR には CI が自動で走りません。PR 本文に貼られた検証結果が証拠です。PR の作成には、リポジトリ設定の「Allow GitHub Actions to create and approve pull requests」が要ります。
- 同じ根拠(Experience の月)は、`docs/wiki/` 直下の Wiki(承認済みかどうかを問わない)が引いている間、`experience_archive.py --archive` で固められません(`--force` で上書きでき、監査記録が残ります)。
- 検索の同義語は `docs/wiki/_synonyms.txt`(1行1グループ。完全一致のみ)。語を足すと、その語での Bootstrap の結果が変わりえます。
- conflict 判定は粗く、偽陽性が出ます(2026-10-07 の実測は候補9件中5件)。判定された件数は週に1度数えてください(議事の見直し条件)。

## 10. まだ無いもの(Phase 3 以降)

次は **未実装** です。Phase 2 でも動きません。

- Skill の改善提案と検証(Skill Proposer / Validator / Evolution Gate。Proposal → Evaluation → 三名体制 → 小柳 Gate → Merge)
- 衝突の自動統合(Conflict Resolver。Phase 2 の conflict は人が解決する)
- Skill の使われ方の指標(Skill Metrics)
- LLM による候補の下書き(Gate G3 で Phase 2 は不承認)
- 抽出の定期実行(cron。Gate G2 で禁止。実績を見て別の議事で再検討)
- Experience の索引と別ストレージへの移動(#24。方式は Phase 1 のまま)
- 否定の向き(極性)まで見る矛盾判定
- 他リポジトリの記録の読み取り

(Phase 2 で入ったもの: Wiki(正式な知識への昇格)、編集の Lock(`scripts/wikiskill_lock.py`。抽出の同時実行を防ぐ)。)

Skill の自動更新は、人間の Gate を通さない形では行いません。

## 11. 関連文書

- 導入議事(Phase 1): `docs/議事_20261006_WikiSkill_Phase1導入.md`
- 設計書(Phase 1): `docs/superpowers/specs/2026-10-06-wikiskill-integration-design.md`
- 実装計画(Phase 1): `docs/superpowers/plans/2026-10-06-wikiskill-phase1-memory-foundation.md`
- 導入議事(Phase 2): `docs/議事/議事_20261007_WikiSkill_Phase2導入.md`
- 設計書(Phase 2): `docs/superpowers/specs/2026-10-07-wikiskill-phase2-knowledge-wiki-design.md`
- 実装計画(Phase 2): `docs/superpowers/plans/2026-10-07-wikiskill-phase2-knowledge-wiki.md`
- Wiki 昇格手順: `docs/wikiskill/Wiki昇格手順.md`
- Phase 2 受け入れ記録(Task 8 で記入): `docs/wikiskill/Phase2受け入れ記録.md`
- 保存方式の候補議事(#24・保留): `docs/議事/議事_20261006_Experience長期保存方式_候補.md`
- 議事のテンプレート: `docs/wikiskill/議事frontmatterテンプレート.md`
- Rollback 手順: `docs/wikiskill/Rollback手順.md`
- 受け入れ記録(Task 8 で記入): `docs/wikiskill/Phase1受け入れ記録.md`
- 候補議事(決裁待ち): `docs/議事_20261006_Skill配布前Privacy検査_候補.md`
- 失敗台帳: `docs/失敗台帳.md`(FK-006)

Task 9(PR・マージ・タグ)に進む条件: repo-scope の Experience 検査(自己点検・本体)と Decision 検査(議事の必須項目)が緑で、置き場所の検査は Baseline の9件だけが赤のままであること(新しい赤が無いこと)。WikiSkill のテストは `wikiskill-tests` ワークフローで走ります。

Phase 1 の受け入れ条件: 新しい privacy 違反 0 / 新しい skill_validation 失敗 0 / Baseline 非悪化 / 110 Skills 不変 / 13リポ配布不変 / セッション A で決めた内容(決定・なぜ・前提・ウタガイ・見直し期限・失敗台帳・再発防止)を、新しいセッション B が復元できること。
