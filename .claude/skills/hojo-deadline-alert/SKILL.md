---
name: hojo-deadline-alert
description: "沖縄企業のミカタ/もらいわすれ堂で締切アラート・告知・SNS投稿・LINE配信の文面や配信タイミングを設計・レビューするときに必ず使う。締切3層ルールと『約1か月前から』表現を強制し、誤った『締切7日前アラート』を排除する。"
---

# 締切アラート3層ルール

沖縄企業のミカタ/もらいわすれ堂の締切まわりの文面・配信設計・SNS投稿を作る/直すときは、
CLAUDE.md 憲法の締切3層ルールに必ず従う。

このスキルは、締切3層ルール(30日以上・7-29日・7日未満)を実装し、
利用者に「約1か月前から」という統一表現で情報提供し、
誤った「7日前アラート」を排除するプロセスを体系化します。

---

## Step 1: 制度の残り日数を確認・計算する

**目的:** 対象制度の締切までの日数を正確に計算し、適用する層を判定する。  
**実行コマンド:**
```python
# 締切日と現在日を照合し、残り日数を計算
from datetime import datetime, timedelta

def calculate_days_until_deadline(deadline_date_str):
    """
    deadline_date_str: "2026-11-15" 形式
    戻り値: int (残り日数)
    """
    deadline = datetime.strptime(deadline_date_str, "%Y-%m-%d")
    today = datetime.now()
    days_remaining = (deadline - today).days
    return days_remaining

# 例: 11月15日締切の場合
days = calculate_days_until_deadline("2026-11-15")
print(f"残り日数: {days}")  # e.g. 41 days → 30日以上層へ
```

**検証方法:**
- [ ] 締切日が原文URL(jGrants API / 各自治体サイト)と一致しているか
- [ ] 「9月31日」「2月30日」など存在しない日付でないか
- [ ] 計算に閏年・うるう秒の影響がないか(Python datetime は自動対応)
- [ ] 残り日数がマイナスになっていないか(既に締切が過ぎていないか)

---

## Step 2: 残り日数に基づいて配信層を判定する

**目的:** 計算した残り日数を3層ルールに照合し、適用する対応(SNS/LINE/次回予告)を決定する。  
**実行コマンド:**
```python
def determine_alert_tier(days_remaining):
    """
    残り日数から配信層を判定
    戻り値: dict {tier, action, message_style}
    """
    if days_remaining >= 30:
        return {
            "tier": "TIER_1_SNS",
            "action": "SNS投稿のみ(LINE配信なし)",
            "reason": "準備期間が十分にある",
            "message_template": "sns_only"
        }
    elif 7 <= days_remaining < 30:
        return {
            "tier": "TIER_2_LINE",
            "action": "LINE個別アラートを送信",
            "reason": "書類・gBizIDの準備が間に合う最後の窓",
            "message_template": "line_urgent_alert"
        }
    else:  # days_remaining < 7
        return {
            "tier": "TIER_3_NEXT",
            "action": "次回公募予告に切り替える(gBizID啓発)",
            "reason": "今回は準備が間に合わないため無理に急かさない",
            "message_template": "next_recruitment_preview"
        }

# 例: 残り41日の場合
tier = determine_alert_tier(41)
print(f"適用層: {tier['tier']}")  # TIER_1_SNS
print(f"対応: {tier['action']}")  # SNS投稿のみ
```

**検証方法:**
- [ ] 返された tier が TIER_1_SNS / TIER_2_LINE / TIER_3_NEXT のいずれかか
- [ ] 7日ちょうどの場合、TIER_2_LINE に正しく分類されているか(境界値テスト)
- [ ] 30日ちょうどの場合、TIER_1_SNS に正しく分類されているか(境界値テスト)

---

## Step 3: 文面の「7日前」禁止表現をスキャンする

