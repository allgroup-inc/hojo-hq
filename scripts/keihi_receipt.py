#!/usr/bin/env python3
"""経費精算: 領収書読取結果の検証と業務判定(純ロジック・PIIを持たない)。

設計: docs/経費精算_試作設計.md / 構築手順書: docs/経費精算_構築手順書.md

このモジュールが担うのは「AIが読み取ったJSONを信用してよいか」の判定だけ。
実データ(領収書画像・申請者・金額)はMicrosoft 365側(SharePoint)にのみ置き、
本リポジトリ(公開)には一切持ち込まない。テストは合成データのみ。

絶対ルール1(正確性最優先)の実装: 金額・日付を推測で補完しない。
欠けていたら「要対応」に落として人が確認する。断定しない。

使い方:
    python3 scripts/keihi_receipt.py --self-test
"""
import hashlib
import re
import sys

# 自動で一覧に載せてよい確信度の下限。これ未満は人が確認する(要対応)。
CONFIDENCE_MIN = 80
# 欠けていたら金額・日付を推測せず要対応に落とす項目(絶対ルール1)。
REQUIRED_FIELDS = ("date", "vendor", "total")

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_INVOICE_RE = re.compile(r"^T\d{13}$")


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def validate_extraction(data):
    """読み取り結果の形式を検査し、問題点を文字列のリストで返す(正常なら空)。

    値がNoneのものは「欠落」であって「形式ちがい」ではないため、ここでは報告しない。
    欠落の扱いは decide_status が担う。
    """
    problems = []

    date = data.get("date")
    if date is not None and not _DATE_RE.match(str(date)):
        problems.append(f"date: 日付はYYYY-MM-DD形式である必要があります({date})")

    for key in ("total", "tax10", "tax8"):
        value = data.get(key)
        if value is None:
            continue
        if not _is_number(value):
            problems.append(f"{key}: 金額が数値ではありません({value})")
        elif value < 0:
            problems.append(f"{key}: 金額がマイナスです({value})")

    invoice_no = data.get("invoice_no")
    if invoice_no is not None and not _INVOICE_RE.match(str(invoice_no)):
        problems.append(f"invoice_no: 登録番号はT+13桁である必要があります({invoice_no})")

    total = data.get("total")
    tax10 = data.get("tax10")
    tax8 = data.get("tax8")
    if all(_is_number(v) for v in (total, tax10, tax8)) and tax10 + tax8 > total:
        problems.append(
            f"tax: 税率内訳の合計({tax10 + tax8})が金額({total})を超えています")

    return problems


def decide_status(data):
    """(ステータス, 理由) を返す。理由は要対応のときだけ入る。

    お預かり = そのまま一覧に載せてよい / 要対応 = 人が確認する。
    """
    reasons = []

    missing = [f for f in REQUIRED_FIELDS if data.get(f) is None]
    if missing:
        reasons.append("読み取れなかった項目: " + ", ".join(missing))

    reasons.extend(validate_extraction(data))

    confidence = data.get("confidence")
    if not _is_number(confidence):
        reasons.append(f"確信度がありません({confidence})")
    elif confidence < CONFIDENCE_MIN:
        reasons.append(f"確信度が{CONFIDENCE_MIN}未満です({confidence})")

    if reasons:
        return "要対応", " / ".join(reasons)
    return "お預かり", ""


def extraction_prompt():
    """領収書画像に添えるプロンプトの正規版。

    Power Automateの HTTP アクションにはこの文字列をそのまま貼る。
    手順書とコードで文言が分かれると事故るため、正はここ一箇所にする。
    """
    return (
        "この領収書画像から次の項目を読み取り、JSONだけを返してください。"
        "前置き・説明・コードフェンスは付けないでください。\n"
        "{\n"
        '  "date": "YYYY-MM-DD",      // 利用日\n'
        '  "vendor": "支払先の店名",\n'
        '  "total": 数値,              // 税込の合計金額(円・記号やカンマなし)\n'
        '  "tax10": 数値,              // 10%対象の金額\n'
        '  "tax8": 数値,               // 8%(軽減税率)対象の金額\n'
        '  "invoice_no": "T+13桁",     // インボイス登録番号。記載がなければ null\n'
        '  "confidence": 0-100の整数   // 読み取り全体の確からしさ\n'
        "}\n"
        "\n"
        "守ること:\n"
        "- 読み取れない項目は必ず null にする。**推測して埋めない**。\n"
        "- 金額は画像に書かれている数字だけを使う。計算して補わない。\n"
        "- 手書き・かすれ・見切れ・ピンボケで判読に自信がないときは confidence を低く付ける。\n"
        "- 軽減税率の区別が読み取れないときは tax10 と tax8 を null にする"
        "(total だけ読めていればよい)。\n"
    )


def _digest(*parts):
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:32]


