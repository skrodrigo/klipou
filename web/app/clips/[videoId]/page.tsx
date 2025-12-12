"use client"

import { use, useEffect, useState } from "react"
import { Button } from "@/components/ui/button"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { cn } from "@/lib/utils"
import {
  IconPlayerPlayFilled,
  IconDownload,
  IconShare2,
  IconBookmark,
  IconThumbUp,
  IconFilter,
  IconCheck,
  IconPencil,
  IconCopy,
  IconTrash,
  IconMenu2,
} from "@tabler/icons-react"
import { listVideoClips, type VideoClip } from "@/infra/videos/videos"
import { useVideoProgress } from "@/hooks/useVideoProgress"

type ClipsPageProps = {
  params: Promise<{
    videoId: string
  }>
}

export default function ClipsPage({ params }: ClipsPageProps) {
  const { videoId: videoIdStr } = use(params)
  const [clips, setClips] = useState<VideoClip[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const videoId = parseInt(videoIdStr, 10) || null
  const { progress, status, error } = useVideoProgress(videoId)

  useEffect(() => {
    async function loadClips() {
      try {
        const items = await listVideoClips(videoId)
        setClips(items)
        if (items.length > 0) {
          setSelectedId(items[0].id)
        }
      } finally {
        setLoading(false)
      }
    }

    loadClips()
  }, [videoId])

  const selectedClip = clips.find((clip) => clip.id === selectedId) ?? null

  return (
    <section className="w-full flex flex-col bg-background p-6">
      {/* Error Banner */}
      {error && (
        <div className="absolute top-0 left-0 right-0 border-b bg-destructive/10 p-3 z-50">
          <p className="text-xs font-medium text-destructive">{error.message}</p>
        </div>
      )}

      {/* Processing Banner */}
      {status === "processing" && !error && (
        <div className="absolute top-0 left-0 right-0 border-b bg-muted/50 p-3 z-50">
          <div className="flex items-center gap-3">
            <div className="flex-1">
              <div className="text-xs font-medium mb-1">Processando vídeo...</div>
              <div className="w-full bg-muted rounded-md h-2">
                <div
                  className="bg-primary h-2 rounded-md transition-all"
                  style={{ width: `${progress}%` }}
                />
              </div>
            </div>
            <span className="text-xs text-muted-foreground">{progress}%</span>
          </div>
        </div>
      )}

      {/* Left Sidebar - Clips List */}
      <aside className="w-64 border-r bg-muted/30 overflow-y-auto flex flex-col">
        <div className="p-4 border-b">
          <div className="flex items-center gap-2">
            <IconMenu2 className="h-4 w-4" />
            <h2 className="text-sm font-semibold">AI clips</h2>
          </div>
        </div>
        <div className="flex-1 overflow-y-auto p-2 space-y-1">
          {clips.map((clip, idx) => (
            <button
              key={clip.id}
              type="button"
              onClick={() => setSelectedId(clip.id)}
              className={cn(
                "w-full flex items-start gap-2 p-2 rounded-md text-left transition-colors text-xs",
                selectedId === clip.id
                  ? "bg-primary/20 border border-primary/30"
                  : "hover:bg-muted border border-transparent"
              )}
            >
              <div className="relative w-12 h-12 rounded bg-black text-white flex-shrink-0 flex items-center justify-center overflow-hidden">
                <IconPlayerPlayFilled className="h-3 w-3" />
                <div className="absolute bottom-0.5 right-0.5 bg-black/80 px-1 py-0.5 rounded text-xs font-medium">
                  720p
                </div>
              </div>
              <div className="flex-1 min-w-0">
                <p className="font-medium line-clamp-2 text-xs">{clip.title}</p>
                <p className="text-xs text-muted-foreground">#{idx + 1}</p>
              </div>
            </button>
          ))}
          {!loading && clips.length === 0 && (
            <p className="text-xs text-muted-foreground p-2">Nenhum clip gerado ainda.</p>
          )}
        </div>
      </aside>

      {/* Main Content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Toolbar */}
        <div className="border-b px-6 py-3 flex items-center gap-3 bg-background">
          <div className="text-sm font-semibold">AI clips</div>
          <div className="flex-1" />
          <Button variant="ghost" size="sm" className="h-8 gap-2 text-xs">
            <span>0/16</span>
          </Button>
          <Button variant="ghost" size="sm" className="h-8 gap-2 text-xs">
            <IconFilter className="h-4 w-4" />
            <span>Filter</span>
          </Button>
          <Select defaultValue="highest">
            <SelectTrigger className="w-32 h-8 text-xs">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="highest">Highest score</SelectItem>
              <SelectItem value="lowest">Lowest score</SelectItem>
              <SelectItem value="newest">Newest</SelectItem>
              <SelectItem value="oldest">Oldest</SelectItem>
            </SelectContent>
          </Select>
          <Button variant="ghost" size="sm" className="h-8 gap-2 text-xs">
            <IconCheck className="h-4 w-4" />
            <span>Select all</span>
          </Button>
        </div>

        {/* Grid of Clips */}
        <div className="flex-1 overflow-y-auto p-6">
          <div className="grid grid-cols-2 gap-6">
            {clips.map((clip, idx) => (
              <div
                key={clip.id}
                onClick={() => setSelectedId(clip.id)}
                className={cn(
                  "group cursor-pointer rounded-md overflow-hidden border-2 transition-all",
                  selectedId === clip.id
                    ? "border-primary bg-primary/5"
                    : "border-muted hover:border-primary/50"
                )}
              >
                {/* Video Card */}
                <div className="relative bg-black text-white overflow-hidden aspect-video">
                  <div className="absolute inset-0 flex items-center justify-center">
                    <IconPlayerPlayFilled className="h-16 w-16 opacity-60" />
                  </div>

                  {/* Quality Badge */}
                  <div className="absolute top-3 left-3 bg-black/80 px-2 py-1 rounded text-xs font-medium">
                    720p
                  </div>

                  {/* Duration Badge */}
                  <div className="absolute bottom-3 right-3 bg-black/80 px-2 py-1 rounded text-xs font-medium">
                    01:05
                  </div>
                </div>

                {/* Card Content */}
                <div className="p-4 space-y-3">
                  {/* Title & Number */}
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex-1">
                      <h3 className="text-sm font-semibold line-clamp-2">
                        {clip.title}
                      </h3>
                    </div>
                    <span className="text-xs text-muted-foreground shrink-0">
                      #{idx + 1}
                    </span>
                  </div>

                  {/* Score */}
                  <div className="flex items-center gap-1">
                    <span className="text-lg font-bold">9.8</span>
                    <span className="text-xs text-muted-foreground">/10</span>
                  </div>

                  {/* Description */}
                  <p className="text-xs text-muted-foreground line-clamp-2">
                    {clip.title}
                  </p>

                  {/* Action Buttons */}
                  <div className="flex items-center gap-2 pt-2">
                    <Button size="sm" className="flex-1 h-8 text-xs">
                      Publish
                    </Button>
                    <Button variant="outline" size="sm" className="h-8">
                      <IconDownload className="h-4 w-4" />
                    </Button>
                    <Button variant="outline" size="sm" className="h-8">
                      <IconShare2 className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              </div>
            ))}

            {!loading && clips.length === 0 && (
              <div className="col-span-full flex items-center justify-center py-12">
                <p className="text-sm text-muted-foreground">Nenhum clip gerado ainda.</p>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Right Sidebar - Details */}
      {selectedClip && (
        <aside className="w-64 border-l bg-muted/30 overflow-y-auto p-4 space-y-4">
          <div>
            <h3 className="text-sm font-semibold mb-2">{selectedClip.title}</h3>
            <div className="flex items-center gap-2">
              <span className="text-2xl font-bold">9.8</span>
              <span className="text-xs text-muted-foreground">/10</span>
            </div>
          </div>

          <div className="space-y-2">
            <Button variant="outline" className="w-full justify-start gap-2 text-xs h-9">
              <IconDownload className="h-4 w-4" />
              <span>Download</span>
            </Button>
            <Button variant="outline" className="w-full justify-start gap-2 text-xs h-9">
              <IconShare2 className="h-4 w-4" />
              <span>Share</span>
            </Button>
            <Button variant="outline" className="w-full justify-start gap-2 text-xs h-9">
              <IconPencil className="h-4 w-4" />
              <span>Edit</span>
            </Button>
            <Button variant="outline" className="w-full justify-start gap-2 text-xs h-9">
              <IconPencil className="h-4 w-4" />
              <span>Rename</span>
            </Button>
            <Button variant="outline" className="w-full justify-start gap-2 text-xs h-9">
              <IconCopy className="h-4 w-4" />
              <span>Duplicate</span>
            </Button>
            <Button
              variant="outline"
              className="w-full justify-start gap-2 text-xs h-9 text-destructive"
            >
              <IconTrash className="h-4 w-4" />
              <span>Delete</span>
            </Button>
          </div>

          <div className="border-t pt-4 space-y-2">
            <Button variant="ghost" className="w-full justify-start gap-2 text-xs h-8">
              <IconThumbUp className="h-4 w-4" />
              <span>Like</span>
            </Button>
            <Button variant="ghost" className="w-full justify-start gap-2 text-xs h-8">
              <IconBookmark className="h-4 w-4" />
              <span>Save</span>
            </Button>
          </div>
        </aside>
      )}
    </section>
  )
}
