#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SNS 投稿の1か月分の見本を作る(2026-11-09 第1段階)。投稿はしない。

  python3 scripts/make_sns_month_preview.py --out /tmp/sns_preview [--start 2026-11-16] [--count 13]

出力(--out のフォルダ。リポジトリの外を指定する。posts/ や site/ には書かない):
  NN_YYYY-MM-DD_<型>.png  … 見本の画像(右下に「見本」と入る)
  一覧.png                … 全部を縮小して並べたもの
  見本の一覧.md           … 投稿日・型・載せた制度(原文URL)・下書きの文章かどうか・外した制度と理由
外部のサービスには何も送らない。制度データ(data/subsidies.json)と文章の台帳を読むだけ。
"""
import argparse
import json
import os
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sns_planner as P  # noqa: E402
import sns_templates as T  # noqa: E402

BASE = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
REPO_OUTPUTS = ("posts", "site", "data")


def _next_monday(d):
    return d + timedelta(days=(7 - d.weekday()) % 7 or 7)


def caption(post):
    lines = []
    if post["type"] in (P.TYPE_A, P.TYPE_OKINAWA):
        lines.append("いま募集中の制度です。くわしい条件は原文で確かめてください。")
        for p in post["programs"]:
            lines.append(f"・{P.short_name(p['name'])}／{P.amount_text(p)}／{P.deadline_text(p, post['date'])}")
            lines.append(f"  原文: {p['source_url']}")
    else:
        e = post["text"]
        lines.append(f"[{e['id']}]({e['status']}) 一般的な説明です。個別の条件は各制度の公募要領で確かめてください。")
    lines.append("締切の約1か月前から、LINEでお知らせします。プロフィールのリンクから。")
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--start")
    ap.add_argument("--count", type=int, default=13)
    a = ap.parse_args(argv)
    out = os.path.abspath(a.out)
    if any(out == os.path.join(BASE, d) or out.startswith(os.path.join(BASE, d) + os.sep) for d in REPO_OUTPUTS):
        print("[ng] 見本は posts/・site/・data/ の中には出しません。リポジトリの外を指定してください")
        return 2
    os.makedirs(out, exist_ok=True)
    start = date.fromisoformat(a.start) if a.start else _next_monday(date.today())
    items = json.load(open(os.path.join(BASE, "data", "subsidies.json"), encoding="utf-8"))["items"]
    ever = json.load(open(os.path.join(BASE, "data", "sns_evergreen.json"), encoding="utf-8"))["items"]
    recent = P.load_recent_ids(today=start)
    result = P.plan(items, ever, start, a.count, allow_drafts=True, recent_ids=recent)

    from PIL import Image
    rows, thumbs, layout_ng = [], [], []
    for i, post in enumerate(result["posts"], 1):
        stamp = "見本(投稿しません)"
        if "text" in post and post["text"]["status"] != "確認済み":
            stamp += "・文章は確認前の下書き"
        name = f"{i:02d}_{post['date']}_{post['type']}.png"
        try:
            im = T.render(post, post["date"], stamp)
        except T.LayoutError as e:
            layout_ng.append((post["date"], post["type"], str(e)))
            continue
        im.save(os.path.join(out, name))
        thumbs.append(im.resize((360, 360)))
        rows.append((name, post))

    if thumbs:
        cols = 4
        sheet = Image.new("RGB", (cols * 370, ((len(thumbs) + cols - 1) // cols) * 370), (230, 230, 230))
        for k, t in enumerate(thumbs):
            sheet.paste(t, ((k % cols) * 370, (k // cols) * 370))
        sheet.save(os.path.join(out, "一覧.png"))

    wk = "月火水木金土日"
    md = [f"# SNS 投稿の見本({start} から {a.count} 回分・投稿しません)", "",
          f"制度データ: data/subsidies.json(更新 {date.today()} 時点のもの)", ""]
    for name, post in rows:
        md.append(f"## {post['date']}({wk[post['date'].weekday()]}) {P.TYPE_LABEL[post['type']]} — {name}")
        md.append("```")
        md.append(caption(post))
        md.append("```")
    md += ["", "## 投稿できなかった日"]
    md += [f"- {d}: {why}" for d, why in result["skipped"]] or ["- なし"]
    md += [f"- {d}({k}): 画像の検査で外した — {why}" for d, k, why in layout_ng]
    md += ["", f"## 候補から外した制度({len(result['rejected'])}件)"]
    reasons = {}
    for it, why in result["rejected"]:
        key = why.split("(")[0]
        reasons.setdefault(key, []).append(f"{P.short_name(it.get('name'))[:40]}({why})")
    for key, names in sorted(reasons.items(), key=lambda kv: -len(kv[1])):
        md.append(f"- {key}: {len(names)}件")
        md += [f"  - {n}" for n in names[:8]]
        if len(names) > 8:
            md.append(f"  - ほか {len(names) - 8}件")
    with open(os.path.join(out, "見本の一覧.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")
    print(f"[ok] 見本 {len(rows)} 枚 / 投稿できなかった日 {len(result['skipped']) + len(layout_ng)} / "
          f"外した制度 {len(result['rejected'])} 件 → {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
