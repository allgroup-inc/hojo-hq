#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
フクギイロ SNS部(ヒロメ管轄拡張) — 県民向け投稿ジェネレータ
data/fukugiiro/seido.json から「キャプション+画像テキスト」を posts/fukugiiro/ に出力する。

方針(既存 generate_sns.py の制約を継承+フクギイロ原則):
- 誇大表現ゼロ(「必ず」「絶対」「誰でももらえる」等は使わない)。金額は書かない(要確認のため)
- すべて「可能性のご案内」トーン+出典URL明記+診断への単一導線(utm_source付き)
- 検証済み(status=検証済み)の制度のみ投稿対象
- 出力は下書き。投稿は金曜承認バッチで人間が確認してから(L2)
"""
import json
import os
import sys
from datetime import datetime, timezone, timedelta

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

JST = timezone(timedelta(hours=9))
BASE = os.path.join(os.path.dirname(__file__), "..")
DATA = os.path.join(BASE, "data", "fukugiiro", "seido.json")
OUT_DIR = os.path.join(BASE, "posts", "fukugiiro")
SHINDAN_URL = "https://allgroup-inc.github.io/hojo-hq/fukugiiro/shindan/?utm_source=instagram&utm_medium=social"
LP_URL = "https://allgroup-inc.github.io/hojo-hq/fukugiiro/?utm_source=instagram&utm_medium=social"

HASHTAGS = "#沖縄 #沖縄子育て #給付金 #手当 #沖縄ママ #沖縄パパ #家計 #もらいわすれ堂"
DISCLAIMER = "※対象になるかの最終判断は各窓口で行われます。金額・要件は公式ページでご確認ください。"

# ライフイベント別の「呼びかけ」文(やさしい日本語)
HOOKS = {
    "子育て": "お子さんがいるご家庭へ",
    "妊娠・出産": "妊娠中・出産されたばかりのご家庭へ",
    "入園・入学": "進学するお子さんがいるご家庭へ",
    "失業": "お仕事を離れたばかりの方へ",
    "低所得・生活苦": "家計が苦しいと感じているご家庭へ",
    "就職・転職": "働き方が変わった方へ",
    "住宅取得・引越": "住まいのことでお困りの方へ",
}


def seido_post(idx, it):
    hook = next((HOOKS[ev] for ev in it["life_events"] if ev in HOOKS), "沖縄のご家庭へ")
    return f"""# 制度紹介 {idx:02d}: {it['name']}

## 画像テキスト
- タイトル: {it['name']}
- サブ: {hook}
- ひとこと: 知らないだけで、受け取れるはずのお金かもしれません

## キャプション
【{hook}】
「{it['name']}」を知っていますか?

{it['target_household']}。

▶ 窓口: {it['how_to_apply']}
▶ 公式: {it['source_url']}

あなたの世帯にあてはまるかは、プロフィールのリンクから3分で診断できます(無料・匿名)。
{SHINDAN_URL}

{DISCLAIMER}
{HASHTAGS}
"""


def launch_post():
    return f"""# ローンチ告知: もらいわすれ堂はじめました

## 画像テキスト
- タイトル: あなたの世帯、いくらもらい忘れてる?
- サブ: 沖縄の給付金・手当を3分で診断(無料・匿名)
- ひとこと: あなたが受け取るまで、いっしょに。

## キャプション
沖縄のご家庭向けに、給付金・手当の「もらい忘れ」をなくすサイト「もらいわすれ堂」をはじめました。

・名前や住所の入力なし、3分の匿名診断
・国の制度から順に掲載中(市町村の制度も順次追加します)
・情報はすべて公式ページと照合してから掲載しています

診断はこちらから(無料)
{SHINDAN_URL}

{DISCLAIMER}
{HASHTAGS}
"""


def gosen_post(items):
    names = "\n".join(f"{i}. {it['name']}" for i, it in enumerate(items[:5], 1))
    return f"""# まとめ: 知っていますか?この5つ

## 画像テキスト
- タイトル: 沖縄のご家庭向け 給付金・手当 5選
- サブ: 「知らなかった」をなくそう
- ひとこと: くわしくはプロフィールのリンクから

## キャプション
どれか1つでも「初めて聞いた」があったら、診断してみる価値があるかもしれません。

{names}

あなたの世帯にあてはまるかは3分で診断できます(無料・匿名)。
{SHINDAN_URL}

{DISCLAIMER}
{HASHTAGS}
"""


FORBIDDEN = ["必ずもらえる", "絶対", "審査なし", "誰でももらえる", "100%", "確実にもらえる", "無条件で支給"]


def main():
    with open(DATA, encoding="utf-8") as f:
        db = json.load(f)
    verified = [it for it in db["items"] if it.get("status") == "検証済み"]
    os.makedirs(OUT_DIR, exist_ok=True)

    files = {"00_launch.md": launch_post(), "01_gosen.md": gosen_post(verified)}
    for i, it in enumerate(verified[:8], 1):
        files[f"{i + 1:02d}_seido_{it['id'].replace('fk-kuni-', '')}.md"] = seido_post(i, it)

    errors = 0
    for name, text in files.items():
        for w in FORBIDDEN:
            if w in text:
                print(f"[ERROR] 禁止表現『{w}』が {name} に含まれる")
                errors += 1
        with open(os.path.join(OUT_DIR, name), "w", encoding="utf-8") as f:
            f.write(text)
    if errors:
        sys.exit(1)
    print(f"生成完了: {len(files)}投稿(検証済み{len(verified)}件から)→ posts/fukugiiro/")
    print("※投稿前に金曜承認バッチで人間確認(L2)。Instagram投稿は手動(API連携はアカウント開設後)")


if __name__ == "__main__":
    main()
