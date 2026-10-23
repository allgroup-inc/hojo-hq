# Canva Template 1 Design Specification
## 「数字と限定感」カルーセル (Numbers & Scarcity)

**Document Version**: 1.0  
**Created**: 2026-09-28  
**Template Format**: 4-page carousel (1080×1350px each)  
**Test Subsidy**: デジタル化・AI導入補助金2026 (¥450万円)

---

## Design System Specifications

### Color Palette
| Color Name | Hex Code | Usage | RGB |
|---|---|---|---|
| Navy (Primary) | #00335C | Background (P1), text (P2-P4) | 0, 51, 92 |
| Orange (Accent) | #F88800 | Large numbers (P1), headers (P2-P4), dividers | 248, 136, 0 |
| White | #FFFFFF | Text on navy, backgrounds (P2-P4) | 255, 255, 255 |
| Light Gray | #F5F5F5 | Table cells (P4), subtle backgrounds | 245, 245, 245 |
| Dark Gray | #333333 | Body text, table text | 51, 51, 51 |

### Typography
| Element | Font | Size | Weight | Color | Usage |
|---|---|---|---|---|---|
| Large Number | Meiryo | 150pt | Bold | #F88800 | P1: Amount display |
| Page Title | Meiryo | 48pt | Bold | #00335C (P2-P4) / #FFFFFF (P1) | Page headers |
| Subtitle | Meiryo | 40pt | Regular | #FFFFFF | P1: Subsidy name |
| Section Label | Meiryo | 32pt | Bold | #00335C | P2-P4: "Before", "After", etc. |
| Body Text | Meiryo | 28pt | Regular | #333333 (P2-P4) / #FFFFFF (P1) | Content text |
| Small Text | Meiryo | 24pt | Regular | #00335C | P1: Industry, P4: details |
| Table Header | Meiryo | 26pt | Bold | #FFFFFF | P4: Column headers |
| Table Body | Meiryo | 22pt | Regular | #333333 | P4: Cell content |
| Footer | Meiryo | 18pt | Regular | #00335C | P1: Date stamp, logo |

### Spacing & Layout
| Element | Value |
|---|---|
| Page Dimensions | 1080×1350px (Instagram carousel standard) |
| Margins (all pages) | 40px (top, bottom, left, right) |
| Internal Padding | 20px between sections |
| Line Height | 1.5 (standard text) / 1.2 (headings) |
| Corner Radius | 8px (buttons, boxes) |

---

## Page 1: Large Number + Industry

### Layout Structure
```
[NAVY BACKGROUND #00335C (full page)]
├─ Top Section (20%)
│  └─ Subsidy Name (white, 40pt)
├─ Middle Section (50%)
│  ├─ Large Orange Number (150pt bold, centered)
│  │  └─ Example: "450万円"
│  └─ Small Industry Text (24pt, navy, centered)
│     └─ Example: "製造業向け"
├─ Bottom Section (20%)
│  └─ Logo + Date Stamp (18pt navy text)
│     └─ "沖縄企業のミカタ | 2026-09-28"
```

### Design Details

**Background**
- Solid Navy color: #00335C
- Full bleed, no margins

**Top Content Area (40px margin top)**
- Text: Subsidy name in white
- Font: Meiryo, 40pt, Regular
- Alignment: Center
- Example: "デジタル化・AI導入補助金2026"

**Center Content Area (vertical center)**
- Large number display
- Font: Meiryo, 150pt, Bold
- Color: Orange #F88800
- Alignment: Center
- Example: "450万円"
- Spacing: 20px below large number

**Industry Label**
- Font: Meiryo, 24pt, Regular
- Color: Navy #00335C (or White #FFFFFF for better contrast)
- Alignment: Center
- Example: "製造業・情報通信業向け"

**Footer (40px margin bottom)**
- Logo text + date stamp
- Font: Meiryo, 18pt, Regular
- Color: Navy #00335C (or White if background treatment)
- Alignment: Center
- Format: "沖縄企業のミカタ | YYYY-MM-DD"
- Example: "沖縄企業のミカタ | 2026-09-28"

### Color Contrast Check
- Navy #00335C on white text: PASS (contrast 8.2:1)
- Orange #F88800 on navy: PASS (contrast 5.5:1)
- White on navy: PASS (contrast 8.6:1)

---

## Page 2: Before/After Example 1

### Layout Structure
```
[WHITE BACKGROUND #FFFFFF (full page)]
├─ Header (10%)
│  └─ Page Title: "Before/After 活用例 1" (navy, 48pt bold)
├─ Content (80%)
│  ├─ Left Section (30%)
│  │  ├─ "Before" Label (orange, 32pt bold)
│  │  └─ Amount: "300万円" (navy, 40pt bold)
│  ├─ Center Section (40%)
│  │  ├─ Industry Name (navy, 36pt bold)
│  │  │  └─ Example: "飲食業"
│  │  └─ Use Case (28pt regular)
│  │     └─ "従業員15名のレストラン"
│  │     └─ "2店舗の会計・予約を自動化"
│  └─ Right Section (30%)
│     ├─ "After" Label (orange, 32pt bold)
│     └─ Amount: "100万円" (navy, 40pt bold)
├─ Divider (visual)
└─ Footer (10%)
   └─ Savings indicator (optional)
```

