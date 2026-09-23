# -*- coding: utf-8 -*-
"""もらいわすれ堂 山梨版 — A区分市町村の制度シード(第2段階・2026-09-23)

守り部審査(docs/守り部審査記録_山梨版_2026-09-20.md)で「個別ページへのリンク可」と
判定された**A区分の市町村7件**のみ(北杜市・富士河口湖町・南アルプス市・上野原市・
昭和町・早川町・小菅村)。B区分(トップページ限定)・論点1の2市町(笛吹市・南部町)は
決裁待ちのため入れない。

作成手順(2026-09-23):
- source_url はWebSearchで検索結果に表示されたURLのみ(推測URLなし)。
  ドメインは監査(data/yamanashi/site_audit.json)の本人確認済みドメインと一致することを機械で確認
- 掲載は事実情報とリンクのみ。説明文の転載はしない
- 金額・対象年齢・締切は原文の逐語照合が済むまで書かない(すべて要確認・verified=False)
- 国の制度の市町村窓口ページ(児童手当・出産子育て応援給付など)は、国の制度と
  二重掲載になるためシードにしない(併給の見え方が紛らわしくなる)

遵守条件(沖縄版 docs/守り部審査記録.md と同じ。収集・照合を始める際の条件):
- robots.txt 遵守・リクエスト間隔1.5秒・連絡先付きUA・事実情報のみ・原文リンク必須
- 「要確認」表示(断定しない)・自治体から中止要請があれば即時対応
"""

