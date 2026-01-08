"use client"

import { useQuery } from "@tanstack/react-query"
import { useParams, useRouter } from "next/navigation"
import { useEffect, useMemo, useRef, useState } from "react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import {
  ArrowLeft02Icon,
  BendToolIcon,
  ChatTranslate01Icon,
  ClosedCaptionFreeIcons,
  Copy02Icon,
  Delete02Icon,
  DownloadSquare01Icon,
  GeometricShapes01Icon,
  Layers01Icon,
  MagicWand01Icon,
  Settings05Icon,
  SubtitleIcon,
  TextAlignJustifyCenterIcon,
  TextSquareIcon
} from "@hugeicons/core-free-icons"
import { HugeiconsIcon } from "@hugeicons/react"
import { Pause, Play, Scissors, X } from "lucide-react"

import { getSession } from "@/infra/auth/auth"
import type { TranscriptSegment } from "@/infra/videos/videos"
import { getClipDetails, getVideoTrimContext } from "@/infra/videos/videos"

function formatTimeLabel(seconds: number) {
  if (!Number.isFinite(seconds) || seconds < 0) return "00:00"
  const totalSeconds = Math.floor(seconds)
  const mins = Math.floor(totalSeconds / 60)
  const secs = totalSeconds % 60
  return `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`
}

function formatTimeRangeLabel(seconds: number) {
  if (!Number.isFinite(seconds) || seconds < 0) return "00:00.00"
  const mins = Math.floor(seconds / 60)
  const secs = seconds % 60
  const wholeSecs = Math.floor(secs)
  const centis = Math.floor((secs - wholeSecs) * 100)
  return `${mins.toString().padStart(2, "0")}:${wholeSecs
    .toString()
    .padStart(2, "0")}.${centis.toString().padStart(2, "0")}`
}

