export type VideoClip = {
  id: number
  title: string
  created_at: string
  video_id: number
}

export type Video = {
  id: number
  title: string
  created_at: string
  status: "pending" | "processing" | "completed" | "failed"
  progress?: number
  duration?: number
  thumbnail?: string
  clips: VideoClip[]
}

export type CreateVideoResponse = Video

export type ListVideosResponse = {
  results: Video[]
}

export type ListVideoClipsResponse = {
  results: VideoClip[]
}
