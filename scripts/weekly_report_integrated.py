#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
統合週次レポート初号機(ループ1「計器盤ループ」— docs/達成確率を上げる設計_仕組みの接続_2026-07-31.md)
Grp信号・個人ストック信号・決裁キューを毎週月曜の1通に集約する。
weekly_report_fukugiiro.py の流儀に合わせた純Python・標準ライブラリのみ。

設計の芯:
- 機械が断定できない数字(ミカタLINE登録数・エンライフboard・GLOW台帳)は勝手に埋めない。
  確認先を示し、記入欄を残す(weekly_report_fukugiiro.py と同じ流儀)
- 個人ストックは**件数とゲート状態のみ**。金額・顧客名・PIIは公開リポジトリに一切書かない
  (data/personal/stock_status.json に金額系キーが混入したら読込を拒否する)
- 決裁キュー(docs/決裁キュー.md)は残数と最古の滞留を数値化する(決裁レイテンシ=唯一の人間起因変数)
- パースに失敗したセクションは安全にスキップし、確認先だけ案内する(レポート全体は落とさない)
- 方程式4(evalなき自動化は必ず事故る)に従い --self-test を実装。CIに載せる前提

data/personal/stock_status.json のスキーマ例(金額フィールドは持たせない):
{
  "updated_at": "2026-08-02",
  "note": "件数とゲート状態のみ。金額・顧客名・PIIは書かない(公開リポジトリ)",
  "products": [
    {"id": 1, "name": "ノビシロ顧問(AIコンサル)", "contracts": 0,
     "gate": "点線・未検証", "gate_criteria": "初回3社の手売り"}
  ]
}
gate の値: 「点線・未検証」→(ゲート合格で)「実線・検証済み」/(不合格で)「撤退」

実行:
  python3 scripts/weekly_report_integrated.py              # 生成
  python3 scripts/weekly_report_integrated.py --self-test  # 自己テスト
