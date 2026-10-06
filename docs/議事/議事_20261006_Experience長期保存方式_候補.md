---
decision_id: D20261006-experience-storage
date: 2026-10-06
title: Raw Experience を Git へ長期保存し続ける設計の適否(候補・Phase 2〜3)
scope: hojo-hq/基盤
tags: [experience, storage, git, wikiskill, phase2]
status: deferred
review_by: 2027-01-06
supersedes:
decided_by: 小柳(Phase 2〜3 で決裁)
---

# 議事: Raw Experience を Git へ長期保存し続けるか(候補・2026-10-06)

本議事は Phase 2〜3 で正式に決裁する候補。WikiSkill Phase 1 の Decision Memory が読む形式で記録する。
小柳さん判断(2026-10-06): Phase 1 の最後に、保存方式は変えない。

## なぜ(背景)

Phase 1 は、Experience の原本(JSONL)を Git にコミットして保存している(`.claude/experience/YYYY-MM/session-*.jsonl`)。1行はおよそ220バイト。全セッションがコミットすると、警告の3MB・上限の10MB(`scripts/experience_archive.py --check`)に1〜2か月で届く可能性がある。

そこで Raw(原本)を Git に置き続けてよいのかを、Phase 1 の導入判断とは分けて決める。Phase 1 では方式も閾値も変えない。

## 前提

- **gzip や archive をしても、Git 履歴のサイズは減らない**。圧縮したファイルを追加しても、過去にコミットした原本の blob は履歴に残る。Archive が減らすのは作業ツリーの見かけの容量だけ
- 現在の閾値(警告 3MB・上限 10MB・Archive は 180日経過後)は変更しない
- 本リポジトリは **PUBLIC**。履歴に入った内容は公開され、後から消せない(公開可否の検査は `scripts/check_experience_privacy.py`)

## 代替案(比較候補)

- Git 継続(現行): 仕組みが最小で監査しやすい。履歴が増え続け、公開リポでは誤混入が永久に残る
- Private 専用 repository: 公開リスクは消える。別 repo の権限・同期・CI の仕組みが要り、新セッションでの取得経路が増える
- DB: 検索・集計が速い。運用と費用が増え、Git の「正本は GitHub」の原則から外れる
- Object Storage: 容量の心配が無い。認証情報の管理が要り、Decision との結びつき(出典の追跡)が弱くなる
- Raw は外部保存・要約のみ Git: 履歴は肥大せず、Wiki(Phase 2)と整合する。Raw の復元は外部保存に依存し、要約の質が結果を左右する
- 保存期間の短縮: 最も単純。古い経験を捨てるので、遠い過去の失敗の根拠が辿れなくなる

## 三名体制の議論

- **スイシン(推進)**: Git 継続は仕組みが最小で監査可能。Decision・失敗台帳・Experience が同じ Git の履歴に並び、出典の追跡が一番簡単。Phase 1 の稼働実績(受け入れ記録)もこの方式で取れた
- **ウタガイ(反対理由・必須記録)**:
  1. 公開リポの履歴は削除できないため、誤って入った情報は永久に残る(公開可否の検査は通過後の保証であり、検査をすり抜けた分は戻せない)
  2. 履歴肥大で clone / CI が遅くなり、全セッションの固定費になる
  3. Archive は見かけの容量しか減らさない(gzip を足しても過去の原本 blob は履歴に残る)
- **ベッカイ(別解・前提を疑う)**: 記録すべきは Raw ではなく「学び」ではないか。Raw は外部保存・要約のみ Git にする案が、Wiki(Phase 2)の設計と整合する。Raw を残す目的(再現・監査)が本当に長期で要るのかも先に確かめたい

## 裁定

未決。Phase 2〜3 の正式な Decision の対象とする。採否が決まるまでは Phase 1 の方式を継続し、`python3 scripts/experience_archive.py --check` で合計サイズを監視する(閾値・方式は変えない)。

## 見直し条件

- Experience の合計が警告の 3MB に到達した時
- Phase 2 の Wiki 設計に着手する時
- 見直し期限: 2027-01-06(期限切れは自動で再議論)

## 関連

- 設計書: `docs/superpowers/specs/2026-10-06-wikiskill-integration-design.md`
- 運用ガイド: `docs/wikiskill/README.md`
- Rollback・Archive の手順: `docs/wikiskill/Rollback手順.md`
- 失敗台帳: `docs/失敗台帳.md` FK-006(配布・公開リポへの拡散。履歴に入った内容が戻せない点で同型)
