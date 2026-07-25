"""早期解約リスク保全システムの定数・チューニング値。"""

EARLY_CHURN_MONTHS = 6

# 年代ビン
AGE_BANDS = [(0, 19, "〜10代"), (20, 29, "20代"), (30, 39, "30代"),
             (40, 49, "40代"), (50, 59, "50代"), (60, 200, "60代〜")]

# 金額ビンの境界（円）。商品特性に応じて小柳さん決裁で調整可。
AMOUNT_EDGES = [3000, 10000, 30000]
AMOUNT_LABELS = ["〜3千", "3千〜1万", "1万〜3万", "3万〜"]

# リスク要因として使う内部項目
FACTOR_FIELDS = ["product", "channel", "apply_form", "amount_band",
                 "age_band", "gender", "area", "agent_id"]

# 学習のスムージング強度（大きいほど少件数を全体平均へ強く引き寄せる）
SMOOTHING_K = 30
# 「参考値」と注記する最小件数（これ未満は母数不足）
MIN_RELIABLE_N = 20

# リスク帯の閾値（ベース解約率に対する倍率）
BAND_HIGH_MULT = 2.0
BAND_LOW_MULT = 1.0
