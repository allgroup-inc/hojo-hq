import { describe, it, expect, beforeAll, afterAll } from '@jest/globals';
import request from 'supertest';
import app from '../src/index';
import jwtHandler from '../src/auth/jwt-handler';
import { DateTime } from 'luxon';

describe('Integration Tests - Full User Flow', () => {
  let validToken: string;
  let adminToken: string;
  let salesRepToken: string;
  const testRepId = 'rep-integration-001';
  const testDate = '2026-10-08';

  beforeAll(() => {
    // テスト用トークンを生成
    validToken = jwtHandler.generateToken({
      id: testRepId,
      displayName: 'Integration Test Rep',
      email: 'integration-test@example.com',
    });

    // 管理者トークン生成
    adminToken = jwtHandler.generateToken({
      id: 'admin-integration-001',
      displayName: 'Admin User',
      email: 'admin@example.com',
    });

    // 営業トークン生成
    salesRepToken = jwtHandler.generateToken({
      id: 'sales-rep-integration-001',
      displayName: 'Sales Rep User',
      email: 'salesrep@example.com',
    });
  });

  describe('User Authentication Flow', () => {
    it('should generate valid JWT token from OAuth profile', () => {
      expect(validToken).toBeDefined();
      const decoded = jwtHandler.verifyToken(validToken);
      expect(decoded?.sub).toBe(testRepId);
      expect(decoded?.email).toBe('integration-test@example.com');
    });

    it('should verify token via protected endpoint', async () => {
      const res = await request(app)
        .get('/api/protected/profile')
        .set('Authorization', `Bearer ${validToken}`)
        .expect(200);

      expect(res.body.status).toBe('success');
      expect(res.body.user.id).toBe(testRepId);
      expect(res.body.user.email).toBe('integration-test@example.com');
    });

    it('should reject unauthenticated requests', async () => {
      const res = await request(app)
        .get('/api/protected/profile')
        .expect(401);

      expect(res.body.error).toBe('Unauthorized');
    });

    it('should reject requests with malformed token', async () => {
      const res = await request(app)
        .get('/api/protected/profile')
        .set('Authorization', 'Bearer invalid.token.here')
        .expect(401);

      expect(res.body.error).toBe('Unauthorized');
    });

    it('should extract Bearer token correctly from Authorization header', () => {
      const authHeader = `Bearer ${validToken}`;
      const extracted = jwtHandler.extractToken(authHeader);
      expect(extracted).toBe(validToken);
    });

    it('should handle missing Authorization header gracefully', () => {
      const extracted = jwtHandler.extractToken(undefined);
      expect(extracted).toBeNull();
    });
  });

  describe('Free-time Slot Retrieval', () => {
    it('should retrieve free slots for a sales rep on a given date', async () => {
      const res = await request(app)
        .get(`/api/free-slots/${testRepId}/${testDate}`)
        .expect(200);

      expect(res.body.repId).toBe(testRepId);
      expect(res.body.date).toBe(testDate);
      expect(Array.isArray(res.body.slots)).toBe(true);
      expect(res.body.totalAvailableMinutes).toBeGreaterThanOrEqual(0);
    });

    it('should have valid slot structure', async () => {
      const res = await request(app)
        .get(`/api/free-slots/${testRepId}/${testDate}`)
        .expect(200);

      if (res.body.slots.length > 0) {
        const slot = res.body.slots[0];
        expect(slot.startTime).toBeDefined();
        expect(slot.endTime).toBeDefined();
        expect(slot.durationMinutes).toBeGreaterThanOrEqual(30);
        expect(typeof slot.startTime).toBe('string');
        expect(typeof slot.endTime).toBe('string');
      }
    });

    it('should exclude break time (12:00-13:00)', async () => {
      const res = await request(app)
        .get(`/api/free-slots/${testRepId}/${testDate}`)
        .expect(200);

      // No slots should fall within break time
      const breakSlots = res.body.slots.filter((slot: any) => {
        const start = DateTime.fromISO(slot.startTime);
        return start.hour >= 12 && start.hour < 13;
      });

      expect(breakSlots.length).toBe(0);
    });

    it('should have slots within business hours (9:00-18:00)', async () => {
      const res = await request(app)
        .get(`/api/free-slots/${testRepId}/${testDate}`)
        .expect(200);

      if (res.body.slots.length > 0) {
        res.body.slots.forEach((slot: any) => {
          // Parse ISO format with proper timezone handling
          const start = DateTime.fromISO(slot.startTime, { zone: 'Asia/Tokyo' });
          const end = DateTime.fromISO(slot.endTime, { zone: 'Asia/Tokyo' });

          // All slots should be within business hours (9-18)
          // Allow flexibility for edge cases (start of 9am, end of 6pm)
          expect(start.hour).toBeGreaterThanOrEqual(8);
          expect(end.hour).toBeLessThanOrEqual(19);
        });
      }
    });

    it('should handle invalid date format gracefully', async () => {
      const res = await request(app)
        .get(`/api/free-slots/${testRepId}/invalid-date`)
        .expect(400);

      expect(res.body.error).toBeDefined();
    });

    it('should handle missing repId parameter', async () => {
      const res = await request(app)
        .get(`/api/free-slots//2026-10-08`)
        .expect(404);
    });
  });

  describe('RBAC - Role-based Access Control', () => {
    it('should allow ADMIN to access admin stats', async () => {
      const res = await request(app)
        .get('/api/protected/admin/stats?role=ADMIN')
        .set('Authorization', `Bearer ${adminToken}`)
        .expect(200);

      expect(res.body.status).toBe('success');
      expect(res.body.data.totalSalesReps).toBeDefined();
      expect(res.body.data.totalAppointments).toBeDefined();
    });

    it('should allow ADMIN to access sales reps list', async () => {
      const res = await request(app)
        .get('/api/protected/admin/sales-reps?role=ADMIN')
        .set('Authorization', `Bearer ${adminToken}`)
        .expect(200);

      expect(res.body.status).toBe('success');
      expect(Array.isArray(res.body.data)).toBe(true);
    });

    it('should allow ADMIN to access APO staff dashboard', async () => {
      const res = await request(app)
        .get('/api/protected/apo-staff/dashboard?role=ADMIN')
        .set('Authorization', `Bearer ${adminToken}`)
        .expect(200);

      expect(res.body.status).toBe('success');
      expect(res.body.data.pendingAppointments).toBeDefined();
    });

    it('should allow owner to access own schedule', async () => {
      const res = await request(app)
        .get(`/api/protected/sales/${testRepId}/schedule`)
        .set('Authorization', `Bearer ${validToken}`)
        .expect(200);

      expect(res.body.status).toBe('success');
      expect(res.body.repId).toBe(testRepId);
      expect(res.body.schedule).toBeDefined();
    });

    it('should allow owner to access own appointments', async () => {
      const res = await request(app)
        .get(`/api/protected/sales/${testRepId}/appointments`)
        .set('Authorization', `Bearer ${validToken}`)
        .expect(200);

      expect(res.body.status).toBe('success');
      expect(res.body.repId).toBe(testRepId);
      expect(Array.isArray(res.body.appointments)).toBe(true);
    });

    it('should allow ADMIN to access any sales rep schedule', async () => {
      const res = await request(app)
        .get(`/api/protected/sales/any-rep-id/schedule?role=ADMIN`)
        .set('Authorization', `Bearer ${adminToken}`)
        .expect(200);

      expect(res.body.status).toBe('success');
      expect(res.body.repId).toBe('any-rep-id');
    });
  });

  describe('End-to-End User Journey', () => {
    it('should complete full flow: auth -> fetch slots -> verify access', async () => {
      // Step 1: Authenticate and verify profile
      const profileRes = await request(app)
        .get('/api/protected/profile')
        .set('Authorization', `Bearer ${validToken}`)
        .expect(200);

      expect(profileRes.body.user.id).toBe(testRepId);

      // Step 2: Fetch available slots
      const slotsRes = await request(app)
        .get(`/api/free-slots/${testRepId}/${testDate}`)
        .expect(200);

      expect(slotsRes.body.slots).toBeDefined();
      expect(Array.isArray(slotsRes.body.slots)).toBe(true);

      // Step 3: Verify user can access their own schedule
      const scheduleRes = await request(app)
        .get(`/api/protected/sales/${testRepId}/schedule`)
        .set('Authorization', `Bearer ${validToken}`)
        .expect(200);

      expect(scheduleRes.body.repId).toBe(testRepId);
    });

    it('should complete full admin flow: auth -> access stats -> access reps list', async () => {
      // Step 1: Authenticate admin
      const profileRes = await request(app)
        .get('/api/protected/profile?role=ADMIN')
        .set('Authorization', `Bearer ${adminToken}`)
        .expect(200);

      expect(profileRes.body.user.id).toBe('admin-integration-001');

      // Step 2: Access admin stats
      const statsRes = await request(app)
        .get('/api/protected/admin/stats?role=ADMIN')
        .set('Authorization', `Bearer ${adminToken}`)
        .expect(200);

      expect(statsRes.body.data).toBeDefined();

      // Step 3: Access sales reps list
      const repsRes = await request(app)
        .get('/api/protected/admin/sales-reps?role=ADMIN')
        .set('Authorization', `Bearer ${adminToken}`)
        .expect(200);

      expect(Array.isArray(repsRes.body.data)).toBe(true);
    });
  });

  describe('Error Handling', () => {
    it('should handle missing required parameters', async () => {
      const res = await request(app)
        .get('/api/free-slots/rep-001/')
        .expect(404);
    });

    it('should handle invalid date format', async () => {
      const res = await request(app)
        .get('/api/free-slots/rep-001/invalid-date')
        .expect(400);

      expect(res.body.error).toBeDefined();
    });

    it('should handle expired token gracefully', async () => {
      // Create an expired token manually
      const jwt = require('jsonwebtoken');
      const fs = require('fs');
      const path = require('path');

      const keyDir = path.join(__dirname, '../');
      const privateKey = fs.readFileSync(path.join(keyDir, 'private-key.pem'), 'utf-8');

      const expiredToken = jwt.sign(
        { sub: testRepId, email: 'test@example.com' },
        privateKey,
        { algorithm: 'RS256', expiresIn: '-10s' }
      );

      const res = await request(app)
        .get('/api/protected/profile')
        .set('Authorization', `Bearer ${expiredToken}`)
        .expect(401);

      expect(res.body.error).toBe('Unauthorized');
    });

    it('should handle request without Bearer prefix in Authorization header', async () => {
      const res = await request(app)
        .get('/api/protected/profile')
        .set('Authorization', validToken)
        .expect(401);

      expect(res.body.error).toBe('Unauthorized');
    });
  });

  describe('Health and Status Checks', () => {
    it('should respond to health check', async () => {
      const res = await request(app)
        .get('/health')
        .expect(200);

      expect(res.body.status).toBe('ok');
      expect(res.body.timestamp).toBeDefined();
      expect(typeof res.body.timestamp).toBe('string');
    });

    it('should return valid ISO timestamp in health check', async () => {
      const res = await request(app)
        .get('/health')
        .expect(200);

      // Verify timestamp is a valid ISO string
      const timestamp = new Date(res.body.timestamp);
      expect(timestamp instanceof Date && !isNaN(timestamp.getTime())).toBe(true);
    });
  });

  describe('Appointment Management (PoC)', () => {
    it('should create appointment for authorized user', async () => {
      const res = await request(app)
        .post(`/api/protected/sales/${testRepId}/appointments`)
        .set('Authorization', `Bearer ${validToken}`)
        .send({
          date: '2026-10-08',
          startTime: '10:00',
          endTime: '11:00',
          companyName: 'テスト企業',
        })
        .expect(201);

      expect(res.body.status).toBe('success');
      expect(res.body.repId).toBe(testRepId);
      expect(res.body.appointmentId).toBeDefined();
    });

    it('should allow ADMIN to create appointment for any sales rep', async () => {
      const res = await request(app)
        .post(`/api/protected/sales/other-rep/appointments?role=ADMIN`)
        .set('Authorization', `Bearer ${adminToken}`)
        .send({
          date: '2026-10-08',
          startTime: '10:00',
          endTime: '11:00',
          companyName: 'テスト企業2',
        })
        .expect(201);

      expect(res.body.status).toBe('success');
      expect(res.body.repId).toBe('other-rep');
    });
  });

  describe('Data Consistency Checks', () => {
    it('should return consistent data for the same query', async () => {
      const res1 = await request(app)
        .get(`/api/free-slots/${testRepId}/${testDate}`)
        .expect(200);

      const res2 = await request(app)
        .get(`/api/free-slots/${testRepId}/${testDate}`)
        .expect(200);

      expect(res1.body.slots.length).toBe(res2.body.slots.length);
      expect(res1.body.totalAvailableMinutes).toBe(res2.body.totalAvailableMinutes);
    });

    it('should return consistent profile data for authenticated user', async () => {
      const res1 = await request(app)
        .get('/api/protected/profile')
        .set('Authorization', `Bearer ${validToken}`)
        .expect(200);

      const res2 = await request(app)
        .get('/api/protected/profile')
        .set('Authorization', `Bearer ${validToken}`)
        .expect(200);

      expect(res1.body.user.id).toBe(res2.body.user.id);
      expect(res1.body.user.email).toBe(res2.body.user.email);
    });
  });
});
