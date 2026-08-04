# note多ジャンル 世界事例リサーチ集(正本)

- 作成: 2026-08-04(並列3系統のWebリサーチを統合)/ 起案: 小柳健さん(「世界中にある事実を深くリサーチして総合したものを軸に」)
- 用途: ①実例研究シリーズ(posts/note/tanpatsu/)のファクト供給源 ②お題キュー(data/tanpatsu_topics.json)の補充源 ③運営計画v3の根拠
- ルール: **記事に使ってよいのは本書に出典URLつきで載っている事実のみ**。誤りが見つかったら本書を先に直し、引用記事を洗い出して訂正する
- 凡例: 〔公式/一次〕=公式発表・IR・公文書・行政 /〔報道〕=第三者メディア取材 /〔自称〕=本人申告のみ /〔未確認〕=裏取り不可
- 注意: リサーチ環境の制約でnote.com等へ直接照合できていない項目がある。**記事公開前に出典を開いて確認する**(運用規程3-1に組込済み)

## 1. note市場の一次データ(日本)

- note流通総額(GMV): 2025年Q3(6-8月)単四半期55億3,700万円・前年比127.4% 〔公式/一次・IR〕
  https://contents.xj-storage.jp/xcontents/AS05592/f0498e9d/b771/436b/8e46/d56515c4e881/140120260113532620.pdf
- 2024年度 年間流通総額170億円超・累計20万人が収益獲得・購入者の月平均支払額2,696円・売上トップ1,000の年平均1,332万円 〔公式/一次〕
  https://note.com/info/n/nbdc8496a3aac
- **公式・約30万件の有料記事分析(2026-01発表)**: 実用ノウハウ系の平均1,842円(上位20%は1,800円前後)/読み物系983円。文字数と売上はほぼ無相関。成長カテゴリ: テクノロジー・AI活用+268.6%、SNS・コンテンツ運用+258.7%、複業・在宅+179.0%。育児メンバーシップ売上トップ10のうち7人が参入1年以内 〔公式/一次〕
  https://prtimes.jp/main/html/rd/p/000000360.000017890.html / https://note.jp/n/n8522197d1ced
- 手数料: 決済手数料(クレカ5%/PayPay7%/ポイント10%/キャリア15%)→プラットフォーム利用料(有料記事・マガジン・メンバーシップ・チップ10%/定期購読マガジン20%)→振込270円/回 〔公式ヘルプ・要原文確認〕
  https://www.help-note.com/hc/ja/articles/360011358873
- 規約: 利益保証・誇大表現(必ず儲かる等)・マルチ勧誘・実態の薄い高額バックエンド誘導は禁止。違反時は記事削除・アカウント停止・売上没収の事例が報道されている 〔公式規約+報道〕
  https://terms.help-note.com/hc/ja/articles/44943817565465 / https://diamond.jp/articles/-/388571
- AI方針: AI使用自体は禁止されていない(表記義務は現時点で未確認)。クリエイター側にAI学習拒否設定あり。AI学習対価還元プログラムが2025-08開始 〔公式+報道〕
  https://note.jp/n/n389ccbb41e92 / https://www.watch.impress.co.jp/docs/news/1662581.html

### 個別事例(note)
- 後藤達也: メンバーシップ3万人超(2024-02本人公表・月500/980円の2層)。Xフォロワー数十万人からの転換事例 〔自称(継続的公開記録)〕
  https://x.com/goto_finance/status/1761179045960822961
- 大原千鶴: 月額2,000円で年500万円超(手数料控除後・本人談)。会員数は出典間で齟齬があり**記事では使わない** 〔報道〕
  https://diamond.jp/articles/-/388566
- けんすう「アル開発室」: 月980円×購読2,000名超(2024-07・公式ページ。複数媒体合算) 〔公式/一次〕
  https://alu.co.jp/dev-room
- カフェkenohi: 小規模店舗がメンバーシップで月会費(会員数十人規模) 〔報道・日経クロストレンド〕
  https://xtrend.nikkei.com/atcl/contents/18/00786/00007/
- 収益分布: 流通総額の大半が上位1,000に集中(トップ1,000平均1,515万円/年・1億円超も存在) 〔報道〕
  https://diamond.jp/articles/-/388566
