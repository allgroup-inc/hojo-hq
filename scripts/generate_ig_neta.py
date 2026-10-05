#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IG投稿案(ig_neta.json)を、**照合済みの制度だけ**から作る。

これまで ig_neta.json は生成元スクリプトが無い手置きのファイルだった。
そのため、照合を通っていない日付や金額が本文に入り、原文が変わっても
気づけないまま3週間使い回され、遥さんの指摘で発覚した(2026-09-24)。

ここで守ること:
  1. **verified=True の制度からしか作らない**
  2. 締切の無い制度(常時・年度内)から選ぶ。照合日が古いと締切は断定できないため
     (照合から30日を過ぎた裏づけで日付を書くと check_ig_neta が止める)
  3. 本文に**日付と金額を書かない**。制度DBの金額欄はほとんどが「要確認」で、
     書いた時点で断定になる。金額は公式ページへ誘導する
  4. 案に seido_id を持たせる。URLの一致ではなくIDで裏づけをたどれるようにする
  5. 前回までに使った制度は選ばない(毎週入れ替わる)

使い方:
  python scripts/generate_ig_neta.py            # 次の5案を作る
  python scripts/generate_ig_neta.py --dry-run  # 書き出さずに見るだけ
  python scripts/generate_ig_neta.py --self-test
