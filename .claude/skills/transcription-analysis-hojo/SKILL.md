---
name: transcription-analysis-hojo
description: "KAKEHASHI・enLife営業の音声記録（Zoom Phone等）から、自動書き起こし→感情分析・顧客課題抽出→note記事・YouTube台本・内部研修教材への再構成。『記録が溜まるだけで活用できない』運用者の違和感から、営業トークの実例・顧客の本音の失言・提案成功の瞬間を機械的に分類し、個人指導・チーム教育・LPコンテンツの実素材へ変換する。"
---

# 音声記録の分析・二次利用（hojo-hq / kakei-crm 専用版）

このスキルは、営業通話の音声記録を Claude Audio API で自動分析し、顧客の課題・懸念を抽出、営業改善教材へ再構成するプロセスを体系化します。目標は「記録が溜まるだけ」から「営業トーク改善に直結する実例素材」へ.

## いつ・どんな場面で使うか

営業マンが月 30 件の客先対応をしており、Zoom Phone や内部録音システムが毎日 3-5 時間の音声を記録している状況が「記録が溜まる一方で、個別対応の繰り返し」になっている場合。

### 具体的な違和感シーン

❌ **Before（運用者が感じる無駄）:**
```
営業記録: 「2026-09-15 小林さん訪問、45分、見積り提出」
実態: その 45 分で 何が起きたのか、何を学ぶべきか、誰にも分からない。
  • 3人の営業マンが全く同じ失敗(顧客が「そこまで予算がない」と言ったのに、
    なぜか高い商品を説明している)を繰り返
  • 成功した提案の「決め手フレーズ」(例: 「3ヶ月で回収」という説明が
    9割の契約につながる)がテキスト記録に残らない
  • 「ユーザーはこう言っている」という仮説が、営業3人の勝手な解釈でばらばら
  • YouTube で「営業のコツ」という汎用動画を作ってもクリック 2-3 件
```

✅ **After（音声分析で実現できること）:**
```
自動分類: 小林さんとの 45 分音声
  ├─ 顧客の課題: 「現在の保険では交通事故の補償が不十分」(実録, 2:13-3:07)
  ├─ 顧客の懸念: 「月の支払が高くなるのが心配」(実録, 5:40-6:15, 感度 0.8)
  ├─ 営業の説明: 「3ヶ月で現在の月支払から回収できる」(実録, 12:30-13:45)
  ├─ 顧客の反応: 肯定的(感情スコア +0.7)
  ├─ 契約結果: 成約
  └─ 教材化: 
      • note 記事: 「『月の支払が心配』と言う顧客に、なぜ『3ヶ月回収』で納得するのか」
        (この会話の実例 3 件から、パターンを抽出)
      • YouTube 台本: 「同じ懸念を 9 件中 8 件で解決した、営業トーク再現」
      • 新人研修: 「この顧客タイプには、まずこう聞く」フロー図 + 音声サンプル

結果:
  • 新人営業が YouTube を見た 48 時間後、類似客で初成約
  • チーム内で「月支払が懸念の顧客」の成功率が 6 割→8 割へ
  • 月 2-3 件の「契約直前でこける」ケースが消滅
```

---

## Step 1: 音声ソースの確認・準備（どこから取るか、法的リスクがないか）

**目的:** 音声ファイルの取得可能性を確認し、法的リスクを排除する。  
**実行コマンド:** 
```bash
# Zoom Phone API 認証テスト
curl -H "Authorization: Bearer $ZOOM_API_TOKEN" \
  https://zoom.us/v2/users/$(user_id)/call_logs
```

**検証方法:**
- [ ] 顧客に「通話は記録され、社内教育に活用される」旨が告知されているか
- [ ] mamori.md が法務承認済みか
- [ ] 音声ファイル保存先が確定しているか（API / クラウド / オンプレ）

### Step 1 の詳細：対応する記録システム

✅ **取得可能**:
- Zoom Phone: 通話履歴から自動ダウンロード可能(API: 要管理者権限)
- Microsoft Teams: 通話録画 + 成績表(リーディング報告)と連携可能
- Google Meet: 録画ファイルをクラウドストレージから取得
- 内部 CTI: 自社システム上のメモ・通話記録

❌ **取得不可 / 法的に要確認**:
- 顧客が「記録されていることを知らなかった」通話（一方当事者の同意は必須）
- 3 社間通話の一部（全員の同意が必要）

---

## Step 2: 書き起こし処理の実装（Claude Audio API を使用）

**目的:** 音声ファイルを Claude Audio API で自動書き起こし。精度 95%+ を目指す。  
**実行コマンド:**
```python
python scripts/transcribe_audio.py --input_audio /path/to/audio.m4a --output_format json
```

