# scripts/

## update-skills.sh — vendored スキルの一括更新
全リポジトリの Superpowers(14) と marketingskills(48) を最新版に入れ替える。
手書き資産(ALLGROUP カスタムスキル・product-marketing.md・hooks・settings・tools)は触らない。

```bash
# 対象リポジトリを $BASE 配下に clone 済みにしてから:
BASE=/workspace DRY_RUN=1 bash scripts/update-skills.sh   # 差分だけ確認
BASE=/workspace          bash scripts/update-skills.sh    # 更新してpush
```
Claude Code on the web では、先に各リポジトリを add_repo → clone してから実行する。
マーケ/インフラの振り分けはスクリプト冒頭の MARKETING_REPOS / INFRA_REPOS を編集。
