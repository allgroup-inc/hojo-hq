import { useCallback, useState } from 'react';
import { DateTime } from 'luxon';

export interface DragSource {
  type: 'appointment-template';
  title: string;
  repId?: string;
}

export interface DropResult {
  repId: string;
  slotTime: DateTime;
  isValid: boolean;
  reason?: string;
}

interface DragDropState {
  isDragging: boolean;
  draggedItem?: DragSource;
  dropZoneHovered?: string;
  lastDropResult?: DropResult;
}

export const useDragDropAppointment = (
  onAppointmentCreate: (repId: string, startTime: DateTime, title: string) => void,
  onDragStart?: (item: DragSource) => void,
  onDragEnd?: (result?: DropResult) => void
) => {
  const [state, setState] = useState<DragDropState>({
    isDragging: false,
  });

  // ドラッグ開始時のハンドラー
  const handleDragStart = useCallback(
    (item: DragSource) => {
      setState((prev) => ({
        ...prev,
        isDragging: true,
        draggedItem: item,
      }));
      onDragStart?.(item);
    },
    [onDragStart]
  );

  // ドラッグ終了時のハンドラー
  const handleDragEnd = useCallback(
    (result?: DropResult) => {
      setState((prev) => ({
        ...prev,
        isDragging: false,
        draggedItem: undefined,
        lastDropResult: result,
      }));
      onDragEnd?.(result);
    },
    [onDragEnd]
  );

  // ドロップゾーン判定ロジック
  const validateDropZone = useCallback(
    (repId: string, slotTime: DateTime, minDurationMinutes: number = 30): DropResult => {
      // 過去時間チェック
      if (slotTime < DateTime.now()) {
        return {
          repId,
          slotTime,
          isValid: false,
          reason: '過去の時間にはスケジュール設定できません',
        };
      }

      // 営業時間チェック（9:00-18:00）
      const hour = slotTime.hour;
      if (hour < 9 || hour >= 18) {
        return {
          repId,
          slotTime,
          isValid: false,
          reason: '営業時間外（9:00-18:00）です',
        };
      }

      // 最小枠長チェック
      if (minDurationMinutes < 30) {
        return {
          repId,
          slotTime,
          isValid: false,
          reason: '最小30分のスロットが必要です',
        };
      }

      return {
        repId,
        slotTime,
        isValid: true,
      };
    },
    []
  );

  // フリースロット適格性チェック
  const isValidDropZone = useCallback(
    (repId: string, slotTime: DateTime, durationMinutes: number = 30): boolean => {
      const result = validateDropZone(repId, slotTime, durationMinutes);
      return result.isValid;
    },
    [validateDropZone]
  );

  // ドロップハンドラー
  const handleDropSlot = useCallback(
    (repId: string, slotTime: DateTime, title: string) => {
      const validation = validateDropZone(repId, slotTime);

      if (validation.isValid) {
        onAppointmentCreate(repId, slotTime, title);
        handleDragEnd(validation);
      } else {
        handleDragEnd({ ...validation, isValid: false });
      }
    },
    [validateDropZone, onAppointmentCreate, handleDragEnd]
  );

  return {
    state,
    handleDragStart,
    handleDragEnd,
    handleDropSlot,
    validateDropZone,
    isValidDropZone,
  };
};

export default useDragDropAppointment;
