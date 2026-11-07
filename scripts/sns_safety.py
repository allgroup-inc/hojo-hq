#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SNS投稿の安全部品(GLOW Instagram 安全対策 M1・M2・鍵の漏えい防止)。

標準ライブラリのみ。投稿スクリプト(post_social.py / ig_manual_post.py)から使う。

1. 承認対象の固定(M1)
   本文・画像の中身の指紋(sha256)・画像の固定URL(コミットに固定)・投稿先の種別・
   作成時点のコミット・作成日時・有効期限をひとまとめにし、その指紋(digest)を承認対象にする。
   投稿の直前に作り直して照らし合わせ、画像は固定URLから取り直して指紋を確かめる。
   1つでも違えば投稿しない(フェイルクローズ)。
2. 制度情報の確認(M2)
   投稿の出典にある制度が、原文照合から72時間以内(暫定値)で、
   公募要領・募集状況・締切の3点が原文と一致していることを確かめる。
   確かめられないものは「要確認」と書いて出すのではなく、投稿しない。
3. 鍵を出力しない
   Meta の返事やエラーをそのまま出さない(鍵や内部情報が混ざり得るため)。
   出してよいのは HTTP ステータスと Meta のエラー番号・種別だけ。
"""
import hashlib
import json
import os
import re
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))
REPO = "allgroup-inc/hojo-hq"
PACKAGE_VERSION = 1
PACKAGE_TTL_HOURS = 48          # 承認待ちの有効期限(次の定期回が古い承認待ちを打ち切る間隔に合わせる)
SEIDO_MAX_AGE_HOURS = 72        # 原文照合の有効期間(暫定値・2026-11-03 方針)
OWN_SITE_PREFIX = "https://allgroup-inc.github.io/hojo-hq/"
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


class SafetyError(Exception):
    """投稿を止める理由。メッセージに鍵や Meta の返事の本文を入れないこと。"""


# ---------------------------------------------------------------- 鍵を出さない

_REDACT_PATTERNS = [
    (re.compile(r"(access_token=)[^&\s\"']+", re.I), r"\1***"),
    (re.compile(r"(\"access_token\"\s*:\s*\")[^\"]+", re.I), r"\1***"),
    (re.compile(r"(Bearer\s+)[A-Za-z0-9._~+/=-]+", re.I), r"\1***"),
    (re.compile(r"\bEAA[A-Za-z0-9]{20,}"), "***"),        # Meta のアクセストークンの形
    (re.compile(r"(appsecret_proof=)[^&\s\"']+", re.I), r"\1***"),
]


def redact(text):
    """鍵の形をした部分を *** に置き換える。最後の安全網であり、これに頼って
    返事をそのまま出してよいという意味ではない。"""
    s = "" if text is None else str(text)
    for pat, rep in _REDACT_PATTERNS:
        s = pat.sub(rep, s)
    return s


def meta_error_summary(exc):
    """Meta API の失敗を、安全に出せる要約(HTTP ステータス・エラー番号・種別)にする。
    返事の本文・メッセージ文・URL は出さない(鍵や投稿先の番号が混ざり得るため)。"""
    if isinstance(exc, urllib.error.HTTPError):
        parts = [f"HTTP {exc.code}"]
        try:
            body = json.loads(exc.read().decode("utf-8", "replace"))
            err = body.get("error") or {}
            for key in ("type", "code", "error_subcode"):
                val = err.get(key)
                if isinstance(val, (int, str)) and re.fullmatch(r"[A-Za-z0-9_]{1,40}", str(val)):
                    parts.append(f"{key}={val}")
        except Exception:  # noqa: BLE001 返事が読めなくても、ステータスだけは出す
            pass
        return " ".join(parts)
    if isinstance(exc, urllib.error.URLError):
        return "通信エラー(URLError)"
    return f"{type(exc).__name__}"


def meta_post(path, params, graph="https://graph.facebook.com/v21.0", opener=None, timeout=60):
    """Meta Graph API へ POST する。鍵は本文(POST の中身)にだけ入れ、URL には入れない。
    失敗したら、要約だけを持つ SafetyError にする(返事の本文は出さない)。"""
    import urllib.parse
    data = urllib.parse.urlencode(params).encode("utf-8")
    req = urllib.request.Request(graph + path, data=data, method="POST")
    open_fn = opener or urllib.request.urlopen
    try:
        with open_fn(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except SafetyError:
        raise
    except Exception as e:  # noqa: BLE001
        raise SafetyError(f"Meta API の呼び出しに失敗しました({meta_error_summary(e)})") from None


# ---------------------------------------------------------------- 数字を読むだけの鍵

# 週次レポート・分析は Meta から数字を読むだけ。投稿できる鍵を使わず、読むだけの権限で
# 作った鍵(META_INSIGHTS_TOKEN)を使う(2026-11-03 設計)。使う前に権限を Meta に問い合わせ(/me/permissions)、
# 投稿・管理の権限が付いていたら使わない。確かめられないときも使わない(フェイルクローズ)。
INSIGHTS_ENV = "META_INSIGHTS_TOKEN"
FORBIDDEN_SCOPES = frozenset({
    "instagram_content_publish", "pages_manage_posts", "pages_manage_engagement",
    "pages_manage_metadata", "instagram_manage_comments", "instagram_manage_messages",
    "pages_messaging", "publish_video", "business_management",
})
_INSIGHTS_CACHE = {}


def auth_headers(token):
    """鍵は URL ではなく通信の付属情報(Authorization)で渡す。"""
    return {"Authorization": f"Bearer {token}"}


def check_read_only_scopes(scopes):
    """権限の一覧から、投稿・管理の権限を含むかを調べ、含むものの一覧を返す(空なら読むだけ)。"""
    return sorted(set(scopes or []) & FORBIDDEN_SCOPES)


def insights_token(env=None, opener=None, graph="https://graph.facebook.com/v21.0"):
    """数字を読むだけの鍵を返す。(token, 理由) の組。token が空なら使えない(理由を表示する)。

    投稿用の鍵(FB_PAGE_ACCESS_TOKEN)へは決して切り替えない。"""
    env = os.environ if env is None else env
    token = (env.get(INSIGHTS_ENV) or "").strip()
    if not token:
        return "", "未接続(読むだけの鍵が未登録)"
    if token in _INSIGHTS_CACHE:
        return _INSIGHTS_CACHE[token]
    # 権限は鍵の持ち主が自分で見られる /me/permissions で確かめる(2026-11-07 変更)。
    # 以前の debug_token はアプリの開発者かアプリ用の鍵でないと呼べず、最小限の権限の
    # システムユーザーの鍵では Meta に断られた(HTTP 400 / code 100)。この方法なら鍵を URL に載せない。
    req = urllib.request.Request(f"{graph}/me/permissions", headers=auth_headers(token))
    open_fn = opener or urllib.request.urlopen
    try:
        with open_fn(req, timeout=30) as r:
            rows = (json.loads(r.read().decode("utf-8")) or {}).get("data")
    except Exception as e:  # noqa: BLE001
        result = ("", f"鍵の権限を確認できないため使いません({meta_error_summary(e)})")
        _INSIGHTS_CACHE[token] = result
        return result
    if not isinstance(rows, list) or not rows:
        result = ("", "鍵の権限の一覧が空のため使いません(確かめられない)")
    else:
        granted = [str(x.get("permission", "")) for x in rows
                   if isinstance(x, dict) and x.get("status") == "granted"]
        bad = check_read_only_scopes(granted)
        if bad:
            result = ("", "鍵に投稿・管理の権限が付いているため使いません: " + ", ".join(bad))
        elif not granted:
            result = ("", "鍵に有効な権限が1つもないため使いません")
        else:
            result = (token, "ok")
    _INSIGHTS_CACHE[token] = result
    return result


# ---------------------------------------------------------------- 指紋と固定URL

def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def sha256_file(path):
    with open(path, "rb") as f:
        return sha256_bytes(f.read())


def pinned_raw_url(sha, relpath):
    """コミットに固定した画像の場所。main の URL は投稿までに中身が変わり得るため使わない。"""
    if not _SHA_RE.match(sha or ""):
        raise SafetyError("画像を固定するコミット番号を確定できません(GITHUB_SHA が無い・形が違う)")
    rel = relpath.replace("\\", "/").lstrip("/")
    if ".." in rel.split("/"):
        raise SafetyError("画像の場所が不正です(..を含む)")
    return f"https://raw.githubusercontent.com/{REPO}/{sha}/{rel}"


def destination_fingerprint(*ids):
    """投稿先(ページ番号・アカウント番号)の指紋。番号そのものはログに出さない。"""
    joined = "|".join(str(i or "") for i in ids)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:16]


def check_destination(expected_fp, *ids):
    """投稿先が想定どおりか確かめる。想定の指紋が未設定なら投稿しない(フェイルクローズ)。"""
    if not all(ids):
        raise SafetyError("投稿先の番号が未設定です")
    if not expected_fp:
        raise SafetyError("投稿先の照合用の指紋が未設定です(投稿先を確かめられないため投稿しません)")
    if destination_fingerprint(*ids) != expected_fp.strip().lower():
        raise SafetyError("投稿先が承認時の想定と一致しません")


MIKATA_DEST_ENV = "SNS_DEST_FP_MIKATA"


def check_mikata_destination(env=None):
    """ミカタの投稿先を確かめる。定期投稿・手動投稿のどちらも、同じ材料
    (Facebook ページの番号 + Instagram の番号)で指紋を作って SNS_DEST_FP_MIKATA と照らし合わせる。
    材料を処理ごとに変えると、1つの登録値で両方を満たせなくなる(2026-11-04 に検出)。"""
    env = os.environ if env is None else env
    check_destination(env.get(MIKATA_DEST_ENV, ""), env.get("FB_PAGE_ID", ""), env.get("IG_USER_ID", ""))


# ---------------------------------------------------------------- 承認対象(M1)

def build_package(*, account, kind, caption, images, sha, base_dir, created_at=None,
                  ttl_hours=PACKAGE_TTL_HOURS, stem=None):
    """承認対象をひとまとめにする。images はリポジトリ内の相対パスの並び。"""
    if not caption or not caption.strip():
        raise SafetyError("本文が空です")
    if not images:
        raise SafetyError("画像がありません")
    created = created_at or datetime.now(JST)
    imgs = []
    for rel in images:
        p = os.path.join(base_dir, rel)
        if not os.path.isfile(p):
            raise SafetyError(f"画像が見つかりません: {rel}")
        imgs.append({"path": rel, "sha256": sha256_file(p), "url": pinned_raw_url(sha, rel)})
    return {
        "version": PACKAGE_VERSION,
        "account": account,
        "kind": kind,
        "stem": stem,
        "caption_sha256": sha256_bytes(caption.encode("utf-8")),
        "images": imgs,
        "commit": sha,
        "created_at": created.isoformat(timespec="seconds"),
        "expires_at": (created + timedelta(hours=ttl_hours)).isoformat(timespec="seconds"),
    }


def package_digest(pkg):
    """承認対象の指紋。キーの順序に左右されないよう整列して計算する。"""
    blob = json.dumps(pkg, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256_bytes(blob.encode("utf-8"))


def _default_fetch(url, timeout=30):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return r.read()


def verify_before_publish(pkg, approved_digest, *, now=None, fetch=_default_fetch):
    """投稿の直前に照らし合わせる。問題があれば SafetyError(投稿しない)。

    - 作り直した承認対象の指紋が、承認されたものと同じか(本文・画像・投稿先の種別・コミット)
    - 期限内か
    - 固定URLから取り直した画像の指紋が、承認時と同じか(Meta が取りに行く画像と同じものか)
    """
    if not approved_digest or not re.fullmatch(r"[0-9a-f]{64}", approved_digest.strip()):
        raise SafetyError("承認された指紋が渡されていません(承認対象を確定できないため投稿しません)")
    if package_digest(pkg) != approved_digest.strip():
        raise SafetyError("承認された中身と、いま投稿しようとしている中身が一致しません")
    now = now or datetime.now(JST)
    try:
        expires = datetime.fromisoformat(pkg["expires_at"])
    except Exception:  # noqa: BLE001
        raise SafetyError("承認対象の有効期限を読めません") from None
    if now > expires:
        raise SafetyError("承認対象の有効期限が切れています(作り直して承認し直してください)")
    for img in pkg["images"]:
        try:
            data = fetch(img["url"])
        except Exception as e:  # noqa: BLE001
            raise SafetyError(f"固定URLの画像を取得できません({meta_error_summary(e)}): {img['path']}") from None
        if sha256_bytes(data) != img["sha256"]:
            raise SafetyError(f"固定URLの画像が承認時と一致しません: {img['path']}")


def preview_lines(pkg, digest, caption):
    """見本通知・承認画面のログに出す内容(鍵と投稿先の番号は含めない)。"""
    lines = [
        f"投稿先: {pkg['account']}({pkg['kind']})",
        f"承認対象の指紋: {digest[:12]}",
        f"コミット: {pkg['commit'][:12]}",
        f"有効期限: {pkg['expires_at']}",
    ]
    for img in pkg["images"]:
        lines.append(f"画像: {img['path']}(指紋 {img['sha256'][:12]})")
    lines.append("本文:")
    lines.append(caption)
    return lines


# ---------------------------------------------------------------- 制度情報の確認(M2)

def extract_sources(md_text):
    """投稿原稿の「## 出典」欄の URL を取り出す。"""
    m = re.search(r"^## 出典\n(.*?)(?=^## |\Z)", md_text, re.S | re.M)
    if not m:
        return []
    return re.findall(r"https?://[^\s)>\]]+", m.group(1))