出力: reports/integrated/<YYYY>-W<週番号>_weekly.md と reports/integrated/latest.md
"""
import json
import os
import random
import re
import sys
from datetime import datetime, timezone, timedelta

JST = timezone(timedelta(hours=9))
BASE = os.path.join(os.path.dirname(__file__), "..")
SUBSIDIES = os.path.join(BASE, "data", "subsidies.json")
STOCK = os.path.join(BASE, "data", "personal", "stock_status.json")
FUKUGIIRO_LATEST = os.path.join(BASE, "reports", "fukugiiro", "latest.md")
KESSAI = os.path.join(BASE, "docs", "決裁キュー.md")
WORKFLOWS = os.path.join(BASE, ".github", "workflows")
OUT_DIR = os.path.join(BASE, "reports", "integrated")

AUDIT_SAMPLE_N = 3    # CLAUDE.md 三名体制ルール5 / 運用規程G2: 週次で無作為3件を再点検

KPI_KEISAI = 150      # CLAUDE.md 支持KPI: 掲載制度数 常時150件以上
KPI_FRESH_HOURS = 24  # CLAUDE.md 支持KPI: 更新遅延24時間以内
LATENCY_RED_DAYS = 14  # ループ3閾値案: 最古の決裁待ち14日超で🔴

# 個人ストック台帳に混入してはいけないキー(金額・PII)。見つけたら読込拒否
FORBIDDEN_KEY_TOKENS = (
    "amount", "yen", "price", "revenue", "income", "salary",
    "金額", "円", "単価", "売上", "報酬", "手取",
    "name_person", "氏名", "住所", "電話", "email", "mail",
)

DATE_RE = re.compile(r"(20\d{2}-\d{2}-\d{2})")


# ---------------------------------------------------------------- Grp信号

def load_subsidies(path=SUBSIDIES):
    """ミカタ制度DB(data/subsidies.json)。読めなければ None(確認先案内へ)。"""
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def freshness(updated_at, now=None):
    """updated_at('YYYY-MM-DD HH:MM')から鮮度を判定。KPI: 更新遅延24時間以内。"""
    try:
        dt = datetime.strptime(updated_at, "%Y-%m-%d %H:%M").replace(tzinfo=JST)
    except Exception:
        return "不明", None
    hours = ((now or datetime.now(JST)) - dt).total_seconds() / 3600
    label = "✅ 24時間以内" if hours <= KPI_FRESH_HOURS else f"⚠ {hours:.0f}時間経過(要確認)"
    return label, hours


def keisai_signal(count):
    """掲載件数の🟢🟡🔴(ループ1のGrp信号)。"""
    if count >= KPI_KEISAI:
        return "🟢"
    return "🟡" if count >= 100 else "🔴"


def parse_fukugiiro_latest(txt):
    """もらいわすれ堂 最新週次レポ(reports/fukugiiro/latest.md)から
    北極星の表2行とボトルネック・次の一手を転記用に抜き出す。取れない項目は None。"""
    week = None
    m = re.search(r"週次レポート\s+(\S+)", txt)
    if m:
        week = m.group(1)
    bn = re.search(r"\*\*ボトルネック\*\*[::]\s*(.+)", txt)
    # 括弧は全角/半角の揺れを許容する(生成元の版差で混在しうる)
    na = re.search(r"\*\*次の一手[((]今週これだけ[))]\*\*[::]\s*(.+)", txt)
    star_rows = [ln.strip() for ln in txt.splitlines()
                 if ln.strip().startswith("| 実受給額") or ln.strip().startswith("| 支援世帯数")]
    return {
        "week": week,
        "bottleneck": bn.group(1).strip() if bn else None,
        "next_action": na.group(1).strip() if na else None,
        "star_rows": star_rows,
    }


def load_fukugiiro_latest(path=FUKUGIIRO_LATEST):
    try:
        with open(path, encoding="utf-8") as f:
            return parse_fukugiiro_latest(f.read())
    except Exception:
        return None


# ---------------------------------------------------------------- 個人ストック

def find_forbidden_keys(obj, path=""):
    """dict/list を再帰し、金額・PII系トークンを含むキー名を列挙する。"""
    bad = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            kl = str(k).lower()
            if any(tok in kl for tok in FORBIDDEN_KEY_TOKENS):
                bad.append(f"{path}{k}")
            bad.extend(find_forbidden_keys(v, f"{path}{k}."))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            bad.extend(find_forbidden_keys(v, f"{path}[{i}]."))
    return bad


def load_stock(path=STOCK):
    """個人ストック台帳(件数とゲート状態のみ)。
    戻り値: (data, error)。ファイル無し→(None, None)=「未計測」表示。
    金額系キー混入や壊れたJSON→(None, 理由)=安全側で表を出さない。"""
    if not os.path.exists(path):
        return None, None
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        return None, f"JSON読込エラー: {e}"
    bad = find_forbidden_keys(data)
    if bad:
        return None, ("金額・PII系のキーを検出したため読込を拒否: " + ", ".join(bad[:5])
                      + "。公開リポジトリには件数とゲート状態のみ置く(本スクリプトdocstring参照)")
    if not isinstance(data.get("products"), list):
        return None, "products 配列がありません(スキーマは本スクリプトdocstring参照)"
    return data, None


def render_stock_section(stock, error):
    head = "## 2. 個人ストック信号 — 8商品の契約件数とゲート状態(金額なし・件数のみ)\n"
    if error:
        return head + f"\n⚠ data/personal/stock_status.json をスキップ({error})\n"
    if stock is None:
        return head + (
            "\n**未計測**(data/personal/stock_status.json が未作成)。"
            "件数とゲート状態のみのスキーマで作成すると、ここが自動で埋まります。\n"
        )
    rows = []
    total = 0
    solid = 0
    for p in stock["products"]:
        n = p.get("contracts", 0)
        total += n if isinstance(n, int) else 0
        gate = p.get("gate", "?")
        if str(gate).startswith("実線"):
            solid += 1
        rows.append(f"| {p.get('id','')} | {p.get('name','?')} | {n} 件 | {gate} | {p.get('gate_criteria','—')} |")
    return (
        head
        + f"\n更新: {stock.get('updated_at','?')}。"
        + "ステージゲート運用: 最初の3件を手売りで需要検証 → 合格で〔実線〕昇格 / 不合格は表から外す。\n\n"
        + "| # | 商品 | 契約 | ゲート | 昇格条件 |\n|---|---|---|---|---|\n"
        + "\n".join(rows)
        + f"\n\n合計契約 **{total} 件** / 実線昇格 **{solid} / {len(stock['products'])} 商品**"
        + ("(全商品が点線=まだ市場検証ゼロ。件数が動いたらこの表が語り始める)" if solid == 0 else "")
        + "\n"
    )


# ---------------------------------------------------------------- 決裁キュー

def parse_kessai(txt, today=None):
    """決裁キュー(docs/決裁キュー.md)から未チェック項目数・最古項目・滞留日数を集計。"""
    today = today or datetime.now(JST).date()
    unchecked = [re.sub(r"^\s*-\s*\[ \]\s*", "", ln).strip()
                 for ln in txt.splitlines() if re.match(r"^\s*-\s*\[ \]", ln)]
    if not unchecked:
        return {"count": 0, "items": [], "oldest_item": None,
                "oldest_date": None, "stale_days": None}
    dated = []
    for item in unchecked:
        m = DATE_RE.search(item)
        if m:
            try:
                dated.append((datetime.strptime(m.group(1), "%Y-%m-%d").date(), item))
            except ValueError:
                pass
    if dated:
        oldest_date, oldest_item = min(dated, key=lambda t: t[0])
        stale = (today - oldest_date).days
    else:
        # 日付が無い場合、並び順ルール(上から順=最速)に従い先頭項目を最古扱い
        oldest_date, oldest_item, stale = None, unchecked[0], None
    return {
        "count": len(unchecked),
        "items": unchecked,          # §4の無作為点検プールに使う
        "oldest_item": oldest_item,
        "oldest_date": oldest_date.isoformat() if oldest_date else None,
        "stale_days": stale,
    }


def _shorten(text, limit=70):
    text = re.sub(r"\*\*|~~", "", text or "")
    return text if len(text) <= limit else text[: limit - 1] + "…"


def render_kessai_section(q):
    head = "## 3. 決裁キュー — 残数と最古の滞留(決裁レイテンシ=唯一の人間起因変数)\n"
    if q is None:
        return head + "\n⚠ docs/決裁キュー.md のパースに失敗したためスキップ(ファイルを直接確認してください)\n"
    if q["count"] == 0:
        return head + "\n🟢 未チェックの決裁待ちは **0件**。キューは空です。\n"
    if q["stale_days"] is None:
        latency = "各項目に日付記載なし(最古=キュー先頭項目とみなす)"
        signal = "🟡"
    else:
        signal = "🔴" if q["stale_days"] > LATENCY_RED_DAYS else ("🟡" if q["stale_days"] > 7 else "🟢")
        latency = f"最古 {q['oldest_date']} 起票 → **滞留 {q['stale_days']} 日**(🔴閾値: {LATENCY_RED_DAYS}日超)"
    return (
        head
        + f"\n| 指標 | 値 |\n|---|---|\n"
        + f"| 未チェック項目数 | **{q['count']} 件** |\n"
        + f"| 決裁レイテンシ | {signal} {latency} |\n"
        + f"| 最古の項目 | {_shorten(q['oldest_item'])} |\n"
        + "\n決裁は「採用/不採用/保留+理由1行」の3択返信でOK(全文: docs/決裁キュー.md)。\n"
    )


def load_kessai(path=KESSAI):
    try:
        with open(path, encoding="utf-8") as f:
            return parse_kessai(f.read())
    except Exception:
        return None


# ---------------------------------------------------------------- 監査所見(独立監査)

def list_scheduled_workflows(path=WORKFLOWS):
    """cron定期実行のワークフロー一覧(= L3/L4自動運転。無作為点検の対象プール)。

    読めない場合は空リストを返す(レポート全体は落とさない)。
    """
    out = []
    try:
        for fn in sorted(os.listdir(path)):
            if not fn.endswith((".yml", ".yaml")):
                continue
            with open(os.path.join(path, fn), encoding="utf-8") as f:
                txt = f.read()
            if re.search(r"^\s*schedule:", txt, re.M) and "cron:" in txt:
                out.append(fn)
    except Exception:
        return []
    return out


def pick_audit_targets(week_tag, workflows, kessai_items, n=AUDIT_SAMPLE_N):
    """今週の無作為点検3件を**決定性**で選ぶ(週番号がシード)。

    同じ週なら何度生成しても同じ3件になる(べき等)。週が変われば組み合わせが変わる。
    resilient-agent-design: 乱数を実行時刻に依存させない(再生成で結果がぶれない)。
    """
    pool = [("定期実行", w) for w in (workflows or [])]
    pool += [("決裁キュー", _shorten(i)) for i in (kessai_items or [])]
    if not pool:
        return []
    return random.Random(week_tag).sample(pool, min(n, len(pool)))


def render_audit_section(targets, week_tag):
    head = ("## 4. 監査所見(独立監査・タダスさん)— 今週の無作為点検\n"
            "\n選定は週番号シードの決定性抽出(同じ週なら何度生成しても同じ対象=べき等)。\n")
    if not targets:
        return head + "\n点検対象プールが空でした(定期実行・決裁キューのどちらも読めず)。ファイルを直接確認してください。\n"
    rows = "\n".join(
        f"| {i} | {kind} | {name} | — (未記入) |"
        for i, (kind, name) in enumerate(targets, 1)
    )
    return (
        head
        + f"\n| # | 種別 | 点検対象 | 所見(監査が記入) |\n|---|---|---|---|\n{rows}\n"
        + "\n点検の観点(3役で見る):\n"
        + "1. **スイシン** — 意図どおり動いているか(直近の実行ログ・出力物)\n"
        + "2. **ウタガイ** — 壊れても気づけるか(失敗時に通知/停止するか。黙って成功扱いになっていないか)\n"
        + "3. **ベッカイ** — そもそも必要か(止めても誰も困らないものが動き続けていないか)\n"
        + f"\n記入先: `reports/integrated/{week_tag}_weekly.md` の本表(latest.md は翌週上書きされます)。\n"
        + "**所見が2週連続で未記入なら、監査が名前だけになっている合図**です(統括経由で小柳さんへ上申)。\n"
    )


# ---------------------------------------------------------------- レポート組み立て

def render_grp_section(db, fukugiiro):
    lines = ["## 1. Grp信号(🟢🟡🔴)— 完全達成が最優先\n"]
    # ミカタ(自動集計できる部分)
    if db:
        keisai = db.get("count", len(db.get("items", [])))
        fresh_label, _ = freshness(db.get("updated_at", ""))
        sig = keisai_signal(keisai)
        gap = "" if keisai >= KPI_KEISAI else f"(あと{KPI_KEISAI - keisai}件)"
        lines.append(
            "### ミカタ(沖縄企業のミカタ)\n\n"
            "| 指標 | 値 | KPI | 信号 |\n|---|---|---|---|\n"
            f"| 掲載制度数 | {keisai} 件 | 常時{KPI_KEISAI}件以上 | {sig}{gap} |\n"
            f"| データ鮮度 | {db.get('updated_at','?')} | {KPI_FRESH_HOURS}時間以内 | {fresh_label} |\n"
            f"| LINE登録数(第一目標1,000社) | 手動確認 | 週20社ペース | 確認先: LINE Official Account Manager+GAS企業台帳(基準❺) |\n"
        )
    else:
        lines.append(
            "### ミカタ(沖縄企業のミカタ)\n\n"
            "⚠ data/subsidies.json が読めないため自動集計をスキップ"
            "(確認先: サイト運用ページ / GitHub Actions fetch ログ)\n"
        )
    # もらいわすれ堂(最新週次レポから転記)
    if fukugiiro:
        star = "\n".join(fukugiiro["star_rows"]) if fukugiiro["star_rows"] else "(北極星の表を検出できず)"
        lines.append(
            f"### もらいわすれ堂(最新週次レポ {fukugiiro.get('week') or '?'} から転記)\n\n"
            "北極星 — 実受給額 / 支援世帯:\n\n"
            "| 指標 | 今週 | 状態 |\n|---|---|---|\n"
            f"{star}\n\n"
            f"> **ボトルネック**: {fukugiiro.get('bottleneck') or '(検出できず — reports/fukugiiro/latest.md を直接確認)'}\n"
            f">\n> **次の一手**: {fukugiiro.get('next_action') or '(検出できず)'}\n"
        )
    else:
        lines.append(
            "### もらいわすれ堂\n\n"
            "⚠ reports/fukugiiro/latest.md が読めないため転記をスキップ"
            "(週次レポworkflow: fukugiiro-weekly-report.yml の実行状況を確認)\n"
        )
    # リポジトリにデータが無いもの(断定しない=確認先案内)
    lines.append(
        "### エンライフ / GLOW(リポジトリ外 — 確認先のみ案内)\n\n"
        "| 事業 | 見るもの | 確認先 |\n|---|---|---|\n"
        "| エンライフ | board整合(見張り番の反映監査結果) | 参謀本部チャット / 見張り番担当者の週次報告 |\n"
        "| GLOW | 台帳の接触消化率(Phase7履歴) | glow-ma台帳ダッシュボード |\n\n"
        "*この2行は台帳・監査結果がリポジトリに入り次第、自動集計へ昇格させる(ループ1の次の接続)。*\n"
    )
    return "\n".join(lines)


def build_report(now=None, db=None, fukugiiro=None, stock=None, stock_err=None,
                 kessai=None, audit=None):
    now = now or datetime.now(JST)
    week_tag = now.strftime("%G-W%V")  # ISO週(例: 2026-W32)
    return week_tag, f"""# 統合週次レポート {week_tag}(ループ1・計器盤)

