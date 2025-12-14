"use client"

import { useState } from "react"

import { EventCalendar } from "@/components/event-calendar"
import type { CalendarEvent } from "@/components/types"
import { sampleEvents } from "@/lib/events/sample-events"

export default function CalendarPage() {
  const [events, setEvents] = useState<CalendarEvent[]>(sampleEvents)

  const handleEventAdd = (event: CalendarEvent) => {
    setEvents((prev) => [...prev, event])
  }

  const handleEventUpdate = (updatedEvent: CalendarEvent) => {
    setEvents((prev) => prev.map((event) => (event.id === updatedEvent.id ? updatedEvent : event)))
  }

  const handleEventDelete = (eventId: string) => {
    setEvents((prev) => prev.filter((event) => event.id !== eventId))
  }

  return (
    <section className="flex flex-col gap-6 p-12">
      <EventCalendar
        events={events}
        onEventAdd={handleEventAdd}
        onEventDelete={handleEventDelete}
        onEventUpdate={handleEventUpdate}
      />
    </section>
  )
}
