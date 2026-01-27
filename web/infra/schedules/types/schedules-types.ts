export type ScheduleStatus = "scheduled" | "posted" | "failed" | "canceled"
export type SchedulePlatform = "tiktok" | "instagram" | "youtube" | "facebook" | "linkedin" | "twitter"

export type Schedule = {
  schedule_id: string
  clip_id: string
  clip_title: string
  clip_storage_path?: string | null
  clip_thumbnail_storage_path?: string | null
  platform: SchedulePlatform
  status: ScheduleStatus
  scheduled_time: string | null
  posted_at: string | null
  post_url: string | null
  created_at: string
}

export type ListSchedulesResponse = {
  total: number
  limit: number
  offset: number
  schedules: Schedule[]
}

export type AvailableClip = {
  clip_id: string
  video_id: string | null
  title: string
  created_at: string
  video_url: string | null
  thumbnail_url: string | null
  ratio: string | null
  duration: number | null
}

export type ListAvailableClipsResponse = {
  total: number
  limit: number
  offset: number
  clips: AvailableClip[]
}

export type CreateSchedulePayload = {
  clip_id: string
  platform: SchedulePlatform
  scheduled_time: string
  organization_id: string
  user_id: string
}

export type CreateScheduleResponse = {
  schedule_id: string
  clip_id: string
  platform: SchedulePlatform
  status: ScheduleStatus
  scheduled_time: string | null
}

export type UpdateSchedulePayload = {
  scheduled_time: string
  organization_id: string
}

export type UpdateScheduleResponse = {
  schedule_id: string
  scheduled_time: string | null
}

export type CancelSchedulePayload = {
  organization_id: string
}

export type CancelScheduleResponse = {
  schedule_id: string
  status: ScheduleStatus
}
