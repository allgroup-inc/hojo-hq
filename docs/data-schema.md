# 制度データのスキーマ(data-schema)

CLAUDE.md「技術構成」が指すスキーマの実体。**正本は `scripts/validate_fukugiiro.py`** で、
本書はその読み下し。定数を変えるときは両方を同時に直すこと(片方だけ直すと乖離する)。

対象ファイル: `data/fukugiiro/seido.json`(沖縄)/ `data/yamanashi/seido.json`(山梨版)

## ファイル全体

```json
{ "updated_at": "YYYY-MM-DD HH:MM", "count": 261, "items": [ ... ] }
```

山梨版は `region` と `note` を追加で持つ。整形は `json.dump(..., ensure_ascii=False, indent=1)` +
末尾改行。**indent を変えると全行が差分になる**ので変えない。

## items[] の必須フィールド

| フィールド | 型 | 規約 |
|---|---|---|
| `id` | string | 一意。`fk-<主体>-<制度>` 形式(例 `fk-naha-kodomo-iryo`)。山梨県の制度は `ym-ken-` |
| `name` | string | 制度の正式名称。表記揺れがあるときは `match_tokens` で吸収する |
| `category` | string | 次の8語のみ: 子育て / 住まい / 医療・健康 / 教育 / 仕事・失業 / 生活支援 / 介護 / 防災・その他 |
| `life_events` | string[] | 次の11語のみ: 妊娠・出産 / 子育て / 入園・入学 / 就職・転職 / 失業 / 住宅取得・引越 / 病気・けが / 介護 / 障がい / 災害 / 低所得・生活苦 |
| `issuer` | string | 実施主体(例「こども家庭庁」「那覇市」) |
| `area` | string | 「全国」「沖縄県」または市町村名 |
| `target_household` | string | **断定しない。**「〜が対象となる可能性があります」で結ぶ(絶対ルール1) |
| `amount_note` | string | 金額。確認できないときは「要確認(公式ページでご確認ください)」 |
| `deadline_type` | string | 常時 / 期限あり / 年度内 / 要確認 |
| `how_to_apply` | string | 窓口の案内まで。**申請代行を示唆しない**(絶対ルール3) |
| `source_url` | string | **https のみ。**原文URL。これが最終根拠(絶対ルール1) |
| `verified` | bool | 原文と突合できたか |
| `status` | string | 検証済み / 要確認 / 終了 |

## 任意フィールド

| フィールド | 用途 |
|---|---|
| `deadline` | `deadline_type="期限あり"` のときの締切日(YYYY-MM-DD)。不明なら null のまま `status="要確認"` |
| `verified_at` / `verified_by` | 突合した日と根拠 |
| `notes` | 出典の表記など |
| `fetched_at` | 収集時刻。cron が毎回更新する |
| `match_tokens` | 制度名と公式ページ見出しの表記揺れを吸収する別名。突合の誤検知対策 |
| `assume_reachable` | bot遮断(403)が既知の自治体サイト。**収集側と検証側の両方が参照する**(片方だけに足さない) |
| `combine_note` | 併給の可否。exclusive / adjust / stackable。断定しない |

## 検査で落ちるもの

`python scripts/validate_fukugiiro.py --self-test` が門番。

- 必須フィールド欠け / 語彙外の category・life_events・deadline_type・status
- `source_url` が http(https のみ許可)
- **禁止表現**が本文に含まれる: 必ずもらえる / 絶対 / 審査なし / 誰でももらえる / 100% / 確実にもらえる / 無条件で支給
- 公的ドメイン(`.go.jp` `.lg.jp` `pref.okinawa.jp` `.city.` `.town.` `.vill.`)以外の `source_url` は
  **エラーではなく警告**。協会けんぽ・日本年金機構など正当な発信元があるため、守り部の目視で判断する

## 掲載してよい状態

- 原文と突合できた → `verified=true` / `status="検証済み"`
- 突合できない・内容が読み取れない → `verified=false` / `status="要確認"`。**消さずに「要確認」で出す**
- 制度が終了した → `status="終了"`

**取得できなかった(ネットワーク失敗)ことは、掲載が誤っている証拠にはならない。**
検証スクリプトは「取得不可」と「内容不一致」を分けて扱う(`scripts/kensho_fukugiiro.py`)。

## SNS・LINEで使うときの追加制約

締切のある制度を告知に使うときは締切3層ルールに従う(`.claude/skills/hojo-deadline-alert`)。

| 残り日数 | 使ってよい場所 |
|---|---|
| 30日以上 | SNS投稿 |
| 7〜29日 | LINE個別アラート |
| 7日未満 | 次回公募予告に切り替える |

「締切7日前アラート」は誤り。利用者向けの表現は「締切の約1か月前から」で統一する。
