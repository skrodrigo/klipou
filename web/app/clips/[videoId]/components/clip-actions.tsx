"use client"

import { useMemo, useState } from "react"
import { useRouter } from "next/navigation"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { HugeiconsIcon } from "@hugeicons/react"
import { Edit02Icon, Copy01Icon, Delete02Icon, ScissorIcon, VideoReplayIcon } from "@hugeicons/core-free-icons"
import type { Clip } from "@/infra/videos/videos"
import { TrimDialog } from "./trim-dialog"


interface ClipActionsProps {
  clip: Clip
  onRename: (clipId: string, title: string) => void
  onDuplicate: (clipId: string) => void
  onDelete: (clipId: string) => void
}

export function ClipActions({ clip, onRename, onDuplicate, onDelete }: ClipActionsProps) {
  const router = useRouter()
  const [renameDialogOpen, setRenameDialogOpen] = useState(false)
  const [renameTitle, setRenameTitle] = useState(clip.title)
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false)
  const [trimDialogOpen, setTrimDialogOpen] = useState(false)

  const videoId = useMemo(() => {
    if (typeof window === "undefined") return ""
    const parts = window.location.pathname.split("/").filter(Boolean)
    const clipsIdx = parts.indexOf("clips")
    return clipsIdx >= 0 ? (parts[clipsIdx + 1] ?? "") : ""
  }, [])

  const handleRename = () => {
    if (renameTitle) {
      onRename(clip.clip_id, renameTitle)
      setRenameDialogOpen(false)
    }
  }

  const handleDelete = () => {
    onDelete(clip.clip_id)
    setDeleteDialogOpen(false)
  }

  return (
    <>
      <div className="flex flex-row lg:flex-col gap-3 shrink-0 lg:pt-2 w-full lg:w-auto overflow-x-auto lg:overflow-visible">
        <ActionButton
          icon={<HugeiconsIcon icon={Edit02Icon} size={16} />}
          label="Renomear"
          variant="default"
          onClick={() => setRenameDialogOpen(true)}
        />
        <ActionButton
          icon={<HugeiconsIcon icon={Copy01Icon} size={16} />}
          label="Duplicar"
          variant="default"
          onClick={() => onDuplicate(clip.clip_id)}
        />
        <ActionButton
          icon={<HugeiconsIcon icon={VideoReplayIcon} size={16} />}
          label="Aparar"
          variant="default"
          onClick={() => setTrimDialogOpen(true)}
        />
        <ActionButton
          icon={<HugeiconsIcon icon={ScissorIcon} size={16} />}
          label="Editar"
          variant="default"
          onClick={() => {
            try {
              sessionStorage.setItem(`clip-edit:${videoId}`, clip.clip_id)
            } catch {
            }
            router.push(`/clips/${videoId}/edit`)
          }}
        />
        <ActionButton
          icon={<HugeiconsIcon icon={Delete02Icon} size={16} />}
          label="Deletar"
          variant="danger"
          onClick={() => setDeleteDialogOpen(true)}
        />
      </div>

      {/* Rename Dialog */}
      <Dialog open={renameDialogOpen} onOpenChange={setRenameDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Renomear Clip</DialogTitle>
            <DialogDescription>Digite o novo título para o clip</DialogDescription>
          </DialogHeader>
          <Input
            value={renameTitle}
            onChange={(e) => setRenameTitle(e.target.value)}
            placeholder="Novo título"
          />
          <div className="flex gap-2 justify-end">
            <Button variant="outline" onClick={() => setRenameDialogOpen(false)}>
              Cancelar
            </Button>
            <Button onClick={handleRename}>
              Renomear
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Delete Dialog */}
      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Deletar Clip</AlertDialogTitle>
            <AlertDialogDescription>
              Tem certeza que deseja deletar este clip? Esta ação não pode ser desfeita.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancelar</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleDelete}
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              Deletar
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <TrimDialog
        open={trimDialogOpen}
        onOpenChange={setTrimDialogOpen}
        clip={clip}
        videoId={videoId}
      />
    </>
  )
}

function ActionButton({ icon, label, variant = "default", onClick }: { icon: React.ReactNode, label: string, variant?: "default" | "danger", onClick?: () => void }) {
  return (
    <Button
      variant={variant === "danger" ? "destructive" : "secondary"}
      className="justify-start gap-3 w-full lg:w-32"
      onClick={onClick}
    >
      {icon}
      <span>{label}</span>
    </Button>
  )
}
