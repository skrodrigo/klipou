"use client"

import React, { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { ArrowLeft, Check, Circle, Loader2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { IconCheck, IconLoader2 } from "@tabler/icons-react"

type ProcessingStatus = "queue" | "sending" | "creating" | "hunting" | "completed"

interface StatusMessage {
  status: ProcessingStatus
  progress: number
  queue_position?: number
}

export default function ProcessingPage() {
  const router = useRouter()
  const [progress, setProgress] = useState(0)
  const [status, setStatus] = useState<ProcessingStatus>("queue")
  const [queuePosition, setQueuePosition] = useState<number | null>(null)
  const [videoId, setVideoId] = useState<string | null>(null)
  const [videoTitle, setVideoTitle] = useState("Seu vídeo")
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    // Get videoId from URL params or session
    const params = new URLSearchParams(window.location.search)
    const id = params.get("videoId")
    if (id) {
      setVideoId(id)
    }

    // Get video title from sessionStorage
    const settings = sessionStorage.getItem("videoSettings")
    if (settings) {
      try {
        const parsed = JSON.parse(settings)
        if (parsed.videoFile?.name) {
          setVideoTitle(parsed.videoFile.name)
        }
      } catch (e) {
        console.error("Error parsing video settings:", e)
      }
    }

    // Connect to SSE
    const eventSource = new EventSource(`/api/videos/${id}/progress`)

    eventSource.onmessage = (event) => {
      try {
        const data: StatusMessage = JSON.parse(event.data)
        setStatus(data.status)
        setProgress(data.progress)
        if (data.queue_position !== undefined) {
          setQueuePosition(data.queue_position)
        }

        // Redirect when completed
        if (data.status === "completed") {
          setTimeout(() => {
            eventSource.close()
            router.push("/dashboard/projects")
          }, 2000)
        }
      } catch (e) {
        console.error("Error parsing SSE message:", e)
      }
    }

    eventSource.onerror = () => {
      console.error("SSE connection error")
      setError("Ocorreu um erro ao conectar com o servidor. Por favor, tente novamente.")
      eventSource.close()
    }

    return () => {
      eventSource.close()
    }
  }, [router])

  const getStatusLabel = () => {
    if (status === "queue" && queuePosition) {
      return `${queuePosition} in queue`
    }
    switch (status) {
      case "sending":
        return "Enviando..."
      case "creating":
        return "Criando seu projeto"
      case "hunting":
        return "Caçando as melhores partes"
      case "completed":
        return "Concluído"
      default:
        return "Next in queue"
    }
  }

  const isStageActive = (stage: ProcessingStatus) => status === stage
  const isStageCompleted = (stage: ProcessingStatus) => {
    const stages = ["queue", "sending", "creating", "hunting"]
    return stages.indexOf(status) > stages.indexOf(stage)
  }

  return (
    <div className="w-full flex flex-col p-6 h-screen">
      <button
        onClick={() => router.back()}
        className="flex items-center gap-2 text-foreground hover:text-foreground text-sm mb-8 w-fit"
      >
        <ArrowLeft size={16} /> Voltar
      </button>

      <div className="flex-1 flex flex-col items-center justify-center">
        <div className="w-full max-w-xl space-y-8">
          {error && (
            <div className="bg-destructive/10 border border-destructive text-destructive rounded-md p-4 text-center">
              <p className="font-medium">{error}</p>
            </div>
          )}
          <div className="bg-card border border-border rounded-md p-4 flex gap-4">
            <div className="w-16 h-16 bg-black rounded-md overflow-hidden flex-shrink-0"></div>
            <div className="flex-1">
              <h3 className="text-sm font-medium text-foreground mb-3 line-clamp-2">
                {videoTitle.toUpperCase()}
              </h3>
              <div className="h-2 bg-muted rounded-full overflow-hidden">
                <div
                  className="h-full bg-primary transition-all duration-300"
                  style={{ width: `${progress}%` }}
                />
              </div>
              <div className="text-xs text-muted-foreground mt-2">{getStatusLabel()} · {progress}%</div>
            </div>
          </div>

          {/* Info Text */}
          <p className="text-start text-muted-foreground">
            Você já pode sair dessa página, assim que terminarmos será enviando um email para você.
            <span className="text-blue-500 underline cursor-pointer"> Não me notifique</span>
          </p>

          {/* Status List */}
          <div className="space-y-3">
            <div className="flex items-center gap-3">
              {isStageCompleted("queue") ? (
                <div className="w-5 h-5 rounded-full border border-primary flex items-center justify-center text-primary">
                  <IconCheck size={12} />
                </div>
              ) : isStageActive("queue") ? (
                <IconLoader2 size={20} className="animate-spin text-foreground" />
              ) : (
                <Circle size={20} className=" text-muted-foreground" />
              )}
              <span className={isStageCompleted("queue") ? "text-muted-foreground line-through text-sm" : "text-muted-foreground text-sm"}>
                Next in queue
              </span>
            </div>

            <div className="flex items-center gap-3">
              {isStageCompleted("sending") ? (
                <div className="w-5 h-5 rounded-full border border-primary flex items-center justify-center text-primary">
                  <Check size={12} />
                </div>
              ) : isStageActive("sending") ? (
                <Loader2 size={20} className="animate-spin text-foreground" />
              ) : (
                <Circle size={20} className=" text-muted-foreground" />
              )}
              <span className={isStageActive("sending") ? "text-foreground font-medium text-sm" : "text-muted-foreground text-sm"}>
                Enviando...
              </span>
            </div>

            <div className="flex items-center gap-3">
              {isStageCompleted("creating") ? (
                <div className="w-5 h-5 rounded-full border border-primary flex items-center justify-center text-primary">
                  <Check size={12} />
                </div>
              ) : isStageActive("creating") ? (
                <Loader2 size={20} className="animate-spin text-foreground" />
              ) : (
                <Circle size={20} className=" text-muted-foreground" />
              )}
              <span className={isStageActive("creating") ? "text-foreground font-medium text-sm" : "text-muted-foreground text-sm"}>
                Criando seu projeto
              </span>
            </div>

            <div className="flex items-center gap-3">
              {isStageCompleted("hunting") ? (
                <div className="w-5 h-5 rounded-full border border-primary flex items-center justify-center text-primary">
                  <Check size={12} />
                </div>
              ) : isStageActive("hunting") ? (
                <Loader2 size={20} className="animate-spin text-foreground" />
              ) : (
                <Circle size={20} className=" text-muted-foreground" />
              )}
              <span className={isStageActive("hunting") ? "text-foreground font-semibold text-sm" : "text-muted-foreground text-sm"}>
                Caçando as melhores partes
              </span>
            </div>
          </div>

          {/* Go to Projects Button */}
          {status === "completed" && (
            <Button
              onClick={() => router.push("/dashboard/projects")}
              className="w-full bg-foreground text-background font-medium h-12 rounded-md hover:bg-foreground/90 transition-colors"
            >
              Ir para Projetos
            </Button>
          )}
        </div>
      </div>
    </div>
  )
}
