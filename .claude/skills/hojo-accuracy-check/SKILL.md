---
name: hojo-accuracy-check
description: "助成金・補助金の締切/金額/要件など制度データを掲載・更新・整形・検証するときに必ず使う。原文URLとの照合、不明時の『要確認』表示、断定禁止という正確性最優先ルールを強制する。Gemini並行検証によるダブルチェック体制で信頼度強化。"
---

# データ正確性チェック(正確性最優先)

沖縄企業のミカタ/もらいわすれ堂の制度データ(締切・金額・要件・対象者・申請先など)を
掲載・更新・整形・検証するときは、CLAUDE.md 憲法の「正確性最優先」に従う。
**Claude + Gemini による並行検証で信頼度を仕組みで強化する。**

---

## 絶対ルール

1. **原文照合必須**: 締切・金額・要件は必ず一次情報(自治体・省庁・jGrants等)の原文URLと照合する。
2. **不明は断定しない**: 照合できない/曖昧な項目は「要確認」と明記して公開する。推測で埋めない。
3. **出典を残す**: 各項目に参照した原文URLを紐づける。URLが取れない情報は掲載保留。
4. **鮮度**: 更新遅延は24時間以内。古い可能性がある項目は日付を添える。
5. **マルチAI検証**: 原文照合は Claude 単独でなく Gemini との並行検証(ダブルチェック)で実施。

---

## Step 1: 原文URLの取得と検証

### 目的
対象の制度データについて、基となった一次情報源(原文URL)を特定・確保する。
URLがない情報は掲載候補から除外する。

### 実行手順

1. **制度の掲載元を確認**
   - jGrants API の場合: `source_url` フィールドから原文URLを抽出
   - 自治体サイト収集の場合: クロール時に保存した `scraped_from_url` を使用
   - 二次情報(ニュースサイト等)からの情報は、一次情報源を遡上できないなら掲載保留

2. **URLの有効性をチェック**
   ```bash
   # 例: 複数URLをバッチ検証
   curl -I -m 5 "https://example.jp/subsidy/..."  # ステータスコード確認
   ```
   - HTTP 200 → 健全
   - HTTP 404 → 削除済み(要確認扱い)
   - HTTP 403 → アクセス制限(スキップ許可・robots.txt確認)
   - タイムアウト(> 10秒) → 一時的エラー(再試行)

3. **robots.txt と利用規約確認**
   - 守り部(mamori.md)が事前承認したサイトのみ
   - 未承認サイトからの転載は禁止(絶対ルール)

### 検証方法
- 後段の Step 2 で原文から値を抽出できるか確認
- 抽出できなければその時点で「要確認」判定

---

## Step 2: 締切/金額/要件の照合

### 目的
取得した制度データの **締切**・**金額**・**要件** が原文と一致するか確認する。
相違があれば原文優先で修正。

### 実行手順(対象項目ごと)

#### 2-A. 締切の照合
1. 原文URL を開き「締切」「応募期限」「申請期限」の文言を探す
2. JSON データの `deadline` フィールドと一致するか確認
3. **日付形式の正規化**:
   - 「2026年11月30日」→ `2026-11-30`
   - 「2026/11/30」→ `2026-11-30`
   - 「R8年11月30日」(令和表記) → `2026-11-30` に統一
4. 不明な場合は「要確認」フラグを立てる(消さずに保持)

#### 2-B. 金額の照合
1. 原文から「補助額」「給付金額」「上限」の文言を抽出
2. JSON の `amount_min`, `amount_max` と照合
3. 通貨単位を統一(全て「円」)
4. 金額が「要申請」「審査により決定」の場合、**空欄にせず「要確認」と明記**

#### 2-C. 要件の照合
1. 原文から「対象者」「要件」「対象業種」を抽出
2. JSON の `requirements` リストと比較
3. **部分一致は NG**: 要件が 1 つでも漏れていたら修正
4. 要件が複雑で要約困難な場合は「詳細は原文参照」と明記

### 検証方法(本セクション下部「実装例」参照)
- Claude API で原文 HTML と JSON を突き合わせ、相違点を抽出
- Gemini API で独立に同じ照合を実施し結果を比較
- 両者で判定が分かれた場合は「要確認」

---

## Step 3: 不明項目の「要確認」判定

