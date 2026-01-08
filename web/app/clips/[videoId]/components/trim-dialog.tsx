"use client"

import { useEffect, useMemo, useRef, useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Search } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Switch } from "@/components/ui/switch"

import { getSession } from "@/infra/auth/auth"
import { getVideoTrimContext, updateClipTrim } from "@/infra/videos/videos"
import type { Clip, TranscriptSegment, VideoTrimContextResponse } from "@/infra/videos/videos"
import { toast } from "sonner"
import { cn } from "@/lib/utils"
import { Slider } from "@/components/ui/slider"

function formatTimeLabel(seconds: number) {
  if (!Number.isFinite(seconds) || seconds < 0) return "00:00"
  const totalSeconds = Math.floor(seconds)
  const hours = Math.floor(totalSeconds / 3600)
  const mins = Math.floor((totalSeconds % 3600) / 60)
  const secs = totalSeconds % 60
  if (hours > 0) {
    return `${hours.toString().padStart(2, "0")}:${mins.toString().padStart(2, "0")}:${secs
      .toString()
      .padStart(2, "0")}`
  }
  return `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`
}

function clamp(n: number, min: number, max: number) {
  return Math.max(min, Math.min(max, n))
}

type TranscriptBlock = {
  start: number
  end: number
  text: string
}

function sliceTextByTimeWindow(args: {
  text: string
  blockStart: number
  blockEnd: number
  windowStart: number
  windowEnd: number
}) {
  const { text, blockStart, blockEnd, windowStart, windowEnd } = args
  const duration = blockEnd - blockStart
  if (!Number.isFinite(duration) || duration <= 0 || text.length === 0) {
    return { prefix: "", selected: text, suffix: "" }
  }

  const a = clamp((windowStart - blockStart) / duration, 0, 1)
  const b = clamp((windowEnd - blockStart) / duration, 0, 1)
  const startRatio = Math.min(a, b)
  const endRatio = Math.max(a, b)

  const startIdx = Math.floor(startRatio * text.length)
  const endIdx = Math.ceil(endRatio * text.length)

  return {
    prefix: text.slice(0, startIdx),
    selected: text.slice(startIdx, endIdx),
    suffix: text.slice(endIdx),
  }
}

function groupTranscriptSegments(
  segments: TranscriptSegment[],
  opts?: {
    maxGapSeconds?: number
    maxCharsPerBlock?: number
  }
): TranscriptBlock[] {
  const maxGapSeconds = opts?.maxGapSeconds ?? 0.7
  const maxCharsPerBlock = opts?.maxCharsPerBlock ?? 240

  const sorted = [...segments].sort((a, b) => a.start - b.start)
  const blocks: TranscriptBlock[] = []

  for (const seg of sorted) {
    const segText = (seg.text ?? "").trim()
    if (!segText) continue

    const last = blocks.at(-1)
    if (!last) {
      blocks.push({ start: seg.start, end: seg.end, text: segText })
      continue
    }

    const gap = seg.start - last.end
    const nextText = `${last.text} ${segText}`.trim()

    if (gap <= maxGapSeconds && nextText.length <= maxCharsPerBlock) {
      last.end = Math.max(last.end, seg.end)
      last.text = nextText
    } else {
      blocks.push({ start: seg.start, end: seg.end, text: segText })
    }
  }

  return blocks
}

