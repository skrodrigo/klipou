"use client"

import { Button } from "@/components/ui/button"
import { Progress } from "@/components/ui/progress"
import { getSession } from "@/infra/auth/auth"
import { uploadVideo } from "@/infra/videos/upload"
import { createJob, getJobProgress, getVideoDetails, type CreateJobPayload } from "@/infra/videos/videos"
import { useVideoStore } from "@/lib/store/video-store"
import { cn } from "@/lib/utils"
import { AlertSquareIcon, CancelSquareIcon, Loading03Icon, LogoutSquare02Icon, SquareIcon, Tick02Icon } from "@hugeicons/core-free-icons"
import { HugeiconsIcon } from "@hugeicons/react"
import { useQuery } from "@tanstack/react-query"
import { useRouter, useSearchParams } from "next/navigation"
import { Suspense, useEffect, useState } from "react"
import { toast } from "sonner"

type ProcessingStatus = "ingestion" | "queued" | "downloading" | "normalizing" | "transcribing" | "analyzing" | "embedding" | "selecting" | "reframing" | "rendering" | "clipping" | "captioning" | "done" | "failed"

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
  const [progress, setProgress] = useState(0)
  const [status, setStatus] = useState<ProcessingStatus>("queued")
  const [jobId, setJobId] = useState<string | null>(null)
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
        const details = await getVideoDetails(videoId, user.organization_id || "")
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
    if (!videoId || !config || !user || isCreatingJob || jobId || !isUploadComplete) {
      return;
    }

    const createJobAfterUpload = async () => {
      setIsCreatingJob(true);
      try {
        if (!videoFile) {
          const { startIngestionFromUrl } = await import("@/infra/videos/upload")
          const started = await startIngestionFromUrl(videoId, {
            language: config.language,
            ratio: config.ratio,
            maxDuration: config.maxDuration,
            autoSchedule: config.autoSchedule,
          })

          if (started.job_id) {
            setJobId(started.job_id)
            setProcessingJobId(started.job_id)
          }
          return
        }

        const jobPayload: CreateJobPayload = {
          video_id: videoId,
          organization_id: user.organization_id || "",
          user_id: String(user.user_id),
          configuration: {
            language: config.language,
            target_ratios: [config.ratio],
            max_clip_duration: config.maxDuration,
            auto_schedule: config.autoSchedule,
          },
        };

        const jobResponse = await createJob(jobPayload);
        setJobId(jobResponse.job_id);
        setProcessingJobId(jobResponse.job_id)
        console.log("Job criado com sucesso:", jobResponse.job_id);
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
    let retries = 0;
    const maxRetries = 10;
    const retryDelay = 500;
    const initialDelay = 5000;

    const connectToSSE = () => {
      const eventSource = getJobProgress(jobId);

      if (!eventSource) {
        setError("Não foi possível conectar ao servidor.");
        return;
      }

      eventSource.onmessage = (event) => {
        try {
          const data: StatusMessage = JSON.parse(event.data);

          if (status !== "done" && status !== "failed") {
            setStatus(data.status);
            setProgress(data.progress);
            setProcessingStatus(data.status)
            setProcessingProgress(data.progress)
          }

          if (data.status === "done") {
            isClosing = true;
            setStatus("done");
            setProgress(100);
            setProcessingStatus("done")
            setProcessingProgress(100)
            setTimeout(() => {
              eventSource.close();
              router.push("/dashboard/projects");
            }, 2000);
          } else if (data.status === "failed") {
            isClosing = true;
            setStatus("failed");
            setProcessingStatus("failed")
            setError(data.error_message || "O processamento falhou. Por favor, tente novamente.");
            eventSource.close();
          }
        } catch (e) {
          console.error("Error parsing SSE message:", e);
        }
      };

      eventSource.onerror = (event: any) => {
        if (!isClosing) {
          if (event.status === 404 && retries < maxRetries) {
            retries++;
            eventSource.close();
            setTimeout(connectToSSE, retryDelay);
          } else {
            setError("Ocorreu um erro ao conectar com o servidor. Por favor, tente novamente.");
            eventSource.close();
          }
        }
      };
    };

    const initialTimer = setTimeout(connectToSSE, initialDelay);

    return () => {
      isClosing = true;
      clearTimeout(initialTimer);
    };
  }, [jobId, router, status]);

  const stages: ProcessingStatus[] = [
    "queued",
    "downloading",
    "normalizing",
    "transcribing",
    "analyzing",
    "embedding",
    "selecting",
    "reframing",
    "rendering",
  ];

  const getUploadState = (): 'completed' | 'active' | 'pending' => {
    if (isUploadComplete) return 'completed';
    if (isUploading) return 'active';
    return 'pending';
  };

  const getStageState = (stage: ProcessingStatus): 'completed' | 'active' | 'pending' | 'failed' => {
    const stageIndex = stages.indexOf(stage);

    if (!isUploadComplete) {
      return 'pending';
    }

    if (status === "done") {
      return 'completed';
    }

    if (status === "failed") {
      const statusIndex = stages.indexOf(status);
      if (stageIndex < statusIndex) return 'completed';
      return 'failed';
    }

    const statusIndex = stages.indexOf(status);
    if (stageIndex < statusIndex) return 'completed';
    if (stageIndex === statusIndex) return 'active';
    return 'pending';
  };

  const getFailedStageIndex = (): number => {
    if (!error || status === "done") return -1;
    return stages.indexOf(status);
  };

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
          <div className="bg-card border border-border rounded-md p-4 flex gap-4">
            <div className="w-16 h-16 bg-black rounded-md overflow-hidden flex-shrink-0">
              {thumbnail ? (
                <img src={thumbnail} alt="Video thumbnail" className="w-full h-full object-cover" />
              ) : videoUrl && videoFile ? (
                <video src={videoUrl} className="w-full h-full object-cover" />
              ) : null}
            </div>
            <div className="flex-1">
              <h3 className="text-sm text-start font-medium text-foreground mb-3 line-clamp-2">
                {getVideoTitle()}
              </h3>
              <Progress className="h-2" value={progress} />
              <div className="text-xs text-muted-foreground mt-2">{progress} %</div>
            </div>
          </div>

          {/* Status List */}
          <div className="space-y-3">
            {/* Upload Stage */}
            <div className="flex items-center gap-3">
              {getUploadState() === 'completed' ? (
                <HugeiconsIcon size={16} icon={Tick02Icon} className='text-primary' />
              ) : getUploadState() === 'active' ? (
                <HugeiconsIcon size={16} icon={Loading03Icon} className='animate-spin text-foreground' />
              ) : (
                <HugeiconsIcon size={16} icon={SquareIcon} className='text-muted-foreground' />
              )}
              <span className={cn(
                "text-sm",
                getUploadState() === 'completed' && "text-muted-foreground line-through",
                getUploadState() === 'active' && "text-foreground font-medium",
                getUploadState() === 'pending' && "text-muted-foreground",
              )}>
                Enviando vídeo{getUploadState() === 'active' && <span className='ml-1'>...</span>}
              </span>
            </div>

            {[
              { stage: "queued" as ProcessingStatus, label: "Na fila" },
              { stage: "downloading" as ProcessingStatus, label: "Preparando o vídeo" },
              { stage: "normalizing" as ProcessingStatus, label: "Fazendo ajustes" },
              { stage: "transcribing" as ProcessingStatus, label: "Transformando e Entendendo" },
              { stage: "analyzing" as ProcessingStatus, label: "Analisando conteúdo" },
              { stage: "embedding" as ProcessingStatus, label: "Indexando o conteúdo" },
              { stage: "selecting" as ProcessingStatus, label: "Selecionando melhores trechos" },
              { stage: "reframing" as ProcessingStatus, label: "Reenquadrando vídeo" },
              { stage: "rendering" as ProcessingStatus, label: "Gerando clips finais" },
            ].map(({ stage, label }, idx) => {
              const state = getStageState(stage);
              const failedIdx = getFailedStageIndex();
              const isFailedStage = error && failedIdx === idx;
              const isAfterFailed = error && failedIdx !== -1 && idx > failedIdx;
              const [dots, setDots] = useState('.');

              useEffect(() => {
                if (state !== 'active') return;
                const interval = setInterval(() => {
                  setDots(prev => prev.length >= 3 ? '.' : prev + '.');
                }, 500);
                return () => clearInterval(interval);
              }, [state]);

              return (
                <div key={stage} className="flex items-center gap-3">
                  {isFailedStage ? (
                    <HugeiconsIcon size={16} icon={CancelSquareIcon} className='text-destructive' />
                  ) : isAfterFailed ? (
                    <HugeiconsIcon size={16} icon={AlertSquareIcon} className='text-muted-foreground' />
                  ) : state === 'completed' ? (
                    <HugeiconsIcon size={16} icon={Tick02Icon} className='text-primary' />
                  ) : state === 'active' ? (
                    <HugeiconsIcon size={16} icon={Loading03Icon} className='animate-spin text-foreground' />
                  ) : (
                    <HugeiconsIcon size={16} icon={SquareIcon} className='text-muted-foreground' />
                  )}
                  <span className={cn(
                    "text-sm",
                    state === 'completed' && "text-muted-foreground line-through",
                    state === 'active' && "text-foreground font-medium",
                    isFailedStage && "text-destructive font-semibold",
                    isAfterFailed && "text-foreground",
                    !isFailedStage && !isAfterFailed && state === 'pending' && "text-muted-foreground",
                  )}>
                    {label}{state === 'active' && !error && <span className='ml-1'>{dots}</span>}
                  </span>
                </div>
              );
            })}
          </div>

          <Button
            onClick={() => router.push("/dashboard/projects")}
            className=" bg-foreground text-background rounded-md hover:bg-foreground/90 transition-colors"
          >
            <HugeiconsIcon size={16} icon={LogoutSquare02Icon} strokeWidth={2} className='text-background' />
            Ir para Projetos
          </Button>
        </div>
      </div>
    </div>
  )
}
