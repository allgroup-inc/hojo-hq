"""合成データ生成器（デモ・検証用の偽データ）。

本物の顧客個人情報は一切使わない。氏名・連絡先も生成しない（システムは顧客IDで扱う）。
出力は private/ 配下に置く前提。実データではないため守り部審査の対象外だが、
公開リポジトリへコミットしないハイジーンとして private/ に出す。

--layout で列レイアウトを切り替える:
  example : docs/churn/column_map.example.json と同じ列名
  real    : 実エクセル（0804最新VER）と同じ列名。契約日=開始日 / 初回保険料着金日=解約日。
            解約した人だけ「初回保険料着金日」に日付が入り、継続中は空欄。

使い方:
  python -m scripts.churn.gen_synthetic --out-dir private/demo --layout real --seed 42
"""
from __future__ import annotations
import argparse
import csv
import os
import random
from datetime import date, timedelta

AS_OF = date(2026, 8, 1)

# 生成する内部の値プール（保険ドメイン寄り）
PRODUCTS = ["医療", "がん", "終身", "学資", "収入保障", "医療女性"]
CHANNELS = ["反響", "紹介", "名簿", "催事", "WEB"]        # リスト種類＝集客チャネル
FORMS = ["対面", "郵送", "WEB", "電話"]                    # 申込方法＝申込形態
PAYMENTS = ["口座振替", "クレジット", "コンビニ"]          # 払込経路（モデル未使用・体裁用）
INSURERS = ["A生命", "B損保", "C生命", "D医療"]            # 保険会社（モデル未使用・体裁用）
GENDERS = ["男性", "女性"]
AREAS = ["那覇市", "沖縄市", "浦添市", "うるま市", "宜野湾市",
         "名護市", "豊見城市", "糸満市", "石垣市", "宮古島市"]
AGENTS = ["OK-01", "OK-02", "OK-03", "OK-04", "OK-05", "OK-06", "OK-07"]
KINDS = ["架電", "案内", "追加案内", "来店", "メール", "面談"]

# 早期解約リスクに仕込むシグナル（加算オフセット）。fitがこれを学習し、
# backtestのAUCが0.5から有意に離れることを狙う。
CHANNEL_W = {"名簿": 0.14, "WEB": 0.10, "催事": 0.03, "反響": -0.02, "紹介": -0.08}
FORM_W = {"電話": 0.10, "WEB": 0.06, "郵送": 0.0, "対面": -0.07}
PRODUCT_W = {"医療女性": 0.06, "がん": 0.04, "医療": 0.02,
             "収入保障": 0.0, "終身": -0.03, "学資": -0.07}
AGENT_W = {"OK-07": 0.13, "OK-06": 0.04, "OK-01": -0.06}
# 未収回数（Ⅳ列）の早期解約への効き。繰り返し未収ほど高リスク＝unpaid_band factorの検証用シグナル。
UNPAID_W = {0: -0.03, 1: 0.06, 2: 0.16, 3: 0.26}
_CIRCLED = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫"


def _iv_string(rng, unpaid_count, as_of, account_issue, relapse=False):
    """Ⅳ列（口座振替の未収履歴）を合成。未<年>+○囲み月＋●/済/★。未収0なら空。

    直近で「引落が終わった月」= as_of.month-1 から遡る（当月はまだ引落未到来）。年跨ぎは
    年ごとに 未<yy> を出し直す（parse_unpaid / _recent_streak と整合させ、連鎖判定を正しく発火させる）。
    relapse=True のとき、解消のギャップ(1ヶ月)をはさんで**さらに古い月**に1回の未収を足す＝再発履歴。
    """
    if unpaid_count <= 0:
        return ""
    s = ("●" if rng.random() < 0.5 else "") + ("済" if rng.random() < 0.6 else "")
    y, m = as_of.year, as_of.month
    last_year = None
    for k in range(1, unpaid_count + 1):   # as_of.month-1 から遡る
        mm, yy = m - k, y
        while mm <= 0:
            mm += 12
            yy -= 1
        if yy != last_year:
            s += "未" + f"{yy % 100:02d}"
            last_year = yy
        s += _CIRCLED[mm - 1]
    if relapse:
        # 直近ブロックの1ヶ月手前(=解消)をはさんだ、さらに古い月に単発の未収（再発の履歴）。
        mm, yy = m - (unpaid_count + 2), y
        while mm <= 0:
            mm += 12
            yy -= 1
        s += "未" + f"{yy % 100:02d}" + _CIRCLED[mm - 1]   # 年prefixを必ず出し文脈を確定
        last_year = yy
    if account_issue:
        s += "★"
    return s


