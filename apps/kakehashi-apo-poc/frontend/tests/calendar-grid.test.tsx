import React from 'react';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { CalendarGrid, Appointment } from '../src/components/CalendarGrid';
import { DateTime } from 'luxon';

describe('CalendarGrid Component', () => {
  const mockAppointments: Appointment[] = [
    {
      id: 'apt-001',
      title: '顧客A 相談',
      startTime: DateTime.now().set({ hour: 10, minute: 0 }),
      endTime: DateTime.now().set({ hour: 11, minute: 0 }),
      status: 'scheduled',
      repId: 'rep-001',
    },
    {
      id: 'apt-002',
      title: '顧客B 提案',
      startTime: DateTime.now().set({ hour: 14, minute: 0 }),
      endTime: DateTime.now().set({ hour: 15, minute: 0 }),
      status: 'confirmed',
      repId: 'rep-002',
    },
  ];

  const mockFreeSlots = new Map([
    ['rep-001', [
      {
        startTime: DateTime.now().set({ hour: 9, minute: 0 }).toISO()!,
        endTime: DateTime.now().set({ hour: 10, minute: 0 }).toISO()!,
        durationMinutes: 60,
      },
      {
        startTime: DateTime.now().set({ hour: 11, minute: 0 }).toISO()!,
        endTime: DateTime.now().set({ hour: 13, minute: 0 }).toISO()!,
        durationMinutes: 120,
      },
    ]],
    ['rep-002', [
      {
        startTime: DateTime.now().set({ hour: 13, minute: 0 }).toISO()!,
        endTime: DateTime.now().set({ hour: 14, minute: 0 }).toISO()!,
        durationMinutes: 60,
      },
    ]],
  ]);

  const mockOnCreateAppointment = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('should render calendar grid with title', () => {
    const now = DateTime.now();
    render(
      <CalendarGrid
        appointments={mockAppointments}
        freeSlots={mockFreeSlots}
        onCreateAppointment={mockOnCreateAppointment}
      />
    );
    expect(screen.getByText(new RegExp(`${now.year}年 ${now.month}月 スケジュール`))).toBeInTheDocument();
  });

  it('should display all unique representatives', () => {
    render(
      <CalendarGrid
        appointments={mockAppointments}
        freeSlots={mockFreeSlots}
        onCreateAppointment={mockOnCreateAppointment}
      />
    );
    expect(screen.getByText('営業ID: rep-001')).toBeInTheDocument();
    expect(screen.getByText('営業ID: rep-002')).toBeInTheDocument();
  });

  it('should display free slots for each representative', () => {
    render(
      <CalendarGrid
        appointments={mockAppointments}
        freeSlots={mockFreeSlots}
        onCreateAppointment={mockOnCreateAppointment}
      />
    );
    // Check for free slot durations
    const slots = screen.getAllByText(/分空き/);
    expect(slots.length).toBeGreaterThan(0);
  });

  it('should display appointments with correct details', () => {
    render(
      <CalendarGrid
        appointments={mockAppointments}
        freeSlots={mockFreeSlots}
        onCreateAppointment={mockOnCreateAppointment}
      />
    );
    expect(screen.getByText('顧客A 相談')).toBeInTheDocument();
    expect(screen.getByText('顧客B 提案')).toBeInTheDocument();
  });

  it('should display appointment status labels', () => {
    render(
      <CalendarGrid
        appointments={mockAppointments}
        freeSlots={mockFreeSlots}
        onCreateAppointment={mockOnCreateAppointment}
      />
    );
    expect(screen.getByText('予定')).toBeInTheDocument(); // scheduled -> 予定
    expect(screen.getByText('確定')).toBeInTheDocument(); // confirmed -> 確定
  });

  it('should display appointment times', () => {
    render(
      <CalendarGrid
        appointments={mockAppointments}
        freeSlots={mockFreeSlots}
        onCreateAppointment={mockOnCreateAppointment}
      />
    );
    // Check if times are displayed (HH:mm format)
    const timeRegex = /\d{2}:\d{2}/;
    const timeElements = screen.getAllByText(timeRegex);
    expect(timeElements.length).toBeGreaterThan(0);
  });

  it('should handle empty appointments', () => {
    render(
      <CalendarGrid
        appointments={[]}
        freeSlots={mockFreeSlots}
        onCreateAppointment={mockOnCreateAppointment}
      />
    );
    expect(screen.getByText(/営業ID: rep-001/)).toBeInTheDocument();
    expect(screen.getAllByText('アポイントメントなし').length).toBeGreaterThan(0);
  });

  it('should handle empty free slots', () => {
    const emptyFreeSlots = new Map([['rep-001', []]]);
    render(
      <CalendarGrid
        appointments={mockAppointments.slice(0, 1)}
        freeSlots={emptyFreeSlots}
        onCreateAppointment={mockOnCreateAppointment}
      />
    );
    expect(screen.getByText('空き枠なし')).toBeInTheDocument();
  });

  it('should display navigation buttons', () => {
    render(
      <CalendarGrid
        appointments={mockAppointments}
        freeSlots={mockFreeSlots}
        onCreateAppointment={mockOnCreateAppointment}
      />
    );
    expect(screen.getByText('前月')).toBeInTheDocument();
    expect(screen.getByText('次月')).toBeInTheDocument();
  });

  it('should handle month navigation', async () => {
    const user = userEvent.setup();
    const { rerender } = render(
      <CalendarGrid
        appointments={mockAppointments}
        freeSlots={mockFreeSlots}
        onCreateAppointment={mockOnCreateAppointment}
      />
    );

    const nextMonthButton = screen.getByText('次月');
    await user.click(nextMonthButton);

    // The component should still render without errors
    expect(screen.getByText('前月')).toBeInTheDocument();
  });

  it('should display message when no data is available', () => {
    render(
      <CalendarGrid
        appointments={[]}
        freeSlots={new Map()}
        onCreateAppointment={mockOnCreateAppointment}
      />
    );
    expect(screen.getByText('営業情報またはアポイントメント情報がありません')).toBeInTheDocument();
  });

  it('should sort appointments by start time', () => {
    const unsortedAppointments: Appointment[] = [
      {
        id: 'apt-001',
        title: '午後の会議',
        startTime: DateTime.now().set({ hour: 14, minute: 0 }),
        endTime: DateTime.now().set({ hour: 15, minute: 0 }),
        status: 'scheduled',
        repId: 'rep-001',
      },
      {
        id: 'apt-002',
        title: '午前の会議',
        startTime: DateTime.now().set({ hour: 10, minute: 0 }),
        endTime: DateTime.now().set({ hour: 11, minute: 0 }),
        status: 'scheduled',
        repId: 'rep-001',
      },
    ];

    render(
      <CalendarGrid
        appointments={unsortedAppointments}
        freeSlots={mockFreeSlots}
        onCreateAppointment={mockOnCreateAppointment}
      />
    );

    const cards = screen.getAllByText(/の会議/);
    expect(cards[0].textContent).toContain('午前の会議');
    expect(cards[1].textContent).toContain('午後の会議');
  });

  it('should filter appointments by current month and year', () => {
    const futureAppointment: Appointment = {
      id: 'apt-future',
      title: '来月の会議',
      startTime: DateTime.now().plus({ months: 1 }).set({ hour: 10, minute: 0 }),
      endTime: DateTime.now().plus({ months: 1 }).set({ hour: 11, minute: 0 }),
      status: 'scheduled',
      repId: 'rep-001',
    };

    const allAppointments = [...mockAppointments, futureAppointment];

    render(
      <CalendarGrid
        appointments={allAppointments}
        freeSlots={mockFreeSlots}
        onCreateAppointment={mockOnCreateAppointment}
      />
    );

    // The future appointment should not be displayed in the current month view
    expect(screen.queryByText('来月の会議')).not.toBeInTheDocument();
  });
});