- **重要な空白**: ゼロから(既存の知名度・フォロワー資産なしで)note単体で月30万円級に到達した**検証可能な**事例は今回の調査では見つからなかった(存在しない証明ではない)。検証可能な成功例は外部資産(Xフォロワー・知名度・専門実績)からの転換が共通項

## 2. X(旧Twitter)の構造(2025-2026)

- アルゴリズム: xAIが公開(2026-01完全版)。AIモデルが反応確率を予測し重み付き和でランキング 〔一次(リポジトリ)〕
  https://github.com/xai-org/x-algorithm
- 外部リンク: リーチ減の方向で各ソース一致(減衰幅は30%減〜ほぼゼロと幅・要自社ABテスト)。実務は「本文で価値提供・リンクはリプ欄/固定ポスト」 〔二次〕
  https://buffer.com/resources/links-on-x/ / https://www.cocorochikai.com/x-tips-url-reply/
- 強いシグナル: リプライ・会話の深さ・投稿後30-60分の初速 〔二次〕
  https://www.teract.ai/resources/twitter-algorithm-2026
- 投稿時間: Sprout Social(約20億エンゲージ分析)火〜木12-18時が最良(米国圏。日本の実務報告は平日夜・日曜午前) 〔大規模データ〕
  https://sproutsocial.com/insights/best-times-to-post-on-twitter/
- 自動化ルール: 予約投稿は可。スパム的自動投稿・自動フォロー・API外の自動操作は凍結対象。**AI自動返信ボットは2025-10改定で事前書面許可制** 〔公式+二次・運用前に原文確認〕
  https://help.x.com/en/rules-and-policies/x-automation / https://www.maxmouse.co.jp/tips/2025/1219_1/
- X API料金: 無料ティア廃止。新規は従量課金(投稿$0.015/件・**リンク入り投稿$0.20/件**・読み取り$0.005/件)。レガシーBasic $200/月 〔二次・契約前にdeveloper.x.comで要確認〕
  https://postproxy.dev/blog/x-api-pricing-2026/
- X広告収益分配: 参加条件(500万インプ/3ヶ月等)達成でも月数百〜数千円規模の報告 → 収益柱にならず送客が正攻法 〔二次+自称〕
  https://momentummarketing.co.jp/2025/10/18/monetize/
- リスク: 過剰アクション→シャドウバン/連携詐欺での凍結/2025年スパムフィルタ誤作動の大量凍結騒動 〔二次+当事者発言〕
  https://mkt-denshi.com/spam-taisaku/
- 0→1万フォロワーの共通型: 毎日1投稿+能動的リプライ/プロフィールのLP化(CTA1本)/リンクは本文に入れない/初速60分の返信対応/人格の見える発信 〔二次・複数ソース一致〕
  https://blog.beehiiv.com/p/build-newsletter-scratch-x-twitter

## 3. 世界のニュースレター・購読ビジネス

### 実測ベンチマーク
- 無料→有料転換率: 実測平均約3%(一般2-5%・大衆紙型1-2%・**ニッチ特化4-10%**、テック系約8%) 〔集計〕
  https://www.reallygoodbusinessideas.com/p/substack-average-paid-subscriber-conversion-rate / https://www.yana-g-y.com/p/substack-free-to-paid-conversion-rate
- 解約率: 有料ニュースレター月3-5%(月4%で約17ヶ月で半減)。ニュース購読全体は月5.8% 〔集計/調査〕
  https://newsletrix.com/blog/free-to-paid-newsletter-conversion-rate / https://recurly.com/research/churn-rate-benchmarks/
- 価格: 月$5-10がボリュームゾーン。上位誌は$15/月・$150/年に収斂。年払いは15-25%引き。Founding tier(通常年額の2-5倍)が定番 〔報道/集計〕
  https://www.reallygoodbusinessideas.com/p/substack-pricing
- Substack全体: 有料購読500万件(2025-03)・開封率平均44% 〔公式+集計〕
  https://substack.com/home/post/p-159133280 / https://backlinko.com/substack-users
- クリエイター所得分布(ConvertKit調査2024): $10万超は約18%・過半数は年$1.5万未満(べき分布) 〔調査〕
  https://www.prnewswire.com/news-releases/new-report-by-top-creator-platform-convertkit-unveils-a-paradigm-shift-the-rise-of-full-time-creators-302133207.html

