---
decision_id: D20261007-wikiskill-phase2
date: 2026-10-07
title: WikiSkill Phase 2 導入(Knowledge Wiki)
scope: hojo-hq/基盤
tags: [wiki, knowledge, wikiskill, phase2]
status: adopted
review_by: 2027-04-05
supersedes:
visibility: public
decided_by: 小柳
---

# 議事: WikiSkill Phase 2 導入(Knowledge Wiki)(2026-10-07)

本議事は、Phase 2 の設計判断を将来の Memory Bootstrap で復元できる正式な Decision として残すためのもの。小柳さんは設計書 v1.1 と実装計画を 2026-10-07 に承認した(Gate G1〜G6 の決裁は下記)。Task 9(PR・マージ・タグ `wikiskill-phase2-v1`)は別承認。

## なぜ(背景)

- Phase 1 で Experience(機械記録)は残るが、それ自体は「知識」にならない。同じ失敗(FK-001〜FK-006 など)が、記録があるのに繰り返される。新しいセッションは記録を自分から読み解かない。
- 失敗台帳と再発防止メモは人が手で書くので、書き忘れた学びは消える。経験から「学びの候補」を機械が拾い、人が確かめて正式な知識にする経路が無い。
- 誤った知識を正式な知識にするより、正しい知識を取りこぼす方が軽い。だから昇格は人だけが行い、機械は候補を出すところまでにする。

## 前提

- 承認は人のみ。承認済み(`review_status: approved`)の Wiki だけが Bootstrap に注入される。候補(`docs/wiki/_candidates/` 配下)は注入しない。
- 信頼の順は Decision > 失敗台帳 > 再発防止 > Wiki > 候補 > Experience。Wiki は Decision と矛盾したら止まる(Decision が勝つ)。
- Skill には反映しない。Skill の自動更新・自己改善は Phase 2 に含めない。
- 対象は public の記録だけ。private の記録・他リポジトリは読まない。本リポジトリは PUBLIC で、候補もブランチを push した時点で公開される。
- 110 Skills・13リポ配布(`scripts/update-skills.sh`)・`.claude/commands/` は変更しない。

## 決定内容

1. **Gate G1〜G6(小柳さん 2026-10-07 決裁)**
   1. **G1**: `.github/CODEOWNERS`(`docs/wiki/` の持ち主は小柳さん)は PR に含める。**branch protection(main に Code Owners の承認必須)は小柳さんが GitHub 設定で有効化する**(未設定の間、「AI がマージしない」は運用上の約束であり、機械の保証ではない)。権限上自動設定できない場合は、他の手段で代替せず、必要な設定を報告して止める。
   2. **G2**: 抽出 workflow(`knowledge-extract.yml`)は `workflow_dispatch` のみ。定期自動実行(cron・schedule)は禁止。実績ができた後に別の議事で再検討する。
   3. **G3**: LLM による下書きは不承認(Task 10 は実施しない)。規則ベースの抽出だけ。
   4. **G4**: Experience の保存方式は Phase 2 では変えない。Phase 3 の中心案は「Raw Experience は別ストレージ、Git には索引・Decision・正式な Wiki」(設計書10章の ②+⑥)。比較は #24 の議事(`docs/議事/議事_20261006_Experience長期保存方式_候補.md`。`status: deferred` のまま)に追記済み。
   5. **G5**: `docs/wiki/` の Obsidian 同期は許可。ただし `_candidates/` を正式な知識として使ってはならない。Bootstrap が読むのは `review_status: approved` の正式な Wiki だけ。
   6. **G6**: Phase 2 の実装開始を承認。Release/Tag `wikiskill-phase2-v1` は、Task 9 の報告を小柳さんが最終承認してから。
