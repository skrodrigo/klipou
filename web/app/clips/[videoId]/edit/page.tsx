"use client"

import { useQuery } from "@tanstack/react-query"
import { useParams, useRouter } from "next/navigation"
import { useEffect, useMemo, useRef, useState } from "react"

import { Button } from "@/components/ui/button"
import {
  ArrowLeft02Icon,
} from "@hugeicons/core-free-icons"
import { HugeiconsIcon } from "@hugeicons/react"

import { getSession } from "@/infra/auth/auth"
import type { TranscriptSegment } from "@/infra/videos/videos"
import { getClipDetails, getVideoTrimContext } from "@/infra/videos/videos"

import { LeftPanel } from "./_components/left-panel"
import { PreviewArea } from "./_components/preview-area"
import { SubtitleConfigPanel } from "./_components/subtitle-config-panel"
import { TimelineArea } from "./_components/timeline-area"
import { TimelineTransportBar } from "./_components/timeline-transport-bar"

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

function formatTimeRangeLabel(seconds: number) {
  if (!Number.isFinite(seconds) || seconds < 0) return "00:00.00"
  const totalCentis = Math.floor(seconds * 100)
  const totalSeconds = Math.floor(totalCentis / 100)
  const centis = totalCentis % 100
  const hours = Math.floor(totalSeconds / 3600)
  const mins = Math.floor((totalSeconds % 3600) / 60)
  const secs = totalSeconds % 60
  if (hours > 0) {
    return `${hours.toString().padStart(2, "0")}:${mins.toString().padStart(2, "0")}:${secs
      .toString()
      .padStart(2, "0")}.${centis.toString().padStart(2, "0")}`
  }
  return `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}.${centis
    .toString()
    .padStart(2, "0")}`
}

