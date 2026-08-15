"""CLI：fit / score / backtest を通しで実行する。

例（顧客データは private/ 配下で実行する）:
  python -m scripts.churn.cli fit --csv private/data.csv --column-map private/column_map.json --model private/risk_model.json --as-of 2026-07-25
  python -m scripts.churn.cli score --csv private/data.csv --column-map private/column_map.json --model private/risk_model.json --out private/list --as-of 2026-07-25
  python -m scripts.churn.cli backtest --csv private/data.csv --column-map private/column_map.json --split 2026-01-01 --as-of 2026-07-25
"""
from __future__ import annotations
import argparse
import os
from datetime import date

from .intake import load_records, load_column_map
from .fit import fit_model, save_model, load_model
from .report_list import build_rows, render_csv, render_html
from .evaluate import backtest
from .report_card import build_card, render_html as render_card_html
from .report_agg import aggregate_by, render_html as render_agg_html
from .interactions import load_interactions
from .customer import build_customers, unlinked_counts
from .karte import render_html as render_karte_html
from .followups import list_followups, render_html as render_followups_html
from .karte_effect import contact_effect
from .console import generate as generate_console
from .triage import classify, triage, render_html as render_today_html
from .cohort import cohort_rows, overall_rate, render_html as render_cohort_html
from .snapshot import snapshot as do_snapshot
from .preflight import preflight_report
from .pipeline import run_pipeline
from .retention import purge_snapshots
from .contact_log import load_contacts
from .playbook import segment_playbook, render_html as render_playbook_html
from .experiment import compare_naive_vs_controlled, assignment_ledger
from .timing import churn_hazard_by_tenure, peak_window, render_html as render_hazard_html
from .config import EXPERIMENT_TREATED_FRACTION
from .config import CAPACITY_PER_DAY, AUC_MIN, SNAPSHOT_RETENTION_YEARS, EARLY_CHURN_MONTHS


def _as_of(value):
    if not value:
        raise SystemExit("--as-of は YYYY-MM-DD で指定してください（PII保護のため既定日は使いません）")
    y, m, d = (int(p) for p in value.split("-"))
    return date(y, m, d)


def cmd_fit(csv_path, column_map_path, model_path, as_of):
    cmap = load_column_map(column_map_path)
    records = load_records(csv_path, cmap, _as_of(as_of))
    model = fit_model(records)
    save_model(model, model_path)
    summary = {"n_resolved": model["n_resolved"], "base_rate": model["base_rate"]}
    print(f"[fit] 学習完了: 成熟実績={summary['n_resolved']}件 ベース解約率={summary['base_rate']:.1%}")
    return summary


def cmd_score(csv_path, column_map_path, model_path, out_prefix, as_of):
    cmap = load_column_map(column_map_path)
    records = load_records(csv_path, cmap, _as_of(as_of))
    scoreable = [r for r in records if r.get("is_scoreable")]
    model = load_model(model_path)
    rows = build_rows(scoreable, model)
    render_csv(rows, out_prefix + ".csv")
    render_html(rows, out_prefix + ".html")
    high = sum(1 for r in rows if r["band"] == "high")
    print(f"[score] 採点対象={len(rows)}件 うち高リスク={high}件 → {out_prefix}.csv / .html")
    return len(rows)


def cmd_backtest(csv_path, column_map_path, split, as_of):
    cmap = load_column_map(column_map_path)
    records = load_records(csv_path, cmap, _as_of(as_of))
    y, m, d = (int(p) for p in split.split("-"))
    metrics = backtest(records, date(y, m, d))
    print(f"[backtest] n_test={metrics['n_test']} AUC={metrics['auc']:.3f} "
          f"pred={metrics['pred_mean']:.1%} actual={metrics['actual_mean']:.1%} "
          f"top10%lift={metrics['top_decile_lift']:.2f} "
          f"ECE={metrics['ece']:.3f} precision@{metrics['capacity']}={metrics['precision_at_capacity']:.1%}")
    if metrics["calibration_warning"]:
        print(f"  ・⚠️較正不良（ECE={metrics['ece']:.3f}）: リスク%の水準がズレています。"
              f"母数・定義を要確認（当たっても優先度づけを誤り得る）")
    return metrics


