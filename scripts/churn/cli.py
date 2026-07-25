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

    args = p.parse_args(argv)
    if args.cmd == "fit":
        cmd_fit(args.csv, args.column_map, args.model, args.as_of)
    elif args.cmd == "score":
        cmd_score(args.csv, args.column_map, args.model, args.out, args.as_of)
    elif args.cmd == "backtest":
        cmd_backtest(args.csv, args.column_map, args.split, args.as_of)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