export default function ClipEditPage() {
  const router = useRouter()
  const params = useParams<{ videoId: string }>()

  const videoId = params?.videoId
  const [clipId, setClipId] = useState<string | null>(null)

  const leftScrollRef = useRef<HTMLDivElement>(null)
  const previewVideoRef = useRef<HTMLVideoElement>(null)
  const previewContainerRef = useRef<HTMLDivElement>(null)
  const subtitleConfigRef = useRef<HTMLDivElement>(null)
  const subtitleOverlayElRef = useRef<HTMLDivElement>(null)
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
  const [isSeeking, setIsSeeking] = useState(false)

  const timelineDragRef = useRef<{ active: boolean; startX: number; startTime: number } | null>(null)

  const historyRef = useRef<{ undo: Array<{ items: TimelineItem[]; tracksCount: number }>; redo: Array<{ items: TimelineItem[]; tracksCount: number }> }>(
    { undo: [], redo: [] }
  )

  const panRef = useRef<{ active: boolean; startX: number; startY: number; panX: number; panY: number } | null>(null)
  const rotateRef = useRef<{ active: boolean; startAngle: number; startRotation: number; cx: number; cy: number } | null>(null)
  const cropOverlayRef = useRef<HTMLDivElement>(null)
  const timelineContainerRef = useRef<HTMLDivElement>(null)

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

  type TimelineItemType = "video" | "subtitle"
  type TimelineItem = {
    id: string
    type: TimelineItemType
    label: string
    start: number
    end: number
    text?: string
    track: number
  }

  const [timelineItems, setTimelineItems] = useState<TimelineItem[]>([])
  const [tracksCount, setTracksCount] = useState(2)
  const [selectedTimelineItemId, setSelectedTimelineItemId] = useState<string | null>(null)
  const [subtitleStyle, setSubtitleStyle] = useState({
    fontFamily: "Montserrat ExtraBold",
    color: "#FFFFFF",
    shadow: true,
  })

  const [subtitleOverlayPos, setSubtitleOverlayPos] = useState({ x: 50, y: 80 })

  const subtitleDragRef = useRef<{
    active: boolean
    startX: number
    startY: number
    posX: number
    posY: number
  } | null>(null)

  const timelineItemDragRef = useRef<{
    active: boolean
    itemId: string
    mode: "move" | "trim-start" | "trim-end"
    startClientX: number
    startClientY: number
    initialStart: number
    initialEnd: number
    initialTrack: number
    beforeItems: TimelineItem[]
    beforeTracksCount: number
  } | null>(null)

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

  const [editingSegmentId, setEditingSegmentId] = useState<string | null>(null)
  const [editingText, setEditingText] = useState("")
  const [editedSubtitleTextById, setEditedSubtitleTextById] = useState<Record<string, string>>({})

  const previewAspectClass =
    ratio === "9:16" ? "aspect-[9/16]" : ratio === "1:1" ? "aspect-square" : "aspect-video"

  const fullVideoUrl = trimContext?.video_url || null
  const clipStart = clip?.start_time ?? 0
  const clipEnd = clip?.end_time ?? 0
  const clipDuration = Math.max(0, clipEnd - clipStart)

  const segmentKey = (seg: TranscriptSegment) => `subtitle-${seg.start}-${seg.end}`

  const clipSegments = useMemo(() => {
    if (!Number.isFinite(clipStart) || !Number.isFinite(clipEnd) || clipEnd <= clipStart) return []
    return segments.filter((s) => {
      const s0 = Number(s.start)
      const s1 = Number(s.end)
      if (!Number.isFinite(s0) || !Number.isFinite(s1)) return false
      return s1 >= clipStart && s0 <= clipEnd
    })
  }, [clipEnd, clipStart, segments])

  const filteredSegments = useMemo(() => {
    const q = search.trim().toLowerCase()
    if (!q) return clipSegments
    return clipSegments.filter((s) => (s.text || "").toLowerCase().includes(q))
  }, [clipSegments, search])

  const leftPanelSegments = isTabTranscript ? clipSegments : filteredSegments

  const startEditingSegment = (segmentId: string, currentText: string) => {
    setEditingSegmentId(segmentId)
    setEditingText(currentText)
  }

  const commitEditingSegment = () => {
    if (!editingSegmentId) return
    const next = editingText

    setEditedSubtitleTextById((prev) => ({ ...prev, [editingSegmentId]: next }))
    setTimelineItems((prev) => prev.map((it) => (it.id === editingSegmentId && it.type === "subtitle" ? { ...it, text: next } : it)))

    setEditingSegmentId(null)
  }

  const cancelEditingSegment = () => {
    setEditingSegmentId(null)
  }

  useEffect(() => {
    if (!Number.isFinite(clipStart) || !Number.isFinite(clipEnd) || clipEnd <= clipStart) {
      setTimelineItems([])
      setTracksCount(2)
      return
    }

    const videoItem: TimelineItem = {
      id: "video-main",
      type: "video" as const,
      label: "Video",
      start: 0,
      end: clipDuration,
      track: 0,
    }

    const subtitleSegs: TimelineItem[] = (clipSegments || [])
      .filter((s) => Number.isFinite(s.start) && Number.isFinite(s.end))
      .map((s) => {
        const startRel = Math.max(0, (s.start ?? 0) - clipStart)
        const endRel = Math.min(clipDuration, (s.end ?? 0) - clipStart)
        const segmentId = segmentKey(s)
        const editedText = editedSubtitleTextById[segmentId]
        return {
          id: segmentId,
          type: "subtitle" as const,
          label: "Legenda",
          start: Math.max(0, Math.min(startRel, clipDuration)),
          end: Math.max(0, Math.min(endRel, clipDuration)),
          text: (editedText ?? s.text) || "",
          track: 1,
        } satisfies TimelineItem
      })
      .filter((it) => it.end > it.start)

    setTimelineItems([videoItem, ...subtitleSegs])
    setTracksCount((prev) => Math.max(prev, 2))
  }, [clipDuration, clipEnd, clipStart, clipSegments, editedSubtitleTextById])

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

  const handleSeek = (time: number) => {
    const el = previewVideoRef.current
    if (!el) return
    const newTime = Math.max(clipStart, Math.min(clipEnd, time))
    el.currentTime = newTime
    setRelativeTime(newTime - clipStart)
  }

  const handleTimelinePointerDown = (e: import("react").PointerEvent) => {
    const container = timelineContainerRef.current
    if (!container) return

    e.preventDefault()
    e.stopPropagation()

    const rect = container.getBoundingClientRect()
    const clickX = e.clientX - rect.left
    const pct = clickX / rect.width
    const newTime = clipStart + pct * clipDuration

    handleSeek(newTime)
    setIsSeeking(true)

    timelineDragRef.current = {
      active: true,
      startX: e.clientX,
      startTime: newTime,
    }

    try {
      ; (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId)
    } catch { }
  }

  const pxToSeconds = (dxPx: number) => {
    const container = timelineContainerRef.current
    if (!container) return 0
    const rect = container.getBoundingClientRect()
    if (!rect.width || clipDuration <= 0) return 0
    return (dxPx / rect.width) * clipDuration
  }

  const clampTime = (t: number) => {
    if (!Number.isFinite(t)) return 0
    return Math.max(0, Math.min(clipDuration, t))
  }

  const startTimelineItemDrag = (
    e: import("react").PointerEvent,
    itemId: string,
    mode: "move" | "trim-start" | "trim-end"
  ) => {
    if (e.button !== 0) return
    e.preventDefault()
    e.stopPropagation()

    const item = timelineItems.find((it) => it.id === itemId)
    if (!item) return

    setSelectedTimelineItemId(itemId)

    timelineItemDragRef.current = {
      active: true,
      itemId,
      mode,
      startClientX: e.clientX,
      startClientY: e.clientY,
      initialStart: item.start,
      initialEnd: item.end,
      initialTrack: item.track,
      beforeItems: timelineItems.map((x) => ({ ...x })),
      beforeTracksCount: tracksCount,
    }

    try {
      ; (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId)
    } catch {
      // ignore
    }
  }

  useEffect(() => {
    const onMove = (e: PointerEvent) => {
      const drag = timelineItemDragRef.current
      if (!drag?.active) return
      if (clipDuration <= 0) return

      const deltaS = pxToSeconds(e.clientX - drag.startClientX)

      const dy = e.clientY - drag.startClientY
      const trackStepPx = 44
      let targetTrack = drag.initialTrack
      if (Math.abs(dy) >= trackStepPx / 2) {
        const steps = Math.round(dy / trackStepPx)
        targetTrack = drag.initialTrack + steps
        if (targetTrack < 0) targetTrack = 0
      }

      if (targetTrack >= tracksCount) {
        setTracksCount(targetTrack + 1)
      }

      setTimelineItems((prev) => {
        const idx = prev.findIndex((it) => it.id === drag.itemId)
        if (idx < 0) return prev

        const it = prev[idx]
        const minLen = 0.2

        let nextStart = drag.initialStart
        let nextEnd = drag.initialEnd

        if (drag.mode === "move") {
          const len = drag.initialEnd - drag.initialStart
          nextStart = clampTime(drag.initialStart + deltaS)
          nextEnd = clampTime(nextStart + len)
          if (nextEnd - nextStart < len) {
            nextStart = clampTime(nextEnd - len)
          }
        }

        if (drag.mode === "trim-start") {
          nextStart = clampTime(drag.initialStart + deltaS)
          nextStart = Math.min(nextStart, drag.initialEnd - minLen)
        }

        if (drag.mode === "trim-end") {
          nextEnd = clampTime(drag.initialEnd + deltaS)
          nextEnd = Math.max(nextEnd, drag.initialStart + minLen)
        }

        const overlaps = (aStart: number, aEnd: number, bStart: number, bEnd: number) => {
          return aStart < bEnd && aEnd > bStart
        }

        const othersOnTargetTrack = prev.filter((x) => x.id !== it.id && x.track === targetTrack)

        if (drag.mode === "move") {
          const overlapItem = othersOnTargetTrack.find((o) => overlaps(nextStart, nextEnd, o.start, o.end))
          if (overlapItem) {
            targetTrack = overlapItem.track + 1
            if (targetTrack >= tracksCount) {
              setTracksCount(targetTrack + 1)
            }
          }
        }

        const othersSameTrack = prev.filter((x) => x.id !== it.id && x.track === targetTrack)

        if (drag.mode === "trim-start") {
          const blockers = othersSameTrack.filter((o) => overlaps(nextStart, nextEnd, o.start, o.end))
          if (blockers.length) {
            const maxEnd = Math.max(...blockers.map((b) => b.end))
            nextStart = Math.min(Math.max(nextStart, maxEnd), nextEnd - minLen)
          }
        }

        if (drag.mode === "trim-end") {
          const blockers = othersSameTrack.filter((o) => overlaps(nextStart, nextEnd, o.start, o.end))
          if (blockers.length) {
            const minStart = Math.min(...blockers.map((b) => b.start))
            nextEnd = Math.max(Math.min(nextEnd, minStart), nextStart + minLen)
          }
        }

        if (drag.mode === "move") {
          const len = drag.initialEnd - drag.initialStart
          let guard = 0
          while (guard < 10) {
            const blocker = othersSameTrack.find((o) => overlaps(nextStart, nextEnd, o.start, o.end))
            if (!blocker) break

            if (deltaS >= 0) {
              nextStart = clampTime(blocker.start - len)
            } else {
              nextStart = clampTime(blocker.end)
            }
            nextEnd = clampTime(nextStart + len)
            if (nextEnd - nextStart < len) {
              nextStart = clampTime(nextEnd - len)
            }
            guard += 1
          }
        }

        const nextItem = { ...it, start: nextStart, end: nextEnd, track: targetTrack }
        const out = prev.slice()
        out[idx] = nextItem
        return out
      })
    }

    const onUp = () => {
      const drag = timelineItemDragRef.current
      if (drag) {
        drag.active = false

        const undoState = historyRef.current.undo
        undoState.push({ items: drag.beforeItems, tracksCount: drag.beforeTracksCount })
        historyRef.current.redo = []
      }
      timelineItemDragRef.current = null
    }

    window.addEventListener("pointermove", onMove)
    window.addEventListener("pointerup", onUp)
    return () => {
      window.removeEventListener("pointermove", onMove)
      window.removeEventListener("pointerup", onUp)
    }
  }, [clipDuration])

  const handleUndo = () => {
    const prev = historyRef.current.undo.pop()
    if (!prev) return
    historyRef.current.redo.push({ items: timelineItems.map((x) => ({ ...x })), tracksCount })
    setTimelineItems(prev.items)
    setTracksCount(prev.tracksCount)
    setSelectedTimelineItemId(null)
  }

  const handleRedo = () => {
    const next = historyRef.current.redo.pop()
    if (!next) return
    historyRef.current.undo.push({ items: timelineItems.map((x) => ({ ...x })), tracksCount })
    setTimelineItems(next.items)
    setTracksCount(next.tracksCount)
    setSelectedTimelineItemId(null)
  }

  const selectedSubtitleItem = useMemo(() => {
    if (!selectedTimelineItemId) return null
    const it = timelineItems.find((s) => s.id === selectedTimelineItemId)
    return it && it.type === "subtitle" ? it : null
  }, [selectedTimelineItemId, timelineItems])

  const activeSubtitlesForPreview = useMemo(() => {
    const t = relativeTime
    return timelineItems
      .filter((it) => it.type === "subtitle" && t >= it.start && t <= it.end)
      .sort((a, b) => a.track - b.track)
  }, [relativeTime, timelineItems])

  const startSubtitleOverlayDrag = (e: import("react").PointerEvent) => {
    if (!activeSubtitlesForPreview.length) return
    if (e.button !== 0) return
    const container = previewContainerRef.current
    if (!container) return
    e.preventDefault()
    e.stopPropagation()

    subtitleDragRef.current = {
      active: true,
      startX: e.clientX,
      startY: e.clientY,
      posX: subtitleOverlayPos.x,
      posY: subtitleOverlayPos.y,
    }
  }

  const handleSplitSelected = () => {
    if (!selectedTimelineItemId) return
    if (clipDuration <= 0) return

    setTimelineItems((prev) => {
      const idx = prev.findIndex((p) => p.id === selectedTimelineItemId)
      if (idx < 0) return prev

      const it = prev[idx]
      const activeDrag = timelineDragRef.current
      const tRaw = activeDrag?.active
        ? (activeDrag.startTime ?? clipStart) - clipStart
        : relativeTime
      const tSnapped = Math.round(tRaw * 100) / 100
      const t = Math.max(0, Math.min(clipDuration, tSnapped))
      const minLen = 0.2

      if (t <= it.start + minLen) return prev
      if (t >= it.end - minLen) return prev

      historyRef.current.undo.push({ items: prev.map((x) => ({ ...x })), tracksCount })
      historyRef.current.redo = []

      const left: TimelineItem = {
        ...it,
        end: t,
      }
      const right: TimelineItem = {
        ...it,
        id: `${it.id}-split-${Math.floor(t * 1000)}`,
        start: t,
      }

      const out = prev.slice()
      out.splice(idx, 1, left, right)
      return out
    })
  }

  useEffect(() => {
    if (!selectedSubtitleItem) return

    const onPointerDown = (e: PointerEvent) => {
      const target = e.target as Node | null
      if (!target) return

      const cfg = subtitleConfigRef.current
      if (cfg && cfg.contains(target)) return

      const overlay = subtitleOverlayElRef.current
      if (overlay && overlay.contains(target)) return

      setSelectedTimelineItemId(null)
    }

    window.addEventListener("pointerdown", onPointerDown, true)
    return () => window.removeEventListener("pointerdown", onPointerDown, true)
  }, [selectedSubtitleItem])

  useEffect(() => {
    if (!isPreviewSelected) return

    const onPointerDown = (e: PointerEvent) => {
      const target = e.target as Node | null
      if (!target) return

      const videoEl = previewVideoRef.current
      if (videoEl && videoEl.contains(target)) return

      const cropOverlay = cropOverlayRef.current
      if (cropOverlay && cropOverlay.contains(target)) return

      setIsPreviewSelected(false)
    }

    window.addEventListener("pointerdown", onPointerDown, true)
    return () => window.removeEventListener("pointerdown", onPointerDown, true)
  }, [isPreviewSelected])

  const handleCyclePlaybackRate = () => {
    const rates: Array<0.5 | 0.75 | 1 | 1.25 | 1.5 | 2> = [0.5, 0.75, 1, 1.25, 1.5, 2]
    const idx = rates.indexOf(playbackRate)
    const next = rates[(idx + 1) % rates.length]
    setPlaybackRate(next)
  }

  useEffect(() => {
    const onMove = (e: PointerEvent) => {
      const container = previewContainerRef.current
      const drag = subtitleDragRef.current
      if (!container || !drag?.active) return

      const rect = container.getBoundingClientRect()
      const dx = e.clientX - drag.startX
      const dy = e.clientY - drag.startY

      const dxPct = rect.width > 0 ? (dx / rect.width) * 100 : 0
      const dyPct = rect.height > 0 ? (dy / rect.height) * 100 : 0

      const clamp = (v: number, min: number, max: number) => Math.max(min, Math.min(max, v))
      setSubtitleOverlayPos({
        x: clamp(drag.posX + dxPct, 0, 100),
        y: clamp(drag.posY + dyPct, 0, 100),
      })
    }

    const onUp = () => {
      if (subtitleDragRef.current) subtitleDragRef.current.active = false
      subtitleDragRef.current = null
    }

    window.addEventListener("pointermove", onMove)
    window.addEventListener("pointerup", onUp)
    return () => {
      window.removeEventListener("pointermove", onMove)
      window.removeEventListener("pointerup", onUp)
    }
  }, [subtitleOverlayPos.x, subtitleOverlayPos.y, selectedSubtitleItem])

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
          <LeftPanel
            activeTab={activeTab}
            onActiveTabChange={setActiveTab as any}
            subtitleMode={subtitleMode}
            onSubtitleModeChange={setSubtitleMode as any}
            search={search}
            onSearchChange={setSearch}
            showLeftTopFade={showLeftTopFade}
            showLeftBottomFade={showLeftBottomFade}
            leftScrollRef={leftScrollRef}
            isTabTranscript={isTabTranscript}
            clipSegments={clipSegments}
            filteredSegments={filteredSegments}
            leftPanelSegments={leftPanelSegments}
            editedSubtitleTextById={editedSubtitleTextById}
            editingSegmentId={editingSegmentId}
            editingText={editingText}
            onEditingTextChange={setEditingText}
            segmentKey={segmentKey}
            startEditingSegment={startEditingSegment}
            commitEditingSegment={commitEditingSegment}
            cancelEditingSegment={cancelEditingSegment}
            formatTimeLabel={formatTimeLabel}
            formatTimeRangeLabel={formatTimeRangeLabel}
          />

          <PreviewArea
            previewAspectClass={previewAspectClass}
            previewContainerRef={previewContainerRef}
            previewVideoRef={previewVideoRef}
            cropOverlayRef={cropOverlayRef}
            subtitleOverlayElRef={subtitleOverlayElRef}
            isPreviewSelected={isPreviewSelected}
            onTogglePreviewSelected={() => setIsPreviewSelected((v) => !v)}
            fullVideoUrl={fullVideoUrl}
            rotation={rotation}
            ratio={ratio}
            videoPan={videoPan}
            cropRect={cropRect}
            onVideoPointerDown={onVideoPointerDown}
            onStartRotateDrag={startRotateDrag}
            onStartCropDrag={startCropDrag}
            activeSubtitlesForPreview={activeSubtitlesForPreview}
            subtitleOverlayPos={subtitleOverlayPos}
            subtitleStyle={subtitleStyle}
            onSelectSubtitle={(id) => setSelectedTimelineItemId(id)}
            onStartSubtitleOverlayDrag={startSubtitleOverlayDrag}
          />

          <SubtitleConfigPanel
            subtitleConfigRef={subtitleConfigRef}
            selectedSubtitleItem={selectedSubtitleItem}
            subtitleStyle={subtitleStyle}
            setSubtitleStyle={setSubtitleStyle}
            formatTimeRangeLabel={formatTimeRangeLabel}
          />
        </div>

        <TimelineTransportBar
          clipStart={clipStart}
          clipEnd={clipEnd}
          relativeTime={relativeTime}
          isPlaying={isPlaying}
          playbackRate={playbackRate}
          showTimeline={showTimeline}
          formatTimeRangeLabel={formatTimeRangeLabel}
          onTogglePlay={handleTogglePlay}
          onCyclePlaybackRate={handleCyclePlaybackRate}
          onSplit={handleSplitSelected}
          onToggleTimeline={() => setShowTimeline((v) => !v)}
          onUndo={handleUndo}
          onRedo={handleRedo}
        />

        <TimelineArea
          showTimeline={showTimeline}
          clipDuration={clipDuration}
          relativeTime={relativeTime}
          showTimelineLeftFade={showTimelineLeftFade}
          showTimelineRightFade={showTimelineRightFade}
          timelineContainerRef={timelineContainerRef}
          timelineScrollRef={timelineScrollRef}
          onTimelinePointerDown={handleTimelinePointerDown}
          formatTimeLabel={formatTimeLabel}
          tracksCount={tracksCount}
          timelineItems={timelineItems}
          selectedTimelineItemId={selectedTimelineItemId}
          startTimelineItemDrag={startTimelineItemDrag}
        />
      </div>
    </div>
  )
}
