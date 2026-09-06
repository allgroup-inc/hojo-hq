#!/usr/bin/env python3
"""もらいわすれ堂 Instagram(@moradou.okinawa)常時チェック。

Instagram Graph API(Meta公式)で投稿一覧とプロフィールを取得し、
出荷ゲートと同じ禁止表現・IG運用v2のルール(タグ5個以内 等)で機械検査する。
GitHub Actions(.github/workflows/ig-check.yml)から毎日実行され、
違反・投稿停滞・トークン失効を検知すると Issue で通知される。

必要なSecrets(未設定の間は「設定待ち」を表示して正常終了する):
  IG_ACCESS_TOKEN  Meta長期アクセストークン(約60日で失効。再発行手順は
                   docs/人間タスク_IG常時チェック_トークン設定.md)
  IG_USER_ID       InstagramビジネスアカウントのユーザーID(数字)

保存するのは IG 上で誰でも見られる公開情報のみ(投稿・キャプション・公開カウント)。
インサイト系の内部数値は公開リポジトリに保存しない(議事_20260906_IG常時チェック体制.md)。

使い方:
  python3 scripts/ig_check.py            # 取得+検査。違反があれば exit 1
  python3 scripts/ig_check.py --selftest # API を呼ばず検査ロジックだけ確認
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from shipping_gate import FORBIDDEN  # 禁止表現は出荷ゲートと単一ソース

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_PATH = REPO_ROOT / "data" / "fukugiiro" / "ig_check_report.json"
GRAPH = "https://graph.facebook.com/v21.0"
HASHTAG_LIMIT = 5          # IG運用v2: タグは5個以内(6個以上は無効化される)
STALE_DAYS = 14            # 最新投稿からこの日数を超えたら「更新停滞」警告
MEDIA_LIMIT = 25


def _get(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def fetch(token: str, user_id: str) -> tuple[dict, list[dict]]:
    prof_fields = "username,media_count,followers_count,biography,website"
    prof = _get(f"{GRAPH}/{user_id}?fields={prof_fields}&access_token={token}")
    media_fields = ("id,caption,media_type,media_product_type,permalink,"
                    "timestamp,like_count,comments_count")
    media = _get(f"{GRAPH}/{user_id}/media?fields={media_fields}"
                 f"&limit={MEDIA_LIMIT}&access_token={token}").get("data", [])
    return prof, media


def check_caption(caption: str) -> tuple[list[str], list[str]]:
    """(violations, warnings) を返す。violationsは出荷ゲート相当のNG。"""
    violations, warnings = [], []
    for pat, reason in FORBIDDEN:
        if re.search(pat, caption):
            violations.append(f"禁止表現({reason.splitlines()[0]})")
    tags = re.findall(r"#[^\s#]+", caption)
    if len(tags) > HASHTAG_LIMIT:
        violations.append(f"ハッシュタグ{len(tags)}個(IG運用v2の上限は{HASHTAG_LIMIT}個。超過分は無効化される)")
    if re.search(r"\d+\s*万\s*円|\d+\s*円", caption) and "要確認" not in caption and "公式" not in caption:
        warnings.append("金額表現があるのに『要確認/公式ページ』の添えがない")
    if "プロフィール" not in caption and "リンク" not in caption:
        warnings.append("プロフィールリンクへの誘導文がない(導線切れの可能性)")
    return violations, warnings


def run_checks(prof: dict, media: list[dict]) -> dict:
    posts, n_viol = [], 0
    for m in media:
        v, w = check_caption(m.get("caption") or "")
        n_viol += len(v)
        posts.append({
            "id": m.get("id"),
            "permalink": m.get("permalink"),
            "timestamp": m.get("timestamp"),
            "media_type": m.get("media_product_type") or m.get("media_type"),
            "like_count": m.get("like_count"),
            "comments_count": m.get("comments_count"),
            "caption_head": (m.get("caption") or "")[:80],
            "violations": v,
            "warnings": w,
        })
    warnings_global = []
    if media:
        latest = media[0].get("timestamp", "")
        try:
            latest_dt = datetime.fromisoformat(latest.replace("+0000", "+00:00"))
            days = (datetime.now(timezone.utc) - latest_dt).days
            if days > STALE_DAYS:
                warnings_global.append(f"最新投稿から{days}日経過(更新停滞。{STALE_DAYS}日を超えています)")
        except ValueError:
            pass
    else:
        warnings_global.append("投稿が取得できませんでした(0件)")
    if not (prof.get("website") or "").strip():
        warnings_global.append("プロフィールのリンク(website)が未設定。動画・キャプションの導線が切れます")
    return {
        "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "account": {k: prof.get(k) for k in
                    ("username", "media_count", "followers_count", "website")},
        "violations_total": n_viol,
        "warnings_global": warnings_global,
        "posts": posts,
    }


def print_report(report: dict) -> None:
    acc = report["account"]
    print(f"## IG常時チェック {report['checked_at']}")
    print(f"アカウント: @{acc.get('username')} / 投稿{acc.get('media_count')}件 / "
          f"フォロワー{acc.get('followers_count')} / リンク: {acc.get('website') or '未設定'}")
    for w in report["warnings_global"]:
        print(f"⚠ {w}")
    for p in report["posts"]:
        mark = "✗" if p["violations"] else ("⚠" if p["warnings"] else "✓")
        print(f"{mark} {p['timestamp']} {p['media_type']} {p['permalink']}")
        for v in p["violations"]:
            print(f"   ✗ {v}")
        for w in p["warnings"]:
            print(f"   ⚠ {w}")
    print(f"違反合計: {report['violations_total']}")


def selftest() -> int:
    ok = True
    v, _ = check_caption("必ずもらえます!締切7日前にお知らせ https://lin.ee/x #a #b #c #d #e #f")
    ok &= len(v) >= 4
    v2, w2 = check_caption("児童手当が広がりました。診断はプロフィールのリンクから。※最終判断は各窓口で行われます")
    ok &= not v2 and not w2
    print("selftest:", "OK" if ok else f"NG (v={v}, v2={v2}, w2={w2})")
    return 0 if ok else 1


def main() -> int:
    if "--selftest" in sys.argv:
        return selftest()
    token, user_id = os.environ.get("IG_ACCESS_TOKEN", ""), os.environ.get("IG_USER_ID", "")
    if not token or not user_id:
        print("IG_ACCESS_TOKEN / IG_USER_ID が未設定です(設定待ちのため正常終了)。")
        print("設定手順: docs/人間タスク_IG常時チェック_トークン設定.md")
        return 0
    try:
        prof, media = fetch(token, user_id)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:300]
        print(f"::error::Graph API エラー HTTP {e.code}: {body}")
        if e.code in (400, 401, 403):
            print("::error::トークン期限切れ(約60日)の可能性。再発行手順: "
                  "docs/人間タスク_IG常時チェック_トークン設定.md")
        return 2
    report = run_checks(prof, media)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print_report(report)
    return 1 if report["violations_total"] else 0


if __name__ == "__main__":
    sys.exit(main())
