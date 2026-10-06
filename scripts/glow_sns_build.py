#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GLOW「世界の懸け橋」の Instagram / Facebook 投稿素材(画像+キャプション)を作る。

  python scripts/glow_sns_build.py            # 全投稿の画像とキャプションを作り直す(フォントのある手元で実行)
  python scripts/glow_sns_build.py --restamp  # 文面の再点検が済んだ日付で出荷ゲート記録だけ更新(画像は触らない)

出力: posts/glow/<id>.jpg(1080x1350)・posts/glow/<id>.md(キャプション+出荷ゲート記録)・posts/glow/order.json(投稿順)
投稿は scripts/glow_sns_post.py(ワークフロー glow-sns-post)が order.json の順に1本ずつ行う。

文面のルール(2026-10-06 小柳さん決裁・議事は glow-docs-private の議事_20261006_GLOW世界の懸け橋_SNS自動投稿):
- 数字・事例は提案資料で照合済みのものだけ。出典を必ず添える。新しい数字を足すときは照合してから
- 「提携」「公式」とは書かない(Alibaba.com の名称・ロゴの使用ルールが未確認のため)。ロゴは使わない
- 「懸け橋」をローマ字で書かない / M&A・承継の話題は出さない(出荷ゲートの禁止表現)
- AIの商品写真には「※写真はAIで作ったイメージです」を必ず入れる
"""
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone

from PIL import Image, ImageDraw, ImageFont

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
OUT = os.path.join(BASE, "posts", "glow")
SRC = os.path.join(OUT, "src")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import shipping_gate  # noqa: E402

JST = timezone(timedelta(hours=9))
W, H = 1080, 1350
NAVY, RED, CREAM, INK, MUTED, SEA, WHITE = (0, 51, 92), (185, 80, 47), (255, 251, 244), (42, 50, 56), (102, 113, 122), (11, 110, 138), (255, 255, 255)
LIGHT_SEA = (234, 244, 247)

FONT_DIRS = [os.path.expanduser("~/.fonts"), "/usr/share/fonts/truetype", "/usr/share/fonts/opentype"]


def font(name, size):
    for d in FONT_DIRS:
        for root, _, files in os.walk(d):
            if name in files:
                return ImageFont.truetype(os.path.join(root, name), size)
    raise SystemExit(f"[error] フォント {name} が見つかりません(~/.fonts に入れてから実行)")


def F(kind, size):
    return font({"g": "BIZUDPGothic-Regular.ttf", "gb": "BIZUDPGothic-Bold.ttf",
                 "m": "ShipporiMinchoB1-ExtraBold.ttf"}[kind], size)


SITE = "https://glow-okinawa.jp/?utm_source={src}&utm_medium=social&utm_campaign=glow_sns"
LINE_GO = "https://allgroup-inc.github.io/hojo-hq/go/glow-{ch}/"
TAGS = "#沖縄 #沖縄県産 #沖縄の生産者 #沖縄特産品 #海外販路 #輸出 #越境EC #Alibaba #世界の懸け橋 #GLOW"
AI_NOTE = "※写真はAIで作ったイメージです。"

# ---------------------------------------------------------------- 投稿の中身
# kind: num(大きな数字)/ wall(5つの壁)/ item(沖縄の産品と英語名)/ case(事例)/ qa(よくある質問)/ text(説明)/ photo(写真+文)
POSTS = [
    {"id": "intro", "kind": "photo", "img": "hero-shuri-calligraphy.jpg", "kicker": "はじめまして",
     "title": "沖縄の力強さを、\n世界へ。",
     "lines": ["沖縄でつくったものを、世界の買い手へ。", "GLOWの「世界の懸け橋」です。"],
     "cap": "はじめまして。株式会社GLOWの「世界の懸け橋」です。\n\n沖縄の生産者・企業のみなさんの商品を、世界最大級の企業どうしの取引サイト「Alibaba.com」の上にあるGLOWの沖縄の売り場に並べ、世界の買い手へ届けるお手伝いをしています。\n\nこのアカウントでは、世界の市場の数字や、海外へ売るときの壁と乗り越え方、沖縄の産品の英語での伝え方などを、わかりやすくお届けします。"},
    {"id": "num-buyers", "kind": "num", "kicker": "世界の市場", "num": "4,000万", "unit": "以上",
     "label": "世界の会社・お店が、\nAlibaba.comで仕入れ先を\n探しています", "src": "出典: Alibaba Group 公表(2024年度は4,800万以上)",
     "cap": "世界で4,000万以上の会社やお店が、Alibaba.comで仕入れ先を探しています。\n\n沖縄にいながら、この人たちに商品を見てもらう方法があります。GLOWは、Alibaba.comの上に沖縄の商品を紹介する売り場を持ち、あなたの商品を並べます。\n\n出典: Alibaba Group 公表(2024年度は4,800万以上)"},
    {"id": "wall-1", "kind": "wall", "no": 1, "title": "海外の展示会", "cost": "1回 約300万円",
     "desc": "出展料・ブースの装飾・商品の輸送を\n合わせた目安。数日で終わり、\n成果が出る保証はありません。",
     "glow": "365日ひらいている売り場に、\nあなたの商品がずっと並びます。",
     "cap": "ふつうに世界へ売ろうとすると、5つの壁があります。\n\n壁1は「海外の展示会」。出展料・装飾・輸送を合わせると1回で約300万円が目安です(条件によって変わります)。しかも数日で終わり、成果が出る保証はありません。\n\nGLOWの売り場なら、365日あなたの商品が世界に並び続けます。"},
    {"id": "item-andagi", "kind": "item", "img": "andagi.webp", "en": "Sata Andagi", "ja": "サーターアンダギー",
     "cap": "サーターアンダギーは、英語の売り場では「Sata Andagi」。\n\n世界の買い手は、まず写真と英語の名前で商品を選びます。どんな味か、どう食べるかを英語でひとこと添えるだけで、伝わり方が変わります。\n\nGLOWの売り場では、英語の商品名と説明をいっしょに整えます。\n\n" + AI_NOTE},
    {"id": "num-inquiries", "kind": "num", "kicker": "世界の市場", "num": "40万件", "unit": "以上",
     "label": "毎日、世界から届く\n商品の問い合わせ", "src": "出典: アリババ株式会社 公式サイト",
     "cap": "Alibaba.comには、毎日40万件以上の問い合わせが世界から届いています。\n\n展示会のように数日で終わるのではなく、一年中、世界の会社が仕入れ先を探しに来る場所です。\n\n出典: アリババ株式会社 公式サイト"},
    {"id": "case-matcha", "kind": "case", "tag": "日本の地域産品", "num": "約720億円",
     "title": "抹茶などの緑茶の輸出が、\n1年で約2倍に", "desc": "2025年の緑茶の輸出額。\n海外の抹茶人気で、\n前の年からほぼ倍に増えました。",
     "src": "出典: 農林水産省(2026年2月公表)",
     "cap": "2025年の緑茶の輸出額は約720億円。海外の抹茶人気で、前の年からほぼ倍に増えました。\n\n日本の地域の産品が、世界で選ばれています。沖縄の産品にも、まだ知られていない魅力がたくさんあります。\n\n出典: 農林水産省(2026年2月公表)"},
    {"id": "qa-english", "kind": "qa", "q": "英語が話せなくても\n大丈夫?",
     "a": "大丈夫です。\n日本語のままやり取りできます。\nGLOWもお手伝いします。",
     "cap": "よく聞かれる質問「英語が話せなくても大丈夫?」\n\n大丈夫です。翻訳の仕組みを使い、日本語のままやり取りできます。英語の商品名や説明づくりも、GLOWがいっしょに進めます。"},
    {"id": "item-mozuku", "kind": "item", "img": "mozuku.webp", "en": "Okinawa Mozuku", "ja": "もずく",
     "cap": "もずくは、英語の売り場では「Okinawa Mozuku」。\n\n「Okinawa」を名前に入れると、どこの産品かがひと目で伝わります。産地の名前は、世界の買い手にとって大事な手がかりです。\n\n" + AI_NOTE},
    {"id": "wall-2", "kind": "wall", "no": 2, "title": "海外への出張", "cost": "欧米1週間 約100万円",
     "desc": "航空券・ホテル・滞在費の目安。\n行っても、決める立場の人に\n会える保証はありません。",
     "glow": "沖縄にいながら、\n世界から問い合わせが届きます。",
     "cap": "海外へ売るときの壁2は「海外への出張」。欧米へ1週間行くと、航空券・ホテル・滞在費で約100万円が目安です(条件によって変わります)。\n\nGLOWの売り場なら、沖縄にいながら、世界の買い手から問い合わせが届きます。"},
    {"id": "fee", "kind": "text", "kicker": "料金はシンプル", "title": "値段は、\nあなたが決められます",
     "lines": ["売り場への掲載  1商品 月1万円", "売れたときだけ  販売価格の20%", "国内の倉庫まで  送料のみ"],
     "foot": "※売れなかった月も、掲載料の月1万円はかかります。", "fs": 52,
     "cap": "世界の懸け橋の料金は3つだけです。\n\n・売り場への掲載: 1商品 月1万円\n・売れたときだけ: 販売価格の20%\n・国内の倉庫までの送料\n\n世界での販売価格は、あなたが決めます。手数料と送料を見込んで値段をつければ、売れたときに損をしません。\n※売れなかった月も、掲載料の月1万円はかかります。"},
    {"id": "item-umibudo", "kind": "item", "img": "umibudo.webp", "en": "Sea Grapes", "ja": "海ぶどう",
     "cap": "海ぶどうは、英語では「Sea Grapes」。\n\n見た目がそのまま名前になっているので、写真といっしょなら世界の買い手にもすぐ伝わります。食感や食べ方をひとこと添えると、もっと選ばれやすくなります。\n\n" + AI_NOTE},
    {"id": "case-kagetsuen", "kind": "case", "tag": "Alibaba.comの事例", "num": "50数か国",
     "title": "人口約12万人の町の\nお茶屋さんが、\n50数か国と取引", "desc": "愛媛県新居浜市の香月園は、\n出店から2年2か月で\n50数か国と取引するように。",
     "src": "出典: アリババ株式会社 お客様事例",
     "cap": "愛媛県新居浜市のお茶屋さん・香月園は、Alibaba.comに出店してから2年2か月で、50数か国と取引するようになりました。\n\n小さな町のお店でも、世界と取引できています。\n\n出典: アリババ株式会社 お客様事例"},
    {"id": "wall-3", "kind": "wall", "no": 3, "title": "言葉", "cost": "通訳1日 約5万円",
     "desc": "商品の説明や値段の交渉で\n言い間違いがあれば、\n大きなトラブルになります。",
     "glow": "日本語のままで、\nやり取りできます。",
     "cap": "海外へ売るときの壁3は「言葉」。通訳をお願いすると1日約5万円が目安です(条件によって変わります)。値段の交渉で言い間違いがあれば、大きなトラブルにもなります。\n\nGLOWの売り場なら、翻訳の仕組みとGLOWのお手伝いで、日本語のままやり取りできます。"},
    {"id": "item-awamori", "kind": "item", "img": "awamori.webp", "en": "Okinawa Awamori", "ja": "泡盛",
     "cap": "泡盛は、英語の売り場では「Okinawa Awamori」。\n\n沖縄にしかないお酒だからこそ、名前の前に「Okinawa」をつけて、どこで生まれたかを伝えます。\n\n※お酒の輸出は、国ごとのルールの確認が必要です。くわしくはご相談ください。\n" + AI_NOTE},
    {"id": "num-export", "kind": "num", "kicker": "日本の輸出", "num": "1兆7,005", "unit": "億円", "small": True,
     "label": "日本の農林水産物・食品の輸出額\n(2025年・13年連続で過去最高)", "src": "出典: 農林水産省(2026年2月公表)",
     "cap": "2025年の日本の農林水産物・食品の輸出額は1兆7,005億円。13年連続で過去最高になりました。\n\n世界の食卓で、日本の産品が選ばれ続けています。\n\n出典: 農林水産省(2026年2月公表)"},
    {"id": "qa-what", "kind": "qa", "q": "どんな商品が\n売れますか?",
     "a": "食品、飲み物、工芸品、雑貨など、\n沖縄でつくられた商品です。\nまず商品名をお聞かせください。",
     "cap": "よく聞かれる質問「どんな商品が売れますか?」\n\n食品、飲み物、工芸品、雑貨など、沖縄でつくられた商品が対象です。売れるかどうかは商品や国によって違うので、まずは商品名をお聞かせください。いっしょに考えます。"},
    {"id": "item-glass", "kind": "item", "img": "glass.webp", "en": "Ryukyu Glass", "ja": "琉球ガラス",
     "cap": "琉球ガラスは、英語では「Ryukyu Glass」。\n\n食品だけでなく、工芸品も世界の買い手に届けられます。手づくりであること、一つずつ色や形が違うことを英語で伝えると、魅力が伝わりやすくなります。\n\n" + AI_NOTE},
    {"id": "wall-4", "kind": "wall", "no": 4, "title": "書類と発送", "cost": "専門用語だらけ",
     "desc": "インボイス、通関、国際輸送。\nひとつでも間違えると、\n商品が港で止まります。",
     "glow": "国内の倉庫へ送るだけ。\nその先はGLOWがつなぎます。",
     "cap": "海外へ売るときの壁4は「書類と発送」。インボイス、通関、国際輸送と専門用語だらけで、ひとつでも間違えると商品が港で止まってしまいます。\n\nGLOWの売り場なら、あなたは日本国内の倉庫へ送るだけ。その先はGLOWがつなぎます。"},
    {"id": "case-awamori-award", "kind": "case", "tag": "沖縄の産品", "num": "最高金賞",
     "title": "泡盛が、世界の\n三大酒類コンペで\n最高金賞", "desc": "忠孝酒造(豊見城市)の\n泡盛『月の蒸溜所』が、\n三大コンペのすべてで最高金賞。",
     "src": "出典: 忠孝酒造 発表、沖縄タイムス",
     "cap": "忠孝酒造(豊見城市)の泡盛『月の蒸溜所』が、世界三大酒類コンペティション(IWSC・ISC・SFWSC)のすべてで最高金賞を受けました。\n\n沖縄の味は、世界の舞台で通用します。\n\n出典: 忠孝酒造 発表、沖縄タイムス"},
    {"id": "item-pineapple", "kind": "item", "img": "pineapple.webp", "en": "Okinawa Pineapple", "ja": "パイナップル",
     "cap": "パイナップルは、英語の売り場では「Okinawa Pineapple」。\n\n生のくだものは国ごとに持ち込みのルールがあります。ジャムやドライフルーツなど、加工した商品から考えるのも一つの方法です。くわしくはご相談ください。\n\n" + AI_NOTE},
    {"id": "price-example", "kind": "text", "kicker": "値付けの例", "title": "原価2,000円なら、\n販売価格は4,125円",
     "lines": ["(原価+利益+送料)÷0.8", "=(2,000+1,000+300)÷0.8", "=4,125円"],
     "foot": "※為替や国ごとの相場は含みません。", "fs": 54,
     "cap": "値付けの例です。原価2,000円、欲しい利益1,000円、倉庫までの送料300円なら、\n\n(2,000+1,000+300)÷0.8=4,125円\n\nこの値段なら、売れたときの手数料20%を引いても、欲しい利益が残ります。サイトの値付けシミュレーターでも同じ計算ができます。\n※為替や国ごとの相場は含みません。"},
    {"id": "wall-5", "kind": "wall", "no": 5, "title": "代金の不安", "cost": "「払ってもらえる?」",
     "desc": "知らない国の、知らない相手。\n送ったのに入金されない、\nという怖さがあります。",
     "glow": "代金をAlibaba.comが\nいったん預かってから\n支払う仕組みがあります。",
     "cap": "海外へ売るときの壁5は「代金の不安」。知らない国の、知らない相手に商品を送るのは怖いものです。\n\nAlibaba.comには、買い手の代金をいったん預かってから支払う仕組みがあります。"},
    {"id": "item-bingata", "kind": "item", "img": "bingata.webp", "en": "Bingata Textile", "ja": "紅型",
     "cap": "紅型は、英語の売り場では「Bingata Textile」。\n\nそのままの名前を残しながら、どんなものかを英語の言葉で添えると、はじめて見る人にも伝わります。\n\n" + AI_NOTE},
    {"id": "num-countries", "kind": "num", "kicker": "世界の市場", "num": "200", "unit": "以上",
     "label": "Alibaba.comを使う企業が\nいる国と地域", "src": "出典: アリババ株式会社 公式サイト",
     "cap": "Alibaba.comは、200以上の国と地域の企業が使っています。\n\n沖縄の商品を、まだ出会ったことのない国の会社に見てもらえる場所です。\n\n出典: アリババ株式会社 公式サイト"},
    {"id": "qa-ship", "kind": "qa", "q": "海外へ自分で\n発送するの?",
     "a": "いいえ。\n送るのは日本国内の倉庫までです。\nその先はGLOWがつなぎます。",
     "cap": "よく聞かれる質問「海外へ自分で発送するの?」\n\nいいえ。あなたが送るのは日本国内の倉庫までです。その先の海外への発送は、GLOWがつなぎます。"},
    {"id": "item-kokuto", "kind": "item", "img": "kokuto.webp", "en": "Okinawan Brown Sugar", "en_size": 70, "ja": "黒糖",
     "cap": "黒糖は、英語では「Okinawan Brown Sugar」。「Kokuto」という呼び名を添えるのも一つの方法です。\n\n世界の買い手が検索で使う言葉と、沖縄ならではの呼び名。両方を入れると、見つけてもらいやすくなります。\n\n" + AI_NOTE},
    {"id": "case-okinawa-export", "kind": "case", "tag": "沖縄からの輸出", "num": "21.4億円",
     "title": "沖縄からの\n飲み物の輸出が、\n過去最高に", "desc": "2024年の沖縄からの飲料の輸出額。\n前の年より28%増え、\n量・金額とも過去最高。",
     "src": "出典: 沖縄地区税関(2025年5月公表)",
     "cap": "2024年の沖縄からの飲料(ビール・ウイスキー・泡盛など)の輸出額は21.4億円。前の年より28%増え、量・金額とも過去最高になりました。\n\n出典: 沖縄地区税関(2025年5月公表)"},
    {"id": "about", "kind": "photo", "img": "minei.webp", "kicker": "株式会社GLOWについて",
     "title": "沖縄の企業の、\nいちばん近くで。",
     "lines": ["代表 嶺井 忍", "沖縄振興開発金融公庫に34年。", "沖縄の企業の資金のご相談に", "何十年も向き合ってきました。"],
     "cap": "株式会社GLOWは、沖縄に根ざした企業支援の会社です。\n\n代表の嶺井は、沖縄振興開発金融公庫に34年。創業のとき、苦しいとき、次の一歩を踏み出すとき、いつも沖縄の経営者のとなりで支えてきました。\n\nその経験を、今度はみなさんの世界への挑戦に生かします。"},
    {"id": "item-soba", "kind": "item", "img": "soba.webp", "en": "Okinawa Soba", "ja": "沖縄そば",
     "cap": "沖縄そばは、英語の売り場では「Okinawa Soba」。\n\n乾麺やスープの素など、日持ちする形にすると海外へ届けやすくなります。どの形で出すかも、いっしょに考えます。\n\n" + AI_NOTE},
    {"id": "qa-unsold", "kind": "qa", "q": "売れなかったら?",
     "a": "販売価格の20%はかかりません。\nただし掲載料の月1万円は、\n売れなかった月もかかります。",
     "cap": "よく聞かれる質問「売れなかったら?」\n\n売れたときにかかる販売価格の20%は、売れなければかかりません。ただし掲載料の月1万円は、売れなかった月もかかります。"},
    {"id": "steps", "kind": "text", "kicker": "始めるまでの流れ", "title": "まずは話を聞く\nところから",
     "lines": ["1  LINEで相談(商品名だけでもOK)", "2  面談で値段や数量を確認", "3  お申し込み", "4  売り場に掲載", "5  注文が入ったら国内の倉庫へ"],
     "foot": "LINEで質問した時点では、お申し込みにはなりません。",
     "cap": "世界の懸け橋を始めるまでの流れです。\n\n1. LINEで相談(商品名を送るだけでもOK)\n2. 面談で値段や数量をいっしょに確認\n3. お申し込み\n4. GLOWの売り場に掲載\n5. 注文が入ったら国内の倉庫へ送るだけ\n\nLINEで質問した時点では、お申し込みにはなりません。"},
    {"id": "what-alibaba", "kind": "text", "kicker": "Alibaba.comとは", "title": "一年中ひらいている\n世界の展示会",
     "lines": ["会社どうしが商品を見せ合い、", "取引の相手を見つける場所。", "それがインターネット上で", "毎日ひらかれています。"],
     "foot": "※GLOWは、Alibaba.com上に沖縄の売り場を持ち、運営しています。",
     "cap": "Alibaba.comは、世界最大級の企業どうしの取引サイトです。\n\n会社どうしが商品を見せ合い、取引の相手を見つける「展示会」が、インターネット上で毎日ひらかれているイメージです。\n\nGLOWは、その中に沖縄の売り場を持ち、運営しています。"},
]

# ---------------------------------------------------------------- 描画


def text_w(draw, s, f):
    return draw.textlength(s, font=f)


FIT_ERRORS = []


def lines_fit(draw, lines, f, maxw, who):
    for ln in lines:
        w = text_w(draw, ln, f)
        if w > maxw:
            FIT_ERRORS.append(f"{who}: 「{ln}」{int(w)}px > {int(maxw)}px")


def paste_logo(img, x, y, h):
    lg = Image.open(os.path.join(SRC, "glow-logo.png")).convert("RGBA")
    lg = lg.resize((round(lg.width * h / lg.height), h), Image.LANCZOS)
    img.paste(lg, (x, y), lg)


def base_canvas():
    img = Image.new("RGB", (W, H), WHITE)
    d = ImageDraw.Draw(img)
    # 下の帯(ブランド)
    d.rectangle([0, H - 120, W, H], fill=CREAM)
    d.line([0, H - 120, W, H - 120], fill=(230, 225, 216), width=2)
    paste_logo(img, 64, H - 102, 84)
    d.text((W - 64, H - 78), "世界の懸け橋", font=F("gb", 30), fill=NAVY, anchor="ra")
    d.text((W - 64, H - 40), "glow-okinawa.jp", font=F("g", 26), fill=MUTED, anchor="ra")
    return img, d


def draw_lines(d, x, y, lines, f, fill, gap, who, maxw=W - 128, anchor="la"):
    lines_fit(d, lines, f, maxw, who)
    for ln in lines:
        d.text((x, y), ln, font=f, fill=fill, anchor=anchor)
        y += gap
    return y


def kicker_title(d, p, y=90):
    d.text((64, y), p["kicker"], font=F("gb", 38), fill=RED)
    return draw_lines(d, 64, y + 70, p["title"].split("\n"), F("m", 76), NAVY, 100, p["id"])


def render(p):
    img, d = base_canvas()
    k, who = p["kind"], p["id"]
    if k == "num":
        d.text((64, 90), p["kicker"], font=F("gb", 40), fill=RED)
        box = [64, 200, W - 64, 900]
        d.rounded_rectangle(box, 28, fill=LIGHT_SEA)
        fn, fu = (F("gb", 130), F("gb", 52)) if p.get("small") else (F("gb", 160), F("gb", 56))
        nw_, uw = text_w(d, p["num"], fn), text_w(d, p["unit"], fu)
        if nw_ + uw + 20 > W - 160:
            FIT_ERRORS.append(f"{who}: 数字が収まりません")
        x0 = (W - (nw_ + uw + 20)) / 2
        d.text((x0, 520), p["num"], font=fn, fill=SEA, anchor="ls")
        d.text((x0 + nw_ + 20, 520), p["unit"], font=fu, fill=SEA, anchor="ls")
        draw_lines(d, W / 2, 600, p["label"].split("\n"), F("gb", 50), INK, 74, who, W - 200, "ma")
        draw_lines(d, 64, 960, [p["src"]], F("g", 30), MUTED, 40, who)
        d.text((64, 1060), "沖縄にいながら、世界の買い手へ。", font=F("gb", 40), fill=NAVY)
    elif k == "wall":
        d.text((64, 90), "ふつうに世界へ売ろうとすると", font=F("gb", 38), fill=RED)
        d.text((64, 150), f"壁{p['no']}", font=F("m", 120), fill=RED)
        d.text((300, 175), p["title"], font=F("m", 84), fill=NAVY)
        d.text((64, 320), p["cost"], font=F("gb", 64), fill=INK)
        y = draw_lines(d, 64, 430, p["desc"].split("\n"), F("g", 46), INK, 74, who)
        gl = p["glow"].split("\n")
        bh = 130 + len(gl) * 84 + 40
        top = y + max(40, (1180 - y - bh) // 2)
        d.rounded_rectangle([64, top, W - 64, top + bh], 28, fill=CREAM, outline=RED, width=4)
        d.text((104, top + 40), "GLOWといっしょなら", font=F("gb", 42), fill=RED)
        draw_lines(d, 104, top + 120, gl, F("gb", 54), NAVY, 84, who, W - 208)
    elif k == "item":
        ph = Image.open(os.path.join(SRC, p["img"])).convert("RGB").resize((760, 760), Image.LANCZOS)
        img.paste(ph, ((W - 760) // 2, 70))
        fe = F("gb", p.get("en_size", 82))
        d.text((W / 2, 900), p["en"], font=fe, fill=NAVY, anchor="ma")
        d.text((W / 2, 1010), p["ja"] + " の英語名", font=F("g", 42), fill=MUTED, anchor="ma")
        d.text((W / 2, 1080), "写真と英語の名前で、世界に選ばれる。", font=F("gb", 40), fill=RED, anchor="ma")
        d.text((W - 64, 1190), AI_NOTE, font=F("g", 24), fill=MUTED, anchor="ra")
        lines_fit(d, [p["en"]], fe, W - 128, who)
    elif k == "case":
        d.text((64, 90), "世界で通用した、地方の力", font=F("gb", 38), fill=RED)
        d.rounded_rectangle([64, 170, W - 64, 1150], 28, fill=CREAM)
        d.text((112, 220), p["tag"], font=F("gb", 38), fill=RED)
        y = draw_lines(d, 112, 290, p["title"].split("\n"), F("gb", 58), NAVY, 82, who, W - 224)
        d.text((112, y + 30), p["num"], font=F("m", 120), fill=NAVY)
        draw_lines(d, 112, y + 200, p["desc"].split("\n"), F("g", 40), INK, 62, who, W - 224)
        draw_lines(d, 112, 1080, [p["src"]], F("g", 28), MUTED, 40, who, W - 224)
    elif k == "qa":
        d.text((64, 90), "よくある質問", font=F("gb", 40), fill=RED)
        d.text((64, 190), "Q", font=F("m", 150), fill=RED)
        y = draw_lines(d, 64, 380, p["q"].split("\n"), F("m", 88), NAVY, 116, who)
        al = p["a"].split("\n")
        bh = 175 + len(al) * 84 + 50
        top = y + max(40, (1180 - y - bh) // 2)
        d.rounded_rectangle([64, top, W - 64, top + bh], 28, fill=CREAM)
        d.text((112, top + 36), "A", font=F("m", 90), fill=NAVY)
        draw_lines(d, 112, top + 175, al, F("gb", 50), INK, 84, who, W - 224)
    elif k == "text":
        y = kicker_title(d, p)
        n = len(p["lines"])
        fs, gap = (60, 130) if n <= 3 else (50, 104)
        fs = p.get("fs", fs)
        bh = 80 + n * gap
        top = y + max(50, (1120 - y - bh) // 2)
        d.rounded_rectangle([64, top, W - 64, top + bh], 28, fill=CREAM)
        draw_lines(d, 112, top + 60, p["lines"], F("gb", fs), NAVY, gap, who, W - 224)
        draw_lines(d, 64, top + bh + 30, [p["foot"]], F("g", 30), MUTED, 40, who)
    elif k == "photo":
        ph = Image.open(os.path.join(SRC, p["img"])).convert("RGB")
        if p["img"].startswith("minei"):
            ph = ph.resize((420, 420), Image.LANCZOS)
            mask = Image.new("L", (420, 420), 0)
            ImageDraw.Draw(mask).ellipse([0, 0, 420, 420], fill=255)
            img.paste(ph, ((W - 420) // 2, 420), mask)
            y = kicker_title(d, p)
            draw_lines(d, W / 2, 880, p["lines"], F("gb", 46), INK, 70, who, W - 128, "ma")
        else:
            tw = W
            th = round(ph.height * tw / ph.width)
            ph = ph.resize((tw, th), Image.LANCZOS).crop((0, 0, W, 760))
            img.paste(ph, (0, 0))
            d.text((64, 800), p["kicker"], font=F("gb", 38), fill=RED)
            y = draw_lines(d, 64, 860, p["title"].split("\n"), F("m", 72), NAVY, 92, who)
            draw_lines(d, 64, y + 20, p["lines"], F("gb", 38), INK, 56, who)
    else:
        raise SystemExit(f"[error] 不明な種類 {k}")
    return img


# ---------------------------------------------------------------- キャプション


def caption(p):
    body = p["cap"].strip()
    cta = ("\n\n▶ くわしく(世界の懸け橋のサイト)\n" + SITE.format(src="facebook") +
           "\n▶ LINEで相談(商品名だけでもOK)\n" + LINE_GO.format(ch="fb"))
    return body + cta + "\n\n" + TAGS


def write_md(p, checked):
    text = (f"# GLOW SNS投稿: {p['id']}\n\n"
            f"## キャプション\n{caption(p)}\n\n"
            + shipping_gate.render_stamp("Claude(glow_sns_build・提案資料の照合済み数字のみ使用)", checked))
    with open(os.path.join(OUT, p["id"] + ".md"), "w", encoding="utf-8") as f:
        f.write(text)


def self_check():
    ids = [p["id"] for p in POSTS]
    assert len(ids) == len(set(ids)), "id が重複しています"
    for p in POSTS:
        c = caption(p)
        assert not re.search(r"KAKEHASHI|kakehashi", c), p["id"]
        assert "提携" not in c and "公式パートナー" not in c, p["id"]
        if p["kind"] == "item":
            assert AI_NOTE in c, p["id"]
        probs = shipping_gate.check_forbidden(c)
        assert not probs, (p["id"], probs)
        assert len(c) <= 2200, (p["id"], "Instagramのキャプション上限2,200文字を超えています")
    print(f"[ok] 自己点検 {len(POSTS)}本")


def main():
    os.makedirs(OUT, exist_ok=True)
    today = datetime.now(JST).date().isoformat()
    self_check()
    if "--restamp" in sys.argv:
        for p in POSTS:
            write_md(p, today)
        print(f"[ok] 出荷ゲート記録を {today} に更新({len(POSTS)}本)")
        return
    imgs = {p["id"]: render(p) for p in POSTS}
    if FIT_ERRORS:
        print("[error] 枠に収まらない行があります(何も保存していません):")
        for e in FIT_ERRORS:
            print("  - " + e)
        raise SystemExit(1)
    for p in POSTS:
        imgs[p["id"]].save(os.path.join(OUT, p["id"] + ".jpg"), "JPEG", quality=90, optimize=True)
        write_md(p, today)
    with open(os.path.join(OUT, "order.json"), "w", encoding="utf-8") as f:
        json.dump([p["id"] for p in POSTS], f, ensure_ascii=False, indent=1)
    print(f"[ok] {len(POSTS)}本の画像とキャプションを作成 → posts/glow/")


if __name__ == "__main__":
    main()
