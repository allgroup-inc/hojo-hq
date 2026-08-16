# オブシディアン連携 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** hojo-hqのClaude Codeセッションが、個人アカウント配下の非公開GitHubリポジトリ
(オブシディアンvaultのGit化)へ、セッションの区切りごとに自動でノートを記録できるようにする。

**Architecture:** vault用の非公開GitHubリポジトリを新規作成し、事業ごとのフォルダ構成で
初期化する。hojo-hqのCLAUDE.mdに常設ルールを追記し、以後のセッションが明示的な指示なしでも
このリポジトリへ記録するようにする。オブシディアン側は「Obsidian Git」プラグイン(人が
ローカルで導入)がこのリポジトリと自動同期する。

**Tech Stack:** GitHub(リポジトリ・API)、Markdown、Obsidian Git(コミュニティプラグイン、
人がローカルで導入)

## Global Constraints

- vaultリポジトリは必ず非公開(private)で作成する(design docのリスク項目)
- 書き込みは会話の区切り単位のみ。1メッセージごとの書き込みは行わない
- 重複防止は「トピックごとに1ファイル、既存があれば追記・更新」方式のみ(意味的重複検出は
  スコープ外)
- 今回はhojo-hq1リポジトリのみで試験導入する。他事業リポジトリへの展開は対象外
- vaultリポジトリ名: `allgroup-vault`、所有: `takeshikoyanagi9-lab`(個人アカウント。
  `mcp__github__get_me`で確認済み、このセッションから直接作成可能)

---

### Task 1: vaultリポジトリの作成とフォルダ雛形

**Files:**
- Create(GitHub上): `takeshikoyanagi9-lab/allgroup-vault`(非公開リポジトリ)
- Create: `README.md`(vaultリポジトリのルート)
- Create: `hojo-hq/README.md`
- Create: `glow-ma/README.md`
- Create: `フクギイロ/README.md`
- Create: `hikari/README.md`
- Create: `kakei/README.md`
- Create: `エンライフ/README.md`
- Create: `個人/README.md`

**Interfaces:**
- Produces: vaultリポジトリの存在とフォルダ構成(Task 2でこのリポジトリ名・URLを参照する)

- [ ] **Step 1: リポジトリを作成する**

`mcp__github__create_repository` を呼ぶ(owner指定なし=個人アカウントに作成される):
- name: `allgroup-vault`
- description: `ALLGROUP横断のオブシディアンノート置き場(Claude Code連携用・非公開)`
- private: `true`
- autoInit: `true`

- [ ] **Step 2: 作成されたリポジトリをクローンする**

```bash
git clone https://github.com/takeshikoyanagi9-lab/allgroup-vault /workspace/allgroup-vault
cd /workspace/allgroup-vault
```

- [ ] **Step 3: ルートREADME.mdを書く**

`/workspace/allgroup-vault/README.md` の内容を以下に置き換える:

```markdown
# ALLGROUP横断ノート(オブシディアンvault)

このリポジトリは、ALLGROUP内の複数事業のClaude Codeセッションが記録するノートの
置き場です。オブシディアン(ノートアプリ)の「Obsidian Git」プラグインで、
ローカルのvaultフォルダと自動同期しています。

## フォルダ構成

- `hojo-hq/` — 沖縄企業のミカタ(補助金・助成金サイト)関連
- `glow-ma/` — GLOW M&A・営業管理システム関連
- `フクギイロ/` — もらいわすれ堂関連
- `hikari/` — hikari事業関連
- `kakei/` — kakei事業関連
- `エンライフ/` — エンライフ事業関連
- `個人/` — 事業をまたがない個人メモ

## 運用ルール

- **トピックごとに1ファイル**。同じ話題のノートが既にあれば、新規作成せず追記・更新する
- 書き込みは会話の区切り単位(1メッセージごとではない)
- 各事業のCLAUDE.mdに、このリポジトリへの記録ルールが定義されている
```

- [ ] **Step 4: 事業ごとのフォルダにプレースホルダーREADMEを置く**

各フォルダに以下の内容で `README.md` を作る(gitは空フォルダを追跡できないため)。
例として `hojo-hq/README.md`:

```markdown
# hojo-hq(沖縄企業のミカタ)

沖縄企業のミカタ(hojo-hqリポジトリ)関連のノートを置く場所です。
Claude Codeセッションが、会話の区切りごとにここへ記録します。
```

同じ形式で `glow-ma/README.md`(見出しを`# glow-ma(GLOW M&A)`に変更)、
`フクギイロ/README.md`(`# フクギイロ(もらいわすれ堂)`)、`hikari/README.md`
(`# hikari`)、`kakei/README.md`(`# kakei`)、`エンライフ/README.md`
(`# エンライフ`)、`個人/README.md`(`# 個人メモ`)をそれぞれ作る。

- [ ] **Step 5: コミット・push**

```bash
cd /workspace/allgroup-vault
git add README.md hojo-hq/README.md glow-ma/README.md フクギイロ/README.md hikari/README.md kakei/README.md エンライフ/README.md 個人/README.md
git commit -m "chore: 初期フォルダ構成とREADMEを作成"
git push origin main
```