### 成功事例
- **Tangle**(政治・超党派): 平日版ほぼ全部無料→有料は日曜版のみ。購読47万(有料7.1万)・年$415万・**転換率16%=業界最高水準**・開封率60% 〔報道〕
  https://pressgazette.co.uk/newsletters/politics-newsletter-makes-nearly-4m-in-subs-despite-giving-most-content-away/
- **Lenny's Newsletter**: 初年度$65,000(Substack公式)→年約$200万・転換率4-5%・$15/月 〔初年度は公式、以降推計〕
  https://on.substack.com/p/how-lenny-rachitsky-earned-65000 / https://growthinreverse.com/lenny/
- **Naptown Scoop**(人口4万の町のローカルNL): 1人運営・購読1.8万(町の半分近く)・開封率65%・2024年広告収入$350K超ペース。**ミカタに最も構造が近い** 〔自称+複数媒体取材〕
  https://www.sidehustlenation.com/local-newsletter-business/ / https://www.nichepursuits.com/my-local-email-newsletter-makes-over-200k-year-heres-how/
- **Industry Dive**(業界別B2B): Informaが企業価値$525Mで買収(2022) 〔報道/公式〕
  https://www.axios.com/2022/07/19/industry-dive-informa-acquisition
- Morning Brew: Insiderへ約$75M評価で売却(2020) 〔報道〕/ The Hustle: 通説$27Mだが**SEC提出書類では現金$17.2M**(誇大数字と一次資料の乖離の好例) 〔公文書〕
  https://www.sec.gov/Archives/edgar/data/1404655/000095017022001221/hubs-20211231.htm
- Milk Road(2人創業・10ヶ月で売却): 購読25万・FB広告CPA $1.21。売却額は**未確認**(推計のみ) 〔当事者公開+未確認〕
  https://theygotacquired.com/content/milk-road-acquired-by-bitfo/
- Superhuman AI: 購読100万超(本人発表)・人間8人+AIツール6種・広告枠完売 〔自称+報道〕
  https://www.thetilt.com/content-entrepreneur/superhuman-ai-content-business
- The Rundown AI: 2年で購読200万・2024年売上$300万(Forbes)・完全無料+広告・講座モデル 〔報道〕
  https://www.forbes.com/profile/rowan-cheung/
- 404 Media: 記者4人×$1,000出資・「人間が書く」を看板に8ヶ月で黒字化 〔報道〕
  https://www.niemanlab.org/2024/02/six-months-in-journalist-owned-tech-publication-404-media-is-profitable/

### 失敗事例(教訓の型)
- **隠す**: Sports Illustrated=AI偽記者(偽顔写真・偽経歴)暴露→CEO解任 〔報道〕
  https://futurism.com/sports-illustrated-ai-generated-writers
- **検品なし量産**: CNET=AI記事の半数超に訂正→停止 〔報道〕/ AI生成2.2万ページで検索流入ほぼゼロ 〔当事者公開〕
  https://news.yahoo.com/cnet-pauses-ai-written-articles-172500603.html / https://tailride.so/blog/google-penalty-22000-ai-pages
- **プラットフォーム依存**: Facebook動画ピボット(再生数60-80%過大計上→事業崩壊) 〔報道〕/ Medium報酬制度改変 〔当事者報告〕
  https://slate.com/technology/2018/10/facebook-online-video-pivot-metrics-false.html
- 読者感情(Reuters Institute 2026): 「主にAI製ニュース」に54%が不快感・信頼20%。**「人間主体+AI補助」なら許容34%** 〔調査機関公式〕
  https://reutersinstitute.politics.ox.ac.uk/digital-news-report/2026/dnr-executive-summary

## 4. 法務・レピュテーション(守り部向け)

- 「簡単に稼げる」系情報商材はSNS勧誘起点の消費者トラブルとして国民生活センター・消費者庁・東京都が継続的に注意喚起(若年層で相談増) 〔公式/一次・行政〕
  https://www.kokusen.go.jp/soudan_topics/data/infoproducts.html / https://www.caa.go.jp/policies/policy/consumer_policy/caution/caution_036/
- 「note×Xで稼ぐ方法」型コンテンツ自体がnoteのBAN攻防の最前線ジャンル(§1規約参照)。**ミカタは収益保証型・稼ぎ方勧誘型の記事を作らない**(運営計画v3の編集方針)

## 5. 統合的な示唆(3系統リサーチの一致点)

