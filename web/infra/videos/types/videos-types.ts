export type Video = {
  video_id: string
  title: string
  source_type: "upload" | "youtube" | "tiktok" | "instagram" | "url"
  source_url?: string
  status: "ingestion" | "queued" | "downloading" | "normalizing" | "transcribing" | "analyzing" | "embedding" | "selecting" | "reframing" | "clipping" | "captioning" | "completed" | "failed"
  duration?: number
  resolution?: string
  thumbnail?: string
  file_size?: number
  created_at: string
  updated_at: string
  current_step?: string
  error_message?: string
  clips_count?: number
}

export type Clip = {
  clip_id: string
  title: string
  start_time: number
  end_time: number
  duration?: number
  ratio?: string
  engagement_score?: number
  confidence_score?: number
  storage_path?: string
  video_url?: string
  full_video_url?: string | null
  thumbnail_url?: string
  transcript?: string
  created_at: string
  updated_at: string
}

export type TranscriptSegment = {
  start: number
  end: number
  text: string
}

export type VideoTrimContextResponse = {
  video_id: string
  video_url: string | null
  transcript: {
    language: string | null
    segments: TranscriptSegment[]
  }
}

export type UpdateClipTrimResponse = {
  clip_id: string
  start_time: number
  end_time: number
  duration: number
  updated_at: string
}

export type Job = {
  job_id: string
  video_id: string
  organization_id: string
  status: "ingestion" | "queued" | "downloading" | "normalizing" | "transcribing" | "analyzing" | "embedding" | "selecting" | "reframing" | "clipping" | "captioning" | "done" | "failed"
  progress: number
  current_step?: string
  error_message?: string
  credits_consumed: number
  created_at: string
  started_at?: string
  completed_at?: string
}

export type CreateVideoResponse = {
  detail: string
  video: Video
}

export type ListVideosResponse = {
  results: Video[]
}

export type ListVideoClipsResponse = {
  results: Clip[]
}

export type VideoProgressResponse = {
  video_id: string
  status: string
  progress: number
  current_step?: string
  error?: string
}

export type VideoStatusResponse = {
  video_id: string
  status: string
  message: string
}

export type ClipDetailsResponse = {
  clip: Clip
}

export type DownloadClipResponse = {
  clip_id: string
  title: string
  download_url: string
  expires_in: number
}

export type DeleteClipResponse = {
  clip_id: string
  status: string
}

export type SubmitClipFeedbackPayload = {
  rating: "good" | "bad"
  comment?: string
}

export type SubmitClipFeedbackResponse = {
  detail: string
  clip_id: string
}

export type CreateJobPayload = {
  video_id: string
  organization_id: string
  user_id: string
  configuration?: {
    language?: string
    target_ratios?: string[]
    max_clip_duration?: number
    num_clips?: number
    auto_schedule?: boolean
  }
}

export type CreateJobResponse = {
  job_id: string
  status: string
  task_id: string
  credits_consumed: number
  credits_remaining: number
}

export type GetJobStatusResponse = {
  job: Job
}

export type ListJobsResponse = {
  jobs: Job[]
  total: number
}

export interface GenerateUploadUrlResponse {
  upload_url: string
  video_id: string
  key: string
}

export interface ConfirmUploadResponse {
  video_id: string
  status: string
}

export interface IngestFromUrlResponse {
  video_id: string
  status: string
  title: string
  duration: number | null
  file_size: number | null
  thumbnail_url: string | null
  task_id: string | null
}
