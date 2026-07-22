#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hojo-hq 検証部(ケンショウくん)/監査(タダスくん) — 日次ヘルスチェック
公開中のサイトとデータを毎日自動で叩き、バグ・表示崩れ・データ異常を検知する。
GitHub Actions で毎日実行し、ERROR を1件でも検知したら異常終了(→Issue自動起票)。

チェック項目:
  [表示]   トップが 200 で表示されるか、ロゴを参照し画像が読めるか
  [データ] subsidies.json の JSON妥当性・件数・重複ID・必須項目・締切の整合
  [鮮度]   updated_at が STALE_HOURS 以内か(CLAUDE.md: 更新遅延24時間以内)
  [KPI]    掲載件数が KPI_TARGET 以上か(未達は WARNING、失敗にはしない)

ERROR = 失敗(exit 1) / WARNING = 記録のみ(exit 0)。レポートは標準出力と
healthcheck_report.txt に出力する。
"""
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone, timedelta

try:  # Windowsコンソール等でも絵文字を出力できるようUTF-8に固定
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

JST = timezone(timedelta(hours=9))
BASE = os.environ.get("SITE_BASE", "https://allgroup-inc.github.io/hojo-hq").rstrip("/")
STALE_HOURS = int(os.environ.get("STALE_HOURS", "30"))     # これを超えたら更新停止とみなし ERROR
MIN_COUNT = int(os.environ.get("MIN_COUNT", "50"))          # これ未満は収集破損とみなし ERROR
KPI_TARGET = int(os.environ.get("KPI_TARGET", "150"))       # 未達は WARNING
REPORT_PATH = os.path.join(os.path.dirname(__file__), "..", "healthcheck_report.txt")

UA = "hojo-hq-healthcheck/1.0 (+https://allgroup-inc.github.io/hojo-hq)"
REQUIRED_FIELDS = ("id", "name", "deadline", "source_url", "status", "tag")

errors: list[str] = []
warnings: list[str] = []
notes: list[str] = []


def cache_bust(url: str) -> str:
    sep = "&" if "?" in url else "?"
    stamp = datetime.now(JST).strftime("%Y%m%d%H%M%S")
    return f"{url}{sep}_cb={stamp}"


def fetch(url: str, binary: bool = False):
    """(status, headers, body) を返す。失敗時は status=None。"""
    req = urllib.request.Request(cache_bust(url), headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as res:
            body = res.read()
            return res.status, dict(res.headers), (body if binary else body.decode("utf-8", "replace"))
    except Exception as e:
        return None, {}, str(e)


def check_page(path: str, label: str, must_contain=None):
    url = BASE + path
    status, _, body = fetch(url)
    if status != 200:
        errors.append(f"[表示] {label} が取得できません ({url}) — status={status} {body[:120]}")
        return None
    notes.append(f"[表示] {label} OK (200, {len(body)} bytes)")
    if must_contain:
        for token in must_contain:
            if token not in body:
                errors.append(f"[表示] {label} に想定要素 '{token}' が見当たりません ({url})")
    return body


def check_links(index_html: str | None):
    """E2Eスモーク: index.html 内の全リンク(href/src, lin.ee等の外部含む)が生きているか。"""
    import re as _re
    import urllib.parse as _up
    if index_html is None:
        return
    # preconnect はオリジンへの事前接続でありリソースではない → 対象外
    scan_html = _re.sub(r'<link[^>]*rel="preconnect"[^>]*>', "", index_html)
    urls = set()
    for m in _re.finditer(r'(?:href|src)="([^"]+)"', scan_html):
        u = m.group(1)
        if u.startswith(("mailto:", "tel:", "javascript:", "data:")):
            continue
        if u == "#" or u.startswith("#"):
            continue  # ページ内アンカーは placeholder 検知側で扱う
        if "${" in u:
            continue  # JSテンプレートリテラル(実URLではない)
        urls.add(_up.urljoin(BASE + "/", u))
    ok = 0
    for u in sorted(urls):
        req = urllib.request.Request(u, headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=30) as res:
                st = res.status
        except urllib.error.HTTPError as e:
            st = e.code
        except Exception as e:
            errors.append(f"[リンク] 取得失敗: {u} — {e}")
            continue
        if st >= 400:
            errors.append(f"[リンク] HTTP {st}: {u}")
        else:
            ok += 1
    notes.append(f"[リンク] {ok}/{len(urls)} 件 OK(リダイレクト追跡後 <400)")


def check_placeholders(index_html: str | None):
    """E2Eスモーク: 開発用プレースホルダや空リンクが本番に残っていないか。"""
    if index_html is None:
        return
    found = []
    for token in ("LINE_URL_PLACEHOLDER", 'href="#"', "TODO", "FIXME"):
        if token in index_html:
            found.append(token)
    if found:
        errors.append(f"[残存] 本番HTMLに開発用の残存物: {', '.join(found)}")
    else:
        notes.append("[残存] PLACEHOLDER / href=\"#\" なし")


def check_js_syntax(index_html: str | None):
    """E2Eスモーク: index.html のインラインJSが構文エラーでないか(node --check)。"""
    import re as _re
    import shutil
    import subprocess
    import tempfile
    if index_html is None:
        return
    node = shutil.which("node")
    if not node:
        warnings.append("[JS] node が無いため構文チェックをスキップしました")
        return
    scripts = _re.findall(r"<script[^>]*>(.*?)</script>", index_html, _re.S)
    inline = [s for s in scripts if s.strip()]
    for i, src in enumerate(inline, 1):
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as tf:
            tf.write(src)
            tmp = tf.name
        try:
            r = subprocess.run([node, "--check", tmp], capture_output=True, text=True, timeout=30)
            if r.returncode != 0:
                msg = (r.stderr or r.stdout).strip().splitlines()
                errors.append(f"[JS] インラインscript#{i} 構文エラー: {msg[0] if msg else 'unknown'}")
            else:
                notes.append(f"[JS] インラインscript#{i} 構文OK")
        finally:
            os.unlink(tmp)


def check_logo(index_html: str | None):
    # index.html がロゴを参照しているか
    ref = "assets/glow-logo.png"
    if index_html is not None and ref not in index_html:
        warnings.append(f"[表示] index.html がロゴ({ref})を参照していません(意図的なら無視可)")
    status, headers, body = fetch(BASE + "/assets/glow-logo.png", binary=True)
    if status != 200:
        errors.append(f"[表示] ロゴ画像が読み込めません(画像切れ) — status={status}")
        return
    ctype = headers.get("Content-Type", "")
    if "image" not in ctype:
        errors.append(f"[表示] ロゴのContent-Typeが画像ではありません: {ctype}")
    if not body.startswith(b"\x89PNG\r\n\x1a\n"):
        errors.append("[表示] ロゴPNGの署名が不正です(壊れた画像の可能性)")
    else:
        notes.append(f"[表示] ロゴ OK (200, {ctype}, {len(body)} bytes)")


def check_data():
    url = BASE + "/data/subsidies.json"
    status, _, body = fetch(url)
    if status != 200:
        errors.append(f"[データ] subsidies.json が取得できません — status={status}")
        return
    try:
        data = json.loads(body)
    except Exception as e:
        errors.append(f"[データ] subsidies.json が壊れています(JSONパース失敗): {e}")
        return

    items = data.get("items")
    if not isinstance(items, list):
        errors.append("[データ] items が配列ではありません")
        return

    count = data.get("count")
    if count != len(items):
        errors.append(f"[データ] count({count}) と items数({len(items)}) が不一致")

    n = len(items)
    if n < MIN_COUNT:
        errors.append(f"[データ] 掲載件数が異常に少ない: {n}件 (<{MIN_COUNT}) — 収集破損の疑い")
    elif n < KPI_TARGET:
        warnings.append(f"[KPI] 掲載件数 {n}件 が目標{KPI_TARGET}件を下回っています")
    notes.append(f"[データ] 件数 {n}件")

    # 重複ID
    ids = [it.get("id") for it in items]
    dup = {i for i in ids if i and ids.count(i) > 1}
    if dup:
        errors.append(f"[データ] IDが重複しています: {list(dup)[:5]}{'...' if len(dup) > 5 else ''}")

    # 必須項目の欠落
    missing_field = 0
    for it in items:
        for f in REQUIRED_FIELDS:
            if not it.get(f):
                missing_field += 1
                break
    if missing_field:
        errors.append(f"[データ] 必須項目が欠けている項目が {missing_field}件")

    # 募集中なのに締切が過去(期限切れを募集中表示 = バグ)
    today = datetime.now(JST).date()
    expired_active = []
    for it in items:
        if it.get("status") == "募集中":
            dl = it.get("deadline")
            try:
                d = datetime.strptime(dl, "%Y-%m-%d").date()
            except Exception:
                continue  # 要確認 等はスキップ
            if d < today:
                expired_active.append((it.get("name", "")[:30], dl))
    if expired_active:
        errors.append(
            f"[データ] 締切切れを「募集中」表示している項目が {len(expired_active)}件 "
            f"(例: {expired_active[0][0]} / {expired_active[0][1]})"
        )

    # 鮮度
    ua = data.get("updated_at")
    try:
        upd = datetime.strptime(ua, "%Y-%m-%d %H:%M").replace(tzinfo=JST)
        age_h = (datetime.now(JST) - upd).total_seconds() / 3600
        if age_h > STALE_HOURS:
            errors.append(f"[鮮度] データが古い: 最終更新 {ua}({age_h:.1f}時間前 > {STALE_HOURS}h)— 更新停止の疑い")
        else:
            notes.append(f"[鮮度] 最終更新 {ua}({age_h:.1f}時間前)OK")
    except Exception:
        warnings.append(f"[鮮度] updated_at を解釈できません: {ua!r}")


def main():
    ts = datetime.now(JST).strftime("%Y-%m-%d %H:%M JST")
    idx = check_page("/", "トップページ", must_contain=["<", "subsidies"])
    check_logo(idx)
    check_links(idx)
    check_placeholders(idx)
    check_js_syntax(idx)
    check_data()

    lines = [f"# hojo-hq 日次ヘルスチェック  {ts}", f"対象: {BASE}", ""]
    lines.append(f"結果: {'❌ 異常あり' if errors else '✅ 正常'}  "
                 f"(ERROR {len(errors)} / WARNING {len(warnings)})")
    lines.append("")
    if errors:
        lines.append("## ❌ ERROR(要対応)")
        lines += [f"- {e}" for e in errors]
        lines.append("")
    if warnings:
        lines.append("## ⚠️ WARNING")
        lines += [f"- {w}" for w in warnings]
        lines.append("")
    lines.append("## ✓ 確認できた項目")
    lines += [f"- {n}" for n in notes]
    report = "\n".join(lines)

    print(report)
    try:
        with open(REPORT_PATH, "w", encoding="utf-8") as f:
            f.write(report + "\n")
    except Exception:
        pass

    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