# area=市町村名 にすると、その市町村のページに「〇〇市の制度」として載る(沖縄版と同じ仕組み)
YMN_MUNI_SEEDS = [
    # ── 北杜市(規約: トップページ及びサイト内のページへのリンクはフリー) ──
    {
        "id": "ym-hokuto-kodomo-iryo",
        "name": "子ども医療費助成制度",
        "category": "医療・健康", "life_events": ["子育て", "病気・けが"],
        "issuer": "北杜市", "area": "北杜市",
        "target_household": "北杜市にお住まいで、お子さんを育てている世帯が対象となる可能性があります(対象年齢は公式ページでご確認ください)",
        "how_to_apply": "北杜市の担当窓口",
        "source_url": "https://www.city.hokuto.yamanashi.jp/docs/1801.html",
    },
    {
        "id": "ym-hokuto-kosodate-ouenkin",
        "name": "子育て応援金支給事業",
        "category": "子育て", "life_events": ["妊娠・出産", "子育て"],
        "issuer": "北杜市", "area": "北杜市",
        "target_household": "北杜市にお住まいで、お子さんが生まれた・育てている世帯が対象となる可能性があります",
        "how_to_apply": "北杜市の担当窓口",
        "source_url": "https://www.city.hokuto.yamanashi.jp/docs/12089.html",
    },
    # ── 富士河口湖町(規約: 各ページへのリンクは原則自由・連絡や許可は不要) ──
    {
        "id": "ym-fujikawaguchiko-jutaku-shinchiku",
        "name": "住宅の新築(購入)支援制度",
        "category": "住まい", "life_events": ["住宅取得・引越"],
        "issuer": "富士河口湖町", "area": "富士河口湖町",
        "target_household": "富士河口湖町内で住宅を新築・購入する世帯が対象となる可能性があります(要件は公式ページでご確認ください)",
        "how_to_apply": "富士河口湖町の担当窓口",
        "source_url": "https://www.town.fujikawaguchiko.lg.jp/ka/info.php?if_id=39",
    },
    # ── 南アルプス市(規約: 原則として自由にリンク可) ──
    {
        "id": "ym-minamialps-kodomo-iryo",
        "name": "子ども医療費助成制度",
        "category": "医療・健康", "life_events": ["子育て", "病気・けが"],
        "issuer": "南アルプス市", "area": "南アルプス市",
        "target_household": "南アルプス市にお住まいで、お子さんを育てている世帯が対象となる可能性があります(対象年齢は公式ページでご確認ください)",
        "how_to_apply": "南アルプス市の担当窓口",
        "source_url": "https://www.city.minami-alps.yamanashi.jp/docs/1116.html",
    },
    {
        "id": "ym-minamialps-kosodate-jutaku",
        "name": "子育て世帯住宅取得支援事業",
        "category": "住まい", "life_events": ["住宅取得・引越", "子育て"],
        "issuer": "南アルプス市", "area": "南アルプス市",
        "target_household": "南アルプス市内で住宅を取得する子育て世帯が対象となる可能性があります(年度ごとの事業のため、受付状況は公式ページでご確認ください)",
        "how_to_apply": "南アルプス市の担当窓口",
        "source_url": "https://www.city.minami-alps.yamanashi.jp/docs/19517.html",
        "deadline_type": "要確認",
    },
    # ── 上野原市(規約: 発信するコンテンツはリンクフリー) ──
    {
        "id": "ym-uenohara-jutaku-reform",
        "name": "住宅リフォーム補助事業",
        "category": "住まい", "life_events": ["住宅取得・引越"],
        "issuer": "上野原市", "area": "上野原市",
        "target_household": "上野原市内で住宅のリフォーム工事を行う世帯が対象となる可能性があります(工事の要件・受付状況は公式ページでご確認ください)",
        "how_to_apply": "上野原市の担当窓口",
        "source_url": "https://www.city.uenohara.yamanashi.jp/page/1930.html",
        "deadline_type": "要確認",
    },
    {
        "id": "ym-uenohara-akiya-reform",
        "name": "空き家・空き店舗バンクリフォーム補助事業",
        "category": "住まい", "life_events": ["住宅取得・引越"],
        "issuer": "上野原市", "area": "上野原市",
        "target_household": "上野原市の空き家バンク等を利用してリフォームを行う方が対象となる可能性があります",
        "how_to_apply": "上野原市の担当窓口",
        "source_url": "https://www.city.uenohara.yamanashi.jp/site/iju/1516.html",
        "deadline_type": "要確認",
    },
    {
        "id": "ym-uenohara-iju-shienkin",
        "name": "移住支援金制度",
        "category": "住まい", "life_events": ["住宅取得・引越", "就職・転職"],
        "issuer": "上野原市", "area": "上野原市",
        "target_household": "上野原市へ移住した方のうち、国・県の移住支援事業の要件に当てはまる方が対象となる可能性があります",
        "how_to_apply": "上野原市の担当窓口",
        "source_url": "https://www.city.uenohara.yamanashi.jp/site/iju/1178.html",
        "deadline_type": "要確認",
    },
    # ── 昭和町(規約: 発信するコンテンツはリンクフリー) ──
    {
        "id": "ym-showa-kosodate-iryo",
        "name": "子育て支援医療費助成制度",
        "category": "医療・健康", "life_events": ["子育て", "病気・けが"],
        "issuer": "昭和町", "area": "昭和町",
        "target_household": "昭和町にお住まいで、お子さんを育てている世帯が対象となる可能性があります(対象年齢は公式ページでご確認ください)",
        "how_to_apply": "昭和町の担当窓口",
        "source_url": "https://www.town.showa.yamanashi.jp/soshiki/5/1646.html",
    },
    {
        "id": "ym-showa-ninkagai-hoiku",
        "name": "認可外保育施設保育料助成金",
        "category": "子育て", "life_events": ["子育て", "入園・入学"],
        "issuer": "昭和町", "area": "昭和町",
        "target_household": "昭和町にお住まいで、認可外保育施設を利用している世帯が対象となる可能性があります",
        "how_to_apply": "昭和町の担当窓口",
        "source_url": "https://www.town.showa.yamanashi.jp/soshiki/13/1178.html",
    },
    # ── 早川町(規約: リンクは原則自由) ──
    {
        "id": "ym-hayakawa-kosodate-iryo",
        "name": "子育て支援医療費助成",
        "category": "医療・健康", "life_events": ["子育て", "病気・けが"],
        "issuer": "早川町", "area": "早川町",
        "target_household": "早川町にお住まいで、お子さんを育てている世帯が対象となる可能性があります",
        "how_to_apply": "早川町の担当窓口",
        "source_url": "https://www.town.hayakawa.yamanashi.jp/people/child-care/nurturing-support/medical-expense.html",
    },
    {
        "id": "ym-hayakawa-kyushoku-hojo",
        "name": "給食費補助金",
        "category": "教育", "life_events": ["子育て", "入園・入学"],
        "issuer": "早川町", "area": "早川町",
        "target_household": "早川町にお住まいで、学校に通うお子さんを育てている世帯が対象となる可能性があります",
        "how_to_apply": "早川町の担当窓口",
        "source_url": "https://www.town.hayakawa.yamanashi.jp/people/child-care/nurturing-support/school-lunch.html",
    },
    {
        "id": "ym-hayakawa-ijusha-kaishu",
        "name": "移住者住宅改修補助",
        "category": "住まい", "life_events": ["住宅取得・引越"],
        "issuer": "早川町", "area": "早川町",
        "target_household": "早川町へ移住し、空き家を取得して改修する方が対象となる可能性があります",
        "how_to_apply": "早川町の担当窓口",
        "source_url": "https://www.town.hayakawa.yamanashi.jp/people/residence/2017-1013-1336-55.html",
        "deadline_type": "要確認",
    },
    # ── 小菅村(規約: 当サイトはリンクフリー。公式サイトはhttp配信のため原文どおりhttpで記載) ──
    {
        "id": "ym-kosuge-kodomo-iryo",
        "name": "こども医療費助成金制度",
        "category": "医療・健康", "life_events": ["子育て", "病気・けが"],
        "issuer": "小菅村", "area": "小菅村",
        "target_household": "小菅村にお住まいで、お子さんを育てている世帯が対象となる可能性があります(対象年齢は公式ページでご確認ください)",
        "how_to_apply": "小菅村の担当窓口",
        "source_url": "http://www.vill.kosuge.yamanashi.jp/living/jyumin/kodomoiryouhiijyosei.html",
    },
    {
        "id": "ym-kosuge-wakamono-teiju",
        "name": "若者定住促進の奨励制度",
        "category": "生活支援", "life_events": ["住宅取得・引越", "妊娠・出産"],
        "issuer": "小菅村", "area": "小菅村",
        "target_household": "小菅村にお住まい・移住する若い世帯が対象となる可能性があります(結婚・出産・定住の奨励金を含みます。内容は公式ページでご確認ください)",
        "how_to_apply": "小菅村の担当窓口",
        "source_url": "http://www.vill.kosuge.yamanashi.jp/administration/promotion/2010/11/post-1.php",
    },
    {
        "id": "ym-kosuge-akiya-kaishu",
        "name": "空き家改修等補助事業",
        "category": "住まい", "life_events": ["住宅取得・引越"],
        "issuer": "小菅村", "area": "小菅村",
        "target_household": "小菅村の空き家を改修して住む方が対象となる可能性があります",
        "how_to_apply": "小菅村の担当窓口",
        "source_url": "http://www.vill.kosuge.yamanashi.jp/living/shinko/renovation.html",
        "deadline_type": "要確認",
    },
]
