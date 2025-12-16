"use client"

import { Button } from "@/components/ui/button"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Switch } from "@/components/ui/switch"
import { useVideoStore } from "@/lib/store/video-store"
import { AlertSquareIcon, ArrowLeft02Icon, AspectRatioIcon, Calendar01Icon, Clock01Icon, Globe02Icon } from "@hugeicons/core-free-icons"
import { HugeiconsIcon } from "@hugeicons/react"
import { useRouter } from "next/navigation"
import { useState, useEffect } from "react"
import { toast } from "sonner"
import { useQuery } from "@tanstack/react-query"
import { getSession } from "@/infra/auth/auth"

export default function VideoSettingsPage() {
  const router = useRouter()
  const { videoFile, videoUrl } = useVideoStore()
  const [ratio, setRatio] = useState("9:16")
  const [clipLength, setClipLength] = useState("60-90")
  const [autoSchedule, setAutoSchedule] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [language, setLanguage] = useState<string>("pt-br")
  const [videoDuration, setVideoDuration] = useState(0)

  const { data: user } = useQuery({
    queryKey: ["auth-session"],
    queryFn: getSession,
  })

  // Captura a duração do vídeo quando ele é carregado
  useEffect(() => {
    if (!videoUrl) return

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
    if (isSubmitting || !videoFile || !user) return

    setIsSubmitting(true)
    try {
      const [, maxDuration] = clipLength.split("-").map(Number)
      const videoId = crypto.randomUUID()

      const config = {
        language,
        ratio,
        maxDuration,
        autoSchedule,
      }

      router.push(
        `/processing?videoId=${videoId}&config=${encodeURIComponent(JSON.stringify(config))}`
      )
    } catch (error) {
      console.error("Error:", error)
      toast.error(error instanceof Error ? error.message : "Erro ao processar")
      setIsSubmitting(false)
    }
  }

  const getVideoTitle = () => {
    if (videoFile) {
      const name = videoFile.name
      return name.length > 50 ? `${name.slice(0, 60)}...` : name
    }
    return "Vídeo"
  }

  const calculateCredits = (): number => {
    if (videoDuration === 0) return 0
    return Math.ceil(videoDuration / 60)
  }

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
              {videoUrl && <video src={videoUrl} className="w-full h-full object-cover" />}
            </div>
            <div className="flex-1 flex items-center justify-start">
              <h3 className="text-sm font-medium text-foreground line-clamp-2 text-center">
                {getVideoTitle()}
              </h3>
            </div>
          </div>

          <div className="space-y-4">
            <Select value={language} onValueChange={(value) => {
              if (value) setLanguage(value)
            }}>
              <SelectTrigger className="flex items-center gap-2 w-full">
                <div className="flex items-center gap-3">
                  <HugeiconsIcon size={16} icon={Globe02Icon} />
                  <span>
                    {language === "pt-br" ? "Português (Brasil)" : language === "en" ? "English" : "Español"}
                  </span>
                </div>
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="pt-br">Português (Brasil)</SelectItem>
                <SelectItem value="en">English</SelectItem>
                <SelectItem value="es">Español</SelectItem>
              </SelectContent>
            </Select>

            <Select value={ratio} onValueChange={(value) => {
              if (value) setRatio(value)
            }}>
              <SelectTrigger className="flex items-center gap-2 w-full">
                <div className="flex items-center gap-3">
                  <HugeiconsIcon size={16} icon={AspectRatioIcon} />
                  <span>
                    {ratio === "9:16" ? "Ratio 9:16" : ratio === "16:9" ? "Ratio 16:9" : "Ratio 1:1"}
                  </span>
                </div>
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="9:16">Ratio 9:16</SelectItem>
                <SelectItem value="16:9">Ratio 16:9</SelectItem>
                <SelectItem value="1:1">Ratio 1:1</SelectItem>
              </SelectContent>
            </Select>

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

            <div className="border border-border rounded-md p-4 flex items-center justify-between bg-transparent">
              <div className="flex items-center gap-3 text-sm text-foreground">
                <HugeiconsIcon size={16} icon={Calendar01Icon} />
                Auto Agendamento e post
              </div>
              <Switch checked={autoSchedule} onCheckedChange={setAutoSchedule} />
            </div>

            <Button
              onClick={handleSend}
              disabled={isSubmitting}
              className="w-full bg-foreground text-background font-medium h-12 rounded-md hover:bg-foreground/90 transition-colors mt-4 disabled:opacity-50"
            >
              {isSubmitting ? "Enviando..." : "Enviar"}
            </Button>

            <div className="flex justify-end items-center gap-2">
              <p className="text-end text-base text-foreground">
                Irá usar {calculateCredits()} créditos
              </p>
              <HugeiconsIcon size={16} icon={AlertSquareIcon} />
            </div>

          </div>
        </div>
      </div>
    </div>
  )
}
