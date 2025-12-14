"use client"

import { use, useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { cn } from "@/lib/utils"
import { HugeiconsIcon } from "@hugeicons/react"
import { ArrowLeft02Icon, Download01Icon, FilterIcon, PlayIcon, Share03Icon, Edit02Icon, Copy01Icon, Delete02Icon, SentIcon, ScissorIcon } from "@hugeicons/core-free-icons"
import { listVideoClips, type VideoClip } from "@/infra/videos/videos"
import { Spinner } from "@/components/ui/spinner"

type ClipsPageProps = {
  params: Promise<{
    videoId: string
  }>
}

export default function ClipsPage({ params }: ClipsPageProps) {
  const router = useRouter()
  const { videoId: videoIdStr } = use(params)
  const [clips, setClips] = useState<VideoClip[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedIdx, setSelectedIdx] = useState(0)
  const videoId = parseInt(videoIdStr, 10) || null

  useEffect(() => {
    async function loadClips() {
      try {
        const items = await listVideoClips(videoId)
        setClips(items)
      } finally {
        setLoading(false)
      }
    }

    loadClips()
  }, [videoId])

  return (
    <div className="w-full h-screen flex flex-col bg-background text-foreground relative">
      <button
        onClick={() => router.back()}
        className="absolute fixed top-6 left-6 flex items-center gap-2 text-foreground hover:text-foreground text-sm z-10"
      >
        <HugeiconsIcon icon={ArrowLeft02Icon} strokeWidth={2} className="" />
        Voltar
      </button>

      <div className="flex-1 flex">
        {/* Left Sidebar - Clips List */}
        <aside className="w-80 pt-40 fixed overflow-y-auto hidden md:block shrink-0 flex flex-col justify-center">
          <div className="p-4 space-y-2">
            {clips.map((clip, idx) => (
              <button
                key={clip.id}
                type="button"
                onClick={() => setSelectedIdx(idx)}
                className={cn(
                  "w-full flex items-center gap-3 p-2 rounded-lg text-left transition-all group",
                  selectedIdx === idx
                    ? "bg-zinc-800/80"
                    : "hover:bg-zinc-900"
                )}
              >
                {/* Vertical Thumbnail Placeholder */}
                <div className="relative w-10 h-16 bg-zinc-800 rounded overflow-hidden flex-shrink-0">
                  <div className="absolute inset-0 flex items-center justify-center">
                    {/* Placeholder visual */}
                    <div className="w-full h-full bg-zinc-700/20"></div>
                  </div>
                </div>

                <div className="flex-1 min-w-0">
                  <p className={cn(
                    "text-xs font-medium line-clamp-2 leading-relaxed",
                    selectedIdx === idx ? "text-zinc-100" : "text-foreground group-hover:text-zinc-300"
                  )}>
                    {clip.title || "Como eu uso o Cursor para front-end (do Figma ao código)"}
                  </p>
                </div>
              </button>
            ))}
            {!loading && clips.length === 0 && (
              <p className="text-xs text-zinc-500 p-2">Nenhum clip gerado ainda.</p>
            )}
          </div>
        </aside>

        {/* Main Content Area */}
        <main className="flex-1 overflow-y-auto p-6 md:p-10">
          <div className="mb-10 w-full flex justify-end items-center gap-2 max-w-7xl">
            <Button variant="secondary" size="sm" className="h-9 text-zinc-300 hover:bg-zinc-800 hover:text-white gap-2 text-xs">
              <HugeiconsIcon icon={FilterIcon} className="h-4 w-4" />
              <span>Filtrar</span>
            </Button>
            <div className="flex bg-card items-center gap-2  rounded-md px-3 h-9">
              <span className="text-xs text-zinc-300">Selecionar Tudo</span>
              <Checkbox />
            </div>
          </div>
          <div className="max-w-5xl mx-auto space-y-16 pb-20">
            {clips.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-20 text-zinc-500">
                <Spinner />
              </div>
            ) : (
              clips.map((clip, idx) => (
                <div key={clip.id} className="flex flex-col lg:flex-row gap-8 items-start group">

                  {/* Left Column: Vertical Video Player */}
                  <div className="shrink-0">
                    <div className="relative w-[280px] aspect-[9/16] bg-card rounded-2xl overflow-hidden border border-zinc-800 shadow-xl">
                      <div className="absolute inset-0 flex items-center justify-center text-zinc-700">
                        {/* Placeholder Content */}
                        <HugeiconsIcon icon={PlayIcon} className="h-12 w-12 opacity-50" />
                      </div>
                    </div>
                  </div>

                  {/* Middle Column: Details */}
                  <div className="flex-1 min-w-0 space-y-5 pt-2">
                    {/* Header: ID + Title */}
                    <div>
                      <h3 className="text-lg font-medium text-zinc-100 flex items-start gap-2 leading-tight">
                        <span className="text-primary font-bold">#{idx + 1}</span>
                        {clip.title || "Redimensione vários elementos HTML com Copiar/Colar + IA!"}
                      </h3>
                    </div>

                    {/* Stats & Primary Actions Row */}
                    <div className="flex items-center flex-wrap gap-2">
                      <div className="flex items-baseline gap-1">
                        <span className="text-4xl font-bold text-white tracking-tighter">9.8</span>
                        <span className="text-sm font-medium text-zinc-500">/10</span>
                      </div>

                      <div className="h-8 w-[1px] bg-muted mx-2 hidden sm:block"></div>

                      <Button className="bg-primary text-white rounded-lg px-6 h-9 text-xs font-medium">
                        <HugeiconsIcon icon={SentIcon} size={14} className="mr-2" />
                        Publicar
                      </Button>

                      <Button variant="secondary" size="icon" className="h-9 w-9 rounded-lg bg-card text-foreground hover:text-white hover:bg-zinc-700">
                        <HugeiconsIcon icon={Download01Icon} size={16} />
                      </Button>
                      <Button variant="secondary" size="icon" className="h-9 w-9 rounded-lg bg-card text-foreground hover:text-white hover:bg-zinc-700">
                        <HugeiconsIcon icon={Share03Icon} size={16} />
                      </Button>
                    </div>

                    {/* Transcript Text */}
                    <div className="bg-transparent">
                      <p className="text-sm text-muted-foreground leading-7">
                        E aí, olha só, com o React Grab, teoricamente agora eu posso vir na minha aplicação, apertar Command C, ele vai abrir isso aqui, para eu selecionar o elemento que eu quero modificar, digamos assim, e aí eu posso falar para ele, por exemplo, esse texto aqui está muito negrito, então eu clico no texto e falo, vou criar um novo agente aqui, esse texto está negrito, diminua ele para a fonte Medium, por exemplo, do Tape. E eu dou um Enter no elemento selecionado ali, e o cursor vai entender automaticamente aonde é que está esse elemento. Olha só, ele entendeu automaticamente, sendo que eu só falei esse texto, eu não falei exatamente qual, por causa que eu copiei, exatamente ele copia qual que é o elemento...
                      </p>
                    </div>
                  </div>

                  {/* Right Column: Floating Actions */}
                  <div className="flex flex-row lg:flex-col gap-3 shrink-0 lg:pt-2 w-full lg:w-auto overflow-x-auto lg:overflow-visible">
                    <ActionButton icon={<HugeiconsIcon icon={Edit02Icon} size={15} />} label="Rename" variant="default" />
                    <ActionButton icon={<HugeiconsIcon icon={Copy01Icon} size={15} />} label="Duplicate" variant="default" />
                    <ActionButton icon={<HugeiconsIcon icon={Delete02Icon} size={15} />} label="Delete" variant="danger" />
                    <ActionButton icon={<HugeiconsIcon icon={ScissorIcon} size={15} />} label="Cut" variant="default" />
                  </div>

                </div>
              ))
            )}
          </div>
        </main>
      </div>
    </div>
  )
}

function ActionButton({ icon, label, variant = "default" }: { icon: React.ReactNode, label: string, variant?: "default" | "danger" }) {
  return (
    <Button
      variant={variant === "danger" ? "destructive" : "secondary"}
      className="justify-start gap-3 w-full lg:w-32"
    >
      {icon}
      <span>{label}</span>
    </Button>
  )
}