"use client"

import type { RefObject } from "react"

import { Button } from "@/components/ui/button"
import { HugeiconsIcon } from "@hugeicons/react"
import {
  BendToolIcon,
  Delete02Icon,
  GeometricShapes01Icon,
  Layers01Icon,
  MagicWand01Icon,
  SubtitleIcon,
  TextSquareIcon,
} from "@hugeicons/core-free-icons"

interface SubtitleStyle {
  fontFamily: string
  color: string
  shadow: boolean
}

interface TimelineItem {
  id: string
  type: "video" | "subtitle"
  label: string
  start: number
  end: number
  text?: string
  track: number
}

interface PreviewAreaProps {
  previewAspectClass: string
  previewContainerRef: RefObject<HTMLDivElement | null>
  previewVideoRef: RefObject<HTMLVideoElement | null>
  cropOverlayRef: RefObject<HTMLDivElement | null>
  subtitleOverlayElRef: RefObject<HTMLDivElement | null>

  isPreviewSelected: boolean
  onTogglePreviewSelected: () => void

  fullVideoUrl: string | null
  rotation: number
  ratio: "9:16" | "1:1" | "16:9"

  videoPan: { x: number; y: number }
  cropRect: { x: number; y: number; w: number; h: number }

  onVideoPointerDown: (e: import("react").PointerEvent) => void
  onStartRotateDrag: (e: import("react").PointerEvent) => void
  onStartCropDrag: (
    handle: "n" | "s" | "e" | "w" | "ne" | "nw" | "se" | "sw",
    e: import("react").PointerEvent
  ) => void

  activeSubtitlesForPreview: TimelineItem[]
  subtitleOverlayPos: { x: number; y: number }
  subtitleStyle: SubtitleStyle
  onSelectSubtitle: (id: string) => void
  onStartSubtitleOverlayDrag: (e: import("react").PointerEvent) => void
}

export function PreviewArea({
  previewAspectClass,
  previewContainerRef,
  previewVideoRef,
  cropOverlayRef,
  subtitleOverlayElRef,
  isPreviewSelected,
  onTogglePreviewSelected,
  fullVideoUrl,
  rotation,
  ratio,
  videoPan,
  cropRect,
  onVideoPointerDown,
  onStartRotateDrag,
  onStartCropDrag,
  activeSubtitlesForPreview,
  subtitleOverlayPos,
  subtitleStyle,
  onSelectSubtitle,
  onStartSubtitleOverlayDrag,
}: PreviewAreaProps) {
  return (
    <div className="flex-1 flex-col p-2 flex items-center justify-center min-h-0">
      <div className="w-full flex items-center justify-center gap-4">
        <div
          className={
            "relative w-[400px] max-h-full bg-muted flex items-center justify-center overflow-hidden cursor-pointer " +
            previewAspectClass
          }
          ref={previewContainerRef}
          onClick={onTogglePreviewSelected}
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

              {activeSubtitlesForPreview.map((sub, i) => (
                <div
                  key={sub.id}
                  ref={i === activeSubtitlesForPreview.length - 1 ? subtitleOverlayElRef : undefined}
                  className="absolute px-4 py-2 text-center select-none"
                  style={{
                    left: `${subtitleOverlayPos.x}%`,
                    top: `${subtitleOverlayPos.y}%`,
                    transform: "translate(-50%, -50%)",
                    fontFamily: subtitleStyle.fontFamily,
                    color: subtitleStyle.color,
                    textShadow: subtitleStyle.shadow ? "0px 2px 8px rgba(0,0,0,0.85)" : "none",
                    cursor: "grab",
                    pointerEvents: "auto",
                    maxWidth: "90%",
                    fontWeight: 800,
                    fontSize: 34,
                    lineHeight: 1.15,
                    whiteSpace: "pre-wrap",
                    zIndex: 20 + sub.track,
                  }}
                  onPointerDown={(e) => {
                    onSelectSubtitle(sub.id)
                    onStartSubtitleOverlayDrag(e)
                  }}
                >
                  {sub.text}
                </div>
              ))}

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
                    onPointerDown={onStartRotateDrag}
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
                      onPointerDown={(e) => onStartCropDrag(h.key, e)}
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
  )
}
