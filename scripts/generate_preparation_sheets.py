#!/usr/bin/env python3
"""
もらいわすれ堂：準備シート自動生成スクリプト

seido.json の制度データから、申請準備シート（Markdown/PDF/Excel）を自動生成。
月1回の更新に対応し、メタデータで生成日時を記録。
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

try:
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
    from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False


class PreparationSheetGenerator:
    """seido.json から準備シートを生成するクラス"""

    def __init__(self, seido_path: Path, output_dir: Path):
        self.seido_path = seido_path
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

        with open(seido_path, 'r', encoding='utf-8') as f:
            self.seido_data = json.load(f)

    def generate_all(self) -> None:
        """全制度の準備シートを生成"""
        metadata = {
            "generated_at": datetime.now().isoformat(),
            "total_sheets": 0,
            "version": "1.0",
            "items": []
        }

        for item in self.seido_data.get("items", []):
            try:
                self.generate_sheet(item)
                metadata["total_sheets"] += 1
                metadata["items"].append({
                    "id": item.get("id"),
                    "name": item.get("name"),
                    "generated": True
                })
            except Exception as e:
                print(f"❌ Error generating sheet for {item.get('name')}: {e}", file=sys.stderr)
                metadata["items"].append({
                    "id": item.get("id"),
                    "name": item.get("name"),
                    "generated": False,
                    "error": str(e)
                })

        # メタデータを保存
        metadata_path = self.output_dir / "metadata.json"
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        print(f"✅ Generated {metadata['total_sheets']} preparation sheets")
        print(f"📋 Metadata saved to {metadata_path}")

    def generate_sheet(self, item: Dict) -> None:
        """1つの制度の準備シートを生成"""
        item_id = item.get("id", "unknown")
        item_name = item.get("name", "Unknown")

        # ファイル名を生成
        safe_name = self._sanitize_filename(item_name)

        # Markdown 版を生成（常に生成）
        md_path = self.output_dir / f"{item_id}_{safe_name}.md"
        md_content = self._generate_markdown(item)
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(md_content)
        print(f"✅ Generated: {md_path}")

        # PDF 版を生成（reportlab がある場合）
        if HAS_REPORTLAB:
            pdf_path = self.output_dir / f"{item_id}_{safe_name}.pdf"
            self._generate_pdf(item, pdf_path)
            print(f"✅ Generated: {pdf_path}")

    def _generate_markdown(self, item: Dict) -> str:
        """Markdown 形式の準備シートを生成"""
        name = item.get("name", "Unknown")
        area = item.get("area", "全国")
        deadline = item.get("deadline", "確認してください")
        target = item.get("target_household", "確認してください")
        how_to_apply = item.get("how_to_apply", "確認してください")
        source_url = item.get("source_url", "")

        # 相談窓口情報（seido.json にない場合はプレースホルダー）
        consultation = item.get("consultation_window", {})

        # 必要書類（seido.json にない場合は汎用リスト）
        required_docs = item.get("required_documents", [
            "申請書類一式",
            "本人確認書類（マイナンバーカードまたは運転免許証）",
            "その他（自治体に確認してください）"
        ])

        md = f"""# 【{name}】申請準備シート

**生成日**: {datetime.now().strftime('%Y年%m月%d日')}
**出典**: {source_url or '公式サイト'}

---

## 📋 制度の基本情報

| 項目 | 内容 |
|---|---|
| **制度名** | {name} |
| **実施自治体** | {area} |
| **申請方法** | {how_to_apply} |
| **申請期限** | {deadline} |

---

## 🎯 対象者

{target}

---

## 📝 必要書類チェックリスト

実際に申請する際に必要な書類をご確認ください。

"""
        for doc in required_docs:
            md += f"- [ ] {doc}\n"

        md += f"""
---

## 📞 相談窓口

制度についての詳細や、書類の集め方がわからない場合は、以下の窓口にお問い合わせください。

"""

        if consultation:
            md += f"""| 項目 | 内容 |
|---|---|
| **窓口** | {consultation.get('municipality', area)} {consultation.get('department', '')} |
| **電話** | {consultation.get('phone', '確認してください')} |
| **営業時間** | {consultation.get('hours', '平日 9:00-17:00')} |
"""
        else:
            md += f"""| 項目 | 内容 |
|---|---|
| **窓口** | {area} の担当部局 |
| **電話** | 各自治体ホームページで確認してください |
| **営業時間** | 平日 9:00-17:00（目安） |
"""

        md += """
