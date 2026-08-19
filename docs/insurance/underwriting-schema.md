# 保険引き受け目安検索 — データスキーマ v2

## 概要
保険会社3社（なないろ生命・FWD生命・チューリッヒ生命）の引き受け基準をJSON化した統合データベース。

## ファイル構成
```
docs/insurance/
├── underwriting_full.json       # 統合データ（すべての疾患・会社）
├── underwriting-schema.md       # このファイル（スキーマ定義）
└── underwriting-meta.json       # メタデータ（最終更新日時等）
```

## データ構造 v2（改善版）

### ルート
```json
{
  "version": "2.0",
  "last_updated": "2026-08-19T00:00:00Z",
  "naneiro": [],      // なないろ生命
  "fwd": [],          // FWD生命
  "zurich": []        // チューリッヒ生命
}
```

### 各保険会社の疾患エントリ（詳細版）
```json
{
  "disease": "神経線維腫",
  "page": 42,
  "judgement": "条件付き",
  "confidence_level": "中",
  "condition_text": "医療・死亡特約のみ可能。その他特約は要確認",
  "data_completeness": 0.6,
  "requires_confirmation": true,
  "official_info_url": "",
  "note": "稀少疾患のため、保険会社の最新基準を必ず確認してください"
}
```

### フィールド定義

| フィールド | 型 | 必須 | 説明 |
|---|---|---|---|
| `disease` | string | ◎ | 病名（日本語） |
| `page` | number | ◎ | PDF上のページ番号 |
| `judgement` | enum | ◎ | `可` \| `条件付き` \| `不可` \| `要確認` |
| `confidence_level` | enum | ◎ | `高` \| `中` \| `低` → UI で信頼度アイコン表示 |
| `condition_text` | string | ○ | 判定の理由・条件（例：「医療・死亡のみ可」） |
| `data_completeness` | number | ○ | 0.0～1.0（データの完成度・信頼度） |
| `requires_confirmation` | boolean | ○ | true = 公式確認が必須（稀少疾患等） |
| `official_info_url` | string | ○ | 保険会社の公式基準URL（準備中は空文字） |
| `note` | string | ○ | 利用者向け補足情報 |

### 例1: 高確信データ（よくある疾患）
```json
{
  "disease": "がん（悪性新生物）",
  "page": 5,
  "judgement": "可",
  "confidence_level": "高",
  "condition_text": "標準的な生命保険の対象疾患。加入可能",
  "data_completeness": 0.95,
  "requires_confirmation": false,
  "official_info_url": "",
  "note": ""
}
```

### 例2: 中程度（特約制限あり）
```json
{
  "disease": "神経線維腫",
  "page": 42,
  "judgement": "条件付き",
  "confidence_level": "中",
  "condition_text": "医療・死亡特約のみ。その他は不可",
  "data_completeness": 0.65,
  "requires_confirmation": true,
  "official_info_url": "",
  "note": "稀少疾患。公式基準を必ず確認してください"
}
```

### 例3: 低信頼度（データ不足）
```json
{
  "disease": "プリオン病（ヤコブ病）",
  "page": 89,
  "judgement": "要確認",
  "confidence_level": "低",
  "condition_text": "情報が限定的です。保険会社に直接問い合わせてください",
  "data_completeness": 0.3,
  "requires_confirmation": true,
  "official_info_url": "",
  "note": "超稀少疾患のため、各保険会社の基準が異なる可能性があります"
}
```

## UI表示ルール

### 信頼度レベルの視覚表現

| レベル | アイコン | 背景色 | CTA |
|---|---|---|---|
| `高` | ✅ | #e8f5e9 | 「詳しく見る」のみ |
| `中` | ⚠️ | #fff3e0 | 「詳しく見る」 + 「公式確認」ボタン |
| `低` | ❌ | #ffebee | 「公式確認」必須表示 |

### 判定ごとの表示

#### 「可」（緑）
```
✅ なないろ生命: 可
   標準的な生命保険の対象疾患。加入可能
   🔗 詳しく見る
```

#### 「条件付き」（黄）
```
⚠️ なないろ生命: 条件付き
   医療・死亡特約のみ。その他は不可
   
   ⚠️ 情報レベルが中程度です
   🔗 詳しく見る  |  📄 公式基準を確認
```

#### 「要確認」（赤）
```
❌ チューリッヒ生命: 要確認
   超稀少疾患のため、各保険会社の基準が異なる可能性があります
   
   ⚠️ 公式基準の確認が必須です
   🔗 公式サイトへ
```

---

## 段階的な改善フロー

### Phase 2-1（今週）
- JSON スキーマを v2 に更新
- UI: confidence_level に基づくアイコン・背景色表示
- UI: condition_text を結果に表示
- UI: 「要確認」フラグ時に警告表示

### Phase 2-2（翌週）
- なないろ・FWD・チューリッヒの公開情報から `data_completeness` を推定
- 稀少疾患リストを識別＆フラグ付与
- official_info_url を段階的に充実

### Phase 2-3（以降）
- ユーザーフィードバック機構（「この情報は正確ですか？」投票）
- 保険会社 API 連携の検討

---

## バージョン履歴

| Version | Date | Changes |
|---|---|---|
| 1.0 | 2026-08-13 | 初版：疾患名・判定・ページ番号のみ |
| 2.0 | 2026-08-19 | 信頼度・条件詳細・データ完成度を追加 |