export function TrimDialog({
  open,
  onOpenChange,
  clip,
  videoId,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  clip: Clip
  videoId: string
}) {
  const queryClient = useQueryClient()
  const videoRef = useRef<HTMLVideoElement>(null)
  const waveRef = useRef<any>(null)
  const transcriptScrollRef = useRef<HTMLDivElement>(null)
  const scrollToSelectedAttemptRef = useRef(0)
  const [showTranscriptTopFade, setShowTranscriptTopFade] = useState(false)
  const [showTranscriptBottomFade, setShowTranscriptBottomFade] = useState(false)

  const { data: user } = useQuery({
    queryKey: ["auth-session"],
    queryFn: getSession,
  })

  const organizationId = user?.organization_id || ""

  const { data, error, refetch, isLoading, isFetching } = useQuery({
    queryKey: ["video-trim-context", videoId, organizationId, clip.clip_id],
    queryFn: () => getVideoTrimContext(videoId, organizationId),
    enabled: open && !!videoId && !!organizationId,
    retry: 1,
  })

  useEffect(() => {
    if (open && videoId && organizationId) {
      refetch()
    }
  }, [open, videoId, organizationId, refetch])

  const [search, setSearch] = useState("")
  const [range, setRange] = useState<[number, number]>([clip.start_time ?? 0, clip.end_time ?? 0])
  const [autoReframe, setAutoReframe] = useState(false)

  useEffect(() => {
    if (open) {
      setSearch("")
      setRange([clip.start_time ?? 0, clip.end_time ?? 0])
      setAutoReframe(false)
    }
  }, [open, clip.clip_id, clip.start_time, clip.end_time])

  const segments: TranscriptSegment[] = (data as VideoTrimContextResponse | undefined)?.transcript?.segments ?? []
  const videoUrl = (clip as any)?.full_video_url || (data as VideoTrimContextResponse | undefined)?.video_url

  const transcriptBlocks = useMemo(() => {
    return groupTranscriptSegments(segments)
  }, [segments])

  const filteredBlocks = useMemo(() => {
    const q = search.trim().toLowerCase()
    if (!q) return transcriptBlocks
    return transcriptBlocks.filter((b) => (b.text || "").toLowerCase().includes(q))
  }, [transcriptBlocks, search])

  const max = useMemo(() => {
    const maybeMax = (data as VideoTrimContextResponse | undefined)?.transcript?.segments?.at(-1)?.end
    return Number.isFinite(maybeMax) ? (maybeMax as number) : Math.max(range[1] || 0, 1)
  }, [data, range])

  const sliderValue = useMemo(() => {
    const a = clamp(range[0], 0, max)
    const b = clamp(range[1], 0, max)
    return a <= b ? [a, b] : [b, a]
  }, [range, max])

  const isSegmentActive = (segStart: number, segEnd: number) => {
    const mid = (segStart + segEnd) / 2
    return mid >= sliderValue[0] && mid <= sliderValue[1]
  }

  const getOverlapWindow = (blockStart: number, blockEnd: number) => {
    const a = Math.min(sliderValue[0], sliderValue[1])
    const b = Math.max(sliderValue[0], sliderValue[1])
    const start = Math.max(blockStart, a)
    const end = Math.min(blockEnd, b)
    const hasOverlap = end > start
    return { start, end, hasOverlap }
  }

  const firstSelectedBlockId = useMemo(() => {
    for (let i = 0; i < filteredBlocks.length; i++) {
      const block = filteredBlocks[i]
      const overlap = getOverlapWindow(block.start, block.end)
      if (overlap.hasOverlap) {
        return `transcript-block-${clip.clip_id}-${block.start}-${i}`
      }
    }
    return null
  }, [clip.clip_id, filteredBlocks, sliderValue[0], sliderValue[1]])

  useEffect(() => {
    if (!open) return
    if (!firstSelectedBlockId) return

    scrollToSelectedAttemptRef.current = 0

    const scrollElement = transcriptScrollRef.current?.querySelector(
      "[data-radix-scroll-area-viewport]",
    ) as HTMLDivElement | null

    if (!scrollElement) return

    let cancelled = false
    let t: number | undefined

    const updateFade = () => {
      const { scrollTop, scrollHeight, clientHeight } = scrollElement
      const canScroll = scrollHeight - clientHeight > 1
      if (!canScroll) {
        setShowTranscriptTopFade(false)
        setShowTranscriptBottomFade(false)
        return
      }
      setShowTranscriptTopFade(scrollTop > 0)
      setShowTranscriptBottomFade(scrollTop + clientHeight < scrollHeight - 1)
    }

    scrollElement.addEventListener("scroll", updateFade, { passive: true })
    updateFade()

    const tryScroll = () => {
      if (cancelled) return
      scrollToSelectedAttemptRef.current += 1

      const el = scrollElement.querySelector(`#${CSS.escape(firstSelectedBlockId)}`) as HTMLElement | null
      if (!el) {
        if (scrollToSelectedAttemptRef.current < 12) {
          t = window.setTimeout(tryScroll, 50)
        }
        return
      }

      const viewportRect = scrollElement.getBoundingClientRect()
      const elRect = el.getBoundingClientRect()

      const delta = elRect.top - viewportRect.top
      scrollElement.scrollTo({
        top: Math.max(0, scrollElement.scrollTop + delta - 24),
        behavior: "instant" as ScrollBehavior,
      })

      window.setTimeout(() => {
        if (!cancelled) updateFade()
      }, 0)
    }

    t = window.setTimeout(tryScroll, 0)

    return () => {
      cancelled = true
      if (t) window.clearTimeout(t)
      scrollElement.removeEventListener("scroll", updateFade)
    }
  }, [open, clip.clip_id, firstSelectedBlockId, filteredBlocks.length])

  useEffect(() => {
    if (!open) {
      setShowTranscriptTopFade(false)
      setShowTranscriptBottomFade(false)
    }
  }, [open])

  const handleSeek = (t: number) => {
    if (videoRef.current) {
      videoRef.current.currentTime = Math.max(0, t)
      if (videoRef.current.paused) {
        videoRef.current.play().catch(() => { })
      }
    }
  }

  const markerLeft = (t: number) => {
    if (!Number.isFinite(max) || max <= 0) return "0%"
    const pct = clamp(t / max, 0, 1) * 100
    return `${pct}%`
  }

  const handleVideoTimeUpdate = () => {
    if (videoRef.current && waveRef.current) {
      waveRef.current.currentTime = videoRef.current.currentTime
    }
  }

  const { mutate: saveTrim, isPending: saving } = useMutation({
    mutationFn: async () => {
      if (!organizationId) throw new Error("organization_id missing")
      return updateClipTrim(clip.clip_id, {
        organization_id: organizationId,
        start_time: range[0],
        end_time: range[1],
      })
    },
    onSuccess: async () => {
      toast.success("Corte atualizado!")
      await queryClient.invalidateQueries({ queryKey: ["video-clips"] })
      onOpenChange(false)
    },
    onError: (e) => {
      toast.error(e instanceof Error ? e.message : "Erro ao atualizar corte")
    },
  })

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="min-w-6xl h-[800px] p-6">

        <DialogHeader>
          <DialogTitle className="text-xl">Editar tamanho do clipe</DialogTitle>
        </DialogHeader>

        <div className="flex-1 flex overflow-hidden">
          <div className="flex flex-col lg:flex-row w-full h-full">

            <div className="flex-1 flex items-center justify-center relative">
              <div className="w-full max-w-xl">
                <div className="relative w-full aspect-video rounded-lg overflow-hidden">
                  {videoUrl ? (
                    <video
                      ref={videoRef}
                      src={videoUrl}
                      className="w-full h-full object-contain"
                      onTimeUpdate={handleVideoTimeUpdate}
                      controls={false}
                    />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center text-white/40">
                      Vídeo indisponível
                    </div>
                  )}
                </div>
              </div>
            </div>
            <div className="flex flex-col">
              <div className="pb-4">
                <div className="relative bg-background rounded-lg">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-white/40" />
                  <Input
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    placeholder="Pesquisar..."
                    className="bg-[#18181b] border-transparent pl-9 text-white placeholder:text-white/40 focus-visible:ring-0 focus-visible:ring-offset-0 h-10 rounded-lg"
                  />
                </div>
              </div>
              <div className="w-full lg:w-[450px] bg-muted rounded-lg flex flex-col overflow-hidden">
                <div className="flex-1 relative overflow-hidden">
                  {showTranscriptTopFade && (
                    <div className="absolute top-0 left-0 right-0 h-20 bg-gradient-to-b from-card to-transparent z-10 pointer-events-none" />
                  )}
                  <ScrollArea ref={transcriptScrollRef} className="h-full">
                    <div className="p-4 space-y-0">
                      {error ? (
                        <div className="text-sm text-red-400">Erro ao carregar transcrição.</div>
                      ) : isLoading || isFetching ? (
                        <div className="text-sm text-white/40 text-center py-8">Carregando transcrição...</div>
                      ) : filteredBlocks.length === 0 ? (
                        <div className="text-sm text-white/40 text-center py-8">Nenhum trecho encontrado.</div>
                      ) : (
                        filteredBlocks.map((block, idx) => {
                          const active = isSegmentActive(block.start, block.end)
                          const overlap = getOverlapWindow(block.start, block.end)
                          const inStartBlock = sliderValue[0] >= block.start && sliderValue[0] <= block.end
                          const inEndBlock = sliderValue[1] >= block.start && sliderValue[1] <= block.end

                          const sliced = overlap.hasOverlap
                            ? sliceTextByTimeWindow({
                              text: block.text,
                              blockStart: block.start,
                              blockEnd: block.end,
                              windowStart: overlap.start,
                              windowEnd: overlap.end,
                            })
                            : { prefix: "", selected: "", suffix: block.text }

                          return (
                            <button
                              id={`transcript-block-${clip.clip_id}-${block.start}-${idx}`}
                              key={`${block.start}-${idx}`}
                              onClick={() => handleSeek(block.start)}
                              className={cn(
                                "w-full text-left group flex items-start gap-4 px-3 py-1.5 transition-colors relative",
                                active ? "bg-transparent" : "bg-transparent",
                                "hover:bg-muted"
                              )}
                            >
                              <span className={cn(
                                "text-xs font-medium tabular-nums w-14 shrink-0 pt-1",
                                "text-muted-foreground"
                              )}>
                                {formatTimeLabel(block.start)}
                              </span>

                              <p className={cn("text-sm leading-snug", "text-foreground/80")}>
                                {sliced.prefix}
                                {overlap.hasOverlap ? (
                                  <span className={cn(" items-center rounded-sm bg-[#1E0055] text-primary-foreground")}>
                                    {inStartBlock && Math.abs(overlap.start - sliderValue[0]) < 0.001 && (
                                      <img
                                        src="/trim-cursor.svg"
                                        alt=""
                                        aria-hidden="true"
                                        className="mr-1 inline-block h-5 w-auto shrink-0"
                                      />
                                    )}
                                    <span>{sliced.selected}</span>
                                    {inEndBlock && Math.abs(overlap.end - sliderValue[1]) < 0.001 && (
                                      <img
                                        src="/trim-cursor.svg"
                                        alt=""
                                        aria-hidden="true"
                                        className="ml-1 inline-block h-5 w-auto shrink-0"
                                      />
                                    )}
                                  </span>
                                ) : null}
                                {sliced.suffix}
                              </p>
                            </button>
                          )
                        })
                      )}
                    </div>
                  </ScrollArea>
                  {showTranscriptBottomFade && (
                    <div className="absolute bottom-0 left-0 right-0 h-20 bg-gradient-to-t from-card to-transparent z-10 pointer-events-none" />
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>

        <div className="flex items-center justify-between">

          <div className="flex items-center gap-4 w-full justify-end">
            <div className="flex items-center gap-2">
              <span className="text-xs text-white/60 font-medium">Auto reframe</span>
              <Switch
                checked={autoReframe}
                onCheckedChange={setAutoReframe}
                className="data-[state=checked]:bg-[#7c3aed]"
              />
            </div>

            <Button
              variant="ghost"
              onClick={() => onOpenChange(false)}
              className="text-white/70 hover:text-white hover:bg-white/5 focus-visible:ring-0"
            >
              Cancelar
            </Button>

            <Button
              onClick={() => saveTrim()}
              disabled={saving || !organizationId}
              className="bg-[#8b5cf6] hover:bg-[#7c3aed] text-white min-w-[80px] focus-visible:ring-0"
            >
              {saving ? "..." : "Salvar"}
            </Button>
          </div>
        </div>

      </DialogContent>
    </Dialog >
  )
}