**目的:** 文案・SNS投稿・LINE配信に「7日前」「1週間前」などの禁止表現が混入していないか検査する。  
**実行コマンド:**
```bash
# 禁止パターンのスキャン (grep 相当)
grep -iE '(7日前|締切7日|7日以内|1週間前|1週間以内|期間1週間)' <draft_file>

# Python での実装例
import re

def scan_forbidden_phrases(text):
    """
    禁止表現を検出し、該当箇所を報告
    戻り値: list of {line_num, matched_text, severity}
    """
    forbidden_patterns = [
        r'7\s*日\s*前',  # 7日前
        r'締切\s*7\s*日',  # 締切7日
        r'7\s*日\s*以内',  # 7日以内
        r'1\s*週間\s*前',  # 1週間前
        r'1\s*週間\s*以内',  # 1週間以内
        r'期間\s*1\s*週間',  # 期間1週間
    ]
    
    violations = []
    for i, line in enumerate(text.split('\n'), 1):
        for pattern in forbidden_patterns:
            if re.search(pattern, line, re.IGNORECASE):
                violations.append({
                    "line": i,
                    "matched": re.search(pattern, line, re.IGNORECASE).group(),
                    "severity": "CRITICAL"
                })
    
    return violations

# 例: SNS投稿の検査
draft = """
新しい助成金が決まりました！
締切は12月15日です。
みなさんは7日前までに準備をしてくださいね。
"""

violations = scan_forbidden_phrases(draft)
for v in violations:
    print(f"⚠️ 行{v['line']}: '{v['matched']}' → 削除または修正が必須")
```

**検証方法:**
- [ ] スキャン結果が0件(禁止表現なし)であることを確認
- [ ] 見つかった場合、当該文章を修正し再スキャン
- [ ] 「7日前」を削除したら、代わりに「約1か月前から」が入っているか確認

---

## Step 4: 利用者向けコピーを「約1か月前から」に統一する

**目的:** 全ての外向けコピー(SNS/LINE/メール)に「約1か月前から」という統一表現を使う。  
**実行コマンド:**
```python
def validate_user_messaging(tier, message_text):
    """
    層別に、利用者向けメッセージが正しい表現か検証
    """
    
    # TIER_1_SNS: 約1か月前から という予告表現を使う
    if tier == "TIER_1_SNS":
        if "約1か月前から" in message_text or "約1ヶ月前から" in message_text:
            return {"status": "OK", "message": "SNS投稿として適切"}
        else:
            return {
                "status": "NG",
                "message": "SNS投稿に『約1か月前から』の表現が必須",
                "suggestion": f"修正例: '{message_text}' → '【助成金のお知らせ】新しい〇〇助成金が決まりました。約1か月前からLINE登録で通知を受け取れます。'"
            }
    
    # TIER_2_LINE: 緊急アラート、「残り〇日」で表現
    elif tier == "TIER_2_LINE":
        days_match = re.search(r'残り(\d+)日', message_text)
        if days_match and 7 <= int(days_match.group(1)) < 30:
            return {"status": "OK", "message": "LINE緊急アラートとして適切"}
        else:
            return {
                "status": "NG",
                "message": "LINE配信では『残り〇日』の具体数字を使う(『約1か月前』は不適切)",
                "suggestion": "修正例: '締切まで残り12日です。申請書類の準備はお済みですか？'"
            }
    
    # TIER_3_NEXT: 次回公募予告で啓発
    elif tier == "TIER_3_NEXT":
        if "gBizID" in message_text or "gビズID" in message_text:
            return {"status": "OK", "message": "次回予告として適切(gBizID啓発含む)"}
        else:
            return {
                "status": "NG",
                "message": "次回予告ではgBizID登録を啓発する",
                "suggestion": "修正例: '今回の〇〇助成金の締切は●月●日です。次回公募に向けて、gBizIDの登録をお勧めしています。'"
            }

# 例: TIER_2_LINE の検証
message = "緊急のお知らせです。〇〇助成金の締切まで残り18日です！"
result = validate_user_messaging("TIER_2_LINE", message)
print(result["status"])  # OK
print(result["message"])  # "LINE緊急アラートとして適切"
```

