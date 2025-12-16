"use client"

import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { Separator } from "@/components/ui/separator"
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { Select, SelectTrigger, SelectContent, SelectItem } from "@/components/ui/select"
import { HugeiconsIcon } from "@hugeicons/react"
import { Download01Icon, Share03Icon, SentIcon, GlobeIcon, LockIcon, PlayIcon, PauseIcon } from "@hugeicons/core-free-icons"
import { useRef, useState } from "react"
import { ClipActions } from "./clip-actions"
import type { Clip } from "@/infra/videos/videos"

interface ClipCardProps {
  clip: Clip
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
  onShareDialogOpenChange: (open: boolean) => void
}

export function ClipCard({
  clip,
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
  onShareDialogOpenChange,
}: ClipCardProps) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const [isPlaying, setIsPlaying] = useState(false)

  const togglePlayPause = () => {
    if (videoRef.current) {
      if (isPlaying) {
        videoRef.current.pause()
      } else {
        videoRef.current.play()
      }
      setIsPlaying(!isPlaying)
    }
  }

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
              <button
                onClick={togglePlayPause}
                className="absolute inset-0 flex items-center justify-center hover:bg-black/50 transition-colors hover:opacity-100 opacity-0 duration-700ms"
              >
                <div className="bg-background cursor-pointer rounded-full p-4 transition-colors duration-700ms">
                  <HugeiconsIcon
                    icon={isPlaying ? PauseIcon : PlayIcon}
                    size={32}
                    className="text-primary"
                  />
                </div>
              </button>
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
                ? (clip.engagement_score / 10).toFixed(1)
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
            onClick={() => onShareDialogOpenChange(true)}
          >
            <HugeiconsIcon icon={Share03Icon} size={16} />
          </Button>
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
                <Button variant="secondary" className="ml-2 bg-foreground hover:bg-foreground/90 text-background">Copy Link</Button>
              </div>
              <div className="mt-4 flex items-center">
                <Input type="email" placeholder="Enter email" className="flex-1" />
                <Button variant="default" className="ml-2">Invite</Button>
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
        </div>

        {/* Transcript Text */}
        <div className="bg-transparent">
          <p className="text-sm text-muted-foreground leading-7">
            {clip.transcript || "Transcrição não disponível para este clip."}
          </p>
        </div>
      </div>

      {/* Right Column: Floating Actions */}
      <ClipActions
        clip={clip}
        onRename={onRename}
        onDuplicate={onDuplicate}
        onDelete={onDelete}
      />
    </div>
  )
}
