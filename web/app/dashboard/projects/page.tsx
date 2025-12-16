"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import {
  Empty,
  EmptyContent,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty"
import { listVideos, deleteVideo, renameVideo, getVideoDetails } from "@/infra/videos/videos"
import { Video } from "@/infra/videos/types/videos-types"
import { Spinner } from "@/components/ui/spinner"
import { HugeiconsIcon } from "@hugeicons/react"
import { MoreHorizontalIcon, ScissorIcon, Delete02Icon, FilterIcon, VideoIcon, Upload01Icon, Edit02Icon, EyeIcon } from "@hugeicons/core-free-icons"
import { useQuery, useMutation } from "@tanstack/react-query"
import { toast } from "sonner"
import { getSession } from "@/infra/auth/auth"

export default function ProjectsPage() {
  const router = useRouter()
  const [videos, setVideos] = useState<Video[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [selectedVideos, setSelectedVideos] = useState<string[]>([])
  const [renameDialogOpen, setRenameDialogOpen] = useState(false)
  const [renameVideoId, setRenameVideoId] = useState<string | null>(null)
  const [renameTitle, setRenameTitle] = useState("")
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
  const [deleteVideoId, setDeleteVideoId] = useState<string | null>(null)

  const { data: user } = useQuery({
    queryKey: ["auth-session"],
    queryFn: getSession,
  })

  const { mutate: deleteVideoFile } = useMutation({
    mutationFn: (videoId: string) => deleteVideo(videoId, user?.organization_id || ""),
    onSuccess: async () => {
      const data = await listVideos()
      setVideos(data)
      toast.success("Projeto deletado!")
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : "Erro ao deletar projeto")
    },
  })

  const { mutate: renameVideoFile } = useMutation({
    mutationFn: ({ videoId, title }: { videoId: string; title: string }) =>
      renameVideo(videoId, title, user?.organization_id || ""),
    onSuccess: async () => {
      const data = await listVideos()
      setVideos(data)
      toast.success("Projeto renomeado!")
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : "Erro ao renomear projeto")
    },
  })

  const { mutate: getVideoDetailsFile } = useMutation({
    mutationFn: (videoId: string) => {
      if (!user?.organization_id) {
        throw new Error("Organization ID não encontrado")
      }
      return getVideoDetails(videoId, user.organization_id)
    },
    onSuccess: (data) => {
      toast.success(`Projeto: ${data.title} - Status: ${data.status}`)
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : "Erro ao obter detalhes")
    },
  })

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

  const handleDeleteSelected = async () => {
    selectedVideos.forEach((videoId) => {
      deleteVideoFile(videoId)
    })
    setSelectedVideos([])
  }

  const handleSelectAll = (checked: boolean) => {
    if (checked) {
      setSelectedVideos(videos.map((video) => video.video_id))
    } else {
      setSelectedVideos([])
    }
  }

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

  const formatDuration = (seconds: number | undefined) => {
    if (seconds === undefined) return "00:00";
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = Math.floor(seconds % 60);
    return `${minutes.toString().padStart(2, '0')}:${remainingSeconds.toString().padStart(2, '0')}`;
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
      <div className="flex flex-col">
        <h1 className="text-2xl text-foreground p-12">Projetos</h1>
        <div className="flex-1 flex items-center justify-center">
          <Spinner />
        </div>
      </div>
    )
  }

  return (
    <div className="flex-1 p-12 overflow-y-auto relative">
      <div className="flex justify-between items-center mb-8">
        <h1 className="text-2xl text-foreground">Projetos</h1>
        <div className="flex items-center gap-2">
          <Button
            variant="secondary"
            size="sm"
            className="h-9 text-zinc-300 hover:bg-zinc-800 hover:text-white gap-2 text-xs"
          >
            <HugeiconsIcon icon={FilterIcon} className="h-4 w-4" />
            <span>Filtrar</span>
          </Button>
          <div className="flex bg-card items-center gap-2 rounded-md px-3 h-9">
            <span className="text-xs text-zinc-300">Selecionar Tudo</span>
            <Checkbox
              checked={selectedVideos.length === videos.length && videos.length > 0}
              onCheckedChange={handleSelectAll}
            />
          </div>
        </div>
      </div>

      {videos.length === 0 ? (
        <div className="flex items-center justify-center h-[calc(100vh-200px)]">
          <Empty>
            <EmptyHeader>
              <EmptyMedia variant="icon">
                <HugeiconsIcon icon={VideoIcon} size={48} />
              </EmptyMedia>
              <EmptyTitle>Nenhum projeto encontrado</EmptyTitle>
              <EmptyDescription>Comece a criar clipes fazendo upload de um vídeo</EmptyDescription>
            </EmptyHeader>
            <EmptyContent>
              <Button onClick={() => router.push("/dashboard")}>
                <HugeiconsIcon icon={Upload01Icon} className="h-4 w-4 mr-2" />
                Fazer upload de vídeo
              </Button>
            </EmptyContent>
          </Empty>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {videos.map((video) => (
            <div
              key={video.video_id}
              onClick={() => router.push(`/clips/${video.video_id}`)}
              className="group relative bg-card rounded-md overflow-hidden transition-colors cursor-pointer hover:border-primary/50"
            >
              <div className="bg-muted relative w-full aspect-video">
                {video.thumbnail ? (
                  <img src={video.thumbnail} alt={video.title} className="w-full h-full object-cover" />
                ) : (
                  <div className="w-full h-full bg-muted" />
                )}

                {video.duration && (
                  <div className="absolute bottom-2 right-2 bg-black/70 text-white text-xs px-2 py-1 rounded-md">
                    {formatDuration(video.duration)}
                  </div>
                )}

                <div className="absolute inset-0 bg-black/60 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center gap-2">
                  <div className="bg-muted px-3 py-1.5 rounded-md flex items-center gap-2 text-xs font-medium border border-border text-foreground">
                    <span className="text-muted-foreground">{video.clips_count || 0}</span> Clips
                  </div>
                  <div className="bg-muted p-1.5 rounded-md border border-border text-foreground">
                    <HugeiconsIcon icon={ScissorIcon} size={16} />
                  </div>
                </div>

                <div
                  className={cn(
                    "absolute top-0 right-0 p-2 opacity-0 group-hover:opacity-100",
                    selectedVideos.includes(video.video_id) && "opacity-100"
                  )}
                  onClick={(e) => e.stopPropagation()}
                >
                  <Checkbox
                    checked={selectedVideos.includes(video.video_id)}
                    onCheckedChange={(checked) => {
                      if (checked) {
                        setSelectedVideos([...selectedVideos, video.video_id])
                      } else {
                        setSelectedVideos(
                          selectedVideos.filter((id) => id !== video.video_id)
                        )
                      }
                    }}
                  />
                </div>
              </div>

              <div className="p-4">
                <div className="text-xs text-muted-foreground mb-1">{formatDate(video.created_at)}</div>
                <h3 className="font-medium text-sm text-foreground mb-2 truncate">{video.title}</h3>
                <div className="flex items-center justify-between mt-4">
                  <span className={`text-xs ${getStatusColor(video.status)}`}>
                    {getStatusLabel(video.status)}
                  </span>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <button className="text-muted-foreground hover:text-foreground transition-colors" onClick={(e) => e.stopPropagation()}>
                        <HugeiconsIcon icon={MoreHorizontalIcon} />
                      </button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem onClick={() => getVideoDetailsFile(video.video_id)}>
                        <HugeiconsIcon icon={EyeIcon} className="h-4 w-4 mr-2" />
                        Ver detalhes
                      </DropdownMenuItem>
                      <DropdownMenuItem onClick={() => {
                        setRenameVideoId(video.video_id)
                        setRenameTitle(video.title)
                        setRenameDialogOpen(true)
                      }}>
                        <HugeiconsIcon icon={Edit02Icon} className="h-4 w-4 mr-2" />
                        Renomear
                      </DropdownMenuItem>
                      <DropdownMenuItem
                        className="text-destructive"
                        onClick={() => {
                          setDeleteVideoId(video.video_id)
                          setDeleteDialogOpen(true)
                        }}
                      >
                        <HugeiconsIcon icon={Delete02Icon} className="h-4 w-4 mr-2" />
                        Deletar
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {selectedVideos.length > 0 && (
        <div className="fixed bottom-20 left-1/2 -translate-x-1/2 bg-card border rounded-md shadow-lg p-2 flex items-center gap-4 animate-in slide-in-from-bottom-5">
          <span className="text-sm font-medium pl-2">
            {selectedVideos.length} selected
          </span>
          <Button variant="destructive" size="sm" onClick={handleDeleteSelected}>
            <HugeiconsIcon icon={Delete02Icon} className="size-4 mr-2" />
            Delete
          </Button>
        </div>
      )}

      {/* Rename Dialog */}
      <Dialog open={renameDialogOpen} onOpenChange={setRenameDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Renomear Projeto</DialogTitle>
            <DialogDescription>Digite o novo título para o projeto</DialogDescription>
          </DialogHeader>
          <input
            type="text"
            value={renameTitle}
            onChange={(e) => setRenameTitle(e.target.value)}
            placeholder="Novo título"
            className="w-full px-3 py-2 border border-border rounded-md bg-background text-foreground"
          />
          <div className="flex gap-2 justify-end">
            <Button variant="outline" onClick={() => setRenameDialogOpen(false)}>
              Cancelar
            </Button>
            <Button
              onClick={() => {
                if (renameVideoId && renameTitle) {
                  renameVideoFile({ videoId: renameVideoId, title: renameTitle })
                  setRenameDialogOpen(false)
                }
              }}
            >
              Renomear
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Delete Dialog */}
      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Deletar Projeto</AlertDialogTitle>
            <AlertDialogDescription>
              Tem certeza que deseja deletar este projeto? Esta ação não pode ser desfeita.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancelar</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                if (deleteVideoId) {
                  deleteVideoFile(deleteVideoId)
                  setDeleteDialogOpen(false)
                }
              }}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              Deletar
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  )
}
