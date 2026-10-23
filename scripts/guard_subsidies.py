#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
制度収集の安全装置(U3 fetch guard)— data/subsidies.json を公開する前の門番。

目的: 「検査に成功したデータ(バイト列)だけが main に push され、Pages に公開される」。
2026-10-05 の事故(jGrants API が 66 クエリすべて 503 → 0 件で上書き → 自治体 17 件だけで
公開ゲート(10 件)を通過 → 約 10 時間 17 件のサイトが公開)の再発防止。
設計: scratchpad の設計 v1.2(判断事項 A〜I 決裁 2026-10-11)。

判定(1 つでも該当したら exit 1。想定外の状態では何も通さない = fail-closed):
  G0 基準なし   : 前回(main)の subsidies.json が読めない / items が無い / 空      → snapshot で判定
  G1 取得失敗   : status が無い / 不完全 / jGrants のクエリが 1 件でも 3 回リトライ後に失敗 /
                  自治体ソースの一覧取得失敗・robots 不許可(前回 1 件以上あるソース)
  G2 絶対下限   : 合計 < MIN_TOTAL
  G3 絶対下限   : jGrants(items から数える。by_source は信用しない)< MIN_JGRANTS
  G4 急減(合計) : (prev - new) * 100 > MAX_DROP_PCT * prev   ※ちょうど MAX_DROP_PCT% は PASS
  G5 急減(自治体): prev_s >= SOURCE_MIN かつ new_s * 100 < SOURCE_DROP_PCT * prev_s
  G6 整合       : JSON 妥当 / items 非空 / 必須項目 / id 重複なし / count == len(items) /
                  by_source が items の集計と一致
例外通過(allow_drop・環境変数・特例分岐)は設けない(判断事項 F)。正当な急減は人が検証した
データを PR で入れて基準を更新する。

必須項目は healthcheck.py の REQUIRED_FIELDS と同じ(docs/data-schema.md の「items[] の必須
フィールド」はもらいわすれ堂のスキーマなので参照しない)。

使い方:
  python3 scripts/guard_subsidies.py snapshot --src data/subsidies.json --dst <prev.json>
  python3 scripts/guard_subsidies.py check --prev <prev.json> --new data/subsidies.json \
          --status <fetch_status.json> [--sha-out <guard.sha>] [--explain]
      --sha-out: PASS のとき、検査したバイト列の sha256 を書く(C2/C3 の照合に使う)
  python3 scripts/guard_subsidies.py const MIN_TOTAL
  python3 scripts/guard_subsidies.py --selftest
