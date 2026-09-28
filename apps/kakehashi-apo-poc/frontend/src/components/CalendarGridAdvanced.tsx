import React, { useState, useCallback } from 'react';
import {
  Box,
  Grid,
  Paper,
  Typography,
  Card,
  CardContent,
  Chip,
  Dialog,
  DialogTitle,
  DialogContent,
  TextField,
  DialogActions,
  Button,
  Alert,
} from '@mui/material';
import { DndProvider, useDrag, useDrop } from 'react-dnd';
import { HTML5Backend } from 'react-dnd-html5-backend';
import { DateTime } from 'luxon';
import useDragDropAppointment from '../hooks/useDragDropAppointment';

interface Appointment {
  id: string;
  title: string;
  startTime: DateTime;
  endTime: DateTime;
  status: 'scheduled' | 'confirmed' | 'cancelled';
  repId: string;
}

interface FreeSlot {
  startTime: string;
  endTime: string;
  durationMinutes: number;
}

interface CalendarGridAdvancedProps {
  appointments: Appointment[];
  freeSlots: Map<string, FreeSlot[]>;
  onCreateAppointment: (repId: string, startTime: DateTime, title: string) => void;
  onError: (error: string) => void;
}

interface DraggedItem {
  title: string;
}

const DroppableSlot: React.FC<{
  slot: FreeSlot;
  repId: string;
  onDropSlot: (repId: string, slotTime: DateTime, title: string) => void;
  isValidDropZone: (repId: string, slotTime: DateTime) => boolean;
}> = ({ slot, repId, onDropSlot, isValidDropZone }) => {
  const slotTime = DateTime.fromISO(slot.startTime);
  const isValid = isValidDropZone(repId, slotTime);

  const [{ isOver }, drop] = useDrop(
    () => ({
      accept: 'appointment-template',
      drop: (item: DraggedItem) => {
        if (isValid) {
          onDropSlot(repId, slotTime, item.title);
        }
      },
      canDrop: () => isValid,
      collect: (monitor) => ({
        isOver: !!monitor.isOver(),
        canDrop: !!monitor.canDrop(),
      }),
    }),
    [repId, slotTime, isValid, onDropSlot]
  );

  const canDrop = isValid;

  return (
    <Box
      ref={drop}
      sx={{
        p: 1,
        mb: 0.5,
        border: canDrop ? '2px solid #4caf50' : '2px dashed #ccc',
        borderRadius: 1,
        backgroundColor: isOver && canDrop ? '#c8e6c9' : canDrop ? '#f1f8e9' : '#f5f5f5',
        cursor: canDrop ? 'grab' : 'not-allowed',
        minHeight: 40,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        transition: 'all 0.2s ease',
        opacity: canDrop ? 1 : 0.6,
      }}
    >
      <Typography variant="caption" color="textSecondary">
        {slot.durationMinutes}分空き
      </Typography>
      {!canDrop && (
        <Typography variant="caption" sx={{ color: '#d32f2f', fontSize: '0.65rem' }}>
          営業時間外
        </Typography>
      )}
    </Box>
  );
};

const DraggableAppointmentCard: React.FC<{
  appointment: Appointment;
}> = ({ appointment }) => {
  const [{ isDragging }, drag] = useDrag(
    () => ({
      type: 'appointment-template',
      item: { title: appointment.title } as DraggedItem,
      collect: (monitor) => ({
        isDragging: !!monitor.isDragging(),
      }),
    }),
    [appointment.title]
  );

  const statusColor = {
    scheduled: 'warning' as const,
    confirmed: 'success' as const,
    cancelled: 'error' as const,
  };

  const statusLabel = {
    scheduled: '予定',
    confirmed: '確定',
    cancelled: 'キャンセル',
  };

  return (
    <Card
      ref={drag}
      sx={{
        opacity: isDragging ? 0.5 : 1,
        cursor: 'grab',
        mb: 1,
        '&:hover': {
          boxShadow: 2,
        },
      }}
    >
      <CardContent sx={{ p: 1, '&:last-child': { pb: 1 } }}>
        <Typography variant="subtitle2" noWrap>
          {appointment.title}
        </Typography>
        <Typography variant="caption" color="textSecondary" sx={{ display: 'block', mt: 0.5 }}>
          {appointment.startTime.toFormat('HH:mm')} - {appointment.endTime.toFormat('HH:mm')}
        </Typography>
        <Chip
          label={statusLabel[appointment.status]}
          size="small"
          color={statusColor[appointment.status]}
          sx={{ mt: 0.5 }}
        />
      </CardContent>
    </Card>
  );
};

