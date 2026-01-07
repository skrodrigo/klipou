"use client"

import { useEffect, useMemo, useState } from "react"
import { useParams, useRouter } from "next/navigation"
import { useQuery } from "@tanstack/react-query"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { ScrollArea } from "@/components/ui/scroll-area"
import { HugeiconsIcon } from "@hugeicons/react"
import {
  ArrowLeft02Icon,
  PlayIcon,
  PauseIcon,
  Share03Icon,
} from "@hugeicons/core-free-icons"

import { getSession } from "@/infra/auth/auth"
import { getClipDetails, getVideoTrimContext } from "@/infra/videos/videos"
import type { TranscriptSegment } from "@/infra/videos/videos"

function formatTimeLabel(seconds: number) {
  if (!Number.isFinite(seconds) || seconds < 0) return "00:00"
  const totalSeconds = Math.floor(seconds)
  const mins = Math.floor(totalSeconds / 60)
  const secs = totalSeconds % 60
  return `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`
}

export default function ClipEditPage() {
  const router = useRouter()
  const params = useParams<{ videoId: string }>()

  const videoId = params?.videoId
  const [clipId, setClipId] = useState<string | null>(null)

  const { data: user } = useQuery({
    queryKey: ["auth-session"],
    queryFn: getSession,
  })

  const organizationId = user?.organization_id || ""

  const [activeTab, setActiveTab] = useState<"Transcrição" | "Editar Subtítulos">("Transcrição")
  const [search, setSearch] = useState("")
  const [ratio, setRatio] = useState<"9:16" | "1:1" | "16:9">("9:16")

  const isTabTranscript = activeTab === "Transcrição"

  useEffect(() => {
    if (!videoId) return
    try {
      const stored = sessionStorage.getItem(`clip-edit:${videoId}`)
      setClipId(stored)
    } catch {
      setClipId(null)
    }
  }, [videoId])

  const { data: clip } = useQuery({
    queryKey: ["clip-details", clipId],
    queryFn: () => getClipDetails(clipId as string),
    enabled: !!clipId,
  })

  const { data: trimContext } = useQuery({
    queryKey: ["video-trim-context", videoId, organizationId],
    queryFn: () => getVideoTrimContext(videoId as string, organizationId),
    enabled: !!videoId && !!organizationId,
    retry: 1,
  })

  const segments: TranscriptSegment[] = trimContext?.transcript?.segments ?? []

  const filteredSegments = useMemo(() => {
    const q = search.trim().toLowerCase()
    if (!q) return segments
    return segments.filter((s) => (s.text || "").toLowerCase().includes(q))
  }, [segments, search])

  const previewAspectClass =
    ratio === "9:16" ? "aspect-[9/16]" : ratio === "1:1" ? "aspect-square" : "aspect-video"

  return (
    <div className="w-full flex flex-col max-h-screen overflow-hidden">
      <div className="py-1 mt-5  flex items-center justify-between px-6">
        <Button
          variant='ghost'
          className="flex items-center hover:bg-transparent gap-2 text-sm font-medium text-foreground transition-colors hover:text-foreground"
          onClick={() => router.back()}
        >
          <HugeiconsIcon icon={ArrowLeft02Icon} strokeWidth={2} />
          Voltar
        </Button>

        <Button className="bg-primary text-primary-foreground hover:bg-primary/90 font-medium">
          Save
        </Button>
      </div>

      <div className="px-5 py-6">
        <div className="flex">
          {/* Left panel */}
          <div className="overflow-hidden w-1/3 border-r border-t border-l border-b border-border">
            <div className="p-3">
              <div className="grid grid-cols-2 rounded-lg bg-muted/60 p-1">
                <button
                  type="button"
                  onClick={() => setActiveTab("Transcrição")}
                  className={
                    "h-9 rounded-md text-sm " +
                    (isTabTranscript
                      ? "bg-background text-foreground shadow-sm"
                      : "text-muted-foreground hover:text-foreground")
                  }
                >
                  Transcrição
                </button>
                <button
                  type="button"
                  onClick={() => setActiveTab("Editar Subtítulos")}
                  className={
                    "h-9 rounded-md text-sm " +
                    (!isTabTranscript
                      ? "bg-background text-foreground shadow-sm"
                      : "text-muted-foreground hover:text-foreground")
                  }
                >
                  Editar Subtítulos
                </button>
              </div>

              <div className="mt-3">
                <Input
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Pesquisar..."
                  className="h-10"
                />
              </div>
            </div>

            <ScrollArea className="h-[560px]">
              <div className="p-3">
                {isTabTranscript ? (
                  filteredSegments.length === 0 ? (
                    <div className="text-sm text-muted-foreground py-10 text-center">Nenhum trecho encontrado.</div>
                  ) : (
                    <div className="space-y-2">
                      {filteredSegments.map((seg, idx) => (
                        <div key={`${seg.start}-${idx}`} className="flex items-start gap-3">
                          <div className="w-16 shrink-0 text-xs tabular-nums text-muted-foreground pt-0.5">
                            {formatTimeLabel(seg.start)}
                          </div>
                          <div className="text-sm text-foreground/90 leading-relaxed">{seg.text}</div>
                        </div>
                      ))}
                    </div>
                  )
                ) : (
                  <div className="text-sm text-muted-foreground py-10 text-center">Selecione uma legenda abaixo para editar.</div>
                )}
              </div>
            </ScrollArea>
          </div>

          {/* Center */}
          <div className="flex-1 flex-col p-2 flex items-center bg-[#111111] justify-center border-r border-t border-b border-border">
            <div className={"w-[400px] h-full bg-muted flex items-center justify-center rounded-lg overflow-hidden " + previewAspectClass}>
              {clip?.video_url ? (
                <video src={clip.video_url} className="w-full h-full object-cover" controls />
              ) : (
                <span className="text-muted-foreground text-sm">Preview</span>
              )}
            </div>
            <div className="mt-2 flex justify-end items-center gap-2 w-full">
              <div className="flex items-center gap-2">
                <Button
                  type="button"
                  variant={ratio === "9:16" ? "secondary" : "ghost"}
                  className="h-8 px-2"
                  onClick={() => setRatio("9:16")}
                >
                  <HugeiconsIcon icon={PlayIcon} size={16} />
                  9:16
                </Button>
                <Button
                  type="button"
                  variant={ratio === "1:1" ? "secondary" : "ghost"}
                  className="h-8 px-2"
                  onClick={() => setRatio("1:1")}
                >
                  <HugeiconsIcon icon={PauseIcon} size={16} />
                  1:1
                </Button>
                <Button
                  type="button"
                  variant={ratio === "16:9" ? "secondary" : "ghost"}
                  className="h-8 px-2"
                  onClick={() => setRatio("16:9")}
                >
                  <HugeiconsIcon icon={Share03Icon} size={16} />
                  16:9
                </Button>
              </div>
            </div>
          </div>

          {/* Right panel */}
          <div className="overflow-hidden p-2 border-border w-[220px]">
            <div className="flex flex-col gap-2">
              <Button type="button" variant="ghost" className="justify-start gap-2 h-10">
                <HugeiconsIcon icon={PlayIcon} size={18} />
                Subtitles
              </Button>
              <Button type="button" variant="ghost" className="justify-start gap-2 h-10">
                <HugeiconsIcon icon={PauseIcon} size={18} />
                Text
              </Button>
              <Button type="button" variant="ghost" className="justify-start gap-2 h-10">
                <HugeiconsIcon icon={Share03Icon} size={18} />
                Transition
              </Button>
            </div>
          </div>
        </div>

        {/* Bottom timeline area */}
        <div>
          <div className="h-24 border-b border-border px-4 flex items-center gap-3">
          </div>

          <div className="px-4 py-4 overflow-y-auto">
            <div className="space-y-3">
              {(segments.length === 0 ? ["Add Text", "Add Text", "Subtitle"] : segments.slice(0, 12)).map((item, idx) => {
                const label = typeof item === "string" ? item : (item.text || "")
                const start = typeof item === "string" ? null : item.start

                return (
                  <div
                    key={`${label}-${idx}`}
                    className="h-9 rounded-md bg-background/40 border border-dashed flex items-center px-3 text-sm"
                  >
                    {start === null ? (
                      <span className={label === "Subtitle" ? "text-primary font-medium" : "text-muted-foreground"}>
                        {label}
                      </span>
                    ) : (
                      <div className="flex items-center justify-between w-full gap-3">
                        <span className="text-xs tabular-nums text-muted-foreground w-16 shrink-0">
                          {formatTimeLabel(start)}
                        </span>
                        <span className="text-sm text-foreground/90 truncate">{label}</span>
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
