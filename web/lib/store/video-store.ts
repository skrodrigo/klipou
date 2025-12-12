import { create } from 'zustand'

interface VideoState {
  videoFile: File | null
  videoUrl: string | null
  setVideoFile: (file: File | null) => void
  clearVideo: () => void
}

export const useVideoStore = create<VideoState>((set) => ({
  videoFile: null,
  videoUrl: null,
  setVideoFile: (file) => {
    set((state) => {
      if (state.videoUrl) {
        URL.revokeObjectURL(state.videoUrl)
      }
      const newUrl = file ? URL.createObjectURL(file) : null
      return { videoFile: file, videoUrl: newUrl }
    })
  },
  clearVideo: () =>
    set((state) => {
      if (state.videoUrl) {
        URL.revokeObjectURL(state.videoUrl)
      }
      return { videoFile: null, videoUrl: null }
    }),
}))
