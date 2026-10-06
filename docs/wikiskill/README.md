# WikiSkill Phase 1 運用ガイド(記憶の仕組み)

小柳さん・守り部向け。Claude Code のセッションが終わっても、決めた理由・前提・反対意見・失敗の記録が次のセッションに引き継がれるようにする仕組みの説明書です。導入の経緯と決裁は `docs/議事_20261006_WikiSkill_Phase1導入.md`。

この仕組みは **記録と取り出しだけ** をします。Skill を自動で書き換えることはしません。

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

## 9. まだ無いもの(Phase 2 以降)

次は **未実装** です。Phase 1 では動きません。

- Wiki(正式な知識ページへの昇格)
- Skill の改善提案と検証(Proposal → Evaluation → 三名体制 → 小柳 Gate → Merge)
- 編集の Lock(同時編集の衝突防止)

Skill の自動更新は、人間の Gate を通さない形では行いません。

## 10. 関連文書

- 導入議事: `docs/議事_20261006_WikiSkill_Phase1導入.md`
- 設計書: `docs/superpowers/specs/2026-10-06-wikiskill-integration-design.md`
- 実装計画: `docs/superpowers/plans/2026-10-06-wikiskill-phase1-memory-foundation.md`
- 議事のテンプレート: `docs/wikiskill/議事frontmatterテンプレート.md`
- Rollback 手順: `docs/wikiskill/Rollback手順.md`
- 受け入れ記録(Task 8 で記入): `docs/wikiskill/Phase1受け入れ記録.md`
- 候補議事(決裁待ち): `docs/議事_20261006_Skill配布前Privacy検査_候補.md`
- 失敗台帳: `docs/失敗台帳.md`(FK-006)

Task 9(PR・マージ・タグ)に進む条件: repo-scope の Experience 検査(自己点検・本体)と Decision 検査(議事の必須項目)が緑で、置き場所の検査は Baseline の9件だけが赤のままであること(新しい赤が無いこと)。WikiSkill のテストは `wikiskill-tests` ワークフローで走ります。

Phase 1 の受け入れ条件: 新しい privacy 違反 0 / 新しい skill_validation 失敗 0 / Baseline 非悪化 / 110 Skills 不変 / 13リポ配布不変 / セッション A で決めた内容(決定・なぜ・前提・ウタガイ・見直し期限・失敗台帳・再発防止)を、新しいセッション B が復元できること。