def cmd_card(csv_path, column_map_path, model_path, apply_id, out_path, as_of):
    cmap = load_column_map(column_map_path)
    records = load_records(csv_path, cmap, _as_of(as_of))
    target = next((r for r in records if str(r.get("apply_id")) == str(apply_id)), None)
    if target is None:
        raise SystemExit(f"申込ID {apply_id} が見つかりません")
    model = load_model(model_path)
    card = build_card(target, model)
    render_card_html(card, out_path)
    print(f"[card] {apply_id}: {card['risk_pct']}% ({card['band']}) → {out_path}")
    return card


def cmd_report(csv_path, column_map_path, out_path, as_of, fields=("agent_id", "channel", "product")):
    cmap = load_column_map(column_map_path)
    records = load_records(csv_path, cmap, _as_of(as_of))
    labels = {"agent_id": "営業マン別", "channel": "チャネル別", "product": "商品別"}
    sections = {labels.get(f, f): aggregate_by(records, f) for f in fields}
    render_agg_html(sections, out_path)
    print(f"[report] 集計軸={list(sections)} → {out_path}")
    return sections


def _print_unlinked(apps, inters):
    u = unlinked_counts(apps, inters)
    if u["apps"] + u["interactions"] > 0:
        print(f"[未紐付] 申込{u['apps']}件・接触{u['interactions']}件は顧客ID欠損のため除外")


def cmd_karte(app_csv, app_map, inter_csv, inter_map, model_path, customer_id, out_path, as_of):
    as_of_d = _as_of(as_of)
    apps = load_records(app_csv, load_column_map(app_map), as_of_d)
    inters = load_interactions(inter_csv, load_column_map(inter_map))
    _print_unlinked(apps, inters)
    model = load_model(model_path)
    customers = build_customers(apps, inters, model, as_of_d)
    prof = customers.get(str(customer_id))
    if prof is None:
        raise SystemExit(f"顧客ID {customer_id} が見つかりません")
    render_karte_html(prof, out_path)
    print(f"[karte] {customer_id}: 累計申込{prof['n_applications']}回 "
          f"最大リスク{prof['max_risk_band']} → {out_path}")
    return prof


def cmd_followups(app_csv, app_map, inter_csv, inter_map, model_path, out_path, as_of):
    as_of_d = _as_of(as_of)
    apps = load_records(app_csv, load_column_map(app_map), as_of_d)
    inters = load_interactions(inter_csv, load_column_map(inter_map))
    _print_unlinked(apps, inters)
    model = load_model(model_path)
    customers = build_customers(apps, inters, model, as_of_d)
    rows = list_followups(customers)
    render_followups_html(rows, out_path)
    print(f"[followups] 要フォロー {len(rows)}件 → {out_path}")
    return len(rows)


def cmd_karte_effect(app_csv, app_map, inter_csv, inter_map, as_of):
    as_of_d = _as_of(as_of)
    apps = load_records(app_csv, load_column_map(app_map), as_of_d)
    inters = load_interactions(inter_csv, load_column_map(inter_map))
    _print_unlinked(apps, inters)
    m = contact_effect(apps, inters)
    body = (f"保全接触あり {m['n_contacted']}件 解約率{m['contacted_rate']:.1%} / "
            f"なし {m['n_not_contacted']}件 解約率{m['not_contacted_rate']:.1%} / "
            f"差{m['diff']:+.1%}")
    if m["reference"]:
        # 母数不足：差を結論として提示しない。参考値であることを前後に明記する
        print(f"[karte-effect] ※参考(母数不足) {body} ※参考(母数不足)")
    else:
        print(f"[karte-effect] {body}")
    return m


def cmd_console(app_csv, app_map, inter_csv, inter_map, model_path, out_dir, as_of):
    as_of_d = _as_of(as_of)
    apps = load_records(app_csv, load_column_map(app_map), as_of_d)
    inters = load_interactions(inter_csv, load_column_map(inter_map))
    _print_unlinked(apps, inters)
    model = load_model(model_path)
    customers = build_customers(apps, inters, model, as_of_d)
    res = generate_console(customers, out_dir)
    # リスク一覧のカルテリンクが同ディレクトリのkarte_*.htmlへ相対リンクするため、
    # 一覧もconsoleのout-dirに書き、リンク切れ(404)を防ぐ
    scoreable = [r for r in apps if r.get("is_scoreable")]
    rows = build_rows(scoreable, model)
    list_csv_path = os.path.join(out_dir, "list.csv")
    list_html_path = os.path.join(out_dir, "list.html")
    render_csv(rows, list_csv_path)
    render_html(rows, list_html_path)
    res["list_csv"] = list_csv_path
    res["list_html"] = list_html_path
    # 3%スコアボード（コホート）と「今日の要接触」も同ディレクトリへ
    cohorts = cohort_rows(apps, as_of_d, model=model)
    render_cohort_html(cohorts, overall_rate(cohorts), os.path.join(out_dir, "cohort.html"))
    today, carry, stats = triage(classify(apps, model, as_of_d), CAPACITY_PER_DAY)
    render_today_html(today, carry, stats, os.path.join(out_dir, "today.html"), CAPACITY_PER_DAY)
    res["cohort_html"] = os.path.join(out_dir, "cohort.html")
    res["today_html"] = os.path.join(out_dir, "today.html")
    print(f"[console] 顧客{res['n_kartes']}件のカルテ＋index＋list＋followups"
          f"＋cohort＋today → {out_dir}/")
    return res


