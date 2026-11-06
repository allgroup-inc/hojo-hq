"""GLOW Instagram 安全対策(2026-11-03)の検査: M8・M1・M2・鍵の漏えい防止・最小権限。

すべて合成データ。実際の Meta への投稿・本番の鍵・外部への通信は使わない
(Meta の呼び出しと画像の取得は偽物に差し替える)。
架空の鍵は実行時に組み立てる(ファイルに鍵の形の文字列を残さない)。
"""
import io
import json
import os
import shutil
import subprocess
import sys
import urllib.error
from datetime import datetime, timedelta

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SCRIPTS = os.path.join(ROOT, "scripts")
sys.path.insert(0, SCRIPTS)

import sns_safety  # noqa: E402
from sns_safety import JST, SafetyError  # noqa: E402

FAKE_TOKEN = "EAA" + "Zz9" * 12          # 架空の鍵(Meta の鍵の形だけ真似る)
FAKE_SHA = "ab" * 20
NOW = datetime(2026, 11, 3, 12, 0, tzinfo=JST)


def _http_error(body):
    return urllib.error.HTTPError("https://graph.example.invalid/x", 400, "Bad Request",
                                  {}, io.BytesIO(json.dumps(body).encode()))


# ---------------------------------------------------------------- 鍵を出さない

def test_redact_hides_token_forms():
    s = sns_safety.redact(f"url?access_token={FAKE_TOKEN}&a=1 Bearer {FAKE_TOKEN} {FAKE_TOKEN}")
    assert FAKE_TOKEN not in s
    assert "access_token=***" in s


def test_meta_error_summary_never_contains_body():
    e = _http_error({"error": {"message": f"bad token {FAKE_TOKEN}", "type": "OAuthException",
                               "code": 190, "error_subcode": 463, "fbtrace_id": "Xyz"}})
    out = sns_safety.meta_error_summary(e)
    assert out == "HTTP 400 type=OAuthException code=190 error_subcode=463"
    assert FAKE_TOKEN not in out and "bad token" not in out


def test_meta_error_summary_rejects_odd_values():
    e = _http_error({"error": {"type": f"x {FAKE_TOKEN}", "code": "190"}})
    assert FAKE_TOKEN not in sns_safety.meta_error_summary(e)


def test_meta_post_failure_message_is_safe():
    def opener(req, timeout=None):
        assert FAKE_TOKEN not in req.full_url        # 鍵は URL に載せない
        assert FAKE_TOKEN.encode() in req.data       # 本文(POST の中身)にだけ入る
        raise _http_error({"error": {"message": f"echo {FAKE_TOKEN}", "code": 190}})
    with pytest.raises(SafetyError) as ei:
        sns_safety.meta_post("/1/media", {"access_token": FAKE_TOKEN}, opener=opener)
    assert FAKE_TOKEN not in str(ei.value) and "HTTP 400" in str(ei.value)


# ---------------------------------------------------------------- 固定URL・投稿先

def test_pinned_url_requires_commit_sha():
    assert sns_safety.pinned_raw_url(FAKE_SHA, "posts/a.png").endswith(f"/{FAKE_SHA}/posts/a.png")
    for bad in ("", "main", "abc"):
        with pytest.raises(SafetyError):
            sns_safety.pinned_raw_url(bad, "posts/a.png")
    with pytest.raises(SafetyError):
        sns_safety.pinned_raw_url(FAKE_SHA, "posts/../x.png")


def test_check_destination():
    fp = sns_safety.destination_fingerprint("111", "222")
    sns_safety.check_destination(fp, "111", "222")
    with pytest.raises(SafetyError, match="指紋が未設定"):
        sns_safety.check_destination("", "111", "222")         # 未設定なら投稿しない
    with pytest.raises(SafetyError):
        sns_safety.check_destination(fp, "111", "999")         # 違う投稿先
    with pytest.raises(SafetyError):
        sns_safety.check_destination(fp, "", "222")


# ---------------------------------------------------------------- 承認対象(M1)

@pytest.fixture
def repo(tmp_path):
    (tmp_path / "posts").mkdir()
    (tmp_path / "posts" / "a.png").write_bytes(b"\x89PNG synthetic image A")
    return tmp_path


def _pkg(repo, caption="本文です", created=NOW):
    return sns_safety.build_package(account="テスト", kind="single", caption=caption,
                                    images=["posts/a.png"], sha=FAKE_SHA, base_dir=str(repo),
                                    created_at=created)


def _fetch_from(repo):
    return lambda url: (repo / "posts" / "a.png").read_bytes()


