"use client"

import { Button } from "@/components/ui/button"
import { HugeiconsIcon } from "@hugeicons/react"
import { ArrowDown03Icon, ScissorIcon } from "@hugeicons/core-free-icons"
import { Pause, Play, Redo2, Undo2 } from "lucide-react"

interface TimelineTransportBarProps {
  clipStart: number
  clipEnd: number
  relativeTime: number
  isPlaying: boolean
  playbackRate: 0.5 | 0.75 | 1 | 1.25 | 1.5 | 2
  showTimeline: boolean

  formatTimeRangeLabel: (seconds: number) => string
  onTogglePlay: () => void
  onCyclePlaybackRate: () => void
  onSplit: () => void
  onToggleTimeline: () => void
  onUndo: () => void
  onRedo: () => void
}

export function TimelineTransportBar({
  clipStart,
  clipEnd,
  relativeTime,
  isPlaying,
  playbackRate,
  showTimeline,
  formatTimeRangeLabel,
  onTogglePlay,
  onCyclePlaybackRate,
  onSplit,
  onToggleTimeline,
  onUndo,
  onRedo,
}: TimelineTransportBarProps) {
  return (
    <div className="shrink-0 px-6">
      <div className="h-12 grid grid-cols-3 items-center">
        <div className="flex items-center gap-2" />

        <div className="flex items-center justify-center gap-3">
          <span className="text-xs tabular-nums text-muted-foreground">{formatTimeRangeLabel(clipStart + relativeTime)}</span>
          <button
            type="button"
            onClick={onTogglePlay}
            className="h-8 w-8 inline-flex items-center justify-center rounded-full bg-accent"
          >
            {isPlaying ? <Pause className="size-4 fill-foreground" /> : <Play className="size-4 fill-foreground" />}
          </button>
          <span className="text-xs tabular-nums text-muted-foreground">{formatTimeRangeLabel(clipEnd)}</span>
        </div>

        <div className="flex items-center justify-end gap-3">
          <button
            type="button"
            onClick={onUndo}
            className="h-8 w-8 inline-flex items-center justify-center rounded-md hover:bg-accent"
            title="Voltar"
          >
            <Undo2 className="size-4" />
          </button>

          <button
            type="button"
            onClick={onRedo}
            className="h-8 w-8 inline-flex items-center justify-center rounded-md hover:bg-accent"
            title="Avançar"
          >
            <Redo2 className="size-4" />
          </button>

          <Button
            onClick={onCyclePlaybackRate}
            className="h-8 px-2 rounded-md bg-transparent text-sm hover:bg-accent"
            title="Velocidade"
          >
            {playbackRate}x
          </Button>

          <button
            type="button"
            onClick={onSplit}
            className="h-8 w-8 inline-flex items-center justify-center rounded-md hover:bg-accent"
            title="Split"
          >
            <HugeiconsIcon icon={ScissorIcon} size={18} />
          </button>

          <button
            type="button"
            onClick={onToggleTimeline}
            className="h-8 w-8 inline-flex items-center justify-center rounded-md hover:bg-accent"
            title={showTimeline ? "Fechar" : "Abrir"}
          >
            <HugeiconsIcon icon={ArrowDown03Icon} />
          </button>
        </div>
      </div>
    </div>
  )
}