def _parse_ts(ts):
    if not ts:
        return None
    try:
        t = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=JST)


def check_seido(md_text, subsidies, *, now=None, max_age_hours=SEIDO_MAX_AGE_HOURS):
    """投稿の出典にある制度がすべて確認済みかを調べ、問題の一覧を返す(空なら投稿可)。

    確認済みの条件(すべて必要):
      - 出典の制度が掲載データにある
      - 原文の照合から max_age_hours 以内
      - 公募要領: 原文を取得でき、AI の照合が一致(食い違い・判定不能は不可)
      - 募集状況: 原文と一致(details.status_match が True)
      - 締切: 原文と一致(details.deadline_match が True)かつ、まだ過ぎていない
    いまの照合ツールは募集状況を確かめていないため、status_match が無いものは止まる。
    """
    now = now or datetime.now(JST)
    srcs = [u for u in extract_sources(md_text) if not u.startswith(OWN_SITE_PREFIX)]
    if not srcs:
        return []  # 制度を紹介しない投稿(自サイトの案内など)
    by_url = {}
    for s in subsidies:
        u = (s.get("source_url") or "").strip()
        if u:
            by_url[u] = s
    problems = []
    for url in srcs:
        s = by_url.get(url)
        label = url.rsplit("/", 1)[-1][:24]
        if not s:
            problems.append(f"[{label}] 出典の制度が掲載データに見つかりません")
            continue
        v = s.get("verified") or {}
        d = v.get("details") or {}
        ts = _parse_ts(v.get("timestamp"))
        if not v:
            problems.append(f"[{label}] 原文の照合記録がありません")
            continue
        if ts is None:
            problems.append(f"[{label}] 照合日時を読めません")
        elif now - ts > timedelta(hours=max_age_hours):
            problems.append(f"[{label}] 原文の照合から{max_age_hours}時間を超えています")
        if d.get("source_reachable") is not True:
            problems.append(f"[{label}] 公募要領(原文)を取得できていません")
        if v.get("conflict"):
            problems.append(f"[{label}] AI同士の照合が食い違っています(人の確認が必要)")
        if v.get("claude_verified") is not True or v.get("gemini_verified") is False:
            problems.append(f"[{label}] 公募要領との照合が一致していません")
        if d.get("status_match") is not True:
            problems.append(f"[{label}] 募集状況を原文で確認できていません")
        if d.get("deadline_match") is not True:
            problems.append(f"[{label}] 締切を原文で確認できていません")
        dl = s.get("deadline")
        try:
            if dl and datetime.fromisoformat(str(dl)[:10]).date() < now.date():
                problems.append(f"[{label}] 締切を過ぎています")
        except ValueError:
            problems.append(f"[{label}] 締切の日付を読めません")
        if s.get("status") != "募集中":
            problems.append(f"[{label}] 掲載データの募集状況が「募集中」ではありません")
    return problems


