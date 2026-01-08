"use client"

import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { Separator } from "@/components/ui/separator"
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { Select, SelectTrigger, SelectContent, SelectItem } from "@/components/ui/select"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Progress } from "@/components/ui/progress"
import { HugeiconsIcon } from "@hugeicons/react"
import { Download01Icon, Share03Icon, SentIcon, GlobeIcon, LockIcon, PlayIcon, PauseIcon } from "@hugeicons/core-free-icons"
import { useEffect, useRef, useState } from "react"
import { ClipActions } from "./clip-actions"
import type { Clip } from "@/infra/videos/videos"

interface ClipCardProps {
  clip: Clip
  videoId: string
  idx: number
  selectedClips: string[]
  onToggleSelection: (clipId: string) => void
  onDownload: (clipId: string) => void
  onPublish: () => void
  onRename: (clipId: string, title: string) => void
  onDuplicate: (clipId: string) => void
  onDelete: (clipId: string) => void
  shareValue: "public" | "private"
  onShareValueChange: (value: "public" | "private") => void
  isShareDialogOpen: boolean
  shareClipId: string | null
  onOpenShareDialog: (clipId: string) => void
  onShareDialogOpenChange: (open: boolean) => void
}

export function ClipCard({
  clip,
  videoId,
  idx,
  selectedClips,
  onToggleSelection,
  onDownload,
  onPublish,
  onRename,
  onDuplicate,
  onDelete,
  shareValue,
  onShareValueChange,
  isShareDialogOpen,
  shareClipId,
  onOpenShareDialog,
  onShareDialogOpenChange,
}: ClipCardProps) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const [isPlaying, setIsPlaying] = useState(false)

  const [currentTime, setCurrentTime] = useState(0)
  const [videoDuration, setVideoDuration] = useState(0)
  const [videoHeight, setVideoHeight] = useState<number | null>(null)

  const transcriptScrollRef = useRef<HTMLDivElement>(null)
  const [showTranscriptTopFade, setShowTranscriptTopFade] = useState(false)
  const [showTranscriptBottomFade, setShowTranscriptBottomFade] = useState(false)

  useEffect(() => {
    const scrollElement = transcriptScrollRef.current?.querySelector(
      "[data-radix-scroll-area-viewport]",
    ) as HTMLDivElement | null

    if (!scrollElement) return

    const handleScroll = () => {
      const { scrollTop, scrollHeight, clientHeight } = scrollElement
      setShowTranscriptTopFade(scrollTop > 0)
      setShowTranscriptBottomFade(scrollTop + clientHeight < scrollHeight - 1)
    }

    handleScroll()
    scrollElement.addEventListener("scroll", handleScroll)
    return () => scrollElement.removeEventListener("scroll", handleScroll)
  }, [clip.transcript])

  const formatDuration = (seconds: number) => {
    if (!Number.isFinite(seconds) || seconds < 0) return null
    const totalSeconds = Math.round(seconds)
    const mins = Math.floor(totalSeconds / 60)
    const secs = totalSeconds % 60
    return mins > 0 ? `${mins}:${secs.toString().padStart(2, "0")}` : `${secs}s`
  }

  const formatTimeLabel = (seconds: number) => {
    if (!Number.isFinite(seconds) || seconds < 0) return "00:00"
    const totalSeconds = Math.floor(seconds)
    const mins = Math.floor(totalSeconds / 60)
    const secs = totalSeconds % 60
    return `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`
  }

  const clipDurationSeconds =
    typeof (clip as any).duration === "number"
      ? (clip as any).duration
      : typeof (clip as any).start_time === "number" && typeof (clip as any).end_time === "number"
        ? (clip as any).end_time - (clip as any).start_time
        : null

  const clipDurationLabel = clipDurationSeconds !== null ? formatDuration(clipDurationSeconds) : null

  const togglePlayPause = () => {
    if (videoRef.current) {
      if (isPlaying) {
        videoRef.current.pause()
      } else {
        window.dispatchEvent(new CustomEvent("clip-video-play", { detail: { clipId: clip.clip_id } }))
        videoRef.current.play()
      }
      setIsPlaying(!isPlaying)
    }
  }

  useEffect(() => {
    const video = videoRef.current
    if (!video) return

    const handleLoadedMetadata = () => {
      if (Number.isFinite(video.duration)) {
        setVideoDuration(video.duration)
      }
      if (Number.isFinite(video.videoHeight) && video.videoHeight > 0) {
        setVideoHeight(video.videoHeight)
      }
    }

    const handleTimeUpdate = () => {
      setCurrentTime(video.currentTime || 0)
      if (Number.isFinite(video.duration)) {
        setVideoDuration(video.duration)
      }
    }

    const handleEnded = () => {
      setIsPlaying(false)
    }

    const handleExternalPlay = (event: Event) => {
      const e = event as CustomEvent<{ clipId?: string }>
      if (e?.detail?.clipId && e.detail.clipId !== clip.clip_id) {
        if (videoRef.current && !videoRef.current.paused) {
          videoRef.current.pause()
        }
        setIsPlaying(false)
      }
    }

    video.addEventListener("loadedmetadata", handleLoadedMetadata)
    video.addEventListener("durationchange", handleLoadedMetadata)
    video.addEventListener("timeupdate", handleTimeUpdate)
    video.addEventListener("ended", handleEnded)
    window.addEventListener("clip-video-play", handleExternalPlay)

    handleLoadedMetadata()
    handleTimeUpdate()

    return () => {
      video.removeEventListener("loadedmetadata", handleLoadedMetadata)
      video.removeEventListener("durationchange", handleLoadedMetadata)
      video.removeEventListener("timeupdate", handleTimeUpdate)
      video.removeEventListener("ended", handleEnded)
      window.removeEventListener("clip-video-play", handleExternalPlay)
    }
  }, [clip.video_url])

  const qualityLabel = (() => {
    if (!videoHeight) return null
    if (videoHeight >= 1080) return "1080p"
    if (videoHeight >= 720) return "720p"
    if (videoHeight >= 480) return "480p"
    return `${videoHeight}p`
  })()

  return (
    <div id={`clip-${clip.clip_id}`} className="flex flex-col lg:flex-row gap-8 items-start group">
      {/* Left Column: Vertical Video Player */}
      <div className="shrink-0">
        <div className="relative w-[280px] aspect-[9/16] bg-card rounded-2xl overflow-hidden border border-zinc-800 group">
          <div className="absolute top-2 right-2 pointer-events-auto z-10">
            <Checkbox
              checked={selectedClips.includes(clip.clip_id)}
              onCheckedChange={() => onToggleSelection(clip.clip_id)}
            />
          </div>
          {clip.video_url ? (
            <>
              <video
                ref={videoRef}
                src={clip.video_url}
                className="w-full h-full object-cover"
                onPlay={() => setIsPlaying(true)}
                onPause={() => setIsPlaying(false)}
              />

              {qualityLabel ? (
                <div className="absolute top-2 left-2 z-10 rounded-md bg-black/60 px-2 py-1 text-[11px] font-medium text-white">
                  {qualityLabel}
                </div>
              ) : null}

              <button
                type="button"
                onClick={togglePlayPause}
                className="absolute inset-0"
                aria-label={isPlaying ? "Pause" : "Play"}
              />

              {!isPlaying ? (
                <button
                  type="button"
                  onClick={togglePlayPause}
                  className="absolute inset-0 z-10 flex items-center justify-center"
                  aria-label="Play"
                >
                  <div className="bg-background/90 backdrop-blur cursor-pointer rounded-full p-4">
                    <HugeiconsIcon icon={PlayIcon} size={32} className="text-primary" />
                  </div>
                </button>
              ) : null}

              {isPlaying ? (
                <div className="absolute bottom-0 left-0 right-0 z-20 px-3 py-2">
                  <div className="absolute inset-x-0 bottom-0 h-20 bg-gradient-to-t from-black/70 to-transparent" />

                  <div className="relative">
                    <div className="flex items-center gap-3">
                      <button
                        type="button"
                        onClick={togglePlayPause}
                        className="text-white"
                        aria-label={isPlaying ? "Pause" : "Play"}
                      >
                        <HugeiconsIcon icon={isPlaying ? PauseIcon : PlayIcon} size={16} />
                      </button>

                      <div className="flex items-center gap-0.5 text-white text-xs font-medium tabular-nums">
                        <span>{formatTimeLabel(currentTime)}</span>
                        <span>/</span>
                        <span>{formatTimeLabel(videoDuration || clipDurationSeconds || 0)}</span>
                      </div>
                    </div>

                    <div className="mt-2">
                      <Progress
                        className="w-full"
                        value={
                          videoDuration > 0
                            ? Math.max(0, Math.min(100, (currentTime / videoDuration) * 100))
                            : 0
                        }
                      />
                    </div>
                  </div>
                </div>
              ) : null}
            </>
          ) : (
            <div className="absolute inset-0 flex flex-col items-center justify-center text-zinc-700 bg-gradient-to-br from-zinc-800 to-zinc-900">
              <p className="text-xs text-zinc-600">Vídeo não disponível</p>
            </div>
          )}
        </div>
      </div>

      {/* Middle Column: Details */}
      <div className="flex-1 min-w-0 space-y-5 pt-2">
        {/* Header: ID + Title */}
        <div>
          <h3 className="text-lg font-medium text-zinc-100 flex items-start gap-2 leading-tight">
            <span className="text-primary font-bold">#{idx + 1}</span>
            {clip.title || "Redimensione vários elementos HTML com Copiar/Colar + IA!"}
          </h3>
        </div>

        {/* Stats & Primary Actions Row */}
        <div className="flex items-center flex-wrap gap-2">
          <div className="flex items-baseline gap-1">
            <span className="text-4xl font-bold text-white tracking-tighter">
              {clip.engagement_score !== undefined && clip.engagement_score !== null
                ? clip.engagement_score % 1 === 0
                  ? clip.engagement_score.toString()
                  : clip.engagement_score.toFixed(1)
                : "N/A"}
            </span>
            <span className="text-sm font-medium text-zinc-500">/10</span>
          </div>

          <div className="h-8 w-[1px] bg-muted mx-2 hidden sm:block"></div>

          <Button
            type="button"
            className="bg-primary text-white rounded-lg px-6 h-9 text-xs font-medium"
            onClick={onPublish}
          >
            <HugeiconsIcon icon={SentIcon} size={16} className="mr-2" />
            Publicar
          </Button>

          <Button
            variant="secondary"
            size="icon"
            className="h-9 w-9 rounded-lg bg-card text-foreground hover:text-white hover:bg-zinc-700"
            onClick={() => onDownload(clip.clip_id)}
          >
            <HugeiconsIcon icon={Download01Icon} size={16} />
          </Button>
          <Button
            variant="secondary"
            size="icon"
            className="h-9 w-9 rounded-lg bg-card text-foreground hover:text-white hover:bg-zinc-700"
            onClick={() => onOpenShareDialog(clip.clip_id)}
          >
            <HugeiconsIcon icon={Share03Icon} size={16} />
          </Button>
          {isShareDialogOpen && shareClipId === clip.clip_id ? (
            <Dialog open={isShareDialogOpen} onOpenChange={onShareDialogOpenChange}>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Compartilhe esse Projeto</DialogTitle>
                  <DialogDescription>
                    Anyone with the link can view
                  </DialogDescription>
                </DialogHeader>
                <div className="mt-4 w-full flex gap-2 justify-between items-center">
                  <Select value={shareValue} onValueChange={(v) => onShareValueChange(v as "public" | "private")}>
                    <SelectTrigger className="flex items-center gap-2 w-full">
                      {shareValue === "public" ? (
                        <div className="flex items-center justify-start gap-2">
                          <HugeiconsIcon icon={GlobeIcon} size={16} />
                          <span>Qualquer pessoa pode ver</span>
                        </div>
                      ) : (
                        <div className="flex items-center justify-start gap-2">
                          <HugeiconsIcon icon={LockIcon} size={16} />
                          <span>Somente você</span>
                        </div>
                      )}
                    </SelectTrigger>

                    <SelectContent>
                      <SelectItem value="public">Qualquer pessoa pode ver</SelectItem>
                      <SelectItem value="private">Somente você</SelectItem>
                    </SelectContent>
                  </Select>
                  <Button
                    variant="secondary"
                    className="ml-2 bg-foreground hover:bg-foreground/90 text-background"
                  >
                    Copy Link
                  </Button>
                </div>
                <div className="mt-4 flex items-center">
                  <Input type="email" placeholder="Enter email" className="flex-1" />
                  <Button variant="default" className="ml-2">
                    Invite
                  </Button>
                </div>
                <Separator />
                <div className="mt-4 pt-4 flex items-center justify-between">
                  <Avatar className="h-8 w-8">
                    <AvatarImage src="https://avatars.githubusercontent.com/u/142619236?v=4" alt="account" />
                    <AvatarFallback>SK</AvatarFallback>
                  </Avatar>
                  <div className="ml-3 flex-1">
                    <p className="text-sm font-medium">Rodrigo Carvalho</p>
                    <p className="text-xs text-muted-foreground">rodrigoa0987@gmail.com</p>
                  </div>
                  <span className="text-xs text-muted-foreground">Owner</span>
                </div>
              </DialogContent>
            </Dialog>
          ) : null}
        </div>

        {/* Transcript Text */}
        <div className="bg-transparent relative">
          {showTranscriptTopFade && (
            <div className="absolute top-0 left-0 right-0 h-20 bg-gradient-to-b from-background to-transparent z-10 pointer-events-none" />
          )}
          <ScrollArea ref={transcriptScrollRef}>
            <div className="pr-4 max-h-[380px] cursor-ns-resize">
              <p className="text-sm text-muted-foreground leading-7 text-justify">
                {clip.transcript || "Transcrição não disponível para este clip."}
              </p>
            </div>
          </ScrollArea>
          {showTranscriptBottomFade && (
            <div className="absolute bottom-0 left-0 right-0 h-20 bg-gradient-to-t from-background to-transparent z-10 pointer-events-none" />
          )}
        </div>
      </div>

      {/* Right Column: Floating Actions */}
      <ClipActions
        clip={clip}
        videoId={videoId}
        onRename={onRename}
        onDuplicate={onDuplicate}
        onDelete={onDelete}
      />
    </div>
  )
}
