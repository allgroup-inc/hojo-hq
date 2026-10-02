"""各テストスクリプトの結果を results/<name>.json に書く。

ワークフロー(block2-test-orchestration*.yml)の「Parse test results」はこの JSON を読む。
ファイル名の stem と中のキーは G1 判定ステップの参照先に合わせる:
  business-axis.json : passed, passed_count, total
  api-chain.json     : passed, passed_count, total
  ui.json            : passed, passed_count, total
  performance.json   : passed, p95_ms, error_rate
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable

P95_THRESHOLD_MS = 1000.0
ERROR_RATE_THRESHOLD = 0.01


def write_result(results_dir, name: str, passed, **extra) -> Path:
    results_dir = Path(results_dir)
    results_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "name": name,
        "passed": bool(passed),
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        **extra,
    }
    path = results_dir / f"{name}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def summarize_performance(results: Iterable[Dict]) -> Dict:
    """エンドポイント別計測の一覧から G1 用の集計値を出す。

    P95 は全計測の最悪値(どれか1つでも超えたら不合格)、エラー率は全リクエストの合算。
    """
    results = list(results)
    p95 = max((float(r.get("p95_ms", 0) or 0) for r in results), default=0.0)
    total = sum(int(r.get("total_requests", 0) or 0) for r in results)
    errors = sum(int(r.get("errors", 0) or 0) for r in results)
    error_rate = (errors / total) if total > 0 else 1.0
    passed = total > 0 and p95 <= P95_THRESHOLD_MS and error_rate <= ERROR_RATE_THRESHOLD
    return {
        "passed": passed,
        "p95_ms": p95,
        "error_rate": error_rate,
        "total_requests": total,
        "errors": errors,
        "measurements": len(results),
    }


def summarize_playwright(report: Dict) -> Dict:
    """`playwright test --reporter=json` の出力(stats)から件数を取る。"""
    stats = report.get("stats") or {}
    expected = int(stats.get("expected", 0) or 0)
    unexpected = int(stats.get("unexpected", 0) or 0)
    flaky = int(stats.get("flaky", 0) or 0)
    skipped = int(stats.get("skipped", 0) or 0)
    total = expected + unexpected + flaky + skipped
    return {
        "passed": total > 0 and unexpected == 0,
        "passed_count": expected,
        "failed_count": unexpected,
        "flaky_count": flaky,
        "skipped_count": skipped,
        "total": total,
    }
