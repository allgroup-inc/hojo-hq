"""学習：成熟実績から要因別リスク率（スムージング付き）とオッズ比を算出。"""
from __future__ import annotations
import json

from .config import FACTOR_FIELDS, SMOOTHING_K

_EPS = 1e-6


def odds(p):
    p = min(max(p, _EPS), 1 - _EPS)
    return p / (1 - p)


def fit_model(records, factor_fields=FACTOR_FIELDS, smoothing_k=SMOOTHING_K):
    resolved = [r for r in records if r.get("is_resolved")]
    n_resolved = len(resolved)
    n_churn = sum(r["is_early_churn"] for r in resolved)
    base_rate = (n_churn / n_resolved) if n_resolved else 0.0
    base_odds = odds(base_rate)

    factors = {}
    for field in factor_fields:
        buckets = {}
        for r in resolved:
            value = r.get(field, "不明")
            b = buckets.setdefault(value, {"n": 0, "c": 0})
            b["n"] += 1
            b["c"] += r["is_early_churn"]
        field_out = {}
        for value, b in buckets.items():
            # スムージング：観測解約率を全体平均へ smoothing_k 件ぶん引き寄せる
            smoothed = (b["c"] + smoothing_k * base_rate) / (b["n"] + smoothing_k)
            field_out[value] = {
                "n": b["n"],
                "rate": smoothed,
                "odds_ratio": odds(smoothed) / base_odds,
            }
        factors[field] = field_out

    return {
        "base_rate": base_rate,
        "smoothing_k": smoothing_k,
        "n_resolved": n_resolved,
        "temperature": 1.0,
        "factors": factors,
    }


def save_model(model, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(model, f, ensure_ascii=False, indent=2)


def load_model(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)