def test_package_verify_ok(repo):
    pkg = _pkg(repo)
    d = sns_safety.package_digest(pkg)
    sns_safety.verify_before_publish(pkg, d, now=NOW + timedelta(hours=1), fetch=_fetch_from(repo))


def test_package_digest_changes_with_caption(repo):
    assert sns_safety.package_digest(_pkg(repo)) != sns_safety.package_digest(_pkg(repo, "別の本文"))


def test_package_stops_on_tampered_image(repo):
    pkg = _pkg(repo)
    d = sns_safety.package_digest(pkg)
    with pytest.raises(SafetyError, match="画像が承認時と一致しません"):
        sns_safety.verify_before_publish(pkg, d, now=NOW, fetch=lambda u: b"swapped")


def test_package_stops_on_digest_mismatch_or_missing(repo):
    pkg = _pkg(repo)
    other = sns_safety.package_digest(_pkg(repo, "別の本文"))
    with pytest.raises(SafetyError, match="一致しません"):
        sns_safety.verify_before_publish(pkg, other, now=NOW, fetch=_fetch_from(repo))
    for bad in ("", None, "xyz"):
        with pytest.raises(SafetyError, match="渡されていません"):
            sns_safety.verify_before_publish(pkg, bad, now=NOW, fetch=_fetch_from(repo))


def test_package_stops_when_expired(repo):
    pkg = _pkg(repo)
    d = sns_safety.package_digest(pkg)
    with pytest.raises(SafetyError, match="期限"):
        sns_safety.verify_before_publish(pkg, d, now=NOW + timedelta(hours=49), fetch=_fetch_from(repo))


def test_package_stops_when_image_unreachable(repo):
    pkg = _pkg(repo)
    d = sns_safety.package_digest(pkg)

    def boom(url):
        raise urllib.error.URLError("down")
    with pytest.raises(SafetyError, match="取得できません"):
        sns_safety.verify_before_publish(pkg, d, now=NOW, fetch=boom)


def test_preview_lines_have_no_secret_or_ids(repo):
    pkg = _pkg(repo)
    text = "\n".join(sns_safety.preview_lines(pkg, sns_safety.package_digest(pkg), "本文です"))
    assert "本文です" in text and "posts/a.png" in text and FAKE_TOKEN not in text


# ---------------------------------------------------------------- 制度情報(M2)

SRC = "https://www.jgrants-portal.go.jp/subsidy/SYNTH0001"
MD = f"## キャプション\n本文\n\n## 出典\n{SRC}\n\n## 出荷ゲート\n- gates: x\n"


def _sub(**over):
    v = {"claude_verified": True, "gemini_verified": None, "conflict": False,
         "timestamp": (NOW - timedelta(hours=10)).isoformat(),
         "details": {"source_reachable": True, "deadline_match": True, "status_match": True}}
    s = {"id": "SYNTH0001", "source_url": SRC, "status": "募集中", "deadline": "2026-12-15", "verified": v}
    for k, val in over.items():
        if k in ("claude_verified", "gemini_verified", "conflict", "timestamp"):
            v[k] = val
        elif k in ("source_reachable", "deadline_match", "status_match"):
            v["details"][k] = val
        else:
            s[k] = val
    return s


def test_seido_ok():
    assert sns_safety.check_seido(MD, [_sub()], now=NOW) == []


@pytest.mark.parametrize("over,needle", [
    ({"timestamp": (NOW - timedelta(hours=73)).isoformat()}, "72時間"),
    ({"status_match": None}, "募集状況"),
    ({"deadline_match": False}, "締切を原文"),
    ({"source_reachable": False}, "公募要領"),
    ({"claude_verified": None}, "公募要領との照合"),
    ({"gemini_verified": False}, "公募要領との照合"),
    ({"conflict": True}, "食い違"),
    ({"deadline": "2026-11-01"}, "締切を過ぎ"),
    ({"status": "募集終了"}, "募集中"),
    ({"verified": None}, "照合記録"),
])
def test_seido_blocks(over, needle):
    probs = sns_safety.check_seido(MD, [_sub(**over)], now=NOW)
    assert any(needle in p for p in probs), probs


def test_seido_unknown_source_blocks():
    assert sns_safety.check_seido(MD, [], now=NOW)


def test_seido_own_site_only_is_not_seido():
    md = "## 出典\nhttps://allgroup-inc.github.io/hojo-hq/?utm_source=instagram\n"
    assert sns_safety.check_seido(md, [], now=NOW) == []


