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

## 6. 未確認・要再調査リスト(記事に使う前に追加照合)

- Milk Road売却額 / Superhuman AIの正確な売上 / Xリンクデブーストの正確な減衰率 / note有料記事の価格上限拡大(5万→10万円説) / beehiiv「State of Paid Newsletters 2026」(bot遮断で未照合) / 大原千鶴氏の会員数(出典間齟齬)
