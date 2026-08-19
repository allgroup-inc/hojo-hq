# 保険引き受け目安検索 — 月次データ品質チェック実行プロンプト

**実行頻度:** 毎月1日 09:00 JST  
**所要時間:** 2～3時間  
**実行者:** 検証部（三名体制：スイシン・ウタガイ・ベッカイ）

---

## 📋 実行プロンプト

コピペで Claude Code に送信してください（定期 Routine として登録済みの場合は自動実行）。

```
あなたは保険引き受け目安検索の検証部責任者です。
以下の月次データ品質チェックを実行してください。

【状況】
- ツール: 保険引き受け目安検索（なないろ・FWD・チューリッヒ生命 3社）
- データ: docs/insurance/underwriting_full.json
- スキーマ: v2（confidence_level, condition_text, data_completeness等を保有）
- 目標: confidence_level「低」→「中」への段階的昇格 + data_completeness 精密化

【STEP 1: 現状把握】
1. docs/insurance/underwriting_full.json を読み込み
2. 以下を自動計算して報告してください:
   - 総疾患数
   - confidence_level 別の内訳（高 / 中 / 低）
   - 平均 data_completeness スコア
   - requires_confirmation=true の件数
   - 公式URL が確定済みの件数

   出力形式:
   ```
   📊 現状統計
   ├─ 総疾患数: XXX
   ├─ 信頼度別: 高 XX件 / 中 XX件 / 低 XX件
   ├─ 平均 completeness: 0.XX
   ├─ 公式確認推奨: XX件
   └─ 公式URL確定: XX件
   ```

【STEP 2: 低信頼度データの抽出】
confidence_level = "低" のデータをすべて抽出して、以下を記録してください:
- 病名
- 各保険会社での判定
- 現在の data_completeness スコア
- requires_confirmation フラグ
- 備考（情報不足の理由）

出力形式（表）:
| 病名 | なないろ | FWD | チューリッヒ | completeness | 理由 |
|---|---|---|---|---|---|

【STEP 3: 公開情報の調査（三名体制）】

以下について、医学文献・保険会社公式情報から調査してください。
各候補について、スイシン（推進）・ウタガイ（懐疑）・ベッカイ（別解）の 3 役で議論を記録してください。

**調査対象**: confidence_level="低" のデータから、以下の優先度で最大5件選定
  1. data_completeness が特に低い（< 0.4）
  2. requires_confirmation=true で公式確認が必須
  3. 稀少疾患だが、医学文献に情報あり

**調査項目**:
  - 医学的な特徴（発症率・予後・必要な治療）
  - 保険会社の公開情報（公式サイト・告知書・引き受け基準）
  - 業界レポート（生保ニュース・経営誌）
  - 他社事例（同じ疾患での判定基準）

**議論フォーマット**:

【疾患: XX】
🎯 スイシン（推進）の見解:
  「公開情報から見ると、confidence_level を『低』→『中』に昇格できる根拠がある」
  根拠: 
    - 医学文献 A の記載から「入院期間の中央値は 30 日」
    - 保険会社 X の公式基準で「慢性期は加入可」と明記
    - ⇒ データが不足しているのではなく、確実な基準が存在する

⚠️ ウタガイ（懐疑）の見解:
  「ちょっと待て。information completeness は本当に上げられるのか」
  懸念:
    - 保険会社 Y は『要問い合わせ』と曖昧なまま
    - 医学的には進行パターンが多様で、一概に判定できない
    - ⇒ 昇格するなら「requires_confirmation=true は維持」が条件

💡 ベッカイ（別解）の見解:
  「前提を疑おう。confidence_level の定義を再確認」
  提案:
    - 「confidence = データの完全性」ではなく「判定の確実性」と定義し直す
    - そうなら「公開情報が確実に存在＝高」「情報が分散＝中」「不明瞭＝低」
    - 当該疾患は「確実な基準が複数存在」なら「中」→「高」に昇格すべき

🎬 結論:
  決定: confidence_level「低」→「中」に昇格、data_completeness 0.35→0.55 に更新
  理由: 公開基準が存在し、判定が可能と確認できたため
  条件: requires_confirmation=true は維持（複雑性が残存するため）
  次アクション: 公式URL の収集を開始
  議事録: docs/insurance/reviews/2026-09-01-XX-review.md に記録
  署名: スイシン / ウタガイ / ベッカイ + 日時

【STEP 4: JSON 更新】

以下のファイルを作成してください:

**ファイル: /tmp/insurance-updates-2026-09-01.yaml**
```yaml
updates:
  - disease: "神経線維腫"
    insurer: "naneiro"
    confidence_level:
      from: "低"
      to: "中"
      reason: "医学文献 + 公式基準で判定可能と確認"
    data_completeness:
      from: 0.35
      to: 0.55
    condition_text: "医療・死亡特約のみ。その他は不可"
    requires_confirmation: true
    official_info_url: ""  # 準備中
    note: "稀少疾患。公式確認を推奨"
    reviewed_by: "検証部（スイシン・ウタガイ・ベッカイ）"
    review_date: "2026-09-01"
```

その後、以下を実行して JSON を更新してください:
```bash
git checkout -b fix/insurance-monthly-check-2026-09-01
python scripts/update-confidence-levels.py \
  --input docs/insurance/underwriting_full.json \
  --updates /tmp/insurance-updates-2026-09-01.yaml \
  --output docs/insurance/underwriting_full.json
