import { request } from "../http"
import type {
  AvailableClip,
  CancelSchedulePayload,
  CancelScheduleResponse,
  CreateSchedulePayload,
  CreateScheduleResponse,
  ListAvailableClipsResponse,
  ListSchedulesResponse,
  Schedule,
  UpdateSchedulePayload,
  UpdateScheduleResponse,
} from "./types/schedules-types"

export type {
  Schedule,
  AvailableClip,
  ListSchedulesResponse,
  ListAvailableClipsResponse,
  CreateSchedulePayload,
  CreateScheduleResponse,
  UpdateSchedulePayload,
  UpdateScheduleResponse,
  CancelSchedulePayload,
  CancelScheduleResponse,
}

export async function listSchedules(params: {
  organizationId: string
  userOrganizationId: string
  start?: string
  end?: string
  status?: string
  platform?: string
  limit?: number
  offset?: number
}): Promise<Schedule[]> {
  const q = new URLSearchParams()
  q.set("user_organization_id", params.userOrganizationId)
  if (params.start) q.set("start", params.start)
  if (params.end) q.set("end", params.end)
  if (params.status) q.set("status", params.status)
  if (params.platform) q.set("platform", params.platform)
  if (params.limit != null) q.set("limit", String(params.limit))
  if (params.offset != null) q.set("offset", String(params.offset))

  const data = await request<ListSchedulesResponse>(
    `/api/organizations/${params.organizationId}/schedules/?${q.toString()}`
  )
  return data.schedules ?? []
}

export async function createSchedule(payload: CreateSchedulePayload): Promise<CreateScheduleResponse> {
  return request<CreateScheduleResponse>("/api/schedules/", {
    method: "POST",
    body: JSON.stringify(payload),
  })
}

export async function updateSchedule(scheduleId: string, payload: UpdateSchedulePayload): Promise<UpdateScheduleResponse> {
  return request<UpdateScheduleResponse>(`/api/schedules/${scheduleId}/`, {
    method: "PUT",
    body: JSON.stringify(payload),
  })
}

export async function cancelSchedule(scheduleId: string, payload: CancelSchedulePayload): Promise<CancelScheduleResponse> {
  return request<CancelScheduleResponse>(`/api/schedules/${scheduleId}/cancel/`, {
    method: "DELETE",
    body: JSON.stringify(payload),
  })
}

export async function listAvailableClipsForCalendar(params: {
  organizationId: string
  userOrganizationId: string
  limit?: number
  offset?: number
}): Promise<AvailableClip[]> {
  const q = new URLSearchParams()
  q.set("user_organization_id", params.userOrganizationId)
  if (params.limit != null) q.set("limit", String(params.limit))
  if (params.offset != null) q.set("offset", String(params.offset))

  const data = await request<ListAvailableClipsResponse>(
    `/api/organizations/${params.organizationId}/calendar/clips/?${q.toString()}`
  )
  return data.clips ?? []
}
