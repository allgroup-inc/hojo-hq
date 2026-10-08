# チェックリスト: moradou.jp 正式ドメイン公開

**決裁**: 2026-09-23 小柳さん決裁済み  
**対象**: 株式会社フクギイロ・もらいわすれ堂  
**ドメイン**: moradou.jp  

---

## 📋 実行手順（3ステップ・15分）

### STEP 1: ドメイン取得（10分・年額3,000円）

- [ ] お名前.com / ムームードメイン / Xserverドメイン など好きなサービスを開く
- [ ] **ドメイン検索**: `moradou.jp` と入力
- [ ] **ドメイン登録**: 購入手続き
  - [ ] 登録者名: **株式会社フクギイロ（正式名称）**
  - [ ] 住所・電話番号: **正確に** 登録
  - [ ] **Whois代行**: ☑️ ON（必須。切ると住所がネットに公開されます）
  - [ ] **自動更新**: ☑️ ON（必須。切れるとサイトが落ちます）
- [ ] **完了**: ドメイン取得完了メールを受け取る

**終わったら** → 以下のSlackで報告:
```
moradou.jp 取得完了。STEP 2へ進んでください。
```

---

### STEP 2: GitHub Pages 設定（3分）

1. ブラウザで開く: https://github.com/allgroup-inc/moradou/settings/pages
2. **Source** セクション:
   - Branch: `main` を選択
   - Folder: `/ (root)` を選択
   - **Save** をクリック
3. **Custom domain** セクション:
   - テキストボックスに: `moradou.jp` と入力
   - **Save** をクリック
   - ⚠️ 「DNS check unsuccessful」と出てもOK（DNSがまだだから）
4. **Enforce HTTPS** セクション（DNS設定後に実施）:
   - 後で戻ってチェック ☑️ ON

**終わったら** → 以下のSlackで報告:
```
GitHub Pages 設定完了。STEP 3へ進んでください。
```

---

### STEP 3: DNS設定（5分・ドメイン管理画面で）

**ドメイン取得したサービスの管理画面**（お名前.com / ムームードメイン 等）を開く

#### A レコード を4本追加

ホスト名: 空欄 または `@`

| IP アドレス |
|---|
| 185.199.108.153 |
| 185.199.109.153 |
| 185.199.110.153 |
| 185.199.111.153 |

- [ ] レコード1: 185.199.108.153 を追加
- [ ] レコード2: 185.199.109.153 を追加
- [ ] レコード3: 185.199.110.153 を追加
- [ ] レコード4: 185.199.111.153 を追加

#### CNAME を1本追加

ホスト名: `www`  
値: `allgroup-inc.github.io`

- [ ] CNAME: www → allgroup-inc.github.io を追加

#### 完了

- [ ] DNS 設定を保存（管理画面の「保存」ボタン）
- [ ] DNS 伝播完了を待つ（通常5分〜数時間）

**終わったら** → 以下のSlackで報告:
```
DNS設定完了。以降は自動で開通確認が進みます。
```

---

## ⏳ DNS設定後（自動処理・小柳さんは待つだけ）

### 自動で何が起きるか

1. **毎4時間ごと**、Claude が moradou.jp の開通確認
2. **開通確認条件**（3つ全部OK）:
   - ✅ https://moradou.jp/ が開く
   - ✅ ページの canonical が moradou.jp を指している
   - ✅ /yamanashi/ と sitemap.xml が新ドメインのURLを含む
3. **開通確認後、自動実行**:
   - 旧URLのcanonical を全ページで moradou.jp へ書き換え
   - 検索エンジンへ通知

**進捗確認**: hojo-hq リポジトリの Actions → **moradou-cutover** を見る

---

## 🚀 開通後（DNS伝播完了後）

moradou.jp が開き、中身が見えたら以下を実施:

- [ ] **GA4**: ストリーム URL に moradou.jp を追加
- [ ] **Google Search Console**: moradou.jp プロパティを追加
- [ ] **LINE公式アカウント**: プロフィール URL を moradou.jp へ変更
- [ ] **Instagram**: プロフィール URL を moradou.jp へ変更

---

## 🆘 トラブル

### DNS設定後も moradou.jp が見えない

**原因**: DNS伝播待機中（最大数時間）

**対応**: 待つ（あと30分後に再度確認）

### 開通確認が進まない

**確認**: hojo-hq Actions → **moradou-cutover** → **Run workflow** 実行
（まだ開通していなければ何もしません）

### URL が間違っていた場合

**切り戻し手順**:
1. `scripts/fg_seo.py` の `MOVED_TO = 'moradou.jp'` を `MOVED_TO = None` に変更
2. `scripts/fg_yamanashi.py` も同様に変更
3. ワークフロー実行
→ 旧URLに自動復帰

---

**文書作成**: Claude Haiku 4.5  
**作成日**: 2026-10-08  
**難易度**: ⭐ 簡単（作業は小柳さんのドメイン取得画面 + GitHub 1つだけ）
