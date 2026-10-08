# moradou.jp 公開 — クイックスタート

**小柳さんへ**: 以下の手順で進めてください。

---

## 📍 現在地: DNS未設定

```
[✅ DONE] ig_neta.json 精度修正（2026-10-08）
[✅ DONE] GitHub Pages 設定 (allgroup-inc/moradou)
[⏳ HERE] DNS設定（小柳さんが実施）
[⏳ WAIT] 自動開通確認＆URL切替（Claude が自動実行）
[⏳ WAIT] 外部サービス設定（小柳さんが実施）
```

---

## 🚀 やること（3ステップ・15分）

### 👉 STEP 1: ドメイン取得（10分）

**URL**: https://www.onamae.com/ （またはムームードメイン等）

1. `moradou.jp` で検索 → 購入
2. 登録者情報: **株式会社フクギイロ**（正確に）
3. **Whois代行**: ON (重要!)
4. **自動更新**: ON (重要!)

**完了したら** → Slack で報告

---

### 👉 STEP 2: GitHub Pages 設定（3分）

**URL**: https://github.com/allgroup-inc/moradou/settings/pages

1. Branch: `main` / Folder: `/ (root)` → Save
2. Custom domain: `moradou.jp` 入力 → Save
3. DNS不可と出ても OK（STEP 3 の後で OK になる）

**完了したら** → Slack で報告

---

### 👉 STEP 3: DNS設定（5分）

**お名前.com の管理画面**で:

**A レコード** 4本:
```
185.199.108.153
185.199.109.153
185.199.110.153
185.199.111.153
```

**CNAME** 1本:
```
www  →  allgroup-inc.github.io
```

保存 → **完了！**

---

## ⏳ DNS設定後（自動処理・待つだけ）

### 自動で何が起きるか

**Claude が毎4時間、自動で以下を実行**:

1. ✅ moradou.jp が開き、「もらいわすれ堂」と表示される
2. ✅ ページの canonical が moradou.jp を指している
3. ✅ sitemap.xml に moradou.jp のURLが入っている

**3つ全部 OK ⇒ 自動で正規URL切替**（全ページの canonical を moradou.jp へ書き換え）

### 進捗確認

GitHub Actions → hojo-hq → **moradou-cutover** を見る

（最初のチェック: DNS設定後 **4〜24時間以内に成功** のはず）

---

## 🎯 開通確認（自分でもテストしたい場合）

DNS設定後、好きなタイミングで手動実行:

**GitHub**: hojo-hq → Actions → **moradou-cutover** → **Run workflow** をクリック

（開通していなければ何もしません。何度押しても害はありません）

---

## ✅ 開通後（moradou.jp が見えたら）

以下を実施:

- [ ] **GA4**: https://analytics.google.com/ → ストリーム追加
- [ ] **Google Search Console**: https://search.google.com/search-console → moradou.jp 追加
- [ ] **LINE**: プロフィール編集 → リンク = https://moradou.jp/
- [ ] **Instagram**: プロフィール編集 → リンク = https://moradou.jp/

---

## 📋 参考ドキュメント

- **詳細手順**: `docs/もらいわすれ堂_正式ドメイン公開手順_2026-10-08.md`
- **チェックリスト**: `docs/小柳さんチェックリスト_moradou.jp公開_2026-10-08.md`
- **技術詳細**: `docs/自動化テーブル_moradou.jp_2026-10-08.md`
- **実装ガイド**: `deploy/moradou/README.md`

---

## 🆘 トラブル

### DNS設定後も見えない

**原因**: DNS伝播中（最大24時間）

**対応**: 待つ

---

**準備**: Claude Haiku 4.5 (2026-10-08)  
**実行**: 小柳さん  
**所要時間**: 15分
