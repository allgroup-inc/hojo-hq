#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
後確認(申込完了後の了承取得)の判定ロジック — 純粋関数のみ

このファイルが担当するのは「判断」だけ。SMSの送信・台帳への保存・業者APIの呼び出しは
一切含まない(それらは着手条件クリア後に別ファイルで実装する)。

■ なぜ判定だけ先に書けるのか
未確定事項(業者が返信を受信できるか / 台帳がスプレッドシートかkintoneか / 取引先の承認)の
いずれが転んでも、下記の規則は変わらない。唯一 judge_reply() だけは「SMS返信で承認を取る」
方式が不採用になった場合に不要になるため、他と分離してある。

■ 個人情報について
**このモジュールは生の携帯番号・氏名・申込内容を一切受け取らない。**
同一番号の名寄せには、呼び出し側が仮名化した不透明なキー(tel_key)だけを渡す。
公開リポジトリに置ける理由がこれ(憲法 絶対ルール2 / 運用規程 1-3 データ)。

使い方:
  python scripts/atokakunin_rules.py --self-test   # ゴールデンセットで判定器自体をeval

「evalなき自動化は出荷しない」(運用規程 1-3 出荷ゲート)の実装として --self-test を持つ。
設計の根拠: docs/後確認SMS_質問リスト_2026-08-14.md §B
仕掛品(2026-08-17 FK-003): 着手条件3点は未達。本ファイルは判定規則の先行実装。
"""
import json
import os
import sys
from datetime import datetime, timedelta

BASE = os.path.join(os.path.dirname(__file__), "..")
GOLDEN_PATH = os.path.join(BASE, "tests", "golden_atokakunin.json")

# ── 状態 ────────────────────────────────────────────────
# 期限切れ後の業務上の扱い(申込が無効になるのか等)はQ5補が未回答のため、
# 状態として持つだけで、そこから先の遷移は定義しない。
STATES = ("未送信", "送信済", "承認_SMS", "承認_電話", "要確認", "送信失敗", "期限切れ")

# ── 既定値(いずれも仮。確定したらここだけ変える) ──────────────
# Q6(「はい」以外の返信の扱い)は未回答。断定を避け、最も安全な側に倒す:
# 完全一致「はい」のみ承認とし、それ以外はすべて人に回す。
DEFAULT_ACCEPT_WORDS = ("はい",)
DEFAULT_CALL_AFTER_DAYS = 2      # Q5=「督促SMSなし・2日後に電話」で確定
DEFAULT_EXPIRE_DAYS = 7          # 仮。Q5補の回答で確定させる
DEFAULT_SEND_WINDOW = (9, 19)    # 仮。Q8未回答
DEFAULT_DAILY_LIMIT = 100        # 仮。Q8未回答

# 前後から取り除く空白(半角・全角・タブ・改行)
_TRIM = " 　\t\r\n"

# ── エラーの分類(resilient-agent-design 原則⑤) ──────────────
RETRYABLE = {"timeout", "rate_limit", "server_5xx", "network"}
NEEDS_HUMAN = {"ambiguous_reply", "unknown_format", "order_not_identified"}
FATAL = {"auth_invalid", "permission_denied", "invalid_number", "balance_empty", "not_found"}


def parse_dt(s):
    """'2026-08-14 15:00' 形式をJSTのナイーブなdatetimeとして読む。"""
    return datetime.strptime(s, "%Y-%m-%d %H:%M")


# ── 1. 返信の判定 ────────────────────────────────────────
def judge_reply(text, accept_words=DEFAULT_ACCEPT_WORDS):
    """お客様の返信文を「承認」か「要確認」に振り分ける。

    確率的な判定(AI・あいまい一致)は使わない。了承という法的な意味を持つ記録を
    確率で決めないため、完全一致だけを承認とし、外れたものはすべて人に回す。
    """
    if text is None:
        return "要確認"
    t = text.strip(_TRIM)
    return "承認" if t in accept_words else "要確認"


# ── 2. 自動承認してよいかの門番 ───────────────────────────
def can_auto_approve(tel_key, open_tel_keys):
    """同じ番号で未完了の申込が2件以上あるときは、自動承認しない。

    「はい」だけの返信では、どちらの申込への返事か特定できない。
    ここを塞がないと、誤って別の申込を承認する事故が静かに起きる(B-4の実装必須項目)。
    open_tel_keys: 未完了申込の tel_key の一覧(重複を含む)
    """
    return list(open_tel_keys).count(tel_key) < 2


def decide_after_reply(record, reply_text, open_tel_keys, accept_words=DEFAULT_ACCEPT_WORDS):
    """返信を受けたときの次の状態を返す。"""
    if record.get("state") != "送信済":
        # 送っていない・すでに決着している申込への返信は、機械で処理しない
        return "要確認"
    if judge_reply(reply_text, accept_words) != "承認":
        return "要確認"
    if not can_auto_approve(record["tel_key"], open_tel_keys):
        return "要確認"
    return "承認_SMS"


# ── 3. 電話リスト / 期限切れ ──────────────────────────────
def is_do_not_call(record):
    """架電禁止・アポ禁(対象外)か。

    共通仕様: **架電禁止は持ち場と無関係に最優先で効く。どこにいても発信しない。**
    この判定は他のどの条件よりも先に効かせる(経過日数・期限・状態を一切見ない)。
    """
    return bool(record.get("do_not_call")) or record.get("list_status") == "対象外"


def needs_call(record, now, wait_days=DEFAULT_CALL_AFTER_DAYS):
    """送信からwait_days経っても返信がない=電話リストに載せる。

    送信失敗・要確認は返信を待つ意味がないので、経過日数によらず即座に対象。
    ただし架電禁止は何より先に効く。
    """
    if is_do_not_call(record):
        return False
    state = record.get("state")
    if state in ("承認_SMS", "承認_電話", "期限切れ"):
        return False
    if state in ("送信失敗", "要確認"):
        return True
    if state != "送信済" or not record.get("sent_at"):
        return False
    return (now - parse_dt(record["sent_at"])) >= timedelta(days=wait_days)


def is_expired(record, now, expire_days=DEFAULT_EXPIRE_DAYS):
    if record.get("state") in ("承認_SMS", "承認_電話") or not record.get("sent_at"):
        return False
    return (now - parse_dt(record["sent_at"])) >= timedelta(days=expire_days)


# ── 3.2 電話リスト(毎朝これを見て上から順にかける) ──────────
# 台帳がスプレッドシートでもkintoneでも、載せる条件と並べ方は同じ。
# だから台帳の種類(Q2-1)が決まる前にここだけ先に作れる。
#
# **このリストに氏名は載らない。** 担当者が見る画面で、申込IDをキーに台帳側の氏名・
# 電話番号を引いて表示する。リスト自体は公開リポジトリで扱える形に保つ。

# 優先度: 小さいほど先にかける
_PRIORITY = {
    "送信失敗": 0,   # 届いていない。放置すると永久に届かないので最優先で番号を直す
    "要確認": 1,     # 返信は来ている=お客様は返事を待っている
    "送信済": 2,     # 返信なし。経過の長い順に追いかける
}
_REASON = {
    "送信失敗": "ショートメールが届いていません。番号を確認してかけ直してください",
    "要確認": "返信は来ていますが承認と判定できませんでした。原文を読んでからかけてください",
    "送信済": "送信から{days}日、返信がありません",
}


def build_call_list(records, now, wait_days=DEFAULT_CALL_AFTER_DAYS,
                    expire_days=DEFAULT_EXPIRE_DAYS):
    """電話をかける対象を、かける順に並べて返す。

    並び順: **まず期限間近**(今日かけないと間に合わない)、次に ①送信失敗 ②要確認
    ③返信なし(経過の長い順)。同条件なら申込ID順で固定する
    (毎朝の並びが実行のたびに変わると、担当者が「どこまでかけたか」を見失うため)。

    期限間近を最上位に置く理由: 送信失敗は急ぐが期限まで日数がある。期限が明日の件は
    今日かけなければ手遅れになる。「取り返しがつかない順」に並べる。
    """
    rows = []
    open_keys = [r.get("tel_key") for r in records
                 if r.get("state") in ("未送信", "送信済", "要確認", "送信失敗")]

    for r in records:
        if not needs_call(r, now, wait_days):
            continue
        state = r.get("state")
        days = 0
        if r.get("sent_at"):
            days = (now - parse_dt(r["sent_at"])).days
        rows.append({
            "order_id": r["order_id"],
            "tel_key": r.get("tel_key"),
            "state": state,
            "waited_days": days,
            "reason": _REASON.get(state, "確認が必要です").format(days=days),
            # 同じ番号で未完了が2件以上 = どの申込への返事か特定できない。
            # 電話で必ず申込を特定してから了承を取る(自動承認は別途 can_auto_approve が塞いでいる)
            "needs_identity_check": not can_auto_approve(r.get("tel_key"), open_keys),
            # 期限切れが目前。今日かけないと間に合わない
            "expiring_soon": bool(r.get("sent_at")) and (expire_days - days) <= 1,
        })

    rows.sort(key=lambda x: (0 if x["expiring_soon"] else 1,
                             _PRIORITY.get(x["state"], 9),
                             -x["waited_days"],
                             x["order_id"]))
    return rows


def build_excluded_list(records):
    """架電禁止で自動化から外した中で、まだ後確認が済んでいないものを返す。

    **黙って消さないための一覧。** 架電禁止だからといって後確認の必要が消えるわけではない。
    自動では触らないが、保全部が人として判断できるよう必ず表に出す
    (沈黙は成功と見分けがつかない)。
    """
    rows = [
        {"order_id": r["order_id"], "state": r.get("state"),
         "reason": "架電禁止・アポ禁のため自動化の対象外。後確認は未了"}
        for r in records
        if is_do_not_call(r) and r.get("state") not in ("承認_SMS", "承認_電話")
    ]
    rows.sort(key=lambda x: x["order_id"])
    return rows


def render_call_list(rows):
    """電話リストをタブ区切りの文字列にする(印刷・貼り付け用)。

    氏名・電話番号は含めない。担当者の画面で申込IDから台帳を引いて表示する。
    """
    header = "順\t申込ID\t経過\t要対応\t理由"
    lines = [header]
    for i, r in enumerate(rows, 1):
        marks = []
        if r["needs_identity_check"]:
            marks.append("申込の特定が必要")
        if r["expiring_soon"]:
            marks.append("期限間近")
        lines.append(f'{i}\t{r["order_id"]}\t{r["waited_days"]}日\t'
                     f'{"/".join(marks) if marks else "—"}\t{r["reason"]}')
    if not rows:
        lines.append("(本日かける対象はありません)")
    return "\n".join(lines)


# ── 3.5 承認語の見直し材料をつくる ────────────────────────
# Q6(「はい」以外の返信の扱い)は「既定のまま2週間走らせ、実際に来た返信文を見てから
# 承認語を決める」と確定(2026-08-17 小柳さん)。その"見直し"を実行させるための道具。
# **この関数は候補を人に提示するだけで、承認語を自動で増やすことは決してしない。**
# 了承の意味を機械が勝手に広げないため(誤承認は取り返しがつかない)。
_HAS_DIGIT = tuple("0123456789０１２３４５６７８９")
_QUESTION = ("?", "？")


def review_candidates(replies, min_count=3, max_len=6, accept_words=DEFAULT_ACCEPT_WORDS):
    """要確認になった返信文から、承認語に追加する候補を頻度順で返す。

    返り値: {"candidates": [(語, 件数), ...], "needs_human_read": 件数}
    candidates に載るのは「短く・数字を含まず・疑問符が無い」ものだけ。
    それ以外は needs_human_read に数え、**人が原文を読む**対象として残す。

    数字を除くのは、お客様が電話番号や生年月日を返信に書いてくる場合があるため
    (候補一覧に個人情報を持ち出さない)。
    """
    counts = {}
    needs_human = 0
    for raw in replies:
        if raw is None:
            needs_human += 1
            continue
        t = raw.strip(_TRIM)
        if not t or t in accept_words:
            continue
        if (len(t) > max_len
                or any(d in t for d in _HAS_DIGIT)
                or any(q in t for q in _QUESTION)):
            needs_human += 1
            continue
        counts[t] = counts.get(t, 0) + 1

    # 件数の多い順。同数なら語順で安定させる(実行のたびに並びが変わらないように)
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    candidates = [(w, c) for w, c in ranked if c >= min_count]
    needs_human += sum(c for w, c in ranked if c < min_count)
    return {"candidates": candidates, "needs_human_read": needs_human}


# ── 4. 送信してよいかの門番(ガードレール) ─────────────────
def can_send(order_id, now, already_sent_ids, sent_today,
             window=DEFAULT_SEND_WINDOW, daily_limit=DEFAULT_DAILY_LIMIT,
             record=None):
    """送ってよいかを判定し、(可否, 理由)で返す。

    理由を必ず返すのは、送らなかった日に「なぜ0件だったか」を後から説明できるようにするため。
    沈黙(0件)は「対象なし」とも「壊れて拾えていない」とも読めてしまう。
    """
    if record is not None and is_do_not_call(record):
        # 架電禁止の方へ機械が一斉送信するのは、電話をかけるより始末が悪い。
        # 自動化からは外し、保全部が人として判断する対象へ回す(build_excluded_listを見ること)。
        return False, "架電禁止・アポ禁の対象(自動送信しない。人が判断する)"
    if order_id in already_sent_ids:
        return False, "二重送信の防止(この申込IDは送信済)"
    if not (window[0] <= now.hour < window[1]):
        return False, f"送信可能時間帯の外({window[0]}時〜{window[1]}時)"
    if sent_today >= daily_limit:
        return False, f"1日の送信上限に到達({daily_limit}件)"
    return True, "送信可"


# ── 5. エラーの扱い(リトライ種別) ───────────────────────
def classify_error(kind):
    """'retry'(再試行してよい) / 'human'(人へ回す) / 'stop'(即停止して通知)"""
    if kind in RETRYABLE:
        return "retry"
    if kind in NEEDS_HUMAN:
        return "human"
    if kind in FATAL:
        return "stop"
    # 知らないエラーを勝手に再試行しない。分からないものは人へ。
    return "human"


def retry_delay_seconds(attempt):
    """30秒 → 2分 → 10分。上限(3回)を超えたらNoneを返す=呼び出し側は落とすこと。"""
    schedule = [30, 120, 600]
    return schedule[attempt - 1] if 1 <= attempt <= len(schedule) else None


# ── self-test ───────────────────────────────────────────
def _as_expected(result):
    """タプルの配列をリストに直す(JSONの期待値と比較できる形にそろえるだけ)。"""
    return {"candidates": [list(x) for x in result["candidates"]],
            "needs_human_read": result["needs_human_read"]}


def _run_section(golden, key, fn):
    failed = 0
    for case in golden.get(key, []):
        got = fn(case)
        if got != case["expect"]:
            failed += 1
            print(f"[SELFTEST FAIL] {key} / {case['name']}: expected {case['expect']!r} got {got!r}")
    return failed


def self_test():
    with open(GOLDEN_PATH, encoding="utf-8") as f:
        golden = json.load(f)

    failed = 0
    total = 0

    failed += _run_section(golden, "reply_judgment", lambda c: judge_reply(c["text"]))
    failed += _run_section(golden, "auto_approve",
                           lambda c: can_auto_approve(c["tel_key"], c["open_tel_keys"]))
    failed += _run_section(golden, "after_reply",
                           lambda c: decide_after_reply(c["record"], c["reply"], c["open_tel_keys"]))
    failed += _run_section(golden, "call_list",
                           lambda c: needs_call(c["record"], parse_dt(c["now"])))
    failed += _run_section(golden, "expire",
                           lambda c: is_expired(c["record"], parse_dt(c["now"])))
    failed += _run_section(golden, "send_gate",
                           lambda c: can_send(c["order_id"], parse_dt(c["now"]),
                                              c["already_sent_ids"], c["sent_today"],
                                              record=c.get("record"))[0])
    failed += _run_section(golden, "excluded_list",
                           lambda c: [r["order_id"] for r in build_excluded_list(c["records"])])
    failed += _run_section(golden, "error_class", lambda c: classify_error(c["kind"]))
    failed += _run_section(golden, "retry_delay", lambda c: retry_delay_seconds(c["attempt"]))
    # JSONに配列で書いた期待値をタプルに直してから比較する
    failed += _run_section(
        golden, "review_candidates",
        lambda c: _as_expected(review_candidates(c["replies"], c.get("min_count", 3))))
    # 電話リストは「並び順」と「フラグ」を別々に確かめる
    failed += _run_section(
        golden, "call_list_order",
        lambda c: [r["order_id"] for r in build_call_list(c["records"], parse_dt(c["now"]))])
    failed += _run_section(
        golden, "call_list_flags",
        lambda c: [[r["order_id"], r["needs_identity_check"], r["expiring_soon"]]
                   for r in build_call_list(c["records"], parse_dt(c["now"]))])

    for k in ("reply_judgment", "auto_approve", "after_reply", "call_list",
              "expire", "send_gate", "error_class", "retry_delay", "review_candidates",
              "call_list_order", "call_list_flags", "excluded_list"):
        total += len(golden.get(k, []))

    # 判定器そのものの前提が崩れていないかの確認(ゴールデンセットの取りこぼし防止)
    if total < 30:
        print(f"[SELFTEST FAIL] ゴールデンセットが薄すぎます({total}件)。30件以上必要です")
        failed += 1

    if failed:
        print(f"\n後確認 判定ロジック self-test: {total}件中 {failed}件 失敗")
        return 1
    print(f"後確認 判定ロジック self-test: {total}件すべて合格")
    return 0


def main():
    if "--self-test" in sys.argv:
        return self_test()
    print(__doc__)
    print("判定のみのモジュールです。--self-test で検証してください。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
