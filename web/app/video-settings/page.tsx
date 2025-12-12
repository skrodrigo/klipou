"use client"

import React, { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { ArrowLeft, Globe, Layout, Clock, Calendar } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Switch } from "@/components/ui/switch"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { IconInfoCircle } from "@tabler/icons-react"
import { createVideo } from "@/infra/videos/videos"

export default function VideoSettingsPage() {
  const router = useRouter()
  const [videoFile, setVideoFile] = useState<File | null>(null)
  const [videoUrl, setVideoUrl] = useState<string>("")
  const [language, setLanguage] = useState("pt-br")
  const [ratio, setRatio] = useState("9:16")
  const [clipLength, setClipLength] = useState("60-90")
  const [autoSchedule, setAutoSchedule] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)

  useEffect(() => {
    const storedFile = sessionStorage.getItem("videoFile")
    const storedUrl = sessionStorage.getItem("videoUrl")

    if (storedUrl) {
      setVideoUrl(storedUrl)
    }

    if (storedFile) {
      try {
        const file = JSON.parse(storedFile)
        setVideoFile(file)
      } catch (e) {
        console.error("Error parsing video file:", e)
      }
    }
  }, [])

  const handleSend = async () => {
    if (isSubmitting || !videoFile) return

    setIsSubmitting(true)
    try {
      // Store settings before creating video
      sessionStorage.setItem("videoSettings", JSON.stringify({
        language,
        ratio,
        clipLength,
        autoSchedule,
        videoUrl,
        videoFile: videoFile ? { name: videoFile.name, size: videoFile.size } : null,
      }))

      // Create video and get the response with video ID
      const response = await createVideo(videoFile)
      const videoId = response?.id || null

      // Navigate to processing with video ID
      router.push(`/processing${videoId ? `?videoId=${videoId}` : ""}`)
    } catch (error) {
      console.error("Error creating video:", error)
      setIsSubmitting(false)
    }
  }

  const getVideoTitle = () => {
    if (videoFile) {
      return videoFile.name
    }
    return "Vídeo"
  }

  return (
    <div className="flex-1 flex flex-col items-center justify-center p-8 w-full h-screen">
      <div className="absolute top-8 left-8">
        <button
          onClick={() => router.back()}
          className="flex items-center gap-2 text-[#ACACAC] hover:text-foreground text-sm"
        >
          <ArrowLeft size={16} /> Voltar
        </button>
      </div>

      <div className="w-full max-w-lg space-y-8">
        <div className="bg-card border border-border rounded-xl p-4 flex gap-4 items-center">
          <div className="w-16 h-16 bg-black rounded-lg overflow-hidden flex-shrink-0">
            {videoUrl && <video src={videoUrl} className="w-full h-full object-cover" />}
          </div>
          <div className="flex-1 flex items-center justify-start">
            <h3 className="text-sm font-medium text-foreground line-clamp-2 text-center">
              {getVideoTitle()}
            </h3>
          </div>
        </div>

        <div className="space-y-4">
          <Select value={language} onValueChange={setLanguage}>
            <SelectTrigger className="border border-border rounded-lg h-12 px-4 bg-transparent text-[#ACACAC]">
              <div className="flex items-center gap-3">
                <Globe size={18} />
                <SelectValue />
              </div>
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="pt-br">Português (Brasil)</SelectItem>
              <SelectItem value="en">English</SelectItem>
              <SelectItem value="es">Español</SelectItem>
            </SelectContent>
          </Select>

          <Select value={ratio} onValueChange={setRatio}>
            <SelectTrigger className="border border-border rounded-lg h-12 px-4 bg-transparent text-[#ACACAC]">
              <div className="flex items-center gap-3">
                <Layout size={18} />
                <SelectValue />
              </div>
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="9:16">Ratio 9:16</SelectItem>
              <SelectItem value="16:9">Ratio 16:9</SelectItem>
              <SelectItem value="1:1">Ratio 1:1</SelectItem>
            </SelectContent>
          </Select>

          <Select value={clipLength} onValueChange={setClipLength}>
            <SelectTrigger className="border border-border rounded-lg h-12 px-4 bg-transparent text-[#ACACAC]">
              <div className="flex items-center gap-3">
                <Clock size={18} />
                <SelectValue />
              </div>
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="30-60">30s-60s</SelectItem>
              <SelectItem value="60-90">60s-90s</SelectItem>
              <SelectItem value="90-120">90s-120s</SelectItem>
            </SelectContent>
          </Select>

          <div className="border border-border rounded-lg p-4 flex items-center justify-between bg-transparent">
            <div className="flex items-center gap-3 text-sm text-foreground">
              <Calendar size={18} />
              Auto Agendamento e post
            </div>
            <Switch checked={autoSchedule} onCheckedChange={setAutoSchedule} />
          </div>

          <Button
            onClick={handleSend}
            disabled={isSubmitting}
            className="w-full bg-foreground text-background font-medium h-12 rounded-lg hover:bg-foreground/90 transition-colors mt-4 disabled:opacity-50"
          >
            {isSubmitting ? "Enviando..." : "Enviar"}
          </Button>

          <div className="flex justify-end items-center gap-2">
            <p className="text-end text-base text-foreground">
              Irá usar 124 créditos
            </p>
            <IconInfoCircle className="w-4 h-4" />
          </div>

        </div>
      </div>
    </div>
  )
}
