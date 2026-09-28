import React, { useCallback, useState } from 'react';
import {
  Box,
  Grid,
  Paper,
  Typography,
  Card,
  CardContent,
  Chip,
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
} from '@mui/material';
import { DndProvider, useDrag, useDrop } from 'react-dnd';
import { HTML5Backend } from 'react-dnd-html5-backend';
import { DateTime } from 'luxon';

export interface Appointment {
  id: string;
  title: string;
  startTime: DateTime;
  endTime: DateTime;
  status: 'scheduled' | 'confirmed' | 'cancelled';
  repId: string;
}

export interface FreeSlot {
  startTime: string;
  endTime: string;
  durationMinutes: number;
}

export interface CalendarGridProps {
  appointments: Appointment[];
  freeSlots: Map<string, FreeSlot[]>; // key: repId, value: list of free slots
  onCreateAppointment: (repId: string, startTime: DateTime, title: string) => void;
}

interface DraggedItem {
  title: string;
}

const DraggableSlot: React.FC<{
  slot: FreeSlot;
  repId: string;
  onDrop: (repId: string, startTime: DateTime) => void;
}> = ({ slot, repId, onDrop }) => {
  const [{ isOver }, drop] = useDrop(
    () => ({
      accept: 'appointment-template',
      drop: () => {
        onDrop(repId, DateTime.fromISO(slot.startTime));
      },
      collect: (monitor) => ({
        isOver: !!monitor.isOver(),
      }),
    }),
    [repId, slot, onDrop]
  );

  return (
    <Box
      ref={drop}
      sx={{
        p: 1,
        mb: 0.5,
        border: '2px dashed #ccc',
        borderRadius: 1,
        backgroundColor: isOver ? '#e3f2fd' : '#f5f5f5',
        cursor: 'grab',
        minHeight: 40,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        transition: 'background-color 0.2s',
      }}
    >
      <Typography variant="caption" color="textSecondary">
        {slot.durationMinutes}分空き
      </Typography>
    </Box>
  );
};

const AppointmentCard: React.FC<{
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
  const [title, setTitle] = useState('');

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

export const CalendarGrid: React.FC<CalendarGridProps> = ({
  appointments,
  freeSlots,
  onCreateAppointment,
}) => {
  const [currentDate, setCurrentDate] = useState(DateTime.now());
  const [dialogOpen, setDialogOpen] = useState(false);
  const [dialogData, setDialogData] = useState<{
    repId: string;
    startTime: DateTime;
  } | null>(null);

  const handleDrop = useCallback(
    (repId: string, startTime: DateTime) => {
      setDialogData({ repId, startTime });
      setDialogOpen(true);
    },
    []
  );

  const handleConfirmDialog = useCallback(
    (title: string) => {
      if (dialogData) {
        onCreateAppointment(dialogData.repId, dialogData.startTime, title);
        setDialogOpen(false);
        setDialogData(null);
      }
    },
    [dialogData, onCreateAppointment]
  );

  const handleCloseDialog = useCallback(() => {
    setDialogOpen(false);
    setDialogData(null);
  }, []);

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
            {year}年 {month}月 スケジュール
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

        {allRepIds.size === 0 ? (
          <Typography color="textSecondary">
            営業情報またはアポイントメント情報がありません
          </Typography>
        ) : (
          <Grid container spacing={3}>
            {Array.from(allRepIds).sort().map((repId) => (
              <Grid item xs={12} sm={6} md={4} key={repId}>
                <Paper sx={{ p: 2, height: '100%', minHeight: 400 }}>
                  <Typography variant="h6" sx={{ mb: 2, fontWeight: 'bold' }}>
                    営業ID: {repId}
                  </Typography>

                  {/* Free slots */}
                  <Box sx={{ mb: 3 }}>
                    <Typography variant="caption" sx={{ fontWeight: 'bold', display: 'block', mb: 1 }}>
                      空き時間
                    </Typography>
                    {(freeSlots.get(repId) || []).length === 0 ? (
                      <Typography variant="caption" color="textSecondary">
                        空き枠なし
                      </Typography>
                    ) : (
                      (freeSlots.get(repId) || []).map((slot, idx) => (
                        <DraggableSlot
                          key={idx}
                          slot={slot}
                          repId={repId}
                          onDrop={handleDrop}
                        />
                      ))
                    )}
                  </Box>

                  {/* Appointments */}
                  <Box>
                    <Typography variant="caption" sx={{ fontWeight: 'bold', display: 'block', mb: 1 }}>
                      スケジュール
                    </Typography>
                    {(appointmentsByRep.get(repId) || [])
                      .filter(
                        (apt) =>
                          apt.startTime.month === month &&
                          apt.startTime.year === year
                      )
                      .sort((a, b) => a.startTime.toMillis() - b.startTime.toMillis())
                      .map((apt) => (
                        <AppointmentCard key={apt.id} appointment={apt} />
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
            onClose={handleCloseDialog}
            onConfirm={handleConfirmDialog}
          />
        )}
      </Box>
    </DndProvider>
  );
};

export default CalendarGrid;
