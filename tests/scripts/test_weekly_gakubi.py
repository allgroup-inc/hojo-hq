"""weekly_gakubi.py の禁止語ガード(CI 赤 9 件 PR-A / 決裁キュー #22・F2)の検査。

- 入力マスク: build_prompt に渡る材料(コミット件名・差分・週次レポ)から禁止語を消す
- 出力 fail-closed: 生成文に禁止語が残っていたら書かない・dry-run でも表示しない・非ゼロ終了
- ログには禁止語の番号と位置だけを出す(語そのものは出さない)
禁止語の実文字列はこのファイルに書かない(check_repo_scope.FORBIDDEN_CONTENT を実行時に読む)。
ネットワークと Claude API は使わない(summarize と collect_changes を差し替える)。
"""
import io
import os
import sys
import unicodedata
from contextlib import redirect_stdout
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import weekly_gakubi as wg  # noqa: E402
from check_repo_scope import FORBIDDEN_CONTENT  # noqa: E402

WORD = FORBIDDEN_CONTENT[0]


def _fullwidth(s: str) -> str:
    """ASCII を全角に写す(NFKC で元に戻る表記揺れ)。"""
    return "".join(chr(ord(c) + 0xFEE0) if 0x21 <= ord(c) <= 0x7E else c for c in s)


def _zero_width(s: str) -> str:
    """各文字の間にゼロ幅スペースを挟む(見た目は同じ)。"""
    return "\u200b".join(s)


def _found_indices(text: str) -> list:
    """text に残っている禁止語の番号(失敗メッセージに語そのものを出さないため番号だけ返す)。

    NFKC+casefold の形と、書式文字・空白を除いた形(ゼロ幅で分断した書き方)の両方で見る。
    """
    folded = unicodedata.normalize("NFKC", text).casefold()
    squashed = wg._squash(text)
    return [
        i for i, w in enumerate(FORBIDDEN_CONTENT)
        if w.casefold() in folded or (wg._squash(w) and wg._squash(w) in squashed)
    ]


def _call(fn, *args, **kwargs):
    """本番関数を呼ぶ。内部で例外が出たとき、既定のトレースバックが引数(禁止語を含み得る文)を表示しないよう、
    例外の種類名だけを持つ AssertionError に置き換える(from None で元の連鎖も切る)。失敗した assert は
    _assert_clean と同様に番号だけを出す。"""
    __tracebackhide__ = True
    try:
        return fn(*args, **kwargs)
    except Exception as e:  # noqa: BLE001  (種類名と最内フレームの位置だけ残して引数は捨てる)
        tb = e.__traceback__
        while tb is not None and tb.tb_next is not None:
            tb = tb.tb_next
        where = f" at {os.path.basename(tb.tb_frame.f_code.co_filename)}:{tb.tb_lineno}" if tb is not None else ""
        raise AssertionError(f"{getattr(fn, '__name__', fn)} が例外を出した: {type(e).__name__}{where}") from None


def _assert_clean(text: str):
    # このフレームをトレースバックから隠す。隠さないと pytest(既定の --tb=auto/long)が失敗時に
    # 引数 text の中身を表示し、公開 CI ログに禁止語が出る(2026-10-12 PR-A のレビュー指摘)。
    __tracebackhide__ = True
    found = _call(_found_indices, text)
    assert found == [], f"禁止語が残っている: FORBIDDEN_CONTENT{found}"


# ---------------------------------------------------------------- mask_forbidden

def test_mask_replaces_exact_word():
    out = _call(wg.mask_forbidden, f"前 {WORD} 後")
    _assert_clean(out)
    assert wg.MASK in out
    assert out.startswith("前 ") and out.endswith(" 後")


def test_mask_is_case_insensitive():
    out = _call(wg.mask_forbidden, f"x {WORD.upper()} y {WORD.lower()} z")
    _assert_clean(out)
    assert out.count(wg.MASK) == 2


def test_mask_handles_fullwidth_spelling():
    out = _call(wg.mask_forbidden, f"全角 {_fullwidth(WORD)} 表記")
    _assert_clean(out)
    assert wg.MASK in out


