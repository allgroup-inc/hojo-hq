# Wiki 昇格手順(WikiSkill Phase 2)

知識の候補を、正式な Wiki(`docs/wiki/` 直下の `<wiki_id>.md`)にするための手順です。候補が正式になる道は **人がマージする PR だけ**です。

- 抽出(`knowledge-extract` ワークフロー)は手動実行のみ。候補だけを載せた PR を作り、main へは直接書きません。
- 正式な Wiki は `docs/wiki/` 直下に置き、ファイル名は `<wiki_id>.md`(`wiki_id` は `W<YYYYMMDD>-<slug>`。ファイル名の stem と一致しないと検査が止まります)。
- 候補は `docs/wiki/_candidates/` に `K….md` として置かれます。
- 関連: Decision 側の書式は `docs/wikiskill/議事frontmatterテンプレート.md`、全体像は `docs/wikiskill/README.md`、止め方は `docs/wikiskill/Rollback手順.md`。

## 1. 昇格 PR の作り方

候補を承認するときは、**別の PR**(昇格 PR)を作ります。

1. `main` から作業ブランチを切る。
2. `docs/wiki/` へ移動して、候補を正式名に変えて移す(`git mv` で履歴を残す)。
   ```
   cd docs/wiki
   git mv _candidates/K….md W<YYYYMMDD>-<slug>.md
   ```
3. frontmatter を人が確定する。承認済み(`review_status: approved`)に必要なキーは次のとおり。

   | キー | 書き方 |
   |---|---|
   | `wiki_id` | `W<YYYYMMDD>-<slug>`。slug は小文字の ASCII(`[a-z0-9-]`)。ファイル名の stem と同じにする(`_archive/` に移したあとも同じ) |
   | `approved_by` | 承認した**人**の名前か GitHub ハンドル。bot 名・空は不可 |
   | `approved_at` | 承認日(日付)。候補の `created_at` 以降にする |
   | `review_by` | 見直し期限。`approved_at` より後、かつ 183 日以内 |
   | `review` | スイシン / ウタガイ / ベッカイ の3役の意見。**ウタガイは必須**で、空・「なし」・「-」・「TBD」は不可 |

   `review_status` は `approved` に変える。`needs_review` は機械が判定する状態なので、人は書かない。
4. 本文の `## 反証(ウタガイ)` は**人が確定する**。抽出が書いた下書きをそのまま承認しない。
5. `python3 scripts/wiki_validate.py` を手元で通してから PR を出す(違反があると exit 1)。
6. 小柳さんがレビューしてマージする。

## 2. AI は PR を用意してよいが、マージしない

AI(エージェント・ワークフロー)は、候補の抽出 PR や昇格 PR の**下書き**を用意してよい。承認とマージはしない。

**注意(Gate G1 の状態)**: GitHub の branch protection(Code Owners のレビュー必須)を小柳さんが有効にするまでは、「AI はマージしない」は**運用上の約束**であり、機械による保証ではありません。`.github/CODEOWNERS` は `docs/wiki/` の持ち主を小柳さんと定めていますが、branch protection が無効の間はマージを止めません。有効にするのは小柳さんの GitHub 設定です。

## 3. 却下

採用しない候補は、削除せず `docs/wiki/_candidates/` に残します。

- `review_status: rejected` にする。
- `rejected_reason` に理由を書く(理由が空だと検査が止まります)。

残しておくのは、同じ候補が再び抽出されたときに重複として扱い、同じ議論を繰り返さないためです。

## 4. conflict の解消

Decision の否定語(禁止 / しない / 却下 / やめる / 不可)を含む裁定と重なる候補は `review_status: conflict` になり、`contradictions` に相手の Decision が入ります。

- Decision と同じ向きだと説明できるときは、`acknowledged_decisions: [{"decision": <Decision の id>, "reason": <Decision と同じ向きである理由>}]` を書いて承認できます。`reason` は必須です。
- **Decision と逆向きの知識は acknowledged にしない。** Decision が優先です。その候補は却下(第3項)するか、先に Decision を議事で見直してから出し直します。

## 5. needs_review の解消

承認済みの Wiki が、承認より**新しい** Decision と矛盾すると `needs_review` になります。

- CI に警告が出ます(違反ではありません)。
- Bootstrap はその Wiki を注入しなくなります。

解消の方法は次のどちらかです。

1. 第4項と同じ `acknowledged_decisions` を付けて**再承認**する(`approved_at` と `review_by` も更新する)。
2. `docs/wiki/_archive/` へ移し、`review_status: superseded` と `superseded_by`(置き換える approved の `wiki_id`)を書く。
   - **置き換える後継のページが無いときは、この方法は使えません**(V09: superseded には superseded_by が必要 / V15: superseded_by は実在する approved の wiki_id を指す)。その場合は `docs/wiki/_candidates/` へ戻し(ファイル名は候補のときの `candidate_id`)、`review_status: rejected` と `rejected_reason`(退役の理由)を書き、承認のキー(`wiki_id`・`approved_by`・`approved_at`・`review_by`・`review`)を外します(2026-10-07 の受け入れ試験用 Wiki の退役はこの方法)。注入されず、再抽出でも重複として扱われます。後継の無い「退役」専用の状態は Phase 3 の課題です。

なお、承認済みの Wiki が根拠に引いている Experience の月は、`experience_archive.py` でアーカイブしてはいけません(根拠が読めなくなるため)。ガードは機械側に入りますが、手で扱うときも同じ規則を守ってください。

## 6. 抽出 PR のマージは「候補として受領」であって承認ではない

`wiki-candidates/<RUN_ID>` ブランチの PR をマージすると、候補が `docs/wiki/_candidates/` に入るだけです。`review_status` は `approved` ではないので、Bootstrap は注入しません。承認は第1項の昇格 PR で初めて成立します。

## 7. GITHUB_TOKEN の PR では CI が自動で走らない

ワークフローが `GITHUB_TOKEN` で作った PR には、CI(`wikiskill-tests` など)が自動では走りません(GitHub の仕様)。

- 抽出 PR の本文に貼ってある検証結果(`wiki_validate.py` の出力)を見る。これが証拠です。
- CI の結果も要るときは、PR を手で更新(空コミットの push など)して CI を起動する。

昇格 PR は人が作るので、通常どおり CI が走ります。
