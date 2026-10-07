# WikiSkill Phase 2 受け入れ記録

Task 8(自動 E2E と、実セッション A → B → C の手動 E2E)の記入結果。**未記入(Task 8 で記入する空の台帳)。**
導入議事: `docs/議事/議事_20261007_WikiSkill_Phase2導入.md`
設計書の合格条件: `docs/superpowers/specs/2026-10-07-wikiskill-phase2-knowledge-wiki-design.md`(13章)

試験用の Wiki は題の先頭を「受け入れ試験:」にし、試験後に `docs/wiki/_archive/` へ superseded として移す(本物の知識として残さない)。試験の note に顧客情報・private の内容を書かない。

## 実セッション E2E(A → B → C)

| 項目 | 内容 |
|---|---|
| 実施日時 | |
| session_id(A) | |
| session_id(B) | |
| session_id(C) | |

| # | 確認項目 | 結果(✅ / ❌) | 備考 |
|---|---|---|---|
| F1 | Session A: note `学び: …` を記録し、Experience と関連する議事を commit・push する | | |
| F2 | 抽出(knowledge-extract を dispatch、またはローカルで `--max 3`)が候補を `docs/wiki/_candidates/` に作る | | |
| F3 | 候補が検証(`python3 scripts/wiki_validate.py`)を通る | | |
| F4 | ウタガイが空のままの昇格は検証で止まる | | |
| F5 | 人の承認(昇格 PR 相当)後、検証が通り commit できる | | |
| F6 | Session B: 注入の並びが [再発防止] → [Wiki] → [Skill] | | |
| F7 | Session B: `[Wiki]` 行に題・要約・`根拠:`・`承認:`・パスが出る | | |
| F8 | Session C: `.claude/wiki.off` で `[Wiki]` だけ止まり、他の区分と記録は動く。消すと戻る | | |
| R4 | 逆方向: 矛盾した候補(conflict)が Session B の注入(段1・段2)に一切出ない。`docs/wiki/` 直下に該当ファイルが無い | | |

## Session B の注入テキスト(`[Wiki]` 行の前後20行)

```text
(Task 8 で貼る)
```

## SessionStart の所要時間

| 測定値(real) | `_audit.log` の `slow` 行の数 | 判定(0.5秒未満 かつ 0件で ✅) |
|---|---|---|
| | | |

## 自動 E2E と全体テスト

| 項目 | 結果 |
|---|---|
| `python3 -m pytest tests/integration/test_wikiskill_wiki_e2e.py -q` | |
| 全体テスト(Phase 1 の固定テスト ID が全て PASS / failed は Baseline の2件のみ)・Phase 2 の新規テスト数(実数) | |
| `python3 scripts/wiki_validate.py && python3 scripts/check_experience_privacy.py` | |

## Baseline 比較

```text
(`python3 scripts/baseline_debt.py --compare` の出力を貼る)
```

## 所見

(Task 8 で記入。❌ が出たら PR をマージせず、該当の Task に戻る)