**検証方法:**
- [ ] TIER_1_SNS では「約1か月前から」「約1ヶ月前から」のどちらかが含まれているか
- [ ] TIER_2_LINE では「残り〇日」の具体数字が含まれているか
- [ ] TIER_3_NEXT では「gBizID」の文字が含まれているか
- [ ] 層ごとに異なるトーン・表現になっているか(SNS≠LINE≠次回予告)

---

## Step 5: 判定に迷う場合の上申手順

**目的:** 運用ルール境界や新規制度への対応で判断が分かれた場合、組織としての決定を取る。  
**実行コマンド:**
```python
def escalate_decision_request(scenario):
    """
    判断が分かれた案件を統括へ上申
    """
    escalation_template = """
【締切アラート3層ルール判定の相談】

制度名: {scheme_name}
締切日: {deadline_date}
残り日数: {days_remaining}

判定が分かれた理由:
{reason}

現在の検討案:
1. 〇〇
2. 〇〇
3. 〇〇

統括(アカリさん)経由で小柳さんへの上申をお願いします。
回答期限: 3営業日以内
    """.format(**scenario)
    
    return escalation_template

# 例: 境界ケース
scenario = {
    "scheme_name": "沖縄県中小企業緊急支援金",
    "deadline_date": "2026-11-01",
    "days_remaining": 7,  # ちょうど TIER_2 の下限
    "reason": "残り日数がちょうど7日で、TIER_1とTIER_2の境界。SNS継続か LINE配信開始かで意見が分かれた。"
}

print(escalate_decision_request(scenario))
```

**検証方法:**
- [ ] 上申テンプレートに制度名・締切日・判定理由が記入されているか
- [ ] 「統括経由で小柳さんへ」のルートを守っているか(ウタガイさん/ベッカイさんの意見を記録しているか)
- [ ] 回答期限(3営業日)を設定しているか

---

## 実装例

### パターン 1: TIER_1_SNS (30日以上) の文案作成

```
【施策】新規助成金のSNS告知
【対象制度】沖縄県デジタル化補助金
【締切日】2026-12-20
【残り日数】41日 → TIER_1_SNS 適用
【配信チャネル】Instagram

【NG パターン】(修正前)
-----
🎯新しい助成金！
締切: 12月20日
最大100万円までサポート！
応募はLINEで👇

👇 [LINE登録ボタン]

#助成金 #沖縄企業 #補助金
-----
問題点:
  • 「約1か月前から」という予告表現がない
  • 準備期間が十分にあることを伝わっていない
  • CVがLINE登録に直結していて、情報発見→登録のプロセスが不自然

【OK パターン】(修正後)
-----
🎯沖縄の企業さんへ
デジタル化補助金が決まりました🎉

▶️ 対象: 中小企業・個人事業主
▶️ 補助額: 最大100万円
▶️ 締切: 12月20日

準備期間は約1か月あります！
申請書類の作成・gBizIDの取得に
時間がかかるから、今から準備を
始めることをお勧めしています。

📲 締切が近くなったら LINEで
アラートをお送りします。

👇 沖縄企業のミカタ 登録はこちら
[詳細ページ]

#助成金 #沖縄企業のミカタ
-----
改善点:
  • 「約1か月」で十分な準備期間を示唆
  • 情報発見(Instagram) → 詳細確認 → LINE登録、の流れが自然
  • 「締切が近くなったらアラート」で、TIER_2への遷移を予告
```

### パターン 2: TIER_2_LINE (7-29日) の配信文案作成

```
【施策】締切アラートのLINE配信
【対象制度】沖縄県デジタル化補助金
【残り日数】15日 → TIER_2_LINE 適用
【配信先】LINE登録者

【テンプレート】
-----
⏰ 締切アラート

申請期限まで **残り15日** です❗

📌 「沖縄県デジタル化補助金」
  補助額: 最大100万円
  締切: 12月20日(木)

⚠️ 重要: 事前にgBizID登録が必須です
  (取得に数日かかるので、お早めに)

【確認項目】
✅ 売上低下の証明書
✅ 事業計画書
✅ gBizID 登録

💡 分からないことがあれば、
沖縄企業のミカタで詳細を確認するか、
専門家相談フォーム(無料)で聞けます。

👉 [詳細ページへ] [相談フォーム]

\#助成金 #沖縄企業のミカタ
-----
ポイント:
  • 「残り15日」で具体的な緊迫感
  • gBizID取得に「数日かかる」と明記(7日以内では準備不可の根拠)
  • 専門家相談への導線(士業送客の出口へ)
```