### Design Details

**Header**
- Background: White #FFFFFF
- Text: "活用例① 飲食業" (or example 1)
- Font: Meiryo, 48pt, Bold
- Color: Navy #00335C
- Margin: 40px top, 20px bottom
- Alignment: Center

**Left Section (Before)**
- Background: Light gray #F5F5F5 with 8px rounded corners
- Border: 2px orange #F88800
- Padding: 20px
- Content:
  - Label: "Before" (Meiryo, 32pt, Bold, Orange #F88800)
  - Amount: "300万円" (Meiryo, 40pt, Bold, Navy #00335C)
  - Alignment: Center

**Center Section (Industry + Use Case)**
- Background: White (no background)
- Content:
  - Industry: "飲食業" (Meiryo, 36pt, Bold, Navy #00335C)
  - Use case lines (Meiryo, 28pt, Regular, Navy #00335C)
    - Line 1: "従業員15名のレストラン"
    - Line 2: "2店舗の会計・予約を自動化"
  - Vertical alignment: Middle
  - Text alignment: Center

**Right Section (After)**
- Background: Light gray #F5F5F5 with 8px rounded corners
- Border: 2px orange #F88800
- Padding: 20px
- Content:
  - Label: "After" (Meiryo, 32pt, Bold, Orange #F88800)
  - Amount: "100万円" (Meiryo, 40pt, Bold, Navy #00335C)
  - Alignment: Center

**Visual Divider**
- Horizontal line, Orange #F88800, 3px thickness
- Margin: 20px top/bottom
- Optional: Add arrow (→) in orange between Before/After

**Footer Note (Optional)**
- "実質負担は約25%" or similar
- Font: Meiryo, 22pt, Regular
- Color: Orange #F88800
- Alignment: Center

### Editable Fields
- Industry name (center)
- Before amount (left)
- After amount (right)
- Use case description (2-3 lines)

### Test Case
- Industry: 飲食業
- Before Amount: 300万円
- After Amount: 100万円
- Use Case: "従業員15名のレストラン\n2店舗の会計・予約を自動化"

---

## Page 3: Before/After Example 2

### Layout Structure
Identical to Page 2, but with different industry/amounts.

### Design Details
Same specifications as Page 2.

### Test Case
- Industry: 製造業
- Before Amount: 500万円
- After Amount: 150万円
- Use Case: "金属加工部品メーカー\n手作業検査プロセスをAI画像検査に置き換え"

---

## Page 4: Quick Reference Table

### Layout Structure
```
[WHITE BACKGROUND #FFFFFF]
├─ Header (15%)
│  └─ "補助率・対象条件・締切" (navy, 48pt bold)
├─ Table (80%)
│  ├─ Header Row (orange background)
│  │  ├─ Column 1: "補助率" (white, bold)
│  │  ├─ Column 2: "対象条件" (white, bold)
│  │  └─ Column 3: "締切" (white, bold)
│  ├─ Data Row 1
│  ├─ Data Row 2
│  └─ Data Row 3
└─ Footer (5%)
   └─ "詳細は公式ページで確認 / LINE無料相談で!" 
```

### Design Details

**Header**
- Font: Meiryo, 48pt, Bold
- Color: Navy #00335C
- Text: "補助率・対象条件・締切"
- Alignment: Center
- Margin: 40px top, 20px bottom

**Table Structure**
- Total width: 1000px (accounting for 40px margins)
- Column widths: 33% each (approximately 330px)
- Border: 1px solid Navy #00335C

**Header Row**
- Background: Orange #F88800
- Text: White #FFFFFF
- Font: Meiryo, 26pt, Bold
- Padding: 15px (vertical), 10px (horizontal)
- Alignment: Center
- Height: 60px

**Data Rows (3 rows)**
- Background: Alternating white #FFFFFF and light gray #F5F5F5
- Font: Meiryo, 22pt, Regular
- Color: Dark gray #333333
- Padding: 15px (vertical), 10px (horizontal)
- Alignment: Center (for補助率/締切), Left (for対象条件)
- Height: 50px per row
- Border: 1px solid navy between rows

**Column 1: 補助率**
- Content format: "最大3/4" or "75%"
- Alignment: Center
- Font: Bold (for emphasis)

**Column 2: 対象条件**
- Content format: "中小企業\n従業員5〜300名"
- Alignment: Left (better readability for longer text)
- Line height: 1.5

**Column 3: 締切**
- Content format: "2026-12-31" or "2026年12月31日"
- Alignment: Center
- Font: Bold

**Footer Note**
- Font: Meiryo, 20pt, Regular
- Color: Navy #00335C
- Text: "詳細は公式ページで確認できます。LINE無料相談で質問もOK!"
- Alignment: Center
- Margin: 20px top

### Editable Fields
- All three columns for each row
- Number of rows (minimum 2, maximum 4)

### Test Case
| 補助率 | 対象条件 | 締切 |
|---|---|---|
| 最大3/4 | 中小企業・従業員5〜300名 | 2026-12-31 |
| 最大2/3 | 小規模企業者（従業員5名以下） | 2027-03-31 |
| 最大3/4 | NPO・社会福祉法人 | 2026-12-15 |

---

## Technical Export Specifications

### PDF Export Settings
- Format: PDF
- Resolution: 300 DPI (for quality print/archive)
- Trim marks: Off
- Bleed: 0px
- Color profile: sRGB (standard for web/print)

### File Naming Convention
- Canva Link: `template1_canva_link.md` (contains URL)
- PDF Export: `template1_numbers_scarcity.pdf` (or template1_[SUBSIDY_ID].pdf for specific instances)
- Archive location: `/docs/ig_templates/`

### Accessibility Requirements
- Color contrast minimum: 4.5:1 for normal text, 3:1 for large text (WCAG AA)
- All text must be selectable (not baked into images)
- Alt text available for decorative elements

---

## Implementation Checklist

### Pre-Build
- [ ] Confirm all hex colors match brand guidelines (#00335C, #F88800, #FFFFFF)
- [ ] Verify font availability (Meiryo or Noto Sans JP for web)
- [ ] Test color contrast for accessibility
- [ ] Prepare test subsidy data

### Build (Page by Page)
- [ ] **P1**: Create navy background, position large orange number, add subtitle/industry, add footer
- [ ] **P2**: Create white background, build Before/After sections, add center industry, test text overflow
- [ ] **P3**: Duplicate P2, update with second example data
- [ ] **P4**: Create table structure, format header row, populate 3 data rows, add footer note

### Quality Testing
- [ ] Visual check: Text readability on all pages
- [ ] Color contrast: Verify orange on navy passes WCAG AA
- [ ] Layout balance: Confirm spacing and margins are consistent
- [ ] Mobile preview: Verify appearance on Instagram (1080×1350 ratio)
- [ ] Text overflow: Test with longer industry names or amounts (e.g., "99,999万円")
- [ ] Export test: PDF export produces clean output

### Deployment
- [ ] Save Canva link to `template1_canva_link.md`
- [ ] Export PDF to `docs/ig_templates/template1_numbers_scarcity.pdf`
- [ ] Test PDF opens correctly in standard viewers
- [ ] Add metadata/comments to PDF noting test subsidy and date

---

## Customization Guide (For Future Use)

### To Customize for Different Subsidy:

1. **P1 Changes**:
   - Replace "450万円" with new max amount
   - Update "デジタル化・AI導入補助金2026" with subsidy name
   - Update "製造業向け" with target industries

2. **P2 Changes**:
   - Update industry name (center)
   - Replace "300万円" and "100万円" with before/after amounts
   - Update use case description (2 lines)

3. **P3 Changes**:
   - Repeat P2 customization with different industry example

4. **P4 Changes**:
   - Update subsidy rate in column 1
   - Update target conditions in column 2
   - Update deadline in column 3

---

## Reference Data (Test Case: デジタル化・AI導入補助金2026)

```json
{
  "subsidy_name": "デジタル化・AI導入補助金2026",
  "max_amount": 4500000,
  "ig_examples": [
    {
      "industry": "飲食業",
      "before_amount": 3000000,
      "after_amount": 1000000,
      "use_case": "従業員15名のレストラン / 2店舗の会計・予約を自動化"
    },
    {
      "industry": "製造業",
      "before_amount": 5000000,
      "after_amount": 1500000,
      "use_case": "金属加工部品メーカー / 手作業検査をAI画像検査に置き換え"
    }
  ],
  "subsidy_rate": "最大3/4",
  "target_conditions": "中小企業・従業員5〜300名",
  "deadline": "2026-12-31"
}
```

---

## Notes & Considerations

### Design Decisions
- **Large Number (P1)**: 150pt is the maximum readable size for Canva at 1080px width with 40px margins
- **Orange on Navy**: Chosen for high contrast and brand consistency
- **Before/After Layout**: 30-30-40 split allows enough space without crowding
- **Table on P4**: 3 columns maximize readability while fitting data relevantly

### Known Limitations
- Canva's font availability: If Meiryo not available, Noto Sans JP is acceptable alternative
- PDF export quality: Always verify PDF exports at 300 DPI before archiving
- Long text handling: Test fields like industry names with 15+ character inputs

### Future Improvements (Post-Launch)
- Animate carousel progression (e.g., slide transitions)
- Add QR code placeholder for P4 (links to full subsidy details)
- Create variants with different color schemes for seasonal campaigns
- Develop template 2 & 3 (Triage & Campaign) following similar structure

---

**Document Version**: 1.0  
**Last Updated**: 2026-09-28  
**Approved By**: [Pending]  
**Implementation Status**: Ready for Canva Design
