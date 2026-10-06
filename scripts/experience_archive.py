#!/usr/bin/env python3
"""WikiSkill Phase 1: Experience のサイズ監視と、180日超の月の gzip 化(Rollback 基盤)。

  python3 scripts/experience_archive.py --check
      .claude/experience の合計サイズを表示。exit 0=正常 / 1=3MB以上(警告) / 2=10MB以上(上限超え)
  python3 scripts/experience_archive.py --archive [--dry-run] [--today YYYY-MM-DD]
      翌月1日から180日以上たった月フォルダ YYYY-MM を archive/YYYY-MM.jsonl.gz に固めて元フォルダを消す。
      原本は gzip の中に全行そのまま残る。--dry-run は対象を表示するだけで何も変えない。
      実行後の差分は Git でコミットする(Phase 1 は手動。月次 Routine は将来)。

規律: 黙って成功しない。想定外の失敗は _audit.log に1行残し、stderr に出して exit 1。
      固めた結果を読み戻して原本と一致を確かめてから、はじめて元のファイルを消す。
stdlib のみ。
"""
from __future__ import annotations

import gzip
import io
import os
import re
import shutil
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wikiskill_common import EXPERIENCE_DIR, audit, project_dir  # noqa: E402

MB = 1024 * 1024
ARCHIVE_DIR = "archive"
_MONTH_RE = re.compile(r"^\d{4}-\d{2}$")
USAGE = "使い方: experience_archive.py --check | --archive [--dry-run] [--today YYYY-MM-DD]"


def _exp(root: Path) -> Path:
    return Path(root) / EXPERIENCE_DIR


def _month_dirs(root: Path) -> list[Path]:
    """YYYY-MM という名前のフォルダだけ(_local / archive / その他は対象外)。"""
    base = _exp(root)
    if not base.is_dir():
        return []
    out = []
    for p in sorted(base.iterdir()):
        if not p.is_dir() or not _MONTH_RE.match(p.name):
            continue
        if not 1 <= int(p.name[5:7]) <= 12:
            continue
        out.append(p)
    return out


def total_size(root: Path) -> int:
    """.claude/experience/**/*.jsonl(_local を除く)と archive/*.jsonl.gz の合計バイト。"""
    base = _exp(root)
    if not base.is_dir():
        return 0
    local = base / "_local"
    total = 0
    for p in base.rglob("*.jsonl"):
        if p.is_file() and local not in p.parents:
            total += p.stat().st_size
    arch = base / ARCHIVE_DIR
    if arch.is_dir():
        for p in arch.glob("*.jsonl.gz"):
            if p.is_file():
                total += p.stat().st_size
    return total


def check_size(root: Path, warn_mb: float = 3.0, fail_mb: float = 10.0) -> int:
    """合計サイズを表示し、0(正常)/ 1(warn 以上)/ 2(fail 以上)を返す。"""
    size = total_size(root)
    print(f"Experience合計 {size / MB:.1f}MB(警告 {warn_mb:g}MB / 上限 {fail_mb:g}MB)")
    if size >= fail_mb * MB:
        return 2
    if size >= warn_mb * MB:
        return 1
    return 0


def _next_month_first(y: int, m: int) -> date:
    return date(y + 1, 1, 1) if m == 12 else date(y, m + 1, 1)


def archivable_months(root: Path, today: date, older_than_days: int = 180) -> list[Path]:
    """月フォルダ YYYY-MM の翌月1日から older_than_days 日以上たったもの(古い順)。"""
    out = []
    for p in _month_dirs(root):
        y, m = int(p.name[:4]), int(p.name[5:7])
        if _next_month_first(y, m) + timedelta(days=older_than_days) <= today:
            out.append(p)
    return out


def _month_bytes(files: list[Path]) -> bytes:
    """ファイル名順に連結。末尾改行のないファイルには改行を1つ足す(行数は変わらない)。"""
    return b"".join(_normalized(f) for f in files)


def _write_gzip(path: Path, data: bytes) -> None:
    """mtime=0・ファイル名なしで書く(同じ入力なら同じバイト列)。"""
    with open(path, "wb") as raw:
        with gzip.GzipFile(filename="", fileobj=raw, mode="wb", mtime=0) as gz:
            gz.write(data)


def _is_block_subsequence(gz_data: bytes, files_data: list[bytes]) -> bool:
    """files_data(各ファイルの正規化済みバイト列)が、gz_data の中に順番どおり・行頭から現れるか。"""
    pos = 0
    for b in files_data:
        idx = gz_data.find(b, pos)
        while idx > 0 and gz_data[idx - 1:idx] != b"\n":
            idx = gz_data.find(b, idx + 1)
        if idx < 0:
            return False
        pos = idx + len(b)
    return True


def _read_gzip(path: Path) -> bytes:
    try:
        with gzip.open(path, "rb") as f:
            return f.read()
    except (OSError, EOFError) as e:  # BadGzipFile は OSError の仲間
        raise RuntimeError(f"{path.name} を読み戻せません({type(e).__name__}: {e})") from e