生成: {now.strftime('%Y-%m-%d %H:%M')} JST(自動生成 / 達成くんフォーマット準拠)
目的: ①Grp完全達成 ②個人手取り300万/月 ③資産1億 の現在地を**毎週月曜の1通**に集約し、
「最新状況の確認」の手動依頼をなくす(逸脱の発見を最大7日以内に保証)。
設計: docs/達成確率を上げる設計_仕組みの接続_2026-07-31.md

---

{render_grp_section(db, fukugiiro)}

{render_stock_section(stock, stock_err)}

{render_kessai_section(kessai)}

{render_audit_section(audit, week_tag)}

---

## 人間の次アクション(この週の依頼)

1. **決裁キュー(§3)を上から**: 最古の項目から3択返信(採用/不採用/保留+理由1行)
2. Grp信号(§1)で🔴🟡が出ている行を1つだけ確認する(全部見ない — ボトルネックだけ)
3. 個人ストック(§2)で件数が動いたら data/personal/stock_status.json の contracts を更新
   (金額は書かない — 件数とゲート状態のみ)
4. 監査所見(§4)が2週連続で未記入なら、監査が回っていない合図として扱う

*本レポートは統合初号機(ループ1)。エンライフ・GLOWの自動集計化と早期警報の閾値(ループ3)は次の接続。*
"""


def main():
    now = datetime.now(JST)
    db = load_subsidies()
    fukugiiro = load_fukugiiro_latest()
    stock, stock_err = load_stock()
    kessai = load_kessai()
    audit = pick_audit_targets(now.strftime("%G-W%V"),
                               list_scheduled_workflows(),
                               (kessai or {}).get("items"))

    week_tag, md = build_report(now, db, fukugiiro, stock, stock_err, kessai, audit)

    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, f"{week_tag}_weekly.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(md)
    with open(os.path.join(OUT_DIR, "latest.md"), "w", encoding="utf-8") as f:
        f.write(md)
    print(f"統合週次レポート生成: {path}")
    print(f"  ミカタ掲載{(db or {}).get('count','?')}件 / "
          f"もらいわすれ堂転記{'OK' if fukugiiro and fukugiiro.get('bottleneck') else 'スキップ'} / "
          f"個人ストック{'表示' if stock else ('拒否' if stock_err else '未計測')} / "
          f"決裁キュー未チェック{(kessai or {}).get('count','?')}件 / "
          f"監査の無作為点検{len(audit)}件")


# ---------------------------------------------------------------- 自己テスト

_SAMPLE_KESSAI = """# 決裁キュー(サンプル)

