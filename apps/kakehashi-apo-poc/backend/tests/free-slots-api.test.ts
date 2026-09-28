import { describe, it, expect, beforeAll, afterAll } from '@jest/globals';
import request from 'supertest';
import app from '../src/index';

describe('GET /api/free-slots/:repId/:date', () => {
  it('should return free slots for a valid repId and date', async () => {
    const res = await request(app)
      .get('/api/free-slots/rep-001/2026-10-05')
      .expect(200);

    expect(res.body).toHaveProperty('repId', 'rep-001');
    expect(res.body).toHaveProperty('date', '2026-10-05');
    expect(res.body).toHaveProperty('slots');
    expect(Array.isArray(res.body.slots)).toBe(true);
    expect(res.body).toHaveProperty('totalAvailableMinutes');
    expect(res.body).toHaveProperty('generatedAt');
  });

  it('should return slots with proper structure', async () => {
    const res = await request(app)
      .get('/api/free-slots/rep-002/2026-10-06')
      .expect(200);

    if (res.body.slots.length > 0) {
      const slot = res.body.slots[0];
      expect(slot).toHaveProperty('startTime');
      expect(slot).toHaveProperty('endTime');
      expect(slot).toHaveProperty('durationMinutes');
      expect(slot.durationMinutes).toBeGreaterThanOrEqual(30);
    }
  });

  it('should reject invalid date format', async () => {
    const res = await request(app)
      .get('/api/free-slots/rep-001/2026/10/05')
      .expect(400);

    expect(res.body).toHaveProperty('error');
    expect(res.body.error).toContain('Invalid date format');
  });

  it('should reject missing parameters', async () => {
    const res = await request(app)
      .get('/api/free-slots/rep-001/')
      .expect(404); // Express routing level 404
  });

  it('should calculate total available minutes correctly', async () => {
    const res = await request(app)
      .get('/api/free-slots/rep-001/2026-10-05')
      .expect(200);

    const sumMinutes = res.body.slots.reduce(
      (sum: number, slot: any) => sum + slot.durationMinutes,
      0
    );
    expect(sumMinutes).toBe(res.body.totalAvailableMinutes);
  });

  it('should verify health endpoint', async () => {
    const res = await request(app)
      .get('/health')
      .expect(200);

    expect(res.body).toHaveProperty('status', 'ok');
    expect(res.body).toHaveProperty('timestamp');
  });
});
