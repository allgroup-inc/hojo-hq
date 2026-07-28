# Frame packet: 02-product-intro

## Project inputs

- Project: /home/user/hojo-hq/video/事業紹介動画
- Design tokens: /home/user/hojo-hq/video/事業紹介動画/frame.md
- RULES_DIR: /root/.agents/skills/hyperframes-animation/rules

## Assigned storyboard block

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