"""
import argparse
import datetime as dt
import json
import os
import re
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
SEIDO = os.path.join(BASE, "data", "fukugiiro", "seido.json")
NETA = os.path.join(BASE, "data", "fukugiiro", "ig_neta.json")

N_ITEMS = 5
OK_DEADLINE_TYPES = ("常時", "年度内")
MAX_MUNI = 1  # 市町村限定の制度は1件まで(県全体に向けたアカウントのため)

# ライフイベントごとの入り方。全部が同じ書き出しにならないようにする
OPENERS = {
    "妊娠・出産": "赤ちゃんを迎える準備のなかで、見落とされがちな制度です。",
    "子育て": "子育て中のご家庭に、知らないままの方が多い制度です。",
    "入園・入学": "進学や入園のタイミングで使える制度です。",
    "病気・けが": "治療が続くときに、負担を軽くする制度があります。",
    "低所得・生活苦": "家計が苦しいとき、相談できる窓口と制度があります。",
    "失業": "仕事を離れたあとに使える制度です。",
    "就職・転職": "働きはじめる前後で使える制度です。",
    "障がい": "障がいのあるご本人・ご家族に向けた制度です。",
    "介護": "介護がはじまったときに使える制度です。",
    "住宅取得・引越": "住まいのことで困ったときに使える制度です。",
}
DEFAULT_OPENER = "知らないままの方が多い制度です。"

# 相談窓口・案内ページは「申請してもらうもの」ではない。同じ言い方をすると嘘になる
WINDOW_WORDS = ("窓口", "相談", "案内", "入口", "センター")
# 同じ書き出し・同じ見出しが1セットに並ぶと定型が透ける。制度IDで散らす
WINDOW_OPENERS = [
    "ひとりで抱えなくて大丈夫です。相談できる窓口があります。",
    "どこに聞けばいいか分からない、がいちばん多い困りごとです。",
    "制度を探す前に、まとめて相談できる場所があります。",
]
WINDOW_TITLES = [
    "「{name}」、相談だけでも大丈夫です",
    "「{name}」、どこに聞けばいいか迷ったら",
    "「{name}」、まとめて相談できます",
]
APPLY_TITLES = [
    "「{name}」、手続きをしないと始まりません",
    "「{name}」、使っていますか?",
    "「{name}」、申し込みを忘れていませんか",
]
HARD_TITLES = [
    "「{name}」、ひとりで抱えないでください",
    "「{name}」、使える人が使えていません",
    "「{name}」、遠慮しなくて大丈夫です",
]
PLAIN_TITLES = [
    "「{name}」、知っていますか?",
    "「{name}」、見落とされがちです",
    "「{name}」、名前だけでも覚えてください",
]

CLOSER = "「うちは対象かな?」と思ったら、まず公式ページを見てみてください。"

# ハッシュタグ用の言い換え。制度DBの分類名をそのまま出すと、
# 当事者に向けて使う言葉として強すぎるものがある(例: 低所得・生活苦)
EVENT_TAG = {
    "低所得・生活苦": "くらしの支援",
    "病気・けが": "医療費",
    "妊娠・出産": "出産",
    "入園・入学": "入園入学",
    "住宅取得・引越": "住まい",
    "就職・転職": "しごと",
    "障がい": "障がい福祉",
    "失業": "仕事さがし",
}


def _clean(text):
    """制度DBの説明から、そのまま投稿に載せると硬い言い回しを整える。
    事実は変えない(断定を足さない・条件を外さない)。"""
    t = (text or "").strip()
    t = re.sub(r"が対象となる可能性があります。?$", "が対象になることがあります。", t)
    t = re.sub(r"\s+", " ", t)
    return t


def area_tag(area):
    return "沖縄" if area in ("全国", "沖縄県") else area


def _tag(word):
    """ハッシュタグに使える形にする。記号が混ざるとそこで切れて別のタグになる。"""
    return "#" + re.sub(r"[^0-9A-Za-zぁ-んァ-ヶ一-龥ー]", "", word or "")[:14]


def _variant(key, options):
    """制度IDから決める(毎回同じ結果・セット内では散らばる)。"""
    return options[sum(ord(c) for c in (key or "")) % len(options)]


def is_window(s):
    """相談窓口・案内ページかどうか(申請して受け取る制度ではない)。"""
    blob = (s.get("name") or "") + (s.get("target_household") or "")
    return any(w in blob for w in WINDOW_WORDS)


def hashtags(s):
    tags = ["#もらいわすれ堂", _tag(area_tag(s.get("area")))]
    for ev in (s.get("life_events") or [])[:2]:
        tags.append(_tag(EVENT_TAG.get(ev, ev)))
    name = re.sub(r"[(（].*?[)）]", "", s.get("name") or "").strip()
    if name:
        tags.append(_tag(name))
    return " ".join(dict.fromkeys(t for t in tags if len(t) > 1))


def _sentence(text):
    """文末に句点を足す(制度DBの欄は句点の有無がそろっていない)。"""
    t = (text or "").strip()
    if t and t[-1] not in "。.!?！?":
        t += "。"
    return t


def build_caption(s):
    ev = (s.get("life_events") or [None])[0]
    opener = (_variant(s.get("id"), WINDOW_OPENERS) if is_window(s)
              else OPENERS.get(ev, DEFAULT_OPENER))
    target = _clean(s.get("target_household"))
    how = _clean(s.get("how_to_apply"))
    parts = [opener, f"「{s.get('name')}」。"]
    if target:
        parts.append(_sentence(target))
    if how:
        label = "相談先は" if is_window(s) else "申し込みの窓口は"
        parts.append(_sentence(f"{label}{how.rstrip('。')}"))
    parts.append("金額や細かい条件は年度で変わることがあるので、"
                 "このページでご確認ください。")
    parts.append(CLOSER)
    return "".join(parts)


def build_caution(s):
    return (f"金額・期限・対象条件は本文に書かない(照合日 {s.get('verified_at')} 時点の"
            f"記録に基づく案のため)。「対象になることがあります」の言い方を崩さない。"
            f"制度ID {s.get('id')}")


def title_of(s):
    name = re.sub(r"[(（].*?[)）]", "", s.get("name") or "").strip()
    ev = (s.get("life_events") or [None])[0]
    if is_window(s):
        return _variant(s.get("id"), WINDOW_TITLES).format(name=name)
    if ev in ("低所得・生活苦", "失業"):
        pool = HARD_TITLES
    elif ev in ("妊娠・出産", "子育て", "入園・入学"):
        pool = APPLY_TITLES
    else:
        pool = PLAIN_TITLES
    return _variant(s.get("id"), pool).format(name=name)


def candidates(seido, used_ids, used_urls):
    out = []
    for s in seido.get("items", []):
        if not s.get("verified"):
            continue
        if s.get("deadline_type") not in OK_DEADLINE_TYPES:
            continue
        if s.get("id") in used_ids or (s.get("source_url") or "") in used_urls:
            continue
        if not (s.get("name") and s.get("source_url")):
            continue
        out.append(s)
    return out


def pick(cands, n=N_ITEMS):
    """ライフイベントが重ならないように選ぶ。全国・県を優先し、市町村限定は1件まで。"""
    def rank(s):
        area = s.get("area")
        return (0 if area == "全国" else 1 if area == "沖縄県" else 2,
                s.get("id") or "")

    chosen, seen_ev, muni = [], set(), 0
    for s in sorted(cands, key=rank):
        ev = (s.get("life_events") or [None])[0]
        if ev in seen_ev:
            continue
        is_muni = s.get("area") not in ("全国", "沖縄県")
        if is_muni and muni >= MAX_MUNI:
            continue
        chosen.append(s)
        seen_ev.add(ev)
        muni += 1 if is_muni else 0
        if len(chosen) == n:
            break
    return chosen


def build(seido, used_ids, used_urls, today):
    picks = pick(candidates(seido, used_ids, used_urls))
    items = []
    for i, s in enumerate(picks, 1):
        items.append({
            "no": i,
            "seido_id": s["id"],
            "title": title_of(s),
            "caption": build_caption(s),
            "hashtags": hashtags(s),
            "caution": build_caution(s),
            "source_url": s["source_url"],
            "image_hint": f"{(s.get('life_events') or ['くらし'])[0]}のやさしいイラスト"
                          f"+「{re.sub(r'[(（].*?[)）]', '', s['name']).strip()[:12]}」",
        })
    week = today.isocalendar()
    return {
        "updated_at": today.isoformat(),
        "week": f"{week[0]}-W{week[1]:02d}",
        "note": "照合済み(verified=True)かつ締切の無い制度だけから "
                "scripts/generate_ig_neta.py が生成。日付・金額は本文に書かない。",
        "items": items,
    }


def previous_ids(neta):
    ids = set(neta.get("used_ids", []))
    for it in neta.get("items", []):
        if it.get("seido_id"):
            ids.add(it["seido_id"])
    return ids


def previous_urls(neta):
    return {it.get("source_url") for it in neta.get("items", []) if it.get("source_url")}


# ── 自己テスト ────────────────────────────────────────────────
def self_test():
    ok = bad = 0

    def check(label, cond):
        nonlocal ok, bad
        if cond:
            ok += 1
        else:
            bad += 1
            print(f"  NG {label}")

    def prog(i, ev, area="全国", verified=True, dtype="常時"):
        return {"id": f"p{i}", "name": f"制度{i}", "area": area, "verified": verified,
                "verified_at": "2026-08-06", "deadline_type": dtype,
                "life_events": [ev], "target_household": "…が対象となる可能性があります",
                "how_to_apply": "市区町村の窓口",
                "source_url": f"https://example.go.jp/{i}"}

    seido = {"items": [
        prog(1, "子育て"), prog(2, "病気・けが"), prog(3, "失業"),
        prog(4, "介護"), prog(5, "障がい"), prog(6, "子育て"),
        prog(7, "住宅取得・引越", verified=False),
        prog(8, "妊娠・出産", dtype="期限あり"),
        prog(9, "入園・入学", area="那覇市"), prog(10, "就職・転職", area="浦添市"),
    ]}
    today = dt.date(2026, 9, 24)

    c = candidates(seido, set(), set())
    check("未照合の制度は候補に入れない", all(x["id"] != "p7" for x in c))
    check("締切ありの制度は候補に入れない", all(x["id"] != "p8" for x in c))
    check("照合済み・締切なしは候補に入る", {x["id"] for x in c} >= {"p1", "p2", "p3"})

    d = build(seido, set(), set(), today)
    check("5案そろう", len(d["items"]) == N_ITEMS)
    check("全案に制度IDが付く", all(it["seido_id"] for it in d["items"]))
    evs = [next(p for p in seido["items"] if p["id"] == it["seido_id"])["life_events"][0]
           for it in d["items"]]
    check("ライフイベントが重ならない", len(evs) == len(set(evs)))
    muni = [it for it in d["items"]
            if next(p for p in seido["items"]
                    if p["id"] == it["seido_id"])["area"] not in ("全国", "沖縄県")]
    check("市町村限定は1件まで", len(muni) <= MAX_MUNI)

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from check_ig_neta import asserted
    claims = [asserted(it) for it in d["items"]]
    check("本文に日付を書かない", all(not c[0] for c in claims))
    check("本文に金額を書かない", all(not c[1] for c in claims))

    check("前回使った制度は選ばない",
          all(it["seido_id"] != "p1" for it in build(seido, {"p1"}, set(), today)["items"]))
    check("前回のURLでも除ける",
          all(it["seido_id"] != "p2"
              for it in build(seido, set(), {"https://example.go.jp/2"}, today)["items"]))

    check("前回のIDを拾える",
          previous_ids({"items": [{"seido_id": "a"}], "used_ids": ["b"]}) == {"a", "b"})

    cap = build_caption(seido["items"][0])
    check("断定をやわらげる", "可能性があります" not in cap and "ことがあります" in cap)
    check("文がくっつかない", "ます申し込み" not in cap and "です申し込み" not in cap)

    window = {"id": "w", "name": "生活困窮者自立支援制度(相談窓口)", "area": "全国",
              "verified": True, "verified_at": "2026-08-06", "deadline_type": "常時",
              "life_events": ["低所得・生活苦"],
              "target_household": "総合相談窓口です",
              "how_to_apply": "自立相談支援機関",
              "source_url": "https://example.go.jp/w"}
    check("相談窓口を見分ける", is_window(window))
    check("相談窓口に『手続きをしないと始まりません』と付けない",
          "始まりません" not in title_of(window))
    w2 = dict(window, id="w2")
    check("制度が違えば書き出しも変わる",
          build_caption(window)[:12] != build_caption(w2)[:12]
          or title_of(window) != title_of(w2))
    check("同じ制度なら毎回同じ", build_caption(window) == build_caption(dict(window)))
    titles = [title_of(p) for p in seido["items"] if p["verified"]]
    check("見出しが全部同じにならない", len(set(titles)) > 1)
    check("同じ制度の見出しは毎回同じ",
          title_of(seido["items"][0]) == title_of(dict(seido["items"][0])))
    check("相談窓口は相談先として書く", "相談先は" in build_caption(window))
    check("ハッシュタグから記号を落とす", "・" not in hashtags(
        {"name": "幼児教育・保育の無償化", "area": "全国", "life_events": ["子育て"]}))
    check("きつい分類名は言い換える",
          "#くらしの支援" in hashtags({"name": "x", "area": "全国",
                                      "life_events": ["低所得・生活苦"]})
          and "低所得" not in hashtags({"name": "x", "area": "全国",
                                       "life_events": ["低所得・生活苦"]}))
    check("出典を見るよう促す", "公式ページ" in cap or "このページ" in cap)
    check("ハッシュタグにブランドが入る", "#もらいわすれ堂" in hashtags(seido["items"][0]))
    check("注意書きに制度IDを残す", "p1" in build_caution(seido["items"][0]))
    check("週番号が入る", d["week"] == "2026-W39")

    # 候補が足りないときは無理に埋めない
    few = build({"items": [prog(1, "子育て")]}, set(), set(), today)
    check("候補が少なければその分だけ出す", len(few["items"]) == 1)

    print(f"自己テスト: OK {ok} / NG {bad}")
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return self_test()

    with open(SEIDO, encoding="utf-8") as f:
        seido = json.load(f)
    prev = {}
    if os.path.exists(NETA):
        with open(NETA, encoding="utf-8") as f:
            prev = json.load(f)

    d = build(seido, previous_ids(prev), previous_urls(prev), dt.date.today())
    if len(d["items"]) < N_ITEMS:
        print(f"::warning::候補が足りず {len(d['items'])}案しか作れませんでした"
              f"(照合済み・締切なしの制度を増やしてください)")
    # 次回に同じ制度を選ばないよう、使った分を積む
    d["used_ids"] = sorted(set(prev.get("used_ids", []))
                           | previous_ids(prev)
                           | {it["seido_id"] for it in d["items"]})

    for it in d["items"]:
        print(f"案{it['no']} [{it['seido_id']}] {it['title']}")
        print(f"   {it['caption'][:100]}…")
        print(f"   {it['hashtags']}")
    if a.dry_run:
        print("\n(--dry-run のため書き出していません)")
        return 0
    with open(NETA, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print(f"\n書き出しました: data/fukugiiro/ig_neta.json({len(d['items'])}案)")
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