def test_issuer_label():
    assert sns_safety.issuer_label("経済産業省") == "経済産業省"
    assert sns_safety.issuer_label("沖縄県(産業・公募補助金)") == "沖縄県(産業・公募補助金)"
    assert sns_safety.issuer_label("沖縄県産業振興公社") == "沖縄県産業振興公社"
    assert sns_safety.issuer_label("建築物等のZEB化・省CO2化普及加速事業") == "要確認"
    assert sns_safety.issuer_label("ものづくり補助金") == "要確認"
    assert sns_safety.issuer_label(None) == "要確認"


# ---------------------------------------------------------------- post_social の通し(偽の Meta)

@pytest.fixture
def social(tmp_path, monkeypatch):
    import post_social as ps
    (tmp_path / "posts" / "launch").mkdir(parents=True)
    (tmp_path / "posts" / "images").mkdir(parents=True)
    (tmp_path / "data").mkdir()
    (tmp_path / "posts" / "launch" / "01_seido.md").write_text(
        f"# 合成\n\n## キャプション\n合成の本文です。\n{SRC}\n\n## 出典\n{SRC}\n\n## 出荷ゲート\n- gates: x\n",
        encoding="utf-8")
    (tmp_path / "posts" / "images" / "01_seido.png").write_bytes(b"\x89PNG synthetic 01")
    subs = tmp_path / "data" / "subsidies.json"
    subs.write_text(json.dumps({"items": [_sub(timestamp=datetime.now(JST).isoformat())]}), encoding="utf-8")
    monkeypatch.setattr(ps, "BASE", str(tmp_path))
    monkeypatch.setattr(ps, "SUBSIDIES_PATH", str(subs))
    monkeypatch.setattr(ps, "STATE_PATH", str(tmp_path / "data" / "state.json"))
    monkeypatch.setattr(ps, "CAROUSEL_DIR", str(tmp_path / "posts" / "carousel"))
    monkeypatch.setattr(ps, "gate_or_die", lambda md: None)
    monkeypatch.setattr(ps.shipping_gate, "verify_file", lambda md: (True, [], []))
    monkeypatch.setattr(ps.time, "sleep", lambda s: None)
    monkeypatch.setenv("GITHUB_SHA", FAKE_SHA)
    monkeypatch.setenv("FB_PAGE_ID", "111")
    monkeypatch.setenv("IG_USER_ID", "222")
    monkeypatch.setenv("FB_PAGE_ACCESS_TOKEN", FAKE_TOKEN)
    monkeypatch.setenv("SNS_DEST_FP_MIKATA", sns_safety.destination_fingerprint("111", "222"))
    calls = []

    def fake_api(path, params):
        calls.append(path)
        return {"id": "m1"}
    monkeypatch.setattr(ps, "api", fake_api)
    img = tmp_path / "posts" / "images" / "01_seido.png"
    monkeypatch.setattr(sns_safety, "_default_fetch", lambda url, timeout=30: img.read_bytes())
    return ps, tmp_path, calls


def _preview(ps, monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["post_social.py", "--preview"])
    ps.main()
    out = dict(line.split("=", 1) for line in capsys.readouterr().out.splitlines() if "=" in line)
    return out


def _post(ps, monkeypatch, stem, digest, created, fetch=None):
    if fetch is not None:
        real = sns_safety.verify_before_publish
        monkeypatch.setattr(sns_safety, "verify_before_publish",
                            lambda pkg, d, **kw: real(pkg, d, fetch=fetch))
    else:
        real = sns_safety.verify_before_publish
        monkeypatch.setattr(sns_safety, "verify_before_publish",
                            lambda pkg, d, **kw: real(pkg, d, fetch=lambda u: _IMG[0]))
    monkeypatch.setattr(sys, "argv", ["post_social.py", "--stem", stem,
                                      "--approved-digest", digest, "--approved-created", created])
    ps.main()


_IMG = [b""]


def test_social_preview_then_post_ok(social, monkeypatch, capsys):
    ps, root, calls = social
    out = _preview(ps, monkeypatch, capsys)
    assert out["seido"] == "ok" and out["pkg"] == "ok" and FAKE_SHA in out["image"]
    _IMG[0] = (root / "posts" / "images" / "01_seido.png").read_bytes()
    _post(ps, monkeypatch, out["stem"], out["pkg_digest"], out["pkg_created"])
    printed = capsys.readouterr().out
    assert calls == ["/111/photos", "/222/media", "/222/media_publish"]
    assert FAKE_TOKEN not in printed


