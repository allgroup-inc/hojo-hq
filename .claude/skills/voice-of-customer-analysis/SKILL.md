---
name: voice-of-customer-analysis
description: "顧客の声(商談録音・電話・インタビュー音声)を集めて文字起こし→分析し、LP・広告コピー・提供メニューの改善に反映するときに使う。「録音を分析して」「お客様の声を集める」「音声から示唆を出して」等で発動。OpenAI音声文字起こしAPI(.claude/tools)が必要。"
---

# 顧客の声の収集・分析(音声→文字起こし→示唆)

商談録音・電話・インタビュー音声を文字起こしし、`customer-research`(marketingskills)の
手法で分析して、コピー・LP・提供メニューの改善に使える示唆を引き出す。

## 前提

`.claude/tools/clis/openai-transcribe.js` を使う(`OPENAI_API_KEY` が必要。
未設定なら `.claude/tools/SETUP.md` を参照して発行する)。

## ワークフロー

### 1. 音声を文字起こしする
```bash
node .claude/tools/clis/openai-transcribe.js transcribe <音声ファイル> --language ja \
  --prompt "業界固有名詞のヒント(例: 沖縄企業のミカタ、NURO光、家計の見直しやさん)" \
  > 文字起こし_YYYYMMDD.json
```
- 対応形式: mp3/mp4/mpeg/mpga/m4a/wav/webm(25MBまで。超えるなら分割)
- `--format srt` にすると字幕形式で出力できる(`explainer-video-production` の動画テロップに転用可)

### 2. 個人情報を確認・マスキングする
文字起こし結果に氏名・電話番号・住所等が含まれていないか確認する。
含まれる場合、次のステップに渡す前に**匿名化・仮名化**する(「Aさん」「40代・世帯主」等に置換)。
このステップを飛ばさない(該当事業のprivacy方針・kakei-hq個人情報保護方針を参照)。

### 3. `customer-research` スキルで分析する
匿名化した文字起こしテキストを渡し、次の観点で分析させる:
- 顧客が実際に使った**生の言葉**(専門用語ではなく本人の表現) — コピーの語彙に反映する素材
- 繰り返し出てくる**不安・悩み・きっかけ**(Jobs to be done)
- 想定していなかった**反論・懸念点**(FAQ・打消し表示の材料)
- 決め手になった一言(CTA・訴求軸の裏付け)

### 4. 反映先を決めて渡す
分析結果は用途に応じて次のスキルへ引き継ぐ:
- LP・広告文言の言い回し改善 → `copywriting` / `ad-creative`
- コンバージョン導線の課題 → `cro`
- よくある反論への対処 → 各事業のFAQ・コンプライアンス系スキル(`kakei-compliance`等)
- 動画の台本素材 → `explainer-video-production`

## 品質・法務のポイント

- **同意なき録音・分析はしない**(告知・同意取得は録音者側の責任。このスキルは処理するだけ)。
- 音声ファイル・生の文字起こし結果・匿名化前データは**リポジトリにコミットしない**。
- 断定的な一般化をしない(1件の発言を「全顧客の声」として扱わない。件数・偏りを明記する)。

## 関連スキル
- `customer-research`(marketingskills) — 分析手法の本体
- `copywriting` / `ad-creative` / `cro` — 分析結果の反映先
- `explainer-video-production` — 字幕・台本への転用
