"""moradou-cutover の安全対策の検査(山梨版停止に伴う判定の変更)。

- 外部接続なし: mc.fetch を差し替え、合成ツリーの上でだけ切替を試す。
- 実ファイルは読むだけ(承認状態・停止設定・ワークフローの文言)。
- 未実施 / 実施済み / 判定不能 の3状態と、承認ゲートの保留を確かめる。
"""
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import deploy_moradou as dm  # noqa: E402
import moradou_cutover as mc  # noqa: E402

NEW = mc.NEW_BASE
OLD = "https://allgroup-inc.github.io/hojo-hq/fukugiiro"
OLD_YAMANASHI = "https://allgroup-inc.github.io/hojo-hq/yamanashi"
TREES = [("site/fukugiiro", OLD, NEW)]
TARGETS = [("scripts/fg_seo.py", NEW)]
APPROVED = {"hold": False, "approved_by": "小柳", "approved_on": "2026-10-15"}
GOOD = {
    "/": (f'<link rel="canonical" href="{NEW}/">もらいわすれ堂', None),
    "/sitemap.xml": (f"<urlset><url><loc>{NEW}/</loc></url></urlset>", None),
}
PARKING = "<html><title>このドメインは取得されています</title></html>"


def _make_repo(tmp_path):
    base = tmp_path / "repo"
    (base / "site" / "fukugiiro" / "sub").mkdir(parents=True)
    (base / "scripts").mkdir(parents=True)
    # 手書きの入口ページ: canonical と、ナビのリンク(旧URLのまま残すべきもの)
    (base / "site" / "fukugiiro" / "index.html").write_text(
        f'<link rel="canonical" href="{OLD}/"><a href="{OLD}/kit/">ナビ</a>もらいわすれ堂',
        encoding="utf-8")
    (base / "site" / "fukugiiro" / "sub" / "page.html").write_text(
        f'<link rel="canonical" href="{OLD}/sub/">', encoding="utf-8")
    (base / "scripts" / "fg_seo.py").write_text('X = 1\nMOVED_TO = None\n', encoding="utf-8")
    return base


def _policy(tmp_path, **fields):
    p = tmp_path / "policy.json"
    p.write_text(json.dumps(fields, ensure_ascii=False), encoding="utf-8")
    return p


def _run(base, policy_path, monkeypatch, responses):
    calls = []

    def fake_fetch(url):
        path = url[len(NEW):]
        calls.append(path)
        return responses.get(path, (None, "HTTP 404"))

    monkeypatch.setattr(mc, "fetch", fake_fetch)
    rc = mc.main_apply(policy_path=str(policy_path), base=str(base), trees=TREES, targets=TARGETS)
    return rc, calls


def _snapshot(base):
    return {p: p.read_bytes() for p in base.rglob("*") if p.is_file()}


# ── 承認ゲート(hold が既定) ──────────────────────────────────────

def test_hold_default_blocks_switch_even_when_live(tmp_path, monkeypatch):
    base = _make_repo(tmp_path)
    before = _snapshot(base)
    rc, calls = _run(base, _policy(tmp_path, hold=True, approved_by="小柳", approved_on="2026-10-15"),
                     monkeypatch, GOOD)
    assert rc == 0
    assert calls == [], "保留中は開通の確認(通信)もしない"
    assert _snapshot(base) == before


def test_missing_policy_file_blocks_switch(tmp_path, monkeypatch):
    base = _make_repo(tmp_path)
    before = _snapshot(base)
    rc, calls = _run(base, tmp_path / "nope.json", monkeypatch, GOOD)
    assert rc == 0 and calls == []
    assert _snapshot(base) == before


@pytest.mark.parametrize("fields", [
    {"hold": False, "approved_by": None, "approved_on": "2026-10-15"},
    {"hold": False, "approved_by": "小柳", "approved_on": None},
    {"hold": False, "approved_by": "", "approved_on": "2026-10-15"},
    {"approved_by": "小柳", "approved_on": "2026-10-15"},  # hold 欄が無い → 既定 true
])
def test_incomplete_approval_blocks_switch(tmp_path, monkeypatch, fields):
    base = _make_repo(tmp_path)
    before = _snapshot(base)
    rc, calls = _run(base, _policy(tmp_path, **fields), monkeypatch, GOOD)
    assert rc == 0 and calls == []
    assert _snapshot(base) == before


