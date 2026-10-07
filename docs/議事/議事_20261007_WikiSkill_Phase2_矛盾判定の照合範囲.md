---
decision_id: D20261007-wikiskill-conflict-scope
date: 2026-10-07
title: WikiSkill Phase 2 矛盾判定の照合範囲(否定文のみ・コード断片除外)
scope: hojo-hq/基盤
tags: [wiki, knowledge, wikiskill, phase2, conflict]
status: adopted
review_by: 2027-01-07
supersedes:
visibility: public
decided_by: 小柳
---

# 議事: WikiSkill Phase 2 矛盾判定の照合範囲(否定文のみ・コード断片除外)(2026-10-07)

Phase 2 の Conflict Detector(`scripts/wiki_schema.py` の `decision_conflicts`)で、Decision 側の何と照合するかを変える。しきい値と安全の仕組みは変えない。導入議事(`docs/議事/議事_20261007_WikiSkill_Phase2導入.md`)の §4 とウタガイ①が「次の議事で扱う」とした件。

## なぜ(背景)

### 変更前

採用済みの Decision の題と裁定に否定語(禁止/しない/却下/やめる/不可)が1つでもあれば、題と裁定の**全文**から特徴語を作っていた。候補の語(ストップワードを除く)がその特徴語に2語以上当たれば conflict にしていた。

### 問題

conflict の多くが偽陽性で、人が毎回確かめることになっていた(導入議事のウタガイ①)。実データでは、候補10件のうち9件が conflict になり、9件とも本当の矛盾ではなかった。

### 実データ 9/9 FP(2026-10-07・`knowledge_extract.py --dry-run --max 10`)

| 候補 | 当たった Decision | 全文照合で一致した語(抜粋) | うち否定文(コード断片を除く)の語 |
|---|---|---|---|
| d20261006-skill-dist-privacy-gate | D20261007-wikiskill-phase2 | skill・採用・小柳・decision・phase・実装 | 0 |
| d20261006-wikiskill-phase1 | skill-dist-privacy-gate / wikiskill-phase2 | phase・小柳・実装・議事 / wikiskill・導入・承認・task ほか16語 | 1(phase)/ 1(task) |
| d20261007-wikiskill-phase2 | skill-dist-privacy-gate | phase・小柳・skill・実装・議事 | 1(phase) |
| fk-001 | wikiskill-phase2 | コミット・push | 0 |
| fk-002 | wikiskill-phase2 | マージ・コミット・実施 | 1(実施) |
| fk-003 | skill-dist-privacy-gate / wikiskill-phase2 | 自動・変更・議事・三名体制 / pr・実測・マージ・dispatch | 1(変更)/ 0 |
| fk-004 | skill-dist-privacy-gate / wikiskill-phase2 | 実装・自動起票・議事・三名体制 / 実装・議事・ウタガイ | 0 / 0 |
| fk-006 | skill-dist-privacy-gate / wikiskill-phase2 | skill・scripts・sh・phase・配布 ほか16語 / skill・commit・phase・小柳 | 1(phase)/ 0 |
| experience-storage | skill-dist-privacy-gate / wikiskill-phase2 | phase・議事・対象・scripts / phase・議事・閾値 | 1(phase)/ 0 |

要点: 9件すべてで、否定文から当たった語は Decision ごとに1語以下だった。しきい値の2語には、否定語を含まない文の語で届いていた(phase・議事・小柳・実装・skill など、組織全体で使う語)。2件(fk-006・experience-storage)は、コード断片 `scripts/update-skills.sh` を分解した `scripts`・`sh` も一致に数えていた。残りの1件(fk-005)は conflict にならなかった(TN)。

### 原因

関係する2つの Decision で、否定語を含む文は次の2つだけ。

- 「ただし Phase 1 では `scripts/update-skills.sh` そのものを変更しない」(D20261006-skill-dist-privacy-gate)
- 「LLM 下書き(Task 10)は実施しない」(D20261007-wikiskill-phase2)

裁定文の残りは、承認の経緯や進め方の説明だった。全文から特徴語を作っていたため、否定文と関係のない説明の語で矛盾と判定していた。

## 変更後(規則①②)

