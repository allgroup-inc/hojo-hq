# カスタマイズガイド

## 1. 抽出する項目を変える(最重要)

`config/schema.json` がそのまま「Claudeに抽出させる項目の定義」です。
`properties` に項目を足し、`required` にも同じ名前を追加します。

例: 求人情報サイトにする場合

```json
{
  "type": "object",
  "properties": {
    "title":    { "type": "string", "description": "求人タイトル" },
    "summary":  { "type": "string", "description": "3文以内の要約" },
    "category": { "type": "string", "description": "職種カテゴリ" },
    "date":     { "type": "string", "description": "掲載日 YYYY-MM-DD。不明なら '要確認'" },
    "salary":   { "type": "string", "description": "給与。不明なら '要確認'" },
    "location": { "type": "string", "description": "勤務地。不明なら '該当なし'" }
  },
  "required": ["title", "summary", "category", "date", "salary", "location"],
  "additionalProperties": false
}
```

ポイント:
- `description` がそのままClaudeへの指示になります。具体的に書くほど精度が上がります
- 「不明なら '要確認'」のルールは残すことを強く推奨します(誤情報の公開防止)
- 項目名を変えたら `scripts/build_site.py` の CARD テンプレートの表示も合わせて
  変更してください

## 2. サイトの見た目を変える

`scripts/build_site.py` の冒頭にある定数を編集します。

- `SITE_TITLE` / `SITE_DESCRIPTION`: サイト名と説明
- `PAGE` 内の `<style>`: 色は `--accent` を変えるだけで全体の印象が変わります
- `CARD`: 1件分の表示テンプレート

## 3. 使用モデルを変える(費用調整)

既定は高精度モデル(claude-opus-5)です。収集量が多く費用を抑えたい場合、
`.github/workflows/pipeline.yml` の該当行のコメントを外します:

```yaml
env:
  ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
  ANTHROPIC_MODEL: claude-haiku-4-5   # 低コストモデル
```

目安(1件あたり数千文字の原文の場合):
- claude-opus-5: 1件 約2〜4円 — 日付・金額の抽出精度が最も高い
- claude-haiku-4-5: 1件 約0.5〜1円 — 単純な整形なら十分

## 4. 実行頻度を変える

`.github/workflows/pipeline.yml` の `cron` を編集します。UTC表記です。

```yaml
schedule:
  - cron: "0 21 * * *"  # JST 06:00(UTC 21:00)
  - cron: "0 3 * * 1"   # 毎週月曜 JST 12:00 だけにする例
```

## 5. 1回あたりの処理件数を変える

`config/sources.yml` の `max_items_per_run` です。初期値20。
API費用の暴走防止のための上限なので、情報源を増やしたら適宜引き上げてください。

## 6. 複数サイトを運営する

このテンプレートをリポジトリごとコピーすれば、何サイトでも並行運用できます
(購入者ご本人の利用に限ります。詳細は LICENSE.md)。