- [ ] **Step 6: 作成結果を確認する**

`mcp__github__get_file_contents` (または同等のツール)で
`takeshikoyanagi9-lab/allgroup-vault` の `README.md` を取得し、Step 3の内容が
反映されていることを確認する。

Expected: リポジトリがprivateで存在し、8個のREADME.md(ルート+7フォルダ)が
コミットされている。

---

### Task 2: hojo-hqのCLAUDE.mdにvault連携ルールを追記

**Files:**
- Modify: `CLAUDE.md`(hojo-hqリポジトリのルート)

**Interfaces:**
- Consumes: Task 1で作成した `takeshikoyanagi9-lab/allgroup-vault` というリポジトリ名

- [ ] **Step 1: CLAUDE.mdの該当箇所を確認する**

```bash
grep -n "^## " /home/user/hojo-hq/CLAUDE.md
```

既存の見出し構成を確認し、「マルチAI連携」節の直後あたりに新しい節を追加する場所を決める。

- [ ] **Step 2: 新しい節を追記する**

`## マルチAI連携(2026-08-06 小柳さん決裁)` 節の直後に、以下を追記する
(既存の書式・トーンに合わせた文面):

```markdown
## オブシディアン連携(2026-08-16 小柳さんとの壁打ちで導入)
複数事業をまたぐ知識ベースとして、個人アカウント配下の非公開リポジトリ
`takeshikoyanagi9-lab/allgroup-vault`(オブシディアンvaultのGit化)へ、
会話の区切りごとに記録する。1メッセージごとの書き込みは行わない。
- 記録先はこのリポジトリなら `allgroup-vault/hojo-hq/` 配下
- **トピックごとに1ファイル**。既存の同トピックのノートがあれば新規作成せず
  追記・更新する(vaultリポジトリのREADME参照)
- 書き込み前に対象フォルダの既存ファイルを確認し、無ければ新規作成、あれば
  そのファイルを追記・更新する
- まずhojo-hq単体の試験運用。他事業リポジトリへの展開は別途判断
- 設計の経緯: docs/superpowers/specs/2026-08-16-obsidian-vault-integration-design.md
```

- [ ] **Step 3: 反映を確認する**

```bash
grep -n "オブシディアン連携" /home/user/hojo-hq/CLAUDE.md
```

Expected: 新しい節見出しがヒットする。

- [ ] **Step 4: コミット**

```bash
cd /home/user/hojo-hq
git add CLAUDE.md
git commit -m "docs: CLAUDE.mdにオブシディアン連携の常設ルールを追記"
```

---

### Task 3: 小柳さん側のセットアップ(Obsidian Gitプラグイン)

この作業はローカルPC上のオブシディアンアプリで行うため、Claude Codeのセッションからは
実行できない。以下は小柳さんへの案内文として使う(そのままチャットで提示する)。

**Files:** なし(人が行う手動セットアップ)

- [ ] **Step 1: 案内文を小柳さんに提示する**

以下をそのままメッセージとして送る:

```
オブシディアン側の設定をお願いします(5〜10分程度)。

1. オブシディアンを開き、設定 → コミュニティプラグイン → 「制限モードをオフ」
   (初回のみ)→ 「閲覧」→ 検索欄に「Git」と入力
2. 「Obsidian Git」というプラグインをインストール → 有効化
3. 左のコマンドパレット(Ctrl/Cmd+P)で「Git」と検索すると、Git関連のコマンドが
   出てくることを確認
4. 今の既存vaultをこのリポジトリと紐づける場合は、Obsidian Gitの設定画面から
   リモートURL(https://github.com/takeshikoyanagi9-lab/allgroup-vault)を設定
   (具体的な紐づけ手順は既存vaultの状態によって変わるため、設定画面を開いた
   スクリーンショットを送ってもらえれば、次のステップを一緒に確認します)
5. 設定完了後、Obsidian Gitの「Pull」コマンドを実行し、Task 1で作った
   フォルダ構成(hojo-hq/ 等7フォルダ)がオブシディアン側に表示されることを確認
```

- [ ] **Step 2: 小柳さんからの確認を待つ**

小柳さんがStep 1を完了し、フォルダ構成がオブシディアン側に表示されたことを
報告したら、このタスクを完了とする。うまくいかない場合は、送られてきた
スクリーンショットをもとに個別に案内する(このリポジトリの他のUI操作案内と
同じ進め方)。

---

## Self-Review Notes

- Spec covery: design docの「1. スコープ」「3. 書き込みのトリガー」「4. 重複防止」
  「5. セットアップ手順」「6. リスク・注意点」は、Task 1(フォルダ構成+非公開リポジトリ)・
  Task 2(トリガー+重複防止ルールのCLAUDE.md反映)・Task 3(セットアップ)でそれぞれ
  カバーしている
- 「1メッセージごとの書き込みをしない」「非公開を維持する」という設計上の制約は
  Global Constraintsに明記し、Task内の文面にも反映した
- Task 3はコード変更を伴わないため、通常のテスト手順の代わりに「人からの確認報告」を
  完了条件とした
