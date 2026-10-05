# GitHub Secrets 設定完全ガイド

note誌面の自動化を動かすために、GitHub Secrets に4つの秘密鍵を登録する手順です。

---

## 📋 必要な4つの Secret

| Secret名 | 説明 | 取得方法 |
|---|---|---|
| `ANTHROPIC_API_KEY` | Claude API キー | Anthropic コンソール |
| `NOTE_USER_EMAIL` | noteのメールアドレス | あなたのnoteアカウント |
| `NOTE_USER_PASSWORD` | noteのパスワード | あなたのnoteアカウント |
| `NOTE_MAGAZINE_ID` | noteマガジンのID番号 | noteマガジンのURL |

---

## 🔧 Step 1: GitHub の Secrets ページを開く

### ブラウザで以下のURLを開く

```
https://github.com/allgroup-inc/hojo-hq/settings/secrets/actions
```

または以下の手順：

1. **GitHub** にログイン
2. **allgroup-inc/hojo-hq** リポジトリを開く
3. リポジトリ上部タブから **Settings** をクリック
4. 左サイドバーから **Secrets and variables** → **Actions** をクリック

![GitHub Settings](https://imgur.com/placeholder.png)

---

## 🔑 Step 2: 各 Secret を登録

### Secret 1️⃣: `ANTHROPIC_API_KEY`

#### ① APIキーを取得する

1. ブラウザで以下を開く: **https://console.anthropic.com/account/keys**
2. Anthropic アカウントでログイン
3. **Create Key** をクリック
4. キーをコピー（`sk-ant-` で始まる長い文字列）

![Anthropic Console](https://imgur.com/placeholder.png)

#### ② GitHub Secrets に登録する

1. GitHub Secrets ページで **New repository secret** をクリック
2. **Name** に `ANTHROPIC_API_KEY` と入力
3. **Secret** に Anthropic から取得したキーをペースト
4. **Add secret** をクリック

```
Name:   ANTHROPIC_API_KEY
Secret: sk-ant-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

✅ 登録完了！

---

### Secret 2️⃣: `NOTE_USER_EMAIL`

#### ① noteのメールアドレスを確認

1. ブラウザで **https://note.com** を開く
2. 右上のプロフィールアイコン → **設定** をクリック
3. **アカウント設定** から **メールアドレス** を確認

または

- noteにログインしたメールアドレスをそのまま使用

#### ② GitHub Secrets に登録する

1. **New repository secret** をクリック
2. **Name** に `NOTE_USER_EMAIL` と入力
3. **Secret** に noteのメールアドレスをペースト
   ```
   例: your-account@gmail.com
   ```
4. **Add secret** をクリック

✅ 登録完了！

---

### Secret 3️⃣: `NOTE_USER_PASSWORD`

#### ① noteのパスワードを確認

noteにログインするときに使用しているパスワードです。

#### ② GitHub Secrets に登録する

1. **New repository secret** をクリック
2. **Name** に `NOTE_USER_PASSWORD` と入力
3. **Secret** に noteのパスワードをペースト
   ```
   例: MySecurePassword123!
   ```
4. **Add secret** をクリック

⚠️ **重要**: GitHub が自動で暗号化してくれるため、ログには表示されません。

✅ 登録完了！

---

### Secret 4️⃣: `NOTE_MAGAZINE_ID` ⭐ 最も重要

このIDを取得する3つの方法：

#### 方法 A: noteマガジンのURLから取得（最も簡単）

1. **note** にログイン
2. 自分のマガジンを開く
   ```
   https://note.com/my/magazines
   ```
3. マガジンをクリック → ブラウザのURLバーを確認

**URL例:**
```
https://note.com/magazines/abc123def456
            ↑ この部分がIDです
```

**結果:**
```
NOTE_MAGAZINE_ID = abc123def456
```

#### 方法 B: マガジンの編集ページから取得

1. noteにログイン
2. 右上メニュー → **クリエイター設定** → **マガジン管理**
3. 編集するマガジンをクリック
4. URLを確認:
   ```
   https://note.com/my/magazines/abc123def456/edit
                                ↑ このIDをコピー
   ```

#### 方法 C: URLに直接アクセスして確認

1. noteにログイン状態で、以下のURLにアクセス:
   ```
   https://note.com/my/magazines
   ```
2. ページ内に「マガジン一覧」が表示される
3. あなたのマガジンの「編集」をクリック
4. URLから `magazines/` の後ろの部分 = ID

#### ② GitHub Secrets に登録する

1. **New repository secret** をクリック
2. **Name** に `NOTE_MAGAZINE_ID` と入力
3. **Secret** に 取得したIDをペースト
   ```
   例: abc123def456
   ```
4. **Add secret** をクリック

✅ 登録完了！

---

## ✅ 確認チェックリスト

GitHub Secrets ページで、以下の4つが登録されているか確認：

- [ ] `ANTHROPIC_API_KEY` — ✅ 登録済み
- [ ] `NOTE_USER_EMAIL` — ✅ 登録済み
- [ ] `NOTE_USER_PASSWORD` — ✅ 登録済み
- [ ] `NOTE_MAGAZINE_ID` — ✅ 登録済み

**すべてチェック✅が入れば完了！**

---

## 🧪 Step 3: ワークフロー実行テスト

### 手動でテスト実行

1. GitHub Actions ページを開く
   ```
   https://github.com/allgroup-inc/hojo-hq/actions/workflows/note-magazine-automation.yml
   ```

2. **Run workflow** ボタンをクリック
   ![Run Workflow](https://imgur.com/placeholder.png)

3. **Branch**: `claude/note-ai-automation-revenue-apb22t` を選択

4. **Run workflow** をクリック

### 実行結果を確認

1. ワークフロー実行が開始される（数秒で開始）
2. 「generate-and-publish」ジョブをクリック
3. ログを確認:

**成功時のログ:**
```
✅ ソースコード取得
✅ Python セットアップ
✅ 依存パッケージをインストール
✅ 記事を自動生成 — Claude API呼び出し成功
✅ 生成記事をコミット
✅ note へ自動投稿 — 投稿完了
```

**失敗時:**
```
❌ ANTHROPIC_API_KEY が見つかりません
  → Secrets が正しく設定されていない

❌ ログイン失敗
  → NOTE_USER_EMAIL / PASSWORD が間違っている

❌ マガジンが見つかりません
  → NOTE_MAGAZINE_ID が間違っている
```

---

## 📅 自動実行開始

Secrets設定が完了すると、以下のスケジュールで自動実行されます：

| 時刻 | 処理 | ファイル |
|---|---|---|
| **毎日 06:30 JST** | 記事生成 | `posts/note_magazine/YYYY-MM-DD_volXXX.md` |
| **毎日 07:00 JST** | 自動投稿 | noteマガジンに掲載 |
| **毎週日曜 18:00 JST** | 分析レポート | `docs/note_analytics/` |

---

## 🆘 トラブルシューティング

### Q: Secret が登録されているのに「見つかりません」と言われる

**A:** GitHub Secrets の変更は、リポジトリの新しいワークフロー実行から反映されます。
- 解決: **Run workflow** で手動実行を再度試してください

### Q: 「ログイン失敗」エラーが出た

**A:** 以下を確認:
1. NOTE_USER_EMAIL / NOTE_USER_PASSWORD が正確か
2. noteアカウントが2段階認証を有効にしていないか
3. noteアカウントが一時的にロックされていないか

**解決:**
- noteに手動でログインして正常に入れるか確認
- Secrets に登録しているメール/パスワードが正しいか再確認

### Q: 「マガジンが見つかりません」エラー

**A:** NOTE_MAGAZINE_ID が間違っている可能性

**解決:**
1. noteで自分のマガジンを開く
2. URLから IDを改めて確認
3. GitHub Secrets で NOTE_MAGAZINE_ID を更新

### Q: GitHub Actions のコストはかかる？

**A:** 無料プランで月3,000分まで無料です。
- この自動化: 毎日 5-10分程度 → 月 150-300分（余裕で無料枠内）

---

## 📞 サポート

ワークフロー実行時のエラーログが出ている場合：

1. **GitHub Actions ページ** でログを全文コピー
2. 以下の情報をまとめる:
   - エラーメッセージ
   - 実行日時
   - 実行履歴

---

**これで完全に自動化されます。毎日自動的に記事が生成・投稿・分析されます！** 🚀
