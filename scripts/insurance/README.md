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

## 符号ルール(指示書v1.0準拠 / 過検知の是正)
- **QCM の解約・戻入・実効単価/想定単価は「少ないほど良い」= 負値が仕様**。`is_expected_negative()` が部門×指標で判定し、要確認から除外する。
- ⑦⑧(ANP/戻入)は ALL委託・QCM のみ円単位、QCM⑦は絶対値。
- board解析は「定例_XXX」ヘッダから各列ブロックの部門を解決し、部門別に符号を適用。
- 負値スキャンは**一次スクリーン**。真の反映監査 = 部門合計(チーム合計)= board の突合(`check_rollup`)。詳細は `docs/insurance/10_数値モデル定義書.md` §4/§6。

## テスト
```
python -m pytest tests/insurance/test_audit_reflection.py -v
```
`NONNEG_METRICS` の根拠は `docs/insurance/10_数値モデル定義書.md` §5(符号の約束)。
