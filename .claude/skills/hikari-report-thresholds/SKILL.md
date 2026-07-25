---
name: hikari-report-thresholds
description: "hikari-report(日次CPAレポート基盤)のdaily_cpa.py・しきい値・撤退判定・データ接続を変更/運用するときに必ず使う。撤退基準と『未接続は明記して静かに欠損させない』ルールを守らせる。"
---

# 日次CPAレポート 判定・接続ルール(hikari-report)

hikari-report(Meta/Google広告の前日実績×リードマスターを毎朝突合し、
媒体×クリエイティブ別のCPA/CVR・撤退判定・異常検知を配信)を変更/運用するときは、
CLAUDE.md に従う。

## 守るルール

1. **撤退基準**: CPA が撤退ライン(初期値 **2,400円**)を **2週連続** で超えたら、その媒体の停止を提案する。
   - しきい値は `config/thresholds.json` で管理(目標CPA1,000円 / 撤退2,400円 / リード0件24hでアラート等)。実測4週間後に見直す。
2. **未接続を静かに欠損させない**: 未設定のSecretがあるデータソースは自動でスキップし、
   レポートに **「未接続」と明記** する。黙って欠損させたり、0を実績として扱わない。
3. **起動は Claudeスケジュールタスク(毎朝07:00)→ workflow_dispatch**。GitHub cron は遅延のため使わない。

## 変更時の手順

1. 突合・CPA/CTR/CVR・撤退判定・異常検知は `scripts/daily_cpa.py`。しきい値変更は `config/thresholds.json`。
2. データソース(Meta API / Graph API / Google Ads)を足す/変えるときは、
   Secret 未設定時に「未接続」と明記してスキップする挙動を必ず維持する。
3. 上位文書 `hikari-hq/docs/連携監査報告.md`・`運用体制.md` と整合させる。

## Runbook

- レポート未着 → Actions実行履歴 → Power Automate実行履歴。
- 「未接続」表示 → 対応する Secret を確認。