"""
import hashlib
import json
import os
import shutil
import sys

# ── 閾値(判断事項 D 決裁 2026-10-11。見直し 2027-01-11)。他で数値を直書きしない ──
MIN_TOTAL = 100          # G2: 合計の絶対下限(履歴 23 日分の最小 137)
MIN_JGRANTS = 80         # G3: jGrants の絶対下限(履歴の最小 120)
MAX_DROP_PCT = 15        # G4: 合計の急減率。15% ちょうどは PASS、超えたら FAIL
SOURCE_MIN = 5           # G5: この件数以上あった自治体ソースだけ半減判定の対象
SOURCE_DROP_PCT = 50     # G5: 自治体ソースの半減判定(50% 未満で FAIL)

REQUIRED_FIELDS = ("id", "name", "deadline", "source_url", "status", "tag")
JGRANTS = "jGrants"
STATUS_SCHEMA = 1


# ── 共通 ────────────────────────────────────────────────────────────────
def load_json(path):
    """(obj, error)。読めなければ obj=None, error に理由。"""
    if not path or not os.path.exists(path):
        return None, f"ファイルが無い: {path}"
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f), None
    except Exception as e:  # JSON 破損・権限など
        return None, f"読めない: {path}: {type(e).__name__}: {e}"


def source_of(item):
    # fetch_local.py の by_source 算出 it.get("source", "jGrants") と同じ定義(I-2)
    return item.get("source", JGRANTS)


def count_by_source(items):
    out = {}
    for it in items:
        s = source_of(it)
        out[s] = out.get(s, 0) + 1
    return out


def drop_exceeds(prev, new, pct):
    """減少率が pct% を超えたら True(ちょうど pct% は False)。整数演算のみ。"""
    return (prev - new) * 100 > pct * prev


# ── G0 ──────────────────────────────────────────────────────────────────
def check_baseline(obj, err):
    """前回データの検証。errors(list[str]) を返す。空なら OK。"""
    if err:
        return [f"G0 基準なし: {err}"]
    if not isinstance(obj, dict):
        return ["G0 基準なし: トップレベルがオブジェクトでない"]
    items = obj.get("items")
    if not isinstance(items, list):
        return ["G0 基準なし: items が無い"]
    if not items:
        return ["G0 基準なし: items が空"]
    n_bad = sum(1 for it in items if not isinstance(it, dict))
    if n_bad:
        return [f"G0 基準なし: items にオブジェクトでない要素が {n_bad} 件"]
    return []


# ── G1〜G6 ──────────────────────────────────────────────────────────────
def check_data(prev, new, status):
    """prev / new / status は読み込み済みのオブジェクト(読めなかった場合は None)。
    (errors, warnings, info) を返す。errors が空なら PASS。"""
    errors, warnings = [], []
    info = {}

    # G6: 新データの整合(最初に見る。壊れていれば他の判定は意味を持たない)。型が違うものは
    # 例外で落とさず G6 として理由を残す(fail-closed のまま、Step Summary に理由が出るように)。
    if not isinstance(new, dict):
        errors.append("G6 整合: 新データが読めない/オブジェクトでない")
        return errors, warnings, info
    items = new.get("items")
    if not isinstance(items, list) or not items:
        errors.append("G6 整合: 新データの items が無い/空")
        return errors, warnings, info
    n_not_dict = sum(1 for it in items if not isinstance(it, dict))
    if n_not_dict:
        errors.append(f"G6 整合: items にオブジェクトでない要素が {n_not_dict} 件")
        items = [it for it in items if isinstance(it, dict)]
        if not items:
            return errors, warnings, info
    for f in REQUIRED_FIELDS:
        n_missing = sum(1 for it in items if not it.get(f))
        if n_missing:
            errors.append(f"G6 整合: 必須項目 {f} が欠けている項目 {n_missing} 件")
    n_bad_id = sum(1 for it in items if it.get("id") and not isinstance(it.get("id"), str))   # 欠落は上の必須項目で数える
    if n_bad_id:
        errors.append(f"G6 整合: id が文字列でない項目 {n_bad_id} 件")
    ids = [it.get("id") for it in items if isinstance(it.get("id"), str)]
    dup = sorted({i for i in ids if i and ids.count(i) > 1})
    if dup:
        errors.append(f"G6 整合: id 重複 {len(dup)} 件(例: {dup[:3]})")
    if new.get("count") != len(items) + n_not_dict:
        errors.append(f"G6 整合: count({new.get('count')}) と items 数({len(items) + n_not_dict}) が不一致")
    new_by = count_by_source(items)
    declared = new.get("by_source")
    if not isinstance(declared, dict) or not all(isinstance(v, int) and not isinstance(v, bool) for v in declared.values()):
        errors.append(f"G6 整合: by_source が無い、または値が整数でない({declared!r:.80})")
    else:
        if sum(declared.values()) != len(items):
            errors.append(f"G6 整合: by_source 合計({sum(declared.values())}) と items 数({len(items)}) が不一致")
        if declared != new_by:
            errors.append(f"G6 整合: by_source({declared}) が items の集計({new_by}) と不一致")

    new_total = len(items)
    new_jg = new_by.get(JGRANTS, 0)
    info["new_total"], info["new_jgrants"], info["new_by_source"] = new_total, new_jg, new_by

    # 前回(G0 は snapshot で済んでいるが、check 単独でも安全側に倒す)
    prev_errors = check_baseline(prev, None if prev is not None else "prev が渡されていない")
    errors += prev_errors
    prev_items = prev.get("items") if not prev_errors else []
    prev_by = count_by_source(prev_items)
    prev_total = len(prev_items)
    info["prev_total"], info["prev_by_source"] = prev_total, prev_by

    # G1: 取得状況
    if not isinstance(status, dict):
        errors.append("G1 取得失敗: status ファイルが無い/読めない(fetch 側が書いていない)")
    else:
        if status.get("schema_version") != STATUS_SCHEMA:
            errors.append(f"G1 取得失敗: status の schema_version が {STATUS_SCHEMA} でない")
        jg = status.get("jgrants")
        if not isinstance(jg, dict):
            errors.append("G1 取得失敗: status に jgrants が無い")
        else:
            if jg.get("incomplete"):
                errors.append("G1 取得失敗: jGrants の取得が途中で終わっている(incomplete)")
            queries, done = jg.get("queries"), jg.get("done")
            if not (isinstance(queries, int) and isinstance(done, int)) or queries < 1 or done != queries:
                errors.append(f"G1 取得失敗: jGrants のクエリ数が不正(queries={queries!r}, done={done!r})")
            failed = jg.get("failed")
            if not isinstance(failed, int) or isinstance(failed, bool):
                errors.append("G1 取得失敗: jGrants の failed が数値でない")
            elif failed >= 1:
                errors.append(
                    f"G1 取得失敗: jGrants のクエリ {failed}/{jg.get('queries')} 件が 3 回リトライ後も失敗"
                    f"(種別 {jg.get('kinds')}; 例 {list(jg.get('failed_keywords') or [])[:5]})"
                )
            if jg.get("retried"):
                warnings.append(f"jGrants: リトライで回復したクエリ {jg.get('retried')} 件")
        local = status.get("local")
        if not isinstance(local, dict):
            errors.append("G1 取得失敗: status に local が無い")
        else:
            if status.get("local_incomplete"):
                errors.append("G1 取得失敗: 自治体の取得が途中で終わっている(local_incomplete)")
            by_label = {v.get("label"): v for v in local.values() if isinstance(v, dict)}
            for label, prev_s in sorted(prev_by.items()):
                if label == JGRANTS:
                    continue
                st = by_label.get(label)
                if st is None:
                    if prev_s >= 1:
                        errors.append(f"G1 取得失敗: 前回 {prev_s} 件あった {label} の取得記録が status に無い")
                    continue
                bad = (not st.get("ok")) or st.get("listing_skipped")
                if bad and prev_s >= 1:
                    reason = "robots 不許可" if st.get("listing_skipped") else "一覧取得失敗"
                    errors.append(f"G1 取得失敗: {label} の一覧が {reason}(前回 {prev_s} 件が失われる)")
            for label, st in by_label.items():
                if ((not st.get("ok")) or st.get("listing_skipped")) and prev_by.get(label, 0) == 0:
                    warnings.append(f"{label}: 一覧取得失敗/robots 不許可(前回 0 件のため警告のみ)")
                if st.get("detail_skipped"):
                    warnings.append(f"{label}: 詳細ページ {st.get('detail_skipped')} 件が robots 不許可で除外")
                if st.get("ok") and not st.get("listing_skipped") and st.get("items", 0) == 0:
                    warnings.append(f"{label}: 一覧は取得できたが採用 0 件")

    # G2 / G3
    if new_total < MIN_TOTAL:
        errors.append(f"G2 絶対下限: 合計 {new_total} 件 < {MIN_TOTAL}")
    if new_jg < MIN_JGRANTS:
        errors.append(f"G3 絶対下限: jGrants {new_jg} 件 < {MIN_JGRANTS}")

    # G4 / G5(prev が健全なときだけ)
    if not prev_errors:
        if drop_exceeds(prev_total, new_total, MAX_DROP_PCT):
            errors.append(
                f"G4 急減: 合計 {prev_total} → {new_total}"
                f"({(prev_total - new_total) * 100 / prev_total:.1f}% 減 > {MAX_DROP_PCT}%)"
            )
        for label, prev_s in sorted(prev_by.items()):
            if label == JGRANTS or prev_s < SOURCE_MIN:
                continue
            new_s = new_by.get(label, 0)
            if new_s * 100 < SOURCE_DROP_PCT * prev_s:
                errors.append(f"G5 急減(自治体): {label} {prev_s} → {new_s}(< {SOURCE_DROP_PCT}%)")
    return errors, warnings, info


# ── 出力 ────────────────────────────────────────────────────────────────
def _oneline(msg):
    """ログ 1 行に収める(改行を含む値がワークフローコマンド ::warning:: 等として解釈されないように)。"""
    return str(msg).replace("\r", " ").replace("\n", " ")


def _annotation(msg):
    """GitHub Actions の注釈(::error::)。改行と % は注釈の構文を壊すので 1 行に潰す。"""
    return "::error title=U3 fetch guard::" + _oneline(msg).replace("%", "%25")


def safe_check_data(prev, new, status):
    """check_data を例外で落とさない(想定外の型でも理由を G6 として残す。fail-closed のまま)。"""
    try:
        return check_data(prev, new, status)
    except Exception as e:
        return [f"G6 整合: 検査中に内部エラー({type(e).__name__}: {e})"], [], {}


def render(errors, warnings, info, explain=False):
    errors = [_oneline(e) for e in errors]
    warnings = [_oneline(w) for w in warnings]
    lines = []
    lines.append(f"[guard] prev={info.get('prev_total')} new={info.get('new_total')} "
                 f"jgrants={info.get('new_jgrants')} errors={len(errors)} warnings={len(warnings)}")
    if explain or errors:
        lines.append(f"[guard] prev by_source={info.get('prev_by_source')}")
        lines.append(f"[guard] new  by_source={info.get('new_by_source')}")
        lines.append(f"[guard] 閾値 MIN_TOTAL={MIN_TOTAL} MIN_JGRANTS={MIN_JGRANTS} "
                     f"MAX_DROP_PCT={MAX_DROP_PCT} SOURCE_MIN={SOURCE_MIN} SOURCE_DROP_PCT={SOURCE_DROP_PCT}")
    for w in warnings:
        lines.append(f"[guard] WARN {w}")
    for e in errors:
        lines.append(f"[guard] NG {e}")
    for e in errors:
        lines.append(_annotation(e))          # run の注釈にも出す(判断事項 A: 赤 run・::error::・Step Summary)
    lines.append("[guard] RESULT: " + ("FAIL" if errors else "PASS"))
    return "\n".join(lines)


def write_step_summary(title, errors, warnings, info):
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"### {title}: {'FAIL' if errors else 'PASS'}\n\n")
            f.write("| 項目 | 値 |\n|---|---|\n")
            for k in ("prev_total", "new_total", "new_jgrants", "prev_by_source", "new_by_source"):
                f.write(f"| {k} | {info.get(k)} |\n")
            for e in errors:
                f.write(f"\n- ❌ {_oneline(e)}")
            for w in warnings:
                f.write(f"\n- ⚠️ {_oneline(w)}")
            f.write("\n\n")
    except Exception as e:  # サマリーが書けなくても判定は変えない
        print(f"[guard] step summary 書き込み失敗: {e}", file=sys.stderr)


# ── サブコマンド ────────────────────────────────────────────────────────
def cmd_snapshot(src, dst):
    obj, err = load_json(src)
    errors = check_baseline(obj, err)
    if errors:
        for e in errors:
            print(f"[guard] NG {e}")
            print(_annotation(e))
        print("[guard] RESULT: FAIL(基準データが無いため取得を開始しない。回復は人の PR)")
        write_step_summary("Snapshot (G0)", errors, [], {"prev_total": None})
        return 1
    shutil.copyfile(src, dst)
    n = len(obj["items"])
    print(f"[guard] snapshot OK: {src} → {dst}({n} 件, by_source={count_by_source(obj['items'])})")
    write_step_summary("Snapshot (G0)", [], [], {"prev_total": n, "prev_by_source": count_by_source(obj["items"])})
    return 0


def _read_bytes_and_json(path):
    """(raw_bytes, obj, error)。sha256 は検査した raw_bytes から計算する(読み直さない)。"""
    if not path or not os.path.exists(path):
        return None, None, f"ファイルが無い: {path}"
    try:
        with open(path, "rb") as f:
            raw = f.read()
        return raw, json.loads(raw.decode("utf-8")), None
    except Exception as e:
        return None, None, f"読めない: {path}: {type(e).__name__}: {e}"


def cmd_check(prev_path, new_path, status_path, explain=False, sha_out=None):
    if sha_out and os.path.exists(sha_out):
        os.remove(sha_out)          # 古い検査済みハッシュを残さない(FAIL なら無い状態で終わる)
    prev, perr = load_json(prev_path)
    raw, new, nerr = _read_bytes_and_json(new_path)
    status, serr = load_json(status_path)
    errors, warnings, info = safe_check_data(prev if not perr else None, new if not nerr else None,
                                             status if not serr else None)
    for label, e in (("prev", perr), ("new", nerr), ("status", serr)):
        if e:
            warnings.insert(0, f"{label}: {e}")
    if not errors and sha_out:
        digest = hashlib.sha256(raw).hexdigest()
        try:
            with open(sha_out, "w", encoding="utf-8") as f:
                f.write(digest + "\n")
            info["sha256"] = digest
        except Exception as e:  # sha が残せなければ C2/C3 で止まる(fail-closed)。理由だけ出す
            errors.append(f"G6 整合: 検査済みハッシュを書き出せない: {sha_out}: {e}")
    print(render(errors, warnings, info, explain))
    if info.get("sha256"):
        print(f"[guard] sha256={info['sha256']} → {sha_out}")
    write_step_summary("Guard (C1)", errors, warnings, info)
    return 1 if errors else 0


def cmd_const(name):
    consts = {k: v for k, v in globals().items() if k.isupper() and isinstance(v, int)}
    if name not in consts:
        print(f"未知の定数: {name}(候補: {sorted(consts)})", file=sys.stderr)
        return 2
    print(consts[name])
    return 0


# ── selftest(正例・負例。CLAUDE.md 再発防止「検査を足したら正例・負例で試す」)──
def _mk(n_jg, pref=8, ric=9, naha=0, dup=False, drop_field=None, bad_count=False, bad_by_source=False):
    items = []
    for i in range(n_jg):
        items.append({"id": f"j{i}", "name": f"制度{i}", "deadline": "2026-12-31",
                      "source_url": f"https://www.jgrants-portal.go.jp/subsidy/j{i}", "status": "募集中", "tag": "okinawa"})
    for label, key, n in (("沖縄県(産業・公募補助金)", "okinawa_pref_sangyo", pref),
                          ("沖縄県産業振興公社", "okinawa_ric", ric), ("那覇市(企業支援)", "naha_city", naha)):
        for i in range(n):
            items.append({"id": f"{key}-{i}", "name": f"{label}制度{i}", "deadline": "要確認",
                          "source_url": f"https://example.lg.jp/{key}/{i}.html", "status": "要確認",
                          "tag": "okinawa", "source": label})
    if dup and items:
        items.append(dict(items[0]))
    if drop_field and items:
        items[0] = {k: v for k, v in items[0].items() if k != drop_field}
    obj = {"updated_at": "2026-10-11 00:00", "count": len(items) + (1 if bad_count else 0),
           "by_tag": {"okinawa": len(items)}, "items": items, "by_source": count_by_source(items)}
    if bad_by_source:
        obj["by_source"] = {JGRANTS: len(items)}
    return obj


def _st(failed=0, queries=66, retried=0, pref_ok=True, ric_ok=True, naha_items=0, pref_skip=False,
        incomplete=False, local_incomplete=False, no_local=False, no_jg=False, schema=STATUS_SCHEMA,
        done=None, drop_label=None):
    st = {"schema_version": schema,
          "jgrants": {"queries": queries, "done": queries if done is None else done, "failed": failed,
                      "retried": retried, "kinds": ({"HTTPError 503": failed} if failed else {}),
                      "failed_keywords": [f"kw{i}" for i in range(failed)], "items": 0, "incomplete": incomplete},
          "local": {"okinawa_pref_sangyo": {"label": "沖縄県(産業・公募補助金)", "ok": pref_ok,
                                            "listing_skipped": pref_skip, "listing_entries": 23,
                                            "detail_skipped": 0, "items": 8 if pref_ok else 0},
                    "okinawa_ric": {"label": "沖縄県産業振興公社", "ok": ric_ok, "listing_skipped": False,
                                    "listing_entries": 10, "detail_skipped": 0, "items": 10 if ric_ok else 0},
                    "naha_city": {"label": "那覇市(企業支援)", "ok": True, "listing_skipped": False,
                                  "listing_entries": 4, "detail_skipped": 0, "items": naha_items}},
          "local_incomplete": local_incomplete}
    if no_local:
        del st["local"]
    if no_jg:
        del st["jgrants"]
    if drop_label:
        st["local"] = {k: v for k, v in st["local"].items() if v["label"] != drop_label}
    return st


def _codes(errors):
    return sorted({e.split()[0] for e in errors})


SELFTEST_CASES = [
    # (name, prev, new, status, expected error codes)
    ("正常: 同件数 128+8+9", _mk(128), _mk(128), _st(), []),
    ("正常: +5%", _mk(128), _mk(135), _st(), []),
    ("正常: -5%", _mk(128), _mk(121), _st(), []),
    ("正常: リトライ回復は失敗に数えない", _mk(128), _mk(128), _st(retried=2), []),
    ("正常: 那覇 0→0", _mk(128, naha=0), _mk(128, naha=0), _st(naha_items=0), []),
    ("正常: 片方向性(prev が事故データ 17 件でも新データが健全なら PASS)", _mk(0), _mk(126), _st(), []),
    ("G1: 1 クエリだけ 3 回とも失敗", _mk(128), _mk(128), _st(failed=1), ["G1"]),
    ("G1: 65 失敗・1 成功", _mk(128), _mk(2), _st(failed=65), ["G1", "G2", "G3", "G4"]),
    ("G1: 10-05 型(66 失敗・自治体 17 件)", _mk(128), _mk(0), _st(failed=66), ["G1", "G2", "G3", "G4"]),
    ("G1: incomplete", _mk(128), _mk(128), _st(incomplete=True), ["G1"]),
    ("G1: status 無し", _mk(128), _mk(128), None, ["G1"]),
    ("G1: status に jgrants 無し", _mk(128), _mk(128), _st(no_jg=True), ["G1"]),
    ("G1: status に local 無し", _mk(128), _mk(128), _st(no_local=True), ["G1"]),
    ("G1: schema_version 違い", _mk(128), _mk(128), _st(schema=99), ["G1"]),
    ("G1: done != queries(途中で止まった記録)", _mk(128), _mk(128), _st(done=60), ["G1"]),
    ("G1: queries=0", _mk(128), _mk(128), _st(queries=0), ["G1"]),
    ("G1: failed が数値でない", _mk(128), _mk(128), {**_st(), "jgrants": {**_st()["jgrants"], "failed": "0"}}, ["G1"]),
    ("G1: 前回 8 件あった県の記録が status に無い", _mk(128), _mk(128), _st(drop_label="沖縄県(産業・公募補助金)"), ["G1"]),
    ("G6: items に dict でない要素", _mk(128), {**_mk(128), "items": _mk(128)["items"] + ["x"], "count": 146}, _st(), ["G6"]),
    ("G6: by_source の値が数値でない", _mk(128), {**_mk(128), "by_source": {"jGrants": "128"}}, _st(), ["G6"]),
    ("G6: id が文字列でない(list)", _mk(128), {**_mk(128), "items": [{**_mk(128)["items"][0], "id": ["x"]}] + _mk(128)["items"][1:]}, _st(), ["G6"]),
    ("G6: source がハッシュ不可(内部エラーでも落ちない)", _mk(128), {**_mk(128), "items": [{**_mk(128)["items"][0], "source": {"a": 1}}] + _mk(128)["items"][1:]}, _st(), ["G6"]),
    ("G0: prev の items に dict でない要素", {"items": [1, 2, 3]}, _mk(128), _st(), ["G0"]),
    ("G1+G5: 県の一覧が失敗(8→0)", _mk(128), _mk(128, pref=0), _st(pref_ok=False), ["G1", "G5"]),
    ("G1+G5: 県の一覧が robots 不許可(8→0)", _mk(128), _mk(128, pref=0), _st(pref_skip=True), ["G1", "G5"]),
    ("G2: 合計 99(全 ok)", _mk(82), _mk(82), _st(), ["G2"]),
    ("G2 境界: 合計 100 は PASS", _mk(83), _mk(83), _st(), []),
    ("G3: jGrants 79", _mk(100, pref=30, ric=30), _mk(79, pref=30, ric=30), _st(), ["G3"]),
    ("G3 境界: jGrants 80 は PASS", _mk(100, pref=30, ric=30), _mk(80, pref=30, ric=30), _st(), []),
    # 100→85 は合計が MIN_TOTAL を割るので式の単体テスト(下の drop_exceeds)で見る。ここでは 200 件で等号を確認
    ("G4 境界: 200→170(15.00%) PASS", _mk(183), _mk(153), _st(), []),
    ("G4 境界: 200→169(15.50%) FAIL", _mk(183), _mk(152), _st(), ["G4"]),
    ("G4 境界: 145→124(14.48%) PASS", _mk(128), _mk(107), _st(), []),
    ("G4 境界: 145→123(15.17%) FAIL", _mk(128), _mk(106), _st(), ["G4"]),
    ("G4 境界: 143→122(14.69%) PASS", _mk(126), _mk(105), _st(), []),
    ("G4 境界: 143→121(15.38%) FAIL", _mk(126), _mk(104), _st(), ["G4"]),
    ("G5 境界: 県 8→4 PASS", _mk(128), _mk(128, pref=4), _st(), []),
    ("G5 境界: 県 8→3 FAIL", _mk(128), _mk(128, pref=3), _st(), ["G5"]),
    ("G5 境界: 公社 9→5 PASS", _mk(128), _mk(128, ric=5), _st(), []),
    ("G5 境界: 公社 9→4 FAIL", _mk(128), _mk(128, ric=4), _st(), ["G5"]),
    ("G5: prev 4 件(SOURCE_MIN 未満)→0 は対象外", _mk(128, pref=4), _mk(128, pref=0), _st(), []),
    ("G6: id 重複", _mk(128), _mk(128, dup=True), _st(), ["G6"]),
    ("G6: 必須項目 deadline 欠落", _mk(128), _mk(128, drop_field="deadline"), _st(), ["G6"]),
    ("G6: count 不一致", _mk(128), _mk(128, bad_count=True), _st(), ["G6"]),
    ("G6: by_source 不一致", _mk(128), _mk(128, bad_by_source=True), _st(), ["G6"]),
    ("G6: 新データが None(読めない)", _mk(128), None, _st(), ["G6"]),
    ("G6: 新データの items 空", _mk(128), {"items": [], "count": 0}, _st(), ["G6"]),
    ("G0: prev が None", None, _mk(128), _st(), ["G0"]),
    ("G0: prev の items 空", {"items": []}, _mk(128), _st(), ["G0"]),
]


def selftest():
    failed = 0
    for name, prev, new, status, expected in SELFTEST_CASES:
        errors, _, _ = safe_check_data(prev, new, status)
        got = _codes(errors)
        ok = got == sorted(expected)
        print(f"[selftest] {'OK ' if ok else 'NG '} {name}: expected={sorted(expected)} got={got}")
        if not ok:
            failed += 1
    # drop_exceeds の境界(式そのもの)
    for prev, new, exp in ((100, 85, False), (100, 84, True), (145, 124, False), (145, 123, True),
                           (143, 122, False), (143, 121, True), (145, 17, True), (143, 150, False)):
        got = drop_exceeds(prev, new, MAX_DROP_PCT)
        ok = got == exp
        print(f"[selftest] {'OK ' if ok else 'NG '} drop_exceeds({prev},{new}) = {got}")
        if not ok:
            failed += 1
    print(f"[selftest] cases={len(SELFTEST_CASES) + 8} failed={failed} RESULT: {'FAIL' if failed else 'PASS'}")
    return 1 if failed else 0


# ── エントリ ────────────────────────────────────────────────────────────
def _arg(argv, name, default=None):
    if name in argv:
        i = argv.index(name)
        if i + 1 < len(argv):
            return argv[i + 1]
    return default


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    cmd = argv[1]
    if cmd == "--selftest":
        return selftest()
    if cmd == "snapshot":
        src, dst = _arg(argv, "--src"), _arg(argv, "--dst")
        if not src or not dst:
            print("snapshot --src <subsidies.json> --dst <prev.json>", file=sys.stderr)
            return 2
        return cmd_snapshot(src, dst)
    if cmd == "check":
        prev, new, status = _arg(argv, "--prev"), _arg(argv, "--new"), _arg(argv, "--status")
        sha_out = _arg(argv, "--sha-out")
        if not prev or not new or not status or ("--sha-out" in argv and (not sha_out or sha_out.startswith("--"))):
            print("check --prev <prev.json> --new <new.json> --status <status.json> [--sha-out <guard.sha>] [--explain]",
                  file=sys.stderr)
            return 2
        return cmd_check(prev, new, status, explain="--explain" in argv, sha_out=sha_out)
    if cmd == "const":
        return cmd_const(argv[2] if len(argv) > 2 else "")
    print(f"未知のコマンド: {cmd}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