**検証方法:**
- [ ] 音声形式が対応しているか（m4a / mp3 / wav / flac / pcm）
- [ ] ファイルサイズが 100MB 以下か（API 仕様）
- [ ] テストファイルで精度が 90% 以上か

### Step 2 の詳細：方法ごとの選択

| 方法 | 精度 | 実装難度 | 法的リスク | 用途 |
|---|---|---|---|---|
| **Claude Audio API** (推奨) | 95%+ | 低 | 低(プライベートモード) | 社内分析・note 素材 |
| **Google Cloud Speech-to-Text** | 92-95% | 低 | 中(データ保持) | 同上 |
| **Whisper (OpenAI)** | 90-92% | 中(ローカル実行) | 低(オンプレ) | 研究向け |
| **外注(人力)** | 99% | 高(コスト) | 高(機密流出) | 法務・契約レビュー |

---

## 実装例 (Python)

```python
# 月末に Zoom Phone API から通話録音を batch 取得 → Claude に送信

import anthropic
import requests
from datetime import datetime, timedelta

client = anthropic.Anthropic(api_key="...")

# Step 1: Zoom Phone API から 先月の通話一覧を取得
def fetch_zoom_calls(user_id, year, month):
    """Zoom Phone admin API で通話ログを取得"""
    start_date = f"{year}-{month:02d}-01"
    end_date = f"{year}-{month:02d}-{30 if month < 12 else 1}"  # 月の最終日を計算
    
    headers = {"Authorization": f"Bearer {ZOOM_API_TOKEN}"}
    response = requests.get(
        "https://zoom.us/v2/users/{user_id}/call_logs",
        params={"from": start_date, "to": end_date, "page_size": 300},
        headers=headers
    )
    return response.json()["call_logs"]

# Step 2: 各通話の音声ファイルをダウンロード、Claude に送信
def analyze_call_recording(call_id, download_url):
    """
    通話音声をダウンロードして Claude に送信。
    書き起こし + 感情分析 + 顧客課題抽出 を一度に実行
    """
    
    # 音声ファイルを temp に保存
    audio_response = requests.get(download_url)
    audio_path = f"/tmp/zoom_{call_id}.m4a"
    with open(audio_path, "wb") as f:
        f.write(audio_response.content)
    
    # 音声ファイルを base64 エンコード
    import base64
    with open(audio_path, "rb") as audio_file:
        audio_data = base64.standard_b64encode(audio_file.read()).decode("utf-8")
    
    # Claude にシステムプロンプト + 音声を送信
    response = client.messages.create(
        model="claude-opus-4-turbo-2025-04-09",
        max_tokens=2000,
        system="""あなたは営業通話分析の専門家です。
以下の形式で自動分析してください:

## 書き起こし
[通話の逐語録。顧客の発言と営業の返答を明確に分ける]

## 顧客の課題（実録）
「〇〇」(XX:XX-YY:YY)
- 感度(0-1): [顧客が強く感じている課題か、小さな疑問か]

## 顧客の懸念
「〇〇」(XX:XX-YY:YY)
- 感度: [この点で購買が止まるリスク度]

## 営業の説明で顧客が納得した瞬間
「営業: 〇〇」(XX:XX-YY:YY)
- 顧客の反応スコア: [-1(反発) ～ 0(中立) ～ +1(納得)]

## 成約状態
[成約 / 継続検討 / 失注]
- 失注の場合、失注の最大要因は何か

## note 記事化の候補
「【実例】〇〇と言う顧客に、〇〇で納得してもらった営業トーク」
[この通話から学べるポイント 3 点を箇条書き]""",
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "audio",
                        "media_type": "audio/mp4",
                        "data": audio_data,
                    }
                ],
            }
        ],
    )
    
    return response.content[0].text

# Step 3: 月次処理
def process_monthly_calls():
    calls = fetch_zoom_calls(user_id="nao.minakata", year=2026, month=9)
    
    analysis_results = []
    for call in calls:
        if call["duration"] < 120:  # 2分未満は除外(テストコール等)
            continue
        
        analysis = analyze_call_recording(call["id"], call["recording_url"])
        analysis_results.append({
            "call_id": call["id"],
            "call_date": call["start_time"],
            "duration": call["duration"],
            "analysis": analysis
        })
    
    return analysis_results

# Step 4: 結果を JSON で保存 → note 記事生成・教材化へ
results = process_monthly_calls()

import json
with open("kakei_call_analysis_2026_09.json", "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
```

---

