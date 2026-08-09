# うごくAIレシピ_LINE開設キット(小柳さん用・作業約15分)

他事業(ミカタ/フクギ)のLINEと分離するため、AIレシピ**専用**のLINE公式アカウントを作り、
通知の届き先を切り替えるキットです(2026-08-09 小柳さん指示)。
結果マガ専用LINEのときと同じ手順です。

## 1. LINE公式アカウントを新規作成(5分)

1. https://developers.line.biz/ にログイン(既存のLINEビジネスIDでOK)
2. **新しいプロバイダー**を作成 → 名前: `airecipe`(任意)
3. その中に **Messaging APIチャネル**を作成
   - チャネル名: `うごくAIレシピ`
   - 業種: 個人/その他 でOK

## 2. トークンとユーザーIDを取得(5分)

1. 作成したチャネルの **[Messaging API設定]** タブ → 一番下の
   **チャネルアクセストークン(長期)** → [発行] → コピー
2. **[チャネル基本設定]** タブ → 一番下の **あなたのユーザーID**(`U`で始まる文字列)→ コピー
3. スマホのLINEで、このアカウントを**友だち追加**(Messaging API設定にあるQRコード)
   ※友だち追加しないと通知が届きません

## 3. GitHub Secrets に登録(3分)

https://github.com/allgroup-inc/hojo-hq/settings/secrets/actions → [New repository secret]

| Name(この名前どおりに) | Secret |
|---|---|
| `AIRECIPE_LINE_CHANNEL_ACCESS_TOKEN` | 手順2-1のトークン |
| `AIRECIPE_LINE_ADMIN_USER_ID` | 手順2-2のユーザーID |

## 4. 疎通テスト(2分)

1. https://github.com/allgroup-inc/hojo-hq/actions/workflows/airecipe-line-test.yml
2. [Run workflow] → main のまま実行
3. スマホに「✅【AIレシピ】専用LINE連携テスト成功」が届けば完了
   - 失敗した場合はログに理由が日本語で出ます(未登録/他事業のトークンを誤登録 など)

## 5. 完了後の動き

- 毎週**火・金 09:35** の下書き完成通知は、以後この専用LINEだけに届きます
- 専用LINEを設定するまでの間は、通知はどこにも飛びません(誤送信防止)。
  下書き自体は https://github.com/allgroup-inc/hojo-hq/tree/main/posts/airecipe に生成され続けます
- ミカタ・フクギ側のLINEには、AIレシピ関連の通知は今後一切流れません
