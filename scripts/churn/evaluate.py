"""バックテスト：過去の一時点で採点したら当たったかを検証する品質ゲート。"""
from __future__ import annotations

from .fit import fit_model
from .score import score_record


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


def split_by_apply_date(records, split):
    resolved = [r for r in records if r.get("is_resolved") and r.get("apply_date")]
    train = [r for r in resolved if r["apply_date"] < split]
    test = [r for r in resolved if r["apply_date"] >= split]
    return train, test


def backtest(records, split):
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

    return {
        "n_train": len(train), "n_test": n_test,
        "pred_mean": pred_mean, "actual_mean": actual_mean,
        "auc": auc(scored), "top_decile_lift": top_decile_lift,
    }