const CreateAppointmentDialog: React.FC<{
  open: boolean;
  repId: string;
  startTime: DateTime;
  onClose: () => void;
  onConfirm: (title: string) => void;
}> = ({ open, repId, startTime, onClose, onConfirm }) => {
  const [title, setTitle] = React.useState('');

  const handleConfirm = () => {
    if (title.trim()) {
      onConfirm(title);
      setTitle('');
    }
  };

  const handleClose = () => {
    setTitle('');
    onClose();
  };

  return (
    <Dialog open={open} onClose={handleClose} maxWidth="sm" fullWidth>
      <DialogTitle>新しいアポイントメントを作成</DialogTitle>
      <DialogContent sx={{ pt: 2 }}>
        <Typography variant="caption" color="textSecondary" sx={{ display: 'block', mb: 2 }}>
          営業ID: {repId} | 開始時刻: {startTime.toFormat('yyyy-MM-dd HH:mm')}
        </Typography>
        <TextField
          autoFocus
          margin="dense"
          label="アポイント名"
          fullWidth
          variant="outlined"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          onKeyPress={(e) => {
            if (e.key === 'Enter') {
              handleConfirm();
            }
          }}
          placeholder="例：顧客A 相談"
        />
      </DialogContent>
      <DialogActions>
        <Button onClick={handleClose}>キャンセル</Button>
        <Button onClick={handleConfirm} variant="contained">
          作成
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export const CalendarGridAdvanced: React.FC<CalendarGridAdvancedProps> = ({
  appointments,
  freeSlots,
  onCreateAppointment,
  onError,
}) => {
  const [currentDate, setCurrentDate] = useState(DateTime.now());
  const [dialogOpen, setDialogOpen] = useState(false);
  const [dialogData, setDialogData] = useState<{
    repId: string;
    startTime: DateTime;
  } | null>(null);
  const [lastDropMessage, setLastDropMessage] = useState<string | null>(null);

  const { isValidDropZone, handleDropSlot, handleDragEnd } = useDragDropAppointment(
    onCreateAppointment,
    undefined,
    (result) => {
      if (result?.isValid) {
        setLastDropMessage('アポイントメントが作成されました！');
        setTimeout(() => setLastDropMessage(null), 3000);
      } else if (result?.reason) {
        onError(result.reason);
      }
    }
  );

  const handleSlotDrop = useCallback(
    (repId: string, slotTime: DateTime, title: string) => {
      handleDropSlot(repId, slotTime, title);
    },
    [handleDropSlot]
  );

  const month = currentDate.month;
  const year = currentDate.year;

  // Group appointments by repId
  const appointmentsByRep = new Map<string, Appointment[]>();
  for (const apt of appointments) {
    if (!appointmentsByRep.has(apt.repId)) {
      appointmentsByRep.set(apt.repId, []);
    }
    appointmentsByRep.get(apt.repId)!.push(apt);
  }

  // Get all unique repIds from both appointments and free slots
  const allRepIds = new Set<string>([
    ...appointmentsByRep.keys(),
    ...freeSlots.keys(),
  ]);

  const handlePreviousMonth = () => {
    setCurrentDate(currentDate.minus({ months: 1 }));
  };

  const handleNextMonth = () => {
    setCurrentDate(currentDate.plus({ months: 1 }));
  };

  return (
    <DndProvider backend={HTML5Backend}>
      <Box sx={{ p: 3 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
          <Typography variant="h5">
            {year}年 {month}月 スケジュール管理
          </Typography>
          <Box>
            <Button onClick={handlePreviousMonth} sx={{ mr: 1 }}>
              前月
            </Button>
            <Button onClick={handleNextMonth}>
              次月
            </Button>
          </Box>
        </Box>

        {lastDropMessage && (
          <Alert severity="success" sx={{ mb: 2 }} onClose={() => setLastDropMessage(null)}>
            {lastDropMessage}
          </Alert>
        )}

        {allRepIds.size === 0 ? (
          <Typography color="textSecondary">
            営業情報またはアポイントメント情報がありません
          </Typography>
        ) : (
          <Grid container spacing={3}>
            {Array.from(allRepIds)
              .sort()
              .map((repId) => (
                <Grid item xs={12} sm={6} md={4} key={repId}>
                  <Paper sx={{ p: 2, height: '100%' }}>
                    <Typography variant="h6" sx={{ mb: 2, fontWeight: 'bold' }}>
                      営業ID: {repId}
                    </Typography>

                    {/* Free slots */}
                    <Box sx={{ mb: 2, p: 1, backgroundColor: '#fafafa', borderRadius: 1 }}>
                      <Typography
                        variant="caption"
                        sx={{ fontWeight: 'bold', display: 'block', mb: 1 }}
                      >
                        📅 空き時間
                      </Typography>
                      {(freeSlots.get(repId) || []).length > 0 ? (
                        (freeSlots.get(repId) || []).map((slot, idx) => (
                          <DroppableSlot
                            key={idx}
                            slot={slot}
                            repId={repId}
                            onDropSlot={handleSlotDrop}
                            isValidDropZone={isValidDropZone}
                          />
                        ))
                      ) : (
                        <Typography variant="caption" color="textSecondary">
                          本日の空き枠はありません
                        </Typography>
                      )}
                    </Box>

                    {/* Appointments */}
                    <Box sx={{ p: 1, backgroundColor: '#fffef0', borderRadius: 1 }}>
                      <Typography
                        variant="caption"
                        sx={{ fontWeight: 'bold', display: 'block', mb: 1 }}
                      >
                        📝 スケジュール
                      </Typography>
                      {(appointmentsByRep.get(repId) || [])
                        .filter(
                          (apt) =>
                            apt.startTime.month === month &&
                            apt.startTime.year === year
                        )
                        .sort((a, b) => a.startTime.toMillis() - b.startTime.toMillis())
                        .map((apt) => (
                          <DraggableAppointmentCard key={apt.id} appointment={apt} />
                        ))}
                      {(appointmentsByRep.get(repId) || []).filter(
                        (apt) =>
                          apt.startTime.month === month &&
                          apt.startTime.year === year
                      ).length === 0 && (
                        <Typography variant="caption" color="textSecondary">
                          アポイントメントなし
                        </Typography>
                      )}
                    </Box>
                  </Paper>
                </Grid>
              ))}
          </Grid>
        )}

        {dialogData && (
          <CreateAppointmentDialog
            open={dialogOpen}
            repId={dialogData.repId}
            startTime={dialogData.startTime}
            onClose={() => {
              setDialogOpen(false);
              setDialogData(null);
            }}
            onConfirm={(title) => {
              if (dialogData) {
                onCreateAppointment(dialogData.repId, dialogData.startTime, title);
                setDialogOpen(false);
                setDialogData(null);
              }
            }}
          />
        )}
      </Box>
    </DndProvider>
  );
};

export default CalendarGridAdvanced;
