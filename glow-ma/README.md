# GLOW M&A・不動産 企業リレーション台帳

設計書: `docs/superpowers/specs/2026-07-26-glow-ma-relation-system-design.md`

## これは何か

GLOWのM&A・不動産事業向けの非公開営業支援基盤。実データ(企業名・対応履歴等)は
Googleスプレッドシートに保持し、このディレクトリにはGAS(Google Apps Script)の
ロジックのみを置く。**実データは一切このリポジトリにコミットしない。**

## セットアップ

(Task 7で追記)

## テスト

```bash
node --test tests/glow_ma_schema.test.mjs tests/glow_ma_dedupe.test.mjs tests/glow_ma_csv_import.test.mjs
```
