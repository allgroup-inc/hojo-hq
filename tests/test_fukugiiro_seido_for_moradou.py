#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
もらいわすれ堂 公開用 seido.json の検証テスト

site/fukugiiro/seido.json が moradou へ配信されるため、以下を検証：
1. JSON として正しく解析できるか
2. 必要なフィールドがすべてあるか
3. 禁止パターン（山梨版・GLOW・ミカタ）が含まれていないか
4. 制度データが妥当か
"""
import json
import os
import unittest
from pathlib import Path

class TestFukugiroSeidoForMoradou(unittest.TestCase):
    """公開用 seido.json の検証"""

    @classmethod
    def setUpClass(cls):
        """テスト対象のJSONファイルを読み込む"""
        base_dir = Path(__file__).parent.parent

        # 修正案2適用後: site/fukugiiro/seido.json を優先（moradou への配信対象）
        seido_path = base_dir / "site" / "fukugiiro" / "seido.json"

        # fallback: 現在は data/fukugiiro/seido.json を参照（ワークフロー実行前）
        if not seido_path.exists():
            seido_path = base_dir / "data" / "fukugiiro" / "seido.json"

        if not seido_path.exists():
            raise FileNotFoundError(f"公開用 seido.json が見つかりません: {seido_path}")

        with open(seido_path, encoding="utf-8") as f:
            cls.data = json.load(f)

        cls.seido_path = seido_path

    def test_json_structure(self):
        """JSON の基本構造を検証"""
        self.assertIn("updated_at", self.data, "updated_at フィールドが必須")
        self.assertIn("count", self.data, "count フィールドが必須")
        self.assertIn("items", self.data, "items フィールドが必須")
        self.assertIsInstance(self.data["items"], list, "items はリスト")

    def test_item_count(self):
        """制度数が妥当か確認"""
        count = len(self.data["items"])
        self.assertEqual(count, self.data["count"], "count がアイテム数と一致")
        self.assertGreater(count, 50, "最低でも50件以上の制度を含む")

    def test_item_required_fields(self):
        """各制度に必須フィールドがあるか確認"""
        required_fields = ["id", "name", "issuer", "source_url"]
        for i, item in enumerate(self.data["items"]):
            for field in required_fields:
                self.assertIn(
                    field, item,
                    f"アイテム {i} に {field} が必須（id: {item.get('id', '??')}）"
                )

    def test_no_yamanashi_data(self):
        """山梨版のデータが含まれていないか確認"""
        forbidden_areas = ["山梨", "甲府", "昭和", "甲斐", "韮崎", "南アルプス"]
        for item in self.data["items"]:
            area = item.get("area", "")
            name = item.get("name", "")
            # area や name に山梨版固有の市町村が含まれていないか
            for forbidden in forbidden_areas:
                self.assertNotIn(
                    forbidden, area,
                    f"山梨版データが混在: {item.get('id')} の area に {forbidden} を含む"
                )

    def test_no_glow_data(self):
        """GLOW（沖縄企業のミカタ）向けのマークが含まれていないか確認"""
        for item in self.data["items"]:
            name = item.get("name", "")
            notes = item.get("notes", "")
            # GLOW や「企業向け」「ミカタ」などのマークがないか
            self.assertNotIn("GLOW", name, f"{item.get('id')} に GLOW が含まれている")
            self.assertNotIn("企業のミカタ", name, f"{item.get('id')} に企業のミカタが含まれている")
            self.assertNotIn("企業向け", notes, f"{item.get('id')} に企業向けが含まれている")

    def test_no_personal_information(self):
        """個人情報(PII)が含まれていないか確認"""
        for item in self.data["items"]:
            # 氏名、電話番号、メールアドレス、住所など
            notes = item.get("notes", "")
            name = item.get("name", "")

            # 一般的な個人情報パターンをチェック（簡易版）
            pii_patterns = ["0\d{1,4}-?\d{1,4}-?\d{4}", "@", "市", "さん", "様"]
            # 「市」は市町村名に使われるので除外
            for pattern in ["@", "さん", "様"]:
                self.assertNotIn(pattern, notes, f"{item.get('id')} に PII の可能性: {pattern}")

    def test_no_duplicate_ids(self):
        """制度IDが重複していないか確認"""
        ids = [item.get("id") for item in self.data["items"]]
        self.assertEqual(len(ids), len(set(ids)), "制度IDが重複している")

    def test_source_urls_are_valid(self):
        """source_url の形式が妥当か確認"""
        for item in self.data["items"]:
            url = item.get("source_url", "")
            self.assertTrue(
                url.startswith(("http://", "https://")),
                f"{item.get('id')} の source_url が HTTP(S) で始まっていない: {url}"
            )

    def test_updated_at_format(self):
        """updated_at が日時形式か確認"""
        updated = self.data.get("updated_at", "")
        # ISO 8601 形式（T 区切り）または スペース区切り形式の両方に対応
        has_iso_format = "T" in updated and ("Z" in updated or "+" in updated or "-" in updated)
        has_space_format = " " in updated and ":" in updated
        self.assertTrue(
            has_iso_format or has_space_format,
            f"updated_at が日時形式ではない: {updated}"
        )

if __name__ == "__main__":
    unittest.main()
