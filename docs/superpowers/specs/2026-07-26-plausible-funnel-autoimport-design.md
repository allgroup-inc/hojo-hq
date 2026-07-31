# 設計書: Plausible ファネル自動取り込み(離脱段の自動集計)

作成日: 2026-07-26 / 起案: たかしくん指示(小柳さん決裁前提) / ステータス: 設計承認済み(実装計画へ)
関連: scripts/weekly_report_fukugiiro.py(§2ファネル)/ docs/フクギイロ_計測レポート設計.md(第2段階)/ site/fukugiiro/assets/fg-analytics.js(イベント発火)

---

## 0. 目的

週次レポートのファネル(§2)は現在「Plausibleダッシュボードから人が数値を転記(5分)」の手動運用。
これを **GitHub Actions が Plausible Stats API から自動取得** し、離脱段(どのステップで何%落ちているか)を自動集計・可視化する。
手動転記を廃し、PDCA の C(計測)を自動化する。

**外部依存(確認済み)**: Plausible の Stats API キーを用意できる(有料/セルフホスト)。キーは GitHub Secret `PLAUSIBLE_API_KEY` に登録(登録操作は人間側)。

---

## 1. アーキテクチャ

```
GitHub Actions(週次cron: fukugiiro-weekly-report.yml に統合)
  └─ scripts/fetch_plausible_funnel.py   ← env PLAUSIBLE_API_KEY(Secret)
       Plausible Stats API(breakdown: property=event:name)を1回呼ぶ
       → data/fukugiiro/funnel.json を生成・commit
  └─ scripts/weekly_report_fukugiiro.py
       funnel.json を読み、§2ファネルを自動で埋める + 最大離脱段を pick_bottleneck に反映
```

既存の Secret 運用(`ANTHROPIC_API_KEY`・`LINE_CHANNEL_ACCESS_TOKEN`)と同型。静的サイトは無改変(APIキーは Actions 内のみ)。

---

## 2. コンポーネント

### 2.1 `scripts/fetch_plausible_funnel.py`(新規)
- 環境変数 `PLAUSIBLE_API_KEY` を読む。**未設定なら何も書かず exit 0**(info ログのみ)。既存挙動を壊さない。
- 設定(定数):
  - `SITE_ID = "allgroup-inc.github.io"`(analytics-config.js と同一)
  - `API_BASE = "https://plausible.io"`(セルフホスト時は環境変数 `PLAUSIBLE_API_BASE` で上書き可)
  - `PERIOD = "7d"`(環境変数 `PLAUSIBLE_PERIOD` で上書き可)
  - `FUNNEL`(順序つきの線形ファネル):
    1. `shindan_start`(診断開始)
    2. `shindan_step_q2`(Q2到達)
    3. `shindan_step_q3`(Q3到達)
    4. `shindan_step_q4`(Q4到達)
    5. `shindan_step_q5`(Q5到達)
    6. `shindan_complete`(診断完了・1件以上)
    7. `line_add_click`(LINE誘導クリック)
  - `ENGAGEMENT`(線形ではない補助指標): `kit_click`, `seido_done_mark`, `jukyu_report_click`, `shindan_zero`
- API 呼び出し: `GET {API_BASE}/api/v1/stats/breakdown?site_id={SITE_ID}&period={PERIOD}&property=event:name&metrics=events&limit=100`、ヘッダ `Authorization: Bearer {key}`。
  レスポンス `{"results":[{"name":"shindan_start","events":N}, …]}` を `{event_name: count}` に畳む。
  - HTTP エラー/タイムアウト時: 標準エラーに理由を出して **exit 1**(ワークフローで検知)。ただし本番運用ではワークフロー側で `continue-on-error` にし、失敗しても週次レポ生成は続行(フォールバック表示)。
- 集計:
  - 各 `FUNNEL` 段の `count`、`cvr_from_prev`(前段比、先頭は null)、`drop_rate`(= 1 − cvr_from_prev)。
  - `key_rates`:
    - `finish_rate` = (shindan_complete + shindan_zero) / shindan_start(診断を終えた割合)
    - `line_cvr` = line_add_click / shindan_complete(完了→LINE誘導クリック率。KPI 30% の観測系)
    - `zero_rate` = shindan_zero / (shindan_complete + shindan_zero)(完了のうち0件だった割合)
    - いずれも分母0なら null(ゼロ除算しない)
  - `worst_drop`: `FUNNEL` の隣接段のうち `drop_rate` 最大の段(= 最も落ちている離脱段)。
- 出力: `data/fukugiiro/funnel.json`(§2.2)。

