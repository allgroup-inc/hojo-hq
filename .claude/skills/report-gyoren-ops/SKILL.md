---
name: report-gyoren-ops
description: "report-hq(業連自動配信システム)のgyoren_main.py・gyoren.yml・配信タイミング・監査を変更/運用/デバッグするときに必ず使う。起動遅延ガード・❺Q再配信・欠損の明示という運用ルールを守らせる。"
---

# 業連配信 運用ルール(report-hq)

report-hq(日時業連シート→チーム別レポートHTMLメールを毎日5回、全社約73名へ自動配信)の
コード変更・運用・デバッグをするときは、設計運用書(CLAUDE.md)の要点に従う。

## 絶対に壊してはいけない運用ルール

1. **起動遅延ガード**: 予定時刻から `MAX_DELAY_MIN`(コード既定120分 / workflowで**180分**指定)を
   超えて遅れた起動は、送信せず停止する。cronの遅延実績1.5〜3hを飲み込み、前日の❺Qを翌朝
   誤配信する事故を防ぐため。
   - `dry_run` 時と `allow_stale=1` では無効化される。
   - 監査タスクの❺Q再配信(0:30 / 遅れ45分)は通過する必要がある。判定は `delay_minutes()` / `Q_SCHEDULE`。
2. **❺Q再配信は監査タスクのみ**: 前日5回分の成否を点検し、❺Q欠落時のみ自動再配信する。
3. **静かに欠損させない**: データ取得やトークンに異常があれば、黙って落とさず異常として扱う(プッシュ通知/監査)。
4. **併走禁止**: 将来Power Automate繰り返しトリガーへ移行する際は cron を撤去する(cronとPAの二重起動をしない)。

## 変更時の手順

1. Qブロック行位置・列マッピング(COLS)・HTMLデザインは `scripts/gyoren_main.py` に集約されている。ここを直す。
2. 送信時刻・遅延ガード・inputs(force_q / dry_run / allow_stale)は `.github/workflows/gyoren.yml`。
3. 宛先はコードではなく Power Automate フロー側で管理(`config/recipients.json` は現在未使用)。宛先変更をコードでやらない。
4. 変更を加えたら **必ず CLAUDE.md(設計運用書)も更新する**(AIセッション引き継ぎ文書のため)。
5. 検証は `dry_run=1`(Artifacts「gyoren-preview」にプレビュー)で行い、本番宛先に誤送信しない。

## Runbook

- レポート未着 → Actions実行履歴 → Power Automate実行履歴 の順で確認。
- 遅延で停止 → 遅延ガードの想定挙動。再送が必要なら監査タスク or `allow_stale=1` を検討。