### 目的
照合できない・曖昧な項目を、推測で埋めず「要確認」として公開する。
ユーザーに対して「AI判定で確実でない」ことを明示。

### 実行手順

1. **「要確認」をマークすべきケース**
   - 原文が見つからない (404、アクセス不可)
   - 複数の解釈が可能 (曖昧な日本語)
   - AI の Claude と Gemini で判定が分かれた
   - 要件が変更されたばかりで新旧併存
   - ユーザーに確認が必要(例: 市町村ごとに異なる)

2. **「要確認」表示の方法**
   ```json
   {
     "deadline": "2026-11-30",
     "deadline_confidence": "確認済み",
     "amount": {
       "min": null,
       "max": 1000000,
       "note": "金額上限は確認できたが下限は要確認"
     },
     "requirements": [
       "沖縄県内に本社がある",
       "従業員数 20 人以上（要確認：基準が変わった可能性）"
     ]
   }
   ```

3. **不確実性の記録**
   - 各項目に `confidence` フィールド (確認済み / 一部確認 / 要確認)
   - 理由を `note` フィールドに記入
   - 確認日時を記録(24時間経過で再確認)

### 検証方法
- 公開前に「要確認」を含む行が正しく表示されるか UI で確認
- 検証部の目視チェックリスト(本セクション下部「本番前テスト」参照)

---

## Step 4: 複数制度の並列検証管理

### 目的
毎日のバッチ検証(複数制度を同時)で、スケーラブルかつ正確性を保つ。

### 実行手順

1. **検証対象の洗い出し**
   - 新規制度: 100%
   - 更新制度(1週間以内): 100%
   - 変更なし制度(1週間以上): サンプリング(5件/日)

2. **並列処理(Python pseudocode)**
   ```python
   # 複数制度を並列で検証
   subsidies_to_check = get_subsidies_to_verify()
   
   for subsidy in subsidies_to_check:
       # Claude 検証
       claude_result = verify_with_claude(
           subsidy_data=subsidy,
           source_url=subsidy['source_url']
       )
       
       # Gemini 検証(並行実行)
       gemini_result = verify_with_gemini(
           subsidy_data=subsidy,
           source_url=subsidy['source_url']
       )
       
       # 結果を比較
       if claude_result == gemini_result:
           subsidy['verification_status'] = 'confirmed'
       else:
           subsidy['verification_status'] = 'require_check'
           subsidy['verification_notes'] = {
               'claude': claude_result,
               'gemini': gemini_result
           }
   ```

3. **結果の集約と記録**
   - 確認済み: そのまま公開
   - 不一致(「要確認」): フラグを立て、検証部へ通知
   - 結果を `data/kpi/verify_history.json` に蓄積

### 検証方法
- 実行ログで「検証スキップ」「並列エラー」がないか確認
- タイムアウト検知で重い計算を検出

---

## Step 5: 締切文言の整合性確認

### 目的
`hojo-deadline-alert` スキルの3層ルール
(SNS投稿: 30日以上 / LINE個別: 7-29日 / 予告: 7日未満)
と整合させる。

### 実行手順

1. 制度の `deadline` から「残り日数」を計算
2. 文言が以下と一致するか確認:
   - 30日以上: 「締切の約1ヶ月前」(「7日前」と言わない！)
   - 7-29日: 「締切まであと○日」
   - 7日未満: 「次回公募予告」

3. 相違があれば修正
   (詳細: docs/hojo-deadline-alert の SKILL.md)

---

## マルチAI照合ルール(2026-08-06 小柳さん決裁)

原文照合(verify-sources)は Claude に加え Gemini でも独立照合するダブルチェック方式。

- **どちらか一方でも矛盾を検知したら「要確認」扱い**(保守的マージ)。
- **AI同士の一致は断定の必要条件であって十分条件ではない**。最終根拠は常に原文URL。
- 判定が割れたときは、指摘した側に原文からの根拠引用を要求する再確認を行う
  (引用できなければ撤回=誤検知として処理。撤回も履歴に残す)。
- 照合結果は `data/kpi/verify_history.json` に日次で蓄積。NG項目の `human_verdict` に
  検証部が false_positive / true_mismatch を記入し、効果測定(見直し期限 2026-11-06)の根拠にする。
