"""合成データ生成器（デモ・検証用の偽データ）。

本物の顧客個人情報は一切使わない。氏名・連絡先も生成しない（システムは顧客IDで扱う）。
出力は private/ 配下に置く前提。実データではないため守り部審査の対象外だが、
公開リポジトリへコミットしないハイジーンとして private/ に出す。

使い方:
  python -m scripts.churn.gen_synthetic --out-dir private/demo --seed 42
"""
from __future__ import annotations
import argparse
import csv
import os
import random
from datetime import date, timedelta

AS_OF = date(2026, 8, 1)

PRODUCTS = ["医療", "がん", "学資", "終身", "自動車", "火災"]
CHANNELS = ["ネット", "折込", "来店", "紹介", "催事"]
FORMS = ["単発", "継続", "WEB完結", "対面"]
GENDERS = ["男性", "女性"]
AREAS = ["那覇", "沖縄市", "浦添", "うるま", "宜野湾", "名護", "豊見城", "糸満", "石垣", "宮古島"]
AGENTS = ["OK-01", "OK-02", "OK-03", "OK-04", "OK-05", "OK-06", "OK-07"]

# 早期解約リスクに仕込むシグナル（加算オフセット）。fitがこれを学習し、
# backtestのAUCが0.5から有意に離れることを狙う。
CHANNEL_W = {"ネット": 0.16, "折込": 0.05, "催事": 0.0, "来店": -0.05, "紹介": -0.07}
FORM_W = {"単発": 0.13, "WEB完結": 0.04, "対面": -0.02, "継続": -0.06}
PRODUCT_W = {"医療": 0.07, "がん": 0.04, "火災": 0.0, "自動車": 0.0, "終身": -0.03, "学資": -0.07}
AGENT_W = {"OK-07": 0.13, "OK-06": 0.04, "OK-01": -0.06}
KINDS = ["架電", "案内", "追加案内", "来店", "メール", "面談"]


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


def gen(out_dir, seed):
    rng = random.Random(seed)
    os.makedirs(out_dir, exist_ok=True)
    apps = []
    inters = []
    apply_id = 1000

    n_customers = 460
    for ci in range(1, n_customers + 1):
        cid = f"C{ci:04d}"
        # 顧客属性は固定（年代・性別・地域）
        age = rng.choice([24, 27, 31, 35, 38, 42, 47, 53, 58, 63, 68])
        gender = rng.choice(GENDERS)
        area = rng.choice(AREAS)
        n_apps = rng.choices([1, 2, 3], weights=[70, 22, 8])[0]

        cust_apps = []
        for _ in range(n_apps):
            apply_id += 1
            product = rng.choice(PRODUCTS)
            channel = rng.choice(CHANNELS)
            form = rng.choice(FORMS)
            agent = rng.choice(AGENTS)
            amount = rng.choice([2000, 3500, 5000, 8000, 12000, 20000, 35000, 50000])
            apply_date = rand_date(rng, date(2024, 7, 1), date(2026, 7, 20))

            p = churn_prob(rng, product, channel, form, amount, age, agent)
            churned = rng.random() < p
            cancel_date = ""
            cancel_reason = ""
            if churned:
                # 6ヶ月以内のどこかで解約（早期解約）。as-of超なら未観測＝継続中扱い
                cd = apply_date + timedelta(days=rng.randint(15, 175))
                if cd <= AS_OF:
                    cancel_date = cd.isoformat()
                    cancel_reason = rng.choice(
                        ["保険料負担", "他社乗換", "説明不足", "家計見直し", "担当変更希望"])
            row = {
                "顧客ID": cid, "申込ID": f"A{apply_id}",
                "申込日": apply_date.isoformat(), "商品": product,
                "集客チャネル": channel, "申込形態": form, "金額": amount,
                "年齢": age, "性別": gender, "地域": area, "営業担当": agent,
                "解約日": cancel_date, "解約理由": cancel_reason,
            }
            apps.append(row)
            cust_apps.append((apply_date, cancel_date))

        # 接触履歴：継続中の顧客に0〜4件。高リスク狙いの一部はわざと直近接触なし
        last_apply = max(d for d, _ in cust_apps)
        n_inter = rng.choices([0, 1, 2, 3, 4], weights=[25, 25, 25, 15, 10])[0]
        for _ in range(n_inter):
            idt = rand_date(rng, last_apply, AS_OF)
            inters.append({
                "顧客ID": cid, "接触日": idt.isoformat(),
                "種別": rng.choice(KINDS), "担当": rng.choice(AGENTS),
                "案内内容": rng.choice(["継続確認", "追加提案", "見直し相談", "定期連絡"]),
                "メモ": "",
            })

    # --- 放置検知(要フォロー)デモ用に、高リスク条件の継続中顧客を数件、接触なしで固定注入 ---
    for k in range(1, 6):
        apply_id += 1
        cid = f"C9{k:03d}"
        apply_date = date(2026, 5, 10) + timedelta(days=k * 3)  # 継続中(<6ヶ月)
        apps.append({
            "顧客ID": cid, "申込ID": f"A{apply_id}",
            "申込日": apply_date.isoformat(), "商品": "医療",
            "集客チャネル": "ネット", "申込形態": "単発", "金額": 2000,
            "年齢": 26, "性別": rng.choice(GENDERS), "地域": rng.choice(AREAS),
            "営業担当": "OK-07", "解約日": "", "解約理由": "",
        })
        # 接触は入れない → 高リスク×接触なし＝要フォロー

    # 未紐付(顧客ID欠損)デモ：数件、IDを空で混ぜる（黙って消さず件数表示させる）
    for _ in range(3):
        apply_id += 1
        apps.append({
            "顧客ID": "", "申込ID": f"A{apply_id}",
            "申込日": "2026-06-15", "商品": "医療", "集客チャネル": "ネット",
            "申込形態": "単発", "金額": 3500, "年齢": 30, "性別": "男性",
            "地域": "那覇", "営業担当": "OK-03", "解約日": "", "解約理由": "",
        })
    inters.append({"顧客ID": "", "接触日": "2026-06-20", "種別": "架電",
                   "担当": "OK-03", "案内内容": "定期連絡", "メモ": ""})

    app_path = os.path.join(out_dir, "apps.csv")
    inter_path = os.path.join(out_dir, "inter.csv")
    with open(app_path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(apps[0].keys()))
        w.writeheader()
        w.writerows(apps)
    with open(inter_path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(inters[0].keys()))
        w.writeheader()
        w.writerows(inters)
    print(f"[gen] 申込 {len(apps)}件 / 接触 {len(inters)}件 → {app_path} / {inter_path}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--seed", type=int, default=42)
    main_args = ap.parse_args()
    gen(main_args.out_dir, main_args.seed)


if __name__ == "__main__":
    main()
