"use client"

interface TimelineItem {
  id: string
  type: "video" | "subtitle"
  label: string
  start: number
  end: number
  text?: string
  track: number
}

interface TimelineTracksProps {
  tracksCount: number
  timelineItems: TimelineItem[]
  clipDuration: number
  selectedTimelineItemId: string | null
  startTimelineItemDrag: (e: import("react").PointerEvent, itemId: string, mode: "move" | "trim-start" | "trim-end") => void
  formatTimeLabel: (seconds: number) => string
}

export function TimelineTracks({
  tracksCount,
  timelineItems,
  clipDuration,
  selectedTimelineItemId,
  startTimelineItemDrag,
  formatTimeLabel,
}: TimelineTracksProps) {
  return (
    <div className="px-2 py-2 space-y-2">
      {Array.from({ length: tracksCount }).map((_, trackIdx) => {
        const items = timelineItems.filter((it) => it.track === trackIdx)

        return (
          <div key={`track-${trackIdx}`} className="flex items-center gap-2">
            <div className="flex-1 h-10 relative rounded-md  bg-background/40">
              {items.map((it) => {
                const leftPct = clipDuration > 0 ? (it.start / clipDuration) * 100 : 0
                const widthPct =
                  clipDuration > 0 ? Math.max(1, ((it.end - it.start) / clipDuration) * 100) : 0
                const isSelected = selectedTimelineItemId === it.id
                const base = it.type === "video" ? "bg-[#7DD3FC]" : "bg-[#FFE46E]"
                const textColor = it.type === "video" ? "text-[#083344]" : "text-[#504720]"

                return (
                  <div
                    key={it.id}
                    className={
                      "absolute top-1 bottom-1 rounded-md border text-xs px-2 flex items-center gap-2 select-none " +
                      base +
                      (isSelected ? " border-foreground/40" : " border-border")
                    }
                    style={{ left: `${leftPct}%`, width: `${widthPct}%` }}
                    onPointerDown={(e) => startTimelineItemDrag(e, it.id, "move")}
                  >
                    <div
                      className="absolute left-0 top-0 bottom-0 w-2 cursor-ew-resize"
                      onPointerDown={(e) => startTimelineItemDrag(e, it.id, "trim-start")}
                    />
                    <div
                      className="absolute right-0 top-0 bottom-0 w-2 cursor-ew-resize"
                      onPointerDown={(e) => startTimelineItemDrag(e, it.id, "trim-end")}
                    />

                    <span className={"text-[10px] tabular-nums shrink-0 " + textColor}>{formatTimeLabel(it.start)}</span>
                    <span className={"truncate " + textColor}>{it.type === "video" ? "Video" : it.text || "Legenda"}</span>
                  </div>
                )
              })}
            </div>
          </div>
        )
      })}
    </div>
  )
}