- 適用範囲は照合サンプリングのみ。全件適用・他用途への拡大は小柳さんへ再上申。
- 実装: `scripts/verify_sources.py` / 汎用パターン: `multi-ai-crosscheck` スキル

---

## 実装例: 複数制度の並列検証

### 例: `scripts/verify_sources.py` (本体コード)

```python
#!/usr/bin/env python3
"""
複数制度データを Claude + Gemini で並列検証し、結果を統合。
見直し期限: 2026-11-06 (3ヶ月の効果測定後に再議論)
"""

import json
import os
import sys
from datetime import datetime
from typing import Dict, List, Optional

# Claude API
import anthropic

# Gemini API
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    print("⚠️  google-generativeai not installed. Gemini verification disabled.", file=sys.stderr)


class SubsidyVerifier:
    def __init__(self, enable_gemini: bool = True):
        self.claude_client = anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
        self.enable_gemini = enable_gemini and GEMINI_AVAILABLE
        
        if self.enable_gemini:
            gemini_key = os.getenv('GEMINI_API_KEY')
            if gemini_key:
                genai.configure(api_key=gemini_key)
            else:
                self.enable_gemini = False
                print("⚠️  GEMINI_API_KEY not set. Gemini verification disabled.", file=sys.stderr)

    def verify_with_claude(self, subsidy: Dict, source_html: str) -> Dict:
        """Claude を使用して制度データを検証"""
        prompt = f"""
以下の制度データが原文(HTML)と一致するか確認してください。

【制度データ(JSON)】
{json.dumps(subsidy, ensure_ascii=False, indent=2)}

【原文(HTML抜粋)】
{source_html[:3000]}

検証項目:
1. 締切日: "{subsidy.get('deadline', 'N/A')}" が原文に含まれているか
2. 金額: "{subsidy.get('amount_max', 'N/A')}" が原文に含まれているか
3. 要件: {subsidy.get('requirements', [])} が全て含まれているか

結果をJSON形式で返してください:
{{
  "deadline_match": true/false,
  "deadline_note": "...",
  "amount_match": true/false,
  "amount_note": "...",
  "requirements_match": true/false,
  "requirements_note": "...",
  "overall_status": "confirmed" or "require_check",
  "mismatches": ["..."]
}}
"""
        response = self.claude_client.messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}]
        )
        
        try:
            result = json.loads(response.content[0].text)
        except json.JSONDecodeError:
            result = {"overall_status": "error", "note": "Claude returned invalid JSON"}
        
        return result

    def verify_with_gemini(self, subsidy: Dict, source_html: str) -> Optional[Dict]:
        """Gemini を使用して制度データを独立検証"""
        if not self.enable_gemini:
            return None
        
        try:
            model = genai.GenerativeModel('gemini-2.0-flash')
            prompt = f"""
以下の助成金・補助金の制度データが原文(HTML)と一致するか確認してください。
Claude によるチェック結果とは独立して判定してください。

【制度データ】
{json.dumps(subsidy, ensure_ascii=False, indent=2)}

【原文(HTML 抜粋)】
{source_html[:3000]}

確認項目:
1. 締切日: "{subsidy.get('deadline', 'N/A')}" が原文に含まれているか
2. 金額: "{subsidy.get('amount_max', 'N/A')}" が原文に含まれているか
3. 要件: {subsidy.get('requirements', [])} が全て含まれているか

JSON形式で結果を返してください:
{{
  "deadline_match": true/false,
  "amount_match": true/false,
  "requirements_match": true/false,
  "overall_status": "confirmed" or "require_check",
  "mismatches": ["..."]
}}
"""
            response = model.generate_content(prompt)
            try:
                result = json.loads(response.text)
            except json.JSONDecodeError:
                result = {"overall_status": "error", "note": "Gemini returned invalid JSON"}
            
            return result
        except Exception as e:
            print(f"⚠️  Gemini API error: {e}", file=sys.stderr)
            return None

    def compare_results(self, claude: Dict, gemini: Optional[Dict]) -> Dict:
        """Claude と Gemini の結果を比較"""
        if not gemini:
            # Gemini なしの場合は Claude の結果をそのまま使用
            return {
                "status": claude.get("overall_status", "unknown"),
                "verified_by": ["claude"],
                "details": claude
            }
        
        # 両者の判定が一致するか確認
        claude_status = claude.get("overall_status")
        gemini_status = gemini.get("overall_status")
        
        if claude_status == gemini_status == "confirmed":
            # 両者が確認→確定
            return {
                "status": "confirmed",
                "verified_by": ["claude", "gemini"],
                "details": {
                    "claude": claude,
                    "gemini": gemini
                }
            }
        elif claude_status == "error" or gemini_status == "error":
            # どちらかがエラー→要確認
            return {
                "status": "require_check",
                "verified_by": ["claude", "gemini"],
                "reason": "API error or invalid response",
                "details": {
                    "claude": claude,
                    "gemini": gemini
                }
            }
        else:
            # 判定が分かれた→保守的に「要確認」
            return {
                "status": "require_check",
                "verified_by": ["claude", "gemini"],
                "reason": "Claude and Gemini disagree",
                "details": {
                    "claude": claude,
                    "gemini": gemini,
                    "mismatches": list(set(
                        claude.get("mismatches", []) + 
                        gemini.get("mismatches", [])
                    ))
                }
            }

    def verify_subsidy(self, subsidy: Dict, source_html: str) -> Dict:
        """単一制度を Claude + Gemini で検証"""
        # Step 1: Claude 検証
        claude_result = self.verify_with_claude(subsidy, source_html)
        
        # Step 2: Gemini 検証(並行)
        gemini_result = self.verify_with_gemini(subsidy, source_html)
        
        # Step 3: 結果を比較・統合
        final_result = self.compare_results(claude_result, gemini_result)
        
        # Step 4: 履歴に記録
        final_result["timestamp"] = datetime.now().isoformat()
        final_result["subsidy_id"] = subsidy.get("id")
        
        return final_result

    def verify_batch(self, subsidies: List[Dict], source_htmls: Dict[str, str]) -> Dict:
        """複数制度をバッチ検証"""
        results = {
            "timestamp": datetime.now().isoformat(),
            "total": len(subsidies),
            "verified": [],
            "require_check": [],
            "errors": []
        }
        
        for subsidy in subsidies:
            subsidy_id = subsidy.get("id")
            source_html = source_htmls.get(subsidy_id, "")
            
            if not source_html:
                results["errors"].append({
                    "subsidy_id": subsidy_id,
                    "error": "No source HTML provided"
                })
                continue
            
            try:
                result = self.verify_subsidy(subsidy, source_html)
                
                if result["status"] == "confirmed":
                    results["verified"].append(result)
                else:
                    results["require_check"].append(result)
            except Exception as e:
                results["errors"].append({
                    "subsidy_id": subsidy_id,
                    "error": str(e)
                })
        
        return results


def main():
    # 使用例
    verifier = SubsidyVerifier(enable_gemini=True)
    
    # テスト用制度データ
    sample_subsidy = {
        "id": "grant-001",
        "title": "沖縄県中小企業AI導入支援事業",
        "deadline": "2026-11-30",
        "amount_max": 1000000,
        "requirements": ["沖縄県内に本社", "従業員数 20 人以上"]
    }
    
    # テスト用原文 HTML
    sample_html = """
    <div class="subsidy">
        <h2>沖縄県中小企業AI導入支援事業</h2>
        <p>締切: 2026年11月30日</p>
        <p>補助額上限: 1,000,000円</p>
        <p>対象: 沖縄県内に本社を置く従業員数20人以上の中小企業</p>
    </div>
    """
    
    result = verifier.verify_subsidy(sample_subsidy, sample_html)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
```

