---
workflow: product-launch-video
flow: automation
storyboard: no
message: "沖縄企業のミカタは、締切を見逃さないための補助金・助成金情報とLINE登録を届ける"
destination: multi (website/YouTube embed, Instagram feed, LINE/Instagram Story・Shorts)
aspect: 1920x1080
language: ja
length: 60s
angle: pain-solution-proof-cta
---

## Intent

沖縄の経営者向けに、「沖縄企業のミカタ」というサービスの存在と価値を60秒で伝える宣伝(セル)動画。
問題提起(締切を見逃す)→解決(自動収集+わかりやすい整理)→裏付け(原文照合の正確性)→CTA(LINE登録)
→タグラインの順。トーンは「専門用語をやさしく翻訳する立ち位置」、誠実・信頼感重視。安っぽい/煽り
表現は避ける。

VO_MODE: verbatim — ナレーション原稿は `docs/事業紹介動画_台本v1.md` を一字一句そのまま使用する。
Capture mode: no-capture — 実サイト(https://allgroup-inc.github.io/hojo-hq/)はキャプチャしない。
イラスト/モックアップ調のビジュアルで構成する(現行サイトはブランド刷新前のため)。

## Assets

- docs/事業紹介動画_台本v1.md — 確定済みナレーション原稿(シーン1〜6、タイミング付き)
- ブランドカラー: ネイビー #00335C / オレンジ #F88800(CLAUDE.md 2026-07-22 小柳さん決裁)
- フォント: Meiryo(Web は Noto Sans JP)
- タグライン: 「補助金・助成金の情報で、沖縄の企業にあかりを。」

## Customizations

- 日本語ナレーション音声(TTS、落ち着いた女声、信頼感のあるトーン)
- 日本語字幕(キャプション)を必ず表示
- ロゴ画像は未確定のため、テキストロゴ「沖縄企業のミカタ」で代用
- マスターは 16:9(1920x1080)で構築。ビルド後に 1:1(Instagram feed)・9:16(Story/Shorts)の
  派生版を作成する(destinationが複数のため)

## Notes

- CVはLINE登録の1点のみ。動画内に他の外部リンク・CTAを追加しない
- 締切表現は「締切の約1か月前から」で統一。「7日前」等の表現は禁止(hojo-deadline-alertルール)
- 「常時150件以上」等、変動する実数値は本文に固定で書かない(hojo-accuracy-checkルール)
- 三名体制レビュー済み(2026-07-27、docs/事業紹介動画_台本v1.md 参照)。台本内容の変更は再レビュー対象