def churn_prob(rng, product, channel, form, amount, age, agent):
    p = 0.12
    p += CHANNEL_W.get(channel, 0.0)
    p += FORM_W.get(form, 0.0)
    p += PRODUCT_W.get(product, 0.0)
    p += AGENT_W.get(agent, 0.0)
    if amount < 3000:
        p += 0.09
    elif amount >= 30000:
        p += -0.04
    if 20 <= age <= 29:
        p += 0.06
    elif age >= 60:
        p += -0.05
    p += rng.uniform(-0.03, 0.03)  # 個体ノイズ
    return min(max(p, 0.02), 0.85)


def rand_date(rng, start, end):
    span = (end - start).days
    return start + timedelta(days=rng.randint(0, span))


# 解約が集中する日数の山（中心, ばらつき, 重み）。初回引落≈33/2回目≈63/3回目≈93/6ヶ月の壁≈162日。
# 「第2の山」を合成データで見せるための仕込み（実データではなく体裁）。
_CHURN_PEAKS = [(33, 6, 45), (63, 6, 22), (93, 6, 13), (162, 7, 20)]


def _churn_day(rng):
    """解約までの日数を、引落サイクル・6ヶ月の壁に山を持つ混合分布から引く（15〜175にクランプ）。"""
    i = rng.choices(range(len(_CHURN_PEAKS)), weights=[w for *_, w in _CHURN_PEAKS])[0]
    center, sd, _ = _CHURN_PEAKS[i]
    return max(15, min(175, int(round(rng.gauss(center, sd)))))


def _birth_from_age(rng, age):
    """年齢からそれっぽい生年月日を作る（体裁用。モデルは使わない）。"""
    y = AS_OF.year - age
    return date(y, rng.randint(1, 12), rng.randint(1, 28))


# 保全アクションと、その"効き"（早期解約率をどれだけ下げるか）のデモ用シグナル。
# 学習デモで「効いた一手」を再現するため。実データではなく合成の仕込み。
ACT_EFFECT = {"減額提案": 0.12, "口座確認": 0.12, "再説明": 0.06, "給付案内": 0.03, "安心コール": 0.02}

# 対話ログ（訪問保全）のデモ用シグナル。教育ループ（dialog/talkscript）を合成データで実演するため。
# 懸念（顧客の不安）＝セグメント。返し方（対話の型）＝早期解約率への効き（乗算係数）。実データではなく合成の仕込み。
# 係数は解約確率への倍率（<1で抑止、1.0で無効=様子見）。小標本でも順位が学習で復元できるよう強めに分離。
CONCERNS = ["保険料負担", "必要性の疑問", "家計不安", "商品理解", "手続き不明"]
APPROACH_FACTOR = {"家計の見直し提案": 0.35, "減額の提示": 0.50, "再説明・納得": 0.75,
                   "給付事例の紹介": 1.10, "様子見": 1.60}
# 懸念ごとに特に効く返し方（マッチで追加の抑止）。教育カード「この懸念にはこの返し方」の仕込み。
CONCERN_MATCH_FACTOR = 0.55
CONCERN_BEST = {"保険料負担": "家計の見直し提案", "必要性の疑問": "給付事例の紹介",
                "家計不安": "減額の提示", "商品理解": "再説明・納得", "手続き不明": "再説明・納得"}


