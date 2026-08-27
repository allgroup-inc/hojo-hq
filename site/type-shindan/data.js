/* 沖縄企業のミカタ 経営者タイプ診断(16タイプ) 診断データ v1
 * - 診断の「中身」(軸・質問・タイプ・推薦テーマ)はすべてこのファイルに集約する。
 *   文面の検証(検証部・守り部レビュー)はこのファイルだけ見ればよい。
 * - 採点・判定のエンジンは logic.js(汎用)。データを差し替えれば別の診断を作れる。
 * - コピーの規律: 制度の断定表現の禁止/締切・金額・要件を書かない/16タイプ性格診断の
 *   元ネタの商標名を出さない。詳細は tests/type-shindan.test.mjs が機械検査する。
 * - ブラウザ(window.TypeShindanData)/Node(module.exports)両対応のUMD形式。
 */
(function (global) {
  "use strict";

  // 推薦先はテーマ別ページ(毎日更新の募集中一覧)への内部リンクに限定する。
  // 制度名・金額・締切を診断コピーに書かないことで、正確性最優先ルールと両立させる。
  var THEMES = {
    setsubi: { path: "../themes/setsubi/", label: "設備投資" },
    it: { path: "../themes/it/", label: "IT・デジタル化" },
    shoene: { path: "../themes/shoene/", label: "省エネ・脱炭素" },
    koyou: { path: "../themes/koyou/", label: "雇用・人材" },
    sogyo: { path: "../themes/sogyo/", label: "創業" },
    shokei: { path: "../themes/shokei/", label: "事業承継・M&A" },
  };

  var AXES = [
    { id: "invest", label: "投資スタンス", letters: ["A", "M"],
      names: { A: "攻め", M: "守り" } },
    { id: "resource", label: "伸ばしたい資源", letters: ["H", "T"],
      names: { H: "ヒト", T: "しくみ・デジタル" } },
    { id: "direction", label: "成長の向き", letters: ["S", "U"],
      names: { S: "ソト(販路)", U: "ウチ(現場)" } },
    { id: "tempo", label: "進め方", letters: ["Q", "J"],
      names: { Q: "すぐ動く", J: "じっくり準備" } },
  ];

  // 各軸3問(奇数にして同点を出さない)。option.letter がその軸のどちらかを指す。
  var QUESTIONS = [
    { axis: "invest", text: "自由に使えるお金が100万円増えたら?",
      options: [
        { letter: "A", label: "新しい取り組みに投資する" },
        { letter: "M", label: "まずは手元に残して備える" },
      ] },
    { axis: "invest", text: "新しい事業のチャンスを見つけたとき",
      options: [
        { letter: "A", label: "多少リスクがあっても挑戦したい" },
        { letter: "M", label: "今の事業を固めるのが先" },
      ] },
    { axis: "invest", text: "会社の5年後を想像してワクワクするのは",
      options: [
        { letter: "A", label: "事業がぐんと広がっている姿" },
        { letter: "M", label: "無理なく安定して続いている姿" },
      ] },
    { axis: "resource", text: "会社の成長に必要なのは、どちらかといえば",
      options: [
        { letter: "H", label: "人を採る・育てる" },
        { letter: "T", label: "設備やITを整える" },
      ] },
    { axis: "resource", text: "業務の悩みを解決するなら",
      options: [
        { letter: "H", label: "頼れる人を増やす" },
        { letter: "T", label: "ツールや機械に任せる" },
      ] },
    { axis: "resource", text: "お金をかけるなら",
      options: [
        { letter: "H", label: "社員の待遇・研修・働きやすさ" },
        { letter: "T", label: "新しい設備・システム" },
      ] },
    { axis: "direction", text: "いちばん伸ばしたいのは",
      options: [
        { letter: "S", label: "新しいお客さま・販路" },
        { letter: "U", label: "今の仕事の質と効率" },
      ] },
    { axis: "direction", text: "まる1日空いたら仕事では",
      options: [
        { letter: "S", label: "営業・発信・人脈づくりに使う" },
        { letter: "U", label: "社内の改善・整理に使う" },
      ] },
    { axis: "direction", text: "うれしい報告はどっち?",
      options: [
        { letter: "S", label: "「新規のお客さまが増えました」" },
        { letter: "U", label: "「現場がスムーズに回ってます」" },
      ] },
    { axis: "tempo", text: "良さそうな制度を見つけたら",
      options: [
        { letter: "Q", label: "まず申し込み方法を調べてすぐ動く" },
        { letter: "J", label: "要件をじっくり読み込んでから決める" },
      ] },
    { axis: "tempo", text: "締切がある仕事は",
      options: [
        { letter: "Q", label: "勢いがあるうちに一気に片づける" },
        { letter: "J", label: "計画を立てて前もって進める" },
      ] },
    { axis: "tempo", text: "書類仕事は",
      options: [
        { letter: "Q", label: "正直、後回しにしがち" },
        { letter: "J", label: "早めに揃えておくと安心" },
      ] },
  ];

  // 進め方(Q/J)別の補助金との付き合い方アドバイス(締切3層ルール:「約1か月前から」表現で統一)
  var ADVICE = {
    Q: "行動の早さが武器。ただ、補助金は申請書類の準備に意外と時間がかかります。気になる公募を締切の約1か月前からLINEでお知らせを受け取っておくと、「気づいたら締切直前…」を防げます。",
    J: "準備力が武器。電子申請に使うgBizIDを早めに取っておくと、公募が始まった日から動けます。気になるテーマの公募開始と締切は、約1か月前からのLINEのお知らせでチェックできます。",
  };

  // 16タイプ。themes は THEMES のキー2つ(軸1と軸2から選定し、明示的に固定して検証部がレビューできる形にする)。
  var TYPES = {
    AHSQ: { name: "島の旗振りリーダー型", tagline: "人を巻き込み、新しい市場へ一番乗り",
      desc: "思い立ったら仲間を集めて動き出すタイプ。勢いと巻き込み力で、新しいお客さまを開拓していきます。",
      strength: "人望と行動力。チームの熱を上げるのが得意",
      caution: "走りながら考える分、事務まわりが置き去りになりがち",
      themes: ["setsubi", "koyou"] },
    AHSJ: { name: "構想プロデューサー型", tagline: "仲間と描いた計画で、事業を広げる",
      desc: "ビジョンを言葉にして人を集め、段取りを整えてから大きく打って出るタイプ。採用や販路の計画づくりが得意です。",
      strength: "構想力と計画性。人が集まる絵を描ける",
      caution: "計画を練り込みすぎて、動き出しが遅れることも",
      themes: ["setsubi", "koyou"] },
    AHUQ: { name: "現場チャレンジャー型", tagline: "現場の熱で、会社を強くする",
      desc: "現場の先頭に立って改善と挑戦を重ねるタイプ。社員と一緒に汗をかきながら、会社の足腰を鍛えます。",
      strength: "現場感覚と決断の速さ。社員との距離が近い",
      caution: "自分が動きすぎて、任せる仕組みづくりが後回しに",
      themes: ["setsubi", "koyou"] },
    AHUJ: { name: "人材育成ビルダー型", tagline: "人が育つ会社は、強くなる",
      desc: "腰を据えて人を育て、組織の力で成長を狙うタイプ。教育や評価の仕組みづくりに関心が高い経営者です。",
      strength: "育成力と粘り強さ。辞めない組織をつくれる",
      caution: "成果が出るまで時間がかかる打ち手が多く、短期の変化に乗り遅れることも",
      themes: ["setsubi", "koyou"] },
    ATSQ: { name: "スピード開拓者型", tagline: "道具を武器に、市場へ最速アプローチ",
      desc: "新しいツールやサービスをすぐ試し、販路開拓に活かすタイプ。デジタルの追い風に乗るのが上手です。",
      strength: "新しもの好きの行動力。試して学ぶのが速い",
      caution: "手を広げすぎて、使いこなす前に次へ行きがち",
      themes: ["setsubi", "it"] },
    ATSJ: { name: "戦略イノベーター型", tagline: "仕組みで勝つ道筋を、先に描く",
      desc: "市場と数字を見ながら、設備やデジタルへの投資で勝ち筋をつくるタイプ。攻めの投資も根拠から入ります。",
      strength: "分析力と投資判断。費用対効果に強い",
      caution: "検討が長引き、好機を逃すことがある",
      themes: ["setsubi", "it"] },
    ATUQ: { name: "即断メカニック型", tagline: "現場の困りごとは、道具で今すぐ解決",
      desc: "現場の非効率を見つけたら、機械やITでさっと解決するタイプ。省力化・自動化の話が大好物です。",
      strength: "課題発見と即実行。現場の負担をすぐ軽くできる",
      caution: "目の前の改善に集中して、全体設計が後回しになりがち",
      themes: ["setsubi", "it"] },
    ATUJ: { name: "未来設計エンジニア型", tagline: "5年後の現場を、いま設計する",
      desc: "生産性の底上げを見据えて、設備更新やシステム導入を計画的に進めるタイプ。長期目線の投資家です。",
      strength: "設計力と継続力。ぶれない投資計画を持てる",
      caution: "完璧な計画を待つうちに、現場の今の困りごとを見落とすことも",
      themes: ["setsubi", "it"] },
    MHSQ: { name: "ご縁つなぎ商人型", tagline: "紹介とご縁で、堅実に輪を広げる",
      desc: "大きな勝負より、人とのつながりで商売を広げるタイプ。フットワークが軽く、地域の顔が広い経営者です。",
      strength: "人脈と信頼。紹介が紹介を呼ぶ",
      caution: "ご縁頼みになり、仕組みでの集客づくりが手薄になりがち",
      themes: ["shoene", "koyou"] },
    MHSJ: { name: "信頼の番頭型", tagline: "手堅い信頼で、長いお付き合いを育てる",
      desc: "既存のお客さまを大切にしながら、確実な一歩ずつで販路を広げるタイプ。約束を守る堅実経営です。",
      strength: "誠実さと継続力。お客さまが離れない",
      caution: "慎重さゆえに、新しい層への打ち手が細くなりがち",
      themes: ["shoene", "koyou"] },
    MHUQ: { name: "チームの世話役型", tagline: "働く人が元気なら、会社は回る",
      desc: "社員の困りごとにすぐ手を打つタイプ。働きやすさを整えることが、会社の守りだと知っている経営者です。",
      strength: "気配りと初動の速さ。職場の空気をつくれる",
      caution: "目の前の人に手を取られ、数字の管理が後手になりがち",
      themes: ["shoene", "koyou"] },
    MHUJ: { name: "じっくり育て職人型", tagline: "急がば回れ。人と技を磨き続ける",
      desc: "技術と人材をこつこつ磨いて、揺らがない会社をつくるタイプ。派手さはなくても土台は誰より固い経営者です。",
      strength: "職人気質の質へのこだわり。長く選ばれる",
      caution: "現状維持が心地よく、変化のきっかけを逃しやすい",
      themes: ["shoene", "koyou"] },
    MTSQ: { name: "堅実チャレンジャー型", tagline: "小さく試して、確かめてから広げる",
      desc: "リスクは抑えつつ、新しい道具や売り方は素早く小さく試すタイプ。失敗しても傷が浅い挑戦の仕方を知っています。",
      strength: "小さく速い実験力。損切りも早い",
      caution: "小さな成功で満足し、広げる決断を先送りしがち",
      themes: ["shoene", "it"] },
    MTSJ: { name: "石橋マーケター型", tagline: "数字で確かめてから、確実に届ける",
      desc: "データと相場観で勝てる場所を見極めてから動くタイプ。無駄撃ちしない販促が持ち味です。",
      strength: "見極める目。費用を無駄にしない",
      caution: "確信が持てるまで動かず、様子見が長くなりがち",
      themes: ["shoene", "it"] },
    MTUQ: { name: "カイゼン推進型", tagline: "今日のムダを、今日なくす",
      desc: "毎日の業務のムダをすぐ直すタイプ。小さな改善の積み重ねで、利益体質の会社をつくります。",
      strength: "改善の目と実行力。コストに強い",
      caution: "細部の改善に没頭し、大きな一手の検討が後回しになりがち",
      themes: ["shoene", "it"] },
    MTUJ: { name: "土台固め設計士型", tagline: "備えあれば、島の台風にも負けない",
      desc: "省エネ・効率化・仕組み化で、何があっても揺らがない経営基盤を計画的に築くタイプ。守りの名手です。",
      strength: "リスク管理と設計力。不測の事態に強い",
      caution: "守りが厚い分、攻めどきのアクセルを踏みそびれることも",
      themes: ["shoene", "it"] },
  };

  var api = { THEMES: THEMES, AXES: AXES, QUESTIONS: QUESTIONS, TYPES: TYPES, ADVICE: ADVICE };
  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  } else {
    global.TypeShindanData = api;
  }
})(typeof window !== "undefined" ? window : globalThis);
