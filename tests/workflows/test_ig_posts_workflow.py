"""ig-posts-mikata.yml(Task 15)の構成テスト。

実行: pytest tests/workflows/test_ig_posts_workflow.py -v
"""
import os

import yaml

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
WORKFLOW = os.path.join(BASE, ".github", "workflows", "ig-posts-mikata.yml")


def _load():
    with open(WORKFLOW, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _triggers(workflow):
    # PyYAML(YAML 1.1)は裸の `on:` を真偽値 True として読むため両方を見る
    return workflow.get("on", workflow.get(True))


def _steps(workflow):
    return workflow["jobs"]["generate-and-verify"]["steps"]


def _step(workflow, name_prefix):
    for s in _steps(workflow):
        if s.get("name", "").startswith(name_prefix):
            return s
    raise AssertionError(f"step not found: {name_prefix}")


def test_workflow_schedule_sunday_18jst():
    """Verify workflow triggers Sunday 18:00 JST (09:00 UTC)."""
    workflow = _load()
    schedule = _triggers(workflow)["schedule"]
    cron_expressions = [s["cron"] for s in schedule]
    assert "0 9 * * 0" in cron_expressions, \
        f"Expected '0 9 * * 0' (Sun 09:00 UTC), got {cron_expressions}"


def test_workflow_dispatch_enabled():
    assert "workflow_dispatch" in _triggers(_load())


def test_verify_runs_before_generate():
    # 生成側は verified NG を候補から外すので、照合が先でないと今週のNGが投稿案に残る
    names = [s.get("name", "") for s in _steps(_load())]
    v = next(i for i, n in enumerate(names) if n.startswith("Verify accuracy"))
    g = next(i for i, n in enumerate(names) if n.startswith("Generate draft posts"))
    assert v < g


def test_verify_uses_existing_flags_only():
    run = _step(_load(), "Verify accuracy")["run"]
    assert "--online" not in run  # verify_mikata_seido.py に存在しないフラグ
    assert "scripts/verify_mikata_seido.py" in run


def test_commit_includes_audit_log_and_forced_draft():
    run = _step(_load(), "Commit & push")["run"]
    assert "data/subsidies.json" in run
    assert "data/kpi/verify_mikata_audit.jsonl" in run
    assert "git add -f data/ig_posts_mikata_draft.json" in run


def test_slack_notify_is_optional():
    step = _step(_load(), "Notify approvers")
    assert step.get("continue-on-error") is True
    assert 'if [ -z "$SLACK_WEBHOOK" ]' in step["run"]
