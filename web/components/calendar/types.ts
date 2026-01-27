export type CalendarView = "month" | "week" | "day" | "agenda";

export interface CalendarEvent {
  id: string;
  title: string;
  description?: string;
  start: Date;
  end: Date;
  allDay?: boolean;
  color?: EventColor;
  location?: string;
  meta?: {
    schedule_id?: string;
    clip_id?: string;
    platform?: string;
  };
}

export type EventColor =
  | "sky"
  | "amber"
  | "violet"
  | "rose"
  | "emerald"
  | "orange";
