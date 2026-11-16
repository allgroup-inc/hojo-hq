#!/usr/bin/env python3
"""もらいわすれ堂 診断ページ監視の外部監視(A案): 監視が動いていることを外部サービス(healthchecks.io など)へ知らせる。

15分監視(diagnosis-monitor.yml の monitor ジョブ)の最後に呼ぶ。外部サービスは「一定時間ハートビートが来ない」ことを
自分で数えて運営へ知らせるので、GitHub Actions のスケジュール起動が止まっても(この仕組みの外から)気づける。

送るもの(healthchecks.io のハートビートURLの形式):
  成功: <URL>        監視が診断ページを検査し、障害Issueの更新まで終えた(ページの正常・異常は問わない。ページの異常は
                     障害Issue と LINE が知らせる)。本文に検査の結果の要約を付ける
  失敗: <URL>/fail   監視が動いたのに検査まで届かなかった(準備失敗・結果が壊れている)/ 障害Issueを更新できなかった
                     → 外部サービスがすぐに知らせる(監視の故障)

ハートビートのURLは Secret(DIAG_HEARTBEAT_URL)で渡す。URLそのものが鍵なので、ログ・Issue・例外文面に出さない。
未設定なら何もしない。送れなくても監視ジョブは赤にしない(外部サービス側が「来ない」ことで気づく)。
設計: docs/診断ページの外部監視_設計.md
"""
import json
import os
import re
import sys
import urllib.error
import urllib.request

RESULT = "diagnosis_monitor_result.json"
UA = "moradou-diagnosis-heartbeat/1.0 (+https://github.com/allgroup-inc/hojo-hq)"


def decide(result_path, handled):
    """('success'|'fail', 本文)。本文は外部サービスの記録に残る短い要約(秘密情報を含めない)。"""
    try:
        with open(result_path, encoding="utf-8") as f:
            result = json.load(f)
    except FileNotFoundError:
        return "fail", "MONITOR_SETUP: 診断ページの検査まで届きませんでした(準備段階の失敗)"
    except Exception:
        return "fail", "RESULT_BROKEN: 検査結果を読めませんでした"
    if handled != "true":
        return "fail", "INCIDENT_NOT_HANDLED: 障害Issueの更新に失敗しました(通知が届かない可能性)"
    if result.get("ok"):
        return "success", "checked: 診断ページは正常"
    sig = re.sub(r"[^\w,]", "", str(result.get("signature") or ""))[:80]
    return "success", f"checked: 診断ページに異常あり({sig})。障害Issue・LINEで通知済み"


def valid_url(url):
    return bool(re.fullmatch(r"https://[^\s/]+/\S+", url or ""))


def send(url, signal, body, timeout=10, tries=3):
    """(送れたか, 説明)。説明に URL を含めない。"""
    target = url.rstrip("/") + ("/fail" if signal == "fail" else "")
    last = ""
    for _ in range(tries):
        req = urllib.request.Request(target, data=body.encode("utf-8")[:10000], method="POST",
                                     headers={"User-Agent": UA, "Content-Type": "text/plain; charset=utf-8"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as res:
                return True, f"HTTP {res.status}"
        except urllib.error.HTTPError as e:
            last = f"HTTP {e.code}"
            if 400 <= e.code < 500 and e.code != 429:
                break  # URLの誤りなどは繰り返しても直らない
        except urllib.error.URLError as e:
            last = f"URLError({type(e.reason).__name__})"
        except Exception as e:
            last = type(e).__name__
    return False, last


def main(env=None, result_path=RESULT):
    env = os.environ if env is None else env
    url = env.get("HEARTBEAT_URL", "")
    if not url:
        print("外部監視の通知先(DIAG_HEARTBEAT_URL)が未設定のため、ハートビートは送りません")
        return 0
    if not valid_url(url):
        print("::warning::外部監視の通知先の形式が想定外のため、ハートビートは送りません(https のURLを設定してください)")
        return 0
    signal, body = decide(result_path, env.get("HANDLED", ""))
    ok, detail = send(url, signal, body)
    kind = "生存(成功)" if signal == "success" else "監視の故障(失敗)"
    if ok:
        print(f"外部監視へ送りました: {kind} / {detail}")
    else:
        print(f"::warning::外部監視へ送れませんでした: {kind} / {detail}(外部サービス側が、届かないことで気づきます)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