1. **AIは「名乗って検品」が生存条件**: 隠した事例は全滅(SI・CNET)。成功例はAI裏方+人間署名か、逆張りの人間宣言
2. **ニッチほど転換率が高い**(4-10% vs 大衆1-2%)。狭さはハンデでなく構造的優位
3. **無料は惜しみなく、有料は編集・整理・研究に**(Tangle 16%)。隠す量と売上は比例しない
4. **Xは集客装置・収益はストック媒体(note/LINE/メール)へ**: X収益分配は柱にならない。リンクは本文に貼らない
5. **買うのはフォロワーではなく検索・SNS経由の非フォロワー**(note公式分析+個別報告の一致点)。実用ノウハウ×1,800円帯が売れ筋
6. **単一プラットフォーム依存が最大の死因**。読者接点の自己保有(LINE・メール)と収益分散が生存者の共通項
7. **ゼロからnote単体で月30万級の検証可能事例は未発見**。既存資産(B2B販路・自社メディア・LINE基盤)との合算設計が現実解

## 6. 採用・人手不足(2026-08-04追加リサーチ・記事07の正本)

- 中小企業の68.0%が人手不足(日商・東商2024年調査、調査開始以来最大) 〔公式/一次〕 https://j-net21.smrj.go.jp/news/hgc8pd000001r322.html
- 人手不足倒産2025年度441件で過去最多・約75%が従業員10人未満(TDB) 〔公式/一次〕 https://www.tdb.co.jp/report/economic/20260409-laborshortage-br25fy/
- 沖縄の有効求人倍率1.1倍前後・福祉2.68倍/建設2.27倍と職種偏在(沖縄労働局) 〔公式/一次〕 https://jsite.mhlw.go.jp/okinawa-roudoukyoku/jirei_toukei/kyujin_kyushoku.html
- 採用コスト相場: 新卒93.6万円/中途103.3万円(リクルート就職白書) 〔公式/一次〕
- 米Klavon's: 時給$15化で1週間に応募1,000件超・16枠即充足 〔報道〕 https://www.wpxi.com/news/top-stories/pittsburgh-ice-cream-shop-raises-salaries-has-more-than-1000-applicants/6BGKVR2JPJFZNAQWXWISIWGOXM/
- 米Chick-fil-Aフランチャイズ: 週3日勤務制で1週間に応募420件・管理職定着100%(当事者申告) 〔報道+自称〕 https://fortune.com/2022/11/02/work-three-days-full-time-hours-chick-fil-a-move-3-day-schedule-gets-429-applications-in-week/
- 英週休3日実証(61社2,900人・6ヶ月): 離職57%減・バーンアウト71%減・92%継続(参加は自己選抜) 〔公式/一次〕 https://www.4dayweek.com/uk-pilot-results
- 元湯陣屋: 週休3日+DXで離職率33%→4%・年商2.9億→7億超 〔報道〕 https://forbesjapan.com/articles/detail/74452
- HILLTOP: 「夜勤なし・ルーチンはロボット」で新卒枠に年約1,000人エントリー(同社によれば) 〔自称〕 https://keikakuhiroba-mfi.com/archives/12041
- RJP(現実的職務予告)メタ分析: 事前開示で自発的離職が有意に低下(Phillips 1998・40研究) 〔学術/一次〕 https://journals.aom.org/doi/10.5465/256964 / 離職36%減推計 https://www.qic-wd.org/umbrella-summary/realistic-job-previews / 主経路は「正直さの知覚」(Earnest 2011) https://onlinelibrary.wiley.com/doi/abs/10.1111/j.1744-6570.2011.01230.x
- リファラル採用: 紹介経由は離職確率10〜30%低い(QJE 2015・9社実データ) 〔学術/一次〕 https://academic.oup.com/qje/article-abstract/130/2/805/2331590
- 入社後ギャップ約79%・筆頭は仕事内容 〔報道〕 https://www.hrpro.co.jp/trend_news.php?news_no=2276 / 中途の最多離職時期は入社3ヶ月未満(エン2024) 〔公式/一次〕 https://corp.en-japan.com/newsrelease/2024/39630.html
- 厚労省「採用と定着 成功事例集」(中小20社・無料) 〔公式/一次〕 https://www.mhlw.go.jp/stf/newpage_38019.html ※個社数値はPDF原本未照合

## 7. 値上げ・価格転嫁(2026-08-04追加リサーチ・記事08の正本)

