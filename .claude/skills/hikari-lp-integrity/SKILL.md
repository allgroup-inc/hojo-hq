---
name: hikari-lp-integrity
description: "hikari-lp(回線診断LPの配信リポジトリ)でLPを追加・編集・公開するときに必ず使う。FORM_ENDPOINT未設定時に偽の完了画面を出さない仕様と、設計ドキュメントの置き場所ルールを守らせる。"
---

# LP配信インテグリティ(hikari-lp)

hikari-lp(GitHub Pages で公開する回線診断LP)で LP を追加・編集・公開するときは、
README のルールに従う。

## 守るルール

1. **偽の完了画面を出さない**: `FORM_ENDPOINT`(Power Automate「HTTP要求の受信時」トリガーURL)が
   未設定の間はリードが1件も届かない。未設定時は **送信を中止し、偽の完了画面を出さない仕様** を必ず維持する。
   - LP追加時は `index.html` 冒頭の `TODO(必須)` を検索し、`FORM_ENDPOINT` を設定する。
2. **戦略・設計ドキュメントはここに置かない**: 設計は非公開リポジトリ `allgroup-inc/hikari-hq` にある。
   このリポジトリ(公開)には戦略・数値・設計を置かない(公開リポジトリに機密を混ぜない)。
3. 公開URLは `https://allgroup-inc.github.io/hikari-lp/lp/<LP_ID>/`。LP_ID 構造を崩さない。

## LP追加/編集の手順

1. `lp/<LP_ID>/` を作り、`index.html` 冒頭の `TODO(必須)` を全て埋める(特に `FORM_ENDPOINT`)。
2. フォーム送信失敗時に成功画面を出していないか確認する(送信中止=正しい挙動)。
3. エリア外・提供対象外の訴求になっていないか確認する(hikari-hq のエリア厳守と整合)。
4. 公開前に、機密・戦略メモを誤って含めていないか確認する。
