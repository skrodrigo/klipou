"use client"

import type { RefObject } from "react"

import { ScrollArea } from "@/components/ui/scroll-area"
import { TimelineTracks } from "./timeline-tracks"

interface TimelineItem {
  id: string
  type: "video" | "subtitle"
  label: string
  start: number
  end: number
  text?: string
  track: number
}

interface TimelineAreaProps {
  showTimeline: boolean
  clipDuration: number
  relativeTime: number

  showTimelineLeftFade: boolean
  showTimelineRightFade: boolean

  timelineContainerRef: RefObject<HTMLDivElement | null>
  timelineScrollRef: RefObject<HTMLDivElement | null>

  onTimelinePointerDown: (e: import("react").PointerEvent) => void
  formatTimeLabel: (seconds: number) => string

  tracksCount: number
  timelineItems: TimelineItem[]
  selectedTimelineItemId: string | null
  startTimelineItemDrag: (e: import("react").PointerEvent, itemId: string, mode: "move" | "trim-start" | "trim-end") => void
}

export function TimelineArea({
  showTimeline,
  clipDuration,
  relativeTime,
  showTimelineLeftFade,
  showTimelineRightFade,
  timelineContainerRef,
  timelineScrollRef,
  onTimelinePointerDown,
  formatTimeLabel,
  tracksCount,
  timelineItems,
  selectedTimelineItemId,
  startTimelineItemDrag,
}: TimelineAreaProps) {
  return (
    <div className={showTimeline ? "shrink-0 max-h-[200px] min-h-[200px]" : "hidden"}>
      <div className="h-full px-4 py-4">
        <div
          ref={timelineContainerRef}
          className="relative h-full bg-background/20 overflow-hidden"
          onPointerDown={onTimelinePointerDown}
        >
          {showTimelineLeftFade ? (
            <div className="pointer-events-none absolute z-10 left-0 top-0 bottom-0 w-10 z-30 bg-gradient-to-r from-background/60 to-transparent" />
          ) : null}
          {showTimelineRightFade ? (
            <div className="pointer-events-none absolute z-10 right-0 top-0 bottom-0 w-10 z-30 bg-gradient-to-l from-background/60 to-transparent" />
          ) : null}

          <div
            className="absolute top-0 bottom-0 z-20 cursor-pointer"
            style={{
              left:
                clipDuration > 0
                  ? `${Math.min(Math.max(relativeTime / clipDuration, 0), 1) * 100}%`
                  : "0%",
            }}
            onPointerDown={onTimelinePointerDown}
          >
            <img
              src="/trim-cursor-editor.svg"
              alt="Playhead"
              className="h-full w-auto z-50 -translate-x-1/2 pointer-events-none select-none pl-[16px]"
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

              <TimelineTracks
                tracksCount={tracksCount}
                timelineItems={timelineItems}
                clipDuration={clipDuration}
                selectedTimelineItemId={selectedTimelineItemId}
                startTimelineItemDrag={startTimelineItemDrag}
                formatTimeLabel={formatTimeLabel}
              />
            </div>
          </ScrollArea>
        </div>
      </div>
    </div>
  )
}
