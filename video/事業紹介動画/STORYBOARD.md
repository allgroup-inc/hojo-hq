---
format: 1920x1080
duration: 86s
message: "沖縄企業のミカタは、締切を見逃さないための補助金・助成金情報とLINE登録を届ける"
arc: Hook → Problem → Product intro → Proof → Benefit(CTA準備) → Branding → CTA
audience: 沖縄の中小企業経営者
mode: autonomous
---

## Video direction

- **palette system** — frame.md(blue-professionalをブランドリマップ): canvas #FFFFFF、ink/primary #00335C(見出し・キーナンバー・アクセント下線)、accent #F88800(強調・グロー・アイコン)。tinted card = primaryの淡色フィル。純黒/純白は避け、ink/canvasのトーンで統一。
- **motion grammar + reveal model** — long-tail power3イーズを既定。各フレームはVOの区切り(読点・意味の切れ目)ごとに1ウィンドウ、t=0では最初のVOフレーズが話す内容だけを出し、以降のピースはVOがそれを言う瞬間に出す(前詰めしない)。保持中は微細なjitterのみ可、レイジーな呼吸アニメーションはしない。
- **rhythm / held-frame allocation** — Frame 5(ブランド)とFrame 3末尾(信頼バッジ)を意図的な静止ビート(held beat)として配置し、情報フレーム(2,3,4)の後にリズムの緩急をつける。
- **negative list** — ナビバー・フッター・スクロールバー・実際のブラウザchrome・実在のロゴ画像(未確定のためテキストロゴのみ)・根拠のない紫青グラデーションの「AI」演出・実データのQRコード(未確定のためダミー枠)。フロントロード(t=0で全部出す)とスクリーンセーバー(各要素が無関係に浮遊し続ける)の両方を禁止。
- **caption band** — 画面下部17%はキャプション帯として空けておく。全フレーム共通。

## Frame 1 — 見逃しの痛み(フック)

- status: outline
- src: compositions/frames/01-hook.html
- duration: 12.352s
- transition_in: cut
- scene: カレンダーに×印、困った表情を連想させるシンプルな図形アニメーション
- voiceover: "補助金の締切を、知らずに逃した経験はありませんか？"
- blueprint: kinetic-type-beats
- role: hook

問いかけで始める。共感を得てから解決策(サービス)を提示する構成の起点。誇張・煽りは避け、実感のある問いにする。

blueprint: kinetic-type-beats(Adapt) — signature moveの「語ごとの入れ替わり」は維持しつつ、1フレーズのみに簡略化。

