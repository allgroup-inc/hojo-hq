"""統合反映監査ドライバ — アップロードされた定例/boardを自動分類・部門同定・突合する。
- 各ファイルを board / 定例 に分類し、タイトルから月を判定。
- 定例の部門は「チーム合計」がどの部門のboard実績と一致するかで機械同定(照合=同定)。
- 部門別のブロック構成を考慮(催事は①〜④、通常は①〜⑥、ALL委託は集計=直接照合対象外)。
氏名は扱わない(チーム合計行のみ)。実数値入り詳細は非追跡ディレクトリへ。"""
from __future__ import annotations
import argparse, glob, os
import rollup_check as rc

# 部門別に「board実績と突合すべきブロック」
DEPT_BLOCKS = {
    "嘉手納": ["①", "②", "③", "④", "⑤", "⑥"],
    "特殊": ["①", "②", "③", "④", "⑤", "⑥"],
    "豊見城": ["①", "②", "③", "④", "⑤", "⑥"],
    "札幌": ["①", "②", "③", "④", "⑤", "⑥"],
    "CRM": ["①", "②", "③", "④", "⑤", "⑥"],
    "QCM": ["①", "②", "③", "④", "⑤", "⑥"],
    "LTV": ["①", "②", "③", "④", "⑤", "⑥"],
    "催事": ["①", "②", "③", "④"],           # 催事は⑤⑥が無い
}
# ALL委託は「委託まとめ(集計)」で単一定例の直接ロールアップにならない → 同定/突合対象外
AGGREGATE = {"ALL委託"}
ALL_DEPTS = list(DEPT_BLOCKS) + list(AGGREGATE)


def classify(path):
    """(kind, month) を返す。kind ∈ {'board','teikei','other'}。month は '6月'/'7月'/None。"""
    import openpyxl
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    sheets = wb.sheetnames
    kind, month = "other", None
    if "【ALLGRP】A3縦" in sheets:
        kind = "board"
        t = str(wb["【ALLGRP】A3縦"].cell(2, 2).value or "")
    elif "【実数値】A3縦" in sheets:
        kind = "teikei"
        t = str(wb["【実数値】A3縦"].cell(2, 2).value or "")
    else:
        t = ""
    for m in ("6月", "7月"):
        if m in t:
            month = m
    wb.close()
    return kind, month


def identify(team, board_actuals_by_dept):
    """定例のチーム合計を各部門のboard実績と突合し、最も揃う部門と(比率, (揃い,必要,modal日))を返す。
    部門ごとに必要ブロック(催事は①〜④)を使い、揃い数÷必要数の最大を選ぶ。"""
    best, best_ratio, best_info = None, -1.0, None
    for dep, ba in board_actuals_by_dept.items():
        blocks = DEPT_BLOCKS[dep]
        sub = {b: ba[b] for b in blocks if b in ba}
        rr = rc.reconcile(team, sub)
        days = [v["matched_day"] for v in rr.values() if v["ok"]]
        modal = max(set(days), key=days.count) if days else None
        aligned = sum(1 for v in rr.values() if v["ok"] and v["matched_day"] == modal)
        ratio = aligned / max(len(blocks), 1)
        if ratio > best_ratio:
            best, best_ratio, best_info = dep, ratio, (aligned, len(blocks), modal)
    return best, best_ratio, best_info


def run(src, out=None, min_ratio=0.8):
    files = sorted(glob.glob(os.path.join(src, "*.xlsx")))
    boards, teikeis = {}, []           # boards: month->path, teikeis: [(path,month)]
    for f in files:
        kind, month = classify(f)
        if kind == "board" and month:
            boards[month] = f          # 同月複数なら最後を採用(最新想定)
        elif kind == "teikei" and month:
            teikeis.append((f, month))
    lines = ["# 統合反映監査(全月・全部門)", ""]
    summary = {}
    for month, board in sorted(boards.items()):
        ba = {}
        for dep in DEPT_BLOCKS:
            try:
                ba[dep] = rc.board_dept_actuals(board, dep)
            except Exception:
                ba[dep] = {}
        assign = {}   # dep -> (path, ratio, info)
        for f, m in teikeis:
            if m != month:
                continue
            team = rc.parse_team_daily(f)
            dep, ratio, info = identify(team, ba)
            if ratio >= min_ratio and (dep not in assign or ratio > assign[dep][1]):
                assign[dep] = (f, ratio, info)
        lines.append(f"## {month}(board: {os.path.basename(board)[:16]})")
        lines.append("| 部門 | 判定 | 揃い | 一致日 |")
        lines.append("|---|---|---|---|")
        stat = {}
        for dep in ALL_DEPTS:
            if dep in AGGREGATE:
                lines.append(f"| {dep} | ⚠ 集計(直接照合対象外) | — | — |")
                stat[dep] = "aggregate"
            elif dep in assign:
                _, ratio, (al, need, modal) = assign[dep]
                lines.append(f"| {dep} | ✅ 整合 | {al}/{need} | day{modal} |")
                stat[dep] = "ok"
            else:
                lines.append(f"| {dep} | ⛔ 未同定/未提供 | — | — |")
                stat[dep] = "missing"
        lines.append("")
        summary[month] = stat
    report = "\n".join(lines) + "\n"
    if out:
        with open(out, "w", encoding="utf-8") as f:
            f.write(report)
    return report, summary


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("src")
    p.add_argument("--out")
    args = p.parse_args(argv)
    report, summary = run(args.src, args.out)
    print(report)
    if args.out:
        print(f"(written to {args.out})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
