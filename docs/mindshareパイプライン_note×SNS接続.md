# Mindshareアービトラージ 6段パイプライン × 既存運用の接続表 — 2026-08-07

`.claude/skills/mindshare-arbitrage` の6段パイプラインを、既に動いている仕組みへ
対応づける(新しい仕組みは作らない。既存のゲートをそのまま使う)。

## 対応表

| 段階 | ミカタSNS | note編集部(ツヅルさん) |
|---|---|---|
| ① 発見 | 月1ネタ供給定例(docs/ネタ供給定例_月1last30days.md)+制度データ | 同左+tanpatsu_topics.json のお題キュー |
| ② レビュー(人間ゲート1) | ネタ帳から採用選定(SNS部→小柳さん) | お題のstatus遷移 pending→drafted の採否 |
| ③ 生成 | generate_sns.py / generate_carousel.py(フックはhook-writer準拠) | tanpatsu-draft.yml(毎月8日・22日に下書き自動生成) |
| ④ スライド化 | generate_images.py / カルーセル7枚組 | 見出し画像(assets/kekka/) |
| ⑤ 承認・投稿(人間ゲート2) | social-post承認ゲート(sns-approval・LINEプレビュー) | 小柳さんの公開承認→publish-record |
| ⑥ 分析・学習 | 週次レポ(Plausible/IG/FB)→次回の選定に反映 | note_kpi.json→週次レポnoteセクション |

## 翻訳の型(ミカタでの定番3方向)
1. **他県の補助金メディア・士業の発信(ニッチ)→ 沖縄の経営者の言葉(メインストリーム)**
2. **英語圏・大企業の事例(遠い)→ 沖縄の飲食・宿泊・小売の現場(近い)**
3. **国の公式文書(硬い)→「で、うちはいくら使えるの?」(やさしい翻訳=憲法トーン)**

## 守ること
- 人間が関わるのは②と⑤の2箇所だけ(それ以外は仕組みで回す)
- 丸パクリ禁止: 必ず自分の言葉への翻訳+価値の追加(補足・整理・沖縄の文脈)
- 事実(制度名・金額・締切)は原文照合(hojo-accuracy-check)、文面仕上げはhumanizer
