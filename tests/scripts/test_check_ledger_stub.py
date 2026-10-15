"""C4 台帳スタブ検査(scripts/check_ledger_stub.py)と update.yml の注入廃止の静的確認。

- 実値のトークン・エンドポイントは使わない。注入の形はダミーの文字列で再現する。
- 一時ファイルは作らない(判定はバイト列とパスの存在だけで行う)。
"""
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import check_ledger_stub as cls  # noqa: E402

WF = (ROOT / ".github" / "workflows" / "update.yml").read_text(encoding="utf-8")
TRACKED = (ROOT / "site" / "assets" / "ledger-config.js").read_bytes()
INJECTED = b'window.MIKATA_LEDGER={endpoint:"https://dummy.invalid/x",token:"DUMMY-NOT-A-SECRET"};\n'


def _steps():
    return yaml.safe_load(WF)["jobs"]["fetch-and-deploy"]["steps"]


def _index(prefix):
    names = [s.get("name") or s.get("uses") or "" for s in _steps()]
    return next(i for i, n in enumerate(names) if n.startswith(prefix))


def test_expected_hash_matches_tracked_stub():
    assert cls.stub_problem(TRACKED) is None


def test_stub_has_no_nonempty_values():
    assert cls.warnings_in(TRACKED) == []


def test_exact_stub_passes():
    assert cls.stub_problem(TRACKED) is None


@pytest.mark.parametrize("data", [TRACKED + b"\n", b"", INJECTED, TRACKED.replace(b"''", b"'x'")])
def test_any_change_fails(data):
    assert cls.stub_problem(data) is not None


def test_injected_dummy_is_caught_by_stub_check_and_warning():
    assert cls.stub_problem(INJECTED) is not None
    assert "ledger_nonempty" in cls.warnings_in(INJECTED)


def test_apps_script_url_warns_and_other_google_paths_do_not():
    assert "apps_script_url" in cls.warnings_in(b"fetch('https://script.google.com/macros/s/DUMMY/exec')")
    assert cls.warnings_in(b"<a href='https://script.google.com/home'>x</a>") == []


def test_missing_artifact_fails_closed():
    assert cls.check_tree(Path("/nonexistent-ledger-check-root")) == 1


def test_selftest_passes():
    assert cls.selftest() == 0


def test_update_yml_no_longer_injects_ledger():
    assert "GAS_LEDGER_ENDPOINT" not in WF
    assert "GAS_LEDGER_TOKEN" not in WF
    assert "site/assets/ledger-config.js" not in WF
    assert "Inject ledger config" not in WF


def test_guard_c4_runs_before_upload_and_gets_no_secrets():
    guard = _steps()[_index("Guard (C4")]
    assert "env" not in guard
    assert "check_ledger_stub.py --selftest" in guard["run"]
    assert "check_ledger_stub.py --root /tmp/pages-deploy" in guard["run"]
    assert _index("Verify artifact (C3") < _index("Guard (C4") < _index("Upload site") < _index("Deploy to GitHub Pages")


def test_c3_and_upload_unchanged_in_text():
    assert "/tmp/pages-deploy/data/subsidies.json" in WF
    assert "uses: actions/upload-pages-artifact@v5" in WF
    assert "uses: actions/deploy-pages@v5" in WF
