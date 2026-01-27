"use client"

import type { Dispatch, RefObject, SetStateAction } from "react"

import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"

interface SubtitleStyle {
  fontFamily: string
  color: string
  shadow: boolean
}

interface SubtitleItem {
  id: string
  start: number
  end: number
}

interface SubtitleConfigPanelProps {
  subtitleConfigRef: RefObject<HTMLDivElement | null>
  selectedSubtitleItem: SubtitleItem | null
  subtitleStyle: SubtitleStyle
  setSubtitleStyle: Dispatch<SetStateAction<SubtitleStyle>>
  formatTimeRangeLabel: (seconds: number) => string
}

export function SubtitleConfigPanel({
  subtitleConfigRef,
  selectedSubtitleItem,
  subtitleStyle,
  setSubtitleStyle,
  formatTimeRangeLabel,
}: SubtitleConfigPanelProps) {
  return (
    <div className="overflow-hidden p-2 w-[280px]">
      {selectedSubtitleItem ? (
        <div ref={subtitleConfigRef} className="w-full rounded-lg bg-background p-3">
          <div className="text-sm font-medium mb-3">Legenda</div>

          <div className="space-y-3">
            <div className="space-y-1">
              <div className="text-xs text-muted-foreground">Fonte</div>
              <Select
                value={subtitleStyle.fontFamily}
                onValueChange={(v) => setSubtitleStyle((s) => ({ ...s, fontFamily: v ?? s.fontFamily }))}
              >
                <SelectTrigger className="h-9">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="Montserrat ExtraBold">Montserrat ExtraBold</SelectItem>
                  <SelectItem value="Montserrat">Montserrat</SelectItem>
                  <SelectItem value="Inter">Inter</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-1">
              <div className="text-xs text-muted-foreground">Cor</div>
              <Input
                value={subtitleStyle.color}
                onChange={(e) => setSubtitleStyle((s) => ({ ...s, color: e.target.value }))}
                className="h-9"
                placeholder="#FFFFFF"
              />
            </div>

            <button
              type="button"
              className={
                "h-9 w-full rounded-md border border-border text-sm " +
                (subtitleStyle.shadow ? "bg-accent" : "bg-transparent hover:bg-accent")
              }
              onClick={() => setSubtitleStyle((s) => ({ ...s, shadow: !s.shadow }))}
            >
              Sombra: {subtitleStyle.shadow ? "On" : "Off"}
            </button>

            <div className="text-xs text-muted-foreground">
              {formatTimeRangeLabel(selectedSubtitleItem.start)} - {formatTimeRangeLabel(selectedSubtitleItem.end)}
            </div>
          </div>
        </div>
      ) : null}
    </div>
  )
}