def build_records(rng):
    """内部正規形のレコード群＋保全アクションログを作る（レイアウト非依存）。"""
    recs = []
    actions = []  # 保全アクションログ（結果記録）: 顧客ID・契約日・接触日・対応内容・結果区分・顧客反応
    apply_id = 1000

    n_customers = 460
    for ci in range(1, n_customers + 1):
        cid = f"C{ci:04d}"
        age = rng.choice([24, 27, 31, 35, 38, 42, 47, 53, 58, 63, 68])
        gender = rng.choice(GENDERS)
        area = rng.choice(AREAS)
        n_apps = rng.choices([1, 2, 3], weights=[70, 22, 8])[0]
        for _ in range(n_apps):
            apply_id += 1
            product = rng.choice(PRODUCTS)
            channel = rng.choice(CHANNELS)
            form = rng.choice(FORMS)
            agent = rng.choice(AGENTS)
            amount = rng.choice([1500, 2000, 3000, 5000, 8000, 12000, 20000, 35000])
            contract = rand_date(rng, date(2024, 7, 1), date(2026, 7, 20))
            order = contract - timedelta(days=rng.randint(1, 20))

            # 払込経路と未収履歴（Ⅳ）。未収は口座振替のみ。繰り返し未収ほど高リスク。
            payment = rng.choices(["口座振替", "クレジットカード", "コンビニ"], weights=[70, 22, 8])[0]
            unpaid_count = (rng.choices([0, 1, 2, 3], weights=[68, 15, 10, 7])[0]
                            if payment == "口座振替" else 0)
            account_issue = payment == "口座振替" and unpaid_count > 0 and rng.random() < 0.3
            # 再発（A3）: 一度解消した後また未収に戻った履歴を一部に仕込む（口座振替・未収ありの35%）
            relapse = payment == "口座振替" and unpaid_count >= 1 and rng.random() < 0.35

            p = churn_prob(rng, product, channel, form, amount, age, agent)
            p += UNPAID_W[min(unpaid_count, 3)]
            # 保全アクション（結果記録）: 4割の契約に保全接触。対応内容（加算）＋返し方（乗算）で早期解約率が下がる（デモ用の効き）。
            contacted = rng.random() < 0.4
            action = rng.choice(list(ACT_EFFECT)) if contacted else None
            concern = rng.choice(CONCERNS) if contacted else None
            # 返し方は懸念に応じて熟練担当が寄せる（現場は既にある程度テーラリング）。
            # 「効いた型」の実績が matched セルに集まり、教育カードが復元できるようにする仕込み。
            approach = None
            if contacted:
                best = CONCERN_BEST[concern]
                others = [a for a in APPROACH_FACTOR if a != best]
                approach = (best if rng.random() < 0.45
                            else rng.choice(others))
            medium = rng.choices(["架電", "訪問"], weights=[85, 15])[0] if contacted else None
            p_after_act = max(p - (ACT_EFFECT[action] if contacted else 0.0), 0.02)
            factor = (APPROACH_FACTOR[approach]
                      * (CONCERN_MATCH_FACTOR if CONCERN_BEST[concern] == approach else 1.0)
                      ) if contacted else 1.0
            p_adj = min(p_after_act * factor, 0.90)
            churned = rng.random() < p_adj
            cancel = None
            status = "成立済"   # 継続（現ステータス実値）
            if churned:
                # 契約から6ヶ月以内で解約。初回/2回目/3回目引落・6ヶ月の壁に山ができる（第2の山のデモ用）
                cd = contract + timedelta(days=_churn_day(rng))
                if cd <= AS_OF:
                    cancel = cd
                    if payment == "口座振替" and unpaid_count >= 2:
                        status = rng.choice(["未払消滅", "不成立【引受後未入金】"])  # 未収起因
                    else:
                        status = "成立後CAN【解約】"  # 自発解約
            if contacted:
                # 接触日: 契約後3〜45日。解約より前（免疫時間バイアスを避ける）。未来の接触は記録しない
                contact_day = contract + timedelta(days=rng.randint(3, 45))
                if cancel is not None and contact_day >= cancel:
                    contact_day = cancel - timedelta(days=rng.randint(2, 6))
                if contact_day < contract:
                    contact_day = contract + timedelta(days=1)
                if contact_day <= AS_OF:
                    reaction = rng.choices(["継続", "検討中", "解約意向"],
                                           weights=([30, 30, 40] if churned else [60, 30, 10]))[0]
                    next_action = rng.choice(["再訪問", "架電フォロー", "様子見", "完了"])
                    actions.append({"顧客ID": cid, "契約日": contract.isoformat(),
                                    "接触日": contact_day.isoformat(), "対応内容": action,
                                    "接触手段": medium, "懸念": concern, "返し方": approach,
                                    "次アクション": next_action,
                                    "結果区分": "つながった", "顧客反応": reaction})
            # 初回引落結果・口座普段使い・引落予定日：継続中かつ直近半年の契約だけ値が入る
            # （古い契約は上書きで消える想定）。高リスクほど不着/遅延・口座問題が出やすい（デモ用シグナル）。
            debit = ""
            account = ""
            due = ""
            if cancel is None and contract >= date(2026, 2, 1):
                account = rng.choice(["いいえ", "未確認"]) if rng.random() < p else "はい"
                due_d = contract + timedelta(days=rng.randint(28, 33))
                due = due_d.isoformat()
                if due_d <= AS_OF:  # 引落済み → 結果が入る（B: 支払い挙動ウォッチ）
                    debit = rng.choice(["不着", "遅延"]) if rng.random() < p * 0.4 else "成功"
                # else: 引落予定日が未来 → 結果なし＝引落前（A: 口座確認トリガーの対象）
            recs.append({
                "customer_id": cid, "apply_id": f"A{apply_id}",
                "product": product, "channel": channel, "form": form,
                "agent": agent, "amount": amount, "age": age,
                "gender": gender, "area": area, "birth": _birth_from_age(rng, age),
                "order_date": order, "contract_date": contract,
                "cancel_date": cancel, "status": status, "debit_result": debit,
                "account_daily": account, "debit_due": due,
                "payment": payment, "insurer": rng.choice(INSURERS),
                "iv": _iv_string(rng, unpaid_count, AS_OF, account_issue, relapse),
            })

    # 放置検知(要フォロー)デモ：高リスク条件・継続中・接触なしを固定注入
    for k in range(1, 6):
        apply_id += 1
        contract = date(2026, 5, 10) + timedelta(days=k * 3)
        recs.append({
            "customer_id": f"C9{k:03d}", "apply_id": f"A{apply_id}",
            "product": "医療女性", "channel": "名簿", "form": "電話",
            "agent": "OK-07", "amount": 1500, "age": 26,
            "gender": rng.choice(GENDERS), "area": rng.choice(AREAS),
            "birth": _birth_from_age(rng, 26),
            "order_date": contract - timedelta(days=5), "contract_date": contract,
            "cancel_date": None, "status": "成立済",
            "debit_result": ("不着" if k in (1, 4) else "遅延" if k == 2 else "成功"),
            "account_daily": "いいえ",
            "debit_due": (contract + timedelta(days=30)).isoformat(),
            "payment": "口座振替", "insurer": "A生命",
            "iv": _iv_string(rng, 2 if k in (1, 4) else 1, AS_OF, k == 1),
        })

    # 対象外・母集団外デモ（率の分母から除外＋件数併記を見せる）
    for st in ("死亡解約", "契約取り消し【成立後】", "取消・解除【成立後】", "謝絶", "PL申込【送信前】"):
        apply_id += 1
        recs.append({
            "customer_id": f"C8{apply_id % 1000:03d}", "apply_id": f"A{apply_id}",
            "product": "医療", "channel": "紹介", "form": "対面",
            "agent": "OK-02", "amount": 3000, "age": 40,
            "gender": rng.choice(GENDERS), "area": rng.choice(AREAS),
            "birth": _birth_from_age(rng, 40),
            "order_date": date(2025, 1, 5), "contract_date": date(2025, 1, 10),
            "cancel_date": (date(2025, 3, 1) if "取" in st or "解" in st or "死" in st else None),
            "status": st, "debit_result": "", "account_daily": "はい",
            "debit_due": "", "payment": "口座振替", "insurer": "B損保", "iv": "",
        })

    # 未紐付(顧客ID欠損)デモ：黙って母集団から消さないことを示す
    for _ in range(3):
        apply_id += 1
        recs.append({
            "customer_id": "", "apply_id": f"A{apply_id}",
            "product": "医療", "channel": "WEB", "form": "WEB",
            "agent": "OK-03", "amount": 3000, "age": 30,
            "gender": "男性", "area": "那覇市", "birth": _birth_from_age(rng, 30),
            "order_date": date(2026, 6, 10), "contract_date": date(2026, 6, 15),
            "cancel_date": None, "status": "成立済", "debit_result": "成功",
            "account_daily": "はい", "debit_due": "2026-07-15",
            "payment": "口座振替", "insurer": "B損保", "iv": "",
        })
    return recs, actions


