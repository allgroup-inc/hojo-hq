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

## スキル運用ポリシー(継続メンテナンス)

「常に最新・かつ軽量」を保つための方針。小柳さんの承認を都度取らず自動で行ってよい範囲と、
提案止まりにする範囲を分けている。

### 自動で行ってよいこと(承認不要)
- **既に採用済みのライブラリ**(obra/superpowers・coreyhaines31/marketingskills)を
  upstream最新commitに追従させる(`update-skills.sh`)。
- 全8リポジトリのスキル数が既定値からズレていないか監査する:
  - マーケ系5リポジトリ(hojo-hq / hikari-hq / hikari-lp / hikari-report / kakei-hq): **73**
    (Superpowers14 + marketingskills48 + ALLGROUPカスタム11)
  - インフラ系3リポジトリ(report-hq / go / allgroup-site): **25**
    (Superpowers14 + ALLGROUPカスタム11、marketingskillsは載せず軽量化)
- 孤立ディレクトリ・重複スキル名など、明らかなゴミを掃除する。

### 提案止まりにすること(承認必須)
- **新しいスキルライブラリ・ツールの追加採用**。品質・関連性の判断は人間が行う。
  見つけたら候補としてチャットで報告するだけに留め、無断でリポジトリに入れない。
- 各事業の `.agents/product-marketing.md` の数値・方針に関わる変更(事実確認が要る箇所)。

### 自動チェックの実行

毎週、この運用を回すRoutine(スケジュール実行)を設定済み。手動で今すぐ回したい場合は
`update-skills.sh` を実行するか、Claude に「スキルの更新チェックして」と頼む。
