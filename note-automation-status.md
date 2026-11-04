# note マガジン自動化プロジェクト — 進捗レポート

**プロジェクト目標**：月30万円の持続的な収益を実現するため、note記事の自動生成・投稿・分析をフル自動化する

---

## 現状概要

### 完了した機能
1. **記事自動生成** ✅
   - Claude Opus 5.5 APIで、毎日朝6:30（JST）に新記事を自動生成
   - L1テーマ8種 × L2テーマ3種 × L3テーマ2種の組み合わせで多様な記事を産出
   - Markdown形式で `posts/note_magazine/YYYY-MM-DD_vol*.md` に保存
   - ワークフロー実行例：記事「2026-11-02_vol2.md」は正常に生成されている

2. **Git自動コミット** ✅
   - 記事生成後、自動的に`git add`・`git commit`・`git push`で履歴を保存
   - 例：commit 46f68f8 "chore: note magazine article generated 2026-11-01"

3. **GitHub Actions ワークフロー** ✅
   - 日次スケジュール: 毎日朝6:30 JST（UTC 21:30）
   - マニュアルトリガーにも対応
   - 複数ステップの順序実行が正常に動作

---

## 現在の課題と改善状況

### 課題1：note.com ログイン自動化
**問題の変遷**：
- **第1段階**：セレクタが見つからず、ログイン処理がスキップされていた
  - 原因：ページ読み込みが完全でない段階で要素を探索していた
  - ログ例：`[error] メールアドレス入力フィールドが見つかりません`

- **第2段階**（セレクタ改善後）：ログインには成功したが、投稿ページの操作で失敗
  - ワークフローラン41320938019：
    ```
    [ok] Markdown ファイルを読み込み ✅
    [ok] メールフィールド見つけました: input[name="login"] ✅
    [ok] メールアドレスを入力 ✅
    [ok] パスワードフィールド見つけました: input[type="password"] ✅
    [ok] パスワードを入力 ✅
    [ok] ログインボタン見つけました: button[type="submit"] ✅
    [ok] note へのログインに成功しました ✅
    [error] note 投稿失敗: Page.click: Timeout 30000ms exceeded.
            waiting for locator("text=新しい記事を作成") ❌
    ```

**根本原因**：
- ログイン後のダッシュボード遷移後、「新しい記事を作成」ボタンが見つからない
- 単一のテキスト指定`text=新しい記事を作成`では、DOM変化に対応できない
- ページのポップアップ・オーバーレイ・非同期読み込み未対応

### 改善実施内容（2026-11-01）

**ログイン部分の改善**（以前から実装済み）：
```python
# 複数のセレクタ戦略を試行
email_selectors = [
    'input[name="login"]',
    'input[name="email"]',
    'input[type="email"]',
    'input[name="account"]',
    'input[placeholder*="メール"]',
    'input[placeholder*="ログイン"]',
]

# 各セレクタについて
for selector in email_selectors:
    await page.wait_for_selector(selector, timeout=3000)  # タイムアウト付き待機
    email_field = await page.query_selector(selector)
    if email_field:
        break
```

**投稿部分の改善**（本日実装）：
- 「新しい記事を作成」ボタンの複数セレクタ対応
  ```python
  create_button_selectors = [
      'text=新しい記事を作成',
      'button:has-text("新しい記事を作成")',
      'a:has-text("新しい記事を作成")',
      '[class*="create"][class*="button"]',
      'button[class*="primary"]',
  ]
  ```

- ページ遷移待機の強化
  - `wait_until="networkidle"` 後に `await asyncio.sleep(2)` を追加
  - ボタンクリック前の待機で、初期化待機時間を増加

- タイトル・本文・公開ボタンのセレクタも複数戦略化
  ```python
  title_selectors = [
      'input[placeholder*="タイトル"]',
      'input[placeholder*="title"]',
      'input[placeholder*="記事タイトル"]',
      'input[type="text"]',
  ]
  ```

- エラー時の詳細ログ出力
  - ボタンが見つからない場合、全ボタン要素を列挙して表示