- **規則①**: Decision 側で照合に使う特徴語を、題と裁定のうち**否定語を含む文(+ その文が この/その/これ/それ/上記/前記 で始まる場合は直前の1文)**だけから作る。遡るのは1文だけで、全文には戻さない。
  - 文の区切りは、句点 `。`・改行・箇条書きの頭(`-` `*` `・`・丸数字・`1.` `1)`)。`decision_memory` は裁定の改行を空白に畳むので、箇条書きの頭は空白の直後でも区切る。`/` では区切らない(実データで必要な場面が無かった)。
  - 否定語の一覧(自己出典の規則で使う)は、従来どおり全文から取る。
- **規則②**: 特徴語を作る前に、コード断片(`` `…` ``)を取り除く。パスやコマンドは一致に数えない。コード断片の中に否定語があっても、その文は否定文として扱わない。
- 実装は `wiki_schema.negation_sentences(text)`(テストできる純関数)。`_decision_feats` がこれを使う。キャッシュのキーは (title, outcome) のまま。
- 再測定(同じ10件・この議事を commit した後のツリー): conflict 9/10 → **0/10**(TP 0 / FP 0 / TN 10 / FN 0)。この議事から出る11件目の候補も conflict にならない。詳細は `docs/wikiskill/Phase2受け入れ記録.md`。

## なぜ安全性を弱めないか

変えるのは「Decision 側の何と比べるか」だけで、次の仕組みはどれも変えていない。

- しきい値: 2語(`CONFLICT_MIN_UNITS = 2`)
- 否定語の一覧(`NEGATION_WORDS`)
- Decision 優先(信頼の順は Decision が最上位)
- CONFLICT 既定(判定に例外が起きたら「矛盾あり」とする fail-closed。抽出器も検証器も同じ)
- 自動統合の禁止(Conflict Resolver は Phase 3)
- Human Approval(昇格は人の PR マージだけ)
- V12 / V13・`needs_review`・`injection_blockers`(Bootstrap で全 Decision を点検し直す)
- Private / Public の区別
- Provenance(根拠の引用)

真の矛盾を拾うテストは、すべてそのまま通る(fixture は書き換えていない)。

- A/B/C(「自動生成物は main へ直接 push しない」と、逆向きの学び)
- E2E の逆方向(矛盾した候補を注入しない)
- E2E の R5(後から採用した Decision と矛盾する承認済み Wiki を注入しない)
- V12 の各テストと `wiki_validate --selftest`(69件)

このうち R5 の fixture「…手順は使わない。この手順は採用しない」は、規則①の最初の形(否定文だけ)では取りこぼした。fixture を書き換えれば検出器の見落としを隠すことになるので、書き換えずに規則①へ「指示語で始まる否定文は直前の1文も見る」を足した。この fixture は、指示語の規則が働いていることの証拠として残している。

## 三名体制の議論

- **スイシン(推進)**: 偽陽性の原因は、比較の対象を全文にしていたことにある。しきい値を上げると真の矛盾も落ちるが、比較の対象を否定文に絞れば真の矛盾(否定文の中で2語以上が重なるもの)は残る。実データでは 9/10 が 0/10 になり、真の矛盾のテストはすべて通る。
- **ウタガイ(反対理由・必須記録)**:
  1. 禁止の中身が否定文の外に書かれていると見落とす。例として、見出しだけが否定で、条件は本文にある場合。今回の R5 の fixture のように、指示語で前の文を受けている場合は直前1文の規則で拾える。しかし2文以上前に書かれていたり、指示語を使わずに書かれていたりすると拾えない。次の2つの形は、検出できないと分かっている。
     - **件名が主題で、裁定は「却下。…」だけの形**。例: 件名「締切7日前アラートの導入」、裁定「却下。準備が間に合わないため」。件名は照合に含めないので、否定文「却下」からは語が当たらない(全文照合では 締切・日前・アラート で当たっていた)。テスト `test_known_false_negative_title_subject_rejected_outcome`(xfail strict)。
     - **文の途中の指示語**。例:「準備が間に合わないため、この案は却下」。指示語を文頭でしか見ないので、直前の文を引かない(`test_negation_sentences_mid_sentence_demonstrative_is_not_supported`)。開き括弧・かぎの直後(「(この運用は禁止)」「「この運用は禁止」」)は文頭として扱う。
  2. 文の区切りを誤る。句点の無い箇条書きや、改行が空白に畳まれた裁定では、箇条書きの頭を空白の直後で見分けている。`- ` を使わない書き方や、表の中の文は1文として扱われ、長すぎたり短すぎたりする。
  3. 否定語の一覧に無い動詞(「使わない」「送らない」など)は、もともと否定文として数えていない。そのため、全文照合のときに別の文の「しない」に助けられて拾えていた矛盾が、今回の変更で落ちうる。例: 裁定「締切7日前のアラートは送らない。Phase 1 では設定を変更しない」と、候補「締切7日前にアラートを送ると登録率が上がる」。全文照合では検出していたが、今回の変更で検出できなくなった(回帰)。テスト `test_known_regression_negation_word_only_in_unrelated_sentence`(xfail strict)。全文照合なら当たっていたことは `test_regression_shape_was_caught_by_whole_text_matching` で確かめている。「送らない」だけの文は、もともと検出していなかった(`test_known_false_negative_verb_not_in_negation_words`)。否定語リストの拡張は別議事で扱う。
  4. 否定語を「言及」しているだけの文も否定文として数える。この議事の裁定の下書きでは、ベッカイの案を「禁止事項」欄と書いた1文が否定文になった。その1文が、Phase 2 導入議事の候補に `ベッカイ`・`見直` の2語で当たり、偽陽性を1件生んだ(仮の worktree で実測)。そこで裁定ではこの語を使わずに書いた。
  5. コード断片を除くと、禁止の対象がパスだけで書かれた Decision(「`x.sh` は変更しない」など)とは、ほぼ一致しなくなる。