def test_social_image_swapped_after_approval_blocks(social, monkeypatch, capsys):
    ps, root, calls = social
    out = _preview(ps, monkeypatch, capsys)
    (root / "posts" / "images" / "01_seido.png").write_bytes(b"\x89PNG swapped")
    _IMG[0] = b"\x89PNG swapped"
    with pytest.raises(SystemExit):
        _post(ps, monkeypatch, out["stem"], out["pkg_digest"], out["pkg_created"])
    assert calls == []


def test_social_caption_changed_after_approval_blocks(social, monkeypatch, capsys):
    ps, root, calls = social
    out = _preview(ps, monkeypatch, capsys)
    md = root / "posts" / "launch" / "01_seido.md"
    md.write_text(md.read_text(encoding="utf-8").replace("合成の本文です。", "書き換えた本文"), encoding="utf-8")
    _IMG[0] = (root / "posts" / "images" / "01_seido.png").read_bytes()
    with pytest.raises(SystemExit):
        _post(ps, monkeypatch, out["stem"], out["pkg_digest"], out["pkg_created"])
    assert calls == []


def test_social_unverified_seido_blocks(social, monkeypatch, capsys):
    ps, root, calls = social
    (root / "data" / "subsidies.json").write_text(
        json.dumps({"items": [_sub(status_match=None, timestamp=datetime.now(JST).isoformat())]}),
        encoding="utf-8")
    out = _preview(ps, monkeypatch, capsys)
    assert out["seido"] == "ng"
    _IMG[0] = (root / "posts" / "images" / "01_seido.png").read_bytes()
    with pytest.raises(SystemExit):
        _post(ps, monkeypatch, out["stem"], out["pkg_digest"], out["pkg_created"])
    assert calls == []


def test_social_destination_unset_blocks(social, monkeypatch, capsys):
    ps, root, calls = social
    out = _preview(ps, monkeypatch, capsys)
    monkeypatch.setenv("SNS_DEST_FP_MIKATA", "")
    _IMG[0] = (root / "posts" / "images" / "01_seido.png").read_bytes()
    with pytest.raises(SystemExit):
        _post(ps, monkeypatch, out["stem"], out["pkg_digest"], out["pkg_created"])
    assert calls == []


def test_social_requires_approval_args(social, monkeypatch):
    ps, root, calls = social
    for argv in (["post_social.py"], ["post_social.py", "--stem", "01_seido"],
                 ["post_social.py", "--stem", "01_seido", "--approved-digest", "a" * 64]):
        monkeypatch.setattr(sys, "argv", argv)
        with pytest.raises(SystemExit):
            ps.main()
    assert calls == []


def test_social_meta_failure_output_is_safe(social, monkeypatch, capsys):
    ps, root, calls = social
    out = _preview(ps, monkeypatch, capsys)

    def failing(path, params):
        raise SafetyError("Meta API の呼び出しに失敗しました(HTTP 400 code=190)")
    monkeypatch.setattr(ps, "api", failing)
    _IMG[0] = (root / "posts" / "images" / "01_seido.png").read_bytes()
    with pytest.raises(SystemExit) as ei:
        _post(ps, monkeypatch, out["stem"], out["pkg_digest"], out["pkg_created"])
    assert FAKE_TOKEN not in str(ei.value) + capsys.readouterr().out


# ---------------------------------------------------------------- 手動投稿(ig_manual_post)

@pytest.fixture
def manual(tmp_path, monkeypatch):
    import ig_manual_post as im
    (tmp_path / "posts").mkdir()
    img = tmp_path / "posts" / "s.png"
    img.write_bytes(b"\x89PNG synthetic story")
    monkeypatch.setattr(im, "BASE", str(tmp_path))
    monkeypatch.setenv("GITHUB_SHA", FAKE_SHA)
    monkeypatch.setenv("IG_USER_ID", "222")
    monkeypatch.setenv("FB_PAGE_ACCESS_TOKEN", FAKE_TOKEN)
    monkeypatch.setenv("FB_PAGE_ID", "111")
    monkeypatch.setenv("SNS_DEST_FP_MIKATA", sns_safety.destination_fingerprint("111", "222"))
    calls = []

    def fake_meta_post(path, params, **kw):
        calls.append((path, params.get("media_type")))
        return {"id": "c1"}
    monkeypatch.setattr(sns_safety, "meta_post", fake_meta_post)
    monkeypatch.setattr(im.time, "sleep", lambda s: None)
    return im, tmp_path, img, calls


def _manual_preview(im, capsys, kind, extra=()):
    assert im.main(["--kind", kind, "--image", "posts/s.png", "--preview", *extra]) == 0
    return dict(l.split("=", 1) for l in capsys.readouterr().out.splitlines() if "=" in l)


