"""公開を停止したサイトを、公開成果物(Pages)から外す。

- apply: 停止したサイトのパスと、そのデータを成果物から削除し、sitemap の該当URLを除く。
- check: 停止したパスが残っていないこと、成果物のどのテキストにも停止先への参照がないことを確かめる。
  失敗は exit 1。値は表示せず、パスと件数だけを表示する。
- 設定: scripts/stopped_sites.json。keep のパス(/go/ymn-* など)は、この処理では削除しない。
- 元のリポジトリの site/ や data/ は変更しない(成果物のディレクトリだけを対象にする)。

使い方:
  python scripts/stop_publish.py --root /tmp/pages-deploy --apply
  python scripts/stop_publish.py --root /tmp/pages-deploy --check
"""
import argparse
import json
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CONFIG_DEFAULT = HERE / "stopped_sites.json"
URL_BLOCK = re.compile(r"<url>.*?</url>", re.S)
TEXT_SUFFIXES = {".html", ".htm", ".js", ".json", ".css", ".txt", ".md", ".xml", ".svg", ".jsonl"}


def load_config(path=CONFIG_DEFAULT) -> dict:
    cfg = json.loads(Path(path).read_text(encoding="utf-8"))
    if cfg.get("version") != 1:
        raise SystemExit("stopped_sites.json: version が想定外")
    return cfg


def _kept(rel: str, cfg: dict) -> bool:
    return any(rel == k or rel.startswith(k) for k in cfg.get("keep", []))


def apply(root: Path, cfg: dict) -> dict:
    removed, dropped = [], 0
    markers = []
    for site in cfg["stopped"]:
        markers += site["url_markers"]
        for prefix in site["site_prefixes"] + site["data_prefixes"]:
            if _kept(prefix, cfg):
                raise SystemExit(f"停止対象が保持の指定と重なっている: {prefix}")
            target = root / prefix.rstrip("/")
            if target.is_dir():
                shutil.rmtree(target)
                removed.append(prefix)
    sitemap = root / "sitemap.xml"
    if sitemap.is_file():
        text = sitemap.read_text(encoding="utf-8")

        def drop(m):
            nonlocal dropped
            block = m.group(0)
            if any(mk in block for mk in markers):
                dropped += 1
                return ""
            return block

        sitemap.write_text(URL_BLOCK.sub(drop, text), encoding="utf-8")
    return {"removed": removed, "sitemap_dropped": dropped}


def check(root: Path, cfg: dict):
    """(fails, passes) を返す。fails は (パス, 理由, 件数)。値は含まない。"""
    fails = []
    for site in cfg["stopped"]:
        for prefix in site["site_prefixes"] + site["data_prefixes"]:
            if (root / prefix.rstrip("/")).exists():
                fails.append((prefix, "公開を停止したパスが成果物に残っている", 1))
        markers = site["url_markers"]
        for f in sorted(root.rglob("*")):
            if not f.is_file() or f.suffix.lower() not in TEXT_SUFFIXES:
                continue
            text = f.read_text(encoding="utf-8", errors="replace")
            n = sum(text.count(mk) for mk in markers)
            if n:
                fails.append((f.relative_to(root).as_posix(), f"停止したサイトへの参照がある({site['name']})", n))
    return fails


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="公開を停止したサイトを公開成果物から外す/検査する")
    ap.add_argument("--root", required=True, help="公開成果物のディレクトリ(例: /tmp/pages-deploy)")
    ap.add_argument("--config", default=str(CONFIG_DEFAULT))
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--apply", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)
    root = Path(args.root)
    if not root.is_dir():
        print("::error::stop_publish: 公開成果物のディレクトリがない")
        return 1
    cfg = load_config(Path(args.config))
    if args.apply:
        rep = apply(root, cfg)
        print(f"stop_publish: 削除 {len(rep['removed'])} 件(パス) / sitemap から {rep['sitemap_dropped']} 件を除外")
        for p in rep["removed"]:
            print(f"  removed {p}")
        return 0
    fails = check(root, cfg)
    for rel, label, n in fails:
        print(f"::error::公開停止の検査 FAIL {rel}: {label} ({n}件)")
    if fails:
        return 1
    print("公開停止の検査 OK: 停止したサイトの残存なし")
    return 0


if __name__ == "__main__":
    sys.exit(main())
