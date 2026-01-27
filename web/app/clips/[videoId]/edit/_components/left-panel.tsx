"use client"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { HugeiconsIcon } from "@hugeicons/react"
import {
  ChatTranslate01Icon,
  ClosedCaptionFreeIcons,
  Copy02Icon,
  DownloadSquare01Icon,
  Settings05Icon,
  TextAlignJustifyCenterIcon,
} from "@hugeicons/core-free-icons"
import type { RefObject } from "react"

import type { TranscriptSegment } from "@/infra/videos/videos"

interface LeftPanelProps {
  activeTab: "Transcrição" | "Editar Subtítulos"
  onActiveTabChange: (v: "Transcrição" | "Editar Subtítulos") => void
  subtitleMode: "Paragraph" | "Sentence"
  onSubtitleModeChange: (v: "Paragraph" | "Sentence") => void

  search: string
  onSearchChange: (next: string) => void

  showLeftTopFade: boolean
  showLeftBottomFade: boolean
  leftScrollRef: RefObject<HTMLDivElement | null>

  isTabTranscript: boolean
  clipSegments: TranscriptSegment[]
  filteredSegments: TranscriptSegment[]
  leftPanelSegments: TranscriptSegment[]

  editedSubtitleTextById: Record<string, string>
  editingSegmentId: string | null
  editingText: string
  onEditingTextChange: (next: string) => void

  segmentKey: (seg: TranscriptSegment) => string
  startEditingSegment: (segmentId: string, currentText: string) => void
  commitEditingSegment: () => void
  cancelEditingSegment: () => void

  formatTimeLabel: (seconds: number) => string
  formatTimeRangeLabel: (seconds: number) => string
}

export function LeftPanel({
  activeTab,
  onActiveTabChange,
  subtitleMode,
  onSubtitleModeChange,
  search,
  onSearchChange,
  showLeftTopFade,
  showLeftBottomFade,
  leftScrollRef,
  isTabTranscript,
  clipSegments,
  filteredSegments,
  leftPanelSegments,
  editedSubtitleTextById,
  editingSegmentId,
  editingText,
  onEditingTextChange,
  segmentKey,
  startEditingSegment,
  commitEditingSegment,
  cancelEditingSegment,
  formatTimeLabel,
  formatTimeRangeLabel,
}: LeftPanelProps) {
  return (
    <div className="overflow-hidden w-1/3 flex flex-col min-h-0">
      <div className="p-3 shrink-0">
        <Tabs value={activeTab} onValueChange={(v) => onActiveTabChange(v as any)}>
          <TabsList className="w-full h-10" variant="default">
            <TabsTrigger value="Transcrição">Transcrição</TabsTrigger>
            <TabsTrigger value="Editar Subtítulos">Editar Subtítulos</TabsTrigger>
          </TabsList>

          <TabsContent value="Transcrição" className="flex mt-3 items-center justify-center gap-2">
            <div className="flex-1">
              <Input value={search} onChange={(e) => onSearchChange(e.target.value)} placeholder="Search" className="h-10" />
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
                <Input value={search} onChange={(e) => onSearchChange(e.target.value)} placeholder="Search" className="h-10" />
              </div>

              <Tabs value={subtitleMode} onValueChange={(v) => onSubtitleModeChange(v as any)}>
                <TabsList variant="default" className="h-10">
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
              clipSegments.length === 0 ? (
                <div className="text-sm text-muted-foreground py-10 text-center">Nenhum trecho encontrado.</div>
              ) : (
                <div className="divide-y divide-border">
                  {(search.trim() ? filteredSegments : clipSegments).map((seg, idx) => {
                    const segmentId = segmentKey(seg)
                    const textValue = editedSubtitleTextById[segmentId] ?? seg.text
                    const isEditing = editingSegmentId === segmentId
                    return (
                      <div key={`${seg.start}-${idx}`} className="py-3">
                        {isEditing ? (
                          <input
                            value={editingText}
                            onChange={(e) => onEditingTextChange(e.target.value)}
                            onBlur={commitEditingSegment}
                            onKeyDown={(e) => {
                              if (e.key === "Enter") commitEditingSegment()
                              if (e.key === "Escape") cancelEditingSegment()
                            }}
                            className="h-auto w-fit"
                            autoFocus
                          />
                        ) : (
                          <div
                            className="text-sm text-foreground/90 leading-relaxed"
                            onDoubleClick={() => startEditingSegment(segmentId, textValue || "")}
                          >
                            {textValue}
                          </div>
                        )}
                      </div>
                    )
                  })}
                </div>
              )
            ) : leftPanelSegments.length === 0 ? (
              <div className="text-sm text-muted-foreground py-10 text-center">Nenhum trecho encontrado.</div>
            ) : subtitleMode === "Sentence" ? (
              <div className="divide-y divide-border">
                {leftPanelSegments.map((seg, idx) => {
                  const segmentId = segmentKey(seg)
                  const textValue = editedSubtitleTextById[segmentId] ?? seg.text
                  const isEditing = editingSegmentId === segmentId
                  return (
                    <div key={`${seg.start}-${idx}`} className="py-3">
                      <div className="flex items-start justify-between gap-3">
                        <div className="w-28 shrink-0 text-xs tabular-nums text-muted-foreground pt-0.5">
                          {formatTimeRangeLabel(seg.start)} - {formatTimeRangeLabel(seg.end)}
                        </div>
                        <div className="flex-1">
                          {isEditing ? (
                            <Input
                              value={editingText}
                              onChange={(e) => onEditingTextChange(e.target.value)}
                              onBlur={commitEditingSegment}
                              onKeyDown={(e) => {
                                if (e.key === "Enter") commitEditingSegment()
                                if (e.key === "Escape") cancelEditingSegment()
                              }}
                              className="h-10"
                              autoFocus
                            />
                          ) : (
                            <div
                              className="text-sm text-foreground/90 leading-relaxed"
                              onDoubleClick={() => startEditingSegment(segmentId, textValue || "")}
                            >
                              {textValue}
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>
            ) : (
              <div className="divide-y divide-border">
                {leftPanelSegments.map((seg, idx) => {
                  const segmentId = segmentKey(seg)
                  const textValue = editedSubtitleTextById[segmentId] ?? seg.text
                  const isEditing = editingSegmentId === segmentId
                  return (
                    <div key={`${seg.start}-${idx}`} className="py-3">
                      <div className="flex items-start gap-3">
                        <div className="w-16 shrink-0 text-xs tabular-nums text-muted-foreground pt-0.5">{formatTimeLabel(seg.start)}</div>
                        <div className="flex-1">
                          {isEditing ? (
                            <Input
                              value={editingText}
                              onChange={(e) => onEditingTextChange(e.target.value)}
                              onBlur={commitEditingSegment}
                              onKeyDown={(e) => {
                                if (e.key === "Enter") commitEditingSegment()
                                if (e.key === "Escape") cancelEditingSegment()
                              }}
                              className="h-10"
                              autoFocus
                            />
                          ) : (
                            <div
                              className="text-sm text-foreground/90 leading-relaxed"
                              onDoubleClick={() => startEditingSegment(segmentId, textValue || "")}
                            >
                              {textValue}
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        </ScrollArea>
      </div>
    </div>
  )
}