def test_manual_story_ok(manual, monkeypatch, capsys):
    im, root, img, calls = manual
    out = _manual_preview(im, capsys, "story")
    real = sns_safety.verify_before_publish
    monkeypatch.setattr(sns_safety, "verify_before_publish",
                        lambda p, d, **kw: real(p, d, fetch=lambda u: img.read_bytes()))
    rc = im.main(["--kind", "story", "--image", "posts/s.png", "--post",
                  "--approved-digest", out["pkg_digest"], "--approved-created", out["pkg_created"]])
    assert rc == 0 and calls == [("/222/media", "STORIES"), ("/222/media_publish", None)]


def test_manual_feed_caption_change_blocks(manual, monkeypatch, capsys, tmp_path):
    im, root, img, calls = manual
    cap = tmp_path / "cap.txt"
    cap.write_text("最初の本文", encoding="utf-8")
    out = _manual_preview(im, capsys, "feed", ("--caption-file", str(cap)))
    cap.write_text("差し替えた本文", encoding="utf-8")
    real = sns_safety.verify_before_publish
    monkeypatch.setattr(sns_safety, "verify_before_publish",
                        lambda p, d, **kw: real(p, d, fetch=lambda u: img.read_bytes()))
    rc = im.main(["--kind", "feed", "--image", "posts/s.png", "--caption-file", str(cap), "--post",
                  "--approved-digest", out["pkg_digest"], "--approved-created", out["pkg_created"]])
    assert rc == 1 and calls == []


def test_manual_without_approval_blocks(manual):
    im, root, img, calls = manual
    assert im.main(["--kind", "story", "--image", "posts/s.png", "--post"]) == 1
    assert calls == []


# ---------------------------------------------------------------- ワークフローの形

yaml = pytest.importorskip("yaml")


def _wf(name):
    with open(os.path.join(ROOT, ".github", "workflows", name), encoding="utf-8") as f:
        text = f.read()
    return yaml.safe_load(text), text


@pytest.mark.parametrize("name", ["ig-feed.yml", "ig-story.yml", "social-post.yml"])
def test_meta_key_only_in_approved_job(name):
    wf, text = _wf(name)
    for jname, job in wf["jobs"].items():
        blob = json.dumps(job, ensure_ascii=False)
        if "FB_PAGE_ACCESS_TOKEN" in blob:
            assert job.get("environment") == "sns-approval", (name, jname)
            assert job.get("if") == "github.ref == 'refs/heads/main'", (name, jname)
    runs = "\n".join(st.get("run", "") for job in wf["jobs"].values() for st in job.get("steps", []))
    assert "set -x" not in runs and "access_token=" not in runs and "graph.facebook.com" not in runs


@pytest.mark.parametrize("name", ["ig-feed.yml", "ig-story.yml", "social-post.yml"])
def test_post_passes_approved_digest(name):
    _, text = _wf(name)
    assert "--approved-digest" in text and "--approved-created" in text
    assert "SNS_DEST_FP_MIKATA" in text


def test_glow_least_privilege():
    wf, _ = _wf("glow-sns-post.yml")
    assert wf["permissions"] == {"contents": "read"}
    post, record = wf["jobs"]["post"], wf["jobs"]["record"]
    assert post["permissions"] == {"contents": "read"}
    assert "GLOW_FB_PAGE_TOKEN" in json.dumps(post) and "GLOW_FB_PAGE_TOKEN" not in json.dumps(record)
    assert record["permissions"] == {"contents": "write"}
    assert wf[True]["schedule"] == [{"cron": "5 3 * * 1,3,5"}]     # 定期実行は変えていない