ORG_SUFFIX = re.compile(
    r"(省|庁|府|県|都|道|市|町|村|局|機構|財団|協会|公社|センター|会議所|連合会|組合|委員会|法人|事務局|本部|事務所)"
    r"([（(].*[)）])?$")


def issuer_label(issuer):
    """「実施主体」に出してよい値か。組織名の形でなければ「要確認」にする。
    jGrants 由来のデータでは、実施主体の欄に事業名が入っていることがある(2026-11-02 の投稿で確認)。"""
    s = (issuer or "").strip()
    if not s or len(s) > 40:
        return "要確認"
    return s if ORG_SUFFIX.search(s) else "要確認"


def _selftest():
    assert redact("a?access_token=EAAB123&x=1") == "a?access_token=***&x=1"
    assert "EAA" not in redact("tok EAAG" + "x" * 30)
    assert issuer_label("経済産業省") == "経済産業省"
    assert issuer_label("建築物等のZEB化・省CO2化普及加速事業") == "要確認"
    assert issuer_label("沖縄県") == "沖縄県"
    assert issuer_label("") == "要確認"
    print("[ok] sns_safety selftest")


if __name__ == "__main__":
    import sys as _sys
    if len(_sys.argv) == 4 and _sys.argv[1] == "--fingerprint":
        # 登録用の指紋を作る: python3 scripts/sns_safety.py --fingerprint <FacebookページID> <InstagramのID>
        # 番号は Meta の画面で確かめた正しい値を使う(GitHub に登録済みの値から作ると照合の意味がない)
        print(destination_fingerprint(_sys.argv[2], _sys.argv[3]))
    else:
        _selftest()
