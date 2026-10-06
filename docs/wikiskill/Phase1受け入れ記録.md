# WikiSkill Phase 1 受け入れ記録(空の台帳)

Task 8(手動 E2E と Baseline 比較)で記入する。それまで空欄のまま置く。
導入議事: `docs/議事_20261006_WikiSkill_Phase1導入.md`

## 手動 E2E(セッション A → 新しいセッション B)

| 項目 | 内容 |
|---|---|
| 実施日時 | |
| session_id(A) | |
| session_id(B) | |
| session_id(C) | |

| # | 確認項目(計画 Task 8 Step 5) | 結果(✅ / ❌) | 備考 |
|---|---|---|---|
| 1 | Session A: 開始直後に `# 🧠 Memory Bootstrap` が注入される(段1)。試験用の議事と note を commit・push して終了できる | | |
| 2 | Session B(新しいセッション): 開始直後の Bootstrap に試験用の `[D]` と「なぜ:」「ウタガイ:」が出る | | |
| 3 | Session B: 最初の指示(「マージ競合の手順」)で段2に `[FK-002]` と `[再発防止]` が出る。2回目の指示では何も注入されない | | |
| 4 | 速度: 各 hook 段は自分の実行時間を測り、500ms を超えたら `.claude/experience/_audit.log` に `slow <event> <ms>ms` を追記する(監査ログのみ・画面警告なし)。下の「速度の実測」で、実測 0.5秒未満 かつ `slow` 行 0件 のとき ✅ | | |
| 5 | Session C: `.claude/memory.off` を置くと Bootstrap も記録も止まり、消すと再開する | | |

## 速度の実測(項目4)

```bash
time (echo '{"session_id":"timing-check","hook_event_name":"SessionStart","source":"startup"}' | bash .claude/hooks/wikiskill-hook.sh SessionStart > /dev/null)
grep -c "slow " .claude/experience/_audit.log    # ファイルが無ければ 0 とみなす
```

測定後、作られた記録ファイル(`.claude/experience/` 以下の `session-timing-check.jsonl`)を削除する。

| 測定値(real) | `slow` 行の数 | 判定(0.5秒未満 かつ 0件で ✅) |
|---|---|---|
| _ 秒 | _ 件 | |

## Bootstrap 実出力(先頭20行)

```text
(Task 8 で貼り付ける)
```

## 所見

(Task 8 で記入)

## Baseline 比較

| 項目 | Privacy | Skill validation | scripts tests |
|---|---|---|---|
| Baseline(2026-10-06 固定) | 9 | 5 | 2 |
| Final | _ | _ | _ |
| Delta | _ | _ | _ |

判定(SAME / IMPROVED / REGRESSION): _