def test_hygiene_check_selftest_and_repo():
    r = subprocess.run([sys.executable, os.path.join(SCRIPTS, "check_workflow_secret_hygiene.py"), "--selftest"],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    r = subprocess.run([sys.executable, os.path.join(SCRIPTS, "check_workflow_secret_hygiene.py")],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout


# 修正前の手動投稿(ig-feed)と同じ形の架空のワークフロー。
# main を読みに行かないので、PR のマージ前でも後でも必ず実行される(飛ばしにならない)。
OLD_STYLE_IG_FEED = """
name: ig-feed
on:
  workflow_dispatch:
    inputs:
      image:
        required: true
permissions:
  contents: read
jobs:
  post:
    runs-on: ubuntu-latest
    steps:
      - name: フィード投稿
        env:
          TOKEN: ${{ secrets.FB_PAGE_ACCESS_TOKEN }}
          IG_USER: ${{ secrets.IG_USER_ID }}
        run: |
          set -e
          set -x
          create=$(curl -sS -X POST "https://graph.facebook.com/v21.0/${IG_USER}/media" \\
            -d "access_token=${TOKEN}")
"""


def test_hygiene_check_catches_old_ig_feed():
    """修正前の ig-feed の形(set -x・承認なし・access_token を引数に)を検査が止めること。"""
    import check_workflow_secret_hygiene as h
    rules = {f[0] for f in h.check_text("ig-feed.yml", OLD_STYLE_IG_FEED)}
    assert {"W1", "W3", "W4", "W5"} <= rules, rules


# ---------------------------------------------------------------- 数字を読むだけの鍵(週次レポート・分析)

def _debug_opener(payload=None, exc=None):
    seen = []

    def opener(req, timeout=None):
        seen.append(req)
        if exc:
            raise exc
        return io.BytesIO(json.dumps({"data": payload}).encode())
    return opener, seen


@pytest.fixture(autouse=True)
def _clear_insights_cache():
    sns_safety._INSIGHTS_CACHE.clear()
    yield
    sns_safety._INSIGHTS_CACHE.clear()


def test_insights_token_missing_never_falls_back_to_publish_key():
    tok, why = sns_safety.insights_token(env={"FB_PAGE_ACCESS_TOKEN": FAKE_TOKEN})
    assert tok == "" and "未接続" in why


def test_insights_token_read_only_ok():
    op, seen = _debug_opener({"is_valid": True, "scopes": ["instagram_basic", "pages_read_engagement"]})
    tok, why = sns_safety.insights_token(env={"META_INSIGHTS_TOKEN": FAKE_TOKEN}, opener=op)
    assert tok == FAKE_TOKEN and why == "ok"
    assert seen[0].get_header("Authorization") == f"Bearer {FAKE_TOKEN}"


@pytest.mark.parametrize("payload,needle", [
    ({"is_valid": True, "scopes": ["instagram_basic", "instagram_content_publish"]}, "投稿・管理の権限"),
    ({"is_valid": True, "scopes": ["pages_manage_posts"]}, "投稿・管理の権限"),
    ({"is_valid": False, "scopes": ["instagram_basic"]}, "無効"),
])
def test_insights_token_refuses(payload, needle):
    op, _ = _debug_opener(payload)
    tok, why = sns_safety.insights_token(env={"META_INSIGHTS_TOKEN": FAKE_TOKEN}, opener=op)
    assert tok == "" and needle in why and FAKE_TOKEN not in why


def test_insights_token_unverifiable_refuses_safely():
    op, _ = _debug_opener(exc=_http_error({"error": {"message": f"x {FAKE_TOKEN}", "code": 190}}))
    tok, why = sns_safety.insights_token(env={"META_INSIGHTS_TOKEN": FAKE_TOKEN}, opener=op)
    assert tok == "" and "確認できない" in why and FAKE_TOKEN not in why


def test_weekly_report_uses_header_not_url(monkeypatch):
    import weekly_report as wr
    monkeypatch.setenv("IG_USER_ID", "222")
    monkeypatch.setenv("FB_PAGE_ID", "111")
    monkeypatch.setenv("META_INSIGHTS_TOKEN", FAKE_TOKEN)
    monkeypatch.setattr(sns_safety, "insights_token", lambda: (FAKE_TOKEN, "ok"))
    calls = []

    def fake_get(url, headers=None):
        calls.append((url, headers))
        return {"followers_count": 1, "media_count": 2, "fan_count": 3, "data": []}
    monkeypatch.setattr(wr, "get", fake_get)
    assert "フォロワー 1人" in wr.section_instagram()
    assert "フォロワー 1人" in wr.section_facebook()
    assert calls and all(FAKE_TOKEN not in u for u, _ in calls)
    assert all(h == {"Authorization": f"Bearer {FAKE_TOKEN}"} for _, h in calls)


def test_weekly_report_refused_token_shows_reason(monkeypatch):
    import weekly_report as wr
    monkeypatch.setenv("IG_USER_ID", "222")
    monkeypatch.setattr(sns_safety, "insights_token", lambda: ("", "未接続(読むだけの鍵が未登録)"))
    monkeypatch.setattr(wr, "get", lambda *a, **k: pytest.fail("鍵が無いのに Meta を呼んだ"))
    assert "未接続" in wr.section_instagram()


def test_funnel_uses_header_not_url(monkeypatch):
    import funnel_deep_dive as fd
    monkeypatch.setenv("IG_USER_ID", "222")
    monkeypatch.setattr(sns_safety, "insights_token", lambda: (FAKE_TOKEN, "ok"))
    calls = []

    def fake_get(url, headers=None):
        calls.append((url, headers))
        if "/media?" in url:
            return {"data": [{"id": "m1", "caption": "c", "timestamp": "2026-11-01T00:00:00+0000"}]}
        if "/insights" in url:
            return {"data": [{"name": "reach", "values": [{"value": 5}]}]}
        return {"followers_count": 1, "media_count": 2}
    monkeypatch.setattr(fd, "get", fake_get)
    fd.ig_block()
    assert len(calls) >= 3 and all(FAKE_TOKEN not in u for u, _ in calls)


@pytest.mark.parametrize("name", ["weekly-report.yml", "funnel-deep-dive.yml"])
def test_report_workflows_have_no_publish_key(name):
    wf, text = _wf(name)
    assert "FB_PAGE_ACCESS_TOKEN" not in json.dumps(wf) and "META_INSIGHTS_TOKEN" in text


# ---------------------------------------------------------------- 投稿先の指紋は1つで定期・手動の両方に効く


def _mikata_env(fp, page="111", ig="222"):
    return {"SNS_DEST_FP_MIKATA": fp, "FB_PAGE_ID": page, "IG_USER_ID": ig}


def test_one_fingerprint_works_for_both_posting_paths(monkeypatch):
    """登録する指紋1つで、定期投稿(post_social)と手動投稿(ig_manual_post)の両方が通ること。"""
    import ig_manual_post as im
    import post_social as ps
    fp = sns_safety.destination_fingerprint("111", "222")
    for k, v in _mikata_env(fp).items():
        monkeypatch.setenv(k, v)
    sns_safety.check_mikata_destination()          # 両方の処理が呼ぶ照合
    for mod in (im, ps):
        src = open(mod.__file__, encoding="utf-8").read()
        assert "check_mikata_destination()" in src, mod.__name__
        assert "check_destination(" not in src.replace("check_mikata_destination(", ""), mod.__name__


@pytest.mark.parametrize("env,needle", [
    (_mikata_env(""), "未設定"),
    (_mikata_env(sns_safety.destination_fingerprint("111", "222"), page=""), "番号が未設定"),
    (_mikata_env(sns_safety.destination_fingerprint("111", "222"), ig="999"), "一致しません"),
    (_mikata_env(sns_safety.destination_fingerprint("222")), "一致しません"),   # 以前の手動投稿の作り方
])
def test_mikata_destination_blocks(env, needle):
    with pytest.raises(SafetyError, match=needle):
        sns_safety.check_mikata_destination(env)


def test_fingerprint_cli_matches_library():
    r = subprocess.run([sys.executable, os.path.join(SCRIPTS, "sns_safety.py"), "--fingerprint", "111", "222"],
                       capture_output=True, text=True)
    assert r.returncode == 0 and r.stdout.strip() == sns_safety.destination_fingerprint("111", "222")


@pytest.mark.parametrize("name", ["ig-feed.yml", "ig-story.yml"])
def test_manual_post_job_gets_page_id(name):
    wf, _ = _wf(name)
    blob = json.dumps(wf["jobs"]["post"])
    assert "secrets.FB_PAGE_ID" in blob and "SNS_DEST_FP_MIKATA" in blob


# ---------------------------------------------------------------- 実際の呼び出しの流れで、1つの指紋が3つの投稿経路すべてに効くこと
# 定期投稿(post_social.main)・手動フィード・手動ストーリーズ(ig_manual_post.main)を、
# 同じ環境変数(FB_PAGE_ID / IG_USER_ID / SNS_DEST_FP_MIKATA)のまま順に通す。Meta への通信は偽物。

PATHS = ("social", "feed", "story")
_ORIG_VERIFY = sns_safety.verify_before_publish   # 読み込み時点の本物(他のテストの差し替えを引き継がない)


@pytest.fixture
def all_paths(social, monkeypatch):
    """social fixture(定期投稿の準備・環境変数・偽の Meta)に、手動投稿の準備を足す。"""
    import ig_manual_post as im
    ps, root, social_calls = social
    img = root / "posts" / "manual.png"
    img.write_bytes(b"\x89PNG synthetic manual")
    cap = root / "cap.txt"
    cap.write_text("手動投稿の本文", encoding="utf-8")
    monkeypatch.setattr(im, "BASE", str(root))
    monkeypatch.setattr(im.time, "sleep", lambda s: None)
    manual_calls = []

    def fake_meta_post(path, params, **kw):
        manual_calls.append(path)
        return {"id": "c1"}
    monkeypatch.setattr(sns_safety, "meta_post", fake_meta_post)
    return ps, im, root, img, cap, social_calls, manual_calls


def _run_path(path, ps, im, root, img, cap, monkeypatch, capsys):
    """1つの投稿経路を「見本 → 承認後の投稿」の順で、本物の main() から動かす。戻り値: 投稿まで進んだか。"""
    if path == "social":
        out = _preview(ps, monkeypatch, capsys)
        _IMG[0] = (root / "posts" / "images" / "01_seido.png").read_bytes()
        try:
            _post(ps, monkeypatch, out["stem"], out["pkg_digest"], out["pkg_created"])
            return True
        except SystemExit:
            return False
    extra = ["--caption-file", str(cap)] if path == "feed" else []
    assert im.main(["--kind", path, "--image", "posts/manual.png", "--preview", *extra]) == 0
    out = dict(l.split("=", 1) for l in capsys.readouterr().out.splitlines() if "=" in l)
    monkeypatch.setattr(sns_safety, "verify_before_publish",
                        lambda p, d, **kw: _ORIG_VERIFY(p, d, fetch=lambda u: img.read_bytes()))
    return im.main(["--kind", path, "--image", "posts/manual.png", *extra, "--post",
                    "--approved-digest", out["pkg_digest"], "--approved-created", out["pkg_created"]]) == 0


def test_one_fp_passes_all_three_real_paths(all_paths, monkeypatch, capsys):
    ps, im, root, img, cap, social_calls, manual_calls = all_paths
    fp = sns_safety.destination_fingerprint("111", "222")
    monkeypatch.setenv("SNS_DEST_FP_MIKATA", fp)      # 3経路とも同じ1つの値
    results = {p: _run_path(p, ps, im, root, img, cap, monkeypatch, capsys) for p in PATHS}
    assert results == {"social": True, "feed": True, "story": True}, results
    assert social_calls == ["/111/photos", "/222/media", "/222/media_publish"]
    assert manual_calls == ["/222/media", "/222/media_publish"] * 2   # フィード・ストーリーズ


@pytest.mark.parametrize("case", ["id_mismatch", "fp_unset", "old_format_fp", "page_id_missing"])
@pytest.mark.parametrize("path", PATHS)
def test_bad_destination_stops_before_publish(all_paths, monkeypatch, capsys, case, path):
    """投稿先が合わないときは、本物の main() の流れで、Meta を1回も呼ばずに止まること。"""
    ps, im, root, img, cap, social_calls, manual_calls = all_paths
    good = sns_safety.destination_fingerprint("111", "222")
    if case == "id_mismatch":
        monkeypatch.setenv("SNS_DEST_FP_MIKATA", good)
        monkeypatch.setenv("IG_USER_ID", "999")                     # 別のアカウントにすり替わった
    elif case == "fp_unset":
        monkeypatch.setenv("SNS_DEST_FP_MIKATA", "")
    elif case == "old_format_fp":
        monkeypatch.setenv("SNS_DEST_FP_MIKATA", sns_safety.destination_fingerprint("222"))  # 以前の手動投稿の作り方
    elif case == "page_id_missing":
        monkeypatch.setenv("SNS_DEST_FP_MIKATA", good)
        monkeypatch.setenv("FB_PAGE_ID", "")
    assert _run_path(path, ps, im, root, img, cap, monkeypatch, capsys) is False
    assert social_calls == [] and manual_calls == []


@pytest.mark.parametrize("name,script", [
    ("social-post.yml", "post_social.py"),
    ("ig-feed.yml", "ig_manual_post.py"),
    ("ig-story.yml", "ig_manual_post.py"),
])
def test_workflow_passes_ids_to_the_posting_step(name, script):
    """承認付きの投稿ジョブの「投稿スクリプトを動かす手順」に、照合に使う3つが正しい出どころから渡ること。"""
    wf, _ = _wf(name)
    job = wf["jobs"]["post"]
    assert job.get("environment") == "sns-approval"
    assert job.get("if") == "github.ref == 'refs/heads/main'"
    steps = [s for s in job["steps"] if script in (s.get("run") or "") and "--preview" not in s.get("run", "")]
    assert len(steps) == 1, steps
    env = steps[0].get("env") or {}
    assert env.get("FB_PAGE_ID") == "${{ secrets.FB_PAGE_ID }}"
    assert env.get("IG_USER_ID") == "${{ secrets.IG_USER_ID }}"
    assert env.get("SNS_DEST_FP_MIKATA") == "${{ vars.SNS_DEST_FP_MIKATA }}"
    # 見本のジョブには投稿用の鍵も番号も渡さない
    for jn, j in wf["jobs"].items():
        if jn != "post":
            assert "FB_PAGE_ACCESS_TOKEN" not in json.dumps(j), jn
