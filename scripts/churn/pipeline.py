"""日次パイプライン（本番実行ハーネス）。

取込 → スキーマ検証(preflight) → fit → backtest →【AUCゲート】→ score → today →
cohort → snapshot を順に実行する。resilient-agent-design の4層（トリガー/ワークフロー/
エージェント/ガードレール）のうち、本モジュールは「ワークフロー＋ガードレール」を担う。

安全に止まる設計:
- スキーマ不正（column_map欠落・必須列欠落・日付パス不能）→ "stopped_schema"。publishしない。
- バックテストAUCが閾値未満 → "stopped_auc"。**当たらないモデルで現場を動かさない**。publishしない。
- 同日の再実行はべき等（idempotency_key = run:<run_date>）。完了済みならスキップして再publishしない。

状態の外部保存:
- 実行状態を out_dir/run_state_<run_date>.json に保存（job_id / idempotency_key / status /
  completed_steps / last_error / auc）。監査・再開のための足跡。

PII（churn-pii-guard）:
- 出力（list/today/cohort/snapshot）は顧客個人情報を含む。private/（gitignore）配下・統制環境限定。
- 実データでの本番実行は守り部審査とご決裁の後。合成データでの検証は審査前でも可。

使い方（合成データ例）:
  python -m scripts.churn.cli pipeline --csv private/demo/apps.csv \
    --column-map private/demo/cmap.json --out-dir private/run \
    --as-of 2026-08-01 --split 2026-01-01 --run-date 2026-08-01
"""
from __future__ import annotations
import json
import os

from .intake import load_column_map, load_records
from .contact_log import load_contacts
from .preflight import preflight_report
from .fit import fit_model
from .evaluate import backtest
from .report_list import build_rows, render_csv, render_html as render_list_html
from .triage import classify, triage, render_html as render_today_html
from .cohort import cohort_rows, overall_rate, excluded_summary, render_html as render_cohort_html
from .snapshot import snapshot as do_snapshot
from .config import AUC_MIN, CAPACITY_PER_DAY


def _state_path(out_dir, run_date):
    return os.path.join(out_dir, f"run_state_{run_date}.json")


def _save_state(out_dir, run_date, state):
    with open(_state_path(out_dir, run_date), "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def _load_state(out_dir, run_date):
    path = _state_path(out_dir, run_date)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def run_pipeline(csv_path, column_map_path, out_dir, as_of, split, run_date,
                 auc_min=AUC_MIN, capacity=CAPACITY_PER_DAY, notify=print,
                 interactions=None, contacts_path=None, contact_map_path=None):
    """日次パイプラインを実行し、実行状態のdictを返す。

    引数:
      as_of, split … datetime.date。run_date … "YYYY-MM-DD" 文字列（べき等キー・月次snapshot用）。
    返り値の主なキー: status / auc / completed_steps / last_error / idempotent_skip。
    """
    os.makedirs(out_dir, exist_ok=True)

    # --- べき等: 同日で完了済みなら再実行しない（再publishしない） ---
    prev = _load_state(out_dir, run_date)
    if prev and prev.get("status") == "completed":
        prev["idempotent_skip"] = True
        notify(f"[pipeline] run:{run_date} は完了済み。べき等スキップ。")
        return prev

    state = {
        "job_id": f"churn-daily:{run_date}",
        "idempotency_key": f"run:{run_date}",
        "status": "running",
        "completed_steps": [],
        "last_error": None,
        "auc": None,
        "idempotent_skip": False,
    }
    _save_state(out_dir, run_date, state)

    def _stop(status, msg):
        state["status"] = status
        state["last_error"] = msg
        _save_state(out_dir, run_date, state)
        notify(f"[pipeline] 安全停止 status={status}: {msg}")
        return state

    cmap = load_column_map(column_map_path)

    # --- ガードレール1: スキーマ検証（preflight）。不正なら publishせず停止 ---
    rep = preflight_report(csv_path, cmap, as_of)
    if not rep["ok"]:
        return _stop("stopped_schema",
                     f"preflight不可: 不足キー={rep['missing_keys']} "
                     f"不足列={rep['missing_columns']} 日付不能={rep['date_parse_fails']}")
    state["completed_steps"].append("preflight")
    _save_state(out_dir, run_date, state)

    records = load_records(csv_path, cmap, as_of)

    # --- 学習 ---
    model = fit_model(records)
    state["completed_steps"].append("fit")
    _save_state(out_dir, run_date, state)

    # --- バックテスト（品質ゲートの根拠） ---
    metrics = backtest(records, split)
    state["auc"] = metrics["auc"]
    # 較正・精度@キャパは情報として残す（AUCが唯一の停止ゲート。較正は警告に留める）
    state["ece"] = metrics["ece"]
    state["calibration_warning"] = metrics["calibration_warning"]
    state["precision_at_capacity"] = metrics["precision_at_capacity"]
    if metrics["calibration_warning"]:
        notify(f"[pipeline] ⚠️較正不良 ECE={metrics['ece']:.3f}（リスク%の水準ズレ・要確認）")
    state["completed_steps"].append("backtest")
    _save_state(out_dir, run_date, state)

    # --- ガードレール2: AUCゲート。閾値未満なら“当たらない”ので publishせず停止 ---
    if metrics["auc"] < auc_min:
        return _stop("stopped_auc",
                     f"AUC {metrics['auc']:.3f} < 閾値 {auc_min:.3f}（当たらないモデルで現場を動かさない）")

    # --- publish: 一覧 / 今日の要接触 / コホート ---
    scoreable = [r for r in records if r.get("is_scoreable")]
    rows = build_rows(scoreable, model)
    render_csv(rows, os.path.join(out_dir, "list.csv"))
    render_list_html(rows, os.path.join(out_dir, "list.html"))
    state["completed_steps"].append("score")
    _save_state(out_dir, run_date, state)

    # 保全ログがあれば「初動（契約直後・未接触）」も今日の要接触に載せる
    contacts = None
    if contacts_path and contact_map_path:
        contacts = load_contacts(contacts_path, load_column_map(contact_map_path))
    today, carry, stats = triage(classify(records, model, as_of, contacts=contacts), capacity)
    render_today_html(today, carry, stats, os.path.join(out_dir, "today.html"), capacity)
    state["completed_steps"].append("today")
    _save_state(out_dir, run_date, state)

    cohorts = cohort_rows(records, as_of, model=model)
    render_cohort_html(cohorts, overall_rate(cohorts), os.path.join(out_dir, "cohort.html"),
                       excluded=excluded_summary(records))
    state["completed_steps"].append("cohort")
    _save_state(out_dir, run_date, state)

    # --- 月次スナップショット（消さずに残す）。run_date の月に保存・べき等 ---
    month = run_date[:7]
    do_snapshot(csv_path, interactions, month, os.path.join(out_dir, "snapshots"))
    state["completed_steps"].append("snapshot")

    state["status"] = "completed"
    _save_state(out_dir, run_date, state)
    notify(f"[pipeline] 完了 run:{run_date} AUC={metrics['auc']:.3f} "
           f"要接触{stats['total']}→今日{len(today)} 継続中{len(scoreable)}件")
    return state