## Step 3: 感情分析・課題抽出（営業改善に結びつく分類）

**目的:** 顧客の課題・懸念・解決軌跡を 3 部構成で抽出し、営業教材化に活用可能な形にする。  
**実行コマンド:**
```python
python scripts/analyze_sentiment.py --input analysis.json --output_format structured
```

**検証方法:**
- [ ] 顧客の課題が「感度スコア」(0-1)付きで抽出されているか
- [ ] 懸念と解決応答のセット（時間指定）が明記されているか
- [ ] 営業が「納得させた瞬間」の感情スコア（-1 ～ +1）が算出されているか

### 3段階の実装難度

- **Level 1 (容易):** 二値分類：肯定語 vs 否定語カウント
- **Level 2 (中程度):** 3段階分類：肯定・中立・懸念の判別
- **Level 3 (推奨):** 課題+懸念+解決軌跡の 3 部構成抽出（Claude による逐語録解析）

---

## Step 4: note 記事・YouTube 台本への変換

**目的:** 感情分析結果から note / YouTube 用コンテンツを自動生成。テンプレ感を排除し、実例中心の構成にする。  
**実行コマンド:**
```python
python scripts/generate_article.py --input analysis.json --template success_pattern
```

**出力形式:**
- note 記事：失敗→成功ストーリー形式（実例を先に見せる）
- YouTube 台本：ケースバイケース対応集（顧客タイプ別）

### パターン 1: 失敗→成功ストーリー

❌ **NG（テンプレ感が強い）:**
```markdown
# 営業が失敗しやすい 5 つのシーンとその対策

1. 顧客が予算の心配をしている
   → ソリューション: 「ROI を説明する」

2. 顧客が他社と比較している
   → ソリューション: 「差別化ポイントを打ち出す」

3. （以下同じテンプレ）
```
（読み手: 「汎用的すぎて、実際の営業場面で使えない」）

✅ **OK（実例を先に見せる）:**
```markdown
# 『月支払が高くなるのが心配』と言う顧客に、実は 8 割が「了承」した営業フレーズ

## 実録: Aさん vs 小林さん（建設業、月支払現在 8,000 円）

### Aさんの失敗ケース
営業A: 「こちらの商品なら、交通事故で最大 500 万の補償が出ます」
顧客: 「いくらになるんですか」
営業A: 「月 12,000 円です」
顧客: 「えっ、4,000 円も増えるんですか……」(即座に関心喪失)

❌ なぜ失敗したか?
  営業A は「補償内容の説明」だけで、費用対効果を言っていない。
  顧客は「支払が 4,000 円増える」という負のイメージだけ残った

### Bさんの成功ケース（同じ顧客タイプ）
営業B: 「交通事故で最大 500 万の補償が出ます」
顧客: 「いくらになるんですか」
営業B: 「月 12,000 円です。現在が 8,000 円だと、増加分は月 4,000 円ですね」
顧客: 「はい……」
営業B: 「これが大事なんですが、もし事故が起きて、病院代や修理費で
       実際に保険金が出たら？」
顧客: 「出ますね」
営業B: 「その時点で月々払った分は、すぐに返ってきます。
       つまり 3 ヶ月あれば、現在の月支払（8,000 円 × 3 = 24,000 円）
       から回収できるということです。その後 9 ヶ月間は、この補償を
       『実質無料』で持つことになります」
顧客: 「あ、そっか……」(納得、成約へ)

✅ なぜ成功したか?
  1. 増加分の数字を明示（4,000 円）
  2. 「実際に保険金が出たら」という具体的シーン
  3. 「3 ヶ月で回収」という受け取りやすい期間スパン
  4. 「その後 9 ヶ月は実質無料」という逆転

## 実績: このフレーズを使った営業の成約率

- 営業A 型（補償説明のみ）: 35 %
- 営業B 型（回収フレーズ）: 82 %

### このパターンで注意する懸念タイプ

「月支払が心配」でも、実は 3 種類がいる:
1. 「4,000 円は高い」=単純に予算最適化 → 回収フレーズで 8 割成約
2. 「そんなに払う価値があるのか」=価値を疑う → 成功事例(実績)で 7 割成約
3. 「契約後のサポート期間が短いなら……」=隠れた不安 → サポート内容を先に説明で 6 割成約

（それぞれの対応フレーズ 3 件の実例付き）
```

#### パターン 2: 新人研修フロー図