Scene 1 (0.0–5.0s): 「補助金の締切を、」がcanvas中央に太字(ink)で入る。Centered、画面の~50%。背景にカレンダーのシルエット+×マークが30%の暗さでフェードイン(missed-deadlineのモチーフ、主役を奪わない程度)。
Scene 2 (5.0–12.352s): 1行目が上段へ落ち着き、VOが続く語を話すタイミングで「知らずに逃した経験はありませんか？」が語単位で中央下に現れる(kinetic-type-beatsのsignature move)。最後の語「ありませんか？」で背景の×マークがaccent(#F88800)で一度だけグロー、その後は静止して残り約2秒保持。

## Frame 2 — サービス紹介

- status: outline
- src: compositions/frames/02-product-intro.html
- duration: 16.853s
- transition_in: crossfade
- scene: サイトのトップ画面を模したモックアップ、制度カードが並ぶ様子
- voiceover: "沖縄企業のミカタが、補助金情報を毎日自動でお届けします。"
- role: product_intro

実サイトのキャプチャは使わず、モックUIとして新規デザインする(BRIEF.md: no-capture)。

blueprint: compose — サービス名ワードマーク→制度カードスタックの2段構成。実サイトキャプチャは使わない。
focal: モック制度カード3枚(プレースホルダー名称「制度A/B/C」、実データ・実ロゴなし)
roles: サービス名ワードマーク = cutout(前景) · 制度カードスタック = cutout(前景) · 背景 = canvas無地(background)

Scene 1 (0.0–5.5s): 「沖縄企業のミカタ」のワードマークが画面上部中央に settle、accentの下線が左から右へ描かれる。Centered。
Scene 2 (5.5–11.5s): VOが「補助金情報を毎日自動で」を話すタイミングで、モック制度カード3枚(角丸・primaryの淡色フィル、プレースホルダー名称、小さな更新アイコン付き)が右下からasymmetric 60/40のレイアウトへ上から順にstagger-revealする。
Scene 3 (11.5–16.853s): 「お届けします。」でカードスタックが落ち着き、小さな矢印/チェックのモチーフがnudge curveで一度前に出て静止、残り約2秒保持。

## Frame 3 — 正確性の裏付け

- status: outline
- src: compositions/frames/03-proof.html
- duration: 15.061s
- transition_in: crossfade
- scene: 制度カード一覧のモックアップ、チェックマークのアニメーション
- voiceover: "掲載情報は原文を確認して公開しているので安心です。"
- role: feature_showcase

「常時◯件」等の固定数値は書かない(hojo-accuracy-checkルール)。信頼性(原文照合)を視覚的に表現する。

blueprint: compose — Frame 2のカードスタックを継続し、原文照合のチェックスイープで信頼性を可視化。
focal: Frame 2からのカードスタック(継続)、各カードの「原文リンク」チップ
roles: カードスタック = cutout(前景・継続) · チェックスイープ = supporting · 確認済みバッジ = cutout(climax)

Scene 1 (0.0–5.0s): Frame 2のカードスタックを引き継ぎ、各カードの脇に小さな「原文リンク」チップが現れる。rule-of-thirds、カード群は左60%。
Scene 2 (5.0–11.0s): VOが「原文を確認して公開しているので」を話す間、チェックマーク(虫眼鏡アイコン)が左から右へカードを順にスイープし、通過したカードのチップがaccentで点灯する(VOのペースに合わせて1枚ずつ)。
Scene 3 (11.0–15.061s): 「安心です。」で全チップが点灯済みとなり、汎用の盾+チェックのバッジ(実在の認証を示唆しない、単なる視覚モチーフ)が中央小さめにsettleして静止、残り約2秒保持。

## Frame 4 — LINE登録のベネフィット

- status: outline
- src: compositions/frames/04-benefit.html
- duration: 13.653s
- transition_in: crossfade
- scene: LINE通知のモックアップ、スマホ画面フレーム
- voiceover: "LINE登録で、締切の約1か月前からお知らせが届きます。"
- role: benefit_highlight

締切表現は「約1か月前から」で固定(hojo-deadline-alertルール、「7日前」表現は禁止)。

blueprint: compose — スマホモック上でLINE登録→カレンダー強調→通知の3段リビール。
focal: スマホモック、カレンダーストリップ(約1か月前を示すハイライト、実日付なし)、通知バブル
roles: スマホモック = cutout(前景) · カレンダーストリップ = supporting · 通知バブル = cutout(climax)

Scene 1 (0.0–4.5s): スマホモックフレームが下から中央にsettle、画面上部に緑系の「LINE登録」チップが現れる。Centered。
Scene 2 (4.5–9.5s): VOが「締切の約1か月前から」を話すタイミングで、スマホ画面にカレンダーストリップが描かれ、締切日(汎用・実日付なし)の約1か月前の範囲がaccentでハイライトされる。asymmetric、スマホ左40%・カレンダー詳細右60%。
Scene 3 (9.5–13.653s): 「お知らせが届きます。」で通知バブル(汎用文言、実内容の断定なし)がロック画面風にスライドイン、settleして静止、残り約2秒保持。

## Frame 5 — ブランド

- status: outline
- src: compositions/frames/05-branding.html
- duration: 14.933s
- transition_in: crossfade
- scene: ロゴ+タグライン表示(ネイビー×オレンジ配色)
- voiceover: "『補助金・助成金の情報で、沖縄の企業にあかりを。』"
- blueprint: kinetic-type-beats
- role: branding

テキストロゴ「沖縄企業のミカタ」を使用(ロゴ画像ファイルは未確定)。

blueprint: kinetic-type-beats(Reproduce) — ワードマーク→タグラインの語単位リビール、signature moveを維持。
focal: ワードマーク「沖縄企業のミカタ」、タグライン全文
roles: ワードマーク = cutout(前景) · タグライン = cutout(climax) · 背景 = canvas無地

Scene 1 (0.0–4.0s): canvasが落ち着いた無地(#FFFFFF)になり、ワードマーク「沖縄企業のミカタ」が画面上部中央にsettle、accentの下線が描かれる。Centered。
Scene 2 (4.0–11.0s): VOがタグラインを話す間、「『補助金・助成金の情報で、沖縄の企業にあかりを。』」がワードマーク下に語/フレーズ単位でリビール(kinetic-type-beats)。キーワード「あかりを」でaccentの柔らかいグローが一度ブルームする(ブランドの「あかり」モチーフに呼応)。
Scene 3 (11.0–14.933s): ワードマーク+タグライン全体がsettleし、静止したロックアップとして保持(意図的なheld beat、追加のモーションなし)。

## Frame 6 — CTA

- status: outline
- src: compositions/frames/06-cta.html
- duration: 13.013s
- transition_in: crossfade
- scene: LINE登録ボタンとQRコードのプレースホルダー
- voiceover: "今すぐLINE登録して、沖縄企業のミカタで検索を。"
- role: cta

CVはLINE登録の1点のみ。他の導線・ボタンを追加しない。QRコードは実データ未確定のためダミー枠で代用。

blueprint: compose — CTAボタンのspring-pop→ワードマーク+QRダミー枠の静止レイアウト。
focal: 「友だち追加」CTAボタン(LINE系グリーン)、QRコードのダミー枠(角丸プレースホルダー)
roles: CTAボタン = cutout(climax) · ワードマーク = supporting · QRダミー枠 = supporting

Scene 1 (0.0–5.5s): 「友だち追加」を模したCTAボタンがspring-pop entrance(signature move)で中央にスケールイン、一度だけ軽くパルスして視線を集める。Centered。
Scene 2 (5.5–13.013s): VOが「沖縄企業のミカタで検索を。」を話すタイミングで、ワードマークとQRコードのダミー枠(実データなし、角丸プレースホルダー)がボタン脇にasymmetric 60/40で並び、残り約2.5秒は静止(他の導線・ボタンは一切追加しない=CV単一ルール)。
