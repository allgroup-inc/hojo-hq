# mindshare-arbitrage「発見(Discovery)」自動化 設計書

作成: 2026-08-17 / 小柳さんとの壁打ちにより策定

## 背景

小柳さんから「AIのマナスとClaude CodeとInstagramを掛け合わせて完全自動化投稿できるのでは」
という相談があった。壁打ちの結果、以下が判明した:

- 既存のSNS自動投稿(`scripts/post_social.py` / `.github/workflows/social-post.yml`)には、
  小柳さん自身が2026-07-30に指示して追加した**投稿前承認ゲート**があり、これは維持したい
  (「完全自動化」の対象は投稿の実行ではなく、その手前のネタ探し・素材づくり)
- `mindshare-arbitrage`スキルに「① 発見(Discovery)」の設計は既に書かれているが、
  実装(スクリプト・ワークフロー)はまだ無い
- マナス(外部AIエージェント)を追加する前に、既存の`last30days`(トレンドリサーチ)・
  `competitor-profiling`等の手持ちスキルで足りるか試すのが合理的、という結論になった

本設計書は、`mindshare-arbitrage`の「①発見」段階を実装するもの。

## 1. スコープ

**作るもの:**
- `scripts/discover_trends.py`: Reddit(公開JSON API)・Hacker News(公開API)から
  候補記事/投稿を収集し、Claude APIでスコア化(新しさ×エンゲージメント)・重複除外・
  要約する
- `data/discovery_candidates.json`: 収集結果の履歴データ(state外部保存の原則)
- `.github/workflows/discover-trends.yml`: 毎朝6:00 JSTに実行、結果をGitHub Issueに
  チェックボックス形式で起票(検証部/健康チェックの既存ワークフローと同じパターン)
- (任意)LINE通知: Issue起票時に「候補一覧ができました」と軽く知らせる
  (`./.github/actions/line-notify`の既存アクションを流用。Secrets未設定時はスキップ)

**作らないもの(スコープ外):**
- マナス(外部AIエージェント)の導入。まず本実装の効果を見てから再検討する
- X(Twitter)・TikTok・YouTubeからの収集(公式APIが有料/複雑なため見送り。
  YouTubeは無料枠のAPIキーがあれば将来追加可能)
- 承認された候補から実際に投稿文面・画像を生成する工程(既存の`generate_carousel.py`等との
  接続方法は、実装計画で決める。今回はあくまで「①発見」まで)
- 投稿前承認ゲートの変更(既存のまま維持する)
- ⑥分析・学習(投稿の反応データを次回のスコアリングに反映する仕組み)は将来の拡張とし、
  今回は含めない

## 2. 全体の流れ

```
毎朝6:00 JST(cron)
  → scripts/discover_trends.py 実行
    1. Reddit / Hacker News から候補記事・投稿を取得
    2. Claude API(claude-haiku-4-5、既存verify_sources.pyと同モデル)で
       スコア化(新しさ×エンゲージメント)・重複除外・日本語要約
    3. data/discovery_candidates.json に追記保存(同日再実行は上書きでべき等)
  → GitHub Issueを自動起票(ラベル: discovery)
    候補ごとにチェックボックス1行(タイトル・出典URL・スコア・要約1〜2文)
  → (任意)LINE通知「本日の候補一覧ができました」
  → 小柳さんがIssue上でチェック(残す)/未チェック(見送り)を判断
  → チェックされた候補は、次回の生成フロー(別途実装)が拾う
```

## 3. データ収集の詳細

- **Reddit**: 対象subreddit群(例: r/smallbusiness, r/marketing等。日本語圏向けの
  「翻訳」を前提とするmindshare-arbitrageの考え方に沿う)の`.json`エンドポイントを
  User-Agent指定で取得(認証不要)
- **Hacker News**: 公式Firebase API(`https://hacker-news.firebaseio.com/v0/`)の
  topstories/newstoriesから取得(認証不要)
- 取得したタイトル・本文抜粋・スコア(upvote数等)・URLをClaude APIに渡し、
  「沖縄の中小企業経営者向けSNS発信のネタとして使えるか」という観点でスコアリング・
  日本語要約させる(プロンプトは`hojo-triangle-review`等の既存プロンプト設計を参考にする)
- 重複除外: 同じURL・類似タイトルは`data/discovery_candidates.json`の既存履歴と
  突き合わせて除外する

## 4. Issue起票の形式(既存healthcheck.ymlパターンを踏襲)

```markdown
## 本日の候補(2026-08-17)

- [ ] **候補タイトル1**(スコア: 8.5)— 出典: <URL>
  要約: 1〜2文の日本語要約
- [ ] **候補タイトル2**(スコア: 7.2)— 出典: <URL>
  要約: 1〜2文の日本語要約
...
```

`gh issue create`で新規起票(既存Issueへの追記ではなく、日ごとに新規Issueとする。
候補は日替わりで意味が変わるため、healthcheckのような「未解決なら追記」方式は適さない)。

## 5. リスク・注意点

- **Claude APIコスト**: 毎朝の実行でAPI呼び出しが発生する。候補数を絞る(例: 各ソース
  上位10件まで)ことでコストを抑える
- **収集元サイトの規約**: RedditもHacker Newsも公開APIの利用規約の範囲内で使う
  (絶対ルール2と同じ考え方。過度な高頻度アクセスをしない)
- **候補の質**: 沖縄の中小企業経営者向けという文脈に合わない候補が混ざる可能性がある。
  スコアリングプロンプトの調整は運用しながら行う想定(見直し期限を設ける)
- **見直し期限**: 導入後1ヶ月(2026-09-17)で、候補の採用率(チェックされた割合)を見て、
  収集元の追加やスコアリング調整、あるいはマナス等の追加ツール検討を判断する
