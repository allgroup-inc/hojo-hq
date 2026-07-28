# Frame packet: 03-proof

## Project inputs

- Project: /home/user/hojo-hq/video/事業紹介動画
- Design tokens: /home/user/hojo-hq/video/事業紹介動画/frame.md
- RULES_DIR: /root/.agents/skills/hyperframes-animation/rules

## Assigned storyboard block

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
