# Frame packet: 06-cta

## Project inputs

- Project: /home/user/hojo-hq/video/事業紹介動画
- Design tokens: /home/user/hojo-hq/video/事業紹介動画/frame.md
- RULES_DIR: /root/.agents/skills/hyperframes-animation/rules

## Assigned storyboard block

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
