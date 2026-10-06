---
decision_id: D20261006-skill-dist-privacy-gate
date: 2026-10-06
title: 自動配布対象Skillは配布前にPrivacy/Scope検査を通す(候補)
scope: hojo-hq/基盤
tags: [skills, privacy, update-skills, distribution]
status: deferred
review_by: 2026-12-06
decided_by: 小柳(決裁待ち)
---

# 議事: 自動配布対象Skillは配布前にPrivacy/Scope検査を通すか(候補・2026-10-06)

本議事は決裁待ちの候補。WikiSkill Phase 1 の Decision Memory が読む形式で記録する。
台帳: `docs/失敗台帳.md` FK-006 / 現状の固定: `docs/wikiskill/baseline-debt.json`

## なぜ(背景)

2026-10-02に追加された8つのSKILL.mdと、2026-10-06にweekly-gakubiが自動生成した週次の学び(commit 6044bb918 / f065ef5a7 / 68343664b)の本文が、`scripts/check_repo_scope.py`の`FORBIDDEN_CONTENT`の1語目(kakei-crm側の統合名)に触れ、公開リポジトリの`repo-scope`CIがmainで赤になった。赤のまま、2026-10-05のPhase 4配布(`docs/Phase4_完了レポート_2026-10-05.md`)で`scripts/update-skills.sh`が11リポジトリへスキルをコピーした。

- なぜ止まらなかったか: ①`repo-scope`は赤でも配布cron・マージを止めない ②Phase 4の配布前点検は「DRY_RUNで差分確認」のみでCI結果を見ていない ③`update-skills.sh`自体に配布前検査が無い
- 影響: hojo-hqと配布先10リポジトリ。緊急度分類(2026-10-06)で顧客の個人情報・M&A情報・実認証情報・非公開戦略の流出は確認されず、内容は名称と社内システムの概要例にとどまる
- 現状: Baseline Debtとして固定済み。是正と再配布は別タスク(決裁キューに起票)

## 前提

- `scripts/update-skills.sh`は WikiSkill Phase 1 では変更しない(本議事の採否に関わらず)
- スキル配布は週次cronで動く
- 配布元はhojo-hqのみ(配布先はコピーを受け取るだけで、配布先からの逆流は無い)

## 代替案

- a: `update-skills.sh`の冒頭で`check_repo_scope.py`を実行し、失敗なら配布を中止する
- b: `repo-scope`CIの結果をGitHub APIで見て、赤なら配布を中止する
- c: 配布先の各リポジトリのCIにも`repo-scope`相当の検査を入れる

## 三名体制の議論

- **スイシン(推進)**: aが最小で即効。配布元の検査を配布の入口に1か所足すだけで、今回の拡散経路(検査が赤でも配布が走る)を直接塞げる
- **ウタガイ(懐疑・反対理由。必須)**:
  1. 配布元の検査だけでは、配布先固有の禁止語を見ない。配布元で通っても配布先の方針に反する文面は素通りする
  2. 配布cronが止まると、drift検知(スキル数の監査)も一緒に止まる。検査の失敗が「静かな停止」になる
  3. 検査の誤検知が1件あるだけで、全リポジトリのスキル更新が止まる副作用がある
- **ベッカイ(別解・前提を疑う)**: 「禁止語検査で止める」より、そもそも「禁止語を含む文書を書かせない」方が上流ではないか。スキル作成時の雛形やskill-creatorにscope確認を組み込めば、検査に落ちる前に防げる。検査で止めるのは最後の網にとどめる

## 裁定

未決(小柳さん決裁待ち)。Phase 1 では`update-skills.sh`を変更しない。採否が決まるまでは、Baseline Debtの比較(`python3 scripts/baseline_debt.py --compare`)で、Phase 1 が違反を増やしていないことだけを確認する。

## 見直し条件

- 是正タスク(禁止語を含むSKILL.mdと学び文書の是正・11リポ再配布・skill_validation不適合の是正)が完了した時
- 同型の拡散(検査が赤のまま配布が進む)が再発した時
- 見直し期限: 2026-12-06(期限切れは自動で再議論)
