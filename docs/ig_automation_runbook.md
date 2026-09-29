# IG投稿自動化 運用ガイド(Week 5+)

対象: 沖縄企業のミカタ(株式会社GLOW)の Instagram 投稿案の週次自動生成と、人の承認ゲート。
※ もらいわすれ堂(株式会社フクギイロ)の投稿依頼は別運用(`docs/Instagram投稿依頼_運用.md` の前半)。混同しない。

原則: **自動化するのは「投稿案づくり」まで。投稿の公開は人が承認したものだけ**(絶対ルール1・5)。
週次の流れは 日曜(自動生成)→ 月曜(ヒロメさん)→ 水曜(必要時のみ再確認)→ 金曜(小柳さん最終承認)。

## 1. 全体像

| 曜日・時刻(JST) | 誰が | 何をする |
|---|---|---|
| 日 18:00 | GitHub Actions(自動) | 照合 → 生成 → push → Slack通知 |
| 月 10:00 | ヒロメさん | 文面・事実の確認(承認ゲート1) |
| 水 10:00 | ヒロメさん(修正があった週のみ) | 修正版の再確認。修正なしならスキップ |
| 金 10:00 | 小柳さん | 最終承認(承認ゲート2)→ 投稿スケジュール設定 |

## 2. 日曜 18:00 自動生成

ワークフロー: `.github/workflows/ig-posts-mikata.yml`(cron `0 9 * * 0` = 日曜 09:00 UTC。`workflow_dispatch` で手動実行も可)。

順序(この順序は意図的。入れ替えない):

1. `python scripts/verify_mikata_seido.py --only-ig` — ig_priority を持つ制度(約31件)を **Claude + Gemini で原文照合**。どちらかが矛盾を検知したら NG(要確認)。Gemini キー未設定なら Claude 単独。Claude キー未設定なら exit 2 で停止(commit も通知もされない)。
2. `python scripts/generate_ig_posts_mikata.py` — 5投稿案を生成(API呼び出しなし・決定的)。**照合が NG の制度は候補から外れる**ため、照合を先に走らせる。
3. commit & push — `data/subsidies.json`、`data/kpi/verify_mikata_audit.jsonl`、`data/ig_posts_mikata_draft.json`(`.gitignore` 対象のため `git add -f`)。コミット名は `auto: IG投稿案生成・検証 YYYY-Www`。
4. Slack通知(`SLACK_WEBHOOK_IG_APPROVALS`)— 未設定なら通知はスキップされる(ジョブは失敗にならない)。

生成ルール(機械が守っていること):
- 残り **30日未満の制度は載せない**(SNSは残り30日以上のみ)。
- 直近 **5週間に投稿した制度は載せない**(`data/ig_posts_history.json` で判定。履歴ファイルが壊れていれば生成は止まる)。
- 金額・補助率・日付を本文に断定しない。数値は `max_amount` / `ig_before_amount` / `ig_after_amount` 由来のみ。補助率は常に「要確認」。
- リンクは `/go/ig/` 経由(lin.ee 直貼りをしない)。承継・M&A系のタグは出さない(`shipping_gate.py`)。
- `publish_blocked: true` の案(締切が「要確認」のテンプレ2など)は、**締切を原文で確認できるまで投稿しない**。

出力を見る場所: `data/ig_posts_mikata_draft.json`(各案の `caption`、`source_url`、`verification_needed`、`publish_blocked`、画像プレースホルダ)。

## 3. 月曜 10:00 — ヒロメさん確認(承認ゲート1)

1. Slack通知のリンクから `ig_posts_mikata_draft.json` を開く(通知が無い週は、Actions の実行結果と `git log` で当週のコミットを探す)。
2. 各案を確認する。
   - `publish_blocked` の案は投稿対象から外す(締切確認待ちとして次週へ)。
   - `verification_needed` の項目は **`source_url` の原文で自分の目で照合**する(`hojo-accuracy-check`)。AI同士の一致は十分条件ではない。
   - 上限額が不自然に大きい案(総予算を1社上限と取り違えている疑い)は、原文で「1者あたりの上限」を確認する。
   - 文面は `humanizer` の観点で確認。【1行フック】/【本文】/【ハッシュタグ】などの見出しラベルは投稿前に外す。
   - 締切の言い回しは「締切の約1か月前から」で統一(`hojo-deadline-alert`)。「7日前アラート」は誤り。
3. 修正が必要なら GitHub にコメント(または該当案を差し戻し)。
4. 問題なければ Slack に **`Monday check: OK`** と返信。

## 4. 水曜 10:00 — 再確認(修正があった週のみ)

- 月曜に修正・差し戻しがあった場合のみ、修正版を月曜と同じ観点で再確認する。
- 修正がなければ何もしない(スキップ)。スキップした事実はSlackに一言残すとよい。

