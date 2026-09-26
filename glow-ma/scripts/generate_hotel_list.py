#!/usr/bin/env python3
"""
沖縄県ホテル・宿泊施設リスト自動生成スクリプト
- 目的: M&A対象になりやすい業態(ホテル・観光)の企業リスト作成を自動化
- 方針: 公的データ・公式サイトのみ使用。推測は禁止。電話番号確認済みのみ記載
- 対象: 本島(沖縄本島)のみ。離島(石垣・宮古など)は除外
"""

import csv
import sys
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import List, Optional
import os

@dataclass
class Hotel:
    """ホテル企業情報"""
    会社名: str
    法人番号: str
    業種: str
    規模: str  # 客室数など
    代表者名: str
    代表者年齢: str
    所在地: str
    電話番号: str
    ランク: str  # A/B/C
    流入ルート: str = "④開拓架電"
    業態メモ: str = ""
    出典: str = ""

class HotelListGenerator:
    """ホテルリスト生成ツール"""

    RANK_RULES = {
        # 客室数 100室以上 → A
        # 複数施設運営の地場運営会社 → A
        "A": "客室100室以上、または複数施設を運営する地場運営会社",
        # 客室数 30-99室 → B
        "B": "客室30〜99室",
        # 客室数 30室未満、または規模情報なし → C
        "C": "客室30室未満、または規模情報が確認できない",
    }

    def __init__(self, output_dir: str = "."):
        """
        Args:
            output_dir: CSVを出力するディレクトリ
        """
        self.output_dir = output_dir
        self.hotels: List[Hotel] = []

    def assign_rank(self, rooms: Optional[int], facility_count: int = 1,
                   is_regional_independent: bool = False) -> str:
        """
        客室数と施設数からランクを判定

        Args:
            rooms: 客室数(Noneの場合は情報なし)
            facility_count: 施設数(複数施設は加点)
            is_regional_independent: 地場資本・独立系フラグ

        Returns:
            ランク (A/B/C)
        """
        # 複数施設で地場運営 → A
        if facility_count > 1 and is_regional_independent:
            return "A"

        # 客室数に基づく判定
        if rooms is None:
            return "C"  # 情報なし
        elif rooms >= 100:
            return "A"
        elif 30 <= rooms <= 99:
            return "B"
        else:  # rooms < 30
            return "C"

    def add_hotel_from_dict(self, data: dict, rank: str = "C",
                           source: str = "手動入力") -> None:
        """辞書からホテル情報を追加"""
        hotel = Hotel(
            会社名=data.get("company_name", ""),
            法人番号=data.get("corporate_number", ""),
            業種=data.get("industry", "宿泊業"),
            規模=data.get("scale", ""),
            代表者名=data.get("rep_name", ""),
            代表者年齢=data.get("rep_age", ""),
            所在地=data.get("address", ""),
            電話番号=data.get("phone", ""),
            ランク=rank,
            流入ルート="④開拓架電",
            業態メモ=data.get("notes", ""),
            出典=source,
        )

        # 検証: 電話番号は必須
        if not hotel.電話番号:
            raise ValueError(f"電話番号が未設定: {hotel.会社名}")

        self.hotels.append(hotel)

    def write_csv(self, filename: Optional[str] = None) -> str:
        """
        CSVファイルに書き込み

        Args:
            filename: 出力ファイル名(省略時は日付ベース)

        Returns:
            出力ファイルパス
        """
        if not filename:
            today = datetime.now().strftime("%Y%m%d")
            filename = f"GLOW法人リスト_ホテル_本島_{today}.csv"

        filepath = os.path.join(self.output_dir, filename)

        # ImportRunner.gs が期待する列順
        fieldnames = [
            "会社名",
            "法人番号",
            "業種",
            "規模",
            "代表者名",
            "代表者年齢",
            "所在地",
            "電話番号",
            "ランク",
            "流入ルート",
            "業態メモ",
            "出典",
        ]

        with open(filepath, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for hotel in sorted(self.hotels, key=lambda h: h.ランク):
                writer.writerow(asdict(hotel))

        print(f"✓ {len(self.hotels)}件のホテルリストを出力: {filepath}")
        return filepath

    def print_summary(self) -> None:
        """サマリーを表示"""
        rank_counts = {}
        for hotel in self.hotels:
            rank = hotel.ランク
            rank_counts[rank] = rank_counts.get(rank, 0) + 1

        print(f"\n📊 ホテルリスト統計:")
        print(f"  総件数: {len(self.hotels)}件")
        for rank in ["A", "B", "C"]:
            count = rank_counts.get(rank, 0)
            rule = self.RANK_RULES.get(rank, "")
            print(f"  ランク{rank}: {count}件 ({rule})")

        # 出典の内訳
        sources = {}
        for hotel in self.hotels:
            src = hotel.出典
            sources[src] = sources.get(src, 0) + 1

        print(f"\n📋 データ源の内訳:")
        for src, count in sorted(sources.items(), key=lambda x: -x[1]):
            print(f"  {src}: {count}件")


def main():
    """
    使用例:
    ```python
    generator = HotelListGenerator(output_dir=".")

    # サンプルデータを追加
    generator.add_hotel_from_dict({
        "company_name": "沖縄ホテル株式会社",
        "corporate_number": "1234567890123",
        "industry": "宿泊業(ホテル)",
        "scale": "100室",
        "rep_name": "山田太郎",
        "rep_age": "55",
        "address": "沖縄県那覇市...",
        "phone": "098-123-4567",
        "notes": "本島最大級の独立系ホテル",
    }, rank="A", source="公式サイト")

    # CSV出力
    filepath = generator.write_csv()
    generator.print_summary()
    ```
    """
    print("ホテルリスト自動生成スクリプト")
    print("=" * 50)
    print("\n使用方法:")
    print("1. このスクリプトをインポート")
    print("2. HotelListGeneratorのインスタンスを作成")
    print("3. add_hotel_from_dict()でホテル情報を追加")
    print("4. write_csv()でCSVに出力")
    print("\n詳細は docstring を参照してください。")


if __name__ == "__main__":
    main()