export default function ClipEditPage() {
  const router = useRouter()
  const params = useParams<{ videoId: string }>()

  const videoId = params?.videoId
  const [clipId, setClipId] = useState<string | null>(null)

  const leftScrollRef = useRef<HTMLDivElement>(null)
  const previewVideoRef = useRef<HTMLVideoElement>(null)
  const previewContainerRef = useRef<HTMLDivElement>(null)
  const timelineScrollRef = useRef<HTMLDivElement>(null)
  const [showLeftTopFade, setShowLeftTopFade] = useState(false)
  const [showLeftBottomFade, setShowLeftBottomFade] = useState(false)
  const [isPreviewSelected, setIsPreviewSelected] = useState(false)
  const [showTimelineLeftFade, setShowTimelineLeftFade] = useState(false)
  const [showTimelineRightFade, setShowTimelineRightFade] = useState(false)
  const [isPlaying, setIsPlaying] = useState(false)
  const [playbackRate, setPlaybackRate] = useState<0.5 | 0.75 | 1 | 1.25 | 1.5 | 2>(1)
  const [relativeTime, setRelativeTime] = useState(0)
  const [showTimeline, setShowTimeline] = useState(true)
  const [cropRect, setCropRect] = useState({ x: 0, y: 0, w: 100, h: 100 })
  const [videoPan, setVideoPan] = useState({ x: 0, y: 0 })
  const [rotation, setRotation] = useState(0)

  const panRef = useRef<{ active: boolean; startX: number; startY: number; panX: number; panY: number } | null>(null)
  const rotateRef = useRef<{ active: boolean; startAngle: number; startRotation: number; cx: number; cy: number } | null>(null)
  const cropOverlayRef = useRef<HTMLDivElement>(null)

  const dragRef = useRef<{
    active: boolean
    handle: "n" | "s" | "e" | "w" | "ne" | "nw" | "se" | "sw"
    startClientX: number
    startClientY: number
    startRect: { x: number; y: number; w: number; h: number }
    aspect: number
  } | null>(null)

  const { data: user } = useQuery({
    queryKey: ["auth-session"],
    queryFn: getSession,
  })

  const organizationId = user?.organization_id || ""

  const [activeTab, setActiveTab] = useState<"Transcrição" | "Editar Subtítulos">("Transcrição")
  const [search, setSearch] = useState("")
  const [ratio, setRatio] = useState<"9:16" | "1:1" | "16:9">("9:16")
  const [subtitleMode, setSubtitleMode] = useState<"Paragraph" | "Sentence">("Paragraph")

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
    queryKey: ["clip-details", clipId, organizationId],
    queryFn: () => getClipDetails(clipId as string, organizationId),
    enabled: !!clipId && !!organizationId,
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

  const leftPanelSegments = isTabTranscript ? segments : filteredSegments

  const previewAspectClass =
    ratio === "9:16" ? "aspect-[9/16]" : ratio === "1:1" ? "aspect-square" : "aspect-video"

  const fullVideoUrl = trimContext?.video_url || null
  const clipStart = clip?.start_time ?? 0
  const clipEnd = clip?.end_time ?? 0
  const clipDuration = Math.max(0, clipEnd - clipStart)

  useEffect(() => {
    const el = previewVideoRef.current
    if (!el) return
    if (!fullVideoUrl) return
    if (!Number.isFinite(clipStart) || !Number.isFinite(clipEnd) || clipEnd <= clipStart) return

    let raf = 0

    const clampPlayback = () => {
      if (el.currentTime < clipStart) el.currentTime = clipStart
      if (el.currentTime > clipEnd) {
        el.pause()
        el.currentTime = clipEnd
      }
    }

    const onTimeUpdate = () => clampPlayback()
    const onSeeking = () => clampPlayback()
    const onLoadedMeta = () => {
      // ensure we seek after metadata is available
      raf = window.requestAnimationFrame(() => {
        try {
          el.currentTime = clipStart
        } catch {
          // ignore
        }
      })
    }

    el.addEventListener("timeupdate", onTimeUpdate)
    el.addEventListener("seeking", onSeeking)
    el.addEventListener("loadedmetadata", onLoadedMeta)

    const onPlay = () => setIsPlaying(true)
    const onPause = () => setIsPlaying(false)
    const onTimeUpdateUI = () => {
      setRelativeTime(Math.min(Math.max(el.currentTime - clipStart, 0), clipDuration))
    }
    el.addEventListener("play", onPlay)
    el.addEventListener("pause", onPause)
    el.addEventListener("timeupdate", onTimeUpdateUI)

    return () => {
      el.removeEventListener("timeupdate", onTimeUpdate)
      el.removeEventListener("seeking", onSeeking)
      el.removeEventListener("loadedmetadata", onLoadedMeta)
      el.removeEventListener("play", onPlay)
      el.removeEventListener("pause", onPause)
      el.removeEventListener("timeupdate", onTimeUpdateUI)
      if (raf) window.cancelAnimationFrame(raf)
    }
  }, [fullVideoUrl, clipStart, clipEnd])

  useEffect(() => {
    const el = previewVideoRef.current
    if (!el) return
    el.playbackRate = playbackRate
  }, [playbackRate])

  const handleTogglePlay = async () => {
    const el = previewVideoRef.current
    if (!el) return
    if (!Number.isFinite(clipStart) || !Number.isFinite(clipEnd) || clipEnd <= clipStart) return

    if (el.paused) {
      if (el.currentTime < clipStart || el.currentTime >= clipEnd) {
        try {
          el.currentTime = clipStart
        } catch {
          // ignore
        }
      }

      try {
        await el.play()
      } catch {
        // ignore
      }
      return
    }

    el.pause()
  }

  const startCropDrag = (
    handle: "n" | "s" | "e" | "w" | "ne" | "nw" | "se" | "sw",
    e: import("react").PointerEvent
  ) => {
    const container = previewContainerRef.current
    if (!container) return
    e.preventDefault()
    e.stopPropagation()

    const aspect = cropRect.h > 0 ? cropRect.w / cropRect.h : 1

    dragRef.current = {
      active: true,
      handle,
      startClientX: e.clientX,
      startClientY: e.clientY,
      startRect: cropRect,
      aspect,
    }

    try {
      ; (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId)
    } catch {
      // ignore
    }
  }

  const onVideoPointerDown = (e: import("react").PointerEvent) => {
    if (!isPreviewSelected) return
    if (e.button !== 0) return
    const container = previewContainerRef.current
    if (!container) return
    e.preventDefault()
    e.stopPropagation()

    panRef.current = {
      active: true,
      startX: e.clientX,
      startY: e.clientY,
      panX: videoPan.x,
      panY: videoPan.y,
    }
  }

  const startRotateDrag = (e: import("react").PointerEvent) => {
    if (!isPreviewSelected) return
    if (e.button !== 0) return
    const overlay = cropOverlayRef.current
    if (!overlay) return
    e.preventDefault()
    e.stopPropagation()

    const rect = overlay.getBoundingClientRect()
    const cx = rect.left + rect.width / 2
    const cy = rect.top + rect.height / 2
    const startAngle = Math.atan2(e.clientY - cy, e.clientX - cx)

    rotateRef.current = {
      active: true,
      startAngle,
      startRotation: rotation,
      cx,
      cy,
    }

    try {
      ; (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId)
    } catch {
      // ignore
    }
  }

  useEffect(() => {
    const onMove = (e: PointerEvent) => {
      const container = previewContainerRef.current
      const drag = dragRef.current
      if (!container || !drag?.active) return

      const rectPx = container.getBoundingClientRect()
      const dxPct = ((e.clientX - drag.startClientX) / rectPx.width) * 100
      const dyPct = ((e.clientY - drag.startClientY) / rectPx.height) * 100

      const minSize = 5
      let next = { ...drag.startRect }

      const applyClamp = () => {
        next.w = Math.max(minSize, Math.min(100, next.w))
        next.h = Math.max(minSize, Math.min(100, next.h))
        next.x = Math.max(0, Math.min(100 - next.w, next.x))
        next.y = Math.max(0, Math.min(100 - next.h, next.y))
      }

      const lockAspect = e.shiftKey

      if (drag.handle.includes("e")) {
        next.w = drag.startRect.w + dxPct
      }
      if (drag.handle.includes("s")) {
        next.h = drag.startRect.h + dyPct
      }
      if (drag.handle.includes("w")) {
        next.x = drag.startRect.x + dxPct
        next.w = drag.startRect.w - dxPct
      }
      if (drag.handle.includes("n")) {
        next.y = drag.startRect.y + dyPct
        next.h = drag.startRect.h - dyPct
      }

      if (lockAspect && (drag.handle === "ne" || drag.handle === "nw" || drag.handle === "se" || drag.handle === "sw")) {
        const wFromH = next.h * drag.aspect
        const hFromW = next.w / drag.aspect

        if (Math.abs(wFromH - next.w) < Math.abs(hFromW - next.h)) {
          const prevW = next.w
          next.w = wFromH
          if (drag.handle.includes("w")) next.x = drag.startRect.x + (drag.startRect.w - next.w)
          if (drag.handle.includes("e")) next.x = drag.startRect.x
          if (drag.handle.includes("n") || drag.handle.includes("s")) {
            // keep vertical edge behavior already computed
          }
          if (prevW !== next.w) {
            // no-op
          }
        } else {
          const prevH = next.h
          next.h = hFromW
          if (drag.handle.includes("n")) next.y = drag.startRect.y + (drag.startRect.h - next.h)
          if (drag.handle.includes("s")) next.y = drag.startRect.y
          if (prevH !== next.h) {
            // no-op
          }
        }
      }

      applyClamp()
      setCropRect(next)
    }

    const onUp = () => {
      if (dragRef.current) dragRef.current.active = false
      dragRef.current = null
    }

    window.addEventListener("pointermove", onMove)
    window.addEventListener("pointerup", onUp)
    return () => {
      window.removeEventListener("pointermove", onMove)
      window.removeEventListener("pointerup", onUp)
    }
  }, [])

  useEffect(() => {
    const onMove = (e: PointerEvent) => {
      const container = previewContainerRef.current
      if (!container) return

      const videoEl = previewVideoRef.current

      const pan = panRef.current
      if (pan?.active) {
        const rect = container.getBoundingClientRect()
        const dx = e.clientX - pan.startX
        const dy = e.clientY - pan.startY

        const viewportW = rect.width * (cropRect.w / 100)
        const viewportH = rect.height * (cropRect.h / 100)
        const videoW = videoEl?.videoWidth ?? 0
        const videoH = videoEl?.videoHeight ?? 0

        let maxX = 50
        let maxY = 50

        if (viewportW > 0 && viewportH > 0 && videoW > 0 && videoH > 0) {
          const videoAspect = videoW / videoH
          const viewportAspect = viewportW / viewportH

          if (videoAspect > viewportAspect) {
            // wider than viewport => overflow horizontally
            const scale = viewportH / videoH
            const scaledW = videoW * scale
            const overflowX = Math.max(0, scaledW - viewportW)
            maxX = overflowX > 0 ? (overflowX / 2 / viewportW) * 100 : 0
            maxY = 0
          } else {
            // taller than viewport => overflow vertically
            const scale = viewportW / videoW
            const scaledH = videoH * scale
            const overflowY = Math.max(0, scaledH - viewportH)
            maxY = overflowY > 0 ? (overflowY / 2 / viewportH) * 100 : 0
            maxX = 0
          }
        }

        const dxPct = viewportW > 0 ? (dx / viewportW) * 100 : 0
        const dyPct = viewportH > 0 ? (dy / viewportH) * 100 : 0

        const clamp = (v: number, min: number, max: number) => Math.max(min, Math.min(max, v))

        setVideoPan({
          x: clamp(pan.panX + dxPct, -maxX, maxX),
          y: clamp(pan.panY + dyPct, -maxY, maxY),
        })
      }

      const rot = rotateRef.current
      if (rot?.active) {
        const angle = Math.atan2(e.clientY - rot.cy, e.clientX - rot.cx)
        const deltaDeg = ((angle - rot.startAngle) * 180) / Math.PI
        setRotation(rot.startRotation + deltaDeg)
      }
    }

    const onUp = () => {
      if (panRef.current) panRef.current.active = false
      panRef.current = null
      if (rotateRef.current) rotateRef.current.active = false
      rotateRef.current = null
    }

    window.addEventListener("pointermove", onMove)
    window.addEventListener("pointerup", onUp)
    return () => {
      window.removeEventListener("pointermove", onMove)
      window.removeEventListener("pointerup", onUp)
    }
  }, [cropRect.x, cropRect.y, cropRect.w, cropRect.h, isPreviewSelected, rotation, videoPan.x, videoPan.y])

  useEffect(() => {
    const root = leftScrollRef.current
    if (!root) return

    const scrollElement = root.querySelector<HTMLDivElement>(
      "[data-radix-scroll-area-viewport]"
    )
    if (!scrollElement) return

    const updateFades = () => {
      const { scrollTop, scrollHeight, clientHeight } = scrollElement
      const canScroll = scrollHeight - clientHeight > 1
      if (!canScroll) {
        setShowLeftTopFade(false)
        setShowLeftBottomFade(false)
        return
      }
      setShowLeftTopFade(scrollTop > 0)
      setShowLeftBottomFade(scrollTop + clientHeight < scrollHeight - 1)
    }

    updateFades()
    scrollElement.addEventListener("scroll", updateFades, { passive: true })
    window.addEventListener("resize", updateFades)

    return () => {
      scrollElement.removeEventListener("scroll", updateFades)
      window.removeEventListener("resize", updateFades)
    }
  }, [activeTab, subtitleMode, search, segments.length, filteredSegments.length])

  useEffect(() => {
    const root = timelineScrollRef.current
    if (!root) return

    const scrollElement = root.querySelector<HTMLDivElement>(
      "[data-radix-scroll-area-viewport]"
    )
    if (!scrollElement) return

    const updateFades = () => {
      const { scrollLeft, scrollWidth, clientWidth } = scrollElement
      const canScroll = scrollWidth - clientWidth > 1
      if (!canScroll) {
        setShowTimelineLeftFade(false)
        setShowTimelineRightFade(false)
        return
      }
      setShowTimelineLeftFade(scrollLeft > 0)
      setShowTimelineRightFade(scrollLeft + clientWidth < scrollWidth - 1)
    }

    updateFades()
    scrollElement.addEventListener("scroll", updateFades, { passive: true })
    window.addEventListener("resize", updateFades)

    return () => {
      scrollElement.removeEventListener("scroll", updateFades)
      window.removeEventListener("resize", updateFades)
    }
  }, [segments.length, clipDuration])

  return (
    <div className="w-full h-screen flex flex-col overflow-hidden">
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

      <div className="px-4 p-2 flex-1 flex flex-col overflow-hidden">
        <div className="flex flex-1 overflow-hidden">
          {/* Left panel */}
          <div className="overflow-hidden w-1/3 flex flex-col min-h-0">
            <div className="p-3 shrink-0">
              <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as any)}>
                <TabsList className="w-full h-10" variant="default">
                  <TabsTrigger value="Transcrição">Transcrição</TabsTrigger>
                  <TabsTrigger value="Editar Subtítulos">Editar Subtítulos</TabsTrigger>
                </TabsList>

                <TabsContent value="Transcrição" className='flex mt-3 items-center justify-center gap-2'>
                  <div className="flex-1">
                    <Input
                      value={search}
                      onChange={(e) => setSearch(e.target.value)}
                      placeholder="Search"
                      className="h-10"
                    />
                  </div>
                  <div className="flex items-center gap-2 justify-center">
                    <Button variant="ghost" size="icon">
                      <HugeiconsIcon icon={Copy02Icon} size={20} />
                    </Button>
                    <Button variant="ghost" size="icon">
                      <HugeiconsIcon icon={DownloadSquare01Icon} size={20} />
                    </Button>
                  </div>
                </TabsContent>

                <TabsContent value="Editar Subtítulos">
                  <div className="mt-3 flex items-center gap-2">
                    <div className="flex-1">
                      <Input
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                        placeholder="Search"
                        className="h-10"
                      />
                    </div>

                    <Tabs value={subtitleMode} onValueChange={(v) => setSubtitleMode(v as any)}>
                      <TabsList variant="default" className='h-10'>
                        <TabsTrigger value="Paragraph" className="group gap-2">
                          <HugeiconsIcon icon={TextAlignJustifyCenterIcon} size={16} />
                          <span className="hidden group-data-[active]:inline">Paragraph</span>
                        </TabsTrigger>
                        <TabsTrigger value="Sentence" className="group gap-2">
                          <HugeiconsIcon icon={ClosedCaptionFreeIcons} size={16} />
                          <span className="hidden group-data-[active]:inline">Sentence</span>
                        </TabsTrigger>
                      </TabsList>
                    </Tabs>
                    <div className="flex items-center gap-2">
                      <Button variant="ghost" size="icon">
                        <HugeiconsIcon icon={ChatTranslate01Icon} size={20} />
                      </Button>
                      <Button variant="ghost" size="icon">
                        <HugeiconsIcon icon={Settings05Icon} size={20} />
                      </Button>
                    </div>
                  </div>
                </TabsContent>
              </Tabs>

            </div>

            <div className="flex-1 relative overflow-hidden">
              {showLeftTopFade && (
                <div className="absolute top-0 left-0 right-0 h-20 bg-gradient-to-b from-background to-transparent z-10 pointer-events-none" />
              )}
              {showLeftBottomFade && (
                <div className="absolute bottom-0 left-0 right-0 h-20 bg-gradient-to-t from-background to-transparent z-10 pointer-events-none" />
              )}

              <ScrollArea ref={leftScrollRef} className="h-full">
                <div className="p-3">
                  {isTabTranscript ? (
                    segments.length === 0 ? (
                      <div className="text-sm text-muted-foreground py-10 text-center">Nenhum trecho encontrado.</div>
                    ) : (
                      <div className="divide-y divide-border">
                        {(search.trim() ? filteredSegments : segments).map((seg, idx) => (
                          <div key={`${seg.start}-${idx}`} className="py-3">
                            <div className="text-sm text-foreground/90 leading-relaxed">{seg.text}</div>
                          </div>
                        ))}
                      </div>
                    )
                  ) : (
                    leftPanelSegments.length === 0 ? (
                      <div className="text-sm text-muted-foreground py-10 text-center">Nenhum trecho encontrado.</div>
                    ) : subtitleMode === "Sentence" ? (
                      <div className="divide-y divide-border">
                        {leftPanelSegments.map((seg, idx) => (
                          <div key={`${seg.start}-${idx}`} className="py-3">
                            <div className="flex items-start justify-between gap-3">
                              <div className="w-28 shrink-0 text-xs tabular-nums text-muted-foreground pt-0.5">
                                {formatTimeRangeLabel(seg.start)} - {formatTimeRangeLabel(seg.end)}
                              </div>
                              <div className="flex-1 text-sm text-foreground/90 leading-relaxed">{seg.text}</div>
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="divide-y divide-border">
                        {leftPanelSegments.map((seg, idx) => (
                          <div key={`${seg.start}-${idx}`} className="py-3">
                            <div className="flex items-start gap-3">
                              <div className="w-16 shrink-0 text-xs tabular-nums text-muted-foreground pt-0.5">
                                {formatTimeLabel(seg.start)}
                              </div>
                              <div className="text-sm text-foreground/90 leading-relaxed">{seg.text}</div>
                            </div>
                          </div>
                        ))}
                      </div>
                    )
                  )}
                </div>
              </ScrollArea>
            </div>
          </div>

          {/* Center */}
          <div className="flex-1 flex-col p-2 flex items-center justify-center min-h-0">
            <div
              className={"relative w-[400px] max-h-full bg-muted flex items-center justify-center overflow-hidden cursor-pointer " + previewAspectClass}
              ref={previewContainerRef}
              onClick={() => setIsPreviewSelected((v) => !v)}
            >
              {isPreviewSelected ? (
                <div
                  className="absolute top-3 left-1/2 -translate-x-1/2 z-20 bg-accent rounded-full px-2 py-1 flex items-center gap-1 border border-border"
                  onClick={(e) => e.stopPropagation()}
                >
                  <Button variant="ghost" className="h-8 px-2 gap-2">
                    <HugeiconsIcon icon={GeometricShapes01Icon} size={18} />
                  </Button>

                  <Button variant="ghost" size="icon" className="h-8 w-8" title={`Ratio (${ratio})`}>
                    <HugeiconsIcon icon={BendToolIcon} size={18} />
                  </Button>

                  <Button variant="ghost" size="icon" className="h-8 w-8" title="Camada">
                    <HugeiconsIcon icon={Layers01Icon} size={18} />
                  </Button>

                  <Button variant="ghost" size="icon" className="h-8 w-8" title="Deletar camada">
                    <HugeiconsIcon icon={Delete02Icon} size={18} />
                  </Button>
                </div>
              ) : null}

              {fullVideoUrl ? (
                <div
                  className="absolute inset-0"
                  style={{
                    transform: `rotate(${rotation}deg)`,
                    transformOrigin: "50% 50%",
                    willChange: "transform",
                  }}
                >
                  <video
                    ref={previewVideoRef}
                    src={fullVideoUrl}
                    className="w-full h-full object-cover"
                    onPointerDown={onVideoPointerDown}
                    style={{
                      clipPath: `inset(${cropRect.y}% ${100 - (cropRect.x + cropRect.w)}% ${100 - (cropRect.y + cropRect.h)}% ${cropRect.x}%)`,
                      objectPosition: `${50 + videoPan.x}% ${50 + videoPan.y}%`,
                    }}
                  />

                  {isPreviewSelected ? (
                    <div
                      ref={cropOverlayRef}
                      className="absolute z-10 border-2 border-primary"
                      style={{
                        left: `${cropRect.x}%`,
                        top: `${cropRect.y}%`,
                        width: `${cropRect.w}%`,
                        height: `${cropRect.h}%`,
                        pointerEvents: "none",
                      }}
                      onClick={(e) => e.stopPropagation()}
                    >
                      <div
                        onPointerDown={startRotateDrag}
                        className="absolute size-3 bg-white border border-border rounded-full"
                        style={{
                          left: "50%",
                          top: "-18px",
                          transform: "translate(-50%, -50%)",
                          cursor: "grab",
                          pointerEvents: "auto",
                        }}
                        title="Rotate"
                      />

                      {([
                        { key: "nw", x: 0, y: 0, cursor: "nwse-resize" },
                        { key: "n", x: 50, y: 0, cursor: "ns-resize" },
                        { key: "ne", x: 100, y: 0, cursor: "nesw-resize" },
                        { key: "e", x: 100, y: 50, cursor: "ew-resize" },
                        { key: "se", x: 100, y: 100, cursor: "nwse-resize" },
                        { key: "s", x: 50, y: 100, cursor: "ns-resize" },
                        { key: "sw", x: 0, y: 100, cursor: "nesw-resize" },
                        { key: "w", x: 0, y: 50, cursor: "ew-resize" },
                      ] as const).map((h) => (
                        <div
                          key={h.key}
                          onPointerDown={(e) => startCropDrag(h.key, e)}
                          className="absolute size-2.5 bg-white border border-border rounded-sm"
                          style={{
                            left: `${h.x}%`,
                            top: `${h.y}%`,
                            transform: "translate(-50%, -50%)",
                            cursor: h.cursor,
                            pointerEvents: "auto",
                          }}
                        />
                      ))}
                    </div>
                  ) : null}
                </div>
              ) : (
                <span className="text-muted-foreground text-sm">Preview</span>
              )}
            </div>

            <div className="mt-3 flex items-center justify-center gap-2 w-full">
              <button
                type="button"
                className="h-9 rounded-md px-3 inline-flex items-center gap-2 border border-border text-foreground/90 hover:bg-muted"
              >
                <HugeiconsIcon icon={TextSquareIcon} size={18} />
                <span className="text-sm">Ratio ({ratio})</span>
              </button>

              <button
                type="button"
                className="h-9 rounded-md px-3 inline-flex items-center gap-2 border border-border text-foreground/90 hover:bg-muted"
              >
                <HugeiconsIcon icon={MagicWand01Icon} size={18} />
                <span className="text-sm">Background</span>
              </button>

              <button
                type="button"
                className="h-9 rounded-md px-3 inline-flex items-center gap-2 border border-border text-foreground/90 hover:bg-muted"
              >
                <HugeiconsIcon icon={SubtitleIcon} size={18} />
                <span className="text-sm">Layouts</span>
              </button>

            </div>
          </div>

          {/* Right panel */}
          <div className="overflow-hidden p-2 w-[80px]">
            <div className="flex flex-col gap-8 mt-3">
              <button className="flex flex-col justify-center items-center">
                <HugeiconsIcon icon={MagicWand01Icon} size={18} />
                <span className="text-xs">AI Tools</span>
              </button>
              <button className="flex flex-col justify-center items-center">
                <HugeiconsIcon icon={TextSquareIcon} size={18} />
                <span className="text-xs">Text</span>
              </button>
              <button className="flex flex-col justify-center items-center">
                <HugeiconsIcon icon={SubtitleIcon} size={18} />
                <span className="text-xs">Subtitles</span>
              </button>
            </div>
          </div>
        </div>

        <div className="shrink-0 px-6">
          <div className="h-12 grid grid-cols-3 items-center">
            <div className="flex items-center gap-2" />

            <div className="flex items-center justify-center gap-3">
              <span className="text-xs tabular-nums text-muted-foreground">{formatTimeRangeLabel(clipStart + relativeTime)}</span>
              <button
                type="button"
                onClick={handleTogglePlay}
                className="h-8 w-8 inline-flex items-center justify-center rounded-full bg-accent"
              >
                {isPlaying ? <Pause className="size-4 fill-foreground" /> : <Play className="size-4 fill-foreground" />}
              </button>
              <span className="text-xs tabular-nums text-muted-foreground">{formatTimeRangeLabel(clipEnd)}</span>
            </div>

            <div className="flex items-center justify-end gap-3">
              <Select
                value={String(playbackRate)}
                onValueChange={(v) => setPlaybackRate(Number(v) as any)}
              >
                <SelectTrigger className="h-8 w-fit rounded-md bg-transparent border border-border px-2 text-sm">
                  <SelectValue>{`${playbackRate}x`}</SelectValue>
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="0.5">0.5x</SelectItem>
                  <SelectItem value="0.75">0.75x</SelectItem>
                  <SelectItem value="1">1x</SelectItem>
                  <SelectItem value="1.25">1.25x</SelectItem>
                  <SelectItem value="1.5">1.5x</SelectItem>
                  <SelectItem value="2">2x</SelectItem>
                </SelectContent>
              </Select>

              <button
                type="button"
                className="h-8 w-8 inline-flex items-center justify-center rounded-md hover:bg-accent"
                title="Split"
              >
                <Scissors className="size-4" />
              </button>

              <button
                type="button"
                onClick={() => setShowTimeline(false)}
                className="h-8 w-8 inline-flex items-center justify-center rounded-md hover:bg-accent"
                title="Fechar"
              >
                <X className="size-4" />
              </button>
            </div>
          </div>
        </div>

        {/* Bottom timeline area */}
        <div className={showTimeline ? "shrink-0 max-h-[200px] min-h-[200px]" : "hidden"}>

          <div className="h-full px-4 py-4">
            <div className="relative h-full bg-background/20 overflow-hidden">
              {showTimelineLeftFade ? (
                <div className="pointer-events-none absolute left-0 top-0 bottom-0 w-10 z-30 bg-gradient-to-r from-background/60 to-transparent" />
              ) : null}
              {showTimelineRightFade ? (
                <div className="pointer-events-none absolute right-0 top-0 bottom-0 w-10 z-30 bg-gradient-to-l from-background/60 to-transparent" />
              ) : null}

              <div
                className="absolute top-0 bottom-0 z-20"
                style={{
                  left:
                    clipDuration > 0
                      ? `${Math.min(Math.max(relativeTime / clipDuration, 0), 1) * 100}%`
                      : "0%",
                }}
              >
                <img
                  src="/trim-cursor-editor.svg"
                  alt="Playhead"
                  className="h-full w-auto -translate-x-1/2 pointer-events-none select-none pl-[16px]"
                />
              </div>

              <ScrollArea className="h-full" ref={timelineScrollRef}>
                <div className="w-max min-w-full">
                  <div className="h-7 flex items-end px-2 relative">
                    <div className="absolute inset-x-0 bottom-0 h-px bg-border/60" />
                    <div className="w-full h-full relative">
                      {Array.from({ length: 6 }).map((_, i) => (
                        <div
                          key={`tick-${i}`}
                          className="absolute bottom-1 text-[10px] tabular-nums text-muted-foreground"
                          style={{ left: `${(i / 5) * 100}%` }}
                        >
                          {formatTimeLabel((clipDuration || 30) * (i / 5))}
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="px-2 py-2">
                    <div className="flex flex-row gap-1">
                      {(segments.length === 0 ? ["Add Text", "Add Text", "Subtitle"] : segments.slice(0, 40)).map((item, idx) => {
                        const label = typeof item === "string" ? item : (item.text || "")
                        const start = typeof item === "string" ? null : item.start
                        const end = typeof item === "string" ? null : item.end

                        const widthPct =
                          start !== null && end !== null && clipDuration > 0
                            ? `${Math.max(3, ((end - start) / clipDuration) * 100)}%`
                            : "120px"

                        return (
                          <div
                            key={`${label}-${idx}`}
                            className="h-8 w-10 rounded-md bg-accent/50 border border-border flex items-center px-2 text-xs shrink-0"
                            style={{ width: widthPct }}
                          >
                            {start === null ? (
                              <span className={label === "Subtitle" ? "text-primary font-medium" : "text-muted-foreground"}>
                                {label}
                              </span>
                            ) : (
                              <div className="flex items-center w-full gap-2 min-w-0">
                                <span className="text-[10px] tabular-nums text-muted-foreground shrink-0">
                                  {formatTimeLabel(start)}
                                </span>
                                <span className="text-xs text-foreground/90 truncate">{label}</span>
                              </div>
                            )}
                          </div>
                        )
                      })}
                    </div>
                  </div>


                </div>
              </ScrollArea>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
