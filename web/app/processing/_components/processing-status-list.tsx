"use client"

import { cn } from "@/lib/utils"
import { AlertSquareIcon, CancelSquareIcon, Loading03Icon, SquareIcon, Tick02Icon } from "@hugeicons/core-free-icons"
import { HugeiconsIcon } from "@hugeicons/react"

export type ProcessingStatus =
  | "ingestion"
  | "queued"
  | "downloading"
  | "normalizing"
  | "transcribing"
  | "analyzing"
  | "embedding"
  | "selecting"
  | "reframing"
  | "rendering"
  | "clipping"
  | "captioning"
  | "done"
  | "failed"

type Props = {
  status: ProcessingStatus
  isUploading: boolean
  isUploadComplete: boolean
  error: string | null
  dots: string
}

const stages: ProcessingStatus[] = [
  "queued",
  "downloading",
  "normalizing",
  "transcribing",
  "analyzing",
  "embedding",
  "selecting",
  "reframing",
  "clipping",
  "captioning",
  "rendering",
]

function getUploadState(isUploading: boolean, isUploadComplete: boolean): "completed" | "active" | "pending" {
  if (isUploadComplete) return "completed"
  if (isUploading) return "active"
  return "pending"
}

function getStageState(
  stage: ProcessingStatus,
  status: ProcessingStatus,
  isUploadComplete: boolean
): "completed" | "active" | "pending" | "failed" {
  const stageIndex = stages.indexOf(stage)

  if (!isUploadComplete) {
    return "pending"
  }

  if (status === "done") {
    return "completed"
  }

  if (status === "failed") {
    const statusIndex = stages.indexOf(status)
    if (stageIndex < statusIndex) return "completed"
    return "failed"
  }

  const statusIndex = stages.indexOf(status)
  if (stageIndex < statusIndex) return "completed"
  if (stageIndex === statusIndex) return "active"
  return "pending"
}

function getFailedStageIndex(error: string | null, status: ProcessingStatus): number {
  if (!error || status === "done") return -1
  return stages.indexOf(status)
}

export function ProcessingStatusList({ status, isUploading, isUploadComplete, error, dots }: Props) {
  const uploadState = getUploadState(isUploading, isUploadComplete)

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-3">
        {uploadState === "completed" ? (
          <HugeiconsIcon size={16} icon={Tick02Icon} className="text-primary" />
        ) : uploadState === "active" ? (
          <HugeiconsIcon size={16} icon={Loading03Icon} className="animate-spin text-foreground" />
        ) : (
          <HugeiconsIcon size={16} icon={SquareIcon} className="text-muted-foreground" />
        )}
        <span
          className={cn(
            "text-sm",
            uploadState === "completed" && "text-muted-foreground line-through",
            uploadState === "active" && "text-foreground font-medium",
            uploadState === "pending" && "text-muted-foreground"
          )}
        >
          Enviando vídeo{uploadState === "active" && <span className="ml-1">...</span>}
        </span>
      </div>

      {[
        { stage: "queued" as const, label: "Na fila" },
        { stage: "downloading" as const, label: "Preparando o vídeo" },
        { stage: "normalizing" as const, label: "Fazendo ajustes" },
        { stage: "transcribing" as const, label: "Transformando e Entendendo" },
        { stage: "analyzing" as const, label: "Analisando conteúdo" },
        { stage: "embedding" as const, label: "Indexando o conteúdo" },
        { stage: "selecting" as const, label: "Selecionando melhores trechos" },
        { stage: "reframing" as const, label: "Reenquadrando vídeo" },
        { stage: "captioning" as const, label: "Gerando legendas" },
        { stage: "rendering" as const, label: "Gerando clips finais" },
      ].map(({ stage, label }, idx) => {
        const state = getStageState(stage, status, isUploadComplete)
        const failedIdx = getFailedStageIndex(error, status)
        const isFailedStage = Boolean(error) && failedIdx === idx
        const isAfterFailed = Boolean(error) && failedIdx !== -1 && idx > failedIdx

        return (
          <div key={stage} className="flex items-center gap-3">
            {isFailedStage ? (
              <HugeiconsIcon size={16} icon={CancelSquareIcon} className="text-destructive" />
            ) : isAfterFailed ? (
              <HugeiconsIcon size={16} icon={AlertSquareIcon} className="text-muted-foreground" />
            ) : state === "completed" ? (
              <HugeiconsIcon size={16} icon={Tick02Icon} className="text-primary" />
            ) : state === "active" ? (
              <HugeiconsIcon size={16} icon={Loading03Icon} className="animate-spin text-foreground" />
            ) : (
              <HugeiconsIcon size={16} icon={SquareIcon} className="text-muted-foreground" />
            )}
            <span
              className={cn(
                "text-sm",
                state === "completed" && "text-muted-foreground line-through",
                state === "active" && "text-foreground font-medium",
                isFailedStage && "text-destructive font-semibold",
                isAfterFailed && "text-foreground",
                !isFailedStage && !isAfterFailed && state === "pending" && "text-muted-foreground"
              )}
            >
              {label}
              {state === "active" && !error && <span className="ml-1">{dots}</span>}
            </span>
          </div>
        )
      })}
    </div>
  )
}
