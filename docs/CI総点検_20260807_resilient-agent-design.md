# CI総点検 2026-08-07 — resilient-agent-designチェックリスト適用

対象: `.github/workflows/` 全23系統。8/4の並走事故(コンフリクトマーカー入りJSONの公開)の
再発防止型を全ワークフローへ横展開する総点検。チェックリストは
`.claude/skills/resilient-agent-design`(8項目)。

## 実施内容(このコミット)

1. **concurrency全系統完備**: 未導入だった12本(fukugiiro-audit / fukugiiro-ci /
   fukugiiro-fetch / fukugiiro-weekly-report / gas-setup / glow-ma-ci / line-test /
   mikata-audit / nobishiro-ci / plausible-check / send-email / weekly-report)へ
   `concurrency: {group: <name>, cancel-in-progress: false}` を追加。
   既導入11本(update/healthcheck/social-post等)と合わせ**23/23**。
2. **pushリトライの強化を横展開**: weekly-report / fukugiiro-fetch の
   `git pull --rebase` を update.yml と同型(`-X theirs`+失敗時`rebase --abort`)へ。
   生成物コンフリクトでマーカーが作業ツリーに残る事故経路を全系統で遮断。
3. 全23本のYAMLパース妥当性を機械確認。

## チェックリスト8項目の判定

| # | 項目 | 判定 | 根拠/残課題 |
|---|---|---|---|
| 1 | 4層分解(Trigger/Workflow/Agent/Guardrail) | ✅ | 収集・整形=コード、Claude API=判断のみ、社外副作用=承認ゲート |
| 2 | 完了条件をシステム側で判定 | ✅ | update=デプロイ前JSON検証ゲート、healthcheck=毎朝の機械判定 |
| 3 | 状態の外部保存 | ✅ | data/のJSON+Gitコミット(監査ログ兼用)+企業台帳(GAS) |
| 4 | 副作用のべき等性 | ✅ | weekly-report=schedule限定+push時dry-run。social-post=`data/social_post_state.json`(日付+素材キーでFB/IG別に二重投稿防止・実装済みを点検で確認) |
| 5 | リトライ上限・種類 | ✅ | push=3回+abort、IG投稿=3回、healthcheckがERROR時Issue+LINE |
| 6 | 権限最小 | ✅ | GITHUB_TOKENは必要権限のみ宣言。Secretsはワークフロー内のみ |
| 7 | ログ・監視 | ✅ | healthcheck(毎朝10時)+Actionsログ+失敗時Issue自動起票 |
| 8 | 文章ルールの強制化 | ✅ | 並走禁止・検証ゲートはコード強制(今回のconcurrency完備で完了) |

## 残課題(次回スプリント候補)
- social-postの状態ファイル(`data/social_post_state.json`)はrunner内のみで有効。
  run自体の再実行(re-run)をまたぐ二重投稿防止が必要になったら、状態のコミット化を検討