### 実装ポイント

1. **並列実行**: Claude と Gemini を非同期で同時実行(実装では明示的に記載していますが、本番では `asyncio` で最適化)
2. **API エラー処理**: 片方のサービスが落ちても動作継続(スキップ扱い)
3. **結果の統合**:
   - 両者一致 → 「確認済み」
   - 一方がエラー → 「要確認」
   - 判定が分かれた → 「要確認」(保守的判定)
4. **履歴記録**: `data/kpi/verify_history.json` に蓄積(後の効果測定に活用)

---

## 検証失敗時(Issue自動起票)

制度データの検証で失敗・リンク切れ・内容不一致が検出された場合の対応。

### 失敗条件

| 失敗種別 | 判定基準 | アクション |
|---|---|---|
| **URL 404/410** | 原文リンク切れ | Issue: 「リンク切れ(ID: xxxx)」 |
| **内容不一致** | Claude/Gemini 判定が「要確認」 | Issue: 「内容要確認(ID: xxxx)」 + スクリーンショット |
| **取得タイムアウト** | HTTP タイムアウト > 30秒 | Issue: 「ネットワーク一時障害」 + retry 予約 |
| **API エラー** | Claude/Gemini のエラーレスポンス | Issue: 「検証 API エラー」 + ログ |
| **robots.txt 違反** | 未承認クロールを検出 | Issue: 「守り部審査待ち」+ 要承認 URL リスト |

