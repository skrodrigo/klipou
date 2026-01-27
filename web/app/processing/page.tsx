"use client"

import { getSession } from "@/infra/auth/auth"
import { uploadVideo } from "@/infra/videos/upload"
import { createJob, getJobProgress, getVideoDetails, getJobStatus, type CreateJobPayload } from "@/infra/videos/videos"
import { useVideoStore } from "@/lib/store/video-store"
import { ProcessingProjectsButton } from "@/app/processing/_components/processing-projects-button"
import { ProcessingStatusList, type ProcessingStatus } from "@/app/processing/_components/processing-status-list"
import { ProcessingVideoCard } from "@/app/processing/_components/processing-video-card"
import { useQuery } from "@tanstack/react-query"
import { useRouter, useSearchParams } from "next/navigation"
import { Suspense, useEffect, useRef, useState } from "react"
import { toast } from "sonner"

interface StatusMessage {
  status: ProcessingStatus
  progress: number
  current_step?: string
  error_message?: string
}

export default function ProcessingPage() {
  return (
    <Suspense fallback={null}>
      <ProcessingPageInner />
    </Suspense>
  )
}

function ProcessingPageInner() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const initialJobIdParam = searchParams.get("jobId")
  const [progress, setProgress] = useState(0)
  const [status, setStatus] = useState<ProcessingStatus>("queued")
  const [jobId, setJobId] = useState<string | null>(initialJobIdParam)
  const sseRef = useRef<EventSource | null>(null)
  const pollRef = useRef<number | null>(null)
  const [videoId, setVideoId] = useState<string | null>(null)
  const [config, setConfig] = useState<any>(null)
  const [didInitFromStore, setDidInitFromStore] = useState(false)
  const {
    videoFile,
    videoUrl,
    videoTitle: storedTitle,
    thumbnailUrl: storedThumb,
    processing,
    setVideoDetails,
    setProcessingConfig,
    setProcessingJobId,
    setProcessingProgress,
    setProcessingStatus,
  } = useVideoStore()
  const [videoTitle, setVideoTitle] = useState<string>(storedTitle || videoFile?.name || "Seu vídeo")
  const [error, setError] = useState<string | null>(null)
  const [thumbnail, setThumbnail] = useState<string | null>(storedThumb)
  const [isCreatingJob, setIsCreatingJob] = useState(false)
  const [isUploadComplete, setIsUploadComplete] = useState(false)
  const [isUploading, setIsUploading] = useState(true)
  const [dots, setDots] = useState(".")

  const { data: user, isLoading: isUserLoading } = useQuery({
    queryKey: ["auth-session"],
    queryFn: getSession,
    retry: 1,
  })

  useEffect(() => {
    if (storedTitle && storedTitle !== videoTitle) {
      setVideoTitle(storedTitle)
    }
    if (storedThumb !== thumbnail) {
      setThumbnail(storedThumb)
    }
  }, [storedTitle, storedThumb])

  useEffect(() => {
    const vid = searchParams.get("videoId")
    const jobIdParam = searchParams.get("jobId")
    const configStr = searchParams.get("config")

    if (!didInitFromStore) {
      if (processing?.jobId && !jobId) {
        setJobId(processing.jobId)
      }

      if (typeof processing?.progress === 'number' && processing.progress !== progress) {
        setProgress(processing.progress)
      }
      if (processing?.status && processing.status !== status) {
        setStatus(processing.status as ProcessingStatus)
      }

      if (processing?.config && !config) {
        setConfig(processing.config)
      }

      setDidInitFromStore(true)
    }

    if (vid && vid !== videoId) {
      setVideoId(vid)
    }

    if (jobIdParam && jobIdParam !== jobId) {
      setJobId(jobIdParam)
      setProcessingJobId(jobIdParam)
    }
    if (configStr) {
      try {
        const parsed = JSON.parse(decodeURIComponent(configStr))
        if (!config) {
          setConfig(parsed)
        }
        setProcessingConfig(parsed)
      } catch (err) {
        console.error("Erro ao parsear config:", err)
      }
    }
  }, [searchParams, didInitFromStore, processing, jobId, config, progress, status, videoId, setProcessingConfig])

  useEffect(() => {
    if (!videoId) {
      return
    }

    if (isUserLoading) {
      return
    }

    if (!user) {
      return
    }

    if (videoFile) {
      setVideoTitle(videoFile.name)
      return
    }

    const fetchDetails = async () => {
      try {
        const orgId = (user as any)?.organization?.organization_id ?? (user as any)?.organization_id ?? ""
        const details = await getVideoDetails(videoId, orgId)
        if (details?.title) {
          setVideoTitle(details.title)
          setVideoDetails({ videoTitle: details.title })
        }
        if (details?.thumbnail_url) {
          setThumbnail(details.thumbnail_url)
          setVideoDetails({ thumbnailUrl: details.thumbnail_url })
        }
      } catch (e) {
      }
    }

    fetchDetails()
  }, [videoId, user, isUserLoading, videoFile, setVideoDetails])

  useEffect(() => {
    if (!videoId || !videoFile || isUploadComplete) {
      return;
    }

    const performUpload = async () => {
      try {
        setIsUploading(true);
        await uploadVideo(videoFile, videoId);
        setIsUploadComplete(true);
        setIsUploading(false);
      } catch (err) {
        toast.error(err instanceof Error ? err.message : "Erro ao fazer upload do vídeo");
        setIsUploading(false);
      }
    };

    performUpload();
  }, [videoId, videoFile, isUploadComplete]);

  useEffect(() => {
    if (!videoId) return
    if (videoFile) return
    if (isUploadComplete) return
    setIsUploading(false)
    setIsUploadComplete(true)
  }, [videoId, videoFile, isUploadComplete])

  useEffect(() => {
    const jobIdFromUrl = searchParams.get("jobId")
    if (jobIdFromUrl && jobIdFromUrl.trim()) {
      return
    }

    if (!videoId || !config || !user || isCreatingJob || jobId || !isUploadComplete) {
      return;
    }

    const createJobAfterUpload = async () => {
      setIsCreatingJob(true);
      try {
        if (!videoFile) {
          const { startIngestionFromUrl } = await import("@/infra/videos/upload")
          const started = await startIngestionFromUrl(videoId, {
            minDuration: config.minDuration,
            maxDuration: config.maxDuration,
            autoSchedule: config.autoSchedule,
          })

          if (started.job_id) {
            setJobId(started.job_id)
            setProcessingJobId(started.job_id)

            router.replace(
              `/processing?videoId=${videoId}&jobId=${started.job_id}&config=${encodeURIComponent(
                JSON.stringify(config)
              )}`
            )
          }
          return
        }

        const jobPayload: CreateJobPayload = {
          video_id: videoId,
          organization_id: ((user as any)?.organization?.organization_id ?? (user as any)?.organization_id ?? "") as string,
          user_id: String(user.user_id),
          configuration: {
            minDuration: config.minDuration,
            maxDuration: config.maxDuration,
            autoSchedule: config.autoSchedule,
          },
        };

        const jobResponse = await createJob(jobPayload);
        setJobId(jobResponse.job_id);
        setProcessingJobId(jobResponse.job_id)
        console.log("Job criado com sucesso:", jobResponse.job_id);

        router.replace(
          `/processing?videoId=${videoId}&jobId=${jobResponse.job_id}&config=${encodeURIComponent(
            JSON.stringify(config)
          )}`
        )
      } catch (err) {
        console.error("Erro ao criar job:", err);
        toast.error(err instanceof Error ? err.message : "Erro ao criar job");
        setError("Erro ao criar job");
      } finally {
        setIsCreatingJob(false);
      }
    };

    createJobAfterUpload();
  }, [videoId, config, user, isCreatingJob, jobId, isUploadComplete]);

  useEffect(() => {
    if (!jobId) {
      return;
    }

    let isClosing = false;
    let isPolling = false;
    let retries = 0;
    const maxRetries = 10;
    const retryDelay = 500;
    const initialDelay = 5000;

    const stopPolling = () => {
      if (pollRef.current) {
        window.clearInterval(pollRef.current)
        pollRef.current = null
      }
      isPolling = false
    }

    const startPolling = () => {
      if (isPolling) return
      stopPolling()
      isPolling = true
      pollRef.current = window.setInterval(async () => {
        if (isClosing) return
        try {
          const job = await getJobStatus(jobId)
          const nextStatus = (job as any)?.status as ProcessingStatus | undefined
          const nextProgress = (job as any)?.progress
          const nextStep = (job as any)?.current_step
          const nextError = (job as any)?.error_message

          if (nextStatus) {
            setStatus(nextStatus)
            setProcessingStatus(nextStatus)
          }
          if (typeof nextProgress === "number" && Number.isFinite(nextProgress)) {
            setProgress(nextProgress)
            setProcessingProgress(nextProgress)
          }

          if (nextStatus === "done") {
            isClosing = true
            stopPolling()
            setStatus("done")
            setProgress(100)
            setProcessingStatus("done")
            setProcessingProgress(100)
            setTimeout(() => router.push("/dashboard/projects"), 1500)
          }
          if (nextStatus === "failed") {
            isClosing = true
            stopPolling()
            setStatus("failed")
            setProcessingStatus("failed")
            setError(nextError || nextStep || "O processamento falhou. Por favor, tente novamente.")
          }
        } catch (e) {
        }
      }, 2000)
    }

    const connectToSSE = () => {
      if (isClosing) {
        return
      }

      if (sseRef.current) {
        try {
          sseRef.current.close()
        } catch (e) {
        }
        sseRef.current = null
      }

      const eventSource = getJobProgress(jobId);

      if (!eventSource) {
        setError("Não foi possível conectar ao servidor.");
        return;
      }

      sseRef.current = eventSource

      eventSource.onmessage = (event) => {
        try {
          const data: StatusMessage = JSON.parse(event.data);

          if ((data as any)?.error_message === "Job not found" || (data as any)?.error === "Job not found") {
            try {
              eventSource.close()
            } catch (e) {
            }
            if (sseRef.current === eventSource) {
              sseRef.current = null
            }

            if (retries < maxRetries) {
              retries++
              setTimeout(connectToSSE, retryDelay)
              return
            }

            startPolling()
            return
          }

          setStatus(data.status);
          setProgress(data.progress);
          setProcessingStatus(data.status)
          setProcessingProgress(data.progress)

          if (data.status === "done") {
            isClosing = true;
            setStatus("done");
            setProgress(100);
            setProcessingStatus("done")
            setProcessingProgress(100)
            setTimeout(() => {
              try {
                eventSource.close();
              } catch (e) {
              }
              if (sseRef.current === eventSource) {
                sseRef.current = null
              }
              router.push("/dashboard/projects");
            }, 2000);
          } else if (data.status === "failed") {
            isClosing = true;
            setStatus("failed");
            setProcessingStatus("failed")
            setError(data.error_message || "O processamento falhou. Por favor, tente novamente.");
            try {
              eventSource.close();
            } catch (e) {
            }
            if (sseRef.current === eventSource) {
              sseRef.current = null
            }
          }
        } catch (e) {
          console.error("Error parsing SSE message:", e);
        }
      };

      eventSource.onerror = (event: any) => {
        if (!isClosing) {
          // EventSource doesn't expose HTTP status reliably. Treat any error as transient and retry.
          if (retries < maxRetries) {
            retries++;
            try {
              eventSource.close();
            } catch (e) {
            }
            if (sseRef.current === eventSource) {
              sseRef.current = null
            }
            setTimeout(connectToSSE, retryDelay);
            return;
          }

          setError("Ocorreu um erro ao conectar com o servidor. Por favor, tente novamente.");
          try {
            eventSource.close();
          } catch (e) {
          }
          if (sseRef.current === eventSource) {
            sseRef.current = null
          }

          startPolling()
        }
      };
    };

    const initialTimer = setTimeout(connectToSSE, initialDelay);

    return () => {
      isClosing = true;
      clearTimeout(initialTimer);
      stopPolling()
      if (sseRef.current) {
        try {
          sseRef.current.close()
        } catch (e) {
        }
        sseRef.current = null
      }
    };
  }, [jobId, router, setProcessingProgress, setProcessingStatus]);

  useEffect(() => {
    if (status === "done" || status === "failed") return

    const interval = setInterval(() => {
      setDots((prev) => (prev.length >= 3 ? "." : prev + "."))
    }, 500)

    return () => clearInterval(interval)
  }, [status])

  const getVideoTitle = () => {
    const title = videoTitle || (videoFile ? videoFile.name : null)
    if (title) {
      return title.length > 60 ? `${title.slice(0, 60)}...` : title
    }
    return "Vídeo"
  }

  return (
    <div className="w-full flex flex-col p-6 h-screen">

      <div className="flex-1 flex flex-col items-center justify-center">
        <div className="w-full max-w-xl space-y-8">
          <ProcessingVideoCard
            thumbnail={thumbnail}
            videoUrl={videoUrl}
            videoFile={videoFile ?? null}
            title={getVideoTitle()}
            progress={progress}
          />

          {/* Status List */}
          <ProcessingStatusList
            status={status}
            isUploading={isUploading}
            isUploadComplete={isUploadComplete}
            error={error}
            dots={dots}
          />

          <ProcessingProjectsButton onClick={() => router.push("/dashboard/projects")} />
        </div>
      </div>
    </div>
  )
}
