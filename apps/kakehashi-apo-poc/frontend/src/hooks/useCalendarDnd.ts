import { useCallback, useState } from 'react';
import { DateTime } from 'luxon';

export interface DndState {
  draggedAppointmentId?: string;
  dropTargetRepId?: string;
  dropTargetTime?: DateTime;
  isDragging?: boolean;
}

export interface UseCalendarDndReturn {
  dndState: DndState;
  handleDragStart: (appointmentId: string) => void;
  handleDragEnd: () => void;
  handleDropZoneEnter: (repId: string, slotTime: DateTime) => void;
  handleDropZoneLeave: () => void;
  resetDndState: () => void;
}

/**
 * Custom hook for managing calendar drag-and-drop state
 * @param onCreateAppointment Callback function to create appointment
 * @returns DnD state and handlers
 */
export const useCalendarDnd = (
  onCreateAppointment: (repId: string, startTime: DateTime, title: string) => void
): UseCalendarDndReturn => {
  const [dndState, setDndState] = useState<DndState>({
    isDragging: false,
  });

  const handleDragStart = useCallback((appointmentId: string) => {
    setDndState((prev) => ({
      ...prev,
      draggedAppointmentId: appointmentId,
      isDragging: true,
    }));
  }, []);

  const handleDragEnd = useCallback(() => {
    if (
      dndState.draggedAppointmentId &&
      dndState.dropTargetRepId &&
      dndState.dropTargetTime
    ) {
      const title = `新規アポ (${dndState.draggedAppointmentId})`;
      onCreateAppointment(dndState.dropTargetRepId, dndState.dropTargetTime, title);
    }
    setDndState({
      isDragging: false,
    });
  }, [dndState, onCreateAppointment]);

  const handleDropZoneEnter = useCallback((repId: string, slotTime: DateTime) => {
    setDndState((prev) => ({
      ...prev,
      dropTargetRepId: repId,
      dropTargetTime: slotTime,
    }));
  }, []);

  const handleDropZoneLeave = useCallback(() => {
    setDndState((prev) => ({
      ...prev,
      dropTargetRepId: undefined,
      dropTargetTime: undefined,
    }));
  }, []);

  const resetDndState = useCallback(() => {
    setDndState({
      isDragging: false,
    });
  }, []);

  return {
    dndState,
    handleDragStart,
    handleDragEnd,
    handleDropZoneEnter,
    handleDropZoneLeave,
    resetDndState,
  };
};

export default useCalendarDnd;
