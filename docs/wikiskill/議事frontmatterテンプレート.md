# 議事frontmatterテンプレート(WikiSkill Phase 1 / Decision Memory)

新しい議事(`docs/議事_YYYYMMDD_<件名>.md`)の先頭に次の frontmatter を付ける。`scripts/decision_memory.py` がこれを読み、Memory Bootstrap(セッション開始時の記憶)が決定の出典 `[D]` として使う。

下の `decision_id: D20260101-example` は書き方の例であり、実在する決定ではない。他の値(`date` `title` `review_by` など)も記入例なので、コピーしたら必ず書き換える。

```yaml
---
decision_id: D20260101-example             # D + 日付 + slug
date: 2026-10-06
title: WikiSkill Phase 1 導入
scope: hojo-hq/基盤                        # 事業/部門。自由記述
tags: [memory, hooks, skills]
status: adopted                            # adopted | rejected | deferred | superseded
review_by: 2027-04-04                      # 省略時は date+180日
supersedes:                                # 置き換える決定の decision_id(任意)
decided_by: 小柳
visibility: public   # 任意。既定はリポジトリの公開性(private リポの議事は private)
---
```

## 各項目の意味

- `decision_id`: 決定の固有ID。`D` + 日付(YYYYMMDD)+ 短い slug。必須。
- `date`: 決定または起案の日(YYYY-MM-DD)。必須。
- `title`: 決定の件名。必須。
- `scope`: どの事業・部門の決定か。自由記述(例: `hojo-hq/基盤`)。
- `tags`: 検索用の語。`[a, b]` の形。Memory Bootstrap が関連する決定を探すときの手がかりになる。
- `status`: `adopted`(採用)/ `rejected`(不採用)/ `deferred`(決裁待ち・保留)/ `superseded`(後の決定で置換)のいずれか。必須。
- `review_by`: 見直し期限(YYYY-MM-DD)。`date` より後の日付。省略すると `date` の180日後になる。期限を過ぎた決定は `expired` と表示される。
- `supersedes`: この決定が置き換える過去の決定の `decision_id`。無ければ空欄のまま。
- `decided_by`: 決裁者。
- `visibility`: 任意。`public` / `private`(それ以外は `--check` で違反)。省略するとリポジトリの公開性に従う(private リポの議事は常に private)。`private` と書いた議事は、Wiki 検証器(V05)が公開 Wiki の根拠(`source_decision`)として認めない。

## 本文の見出し(既存の議事と同じ)

```markdown
## なぜ(背景)
## 前提
## 代替案
## 三名体制の議論
- **スイシン(推進)**: ...
- **ウタガイ(懐疑・反対理由。必須)**: ...
- **ベッカイ(別解・前提を疑う)**: ...
## 裁定
## 見直し条件
```

## 注意(3点)

1. **過去の議事には付け直さない(遡及しない)。** frontmatter が無い既存の議事は、`decision_memory.py` が見出しと行の形から推定して読む。既存ファイルは書き換えない。
2. **ウタガイ(反対理由)が空欄だと `--check` で止まる。** `ウタガイ` の行が無い、またはコロンの後(または直下の字下げ項目)に反対理由が無い場合は違反になる。検査は `python3 scripts/decision_memory.py --check docs/議事_YYYYMMDD_<件名>.md`(違反があれば exit 1)。
3. **見出しは `## なぜ` か `## 背景` を必ず置く。** どちらも無いと `--check` が止まる。`status`・`date`・`title`・`decision_id` が欠けた場合も同様。
