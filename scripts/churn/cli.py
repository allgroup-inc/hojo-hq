"""CLI：fit / score / backtest を通しで実行する。

例（顧客データは private/ 配下で実行する）:
  python -m scripts.churn.cli fit --csv private/data.csv --column-map private/column_map.json --model private/risk_model.json
  python -m scripts.churn.cli score --csv private/data.csv --column-map private/column_map.json --model private/risk_model.json --out private/list
  python -m scripts.churn.cli backtest --csv private/data.csv --column-map private/column_map.json --split 2026-01-01
"""
from __future__ import annotations
import argparse
from datetime import date

from .intake import load_records, load_column_map
from .fit import fit_model, save_model, load_model
from .report_list import build_rows, render_csv, render_html
from .evaluate import backtest
from .report_card import build_card, render_html as render_card_html
from .report_agg import aggregate_by, render_html as render_agg_html


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
          f"top10%lift={metrics['top_decile_lift']:.2f}")
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
