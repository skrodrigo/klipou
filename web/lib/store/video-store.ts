import { create } from 'zustand'

interface VideoState {
  videoFile: File | null
  videoUrl: string
  setVideo: (file: File) => void
  clearVideo: () => void
}

export const useVideoStore = create<VideoState>((set) => ({
  videoFile: null,
  videoUrl: '',
  setVideo: (file) => {
    const url = URL.createObjectURL(file)
    set({ videoFile: file, videoUrl: url })
  },
  clearVideo: () => set({ videoFile: null, videoUrl: '' }),
}))
