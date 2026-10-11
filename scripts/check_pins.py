"""L2' : requirements(ハッシュ固定)と PyPI 公式メタデータの完全照合。標準ライブラリのみ。

検査(1 つでも該当すれば exit 1):
  - 期待リスト(必須 --expect): 固定すべき pkg==ver の集合と、ファイル内のブロック集合が完全一致しない
      (パッケージを丸ごと消しても、期待リストは workflow 側にあるので検出できる)
  - 構文: `pkg==ver` 以外の指定子 / 64 桁 16 進でないハッシュ / --hash 以外のオプション /
          行末 `\\` の継続が EOF・空行・コメント行で途切れている
  - 重複: 同じパッケージの複数ブロック / 同じブロック内の重複ハッシュ
  - 不足: PyPI にある(yanked でない)ファイル内容(sha256)が列挙に無い
  - 余分: 列挙にあるが PyPI のそのパッケージ・その版のどのファイルにも無い sha256
  - yanked: 列挙した sha256 を持つファイルがすべて yanked
  - 取得不能: 404・ネットワーク失敗(黙って通さない)
保証範囲: 照合の単位は「ファイル内容(sha256)」。同じ内容のファイルが複数名で登録されていても
  pip は内容ハッシュでしか検証しないため、本検査も内容単位で過不足を見る(ファイル名は報告にだけ使う)。
使い方: python3 check_pins.py <requirements> --expect pkg==ver [pkg==ver ...]
"""
import json, re, sys, urllib.request

HEX64 = re.compile(r"^[0-9a-f]{64}$")
SPEC_RE = re.compile(r"([A-Za-z0-9][A-Za-z0-9._-]*)==([A-Za-z0-9.+!-]+)")   # 固定指定子(requirements・--expect 共通)

def norm(name):
    return re.sub(r"[-_.]+", "-", name).lower()

def parse(path):
    """行継続(末尾の \\)をつないで論理行にし、pkg==ver と --hash を取り出す。構文エラーも返す。"""
    logical, errors, buf, start = [], [], "", 0
    for lineno, raw in enumerate(open(path, encoding="utf-8"), 1):
        body = raw.split("#", 1)[0].rstrip("\n")
        if not body.strip():
            if buf:
                errors.append(f"構文: {start} 行目の行継続が空行/コメント行({lineno} 行目)で途切れている")
                buf, start = "", 0
            continue
        if body.rstrip().endswith("\\"):
            if not buf:
                start = lineno
            buf += body.rstrip()[:-1] + " "
            continue
        logical.append((start or lineno, buf + body))
        buf, start = "", 0          # 論理行を確定したら継続状態と開始行番号を必ず戻す
    if buf:
        errors.append(f"構文: {start} 行目からの行継続が未完了のまま EOF")
    blocks = []
    for lineno, ln in logical:
        toks = ln.split()
        spec, opts = toks[0], toks[1:]
        m = SPEC_RE.fullmatch(spec)
        if not m:
            errors.append(f"構文: {lineno} 行目 固定指定子ではない: {spec}")
            continue
        hashes = []
        for o in opts:
            hm = re.fullmatch(r"--hash=sha256:([0-9a-fA-F]+)", o)
            if not hm or not HEX64.match(hm.group(1).lower()):
                errors.append(f"構文: {lineno} 行目 不正なオプション/ハッシュ ({spec}): {o[:40]}")
                continue
            hashes.append(hm.group(1).lower())
        if not hashes:
            errors.append(f"構文: {lineno} 行目 {spec} にハッシュが 1 つも無い")
        blocks.append((norm(m.group(1)), m.group(2), hashes))
    return blocks, errors

def pypi_files(pkg, ver):
    """sha256 -> [(filename, yanked), ...]。同じ内容のファイルが複数あっても潰さない。"""
    with urllib.request.urlopen(f"https://pypi.org/pypi/{pkg}/{ver}/json", timeout=30) as r:
        d = json.load(r)
    out = {}
    for f in d["urls"]:
        out.setdefault(f["digests"]["sha256"].lower(), []).append((f["filename"], bool(f.get("yanked"))))
    return out

def main(argv):
    if len(argv) < 2:
        print("使い方: check_pins.py <requirements> --expect pkg==ver ..."); return 2
    path = argv[1]
    errors = []
    expect, expect_pkgs = set(), {}
    if "--expect" in argv:
        for s in argv[argv.index("--expect") + 1:]:
            m = SPEC_RE.fullmatch(s)          # requirements 側と同じ厳格な `pkg==ver` 構文
            if not m:
                errors.append(f"期待リストの構文誤り(pkg==ver のみ可): {s}"); continue
            n, v = norm(m.group(1)), m.group(2)
            if n in expect_pkgs:
                errors.append(f"期待リストの重複: {n}({expect_pkgs[n]} と {v})"); continue
            expect_pkgs[n] = v
            expect.add(f"{n}=={v}")
    if not expect:
        errors.append("期待リスト(--expect)が未指定。固定すべき pkg==ver を workflow 側から必ず渡す")
    blocks, perr = parse(path)
    errors += perr
    seen, total_listed = {}, 0
    for pkg, ver, hashes in blocks:
        if pkg in seen:
            errors.append(f"重複: {pkg} のブロックが複数({seen[pkg]} と {ver})"); continue
        seen[pkg] = ver
        if len(hashes) != len(set(hashes)):
            errors.append(f"重複: {pkg}=={ver} に同じハッシュが複数")
        listed = set(hashes)
        total_listed += len(listed)
        try:
            files = pypi_files(pkg, ver)
        except Exception as e:
            errors.append(f"取得不能: {pkg}=={ver}: {type(e).__name__} {getattr(e, 'code', '')}"); continue
        names = lambda h: "/".join(fn for fn, _ in files[h])
        live = {h for h, fl in files.items() if any(not y for _, y in fl)}      # 1 つでも非 yanked なら有効
        for h in sorted(live - listed):
            errors.append(f"不足: {pkg}=={ver} {names(h)} {h[:12]}…")
        for h in sorted(listed - set(files)):
            errors.append(f"余分/不一致: {pkg}=={ver} のどのファイルにも無い {h[:12]}…")
        for h in sorted(listed & (set(files) - live)):
            errors.append(f"yanked: {pkg}=={ver} {names(h)} {h[:12]}…")
    got = {f"{p}=={v}" for p, v in seen.items()}
    for s in sorted(expect - got):
        errors.append(f"期待リストにあるがファイルに無い: {s}")
    for s in sorted(got - expect):
        errors.append(f"期待リスト外: {s}")
    print(f"packages={len(seen)} expected={len(expect)} listed_hashes={total_listed} errors={len(errors)}")
    for e in errors:
        print("NG", e)
    print("RESULT:", "FAIL" if errors else "PASS")
    return 1 if errors else 0

if __name__ == "__main__":
    sys.exit(main(sys.argv))
