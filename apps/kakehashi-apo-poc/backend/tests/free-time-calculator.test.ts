import { describe, it, expect } from '@jest/globals';
import { FreeTimeCalculator } from '../src/services/free-time-calculator';

describe('FreeTimeCalculator', () => {
  const calculator = new FreeTimeCalculator();

  it('should calculate free slots with no existing appointments', () => {
    const slots = calculator.calculateFreeSlots('rep-001', '2026-10-04', []);
    expect(slots.length).toBeGreaterThan(0);
    expect(slots[0].startTime).toContain('09:00');
  });

  it('should exclude break time (12:00-13:00)', () => {
    const slots = calculator.calculateFreeSlots('rep-001', '2026-10-04', []);
    // Check that no slot includes the break period (12:00-13:00)
    // Slots should either end at 12:00 or start at 13:00
    const breakConflictSlots = slots.filter(s => {
      const startTime = new Date(s.startTime).getHours();
      const endTime = new Date(s.endTime).getHours();
      // Check if slot spans across break time
      return (startTime < 12 && endTime > 13) || (startTime >= 12 && startTime < 13);
    });
    expect(breakConflictSlots.length).toBe(0);
  });

  it('should exclude appointments with travel time buffer', () => {
    const appointments = [
      {
        repId: 'rep-001',
        startTime: '2026-10-04T10:00:00+09:00',
        endTime: '2026-10-04T11:00:00+09:00',
      },
    ];
    const slots = calculator.calculateFreeSlots('rep-001', '2026-10-04', appointments);
    const conflictSlots = slots.filter(s =>
      s.startTime.includes('10:') || s.startTime.includes('09:30')
    );
    // Should have no slots from 09:30 to 11:30 (due to 30min travel buffer before and after)
    expect(conflictSlots.length).toBe(0);
  });

  it('should return slots with correct duration', () => {
    const slots = calculator.calculateFreeSlots('rep-001', '2026-10-04', []);
    for (const slot of slots) {
      expect(slot.durationMinutes).toBeGreaterThanOrEqual(30);
    }
  });
});