def idempotency_key(message_id):
    """メールのMessage-IDから再処理防止キーを作る。空ならNone(キーを作らない)。

    ハッシュにするのは、SharePointの列に置いても送信者情報が読み取れないようにするため。
    """
    if not message_id:
        return None
    normalized = str(message_id).strip().strip("<>").strip()
    if not normalized:
        return None
    return _digest("mail", normalized)


def duplicate_key(applicant, used_date, amount, vendor):
    """同一申請者×同日×同額×同店舗の重複を見つけるためのキー。

    表記ゆれ(大小文字・前後の空白)を吸収してから作る。
    """
    return _digest(
        "dup",
        str(applicant).strip().lower(),
        str(used_date).strip(),
        str(amount).strip() if isinstance(amount, str) else repr(amount),
        str(vendor).strip().lower(),
    )


def _self_test():
    fails = []
    checked = []

    def check(name, cond):
        checked.append(name)
        if cond:
            return
        fails.append(name)

    # --- 確信度ゲート: 80以上は自動で「お預かり」、未満は「要対応」 ---
    good = {"date": "2026-04-12", "vendor": "◯◯商店", "total": 3240,
            "tax10": 3240, "tax8": 0, "invoice_no": "T1234567890123", "confidence": 95}
    status, reason = decide_status(good)
    check("確信度95は お預かり", status == "お預かり")
    check("確信度95に理由は不要", reason == "")

    low = dict(good)
    low["confidence"] = 79
    status, reason = decide_status(low)
    check("確信度79は 要対応", status == "要対応")
    check("確信度79の理由が残る", "確信度" in reason)

    # --- 金額を推測しない: 必須項目が欠けていたら確信度が高くても要対応 ---
    missing_total = dict(good)
    missing_total["total"] = None
    status, reason = decide_status(missing_total)
    check("金額欠落は確信度99でも要対応", status == "要対応")
    check("金額欠落の理由が残る", "total" in reason)

    # --- 検証: 日付・金額の形式 ---
    problems = validate_extraction(good)
    check("正常データに問題なし", problems == [])

    bad_date = dict(good)
    bad_date["date"] = "2026/04/12"
    check("日付形式ちがいを検出", any("date" in p for p in validate_extraction(bad_date)))

    negative = dict(good)
    negative["total"] = -100
    check("マイナス金額を検出", any("total" in p for p in validate_extraction(negative)))

    # --- インボイス登録番号: T+13桁。空(免税事業者)は正常 ---
    bad_invoice = dict(good)
    bad_invoice["invoice_no"] = "T123"
    check("登録番号の桁ちがいを検出", any("invoice_no" in p for p in validate_extraction(bad_invoice)))

    tax_free = dict(good)
    tax_free["invoice_no"] = None
    check("登録番号なし(免税事業者)は正常", validate_extraction(tax_free) == [])

    # --- 税率内訳が合計を超えないこと ---
    bad_tax = dict(good)
    bad_tax["tax10"] = 5000
    check("内訳が合計超過を検出", any("tax" in p for p in validate_extraction(bad_tax)))

    # --- べき等キー: 同じメールは同じキー。再送で行が二重にならない ---
    k1 = idempotency_key("<abc@mail.example.com>")
    k2 = idempotency_key("abc@mail.example.com")
    check("Message-IDの山括弧有無で同一キー", k1 == k2)
    check("別メールは別キー", k1 != idempotency_key("<xyz@mail.example.com>"))
    check("空のMessage-IDはキーを作らない", idempotency_key("") is None)

    # --- 重複領収書キー: 同一申請者×同日×同額×同店舗 ---
    d1 = duplicate_key("koyanagi@example.com", "2026-04-12", 3240, "◯◯商店")
    d2 = duplicate_key("KOYANAGI@example.com", "2026-04-12", 3240, " ◯◯商店 ")
    check("大小文字と前後空白は同一の重複キー", d1 == d2)
    check("金額違いは別キー", d1 != duplicate_key("koyanagi@example.com", "2026-04-12", 3241, "◯◯商店"))

    # --- 正規プロンプト: Power Automateへ貼る唯一の版。手順書と乖離させない ---
    prompt = extraction_prompt()
    for key in ("date", "vendor", "total", "tax10", "tax8", "invoice_no", "confidence"):
        check(f"プロンプトが{key}を要求している", key in prompt)
    check("プロンプトが推測を禁じている", "推測" in prompt)
    check("プロンプトが不明時のnullを指示している", "null" in prompt)
    check("プロンプトがJSONのみを指示している", "JSON" in prompt)

    if fails:
        print(f"SELF-TEST FAILED ({len(fails)}/{len(checked)}件):")
        for f in fails:
            print("  - " + f)
        return 1
    print(f"keihi_receipt self-test: OK ({len(checked)}件)")
    return 0


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        sys.exit(_self_test())
    print(__doc__)
