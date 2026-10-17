"""顧客IDの仮名化(トークン化)。churn-pii-guard / 仮名化設計に準拠。

別システムの顧客IDを、鍵つきの決定的トークンに置換する。
- 決定的: 同じ顧客ID＋同じ鍵 → 常に同じトークン。だから複数申込みの名寄せ・接触履歴の束ねは不変。
- 一方向: 鍵(secret)を知らなければトークンから顧客IDを復元するのは困難(HMAC-SHA256)。
- 鍵は private/ の外(環境変数 CHURN_TOKEN_SECRET)で管理し、リポジトリにもデータにも置かない。

注意(仮名化設計 §4 ウタガイ): 顧客ID空間が小さい/連番だと総当たりで逆引きされ得る。
また準識別子(年代×地域×商品×担当)の組合せによる再識別は仮名化では消えない。
「トークン化=安全」と誤認せず、出力最小化・公開範囲・アクセス制御を併用すること。
"""
from __future__ import annotations
import hashlib
import hmac
import os

# トークンの長さ(16進の文字数)。衝突が実務上無視できる程度に取る。
_TOKEN_HEX_LEN = 24
_ENV_SECRET = "CHURN_TOKEN_SECRET"


def tokenize(customer_id, secret):
    """顧客IDを決定的トークン(t_<hex>)に変換する。

    customer_id / secret が空なら ValueError(弱い鍵で黙って仮名化しない)。
    """
    if customer_id is None or str(customer_id).strip() == "":
        raise ValueError("customer_id が空です。仮名化できません。")
    if secret is None or str(secret) == "":
        raise ValueError(
            "トークン化の鍵(secret)が空です。弱い鍵では仮名化が無意味になります。"
            f" 環境変数 {_ENV_SECRET} を設定してください。")
    digest = hmac.new(
        str(secret).encode("utf-8"),
        str(customer_id).encode("utf-8"),
        hashlib.sha256).hexdigest()
    return "t_" + digest[:_TOKEN_HEX_LEN]


def load_secret():
    """環境変数から鍵を読む。未設定なら明示エラー(既定値を使わない)。"""
    secret = os.environ.get(_ENV_SECRET, "")
    if not secret:
        raise ValueError(
            f"環境変数 {_ENV_SECRET} が未設定です。仮名化の鍵は private/ の外で管理してください。")
    return secret