def _plan_month(root: Path, month_dir: Path) -> tuple[str, str, list[Path]]:
    """月フォルダに対して archive() が何をするかを決める(読むだけで何も変えない)。

    action: "skip"(固めるものがない)/ "archive"(新規に固める)/
            "resume"(gz は既に完全。前回の削除失敗の後始末だけ行う)/ "refuse"(見送り。detail に理由)
    """
    files = sorted(month_dir.glob("session-*.jsonl"))
    if not files:
        return "skip", "session-*.jsonl がない", files
    expected = {p.name for p in files}
    extra = sorted(p.name for p in month_dir.iterdir() if p.name not in expected)
    if extra:
        return "refuse", f"session-*.jsonl 以外のものがある(原本は無傷): {', '.join(extra)}", files
    dest = _exp(root) / ARCHIVE_DIR / f"{month_dir.name}.jsonl.gz"
    if not dest.exists():
        return "archive", "", files
    try:
        gz_data = _read_gzip(dest)
    except RuntimeError as e:
        return "refuse", f"{dest.name} が既にあり、読み戻せないため上書きしません(原本は無傷): {e}", files
    if _is_block_subsequence(gz_data, [_normalized(f) for f in files]):
        return "resume", f"{dest.name} は既に原本の全行を含む(前回の削除失敗の後始末)", files
    return "refuse", f"{dest.name} が既にあり、残っている原本と内容が一致しないため上書きしません(原本は無傷)", files


def _normalized(f: Path) -> bytes:
    data = f.read_bytes()
    return data + b"\n" if data and not data.endswith(b"\n") else data


def _remove_month(month_dir: Path, dest: Path) -> None:
    """検証済みの gz がある月フォルダを消す。失敗したら、何が残っているかを正確に伝える。"""
    try:
        shutil.rmtree(month_dir)
    except Exception as e:  # noqa: BLE001
        left = sorted(str(p) for p in month_dir.rglob("*") if p.is_file()) if month_dir.exists() else []
        raise RuntimeError(
            f"{dest.name} は検証済みで完全です。ただし {month_dir.name} フォルダの削除に失敗し、"
            f"一部だけ消えている可能性があります({type(e).__name__}: {e})。"
            f"残っているファイルを手で削除するか、同じコマンドを再実行すると後始末を完了します: "
            f"{', '.join(left) if left else '(なし)'}"
        ) from e


def _archive_month(root: Path, month_dir: Path) -> Path | None:
    action, detail, files = _plan_month(root, month_dir)
    if action == "skip":
        return None  # 固めるものがない(空フォルダは触らない)
    if action == "refuse":
        raise RuntimeError(f"{month_dir.name} は見送り: {detail}")
    arch = _exp(root) / ARCHIVE_DIR
    dest = arch / f"{month_dir.name}.jsonl.gz"
    if action == "archive":
        data = _month_bytes(files)
        arch.mkdir(parents=True, exist_ok=True)
        tmp = arch / f".{dest.name}.tmp"
        try:
            _write_gzip(tmp, data)
            if _read_gzip(tmp) != data:
                raise RuntimeError(f"{dest.name} の読み戻しが原本と一致しません(原本は無傷)")
            os.replace(tmp, dest)
        finally:
            if tmp.exists():
                tmp.unlink()
    _remove_month(month_dir, dest)
    return dest


def archive(root: Path, today: date, older_than_days: int = 180) -> list[Path]:
    """対象の各月を archive/YYYY-MM.jsonl.gz に固めて元フォルダを削除。作った gz のパスを返す。

    途中で失敗したら止まる(fail-fast)。それまでに固めた月はエラーメッセージに含める。
    """
    done: list[Path] = []
    for month_dir in archivable_months(root, today, older_than_days):
        try:
            dest = _archive_month(root, month_dir)
        except Exception as e:
            if done:
                names = ", ".join(p.name for p in done)
                raise RuntimeError(f"{e} / 失敗より前に固め終えた月(変更済み・要コミット): {names}") from e
            raise
        if dest is not None:
            done.append(dest)
    return done


def _parse(argv: list[str]):
    """(mode, dry_run, today) を返す。不正なら None。"""
    mode, dry, today = None, False, None
    args = list(argv)
    while args:
        a = args.pop(0)
        if a in ("--check", "--archive"):
            if mode is not None:
                return None
            mode = a
        elif a == "--dry-run":
            dry = True
        elif a == "--today":
            if not args:
                return None
            try:
                today = date.fromisoformat(args.pop(0))
            except ValueError:
                return None
        else:
            return None
    if mode is None or (mode == "--check" and (dry or today is not None)):
        return None
    if dry and mode != "--archive":
        return None
    return mode, dry, today


def main(argv: list[str], root: Path | None = None) -> int:
    parsed = _parse(argv)
    if parsed is None:
        print(USAGE, file=sys.stderr)
        return 2
    mode, dry, today = parsed
    root = Path(root) if root is not None else None
    try:
        if root is None:
            root = project_dir()
        if mode == "--check":
            return check_size(root)
        today = today or date.today()
        if dry:
            months = archivable_months(root, today)
            would, refused, stopped = 0, 0, False
            for p in months:
                action, detail, files = _plan_month(root, p)
                if action == "skip":
                    continue
                if action == "refuse":
                    print(f"[dry-run] {p.name}: 見送り({detail})")
                    refused += 1
                    stopped = True
                elif stopped:
                    print(f"[dry-run] {p.name}: 未実行(前の月の見送りで実行が止まるため)")
                elif action == "resume":
                    print(f"[dry-run] {p.name}: 後始末のみ({detail})")
                    would += 1
                else:
                    print(f"[dry-run] {p.name}: {len(files)} ファイルを archive/{p.name}.jsonl.gz に固める予定")
                    would += 1
            print(f"[dry-run] 実行予定 {would} か月 / 見送り {refused} か月(何も変更していません)")
            return 0
        done = archive(root, today)
        for p in done:
            print(f"archived: {p.name}")
        print(f"対象 {len(done)} か月を固めました(結果は Git でコミットしてください)")
        return 0
    except Exception as e:  # noqa: BLE001 - 失敗を必ず記録して非0で終わる(fail closed)
        msg = f"experience_archive {mode} 失敗: {type(e).__name__}: {e}"
        try:
            audit(root if root is not None else Path.cwd(), "archive", msg)
        except Exception:  # noqa: BLE001
            pass
        print(msg, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
