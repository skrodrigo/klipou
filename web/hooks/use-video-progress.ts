import { useEffect, useState, useCallback } from "react"
import { getVideoProgress } from "@/infra/videos/videos"

type ProgressEvent = {
  progress: number
  status: "processing" | "completed"
}

type UseVideoProgressError = {
  type: "connection_failed" | "parse_error" | "invalid_data"
  message: string
}

export function useVideoProgress(videoId: number | null) {
  const [progress, setProgress] = useState(0)
  const [status, setStatus] = useState<"idle" | "processing" | "completed">("idle")
  const [error, setError] = useState<UseVideoProgressError | null>(null)

  const connect = useCallback(() => {
    if (!videoId) return

    const eventSource = getVideoProgress(videoId)
    if (!eventSource) return

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as unknown

        if (!isProgressEvent(data)) {
          setError({
            type: "invalid_data",
            message: "Invalid progress event format",
          })
          return
        }

        setProgress(data.progress)
        setStatus(data.status)
        setError(null)

        if (data.status === "completed") {
          eventSource.close()
        }
      } catch {
        setError({
          type: "parse_error",
          message: "Failed to parse SSE event",
        })
      }
    }

    eventSource.onerror = () => {
      setError({
        type: "connection_failed",
        message: "SSE connection error",
      })
      eventSource.close()
      setStatus("idle")
    }

    return () => eventSource.close()
  }, [videoId])

  useEffect(() => {
    const cleanup = connect()
    return cleanup
  }, [connect])

  return { progress, status, error }
}

function isProgressEvent(data: unknown): data is ProgressEvent {
  if (typeof data !== "object" || data === null) return false
  const obj = data as Record<string, unknown>
  return (
    typeof obj.progress === "number" &&
    (obj.status === "processing" || obj.status === "completed")
  )
}