def test_mask_handles_every_forbidden_word():
    text = "\n".join(f"- {w} の件" for w in FORBIDDEN_CONTENT)
    out = _call(wg.mask_forbidden, text)
    _assert_clean(out)
    assert out.count(wg.MASK) >= len(FORBIDDEN_CONTENT)


def test_mask_leaves_clean_text_unchanged():
    text = "沖縄企業のミカタ: 制度 143 件、締切の約1か月前からアラート。kakei-crm へ移設。"
    assert _call(wg.mask_forbidden, text) == text


def test_mask_keeps_surrounding_text_byte_for_byte():
    """丸数字・全角括弧・全角英数など、禁止語の外側は正規化で変えない(①→1 のような変化を起こさない)。"""
    before = "ルール8②(全角)Ａ案 "
    after = " ③ＫＰＩ"
    out = _call(wg.mask_forbidden, before + _fullwidth(WORD) + after)
    _assert_clean(out)  # 先に語が残っていないことを番号だけで確かめる(以降の比較で out が表示されても語は出ない)
    same = out == before + wg.MASK + after
    assert same, f"外側の文が変わった: 長さ {len(out)} / 印の数 {out.count(wg.MASK)}"


def test_mask_removes_zero_width_split_spelling_from_inputs():
    """ゼロ幅スペースで分断した書き方も、材料の段階でマスクする(書式文字を先に落とすため)。"""
    out = _call(wg.mask_forbidden, f"件名: {_zero_width(WORD)} の是正")
    _assert_clean(out)
    assert wg.MASK in out and "\u200b" not in out


# ---------------------------------------------------------------- find_forbidden

def test_find_returns_none_for_clean_text():
    assert _call(wg.find_forbidden, "今週は大きな進展なし。制度 143 件。") is None


@pytest.mark.parametrize(
    "variant",
    [
        lambda w: w,
        lambda w: w.upper(),
        lambda w: _fullwidth(w),
        lambda w: _zero_width(w),
        lambda w: w[:3] + "\u00ad" + w[3:],  # ソフトハイフン
    ],
    ids=["raw", "upper", "fullwidth", "zero-width", "soft-hyphen"],
)
def test_find_detects_spelling_variants(variant):
    hit = _call(wg.find_forbidden, f"行1\n行2 {variant(WORD)} 続き")
    assert hit is not None
    idx, pos, how = hit
    # 失敗時に hit の中身(将来、文の抜粋を返す変更が入ると禁止語を含み得る)を表示しないよう、真偽値に畳んでから assert する
    idx_ok = idx == 0
    pos_ok = isinstance(pos, int) and pos > 0
    how_ok = isinstance(how, str) and bool(how)
    assert idx_ok, "番号が 0 でない"
    assert pos_ok, "位置が正の整数でない"
    assert how_ok, "検査名が空"


def test_find_reports_index_of_other_words():
    for i, w in enumerate(FORBIDDEN_CONTENT):
        hit = _call(wg.find_forbidden, f"a {w} b")
        assert hit is not None and hit[0] == i, (i, hit[0] if hit else None)


# ---------------------------------------------------------------- build_prompt

def _changes(**over):
    base = {"log": "abc 2026-10-05 docs: x", "changed_files": ["docs/a.md"], "queue_diff": "", "latest_report": ""}
    base.update(over)
    return base


def test_build_prompt_masks_commit_log():
    p = _call(wg.build_prompt, _changes(log=f"abc 2026-10-05 docs: {WORD} の是正"), "2026-W41")
    _assert_clean(p)
    assert wg.MASK in p


def test_build_prompt_masks_queue_diff_and_report():
    p = _call(wg.build_prompt,
        _changes(queue_diff=f"+ {WORD.lower()} を移設", latest_report=f"レポ {_fullwidth(WORD)}"),
        "2026-W41",
    )
    _assert_clean(p)
    template_marks = _call(wg.build_prompt, _changes(), "2026-W41").count(wg.MASK)  # 定型文の説明行にある印は数えない
    assert p.count(wg.MASK) == template_marks + 2


def test_build_prompt_masks_changed_file_names():
    p = _call(wg.build_prompt, _changes(changed_files=[f"docs/{WORD}_memo.md"]), "2026-W41")
    _assert_clean(p)