### Issue テンプレート

```markdown
## 制度データ検証失敗: [失敗種別]

**失敗日時**: [ISO 8601]
**対象制度**: [制度ID / 制度名]
**原文URL**: [URL]
**検証方式**: Claude + Gemini 並行検証

### 検証結果
| 項目 | Claude | Gemini | 判定 |
|---|---|---|---|
| 締切 | ✓ 確認 | ✗ 不一致 | NG |
| 金額 | ✓ 確認 | ✓ 確認 | OK |
| 要件 | ? 取得失敗 | ✓ 確認 | 要確認 |

### 原因
(Claude/Gemini の判定理由を引用)
- Claude: "原文に『1,000,000円』と明記されているが、データは『500,000円』"
- Gemini: "同上。さらに要件の『20人以上』が『30人以上』に変更された可能性"

### 対応方針
- [ ] 原文 URL を再確認(ブラウザで手動開封)
- [ ] 404 ならサイトをクロール除外リストに追加
- [ ] 内容変更なら `deadline`, `amount_max`, `requirements` を修正
- [ ] 修正後に再検証(Claude + Gemini両者確認)

### リンク
- 検証ログ: `data/kpi/verify_history.json` の当日分
- ワークフロー: https://github.com/allgroup-inc/hojo-hq/actions/runs/...

**Label**: `verification`, `data-quality`
**Assignee**: @kensho.md (検証部)
```

### GitHub Actions での自動起票

`.github/workflows/verify-sources.yml` に Issue 自動作成ステップを組み込む:

```yaml
- name: Create verification failure issues
  if: failure() || env.VERIFICATION_FAILED == 'true'
  uses: actions/github-script@v7
  with:
    script: |
      const failures = JSON.parse(fs.readFileSync('verify_results.json', 'utf8'));
      for (const failure of failures.require_check) {
        await github.rest.issues.create({
          owner: context.repo.owner,
          repo: context.repo.repo,
          title: `データ検証要確認: ${failure.subsidy_id}`,
          body: `Claude: ${failure.details.claude.overall_status}\nGemini: ${failure.details.gemini?.overall_status || 'N/A'}\n\n詳細: data/kpi/verify_history.json`,
          labels: ['verification', 'data-quality']
        });
      }
```

---

## Gemini並行検証（マルチAI連携）

**導入決裁**: 2026-08-06 小柳さん承認 / **見直し期限**: 2026-11-06

原文照合の信頼度を仕組みで強化するため、Claude に加えて Gemini による独立検証を並行実施。

### なぜ Gemini を追加するのか

- **系統誤りの検知**: 同じ AI モデルだけでは、同じ誤り方(例: 「月」を「日」と読み間違え)が繰り返される
- **相互チェック**: 別会社・別系統のモデルが独立に抽出することで、読み落とし(偽陰性)を減らせる
- **保守的判定**: どちらか一方が矛盾を検知したら「要確認」扱いにすることで、見栄え優先で正確性を損なう誘惑を排除

### 実装フロー

```
原文 URL を取得
    ↓
 ┌─ Claude API で検証(Step 2 参照)
 │   ↓
 │   { "deadline_match": true, "amount_match": false, ... }
 │   
 ├─ Gemini API で検証(同じ原文で独立判定)
 │   ↓
 │   { "deadline_match": true, "amount_match": false, ... }
 │
 └─ 結果を比較
     ↓
     Claude == Gemini?
     ├─ YES → "confirmed"(公開可)
     ├─ NO  → "require_check"(検証部へ)
     └─ ERROR → "require_check"(保守的)
```

### Gemini API の設定