## 5. 金曜 10:00 — 小柳さん最終承認

1. 月曜(と水曜)の確認済み案を確認し、Slack で OK を返す。
2. OK が出た案だけ投稿スケジュールを設定する。承認前・`publish_blocked` の案は設定しない。
3. 投稿した制度は `data/ig_posts_history.json` に記録する(5週間重複除外の元データ。生成スクリプトは履歴を書かない。記録が漏れると同じ制度が再登場する)。

## 6. インシデント対応

| 症状 | 対応 |
|---|---|
| Claude と Gemini の照合が割れた(`conflict`、`needs_manual_review`) | 該当案は投稿しない。`details.claude_extracted` / `gemini_extracted` を見比べ、**原文URLで人が確認**してから可否を決める。`data/kpi/verify_mikata_audit.jsonl` に記録が残る |
| 原文に到達できない(取得失敗) | 「取得できなかった」は「内容が違う」の証拠ではない。別経路(ブラウザ)で原文を確認する。403 は遮断、404 は消滅の可能性で意味が逆 |
| 期限切れ・残り30日未満の制度 | 自動で候補から外れる(`ig_exclude: true` 運用)。手動で載せない |
| 新しい制度を加えたい | 定期データ更新後に `ig_priority` / `ig_template` を付与する。付与しない制度は生成対象外 |
| 週次ワークフローが失敗(赤) | Actions のログを確認。Claude キー欠落(`ANTHROPIC_API_KEY`)は exit 2 で無配信になる。復旧後 `workflow_dispatch` で再実行 |
| 日曜に案が0件・少ない | `ig_*` が `update.yml` の再収集で消えていないか確認。履歴の5週間除外で枯渇していないかも確認 |
| Slack通知が来ない | `SLACK_WEBHOOK_IG_APPROVALS` 未設定の可能性(未設定はスキップ動作)。Actions の実行結果を直接見る |
| 誤った内容を投稿してしまった | 即時に該当投稿を非表示/削除 → 小柳さんに報告 → 原因を再発防止メモ(CLAUDE.md)へ1行追記。ニドナシ機構(nokosu/fukabori/mihari)に連絡 |
| 同じ制度が重複して出た | `ig_posts_history.json` の記録漏れを確認して追記 |

## 7. 既知の未解決事項(本番前に小柳さんの判断が要る)

Task 13〜16 の報告で挙がった未解決点。解消するまでは「日曜の自動実行を信頼して放置」しない。

1. **`update.yml`(1日4回)が `data/subsidies.json` を作り直す**ため、`verified` と `ig_*` が消える。日曜 21:00 の収集で照合結果が消える、`ig_*` が消えると生成が0件になる、という恐れがある。main 統合前に、収集側で既存フィールドを引き継ぐ対応が必要。
2. **`schedule` は main にあるファイルでしか発火しない。** 統合までは `workflow_dispatch` のみ。
3. **下書きJSONが PUBLIC リポジトリにコミットされる**(承認前の文面が月曜前に公開状態になる)。公開範囲の変更にあたるため、非公開化または別置きを検討。
4. **`scripts/shipping_gate.py` の `TARGET_GROUPS` に下書きJSONが未登録**(CLAUDE.md の再発防止メモ)。JSON対応を含め要対応。
5. **議事が未作成**。外部送信(Slack)と main への自動 push は議事必須の類型(三名体制 ルール8②)。`docs/議事_YYYYMMDD_IG投稿自動化.md` を、ウタガイの反対理由つきで作成する。
6. **上限額の異常値**(例: 295億円は総予算の疑い)。優先順位(ig_priority)の並びにも影響するため原文で確認。
7. **Secrets の存在が未確認**: `ANTHROPIC_API_KEY`、`GEMINI_API_KEY`、`SLACK_WEBHOOK_IG_APPROVALS`。
8. テスト投稿2の `#事業承継` は `shipping_gate` の禁止対象。実運用の生成器はこのタグを出さない。

## 8. 関連ファイル

- ワークフロー: `.github/workflows/ig-posts-mikata.yml`
- 生成: `scripts/generate_ig_posts_mikata.py` / 照合: `scripts/verify_mikata_seido.py`
- 出荷ゲート: `scripts/shipping_gate.py`
- データ: `data/subsidies.json`、`data/ig_posts_mikata_draft.json`、`data/ig_posts_history.json`、`data/kpi/verify_mikata_audit.jsonl`
- テスト投稿と承認記録: `docs/ig_posts_test/`(`approval_log.md` ほか)
- 実装計画: `docs/superpowers/plans/2026-09-28-mikata-ig-automation.md`
- 手動確認の観点: スキル `hojo-accuracy-check` / `hojo-deadline-alert` / `humanizer`
- 締切3層ルール・絶対ルール: `CLAUDE.md`