```
note/YouTube では「失敗→成功」を実録で見せる。
内部研修では「このタイプの顧客が来たら、まずこう聞く」という
フロー図 + 音声サンプル を組み合わせる。

構成:
  1. 顧客タイプ診断フロー
     「支払が心配」という発言が出た
     → 次に「他社と比較」が出るか、「そもそも必要性を疑う」が出るか
     → 初回の問い返しで判別
  
  2. 判別後の対応フレーズ 3 パターン(実録音声)
  
  3. 応答例「顧客がこう返してきたら」(ケースバイケース 5 件)
  
  4. 月 1 回の「実例追加」(先月のコール記録から新しい失言・成功を抽出)
```

---

## Step 5: 個人・チーム教育への活用（フィードバック・可視化）

### 個別フィードバック（Aさんが使った失言フレーズを特定）

```python
# Aさんの先月の通話 12 件を分析
# ウ: 「月支払の説明」で失注が 4 件

instruction = """
Aさんの先月の通話 12 件のうち、顧客が『月支払が心配』と言ったのは 8 件。
そのうち成約が 4 件、失注が 4 件です。

失注 4 件で Aさんが使ったフレーズと、成約 4 件で使ったフレーズを
比較して、差異を抽出してください。

特に注目: 『増加分の数字を明示したか』『回収スパンを言ったか』
『実際の保険金事例を話したか』の 3 点。
"""

# 結果: 
# 成約 4 件では「回収フレーズ」を全て話していた
# 失注 4 件では「補償内容の説明」で止まっていた

# → Aさんへのフィードバック資料
report = """
Aさんへ: 先月の顧客対応から見えたこと

成約率が 50% 停滞しているのは、『回収フレーズ』の未使用が原因です。

先月の成功事例（8/25 のS社訪問、45 分）では、
営業B が使った「3ヶ月で回収」の説明が、顧客の『月支払が心配』
という懸念を一気に解決しています。

Aさんが使っていないフレーズ: (実録音声を再生 5:30-6:00)
「つまり 3 ヶ月あれば、現在の月支払から回収できます」

来月の実試:
  月支払の質問が出たら、このフレーズを必ず返す練習をしましょう。
  具体的に: (実例 YouTube リンク) を視聴 → (5 分の実習コール)
  
成功時は月初に共有し、チーム全体の教材に昇格させます。
"""
```

### チーム成功率の向上モニタリング

```
月初: 前月の音声記録 30 件を自動分析
    ↓
    顧客タイプ別の成約率を可視化
    ├─ 「月支払が心配」タイプ: 成約率 68 %（目標 75%）
    ├─ 「他社と比較」タイプ: 成約率 51 %（目標 60%）
    └─ 「必要性を疑う」タイプ: 成約率 42 %（目標 55%）
    
月中: 新しい成功事例が出た瞬間、note 記事化 → YouTube 公開
    ↓
    （その翌日に同じ場面が出た営業は、すぐに新しいフレーズを試せる）
    
月末: 成功率の改善を集計
    • 「月支払」タイプ: 68 % → 71 %
    • 「他社比較」タイプ: 51 % → 55 %
    → 改善が見られたフレーズ・パターンを固定化

四半期終了: 固定化したフレーズを SOP（標準営業プロセス）へ昇格
```

---

## Step 6: 生成物の出力先と連携（出力形式・法的チェック）

### 出力形式と使用先

```
入力: Zoom Phone 音声（月 30-50 件、各 30-60 分）
    ↓
処理: Claude Audio API で書き起こし + 感情分析 + 課題抽出
    ↓
出力 A: JSON 形式（内部データベース）
  └─ 個別営業のダッシュボード（先月の成約率、失敗パターン）
    
出力 B: note 記事素材
  └─ 実例 3-5 件の要約 → 月 1 回の記事公開
    └─ 「営業のコツ」を実録ベースで更新
    
出力 C: YouTube 台本（月 2-3 本）
  └─ 「こんな顧客への対応」シリーズ
    └─ 実例 + フレーズ紹介 + 失敗例とのビフォーアフター
    
出力 D: 新人研修教材
  └─ 「顧客タイプ別フロー」+ 実録音声サンプル
    └─ 半期ごとに更新（前 3 ヶ月の新しいパターンを追加）
```

### 法的・倫理的チェック（mamori.md 連携）

```
□ 顧客の同意は記録されているか
  └─ 「お客様との通話を社内教育に活用する場合があります」の確認
  
□ 個人情報のマスク処理は十分か
  └─ 顧客氏名 → 「製造業の経営者」、金融情報 → 「月支払」に抽象化
  
□ 外部公開(note/YouTube)の判断は誰がするか
  └─ デフォルト: 営業チーム内のみ。公開には mamori.md + 小柳さんの承認
  
□ 営業マンの失敗事例を公開する際、本人の同意は取ったか
  └─ チーム内教材なら不要。動画化なら本人確認が必須
```

