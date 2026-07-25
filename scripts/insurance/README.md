# 反映監査 audit_reflection.py

ALLGRP board(xlsx)の反映(入力)の正確性を機械検知する。断定せず「要確認」を出す。

## 使い方
```
python scripts/insurance/audit_reflection.py <board.xlsx> --out <report.md>
```

- 生データ・実データレポートは **git にコミットしない**(設計書§5)。
- 出力先はスクラッチパッド等の**非追跡ディレクトリ**にする。

## 検知内容
- 非負であるべき指標の負値(`NONNEG_METRICS`)= `detect_negative_anomalies`
- 空欄(blank)= `detect_blanks`
- ロールアップ照合(個人合計 = 管轄 = 全体)= `check_rollup`

## テスト
```
python -m pytest tests/insurance/test_audit_reflection.py -v
```
`NONNEG_METRICS` の根拠は `docs/insurance/10_数値モデル定義書.md` §5(符号の約束)。