def test_build_prompt_template_itself_is_clean():
    _assert_clean(_call(wg.build_prompt, _changes(), "2026-W41"))


# ---------------------------------------------------------------- main (fail-closed)

@pytest.fixture
def isolated(monkeypatch, tmp_path):
    out_dir = tmp_path / "学び"
    monkeypatch.setattr(wg, "OUT_DIR", str(out_dir))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "dummy-for-test")
    monkeypatch.setattr(wg, "collect_changes", lambda days=7: _changes())
    return out_dir


def _run_main(monkeypatch, argv):
    monkeypatch.setattr(sys, "argv", ["weekly_gakubi.py", *argv])
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = _call(wg.main)
    return rc, buf.getvalue()


def test_main_refuses_to_write_when_output_has_forbidden_word(isolated, monkeypatch):
    monkeypatch.setattr(wg, "summarize", lambda prompt: (f"- 決定: {WORD} を移設", "test-model"))
    rc, out = _run_main(monkeypatch, [])
    assert rc == 1
    assert not isolated.exists() or not list(isolated.iterdir())
    _assert_clean(out)
    assert "::error::" in out
    assert "FORBIDDEN_CONTENT[0]" in out


def test_main_dry_run_does_not_print_forbidden_output(isolated, monkeypatch):
    monkeypatch.setattr(wg, "summarize", lambda prompt: (f"- 決定: {WORD.upper()} を移設\n- 他の行", "test-model"))
    rc, out = _run_main(monkeypatch, ["--dry-run"])
    assert rc == 1
    _assert_clean(out)
    assert "他の行" not in out  # 本文は一切出さない(位置番号のみ)
    assert "::error::" in out


def test_main_error_line_has_position_only(isolated, monkeypatch):
    monkeypatch.setattr(wg, "summarize", lambda prompt: (f"- 先頭\n- {WORD} の件", "test-model"))
    rc, out = _run_main(monkeypatch, ["--dry-run"])
    assert rc == 1
    _assert_clean(out)
    err = [l for l in out.splitlines() if l.startswith("::error::")]
    assert len(err) == 1
    assert "位置" in err[0] and any(ch.isdigit() for ch in err[0])


def test_main_dry_run_prints_clean_note(isolated, monkeypatch):
    monkeypatch.setattr(wg, "summarize", lambda prompt: ("- 今週は大きな進展なし", "test-model"))
    rc, out = _run_main(monkeypatch, ["--dry-run"])
    assert rc == 0
    assert "今週は大きな進展なし" in out
    assert not isolated.exists()


def test_main_writes_clean_note(isolated, monkeypatch):
    monkeypatch.setattr(wg, "summarize", lambda prompt: ("- 今週は大きな進展なし", "test-model"))
    rc, out = _run_main(monkeypatch, [])
    assert rc == 0
    files = list(isolated.iterdir())
    assert len(files) == 1
    assert "今週は大きな進展なし" in files[0].read_text(encoding="utf-8")


def test_main_prompt_sent_to_model_is_masked(isolated, monkeypatch):
    seen = {}

    def fake_summarize(prompt):
        seen["prompt"] = prompt
        return "- ok", "test-model"

    monkeypatch.setattr(wg, "collect_changes", lambda days=7: _changes(log=f"abc 2026-10-05 docs: {WORD}"))
    monkeypatch.setattr(wg, "summarize", fake_summarize)
    rc, _ = _run_main(monkeypatch, ["--dry-run"])
    assert rc == 0
    _assert_clean(seen["prompt"])


# ---------------------------------------------------------------- self-test(ワークフローが生成前に毎回走らせる)

def test_self_test_covers_forbidden_guard(monkeypatch):
    """self_test は正例(禁止語なし→通る)と負例(禁止語あり→止まる)を含む。"""
    calls = []
    real = wg.find_forbidden

    def spy(text):
        calls.append(text)
        return real(text)

    monkeypatch.setattr(wg, "find_forbidden", spy)
    buf = io.StringIO()
    with redirect_stdout(buf):
        _call(wg.self_test)
    assert "self-test OK" in buf.getvalue()
    results = [real(t) for t in calls]
    assert any(r is None for r in results) and any(r is not None for r in results)
