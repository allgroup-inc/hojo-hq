# 自動化テーブル: moradou.jp 公開フロー（2026-10-08）

## 実装状況一覧

| 項番 | タスク | 実装者 | 実施方法 | ステータス |
|---|---|---|---|---|
| 1️⃣ | ドメイン取得 (`moradou.jp`) | 小柳さん | お名前.com等 | ⏳ 待機 |
| 2️⃣ | GitHub Pages 設定 (allgroup-inc/moradou) | 小柳さん | GitHub Settings → Pages | ⏳ 待機 |
| 3️⃣ | DNS A レコード 4本 追加 | 小柳さん | ドメイン管理画面 | ⏳ 待機 |
| 4️⃣ | DNS CNAME 追加 (www) | 小柳さん | ドメイン管理画面 | ⏳ 待機 |
| **5️⃣** | **DNS開通実測** | **Claude（自動）** | **moradou_cutover.py** | ✅ **準備完了** |
| **6️⃣** | **正規URL切替自動化** | **Claude（自動）** | **fg_seo.py / fg_yamanashi.py** | ✅ **準備完了** |
| 7️⃣ | GA4 ストリーム設定 | 小柳さん | GA4 管理画面 | ⏳ 待機 |
| 8️⃣ | Search Console プロパティ追加 | 小柳さん | GSC | ⏳ 待機 |
| 9️⃣ | LINE プロフィール URL 更新 | 小柳さん | LINE公式 | ⏳ 待機 |
| 🔟 | Instagram プロフィール URL 更新 | 小柳さん | Instagram | ⏳ 待機 |

---

## 自動化実装詳細

### STEP 5: DNS開通実測（自動・毎4時間）

**ファイル**: `.github/workflows/moradou-cutover.yml`

**スケジュール**: `cron: "17 */4 * * *"` (毎4時間、:17分)

**実装スクリプト**: `scripts/moradou_cutover.py --check`

**判定基準**（以下すべて満たしたら「開通」）:

1. ✅ `https://moradou.jp/` が HTTP 200 で返る（SSL証明書も正規）
2. ✅ ページ内に「もらいわすれ堂」のテキストがある
3. ✅ `<link rel="canonical" href="https://moradou.jp/">` が含まれている
4. ✅ `https://moradou.jp/yamanashi/` が HTTP 200 で返る
5. ✅ `https://moradou.jp/sitemap.xml` に `<loc>https://moradou.jp/` が含まれている

**判定後の動き**:
- すべて ✅ → 自動で STEP 6 へ進む（正規URL切替）
- 1つ❌でも → 何もしない / 4時間後に再判定

**進捗確認**: GitHub Actions → hojo-hq → **moradou-cutover** ワークフロー

---

### STEP 6: 正規URL切替自動化（自動・開通確認後）

**ファイル**: `.github/workflows/moradou-cutover.yml` の `apply` ステップ

**実装スクリプト**:
- `scripts/fg_seo.py` → SEO ページのcanonical を書き換え
- `scripts/fg_yamanashi.py` → 山梨版ページのcanonical を書き換え

**実行内容**:
1. MOVED_TO = "moradou.jp" を設定
2. 全ページ（439ページ + 手書きページ）を再生成
3. canonical が `https://moradou.jp/~` を指すように書き換え
4. Git にコミット＆プッシュ

**完了後**:
- ✅ 検索エンジン側が canonical を拾って自動更新
- ✅ 旧URL (github.io) はリダイレクト状態に
- ✅ ワークフロー自動無効化（MOVED_TO が入っていたら何もしない）

---

## 切り戻し手順（もし必要な場合）

```python
# scripts/fg_seo.py の1行目を変更
MOVED_TO = None  # "moradou.jp" から変更

# scripts/fg_yamanashi.py の1行目を変更
MOVED_TO = None  # "moradou.jp" から変更

# 変更をコミット
git add scripts/fg_seo.py scripts/fg_yamanashi.py
git commit -m "revert: moradou.jp から旧URL (github.io) に戻す"
git push

# ワークフロー実行：hojo-hq → fukugiiro-fetch
# → 次の実行時に自動で旧URLに復帰
```

---

## 現在の準備状況

| 部品 | ファイル | 確認日 | 状態 |
|---|---|---|---|
| ワークフロー | `.github/workflows/moradou-cutover.yml` | 2026-10-08 | ✅ 実装済み |
| 開通判定スクリプト | `scripts/moradou_cutover.py` | 2026-10-08 | ✅ 実装済み |
| SEO書き換え | `scripts/fg_seo.py` | 2026-10-08 | ✅ 実装済み |
| 山梨版書き換え | `scripts/fg_yamanashi.py` | 2026-10-08 | ✅ 実装済み |
| site/fukugiiro コンテンツ | `site/fukugiiro/` | 2026-10-08 | ✅ 最新版(STEP 1完了) |
| 配信先リポジトリ | `allgroup-inc/moradou` | 2026-10-08 | ✅ 存在確認 |

---

## トラブルシューティング

### 開通実測が失敗する場合

**症状**: `moradou-cutover` の ❌ ステータス

**確認**: `moradou_cutover.py` の判定ログ（Actions出力で確認）

| エラー | 意味 | 対応 |
|---|---|---|
| "開通していません (exit 2)" | DNS伝播がまだ | DNS設定後1-6時間待つ |
| "HTTP 403" | アクセス制限 | DNS設定確認 |
| "404" | ドメイン存在しない | DNS設定確認 |
| "もらいわすれ堂が見つからない" | 内容がない | allgroup-inc/moradou のビルド確認 |
| "canonical が moradou.jp を指していない" | 旧URL設定のまま | deployment 再実行 |

---

## 監視ポイント

DNS設定完了後は以下を監視:

1. **GitHub Actions**: moradou-cutover ワークフロー
   - 初回成功時刻をメモ
   - 失敗 ❌ が連続していないか確認

2. **DNS 伝播**: DNSチェッカー（https://dns.google/）で確認
   - moradou.jp のA レコード 4本が正しく返っているか

3. **ブラウザ**: 手動でアクセス確認
   - https://moradou.jp/
   - https://moradou.jp/fukugiiro/
   - https://moradou.jp/yamanashi/

---

**文書作成**: Claude Haiku 4.5  
**作成日**: 2026-10-08  
**レベル**: 技術者向け（自動化の仕組み）
