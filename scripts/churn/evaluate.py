"""バックテスト：過去の一時点で採点したら当たったかを検証する品質ゲート。"""
from __future__ import annotations

from .fit import fit_model
from .score import score_record
from .config import CAPACITY_PER_DAY, CALIBRATION_ECE_WARN


def auc(pairs):
    """(risk, actual) のリストから Mann-Whitney AUC。"""
    pos = [r for r, y in pairs if y == 1]
    neg = [r for r, y in pairs if y == 0]
    if not pos or not neg:
        return 0.5
    wins = 0.0
    for p in pos:
        for n in neg:
            wins += 1.0 if p > n else 0.5 if p == n else 0.0
    return wins / (len(pos) * len(neg))


def calibration(scored, bins=10):
    """予測%と実測%の一致（较正）。予測リスクを bins 等幅に分け、各ビンの予測平均・実測平均。

    返り値: (rows, ece)。ece=期待较正誤差（件数重み付き |予測−実測| の平均）。
    ece が大きい＝リスク%が信用できない（当たっても水準がズレる）。churn-model-quality-gate。
    """
    buckets = [[] for _ in range(bins)]
    for r, y in scored:
        idx = min(bins - 1, max(0, int(r * bins)))
        buckets[idx].append((r, y))
    n_total = len(scored)
    rows, ece = [], 0.0
    for i, b in enumerate(buckets):
        if not b:
            rows.append({"bin": i, "n": 0, "pred": None, "actual": None})
            continue
        pred = sum(x for x, _ in b) / len(b)
        actual = sum(y for _, y in b) / len(b)
        rows.append({"bin": i, "n": len(b), "pred": pred, "actual": actual})
        ece += (len(b) / n_total) * abs(pred - actual)
    return rows, ece


def precision_at_capacity(scored, capacity):
    """上位 capacity 件（リスク高い順）の実解約率＝限られたキャパを当てられているか。"""
    ranked = sorted(scored, key=lambda x: x[0], reverse=True)
    k = min(capacity, len(ranked))
    if k == 0:
        return 0.0
    return sum(y for _, y in ranked[:k]) / k


def split_by_apply_date(records, split):
    resolved = [r for r in records if r.get("is_resolved") and r.get("apply_date")]
    train = [r for r in resolved if r["apply_date"] < split]
    test = [r for r in resolved if r["apply_date"] >= split]
    return train, test


def backtest(records, split, capacity=CAPACITY_PER_DAY, ece_warn=CALIBRATION_ECE_WARN):
    train, test = split_by_apply_date(records, split)
    model = fit_model(train)
    scored = [(score_record(r, model)["risk"], r["is_early_churn"]) for r in test]
    n_test = len(test)
    pred_mean = sum(s for s, _ in scored) / n_test if n_test else 0.0
    actual_mean = sum(y for _, y in scored) / n_test if n_test else 0.0

    # 上位10%のリフト（高リスク上位の実際の解約率 / 全体）
    top_decile_lift = 0.0
    if n_test >= 10 and actual_mean > 0:
        ranked = sorted(scored, key=lambda x: x[0], reverse=True)
        k = max(1, n_test // 10)
        top_rate = sum(y for _, y in ranked[:k]) / k
        top_decile_lift = top_rate / actual_mean

    cal_rows, ece = calibration(scored)
    return {
        "n_train": len(train), "n_test": n_test,
        "pred_mean": pred_mean, "actual_mean": actual_mean,
        "auc": auc(scored), "top_decile_lift": top_decile_lift,
        "calibration": cal_rows, "ece": ece,
        "calibration_warning": ece > ece_warn,
        "precision_at_capacity": precision_at_capacity(scored, capacity),
        "capacity": capacity,
    }
