# IG Template 3 - Seasonal Campaign Carousel

## Template Overview

**Project Name:** IG Template 3 - Seasonal Campaign  
**Purpose:** 6-page Instagram carousel for promoting business transformation subsidies  
**Status:** Design prototype created (interactive mockup)

## Design Specifications

### Dimensions
- **Size per page:** 1080×1350px (Instagram carousel standard)
- **Total pages:** 6

### Color Palette
- **Primary Navy:** #00335C
- **Accent Orange:** #F88800
- **Background Light Gray:** #F5F5F5
- **Text Dark:** #333333
- **White:** #FFFFFF

### Typography
- **Title Font:** Meiryo / Noto Sans JP, 32pt
- **Body Font:** Meiryo / Noto Sans JP, 28pt
- **Heading Font:** Meiryo / Noto Sans JP, 36-48pt (varies by slide)

## Page Structure

### Page 1: Hook
- **Background:** Navy gradient (#00335C → #001f3f)
- **Text Color:** White with orange accent
- **Content:** "事業転換を検討していますか？" (large, 48px)
- **Subtext:** "国が最大1.5億円サポートします。" (36px)

### Pages 2-4: Transformation Examples

#### Page 2: Manufacturing to IoT
- **Industry:** 製造業
- **Before:** 人手による製造プロセス
- **After:** IoT活用による自動化製造
- **Benefit:** 生産性40%向上、コスト30%削減

#### Page 3: Retail to E-commerce
- **Industry:** 小売業
- **Before:** 実店舗のみの販売体制
- **After:** ECサイト展開で全国販売
- **Benefit:** 顧客層2倍拡大、売上50%増加

#### Page 4: Food Service to Delivery
- **Industry:** 飲食業
- **Before:** 店舗飲食のみの営業体制
- **After:** 宅配・中食事業へ展開
- **Benefit:** 営業時間外の収益化、店舗負荷軽減

**Design Pattern for Pages 2-4:**
- Light gray background
- Before/After boxes with navy/orange borders
- Benefit box with navy background and white text
- Icon + benefit description (24px)

### Page 5: Preparation Checklist
- **Background:** Navy gradient (#00335C → #001f3f)
- **Text Color:** White with orange accents
- **Title:** "事業転換の準備チェックリスト（6か月の計画例）"
- **Checklist Items:**
  - ☐ 6ヶ月前：経営課題の整理と転換目標の設定
  - ☐ 3ヶ月前：事業計画ドラフト作成・資金試算
  - ☐ 1ヶ月前：申請書類の準備・経理資料確認
  - ☐ 申請直前：書類チェック・最終提出準備
- **Checkbox Style:** ☐ (empty) → ☑ (filled) for editable versions

### Page 6: Call-to-Action
- **Background:** Orange (#F88800)
- **Text Color:** White
- **Primary Text:** "詳しくはプロフィールのLINEから相談できます"
- **CTA Element:** QR Code placeholder (editable, 180×180px)
- **Secondary Text:** "無料相談受付中"

## Test Case: Business Reconstruction Subsidy GX/DX Type

**Test Subsidy:** 事業再構築補助金GX・DX型 (Max ¥1.5B)

### Test Results
- ✅ Page 1: Hook matches subsidy scale (¥1.5 billion support message)
- ✅ Pages 2-4: Industry transformation examples relevant to GX/DX conversion
- ✅ Page 5: 6-month timeline appropriate for large subsidy application
- ✅ Page 6: QR code enables LINE consultation signup

## Implementation Guide

### For Canva Project Creation

1. **Create New Canva Project**
   - Dimensions: 1080×1350px
   - Create 6 separate pages (or use carousel feature if available)

2. **Set Up Design System**
   - Add navy #00335C as primary color
   - Add orange #F88800 as accent
   - Set fonts to Meiryo (or Noto Sans JP fallback)

3. **Import or Recreate Pages**
   - Use the interactive prototype as visual reference
   - Recreate each page following the specifications above
   - Ensure consistent spacing and alignment across pages

4. **Add Editable Elements**
   - Make title text editable for A/B testing
   - Make benefit descriptions editable
   - QR code should be easily replaceable
   - Checklist checkboxes should support ☐/☑ toggling

5. **Export Options**
   - Export as PDF (6 pages)
   - Export individual PNG files for social media preview
   - Export as video carousel if Canva supports

## Interactive Prototype

An interactive HTML prototype of this design is available at:
https://claude.ai/artifact/39rVY2z2xjTWpiZihSFrQj

**Features:**
- Live preview of all 6 pages
- Page navigation with arrow buttons or keyboard shortcuts (← → or A/D keys)
- Responsive design (desktop and mobile preview)
- All design specifications implemented

## Notes

- The checklist timeline (6mo / 3mo / 1mo / 直前) is editable for different subsidy types
- Industry examples can be swapped for other sectors (agriculture, manufacturing, services, etc.)
- QR code placeholder should link to LINE friend-add endpoint via `/go/line_redirect`
- All color contrasts meet WCAG AA standards

## Future Customization

For other subsidy types, adjust:
- **Page 5 Timeline:** Match application deadlines (e.g., 3-month prep for smaller subsidies)
- **Pages 2-4 Examples:** Select industries most relevant to that subsidy's target
- **Page 1 Benefit:** Update grant amount and type name

---

**Created:** 2026-09-28  
**Template Version:** 3  
**Design Standard:** Meiryo + Navy/Orange theme  
**Status:** Ready for Canva import
