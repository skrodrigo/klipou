"use client"

import { useEffect, useState } from "react"
import { MoreHorizontal, Scissors } from "lucide-react"
import { Skeleton } from "@/components/ui/skeleton"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { listVideos } from "@/infra/videos/videos"
import type { Video } from "@/infra/videos/videos"

export default function ProjectsPage() {
  const [videos, setVideos] = useState<Video[]>([])
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    const fetchVideos = async () => {
      try {
        const data = await listVideos()
        setVideos(data)
      } catch (error) {
        console.error("Error fetching videos:", error)
      } finally {
        setIsLoading(false)
      }
    }

    fetchVideos()
  }, [])

  const formatDate = (dateString: string) => {
    const date = new Date(dateString)
    return date.toLocaleDateString("pt-BR", {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    })
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case "completed":
        return "text-primary"
      case "processing":
        return "text-orange-500"
      case "failed":
        return "text-destructive"
      default:
        return "text-muted-foreground"
    }
  }

  const getStatusLabel = (status: string) => {
    switch (status) {
      case "completed":
        return "Concluído"
      case "processing":
        return "Processando..."
      case "failed":
        return "Erro"
      case "pending":
        return "Pendente"
      default:
        return status
    }
  }

  if (isLoading) {
    return (
      <div className="flex-1 p-12 overflow-y-auto">
        <h1 className="text-2xl mb-8 text-foreground">Projetos</h1>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {Array(3)
            .fill(null)
            .map((_, i) => (
              <div
                key={i}
                className="group relative bg-card border border-border rounded-md overflow-hidden"
              >
                <div className="aspect-video bg-muted relative">
                  <Skeleton className="w-full h-full rounded-none" />
                </div>

                <div className="p-4">
                  <Skeleton className="h-3 w-24 mb-3" />
                  <Skeleton className="h-4 w-full mb-2" />
                  <Skeleton className="h-4 w-3/4 mb-4" />
                  <div className="flex items-center justify-between mt-4">
                    <Skeleton className="h-3 w-16" />
                    <Skeleton className="h-4 w-4" />
                  </div>
                </div>
              </div>
            ))}
        </div>
      </div>
    )
  }

  return (
    <div className="flex-1 p-12 overflow-y-auto">
      <h1 className="text-2xl mb-8 text-foreground">Projetos</h1>

      {videos.length === 0 ? (
        <div className="text-muted-foreground">Nenhum projeto encontrado</div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {videos.map((video) => (
            <div
              key={video.id}
              className="group relative bg-card border border-border rounded-md overflow-hidden transition-colors cursor-pointer"
            >
              {/* Thumbnail */}
              <div className="aspect-video bg-muted relative">
                {/* Hover Overlay */}
                <div className="absolute inset-0 bg-black/60 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center gap-2">
                  <div className="bg-muted px-3 py-1.5 rounded-md flex items-center gap-2 text-xs font-medium border border-border text-foreground">
                    <span className="text-muted-foreground">{video.clips?.length || 0}</span> Clips
                  </div>
                  <div className="bg-muted p-1.5 rounded-md border border-border text-foreground">
                    <Scissors size={14} />
                  </div>
                </div>

                {/* Checkbox for selection */}
                <div className="absolute top-2 right-2 opacity-0 group-hover:opacity-100">
                  <div className="w-4 h-4 border border-muted-foreground rounded bg-transparent" />
                </div>
              </div>

              {/* Info */}
              <div className="p-4">
                <div className="text-xs text-muted-foreground mb-1">{formatDate(video.created_at)}</div>
                <h3 className="font-medium text-sm text-foreground mb-2 truncate">{video.title}</h3>
                <div className="flex items-center justify-between mt-4">
                  <span className={`text-xs ${getStatusColor(video.status)}`}>
                    {getStatusLabel(video.status)}
                  </span>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <button className="text-muted-foreground hover:text-foreground transition-colors">
                        <MoreHorizontal size={16} />
                      </button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem>Ver detalhes</DropdownMenuItem>
                      <DropdownMenuItem>Editar</DropdownMenuItem>
                      <DropdownMenuItem className="text-destructive">Deletar</DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
