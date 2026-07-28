# Frame packet: 04-benefit

## Project inputs

- Project: /home/user/hojo-hq/video/事業紹介動画
- Design tokens: /home/user/hojo-hq/video/事業紹介動画/frame.md
- RULES_DIR: /root/.agents/skills/hyperframes-animation/rules

## Assigned storyboard block

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
