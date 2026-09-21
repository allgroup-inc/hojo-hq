# Obsidian連携ガイド — 決定事項が「自動で」溜まる仕組み(2026-09-21 全面改訂)

最終更新: 2026-09-21 / 見直し期限: 2027-03-21

## 結論(いまの仕組み)

Obsidianの保管庫(vault)は、非公開リポジトリ **allgroup-inc/obsidian-vault** としてGitHub上にある。
そこへ **毎朝6時(日本時間)に、この公開リポジトリ hojo-hq の文書が自動で写される**
(obsidian-vault側の GitHub Actions `sync-public`。秘密鍵不要・人の操作ゼロ)。

```
各チャット(Claude Codeセッション)
   ↓ 決定・学び・仕組みを docs/ に議事・連携メモとして残す(月1で自動催促あり)
hojo-hq(公開・正本)                       glow-docs-private / kakei-crm(非公開・正本)
   ↓ 毎朝6時 自動同期(全文)                    ↓ 写さない(索引への案内のみ)
obsidian-vault(GitHub上の保管庫)
   ↓ Obsidianの Git プラグインが10分ごとに自動取り込み
小柳さんの手元のObsidian
```

写るもの: `CLAUDE.md` / `docs/**/*.md` / `reports/**/*.md` / `.claude/skills/*/SKILL.md`(→ `同期/hojo-hq/skills/`)。
加えて **決定事項タイムライン.md**(議事・連携メモを新しい順に一覧)と **同期/_同期記録.md** が自動生成される。
保管庫の入口ノートは `00_はじめに.md`。

非公開リポジトリの中身は写さない(顧客情報を含みうる文書を別の場所へ複製しない。安全装置の判断・2026-09-21)。
非公開側の索引は各リポジトリ内の `docs/全体マップ.md` / `docs/部品庫.md` を GitHub 上で直接読む。

## 小柳さんの手元で1回だけ必要なこと(1分)

Gitプラグインの設定は保管庫側で「10分ごとに自動取り込み・起動時にも取り込み・15分ごとに自動送信」に
変更済み。ただし設定ファイルが手元に届くまでは旧設定(取り込みなし)のままなので、**初回だけ**:
1. Obsidianでコマンドパレット(Ctrl/Cmd+P)→「Git: Pull」を実行
2. Obsidianを再起動

以後は何もしなくても、議事が増えるたび手元に映る。うまくいったかは `00_はじめに.md` が見えるかで分かる。

## 仕組みの場所(直したいとき)
- 同期スクリプト: obsidian-vault `_sync/sync_vault.py`(引数 `--src 名前=パス` を足せば別リポジトリも写せる)
- 定期実行: obsidian-vault `.github/workflows/sync-public.yml`(毎日 21:00 UTC = 06:00 JST、手動実行も可)
- プラグイン設定: obsidian-vault `.obsidian/plugins/obsidian-git/data.json`

## 「自動で溜まる」を保つルール
- 決定・仕組み・学びは、チャットに置き去りにせず `docs/` へ(議事は `議事_YYYYMMDD_件名.md`)
- 毎月1日、主要チャット(❶営業管理システム・❷市場調査・山梨版・家計総合システム)には整理担当セッションから
  「先月の決定を議事化して」という依頼が自動で届く(Routine)。❸事業構成&ゆんたくだけは Claude Code 外のため手動
- Obsidian側だけに決定事項を書かない(鏡に書いても元には映らない。正本はGitHub)

## 任意の強化(やらなくても回る)
- 非公開リポジトリも保管庫へ写したい場合: GitHub で「Fine-grained personal access token」(対象: glow-docs-private・kakei-crm・obsidian-vault、権限: Contents 読み書き)を作り、
  obsidian-vault の Secrets に `VAULT_SYNC_TOKEN` として登録すれば、同じスクリプトで写せる(ワークフローの追加は整理担当セッションへ依頼)。
  ただし顧客情報を含む文書が保管庫にも複製されることになるので、守り部の判断を先に通す