- 転嫁率: 中企庁53.5%(2025年9月) 〔公式/一次〕 https://www.meti.go.jp/press/2025/11/20251128002/20251128002.html / TDB39.4%(過去最低) https://www.tdb.co.jp/report/economic/20250828-pricepass-on202507/ / TSR57.1%。**調査主体で数値が違うため併記し「満額転嫁できていない」のみ断定**
- 九州・沖縄36.9%(2022年以来最低) 〔一次+報道〕 https://www.nikkei.com/article/DGXZQOJC126UA0S5A910C2000000/ / コザ信金191社: 原材料転嫁5割未満33.4% 〔報道〕 https://www.okinawatimes.co.jp/articles/-/1876630
- ガリガリ君(2016年60→70円): お詫びCM・値上げ月に前年比約+10% 〔報道〕 https://xtrend.nikkei.com/atcl/contents/18/00151/00037/
- うまい棒(2022年10→12円): 「なくなっちゃうほうが、悲しいから」で感謝優勢 〔報道〕 https://president.jp/articles/-/86513?page=1
- QBハウス(2019年+11%): 客数減は会社想定を大きく下回り増収継続 〔報道〕 https://biz-journal.jp/2019/10/post_121930.html
- Amazon Prime(2014年$79→$99): 特典拡充同時実施で更新率は15ヶ月で回復・値上げ前超え 〔報道(CIRP)〕 https://www.fool.com/investing/2016/06/01/amazon-prime-improves-its-customer-retention-rate.aspx
- 鳥貴族(2017年280→298円): 客数10ヶ月連続減・営業利益予想37%下方修正。「280円均一」がブランドの核だった 〔報道〕 https://maonline.jp/articles/torikizoku_20180921 / https://gendai.media/articles/-/64293
- Netflix(2011年実質60%値上げ+分割): 3ヶ月で80万人減・株価7割下落 〔報道〕 https://techland.time.com/2011/10/24/netflix-loses-800000-subscribers-after-price-hike-qwikster-debacle/
- ステルス値上げ(告知なし減量)は告知値上げより信頼毀損が大きい 〔報道〕 https://xtrend.nikkei.com/atcl/contents/18/01199/00002/
- 学術: コスト由来の値上げは公正と受容・便乗は82%が不公正(Kahneman et al. 1986雪かきスコップ実験) 〔学術/一次〕 https://www.researchgate.net/publication/4900848_Fairness_As_a_Constraint_on_Profit_Seeking_Entitlements_In_The_Market / 顧客満足が値上げ耐性を作る(Homburg 2005) https://journals.sagepub.com/doi/abs/10.1177/0092070304269953 / 松竹梅=妥協効果(Simonson 1989) https://academic.oup.com/jcr/article-abstract/16/2/158/1800431
- B2B交渉の後ろ盾: 労務費転嫁指針(内閣官房・公取委2023) 〔公式/一次〕 https://www.jftc.go.jp/houdou/pressrelease/2023/nov/231129_roumuhitenka.html / 価格交渉ハンドブック(中企庁) https://www.chusho.meti.go.jp/keiei/torihiki/pamflet/kakaku_kosho_handbook.pdf

## 8. 事業承継(2026-08-04追加リサーチ・記事09の正本)

