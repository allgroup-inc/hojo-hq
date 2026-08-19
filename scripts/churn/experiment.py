"""因果効果測定（段階導入・対照群・アップリフト）。

「保全アクションが本当に早期解約を減らすか」を、単純比較（生存者バイアスあり）ではなく
**対照群比較**で測る。保全対象を先行群/後発群に決定的に割り付け（顧客IDのhash・実行間で不変・
無作為）、群間の早期解約率差を信頼区間つきで出す。**全員がいずれ保全を受ける段階導入**の台帳
として使えば、「後発群に一時的に保全しない」ことで因果を測りつつ、放置には至らせない。

規律（churn-retention-ops / churn-model-quality-gate）:
- 符号は diff = 対照(後発) − 介入(先行)。**正＝保全が早期解約を減らした**。
- 母数不足（min(n) < MIN_RELIABLE_N）は reference=True で「参考」。断定しない。
- 区間が0を跨ぐなら「効果あり」と言い切らない（下限>0で初めて有意に減少）。
- 単純比較（effect_learning.effect）と並置し、**結論には対照群比較(uplift)を使う**。

割付は乱数を使わず純関数（hash）。実行のたびにブレると段階導入の台帳が壊れるため。
ウェーブ（salt）を変えれば次の実験で割付を組み替えられる。
"""
from __future__ import annotations
import hashlib
import math

from .config import EXPERIMENT_TREATED_FRACTION, MIN_RELIABLE_N
from .effect_learning import effect


def _uniform(customer_id, salt=""):
    """顧客IDから決定的な一様値[0,1)。乱数を使わない（実行間で不変）。"""
    h = hashlib.sha256(f"{salt}|{customer_id}".encode("utf-8")).hexdigest()
    return int(h[:16], 16) / 16 ** 16


def assign_arm(customer_id, treated_fraction=EXPERIMENT_TREATED_FRACTION, salt=""):
    """先行（介入＝保全を先に受ける）/ 後発（対照）に決定的に割り付ける。"""
    return "先行" if _uniform(customer_id, salt) < treated_fraction else "後発"


def assignment_ledger(customer_ids, treated_fraction=EXPERIMENT_TREATED_FRACTION, salt=""):
    """段階導入の台帳：各群の件数。"""
    led = {"先行": 0, "後発": 0}
    for cid in customer_ids:
        led[assign_arm(cid, treated_fraction, salt)] += 1
    led["total"] = led["先行"] + led["後発"]
    return led


def wilson_interval(k, n, z=1.96):
    """二項割合のWilsonスコア信頼区間。n=0は(0,0)。"""
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    center = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, center - half), min(1.0, center + half))


def _rate(recs):
    k = sum(r.get("is_early_churn") or 0 for r in recs)
    return k, len(recs)


def uplift(records, treated_fraction=EXPERIMENT_TREATED_FRACTION, salt="",
           min_reliable=MIN_RELIABLE_N, z=1.96):
    """先行/後発の早期解約率差を区間推定（Newcombe法・Wilson由来）。

    diff = 対照(後発) − 介入(先行)。正＝保全が早期解約を減らした。
    成熟実績（is_resolved）のみを対象にする。
    """
    resolved = [r for r in records if r.get("is_resolved")]
    treat = [r for r in resolved if assign_arm(r.get("customer_id"), treated_fraction, salt) == "先行"]
    ctrl = [r for r in resolved if assign_arm(r.get("customer_id"), treated_fraction, salt) == "後発"]

    k_t, n_t = _rate(treat)
    k_c, n_c = _rate(ctrl)
    p_t = k_t / n_t if n_t else 0.0
    p_c = k_c / n_c if n_c else 0.0
    l_t, u_t = wilson_interval(k_t, n_t, z)
    l_c, u_c = wilson_interval(k_c, n_c, z)

    diff = p_c - p_t
    # Newcombe(方法10): Wilson区間から差の信頼区間を組む
    lower = diff - math.sqrt((p_c - l_c) ** 2 + (u_t - p_t) ** 2)
    upper = diff + math.sqrt((u_c - p_c) ** 2 + (p_t - l_t) ** 2)

    return {
        "n_treat": n_t, "rate_treat": p_t, "ci_treat": (l_t, u_t),
        "n_ctrl": n_c, "rate_ctrl": p_c, "ci_ctrl": (l_c, u_c),
        "diff": diff, "diff_ci": (lower, upper),
        "reference": min(n_t, n_c) < min_reliable,
    }


def max_consecutive_streak(unpaid_months):
    """未収月 (年, 月) の集合から、最長の連続月数を返す（年跨ぎ対応・重複除去）。

    未払消滅は「4ヶ月連続未払」で起きる。ある契約が過去に何ヶ月連続で未収だったかを、
    A1（未払消滅目前の保全）の対象抽出に使う。"""
    if not unpaid_months:
        return 0
    ordinals = sorted({y * 12 + (m - 1) for (y, m) in unpaid_months})
    best = run = 1
    for prev, cur in zip(ordinals, ordinals[1:]):
        run = run + 1 if cur == prev + 1 else 1
        best = max(best, run)
    return best


def imminent_lapse_uplift(records, min_streak=3, treated_fraction=EXPERIMENT_TREATED_FRACTION,
                          salt="", min_reliable=MIN_RELIABLE_N):
    """A1（未払消滅の根絶）の効果測定。

    最長未収連続 >= min_streak（＝未払消滅目前を経験した）契約だけを対象に、先行/後発の
    早期解約率差を uplift で測る。**割付でランダム化するため因果**（生存者バイアスなし）。
    合成データには A1 の介入（手続き支援）が仕込まれていないので diff≒0＝「効果なし/参考」が正しい。
    実データで先行群に手続き支援を当てて初めて差が出る、という読み方をする。"""
    target = [r for r in records
              if max_consecutive_streak(r.get("unpaid_months") or []) >= min_streak]
    out = uplift(target, treated_fraction, salt, min_reliable)
    out["n_target"] = len(target)
    return out


def relapse_uplift(records, treated_fraction=EXPERIMENT_TREATED_FRACTION,
                   salt="", min_reliable=MIN_RELIABLE_N):
    """決定1（再発監視の効果検証）。

    再発履歴（未収エピソード≥2＝解消をはさんで再び未収）を持つ契約だけを対象に、先行/後発の
    早期解約率差を uplift で測る。割付ランダム化で因果。**優先度順への組込みは、ここで効果が
    確認できてから**（決定ブリーフ 決定1）。合成データには再発への介入が仕込まれていないので
    diff≒0＝「効果なし/参考」が正しい。"""
    from .relapse import unpaid_episodes
    target = [r for r in records
              if len(unpaid_episodes(r.get("unpaid_months") or [])) >= 2]
    out = uplift(target, treated_fraction, salt, min_reliable)
    out["n_target"] = len(target)
    return out


def compare_naive_vs_controlled(records, contacts, mature_before,
                                treated_fraction=EXPERIMENT_TREATED_FRACTION, salt="",
                                min_reliable=MIN_RELIABLE_N):
    """単純比較（接触あり/なし・生存者バイアスあり）と対照群比較（先行/後発）を並置。

    **結論には controlled（対照群）を使う**。naive は参考（バイアスの向きを見るため）。
    """
    naive = effect(records, contacts, mature_before, min_reliable)   # 生存者バイアスが残る
    controlled = uplift(records, treated_fraction, salt, min_reliable)
    return {
        "naive": naive,            # 参考：接触あり−なし（因果ではない）
        "controlled": controlled,  # 結論：後発−先行（対照群）
        "conclusion_uses": "controlled",
    }
