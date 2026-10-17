# Fukuda Historical Data Import - Sample Test Data

This document provides sample test data for validating the HistoricalDataImporter.gs functionality before importing Fukuda's actual 100 records.

## Sample Data Set (10 records for testing)

| 企業名 | 電話番号 | 手紙送付日 | 架電日 | 通話結果 | 所在地 | 代表者名 | 業種 | 規模 | 代表者年齢 | 備考 |
|---|---|---|---|---|---|---|---|---|---|---|
| 株式会社ABC建設 | 098-123-4567 | 2026-08-01 | 2026-08-10 | 繋がった | 沖縄県那覇市中央1-1-1 | 山田太郎 | 建設 | 20-50名 | 65 | 親切な対応、再架電予定 |
| 有限会社XYZ整備 | 0981234568 | 2026-07-15 | 2026-07-20 | 不在 | 沖縄県宜野湾市 | 鈴木花子 | 自動車整備 | 10-20名 | 58 |  |
| 社福法人福祉会 | (098)123-4569 | 2026-09-01 | 2026-09-05 | 切られた |  | 伊藤次郎 | 福祉 | 100名以上 | 72 | 忙しそう |
| 个人名義_運送 | 098-123-4570 | 2026-06-10 |  | 不適切 |  |  |  |  |  | 連絡失敗 |
| 沖縄リゾート | 0981234571 | 2026-08-20 | 2026-08-21 | 興味なし | 沖縄県名護市 | 田中美咲 | 宿泊観光 | 50名 | 55 |  |
| 美容室プリン | 098-123-4572 | 2026-09-10 | 2026-09-12 | 繋がった | 沖縄県浦添市 | 佐藤由美 | 美容 | 5-10名 | 42 | SNS運用に興味 |
| 飲食店トマト | 0981234573 | 2026-07-01 | 2026-07-05 | 繋がった | 沖縄県中部 | 加藤健太 | 飲食 | 10名 | 48 | オーナー経営 |
| 製造業ベータ | 098-123-4574 | 2026-08-15 | 2026-08-22 | 不在 |  |  | 製造 |  | 70 | 2回目の架電で繋がった見込み |
| 医療法人ガンマ | 0981234575 | 2026-09-05 | 2026-09-08 | 繋がった |  | 加藤詩織 | 医療 | 30名 | 61 |  |
| 建設_重村 | 098-123-4576 | 2026-06-20 | 2026-06-25 | 検討中 | 沖縄県北部 | 重村武志 | 建設 | 15名 | 68 | 次回接触: 10月中旬 |

## Test Execution Steps

### 1. Create Staging Sheet
1. In GLOW企業リレーション台帳, create a new tab named `福田_履歴インポート`
2. Copy the header row: 企業名, 電話番号, 手紙送付日, 架電日, 通話結果, 所在地, 代表者名, 業種, 規模, 代表者年齢, 備考
3. Paste the 10 sample rows above

### 2. Run Import
1. Menu: GLOW台帳 → 福田データ：100件インポート
2. Wait for completion

### 3. Verify Results Sheet
Check `福田_インポート結果` tab for:
- All 10 should process (some may have warnings)
- Messages should distinguish between valid, warning, and error records

### 4. Verify Company Master
1. Check if all companies appear in Web管理画面
2. Verify interaction history for each company shows both letter and call records
3. Check that related companies (same phone number) are linked

## Expected Validation Outcomes

| Row | Enterprise | Phone | Expected Result | Notes |
|---|---|---|---|---|
| 1 | 株式会社ABC建設 | 098-123-4567 | ✅ Valid | All fields properly formatted |
| 2 | 有限会社XYZ整備 | 0981234568 | ✅ Valid | Phone with no dashes normalized |
| 3 | 社福法人福祉会 | (098)123-4569 | ✅ Valid | Phone with parentheses normalized |
| 4 | 个人名義_運送 | 098-123-4570 | ⚠️ Warning | Missing company name format; call date empty but letter date present |
| 5 | 沖縄リゾート | 0981234571 | ✅ Valid | Only letter date, no call date - should record letter only |
| 6 | 美容室プリン | 098-123-4572 | ✅ Valid | All dates valid |
| 7 | 飲食店トマト | 0981234573 | ✅ Valid | All dates valid |
| 8 | 製造業ベータ | 098-123-4574 | ⚠️ Warning | Missing company name format; missing representative name |
| 9 | 医療法人ガンマ | 0981234575 | ✅ Valid | All dates valid |
| 10 | 建設_重村 | 098-123-4576 | ✅ Valid | All dates valid |

## Edge Cases Tested

1. **Phone Number Format Variations** (Rows 1-3):
   - `098-123-4567` → normalized to `0981234567`
   - `0981234568` → stays same
   - `(098)123-4569` → normalized to `0981234569`

2. **Missing Optional Fields** (Rows 2, 4, 8):
   - Missing location, representative, industry data should not cause rejection
   - System assigns defaults where appropriate

3. **Date-Only Records** (Row 5):
   - Only letter date, no call date → creates letter-send interaction record only
   - Should not fail validation

4. **Partial Company Names** (Rows 4, 8):
   - Non-standard format but contains text → accepted with warning
   - System normalizes to existing pattern if possible

## Quality Checks in Importer

The importer validates:

✅ **必須チェック**:
- 企業名: Not empty
- 電話番号: Not empty, 10-11 digits after normalization

✅ **形式チェック**:
- 手紙送付日, 架電日: Valid YYYY/MM/DD format (or empty)
- 電話番号: Converts to digits-only, removes common separators

✅ **論理チェック**:
- Chronological: Letter date ≤ Call date (when both present)
- Interaction records created for each valid date

✅ **重複チェック**:
- Detects existing phone number in master
- Flags related companies (same phone number)
- Prevents re-import of duplicates

## Next Steps After Sample Testing

Once sample data imports successfully:

1. **Prepare Fukuda's 100 records**: Confirm data is in similar format
2. **Create "福田_履歴インポート" tab**: Paste actual 100 rows
3. **Run actual import**: Execute importFukudaHistoricalData()
4. **Review result report**: Check for any errors or warnings
5. **Verify in Web画面**: Confirm all 100 companies visible with correct histories
6. **Begin normal workflow**: Fukuda can now use Web管理画面 to manage these 100 companies

---

**If sample test passes, proceed to production import with Fukuda's actual data. If any validation errors occur, refer to HistoricalDataImporter.gs error messages to fix data format issues.**
