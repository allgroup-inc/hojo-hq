"""Ⅳ列（口座振替の未収履歴）パーサ（徳元さん確定 2026-08-17）。

Ⅳは1セルに複数月の未収を詰めた複合コード。記法:
- 未 = 未収（ラベル）
- ASCII2桁 26/25 = 年（2026/2025）。以降の月に適用。
- ○囲み数字 ①〜⑫ = 月
- ● = コンビニ用紙を発送 / 済 = 未収案内で話した（接触） / ★ = 口座不備・口座設定間に合わず

抽出: 未収月の**distinct集合**（重複計上を避ける）＝unpaid_count（繰り返し未収＝高リスクの予測因子）、
接触済み(済)・コンビニ発送(●)・口座不備(★)のフラグ。未知トークンは parse_ok=False で監査に残し、
拾える分は拾う（全読込を止めない）。docs/churn/現ステータス分類ルール.md / データ仕様_未収と初回引落.md。
"""
from __future__ import annotations

# ○囲み数字 ①(U+2460)〜⑳(U+2473)
_CIRCLED = {chr(0x2460 + i): i + 1 for i in range(20)}
_MARKERS = {"未", "済", "●", "★", "/", "／", " ", "　", "・", ",", "，"}


def parse_unpaid(cell):
    """Ⅳセル → 未収の集計とフラグ。"""
    s = "" if cell is None else str(cell)
    out = {"unpaid_count": 0, "unpaid_months": [],
           "contacted": "済" in s, "konbini_sent": "●" in s, "account_issue": "★" in s,
           "parse_ok": True}
    months = set()
    cur_year = None
    i, n = 0, len(s)
    while i < n:
        c = s[i]
        if c.isascii() and c.isdigit():
            j = i
            while j < n and s[j].isascii() and s[j].isdigit():
                j += 1
            digits = s[i:j]
            if len(digits) == 2:
                cur_year = 2000 + int(digits)
            else:
                out["parse_ok"] = False   # 想定外の桁数
            i = j
            continue
        if c in _CIRCLED:
            m = _CIRCLED[c]
            if 1 <= m <= 12:
                months.add((cur_year, m))
            else:
                out["parse_ok"] = False   # 月として不正（⑬以上）
            i += 1
            continue
        if c not in _MARKERS:
            out["parse_ok"] = False        # 未知トークン（監査に残す）
        i += 1
    out["unpaid_months"] = sorted(months, key=lambda t: (t[0] or 0, t[1]))
    out["unpaid_count"] = len(months)
    return out


def bin_unpaid_count(count):
    """未収回数をビン化（要因用）。0 / 1 / 2+。"""
    if count <= 0:
        return "0"
    if count == 1:
        return "1"
    return "2+"
