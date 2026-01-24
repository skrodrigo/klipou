"use client"

import { Button } from "@/components/ui/button"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
} from "@/components/ui/select"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import { useVideoStore } from "@/lib/store/video-store"
import { AlertSquareIcon, ArrowLeft02Icon, Calendar01Icon, Clock01Icon } from "@hugeicons/core-free-icons"
import { HugeiconsIcon } from "@hugeicons/react"
import { useRouter } from "next/navigation"
import { useState, useEffect } from "react"
import { toast } from "sonner"
import { useQuery } from "@tanstack/react-query"
import { getSession } from "@/infra/auth/auth"
import { startIngestionFromUrl } from "@/infra/videos/upload"
import { Spinner } from "@/components/ui/spinner"

export default function VideoSettingsPage() {
  const router = useRouter()
  const { videoFile, videoUrl, videoId, videoTitle, thumbnailUrl, duration, fileSize, taskId, setProcessingConfig } = useVideoStore()
  const [clipLength, setClipLength] = useState("60-90")
  const [autoSchedule, setAutoSchedule] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [videoDuration, setVideoDuration] = useState(0)

  const { data: user } = useQuery({
    queryKey: ["auth-session"],
    queryFn: getSession,
  })

  useEffect(() => {
    if (!videoUrl) return

    if (duration) {
      setVideoDuration(Math.ceil(duration))
      return
    }

    const video = document.createElement('video')

    const handleLoadedMetadata = () => {
      setVideoDuration(Math.ceil(video.duration))
    }

    video.addEventListener('loadedmetadata', handleLoadedMetadata)
    video.src = videoUrl

    return () => {
      video.removeEventListener('loadedmetadata', handleLoadedMetadata)
    }
  }, [videoUrl])

  const handleSend = async () => {
    if (isSubmitting || !user) return

    setIsSubmitting(true)
    try {
      const [minDuration, maxDuration] = clipLength.split("-").map(Number)

      const config = {
        minDuration,
        maxDuration,
        autoSchedule,
      }

      setProcessingConfig(config)

      if (videoFile) {
        const newVideoId = crypto.randomUUID()
        router.push(
          `/processing?videoId=${newVideoId}&config=${encodeURIComponent(JSON.stringify(config))}`
        )
        return
      }

      if (videoId) {
        const started = await startIngestionFromUrl(videoId)
        router.push(
          `/processing?videoId=${started.video_id}&config=${encodeURIComponent(JSON.stringify(config))}`
        )
        return
      }

      toast.error("Nenhum vídeo selecionado")
    } catch (error) {
      console.error("Error:", error)
      toast.error(error instanceof Error ? error.message : "Erro ao processar")
      setIsSubmitting(false)
    }
  }

  const getVideoTitle = () => {
    const title = videoTitle || (videoFile ? videoFile.name : null)
    if (title) {
      return title.length > 60 ? `${title.slice(0, 60)}...` : title
    }
    return "Vídeo"
  }

  const calculateCredits = (): number => {
    if (videoDuration === 0) return 0
    return Math.ceil(videoDuration / 60)
  }

  const previewUrl = thumbnailUrl || videoUrl
  const effectiveFileSize = fileSize ?? (videoFile ? videoFile.size : null)
  const sizeLabel = effectiveFileSize ? `${(effectiveFileSize / (1024 * 1024)).toFixed(1)}MB` : null
  const canPreviewVideo = Boolean(videoFile && videoUrl)

  return (
    <div className="w-full flex flex-col p-6 h-screen">
      <Button
        variant='ghost'
        onClick={() => router.back()}
        className="flex items-center gap-2 text-foreground hover:text-foreground text-sm mb-8 w-fit"
      >
        <HugeiconsIcon icon={ArrowLeft02Icon} strokeWidth={2} />
        Voltar
      </Button>

      <div className="flex-1 flex flex-col items-center justify-center ">
        <div className="w-full max-w-xl space-y-8">
          <div className="bg-card border border-border rounded-xl p-4 flex gap-4 items-center">
            <div className="w-16 h-16 bg-black rounded-md overflow-hidden flex-shrink-0">
              {thumbnailUrl ? (
                <img src={thumbnailUrl} className="w-full h-full object-cover" />
              ) : canPreviewVideo ? (
                <video src={videoUrl ?? undefined} className="w-full h-full object-cover" />
              ) : (
                <div className="w-full h-full bg-muted" />
              )}
            </div>
            <div className="flex-1 flex flex-col items-start justify-start">
              <h3 className="text-sm font-medium text-foreground line-clamp-2 text-start">
                {getVideoTitle()}
              </h3>
            </div>
          </div>

          <div className="space-y-5">
            <div className="space-y-2">
              <Label className="text-muted-foreground">Duração média dos clips</Label>
              <Select value={clipLength} onValueChange={(value) => {
                if (value) setClipLength(value)
              }}>
                <SelectTrigger className="flex items-center gap-2 w-full">
                  <div className="flex items-center gap-3">
                    <HugeiconsIcon size={16} icon={Clock01Icon} />
                    <span>
                      {clipLength === "30-60" ? "30s-60s" : clipLength === "60-90" ? "60s-90s" : "90s-120s"}
                    </span>
                  </div>
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="30-60">30s-60s</SelectItem>
                  <SelectItem value="60-90">60s-90s</SelectItem>
                  <SelectItem value="90-120">90s-120s</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label className="text-muted-foreground">Auto agendamento (não implementado agora)</Label>
              <div className="border border-border rounded-md p-4 flex items-center justify-between bg-transparent">
                <div className="flex items-center gap-3 text-sm text-foreground">
                  <HugeiconsIcon size={16} icon={Calendar01Icon} />
                  Auto Agendamento e post
                </div>
                <Switch checked={autoSchedule} onCheckedChange={setAutoSchedule} />
              </div>
            </div>

            <Button
              onClick={handleSend}
              disabled={isSubmitting}
              className="w-full bg-foreground text-background font-medium h-12 rounded-md hover:bg-foreground/90 transition-colors mt-4 disabled:opacity-50"
            >
              {isSubmitting ? <Spinner /> : "Enviar"}
            </Button>

            <div className="flex justify-end items-center gap-2">
              <Label>
                Irá usar {calculateCredits()} créditos
              </Label>
              <HugeiconsIcon size={16} icon={AlertSquareIcon} />
            </div>

          </div>
        </div>
      </div>
    </div>
  )
}