- **ベッカイ(別解・前提を疑う)**: そもそも否定語の推測に頼らず、Decision に人が「禁止事項」の欄を書き、そこだけと照合する設計の方が確実ではないか。書き手の負担は増えるが、文の区切りや指示語の推測が要らなくなる。
  - **件名を常に比較する案(小柳判断)**: 否定文に加えて、件名を常に照合の対象に入れる案。ウタガイ①の「却下。…」の形は拾える(試算で 締切・日前・アラート が当たる)。その代わり、実データの同じ10件のうち **5件が偽陽性に戻る**(FP 0 → 5)。戻るのは wikiskill-phase1、wikiskill-phase2、fk-003、fk-006、experience-storage で、fk-006 は skill-dist-privacy-gate と skill・scope・配布・検査 などで当たる。この議事から出る11件目の候補も conflict になる。試算は 2026-10-07 の dry-run で、コードには入れていない。

## 裁定

承認(2026-10-07 小柳さん)。Decision 側の照合の対象を、否定語を含む文(+ その文が この/その/これ/それ/上記/前記 で始まる場合は直前の1文)に絞り、コード断片を除く。しきい値2語・否定語の一覧・自己出典の規則・fail-closed・V12/V13・Human Approval は据え置く。

- ウタガイ①②④は見直し条件で監視する。③は回帰の形として `test_known_regression_negation_word_only_in_unrelated_sentence`(xfail strict)に残し、否定語リストの拡張は別議事とする。⑤は実データで観察する。
- R5 の E2E fixture は書き換えず、指示語の規則で検出を保つ。
- ベッカイの案(Decision に人が専用の欄を書き、その欄と照合する設計)は、次の見直しで、規則による照合と比べる候補にする。

## 見直し条件

次のいずれかが起きたら、期限(2027-01-07)を待たずに再議論する。

- 次に実データを測り直したとき、真の矛盾(TP)を1件以上取りこぼしていた
- conflict の偽陽性率が再び 50% を超えた
- 否定語の一覧に無い動詞で書かれた禁止(「使わない」「送らない」など。既知の偽陰性の類型)が、実際の Decision で見つかった(否定語リストの拡張は別議事)
- 件名が主題で裁定が「却下。…」だけの Decision が、実際に採用された(件名を常に比較する案を小柳さんが判断する。試算では実データ10件中 FP 5件が戻る)

## Rollback

この変更の commit(`fix(wikiskill): 矛盾判定の照合範囲を否定文だけに限定しコード断片を除外(しきい値・安全原則は不変)`)を revert する。全文照合に戻る。議事の commit は残してよい(記録として)。

## 関連

- 導入議事: `docs/議事/議事_20261007_WikiSkill_Phase2導入.md`(§4 実測した偽陽性・ウタガイ①)
- 受け入れ記録: `docs/wikiskill/Phase2受け入れ記録.md`(矛盾判定の再測定)
- 運用ガイド: `docs/wikiskill/README.md`(9章)