### 2.2 `data/fukugiiro/funnel.json`(新規・生成物)
```json
{
  "schema_version": 1,
  "updated_at": "2026-07-26",
  "period": "7d",
  "source": "plausible-stats-api",
  "stages": [
    {"key": "shindan_start", "label": "診断開始", "count": 0, "cvr_from_prev": null, "drop_rate": null}
  ],
  "engagement": {"kit_click": 0, "seido_done_mark": 0, "jukyu_report_click": 0, "shindan_zero": 0},
  "key_rates": {"finish_rate": null, "line_cvr": null, "zero_rate": null},
  "worst_drop": null,
  "note": "PLAUSIBLE_API_KEY 未設定時は生成されず、週次レポは手動確認先にフォールバック。"
}
```
初期はリポジトリにコミットしない(キー設定後に Actions が初生成)か、全ゼロのプレースホルダを置く。→ **プレースホルダは置かない**(未生成=フォールバックが明確なため)。

### 2.3 `.github/workflows/fukugiiro-weekly-report.yml`(修正)
- 「週次レポート生成」ステップの**前**に取得ステップを追加:
  ```yaml
  - name: Plausibleファネル取得(キーが有れば)
    continue-on-error: true
    env:
      PLAUSIBLE_API_KEY: ${{ secrets.PLAUSIBLE_API_KEY }}
    run: python scripts/fetch_plausible_funnel.py
  ```
- Commit ステップの `git add` 対象に `data/fukugiiro/funnel.json` を追加。
- `continue-on-error: true` により、キー未設定・API障害でも週次レポ生成は必ず続行。

### 2.4 `scripts/weekly_report_fukugiiro.py`(修正)
- `load_funnel()` を追加: `data/fukugiiro/funnel.json` を読む。無ければ `None`。
- §2 の描画を分岐:
  - funnel あり: 各段の件数・転換率・離脱率の表を自動生成。`worst_drop` を強調表示(例:「最大離脱: Q3→Q4 で −42%」)。`line_cvr` を KPI30% と対比。
  - funnel なし(None): **現行の「確認先(手動記入)」表示のまま**(後方互換)。
- `pick_bottleneck()`: funnel があれば `worst_drop`/`line_cvr` を根拠にボトルネックと次アクションを決定(データ駆動化)。無ければ現行ヒューリスティック。

---

## 3. テスト・検証

- `fetch_plausible_funnel.py --self-test`: 固定の breakdown レスポンス fixture(`tests/golden_funnel.json`)を使い、①stages の count/cvr/drop ②key_rates ③worst_drop が期待値と一致することを確認(ネットワーク不要)。方程式4準拠。
- ゼロ除算・欠損イベント(あるイベントが0件で結果に出ない)を fixture に含める(count=0 として扱う)。
- `weekly_report_fukugiiro.py`: funnel.json あり/なし両方で例外なく生成できること(既存の実行確認に funnel あり系を追加)。
- CI: 新スクリプトの `--self-test` を **`fukugiiro-ci.yml`** に載せる(jukyu の先例に倣う)。`scripts/fetch_plausible_funnel.py` と `tests/golden_funnel.json` を push/pull_request の paths トリガに追加し、検証ステップで `python scripts/fetch_plausible_funnel.py --self-test` を実行。

---

## 4. 正確性・守り(絶対遵守)

- 取得するのは**集計イベント件数のみ**。個人識別子・回答内容は取得しない(Plausible は元々 Cookie なし)。守り部の計測方針(第2段階)の範囲内。
- API キーはリポジトリに置かない。GitHub Secret のみ。ログにキーを出さない。
- 数値は「観測値」として提示し、断定的な因果表現はしない(例:「Q3で落ちている**傾向**」)。

---

## 5. 小柳さん決裁事項

1. Plausible Stats API キーの発行と GitHub Secret `PLAUSIBLE_API_KEY` への登録(人間側の作業)。
2. 有料プラン費用(Stats API 利用可能なプラン)の承認。セルフホストなら不要。

---

## 6. スコープ外(YAGNI)

- 別建ての日次ジョブ/しきい値アラート通知(まずは週次レポの worst_drop 表示で足りる。将来拡張)。
- 流入元別(go channel / referrer)分析、時間帯別分析。
- 受給ジャーニー(ユーザーID紐付け)= LIFF+バックエンド Phase1 の別プロジェクト。

---

## 7. デリバリー

- 変更: `scripts/fetch_plausible_funnel.py`(新規)/ `scripts/weekly_report_fukugiiro.py`(修正)/ `.github/workflows/fukugiiro-weekly-report.yml`(修正)/ `tests/golden_funnel.json`(新規)。
- ブランチ: `claude/okinawa-disposable-income-plan-axxs6v`(直近の jukyu 統合修正の上に積む)。
- キー登録前でもマージ可能(未設定時フォールバックで無害)。キー登録後、初回 Actions 実行で funnel.json が生成され自動反映される。
