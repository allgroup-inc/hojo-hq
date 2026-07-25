"""採点：モデルのオッズ比を合成してリスク%・帯・ヒット要因を返す。"""
from __future__ import annotations
import math

from .config import (BAND_HIGH_MULT, BAND_LOW_MULT, FACTOR_FIELDS, MIN_RELIABLE_N,
                     HIGH_CUTOFF_CEILING)
from .fit import odds


def band_of(risk, base_rate):
    high_cut = min(BAND_HIGH_MULT * base_rate, HIGH_CUTOFF_CEILING)
    if risk >= high_cut:
        return "high"
    if risk <= BAND_LOW_MULT * base_rate:
        return "low"
    return "med"


def display_pct(risk):
    """表示用%は 0.1〜99.0 に丸め込む。断定表現（0% / 100%）を避けるため。
    内部の risk（バックテスト・キャリブレーションで使う生値）はここでは変えない。"""
    return round(min(max(risk, 0.001), 0.99) * 100, 1)


def score_record(record, model, factor_fields=FACTOR_FIELDS):
    base_rate = model["base_rate"]
    temperature = model.get("temperature", 1.0)
    log_odds = math.log(odds(base_rate))
    contributions = []

    for field in factor_fields:
        value = record.get(field, "不明")
        entry = model["factors"].get(field, {}).get(value)
        if not entry:
            continue  # 未知の値は寄与なし（ベースのまま）
        or_v = entry["odds_ratio"]
        log_odds += temperature * math.log(or_v)
        contributions.append({
            "field": field, "value": value, "odds_ratio": or_v,
            "direction": "up" if or_v > 1 else "down",
            "n": entry["n"], "reference": entry["n"] < MIN_RELIABLE_N,
        })

    combined_odds = math.exp(log_odds)
    risk = combined_odds / (1 + combined_odds)
    contributions.sort(key=lambda c: abs(math.log(c["odds_ratio"])), reverse=True)

    return {
        "risk": risk,
        "band": band_of(risk, base_rate),
        "base_rate": base_rate,
        "hit_factors": contributions[:3],
    }