def _d(v):
    return v.isoformat() if v else ""


def write_example(recs, path):
    cols = ["顧客ID", "申込ID", "申込日", "商品", "集客チャネル", "申込形態",
            "金額", "年齢", "性別", "地域", "営業担当", "解約日", "解約理由"]
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in recs:
            w.writerow({
                "顧客ID": r["customer_id"], "申込ID": r["apply_id"],
                "申込日": _d(r["contract_date"]), "商品": r["product"],
                "集客チャネル": r["channel"], "申込形態": r["form"],
                "金額": r["amount"], "年齢": r["age"], "性別": r["gender"],
                "地域": r["area"], "営業担当": r["agent"],
                "解約日": _d(r["cancel_date"]),
                "解約理由": "保険料負担" if r["cancel_date"] else "",
            })


def write_real(recs, path):
    """実エクセル（0804最新VER）と同じ列名で書き出す。
    契約日=開始日 / 初回保険料着金日=解約日（継続中は空欄）。"""
    cols = ["営業担当者", "顧客ID", "現ステータス", "受注日", "契約日", "生年月日",
            "年齢", "住所　県", "申し込み商品", "保険料￥", "払込経路", "申込方法",
            "年", "月", "日", "市町村", "Ⅳ", "契：性別", "保険会社", "リスト種類",
            "初回保険料着金日", "初回引落結果", "口座普段使い", "引落予定日"]
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in recs:
            c = r["contract_date"]
            w.writerow({
                "営業担当者": r["agent"], "顧客ID": r["customer_id"],
                "現ステータス": r["status"], "受注日": _d(r["order_date"]),
                "契約日": _d(c), "生年月日": _d(r["birth"]), "年齢": r["age"],
                "住所　県": "沖縄県", "申し込み商品": r["product"],
                "保険料￥": r["amount"], "払込経路": r["payment"],
                "申込方法": r["form"],
                "年": c.year, "月": c.month, "日": c.day,
                "市町村": r["area"], "Ⅳ": r.get("iv", ""),
                "契：性別": r["gender"],
                "保険会社": r["insurer"], "リスト種類": r["channel"],
                "初回保険料着金日": _d(r["cancel_date"]),
                "初回引落結果": r.get("debit_result", ""),
                "口座普段使い": r.get("account_daily", ""),
                "引落予定日": r.get("debit_due", ""),
            })