def cmd_cohort(csv_path, column_map_path, out_path, as_of, model_path=None):
    as_of_d = _as_of(as_of)
    records = load_records(csv_path, load_column_map(column_map_path), as_of_d)
    model = load_model(model_path) if model_path else None
    rows = cohort_rows(records, as_of_d, model=model)
    ov = overall_rate(rows)
    render_cohort_html(rows, ov, out_path)
    shown = "算出不能" if ov["rate"] is None else f"{ov['rate']*100:.1f}%"
    print(f"[cohort] 全体早期解約率(成熟分) {shown} 目標3% "
          f"({ov['churn']}/{ov['resolved']}) → {out_path}")
    return ov


def cmd_today(csv_path, column_map_path, model_path, out_path, as_of, capacity,
              contacts_path=None, contact_map_path=None):
    as_of_d = _as_of(as_of)
    records = load_records(csv_path, load_column_map(column_map_path), as_of_d)
    model = load_model(model_path)
    contacts = (load_contacts(contacts_path, load_column_map(contact_map_path))
                if contacts_path and contact_map_path else None)
    today, carry, stats = triage(classify(records, model, as_of_d, contacts=contacts), capacity)
    render_today_html(today, carry, stats, out_path, capacity)
    print(f"[today] 要接触{stats['total']}件 → 今日{len(today)} / "
          f"繰り越し{stats['carry_count']} → {out_path}")
    return stats


def cmd_snapshot(csv_path, interactions, month, out_dir, force):
    return do_snapshot(csv_path, interactions, month, out_dir, force)


def cmd_pipeline(csv_path, column_map_path, out_dir, as_of, split, run_date,
                 auc_min, capacity, interactions, contacts=None, contact_map=None):
    st = run_pipeline(csv_path, column_map_path, out_dir, _as_of(as_of), _as_of(split),
                      run_date, auc_min=auc_min, capacity=capacity, interactions=interactions,
                      contacts_path=contacts, contact_map_path=contact_map)
    mark = {"completed": "✅完了", "stopped_auc": "🛑AUC停止",
            "stopped_schema": "🛑スキーマ停止"}.get(st["status"], st["status"])
    auc = "－" if st["auc"] is None else f"{st['auc']:.3f}"
    print(f"[pipeline] {mark}  AUC={auc} 済工程={st['completed_steps']}"
          + ("（べき等スキップ）" if st.get("idempotent_skip") else ""))
    return st


