"use client"

import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription, SheetFooter } from "@/components/ui/sheet"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { SchedulePicker } from "@/components/ui/schedule-picker"
import { Textarea } from "@/components/ui/textarea"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { HugeiconsIcon } from "@hugeicons/react"
import { Upload04Icon } from "@hugeicons/core-free-icons"

interface PublishSheetProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  description: string
  onDescriptionChange: (value: string) => void
  visibility: "public" | "private" | "friends"
  onVisibilityChange: (value: "public" | "private" | "friends") => void
  allowComments: boolean
  onAllowCommentsChange: (value: boolean) => void
  allowDuets: boolean
  onAllowDuetsChange: (value: boolean) => void
  allowStitch: boolean
  onAllowStitchChange: (value: boolean) => void
  scheduleAt: string
  onScheduleAtChange: (value: string) => void
}

export function PublishSheet({
  open,
  onOpenChange,
  description,
  onDescriptionChange,
  visibility,
  onVisibilityChange,
  allowComments,
  onAllowCommentsChange,
  allowDuets,
  onAllowDuetsChange,
  allowStitch,
  onAllowStitchChange,
  scheduleAt,
  onScheduleAtChange,
}: PublishSheetProps) {
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side="right"
        className="sm:min-w-3xl w-full gap-0 p-0"
        showCloseButton={false}
      >
        <div className="flex h-full">
          <div className="border-b sm:border-b-0 border-border p-4">
            <SheetHeader className="p-0">
              <SheetTitle>Publicar no social</SheetTitle>
              <SheetDescription className="sr-only">Publicar clip</SheetDescription>
            </SheetHeader>

            <div className="mt-4 space-y-3">
              <div className="flex items-center gap-3">
                <Checkbox />
                <div className="relative">
                  <Avatar className="h-8 w-8">
                    <AvatarImage src="https://avatars.githubusercontent.com/u/142619236?v=4" alt="account" />
                    <AvatarFallback>SK</AvatarFallback>
                  </Avatar>
                  <img src="/social/tiktok.svg" alt="TikTok" className="absolute bottom-0 right-0 h-4 w-4" />
                </div>
                <div className="min-w-0">
                  <div className="text-sm font-medium truncate">skrodrigo</div>
                  <div className="text-xs text-muted-foreground truncate">@skrodrigo</div>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <Checkbox />
                <div className="relative">
                  <Avatar className="h-8 w-8">
                    <AvatarImage src="https://avatars.githubusercontent.com/u/142619236?v=4" alt="account" />
                    <AvatarFallback>SK</AvatarFallback>
                  </Avatar>
                  <img src="/social/shorts.svg" alt="Shorts" className="absolute bottom-0 right-0 h-4 w-4" />
                </div>
                <div className="min-w-0">
                  <div className="text-sm font-medium truncate">Rodrigo Carvalho</div>
                  <div className="text-xs text-muted-foreground truncate">@srkdg</div>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <Checkbox />
                <div className="relative">
                  <Avatar className="h-8 w-8">
                    <AvatarImage src="https://avatars.githubusercontent.com/u/142619236?v=4" alt="account" />
                    <AvatarFallback>SK</AvatarFallback>
                  </Avatar>
                  <img src="/social/instagram.svg" alt="Instagram" className="absolute bottom-0 right-0 h-4 w-4" />
                </div>
                <div className="min-w-0">
                  <div className="text-sm font-medium truncate">Rodrigo Carvalho</div>
                  <div className="text-xs text-muted-foreground truncate">@srkdg</div>
                </div>
              </div>

              <Button variant="secondary" className="w-full justify-center" size="sm">
                Manage Accounts
              </Button>
            </div>
          </div>
          <div className="p-4 flex-1 space-y-6 bg-background border border-r-0 my-6 rounded-l-lg">
            <div className="space-y-2">
              <div className="text-sm font-medium">Descrição</div>
              <Textarea
                value={description}
                onChange={(e) => onDescriptionChange(e.target.value)}
                placeholder="#Frontend #Desenvolvimento #AIEnhancement #Programacao #React"
                className="min-h-28"
              />
            </div>

            <div className="space-y-2">
              <div className="text-sm font-medium">Visibilidade</div>
              <Tabs value={visibility} onValueChange={(v) => {
                if (v === "public" || v === "private" || v === "friends") onVisibilityChange(v)
              }} className="w-full">
                <TabsList className='w-full h-10'>
                  <TabsTrigger value="public" className="flex-1 justify-center">Public</TabsTrigger>
                  <TabsTrigger value="private" className="flex-1 justify-center">Private</TabsTrigger>
                  <TabsTrigger value="friends" className="flex-1 justify-center">Friends</TabsTrigger>
                </TabsList>
              </Tabs>
            </div>

            <div className="space-y-2">
              <div className="text-sm font-medium">Allow</div>
              <div className="space-y-2">
                <label className="flex items-center gap-2 text-sm">
                  <Checkbox checked={allowComments} onCheckedChange={(v) => onAllowCommentsChange(Boolean(v))} />
                  comentários
                </label>
                <label className="flex items-center gap-2 text-sm">
                  <Checkbox checked={allowDuets} onCheckedChange={(v) => onAllowDuetsChange(Boolean(v))} />
                  Duets
                </label>
                <label className="flex items-center gap-2 text-sm">
                  <Checkbox checked={allowStitch} onCheckedChange={(v) => onAllowStitchChange(Boolean(v))} />
                  Stitch
                </label>
              </div>
            </div>

            <div className="space-y-2">
              <div className="text-sm font-medium">Thumbnail</div>
              <div className="flex items-center gap-3">
                <div className="h-14 w-10 rounded-md border border-border bg-card flex items-center justify-center">
                  <HugeiconsIcon icon={Upload04Icon} size={16} />
                </div>
              </div>
            </div>
          </div>
        </div>
        <div className="flex p-4 items-center justify-between w-full">
          <Button variant="secondary" onClick={() => onOpenChange(false)} className="order-last sm:order-first">
            Cancelar
          </Button>
          <div className="flex flex-col sm:flex-row gap-2 sm:items-center">
            <SchedulePicker value={scheduleAt} onChange={onScheduleAtChange} />
            <Button className="bg-primary text-white" onClick={() => onOpenChange(false)}>
              Publicar
            </Button>
          </div>
        </div>
      </SheetContent>
    </Sheet>
  )
}