git add docs/insurance/underwriting_full.json
git commit -m "chore(insurance): 2026-09月次データ品質チェック

confidence_level 昇格: X件
  - 神経線維腫（なないろ）: 低→中
  - XX（FWD）: 低→中
  - XX（チューリッヒ）: 低→中

data_completeness 更新: 平均 0.XX → 0.XX

三名体制レビュー実施
  スイシン(推進) / ウタガイ(懐疑) / ベッカイ(別解)
  
議事録: docs/insurance/reviews/2026-09-01-monthly-review.md"
git push origin fix/insurance-monthly-check-2026-09-01
```

【STEP 5: 月次レポート作成】

以下をファイル化して、検証部チャネルに共有してください:

**ファイル: docs/insurance/reviews/2026-09-01-monthly-review.md**
```markdown
# 2026年9月 月次データ品質チェック

実施日: 2026-09-01
実施者: 検証部（スイシン・ウタガイ・ベッカイ）

## 📊 現状統計

【STEP 1 の結果をコピペ】

## 🔄 改善内容

【STEP 2-3 の議論結果をコピペ】

## 📈 品質スコア推移

| 指標 | 先月 | 今月 | 変化 |
|---|---|---|---|
| 信頼度「高」比率 | 35% | 38% | +3% |
| 平均 completeness | 0.70 | 0.72 | +0.02 |
| 公式URL 確定 | 110件 | 120件 | +10件 |
| 総合スコア | 70/100 | 72/100 | +2点 |

## 🎯 目標との比較

目標（12ヶ月後): 信頼度「高」50% / completeness 0.85 / 総合スコア 85/100

現在の進捗:
  - 信頼度「高」: 38% → 目標比 -12%（月 2～3%ペースで改善中 ✓）
  - completeness: 0.72 → 目標比 -13%（月 +0.015ペースで改善中 ✓）

## 📝 次月の優先タスク

【STEP 2 で未処理の低信頼度データから、優先度の高い XX件を選定】

例:
  1. XX（稀少ながら医学文献が豊富）
  2. XX（保険会社X公式サイトで基準確定）
  3. XX（要問い合わせから確認済みに昇格可能性あり）
```

【STEP 6: Slack 報告】

検証部チャネル（#検証-保険）に以下を投稿:

```
📊 2026年9月 月次データ品質チェック 完了

✅ 信頼度「低」→「中」: X件昇格
  - 神経線維腫（なないろ）: 0.35 → 0.55
  - XX（FWD）: 0.30 → 0.50
  - XX（チューリッヒ）: 0.25 → 0.45

📈 品質スコア: 70 → 72/100 (+2点)
  - 信頼度「高」比率: 35% → 38%
  - 平均 completeness: 0.70 → 0.72
  - 公式URL 確定: 110 → 120件

📝 議事録: https://github.com/allgroup-inc/hojo-hq/blob/main/docs/insurance/reviews/2026-09-01-monthly-review.md

🎯 来月の優先: XX（医学文献豊富）、XX（公式確認予定）、XX（要確認昇格）

👥 実施者: スイシン / ウタガイ / ベッカイ（検証部）
```

---

## ✅ チェックリスト

- [ ] STEP 1: 現状統計を計算・報告
- [ ] STEP 2: 低信頼度データを抽出（表形式）
- [ ] STEP 3: 最大5件について三名体制で議論＆記録
- [ ] STEP 4: JSON を更新＆ commit＆push
- [ ] STEP 5: 月次レポートを作成
- [ ] STEP 6: Slack に報告

---

## 📌 重要な約束事項（必ず守る）

✅ **必ず三名体制で議論**
  - スイシン（推進）、ウタガイ（懐疑）、ベッカイ（別解）の 3 役必須
  - ウタガイの「反対理由」をテキスト化（議事録に残す）

✅ **confidence_level 昇格の基準は厳格に**
  - 「低」→「中」: 公開情報で基準が存在することを確認
  - 「中」→「高」: 複数の公式ソースで一貫性を確認
  - 昇格不可: requires_confirmation=true を維持

✅ **必ず git commit で履歴を残す**
  - 何が変わったのか、なぜ変わったのかを commit message に記録
  - 後から「なぜこのデータが中なのか」と質問されたときに回答可能にする

✅ **月次1日を絶対期限**
  - 遅れると利用者への説明が困難になる
  - Routine で自動実行されるため、手作業がある場合は前日までに完了

---

## 🔗 関連リンク

- スキーマ定義: `docs/insurance/underwriting-schema.md`
- 導線設計: `docs/insurance/保険引き受け目安検索_導線設計.md`
- 三名体制ルール: `docs/スペシャリスト名簿.md` + `docs/三名体制運営規程.md`
```

---

## 運用上のコツ

### 1. ウタガイ（懐疑）役が反対しやすい環境づくり
- 「できるだけ高い数字にしたい」圧力に抗う
- ウタガイの反対理由を記録することが品質維持の鍵
- ウタガイが反対しない → 議論が形骸化している信号

### 2. 議事録は「なぜ」を残す
- 結論だけでなく、「なぜ confidence_level を中に昇格したのか」
- 6ヶ月後、新しいメンバーが同じ疾患で判定するときの根拠になる

### 3. 公式URL の収集を平行実施
- 月次チェック時に「公式URL がまだ」であれば、即座に調査開始
- 6ヶ月で全疾患の 70% 以上を公式URL 付きにする目標