def _mature_before(as_of, months=EARLY_CHURN_MONTHS):
    """as_of から months ヶ月前（この日より前の契約＝6ヶ月窓が経過し成熟）。日はそのまま。"""
    idx = as_of.year * 12 + (as_of.month - 1) - months
    day = min(as_of.day, 28)  # 月末差異を避ける
    return date(idx // 12, idx % 12 + 1, day)


def cmd_playbook(csv_path, column_map_path, contacts_path, contact_map_path,
                 out_path, as_of, segment):
    as_of_d = _as_of(as_of)
    cmap = load_column_map(column_map_path)
    records = load_records(csv_path, cmap, as_of_d)
    contacts = load_contacts(contacts_path, load_column_map(contact_map_path))
    rows = segment_playbook(records, contacts, _mature_before(as_of_d), segment_field=segment)
    labels = {"product": "商品", "agent_id": "営業担当", "channel": "チャネル", "area": "地域"}
    render_playbook_html(rows, out_path, segment_label=labels.get(segment, segment))
    print(f"[playbook] セグメント={segment} {len(rows)}層 → {out_path}")
    return rows


def cmd_hazard(csv_path, column_map_path, out_path, as_of):
    as_of_d = _as_of(as_of)
    records = load_records(csv_path, load_column_map(column_map_path), as_of_d)
    hz = churn_hazard_by_tenure(records)
    render_hazard_html(hz, out_path)
    lo, hi = peak_window(hz)
    peak = "実績なし" if lo is None else f"契約後{lo}〜{hi}日"
    ref = "（参考・母数不足）" if hz["reference"] else ""
    print(f"[hazard] 早期解約{hz['total']}件{ref} 解約のヤマ={peak}"
          f"（その手前が架電の勝負どき）→ {out_path}")
    return hz


def cmd_uplift(csv_path, column_map_path, contacts_path, contact_map_path, as_of,
               treated_fraction, salt):
    as_of_d = _as_of(as_of)
    cmap = load_column_map(column_map_path)
    records = load_records(csv_path, cmap, as_of_d)
    contacts = load_contacts(contacts_path, load_column_map(contact_map_path))
    out = compare_naive_vs_controlled(records, contacts, _mature_before(as_of_d),
                                      treated_fraction=treated_fraction, salt=salt)
    led = assignment_ledger([r.get("customer_id") for r in records], treated_fraction, salt)
    c = out["controlled"]
    ref = "（参考・母数不足）" if c["reference"] else ""
    print(f"[uplift] 段階導入台帳 先行{led['先行']}/後発{led['後発']}（計{led['total']}）")
    print(f"  結論=対照群比較{ref}: 介入(先行){c['rate_treat']:.1%}(n={c['n_treat']}) / "
          f"対照(後発){c['rate_ctrl']:.1%}(n={c['n_ctrl']})")
    print(f"  早期解約の減少 diff={c['diff']:+.1%} "
          f"95%CI[{c['diff_ci'][0]:+.1%}, {c['diff_ci'][1]:+.1%}]"
          + ("（0を含む＝有意でない）" if c['diff_ci'][0] <= 0 <= c['diff_ci'][1] else "（0を跨がない＝有意に減少）"))
    n = out["naive"]
    print(f"  ※参考(生存者バイアス) 単純比較: 接触あり{n['rate_c']:.1%} / なし{n['rate_n']:.1%} "
          f"差{n['diff']:+.1%}（因果ではない）")
    return out


def cmd_retention(snapshots_dir, as_of, years, apply):
    rep = purge_snapshots(snapshots_dir, _as_of(as_of), years, apply)
    mode = "実削除" if apply else "ドライラン（消しません）"
    print(f"[retention] {mode} 保持{rep['retention_years']}年 "
          f"満期{len(rep['expired'])}件 保持継続{rep['kept']}件")
    if rep["expired"]:
        print(f"  ・満期: {rep['expired']}")
    if apply:
        print(f"  ・削除済: {rep['deleted']} → deletion_log.json に記録")
    elif rep["expired"]:
        print("  ※実削除は --apply を付けて実行してください")
    return rep


def cmd_preflight(csv_path, column_map_path, as_of):
    rep = preflight_report(csv_path, load_column_map(column_map_path), _as_of(as_of))
    mark = "✅可" if rep["ok"] else "🛑不可"
    print(f"[preflight] {mark}  総{rep['n_total']}件 未紐付{rep['n_unlinked']} "
          f"成熟{rep['n_resolved']} 継続中{rep['n_scoreable']}")
    if rep["missing_keys"]:
        print(f"  ・column_map不足キー: {rep['missing_keys']}")
    if rep["missing_columns"]:
        print(f"  ・CSVに無い対応列: {rep['missing_columns']}")
    if rep.get("forbidden_name_keys"):
        print(f"  ・🛑顧客名の持込は禁止（ID管理が前提）: {rep['forbidden_name_keys']} "
              f"→ column_mapから外してください")
    bad = {k: v for k, v in rep["date_parse_fails"].items() if v}
    if bad:
        print(f"  ・日付パス不能: {bad}")
    if rep.get("account_flag_unexpected"):
        print(f"  ・口座フラグ想定外値: {rep['account_flag_unexpected']}件"
              f"（想定「はい/いいえ/未確認」。入力側の運用確認を推奨・#142項目4）")
    return rep


def main(argv=None):
    p = argparse.ArgumentParser(prog="churn", description="早期解約リスク保全")
    sub = p.add_subparsers(dest="cmd", required=True)

    for name in ("fit", "score", "backtest"):
        sp = sub.add_parser(name)
        sp.add_argument("--csv", required=True)
        sp.add_argument("--column-map", required=True)
        sp.add_argument("--as-of", required=True)
        if name in ("fit", "score"):
            sp.add_argument("--model", required=True)
        if name == "score":
            sp.add_argument("--out", required=True)
        if name == "backtest":
            sp.add_argument("--split", required=True)

    sp_card = sub.add_parser("card")
    sp_card.add_argument("--csv", required=True)
    sp_card.add_argument("--column-map", required=True)
    sp_card.add_argument("--as-of", required=True)
    sp_card.add_argument("--model", required=True)
    sp_card.add_argument("--apply-id", required=True)
    sp_card.add_argument("--out", required=True)

    sp_report = sub.add_parser("report")
    sp_report.add_argument("--csv", required=True)
    sp_report.add_argument("--column-map", required=True)
    sp_report.add_argument("--as-of", required=True)
    sp_report.add_argument("--out", required=True)

    sp_karte = sub.add_parser("karte")
    sp_karte.add_argument("--csv", required=True)
    sp_karte.add_argument("--column-map", required=True)
    sp_karte.add_argument("--interactions", required=True)
    sp_karte.add_argument("--interaction-map", required=True)
    sp_karte.add_argument("--model", required=True)
    sp_karte.add_argument("--customer-id", required=True)
    sp_karte.add_argument("--out", required=True)
    sp_karte.add_argument("--as-of", required=True)

    sp_fu = sub.add_parser("followups")
    sp_fu.add_argument("--csv", required=True)
    sp_fu.add_argument("--column-map", required=True)
    sp_fu.add_argument("--interactions", required=True)
    sp_fu.add_argument("--interaction-map", required=True)
    sp_fu.add_argument("--model", required=True)
    sp_fu.add_argument("--out", required=True)
    sp_fu.add_argument("--as-of", required=True)

    sp_ke = sub.add_parser("karte-effect")
    sp_ke.add_argument("--csv", required=True)
    sp_ke.add_argument("--column-map", required=True)
    sp_ke.add_argument("--interactions", required=True)
    sp_ke.add_argument("--interaction-map", required=True)
    sp_ke.add_argument("--as-of", required=True)

    sp_console = sub.add_parser("console")
    sp_console.add_argument("--csv", required=True)
    sp_console.add_argument("--column-map", required=True)
    sp_console.add_argument("--interactions", required=True)
    sp_console.add_argument("--interaction-map", required=True)
    sp_console.add_argument("--model", required=True)
    sp_console.add_argument("--out-dir", required=True)
    sp_console.add_argument("--as-of", required=True)

    sp_cohort = sub.add_parser("cohort")
    sp_cohort.add_argument("--csv", required=True)
    sp_cohort.add_argument("--column-map", required=True)
    sp_cohort.add_argument("--out", required=True)
    sp_cohort.add_argument("--as-of", required=True)
    sp_cohort.add_argument("--model", help="任意。指定すると着地見込み(推計)も表示")

    sp_today = sub.add_parser("today")
    sp_today.add_argument("--csv", required=True)
    sp_today.add_argument("--column-map", required=True)
    sp_today.add_argument("--model", required=True)
    sp_today.add_argument("--out", required=True)
    sp_today.add_argument("--as-of", required=True)
    sp_today.add_argument("--capacity", type=int, default=CAPACITY_PER_DAY)
    sp_today.add_argument("--contacts", help="任意。保全ログCSV（初動＝契約直後・未接触を拾う）")
    sp_today.add_argument("--contact-map", help="任意。保全ログのcolumn_map")

    sp_pre = sub.add_parser("preflight")
    sp_pre.add_argument("--csv", required=True)
    sp_pre.add_argument("--column-map", required=True)
    sp_pre.add_argument("--as-of", required=True)

    sp_ret = sub.add_parser("retention")
    sp_ret.add_argument("--dir", required=True)
    sp_ret.add_argument("--as-of", required=True)
    sp_ret.add_argument("--years", type=int, default=SNAPSHOT_RETENTION_YEARS)
    sp_ret.add_argument("--apply", action="store_true")

    sp_hz = sub.add_parser("hazard")
    sp_hz.add_argument("--csv", required=True)
    sp_hz.add_argument("--column-map", required=True)
    sp_hz.add_argument("--out", required=True)
    sp_hz.add_argument("--as-of", required=True)

    sp_up = sub.add_parser("uplift")
    sp_up.add_argument("--csv", required=True)
    sp_up.add_argument("--column-map", required=True)
    sp_up.add_argument("--contacts", required=True)
    sp_up.add_argument("--contact-map", required=True)
    sp_up.add_argument("--as-of", required=True)
    sp_up.add_argument("--treated-fraction", type=float, default=EXPERIMENT_TREATED_FRACTION)
    sp_up.add_argument("--salt", default="")

    sp_pb = sub.add_parser("playbook")
    sp_pb.add_argument("--csv", required=True)
    sp_pb.add_argument("--column-map", required=True)
    sp_pb.add_argument("--contacts", required=True)
    sp_pb.add_argument("--contact-map", required=True)
    sp_pb.add_argument("--out", required=True)
    sp_pb.add_argument("--as-of", required=True)
    sp_pb.add_argument("--segment", default="product")

    sp_snap = sub.add_parser("snapshot")
    sp_snap.add_argument("--csv", required=True)
    sp_snap.add_argument("--interactions")
    sp_snap.add_argument("--month", required=True)
    sp_snap.add_argument("--out-dir", default="private/snapshots")
    sp_snap.add_argument("--force", action="store_true")

    sp_pipe = sub.add_parser("pipeline")
    sp_pipe.add_argument("--csv", required=True)
    sp_pipe.add_argument("--column-map", required=True)
    sp_pipe.add_argument("--out-dir", required=True)
    sp_pipe.add_argument("--as-of", required=True)
    sp_pipe.add_argument("--split", required=True)
    sp_pipe.add_argument("--run-date", required=True)
    sp_pipe.add_argument("--interactions")
    sp_pipe.add_argument("--contacts", help="任意。保全ログCSV（初動を今日の要接触に載せる）")
    sp_pipe.add_argument("--contact-map", help="任意。保全ログのcolumn_map")
    sp_pipe.add_argument("--auc-min", type=float, default=AUC_MIN)
    sp_pipe.add_argument("--capacity", type=int, default=CAPACITY_PER_DAY)

    args = p.parse_args(argv)
    if args.cmd == "fit":
        cmd_fit(args.csv, args.column_map, args.model, args.as_of)
    elif args.cmd == "score":
        cmd_score(args.csv, args.column_map, args.model, args.out, args.as_of)
    elif args.cmd == "backtest":
        cmd_backtest(args.csv, args.column_map, args.split, args.as_of)
    elif args.cmd == "card":
        cmd_card(args.csv, args.column_map, args.model, args.apply_id, args.out, args.as_of)
    elif args.cmd == "report":
        cmd_report(args.csv, args.column_map, args.out, args.as_of)
    elif args.cmd == "karte":
        cmd_karte(args.csv, args.column_map, args.interactions, args.interaction_map,
                  args.model, args.customer_id, args.out, args.as_of)
    elif args.cmd == "followups":
        cmd_followups(args.csv, args.column_map, args.interactions, args.interaction_map,
                      args.model, args.out, args.as_of)
    elif args.cmd == "karte-effect":
        cmd_karte_effect(args.csv, args.column_map, args.interactions,
                         args.interaction_map, args.as_of)
    elif args.cmd == "console":
        cmd_console(args.csv, args.column_map, args.interactions, args.interaction_map,
                    args.model, args.out_dir, args.as_of)
    elif args.cmd == "cohort":
        cmd_cohort(args.csv, args.column_map, args.out, args.as_of, args.model)
    elif args.cmd == "today":
        cmd_today(args.csv, args.column_map, args.model, args.out, args.as_of, args.capacity,
                  args.contacts, args.contact_map)
    elif args.cmd == "snapshot":
        cmd_snapshot(args.csv, args.interactions, args.month, args.out_dir, args.force)
    elif args.cmd == "pipeline":
        cmd_pipeline(args.csv, args.column_map, args.out_dir, args.as_of, args.split,
                     args.run_date, args.auc_min, args.capacity, args.interactions,
                     args.contacts, args.contact_map)
    elif args.cmd == "preflight":
        cmd_preflight(args.csv, args.column_map, args.as_of)
    elif args.cmd == "retention":
        cmd_retention(args.dir, args.as_of, args.years, args.apply)
    elif args.cmd == "hazard":
        cmd_hazard(args.csv, args.column_map, args.out, args.as_of)
    elif args.cmd == "uplift":
        cmd_uplift(args.csv, args.column_map, args.contacts, args.contact_map,
                   args.as_of, args.treated_fraction, args.salt)
    elif args.cmd == "playbook":
        cmd_playbook(args.csv, args.column_map, args.contacts, args.contact_map,
                     args.out, args.as_of, args.segment)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