- 後継者不在率: 全国50.1%・沖縄61.0%(過去最低だが全国6位。2016年は86.2%で全国ワースト1位)(TDB2025) 〔公式/一次+報道〕 https://www.tdb.co.jp/report/economic/20251121-successor25y/ / https://www.okinawatimes.co.jp/articles/-/1735655
- 休廃業・解散2025年6万7,210件で3年連続最多・**直前期黒字が49.1%**(TSR。"儲かっているのに廃業"の直訳ではない点注意) 〔公式/一次〕 https://prtimes.jp/main/html/rd/p/000000025.000126976.html
- 後継者難倒産533件・うち代表者の病気死亡起因が4割超(TDB2025年度) 〔公式/一次〕 https://www.tdb.co.jp/report/bankruptcy/aggregation/20260408-bankruptfy2025/
- 承継準備5〜10年・60歳頃着手を国が明記(事業承継ガイドライン) 〔公式/一次〕 https://www.chusho.meti.go.jp/zaimu/shoukei/download/shoukei_guideline.pdf
- 沖縄実例: 花ぐすく香華堂(創業50年余の惣菜)→運送業沖縄SEIWAへ第三者承継・従業員全員引継ぎ(県センター+沖縄公庫) 〔公式/一次〕 https://www.okinawakouko.go.jp/newsrelease/1749531948/
- 事業承継・引継ぎ支援センター: 2024年度成約2,132件・後継者人材バンク106件で過去最高 〔公式/一次〕 https://www.smrj.go.jp/press/2025/f7mbjf000000dnpt-att/20250530_press01.pdf
- 中川政七商店: 300年で初の親族外承継・在任中に年商12億→57億 〔報道〕 https://president.jp/articles/-/96237
- Bob's Red Mill: ESOPで従業員に会社を贈与・従業員200→600人・売上過去最高 〔報道〕 https://www.forbes.com/sites/christophermarquis/2024/05/22/bobs-red-mill-securing-the-future-through-employee-ownership/
- Teamshares: 引退オーナーから80社超買収→従業員保有80%へ移行モデル 〔報道〕 https://techcrunch.com/2023/08/24/this-venture-backed-startup-has-quietly-bought-more-than-80-mom-and-pop-shops/
- サーチファンド: Stanford追跡(681本)IRR35.1%・ROI4.5倍 〔公式/一次〕 https://cdn.prod.website-files.com/6455268783d6938b9451ea80/669fbcb3e5f07cc9a6093751_StanfordGSB_Study_2024.pdf / 日本初は山口キャピタル(2019) https://yamaguchi-capital.co.jp/search-fund/
- relay(オープンネーム承継公募): 2025年コザ信金と提携=沖縄金融機関初 〔報道〕 https://www.okinawatimes.co.jp/articles/-/1761862
- BizBuySell2025: 売却価格中央値$35万・成約期間中央値170日 〔公式/一次(自社集計)〕 https://www.bizbuysell.com/blog/2025-year-in-review/
- 失敗: 一澤帆布(2通の遺言で兄弟裁判・ブランド分裂) https://ja.wikipedia.org/wiki/一澤帆布工業 / ルシアンHD(悪質買い手・30社近く) 〔報道〕 https://diamond.jp/articles/-/349818 / 国の対応=中小M&Aガイドライン第3版+登録制度(取消事例あり) https://www.meti.go.jp/press/2024/08/20240830002/20240830002.html / https://ma-shienkikan.go.jp/

## 9. 観光・インバウンド×地方(2026-08-04追加リサーチ・記事10の正本)

- 2025年: 訪日4,268万人(JNTO)・消費9兆4,559億円(観光庁)ともに過去最高 〔公式/一次〕 https://www.jnto.go.jp/news/press/20260121_monthly.html / https://www.mlit.go.jp/kankocho/news02_00071.html
- 外国人延べ宿泊: 地方部+19.1%は三大都市圏+5.1%の約4倍 〔公式/一次(観光庁統計)〕 https://www.mlit.go.jp/kankocho/tokei_hakusyo/shohidoko.html
- 高付加価値旅行者(100万円以上/回)は訪日客の約1%で消費の11.5% 〔公式/一次〕 https://www.mlit.go.jp/kankocho/news03_000235.html / モデル11地域に「沖縄・奄美」選定 https://www.travelvoice.jp/20230329-153200
- 沖縄: 2025年度入域1,093万人で過去最多。2025年11月以降の中国便欠航を台湾・韓国でカバー=市場分散の実証 〔報道(県発表)〕 https://www.okinawatimes.co.jp/articles/-/1826517
- メーカンポン村(タイ・人口数百人): 5世帯ホームステイ→村収入の9割が観光・受入19軒 〔公式/一次+報道〕 https://mekongtourism.org/baan-mae-kampong-exploring-a-pioneering-cbt-project-in-thailand/ / https://www.nationthailand.com/in-focus/30374699
- フェロー諸島Heimablídni: 農家・漁師の自宅夕食1人45ユーロ〜(政府観光局公認) 〔公式/一次〕 https://visitfaroeislands.com/en/see-do/activities/dining/heimablidni
- カイコウラ: マオリ5家族が自宅担保で創業→町全体で年約100万人・2,800万NZドル(※1社の数字ではない) 〔公式/一次(IWC)〕 https://wwhandbook.iwc.int/en/case-studies/new-zealand-kaikoura
- Walk Japan: 約62万円の歩く旅・2025年6,830人 〔報道〕 https://president.jp/articles/-/115833?page=2 / 堺の包丁研ぎ: 2.6万円×年2,000人 https://yamatogokoro.jp/column/experience-report/56893/ / KURABITO STAY: 冬の閑散期に2泊3日8.8万円(JNTO事例化) https://www.jnto.go.jp/projects/regional-support/resources/3930.html
- 城崎温泉: 小規模家族経営×欧米豪FIT特化で外国人宿泊6年で約45倍(2011年比・豊岡市集計) 〔報道〕 https://yamatogokoro.jp/inbound_case/27839/
- 失敗: 鬼怒川温泉(団体依存・価格競争の崩壊) https://ja.wikipedia.org/wiki/鬼怒川温泉 / OTA実質手数料15〜20%超 〔業界コラム〕 https://miyako.com/aio/articles/ota-cost-calculator/ / 京都オーバーツーリズム(宿泊税最高1万円へ) https://www.tokyo-np.co.jp/article/383849

