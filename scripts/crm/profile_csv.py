#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
顧客管理(家計の見直しやさん)— 移行元CSVの実態把握プロファイラ

既存システムから吐き出したCSVを読み、以下を報告する。設計提案はしない(実態を見るだけ)。
  1. 項目名の一覧
  2. 欠損率(空文字・NULL文字列・全角スペースのみ も欠損として数える)
  3. 表記ゆれ(全角半角混在・空白・ハイフン種別・電話/日付/郵便番号のフォーマット揺れ)

PII取り扱い(.claude/skills/churn-pii-guard 準拠。本リポジトリは公開):
- 入力CSVも出力レポートも private/ 配下だけを想定する(private/ は .gitignore 済)
- 既定で実値を出力しない。値は文字クラス(例 漢字4)と書式パターン(例 999-9999-9999)に
  マスクして集計する。生値を見たいときだけ --show-samples を明示的に付ける
- --show-samples を付けた出力は顧客個人情報そのもの。コミット・Issue・PR・チャット貼付は禁止

使い方:
  python3 scripts/crm/profile_csv.py private/kokyaku.csv
  python3 scripts/crm/profile_csv.py private/*.csv --out private/profile.md
"""
import argparse
import csv
import glob
import os
import re
import sys
import unicodedata
from collections import Counter

# ── 欠損とみなす値 ────────────────────────────────────────────────
NULL_TOKENS = {"", "null", "NULL", "None", "nan", "NaN", "-", "ー", "−", "なし", "不明", "未設定", "#N/A", "N/A"}

# 既存システムのエクスポートは Shift_JIS(cp932)が多い。順に試して最初に通ったものを採用
ENCODINGS = ["utf-8-sig", "cp932", "utf-8", "euc-jp"]

# ハイフンに見える文字(表記ゆれの主犯)
HYPHENS = {
    "-": "半角ハイフン",
    "‐": "全角ハイフン(U+2010)",
    "‑": "ノーブレークハイフン",
    "–": "en dash",
    "—": "em dash",
    "―": "ホリゾンタルバー",
    "ー": "長音記号",
    "−": "全角マイナス(U+2212)",
    "﹣": "小字ハイフン",
    "－": "全角ハイフンマイナス",
}

KANSUJI = "〇一二三四五六七八九十"

# 列名から項目の種類を推定する(推定であって断定ではない。判定用チェックの出し分けに使うだけ)
KIND_PATTERNS = [
    ("tel", r"電話|TEL|Tel|tel|携帯|ケータイ|けいたい|固定|連絡先"),
    ("name", r"氏名|名前|姓|名$|お名前|顧客名|契約者"),
    ("kana", r"カナ|かな|フリガナ|ふりがな|ヨミ|読み"),
    ("addr", r"住所|所在地|番地|丁目|町名|市区町村|市町村"),
    ("zip", r"郵便|〒|ZIP|zip|Zip"),
    ("date", r"生年月日|誕生日|birth|日付|年月日|日時|登録日|契約日|申込"),
    ("email", r"メール|mail|Mail|E-?MAIL|アドレス"),
]


def detect_kind(header):
    for kind, pat in KIND_PATTERNS:
        if re.search(pat, header):
            return kind
    return "other"


def read_csv(path):
    """エンコーディングと区切り文字を推定して読む。(rows, header, encoding, delimiter)を返す"""
    raw = open(path, "rb").read()
    text, enc = None, None
    for e in ENCODINGS:
        try:
            text = raw.decode(e)
            enc = e
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        # どれでも読めない場合は cp932 で置換読み(壊れ文字の混入位置を後で報告する)
        text, enc = raw.decode("cp932", errors="replace"), "cp932(置換あり)"

    sample = text[:8192]
    try:
        delimiter = csv.Sniffer().sniff(sample, delimiters=",\t;").delimiter
    except csv.Error:
        delimiter = ","

    reader = csv.reader(text.splitlines(), delimiter=delimiter)
    rows = list(reader)
    if not rows:
        return [], [], enc, delimiter
    return rows[1:], rows[0], enc, delimiter


def is_missing(v):
    return v.strip().replace("　", "") in NULL_TOKENS or v.strip().replace("　", "") == ""


def char_classes(v):
    """文字種の内訳を返す。表記ゆれ(全角半角混在など)の検知に使う"""
    cls = set()
    for ch in v:
        if ch in HYPHENS:
            cls.add("hyphen")
            continue
        name = unicodedata.name(ch, "")
        east = unicodedata.east_asian_width(ch)
        if ch.isdigit():
            cls.add("全角数字" if east in "FW" else "半角数字")
        elif "CJK UNIFIED" in name:
            cls.add("漢字")
        elif "HIRAGANA" in name:
            cls.add("ひらがな")
        elif "KATAKANA" in name:
            cls.add("半角カナ" if east == "H" else "カタカナ")
        elif ch.isalpha():
            cls.add("全角英字" if east in "FW" else "半角英字")
        elif ch == "　":
            cls.add("全角スペース")
        elif ch == " ":
            cls.add("半角スペース")
        elif ch.strip():
            cls.add("記号")
    return cls


def mask(v):
    """値を書式パターンにマスクする。数字→9 / 英字→A / かな・漢字→そのクラス記号"""
    out = []
    for ch in v:
        if ch.isdigit():
            out.append("9")
        elif ch in HYPHENS:
            out.append("-")
        elif ch.isalpha():
            name = unicodedata.name(ch, "")
            if "CJK UNIFIED" in name:
                out.append("漢")
            elif "HIRAGANA" in name:
                out.append("か")
            elif "KATAKANA" in name:
                out.append("カ")
            else:
                out.append("A")
        else:
            out.append(ch)
    # 連続する同一クラスを圧縮(漢漢漢 → 漢x3)
    compressed, prev, run = [], None, 0
    for ch in out + [None]:
        if ch == prev:
            run += 1
            continue
        if prev is not None:
            compressed.append(prev if run == 1 else f"{prev}x{run}")
        prev, run = ch, 1
    return "".join(compressed)


def profile_column(header, values):
    """1列分の統計を返す。values は生値のリスト(空含む)"""
    total = len(values)
    filled = [v for v in values if not is_missing(v)]
    kind = detect_kind(header)

    info = {
        "header": header,
        "kind": kind,
        "total": total,
        "filled": len(filled),
        "missing_rate": (total - len(filled)) / total if total else 0.0,
        "unique": len(set(filled)),
        "patterns": Counter(mask(v) for v in filled).most_common(6),
        "warnings": [],
    }

    if not filled:
        return info

    # ── 表記ゆれの検知 ───────────────────────────────────────────
    all_cls = Counter()
    for v in filled:
        all_cls.update(char_classes(v))
    info["char_classes"] = all_cls

    w = info["warnings"]
    if all_cls.get("全角数字") and all_cls.get("半角数字"):
        w.append(f"全角数字と半角数字が混在(全角{all_cls['全角数字']}件/半角{all_cls['半角数字']}件)")
    if all_cls.get("全角英字") and all_cls.get("半角英字"):
        w.append(f"全角英字と半角英字が混在(全角{all_cls['全角英字']}件/半角{all_cls['半角英字']}件)")
    if all_cls.get("半角カナ"):
        w.append(f"半角カナを含む({all_cls['半角カナ']}件)")

    lead_trail = sum(1 for v in filled if v != v.strip().strip("　"))
    if lead_trail:
        w.append(f"前後に空白がある値: {lead_trail}件")
    inner_space = sum(1 for v in filled if re.search(r"[ 　]", v.strip()))
    if inner_space:
        note = "姓名の区切りか要確認" if kind in ("name", "kana") else "半角/全角スペースの混在に注意"
        w.append(f"値の途中に空白がある値: {inner_space}件({note})")

    hy = Counter(ch for v in filled for ch in v if ch in HYPHENS)
    if len(hy) > 1:
        detail = " / ".join(f"{HYPHENS[c]}{n}件" for c, n in hy.most_common())
        w.append(f"ハイフン種別が混在: {detail}")

    # 種類別の追加チェック
    if kind == "tel":
        shapes = Counter()
        for v in filled:
            d = re.sub(r"\D", "", unicodedata.normalize("NFKC", v))
            has_sep = bool(re.search(r"[^\d]", v.strip()))
            shapes[f"{len(d)}桁/{'区切りあり' if has_sep else '区切りなし'}"] += 1
        info["tel_shapes"] = shapes.most_common(8)
        if len(shapes) > 1:
            w.append(f"電話番号の桁数・区切りが{len(shapes)}種類に分かれている")
        multi = sum(1 for v in filled if re.search(r"[、,／/\n]", v))
        if multi:
            w.append(f"1セルに複数番号が入っている疑い: {multi}件")

    if kind == "date":
        fmts = Counter()
        for v in filled:
            n = unicodedata.normalize("NFKC", v).strip()
            if re.match(r"^\d{4}[/-]\d{1,2}[/-]\d{1,2}", n):
                fmts["YYYY-MM-DD系"] += 1
            elif re.match(r"^\d{8}$", n):
                fmts["8桁数字"] += 1
            elif re.search(r"[明治大正昭和平成令和MTSHR]\s*\d{1,2}[年.]", n):
                fmts["和暦"] += 1
            elif re.match(r"^\d{4}年", n):
                fmts["YYYY年MM月DD日"] += 1
            else:
                fmts["その他"] += 1
        info["date_formats"] = fmts.most_common()
        if len(fmts) > 1:
            w.append(f"日付書式が{len(fmts)}種類に分かれている(和暦・8桁数字の混在は要確認)")

    if kind == "addr":
        kanji_num = sum(1 for v in filled if re.search(f"[{KANSUJI}]丁目", v))
        arabic_num = sum(1 for v in filled if re.search(r"\d\s*丁目", v))
        dash_style = sum(1 for v in filled if re.search(r"\d[-‐−ー]\d", v))
        if kanji_num and arabic_num:
            w.append(f"丁目が漢数字({kanji_num}件)と算用数字({arabic_num}件)で混在")
        if dash_style and (kanji_num or arabic_num):
            w.append(f"「N丁目M番地」形式と「N-M」形式が混在(ハイフン形式{dash_style}件)")
        # 建物名の有無(数字で終わらない=建物名付きの可能性)
        with_bldg = sum(1 for v in filled if re.search(r"(号室|マンション|アパート|ハイツ|コーポ|荘|ビル|[A-Za-zＡ-Ｚａ-ｚ]棟)", v))
        if with_bldg:
            w.append(f"建物名を含む値: {with_bldg}件(番地までで切って比較する必要あり)")
        pref = sum(1 for v in filled if v.strip().startswith(("沖縄県", "沖縄")))
        if pref and pref < len(filled):
            w.append(f"都道府県から始まる値と市町村から始まる値が混在(県付き{pref}件/{len(filled)}件)")

    if kind == "zip":
        shapes = Counter("7桁" if len(re.sub(r"\D", "", unicodedata.normalize("NFKC", v))) == 7 else "7桁以外" for v in filled)
        if len(shapes) > 1:
            w.append(f"郵便番号の桁数が不揃い: {dict(shapes)}")

    return info


def render(path, header, rows, infos, enc, delimiter, show_samples, col_values):
    L = []
    L.append(f"## {os.path.basename(path)}")
    L.append("")
    L.append(f"- 行数(ヘッダ除く): {len(rows)}")
    L.append(f"- 列数: {len(header)}")
    L.append(f"- 文字コード判定: {enc} / 区切り: {delimiter!r}")
    ragged = sum(1 for r in rows if len(r) != len(header))
    if ragged:
        L.append(f"- **列数が合わない行: {ragged}行**(カンマ混入・改行混入の疑い)")
    dup_headers = [h for h, n in Counter(header).items() if n > 1]
    if dup_headers:
        L.append(f"- **重複した列名: {dup_headers}**")
    L.append("")
    L.append("| # | 項目名 | 推定種別 | 欠損率 | 非空 | ユニーク | 表記ゆれ |")
    L.append("|---|---|---|---|---|---|---|")
    for i, info in enumerate(infos, 1):
        warn = "<br>".join(info["warnings"]) if info["warnings"] else "—"
        L.append(
            f"| {i} | {info['header']} | {info['kind']} | {info['missing_rate']*100:.1f}% | "
            f"{info['filled']} | {info['unique']} | {warn} |"
        )
    L.append("")

    L.append("### 値の書式パターン(上位・マスク済 / 9=数字 A=英字 漢=漢字 か=ひらがな カ=カタカナ)")
    L.append("")
    for info in infos:
        if not info["filled"]:
            L.append(f"- **{info['header']}**: 全件欠損")
            continue
        pats = ", ".join(f"`{p}`({n})" for p, n in info["patterns"])
        L.append(f"- **{info['header']}**: {pats}")
        if info.get("tel_shapes"):
            L.append(f"  - 電話の桁数内訳: {', '.join(f'{s}={n}' for s, n in info['tel_shapes'])}")
        if info.get("date_formats"):
            L.append(f"  - 日付書式内訳: {', '.join(f'{s}={n}' for s, n in info['date_formats'])}")
        if show_samples:
            samples = [v for v in col_values[info["header"]] if not is_missing(v)][:3]
            L.append(f"  - 実値サンプル(PII・共有禁止): {samples}")
    L.append("")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description="移行元CSVの項目・欠損率・表記ゆれを報告する")
    ap.add_argument("paths", nargs="+", help="CSVファイル(glob可)")
    ap.add_argument("--out", help="レポートの出力先(.md)。private/ 配下を推奨")
    ap.add_argument("--show-samples", action="store_true",
                    help="実値サンプルを出力する(顧客個人情報。共有・コミット禁止)")
    args = ap.parse_args()

    targets = []
    for p in args.paths:
        targets.extend(sorted(glob.glob(p)) or [p])

    out = ["# 移行元CSV 実態把握レポート", "",
           "※ 値はマスク済(--show-samples 指定時を除く)。本レポートは private/ 配下に置くこと。", ""]

    for path in targets:
        if not os.path.exists(path):
            print(f"[skip] 見つかりません: {path}", file=sys.stderr)
            continue
        rows, header, enc, delimiter = read_csv(path)
        if not header:
            print(f"[skip] 空ファイル: {path}", file=sys.stderr)
            continue
        col_values = {h: [] for h in header}
        for r in rows:
            for i, h in enumerate(header):
                col_values[h].append(r[i] if i < len(r) else "")
        infos = [profile_column(h, col_values[h]) for h in dict.fromkeys(header)]
        out.append(render(path, header, rows, infos, enc, delimiter, args.show_samples, col_values))

    text = "\n".join(out)
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"出力: {args.out}")
    else:
        print(text)


if __name__ == "__main__":
    main()
