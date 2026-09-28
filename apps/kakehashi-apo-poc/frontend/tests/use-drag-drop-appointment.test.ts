import { renderHook, act } from '@testing-library/react';
import { DateTime } from 'luxon';
import useDragDropAppointment from '../src/hooks/useDragDropAppointment';

describe('useDragDropAppointment Hook', () => {
  const mockOnCreate = jest.fn();
  const mockOnDragStart = jest.fn();
  const mockOnDragEnd = jest.fn();

  beforeEach(() => {
    mockOnCreate.mockClear();
    mockOnDragStart.mockClear();
    mockOnDragEnd.mockClear();
  });

  it('should validate valid drop zone', () => {
    const { result } = renderHook(() =>
      useDragDropAppointment(mockOnCreate)
    );

    const futureTime = DateTime.now().plus({ days: 1 }).set({ hour: 10 });
    const validation = result.current.validateDropZone('rep-001', futureTime, 30);

    expect(validation.isValid).toBe(true);
  });

  it('should reject past time drop', () => {
    const { result } = renderHook(() =>
      useDragDropAppointment(mockOnCreate)
    );

    const pastTime = DateTime.now().minus({ days: 1 });
    const validation = result.current.validateDropZone('rep-001', pastTime, 30);

    expect(validation.isValid).toBe(false);
    expect(validation.reason).toContain('過去');
  });

  it('should reject outside business hours', () => {
    const { result } = renderHook(() =>
      useDragDropAppointment(mockOnCreate)
    );

    const offHourTime = DateTime.now().plus({ days: 1 }).set({ hour: 20 });
    const validation = result.current.validateDropZone('rep-001', offHourTime, 30);

    expect(validation.isValid).toBe(false);
    expect(validation.reason).toContain('営業時間外');
  });

  it('should handle appointment creation on valid drop', () => {
    const { result } = renderHook(() =>
      useDragDropAppointment(mockOnCreate)
    );

    const futureTime = DateTime.now().plus({ days: 1 }).set({ hour: 10 });

    act(() => {
      result.current.handleDropSlot('rep-001', futureTime, 'New Appointment');
    });

    expect(mockOnCreate).toHaveBeenCalledWith('rep-001', futureTime, 'New Appointment');
  });

  it('should not create appointment on invalid drop', () => {
    const { result } = renderHook(() =>
      useDragDropAppointment(mockOnCreate)
    );

    const pastTime = DateTime.now().minus({ days: 1 });

    act(() => {
      result.current.handleDropSlot('rep-001', pastTime, 'Invalid Appointment');
    });

    expect(mockOnCreate).not.toHaveBeenCalled();
  });

  it('should track drag state correctly', () => {
    const { result } = renderHook(() =>
      useDragDropAppointment(mockOnCreate, mockOnDragStart, mockOnDragEnd)
    );

    expect(result.current.state.isDragging).toBe(false);

    act(() => {
      result.current.handleDragStart({
        type: 'appointment-template',
        title: 'Test Item',
      });
    });

    expect(result.current.state.isDragging).toBe(true);
    expect(result.current.state.draggedItem?.title).toBe('Test Item');
    expect(mockOnDragStart).toHaveBeenCalled();
  });

  it('should check valid drop zone', () => {
    const { result } = renderHook(() =>
      useDragDropAppointment(mockOnCreate)
    );

    const futureTime = DateTime.now().plus({ days: 1 }).set({ hour: 14 });
    const isValid = result.current.isValidDropZone('rep-001', futureTime, 30);

    expect(isValid).toBe(true);
  });

  it('should handle minimum duration validation', () => {
    const { result } = renderHook(() =>
      useDragDropAppointment(mockOnCreate)
    );

    const futureTime = DateTime.now().plus({ days: 1 }).set({ hour: 10 });
    const validation = result.current.validateDropZone('rep-001', futureTime, 20);

    expect(validation.isValid).toBe(false);
    expect(validation.reason).toContain('30分');
  });

  it('should reject early morning hours', () => {
    const { result } = renderHook(() =>
      useDragDropAppointment(mockOnCreate)
    );

    const earlyMorning = DateTime.now().plus({ days: 1 }).set({ hour: 8 });
    const validation = result.current.validateDropZone('rep-001', earlyMorning, 30);

    expect(validation.isValid).toBe(false);
    expect(validation.reason).toContain('営業時間外');
  });

  it('should include repId and slotTime in validation result', () => {
    const { result } = renderHook(() =>
      useDragDropAppointment(mockOnCreate)
    );

    const futureTime = DateTime.now().plus({ days: 1 }).set({ hour: 10 });
    const validation = result.current.validateDropZone('rep-999', futureTime, 30);

    expect(validation.repId).toBe('rep-999');
    expect(validation.slotTime).toEqual(futureTime);
  });
});
