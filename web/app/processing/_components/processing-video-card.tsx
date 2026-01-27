"use client"

import { Progress } from "@/components/ui/progress"

type Props = {
  thumbnail: string | null
  videoUrl: string | null
  videoFile: File | null
  title: string
  progress: number
}

export function ProcessingVideoCard({ thumbnail, videoUrl, videoFile, title, progress }: Props) {
  return (
    <div className="bg-accent border border-border rounded-md p-4 flex gap-4">
      <div className="w-16 h-16 bg-black rounded-md overflow-hidden flex-shrink-0">
        {thumbnail ? (
          <img src={thumbnail} alt="Video thumbnail" className="w-full h-full object-cover" />
        ) : videoUrl && videoFile ? (
          <video src={videoUrl} className="w-full h-full object-cover" />
        ) : null}
      </div>
      <div className="flex-1">
        <h3 className="text-sm text-start font-medium text-foreground mb-3 line-clamp-2">{title}</h3>
        <Progress className="h-2" value={progress} />
        <div className="text-xs text-muted-foreground mt-2">{progress} %</div>
      </div>
    </div>
  )
}