2. **仕組み(Candidate → Validation → Human Approval → Official Wiki)**
   1. 抽出(`scripts/knowledge_extract.py`)は commit 済みで HEAD から変わっていない public かつ hojo-hq の Experience 行と、commit 済みの議事・失敗台帳だけを読む。書き込み先は `docs/wiki/_candidates/` の `K….md` だけ。書く前に自分の出力を検証器に掛け、違反した候補は書かない。排他は `.claude/locks/knowledge-extract.lock`(30分・heartbeat。stale の自動解除は終了印または pid 死亡のときだけ。それ以外は `--break-stale-lock`)。
   2. 検証(`scripts/wiki_validate.py`)は V01〜V15。引用の最小長 `MIN_QUOTE = 8`、見直し期限は承認日から `MAX_REVIEW_DAYS = 183` 日以内、`approved_at >= created_at`、題が既存の Wiki・他の候補と双方向で 0.6 以上似ていたら重複として止める(`duplicate_of` の明記が必要)、禁止語は不可視文字を除いて検査する。
   3. 正式な Wiki は `docs/wiki/` 直下の `<wiki_id>.md`。置き換えられたものは `docs/wiki/_archive/`。昇格の道は人がマージする PR だけ(`docs/wikiskill/Wiki昇格手順.md`)。
   4. Bootstrap は `[Wiki]` 行に、題・要約(160字)・根拠の件数(Exp / Decision / FK)・承認者・承認日・パスを出す。
   5. 同義語表 `docs/wiki/_synonyms.txt`(初期4行: マージ/merge、コミット/commit、締切/期限/deadline、議事/decision。完全一致のみ)。これらの語では Bootstrap の結果が変わりうる。
   6. 矛盾検知: 採用済みで test でない Decision の題+裁定に否定語(禁止/しない/却下/やめる/不可)があり、ストップワード除去後の共有語が2つ以上あるものを conflict とする。候補自身の出典 Decision は、候補が否定語を言い直している間だけ除く(語の一致だけを見る。向き(極性)は見ない。Phase 3 の課題)。承認済み Wiki より新しい Decision が矛盾したら `needs_review`(CI は警告のみ。Bootstrap は全 Decision を再点検して注入を止める)。
   7. 部分停止は `.claude/wiki.off`(`[Wiki]` だけ止まる)。全体停止は `.claude/memory.off`(従来どおり記録も注入も止まる)。
   8. Archive の防護: `experience_archive.py --archive` は `docs/wiki/` 配下の Wiki・候補・退役ページすべてが根拠に引いている月を固めない(`--force` と監査記録でだけ上書き)。
