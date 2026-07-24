# .claude/tools — 広告/計測データ連携 セットアップ手順

マーケスキル(ads / ad-creative / cro / analytics 等)が「実績データを引く」ときに使う、
依存ゼロのNode CLI群。あなたのスタックに絞って収録: Meta / Google広告 / GA4 / TikTok / Google Search Console。

> **状態: 配管は完成・トークン未設定。** 下記トークンを発行して環境変数に入れれば即稼働。
> トークン発行は各管理画面での作業(Claudeは代行不可)。安全のため**トークンはリポジトリにコミットしない**。

## 動作確認(トークン不要)
```bash
node .claude/tools/clis/meta-ads.js campaigns list --dry-run   # 実APIを叩かず送信内容だけ表示
```

## 必要な環境変数(実名)
| プラットフォーム | 環境変数 | 発行手順(要点) |
|---|---|---|
| **Meta広告** | `META_ACCESS_TOKEN`, `META_AD_ACCOUNT_ID`(act_込み) | Meta Business設定 → ユーザー → **システムユーザー**追加 → 広告アカウントへ割当 → 「トークン生成」(権限: ads_read, ads_management) → 長期トークン発行。AD_ACCOUNT_IDは広告マネージャのURL `act_XXXX`。 |
| **GA4** | `GA4_ACCESS_TOKEN`(+ プロパティIDは引数) | GCPでサービスアカウント作成 → GA4管理→アカウントのアクセス管理で閲覧権限付与 → OAuth/SAでアクセストークン取得(詳細 `integrations/ga4.md`)。プロパティIDはGA4管理→プロパティ設定。 |
| **Google広告** | `GOOGLE_ADS_TOKEN`, `GOOGLE_ADS_DEVELOPER_TOKEN`, `GOOGLE_ADS_CUSTOMER_ID` | Google Ads API Center で**developer token**申請(承認要) → OAuthでアクセストークン。CustomerIDは10桁(ハイフン無し)。 |
| **TikTok広告** | `TIKTOK_ACCESS_TOKEN`, `TIKTOK_ADVERTISER_ID` | TikTok for Business → Developers → アプリ作成 → OAuthでアクセストークン。 |
| **Search Console** | `GSC_ACCESS_TOKEN` | GCPサービスアカウント → Search Consoleでそのアカウントに権限付与 → アクセストークン取得。 |

各プラットフォームの操作詳細は `integrations/<name>.md`、全体一覧は `REGISTRY.md`。

## トークンの入れ方(2通り)
1. **対話セッションで使う**: `.env.example` を `.env` にコピーして値を記入し、`set -a; source .claude/tools/.env; set +a` で読み込む。**`.env` はコミットしない**(下記gitignore)。
2. **GitHub Actionsで定期実行**: リポジトリ Settings → Secrets and variables → Actions に**同名で登録**。既存の hikari-report/daily-cpa.yml はこの方式(META_ACCESS_TOKEN等)を想定済み。

## おすすめ着手順
1. **Meta広告 + GA4**(主戦場・最優先) → 2. TikTok(kakei) → 3. Google広告 → 4. Search Console。
まずMetaを入れれば `ads`/`ad-creative` が実績CPA/CTRを見て最適化提案できる。
