---
decision_id: D20261006-wikiskill-phase1
date: 2026-10-06
title: WikiSkill Phase 1(記憶基盤)の導入
scope: hojo-hq/基盤
tags: [memory, hooks, wikiskill, skills, decision-memory]
status: adopted
review_by: 2027-04-04
supersedes:
decided_by: 小柳
---

# 議事: WikiSkill Phase 1(記憶基盤)の導入(2026-10-06)

本議事は、この設計判断そのものを将来の Memory Bootstrap で復元できる正式な Decision として残すためのもの(小柳さん指示 2026-10-06)。

## なぜ(背景)

- セッションが終わると理由・前提・反対意見が散逸し、同じ議論と同じミスが繰り返される。議事や失敗台帳に書いてあっても、新しいセッションは自分から探さない。
- Skill(110本)がどれだけ役に立っているかの実績がまだ測れていない。使われ方を機械的に残す土台が無いと、Skill の改善を根拠に基づいて決められない。
- 2026-10-06 の基線確認(FK-006)で、禁止語が Skill 配布経由で11リポに広がっていたことが分かった。記憶の仕組みを入れるなら、同じ型の事故(公開リポに載せてはいけないものを載せる)を新しく作らないことが前提になる。

## 前提

- 正本は GitHub。本リポジトリは PUBLIC で、Bootstrap は現在のリポ内しか読まない(他リポ・private を横断しない)。
- Experience の原本も Git にコミットする(`.gitignore` に入れるのは `_local/`・`_audit.log`・`memory.off`・`locks/` のみ)。
- 110 Skills と13リポへの配布(`scripts/update-skills.sh`、`.claude/commands/`)は変更しない。
- Phase 1 の範囲は記録と取り出しまで。Skill の自動改善・自動更新は含めない。
- 既存の赤(privacy 9件 / skill_validation 5件 / scripts tests 2件)は Baseline Debt として固定し、是正は別タスクで行う。

## 決定内容

1. **修正4点(小柳さん 2026-10-06)**
   1. Logger の silent fail を禁止する。記録・検索の失敗は作業を止めないが、必ず `.claude/experience/_audit.log` に残し、hook の `systemMessage` で利用者に警告する。
   2. Bootstrap は毎セッション自動で動かし、関連する情報だけを出す。
   3. Experience と Decision を分け、Decision を上位の信頼として扱う(信頼順: Decision > 失敗台帳 > 再発防止メモ > Experience)。
   4. Phase 1 は Skill の自動改善・自動更新を行わない。
2. **Decision 8件**
   1. Bootstrap は ON。関連する情報のみ出す。
   2. 見直し期限は決定ごとに設定する。未指定なら180日。
   3. 三名体制は半自動で運用し、最終 Gate は人間(小柳さん)が持つ。
   4. Experience は原本を保持し、定期的に Archive(180日超の月を gzip)し、肥大化を監視する(警告3MB・失敗10MB)。
   5. GLOW世界関連は初期 Private。迷ったら Private。Public 化は明示的に判定して行う。
   6. Knowledge Extractor は AI による抽出を可とし、正式な Wiki への昇格は人間が確認する。
   7. 緊急 Rollback は守り部が実施でき、事後48時間以内に小柳さんの Gate を通す。
   8. Lock の timeout は30分。heartbeat で延長し、更新が止まったものは stale と判定する。
3. **Baseline Debt の扱い(小柳さん 2026-10-06)**: 既存の赤を固定して Phase 1 を継続する。各 Task の終了時に `python3 scripts/baseline_debt.py --compare` が SAME か IMPROVED であることを確認し、REGRESSION なら停止する。既存の赤の是正は Phase 1 と分離した別タスク(決裁キュー)で扱う。

## 代替案

- Obsidian 側に書く案: 却下。Obsidian は hojo-hq を映す鏡であり、鏡に書いても元には映らない。
- 全 Wiki を毎回投入する案: 却下。トークンを浪費し、関連の薄い情報で本題が埋もれる。
- Skill の自動更新を Phase 1 に含める案: 却下。人間の Gate が必須であり、記録と取り出しが固まる前に自動更新を入れると原因の切り分けができない。

## 三名体制の議論

- **スイシン**: 既存資産(議事・失敗台帳・再発防止メモ・Skill)を再利用し、新設は最小にする。記録(Experience Logger)と取り出し(Memory Bootstrap)の2点だけを足し、Decision は既存の議事に frontmatter を付ける形で扱う。
- **ウタガイ(反対理由・必須記録)**:
  1. hook を4本追加するのは全セッションの固定費になる。500ms の上限を守れる保証が無い。
  2. Experience を公開リポジトリに置くこと自体が、情報漏えいの面を増やす。記録範囲を縛っても、note は自由記述になる。
  3. 関連度の照合は粗く、誤った Decision を関連として出すと、利用者の前提を誤らせる。
  - 受け入れ条件: 時間上限をテストで固定する / note は CI の検査対象にする / 出力には出典と見直し期限を必ず付ける / Baseline Debt で新しい赤を増やさない。
- **ベッカイ**: Decision は議事に既にある。足りないのは「取り出し」であり、記録ではない。だから Bootstrap を Phase 1 の中心に置く(MVP 比較で Bootstrap 案を採る根拠)。

## 裁定

2026-10-06 小柳さん承認。Task 9(PR・マージ・タグ)は別承認。

- 内容は上記と設計書 v1.1 冒頭のとおり。ウタガイの3点は受け入れ条件として実装に取り込む。
- 実装は Subagent-driven で進める。

## 見直し条件

次のいずれかが起きたら、期限(2027-04-04)を待たず再議論する。

- hook の実行が 500ms を超える事象が週3回
- Experience の privacy 検査で違反が1件
- Memory Bootstrap の誤関連が利用者申告で3件
- Baseline Debt が悪化(REGRESSION)

Phase 1 の受け入れ条件(新しい privacy 違反 0 / 新しい skill_validation 失敗 0 / Baseline 非悪化 / 110 Skills 不変 / 13リポ配布不変 / セッション A で決めた内容をセッション B が復元)は `docs/wikiskill/Phase1受け入れ記録.md` に記録する。

## Rollback

`docs/wikiskill/Rollback手順.md`(停止スイッチ `.claude/memory.off` から、PR 全体の revert まで段階別)。

## 関連

- 設計書: `docs/superpowers/specs/2026-10-06-wikiskill-integration-design.md`
- 実装計画: `docs/superpowers/plans/2026-10-06-wikiskill-phase1-memory-foundation.md`
- 候補議事: `docs/議事_20261006_Skill配布前Privacy検査_候補.md`(決裁待ち)
- 失敗台帳 FK-006(`docs/失敗台帳.md`)
