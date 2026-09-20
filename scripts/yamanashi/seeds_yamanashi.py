# -*- coding: utf-8 -*-
"""もらいわすれ堂 山梨版 — 山梨県の制度シード(第2段階)

守り部審査(docs/守り部審査記録_山梨版_2026-09-20.md)で「個別ページへのリンク可」と
判定されたA区分のうち、山梨県(www.pref.yamanashi.jp)分。
県の規約: 「山梨県ホームページには自由にリンクしていただけます」
          条件=リンクである旨の明記(出典表示で満たす)・フレーム内表示の禁止(別タブ遷移で満たす)

掲載方針(沖縄版と同じ):
- 保持するのは事実情報とリンクのみ。説明文の転載はしない
- 金額・締切は原則 status="要確認"。原文照合が済むまで verified=False
- source_url は 2026-09-20 に WebSearch で現存を確認(検索最上位がURL・タイトルとも一致)。
  ただし本文の逐語照合は未実施のため、検証部の確認までは要確認のままとする

市町村独自の制度は、守り部の論点1・2(営利サイト可否/トップページ限定)の決裁後に追加する。
"""

# 山梨県の制度。area="山梨県" にすると市町村ページ27枚すべてに自動で載る(沖縄版と同じ仕組み)
YMN_PREF_SEEDS = [
    {
        "id": "ym-ken-nyuyoji-iryo",
        "name": "乳幼児医療費の助成",
        "category": "医療・健康", "life_events": ["子育て", "病気・けが"],
        "issuer": "山梨県(実施は市町村)", "area": "山梨県",
        "target_household": "山梨県内にお住まいで、乳幼児を育てている世帯が対象となる可能性があります(対象年齢や助成内容は市町村ごとに決められています)",
        "how_to_apply": "お住まいの市町村の担当窓口",
        "source_url": "https://www.pref.yamanashi.jp/kosodate/71890998147.html",
        "amount_note": "要確認(対象年齢・自己負担の有無は市町村で異なります。公式ページと窓口でご確認ください)",
        "deadline_type": "常時",
    },
    {
        "id": "ym-ken-hitorioya-iryo",
        "name": "ひとり親家庭等医療費助成",
        "category": "医療・健康", "life_events": ["子育て", "離婚・死別", "病気・けが"],
        "issuer": "山梨県(実施は市町村)", "area": "山梨県",
        "target_household": "山梨県内にお住まいのひとり親家庭の親と子(18歳年度末まで)、父母のない児童が対象となる可能性があります",
        "how_to_apply": "お住まいの市町村の担当窓口",
        "source_url": "https://www.pref.yamanashi.jp/kodomo-fukushi/40_026.html",
        "match_tokens": ["ひとり親家庭"],
        "amount_note": "要確認(生活保護受給世帯や所得が一定以上の世帯は対象外とされています。公式ページと窓口でご確認ください)",
        "deadline_type": "常時",
    },
    {
        "id": "ym-ken-judo-shinshin-iryo",
        "name": "重度心身障害者医療費助成制度",
        "category": "医療・健康", "life_events": ["障害", "病気・けが"],
        "issuer": "山梨県(実施は市町村)", "area": "山梨県",
        "target_household": "山梨県内にお住まいで、重度の心身障害のある方が対象となる可能性があります",
        "how_to_apply": "お住まいの市町村の担当窓口",
        "source_url": "https://www.pref.yamanashi.jp/shogai-fks/judo/jidoukanpu-ikou.html",
        "amount_note": "要確認(対象となる障害の程度・助成の方法は公式ページと窓口でご確認ください)",
        "deadline_type": "常時",
    },
    {
        "id": "ym-ken-nanbyo-iryo",
        "name": "難病医療費助成制度",
        "category": "医療・健康", "life_events": ["病気・けが"],
        "issuer": "山梨県", "area": "山梨県",
        "target_household": "国が定める指定難病と診断され、一定の重症度等の要件に当てはまる方が対象となる可能性があります",
        "how_to_apply": "お住まいの地域を管轄する保健所",
        "source_url": "https://www.pref.yamanashi.jp/kenko-zsn/boshinanbyou/aratana-nanbyou.html",
        "match_tokens": ["難病"],
        "amount_note": "要確認(自己負担の上限額は所得等に応じて決まります。公式ページと窓口でご確認ください)",
        "deadline_type": "常時",
    },
    {
        "id": "ym-ken-iju-shienkin",
        "name": "山梨県移住支援金",
        "category": "住まい", "life_events": ["住宅取得・引越", "就職・転職"],
        "issuer": "山梨県(市町村と共同)", "area": "山梨県",
        "target_household": "東京圏から山梨県内へ移住し、就業・起業などの要件を満たす世帯が対象となる可能性があります",
        "how_to_apply": "移住先の市町村の担当窓口",
        "source_url": "https://www.pref.yamanashi.jp/jinko-taisaku/koukai/ijushienkin.html",
        "match_tokens": ["移住支援金"],
        "amount_note": "要確認(予算の範囲内で支給されるため、年度途中に受付が終わることがあります。公式ページと窓口でご確認ください)",
        "deadline_type": "要確認",
    },
]
