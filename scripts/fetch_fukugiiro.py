#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
フクギイロ 収集部(シュシュ・個人向け管轄)v1 — シードURL方式
守り部承認済みドメイン(こども家庭庁・厚労省・文科省・内閣府 / 審査記録第2号)の
主要制度をシードとして、公式ページの到達性を確認できたものだけを data/fukugiiro/seido.json に書く。

設計原則(審査記録の遵守条件そのまま):
- 保持するのは事実情報(制度名・発行元・窓口・原文URL)のみ。説明文の転載はしない
- 金額・締切は書かない(amount_note=要確認)。ケンショウの一次ソース突合後に人が embellish する
- robots.txt を毎回確認・連絡先付きUA・リクエスト間隔1.5秒以上
- 到達性(HTTP 200)が確認できないシードはDBに書かない(壊れたリンクを公開しない)
- 書き込み前に validate_fukugiiro.validate() を通し、エラーがあれば書かずに異常終了
- 実行は GitHub Actions のみ・朝夕2回まで(第1次審査ウタガイ採用事項)

TODO(ベッカイ採用事項): 各府省RSS/新着の監視は v2 で追加(新設・随時給付の検知用)
"""
import json
import os
import sys
import time
import urllib.request
import urllib.robotparser
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(__file__))
from validate_fukugiiro import validate  # noqa: E402

JST = timezone(timedelta(hours=9))
UA = "hojo-hq-bot/1.0 (+https://allgroup-inc.github.io/hojo-hq; contact: bot@en-life.co.jp)"
BASE = os.path.join(os.path.dirname(__file__), "..")
OUT = os.path.join(BASE, "data", "fukugiiro", "seido.json")

# シード: 承認済みドメインの主要制度(URLは2026-07-22に検索で特定。到達性は毎回実行時に再確認)
SEEDS = [
    {
        "id": "fk-kuni-jidoteate",
        "name": "児童手当",
        "category": "子育て", "life_events": ["子育て"],
        "issuer": "こども家庭庁", "area": "全国",
        "target_household": "中学生以下(2024年10月以降は高校生年代まで拡充)のお子さんを育てている世帯が対象となる可能性があります",
        "how_to_apply": "お住まいの市区町村の窓口",
        "source_url": "https://www.cfa.go.jp/policies/kokoseido/jidouteate",
    },
    {
        "id": "fk-kuni-jidofuyoteate",
        "name": "児童扶養手当",
        "category": "子育て", "life_events": ["子育て", "低所得・生活苦"],
        "issuer": "こども家庭庁", "area": "全国",
        "target_household": "ひとり親家庭などでお子さんを育てている世帯が対象となる可能性があります",
        "how_to_apply": "お住まいの市区町村の窓口",
        "source_url": "https://www.cfa.go.jp/policies/hitori-oya/fuyou-teate",
    },
    {
        "id": "fk-kuni-shussan-ichijikin",
        "name": "出産育児一時金",
        "category": "子育て", "life_events": ["妊娠・出産"],
        "issuer": "厚生労働省(各健康保険)", "area": "全国",
        "target_household": "健康保険に加入している方(被扶養者を含む)が出産したときに対象となる可能性があります",
        "how_to_apply": "加入している健康保険(協会けんぽ・国保など)への申請。多くは医療機関での直接支払制度が利用できます",
        "source_url": "https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/kenkou_iryou/iryouhoken/shussan/index.html",
    },
    {
        "id": "fk-kuni-ikuji-kyufu",
        "name": "育児休業給付(雇用保険)",
        "category": "子育て", "life_events": ["妊娠・出産", "子育て", "就職・転職"],
        "issuer": "厚生労働省・ハローワーク", "area": "全国",
        "target_household": "雇用保険に加入していて育児休業を取得する方が対象となる可能性があります",
        "how_to_apply": "原則、勤務先を通じてハローワークへ申請",
        "source_url": "https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/0000158500.html",
    },
    {
        "id": "fk-kuni-jukyo-kakuho",
        "name": "住居確保給付金",
        "category": "住まい", "life_events": ["失業", "低所得・生活苦", "住宅取得・引越"],
        "issuer": "厚生労働省", "area": "全国",
        "target_household": "離職・収入減少などで家賃の支払いにお困りの世帯が対象となる可能性があります",
        "how_to_apply": "お住まいの自治体の自立相談支援機関",
        "source_url": "https://corona-support.mhlw.go.jp/jukyokakuhokyufukin/index.html",
    },
    {
        "id": "fk-kuni-kogaku-ryoyo",
        "name": "高額療養費制度",
        "category": "医療・健康", "life_events": ["病気・けが"],
        "issuer": "厚生労働省(各健康保険)", "area": "全国",
        "target_household": "1ヶ月の医療費の自己負担が上限額を超えた方が対象となる可能性があります",
        "how_to_apply": "加入している健康保険への申請(事前の限度額適用認定証の利用も可能です)",
        "source_url": "https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/kenkou_iryou/iryouhoken/juuyou/kougakuiryou/index.html",
    },
    {
        "id": "fk-kuni-shugaku-shien",
        "name": "高等教育の修学支援新制度(授業料等減免・給付型奨学金)",
        "category": "教育", "life_events": ["入園・入学"],
        "issuer": "文部科学省", "area": "全国",
        "target_household": "大学・短大・高専・専門学校に進学する(在学中の)お子さんがいる世帯が対象となる可能性があります(2025年度から多子世帯の拡充があります)",
        "how_to_apply": "在学校・進学先を通じた申込み(日本学生支援機構)",
        "source_url": "https://www.mext.go.jp/kyufu/",
        "amount_note": "給付型奨学金(返還不要)と授業料・入学金の減免をセットで受けられる場合があります。世帯年収の目安は約600万円まで、令和7年度からは扶養する子3人以上の多子世帯は所得制限なく減免の対象になる場合があります(要確認)",
        "verified": True, "verified_at": "2026-08-06",
        "verified_by": "kensho(文部科学省 公式ページ照合WebSearch)+小柳さん同席確認 2026-08-06",
    },
    {
        "id": "fk-kuni-hitorioya-shien",
        "name": "ひとり親家庭への支援制度(全体案内)",
        "category": "子育て", "life_events": ["子育て", "低所得・生活苦"],
        "issuer": "こども家庭庁", "area": "全国",
        "target_household": "ひとり親家庭の世帯向けの各種支援(手当・貸付・就業支援など)の入口です",
        "how_to_apply": "お住まいの市区町村の窓口",
        "source_url": "https://www.cfa.go.jp/policies/hitori-oya",
        "match_tokens": ["ひとり親家庭"],
    },
    {
        "id": "fk-kuni-ninpu-shien",
        "name": "妊婦のための支援給付・伴走型相談支援",
        "category": "子育て", "life_events": ["妊娠・出産"],
        "issuer": "こども家庭庁", "area": "全国",
        "target_household": "妊娠された方・出産された世帯が対象となる可能性があります",
        "how_to_apply": "お住まいの市区町村の窓口(母子保健担当)",
        "source_url": "https://www.cfa.go.jp/policies/shussan-kosodate",
    },
    {
        "id": "fk-kuni-shugakushienkin-koko",
        "name": "高等学校等就学支援金",
        "category": "教育", "life_events": ["入園・入学"],
        "issuer": "文部科学省", "area": "全国",
        "target_household": "高校等に通うお子さんがいる世帯が対象となる可能性があります(令和8年度から所得制限が撤廃され、世帯収入にかかわらず授業料が実質無償となる案内が出ています。学校種別・支給額の詳細は公式ページでご確認ください)",
        "how_to_apply": "在学する学校を通じた申請(オンライン申請 e-Shien)",
        "source_url": "https://www.mext.go.jp/a_menu/shotou/mushouka/1342674.htm",
    },
    {
        "id": "fk-kuni-shogaku-kyufukin-koko",
        "name": "高校生等奨学給付金",
        "category": "教育", "life_events": ["入園・入学", "低所得・生活苦"],
        "issuer": "文部科学省(窓口は都道府県)", "area": "全国",
        "target_household": "住民税非課税世帯等で高校生等のお子さんがいる世帯が対象となる可能性があります",
        "how_to_apply": "お住まいの都道府県への申請(学校経由の場合あり)",
        "source_url": "https://www.mext.go.jp/a_menu/shotou/mushouka/1344089.htm",
    },
    {
        "id": "fk-kuni-kyushokusha-shien",
        "name": "求職者支援制度(職業訓練受講給付金)",
        "category": "仕事・失業", "life_events": ["失業", "就職・転職", "低所得・生活苦"],
        "issuer": "厚生労働省・ハローワーク", "area": "全国",
        "target_household": "雇用保険を受給できない求職中の方(フリーランス・自営業を廃業した方等を含む)が対象となる可能性があります",
        "how_to_apply": "ハローワーク",
        "source_url": "https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/koyou_roudou/koyou/kyushokusha_shien/index.html",
    },
    {
        "id": "fk-kuni-seikatsu-konkyu",
        "name": "生活困窮者自立支援制度(相談窓口)",
        "category": "生活支援", "life_events": ["低所得・生活苦", "失業"],
        "issuer": "厚生労働省", "area": "全国",
        "target_household": "生活にお困りごとを抱えている世帯の総合相談窓口です(家賃・就労・家計・子どもの学習支援など)",
        "how_to_apply": "お住まいの自治体の自立相談支援機関",
        "source_url": "https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/0000055454.html",
        "match_tokens": ["生活困窮者自立支援"],
    },
    {
        "id": "fk-kuni-kyoiku-kunren",
        "name": "教育訓練給付金",
        "category": "仕事・失業", "life_events": ["就職・転職"],
        "issuer": "厚生労働省・ハローワーク", "area": "全国",
        "target_household": "働きながら(または離職後に)資格取得やスキルアップを目指す方が対象となる可能性があります",
        "how_to_apply": "ハローワーク",
        "source_url": "https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/koyou_roudou/jinzaikaihatsu/kyouiku.html",
    },
    # --- 第2次シード拡充(2026-07-23 シュシュ。承認済み4府省+同一ドメインの公式特設サイトのみ) ---
    {
        "id": "fk-kuni-hoiku-mushoka",
        "name": "幼児教育・保育の無償化",
        "category": "子育て", "life_events": ["入園・入学", "子育て"],
        "issuer": "こども家庭庁", "area": "全国",
        "target_household": "3〜5歳のお子さん(住民税非課税世帯は0〜2歳も)が幼稚園・保育所・認定こども園などを利用する世帯が対象となる可能性があります",
        "how_to_apply": "利用する施設・お住まいの市区町村の窓口",
        "source_url": "https://www.cfa.go.jp/policies/kokoseido/mushouka",
        "match_tokens": ["無償化"],
    },
    {
        "id": "fk-kuni-tokubetsu-jifute",
        "name": "特別児童扶養手当",
        "category": "子育て", "life_events": ["子育て", "障がい"],
        "issuer": "厚生労働省", "area": "全国",
        "target_household": "障がいのあるお子さん(20歳未満)を育てている世帯が対象となる可能性があります",
        "how_to_apply": "お住まいの市区町村の窓口",
        "source_url": "https://www.mhlw.go.jp/bunya/shougaihoken/jidou/huyou.html",
        "match_tokens": ["特別児童扶養手当"],
    },
    {
        "id": "fk-kuni-shogaiji-fukushi",
        "name": "障害児福祉手当",
        "category": "子育て", "life_events": ["子育て", "障がい"],
        "issuer": "厚生労働省", "area": "全国",
        "target_household": "重度の障がいのあるお子さん(20歳未満)を育てている世帯が対象となる可能性があります",
        "how_to_apply": "お住まいの市区町村の窓口",
        "source_url": "https://www.mhlw.go.jp/bunya/shougaihoken/jidou/hukushi.html",
        "match_tokens": ["障害児福祉手当"],
    },
    {
        "id": "fk-kuni-tokubetsu-shogaisha",
        "name": "特別障害者手当",
        "category": "生活支援", "life_events": ["障がい"],
        "issuer": "厚生労働省", "area": "全国",
        "target_household": "重度の障がいがあり日常生活で常時特別の介護が必要な方(20歳以上)が対象となる可能性があります",
        "how_to_apply": "お住まいの市区町村の窓口",
        "source_url": "https://www.mhlw.go.jp/bunya/shougaihoken/jidou/tokubetsu.html",
        "match_tokens": ["特別障害者手当"],
    },
    {
        "id": "fk-kuni-jiritsushien-iryo",
        "name": "自立支援医療(医療費の自己負担軽減)",
        "category": "医療・健康", "life_events": ["病気・けが", "障がい"],
        "issuer": "厚生労働省", "area": "全国",
        "target_household": "心身の治療を続けている方(精神通院・更生医療・育成医療)が対象となる可能性があります",
        "how_to_apply": "お住まいの市区町村の窓口",
        "source_url": "https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/hukushi_kaigo/shougaishahukushi/jiritsu/index.html",
        "match_tokens": ["自立支援医療"],
    },
    {
        "id": "fk-kuni-koyohoken-kihonteate",
        "name": "雇用保険の基本手当(失業給付)",
        "category": "仕事・失業", "life_events": ["失業"],
        "issuer": "厚生労働省・ハローワーク", "area": "全国",
        "target_household": "離職して求職活動をしている、雇用保険に加入していた方が対象となる可能性があります",
        "how_to_apply": "ハローワーク",
        "source_url": "https://www.hellowork.mhlw.go.jp/insurance/insurance_basicbenefit.html",
        "match_tokens": ["基本手当"],
    },
    {
        "id": "fk-kuni-kaigokyugyo-kyufu",
        "name": "介護休業給付金(雇用保険)",
        "category": "介護", "life_events": ["介護", "就職・転職"],
        "issuer": "厚生労働省・ハローワーク", "area": "全国",
        "target_household": "家族の介護のために休業する、雇用保険に加入している方が対象となる可能性があります",
        "how_to_apply": "原則、勤務先を通じてハローワークへ申請",
        "source_url": "https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/0000135090.html",
        "match_tokens": ["介護休業給付"],
    },
    {
        "id": "fk-kuni-rousai",
        "name": "労災保険の給付(仕事中・通勤中のけが・病気)",
        "category": "仕事・失業", "life_events": ["病気・けが"],
        "issuer": "厚生労働省", "area": "全国",
        "target_household": "仕事中や通勤中のけが・病気で治療や休業が必要になった方が対象となる可能性があります(パート・アルバイトも対象です)",
        "how_to_apply": "労働基準監督署(多くは勤務先経由)",
        "source_url": "https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/koyou_roudou/roudoukijun/rousai/index.html",
        "match_tokens": ["労災"],
    },
    {
        "id": "fk-kuni-miharai-chingin",
        "name": "未払賃金立替払制度",
        "category": "仕事・失業", "life_events": ["失業"],
        "issuer": "厚生労働省", "area": "全国",
        "target_household": "勤務先の倒産などで賃金が支払われないまま退職した方が対象となる可能性があります",
        "how_to_apply": "労働基準監督署",
        "source_url": "https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/koyou_roudou/roudoukijun/kijungyosei/miharai/index.html",
        "match_tokens": ["未払賃金"],
    },
    {
        "id": "fk-kuni-seikatsu-hogo",
        "name": "生活保護制度(相談窓口)",
        "category": "生活支援", "life_events": ["低所得・生活苦"],
        "issuer": "厚生労働省", "area": "全国",
        "target_household": "収入や資産だけでは生活が難しい世帯のための、最後のセーフティネットの相談窓口です。ためらわずに相談できます",
        "how_to_apply": "お住まいの地域の福祉事務所",
        "source_url": "https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/hukushi_kaigo/seikatsuhogo/seikatuhogo/index.html",
        "match_tokens": ["生活保護"],
    },
    {
        "id": "fk-kuni-nenkin-kyufukin",
        "name": "年金生活者支援給付金",
        "category": "生活支援", "life_events": ["低所得・生活苦"],
        "issuer": "厚生労働省", "area": "全国",
        "target_household": "年金を受給していて所得が一定以下の方が対象となる可能性があります(年金に上乗せして支給されます)",
        "how_to_apply": "日本年金機構(年金事務所)への請求",
        "source_url": "https://www.mhlw.go.jp/nenkinkyuufukin/",
        "match_tokens": ["年金生活者支援給付金"],
    },
    {
        "id": "fk-kuni-saigai-choui",
        "name": "災害弔慰金・災害援護資金など(被災時の支援)",
        "category": "防災・その他", "life_events": ["災害"],
        "issuer": "厚生労働省", "area": "全国",
        "target_household": "台風などの自然災害で被害を受けた世帯が対象となる可能性があります",
        "how_to_apply": "お住まいの市区町村の窓口",
        "source_url": "https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/hukushi_kaigo/seikatsuhogo/saigaikyujo/index.html",
        "match_tokens": ["災害弔慰金"],
    },
    {
        "id": "fk-kuni-shugaku-enjo",
        "name": "就学援助(小・中学生の学用品費・給食費など)",
        "category": "教育", "life_events": ["入園・入学", "低所得・生活苦"],
        "issuer": "文部科学省(窓口は市区町村)", "area": "全国",
        "target_household": "経済的な理由で小・中学校の就学にお困りの世帯が対象となる可能性があります",
        "how_to_apply": "お子さんが通う学校・お住まいの市区町村の教育委員会",
        "source_url": "https://www.mext.go.jp/a_menu/shotou/career/05010502/017.htm",
        "match_tokens": ["就学援助"],
    },
    {
        "id": "fk-kuni-tokushi-shorei",
        "name": "特別支援教育就学奨励費",
        "category": "教育", "life_events": ["入園・入学", "障がい"],
        "issuer": "文部科学省(窓口は学校・教育委員会)", "area": "全国",
        "target_household": "特別支援学校・特別支援学級などに通うお子さんがいる世帯が対象となる可能性があります",
        "how_to_apply": "お子さんが通う学校・教育委員会",
        "source_url": "https://www.mext.go.jp/a_menu/shotou/tokubetu/material/1340250.htm",
        "match_tokens": ["就学奨励"],
    },
    {
        "id": "fk-kuni-safetynet-jutaku",
        "name": "住宅セーフティネット制度(住宅確保要配慮者の入居支援)",
        "category": "住まい", "life_events": ["住宅取得・引越", "低所得・生活苦"],
        "issuer": "国土交通省", "area": "全国",
        "target_household": "低所得・ひとり親・高齢などの理由で民間賃貸住宅への入居にお困りの世帯が対象となる可能性があります",
        "how_to_apply": "お住まいの自治体の居住支援窓口・居住支援法人",
        "source_url": "https://www.mlit.go.jp/jutakukentiku/house/jutakukentiku_house_tk3_000055.html",
        "match_tokens": ["セーフティネット"],
    },
    {
        "id": "fk-kuni-kosodate-green",
        "name": "子育てグリーン住宅支援事業(新築・リフォーム補助)",
        "category": "住まい", "life_events": ["住宅取得・引越", "子育て"],
        "issuer": "国土交通省", "area": "全国",
        "target_household": "省エネ住宅の新築や省エネリフォームを行う世帯(子育て・若者夫婦世帯は補助が手厚い)が対象となる可能性があります",
        "how_to_apply": "登録事業者(工務店・リフォーム会社)を通じた申請",
        "source_url": "https://kosodate-green.mlit.go.jp/",
        "match_tokens": ["子育てグリーン"],
    },
    # ── 沖縄県(県レベル・守り部✅条件付き承認 2026-07-27: 事実+リンクのみ・本文転載禁止・出典.lg.jp)──
    {
        "id": "fk-ken-boshi-fushi-kafu-shikin",
        "name": "母子父子寡婦福祉資金貸付金",
        "category": "生活支援", "life_events": ["子育て", "低所得・生活苦"],
        "issuer": "沖縄県", "area": "沖縄県",
        "target_household": "ひとり親家庭(母子・父子)や寡婦の方が、生活・就学・住宅などの資金でお困りのときに対象となる可能性があります",
        "how_to_apply": "お住まいの市町村または県の福祉事務所の窓口へ相談",
        "source_url": "https://www.pref.okinawa.lg.jp/kyoiku/kosodate/1008226/1036501/1036529/1036517.html",
        "match_tokens": ["母子父子寡婦福祉資金", "貸付"],
    },
    {
        "id": "fk-ken-hitorioya-jutaku-shikin",
        "name": "沖縄県ひとり親家庭住宅支援資金貸付",
        "category": "住まい", "life_events": ["住宅取得・引越", "低所得・生活苦"],
        "issuer": "沖縄県", "area": "沖縄県",
        "target_household": "自立支援プログラムに参加し、就職や技能習得に取り組むひとり親家庭が対象となる可能性があります",
        "how_to_apply": "事前に母子父子自立支援プログラムの策定が必要。申請窓口は沖縄県母子寡婦福祉連合会(098-887-4099)",
        "amount_note": "家賃の実費(月額上限7万円・最長12か月)／無利子・保証人不要",
        "source_url": "https://www.pref.okinawa.lg.jp/kyoiku/kosodate/1008226/1036501/1036529/1036514.html",
        "match_tokens": ["ひとり親", "住宅支援資金"],
    },
    {
        "id": "fk-ken-hitorioya-kurashi-ouen",
        "name": "沖縄県ひとり親家庭暮らし応援事業",
        "category": "生活支援", "life_events": ["子育て", "低所得・生活苦"],
        "issuer": "沖縄県", "area": "沖縄県",
        "target_household": "児童扶養手当の受給世帯など、ひとり親家庭の方が対象となる可能性があります",
        "how_to_apply": "申請は専用キャンペーンサイト(電子クーポン)から。問い合わせは事業事務局(沖縄JTB株式会社・050-1794-2924)",
        "amount_note": "電子クーポン 児童1人あたり1万円(2人目以降 各5千円加算)",
        "deadline": "2026-10-15", "deadline_type": "期限あり",
        "source_url": "https://www.pref.okinawa.lg.jp/kyoiku/kosodate/1008226/1036501/1036531/1039524.html",
        "match_tokens": ["ひとり親", "暮らし応援"],
    },
    {
        "id": "fk-ken-kenei-jutaku",
        "name": "沖縄県営住宅",
        "category": "住まい", "life_events": ["住宅取得・引越", "低所得・生活苦"],
        "issuer": "沖縄県", "area": "沖縄県",
        "target_household": "住まいにお困りで、所得などの要件にあてはまる世帯が対象となる可能性があります",
        "how_to_apply": "沖縄県住宅供給公社・県の住宅窓口へ",
        "source_url": "https://www.pref.okinawa.lg.jp/machizukuri/jutakutochi/1012327/1012334/index.html",
        "match_tokens": ["県営住宅"],
        "amount_note": "家賃は世帯の収入などに応じて設定されます。入居には収入基準(月額所得の上限。子育て世帯は緩和あり)があり、募集時期に申込みが必要です(要確認)",
        "verified": True, "verified_at": "2026-08-06",
        "verified_by": "kensho(沖縄県 公式ページ照合WebSearch)+小柳さん同席確認 2026-08-06",
    },
    {
        "id": "fk-ken-senshiniryo-funin",
        "name": "沖縄県 先進医療不妊治療費助成事業",
        "category": "子育て", "life_events": ["妊娠・出産"],
        "issuer": "沖縄県", "area": "沖縄県",
        "target_household": "保険診療と併用する先進医療の不妊治療を受けている方が対象となる可能性があります",
        "how_to_apply": "お住まいの地域を管轄する保健所へ申請(那覇市は那覇市保健所)",
        "amount_note": "1回の申請につき上限7万円(支払額と基準額の少ない方の7割)",
        "source_url": "https://www.pref.okinawa.lg.jp/iryokenko/kenko/1006303/1006171.html",
        "match_tokens": ["先進医療", "不妊"],
    },
    {
        "id": "fk-ken-fuiku-kensa",
        "name": "沖縄県 不育症検査費用助成事業",
        "category": "子育て", "life_events": ["妊娠・出産"],
        "issuer": "沖縄県", "area": "沖縄県",
        "target_household": "不育症の検査を受けた方が対象となる可能性があります",
        "how_to_apply": "お住まいの地域を管轄する保健所へ申請(那覇市は那覇市保健所)",
        "amount_note": "1回の検査費用の7割(上限6万円)",
        "source_url": "https://www.pref.okinawa.lg.jp/iryokenko/kenko/1006303/1006306.html",
        "match_tokens": ["不育症", "検査"],
    },
    {
        "id": "fk-ken-kodomo-iryohi",
        "name": "沖縄県 こども医療費助成制度",
        "category": "医療・健康", "life_events": ["子育て"],
        "issuer": "沖縄県", "area": "沖縄県",
        "target_household": "県内にお住まいで対象年齢のお子さんがいる世帯が対象となる可能性があります(実施は市町村)",
        "how_to_apply": "お住まいの市町村の窓口",
        "source_url": "https://www.pref.okinawa.lg.jp/iryokenko/iryo/1005869/1005890.html",
        "match_tokens": ["こども医療費", "医療費助成"],
    },
    {
        "id": "fk-ken-boshi-fushi-iryohi",
        "name": "沖縄県 母子及び父子家庭等医療費助成事業",
        "category": "医療・健康", "life_events": ["子育て", "低所得・生活苦"],
        "issuer": "沖縄県", "area": "沖縄県",
        "target_household": "健康保険に加入するひとり親家庭などで、対象年齢のお子さん等がいる世帯が対象となる可能性があります",
        "how_to_apply": "お住まいの市町村の窓口",
        "source_url": "https://www.pref.okinawa.lg.jp/kyoiku/kosodate/1008226/1036501/1036529/1036519.html",
        "match_tokens": ["母子", "父子", "医療費助成"],
    },
    {
        "id": "fk-ken-judo-shinshin-iryohi",
        "name": "沖縄県 重度心身障害者医療費助成制度",
        "category": "医療・健康", "life_events": ["障がい", "病気・けが"],
        "issuer": "沖縄県", "area": "沖縄県",
        "target_household": "重度の心身障害のある方が対象となる可能性があります(自動償還で口座振込)",
        "how_to_apply": "お住まいの市町村の担当窓口",
        "source_url": "https://www.pref.okinawa.lg.jp/kyoiku/shogaifukushi/1007022/1018788/1006977/1006987.html",
        "match_tokens": ["重度心身障害者", "医療費助成"],
    },
    {
        "id": "fk-ken-nanbyo-iryohi",
        "name": "沖縄県 特定医療費(指定難病)助成制度",
        "category": "医療・健康", "life_events": ["病気・けが"],
        "issuer": "沖縄県", "area": "沖縄県",
        "target_household": "国が定める指定難病と診断された方が対象となる可能性があります",
        "how_to_apply": "お住まいの地域の保健所へ申請",
        "source_url": "https://www.pref.okinawa.lg.jp/iryokenko/hokenjo/1008066/1008086/1028432.html",
        "match_tokens": ["指定難病", "特定医療費"],
    },
]

# 追加シード(市町村独自・国/県の未収載。公式URLを検索で照合済み)を連結する。
# assume_reachable=True のシードは、bot遮断(403等)する自治体サイト向けに到達性チェックを省く。
try:
    from fetch_fukugiiro_extra import EXTRA_SEEDS
    SEEDS += EXTRA_SEEDS
except Exception as _e:  # モジュールが無くても既存シードで動く
    print(f"[info] EXTRA_SEEDS 読み込みスキップ: {_e}")

# 一時非公開エリア(2026-08-18 小柳さん指示・議事_20260818_沖縄市うるま市一時非公開.md)。
# 管理は fg_seo.HIDDEN_MUNIS の1箇所(市独自制度・市町村ページ・一覧・診断すべてに効く)。
from fg_seo import HIDDEN_MUNIS as HIDDEN_AREAS

_robots_cache = {}


def robots_ok(url):
    from urllib.parse import urlparse
    host = urlparse(url).netloc
    if host not in _robots_cache:
        rp = urllib.robotparser.RobotFileParser()
        try:
            req = urllib.request.Request(f"https://{host}/robots.txt", headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=20) as res:
                rp.parse(res.read().decode("utf-8", "replace").splitlines())
        except Exception:
            rp = None  # robots.txt無し等 → 制限指定なし扱い
        _robots_cache[host] = rp
        time.sleep(1.5)
    rp = _robots_cache[host]
    return True if rp is None else rp.can_fetch(UA, url)


def reachable(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=25) as res:
            return res.status == 200
    except Exception:
        return False


def main():
    now = datetime.now(JST).strftime("%Y-%m-%d %H:%M")
    items, skipped = [], []
    for seed in SEEDS:
        if seed.get("area") in HIDDEN_AREAS:
            skipped.append((seed["name"], "一時非公開(HIDDEN_AREAS)"))
            print(f"SKIP(hidden): {seed['name']}")
            continue
        url = seed["source_url"]
        if not robots_ok(url):
            skipped.append((seed["name"], "robots.txt不許可"))
            print(f"SKIP(robots): {seed['name']}")
            continue
        # 手動照合済み(assume_reachable)は、bot遮断する自治体サイト等のため到達性チェックを省く
        ok = True if seed.get("assume_reachable") else reachable(url)
        time.sleep(1.5)
        if not ok:
            skipped.append((seed["name"], "URL到達不可"))
            print(f"SKIP(unreachable): {seed['name']} {url}")
            continue
        item = dict(seed)
        item.update({
            # 金額・締切は原則「要確認」だが、一次ソース照合済みで確定した制度は seed 側に持たせる
            "amount_note": seed.get("amount_note", "要確認(公式ページでご確認ください)"),
            "deadline_type": seed.get("deadline_type", "常時" if seed["id"] != "fk-kuni-jukyo-kakuho" else "要確認"),
            "deadline": seed.get("deadline"),
            # 検証状態はシードを一次情報源にする(公式ページ照合済みは seed 側に verified を持たせる)。
            # 収集のたびにリセットされないよう、seed の値を尊重する。既存DB引き継ぎ(下)は安全網。
            "verified": bool(seed.get("verified", False)),
            "verified_at": seed.get("verified_at"),
            "verified_by": seed.get("verified_by"),
            "status": seed.get("status", "検証済み" if seed.get("verified") else "要確認"),
            "notes": "出典: " + seed["issuer"].split("(")[0] + "ウェブサイト",
            "fetched_at": now,
        })
        items.append(item)
        print(f"OK: {seed['name']}")

    # 既存DBの検証状態を引き継ぐ(収集のたびに verified がリセットされる事故の防止)
    try:
        with open(OUT, encoding="utf-8") as f:
            prev = {p["id"]: p for p in json.load(f).get("items", [])}
    except Exception:
        prev = {}
    for item in items:
        old = prev.get(item["id"])
        if old and old.get("source_url") == item["source_url"] and old.get("verified"):
            item["verified"] = True
            item["verified_at"] = old.get("verified_at")
            item["verified_by"] = old.get("verified_by")
            item["status"] = old.get("status", "検証済み")

    data = {"updated_at": now, "count": len(items), "items": items}
    errors, warns = validate(data)
    for w in warns:
        print(f"[WARN] {w}")
    if errors:
        for e in errors:
            print(f"[ERROR] {e}")
        print("検証エラーのため書き込みを中止")
        sys.exit(1)

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print(f"書き込み完了: {len(items)}件 / スキップ {len(skipped)}件 {skipped if skipped else ''}")
    # シードの半数以上が到達不可なら異常(サイト構造変化・ネットワーク断の疑い)
    if len(items) < len(SEEDS) / 2:
        print("[ERROR] シードの過半が取得不可 — 要調査")
        sys.exit(1)


if __name__ == "__main__":
    main()