---

## ⏰ 申請ステップ

### Week 1: 確認・相談
1. 相談窓口に電話して、「この制度は自分に該当するか？」を確認
2. 必要書類を確認
3. 書類収集の方法を確認

### Week 2-3: 書類作成・準備
1. 必要書類を集める
2. 申請書に記入する
3. 不明な点があれば再度相談窓口に確認

### Week 4: 申請
1. 書類が揃ったことを確認
2. 相談窓口に直接提出、または郵送
3. 受付票をもらう（郵送の場合は控えを保管）

### その後
- 審査期間を自治体に確認
- 結果通知を待つ
- 受給

---

## 💡 ワンポイントアドバイス

- **相談窓口に電話するときのコツ**: 「この制度は自分に該当しますか？」「必要な書類は何ですか？」の2点を先に確認すると、スムーズです
- **書類が多い場合**: 1回に全部集めようとせず、相談窓口で「どれから集めたらいいか」の優先順位を聞くのがおすすめ
- **期限に注意**: 申請締切がある制度は、早めに行動することをおすすめします

---

## 📌 その他のリソース

- **制度の詳細**: [公式サイト]({source_url})
- **もらいわすれ堂で診断し直す**: https://moradou.jp/shindan
- **LINE相談**: もらいわすれ堂公式アカウント

---

**このシートは {datetime.now().strftime('%Y年%m月%d日')} 時点の情報を基に生成されています。**
**最新情報は公式サイトでご確認ください。**
"""
        return md

    def _generate_pdf(self, item: Dict, output_path: Path) -> None:
        """PDF 形式の準備シートを生成（reportlab 使用）"""
        if not HAS_REPORTLAB:
            return

        name = item.get("name", "Unknown")

        # PDF ドキュメント作成
        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=A4,
            title=f"{name} 申請準備シート"
        )

        story = []
        styles = getSampleStyleSheet()

        # タイトル
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=16,
            textColor=(0, 51, 92),  # ネイビー
            spaceAfter=12,
            alignment=TA_CENTER
        )
        story.append(Paragraph(f"【{name}】申請準備シート", title_style))
        story.append(Spacer(1, 0.3 * inch))

        # 基本情報セクション
        section_style = ParagraphStyle(
            'SectionTitle',
            parent=styles['Heading2'],
            fontSize=12,
            textColor=(0, 51, 92),
            spaceAfter=6
        )
        story.append(Paragraph("📋 制度の基本情報", section_style))

        info_text = f"""
        <b>制度名:</b> {item.get('name', '')}<br/>
        <b>実施自治体:</b> {item.get('area', '全国')}<br/>
        <b>申請方法:</b> {item.get('how_to_apply', '')}<br/>
        <b>対象者:</b> {item.get('target_household', '')}
        """
        story.append(Paragraph(info_text, styles['Normal']))
        story.append(Spacer(1, 0.2 * inch))

        # 必要書類
        story.append(Paragraph("📝 必要書類チェックリスト", section_style))
        required_docs = item.get("required_documents", [
            "申請書類一式",
            "本人確認書類",
            "その他（自治体に確認）"
        ])
        docs_text = "<br/>".join([f"☐ {doc}" for doc in required_docs])
        story.append(Paragraph(docs_text, styles['Normal']))

        # ドキュメント生成
        doc.build(story)

    def _sanitize_filename(self, name: str) -> str:
        """ファイル名として安全な文字列に変換"""
        # Windows/Linux の両方で問題のないファイル名に
        invalid_chars = '<>:"/\\|?*'
        safe_name = name
        for char in invalid_chars:
            safe_name = safe_name.replace(char, '')
        return safe_name.strip()


def main():
    """メイン処理"""
    seido_path = Path(__file__).parent.parent / "data" / "fukugiiro" / "seido.json"
    output_dir = Path(__file__).parent.parent / "data" / "fukugiiro" / "preparation_sheets"

    if not seido_path.exists():
        print(f"❌ Error: seido.json not found at {seido_path}", file=sys.stderr)
        sys.exit(1)

    print(f"📂 Output directory: {output_dir}")
    print(f"📋 Reading from: {seido_path}\n")

    generator = PreparationSheetGenerator(seido_path, output_dir)
    generator.generate_all()

    print(f"\n✨ All preparation sheets generated successfully!")


if __name__ == "__main__":
    main()
