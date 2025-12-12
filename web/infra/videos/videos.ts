import { request, requestSSE } from "../http"
import type {
  Video,
  VideoClip,
  CreateVideoResponse,
  ListVideosResponse,
  ListVideoClipsResponse,
} from "./types/videos-types"

export type { Video, VideoClip, CreateVideoResponse, ListVideosResponse, ListVideoClipsResponse }

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

export async function listVideoClips(videoId: number | null): Promise<VideoClip[]> {
  if (!videoId) return []
  const data = await request<ListVideoClipsResponse>(`/api/videos/${videoId}/clips/`)
  return data.results ?? []
}

export function getVideoProgress(videoId: number | null): EventSource | null {
  if (!videoId) return null
  return requestSSE(`/api/videos/${videoId}/progress/`)
}
