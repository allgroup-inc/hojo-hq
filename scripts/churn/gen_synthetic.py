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


def _birth_from_age(rng, age):
    """年齢からそれっぽい生年月日を作る（体裁用。モデルは使わない）。"""
    y = AS_OF.year - age
    return date(y, rng.randint(1, 12), rng.randint(1, 28))


def build_records(rng):
    """内部正規形のレコード群を作る（レイアウト非依存）。"""
    recs = []
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

            p = churn_prob(rng, product, channel, form, amount, age, agent)
            churned = rng.random() < p
            cancel = None
            status = "継続中"
            if churned:
                # 契約から6ヶ月以内のどこかで解約。as-of超なら未観測＝継続中扱い
                cd = contract + timedelta(days=rng.randint(15, 175))
                if cd <= AS_OF:
                    cancel = cd
                    status = "解約"
            # 初回引落結果：継続中かつ直近半年の契約だけ値が入る（古い契約は上書きで消える想定）。
            # 高リスクほど不着/遅延が出やすいよう相関させる（デモ用シグナル）。
            debit = ""
            if cancel is None and contract >= date(2026, 2, 1):
                debit = rng.choice(["不着", "遅延"]) if rng.random() < p * 0.4 else "成功"
            recs.append({
                "customer_id": cid, "apply_id": f"A{apply_id}",
                "product": product, "channel": channel, "form": form,
                "agent": agent, "amount": amount, "age": age,
                "gender": gender, "area": area, "birth": _birth_from_age(rng, age),
                "order_date": order, "contract_date": contract,
                "cancel_date": cancel, "status": status, "debit_result": debit,
                "payment": rng.choice(PAYMENTS), "insurer": rng.choice(INSURERS),
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
            "cancel_date": None, "status": "継続中",
            "debit_result": ("不着" if k in (1, 4) else "遅延" if k == 2 else "成功"),
            "payment": "コンビニ", "insurer": "A生命",
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
            "cancel_date": None, "status": "継続中", "debit_result": "成功",
            "payment": "口座振替", "insurer": "B損保",
        })
    return recs


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
            "年", "月", "日", "市町村", "契：性別", "保険会社", "リスト種類",
            "初回保険料着金日", "初回引落結果"]
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
                "市町村": r["area"], "契：性別": r["gender"],
                "保険会社": r["insurer"], "リスト種類": r["channel"],
                "初回保険料着金日": _d(r["cancel_date"]),
                "初回引落結果": r.get("debit_result", ""),
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
    recs = build_records(rng)
    app_path = os.path.join(out_dir, "apps.csv")
    inter_path = os.path.join(out_dir, "inter.csv")
    if layout == "real":
        write_real(recs, app_path)
    else:
        write_example(recs, app_path)
    n_inter = write_interactions(recs, inter_path, rng)
    print(f"[gen] レイアウト={layout} 申込 {len(recs)}件 / 接触 {n_inter}件 "
          f"→ {app_path} / {inter_path}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--layout", choices=["example", "real"], default="real")
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()
    gen(a.out_dir, a.seed, a.layout)


if __name__ == "__main__":
    main()