def test_policy_states(tmp_path):
    assert mc.policy(str(tmp_path / "nope.json"))[0] is False
    assert mc.policy(str(_policy(tmp_path, **APPROVED)))[0] is True
    assert mc.policy(str(_policy(tmp_path, **dict(APPROVED, hold=True))))[0] is False
    bad = tmp_path / "broken.json"
    bad.write_text("{not json", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):  # 壊れた承認ファイルは通さない(fail-closed)
        mc.policy(str(bad))


def test_policy_cli_reports_not_approved_for_repo_default():
    out = subprocess.run([sys.executable, str(ROOT / "scripts" / "moradou_cutover.py"), "--policy"],
                         capture_output=True, text=True, cwd=str(ROOT), timeout=60)
    assert out.returncode == 0
    assert out.stdout.strip().splitlines()[-1] == "approved=false"


# ── 未実施 / 実施済み / 判定不能 ───────────────────────────────

def test_not_switched_and_approved_switches_canonicals_only(tmp_path, monkeypatch, capsys):
    base = _make_repo(tmp_path)
    rc, calls = _run(base, _policy(tmp_path, **APPROVED), monkeypatch, GOOD)
    assert rc == 0
    assert calls == ["/", "/sitemap.xml"]
    assert f'MOVED_TO = "{NEW}"' in (base / "scripts" / "fg_seo.py").read_text(encoding="utf-8")
    index = (base / "site" / "fukugiiro" / "index.html").read_text(encoding="utf-8")
    assert f'<link rel="canonical" href="{NEW}/">' in index
    assert f'<a href="{OLD}/kit/">ナビ</a>' in index, "ナビのリンクは旧URLのまま(ページは旧URLに在る)"
    sub = (base / "site" / "fukugiiro" / "sub" / "page.html").read_text(encoding="utf-8")
    assert f'href="{NEW}/sub/"' in sub
    assert mc.stale_canonicals(TREES, str(base)) == []


def test_already_switched_is_noop(tmp_path, monkeypatch, capsys):
    base = _make_repo(tmp_path)
    (base / "scripts" / "fg_seo.py").write_text(f'X = 1\nMOVED_TO = "{NEW}"\n', encoding="utf-8")
    index = base / "site" / "fukugiiro" / "index.html"
    index.write_text(f'<link rel="canonical" href="{NEW}/">もらいわすれ堂', encoding="utf-8")
    sub = base / "site" / "fukugiiro" / "sub" / "page.html"
    sub.write_text(f'<link rel="canonical" href="{NEW}/sub/">', encoding="utf-8")
    before = _snapshot(base)
    rc, _calls = _run(base, _policy(tmp_path, **APPROVED), monkeypatch, GOOD)
    assert rc == 0
    assert _snapshot(base) == before
    assert "変更はありません" in capsys.readouterr().out


@pytest.mark.parametrize("responses", [
    # 通信失敗(ドメインが引けない)
    {"/": (None, "つながらない(NXDOMAIN)"), "/sitemap.xml": GOOD["/sitemap.xml"]},
    # ドメイン業者の仮ページ(200だが中身が違う)
    {"/": (PARKING, None), "/sitemap.xml": GOOD["/sitemap.xml"]},
    # トップは出るが canonical が旧URLのまま
    {"/": (f'<link rel="canonical" href="{OLD}/">もらいわすれ堂', None),
     "/sitemap.xml": GOOD["/sitemap.xml"]},
    # sitemap が旧URLのまま
    {"/": GOOD["/"], "/sitemap.xml": (f"<urlset><loc>{OLD}/</loc></urlset>", None)},
    # 何も取れない
    {},
])
def test_not_live_or_unjudgeable_never_switches(tmp_path, monkeypatch, responses):
    base = _make_repo(tmp_path)
    before = _snapshot(base)
    rc, _calls = _run(base, _policy(tmp_path, **APPROVED), monkeypatch, responses)
    assert rc == mc.NOT_LIVE, "異常(1)ではなく『まだ』(2)として扱う"
    assert _snapshot(base) == before, "判定できないときは1バイトも変えない"


# ── 山梨版の停止 ───────────────────────────────────────────

def test_yamanashi_is_not_probed_and_fukugiiro_alone_can_switch(tmp_path, monkeypatch):
    base = _make_repo(tmp_path)
    rc, calls = _run(base, _policy(tmp_path, **APPROVED), monkeypatch, GOOD)
    assert rc == 0
    assert not any(c.startswith("/yamanashi") for c in calls), "停止中の山梨版を開通判定に使わない"


