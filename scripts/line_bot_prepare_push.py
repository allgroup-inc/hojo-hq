#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LINE会話ボット(gas/line-bot)を Apps Script へ反映する前の点検と、反映用フォルダの組み立て。

使い方: python3 scripts/line_bot_prepare_push.py <ライブを clasp pull したフォルダ> <出力フォルダ>

- ライブ側で「function routeMessage_」を含むファイルを本体とみなし、同じファイル名のまま
  リポジトリの gas/line-bot/Code.gs に置き換える。Template.gs は「Template」として足す。
- ライブにだけある関数がある場合は止める(エディタで直接足された修正を上書きで消さないため)。
- 本体以外のファイルが同じ名前の const / function を持っている場合も止める(GASは全ファイルで
  名前を共有するため、重複すると保存時にエラーになる)。
- appsscript.json などその他のファイルはライブのまま残す。
"""
import os
import re
import shutil
import sys

BASE = os.path.join(os.path.dirname(__file__), "..")
REPO_DIR = os.path.join(BASE, "gas", "line-bot")
SCRIPT_EXT = (".gs", ".js")
FUNC_RE = re.compile(r"^function\s+([A-Za-z0-9_$]+)\s*\(", re.M)
CONST_RE = re.compile(r"^(?:const|let|var)\s+([A-Za-z0-9_$]+)\s*=", re.M)
VERSION_RE = re.compile(r"統合版\s*(v[0-9.]+)")


def names(text):
    return set(FUNC_RE.findall(text)) | set(CONST_RE.findall(text))


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def main(live_dir, out_dir):
    repo_main = read(os.path.join(REPO_DIR, "Code.gs"))
    repo_tpl = read(os.path.join(REPO_DIR, "Template.gs"))
    repo_names = names(repo_main) | names(repo_tpl)

    scripts = sorted(f for f in os.listdir(live_dir) if f.endswith(SCRIPT_EXT))
    main_files = [f for f in scripts if "function routeMessage_" in read(os.path.join(live_dir, f))]
    if len(main_files) != 1:
        sys.exit(f"::error::ライブ側で会話ボット本体のファイルを特定できません(候補: {main_files or 'なし'})")
    main_file = main_files[0]
    ext = os.path.splitext(main_file)[1]
    live_main = read(os.path.join(live_dir, main_file))
    m = VERSION_RE.search(live_main)
    print(f"::notice::ライブの本体: {main_file}(版: {m.group(1) if m else '不明'}) → リポジトリの版: "
          f"{VERSION_RE.search(repo_main).group(1)}")

    lost = sorted(set(FUNC_RE.findall(live_main)) - set(FUNC_RE.findall(repo_main + repo_tpl)))
    if lost:
        sys.exit("::error::ライブにだけある関数があります。エディタで直接足された修正を消さないよう、"
                 f"先に gas/line-bot/Code.gs へ取り込んでください: {', '.join(lost)}")

    tpl_file = "Template" + ext
    others = [f for f in scripts if f not in (main_file, tpl_file)]
    for f in others:
        dup = names(read(os.path.join(live_dir, f))) & repo_names
        if dup:
            sys.exit(f"::error::{f} がボット本体と同じ名前を持っています: {', '.join(sorted(dup))}")
    if others:
        print(f"::notice::そのまま残すファイル: {', '.join(others)}")

    if os.path.exists(out_dir):
        shutil.rmtree(out_dir)
    shutil.copytree(live_dir, out_dir, ignore=shutil.ignore_patterns(".clasp.json"))
    with open(os.path.join(out_dir, main_file), "w", encoding="utf-8") as f:
        f.write(repo_main)
    with open(os.path.join(out_dir, tpl_file), "w", encoding="utf-8") as f:
        f.write(repo_tpl)
    changed = live_main != repo_main
    print(f"::notice::本体の差分: {'あり' if changed else 'なし'}(ライブ {live_main.count(chr(10))}行 → "
          f"{repo_main.count(chr(10))}行)")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
