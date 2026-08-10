# hojo-churn 隔離実行 セットアップ手順（実データを安全に動かす統制環境）

早期解約リスク保全システムを**実データ**で動かすための、非公開・統制環境 `hojo-churn` の
構築手順。この環境は「顧客個人情報の処理」を公開リポジトリ（`allgroup-inc/hojo-hq`）から
**物理的に分離**するためのもの（churn-pii-guard／守り部審査 #142 の項目5〜8に直接対応）。

> **前提（この手順に着手してよい条件）**
> 1. 守り部審査（Issue #142）が完了していること（本手順が項目5〜8の評価材料になる）。
> 2. 小柳さんの実データ投入決裁が下りていること。
> 3. `docs/churn/業務定数_決裁ログ.md` の 🟡 が全て 🟢 になっていること。
>
> **この3つが揃うまでは合成データ（private/demo）でのみ動かす。** 手順の“準備”（リポ枠の確保・
> runner の用意など、実データを入れない作業）は先行してよいが、**実データを1件でも入れるのは
> 上記3条件が揃った後**。判定は守り部・専門家、最終決裁は小柳さん（AIは判定者にならない）。

---

## 0. 全体像

```
[統制された社内環境（ネット非露出・アクセス制御）]
  ├─ 非公開リポ hojo-churn（private）
  │    ├─ scripts/churn/    ← 公開リポからコードのみ複製（PIIは持ち込まない）
  │    ├─ .github/workflows/churn-daily.yml  ← 雛形を配置
  │    └─ private/          ← 実データ・成果物（.gitignore・コミット禁止）
  └─ self-hosted runner（この環境内でのみ実行）
```

公開リポ側は**コードと設計だけ**を持ち、実データ・モデル・カルテHTMLは一切持たない。
両者のコードは公開リポを源泉にし、hojo-churn へは**一方向で複製**する（PIIは逆流させない）。

---

## 1. 非公開リポジトリ hojo-churn を用意する（審査項目8: 公開分離）

- 可視性 **private**。組織 `allgroup-inc` 配下に作成（アクセスは業務上必要な最小メンバーのみ）。
- README に冒頭で明記: 「顧客個人情報を扱う統制環境。公開リポと分離。private/ は絶対にコミット外」。
- `.gitignore` に最低限:
  ```
  private/
  *.csv
  risk_model.json
  *.html
  run_state_*.json
  ```
  （公開リポの `.gitignore` を踏襲し、実データ／モデル／出力がコミット対象に出ない状態を維持）

## 2. コードを複製する（PIIは持ち込まない）

- `scripts/churn/`・`tests/churn/`・`docs/churn/` を公開リポから hojo-churn へ複製。
- 実データ・合成データ・モデル・出力（`private/` 配下）は**複製しない**。
- 更新運用: 機能追加は公開リポのブランチで TDD → hojo-churn へコードのみ反映（サブモジュール or
  定期同期スクリプト）。**コードは公開リポが源泉、データは hojo-churn 限定**を崩さない。

## 3. self-hosted runner を登録する（審査項目5・8: アクセス制御・保管場所）

- 統制された社内ネットワーク内のマシンに GitHub Actions の self-hosted runner を登録。
- **インターネットに実データを露出させない**構成（外向きは GitHub API 等の必要最小限のみ）。
- runner マシン自体のディスク暗号化・OSアカウント権限の最小化（審査項目6・5）。
- runner のラベルを workflow の `runs-on: self-hosted` に一致させる。

## 4. シークレット/変数を設定する（審査項目5・6・9: 権限・暗号化・経路）

`churn-daily.yml`（雛形は `docs/churn/churn-daily.workflow.yml`）が参照する値を、
GitHub の **Secrets / Variables** に登録（リポジトリには絶対に平文で置かない）。

| 種別 | 名前 | 内容 | 備考 |
|---|---|---|---|
| secret | `CHURN_CSV_PATH` | 実申込CSVの**パス**（runner内） | 値そのものは runner ローカル。経路は暗号化 |
| secret | `CHURN_CMAP_PATH` | column_map JSON のパス | 実列名→system keyの対応 |
| secret | `CHURN_OUT_DIR` | 成果物の出力先（`private/` 配下） | 統制環境内に留める |
| variable | `CHURN_SPLIT` | バックテスト分割日 `YYYY-MM-DD` | 決裁済の検証設定 |

- エクスポート経路（顧客管理画面→CSV）と保管先の**委託契約・安全管理措置**を守り部が確認（審査項目9）。

## 5. workflow を配置する（審査項目7: 監査ログ）

- `docs/churn/churn-daily.workflow.yml` を hojo-churn の `.github/workflows/churn-daily.yml` へ配置。
- `permissions: contents: read`（最小権限）。成果物を GitHub 側へ upload しない（PII）。
- 実行のたびに `private/run_state_<日付>.json`（status/completed_steps/last_error/auc）と
  `private/.../snapshots/<月>/manifest.json`（行数・sha256）が残る＝**監査ログ**。
  誰がいつ実行したかは Actions の実行履歴と runner のアクセスログで独立点検可能（監査テキホウさん）。

## 6. 初回検証（実データ・段階導入）

1. **preflight を単体で回す**（`cli preflight`）: 不足キー・不足列・日付パス不能・件数を確認。
   ここで 🛑 なら column_map を直す。**publishは起きない**。
2. **pipeline を1回手動実行**（`workflow_dispatch`）: AUCゲートで止まるか／通るかを確認。
   - AUC < 決裁閾値 → `stopped_auc`（現場に出さない）。実データAUCを見て `AUC_MIN` を最終確定。
   - スキーマ不正 → `stopped_schema`。
3. **効果測定・学習は段階導入**（churn-retention-ops）: 単純比較で断定しない。先行/後発に分けて
   因果を測る運用に載せる。母数不足は「参考」。
4. 問題なければ `schedule`（日次）を有効化。**同日再実行はべき等**（run:<日付>）。

## 7. 保持期限・削除の運用（審査項目3を反映する場所）

- 守り部・専門家が決めた**保持年数**と**確実削除の手順**を、ここに追記して運用に組み込む
  （例: 保持N年→期限切れ月次スナップショットの削除ジョブ・バックアップ側の削除確認）。
- 現時点は**未確定**（#142 項目3）。決定するまで削除運用は空欄。決定後、削除の自動化も
  resilient-agent-design（べき等・完了条件・監査ログ）に沿って追加する。

---

## この手順が審査 #142 に対して示せること（対応表）

| #142 審査項目 | この手順での担保 |
|---|---|
| 5. アクセス制御 | 手順1（最小メンバー）・3（runner権限最小）・4（Secrets） |
| 6. 暗号化 | 手順3（ディスク暗号化）・4（経路暗号化） |
| 7. 監査ログ | 手順5（run_state・manifest・Actions履歴・runnerログ） |
| 8. 保管場所・公開分離 | 手順1・2・3（private・社内・ネット非露出・コード一方向複製） |
| 9. 委託・エクスポート経路 | 手順4（経路と委託契約を守り部確認） |

※ 項目1（利用目的）・2（最小化の一部）・3（保持期限）・4（口座フラグの目的内判断）は
**人（守り部・専門家）の判断**。本手順は環境統制の担保であり、法的判断の代替ではない。