def test_real_stop_config_excludes_yamanashi_from_targets():
    assert "yamanashi" in mc.stopped_keys(mc.STOPPED_CONFIG)
    assert [rel for rel, _o, _n in mc.SITE_TREES] == ["site/fukugiiro"]
    assert [rel for rel, _n in mc.TARGETS] == ["scripts/fg_seo.py"]


def test_stopped_yamanashi_stale_page_is_ignored(tmp_path):
    base = tmp_path / "repo"
    (base / "site" / "yamanashi").mkdir(parents=True)
    (base / "site" / "yamanashi" / "index.html").write_text(
        f'<link rel="canonical" href="{OLD_YAMANASHI}/">', encoding="utf-8")
    stopped = tmp_path / "stopped.json"
    stopped.write_text(json.dumps({"version": 1, "stopped": [{"key": "yamanashi"}]}), encoding="utf-8")
    keys = mc.stopped_keys(str(stopped))
    trees = mc.active_trees(keys)
    assert [rel for rel, _o, _n in trees] == ["site/fukugiiro"]
    assert mc.active_targets(keys) == [("scripts/fg_seo.py", NEW)]
    assert mc.stale_canonicals(trees, str(base)) == [], "停止したサイトの古いページは検査の対象外"
    # 対照: 停止の設定を外せば同じページが検出される(検査が素通りしていないことの確認)
    all_trees = [(r, o, n) for _k, r, o, n in mc._ALL_TREES]
    assert mc.stale_canonicals(all_trees, str(base)) == ["site/yamanashi/index.html"]


# ── 自己テストと、ワークフローの文言 ─────────────────────────────

def test_self_test_passes_on_repo():
    out = subprocess.run([sys.executable, str(ROOT / "scripts" / "moradou_cutover.py"), "--self-test"],
                         capture_output=True, text=True, cwd=str(ROOT), timeout=120)
    assert out.returncode == 0, out.stdout + out.stderr


def _workflow_steps():
    wf = (ROOT / ".github" / "workflows" / "moradou-cutover.yml").read_text(encoding="utf-8")
    return wf, re.split(r"\n      - name: ", wf)[1:]


def test_workflow_never_regenerates_yamanashi():
    wf, _ = _workflow_steps()
    assert "build_yamanashi" not in wf
    assert not re.search(r"git add [^\n]*site/yamanashi", wf)


def test_workflow_has_policy_step_before_check():
    wf, _ = _workflow_steps()
    assert "id: policy" in wf and "moradou_cutover.py --policy" in wf
    assert wf.index("id: policy") < wf.index("id: check")


def test_workflow_gates_every_switch_step_on_approval():
    _, steps = _workflow_steps()
    gate = "steps.policy.outputs.approved == 'true'"
    gated = [s for s in steps if any(k in s for k in ("--apply", "取りこぼし", "git add"))]
    assert len(gated) == 3, "切替・取りこぼし確認・コミットの3段がある"
    for s in gated:
        m = re.search(r"^        if: (.*)$", s, re.M)
        assert m and gate in m.group(1), s.splitlines()[0]


# ── 停止設定の fail-closed(欠落・不正・コードとの食い違いでは切替を止める) ──

def _write_stop_cfg(tmp_path, obj):
    p = tmp_path / "stopped.json"
    p.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")
    return str(p)


def test_missing_stop_config_raises(tmp_path):
    with pytest.raises(RuntimeError):
        mc.stopped_keys(str(tmp_path / "nope.json"))


def test_broken_stop_config_raises(tmp_path):
    p = tmp_path / "stopped.json"
    p.write_text("{not json", encoding="utf-8")
    with pytest.raises(RuntimeError):
        mc.stopped_keys(str(p))


def test_unexpected_stop_config_version_raises(tmp_path):
    cfg = _write_stop_cfg(tmp_path, {"version": 2, "stopped": [{"key": "yamanashi"}]})
    with pytest.raises(RuntimeError):
        mc.stopped_keys(cfg)


def test_stop_config_that_drops_code_stop_raises(tmp_path):
    # 設定から yamanashi を消しただけでは再開しない。食い違いは例外で知らせる
    cfg = _write_stop_cfg(tmp_path, {"version": 1, "stopped": []})
    with pytest.raises(RuntimeError, match="yamanashi"):
        mc.stopped_keys(cfg)


