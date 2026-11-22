# -*- coding: utf-8 -*-
"""note下書き生成の安全性試験（合成データ・外部通信なし・記録ファイルを触らない）。

確認すること:
- 外部AI（Anthropic）を呼ばない（--offline）
- 出力は --out-dir の中だけに書く。記録ファイルは更新しない
- 外部通信（ソケット）を開かない
- 秘密情報（APIキー）が出力に出ない
- 入力が無いときは、何も書かずに止まる
"""
import contextlib
import hashlib
import importlib
import io
import json
import os
import shutil
import socket
import sys
import tempfile
import unittest
from datetime import date, timedelta
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

FAKE_KEY = "sk-test-SECRET-DO-NOT-LEAK"


def _synthetic(today):
    far = (today + timedelta(days=90)).isoformat()
    near = (today + timedelta(days=10)).isoformat()
    items = [
        {"id": "t1", "name": "合成制度A", "issuer": "合成省", "deadline": far, "tag": "okinawa",
         "max_amount": 3000000, "status": "募集中", "target_area": "沖縄県", "employees": "制約なし"},
        {"id": "t2", "name": "合成制度B", "issuer": "合成庁", "deadline": far, "tag": "nationwide",
         "max_amount": 0, "status": "募集中", "target_area": "全国", "employees": "制約なし"},
        {"id": "t3", "name": "合成制度C", "issuer": "合成県", "deadline": near, "tag": "shokei",
         "max_amount": 500000, "status": "募集中", "target_area": "沖縄県", "employees": "制約なし"},
    ]
    return {"updated_at": "2026-01-01 00:00", "count": len(items), "items": items}


def _digest(path):
    if not os.path.exists(path):
        return "absent"
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


class OfflineGenerateNoteTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="note_offline_")
        self.work = os.path.join(self.tmp, "work")
        os.makedirs(self.work)
        self.data_path = os.path.join(self.work, "subsidies.json")
        with open(self.data_path, "w", encoding="utf-8") as f:
            json.dump(_synthetic(date.today()), f, ensure_ascii=False)
        # 記録ファイル（実物のパス）が変わっていないことを後で確かめる
        import generate_note as gn
        self.gn = importlib.reload(gn)
        self.real_snapshot = self.gn.SNAPSHOT_PATH
        self.real_archive = os.path.join(self.gn.BASE, "data", "gone_archive.json")
        self.before = {p: _digest(p) for p in (self.real_snapshot, self.real_archive)}
        self.out_dir = os.path.join(self.tmp, "out")
        self.real_out = os.path.join(self.gn.BASE, "posts", "note")  # 実際の下書きの場所
        self.repo_note_before = sorted(os.listdir(self.real_out)) if os.path.isdir(self.real_out) else []

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _run_main(self, argv):
        self.gn.DATA_PATH = self.data_path
        self.gn.SNAPSHOT_PATH = os.path.join(self.work, "snapshot.json")  # 合成の場所だけ
        buf = io.StringIO()
        with mock.patch.object(sys, "argv", ["generate_note.py"] + argv), \
             contextlib.redirect_stdout(buf):
            self.gn.main()
        return buf.getvalue()

    def test_ai_is_not_called_with_offline_even_if_key_set(self):
        # ANTHROPIC_API_KEY があっても、--offline では anthropic を読み込まない
        blocker = mock.MagicMock(side_effect=AssertionError("外部AIを呼んだ"))
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": FAKE_KEY}), \
             mock.patch.object(sys, "argv", ["generate_note.py", "--offline"]), \
             mock.patch.dict(sys.modules, {"anthropic": blocker}):
            self.gn = importlib.reload(self.gn)
            text = self.gn.ai_column({"total": 3, "new": 0, "gone": 0, "closing": 1})
        self.assertIn("AI編集長", text)
        blocker.assert_not_called()

    def test_writes_only_into_out_dir_and_no_network(self):
        def no_net(*a, **k):
            raise AssertionError("外部通信を開こうとした")
        with mock.patch.object(socket, "socket", side_effect=no_net), \
             mock.patch.object(socket, "create_connection", side_effect=no_net):
            out = self._run_main(["--offline", "--out-dir", self.out_dir])
        files = os.listdir(self.out_dir)
        self.assertEqual(len(files), 1, files)
        self.assertTrue(files[0].endswith(".md"))
        self.assertIn("生成しました", out)
        # 記録ファイルは一切変わっていない
        self.assertEqual(self.before, {p: _digest(p) for p in self.before})
        self.assertEqual(self.repo_note_before,
                         sorted(os.listdir(self.real_out)) if os.path.isdir(self.real_out) else [])

    def test_no_secret_in_output(self):
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": FAKE_KEY}):
            out = self._run_main(["--offline", "--out-dir", self.out_dir])
        self.assertNotIn(FAKE_KEY, out)
        for f in os.listdir(self.out_dir):
            with open(os.path.join(self.out_dir, f), encoding="utf-8") as fh:
                self.assertNotIn(FAKE_KEY, fh.read())

    def test_stops_without_writing_when_input_missing(self):
        self.gn.DATA_PATH = os.path.join(self.work, "missing.json")
        self.gn.SNAPSHOT_PATH = os.path.join(self.work, "snapshot.json")
        with mock.patch.object(sys, "argv", ["generate_note.py", "--offline", "--out-dir", self.out_dir]):
            with self.assertRaises((FileNotFoundError, OSError)):
                self.gn.main()
        self.assertFalse(os.path.isdir(self.out_dir) and os.listdir(self.out_dir))

    def test_offline_editor_note_has_no_banned_words(self):
        # 禁止語の検査はAIが書く後記に掛ける（免責文の「必ず原文で…」は設計どおりの固定文）
        text = self.gn.ai_column({"total": 3, "new": 0, "gone": 0, "closing": 1})
        for w in self.gn.BANNED_WORDS:
            self.assertNotIn(w, text)


if __name__ == "__main__":
    unittest.main()
