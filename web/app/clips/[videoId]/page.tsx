"use client"

import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Spinner } from "@/components/ui/spinner"
import { getSession } from "@/infra/auth/auth"
import { deleteClip, downloadClip, duplicateClip, listVideoClips, renameClip, submitClipFeedback } from "@/infra/videos/videos"
import { cn } from "@/lib/utils"
import { ArrowLeft02Icon, Delete02Icon, FilterIcon } from "@hugeicons/core-free-icons"
import { HugeiconsIcon } from "@hugeicons/react"
import { useMutation, useQuery } from "@tanstack/react-query"
import { useQueryClient } from "@tanstack/react-query"
import { useRouter } from "next/navigation"
import { use, useEffect, useRef, useState } from "react"
import { toast } from "sonner"
import { PublishSheet } from "./_components/publish-sheet"
import { ClipCard } from "./_components/clip-card"

type ClipsPageProps = {
  params: Promise<{
    videoId: string
  }>
}

export default function ClipsPage({ params }: ClipsPageProps) {
  const router = useRouter()
  const queryClient = useQueryClient()
  const { videoId: videoIdStr } = use(params)
  const [selectedIdx, setSelectedIdx] = useState(0)
  const [selectedClips, setSelectedClips] = useState<string[]>([])

  const [publishOpen, setPublishOpen] = useState(false)
  const [description, setDescription] = useState("")
  const [visibility, setVisibility] = useState<"public" | "private" | "friends">("public")
  const [allowComments, setAllowComments] = useState(true)
  const [allowDuets, setAllowDuets] = useState(true)
  const [allowStitch, setAllowStitch] = useState(true)
  const [scheduleAt, setScheduleAt] = useState("")
  const [isDialogOpen, setDialogOpen] = useState(false)
  const [shareClipId, setShareClipId] = useState<string | null>(null)
  const videoId = videoIdStr
  const [value, setValue] = useState<"public" | "private">("private")
  const [showTopFade, setShowTopFade] = useState(false)
  const [showBottomFade, setShowBottomFade] = useState(false)
  const scrollRef = useRef<HTMLDivElement>(null)

  const { data: user } = useQuery({
    queryKey: ["auth-session"],
    queryFn: getSession,
  })

  const organizationId = user?.organization?.organization_id ?? user?.organization_id ?? ""

  const { data: clips = [], isLoading: loading } = useQuery({
    queryKey: ["video-clips", videoId],
    queryFn: () => listVideoClips(videoId),
    enabled: !!videoId,
  })

  const sortedClips = [...clips].sort((a, b) => {
    const aScore = typeof a.engagement_score === "number" ? a.engagement_score : -Infinity
    const bScore = typeof b.engagement_score === "number" ? b.engagement_score : -Infinity
    if (bScore !== aScore) return bScore - aScore
    return 0
  })

  const { mutate: downloadClipFile } = useMutation({
    mutationFn: (clipId: string) => downloadClip(clipId, organizationId),
    onSuccess: (data) => {
      window.open(data.download_url, "_blank")
      toast.success("Download iniciado!")
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : "Erro ao baixar clip")
    },
  })

  const { mutate: submitFeedback } = useMutation({
    mutationFn: (clipId: string) => submitClipFeedback(clipId, { rating: "good" }),
    onSuccess: () => {
      toast.success("Feedback enviado!")
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : "Erro ao enviar feedback")
    },
  })

  const { mutate: deleteClipFile } = useMutation({
    mutationFn: (clipId: string) => deleteClip(clipId, organizationId),
    onSuccess: (_data, clipId) => {
      toast.success("Clip deletado!")

      queryClient.setQueryData(["video-clips", videoId], (old: any) => {
        const oldArr = Array.isArray(old) ? old : (old?.results ?? old ?? [])
        if (!Array.isArray(oldArr)) return old
        return oldArr.filter((c: any) => c?.clip_id !== clipId)
      })

      queryClient.invalidateQueries({ queryKey: ["video-clips", videoId] })
      setSelectedClips([])
      if (selectedIdx >= sortedClips.length) {
        setSelectedIdx(sortedClips.length - 1)
      } else {
        setSelectedIdx(0)
      }
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : "Erro ao deletar clip")
    },
  })

  const { mutate: renameClipFile } = useMutation({
    mutationFn: ({ clipId, title }: { clipId: string; title: string }) =>
      renameClip(clipId, title, organizationId),
    onSuccess: () => {
      toast.success("Clip renomeado!")
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : "Erro ao renomear clip")
    },
  })

  const { mutate: duplicateClipFile } = useMutation({
    mutationFn: (clipId: string) => duplicateClip(clipId, organizationId),
    onSuccess: () => {
      toast.success("Clip duplicado!")
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : "Erro ao duplicar clip")
    },
  })

  const handleClipSelect = (clipId: string, idx: number) => {
    setSelectedIdx(idx)
    const element = document.getElementById(`clip-${clipId}`)
    if (element) {
      element.scrollIntoView({ behavior: "smooth", block: "center" })
    }
  }

  const handleSelectAll = (checked: boolean | "indeterminate") => {
    if (checked === true) {
      setSelectedClips(sortedClips.map((clip) => clip.clip_id))
    } else {
      setSelectedClips([])
    }
  }

  const toggleClipSelection = (clipId: string) => {
    setSelectedClips(prev =>
      prev.includes(clipId)
        ? prev.filter(id => id !== clipId)
        : [...prev, clipId]
    )
  }

  useEffect(() => {
    const scrollElement = scrollRef.current?.querySelector(
      "[data-radix-scroll-area-viewport]",
    )

    if (!scrollElement) return

    const handleScroll = () => {
      const { scrollTop, scrollHeight, clientHeight } = scrollElement
      setShowTopFade(scrollTop > 0)
      setShowBottomFade(scrollTop + clientHeight < scrollHeight - 1)
    }

    handleScroll()
    scrollElement.addEventListener("scroll", handleScroll)
    return () => scrollElement.removeEventListener("scroll", handleScroll)
  }, [sortedClips])

  return (
    <div className="w-full h-screen flex flex-col bg-background text-foreground relative">
      <Button
        onClick={() => router.back()}
        variant='ghost'
        className="absolute fixed top-6 left-6 flex items-center gap-2 text-foreground hover:text-foreground text-sm z-10"
      >
        <HugeiconsIcon icon={ArrowLeft02Icon} strokeWidth={2} />
        Voltar
      </Button>

      {loading ? (
        <div className="flex flex-col p-12">
          <div className="flex-1 flex items-center justify-center">
            <Spinner />
          </div>
        </div>
      ) : (
        <div className="flex-1 flex">
          {/* Left Sidebar - Clips List */}
          {sortedClips.length === 0 ? null : (
            <aside className="w-80 fixed inset-y-0 hidden lg:flex shrink-0 items-center">
              <div className="relative w-full">
                {showTopFade && (
                  <div className="absolute top-0 left-0 right-0 h-8 bg-gradient-to-b from-background to-transparent z-10 pointer-events-none" />
                )}
                <div className="w-full">
                  <ScrollArea ref={scrollRef} >
                    <div className="p-4 space-y-2 max-h-[500px]">
                      {sortedClips.map((clip, idx) => (
                        <button
                          key={clip.clip_id}
                          type="button"
                          onClick={() => handleClipSelect(clip.clip_id, idx)}
                          className={cn(
                            "w-full flex items-center gap-3 p-2 rounded-lg text-left transition-all group",
                            selectedIdx === idx
                              ? "bg-zinc-800/80"
                              : "hover:bg-zinc-900"
                          )}
                        >
                          <div className="relative w-10 h-16 bg-zinc-800 rounded overflow-hidden flex-shrink-0">
                            {clip.video_url ? (
                              <video
                                src={clip.video_url}
                                className="w-full h-full object-cover"
                              />
                            ) : (
                              <div className="absolute inset-0 flex items-center justify-center">
                                <div className="w-full h-full bg-zinc-700/20"></div>
                              </div>
                            )}
                          </div>

                          <div className="flex-1 min-w-0">
                            <p className={cn(
                              "text-xs font-medium line-clamp-2 leading-relaxed",
                              selectedIdx === idx ? "text-zinc-100" : "text-foreground group-hover:text-zinc-300"
                            )}>
                              {clip.title || "Como eu uso o Cursor para front-end (do Figma ao código)"}
                            </p>
                          </div>
                        </button>
                      ))}
                    </div>
                  </ScrollArea>
                </div>
                {showBottomFade && (
                  <div className="absolute bottom-0 left-0 right-0 h-8 bg-gradient-to-t from-background to-transparent z-10 pointer-events-none" />
                )}
              </div>
            </aside>
          )}

          {/* Main Content Area */}
          <main className="flex-1 overflow-y-auto p-6 md:p-10 lg:ml-80">
            <div className="mb-10 w-full flex justify-end items-center gap-2 max-w-7xl">
              <Button variant="secondary" size="sm" className="h-9 text-zinc-300 hover:bg-zinc-800 hover:text-white gap-2 text-xs">
                <HugeiconsIcon icon={FilterIcon} className="h-4 w-4" />
                <span>Filtrar</span>
              </Button>
              <div className="flex bg-card items-center gap-2 rounded-md px-3 h-9">
                <span className="text-xs text-zinc-300">Selecionar Tudo</span>
                <Checkbox
                  checked={selectedClips.length === sortedClips.length && sortedClips.length > 0}
                  onCheckedChange={handleSelectAll}
                />
              </div>
            </div>
            <div className="max-w-5xl mx-auto space-y-16 pb-20">
              {sortedClips.length === 0 ? null : (
                sortedClips.map((clip, idx) => (
                  <ClipCard
                    key={clip.clip_id}
                    clip={clip}
                    videoId={videoId}
                    idx={idx}
                    selectedClips={selectedClips}
                    onToggleSelection={toggleClipSelection}
                    onDownload={downloadClipFile}
                    onPublish={() => setPublishOpen(true)}
                    onRename={(clipId, title) => renameClipFile({ clipId, title })}
                    onDuplicate={duplicateClipFile}
                    onDelete={deleteClipFile}
                    shareValue={value}
                    onShareValueChange={setValue}
                    isShareDialogOpen={shareClipId === clip.clip_id && isDialogOpen}
                    shareClipId={shareClipId}
                    onOpenShareDialog={(clipId: string) => {
                      setShareClipId(clipId)
                      setDialogOpen(true)
                    }}
                    onShareDialogOpenChange={(open) => {
                      setDialogOpen(open)
                      if (!open) setShareClipId(null)
                    }}
                  />
                ))
              )}
            </div>

            <PublishSheet
              open={publishOpen}
              onOpenChange={setPublishOpen}
              description={description}
              onDescriptionChange={setDescription}
              visibility={visibility}
              onVisibilityChange={setVisibility}
              allowComments={allowComments}
              onAllowCommentsChange={setAllowComments}
              allowDuets={allowDuets}
              onAllowDuetsChange={setAllowDuets}
              allowStitch={allowStitch}
              onAllowStitchChange={setAllowStitch}
              scheduleAt={scheduleAt}
              onScheduleAtChange={setScheduleAt}
            />

            {selectedClips.length > 0 && (
              <div className="fixed bottom-20 z-50 left-1/2 -translate-x-1/2 bg-card border rounded-md shadow-lg p-2 flex items-center gap-4 animate-in slide-in-from-bottom-5">
                <span className="text-sm font-medium pl-2">
                  {selectedClips.length} selecionado{selectedClips.length > 1 ? 's' : ''}
                </span>
                <Button variant="destructive" size="sm" onClick={() => setSelectedClips([])}>
                  <HugeiconsIcon icon={Delete02Icon} className="size-4 mr-2" />
                  Deletar
                </Button>
              </div>
            )}
          </main>
        </div>
      )}
    </div>
  )
}