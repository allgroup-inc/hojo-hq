# 三名体制(トライアングル体制)スキル検証スクリプト

このディレクトリには、`.claude/skills/hojo-triangle-review/SKILL.md` で定義された三名体制ディスカッション(トライアングル体制)の自動検証スクリプトが含まれています。

## 用途

議事ファイル(`docs/議事_YYYYMMDD_<件名>.md`)が、三名体制の規程に従っているかを自動検査します。

## インストール

不要。Python 3.8 以上があれば実行可能。

## 使用方法

### 全議事ファイルを検証

```bash
# ファイル形式チェック
python tests/skill_validation/test_triangle_review.py validate_format

# ウタガイセクション有効性チェック
python tests/skill_validation/test_triangle_review.py validate_utagai

# 参照ファイル存在性チェック
python tests/skill_validation/test_triangle_review.py validate_references

# 見直し期限妥当性チェック
python tests/skill_validation/test_triangle_review.py validate_deadline
```

### 特定の議事ファイルだけを検証

```bash
python tests/skill_validation/test_triangle_review.py validate_format docs/議事_20261005_件名.md
python tests/skill_validation/test_triangle_review.py validate_utagai docs/議事_20261005_件名.md
```

### 失敗モードを自動検出

```bash
python tests/skill_validation/test_triangle_review.py auto_issue
```

## 検証項目

### Step 6-1: ファイル形式チェック (validate_format)

- ✓ ファイル名が `議事_YYYYMMDD_<件名>.md` 形式か
- ✓ 必須セクション(論点/スイシン/ウタガイ/ベッカイ/結論)がすべて存在するか
- ✓ ファイルサイズが正常か(1KB～50KB)
- ✓ YAML front matter がないか

### Step 6-2: ウタガイセクション有効性チェック (validate_utagai)

- ✓ ウタガイ(懐疑)セクションが空欄でないか
- ✓ 反対理由が最低50字以上あるか
- ✓ 反対理由が具体的か(根拠を含むか)
- ✓ 「※反対理由の記録」ラベルが付いているか(推奨)

### Step 6-3: 参照ファイル存在性チェック (validate_references)

- ✓ 議事内で参照される全ての `docs/*.md` ファイルが実在するか
- ✓ URL の形式が正しいか(http/https)

### Step 6-4: 見直し期限妥当性チェック (validate_deadline)

- ✓ 見直し期限が「最長6ヶ月」ルール内か(180日以内)
- ✓ 期限が過去日付になっていないか
- ✓ 期限形式が YYYY-MM-DD か

## 終了コード

- **0**: すべての検証が PASS
- **1**: 1項目以上の検証が FAIL

## 自動検出される失敗モード

### 失敗モード 1: ウタガイの反対理由が記録されていない

**検出方法**: ウタガイ(懐疑)セクションが空欄

**対応**: Step 4 「ウタガイの反対理由が『有効』か検証」を参照

### 失敗モード 2: ウタガイが遠回しで、反対理由として成立していない

**検出方法**: 反対理由が短すぎる(50字未満)、または曖昧(根拠がない)

**対応**: SKILL.md Step 2「ウタガイ役からの反対理由を引き出す」を参照

### 失敗モード 3: 議事なしで先行実装

**検出方法**: ファイルが存在しない、またはセクションが欠落している

**対応**: SKILL.md Step 1「議論対象の判定」を参照

### 失敗モード 4: 議事が存在しないファイルを参照している

**検出方法**: 参照ファイル存在性チェックで検出

**対応**: SKILL.md Step 3「参照ファイルの存在性チェック」を参照

## 使用例

```bash
# 1. 新しく作った議事ファイルを検証
python tests/skill_validation/test_triangle_review.py validate_format docs/議事_20261005_新施策.md
python tests/skill_validation/test_triangle_review.py validate_utagai docs/議事_20261005_新施策.md
python tests/skill_validation/test_triangle_review.py validate_references docs/議事_20261005_新施策.md
python tests/skill_validation/test_triangle_review.py validate_deadline docs/議事_20261005_新施策.md

# 2. すべての議事ファイルが有効か一括チェック
for cmd in validate_format validate_utagai validate_references validate_deadline; do
  python tests/skill_validation/test_triangle_review.py $cmd
done

# 3. 失敗している議事をすべて表示
python tests/skill_validation/test_triangle_review.py auto_issue
```

## 参照

- `.claude/skills/hojo-triangle-review/SKILL.md` — スキルの詳細手順
- `CLAUDE.md` — 三名体制運営規程
- `docs/議事_YYYYMMDD_*.md` — 議事テンプレート
