"use client"

import { useEffect, useMemo, useState } from "react"

import type { CalendarEvent } from "@/components/calendar"
import { EventCalendar } from "@/components/calendar/event-calendar"

import { useQuery } from "@tanstack/react-query"
import { getSession } from "@/infra/auth/auth"
import {
  cancelSchedule,
  createSchedule,
  listAvailableClipsForCalendar,
  listSchedules,
  updateSchedule,
} from "@/infra/schedules/schedules"
import type { AvailableClip, Schedule } from "@/infra/schedules/types/schedules-types"

export default function CalendarPage() {
  const { data: user } = useQuery({
    queryKey: ["auth-session"],
    queryFn: getSession,
  })

  const organizationId = user?.organization_id || ""
  const userId = (user as any)?.user_id || ""

  const range = useMemo(() => {
    const now = new Date()
    const start = new Date(now)
    start.setDate(start.getDate() - 30)
    start.setHours(0, 0, 0, 0)

    const end = new Date(now)
    end.setDate(end.getDate() + 90)
    end.setHours(23, 59, 59, 999)

    return {
      start: start.toISOString(),
      end: end.toISOString(),
    }
  }, [])

  const { data: availableClips = [] } = useQuery({
    queryKey: ["calendar-available-clips", organizationId],
    queryFn: () =>
      listAvailableClipsForCalendar({
        organizationId,
        userOrganizationId: organizationId,
        limit: 200,
        offset: 0,
      }),
    enabled: !!organizationId,
  })

  const { data: schedules = [] } = useQuery({
    queryKey: ["calendar-schedules", organizationId, range.start, range.end],
    queryFn: () =>
      listSchedules({
        organizationId,
        userOrganizationId: organizationId,
        start: range.start,
        end: range.end,
        limit: 500,
        offset: 0,
      }),
    enabled: !!organizationId,
  })

  const [events, setEvents] = useState<CalendarEvent[]>([])

  useEffect(() => {
    const nextEvents: CalendarEvent[] = schedules
      .filter((s) => !!s.scheduled_time)
      .map((s) => {
        const start = new Date(s.scheduled_time as string)
        const end = new Date(start)
        end.setHours(end.getHours() + 1)
        return {
          id: s.schedule_id,
          title: `[${s.platform}] ${s.clip_title}`,
          start,
          end,
          allDay: false,
          color: s.status === "posted" ? "emerald" : s.status === "failed" ? "rose" : "sky",
          meta: {
            schedule_id: s.schedule_id,
            clip_id: s.clip_id,
            platform: s.platform,
          },
        }
      })

    setEvents(nextEvents)
  }, [schedules])

  const handleEventAdd = async (event: CalendarEvent) => {
    if (!organizationId || !userId) return

    const clipId = event.meta?.clip_id
    const platform = (event.meta?.platform || "tiktok") as Schedule["platform"]

    if (!clipId) return

    const created = await createSchedule({
      clip_id: clipId,
      platform,
      scheduled_time: event.start.toISOString(),
      organization_id: organizationId,
      user_id: userId,
    })

    setEvents((prev) =>
      prev.concat({
        ...event,
        id: created.schedule_id,
        title: event.title || "Post agendado",
        meta: {
          ...(event.meta ?? {}),
          schedule_id: created.schedule_id,
          clip_id: clipId,
          platform,
        },
      })
    )
  }

  const handleEventUpdate = async (updatedEvent: CalendarEvent) => {
    const scheduleId = updatedEvent.meta?.schedule_id || updatedEvent.id
    if (!organizationId || !scheduleId || !userId) return

    const prevEvent = events.find((e) => e.id === updatedEvent.id)
    const prevClipId = prevEvent?.meta?.clip_id
    const prevPlatform = prevEvent?.meta?.platform

    const nextClipId = updatedEvent.meta?.clip_id
    const nextPlatform = updatedEvent.meta?.platform

    const clipOrPlatformChanged =
      (prevClipId && nextClipId && prevClipId !== nextClipId) ||
      (prevPlatform && nextPlatform && prevPlatform !== nextPlatform)

    if (clipOrPlatformChanged) {
      await cancelSchedule(scheduleId, { organization_id: organizationId })
      const created = await createSchedule({
        clip_id: nextClipId || prevClipId || "",
        platform: ((nextPlatform || prevPlatform || "tiktok") as unknown) as Schedule["platform"],
        scheduled_time: updatedEvent.start.toISOString(),
        organization_id: organizationId,
        user_id: userId,
      })

      setEvents((prev) =>
        prev.map((event) =>
          event.id === updatedEvent.id
            ? {
              ...updatedEvent,
              id: created.schedule_id,
              meta: {
                ...(updatedEvent.meta ?? {}),
                schedule_id: created.schedule_id,
              },
            }
            : event
        )
      )
      return
    }

    await updateSchedule(scheduleId, {
      scheduled_time: updatedEvent.start.toISOString(),
      organization_id: organizationId,
    })

    setEvents((prev) => prev.map((event) => (event.id === updatedEvent.id ? updatedEvent : event)))
  }

  const handleEventDelete = async (eventId: string) => {
    if (!organizationId) return

    await cancelSchedule(eventId, { organization_id: organizationId })
    setEvents((prev) => prev.filter((event) => event.id !== eventId))
  }

  return (
    <section className="flex flex-col gap-6 p-12">
      <EventCalendar
        events={events}
        availableClips={availableClips.map((c) => ({ clip_id: c.clip_id, title: c.title }))}
        onEventAdd={handleEventAdd}
        onEventDelete={handleEventDelete}
        onEventUpdate={handleEventUpdate}
      />
    </section>
  )
}
