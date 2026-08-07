# マルチAI連携セットアップガイド(Claude Code × Gemini / ChatGPT)

作成: 2026-08-06 / 対象: hojo-hq 全部門(まず検証部・SNS部での活用を想定)
位置づけ: **提案・手順書**。本番運用への組み込み(コスト発生・体制変更)は小柳さん決裁が前提(絶対ルール5)。

---

## 1. 目的と全体像

Claude Code で作業しながら、Gemini や ChatGPT(OpenAI)を**自動で**呼び出し、
セカンドオピニオン取得・クロスチェック・並行作業に使う仕組みのセットアップ手順。

| パターン | 難易度 | 向いている用途 | 自動化の度合い |
|---|---|---|---|
| A. 他社CLI + CLAUDE.mdルール | ★(最小) | セカンドオピニオン、レビュー | Claudeがルールに従い自発的に実行 |
| B. MCPサーバー接続 | ★★ | 会話中のツールとして常用 | Claudeが必要と判断したら自動呼び出し |
| C. Hooks(強制実行) | ★★ | 「毎回必ず」のチェック | Claudeの判断に依存せず100%実行 |
| D. GitHub Actions組み込み | ★★★ | 収集パイプラインの二重検証 | 完全自動(cron) |

まず **パターンA を1日で試し、効果があれば B/C/D に進む** のがおすすめ。

---

## 2. パターンA: 他社CLI + CLAUDE.mdルール(最小構成・推奨スタート)

ローカルの Claude Code 環境で、Gemini CLI / Codex CLI をインストールし、
CLAUDE.md に「いつ他AIに聞くか」のルールを書くだけ。

### 手順

1. **Gemini CLI のインストール**(Node.js 20以上が必要)
   ```bash
   npm install -g @google/gemini-cli
   gemini   # 初回起動でGoogleアカウント認証(無料枠あり)またはAPIキー設定
   ```
   非対話で使う場合:
   ```bash
   gemini -p "このテキストの事実関係をチェックして: ..."
   ```

2. **(任意)OpenAI Codex CLI のインストール**
   ```bash
   npm install -g @openai/codex
   codex exec "この関数の問題点を指摘して"   # 非対話実行
   ```

3. **CLAUDE.md に運用ルールを追記**(例)
   ```markdown
   ## マルチAI運用ルール
   - 制度データ(締切・金額・要件)を整形・更新したときは、
     `gemini -p "..."` で同じ原文からの抽出を再実行し、結果を突き合わせる。
     不一致項目は断定せず「要確認」とする。
   - SNS投稿文の最終稿は gemini にも自然さチェックを依頼し、指摘があれば反映を検討する。
   - 他AIの回答は参考意見。最終判断は原文URL照合を優先する。
   ```

これだけで、Claude Code は該当作業のたびに Bash 経由で Gemini を呼び、結果を突き合わせるようになる。

### コスト
- Gemini CLI は個人Googleアカウント認証で無料枠(回数制限あり)から開始可能
- Codex CLI は ChatGPT Plus 等のサブスクまたは OpenAI APIキーが必要

---

## 3. パターンB: MCPサーバー接続

他社LLMをツール化した MCP サーバーを接続すると、Claude が会話の流れで自動的に呼び出せる。

### 手順

1. コミュニティ製MCPサーバーの追加例(Gemini):
   ```bash
   claude mcp add gemini -- npx github:ShunL12324/claude-code-gemini-mcp
   ```

2. プロジェクト共有にする場合は `.mcp.json` をリポジトリに置く:
   ```json
   {
     "mcpServers": {
       "gemini": {
         "type": "stdio",
         "command": "npx",
         "args": ["github:ShunL12324/claude-code-gemini-mcp"],
         "env": { "GEMINI_API_KEY": "${GEMINI_API_KEY}" }
       }
     }
   }
   ```
   ※ APIキー本体は書かない。環境変数参照のみ(キーは各自のOS環境変数か `settings.local.json` へ)。

3. 使い方: 「この判断、Geminiのセカンドオピニオンも取って」と言えば自動でツール呼び出しされる。

---

## 4. パターンC: Hooks(毎回必ず実行させる)

「Claudeの判断任せでなく、特定操作のたびに必ず他AIチェックを走らせたい」場合。
`.claude/settings.json` の PostToolUse フックを使う。

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "~/.claude/hooks/gemini-check.sh"
          }
        ]
      }
    ]
  }
}
```

`gemini-check.sh` の骨子(標準入力でツール実行情報がJSONで渡る):
```bash
#!/bin/bash
INPUT=$(cat)
FILE=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')
case "$FILE" in
  */data/*.json)
    gemini -p "次の助成金データに事実誤認の兆候がないか点検して: $(cat "$FILE")" \
      > /tmp/gemini-check-result.txt
    ;;
esac
```

注意: フックは毎回実行されるため、対象を絞らないとコストと待ち時間が膨らむ。matcher とスクリプト内の条件分岐で必ず限定すること。

---

## 5. パターンD: 収集パイプラインへの組み込み(hojo-hq 応用)

検証部(kensho.md)の二重検証を自動化する構成案。

```
GitHub Actions (cron 1日4回)
  ├─ 収集: jGrants API・自治体サイト巡回
  ├─ 整形: Claude API → JSON
  ├─ ★クロスチェック: Gemini API に同じ原文を渡し独立抽出
  ├─ 突合: 締切・金額・要件が一致 → 公開 / 不一致 → 「要確認」フラグ
  └─ 公開: GitHub Pages
```

- ワークフローに `GEMINI_API_KEY` を GitHub Secrets として追加し、整形ステップの後に Gemini 抽出+diff 比較ステップを挟む
- **絶対ルール1(正確性最優先)との整合**: 2つのAIが独立に抽出して一致した項目のみ断定表示、不一致は自動で「要確認」に落ちるため、ルールをむしろ強化する方向の仕組み
- 導入判断・API費用は小柳さん決裁事項

---

## 6. 注意点(共通)

| 項目 | 内容 |
|---|---|
| APIキー管理 | リポジトリにコミットしない。GitHub Secrets / OS環境変数 / `settings.local.json`(git管理外)のみ |
| コスト | 他社API利用料が別途発生。「重要案件のみ」「制度データのみ」など対象を限定する運用ルールをCLAUDE.mdに明記 |
| レート制限 | 1日4回×150件超の全件クロスチェックは無料枠を超える可能性。新規・変更差分のみチェックする設計にする |
| 回答の扱い | 他AIの出力も誤り得る。最終根拠は常に原文URL(絶対ルール1)。AI同士の一致は「断定してよい」の必要条件であって十分条件ではない |
| リモート環境の制約 | Claude Code のクラウドセッション(この環境)は外部通信がプロキシ制限され他社CLIも未導入。パターンA〜Cはローカル環境またはCLI等を導入した専用環境で実施 |

---

## 7. 導入ロードマップ(案)

1. **今週**: ローカルで パターンA(Gemini CLI + CLAUDE.mdルール1行)を試行。SNS投稿文チェックなど低リスク業務で効果を見る
2. **2週間後**: 効果があれば パターンD の設計に着手(まず週次バッチで差分のみクロスチェック)
3. **判断**: API費用見積りとあわせて小柳さんへ上申 → 決裁後に本番組み込み
