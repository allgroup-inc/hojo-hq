import { DateTime, Interval } from 'luxon';

interface Appointment {
  startTime: string; // ISO 8601 format
  endTime: string;   // ISO 8601 format
  repId: string;
}

interface FreeSlot {
  startTime: string;
  endTime: string;
  durationMinutes: number;
}

export class FreeTimeCalculator {
  private readonly WORK_START = 9; // 09:00
  private readonly WORK_END = 18;   // 18:00
  private readonly BREAK_START = 12; // 12:00
  private readonly BREAK_END = 13;   // 13:00
  private readonly BREAK_DURATION = 60; // minutes
  private readonly TRAVEL_TIME = 30; // minutes
  private readonly MIN_SLOT_DURATION = 30; // minutes
  private readonly TIMEZONE = 'Asia/Tokyo';

  calculateFreeSlots(
    repId: string,
    date: string, // YYYY-MM-DD
    existingAppointments: Appointment[]
  ): FreeSlot[] {
    const dt = DateTime.fromISO(date, { zone: this.TIMEZONE });
    const workStart = dt.set({ hour: this.WORK_START, minute: 0, second: 0 });
    const workEnd = dt.set({ hour: this.WORK_END, minute: 0, second: 0 });
    const breakStart = dt.set({ hour: this.BREAK_START, minute: 0, second: 0 });
    const breakEnd = dt.set({ hour: this.BREAK_END, minute: 0, second: 0 });

    // Filter appointments for this rep on this date
    const dayAppointments = existingAppointments
      .filter(apt => apt.repId === repId && apt.startTime.startsWith(date))
      .map(apt => ({
        start: DateTime.fromISO(apt.startTime, { zone: this.TIMEZONE }),
        end: DateTime.fromISO(apt.endTime, { zone: this.TIMEZONE }),
      }))
      .sort((a, b) => a.start.toMillis() - b.start.toMillis());

    // Build occupied intervals (appointments + travel time + break)
    const occupied: { start: DateTime; end: DateTime }[] = [];

    // Add break
    occupied.push({ start: breakStart, end: breakEnd });

    // Add appointments with travel time buffer
    for (const apt of dayAppointments) {
      const start = apt.start.minus({ minutes: this.TRAVEL_TIME });
      const end = apt.end.plus({ minutes: this.TRAVEL_TIME });
      occupied.push({ start, end });
    }

    // Sort and merge overlapping intervals
    occupied.sort((a, b) => a.start.toMillis() - b.start.toMillis());
    const merged = this.mergeIntervals(occupied);

    // Find free slots
    const freeSlots: FreeSlot[] = [];
    let currentTime = workStart;

    for (const interval of merged) {
      if (interval.start > currentTime) {
        const slotEnd = interval.start;
        const slotDuration = slotEnd.diff(currentTime, 'minutes').minutes;

        if (slotDuration >= this.MIN_SLOT_DURATION) {
          freeSlots.push({
            startTime: currentTime.toISO(),
            endTime: slotEnd.toISO(),
            durationMinutes: Math.floor(slotDuration),
          });
        }
      }
      currentTime = interval.end;
    }

    // Handle remaining time until end of work day
    if (currentTime < workEnd) {
      const slotDuration = workEnd.diff(currentTime, 'minutes').minutes;
      if (slotDuration >= this.MIN_SLOT_DURATION) {
        freeSlots.push({
          startTime: currentTime.toISO(),
          endTime: workEnd.toISO(),
          durationMinutes: Math.floor(slotDuration),
        });
      }
    }

    return freeSlots;
  }

  private mergeIntervals(intervals: { start: DateTime; end: DateTime }[]): { start: DateTime; end: DateTime }[] {
    if (intervals.length === 0) return [];

    const merged = [];
    let current = intervals[0];

    for (let i = 1; i < intervals.length; i++) {
      if (intervals[i].start <= current.end) {
        current.end = DateTime.max(current.end, intervals[i].end);
      } else {
        merged.push(current);
        current = intervals[i];
      }
    }
    merged.push(current);
    return merged;
  }
}
