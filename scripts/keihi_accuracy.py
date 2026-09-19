#!/usr/bin/env python3
"""経費精算: 領収書の読取精度を実測する(Power Automate導入前の検証用)。

目的: 月額のPower Automate Premiumを買う前に「Claudeが日本の領収書を読めるか」を
      事実で確かめる。設計書§8の全社展開GO基準「読取成功率80%以上」の実測に使う。
      議事: docs/議事_20260912_経費精算の着工方針.md(上申2)

**個人情報の扱い**: 領収書画像と読取結果は個人情報を含む。本リポジトリは公開のため、
入力画像も結果ファイルも絶対にコミットしない。既定の出力先はリポジトリの外(スクラッチ)。

使い方:
    export ANTHROPIC_API_KEY=...
    python3 scripts/keihi_accuracy.py --images ~/receipts --out ~/keihi_result.json
    python3 scripts/keihi_accuracy.py --self-test   # API不要(集計ロジックのみ)
"""
import argparse
import base64
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import keihi_receipt  # noqa: E402

MODEL = "claude-sonnet-5"
GO_THRESHOLD = 80.0  # 設計書§8: 読取成功率80%以上で全社展開GO
SUFFIXES = (".jpg", ".jpeg", ".png", ".webp", ".gif")
MEDIA_TYPES = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
               ".webp": "image/webp", ".gif": "image/gif"}


def summarize(results):
    """読取結果の一覧から成功率をまとめる。

    0件のときに0%と断定しない(絶対ルール1: 不明は不明のまま出す)。
    母数30件未満は参考値として明示する(log-analysis-playbook A-3)。
    """
    total = len(results)
    ok = sum(1 for r in results if r.get("status") == "お預かり")
    needs_review = total - ok
    success_rate = round(ok / total * 100, 1) if total else None
    return {
        "total": total,
        "ok": ok,
        "needs_review": needs_review,
        "success_rate": success_rate,
        "meets_go_threshold": success_rate is not None and success_rate >= GO_THRESHOLD,
        "reference_only": total < 30,
    }


def read_one(client, path, model):
    """領収書画像を1枚読み取り、判定まで済ませた記録を返す。"""
    media_type = MEDIA_TYPES.get(path.suffix.lower(), "image/jpeg")
    encoded = base64.standard_b64encode(path.read_bytes()).decode("ascii")
    try:
        resp = client.messages.create(
            model=model,
            max_tokens=1000,
            messages=[{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64",
                                             "media_type": media_type, "data": encoded}},
                {"type": "text", "text": keihi_receipt.extraction_prompt()},
            ]}],
        )
        text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text").strip()
        extraction = json.loads(text[text.index("{"):text.rindex("}") + 1])
    except Exception as e:  # noqa: BLE001
        # 読めなかったものは「要対応」として数える。推測で埋めない。
        return {"file": path.name, "status": "要対応",
                "reason": f"読取に失敗({type(e).__name__})", "extraction": None}

    status, reason = keihi_receipt.decide_status(extraction)
    return {"file": path.name, "status": status, "reason": reason, "extraction": extraction}


def _self_test():
    fails = []
    checked = []

    def check(name, cond):
        checked.append(name)
        if not cond:
            fails.append(name)

    # --- 集計: 読取成功率 = お預かり ÷ 全件 ---
    results = [
        {"status": "お預かり"}, {"status": "お預かり"},
        {"status": "お預かり"}, {"status": "お預かり"},
        {"status": "要対応"},
    ]
    s = summarize(results)
    check("全5件が数えられる", s["total"] == 5)
    check("お預かり4件", s["ok"] == 4)
    check("要対応1件", s["needs_review"] == 1)
    check("読取成功率80.0%", s["success_rate"] == 80.0)
    check("80%ちょうどはGO基準を満たす", s["meets_go_threshold"] is True)

    below = summarize([{"status": "お預かり"}, {"status": "要対応"}])
    check("50%はGO基準を満たさない", below["meets_go_threshold"] is False)

    # --- 0件のときに割り算で落ちない・断定しない ---
    empty = summarize([])
    check("0件でも落ちない", empty["total"] == 0)
    check("0件の成功率はNone(0%と断定しない)", empty["success_rate"] is None)
    check("0件はGO判定しない", empty["meets_go_threshold"] is False)

    # --- 母数が少ないときは参考値と明示する(log-analysis-playbook A-3) ---
    check("30件未満は参考値フラグ", summarize(results)["reference_only"] is True)
    many = [{"status": "お預かり"}] * 30
    check("30件以上は参考値フラグなし", summarize(many)["reference_only"] is False)

    if fails:
        print(f"SELF-TEST FAILED ({len(fails)}/{len(checked)}件):")
        for f in fails:
            print("  - " + f)
        return 1
    print(f"keihi_accuracy self-test: OK ({len(checked)}件)")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="領収書の読取精度を実測する")
    parser.add_argument("--images", help="領収書画像が入ったフォルダ(リポジトリ外を指定すること)")
    parser.add_argument("--out", help="結果JSONの出力先(リポジトリ外を指定すること)")
    parser.add_argument("--model", default=MODEL)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args(argv)

    if args.self_test:
        return _self_test()
    if not args.images:
        parser.error("--images を指定してください(--self-test で集計ロジックだけ点検できます)")

    repo = Path(__file__).resolve().parent.parent
    for label, value in (("--images", args.images), ("--out", args.out)):
        if not value:
            continue
        if repo in Path(value).resolve().parents or Path(value).resolve() == repo:
            print(f"[中止] {label} がリポジトリ内を指しています。"
                  "領収書と読取結果は個人情報のため、リポジトリ外を指定してください。")
            return 2

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("[中止] ANTHROPIC_API_KEY が未設定です。")
        return 2

    images = sorted(p for p in Path(args.images).iterdir() if p.suffix.lower() in SUFFIXES)
    if not images:
        print(f"[中止] 画像が見つかりません: {args.images}")
        return 2

    import anthropic
    client = anthropic.Anthropic(api_key=api_key)

    results = []
    for path in images:
        record = read_one(client, path, args.model)
        results.append(record)
        print(f"{path.name}: {record['status']}"
              + (f" — {record['reason']}" if record.get("reason") else ""))

    summary = summarize(results)
    print("\n=== 実測結果 ===")
    print(f"全{summary['total']}件 / お預かり{summary['ok']}件 / 要対応{summary['needs_review']}件")
    rate = summary["success_rate"]
    print(f"読取成功率: {'測定不可' if rate is None else f'{rate}%'}"
          + ("(母数30件未満のため参考値)" if summary["reference_only"] else ""))
    print(f"全社展開GO基準({GO_THRESHOLD}%以上): "
          + ("満たす" if summary["meets_go_threshold"] else "満たさない"))

    if args.out:
        Path(args.out).write_text(
            json.dumps({"summary": summary, "results": results}, ensure_ascii=False, indent=2),
            encoding="utf-8")
        print(f"\n結果を書き出しました: {args.out}(個人情報を含むためコミットしないこと)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