---

## 第1次テスト実行（ワークフローラン 41321237417）

**実行時刻**: 2026-11-01 15:30頃（手動トリガー）
**結果**: ❌ 失敗（ダッシュボード読み込み不十分）

**失敗の詳細**：
- ✅ 記事生成：成功
- ✅ ログイン：成功  
- ❌ **「新しい記事を作成」ボタン検出**：失敗
  - 原因：マガジン URL へのアクセス後、ページの JavaScript 初期化が完了していない
  - 症状：ページ内に3個のボタンがあるが、全てテキストが空状態
  - 推測：`wait_until="networkidle"` + `asyncio.sleep(2)` では不十分

**改善内容** (本日実装):
- ダッシュボード読み込み待機を最大10秒に延長
- ボタンのテキスト内容が実際に表示されるまで待つ仕様に変更
- エラー時に全ボタンの詳細情報（class、role、href）を出力

---

## 第2次テスト実行（ワークフローラン 実行中）

**ワークフローラン ID**: 確認待ち
**実行時刻**: 2026-11-01 15:40頃（手動トリガー）
**期待値**：
1. ✅ 記事生成（既に確認済み）
2. ✅ ログイン（既に確認済み）
3. ✅ **「新しい記事を作成」ボタン検出**（本次改善ポイント：JavaScript 初期化待機強化）
4. ✅ タイトル・本文の入力
5. ✅ 投稿ボタンクリック
6. ✅ Git にコミット・プッシュ

---

## 技術的背景

### note.com の DOM 構造の特徴
- **動的レンダリング**: ログイン後、複数のエレメントが非同期で追加される
- **SPA要素**: ページ遷移が JavaScript で制御される部分あり
- **セレクタの脆弱性**: クラス名・ID がバージョンごとに変わる可能性

### Playwright での対応戦略
- `wait_for_selector()`: タイムアウト付きで、要素が実際に DOM に現れるまで待つ
- 複数セレクタ試行: 一つが失敗しても、別のセレクタで対応
- `asyncio.sleep()`: JavaScript の初期化・レンダリング完了を待つ（粗いが効果的）
- 詳細ログ: 失敗時に全要素を列挙することで、次の改善方向を特定しやすく

---

## 今後の対応方針（仮説）

### 短期（今週）
- 本日のセレクタ改善テスト結果を確認
- 依然失敗する場合、note.com のブラウザ実行ログを見るか、DevTools 相当の情報を取得

### 中期（来週）
- 投稿完了の確認ロジックを強化（例：URL変化の監視、特定テキストの出現確認）
- API 化可能な部分を検討（非公開APIがあればそちらで自動化）

### 長期（月内）
- 週次分析機能の完成
- note 内での記事パフォーマンス（いいね数・読了率）をフィードバックとして記事生成に組み込む
- 月30万円の収益確保に向けたコンテンツ戦略の最適化

---

## ファイル構成と変更箇所

**変更ファイル**：
- `/home/user/hojo-hq/scripts/publish_note_article.py`
  - 行 77-145: `login_to_note()` 関数（複数セレクタ戦略）
  - 行 200-290: `post_to_magazine()` 関数（本日改善）

**参考コミット**：
- `54011a5a`: "fix: improve note.com login selectors with multiple fallbacks and better timing"
- `03a46afa`: "fix: improve note.com post button selectors with multiple fallbacks and timing control"

**GitHub Actions ワークフロー**：
- `.github/workflows/note-magazine-automation.yml`
  - 毎日 06:30 JST（UTC 21:30）にスケジュール実行
  - 手動トリガーも対応

---

## まとめ

**現在地**：ログイン機能が動作確認済み。投稿前の「ボタン検出」ステップで失敗していたが、本日セレクタを改善。

**次のマイルストーン**：ワークフローラン 41321237417 の結果を確認し、投稿まで成功すれば完全自動化が実現可能。

**リスク**：note.com が DOM 構造をアップデートした場合、再度セレクタ調整が必要になる可能性がある。その場合は、複数セレクタ試行で対応予定。
