# note マガジン完全自動化システム実装ガイド

**目標:** note マガジンの月収益を **¥300,000** に到達させる  
**手段:** 毎日朝7時に高エンゲージメント記事を自動生成・自動投稿  
**タイムライン:** 4週間で月30万円達成  

---

## システム概要

```
┌─────────────────────────────────────────────────────────┐
│ GitHub Actions (スケジュール実行)                          │
├─────────────────────────────────────────────────────────┤
│                                                           │
│  毎日 06:30 (JST) ────┐                                   │
│                       ├─→ 記事自動生成 (Claude API)       │
│  毎日 07:00 (JST) ────┤    ↓                              │
│                       ├─→ note 自動投稿 (Playwright)    │
│                       │    ↓                              │
│  毎週日曜 18:00 (JST) ┤    記事ファイル保存               │
│                       └─→ 週次分析・最適化提案 (Claude)  │
│                            ↓                              │
│                            レポート生成・コミット          │
│                                                           │
└─────────────────────────────────────────────────────────┘
```

---

## コンテンツ戦略（3層構造）

### **L1 集客記事（8割・毎日投稿）**

**目的:** ビュー数を稼ぐ（理想: 500ビュー/記事）  
**スタイル:** 「〜の前に知っておきたい」系  
**パターン:** 読者の「困り」「疑い」に応える逆張り視点  

**テーマ例:**
- 「助成金をもらう前に知っておきたい、税務申告のリスク」
- 「フリーランスが単価を決める前に知っておきたい、相場より重要な判断基準」
- 「起業家が最初にやるべき、資金確保より先にやること」
- 「補助金の採択率を上げる、企業の『本気度』の見せ方」
- 「個人事業主が防ぐべき、経理ルール・納税ミス5選」
- 「地方だから不利は本当か、沖縄起業家が知らない有利条件」

**成功例（スクリーンショット参照）:**
- 「0→1万フォロワーを目指す前に...」: 13ビュー・8スキ(61.5%エンゲージメント) ✅
- 「地方だから不利」: 16ビュー・4スキ(25%) ✅

---

### **L2 インサイト記事（15%・週2-3本）**

**目的:** 信頼構築・長期購読継続  
**スタイル:** 失敗事例・業界分析・データ共有  

**テーマ例:**
- 「note AI自動運営で売上0円だった1か月 — AIより必要だった『人間の判断基準』」
- 「補助金は『現れた』ニュースはあっても『消えた』記録はどこにもない」
- 「沖縄×本州の補助金制度差をデータで見えた構造」

---

### **L3 有料販売（5%・週1本）**

**目的:** 収益化・会員転換  
**スタイル:** B2B白書・会員限定レポート  

**テーマ例:**
- 「2026年度沖縄補助金マップ＆活用戦略ガイド（B2B白書）」
- 「沖縄中小企業の資金調達パターン辞典（会員限定）」

---

## セットアップ手順

### **ステップ1: GitHub Secrets に認証情報を設定**

リポジトリの Settings → Secrets and variables → Actions から以下を追加:

| キー | 値 | 取得方法 |
|------|-----|--------|
| `ANTHROPIC_API_KEY` | Claude API キー | https://console.anthropic.com |
| `NOTE_USER_EMAIL` | note ログインメール | あなたのnoteアカウント |
| `NOTE_USER_PASSWORD` | note パスワード | あなたのnoteアカウント |
| `NOTE_MAGAZINE_ID` | マガジンID | noteの管理画面URLから抽出 |
| `SLACK_WEBHOOK_URL` | Slack 通知用 (オプション) | https://api.slack.com |

### **ステップ2: 手動実行でテスト**

GitHub Actions のページで `note マガジン完全自動化` ワークフロー → Run workflow をクリック。

**ログから確認:**
```
✅ 記事を保存: posts/note_magazine/2026-10-03_vol1.md
✅ note への投稿に成功しました
✅ レポートを保存: docs/note_analytics/2026-10-03_weekly_analysis.md
```

### **ステップ3: スケジュール確認**

ワークフロー内の `on.schedule` cron を確認：

```yaml
- cron: '30 21 * * *'  # 毎日 06:30 JST に記事生成・投稿
- cron: '0 9 * * 0'    # 毎週日曜 18:00 JST に分析
```

**時刻変更例：** 朝8時に変更する場合
```yaml
- cron: '0 23 * * *'  # UTC 23:00 = JST 08:00
```

---

## スクリプト詳細

### **1. `scripts/generate_note_magazine_daily.py`**

毎日新しいテーマで記事を自動生成。

