# OpenAI 音声文字起こし(Speech-to-Text)

顧客の声(商談録音・電話・インタビュー等)を文字起こしし、`voice-of-customer-analysis`
スキル経由で `customer-research`(marketingskills)に渡して分析するための連携。

## なぜOpenAIか(技術的な比較結果)

2026年時点での比較(1分あたり概算):
| 提供元 | 目安コスト | 備考 |
|---|---|---|
| **OpenAI(whisper-1 / gpt-4o-transcribe)** | 約0.5〜0.9円/分 | 最安・シンプル。今回採用 |
| Google Cloud Speech-to-Text | 約2円/分 | やや割高 |
| AssemblyAI | 約0.15〜0.45ドル/時間 | 話者分離・感情分析等の追加機能込みなら選択肢 |

60分の商談録音でも数十円程度。Anthropic(Claude)自体は音声文字起こしAPIを提供していないため、
別ベンダー(OpenAI)のAPIを使う。これは技術的に最も合理的な選択であり、他意はない。

## セットアップ

1. https://platform.openai.com/ でアカウント作成 → **API keys** → 新規キー発行
2. 環境変数 `OPENAI_API_KEY` に設定(詳細は `../SETUP.md`)
3. 支払い方法の登録が必要(従量課金・月額固定費なし)

## 使い方

```bash
# 動作確認(APIを叩かず送信内容だけ表示)
node .claude/tools/clis/openai-transcribe.js transcribe 録音.mp3 --dry-run --language ja

# 実際に文字起こし
node .claude/tools/clis/openai-transcribe.js transcribe 録音.mp3 --language ja > 文字起こし結果.json
```

### オプション
| オプション | 説明 |
|---|---|
| `--model` | `whisper-1`(標準)または `gpt-4o-transcribe`(高精度・やや高コスト)。省略時 `whisper-1` |
| `--language` | 言語コード(`ja`推奨。省略すると自動判定だが日本語では明示推奨) |
| `--prompt` | 固有名詞・業界用語のヒントを渡せる(例:「沖縄企業のミカタ、NURO光、家計の見直しやさん」) |
| `--format` | `verbose_json`(既定・タイムスタンプ付き) / `text` / `srt` / `vtt`(字幕形式。動画のテロップにも流用可) |

対応音声形式: mp3, mp4, mpeg, mpga, m4a, wav, webm(25MBまで。超える場合は分割が必要)

## プライバシー・法務上の注意(顧客の声を扱うため)

- 顧客の同意なく録音・分析しない。**録音の告知・同意取得は録音者側の責任**(このツールは処理するだけ)
- 文字起こし結果に個人情報(氏名・電話番号・住所)が含まれる場合、`customer-research`等に渡す前に
  **匿名化・仮名化を検討**する(kakei-hqの個人情報保護方針、hikari-hqのリード管理方針を参照)
- 音声ファイル・文字起こし結果をリポジトリにコミットしない(`.gitignore`推奨)
