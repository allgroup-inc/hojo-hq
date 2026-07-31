# コード隔離ランブック(保全システムを非公開リポジトリへ)

作成日: 2026-07-26 / 起案: Claude(churn-pii-guard 準拠)/ 実行の決裁: 小柳さん
目的: 早期解約リスク保全システムのコード(`scripts/churn/` 一式)を、**公開リポジトリ `hojo-hq` から非公開リポジトリ `hojo-churn`(private)へ隔離**する。
狙い: 誤コミット=世界公開という最悪ケースを構造から消す(分離アーキテクチャ案 §2 の②)。
前提: 本ランブックは**準備**。実行は小柳さんが `hojo-churn`(private)を新設する決裁の後。

---

## 0. 実行前チェック(churn-pii-guard)
- [ ] `hojo-churn` を **private** で作成することを小柳さんが決裁済み。
- [ ] `private/`(顧客データ)は**移設対象に含めない**(そもそもコミットされていない)。移すのはコードとPIIなしのドキュメント/例のみ。
- [ ] 移設後、`hojo-churn` にも `.githooks` / `.github/workflows/pii-guard.yml`(誤コミット検知)を必ず持たせる。

## 1. 何が動いて、何が残るか

| 対象 | 移設先 | 備考 |
|---|---|---|
| `scripts/churn/**`(コード一式) | → `hojo-churn`(private) | 保全システム本体 |
| `tests/churn/**` | → `hojo-churn` | テスト |
| `docs/superpowers/specs/2026-07-2*-*.md`(churn/karte/console/security系) | → `hojo-churn` | 設計・計画・体制・セキュリティ文書 |
| `docs/顧客*.md` / `docs/守り部審査*.md`(本ランブック含む) | → `hojo-churn` | セキュリティ関連文書 |
| `.githooks/` / `.github/workflows/pii-guard.yml` | → `hojo-churn`(コピー) | 誤コミット検知を移設先にも |
| `.claude/skills/churn-*`(3スキル) | → `hojo-churn`(コピー) | 運用スキル |
| 公開サイト(`site/`, `posts/`, Pages系, 制度収集スクリプト) | **`hojo-hq` に残す** | 公開物・PIIなし |

> 判断ポイント: 移設後、`hojo-hq`(公開)から churn コードを**削除するか**。分離を徹底するなら削除推奨(churn は PII を含まないので情報漏えいではないが、公開リポジトリに機密処理コードを残す意味がない)。→ 小柳さん決裁。

## 2. 移設の2案

### 案A(推奨・単純):クリーンコピーで新設
churn の git 履歴は `hojo-hq` 側に残る(PIIなしなので問題なし)。移設先はコードの現在版から作る。
```bash
# 0) 小柳さんが GitHub で allgroup-inc/hojo-churn を private で作成

# 1) 作業ディレクトリを用意
mkdir /tmp/hojo-churn && cd /tmp/hojo-churn && git init

# 2) hojo-hq から churn 関連一式をコピー(private/ は絶対に含めない)
SRC=/path/to/hojo-hq
mkdir -p scripts tests docs .github/workflows .githooks .claude/skills
cp -r "$SRC"/scripts/churn        scripts/
cp -r "$SRC"/tests/churn          tests/
cp    "$SRC"/.github/workflows/pii-guard.yml .github/workflows/
cp -r "$SRC"/.githooks/*          .githooks/
cp -r "$SRC"/.claude/skills/churn-* .claude/skills/
cp    "$SRC"/docs/顧客*.md "$SRC"/docs/守り部審査*.md "$SRC"/docs/コード隔離*.md docs/ 2>/dev/null
cp    "$SRC"/docs/superpowers/specs/2026-07-2*-*.md docs/ 2>/dev/null

# 3) .gitignore に private/ を入れる(顧客データ用の置き場を最初から除外)
printf '\n# 顧客個人データ・モデル・出力はコミットしない\nprivate/\n' >> .gitignore

# 4) 誤コミット検知を有効化して初コミット
git config core.hooksPath .githooks
git add -A && git commit -m "init: 保全システムを非公開リポジトリへ隔離"
git branch -M main
git remote add origin git@github.com:allgroup-inc/hojo-churn.git
git push -u origin main
```

### 案B(履歴保持):subtree split
churn の履歴ごと切り出したい場合。
```bash
cd /path/to/hojo-hq
git subtree split -P scripts/churn -b churn-only   # コード履歴を枝に
# 新規 private リポジトリ hojo-churn を作り、この枝を土台に再構成(tests/docs は別途コピー)
```
> 注意: subtree は `scripts/churn` 単位。tests/docs/skills は別パスなので、案Bでも周辺はコピーが要る。手間の割に利点が小さいので、通常は**案Aで十分**。

## 3. 移設後の後始末(決裁次第)
- [ ] `hojo-churn` で `python -m unittest discover -s tests/churn` が全通過することを確認。
- [ ] `hojo-churn` で `git config core.hooksPath .githooks`(各自)＋ CI(pii-guard)が動くことを確認。
- [ ] (決裁により)`hojo-hq`(公開)から churn コード・関連docsを削除するPRを出す。公開サイトの動作に影響しないことを確認(churn は Pages とは独立)。
- [ ] アクセス権: `hojo-churn` は**限定メンバーのみ**(最小権限)。

## 4. 実データはこの後
- コード隔離が済んでも、**実データ投入は守り部審査チェックリストの通過＋小柳さん決裁が前提**(セキュリティ運営体制の関門)。
- 実データ・モデル・カルテは移設先でも `private/` 限定・非コミット。誤コミット検知が両リポジトリで効く状態にしておく。

## 5. 決裁待ち事項(小柳さん)
- [ ] `hojo-churn`(private)を新設してよいか
- [ ] 案A(クリーンコピー)/案B(履歴保持)どちらにするか(推奨=A)
- [ ] 移設後、`hojo-hq`(公開)から churn コードを削除するか
- [ ] `hojo-churn` のアクセス権(誰まで)

> 本ランブックはPIIを含まないため公開リポジトリに置いてよい。実行は決裁後。