### パターン 3: TIER_3_NEXT (7日未満) の配信文案作成

```
【施策】次回公募予告 + gBizID啓発
【対象制度】沖縄県デジタル化補助金
【残り日数】3日 → TIER_3_NEXT 適用
【配信先】LINE登録者 / SNS

【テンプレート】
-----
📢 重要なお知らせ

デジタル化補助金の申請締切が
**12月20日(木)23時59分** です❗

申請予定のお客様は、お急ぎください。

---

💡 **次回公募に向けた準備ガイド**

次の公募は来年3月頃の予定です。

申請を成功させるためには、
事前に **gBizID** の登録が必須です。

🔗 gBizID登録はこちら
https://gbiz-id.go.jp/

**gBizID取得にかかる日数:**
  • 基本: 5営業日
  • 書類不備で修正が必要: 10営業日以上

次の公募に向けて、
今から準備を始めることをお勧めします✨

---

ご質問は沖縄企業のミカタへ
👉 [詳細ページ] [相談フォーム]

\#助成金 #gBizID
-----
ポイント:
  • 「今回は準備が間に合わない」と暗に示唆
  • gBizID の「5営業日」「10営業日以上」という具体的なリードタイムを明記
  • 「次の公募は3月頃」で希望を残す
```

---

## 本番前テスト

本番での実装の前に、以下のローカルテストを実行する。

**事前準備:**
```bash
# テスト環境の構築
mkdir -p tests/deadline-alert
cd tests/deadline-alert

# Python テスト用仮想環境
python -m venv venv && source venv/bin/activate
pip install pytest requests python-dotenv
```

**テスト実行チェックリスト:**

```bash
# 1. SKILL.md 形式検査
bash scripts/validate_skill_format.sh | grep hojo-deadline-alert
# 期待値: ✅ PASS

# 2. 残り日数計算テスト
python -c "
from datetime import datetime, timedelta
today = datetime.now()
deadline_30_days = today + timedelta(days=30)
deadline_15_days = today + timedelta(days=15)
deadline_3_days = today + timedelta(days=3)

print(f'30日後: {(deadline_30_days - today).days} days → TIER_1_SNS')
print(f'15日後: {(deadline_15_days - today).days} days → TIER_2_LINE')
print(f'3日後: {(deadline_3_days - today).days} days → TIER_3_NEXT')
"
# 期待値:
# 30日後: 30 days → TIER_1_SNS
# 15日後: 15 days → TIER_2_LINE
# 3日後: 3 days → TIER_3_NEXT

# 3. 禁止表現スキャンテスト
python scripts/scan_deadline_phrases.py --sample_text "締切は12月15日です。7日前までに準備してください。"
# 期待値: ⚠️ Line 1: '7日前' found → CRITICAL violation

# 4. 「約1か月前から」表現検証テスト
python scripts/validate_tier_messaging.py --tier TIER_1_SNS --message "約1か月前からLINE登録で通知を受け取れます"
# 期待値: ✅ OK - TIER_1_SNS に適切な表現

# 5. GitHub Actions ワークフロー確認
git push origin claude/superpowers-per-chat-3mbx56
# GitHub Actions で skill-validation.yml が実行される
# 期待値: skill-validation.yml での形式検査が PASS
```

**完了条件:**
- [ ] SKILL.md が形式検査を PASS する
- [ ] 残り日数計算が正確(30日・15日・3日の境界値が正しく層を判定)
- [ ] 禁止表現「7日前」「1週間前」がすべて検出される
- [ ] TIER_1_SNS では「約1か月前から」が含まれている
- [ ] TIER_2_LINE では「残り〇日」の具体数字が含まれている
- [ ] TIER_3_NEXT では「gBizID」の文字が含まれている
- [ ] GitHub Actions による自動検査に引っかかることがない

