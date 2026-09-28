import { describe, it, expect, beforeAll } from '@jest/globals';
import request from 'supertest';
import app from '../src/index';
import jwtHandler from '../src/auth/jwt-handler';
import { UserRole } from '../src/types/user.types';

describe('Auth Middleware Tests', () => {
  let validToken: string;

  beforeAll(() => {
    // 有効なトークンを生成
    validToken = jwtHandler.generateToken({
      id: 'test-user-001',
      displayName: 'Test User',
      email: 'test@example.com',
    });
  });

  describe('GET /api/protected/profile', () => {
    it('should access with valid token', async () => {
      const res = await request(app)
        .get('/api/protected/profile')
        .set('Authorization', `Bearer ${validToken}`)
        .expect(200);

      expect(res.body.status).toBe('success');
      expect(res.body.user).toBeDefined();
      expect(res.body.user.email).toBe('test@example.com');
      expect(res.body.user.displayName).toBe('Test User');
    });

    it('should reject without Authorization header', async () => {
      const res = await request(app)
        .get('/api/protected/profile')
        .expect(401);

      expect(res.body.error).toBe('Unauthorized');
      expect(res.body.message).toContain('Missing Authorization header');
    });

    it('should reject with invalid token', async () => {
      const res = await request(app)
        .get('/api/protected/profile')
        .set('Authorization', 'Bearer invalid.token.here')
        .expect(401);

      expect(res.body.error).toBe('Unauthorized');
      expect(res.body.message).toContain('Invalid or expired token');
    });

    it('should reject with malformed Authorization header', async () => {
      const res = await request(app)
        .get('/api/protected/profile')
        .set('Authorization', 'InvalidFormat token')
        .expect(401);

      expect(res.body.error).toBe('Unauthorized');
      expect(res.body.message).toContain('Invalid Authorization format');
    });

    it('should include iat and exp in user object', async () => {
      const res = await request(app)
        .get('/api/protected/profile')
        .set('Authorization', `Bearer ${validToken}`)
        .expect(200);

      expect(res.body.user.iat).toBeDefined();
      expect(res.body.user.exp).toBeDefined();
      expect(typeof res.body.user.iat).toBe('number');
      expect(typeof res.body.user.exp).toBe('number');
    });
  });

  describe('GET /api/protected/admin/stats (RBAC)', () => {
    it('should allow ADMIN role', async () => {
      const res = await request(app)
        .get('/api/protected/admin/stats?role=ADMIN')
        .set('Authorization', `Bearer ${validToken}`)
        .expect(200);

      expect(res.body.status).toBe('success');
      expect(res.body.data.totalSalesReps).toBe(12);
      expect(res.body.data.totalAppointments).toBe(245);
    });

    it('should reject SALES_REP role', async () => {
      const res = await request(app)
        .get('/api/protected/admin/stats?role=SALES_REP')
        .set('Authorization', `Bearer ${validToken}`)
        .expect(403);

      expect(res.body.error).toBe('Forbidden');
      expect(res.body.message).toContain('Access denied');
      expect(res.body.message).toContain('ADMIN');
    });

    it('should reject APO_STAFF role', async () => {
      const res = await request(app)
        .get('/api/protected/admin/stats?role=APO_STAFF')
        .set('Authorization', `Bearer ${validToken}`)
        .expect(403);

      expect(res.body.error).toBe('Forbidden');
    });

    it('should use default SALES_REP role if not specified', async () => {
      const res = await request(app)
        .get('/api/protected/admin/stats')
        .set('Authorization', `Bearer ${validToken}`)
        .expect(403);

      expect(res.body.error).toBe('Forbidden');
    });
  });

  describe('GET /api/protected/apo-staff/dashboard (RBAC)', () => {
    it('should allow APO_STAFF role', async () => {
      const res = await request(app)
        .get('/api/protected/apo-staff/dashboard?role=APO_STAFF')
        .set('Authorization', `Bearer ${validToken}`)
        .expect(200);

      expect(res.body.status).toBe('success');
      expect(res.body.data.pendingAppointments).toBeDefined();
    });

    it('should allow ADMIN role', async () => {
      const res = await request(app)
        .get('/api/protected/apo-staff/dashboard?role=ADMIN')
        .set('Authorization', `Bearer ${validToken}`)
        .expect(200);

      expect(res.body.status).toBe('success');
    });

    it('should reject SALES_REP role', async () => {
      const res = await request(app)
        .get('/api/protected/apo-staff/dashboard?role=SALES_REP')
        .set('Authorization', `Bearer ${validToken}`)
        .expect(403);

      expect(res.body.error).toBe('Forbidden');
    });
  });

  describe('GET /api/protected/sales/:repId/schedule (Owner or Admin)', () => {
    it('should allow owner to access own schedule', async () => {
      const res = await request(app)
        .get('/api/protected/sales/test-user-001/schedule')
        .set('Authorization', `Bearer ${validToken}`)
        .expect(200);

      expect(res.body.status).toBe('success');
      expect(res.body.repId).toBe('test-user-001');
      expect(res.body.schedule.appointments).toBeDefined();
      expect(Array.isArray(res.body.schedule.appointments)).toBe(true);
    });

    it('should reject other user accessing schedule', async () => {
      const res = await request(app)
        .get('/api/protected/sales/other-user-id/schedule')
        .set('Authorization', `Bearer ${validToken}`)
        .expect(403);

      expect(res.body.error).toBe('Forbidden');
      expect(res.body.message).toContain('your own resources');
    });

    it('should allow ADMIN to access any schedule', async () => {
      const res = await request(app)
        .get('/api/protected/sales/other-user-id/schedule?role=ADMIN')
        .set('Authorization', `Bearer ${validToken}`)
        .expect(200);

      expect(res.body.status).toBe('success');
      expect(res.body.repId).toBe('other-user-id');
    });
  });

  describe('GET /api/protected/sales/:repId/appointments', () => {
    it('should retrieve appointments for owner', async () => {
      const res = await request(app)
        .get('/api/protected/sales/test-user-001/appointments')
        .set('Authorization', `Bearer ${validToken}`)
        .expect(200);

      expect(res.body.status).toBe('success');
      expect(res.body.repId).toBe('test-user-001');
      expect(Array.isArray(res.body.appointments)).toBe(true);
      expect(res.body.appointments.length).toBeGreaterThan(0);
    });

    it('should reject non-owner access', async () => {
      const res = await request(app)
        .get('/api/protected/sales/other-user-id/appointments')
        .set('Authorization', `Bearer ${validToken}`)
        .expect(403);

      expect(res.body.error).toBe('Forbidden');
    });

    it('should allow ADMIN to access any appointments', async () => {
      const res = await request(app)
        .get('/api/protected/sales/other-user-id/appointments?role=ADMIN')
        .set('Authorization', `Bearer ${validToken}`)
        .expect(200);

      expect(res.body.status).toBe('success');
      expect(res.body.repId).toBe('other-user-id');
    });
  });

  describe('GET /api/protected/admin/sales-reps', () => {
    it('should return sales reps list for ADMIN', async () => {
      const res = await request(app)
        .get('/api/protected/admin/sales-reps?role=ADMIN')
        .set('Authorization', `Bearer ${validToken}`)
        .expect(200);

      expect(res.body.status).toBe('success');
      expect(Array.isArray(res.body.data)).toBe(true);
      expect(res.body.data.length).toBeGreaterThan(0);
      expect(res.body.data[0]).toHaveProperty('displayName');
      expect(res.body.data[0]).toHaveProperty('email');
      expect(res.body.data[0]).toHaveProperty('role');
    });

    it('should reject non-ADMIN access', async () => {
      const res = await request(app)
        .get('/api/protected/admin/sales-reps?role=SALES_REP')
        .set('Authorization', `Bearer ${validToken}`)
        .expect(403);

      expect(res.body.error).toBe('Forbidden');
    });
  });

  describe('POST /api/protected/sales/:repId/appointments', () => {
    it('should allow owner to create appointment', async () => {
      const res = await request(app)
        .post('/api/protected/sales/test-user-001/appointments')
        .set('Authorization', `Bearer ${validToken}`)
        .send({})
        .expect(201);

      expect(res.body.status).toBe('success');
      expect(res.body.repId).toBe('test-user-001');
    });

    it('should reject non-owner creating appointment', async () => {
      const res = await request(app)
        .post('/api/protected/sales/other-user-id/appointments')
        .set('Authorization', `Bearer ${validToken}`)
        .send({})
        .expect(403);

      expect(res.body.error).toBe('Forbidden');
    });
  });

  describe('Error handling', () => {
    it('should return 400 for invalid role parameter', async () => {
      const res = await request(app)
        .get('/api/protected/profile?role=INVALID_ROLE')
        .set('Authorization', `Bearer ${validToken}`)
        .expect(400);

      expect(res.body.error).toBe('Bad request');
      expect(res.body.message).toContain('Invalid role');
    });

    it('should return 401 without authentication on protected endpoint', async () => {
      const res = await request(app)
        .get('/api/protected/profile')
        .expect(401);

      expect(res.body.error).toBe('Unauthorized');
    });
  });
});
