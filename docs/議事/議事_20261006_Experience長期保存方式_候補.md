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

## Phase 2 時点の比較(追記 2026-10-07)

WikiSkill Phase 2 の設計書(`docs/superpowers/specs/2026-10-07-wikiskill-phase2-knowledge-wiki-design.md` 10章)で作った比較表と推奨を、本議事に転記する。**本議事の `status: deferred` は変えない**(採否は Phase 2〜3 で小柳さんが決裁する)。小柳さんは 2026-10-07 に Gate G4 として「Phase 2 は現状維持。Phase 3 で『Raw 別ストレージ + Git には索引・Decision・正式な Wiki』を中心案に再検討する」と決めた(導入議事: `docs/議事/議事_20261007_WikiSkill_Phase2導入.md`)。

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