---

## 検証失敗時

以下の条件で検証が失敗する場合、対応を行う。

**残り日数計算エラー**
```
症状: 計算結果がマイナス (例: -5日)
原因: 締切日が過去の日付になっている、または今日の日付が誤っている
対応:
  1. 締切日が正しいか、原文URL で確認
  2. システムの日時設定を確認 (date コマンド)
  3. 計算式を再確認 (deadline - today)
自動起票: GitHub Issue #[auto-number] - "Deadline calculation error: negative days detected"
```

**禁止表現「7日前」が混入**
```
症状: スキャン結果に '7日前' が含まれている
原因: SNS投稿・LINE配信文案の作成時に禁止表現が誤挿入された
対応:
  1. 該当ファイルを特定し、grep で全文検索
  2. 「7日前」を「約1か月前から」または「残り〇日」に置換
  3. 再スキャンして全て削除されたことを確認
自動起票: GitHub Issue - "Forbidden deadline phrase '7日前' detected"
```

**層の判定エラー(TIER_1 vs TIER_2 の誤り)**
```
症状: 残り日数が29日なのに、TIER_1_SNS (SNS のみ)と判定されている
原因: 層判定ロジックの境界値が誤っている (>= 30 vs > 29)
対応:
  1. 境界値の定義を確認 (残り30日 → TIER_1 / 7-29日 → TIER_2)
  2. 条件式を修正
  3. テストケースで 30日、29日、7日、6日の 4 パターンを確認
自動起票: GitHub Issue - "Tier classification boundary error at X days"
```

**「約1か月前から」の表現がない**
```
症状: TIER_1_SNS の文案に「約1か月前から」が含まれていない
原因: SNS 投稿作成時に、統一表現を忘れた
対応:
  1. 文案を確認し、「1か月」「1ヶ月」「30日」など同義表現が含まれているか検索
  2. 表現が全くない場合、以下のテンプレートを使用:
     「締切の約1か月前からLINE登録で通知を受け取れます」
  3. 修正後、validate_tier_messaging.py で再検証
自動起票: GitHub Issue - "TIER_1_SNS messaging missing '約1か月前から' phrase"
```

**gBizID 啓発が TIER_3 に含まれていない**
```
症状: 次回公募予告(TIER_3)の配信文に gBizID が言及されていない
原因: 次回準備ガイド作成時に、重要要素を見落とした
対応:
  1. TIER_3 の文案を確認
  2. 以下の要素が含まれているか確認:
     - gBizID 登録リンク
     - 「5営業日」などの取得期間
  3. 不足していれば、パターン 3 の例を参考に追加
自動起票: GitHub Issue - "TIER_3_NEXT missing gBizID guidance"
```

---

## チェックリスト（本番運用時）

```
□ 制度DB に新しい助成金を追加するたびに、締切日を確認しているか
  └─ 原文URL (jGrants/各自治体) と照合

□ 残り日数の計算が正確か (毎日チェック)
  └─ 複数制度の層を一表で可視化する(月1回)

□ SNS投稿・LINE配信の文案作成時に禁止表現スキャンを実行しているか
  └─ 「7日前」「1週間前」は自動検出

□ 全 SNS 投稿に「約1か月前から」が含まれているか
  └─ タイムライン確認(週1回)

□ LINE 配信が正確なタイミング(TIER_2 で 7-29日のとき)で送信されているか
  └─ 配信ログを確認(月1回)

□ TIER_3 へ切り替わった制度に、gBizID啓発が含まれているか
  └─ 次回公募予告を確認(月1回)

□ 判断が分かれたケースで上申手順を守っているか
  └─ 統括(アカリさん)→ 小柳さんのルートを記録(全件)
```

---

## 関連スキル

- `hojo-accuracy-check` — 締切日・金額・要件の原文照合
- `shiryo-sakusei` — SNS 投稿・LINE メッセージの生成
- `humanizer` — 統一表現の自然な日本語化
- `shipping_gate` — 外向けコンテンツの品質検査
- `go-link-discipline` — SNS/LINE/Email の計測イベント一貫性確保