def test_empty_selection_still_excludes_yamanashi():
    assert "site/yamanashi" not in [rel for rel, _o, _n in mc.active_trees(set())]
    assert "scripts/fg_yamanashi.py" not in [rel for rel, _n in mc.active_targets(set())]


def test_cutover_never_touches_yamanashi_targets(tmp_path):
    base = tmp_path / "repo"
    (base / "scripts").mkdir(parents=True)
    (base / "scripts" / "fg_seo.py").write_text("MOVED_TO = None\n", encoding="utf-8")
    (base / "scripts" / "fg_yamanashi.py").write_text("MOVED_TO = None\n", encoding="utf-8")
    changed = mc.apply_cutover(mc.active_targets(set()), str(base))
    assert changed == ["scripts/fg_seo.py"]
    assert (base / "scripts" / "fg_yamanashi.py").read_text(encoding="utf-8") == "MOVED_TO = None\n"


def test_cutover_cli_stops_when_stop_config_missing(tmp_path):
    # 承認済みでも、停止設定が無ければ何も判定せず止まる(承認状態も出さない)
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    shutil.copy(ROOT / "scripts" / "moradou_cutover.py", scripts / "moradou_cutover.py")
    (scripts / "moradou_cutover_policy.json").write_text(json.dumps(APPROVED), encoding="utf-8")
    out = subprocess.run([sys.executable, str(scripts / "moradou_cutover.py"), "--policy"],
                         capture_output=True, text=True, timeout=60)
    assert out.returncode != 0
    assert "approved=" not in out.stdout


def test_stop_publish_stops_and_deletes_nothing_when_config_missing(tmp_path):
    root = tmp_path / "pages"
    (root / "site" / "yamanashi").mkdir(parents=True)
    out = subprocess.run([sys.executable, str(ROOT / "scripts" / "stop_publish.py"),
                          "--root", str(root), "--config", str(tmp_path / "nope.json"), "--apply"],
                         capture_output=True, text=True, timeout=60)
    assert out.returncode != 0
    assert (root / "site" / "yamanashi").is_dir(), "設定が読めないときは何も削除しない"


def test_code_stop_is_recorded_in_real_config():
    assert mc.STOPPED_IN_CODE <= mc.stopped_keys(mc.STOPPED_CONFIG)


# ── 山梨版が再生成・再公開されない / 福岡版・LINE・/go/ は影響を受けない ──

def test_only_pr_ci_builds_yamanashi_and_nothing_writes_it():
    def _run_lines(p):
        # コメント行は除く(「実行しない」と書いた説明文を実行とみなさない)
        return [ln for ln in p.read_text(encoding="utf-8").splitlines()
                if ln.strip() and not ln.strip().startswith("#")]
    hits = {p.name for p in (ROOT / ".github" / "workflows").glob("*.yml")
            if any("build_yamanashi" in ln for ln in _run_lines(p))}
    # 夜間の収集・切替・配信からは外れている。PR時の検査ビルドだけを残す(書き込み・公開はしない)
    assert hits == {"fukugiiro-ci.yml"}
    ci = (ROOT / ".github" / "workflows" / "fukugiiro-ci.yml").read_text(encoding="utf-8")
    assert not re.search(r"git (add|commit|push)", ci)


_LINE_RE = re.compile(r"https://(?:lin\.ee/[A-Za-z0-9_-]+|line\.me/R/(?:ti/p|oaMessage)/%40[A-Za-z0-9_-]*)")


def test_moradou_build_keeps_fukugiiro_line_links_and_go_pages(tmp_path):
    out = tmp_path / "moradou"
    assert dm.build(str(out), "moradou.jp") == 0
    built = set()
    for p in out.rglob("*.html"):
        built |= set(_LINE_RE.findall(p.read_text(encoding="utf-8")))
    src_fk = set()
    for p in (ROOT / "site" / "fukugiiro").rglob("*.html"):
        src_fk |= set(_LINE_RE.findall(p.read_text(encoding="utf-8")))
    assert src_fk, "福岡版のLINE導線が源泉に無い(検査の前提が崩れている)"
    assert src_fk <= built, "福岡版のLINE導線が配信ツリーから消えた"
    assert {p.name for p in (ROOT / "site" / "go").glob("fg-*")} == \
        {p.name for p in (out / "go").glob("fg-*")}
    assert {p.name for p in (ROOT / "site" / "go").glob("ymn-*")} == \
        {p.name for p in (out / "go").glob("ymn-*")}, "/go/ymn-* は残す判断(stopped_sites.json の keep)"