```bash
# ドライラン（出力のみ、ファイル保存なし）
python scripts/generate_note_magazine_daily.py --dry-run

# 実行（ファイルに保存）
python scripts/generate_note_magazine_daily.py

# 投稿まで実行（環境変数設定後）
ANTHROPIC_API_KEY=sk-... python scripts/generate_note_magazine_daily.py
```

**生成される内容:**
- 毎日のテーマが異なる（月30テーマをローテーション）
- 1000-1800字の完全な記事本文
- Markdown 形式で `posts/note_magazine/` に保存

### **2. `scripts/publish_note_article.py`**

Markdown ファイルを note マガジンに自動投稿。

```bash
# 手動投稿テスト（ブラウザ表示）
python scripts/publish_note_article.py posts/note_magazine/2026-10-03_vol1.md --show

# ヘッドレス投稿（本運用）
python scripts/publish_note_article.py posts/note_magazine/2026-10-03_vol1.md
```

**前提条件:**
```
pip install playwright
playwright install chromium
```

### **3. `scripts/analyze_note_performance.py`**

毎週のパフォーマンス分析・最適化提案を自動生成。

```bash
# レポート生成のみ
python scripts/analyze_note_performance.py

# Claude による分析を含める
ANTHROPIC_API_KEY=sk-... python scripts/analyze_note_performance.py --claude
```

**出力:**
- `docs/note_analytics/YYYY-MM-DD_weekly_analysis.md` に レポート保存
- 来週のテーマ提案を Claude が自動生成
- パフォーマンス指標（ビュー数・スキ率・エンゲージメント）をダッシュボード化

---

## パフォーマンス目標

### **現状（2026-10-03）**
- 週間ビュー数: **101**
- 週間スキ数: **19**
- 平均エンゲージメント率: **15.6%**
- 必要な改善倍率: **25倍**

### **Week 2 目標（2026-10-10）**
- ビュー数: **300-500** (毎日50-70ビュー)
- スキ数: **30-50** (エンゲージメント率 10-15%)
- 投稿頻度: 毎日朝7:00 + X 同時投稿

### **Week 4 目標（2026-10-24）**
- ビュー数: **1,500** (月2,500達成の60%)
- スキ数: **150-200** (エンゲージメント率 10-13%)
- 会員転換: 月商 ¥50,000 (会員50人×500円)

### **月末目標（2026-10-31）**
- ビュー数: **2,500**
- スキ数: **300+**
- 会員転換: 月商 ¥100,000
- L3 販売: 月商 ¥200,000
- **合計月収: ¥300,000** ✅

---

## トラブルシューティング

### **Q: 投稿が失敗する（note へのログインに失敗）**

**原因:** note のログイン画面が変更されたか、メールアドレス/パスワードが誤り

**対応:**
1. `NOTE_USER_EMAIL` と `NOTE_USER_PASSWORD` を再確認
2. note で２段階認証が有効になっていないか確認
3. Playwright のセレクタが変更されていないか確認
   ```bash
   python scripts/publish_note_article.py --show posts/note_magazine/*.md
   ```
   でブラウザ画面を確認し、要素を特定

### **Q: 記事が生成されない（Claude API エラー）**

**原因:** `ANTHROPIC_API_KEY` が無効か期限切れ

**対応:**
1. API キーを再生成（https://console.anthropic.com）
2. Secrets を更新
3. ワークフローを再実行

### **Q: 日次実行されない（スケジュール実行されない）**

**原因:** Actions が無効か、cron 式が誤り

**対応:**
1. リポジトリの Actions タブで workflow が有効か確認
2. cron 式を validate: https://crontab.guru
3. 手動実行で動作確認
   ```bash
   gh workflow run note-magazine-automation.yml
   ```

---

## 今後の拡張

- [ ] **X 自動投稿:** API で記事発行時に自動ツイート
- [ ] **会員管理:** note API で購読者数・売上を自動集計
- [ ] **A/B テスト:** 記事タイトル・時間帯を自動最適化
- [ ] **LINE 連携:** 新記事公開時に LINE で通知
- [ ] **SEO 最適化:** Google Analytics データに基づき記事改善

---

## 参考資料

- note API ドキュメント: https://note.com/info/n/...（非公開、要調査）
- Claude API: https://console.anthropic.com
- Playwright: https://playwright.dev
- GitHub Actions: https://docs.github.com/en/actions

---

**最終確認:**

- [x] 記事自動生成スクリプト実装
- [x] note 自動投稿スクリプト実装
- [x] 週次分析スクリプト実装
- [x] GitHub Actions ワークフロー実装
- [x] Secrets 設定方法を文書化
- [ ] **本番運用開始: 2026-10-04 朝6:30 〜**

