"use client"

import React, { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { ArrowLeft, Check, Circle, Loader2 } from "lucide-react"
import { Button } from "@/components/ui/button"
import { IconCheck, IconLoader2, IconLogout2, IconAlertCircle, IconCircleCheck, IconCircleCheckFilled } from "@tabler/icons-react"
import { requestSSE } from "@/infra/http"
import { useVideoStore } from "@/lib/store/video-store"
import { cn } from "@/lib/utils"

type ProcessingStatus = "queue" | "sending" | "creating" | "hunting" | "completed" | "failed"

interface StatusMessage {
  status: ProcessingStatus
  progress: number
  queue_position?: number
  error?: string
  failed_stage?: ProcessingStatus
}

export default function ProcessingPage() {
  const router = useRouter()
  const [progress, setProgress] = useState(0)
  const [status, setStatus] = useState<ProcessingStatus>("queue")
  const [queuePosition, setQueuePosition] = useState<number | null>(null)
  const [videoId, setVideoId] = useState<string | null>(null)
  const { videoFile, videoUrl } = useVideoStore()
  const videoTitle = videoFile?.name || "Seu vídeo"
  const [error, setError] = useState<string | null>(null)
  const [failedStage, setFailedStage] = useState<ProcessingStatus | null>(null)
  const [thumbnail, setThumbnail] = useState<string | null>(null)

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const id = params.get("videoId");
    if (id) {
      setVideoId(id);
      fetch(`/api/videos/${id}/`)
        .then(res => res.json())
        .then(data => {
          if (data.thumbnail) {
            setThumbnail(data.thumbnail);
          }
        })
        .catch(err => console.error("Error fetching video:", err));
    }
  }, []);

  useEffect(() => {
    if (!videoId) {
      return;
    }

    let isClosing = false;
    const eventSource = requestSSE(`/api/videos/${videoId}/progress/`);

    eventSource.onmessage = (event) => {
      try {
        const data: StatusMessage = JSON.parse(event.data);
        setStatus(data.status);
        setProgress(data.progress);
        if (data.queue_position !== undefined) {
          setQueuePosition(data.queue_position);
        }

        if (data.status === "completed") {
          isClosing = true;
          setTimeout(() => {
            eventSource.close();
            router.push("/dashboard/projects");
          }, 2000);
        } else if (data.status === "failed") {
          isClosing = true;
          setError(data.error || "O processamento falhou. Por favor, tente novamente.");
          setFailedStage(data.failed_stage || null);
          eventSource.close();
        }
      } catch (e) {
        console.error("Error parsing SSE message:", e);
      }
    };

    eventSource.onerror = () => {
      if (!isClosing) {
        setError("Ocorreu um erro ao conectar com o servidor. Por favor, tente novamente.");
      }
      eventSource.close();
    };

    return () => {
      eventSource.close();
    };
  }, [videoId, router]);

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
      case "failed":
        return "Falhou"
      default:
        return "Next in queue"
    }
  }

  const stages: ProcessingStatus[] = ["queue", "sending", "creating", "hunting"];

  const getStageState = (stage: ProcessingStatus): 'completed' | 'active' | 'pending' | 'failed' => {
    const stageIndex = stages.indexOf(stage);

    if (failedStage) {
      const failedIndex = stages.indexOf(failedStage);
      if (stageIndex < failedIndex) return 'completed';
      return 'failed';
    }

    const statusIndex = stages.indexOf(status);
    if (stageIndex < statusIndex) return 'completed';
    if (stageIndex === statusIndex) return 'active';
    return 'pending';
  };

  return (
    <div className="w-full flex flex-col p-6 h-screen">

      <div className="flex-1 flex flex-col items-center justify-center">
        <div className="w-full max-w-xl space-y-8">
          <div className="bg-card border border-border rounded-md p-4 flex gap-4">
            <div className="w-16 h-16 bg-black rounded-md overflow-hidden flex-shrink-0">
              {thumbnail ? (
                <img src={thumbnail} alt="Video thumbnail" className="w-full h-full object-cover" />
              ) : videoUrl ? (
                <video src={videoUrl} className="w-full h-full object-cover" />
              ) : null}
            </div>
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
              <div className="text-xs text-muted-foreground mt-2">{progress} %</div>
            </div>
          </div>

          {/* Info Text */}
          <p className="text-start text-muted-foreground">
            Você já pode sair dessa página!
          </p>

          {/* Status List */}
          <div className="space-y-3">
            {[{
              stage: "queue",
              label: "Next in queue",
              failedLabel: "Falha na fila"
            }, {
              stage: "sending",
              label: "Gerando Clipes",
              failedLabel: "Erro ao gerar clipes"
            }, {
              stage: "creating",
              label: "Criando seu projeto",
              failedLabel: "Não foi possível criar o projeto"
            }, {
              stage: "hunting",
              label: "Buscando melhores clipes",
              failedLabel: "Erro ao buscar clipes"
            }].map(({ stage, label, failedLabel }) => {
              const state = getStageState(stage as ProcessingStatus);
              return (
                <div key={stage} className="flex items-center gap-3">
                  {state === 'failed' ? (
                    <IconAlertCircle size={20} className="text-destructive" />
                  ) : state === 'completed' ? (
                    <IconCircleCheckFilled size={20} className="text-primary" />
                  ) : state === 'active' ? (
                    <IconLoader2 size={20} className="animate-spin text-foreground" />
                  ) : (
                    <Circle size={20} className="text-muted-foreground" />
                  )}
                  <span className={cn(
                    "text-sm",
                    state === 'completed' && "text-muted-foreground line-through",
                    state === 'active' && "text-foreground font-medium",
                    state === 'pending' && "text-muted-foreground",
                    state === 'failed' && "text-destructive font-semibold",
                  )}>
                    {state === 'failed' ? failedLabel : label}
                  </span>
                </div>
              );
            })}
          </div>

          <Button
            onClick={() => router.push("/dashboard/projects")}
            className=" bg-foreground text-background rounded-md hover:bg-foreground/90 transition-colors"
          >
            <IconLogout2 />
            Ir para Projetos
          </Button>
        </div>
      </div>
    </div>
  )
}
