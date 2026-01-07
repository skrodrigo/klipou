import { request, requestSSE } from "../http"
import type {
  Video,
  Clip,
  Job,
  TranscriptSegment,
  VideoTrimContextResponse,
  UpdateClipTrimResponse,
  CreateVideoResponse,
  ListVideosResponse,
  ListVideoClipsResponse,
  VideoProgressResponse,
  VideoStatusResponse,
  ClipDetailsResponse,
  DownloadClipResponse,
  DeleteClipResponse,
  SubmitClipFeedbackPayload,
  SubmitClipFeedbackResponse,
  CreateJobPayload,
  CreateJobResponse,
  GetJobStatusResponse,
  ListJobsResponse,
} from "./types/videos-types"

export type {
  Video,
  Clip,
  Job,
  TranscriptSegment,
  VideoTrimContextResponse,
  UpdateClipTrimResponse,
  CreateVideoResponse,
  ListVideosResponse,
  ListVideoClipsResponse,
  VideoProgressResponse,
  VideoStatusResponse,
  ClipDetailsResponse,
  DownloadClipResponse,
  DeleteClipResponse,
  SubmitClipFeedbackPayload,
  SubmitClipFeedbackResponse,
  CreateJobPayload,
  CreateJobResponse,
  GetJobStatusResponse,
  ListJobsResponse,
}

// Videos
export async function listVideos(): Promise<Video[]> {
  const data = await request<ListVideosResponse>("/api/videos/")
  return data.results ?? []
}

export async function createVideo(file: File, title?: string): Promise<CreateVideoResponse> {
  const formData = new FormData()
  formData.append("file", file)
  formData.append("title", title || file.name)
  return request<CreateVideoResponse>("/api/videos/", {
    method: "POST",
    body: formData,
  })
}

export async function deleteVideo(videoId: string, organizationId: string): Promise<void> {
  await request(`/api/videos/${videoId}/delete/`, {
    method: "DELETE",
    body: JSON.stringify({ organization_id: organizationId }),
  })
}

export async function renameVideo(videoId: string, title: string, organizationId: string): Promise<any> {
  return request(`/api/videos/${videoId}/rename/`, {
    method: "PUT",
    body: JSON.stringify({ title, organization_id: organizationId }),
  })
}

export async function getVideoDetails(videoId: string, organizationId: string): Promise<any> {
  return request(`/api/videos/${videoId}/`, {
    method: "GET",
    headers: {
      "X-Organization-ID": organizationId,
    },
  })
}

export function getVideoProgress(videoId: string): EventSource | null {
  if (!videoId) return null
  return requestSSE(`/api/videos/${videoId}/progress/`)
}

export async function updateVideoStatus(videoId: string, status: string): Promise<VideoStatusResponse> {
  return request<VideoStatusResponse>(`/api/videos/${videoId}/status/`, {
    method: "PUT",
    body: JSON.stringify({ status }),
  })
}

// Clips
export async function listVideoClips(videoId: string): Promise<Clip[]> {
  if (!videoId) return []
  const data = await request<ListVideoClipsResponse>(`/api/videos/${videoId}/clips/`)
  return data.results ?? []
}

export async function getClipDetails(clipId: string): Promise<Clip> {
  const data = await request<ClipDetailsResponse>(`/api/clips/${clipId}/`)
  return data.clip
}

export async function downloadClip(clipId: string, organizationId: string): Promise<DownloadClipResponse> {
  return request<DownloadClipResponse>(`/api/clips/${clipId}/download/`, {
    method: "GET",
    headers: {
      "X-Organization-ID": organizationId,
    },
  })
}

export async function deleteClip(clipId: string, organizationId: string): Promise<DeleteClipResponse> {
  return request<DeleteClipResponse>(`/api/clips/${clipId}/delete/`, {
    method: "DELETE",
    body: JSON.stringify({ organization_id: organizationId }),
  })
}

export async function submitClipFeedback(
  clipId: string,
  payload: SubmitClipFeedbackPayload
): Promise<SubmitClipFeedbackResponse> {
  return request<SubmitClipFeedbackResponse>(`/api/clips/${clipId}/feedback/`, {
    method: "POST",
    body: JSON.stringify(payload),
  })
}

export async function renameClip(clipId: string, title: string, organizationId: string): Promise<any> {
  return request(`/api/clips/${clipId}/rename/`, {
    method: "PUT",
    body: JSON.stringify({ title, organization_id: organizationId }),
  })
}

export async function duplicateClip(clipId: string, organizationId: string): Promise<any> {
  return request(`/api/clips/${clipId}/duplicate/`, {
    method: "POST",
    body: JSON.stringify({ organization_id: organizationId }),
  })
}

export async function getVideoTrimContext(videoId: string, organizationId: string): Promise<VideoTrimContextResponse> {
  return request<VideoTrimContextResponse>(`/api/videos/${videoId}/trim-context/?organization_id=${organizationId}`, {
    method: "GET",
    headers: {
      "X-Organization-ID": organizationId,
    },
  })
}

export async function updateClipTrim(
  clipId: string,
  payload: { organization_id: string; start_time: number; end_time: number }
): Promise<UpdateClipTrimResponse> {
  return request<UpdateClipTrimResponse>(`/api/clips/${clipId}/trim/`, {
    method: "PUT",
    body: JSON.stringify(payload),
  })
}

// Jobs
export async function createJob(payload: CreateJobPayload): Promise<CreateJobResponse> {
  return request<CreateJobResponse>("/api/jobs/", {
    method: "POST",
    body: JSON.stringify(payload),
  })
}

export async function getJobStatus(jobId: string): Promise<Job> {
  const data = await request<GetJobStatusResponse>(`/api/jobs/${jobId}/`)
  return data.job
}

export function getJobProgress(jobId: string): EventSource | null {
  if (!jobId) return null
  return requestSSE(`/api/jobs/${jobId}/stream/`)
}

export async function listJobs(organizationId: string): Promise<Job[]> {
  const data = await request<ListJobsResponse>(`/api/organizations/${organizationId}/jobs/`)
  return data.jobs ?? []
}

// Organization
export async function getOrganization(organizationId: string): Promise<any> {
  return request(`/api/organizations/${organizationId}/`)
}

export async function getOrganizationCredits(organizationId: string): Promise<{ credits_available: number; credits_monthly: number }> {
  return request<{ credits_available: number; credits_monthly: number }>(`/api/organizations/${organizationId}/credits/`)
}