---

## 本番前テスト

本番での実装の前に、以下のローカルテストを実行する。

**事前準備:**
```bash
# サンプル音声ファイルの入手
wget https://example.com/sample-zoom-call.m4a -O test_audio.m4a

# テスト用 Python 環境の構築
python -m venv venv && source venv/bin/activate
pip install anthropic requests python-dotenv
```

**テスト実行チェックリスト:**
```bash
# 1. SKILL.md 形式検査
bash scripts/validate_skill_format.sh | grep transcription-analysis-hojo
# 期待値: ✅ PASS

# 2. 実装例の実行
python scripts/transcribe_audio.py --input_audio test_audio.m4a --output_format json
# 期待値: analysis.json が生成される

# 3. 感情分析処理の実行
python scripts/analyze_sentiment.py --input analysis.json --output_format structured
# 期待値: structured_analysis.json が生成される

# 4. 記事生成の実行
python scripts/generate_article.py --input analysis.json --template success_pattern
# 期待値: article_draft.md が生成される

# 5. CI ワークフロー確認
git push origin claude/superpowers-per-chat-3mbx56
# GitHub Actions で skill-validation.yml が実行される
```

**完了条件:**
- [ ] SKILL.md が形式検査を PASS する（3つの警告が解消される）
- [ ] 実装例が実行可能で、JSON 出力が生成される
- [ ] 感情分析・記事生成が正常に実行される
- [ ] GitHub Actions による自動検査に引っかかることがない

---

## 検証失敗時

以下の条件で検証が失敗する場合、対応を行う。

**音声フォーマット非対応**
```
症状: HTTPError 400 - "Unsupported media type"
原因: 音声ファイル形式が対応していない（m4a/mp3/wav/flac/pcm のいずれかが必須）
対応: ffmpeg で変換
  ffmpeg -i input.mov -c:a aac -q:a 9 output.m4a
自動起票: GitHub Issue #[auto-number] - "Audio format conversion required"
```

**API 認証エラー**
```
症状: HTTPError 401 - "Unauthorized"
原因: CLAUDE_API_KEY が未設定または期限切れ
対応:
  export CLAUDE_API_KEY="sk-..."
  # または .env ファイルに記入
検証コマンド: python -c "import anthropic; print(anthropic.Anthropic().models.list())"
```

**ファイルサイズ超過**
```
症状: HTTPError 413 - "Payload too large"
原因: 音声ファイルが 100MB を超えている
対応: 音声を分割、または圧縮
  ffmpeg -i input.m4a -q:a 4 output.m4a  # 品質低下許容で圧縮
自動起票: GitHub Issue - "Audio file requires splitting"
```

**テキスト抽出失敗**
```
症状: JSON decode error または empty transcription
原因: 音声が低品質、背景ノイズが多い、言語が異なる
対応:
  1. オーディオの品質確認: ffprobe test_audio.m4a | grep -E "bitrate|sample_rate"
  2. ノイズ除去: ffmpeg-normalize を使用
  3. 言語設定確認: system prompt に言語を明記（"日本語で書き起こしてください"）
自動起票: GitHub Issue - "Transcription quality below threshold"
```

**感情分析の精度低下**
```
症状: 課題抽出が 30% 以下、感情スコアが全て中立(-0.2 ～ 0.2)
原因: 会話の専門用語が多い、営業トークが単調、顧客発言が少ない
対応:
  1. system prompt を業界別にカスタマイズ
  2. 分析の段階化：Level 1（二値分類）から開始
  3. テンプレートを見直し：「感情」から「懸念シグナル」へ軸足を移す
```

---

## チェックリスト（本番運用時）

```
□ 月末に Zoom Phone から音声ファイルを一括取得できるか
  └─ API キー・認証情報・クラウドストレージパス確認

□ Claude Audio API の月額コスト試算は完了か
  └─ 音声 30 時間/月 → ~$200-300

□ note / YouTube への公開ルールが定まっているか
  └─ 誰が承認者か、個人情報マスクルールは何か

□ 新人研修への組み込みタイミングは決まっているか
  └─ 入社後いつから、どのフローで使うか

□ 法務承認は完了しているか
  └─ mamori.md の確認
```

---

## 関連スキル

- `humanizer` — YouTube / note 記事の自然な日本語表現
- `shiryo-sakusei` — 実例の出典確認・数値精度検証
- `user-research-hojo` — 顧客タイプの細分化と対応フロー
- `taste-skill` — 記事・動画の「AI が作った感」排除
