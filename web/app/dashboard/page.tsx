"use client"

import { useRef, useState } from "react"
import { useRouter } from "next/navigation"

import { useVideoStore } from "@/lib/store/video-store"
import { Input } from "@/components/ui/input"
import { Paperclip, X } from "lucide-react"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"

export default function DashboardPage() {
  const [files, setFiles] = useState<File[]>([])
  const [isDragging, setIsDragging] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const { setVideoFile } = useVideoStore()
  const router = useRouter()

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = Array.from(e.target.files ?? [])
    const videoFiles = selected.filter((f) => f.type.startsWith("video"))
    if (videoFiles.length > 0) {
      setFiles([videoFiles[0]])
    }
  }

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(true)
  }

  const handleDragLeave = () => {
    setIsDragging(false)
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
    const droppedFiles = Array.from(e.dataTransfer.files ?? [])
    const videoFiles = droppedFiles.filter((f) => f.type.startsWith("video"))
    if (videoFiles.length > 0) {
      setFiles([videoFiles[0]])
    }
  }

  const removeFile = (idx: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== idx))
  }

  const handleContinue = async () => {
    if (!files.length || isSubmitting) {
      return
    }

    setIsSubmitting(true)
    try {
      const file = files[0]
      if (file) {
        setVideoFile(file)
        router.push("/video-settings")
      }
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="flex items-center justify-center" style={{ minHeight: "calc(100vh - 3.5rem)" }}>
      <div className="w-full max-w-2xl px-4">


        {files.length > 0 && (
          <div className="flex flex-wrap gap-2 mb-4">
            {files.map((file, idx) => {
              const videoUrl = URL.createObjectURL(file)
              return (
                <div
                  key={file.name + file.size + idx}
                  className="relative group  rounded-md overflow-hidden border border-border w-24 h-24"
                >
                  <video
                    src={videoUrl}
                    className="w-full h-full object-cover bg-black"
                  />
                  <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                    <button
                      onClick={() => removeFile(idx)}
                      className="bg-accent text-white rounded-md p-2 hover:bg-muted/90"
                    >
                      <X className="h-4 w-4" />
                    </button>
                  </div>
                  <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/80 to-transparent p-2">
                    <p className="text-xs text-white font-medium truncate">
                      {file.name}
                    </p>
                  </div>
                </div>
              )
            })}
          </div>
        )}

        <div className="space-y-4 flex gap-2">

          <div
            className={cn(
              "relative rounded-md transition-all flex-1",
              isDragging ? "" : "border-border"
            )}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
          >
            <div className="flex gap-3 items-center h-12">
              <input
                hidden
                onChange={handleFileChange}
                ref={fileInputRef}
                type="file"
                accept="video/*"
                multiple
              />
              <button
                onClick={() => fileInputRef.current?.click()}
                className="text-muted-foreground border rounded-full p-3 border-border hover:text-foreground transition-colors"
              >
                <Paperclip className="h-5 w-5" />
              </button>
              <Input
                placeholder="Paste link or drag your video here"
                className="flex-1 focus-visible:ring-0 h-12 focus-visible:ring-offset-0 placeholder:text-muted-foreground"
              />
            </div>
          </div>

          <Button
            className="rounded-md h-12 font-semibold"
            disabled={!files.length || isSubmitting}
            onClick={handleContinue}
          >
            {isSubmitting ? "Generating clips..." : "Continue"}
          </Button>
        </div>
      </div>
    </div>
  )
}