## 10. 中小のAI導入実務(2026-08-04追加リサーチ・記事11の正本)

- 中小のAI導入率20.4%(中小機構2026) 〔公式/一次・本文未照合〕 https://www.smrj.go.jp/research_case/questionnaire/fbrion0000002pjw-att/202603_AI_point.pdf / 大企業43.3% vs 中小23.4%(TSR) https://www.tsr-net.co.jp/data/detail/1202766_1527.html
- **九州・沖縄: 活用35.9%・効果実感90.7%**(TDB2026年3月・沖縄向けフック最有力) 〔公式/一次・本文未照合〕 https://www.tdb.co.jp/report/economic/20260528-genai-kyusyu/
- 活用しない理由1位「業務がイメージできない」63.4%(中小企業白書2026) 〔公式/一次・本文未照合〕 https://www.chusho.meti.go.jp/pamflet/hakusyo/2026/PDF/chusho/00Hakusyo_zentai.pdf
- 失敗調査: Gartner「30%がPoC後放棄」 〔公式/一次〕 https://www.gartner.com/en/newsroom/press-releases/2024-07-29-gartner-predicts-30-percent-of-generative-ai-projects-will-be-abandoned-after-proof-of-concept-by-end-of-2025 / MIT「95%が測定可能なリターンなし」 〔報道〕 https://www.forbes.com/sites/jasonsnyder/2025/08/26/mit-finds-95-of-genai-pilots-fail-because-companies-avoid-friction/ / TDB課題1位「人材・ノウハウ不足」54.1% https://www.tdb.co.jp/report/economic/2rwpbngj_lop/
- 成功: 岡田研磨(白書掲載・月530時間削減) 〔公式/一次・本文未照合〕 https://digiwith.smrj.go.jp/cocoapp/info/feature/hakusyo202604.php / 旭鉄工(IoT年4億円削減+生成AIで横展開) 〔報道〕 https://monoist.itmedia.co.jp/mn/articles/2307/11/news076.html / QuickBooks記帳で月12時間節約(Intuit自称) https://quickbooks.intuit.com/r/bookkeeping/ai-bookkeeping-benefits/
- Klarna: AIが700人分処理と発表→品質面で人間対応を再強化の揺り戻し 〔公式/一次+報道〕 https://www.klarna.com/international/press/klarna-ai-assistant-handles-two-thirds-of-customer-service-chats-in-its-first-month/ / https://www.twig.so/blog/klarna-ai-customer-support-efficiency
- 公的支援(存在のみ・詳細は公募要領で要確認): デジタル化・AI導入補助金 https://it-shien.smrj.go.jp/ / 中小企業省力化投資補助金 https://shoryokuka.smrj.go.jp/

## 11. 未確認・要再調査リスト(記事に使う前に追加照合)

- Milk Road売却額 / Superhuman AIの正確な売上 / Xリンクデブーストの正確な減衰率 / note有料記事の価格上限拡大(5万→10万円説) / beehiiv「State of Paid Newsletters 2026」(bot遮断で未照合) / 大原千鶴氏の会員数(出典間齟齬)
- 中小企業白書2026・中小機構AI調査・TDB九州沖縄版・商工中金調査の各数値(リサーチ環境から本文PDF未照合。記事07・11の公開前に原文照合必須)
- 厚労省「採用と定着」事例集の個社数値(PDF 403で未照合) / QBハウス値上げ後の客数減少率の一次数値 / M&A後の雇用維持率の白書原典