#### 前提条件
- **GEMINI_API_KEY 環境変数が設定されていること**
  ```bash
  export GEMINI_API_KEY="your-api-key-here"
  ```
  取得方法: [Google AI Studio](https://aistudio.google.com/app/apikey)

#### Python での実装例

```python
import google.generativeai as genai
import os

# 初期化
genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
model = genai.GenerativeModel('gemini-2.0-flash')

# プロンプト(Claude と同じ)
prompt = """
以下の制度データが原文と一致するか確認してください。

【制度データ】
{制度の JSON}

【原文 HTML】
{原文の抜粋}

確認結果を JSON で返してください。
"""

# 実行
response = model.generate_content(prompt)
print(response.text)  # JSON 文字列を返す
```

### 判定ロジック(Python)

```python
def compare_claude_gemini(claude_result: dict, gemini_result: dict) -> dict:
    """
    Claude と Gemini の判定を比較。
    
    判定条件:
    - 両者とも "confirmed" → 最終判定: "confirmed"
    - どちらかが "require_check" → 最終判定: "require_check"(保守的)
    - どちらかが API エラー → 最終判定: "require_check"
    """
    
    if claude_result.get('overall_status') == 'error' or gemini_result.get('overall_status') == 'error':
        return {
            'final_status': 'require_check',
            'reason': 'API error occurred',
            'claude': claude_result,
            'gemini': gemini_result
        }
    
    if claude_result.get('overall_status') == 'confirmed' and gemini_result.get('overall_status') == 'confirmed':
        # 両者が確認 → 確定
        mismatches = set(claude_result.get('mismatches', []) + gemini_result.get('mismatches', []))
        return {
            'final_status': 'confirmed',
            'mismatches': list(mismatches) if mismatches else [],
            'claude': claude_result,
            'gemini': gemini_result
        }
    
    # その他(判定が分かれた) → 保守的に「要確認」
    return {
        'final_status': 'require_check',
        'reason': 'Claude and Gemini disagree',
        'claude': claude_result,
        'gemini': gemini_result,
        'mismatches': list(set(
            claude_result.get('mismatches', []) + 
            gemini_result.get('mismatches', [])
        ))
    }
```

### 効果測定(見直し期限: 2026-11-06)

Gemini 導入 3 ヶ月後(11月初旬)に以下を検証:

1. **偽陽性率**: NG と判定されたうち、実際に誤りだった割合
   - 目標: 90% 以上が真の誤りである
   - 結果: < 70% なら判定プロンプトを調整

2. **見逃し率**: 実際の誤りをどれだけ検知したか
   - 目標: 前月比で見逃しが 30% 以上減少
   - 結果: 改善なければ Claude の判定閾値を変更

3. **API コスト**: Gemini 無料枠の消費状況
   - 現在: 5件/日 × 30日 = 月 150 件
   - 全件拡大時の費用推定を算出し、小柳さんに上申

4. **運用負荷**: 「要確認」Issue の処理時間
   - 目標: 平均 10 分以下/件
   - 結果: > 30 分なら誤検知が多い可能性

---

## 本番前テスト(チェックリスト)

制度データを掲載・更新する前に、以下のチェックリストをクリアすること。
**本セッションではローカル環境で全項目を検証する手順を記載。**

### 前提準備

```bash
# 環境確認
export ANTHROPIC_API_KEY="sk-..."  # Claude API キー
export GEMINI_API_KEY="..."         # Gemini API キー(なくても OK、スキップ扱い)

# 検証スクリプトを実行可能にする
python3 scripts/verify_sources.py --help
```

### テストチェックリスト

- [ ] **1. URL有効性テスト**
  ```bash
  # 対象制度の source_url が 404 でないか確認
  curl -I "https://example.jp/subsidy/..." | grep "HTTP"
  ```
  期待値: `HTTP/2 200` または `HTTP/1.1 200`

- [ ] **2. Claude 単独検証テスト**
  ```bash
  python3 scripts/verify_sources.py \
    --subsidy-id grant-001 \
    --verify-with claude-only
  ```
  期待値: `"overall_status": "confirmed"` (誤りがなければ)

- [ ] **3. Gemini 単独検証テスト**
  ```bash
  python3 scripts/verify_sources.py \
    --subsidy-id grant-001 \
    --verify-with gemini-only
  ```
  期待値: Claude と同じ結果

- [ ] **4. 並行検証テスト(Claude + Gemini)**
  ```bash
  python3 scripts/verify_sources.py \
    --subsidy-id grant-001 \
    --verify-with both
  ```
  期待値: `"final_status": "confirmed"` (両者一致)

- [ ] **5. 不一致検知テスト**
  ```bash
  # テスト用に金額を意図的に間違えた制度データで実行
  python3 scripts/verify_sources.py \
    --subsidy-id test-mismatch \
    --verify-with both
  ```
  期待値: `"final_status": "require_check"` (不一致を検知)

- [ ] **6. タイムアウト処理テスト**
  ```bash
  # 応答の遅いサイトを対象に実行
  timeout 35 python3 scripts/verify_sources.py \
    --subsidy-id slow-source \
    --timeout 30
  ```
  期待値: 30秒で タイムアウト扱い → `"require_check"`

- [ ] **7. 複数制度バッチテスト**
  ```bash
  python3 scripts/verify_sources.py \
    --batch data/test_subsidies.json \
    --verify-with both \
    --output verify_results.json
  ```
  期待値: `verify_results.json` に結果が JSON で出力

- [ ] **8. 締切表現の整合性テスト**
  制度の `deadline` から計算した「残り日数」が以下と一致するか:
  - 30日以上: 文言に「約1ヶ月前」を含む (「7日前」は NG)
  - 7-29日: 「あと○日」と言及
  - 7日未満: 「次回公募予告」表示
  ```bash
  python3 scripts/validate_deadline_text.py \
    --subsidy-id grant-001
  ```

- [ ] **9. 出典 URL の記録確認**
  各制度の JSON に以下が含まれているか:
  ```json
  {
    "source_url": "https://example.jp/subsidy/grant-001",
    "verified_at": "2026-10-05T10:30:00Z",
    "verified_by": ["claude", "gemini"],
    "verification_status": "confirmed"
  }
  ```

- [ ] **10. UI 表示テスト**
  掲載用 HTML ページで以下を確認:
  - [ ] 「要確認」フラグが正しく表示される
  - [ ] 金額が「要確認」のとき、空欄でなく「要確認」と表示
  - [ ] 締切が「要確認」のとき、推測値でなく「要確認」と表示
  - [ ] 出典 URL がクリッカブルなリンク

- [ ] **11. GitHub Actions ワークフロー検証**
  本番環境でのパイプライン実行確認:
  ```bash
  # ローカルで .github/workflows/verify-sources.yml をシミュレート
  ./scripts/run_local_workflow.sh
  ```
  期待値: ワークフロー完了 + Issue 自動起票(NG 件数ぶん)

- [ ] **12. 検証履歴の記録確認**
  ```bash
  jq '.[] | select(.subsidy_id == "grant-001")' data/kpi/verify_history.json
  ```
  期待値: 今日の日付 + 検証結果が JSON で記録

### 本番投入OK の条件

以下の全項目をクリア:

1. ✅ テスト 1-5: 基本検証が通っている
2. ✅ テスト 6-8: 安定性・互換性が確認できた
3. ✅ テスト 9-12: 記録・表示・ワークフローが正常
4. ✅ Issue 0 件: 自動起票されたニセの Issue がない
5. ✅ 検証部承認: 検証部(kensho.md)の目視確認済み

---

## やってはいけないこと

- 原文にない金額・締切を「たぶんこう」で書く。
- 「要確認」を外して断定形に整える(見栄え優先で正確性を犠牲にする)。
- 守り部未承認のサイトをクロール/転載する。
- 「AI が 2 つとも一致したから確認不要」と断定する(一致しても原文照合は省略しない)。
- Gemini API が落ちているときに「要確認」を「確認済み」に変える(降格禁止)。
- 過去の「要確認」を見直さずに放置する(3 ヶ月以上放置は再検証)。

---

## 参考リンク

- **原文照合の定義**: CLAUDE.md 絶対ルール 1
- **マルチAI導入決定議事**: docs/マルチAI連携_導入決定_2026-08-06.md
- **マルチAI セットアップガイド**: docs/マルチAI連携セットアップガイド.md
- **Gemini 並行検証参考実装**: .claude/skills/hojo-lighthouse-triage/SKILL.md (Phase 2)
- **deadline 表現統一ルール**: .claude/skills/hojo-deadline-alert/SKILL.md
- **検証部プレイブック**: docs/検証部プレイブック.md (検証部固有の運用細則)
