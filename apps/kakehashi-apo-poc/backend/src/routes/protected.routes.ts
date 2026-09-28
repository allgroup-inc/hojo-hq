import express, { Router, RequestHandler } from 'express';
import { authenticate, authorize, authorizeOwnerOrAdmin } from '../middleware/auth.middleware';
import { UserRole, AuthRequest } from '../types/user.types';

const router = Router();

/**
 * GET /protected/profile
 * 認証済みユーザーのプロフィール取得
 * アクセス: すべての認証済みユーザー
 */
router.get('/profile', authenticate as RequestHandler, ((req: AuthRequest, res) => {
  res.json({
    status: 'success',
    message: 'Profile retrieved successfully',
    user: req.user,
  });
}) as RequestHandler);

/**
 * GET /protected/admin/stats
 * 管理者向け統計情報
 * アクセス: ADMIN ロールのみ
 */
router.get(
  '/admin/stats',
  authenticate,
  authorize(UserRole.ADMIN),
  (req, res) => {
    res.json({
      status: 'success',
      message: 'Admin statistics retrieved successfully',
      data: {
        totalSalesReps: 12,
        totalAppointments: 245,
        avgAppointmentsPerRep: 20.4,
        avgAppointmentDurationMinutes: 45,
        appointmentCompletionRate: 0.92,
      },
    });
  }
);

/**
 * GET /protected/admin/sales-reps
 * 営業マン一覧（管理者用）
 * アクセス: ADMIN ロールのみ
 */
router.get(
  '/admin/sales-reps',
  authenticate,
  authorize(UserRole.ADMIN),
  (req, res) => {
    res.json({
      status: 'success',
      message: 'Sales representatives list retrieved successfully',
      data: [
        {
          id: 'rep-001',
          displayName: '営業太郎',
          email: 'taro@example.com',
          role: 'SALES_REP',
          appointmentCount: 20,
        },
        {
          id: 'rep-002',
          displayName: '営業花子',
          email: 'hanako@example.com',
          role: 'SALES_REP',
          appointmentCount: 18,
        },
      ],
    });
  }
);

/**
 * GET /protected/apo-staff/dashboard
 * 予約管理スタッフ向けダッシュボード
 * アクセス: APO_STAFF・ADMIN ロール
 */
router.get(
  '/apo-staff/dashboard',
  authenticate,
  authorize(UserRole.APO_STAFF, UserRole.ADMIN),
  (req, res) => {
    res.json({
      status: 'success',
      message: 'APO staff dashboard retrieved successfully',
      data: {
        pendingAppointments: 5,
        todaysAppointments: 8,
        upcomingWeekAppointments: 23,
        lastUpdated: new Date().toISOString(),
      },
    });
  }
);

/**
 * GET /protected/sales/:repId/schedule
 * 営業マンのスケジュール取得
 * アクセス: 本人・APO_STAFF・ADMIN
 */
router.get(
  '/sales/:repId/schedule',
  authenticate,
  authorizeOwnerOrAdmin,
  (req, res) => {
    const { repId } = req.params;

    res.json({
      status: 'success',
      message: 'Schedule retrieved successfully',
      repId,
      schedule: {
        date: '2026-10-05',
        dayOfWeek: 'Sunday',
        appointments: [
          {
            id: 'apt-001',
            title: '顧客A相談',
            startTime: '10:00',
            endTime: '11:00',
            status: 'confirmed',
          },
          {
            id: 'apt-002',
            title: '顧客B打ち合わせ',
            startTime: '14:00',
            endTime: '15:30',
            status: 'pending',
          },
        ],
      },
    });
  }
);

/**
 * GET /protected/sales/:repId/appointments
 * 営業マンの予約一覧
 * アクセス: 本人・APO_STAFF・ADMIN
 */
router.get(
  '/sales/:repId/appointments',
  authenticate,
  authorizeOwnerOrAdmin,
  (req, res) => {
    const { repId } = req.params;

    res.json({
      status: 'success',
      message: 'Appointments retrieved successfully',
      repId,
      appointments: [
        {
          id: 'apt-001',
          date: '2026-10-05',
          startTime: '10:00',
          endTime: '11:00',
          companyName: '株式会社A',
          representative: '代表者',
          status: 'completed',
        },
        {
          id: 'apt-002',
          date: '2026-10-12',
          startTime: '14:00',
          endTime: '15:30',
          companyName: '株式会社B',
          representative: '営業部長',
          status: 'pending',
        },
      ],
    });
  }
);

/**
 * POST /protected/sales/:repId/appointments (PoC: 未実装)
 * 予約作成
 * アクセス: 本人・APO_STAFF・ADMIN
 */
router.post(
  '/sales/:repId/appointments',
  authenticate,
  authorizeOwnerOrAdmin,
  (req, res) => {
    const { repId } = req.params;

    res.status(201).json({
      status: 'success',
      message: 'Appointment created successfully (PoC: not yet implemented)',
      repId,
      appointmentId: 'apt-new-001',
    });
  }
);

export default router;
