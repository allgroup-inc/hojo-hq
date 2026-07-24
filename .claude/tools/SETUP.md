# .claude/tools — 広告/計測データ連携(任意)

マーケスキル(ads / ad-creative / cro / analytics 等)が「実績データを引く」ときに使う、
依存ゼロのNode CLI群。あなたのスタックに絞って収録: Meta / Google広告 / GA4 / TikTok / Google Search Console。

## 使い方
各CLIは環境変数を読む。トークンを設定してから実行する。
```bash
node .claude/tools/clis/meta-ads.js insights get           # 例
node .claude/tools/clis/ga4.js --help
```
※ `--dry-run` を付ければ実際のAPIを叩かず、送るリクエスト内容だけ確認できる。

## 必要な環境変数(接続にはあなたのトークンが必要)
| プラットフォーム | 環境変数 | 取得元 |
|---|---|---|
| Meta広告 | `META_ACCESS_TOKEN` / `META_AD_ACCOUNT_ID`(act_込み) | Meta Business Suite → システムユーザートークン |
| Google広告 | `GOOGLE_ADS_*`(developer token / OAuth) | Google Ads API(developer token承認後) |
| GA4 | `GA4_PROPERTY_ID` ほか(guide参照) | GA4管理画面 |
| TikTok広告 | `TIKTOK_ACCESS_TOKEN` ほか | TikTok Business |
| Search Console | 認証情報(guide参照) | Google Search Console |

**現状これらは未設定**(report-hq / hikari-report の CLAUDE.md でも「未設定」)。
トークンを用意すれば、その時点でスキルが実データを使った最適化まで回せる。
GitHub Actions で回す場合は Settings → Secrets に同名で登録する。

詳細な各プラットフォームの操作は `integrations/<name>.md` を参照。ツール全体の一覧は `REGISTRY.md`。