def write_interactions(recs, path, rng):
    """接触履歴（別台帳想定）。継続中の顧客に0〜4件。一部はわざと直近接触なし。"""
    by_cust = {}
    for r in recs:
        if r["customer_id"]:
            by_cust.setdefault(r["customer_id"], []).append(r)
    rows = []
    for cid, apps in by_cust.items():
        if cid.startswith("C9"):
            continue  # 要フォロー注入分は接触なしのまま
        last = max(a["contract_date"] for a in apps)
        n = rng.choices([0, 1, 2, 3, 4], weights=[25, 25, 25, 15, 10])[0]
        for _ in range(n):
            rows.append({
                "顧客ID": cid, "接触日": _d(rand_date(rng, last, AS_OF)),
                "種別": rng.choice(KINDS), "担当": rng.choice(AGENTS),
                "案内内容": rng.choice(["継続確認", "追加提案", "見直し相談", "定期連絡"]),
                "メモ": "",
            })
    rows.append({"顧客ID": "", "接触日": "2026-06-20", "種別": "架電",
                 "担当": "OK-03", "案内内容": "定期連絡", "メモ": ""})
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["顧客ID", "接触日", "種別", "担当", "案内内容", "メモ"])
        w.writeheader()
        w.writerows(rows)
    return len(rows)


def gen(out_dir, seed, layout):
    rng = random.Random(seed)
    os.makedirs(out_dir, exist_ok=True)
    recs, actions = build_records(rng)
    app_path = os.path.join(out_dir, "apps.csv")
    inter_path = os.path.join(out_dir, "inter.csv")
    act_path = os.path.join(out_dir, "actions.csv")
    if layout == "real":
        write_real(recs, app_path)
    else:
        write_example(recs, app_path)
    n_inter = write_interactions(recs, inter_path, rng)
    with open(act_path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["顧客ID", "契約日", "接触日", "対応内容", "接触手段",
                                          "懸念", "返し方", "次アクション", "結果区分", "顧客反応"])
        w.writeheader()
        w.writerows(actions)
    print(f"[gen] レイアウト={layout} 申込 {len(recs)}件 / 接触 {n_inter}件 / "
          f"保全ログ {len(actions)}件 → {app_path} / {inter_path} / {act_path}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--layout", choices=["example", "real"], default="real")
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()
    gen(a.out_dir, a.seed, a.layout)


if __name__ == "__main__":
    main()