3. **Phase 3 へ持ち越し**: Skill Proposer / Validator / Evolution Gate、Conflict Resolver(自動統合)、Skill Metrics、LLM 下書き(G3)、Experience の索引と移動(#24)、月次 cron(G2)、極性を見る矛盾判定、Archive を考慮した V03(索引の `pinned`)、他リポジトリの読み取り。
4. **実測した偽陽性(2026-10-07・実データ)**: 候補9件のうち5件が conflict と判定された。5件はすべて長い1件の Decision(`D20261006-skill-dist-privacy-gate`)から出ており、4件は組織全体の語(議事・三名体制・実装・phase・小柳)だけで一致、1件(SKILL.md と失敗台帳の候補)だけが本当の矛盾の可能性がある。閾値は計画どおり変えない。後で直す案(別の議事が要る): 否定語を含む文だけで照合する。**試算(参考)**: Task 4 のレビュー時の試算(stop語除外・自己出典除外を入れる前の 6 件時点)で、否定語を含む文だけで照合すると 6→3 件、さらに自己出典を除外すると 2 件。出荷版の実測は 9 件中 5 件。**追記(2026-10-07・最終レビュー)**: この議事を commit した後の今のツリーで同じ dry-run を測ると、候補10件(上限)のうち9件が conflict。9件のうち8件はこの議事そのもの(`D20261007-wikiskill-phase2`。phase・議事・小柳・skill・承認などで一致)、6件は `D20261006-skill-dist-privacy-gate` と重なる。長い議事が増えるほど偽陽性が増える。閾値と照合の範囲は変えていない(変えるには別の議事が要る)。
   - **照合範囲の修正(2026-10-07)**: `docs/議事/議事_20261007_WikiSkill_Phase2_矛盾判定の照合範囲.md`(否定語を含む文 + 指示語で始まる否定文の直前1文だけ・コード断片を除く。しきい値は2のまま)。同じ10件の再測定で conflict は 9/10 → 0/10。

## 代替案

- LLM による抽出を MVP に入れる案: 却下。幻覚で、根拠の無い「学び」が公開リポに載る。規則ベースで始め、LLM は G3 のとおり不承認。
- 候補を Bootstrap に低信頼で出す案: 却下。未承認のものが判断に混ざる。注入は承認済みだけ。
- Obsidian 側に Wiki を書く案: 却下。正本は GitHub。Obsidian は hojo-hq を映す鏡で、鏡に書いても元には映らない。
- 月次 cron で自動抽出する案: 却下(G2)。レビュー負債が溜まるかどうかを実績で見てから。
- Experience の保存方式を同時に変える案: 却下(G4)。#24 を決裁する前に方式を変えない。

## 三名体制の議論

- **スイシン(推進)**: 既存資産と同じ PR・CI・CODEOWNERS で完結する。新設は、抽出・検証・`[Wiki]` 注入の3点に絞る。承認は昇格 PR のマージだけで、新しい承認画面や外部サービスを足さない。
- **ウタガイ(反対理由・必須記録)**:
  1. 否定語による矛盾判定は粗く、偽陽性の conflict がレビュー負債になる。実データの実測で候補9件のうち5件(5/9)が conflict になり、うち4件は組織全体の語だけで当たった。この議事を足した後は候補10件のうち9件(9/10。2026-10-07 実測)になり、9件のうち8件はこの議事自身と重なっている。見落とすより騒ぎすぎる方向に倒れており、人が毎回確かめることになる。
  2. 公開リポジトリでは、ブランチを push した時点で公開される。検証器が危ないものを見逃す(偽陰性)と、レビューの前に公開されてしまう。マージで公開されるのではない。
  3. 承認が小柳さんに集中し、候補が溜まると形骸化して「通すだけ」になる。branch protection(G1)が無効の間は、AI がマージしない保証も運用上の約束にすぎない。
  - 受け入れ条件: 抽出の実行は dispatch のみ(G2・cron 禁止)/ 1回10件まで / conflict の偽陽性件数を週次で数える / push 前に検証する(検証に通らない候補は書かず、PR 本文に検証出力を貼る)/ 入力は commit 済みの public 行だけ(`MIN_QUOTE` と禁止語検査で、引用の丸写しと機密の混入を止める)。
- **ベッカイ(別解・前提を疑う)**: そもそも Wiki は要るのか。失敗台帳と再発防止メモで足りるなら、Phase 2 は同義語表と検索語行の改善だけで十分ではないか。MVP の後に、`[Wiki]` が実際に採用された件数で再評価する。

## 裁定

承認(2026-10-07 小柳さん)。承認済みの知識だけを `[Wiki]` で注入し、昇格は人だけ・抽出は dispatch のみ・LLM 下書きと Skill 反映は無し。Task 9(PR・マージ・タグ)は別承認。

- ウタガイの3点は受け入れ条件として実装に取り込む(dispatch のみ・1回10件・push 前検証・commit 済み入力のみ)。偽陽性は閾値を変えず、実測を残して次の議事で扱う。
- ベッカイの問いは棄却せず、MVP 後の再評価で答える(採用件数が少なければ縮小する)。
- 実装は Subagent-driven で進める。LLM 下書き(Task 10)は実施しない。

## 見直し条件

次のいずれかが起きたら、期限(2027-04-05)を待たず再議論する。

- Rollback 条件 RB1〜RB5(`docs/wikiskill/Rollback手順.md` の Phase 2 節)のどれか(RB1 検証器の偽陰性で誤った知識が approved に入った / RB2 private 由来のテキストが候補に出た / RB3 Bootstrap の `slow` が週3回 / RB4 Baseline が REGRESSION / RB5 Decision と矛盾する Wiki が注入された)
- 3か月たっても approved の Wiki が 0 件(仕組みが使われていない。ベッカイの問いへの答えが「要らない」)
- conflict と判定されたもののうち、8割以上が偽陽性だった(矛盾判定の作り直しが要る)

### 既知の Performance Debt

SessionStart hook の単発計時テスト `test_hook_session_start_under_500ms_on_real_copy` は、この実行環境では単独でも 0.5 秒を跨ぐことがある(実測 0.512 秒。Phase 1 単体 0.36〜0.42 秒、Phase 2 の追加分は約 0.04 秒)。
ロジックの回帰ではなく性能余裕の不足。基準 0.5 秒は変えず、最適化は Phase 3 着手時に見直す(詳細: `docs/wikiskill/Phase2受け入れ記録.md` の「既知の Performance Debt」)。

## Rollback

`docs/wikiskill/Rollback手順.md` の「Phase 2」節(部分停止 `.claude/wiki.off` から、Wiki 1件の revert、workflow の無効化、PR 全体の revert まで段階別)。

## 関連

- 設計書: `docs/superpowers/specs/2026-10-07-wikiskill-phase2-knowledge-wiki-design.md`
- 実装計画: `docs/superpowers/plans/2026-10-07-wikiskill-phase2-knowledge-wiki.md`
- 運用ガイド: `docs/wikiskill/README.md`(Phase 2 章)
- 昇格手順: `docs/wikiskill/Wiki昇格手順.md`
- 受け入れ記録(Task 8 で記入): `docs/wikiskill/Phase2受け入れ記録.md`
- Phase 1 導入議事: `docs/議事_20261006_WikiSkill_Phase1導入.md`
- #24 Experience 長期保存方式: `docs/議事/議事_20261006_Experience長期保存方式_候補.md`