最終更新: 2026-07-31

- [ ] ①**税理士に依頼の電話1本**(10分)
- [x] ②済んだ項目
- [ ] 県広報メール送信 — 依頼済み・返答待ち(2026-07-30)
- [ ] 2026-09下旬: Metaトークン再発行(期限9/28)
"""

_SAMPLE_LATEST = """# もらいわすれ堂 週次レポート 2026-W31

> **ボトルネック**: 受給報告がまだ0件。
>
> **次の一手(今週これだけ)**: 初回配信を送る。

| 指標 | 今週 | 状態 |
|---|---|---|
| 実受給額(累計) | 0 円 | 受付開始前 |
| 支援世帯数(受給報告) | 0 世帯 | 受付開始前 |
"""


def self_test():
    import tempfile
    failed = 0
    total = 0

    def check(name, cond, detail=""):
        nonlocal failed, total
        total += 1
        if not cond:
            failed += 1
            print(f"[SELFTEST FAIL] {name} {detail}")

    # 1) 決裁キューのパース(件数・最古日付・滞留日数)
    q = parse_kessai(_SAMPLE_KESSAI, today=datetime(2026, 8, 2, tzinfo=JST).date())
    check("kessai.count", q["count"] == 3, f"got {q['count']}")
    check("kessai.oldest_date", q["oldest_date"] == "2026-07-30", f"got {q['oldest_date']}")
    check("kessai.stale_days", q["stale_days"] == 3, f"got {q['stale_days']}")
    check("kessai.oldest_item", "県広報" in (q["oldest_item"] or ""), f"got {q['oldest_item']}")
    # 日付なしキューは先頭項目が最古扱い
    q2 = parse_kessai("- [ ] 項目A\n- [ ] 項目B\n")
    check("kessai.no_date", q2["stale_days"] is None and q2["oldest_item"] == "項目A")
    # 空キュー
    q3 = parse_kessai("すべて済み\n- [x] 完了項目\n")
    check("kessai.empty", q3["count"] == 0)
    check("kessai.render_empty", "0件" in render_kessai_section(q3))
    check("kessai.render_none", "スキップ" in render_kessai_section(None))

    # 2) もらいわすれ堂latestの転記抽出
    p = parse_fukugiiro_latest(_SAMPLE_LATEST)
    check("fukugiiro.week", p["week"] == "2026-W31", f"got {p['week']}")
    check("fukugiiro.bottleneck", p["bottleneck"] == "受給報告がまだ0件。", f"got {p['bottleneck']}")
    check("fukugiiro.next_action", p["next_action"] == "初回配信を送る。", f"got {p['next_action']}")
    check("fukugiiro.star_rows", len(p["star_rows"]) == 2, f"got {p['star_rows']}")

    # 3) 個人ストック台帳(正例・ファイル無し・金額キー混入の拒否)
    with tempfile.TemporaryDirectory() as td:
        ok_path = os.path.join(td, "ok.json")
        with open(ok_path, "w", encoding="utf-8") as f:
            json.dump({"updated_at": "2026-08-02", "products": [
                {"id": 1, "name": "テスト商品", "contracts": 2,
                 "gate": "点線・未検証", "gate_criteria": "初回3社"}]}, f)
        data, err = load_stock(ok_path)
        check("stock.ok", err is None and data and data["products"][0]["contracts"] == 2, f"err={err}")
        check("stock.render", "2 件" in render_stock_section(data, err))

        data, err = load_stock(os.path.join(td, "missing.json"))
        check("stock.missing", data is None and err is None)
        check("stock.render_missing", "未計測" in render_stock_section(None, None))

        bad_path = os.path.join(td, "bad.json")
        with open(bad_path, "w", encoding="utf-8") as f:
            json.dump({"products": [{"id": 1, "name": "x", "contracts": 1,
                                     "gate": "点線", "amount_yen": 100000}]}, f)
        data, err = load_stock(bad_path)
        check("stock.forbid_amount", data is None and err and "拒否" in err, f"err={err}")
        check("stock.render_forbid", "スキップ" in render_stock_section(data, err))

    # 4) 信号・鮮度の判定
    check("signal.green", keisai_signal(153) == "🟢")
    check("signal.yellow", keisai_signal(120) == "🟡")
    check("signal.red", keisai_signal(39) == "🔴")
    now = datetime(2026, 8, 2, 12, 0, tzinfo=JST)
    check("fresh.ok", freshness("2026-08-02 06:00", now)[0].startswith("✅"))
    check("fresh.late", freshness("2026-07-29 06:00", now)[0].startswith("⚠"))
    check("fresh.unknown", freshness("こわれた日付", now)[0] == "不明")

    # 5) 監査の無作為点検(決定性・べき等・欠損時の安全動作)
    wfs = ["a.yml", "b.yml", "c.yml", "d.yml"]
    items = ["決裁1", "決裁2", "決裁3"]
    t1 = pick_audit_targets("2026-W33", wfs, items)
    t2 = pick_audit_targets("2026-W33", wfs, items)
    check("audit.size", len(t1) == 3, f"got {len(t1)}")
    check("audit.deterministic", t1 == t2, f"{t1} != {t2}")       # 同じ週=同じ3件(べき等)
    check("audit.no_dup", len({n for _, n in t1}) == 3, f"got {t1}")
    check("audit.rotates", pick_audit_targets("2026-W34", wfs, items) != t1)  # 週が変われば入れ替わる
    check("audit.pool_small", len(pick_audit_targets("2026-W33", ["only.yml"], [])) == 1)
    check("audit.pool_empty", pick_audit_targets("2026-W33", [], []) == [])
    check("audit.render_empty", "プールが空" in render_audit_section([], "2026-W33"))
    rendered = render_audit_section(t1, "2026-W33")
    check("audit.render_blank", "(未記入)" in rendered and "2週連続" in rendered)
    check("audit.render_week", "2026-W33_weekly.md" in rendered)
    check("audit.workflows_missing", list_scheduled_workflows("/nonexistent/path") == [])
    # 実リポジトリの定期実行を1本以上拾えること(プールが枯れていない確認)
    check("audit.workflows_real", len(list_scheduled_workflows()) >= 1,
          f"got {len(list_scheduled_workflows())}")

    # 6) レポート全体が入力欠損でも組み立てられる(安全なスキップ)
    tag, md = build_report(now=datetime(2026, 8, 3, 9, 0, tzinfo=JST))
    check("report.week_tag", tag == "2026-W32", f"got {tag}")
    check("report.builds", "統合週次レポート" in md and "スキップ" in md and "未計測" in md)
    check("report.audit_section", "## 4. 監査所見" in md)
    for tok in ("万円", "手取り額", "@"):  # 金額・PIIらしき断片が欠損時レポートに出ないこと
        check(f"report.clean:{tok}", tok not in md)

    if failed:
        print(f"自己テスト失敗: {failed} 件")
        return 1
    print(f"自己テスト OK: {total}チェック(決裁キュー・転記・ストック台帳の正例/負例・金額キー拒否・欠損時スキップ)")
    return 0


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        sys.exit(self_test())
    main()
