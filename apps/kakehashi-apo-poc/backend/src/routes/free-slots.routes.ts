import express, { Router, Request, Response } from 'express';
import { FreeTimeCalculator } from '../services/free-time-calculator';

const router = Router();
const freeTimeCalc = new FreeTimeCalculator();

/**
 * GET /free-slots/:repId/:date
 * 営業マンの空き時間スロットリスト取得
 *
 * パラメータ:
 * - repId: 営業マン ID (GUID形式)
 * - date: 対象日 (YYYY-MM-DD形式)
 *
 * クエリパラメータ (オプション):
 * - minDuration: 最小スロット長 (分、デフォルト 30)
 * - travelTime: 移動時間 (分、デフォルト 30)
 *
 * レスポンス:
 * {
 *   "repId": "rep-001",
 *   "date": "2026-10-05",
 *   "slots": [
 *     {
 *       "startTime": "2026-10-05T09:00:00+09:00",
 *       "endTime": "2026-10-05T12:00:00+09:00",
 *       "durationMinutes": 180
 *     },
 *     ...
 *   ],
 *   "totalAvailableMinutes": 480,
 *   "generatedAt": "2026-10-05T14:30:00.000Z"
 * }
 */
router.get('/free-slots/:repId/:date', async (req: Request, res: Response) => {
  try {
    const { repId, date } = req.params;

    // バリデーション: repId と date の形式チェック
    if (!repId || !date) {
      return res.status(400).json({
        error: 'Missing required parameters: repId, date',
      });
    }

    // date が YYYY-MM-DD 形式か確認
    if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) {
      return res.status(400).json({
        error: 'Invalid date format. Use YYYY-MM-DD',
      });
    }

    // TODO: ここで実際に既存アポイントメントをDBから取得する（Phase 1以降）
    // 現在 PoC では、空のリストで計算（全時間が利用可能）
    const existingAppointments: Array<{
      repId: string;
      startTime: string;
      endTime: string;
    }> = [];

    const slots = freeTimeCalc.calculateFreeSlots(repId, date, existingAppointments);

    // 合計利用可能時間を集計
    const totalAvailableMinutes = slots.reduce(
      (sum, slot) => sum + slot.durationMinutes,
      0
    );

    return res.status(200).json({
      repId,
      date,
      slots,
      totalAvailableMinutes,
      generatedAt: new Date().toISOString(),
    });
  } catch (error) {
    console.error('Error calculating free slots:', error);
    return res.status(500).json({
      error: 'Internal server error',
      message: error instanceof Error ? error.message : 'Unknown error',
    });
  }
});

export default router;
